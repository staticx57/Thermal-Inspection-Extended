"""
High-performance video display widget with embedded inspection overlay.
"""

import logging
from typing import List

import cv2
import numpy as np

from PyQt6.QtWidgets import QLabel, QSizePolicy
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QImage, QPixmap

from thermal_inspection.processing.roi_manager import ROI
from thermal_inspection.processing.thermal_analyzer import HotSpot, ColdSpot, ThermalAnomaly

from .overlay_widget import InspectionOverlayWidget

logger = logging.getLogger(__name__)


class VideoWidget(QLabel):
    """
    High-performance video display widget with embedded inspection overlay.
    Reuses frame buffers to reduce memory allocations on Jetson.
    """
    # Signal for cursor position (emits x, y in frame coordinates)
    cursor_moved = pyqtSignal(int, int)
    # Signal for spot meter creation (emits x, y in frame coordinates)
    spot_meter_clicked = pyqtSignal(int, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(640, 480)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setStyleSheet("background-color: #000000; border: 2px solid #404040;")

        # Enable mouse tracking for cursor temperature readout
        self.setMouseTracking(True)

        # Frame buffer reuse (performance optimization for Jetson)
        self._last_qimage = None
        self._last_qpixmap = None
        self._frame_width = 0
        self._frame_height = 0

        # Measurement point mode
        self.add_point_mode = False

        # Embedded inspection overlay
        self.overlay = InspectionOverlayWidget(self)

    def update_frame(self, frame: np.ndarray):
        """Update displayed frame with performance optimization."""
        if frame is None or frame.size == 0:
            return

        orig_height, orig_width = frame.shape[:2]

        # Performance optimization: Resize using OpenCV (fast, C++) to the widget's
        # actual display size before feeding it into the expensive Qt graphics pipeline.
        widget_size = self.size()
        widget_w, widget_h = widget_size.width(), widget_size.height()

        if widget_w > 0 and widget_h > 0 and orig_width > widget_w:
            # Calculate aspect-preserving dimensions
            aspect = orig_width / orig_height
            target_w = widget_w
            target_h = int(target_w / aspect)
            if target_h > widget_h:
                target_h = widget_h
                target_w = int(target_h * aspect)

            # Use OpenCV resize (much faster than QPixmap.scaled for 4K arrays)
            frame = cv2.resize(frame, (target_w, target_h), interpolation=cv2.INTER_LINEAR)

        height, width = frame.shape[:2]

        # Store frame dimensions for cursor position mapping (MUST BE ORIGINAL for accurate coordinates)
        self._frame_width = orig_width
        self._frame_height = orig_height

        # Convert BGR to RGB
        if len(frame.shape) == 3 and frame.shape[2] == 3:
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        else:
            rgb_frame = frame

        qimage = QImage(rgb_frame.data, width, height, 3 * width, QImage.Format.Format_RGB888)
        self._last_qimage = qimage.copy()

        # Display directly (it's already scaled)
        self._last_qpixmap = QPixmap.fromImage(self._last_qimage)
        self.setPixmap(self._last_qpixmap)

        # Update overlay coordinate transformation
        self.overlay.set_frame_transform(
            orig_width, orig_height,
            width, height,
            self.width(), self.height()
        )

    def update_rois(self, rois: List[ROI]):
        """Update ROIs on overlay."""
        self.overlay.update_rois(rois)

    def update_thermal_detections(self, hot_spots: List[HotSpot], cold_spots: List[ColdSpot], anomalies: List[ThermalAnomaly]):
        """Update thermal detections on overlay."""
        self.overlay.update_thermal_detections(hot_spots, cold_spots, anomalies)

    def set_add_point_mode(self, enabled: bool):
        """Enable/disable measurement point adding mode."""
        self.add_point_mode = enabled
        if enabled:
            self.setCursor(Qt.CursorShape.CrossCursor)
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)

        self.overlay.set_spot_meter_mode(enabled, emit_signal=False)

    def update_measurement_points(self, points):
        """Update measurement points on overlay."""
        self.overlay.update_measurement_points(points)

    def resizeEvent(self, event):
        """Ensure overlay matches video widget size and update coordinate transformation."""
        super().resizeEvent(event)
        self.overlay.setGeometry(self.rect())

        if self._last_qpixmap and hasattr(self.overlay, 'frame_size') and self.overlay.frame_size != (640, 512):
            if self._last_qimage:
                frame_width, frame_height = self.overlay.frame_size
                self._last_qpixmap = QPixmap.fromImage(self._last_qimage).scaled(
                    self.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
                )
                self.setPixmap(self._last_qpixmap)

                self.overlay.set_frame_transform(
                    frame_width, frame_height,
                    self._last_qpixmap.width(), self._last_qpixmap.height(),
                    self.width(), self.height()
                )

    def enterEvent(self, event):
        """Mouse entered the widget."""
        super().enterEvent(event)

    def leaveEvent(self, event):
        """Mouse left the widget."""
        super().leaveEvent(event)

    def mouseMoveEvent(self, event):
        """Track mouse for cursor temperature and coordinate mapping."""
        x = event.position().x()
        y = event.position().y()

        # Convert to frame coordinates
        frame_x, frame_y = self._widget_to_frame_coords(x, y)

        if frame_x is not None and frame_y is not None:
            self.cursor_moved.emit(frame_x, frame_y)

        super().mouseMoveEvent(event)

    def mousePressEvent(self, event):
        """Handle mouse click for calibration points only."""
        if self.add_point_mode and not self.overlay.spot_meter_mode:
            x = event.pos().x()
            y = event.pos().y()

            frame_x, frame_y = self._widget_to_frame_coords(x, y)

            if frame_x is not None and frame_y is not None:
                logger.info(f"VideoWidget calibration point at ({frame_x}, {frame_y})")
                self.spot_meter_clicked.emit(frame_x, frame_y)

        super().mousePressEvent(event)

    def _widget_to_frame_coords(self, wx, wy):
        """Convert widget coordinates to frame coordinates."""
        if self._last_qpixmap is None or self._frame_width == 0 or self._frame_height == 0:
            return None, None

        pm_width = self._last_qpixmap.width()
        pm_height = self._last_qpixmap.height()

        offset_x = (self.width() - pm_width) / 2
        offset_y = (self.height() - pm_height) / 2

        if (wx < offset_x or wx > offset_x + pm_width or
            wy < offset_y or wy > offset_y + pm_height):
            return None, None

        rel_x = wx - offset_x
        rel_y = wy - offset_y

        frame_x = int(rel_x * (self._frame_width / pm_width))
        frame_y = int(rel_y * (self._frame_height / pm_height))

        frame_x = max(0, min(frame_x, self._frame_width - 1))
        frame_y = max(0, min(frame_y, self._frame_height - 1))

        return frame_x, frame_y
