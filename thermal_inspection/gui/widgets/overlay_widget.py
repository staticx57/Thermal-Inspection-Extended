"""
Inspection overlay widget for drawing ROIs, hot spots, cold spots, and anomalies.
Replaces AlertOverlayWidget from ADAS system.
"""

import logging
import time
from typing import List, Optional

from PyQt6.QtWidgets import QWidget, QMenu
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPainter, QPen, QColor, QPolygon

from thermal_inspection.processing.roi_manager import ROI, ROIType
from thermal_inspection.processing.thermal_analyzer import HotSpot, ColdSpot, ThermalAnomaly
from thermal_inspection.gui.widgets.colorbar_widget import ColorbarWidget

logger = logging.getLogger(__name__)


class InspectionOverlayWidget(QWidget):
    """
    Overlay widget for drawing ROIs, hot spots, cold spots, and anomalies.
    Replaces AlertOverlayWidget from ADAS system.
    """

    # Signals for ROI drawing
    roi_created = pyqtSignal(object)  # Emits newly created ROI
    roi_selected = pyqtSignal(str)    # Emits selected ROI ID
    spot_meter_clicked = pyqtSignal(int, int)  # Emits (x, y) coordinates of spot meter click
    # Signals for mode changes (to sync button states)
    spot_meter_mode_changed = pyqtSignal(bool)  # Emitted when spot meter mode changes internally
    drawing_mode_changed = pyqtSignal(bool)     # Emitted when drawing mode changes internally

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.setStyleSheet("background: transparent;")

        self.rois: List[ROI] = []
        self.hot_spots: List[HotSpot] = []
        self.cold_spots: List[ColdSpot] = []
        self.anomalies: List[ThermalAnomaly] = []
        self.selected_roi_id: Optional[str] = None
        self.show_detection_info = False

        # Multi-select support
        self.selected_roi_ids: set = set()

        # Measurement points
        self.measurement_points: List = []
        self.spot_meter_mode = False

        # ROI drawing state
        self.drawing_mode = False
        self.drawing_type = ROIType.RECTANGLE
        self.draw_start_pos = None
        self.draw_current_pos = None
        self.temp_polygon_points = []

        # Coordinate transformation for scaled video
        self.frame_size = (640, 512)
        self.thermal_resolution = (640, 512)
        self.scale = 1.0
        self.offset_x = 0
        self.offset_y = 0

        # View mode and fusion settings for coordinate transformation
        self.current_view_mode = 'thermal'
        self.fusion_priority = 'thermal'
        self.pip_rect = None
        self.pip_thermal_rect = None

        # Temperature unit for hot/cold spot display
        self.current_temp_unit = 'C'

        # Individual toggles for each detection type
        self.show_hot_spots = True
        self.show_cold_spots = True
        self.show_anomalies = True

        # Cursor temperature readout
        self.cursor_enabled = False
        self.cursor_x = 0
        self.cursor_y = 0
        self.cursor_temp = None
        self.temp_map = None
        self.temp_map_unit = " (raw)"

        # Colorbar/Legend
        self.colorbar = ColorbarWidget(self)
        self.colorbar.set_enabled(True)
        self.colorbar.set_position("right")

        # Spot Meter Difference Mode
        self.comparison_spot1_id = None
        self.comparison_spot2_id = None
        self.comparison_delta = 0.0

        # Grid Overlay
        self.grid_enabled = False
        self.grid_spacing_x = 50
        self.grid_spacing_y = 50
        self.grid_color = QColor(255, 255, 255, 128)

    def set_view_mode(self, mode: str, fusion_priority: str = 'rgb', pip_size: float = 0.25):
        """Set current view mode for proper detection overlay handling."""
        logger.info(f"[OVERLAY] set_view_mode called: mode='{mode}', fusion_priority='{fusion_priority}'")
        self.current_view_mode = mode
        self.fusion_priority = fusion_priority

        if mode == 'picture_in_picture':
            frame_w, frame_h = self.frame_size
            margin = 10
            pip_allocated_w = int(frame_w * pip_size)
            pip_allocated_h = int(frame_h * pip_size)

            x = frame_w - pip_allocated_w - margin
            y = margin

            if hasattr(self, 'thermal_resolution') and self.thermal_resolution:
                tw, th = self.thermal_resolution
                actual_w, actual_h, offset_x, offset_y = self._calculate_aspect_ratio_fit(
                    tw, th, pip_allocated_w, pip_allocated_h
                )

                self.pip_rect = (x, y, pip_allocated_w, pip_allocated_h)
                self.pip_thermal_rect = (
                    x + offset_x,
                    y + offset_y,
                    actual_w,
                    actual_h
                )
                logger.info(f"[OVERLAY] PIP mode: allocated=({x},{y},{pip_allocated_w},{pip_allocated_h}), "
                           f"thermal_actual=({x+offset_x},{y+offset_y},{actual_w},{actual_h})")
            else:
                self.pip_rect = (x, y, pip_allocated_w, pip_allocated_h)
                self.pip_thermal_rect = self.pip_rect
        else:
            self.pip_rect = None
            self.pip_thermal_rect = None

        self.update()

    def set_thermal_resolution(self, w: int, h: int):
        """Set thermal sensor resolution for coordinate scaling."""
        self.thermal_resolution = (w, h)

    def set_temp_map(self, temp_map, unit=" (raw)"):
        """Set cached temperature map for cursor readout."""
        self.temp_map = temp_map
        self.temp_map_unit = unit

    def set_cursor_enabled(self, enabled: bool):
        """Enable or disable cursor temperature readout."""
        self.cursor_enabled = enabled
        if enabled:
            self.setMouseTracking(True)
        else:
            self.setMouseTracking(False)
        self.update()

    def _should_draw_thermal_overlays(self) -> bool:
        """Check if thermal-based overlays should be drawn in current view mode."""
        if self.current_view_mode == 'rgb':
            return False
        return True

    def _calculate_aspect_ratio_fit(self, src_w: float, src_h: float, dst_w: float, dst_h: float) -> tuple:
        """Calculate actual displayed size and offset when fitting source into destination."""
        if src_w == 0 or src_h == 0 or dst_w == 0 or dst_h == 0:
            return (dst_w, dst_h, 0, 0)

        src_aspect = src_w / src_h
        dst_aspect = dst_w / dst_h

        if src_aspect > dst_aspect:
            actual_w = dst_w
            actual_h = dst_w / src_aspect
            offset_x = 0
            offset_y = (dst_h - actual_h) / 2
        else:
            actual_h = dst_h
            actual_w = dst_h * src_aspect
            offset_x = (dst_w - actual_w) / 2
            offset_y = 0

        return (actual_w, actual_h, offset_x, offset_y)

    def _transform_thermal_coords(self, x: float, y: float) -> tuple:
        """Transform thermal sensor coordinates to display coordinates."""
        if not hasattr(self, 'thermal_resolution') or not self.thermal_resolution:
            logger.warning("[OVERLAY] thermal_resolution not set! Using default 640x512.")
            self.thermal_resolution = (640, 512)

        tw, th = self.thermal_resolution
        fw, fh = self.frame_size

        if tw == 0 or th == 0 or fw == 0 or fh == 0:
            return self.frame_to_widget(x, y)

        if self.current_view_mode == 'side_by_side':
            # FusionProcessor._side_by_side() does `np.hstack([thermal, rgb])`
            # (or the reverse) after only matching heights — each panel keeps
            # its own native width. There is no 50/50 split and no letterbox
            # fit, so the thermal panel is thermal's native resolution,
            # unscaled, at whichever end fusion_priority puts it.
            if self.fusion_priority == 'thermal':
                thermal_start = 0  # thermal on left
            else:
                thermal_start = fw - tw  # thermal on right

            frame_x = thermal_start + x
            frame_y = y

            return self.frame_to_widget(frame_x, frame_y)

        elif self.pip_rect is not None:
            if self.fusion_priority == 'thermal':
                scale_x = fw / tw
                scale_y = fh / th
                frame_x = x * scale_x
                frame_y = y * scale_y
                return self.frame_to_widget(frame_x, frame_y)
            else:
                if hasattr(self, 'pip_thermal_rect') and self.pip_thermal_rect is not None:
                    pip_x, pip_y, pip_w, pip_h = self.pip_thermal_rect
                    scale_x = pip_w / tw
                    scale_y = pip_h / th
                    offset_x = 0
                    offset_y = 0
                else:
                    pip_x, pip_y, pip_allocated_w, pip_allocated_h = self.pip_rect
                    pip_w, pip_h, offset_x, offset_y = self._calculate_aspect_ratio_fit(
                        tw, th, pip_allocated_w, pip_allocated_h
                    )
                    pip_x += offset_x
                    pip_y += offset_y
                    scale_x = pip_w / tw
                    scale_y = pip_h / th

                frame_x = pip_x + (x * scale_x)
                frame_y = pip_y + (y * scale_y)

                if 200 <= x <= 450 and 150 <= y <= 350:
                    logger.info(f"[OVERLAY] PIP transform: input=({x:.1f},{y:.1f}), priority={self.fusion_priority}")

                return self.frame_to_widget(frame_x, frame_y)

        else:
            scale_x = fw / tw
            scale_y = fh / th
            frame_x = x * scale_x
            frame_y = y * scale_y
            return self.frame_to_widget(frame_x, frame_y)

    def set_spot_meter_mode(self, enabled: bool, emit_signal: bool = True):
        """Enable or disable spot metering mode."""
        self.spot_meter_mode = enabled
        if emit_signal:
            self.spot_meter_mode_changed.emit(enabled)
        if enabled:
            self.setCursor(Qt.CursorShape.CrossCursor)
        else:
            self.unsetCursor()

    def update_rois(self, rois: List[ROI]):
        """Update ROI list for visualization."""
        self.rois = rois
        self.update()

    def update_thermal_detections(self, hot_spots: List[HotSpot], cold_spots: List[ColdSpot], anomalies: List[ThermalAnomaly]):
        """Update thermal detection results."""
        self.hot_spots = hot_spots
        self.cold_spots = cold_spots
        self.anomalies = anomalies
        self.update()

    def update_measurement_points(self, points: List):
        """Update measurement points for visualization."""
        self.measurement_points = points
        self.update()

    def set_frame_transform(self, frame_width: int, frame_height: int, pixmap_width: int, pixmap_height: int, widget_width: int, widget_height: int):
        """Update coordinate transformation parameters."""
        self.frame_size = (frame_width, frame_height)
        self.scale = pixmap_width / frame_width
        self.offset_x = (widget_width - pixmap_width) // 2
        self.offset_y = (widget_height - pixmap_height) // 2

        if self.current_view_mode == 'picture_in_picture':
            pip_size = 0.25
            margin = 10
            pip_allocated_w = int(frame_width * pip_size)
            pip_allocated_h = int(frame_height * pip_size)
            x = frame_width - pip_allocated_w - margin
            y = margin

            if self.fusion_priority == 'rgb':
                if hasattr(self, 'thermal_resolution') and self.thermal_resolution:
                    tw, th = self.thermal_resolution
                    actual_w, actual_h, offset_x, offset_y = self._calculate_aspect_ratio_fit(
                        tw, th, pip_allocated_w, pip_allocated_h
                    )
                    self.pip_rect = (x, y, pip_allocated_w, pip_allocated_h)
                    self.pip_thermal_rect = (
                        x + offset_x,
                        y + offset_y,
                        actual_w,
                        actual_h
                    )
                else:
                    self.pip_rect = (x, y, pip_allocated_w, pip_allocated_h)
                    self.pip_thermal_rect = self.pip_rect
            else:
                self.pip_rect = None
                self.pip_thermal_rect = None
            logger.info(f"[OVERLAY] PIP rect recalculated: allocated={self.pip_rect}, thermal_actual={self.pip_thermal_rect}")

    def frame_to_widget(self, x: float, y: float) -> tuple:
        """Convert frame coordinates to widget coordinates."""
        widget_x = int(x * self.scale + self.offset_x)
        widget_y = int(y * self.scale + self.offset_y)
        return (widget_x, widget_y)

    def widget_to_frame(self, x: float, y: float) -> tuple:
        """Convert widget coordinates to frame coordinates."""
        frame_x = int((x - self.offset_x) / self.scale)
        frame_y = int((y - self.offset_y) / self.scale)
        return (frame_x, frame_y)

    def enterEvent(self, event):
        """Mouse entered the overlay widget."""
        super().enterEvent(event)

    def set_selected_roi(self, roi_id: Optional[str]):
        """Highlight a specific ROI."""
        self.selected_roi_id = roi_id
        self.update()

    def _format_temperature_with_unit(self, temp_celsius: float, original_unit: str, raw_value: Optional[float] = None) -> tuple:
        """Convert temperature to current unit and return with unit symbol."""
        if "(raw)" in original_unit:
            if self.current_temp_unit == 'RAW':
                return (temp_celsius, " (raw)")
            else:
                return (temp_celsius, " (AGC)")

        if self.current_temp_unit == 'RAW':
            if raw_value is not None:
                return (raw_value, " (Y16)")
            else:
                return (temp_celsius, "°C")

        if (self.current_temp_unit == 'C' and "C" in original_unit) or \
           (self.current_temp_unit == 'F' and "F" in original_unit) or \
           (self.current_temp_unit == 'K' and "K" in original_unit):
            return (temp_celsius, original_unit)

        if "F" in original_unit:
            temp_celsius = (temp_celsius - 32) * 5/9
        elif "K" in original_unit:
            temp_celsius = temp_celsius - 273.15

        if self.current_temp_unit == 'C':
            return (temp_celsius, "°C")
        elif self.current_temp_unit == 'F':
            temp_f = temp_celsius * 9/5 + 32
            return (temp_f, "°F")
        elif self.current_temp_unit == 'K':
            temp_k = temp_celsius + 273.15
            return (temp_k, "K")

        return (temp_celsius, "°C")

    def set_temperature_unit(self, unit: str):
        """Set the temperature unit for display (C/F/K/RAW)."""
        self.current_temp_unit = unit
        self.update()

    def paintEvent(self, event):
        """Draw ROIs and thermal detections."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        def draw_label(x, y, text, color):
            font_metrics = painter.fontMetrics()
            rect = font_metrics.boundingRect(text)
            rect.adjust(-2, -2, 2, 2)
            rect.moveTo(x, y - rect.height() + 2)

            painter.setBrush(QColor(0, 0, 0, 160))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRect(rect)

            painter.setPen(QPen(color, 1))
            painter.drawText(x, y, text)

        # Draw grid overlay
        if self.grid_enabled and self._should_draw_thermal_overlays():
            painter.setPen(QPen(self.grid_color, 1, Qt.PenStyle.DashLine))

            if hasattr(self, 'thermal_resolution') and self.thermal_resolution:
                tw, th = self.thermal_resolution
            else:
                tw = self.frame_size[0]
                th = self.frame_size[1]

            x = 0
            while x <= tw:
                wx1, wy1 = self._transform_thermal_coords(x, 0)
                wx2, wy2 = self._transform_thermal_coords(x, th)
                painter.drawLine(int(wx1), int(wy1), int(wx2), int(wy2))
                x += self.grid_spacing_x

            y = 0
            while y <= th:
                wx1, wy1 = self._transform_thermal_coords(0, y)
                wx2, wy2 = self._transform_thermal_coords(tw, y)
                painter.drawLine(int(wx1), int(wy1), int(wx2), int(wy2))
                y += self.grid_spacing_y

        # Draw ROIs
        for roi in self.rois:
            is_selected = roi.roi_id in self.selected_roi_ids or roi.roi_id == self.selected_roi_id

            if is_selected:
                color = QColor(0, 255, 255)
                thickness = 3
            elif roi.roi_type == ROIType.RECTANGLE:
                color = QColor(0, 255, 0)
                thickness = 2
            elif roi.roi_type == ROIType.POLYGON:
                color = QColor(255, 255, 0)
                thickness = 2
            elif roi.roi_type == ROIType.ELLIPSE:
                color = QColor(255, 128, 0)
                thickness = 2
            elif roi.roi_type == ROIType.CIRCLE:
                color = QColor(128, 0, 255)
                thickness = 2
            else:
                color = QColor(255, 255, 255)
                thickness = 2

            pen = QPen(color, thickness)

            if is_selected and roi.roi_id != self.selected_roi_id:
                pen.setStyle(Qt.PenStyle.DashLine)

            painter.setPen(pen)

            if roi.roi_type == ROIType.RECTANGLE:
                x, y, w, h = roi.get_bbox()
                wx1, wy1 = self.frame_to_widget(x, y)
                wx2, wy2 = self.frame_to_widget(x + w, y + h)
                painter.drawRect(wx1, wy1, wx2 - wx1, wy2 - wy1)
            elif roi.roi_type == ROIType.POLYGON:
                from PyQt6.QtCore import QPoint
                points = [QPoint(int(self.frame_to_widget(p[0], p[1])[0]),
                                int(self.frame_to_widget(p[0], p[1])[1])) for p in roi.points]
                painter.drawPolygon(QPolygon(points))
            elif roi.roi_type == ROIType.ELLIPSE:
                x, y, w, h = roi.get_bbox()
                wx1, wy1 = self.frame_to_widget(x, y)
                wx2, wy2 = self.frame_to_widget(x + w, y + h)
                painter.drawEllipse(wx1, wy1, wx2 - wx1, wy2 - wy1)
            elif roi.roi_type == ROIType.CIRCLE:
                x, y, w, h = roi.get_bbox()
                wx1, wy1 = self.frame_to_widget(x, y)
                wx2, wy2 = self.frame_to_widget(x + w, y + h)
                ww = wx2 - wx1
                radius = int(ww / 2)
                center_x = int(wx1 + radius)
                center_y = int(wy1 + radius)
                painter.drawEllipse(center_x - radius, center_y - radius, radius * 2, radius * 2)

            if roi.label:
                display_text = roi.label
                if roi.custom_palette:
                    display_text += f" [{roi.custom_palette}]"

                x, y, _, _ = roi.get_bbox()
                wx, wy = self.frame_to_widget(x, y)
                draw_label(int(wx), int(wy) - 5, display_text, color)

        # Draw hot spots
        if self.show_hot_spots and self._should_draw_thermal_overlays():
            for hot_spot in self.hot_spots:
                painter.setPen(QPen(QColor(255, 0, 0), 2))
                x, y = hot_spot.centroid
                wx, wy = self._transform_thermal_coords(x, y)
                painter.drawEllipse(int(wx) - 5, int(wy) - 5, 10, 10)
                temp_val, unit_symbol = self._format_temperature_with_unit(
                    hot_spot.max_temp, hot_spot.unit, hot_spot.raw_value)
                draw_label(int(wx) + 10, int(wy), f"{temp_val:.1f}{unit_symbol}", QColor(255, 100, 100))

        # Draw cold spots
        if self.show_cold_spots and self._should_draw_thermal_overlays():
            for cold_spot in self.cold_spots:
                painter.setPen(QPen(QColor(0, 128, 255), 2))
                x, y = cold_spot.centroid
                wx, wy = self._transform_thermal_coords(x, y)
                painter.drawEllipse(int(wx) - 5, int(wy) - 5, 10, 10)
                temp_val, unit_symbol = self._format_temperature_with_unit(
                    cold_spot.min_temp, cold_spot.unit, cold_spot.raw_value)
                draw_label(int(wx) + 10, int(wy), f"{temp_val:.1f}{unit_symbol}", QColor(100, 200, 255))

        # Draw anomalies
        if self.show_anomalies and self._should_draw_thermal_overlays():
            for anomaly in self.anomalies:
                painter.setPen(QPen(QColor(255, 255, 0), 3))
                x, y = anomaly.location
                wx, wy = self._transform_thermal_coords(x, y)
                painter.drawLine(int(wx), int(wy) - 10, int(wx) - 8, int(wy) + 6)
                painter.drawLine(int(wx) - 8, int(wy) + 6, int(wx) + 8, int(wy) + 6)
                painter.drawLine(int(wx) + 8, int(wy) + 6, int(wx), int(wy) - 10)

                label_text = f"⚠ {anomaly.description}" if anomaly.description else f"⚠ {anomaly.anomaly_type.value}"
                draw_label(int(wx) + 15, int(wy), label_text, QColor(255, 255, 0))

        # Draw measurement points (spot meters)
        if self._should_draw_thermal_overlays():
            for i, point in enumerate(self.measurement_points):
                wx, wy = self._transform_thermal_coords(point.x, point.y)

                if i == 4 and self.current_view_mode == 'picture_in_picture':
                    logger.info(f"[SPOT DEBUG] Center spot: input=({point.x},{point.y}), output=({wx},{wy})")

                should_flash = False
                if hasattr(self, 'analysis_panel') and hasattr(self.analysis_panel, 'spot_meter_panel'):
                    spot_data = self.analysis_panel.spot_meter_panel.get_spot(point.point_id)
                    if spot_data and spot_data.alert:
                        if spot_data.alert.triggered and spot_data.alert.flash_enabled:
                            should_flash = True

                r, g, b = point.color

                if should_flash:
                    flash_on = int(time.time() * 2) % 2 == 0
                    if flash_on:
                        r, g, b = 255, 0, 0

                point_color = QColor(r, g, b)
                painter.setPen(QPen(point_color, 2))
                painter.setBrush(QColor(r, g, b, 100))

                painter.drawEllipse(int(wx) - 5, int(wy) - 5, 10, 10)

                if point.temperature is not None:
                    unit = getattr(point, 'unit', '')
                    label_text = f"{point.label}: {point.temperature:.1f}{unit}"
                else:
                    label_text = f"{point.label}: --"
                draw_label(int(wx) + 12, int(wy) + 5, label_text, point_color)

        # Draw spot meter comparison line
        if self.comparison_spot1_id and self.comparison_spot2_id and self._should_draw_thermal_overlays():
            spot1 = None
            spot2 = None
            for point in self.measurement_points:
                if self.comparison_spot1_id in str(point.label) or f"_{int(point.x)}_{int(point.y)}" in self.comparison_spot1_id:
                    spot1 = point
                if self.comparison_spot2_id in str(point.label) or f"_{int(point.x)}_{int(point.y)}" in self.comparison_spot2_id:
                    spot2 = point

            if spot1 and spot2:
                wx1, wy1 = self._transform_thermal_coords(spot1.x, spot1.y)
                wx2, wy2 = self._transform_thermal_coords(spot2.x, spot2.y)

                painter.setPen(QPen(QColor(255, 255, 0), 2, Qt.PenStyle.DashLine))
                painter.drawLine(int(wx1), int(wy1), int(wx2), int(wy2))

                mid_x = (wx1 + wx2) / 2
                mid_y = (wy1 + wy2) / 2

                delta_sign = "+" if self.comparison_delta >= 0 else ""
                delta_text = f"Δ{delta_sign}{self.comparison_delta:.1f}°C"

                draw_label(int(mid_x), int(mid_y), delta_text, QColor(255, 255, 0))

        # Draw cursor temperature readout (topmost layer)
        if self.cursor_enabled and self.cursor_temp is not None and self._should_draw_thermal_overlays():
            wx, wy = self._transform_thermal_coords(self.cursor_x, self.cursor_y)

            painter.setPen(QPen(QColor(255, 255, 0), 1, Qt.PenStyle.DashLine))
            cross_size = 20
            painter.drawLine(int(wx) - cross_size, int(wy), int(wx) + cross_size, int(wy))
            painter.drawLine(int(wx), int(wy) - cross_size, int(wx), int(wy) + cross_size)

            temp_display, unit = self._format_temperature_with_unit(self.cursor_temp, self.temp_map_unit)
            label_text = f"{temp_display}{unit}"
            draw_label(int(wx) + 25, int(wy) - 10, label_text, QColor(255, 255, 0))

        # Draw temporary ROI being created
        if self.drawing_mode and self.draw_start_pos and self.draw_current_pos:
            painter.setPen(QPen(QColor(255, 255, 0), 2, Qt.PenStyle.DashLine))

            if self.drawing_type == ROIType.RECTANGLE:
                x = min(self.draw_start_pos.x(), self.draw_current_pos.x())
                y = min(self.draw_start_pos.y(), self.draw_current_pos.y())
                w = abs(self.draw_current_pos.x() - self.draw_start_pos.x())
                h = abs(self.draw_current_pos.y() - self.draw_start_pos.y())
                painter.drawRect(x, y, w, h)

            elif self.drawing_type == ROIType.ELLIPSE:
                x = min(self.draw_start_pos.x(), self.draw_current_pos.x())
                y = min(self.draw_start_pos.y(), self.draw_current_pos.y())
                w = abs(self.draw_current_pos.x() - self.draw_start_pos.x())
                h = abs(self.draw_current_pos.y() - self.draw_start_pos.y())
                painter.drawEllipse(x, y, w, h)

            elif self.drawing_type == ROIType.CIRCLE:
                center_x = self.draw_start_pos.x()
                center_y = self.draw_start_pos.y()
                radius = int(((self.draw_current_pos.x() - center_x) ** 2 +
                             (self.draw_current_pos.y() - center_y) ** 2) ** 0.5)
                painter.drawEllipse(center_x - radius, center_y - radius, radius * 2, radius * 2)

            elif self.drawing_type == ROIType.POLYGON and self.temp_polygon_points:
                from PyQt6.QtCore import QPoint
                points = self.temp_polygon_points + [self.draw_current_pos]
                for i in range(len(points) - 1):
                    painter.drawLine(points[i], points[i + 1])

    def enable_drawing_mode(self, roi_type: ROIType = ROIType.RECTANGLE):
        """Enable ROI drawing mode."""
        if self.spot_meter_mode:
            self.set_spot_meter_mode(False)
        self.drawing_mode = True
        self.drawing_type = roi_type
        self.draw_start_pos = None
        self.draw_current_pos = None
        self.temp_polygon_points = []
        self.setCursor(Qt.CursorShape.CrossCursor)
        logger.info(f"Drawing mode enabled: {roi_type}")
        self.drawing_mode_changed.emit(True)

    def disable_drawing_mode(self):
        """Disable ROI drawing mode."""
        was_drawing = self.drawing_mode
        self.drawing_mode = False
        self.draw_start_pos = None
        self.draw_current_pos = None
        self.temp_polygon_points = []
        self.setCursor(Qt.CursorShape.ArrowCursor)
        logger.info("Drawing mode disabled")
        if was_drawing:
            self.drawing_mode_changed.emit(False)

    def set_show_detection_info(self, show: bool):
        """Toggle visibility of detection info."""
        self.show_detection_info = show
        self.update()

    def mousePressEvent(self, event):
        """Handle mouse press for ROI drawing and selection."""
        click_wx, click_wy = self.widget_to_frame(event.pos().x(), event.pos().y())
        click_x, click_y = click_wx, click_wy
        valid_click = True

        # Handle spot meter mode
        if self.spot_meter_mode:
            if self.current_view_mode == 'side_by_side':
                # Mirrors _transform_thermal_coords(): FusionProcessor._side_by_side()
                # hstacks the two panels at their own native widths (only height is
                # matched), so the thermal panel is thermal's native resolution,
                # unscaled, at whichever end fusion_priority puts it — not a 50/50
                # split with letterboxing.
                fw, fh = self.frame_size
                tw, th = self.thermal_resolution if self.thermal_resolution else (640, 512)

                if self.fusion_priority == 'thermal':
                    thermal_start = 0
                    thermal_in_region = (click_wx < tw)
                else:
                    thermal_start = fw - tw
                    thermal_in_region = (click_wx >= thermal_start)

                if thermal_in_region:
                    click_x = click_wx - thermal_start
                    click_y = click_wy
                    click_x = max(0, min(tw - 1, click_x))
                    click_y = max(0, min(th - 1, click_y))
                else:
                    logger.info("Clicked on RGB side in Side-by-Side mode - Ignoring spot meter add")
                    valid_click = False

            elif self.pip_rect is not None:
                fw, fh = self.frame_size
                tw, th = self.thermal_resolution if self.thermal_resolution else (640, 514)

                if self.fusion_priority == 'thermal':
                    # Thermal is the main image, allow clicks anywhere on main display
                    if fw > 0 and fh > 0:
                        click_x = click_wx * (tw / fw)
                        click_y = click_wy * (th / fh)
                        click_x = max(0, min(tw - 1, click_x))
                        click_y = max(0, min(th - 1, click_y))
                    else:
                        valid_click = False
                else:
                    # Thermal is in PIP, only accept clicks inside PIP region
                    if hasattr(self, 'pip_thermal_rect') and self.pip_thermal_rect is not None:
                        pip_x, pip_y, pip_w, pip_h = self.pip_thermal_rect
                    else:
                        pip_x, pip_y, pip_allocated_w, pip_allocated_h = self.pip_rect
                        actual_w, actual_h, offset_x, offset_y = self._calculate_aspect_ratio_fit(tw, th, pip_allocated_w, pip_allocated_h)
                        pip_x += offset_x
                        pip_y += offset_y
                        pip_w = actual_w
                        pip_h = actual_h

                    if (pip_x <= click_wx <= pip_x + pip_w) and (pip_y <= click_wy <= pip_y + pip_h):
                        scale_x = pip_w / tw
                        scale_y = pip_h / th
                        click_x = (click_wx - pip_x) / scale_x
                        click_y = (click_wy - pip_y) / scale_y
                        click_x = max(0, min(tw - 1, click_x))
                        click_y = max(0, min(th - 1, click_y))
                    else:
                        logger.info("Clicked outside thermal PIP region - Ignoring spot meter add")
                        valid_click = False

            elif hasattr(self, 'thermal_resolution') and self.thermal_resolution:
                tw, th = self.thermal_resolution
                fw, fh = self.frame_size
                if fw > 0 and fh > 0:
                    click_x = click_wx * (tw / fw)
                    click_y = click_wy * (th / fh)

            if valid_click:
                self.spot_meter_clicked.emit(int(click_x), int(click_y))

            event.accept()
            return

        if not self.drawing_mode:
            click_x, click_y = self.widget_to_frame(event.pos().x(), event.pos().y())
            modifiers = event.modifiers()
            ctrl_pressed = modifiers & Qt.KeyboardModifier.ControlModifier
            shift_pressed = modifiers & Qt.KeyboardModifier.ShiftModifier

            clicked_roi = None
            for roi in self.rois:
                if roi.contains_point((click_x, click_y)):
                    clicked_roi = roi
                    break

            if clicked_roi:
                if ctrl_pressed:
                    if clicked_roi.roi_id in self.selected_roi_ids:
                        self.selected_roi_ids.remove(clicked_roi.roi_id)
                    else:
                        self.selected_roi_ids.add(clicked_roi.roi_id)
                    self.set_selected_roi(clicked_roi.roi_id)
                    self.roi_selected.emit(clicked_roi.roi_id)

                elif shift_pressed:
                    if self.selected_roi_id:
                        try:
                            start_idx = next(i for i, r in enumerate(self.rois) if r.roi_id == self.selected_roi_id)
                            end_idx = next(i for i, r in enumerate(self.rois) if r.roi_id == clicked_roi.roi_id)
                            start, end = min(start_idx, end_idx), max(start_idx, end_idx)
                            for i in range(start, end + 1):
                                self.selected_roi_ids.add(self.rois[i].roi_id)
                        except StopIteration:
                            pass
                    self.set_selected_roi(clicked_roi.roi_id)
                    self.roi_selected.emit(clicked_roi.roi_id)
                else:
                    self.selected_roi_ids.clear()
                    self.selected_roi_ids.add(clicked_roi.roi_id)
                    self.set_selected_roi(clicked_roi.roi_id)
                    self.roi_selected.emit(clicked_roi.roi_id)

                self.update()
                event.accept()
            else:
                if not ctrl_pressed and not shift_pressed:
                    if self.selected_roi_ids or self.selected_roi_id:
                        self.selected_roi_ids.clear()
                        self.set_selected_roi(None)
                        self.update()
                        event.accept()
                    else:
                        event.ignore()
            return

        if self.drawing_type == ROIType.POLYGON:
            self.temp_polygon_points.append(event.pos())
            self.update()
        else:
            self.draw_start_pos = event.pos()
            self.draw_current_pos = event.pos()
            self.update()

    def mouseMoveEvent(self, event):
        """Handle mouse move for ROI drawing AND cursor temperature readout."""
        if self.drawing_mode and self.draw_start_pos:
            self.draw_current_pos = event.pos()
            self.update()

        super().mouseMoveEvent(event)

        if not self.cursor_enabled:
            return

        if self.temp_map is None:
            return

        if not self._should_draw_thermal_overlays():
            return

        wx, wy = event.pos().x(), event.pos().y()
        fx, fy = self.widget_to_frame(wx, wy)

        thermal_x, thermal_y = fx, fy
        valid_coords = True

        if self.current_view_mode == 'side_by_side':
            # See _transform_thermal_coords(): the thermal panel is thermal's
            # native resolution, unscaled — no 50/50 split or letterboxing.
            fw, fh = self.frame_size
            tw, th = self.thermal_resolution if self.thermal_resolution else (640, 512)

            if self.fusion_priority == 'thermal':
                thermal_start = 0
                thermal_in_region = (fx < tw)
            else:
                thermal_start = fw - tw
                thermal_in_region = (fx >= thermal_start)

            if thermal_in_region:
                thermal_x = fx - thermal_start
                thermal_y = fy
                thermal_x = max(0, min(tw - 1, thermal_x))
                thermal_y = max(0, min(th - 1, thermal_y))
            else:
                valid_coords = False

        elif self.pip_rect is not None:
            tw, th = self.thermal_resolution if self.thermal_resolution else (640, 514)

            if hasattr(self, 'pip_thermal_rect') and self.pip_thermal_rect is not None:
                pip_x, pip_y, pip_w, pip_h = self.pip_thermal_rect
            else:
                pip_x, pip_y, pip_allocated_w, pip_allocated_h = self.pip_rect
                actual_w, actual_h, offset_x, offset_y = self._calculate_aspect_ratio_fit(tw, th, pip_allocated_w, pip_allocated_h)
                pip_x += offset_x
                pip_y += offset_y
                pip_w = actual_w
                pip_h = actual_h

            if (pip_x <= fx <= pip_x + pip_w) and (pip_y <= fy <= pip_y + pip_h):
                scale_x = pip_w / tw
                scale_y = pip_h / th
                thermal_x = (fx - pip_x) / scale_x
                thermal_y = (fy - pip_y) / scale_y
                thermal_x = max(0, min(tw - 1, thermal_x))
                thermal_y = max(0, min(th - 1, thermal_y))
            else:
                valid_coords = False

        if valid_coords and self.temp_map is not None:
            h, w = self.temp_map.shape
            tx = int(thermal_x)
            ty = int(thermal_y)

            if 0 <= tx < w and 0 <= ty < h:
                self.cursor_x = thermal_x
                self.cursor_y = thermal_y
                self.cursor_temp = self.temp_map[ty, tx]
                self.update()
            else:
                self.cursor_temp = None
        else:
            self.cursor_temp = None

    def mouseReleaseEvent(self, event):
        """Handle mouse release to finalize ROI."""
        if not self.drawing_mode or not self.draw_start_pos:
            return

        if self.drawing_type == ROIType.POLYGON:
            return

        try:
            from thermal_inspection.processing.roi_manager import ROI, ROISource
            import uuid

            if self.drawing_type == ROIType.RECTANGLE:
                x = min(self.draw_start_pos.x(), event.pos().x())
                y = min(self.draw_start_pos.y(), event.pos().y())
                w = abs(event.pos().x() - self.draw_start_pos.x())
                h = abs(event.pos().y() - self.draw_start_pos.y())

                if w > 10 and h > 10:
                    fx1, fy1 = self.widget_to_frame(x, y)
                    fx2, fy2 = self.widget_to_frame(x + w, y + h)
                    points = [(fx1, fy1), (fx2, fy1), (fx2, fy2), (fx1, fy2)]
                    roi = ROI(
                        roi_id=str(uuid.uuid4()),
                        roi_type=ROIType.RECTANGLE,
                        roi_source=ROISource.MANUAL,
                        points=points,
                        label=f"ROI-{len(self.rois) + 1}"
                    )
                    self.roi_created.emit(roi)

            elif self.drawing_type == ROIType.ELLIPSE:
                x = min(self.draw_start_pos.x(), event.pos().x())
                y = min(self.draw_start_pos.y(), event.pos().y())
                w = abs(event.pos().x() - self.draw_start_pos.x())
                h = abs(event.pos().y() - self.draw_start_pos.y())

                if w > 10 and h > 10:
                    fx1, fy1 = self.widget_to_frame(x, y)
                    fx2, fy2 = self.widget_to_frame(x + w, y + h)
                    points = [(fx1, fy1), (fx2, fy1), (fx2, fy2), (fx1, fy2)]
                    roi = ROI(
                        roi_id=str(uuid.uuid4()),
                        roi_type=ROIType.ELLIPSE,
                        roi_source=ROISource.MANUAL,
                        points=points,
                        label=f"ROI-{len(self.rois) + 1}"
                    )
                    self.roi_created.emit(roi)

            elif self.drawing_type == ROIType.CIRCLE:
                center_x = self.draw_start_pos.x()
                center_y = self.draw_start_pos.y()
                radius = int(((event.pos().x() - center_x) ** 2 +
                             (event.pos().y() - center_y) ** 2) ** 0.5)

                if radius > 5:
                    fcx, fcy = self.widget_to_frame(center_x, center_y)
                    fpx, fpy = self.widget_to_frame(event.pos().x(), event.pos().y())

                    points = [(fcx, fcy), (fpx, fpy)]
                    roi = ROI(
                        roi_id=str(uuid.uuid4()),
                        roi_type=ROIType.CIRCLE,
                        roi_source=ROISource.MANUAL,
                        points=points,
                        label=f"ROI-{len(self.rois) + 1}"
                    )
                    self.roi_created.emit(roi)

        except Exception as e:
            logger.error(f"Error creating ROI: {e}", exc_info=True)

        self.draw_start_pos = None
        self.draw_current_pos = None
        self.update()

    def mouseDoubleClickEvent(self, event):
        """Handle double click to finalize polygon."""
        if self.drawing_mode and self.drawing_type == ROIType.POLYGON:
            if len(self.temp_polygon_points) > 2:
                try:
                    from thermal_inspection.processing.roi_manager import ROI, ROISource
                    import uuid

                    points = []
                    for p in self.temp_polygon_points:
                        fx, fy = self.widget_to_frame(p.x(), p.y())
                        points.append((fx, fy))

                    roi = ROI(
                        roi_id=str(uuid.uuid4()),
                        roi_type=ROIType.POLYGON,
                        roi_source=ROISource.MANUAL,
                        points=points,
                        label=f"ROI-{len(self.rois) + 1}"
                    )
                    self.roi_created.emit(roi)

                    self.temp_polygon_points = []
                    self.draw_start_pos = None
                    self.draw_current_pos = None
                    self.update()

                except Exception as e:
                    logger.error(f"Error creating polygon ROI: {e}", exc_info=True)

    def contextMenuEvent(self, event):
        """Show context menu for ROI operations."""
        if not self.selected_roi_id:
            return

        selected_roi = None
        for roi in self.rois:
            if roi.roi_id == self.selected_roi_id:
                selected_roi = roi
                break

        if not selected_roi:
            return

        menu = QMenu(self)
        num_selected = len(self.selected_roi_ids) if self.selected_roi_ids else 1

        if num_selected > 1:
            palette_menu = menu.addMenu(f"Set Palette ({num_selected} ROIs)")
        else:
            palette_menu = menu.addMenu("Set Palette")

        palettes = [
            ("white_hot", "White Hot"),
            ("black_hot", "Black Hot"),
            ("ironbow", "Ironbow"),
            ("rainbow", "Rainbow"),
            ("lava", "Lava"),
            ("arctic", "Arctic"),
            ("medical", "Medical"),
            ("plasma", "Plasma"),
            ("amber", "Amber"),
            ("gray", "Gray")
        ]

        for palette_id, palette_name in palettes:
            action = palette_menu.addAction(palette_name)
            action.triggered.connect(lambda checked, p=palette_id: self._set_roi_palette(p))

        clear_action = palette_menu.addAction("Clear Custom Palette")
        clear_action.triggered.connect(self._clear_roi_palette)

        menu.addSeparator()

        if num_selected > 1:
            delete_action = menu.addAction(f"Delete {num_selected} ROIs")
        else:
            delete_action = menu.addAction("Delete ROI")
        delete_action.triggered.connect(self._delete_selected_roi)

        menu.exec(event.globalPos())

    def _set_roi_palette(self, palette_name: str):
        """Set palette for all selected ROIs."""
        parent_window = self.window()
        if not hasattr(parent_window, '_on_roi_palette_changed'):
            return

        roi_ids = list(self.selected_roi_ids) if self.selected_roi_ids else [self.selected_roi_id]

        for roi_id in roi_ids:
            if roi_id:
                parent_window._on_roi_palette_changed(roi_id, palette_name)

        logger.info(f"Setting palette '{palette_name}' for {len(roi_ids)} ROI(s)")

    def _clear_roi_palette(self):
        """Clear custom palette for all selected ROIs."""
        parent_window = self.window()
        if not hasattr(parent_window, '_on_roi_palette_cleared'):
            return

        roi_ids = list(self.selected_roi_ids) if self.selected_roi_ids else [self.selected_roi_id]

        for roi_id in roi_ids:
            if roi_id:
                parent_window._on_roi_palette_cleared(roi_id)

        logger.info(f"Clearing custom palette for {len(roi_ids)} ROI(s)")

    def _delete_selected_roi(self):
        """Delete all selected ROIs."""
        parent_window = self.window()
        if not hasattr(parent_window, '_on_roi_delete'):
            return

        roi_ids = list(self.selected_roi_ids) if self.selected_roi_ids else [self.selected_roi_id]

        for roi_id in roi_ids:
            if roi_id:
                parent_window._on_roi_delete(roi_id)

        logger.info(f"Deleting {len(roi_ids)} ROI(s)")

        self.selected_roi_ids.clear()
        self.selected_roi_id = None
        self.update()

    def resizeEvent(self, event):
        """Handle resize to reposition colorbar."""
        super().resizeEvent(event)
        self._position_colorbar()

    def _position_colorbar(self):
        """Position the colorbar widget in the top-right corner."""
        if hasattr(self, 'colorbar') and self.colorbar:
            margin = 10
            x = self.width() - self.colorbar.width() - margin
            y = margin
            self.colorbar.move(x, y)
            self.colorbar.raise_()

    def update_colorbar_palette(self, palette_lut):
        """Update colorbar with new palette LUT."""
        if hasattr(self, 'colorbar') and self.colorbar:
            self.colorbar.set_palette_lut(palette_lut)

    def update_colorbar_range(self, temp_min: float, temp_max: float, unit: str = "°C"):
        """Update colorbar temperature range."""
        if hasattr(self, 'colorbar') and self.colorbar:
            self.colorbar.set_temperature_range(temp_min, temp_max, unit)

    def set_colorbar_enabled(self, enabled: bool):
        """Enable or disable colorbar display."""
        if hasattr(self, 'colorbar') and self.colorbar:
            self.colorbar.set_enabled(enabled)

    def set_comparison(self, spot1_id: str, spot2_id: str, delta: float):
        """Set spot meter comparison data for visualization."""
        self.comparison_spot1_id = spot1_id if spot1_id else None
        self.comparison_spot2_id = spot2_id if spot2_id else None
        self.comparison_delta = delta
        self.update()

    def set_grid_enabled(self, enabled: bool):
        """Enable or disable grid overlay."""
        self.grid_enabled = enabled
        self.update()

    def set_grid_spacing(self, x: int, y: int):
        """Set grid spacing."""
        self.grid_spacing_x = x
        self.grid_spacing_y = y
        if self.grid_enabled:
            self.update()

    def set_grid_color(self, color: QColor):
        """Set grid color."""
        self.grid_color = color
        if self.grid_enabled:
            self.update()
