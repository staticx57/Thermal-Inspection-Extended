#!/usr/bin/env python3
"""
Qt-based GUI for Thermal Inspection Fusion Tool
Professional interface for circuit board and residential house inspection
Optimized for Jetson Orin and x86-64 platforms
"""
import sys
import numpy as np
from typing import List, Optional, Dict
import logging
from pathlib import Path

try:
    from PyQt6.QtWidgets import (QMainWindow, QWidget, QLabel, QPushButton,
                                  QVBoxLayout, QHBoxLayout, QGridLayout, QApplication,
                                  QSizePolicy, QFileDialog, QListWidget, QListWidgetItem,
                                  QComboBox, QSpinBox, QDoubleSpinBox, QCheckBox,
                                  QGroupBox, QScrollArea, QTabWidget, QFrame, QMessageBox,
                                  QSlider, QProgressBar)
    from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QThread, QSize
    from PyQt6.QtGui import QImage, QPixmap, QFont, QPainter, QPen, QColor, QPalette
    PYQT_AVAILABLE = True
except ImportError:
    PYQT_AVAILABLE = False
    print("WARNING: PyQt5 not available. Install with: pip3 install PyQt5")

import cv2
from view_mode import ViewMode
from palette_manager import PaletteType
from roi_manager import ROI, ROIType
from thermal_analyzer import ThermalStatistics, HotSpot, ColdSpot, ThermalAnomaly, TemperatureTrend

logger = logging.getLogger(__name__)


# ============================================================================
# Qt Styling (QSS - CSS-like)
# ============================================================================

DARK_THEME = """
QMainWindow {
    background-color: #1a1a1a;
}

QWidget {
    background-color: #1a1a1a;
}

QPushButton {
    background-color: #2d2d2d;
    color: #e0e0e0;
    border: 2px solid #404040;
    border-radius: 8px;
    padding: 10px 20px;
    font-size: 14px;
    font-weight: bold;
    min-width: 120px;
}

QPushButton:hover {
    background-color: #3d3d3d;
    border: 2px solid #00aaff;
}

QPushButton:pressed {
    background-color: #1d1d1d;
}

QPushButton:checked {
    background-color: #00aaff;
    color: #ffffff;
    border: 2px solid #00ddff;
}

QPushButton:disabled {
    background-color: #1a1a1a;
    color: #666666;
    border: 2px solid #2d2d2d;
}

QLabel {
    color: #e0e0e0;
}

QLabel#info_panel {
    background-color: rgba(0, 0, 0, 180);
    color: #00ff00;
    border: 1px solid #404040;
    border-radius: 5px;
    padding: 10px;
    font-size: 12px;
    font-family: monospace;
}

QGroupBox {
    background-color: #2d2d2d;
    border: 2px solid #404040;
    border-radius: 5px;
    margin-top: 10px;
    padding: 10px;
    color: #e0e0e0;
    font-weight: bold;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 5px;
}

QListWidget {
    background-color: #1a1a1a;
    color: #e0e0e0;
    border: 1px solid #404040;
    border-radius: 3px;
}

QListWidget::item:selected {
    background-color: #00aaff;
}

QComboBox {
    background-color: #2d2d2d;
    color: #e0e0e0;
    border: 1px solid #404040;
    border-radius: 3px;
    padding: 5px;
}

QComboBox:hover {
    border: 1px solid #00aaff;
}

QComboBox::drop-down {
    border: none;
}

QComboBox QAbstractItemView {
    background-color: #2d2d2d;
    color: #e0e0e0;
    selection-background-color: #00aaff;
}

QSpinBox, QDoubleSpinBox {
    background-color: #2d2d2d;
    color: #e0e0e0;
    border: 1px solid #404040;
    border-radius: 3px;
    padding: 3px;
}

QSpinBox:hover, QDoubleSpinBox:hover {
    border: 1px solid #00aaff;
}

QCheckBox {
    color: #e0e0e0;
}

QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border: 2px solid #404040;
    border-radius: 3px;
    background-color: #2d2d2d;
}

QCheckBox::indicator:checked {
    background-color: #00aaff;
}

QTabWidget::pane {
    border: 1px solid #404040;
    background-color: #2d2d2d;
}

QTabBar::tab {
    background-color: #1a1a1a;
    color: #e0e0e0;
    border: 1px solid #404040;
    padding: 8px 16px;
    margin-right: 2px;
}

QTabBar::tab:selected {
    background-color: #00aaff;
    color: #ffffff;
}

QTabBar::tab:hover {
    background-color: #3d3d3d;
}
"""

LIGHT_THEME = """
QMainWindow {
    background-color: #f5f5f5;
}

QWidget {
    background-color: #f5f5f5;
}

QPushButton {
    background-color: #ffffff;
    color: #202020;
    border: 2px solid #c0c0c0;
    border-radius: 8px;
    padding: 10px 20px;
    font-size: 14px;
    font-weight: bold;
    min-width: 120px;
}

QPushButton:hover {
    background-color: #f0f0f0;
    border: 2px solid #0080ff;
}

QPushButton:pressed {
    background-color: #e0e0e0;
}

QPushButton:checked {
    background-color: #0080ff;
    color: #ffffff;
    border: 2px solid #0099ff;
}

QPushButton:disabled {
    background-color: #f5f5f5;
    color: #a0a0a0;
    border: 2px solid #d0d0d0;
}

QLabel {
    color: #202020;
}

QLabel#info_panel {
    background-color: rgba(255, 255, 255, 200);
    color: #006600;
    border: 1px solid #c0c0c0;
    border-radius: 5px;
    padding: 10px;
    font-size: 12px;
    font-family: monospace;
}

QGroupBox {
    background-color: #ffffff;
    border: 2px solid #c0c0c0;
    border-radius: 5px;
    margin-top: 10px;
    padding: 10px;
    color: #202020;
    font-weight: bold;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 5px;
}

QListWidget {
    background-color: #ffffff;
    color: #202020;
    border: 1px solid #c0c0c0;
    border-radius: 3px;
}

QListWidget::item:selected {
    background-color: #0080ff;
    color: #ffffff;
}

QComboBox {
    background-color: #ffffff;
    color: #202020;
    border: 1px solid #c0c0c0;
    border-radius: 3px;
    padding: 5px;
}

QComboBox:hover {
    border: 1px solid #0080ff;
}

QComboBox::drop-down {
    border: none;
}

QComboBox QAbstractItemView {
    background-color: #ffffff;
    color: #202020;
    selection-background-color: #0080ff;
    selection-color: #ffffff;
}

QSpinBox, QDoubleSpinBox {
    background-color: #ffffff;
    color: #202020;
    border: 1px solid #c0c0c0;
    border-radius: 3px;
    padding: 3px;
}

QSpinBox:hover, QDoubleSpinBox:hover {
    border: 1px solid #0080ff;
}

QCheckBox {
    color: #202020;
}

QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border: 2px solid #c0c0c0;
    border-radius: 3px;
    background-color: #ffffff;
}

QCheckBox::indicator:checked {
    background-color: #0080ff;
}

QTabWidget::pane {
    border: 1px solid #c0c0c0;
    background-color: #ffffff;
}

QTabBar::tab {
    background-color: #f5f5f5;
    color: #202020;
    border: 1px solid #c0c0c0;
    padding: 8px 16px;
    margin-right: 2px;
}

QTabBar::tab:selected {
    background-color: #0080ff;
    color: #ffffff;
}

QTabBar::tab:hover {
    background-color: #e0e0e0;
}
"""

SOLARIZED_THEME = """
QMainWindow {
    background-color: #fdf6e3;
}

QWidget {
    background-color: #fdf6e3;
}

QPushButton {
    background-color: #eee8d5;
    color: #657b83;
    border: 2px solid #93a1a1;
    border-radius: 8px;
    padding: 10px 20px;
    font-size: 14px;
    font-weight: bold;
    min-width: 120px;
}

QPushButton:hover {
    background-color: #e8e2cf;
    border: 2px solid #268bd2;
}

QPushButton:pressed {
    background-color: #dfd9c6;
}

QPushButton:checked {
    background-color: #268bd2;
    color: #fdf6e3;
    border: 2px solid #2aa198;
}

QPushButton:disabled {
    background-color: #fdf6e3;
    color: #93a1a1;
    border: 2px solid #eee8d5;
}

QLabel {
    color: #657b83;
}

QGroupBox {
    background-color: #eee8d5;
    border: 2px solid #93a1a1;
    border-radius: 5px;
    margin-top: 10px;
    padding: 10px;
    color: #586e75;
    font-weight: bold;
}

QListWidget {
    background-color: #fdf6e3;
    color: #657b83;
    border: 1px solid #93a1a1;
    border-radius: 3px;
}

QCheckBox {
    color: #657b83;
}

QComboBox {
    background-color: #eee8d5;
    color: #657b83;
    border: 1px solid #93a1a1;
}

QSpinBox {
    background-color: #eee8d5;
    color: #657b83;
    border: 1px solid #93a1a1;
}

QListWidget::item:selected {
    background-color: #268bd2;
    color: #fdf6e3;
}

QLabel#info_panel {
    background-color: rgba(238, 232, 213, 200);
    color: #2aa198;
    border: 1px solid #93a1a1;
    border-radius: 5px;
    padding: 10px;
    font-size: 12px;
    font-family: monospace;
}
"""

COLORFUL_THEME = """
QMainWindow {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                                      stop:0 #1a3a52, stop:1 #0f1e2e);
}

QWidget {
    background-color: #0f1e2e;
}

QPushButton {
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                       stop:0 #2c5f7e, stop:1 #1c4a6e);
    color: #d4e8ff;
    border: 2px solid #4a7c9e;
    border-radius: 8px;
    padding: 10px 20px;
    font-size: 14px;
    font-weight: bold;
    min-width: 120px;
}

QPushButton:hover {
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                       stop:0 #3c8fae, stop:1 #2c7f9e);
    border: 2px solid #6bcf9d;
}

QPushButton:pressed {
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                       stop:0 #1c4a6e, stop:1 #0c3a5e);
}

QPushButton:checked {
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                       stop:0 #6bcf9d, stop:1 #44a569);
    color: #ffffff;
    border: 2px solid #57cafe;
}

QPushButton:disabled {
    background-color: #1a3a52;
    color: #4a7c9e;
    border: 2px solid #1c4a6e;
}

QLabel {
    color: #d4e8ff;
}

QGroupBox {
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                       stop:0 #1c4a6e, stop:1 #0c3a5e);
    border: 2px solid #4a7c9e;
    border-radius: 5px;
    margin-top: 10px;
    padding: 10px;
    color: #d4e8ff;
    font-weight: bold;
}

QListWidget {
    background-color: #0f1e2e;
    color: #d4e8ff;
    border: 1px solid #4a7c9e;
    border-radius: 3px;
}

QListWidget::item:selected {
    background-color: #6bcf9d;
    color: #ffffff;
}

QLabel#info_panel {
    background-color: rgba(12, 58, 94, 200);
    color: #57cafe;
    border: 1px solid #4a7c9e;
    border-radius: 5px;
    padding: 10px;
    font-size: 12px;
    font-family: monospace;
}
"""


# ============================================================================
# Inspection Overlay Widget
# ============================================================================

class InspectionOverlayWidget(QWidget):
    """
    Overlay widget for drawing ROIs, hot spots, cold spots, and anomalies.
    Replaces AlertOverlayWidget from ADAS system.
    """

    # Signals for ROI drawing
    from PyQt6.QtCore import pyqtSignal
    roi_created = pyqtSignal(object)  # Emits newly created ROI
    roi_selected = pyqtSignal(str)    # Emits selected ROI ID

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)  # Enable mouse interaction
        self.setStyleSheet("background: transparent;")

        self.rois: List[ROI] = []
        self.hot_spots: List[HotSpot] = []
        self.cold_spots: List[ColdSpot] = []
        self.anomalies: List[ThermalAnomaly] = []
        self.selected_roi_id: Optional[str] = None

        # ROI drawing state
        self.drawing_mode = False
        self.drawing_type = ROIType.RECTANGLE  # Default
        self.draw_start_pos = None
        self.draw_current_pos = None
        self.temp_polygon_points = []

        # Coordinate transformation for scaled video
        self.frame_size = (640, 512)  # Original frame size (width, height)
        self.scale = 1.0
        self.offset_x = 0
        self.offset_y = 0

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

    def set_frame_transform(self, frame_width: int, frame_height: int, pixmap_width: int, pixmap_height: int, widget_width: int, widget_height: int):
        """
        Update coordinate transformation parameters.

        Args:
            frame_width: Original frame width
            frame_height: Original frame height
            pixmap_width: Scaled pixmap width
            pixmap_height: Scaled pixmap height
            widget_width: Widget width
            widget_height: Widget height
        """
        self.frame_size = (frame_width, frame_height)
        self.scale = pixmap_width / frame_width  # Assuming uniform scaling
        # Calculate offset for centered image
        self.offset_x = (widget_width - pixmap_width) // 2
        self.offset_y = (widget_height - pixmap_height) // 2

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

    def set_selected_roi(self, roi_id: Optional[str]):
        """Highlight a specific ROI."""
        self.selected_roi_id = roi_id
        self.update()

    def paintEvent(self, event):
        """Draw ROIs and thermal detections."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Helper to draw text with background
        def draw_label(x, y, text, color):
            font_metrics = painter.fontMetrics()
            rect = font_metrics.boundingRect(text)
            # Add padding
            rect.adjust(-2, -2, 2, 2)
            rect.moveTo(x, y - rect.height() + 2)
            
            painter.setBrush(QColor(0, 0, 0, 160))  # Semi-transparent black
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRect(rect)
            
            painter.setPen(QPen(color, 1))
            painter.drawText(x, y, text)

        # Draw ROIs
        for roi in self.rois:
            # Determine color and thickness
            if roi.roi_id == self.selected_roi_id:
                color = QColor(0, 255, 255)  # Cyan for selected
                thickness = 3
            elif roi.roi_type == ROIType.RECTANGLE:
                color = QColor(0, 255, 0)  # Green for rectangle
                thickness = 2
            elif roi.roi_type == ROIType.POLYGON:
                color = QColor(255, 255, 0)  # Yellow for polygon
                thickness = 2
            elif roi.roi_type == ROIType.ELLIPSE:
                color = QColor(255, 128, 0)  # Orange for ellipse
                thickness = 2
            elif roi.roi_type == ROIType.CIRCLE:
                color = QColor(128, 0, 255)  # Purple for circle
                thickness = 2
            else:
                color = QColor(255, 255, 255)  # White fallback
                thickness = 2

            pen = QPen(color, thickness)
            painter.setPen(pen)

            # Draw based on ROI type (with coordinate transformation)
            if roi.roi_type == ROIType.RECTANGLE:
                x, y, w, h = roi.get_bbox()
                # Transform frame coordinates to widget coordinates
                wx1, wy1 = self.frame_to_widget(x, y)
                wx2, wy2 = self.frame_to_widget(x + w, y + h)
                painter.drawRect(wx1, wy1, wx2 - wx1, wy2 - wy1)
            elif roi.roi_type == ROIType.POLYGON:
                from PyQt6.QtCore import QPoint
                # Transform all polygon points
                points = [QPoint(int(self.frame_to_widget(p[0], p[1])[0]),
                                int(self.frame_to_widget(p[0], p[1])[1])) for p in roi.points]
                from PyQt6.QtGui import QPolygon
                painter.drawPolygon(QPolygon(points))
            elif roi.roi_type == ROIType.ELLIPSE:
                x, y, w, h = roi.get_bbox()
                # Transform frame coordinates to widget coordinates
                wx1, wy1 = self.frame_to_widget(x, y)
                wx2, wy2 = self.frame_to_widget(x + w, y + h)
                painter.drawEllipse(wx1, wy1, wx2 - wx1, wy2 - wy1)
            elif roi.roi_type == ROIType.CIRCLE:
                x, y, w, h = roi.get_bbox()
                # Transform to widget coordinates
                wx1, wy1 = self.frame_to_widget(x, y)
                wx2, wy2 = self.frame_to_widget(x + w, y + h)
                ww = wx2 - wx1
                wh = wy2 - wy1
                radius = int(ww / 2)
                center_x = int(wx1 + radius)
                center_y = int(wy1 + radius)
                painter.drawEllipse(center_x - radius, center_y - radius, radius * 2, radius * 2)

            # Draw label
            if roi.label:
                x, y, _, _ = roi.get_bbox()
                wx, wy = self.frame_to_widget(x, y)
                draw_label(int(wx), int(wy) - 5, roi.label, color)

        # Draw hot spots (with coordinate transformation)
        for hot_spot in self.hot_spots:
            painter.setPen(QPen(QColor(255, 0, 0), 2))  # Red
            x, y = hot_spot.centroid
            wx, wy = self.frame_to_widget(x, y)
            painter.drawEllipse(int(wx) - 5, int(wy) - 5, 10, 10)
            draw_label(int(wx) + 10, int(wy), f"{hot_spot.max_temp:.1f}{hot_spot.unit}", QColor(255, 100, 100))

        # Draw cold spots (with coordinate transformation)
        for cold_spot in self.cold_spots:
            painter.setPen(QPen(QColor(0, 128, 255), 2))  # Light blue
            x, y = cold_spot.centroid
            wx, wy = self.frame_to_widget(x, y)
            painter.drawEllipse(int(wx) - 5, int(wy) - 5, 10, 10)
            draw_label(int(wx) + 10, int(wy), f"{cold_spot.min_temp:.1f}{cold_spot.unit}", QColor(100, 200, 255))

        # Draw anomalies (with coordinate transformation)
        for anomaly in self.anomalies:
            painter.setPen(QPen(QColor(255, 255, 0), 3))  # Yellow
            x, y = anomaly.location
            wx, wy = self.frame_to_widget(x, y)
            # Draw warning triangle
            painter.drawLine(int(wx), int(wy) - 10, int(wx) - 8, int(wy) + 6)
            painter.drawLine(int(wx) - 8, int(wy) + 6, int(wx) + 8, int(wy) + 6)
            painter.drawLine(int(wx) + 8, int(wy) + 6, int(wx), int(wy) - 10)
            
            # Use description if available, otherwise type
            label_text = f"⚠ {anomaly.description}" if anomaly.description else f"⚠ {anomaly.anomaly_type.value}"
            draw_label(int(wx) + 15, int(wy), label_text, QColor(255, 255, 0))

        # Draw temporary ROI being created
        if self.drawing_mode and self.draw_start_pos and self.draw_current_pos:
            painter.setPen(QPen(QColor(255, 255, 0), 2, Qt.PenStyle.DashLine))  # Yellow dashed line

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
                from PyQt6.QtGui import QPolygon
                # Draw lines between polygon points
                points = self.temp_polygon_points + [self.draw_current_pos]
                for i in range(len(points) - 1):
                    painter.drawLine(points[i], points[i + 1])

    def enable_drawing_mode(self, roi_type: ROIType = ROIType.RECTANGLE):
        """Enable ROI drawing mode."""
        self.drawing_mode = True
        self.drawing_type = roi_type
        self.draw_start_pos = None
        self.draw_current_pos = None
        self.temp_polygon_points = []
        self.setCursor(Qt.CursorShape.CrossCursor)
        logger.info(f"Drawing mode enabled: {roi_type}")

    def disable_drawing_mode(self):
        """Disable ROI drawing mode."""
        self.drawing_mode = False
        self.draw_start_pos = None
        self.draw_current_pos = None
        self.temp_polygon_points = []
        self.setCursor(Qt.CursorShape.ArrowCursor)
        logger.info("Drawing mode disabled")

    def mousePressEvent(self, event):
        """Handle mouse press for ROI drawing."""
        if not self.drawing_mode:
            # Check if clicking on existing ROI for selection
            # Transform click to frame coordinates
            click_x, click_y = self.widget_to_frame(event.pos().x(), event.pos().y())
            
            for roi in self.rois:
                if roi.contains_point((click_x, click_y)):
                    self.set_selected_roi(roi.roi_id)
                    self.roi_selected.emit(roi.roi_id)
                    break
            return

        if self.drawing_type == ROIType.POLYGON:
            # For polygon, collect multiple points
            self.temp_polygon_points.append(event.pos())
            self.update()
        else:
            # For rectangle, ellipse, circle - start drawing
            self.draw_start_pos = event.pos()
            self.draw_current_pos = event.pos()
            self.update()

    def mouseMoveEvent(self, event):
        """Handle mouse move for ROI drawing."""
        if self.drawing_mode and self.draw_start_pos:
            self.draw_current_pos = event.pos()
            self.update()

    def mouseReleaseEvent(self, event):
        """Handle mouse release to finalize ROI."""
        if not self.drawing_mode or not self.draw_start_pos:
            return

        if self.drawing_type == ROIType.POLYGON:
            # Polygon requires double-click or Enter key to finish
            return

        try:
            # Create ROI from drawn shape
            from roi_manager import ROI, ROISource
            import uuid

            if self.drawing_type == ROIType.RECTANGLE:
                x = min(self.draw_start_pos.x(), event.pos().x())
                y = min(self.draw_start_pos.y(), event.pos().y())
                w = abs(event.pos().x() - self.draw_start_pos.x())
                h = abs(event.pos().y() - self.draw_start_pos.y())

                if w > 10 and h > 10:  # Minimum size
                    # Transform widget coordinates to frame coordinates
                    fx1, fy1 = self.widget_to_frame(x, y)
                    fx2, fy2 = self.widget_to_frame(x + w, y + h)
                    # Convert bounds to points (4 corners) in frame coordinates
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
                    # Transform widget coordinates to frame coordinates
                    fx1, fy1 = self.widget_to_frame(x, y)
                    fx2, fy2 = self.widget_to_frame(x + w, y + h)
                    # Convert ellipse bounds to points (4 corners of bounding box) in frame coordinates
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
                    # Transform center to frame coordinates
                    fcx, fcy = self.widget_to_frame(center_x, center_y)
                    
                    # Calculate a point on the circumference in frame coordinates
                    # We can't just transform the radius because scaling might be different (though here it's uniform)
                    # Let's transform the current mouse position
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

        # Reset drawing state
        self.draw_start_pos = None
        self.draw_current_pos = None
        self.update()

    def mouseDoubleClickEvent(self, event):
        """Handle double-click to finish polygon drawing."""
        if self.drawing_mode and self.drawing_type == ROIType.POLYGON and len(self.temp_polygon_points) >= 3:
            from roi_manager import ROI, ROISource
            import uuid

            # Convert QPoint to tuples
            points = [(p.x(), p.y()) for p in self.temp_polygon_points]

            # Calculate bounding box
            xs = [p[0] for p in points]
            ys = [p[1] for p in points]
            x, y = min(xs), min(ys)
            w, h = max(xs) - x, max(ys) - y

            roi = ROI(
                roi_id=str(uuid.uuid4()),
                roi_type=ROIType.POLYGON,
                bounds=(x, y, w, h),
                polygon_points=points,
                label=f"ROI-{len(self.rois) + 1}",
                source=ROISource.MANUAL
            )
            self.roi_created.emit(roi)

            # Reset polygon drawing
            self.temp_polygon_points = []
            self.draw_start_pos = None
            self.draw_current_pos = None
            self.update()

    def mouseDoubleClickEvent(self, event):
        """Handle double click to finalize polygon."""
        if self.drawing_mode and self.drawing_type == ROIType.POLYGON:
            if len(self.temp_polygon_points) > 2:
                try:
                    from roi_manager import ROI, ROISource
                    import uuid
                    
                    # Transform all points to frame coordinates
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
                    
                    # Reset drawing state
                    self.temp_polygon_points = []
                    self.draw_start_pos = None
                    self.draw_current_pos = None
                    self.update()
                    
                except Exception as e:
                    logger.error(f"Error creating polygon ROI: {e}", exc_info=True)

class VideoWidget(QLabel):
    """
    High-performance video display widget with embedded inspection overlay.
    Reuses frame buffers to reduce memory allocations on Jetson.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(640, 480)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setStyleSheet("background-color: #000000; border: 2px solid #404040;")

        # Frame buffer reuse (performance optimization for Jetson)
        self._last_qimage = None
        self._last_qpixmap = None

        # Embedded inspection overlay
        self.overlay = InspectionOverlayWidget(self)

    def update_frame(self, frame: np.ndarray):
        """Update displayed frame with performance optimization."""
        if frame is None or frame.size == 0:
            return

        height, width = frame.shape[:2]

        # Convert BGR to RGB
        if len(frame.shape) == 3 and frame.shape[2] == 3:
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        else:
            rgb_frame = frame

        # Create QImage (reuse buffer if possible)
        bytes_per_line = 3 * width
        qimage = QImage(rgb_frame.data, width, height, bytes_per_line, QImage.Format.Format_RGB888)

        # Deep copy to take ownership (crucial for thread safety)
        self._last_qimage = qimage.copy()

        # Scale to widget size and display
        # PERFORMANCE: Use FastTransformation instead of SmoothTransformation
        # SmoothTransformation uses bicubic interpolation (~100ms per frame)
        # FastTransformation uses nearest neighbor (~1ms per frame)
        self._last_qpixmap = QPixmap.fromImage(self._last_qimage).scaled(
            self.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.FastTransformation
        )
        self.setPixmap(self._last_qpixmap)

        # Update overlay coordinate transformation
        self.overlay.set_frame_transform(
            width, height,  # Original frame size
            self._last_qpixmap.width(), self._last_qpixmap.height(),  # Scaled pixmap size
            self.width(), self.height()  # Widget size
        )

    def update_rois(self, rois: List[ROI]):
        """Update ROIs on overlay."""
        self.overlay.update_rois(rois)

    def update_thermal_detections(self, hot_spots: List[HotSpot], cold_spots: List[ColdSpot], anomalies: List[ThermalAnomaly]):
        """Update thermal detections on overlay."""
        self.overlay.update_thermal_detections(hot_spots, cold_spots, anomalies)

    def resizeEvent(self, event):
        """Ensure overlay matches video widget size and update coordinate transformation."""
        super().resizeEvent(event)
        self.overlay.setGeometry(self.rect())

        # Update coordinate transformation if we have frame dimensions
        if self._last_qpixmap and hasattr(self.overlay, 'frame_size') and self.overlay.frame_size != (640, 512):
            # Re-scale pixmap and update transformation
            if self._last_qimage:
                frame_width, frame_height = self.overlay.frame_size
                self._last_qpixmap = QPixmap.fromImage(self._last_qimage).scaled(
                    self.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
                )
                self.setPixmap(self._last_qpixmap)

                # Update overlay coordinate transformation
                self.overlay.set_frame_transform(
                    frame_width, frame_height,
                    self._last_qpixmap.width(), self._last_qpixmap.height(),
                    self.width(), self.height()
                )

        # Trigger overlay repaint with new coordinates
        self.overlay.update()


# ============================================================================
# Control Panel
# ============================================================================

class ControlPanel(QWidget):
    """
    Control panel with inspection-specific buttons.
    Replaces driving controls with inspection controls.
    """

    # Simple mode signals (always visible)
    palette_clicked = pyqtSignal()
    view_mode_clicked = pyqtSignal()
    day_night_clicked = pyqtSignal()

    # Recording signals
    record_toggled = pyqtSignal(bool)
    snapshot_clicked = pyqtSignal()

    # ROI signals
    auto_roi_clicked = pyqtSignal()
    draw_roi_clicked = pyqtSignal()
    clear_rois_clicked = pyqtSignal()
    save_rois_clicked = pyqtSignal()
    load_rois_clicked = pyqtSignal()

    # Analysis signals
    freeze_frame_toggled = pyqtSignal(bool)

    # Developer mode signals
    device_clicked = pyqtSignal()
    fusion_mode_clicked = pyqtSignal()
    fusion_alpha_clicked = pyqtSignal()
    fusion_priority_clicked = pyqtSignal()
    motion_detection_toggled = pyqtSignal(bool)
    edge_detection_toggled = pyqtSignal(bool)
    anomaly_priority_toggled = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)

        # Main layout
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(10, 10, 10, 10)
        self.main_layout.setSpacing(15)  # Increased spacing

        # === Simple Controls (Always Visible) ===
        self.simple_layout = QHBoxLayout()

        self.palette_btn = QPushButton("🎨 Palette")
        self.view_btn = QPushButton("👁 View")
        self.day_night_btn = QPushButton("☀ Day")

        self.simple_layout.addWidget(self.palette_btn)
        self.simple_layout.addWidget(self.view_btn)
        self.simple_layout.addStretch()
        self.simple_layout.addWidget(self.day_night_btn)

        self.main_layout.addLayout(self.simple_layout)

        # === Developer Controls (Hidden by default) ===
        self.dev_controls = QWidget()
        self.dev_layout = QGridLayout(self.dev_controls)
        self.dev_layout.setSpacing(8)

        # Row 0: Recording controls
        self.record_btn = QPushButton("⏺ Record: OFF")
        self.record_btn.setCheckable(True)
        self.snapshot_btn = QPushButton("📷 Snapshot")
        self.freeze_btn = QPushButton("⏸ Freeze: OFF")
        self.freeze_btn.setCheckable(True)

        self.dev_layout.addWidget(self.record_btn, 0, 0)
        self.dev_layout.addWidget(self.snapshot_btn, 0, 1)
        self.dev_layout.addWidget(self.freeze_btn, 0, 2)

        # Row 1: ROI controls
        self.auto_roi_btn = QPushButton("🔍 Auto ROI")
        self.draw_roi_btn = QPushButton("✏ Draw ROI")
        self.clear_roi_btn = QPushButton("🗑 Clear ROIs")

        self.dev_layout.addWidget(self.auto_roi_btn, 1, 0)
        self.dev_layout.addWidget(self.draw_roi_btn, 1, 1)
        self.dev_layout.addWidget(self.clear_roi_btn, 1, 2)

        # Row 2: ROI persistence
        self.save_roi_btn = QPushButton("💾 Save ROIs")
        self.load_roi_btn = QPushButton("📂 Load ROIs")

        self.dev_layout.addWidget(self.save_roi_btn, 2, 0)
        self.dev_layout.addWidget(self.load_roi_btn, 2, 1)

        # Row 3: Processing controls
        self.device_btn = QPushButton("🖥 Device: CPU")
        self.motion_btn = QPushButton("🏃 Motion: ON")
        self.motion_btn.setCheckable(True)
        self.motion_btn.setChecked(True)
        self.edge_btn = QPushButton("📐 Edges: ON")
        self.edge_btn.setCheckable(True)
        self.edge_btn.setChecked(True)
        self.anomaly_priority_btn = QPushButton("🎯 Anomaly: OFF")
        self.anomaly_priority_btn.setCheckable(True)
        self.anomaly_priority_btn.setChecked(False)

        self.dev_layout.addWidget(self.device_btn, 3, 0)
        self.dev_layout.addWidget(self.motion_btn, 3, 1)
        self.dev_layout.addWidget(self.edge_btn, 3, 2)
        self.dev_layout.addWidget(self.anomaly_priority_btn, 3, 3)

        # Row 4: Fusion controls
        self.fusion_mode_btn = QPushButton("🔀 Fusion: Alpha")
        self.fusion_alpha_btn = QPushButton("⚖ Alpha: 0.5")
        self.fusion_priority_btn = QPushButton("🎯 Priority: Thermal")

        self.dev_layout.addWidget(self.fusion_mode_btn, 4, 0)
        self.dev_layout.addWidget(self.fusion_alpha_btn, 4, 1)
        self.dev_layout.addWidget(self.fusion_priority_btn, 4, 2)

        self.main_layout.addWidget(self.dev_controls)
        self.dev_controls.setVisible(False)

        # Connect signals
        self._connect_signals()

    def _connect_signals(self):
        """Connect button signals."""
        # Simple controls
        self.palette_btn.clicked.connect(lambda: self.palette_clicked.emit())
        self.view_btn.clicked.connect(lambda: self.view_mode_clicked.emit())
        self.day_night_btn.clicked.connect(lambda: self.day_night_clicked.emit())

        # Recording
        self.record_btn.toggled.connect(self.record_toggled.emit)
        self.snapshot_btn.clicked.connect(lambda: self.snapshot_clicked.emit())
        self.freeze_btn.toggled.connect(self.freeze_frame_toggled.emit)

        # ROI
        self.auto_roi_btn.clicked.connect(lambda: self.auto_roi_clicked.emit())
        self.draw_roi_btn.clicked.connect(lambda: self.draw_roi_clicked.emit())
        self.clear_roi_btn.clicked.connect(lambda: self.clear_rois_clicked.emit())
        self.save_roi_btn.clicked.connect(lambda: self.save_rois_clicked.emit())
        self.load_roi_btn.clicked.connect(lambda: self.load_rois_clicked.emit())

        # Processing
        self.device_btn.clicked.connect(lambda: self.device_clicked.emit())
        self.motion_btn.toggled.connect(self.motion_detection_toggled.emit)
        self.edge_btn.toggled.connect(self.edge_detection_toggled.emit)
        self.anomaly_priority_btn.toggled.connect(self.anomaly_priority_toggled.emit)

        # Fusion
        self.fusion_mode_btn.clicked.connect(lambda: self.fusion_mode_clicked.emit())
        self.fusion_alpha_btn.clicked.connect(lambda: self.fusion_alpha_clicked.emit())
        self.fusion_priority_btn.clicked.connect(lambda: self.fusion_priority_clicked.emit())

    def show_developer_controls(self, show: bool):
        """Toggle developer controls visibility."""
        self.dev_controls.setVisible(show)

    def update_palette_button(self, palette: str):
        """Update palette button text."""
        self.palette_btn.setText(f"🎨 {palette.replace('_', ' ').title()}")

    def update_view_button(self, view: str):
        """Update view mode button text."""
        self.view_btn.setText(f"👁 {view.replace('_', ' ').title()}")

    def update_theme_button(self, theme: str):
        """Update theme button text."""
        theme_icons = {
            "light": "☀ Light",
            "dark": "🌙 Dark",
            "solarized": "🌊 Solarized",
            "colorful": "🎨 Colorful"
        }
        # Handle auto mode with actual theme
        if "(" in theme and theme.startswith("auto"):
            self.day_night_btn.setText(f"🔄 {theme}")
        else:
            display_text = theme_icons.get(theme, f"🔄 Auto")
            self.day_night_btn.setText(display_text)

    def update_fusion_mode_button(self, mode: str):
        """Update fusion mode button text."""
        mode_display = mode.replace('_', ' ').title()
        self.fusion_mode_btn.setText(f"🔀 Fusion: {mode_display}")

    def update_fusion_alpha_button(self, alpha: float):
        """Update fusion alpha button text."""
        self.fusion_alpha_btn.setText(f"⚖ Alpha: {alpha:.1f}")

    def update_fusion_priority_button(self, priority: str):
        """Update fusion priority button text."""
        self.fusion_priority_btn.setText(f"🎯 Priority: {priority.title()}")

    def update_record_button(self, recording: bool):
        """Update record button text."""
        if recording:
            self.record_btn.setText("⏹ Recording...")
        else:
            self.record_btn.setText("⏺ Record: OFF")

    def update_freeze_button(self, frozen: bool):
        """Update freeze button text."""
        if frozen:
            self.freeze_btn.setText("▶ Resume")
        else:
            self.freeze_btn.setText("⏸ Freeze: OFF")

    def update_motion_button(self, enabled: bool):
        """Update motion detection button."""
        if enabled:
            self.motion_btn.setText("🏃 Motion: ON")
        else:
            self.motion_btn.setText("🏃 Motion: OFF")

    def update_edge_button(self, enabled: bool):
        """Update edge detection button."""
        if enabled:
            self.edge_btn.setText("📐 Edges: ON")
        else:
            self.edge_btn.setText("📐 Edges: OFF")

    def update_anomaly_priority_button(self, enabled: bool):
        """Update anomaly priority button."""
        if enabled:
            self.anomaly_priority_btn.setText("🎯 Anomaly: ON")
        else:
            self.anomaly_priority_btn.setText("🎯 Anomaly: OFF")

    def update_view_button(self, view_mode: str):
        """Update view mode button text."""
        # Handle ViewMode object or string
        if hasattr(view_mode, 'lower'):
            mode_str = view_mode.lower()
        else:
            mode_str = str(view_mode).lower()
        
        mode_names = {
            "thermal": "🌡 Thermal",
            "thermal_only": "🌡 Thermal",
            "rgb": "📷 RGB",
            "rgb_only": "📷 RGB",
            "fusion": "🔥 Fusion",
            "side_by_side": "⬌ Side-by-Side",
            "picture_in_picture": "📺 PiP",
            "pip": "📺 PiP"
        }
        mode_text = mode_names.get(mode_str, "👁 View")
        self.view_btn.setText(mode_text)


# ============================================================================
# Info Panel (Minimal Status Overlay)
# ============================================================================

class InfoPanel(QLabel):
    """
    Minimal inspection status overlay (280x70px, top-right corner).
    Shows FPS, thermal status, ROI count, and recording status.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("info_panel")
        self.setFixedSize(280, 70)
        self.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.setWordWrap(True)

    def update_info(self, fps: float, roi_count: int, thermal_connected: bool, rgb_connected: bool, recording: bool = False):
        """Update inspection status information."""
        # Performance quality indicator
        if fps >= 25:
            quality = "● "  # Green
        elif fps >= 15:
            quality = "● "  # Yellow
        else:
            quality = "● "  # Red

        # Connection status
        thermal_status = "✓" if thermal_connected else "✗"
        rgb_status = "✓" if rgb_connected else "✗"

        # Recording indicator
        rec_indicator = " [⏺ REC]" if recording else ""

        info_text = (
            f"{quality}FPS: {fps:.1f}{rec_indicator}\n"
            f"ROIs: {roi_count}\n"
            f"Thermal:{thermal_status} RGB:{rgb_status}"
        )

        self.setText(info_text)


# ============================================================================
# Thermal Analysis Panel (Right Sidebar)
# ============================================================================

class ThermalAnalysisPanel(QWidget):
    """
    Right sidebar panel for thermal analysis display.
    Shows temperature statistics, hot/cold spots, trends, and anomalies.
    """
    
    baseline_toggled = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(380)  # Increased from 350 for better readability

        # Main layout with scroll area
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.Shape.NoFrame)  # Remove frame for cleaner look

        content = QWidget()
        self.content_layout = QVBoxLayout(content)
        self.content_layout.setSpacing(15)  # Increased spacing
        self.content_layout.setContentsMargins(5, 5, 5, 5)

        # Helper function to create section headers
        def create_section_header(text):
            header = QLabel(text)
            font = QFont()
            font.setPointSize(11)
            font.setBold(True)
            header.setFont(font)
            return header

        # Helper function to create separators
        def create_separator():
            line = QFrame()
            line.setFrameShape(QFrame.Shape.HLine)
            line.setFrameShadow(QFrame.Shadow.Sunken)
            palette = line.palette()
            palette.setColor(QPalette.ColorRole.WindowText, palette.color(QPalette.ColorRole.Mid))
            line.setPalette(palette)
            return line

        # === Temperature Statistics ===
        self.content_layout.addWidget(create_section_header("📊 Temperature Statistics"))
        
        self.stats_label = QLabel("No data")
        self.stats_label.setWordWrap(True)
        font = QFont("Consolas", 10)  # Larger, more readable font
        self.stats_label.setFont(font)
        self.stats_label.setStyleSheet("padding: 5px;")
        self.content_layout.addWidget(self.stats_label)
        
        # Baseline control
        self.baseline_btn = QPushButton("🔒 Lock Baseline")
        self.baseline_btn.setCheckable(True)
        self.baseline_btn.setToolTip("Lock current mean temperature as baseline for relative measurements")
        self.baseline_btn.setMinimumHeight(32)
        self.content_layout.addWidget(self.baseline_btn)
        
        self.content_layout.addWidget(create_separator())

        # === Hot Spots ===
        self.content_layout.addWidget(create_section_header("🔥 Hot Spots"))
        
        self.hotspot_list = QListWidget()
        self.hotspot_list.setMaximumHeight(70)
        font = QFont()
        font.setPointSize(10)
        self.hotspot_list.setFont(font)
        self.content_layout.addWidget(self.hotspot_list)
        
        self.content_layout.addWidget(create_separator())

        # === Cold Spots ===
        self.content_layout.addWidget(create_section_header("❄️ Cold Spots"))
        
        self.coldspot_list = QListWidget()
        self.coldspot_list.setMaximumHeight(70)
        font = QFont()
        font.setPointSize(10)
        self.coldspot_list.setFont(font)
        self.content_layout.addWidget(self.coldspot_list)
        
        self.content_layout.addWidget(create_separator())

        # === Thermal Anomalies ===
        self.content_layout.addWidget(create_section_header("⚠️ Thermal Anomalies"))
        
        self.anomaly_list = QListWidget()
        self.anomaly_list.setMaximumHeight(70)
        font = QFont()
        font.setPointSize(10)
        self.anomaly_list.setFont(font)
        self.content_layout.addWidget(self.anomaly_list)
        
        self.content_layout.addWidget(create_separator())

        # === Regions of Interest ===
        self.content_layout.addWidget(create_section_header("📍 Regions of Interest"))
        
        self.roi_list = QListWidget()
        self.roi_list.setMaximumHeight(80)
        font = QFont()
        font.setPointSize(10)
        self.roi_list.setFont(font)
        self.content_layout.addWidget(self.roi_list)

        # ROI palette selector (compact horizontal layout)
        roi_palette_layout = QHBoxLayout()
        roi_palette_layout.setSpacing(8)
        roi_label = QLabel("Palette:")
        font = QFont()
        font.setPointSize(10)
        roi_label.setFont(font)
        roi_palette_layout.addWidget(roi_label)
        
        self.roi_palette_combo = QComboBox()
        self.roi_palette_combo.setMinimumHeight(28)
        # Populate with all 45 palettes
        for palette in PaletteType:
            self.roi_palette_combo.addItem(palette.value.replace('_', ' ').title(), palette.value)
        roi_palette_layout.addWidget(self.roi_palette_combo, 1)
        self.content_layout.addLayout(roi_palette_layout)
        
        self.content_layout.addWidget(create_separator())

        # === Temperature Trend ===
        self.content_layout.addWidget(create_section_header("📈 Temperature Trend"))
        
        self.trend_label = QLabel("No trend data")
        self.trend_label.setWordWrap(True)
        font = QFont("Consolas", 10)
        self.trend_label.setFont(font)
        self.trend_label.setStyleSheet("padding: 5px;")
        self.content_layout.addWidget(self.trend_label)

        self.content_layout.addStretch()

        scroll.setWidget(content)
        main_layout.addWidget(scroll)
        
        self.baseline_btn.toggled.connect(self.baseline_toggled.emit)

    def update_rois(self, rois: List[ROI]):
        """Update ROI list."""
        self.roi_list.clear()
        for roi in rois:
            label = roi.label or f"{roi.roi_type.value} ({roi.roi_id[:8]})"
            self.roi_list.addItem(label)

    def update_statistics(self, stats: Optional[ThermalStatistics]):
        """Update temperature statistics display."""
        if stats is None:
            self.stats_label.setText("No data")
            return

        unit = stats.unit
        text = (
            f"Min:  {stats.min_temp:.1f}{unit}\n"
            f"Max:  {stats.max_temp:.1f}{unit}\n"
            f"Mean: {stats.mean_temp:.1f}{unit}\n"
            f"Std:  {stats.std_temp:.1f}{unit}"
        )
        
        if stats.relative_mean is not None:
            text += f"\n\nΔ Mean: {stats.relative_mean:+.1f}{unit}"
            
        self.stats_label.setText(text)

    def update_hot_spots(self, hot_spots: List[HotSpot]):
        """Update hot spot list."""
        self.hotspot_list.clear()
        for i, hs in enumerate(hot_spots):
            self.hotspot_list.addItem(f"#{i}: {hs.max_temp:.1f}{hs.unit} at ({hs.centroid[0]:.0f}, {hs.centroid[1]:.0f})")

    def update_cold_spots(self, cold_spots: List[ColdSpot]):
        """Update cold spot list."""
        self.coldspot_list.clear()
        for i, cs in enumerate(cold_spots):
            self.coldspot_list.addItem(f"#{i}: {cs.min_temp:.1f}{cs.unit} at ({cs.centroid[0]:.0f}, {cs.centroid[1]:.0f})")

    def update_anomalies(self, anomalies: List[ThermalAnomaly]):
        """Update anomaly list."""
        self.anomaly_list.clear()
        for i, anom in enumerate(anomalies, 1):
            self.anomaly_list.addItem(f"#{i}: {anom.anomaly_type} - {anom.description}")

    def update_trend(self, trend: Optional[TemperatureTrend]):
        """Update temperature trend display."""
        if trend is None or trend.data_points == 0:
            self.trend_label.setText("No trend data")
            return

        text = (
            f"Direction: {trend.trend_direction}\n"
            f"Rate: {trend.rate_of_change:.3f}°C/s\n"
            f"Predicted: {trend.predicted_temp:.1f}°C\n"
            f"Data points: {trend.data_points}"
        )
        self.trend_label.setText(text)


# ============================================================================
# Anomaly Priority Control Widget
# ============================================================================

class AnomalyWidget(QWidget):
    """Anomaly priority control panel widget."""

    # Signals
    anomaly_priority_toggled = pyqtSignal(bool)
    anomaly_types_changed = pyqtSignal(dict)
    fade_strength_changed = pyqtSignal(float)
    fade_distance_changed = pyqtSignal(int)
    motion_threshold_changed = pyqtSignal(int)
    edge_thresholds_changed = pyqtSignal(int, int)
    hot_spot_percentile_changed = pyqtSignal(int)
    cold_spot_percentile_changed = pyqtSignal(int)
    min_anomaly_size_changed = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(380)

        # State
        self.enabled_types = {
            "motion": True,
            "edges": True,
            "hot_spots": True,
            "cold_spots": True,
            "thermal_anomalies": True
        }

        self.anomaly_counts = {
            "motion": 0,
            "edges": 0,
            "hot_spots": 0,
            "cold_spots": 0,
            "thermal_anomalies": 0
        }

        self._init_ui()
        self._connect_signals()

    def _init_ui(self):
        """Initialize widget UI components."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(15)

        # Scroll area for content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget()
        self.content_layout = QVBoxLayout(content)
        self.content_layout.setSpacing(15)
        self.content_layout.setContentsMargins(5, 5, 5, 5)

        # 1. Main toggle
        self._create_main_toggle()

        # 2. Anomaly types multi-select
        self._create_type_selector()

        # 3. Gradient controls
        self._create_gradient_controls()

        # 4. Detection settings (collapsible)
        self._create_detection_settings()

        # 5. Performance display
        self._create_performance_display()

        self.content_layout.addStretch()

        scroll.setWidget(content)
        main_layout.addWidget(scroll)

    def _create_main_toggle(self):
        """Create main anomaly priority ON/OFF toggle."""
        toggle_group = QGroupBox("ANOMALY PRIORITY CONTROL")
        toggle_layout = QVBoxLayout(toggle_group)

        self.main_toggle = QPushButton("Anomaly Priority: OFF")
        self.main_toggle.setCheckable(True)
        self.main_toggle.setMinimumHeight(40)
        self.main_toggle.setToolTip("Enable/disable anomaly priority gradient fade visualization")

        toggle_layout.addWidget(self.main_toggle)
        self.content_layout.addWidget(toggle_group)

    def _create_type_selector(self):
        """Create anomaly type multi-select checkboxes."""
        type_group = QGroupBox("ANOMALY TYPES")
        type_layout = QVBoxLayout(type_group)

        info_label = QLabel("Select which detections to highlight:")
        info_label.setWordWrap(True)
        type_layout.addWidget(info_label)

        # Create checkboxes with live count labels
        self.type_checkboxes = {}
        self.type_count_labels = {}

        anomaly_type_configs = [
            ("motion", "Motion Detections", "Temporal changes between frames"),
            ("edges", "Edge Clusters", "Thermal boundary edges"),
            ("hot_spots", "Hot Spots", "95th percentile temperature"),
            ("cold_spots", "Cold Spots", "5th percentile temperature"),
            ("thermal_anomalies", "Thermal Anomalies", "Statistical outliers")
        ]

        for key, label, tooltip in anomaly_type_configs:
            row_layout = QHBoxLayout()

            checkbox = QCheckBox(label)
            checkbox.setChecked(True)
            checkbox.setToolTip(tooltip)
            self.type_checkboxes[key] = checkbox

            count_label = QLabel("(0 found)")
            count_label.setStyleSheet("font-size: 10px;")
            self.type_count_labels[key] = count_label

            row_layout.addWidget(checkbox)
            row_layout.addWidget(count_label)
            row_layout.addStretch()

            type_layout.addLayout(row_layout)

        # Total count
        self.total_count_label = QLabel("Total: 0 anomalies")
        font = QFont()
        font.setBold(True)
        self.total_count_label.setFont(font)
        type_layout.addWidget(self.total_count_label)

        self.content_layout.addWidget(type_group)

    def _create_gradient_controls(self):
        """Create gradient fade control sliders."""
        gradient_group = QGroupBox("GRADIENT FADE")
        gradient_layout = QVBoxLayout(gradient_group)

        # Fade Strength slider
        strength_label = QLabel("Fade Strength:")
        gradient_layout.addWidget(strength_label)

        strength_row = QHBoxLayout()
        self.fade_strength_slider = QSlider(Qt.Orientation.Horizontal)
        self.fade_strength_slider.setMinimum(5)  # 0.5
        self.fade_strength_slider.setMaximum(20)  # 2.0
        self.fade_strength_slider.setValue(10)  # 1.0
        self.fade_strength_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.fade_strength_slider.setTickInterval(5)
        self.fade_strength_slider.setToolTip("Controls gradient steepness (0.5 soft - 2.0 sharp)")

        self.fade_strength_value = QLabel("1.0")
        self.fade_strength_value.setMinimumWidth(35)

        strength_row.addWidget(self.fade_strength_slider)
        strength_row.addWidget(self.fade_strength_value)
        gradient_layout.addLayout(strength_row)

        strength_hint = QLabel("(0.5 soft ← → 2.0 sharp)")
        strength_hint.setStyleSheet("font-size: 9px;")
        gradient_layout.addWidget(strength_hint)

        # Fade Distance slider
        distance_label = QLabel("Fade Distance:")
        gradient_layout.addWidget(distance_label)

        distance_row = QHBoxLayout()
        self.fade_distance_slider = QSlider(Qt.Orientation.Horizontal)
        self.fade_distance_slider.setMinimum(50)
        self.fade_distance_slider.setMaximum(200)
        self.fade_distance_slider.setValue(100)
        self.fade_distance_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.fade_distance_slider.setTickInterval(50)
        self.fade_distance_slider.setToolTip("Maximum distance for gradient fade effect (pixels)")

        self.fade_distance_value = QLabel("100px")
        self.fade_distance_value.setMinimumWidth(50)

        distance_row.addWidget(self.fade_distance_slider)
        distance_row.addWidget(self.fade_distance_value)
        gradient_layout.addLayout(distance_row)

        distance_hint = QLabel("(50px ← → 200px)")
        distance_hint.setStyleSheet("font-size: 9px;")
        gradient_layout.addWidget(distance_hint)

        self.content_layout.addWidget(gradient_group)

    def _create_detection_settings(self):
        """Create collapsible detection settings section."""
        self.detection_group = QGroupBox("DETECTION SETTINGS")
        detection_layout = QVBoxLayout(self.detection_group)

        # Expand/Collapse button
        self.detection_expand_btn = QPushButton("Expand Settings")
        self.detection_expand_btn.setCheckable(True)
        self.detection_expand_btn.setMaximumHeight(28)
        detection_layout.addWidget(self.detection_expand_btn)

        # Collapsible content
        self.detection_content = QWidget()
        self.detection_content.setVisible(False)
        settings_layout = QVBoxLayout(self.detection_content)
        settings_layout.setContentsMargins(0, 0, 0, 0)

        # Motion Threshold
        motion_layout = QHBoxLayout()
        motion_layout.addWidget(QLabel("Motion Threshold:"))
        self.motion_threshold_spin = QSpinBox()
        self.motion_threshold_spin.setRange(5, 50)
        self.motion_threshold_spin.setValue(20)
        self.motion_threshold_spin.setToolTip("Sensitivity for motion detection")
        motion_layout.addWidget(self.motion_threshold_spin)
        settings_layout.addLayout(motion_layout)

        # Edge Thresholds
        edge_low_layout = QHBoxLayout()
        edge_low_layout.addWidget(QLabel("Edge Low:"))
        self.edge_low_spin = QSpinBox()
        self.edge_low_spin.setRange(10, 100)
        self.edge_low_spin.setValue(50)
        self.edge_low_spin.setToolTip("Low threshold for edge detection")
        edge_low_layout.addWidget(self.edge_low_spin)
        settings_layout.addLayout(edge_low_layout)

        edge_high_layout = QHBoxLayout()
        edge_high_layout.addWidget(QLabel("Edge High:"))
        self.edge_high_spin = QSpinBox()
        self.edge_high_spin.setRange(50, 200)
        self.edge_high_spin.setValue(150)
        self.edge_high_spin.setToolTip("High threshold for edge detection")
        edge_high_layout.addWidget(self.edge_high_spin)
        settings_layout.addLayout(edge_high_layout)

        # Hot Spot Percentile
        hot_layout = QHBoxLayout()
        hot_layout.addWidget(QLabel("Hot Spot %ile:"))
        self.hot_spot_spin = QSpinBox()
        self.hot_spot_spin.setRange(85, 99)
        self.hot_spot_spin.setValue(95)
        self.hot_spot_spin.setToolTip("Percentile threshold for hot spot detection")
        hot_layout.addWidget(self.hot_spot_spin)
        settings_layout.addLayout(hot_layout)

        # Cold Spot Percentile
        cold_layout = QHBoxLayout()
        cold_layout.addWidget(QLabel("Cold Spot %ile:"))
        self.cold_spot_spin = QSpinBox()
        self.cold_spot_spin.setRange(1, 15)
        self.cold_spot_spin.setValue(5)
        self.cold_spot_spin.setToolTip("Percentile threshold for cold spot detection")
        cold_layout.addWidget(self.cold_spot_spin)
        settings_layout.addLayout(cold_layout)

        # Min Anomaly Size
        size_layout = QHBoxLayout()
        size_layout.addWidget(QLabel("Min Size (px²):"))
        self.min_size_spin = QSpinBox()
        self.min_size_spin.setRange(100, 2000)
        self.min_size_spin.setValue(400)
        self.min_size_spin.setSingleStep(100)
        self.min_size_spin.setToolTip("Minimum anomaly area size filter")
        size_layout.addWidget(self.min_size_spin)
        settings_layout.addLayout(size_layout)

        detection_layout.addWidget(self.detection_content)
        self.content_layout.addWidget(self.detection_group)

    def _create_performance_display(self):
        """Create performance metrics display."""
        perf_group = QGroupBox("PERFORMANCE")
        perf_layout = QVBoxLayout(perf_group)

        self.fps_label = QLabel("FPS: --")
        self.processing_time_label = QLabel("Processing: --")
        self.overhead_label = QLabel("Overhead: --")

        self.overhead_bar = QProgressBar()
        self.overhead_bar.setRange(0, 100)
        self.overhead_bar.setValue(0)
        self.overhead_bar.setTextVisible(True)
        self.overhead_bar.setFormat("%p%")
        self.overhead_bar.setMaximumHeight(20)

        perf_layout.addWidget(self.fps_label)
        perf_layout.addWidget(self.processing_time_label)
        perf_layout.addWidget(self.overhead_label)
        perf_layout.addWidget(self.overhead_bar)

        self.content_layout.addWidget(perf_group)

    def _connect_signals(self):
        """Connect internal widget signals."""
        # Main toggle
        self.main_toggle.toggled.connect(self._on_main_toggle_changed)

        # Anomaly type checkboxes
        for key, checkbox in self.type_checkboxes.items():
            checkbox.stateChanged.connect(self._on_type_checkbox_changed)

        # Gradient sliders
        self.fade_strength_slider.valueChanged.connect(self._on_fade_strength_changed)
        self.fade_distance_slider.valueChanged.connect(self._on_fade_distance_changed)

        # Detection settings expand/collapse
        self.detection_expand_btn.toggled.connect(self._on_detection_expand_toggled)

        # Detection setting spinboxes
        self.motion_threshold_spin.valueChanged.connect(self.motion_threshold_changed.emit)
        self.edge_low_spin.valueChanged.connect(self._on_edge_thresholds_changed)
        self.edge_high_spin.valueChanged.connect(self._on_edge_thresholds_changed)
        self.hot_spot_spin.valueChanged.connect(self.hot_spot_percentile_changed.emit)
        self.cold_spot_spin.valueChanged.connect(self.cold_spot_percentile_changed.emit)
        self.min_size_spin.valueChanged.connect(self.min_anomaly_size_changed.emit)

    def _on_main_toggle_changed(self, checked: bool):
        """Handle main toggle state change."""
        self.main_toggle.setText(f"Anomaly Priority: {'ON' if checked else 'OFF'}")
        self.anomaly_priority_toggled.emit(checked)

    def _on_type_checkbox_changed(self):
        """Handle anomaly type checkbox changes."""
        for key, checkbox in self.type_checkboxes.items():
            self.enabled_types[key] = checkbox.isChecked()

        self.anomaly_types_changed.emit(self.enabled_types)
        self._update_total_count()

    def _on_fade_strength_changed(self, value: int):
        """Handle fade strength slider change."""
        strength = value / 10.0  # Convert 5-20 to 0.5-2.0
        self.fade_strength_value.setText(f"{strength:.1f}")
        self.fade_strength_changed.emit(strength)

    def _on_fade_distance_changed(self, value: int):
        """Handle fade distance slider change."""
        self.fade_distance_value.setText(f"{value}px")
        self.fade_distance_changed.emit(value)

    def _on_detection_expand_toggled(self, expanded: bool):
        """Handle detection settings expand/collapse."""
        self.detection_content.setVisible(expanded)
        self.detection_expand_btn.setText("Collapse Settings" if expanded else "Expand Settings")

    def _on_edge_thresholds_changed(self):
        """Handle edge threshold changes."""
        low = self.edge_low_spin.value()
        high = self.edge_high_spin.value()
        self.edge_thresholds_changed.emit(low, high)

    def update_counts(self, counts: dict):
        """Update live anomaly counts.

        Args:
            counts: Dict with keys matching enabled_types
        """
        for key, count in counts.items():
            if key in self.anomaly_counts:
                self.anomaly_counts[key] = count
                if key in self.type_count_labels:
                    self.type_count_labels[key].setText(f"({count} found)")

        self._update_total_count()

    def _update_total_count(self):
        """Update total anomaly count display."""
        total = sum(
            self.anomaly_counts[key]
            for key in self.enabled_types
            if self.enabled_types[key]
        )
        self.total_count_label.setText(f"Total: {total} anomalies")

    def update_performance(self, fps: float, processing_time: float, overhead: float = 0.0):
        """Update performance metrics.

        Args:
            fps: Current frames per second
            processing_time: Processing time in milliseconds
            overhead: Overhead percentage (0-100)
        """
        self.fps_label.setText(f"FPS: {fps:.1f}")
        self.processing_time_label.setText(f"Processing: {processing_time:.1f}ms")
        self.overhead_label.setText(f"Overhead: {overhead:.1f}%")

        self.overhead_bar.setValue(int(overhead))

        # Color code overhead bar
        if overhead < 10:
            color = "#4CAF50"  # Green
        elif overhead < 20:
            color = "#FFC107"  # Yellow
        else:
            color = "#F44336"  # Red

        self.overhead_bar.setStyleSheet(f"""
            QProgressBar::chunk {{
                background-color: {color};
            }}
        """)

    def set_anomaly_priority_enabled(self, enabled: bool):
        """Programmatically set anomaly priority state."""
        self.main_toggle.setChecked(enabled)


# ============================================================================
# Main Inspection Window
# ============================================================================

class BosonControlPanel(QWidget):
    """FLIR Boson camera control panel widget."""

    # Signals
    ffc_triggered = pyqtSignal()
    gain_mode_changed = pyqtSignal(str)  # 'high', 'low', 'auto'
    ffc_mode_changed = pyqtSignal(str)  # 'manual', 'auto', 'external'
    color_lut_changed = pyqtSignal(str)  # LUT name

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(380)
        self._init_ui()
        self._connect_signals()

    def _init_ui(self):
        """Initialize widget UI components."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(15)

        # Scroll area for content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setSpacing(15)
        content_layout.setContentsMargins(5, 5, 5, 5)

        # SDK Connection Status
        self._create_connection_status(content_layout)

        # Camera Info
        self._create_camera_info(content_layout)

        # FFC Controls
        self._create_ffc_controls(content_layout)

        # Gain Controls
        self._create_gain_controls(content_layout)

        # Color LUT Controls
        self._create_color_lut_controls(content_layout)

        # Temperature Display
        self._create_temperature_display(content_layout)

        content_layout.addStretch()
        scroll.setWidget(content)
        main_layout.addWidget(scroll)

    def _create_connection_status(self, layout):
        """Create SDK connection status display."""
        status_group = QGroupBox("SDK CONNECTION")
        status_layout = QVBoxLayout(status_group)

        self.connection_status_label = QLabel("● Disconnected")
        self.connection_status_label.setStyleSheet("color: #ff4444; font-weight: bold;")
        status_layout.addWidget(self.connection_status_label)

        self.connection_hint = QLabel("Enable SDK with --enable-boson-sdk")
        self.connection_hint.setStyleSheet("font-size: 10px; color: #888;")
        self.connection_hint.setWordWrap(True)
        status_layout.addWidget(self.connection_hint)

        layout.addWidget(status_group)

    def _create_camera_info(self, layout):
        """Create camera info display."""
        info_group = QGroupBox("CAMERA INFORMATION")
        info_layout = QVBoxLayout(info_group)

        self.info_labels = {}

        info_fields = [
            ('serial', 'Serial Number:'),
            ('part_number', 'Part Number:'),
            ('software', 'Software Version:'),
            ('lens', 'Lens Number:'),
            ('table', 'Table Number:')
        ]

        for key, label_text in info_fields:
            row = QHBoxLayout()
            label = QLabel(label_text)
            label.setStyleSheet("font-weight: bold; min-width: 120px;")
            value = QLabel("N/A")
            value.setStyleSheet("color: #888;")
            value.setWordWrap(True)

            row.addWidget(label)
            row.addWidget(value, stretch=1)

            self.info_labels[key] = value
            info_layout.addLayout(row)

        layout.addWidget(info_group)

    def _create_ffc_controls(self, layout):
        """Create FFC control buttons."""
        ffc_group = QGroupBox("FLAT FIELD CORRECTION (FFC)")
        ffc_layout = QVBoxLayout(ffc_group)

        # Manual FFC trigger button
        self.ffc_button = QPushButton("⚡ Trigger FFC")
        self.ffc_button.setMinimumHeight(40)
        self.ffc_button.setToolTip("Manually trigger Flat Field Correction (watch camera shutter)")
        ffc_layout.addWidget(self.ffc_button)

        # FFC Mode selection
        ffc_mode_layout = QHBoxLayout()
        ffc_mode_layout.addWidget(QLabel("FFC Mode:"))

        self.ffc_mode_combo = QComboBox()
        self.ffc_mode_combo.addItems(['Manual', 'Auto', 'External'])
        self.ffc_mode_combo.setToolTip("FFC mode: Manual, Auto, or External trigger")
        ffc_mode_layout.addWidget(self.ffc_mode_combo, stretch=1)

        ffc_layout.addLayout(ffc_mode_layout)

        # Last FFC status
        self.ffc_status_label = QLabel("Status: Ready")
        self.ffc_status_label.setStyleSheet("font-size: 10px; color: #888;")
        ffc_layout.addWidget(self.ffc_status_label)

        layout.addWidget(ffc_group)

    def _create_gain_controls(self, layout):
        """Create gain mode controls."""
        gain_group = QGroupBox("GAIN MODE")
        gain_layout = QVBoxLayout(gain_group)

        self.gain_mode_combo = QComboBox()
        self.gain_mode_combo.addItems(['High', 'Low', 'Auto'])
        self.gain_mode_combo.setToolTip("Sensor gain mode:\n• High: Optimal for low temps\n• Low: Optimal for high temps\n• Auto: Automatic switching")
        gain_layout.addWidget(self.gain_mode_combo)

        # Current gain display
        self.current_gain_label = QLabel("Current: Auto")
        self.current_gain_label.setStyleSheet("font-size: 10px; color: #888;")
        gain_layout.addWidget(self.current_gain_label)

        layout.addWidget(gain_group)

    def _create_color_lut_controls(self, layout):
        """Create color LUT controls."""
        lut_group = QGroupBox("COLOR LOOKUP TABLE (LUT)")
        lut_layout = QVBoxLayout(lut_group)

        self.color_lut_combo = QComboBox()
        self.color_lut_combo.addItems([
            'White Hot', 'Black Hot', 'Rainbow', 'Rainbow HC',
            'Ironbow', 'Lava', 'Arctic', 'Globow',
            'Graded Fire', 'Hottest'
        ])
        self.color_lut_combo.setToolTip("Hardware color palette (applies on-camera)")
        lut_layout.addWidget(self.color_lut_combo)

        hint = QLabel("Note: Hardware LUT applies before software processing")
        hint.setStyleSheet("font-size: 9px; color: #888;")
        hint.setWordWrap(True)
        lut_layout.addWidget(hint)

        layout.addWidget(lut_group)

    def _create_temperature_display(self, layout):
        """Create FPA temperature display."""
        temp_group = QGroupBox("FPA TEMPERATURE")
        temp_layout = QVBoxLayout(temp_group)

        self.fpa_temp_label = QLabel("N/A")
        self.fpa_temp_label.setStyleSheet("font-size: 24px; font-weight: bold; color: #00aaff;")
        self.fpa_temp_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        temp_layout.addWidget(self.fpa_temp_label)

        self.fpa_temp_unit = QLabel("Focal Plane Array Temperature")
        self.fpa_temp_unit.setStyleSheet("font-size: 10px; color: #888;")
        self.fpa_temp_unit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        temp_layout.addWidget(self.fpa_temp_unit)

        # Auto-refresh toggle
        refresh_layout = QHBoxLayout()
        self.temp_auto_refresh = QCheckBox("Auto-refresh (1s)")
        self.temp_auto_refresh.setChecked(True)
        self.temp_auto_refresh.setToolTip("Automatically read temperature every second")
        refresh_layout.addWidget(self.temp_auto_refresh)
        refresh_layout.addStretch()
        temp_layout.addLayout(refresh_layout)

        layout.addWidget(temp_group)

    def _connect_signals(self):
        """Connect internal signals."""
        self.ffc_button.clicked.connect(lambda: self.ffc_triggered.emit())
        self.gain_mode_combo.currentTextChanged.connect(
            lambda text: self.gain_mode_changed.emit(text.lower())
        )
        self.ffc_mode_combo.currentTextChanged.connect(
            lambda text: self.ffc_mode_changed.emit(text.lower())
        )
        self.color_lut_combo.currentTextChanged.connect(
            lambda text: self.color_lut_changed.emit(text.lower().replace(' ', '_'))
        )

    def update_connection_status(self, connected: bool):
        """Update SDK connection status."""
        if connected:
            self.connection_status_label.setText("● Connected")
            self.connection_status_label.setStyleSheet("color: #44ff44; font-weight: bold;")
            self.connection_hint.setText("SDK features available")

            # Enable controls
            self.ffc_button.setEnabled(True)
            self.gain_mode_combo.setEnabled(True)
            self.ffc_mode_combo.setEnabled(True)
            self.color_lut_combo.setEnabled(True)
        else:
            self.connection_status_label.setText("● Disconnected")
            self.connection_status_label.setStyleSheet("color: #ff4444; font-weight: bold;")
            self.connection_hint.setText("Enable SDK with --enable-boson-sdk")

            # Disable controls
            self.ffc_button.setEnabled(False)
            self.gain_mode_combo.setEnabled(False)
            self.ffc_mode_combo.setEnabled(False)
            self.color_lut_combo.setEnabled(False)

    def update_camera_info(self, info):
        """Update camera information display."""
        if hasattr(info, 'serial_number') and info.serial_number:
            self.info_labels['serial'].setText(info.serial_number)
            self.info_labels['serial'].setStyleSheet("color: #e0e0e0;")

        if hasattr(info, 'camera_part_number') and info.camera_part_number:
            self.info_labels['part_number'].setText(info.camera_part_number)
            self.info_labels['part_number'].setStyleSheet("color: #e0e0e0;")

        if hasattr(info, 'software_version') and info.software_version:
            self.info_labels['software'].setText(info.software_version)
            self.info_labels['software'].setStyleSheet("color: #e0e0e0;")

        if hasattr(info, 'lens_number') and info.lens_number is not None:
            self.info_labels['lens'].setText(str(info.lens_number))
            self.info_labels['lens'].setStyleSheet("color: #e0e0e0;")

        if hasattr(info, 'table_number') and info.table_number is not None:
            self.info_labels['table'].setText(str(info.table_number))
            self.info_labels['table'].setStyleSheet("color: #e0e0e0;")

        # Update gain mode if available
        if hasattr(info, 'gain_mode') and info.gain_mode:
            self.current_gain_label.setText(f"Current: {info.gain_mode.name}")
            self.current_gain_label.setStyleSheet("font-size: 10px; color: #00aaff;")

    def update_fpa_temperature(self, temp_kelvin: float, temp_celsius: float):
        """Update FPA temperature display."""
        self.fpa_temp_label.setText(f"{temp_celsius:.1f}°C")
        self.fpa_temp_unit.setText(f"({temp_kelvin:.1f}K)")

    def set_ffc_status(self, message: str, is_error: bool = False):
        """Update FFC status message."""
        color = "#ff4444" if is_error else "#44ff44"
        self.ffc_status_label.setText(f"Status: {message}")
        self.ffc_status_label.setStyleSheet(f"font-size: 10px; color: {color};")


class InspectionAppWindow(QMainWindow):
    """
    Main inspection application window.
    Replaces DriverAppWindow with inspection-focused UI.
    """

    def __init__(self, app_instance=None):
        super().__init__()
        self.app = app_instance

        # Window setup
        self.setWindowTitle("Thermal Inspection Fusion Tool v2.0")
        self.setMinimumSize(1280, 720)

        # State
        self.current_theme = "dark"
        self.developer_mode = False
        self.recording = False
        self.frozen = False

        # Build UI
        self._build_ui()

        # Apply initial theme
        self._apply_theme(self.current_theme)

    def _build_ui(self):
        """Build the main UI layout."""
        # Central widget
        central = QWidget()
        self.setCentralWidget(central)

        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Left side: Video + Controls
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)

        # Video widget
        self.video_widget = VideoWidget()
        left_layout.addWidget(self.video_widget, stretch=9)

        # Control panel
        self.control_panel = ControlPanel()
        left_layout.addWidget(self.control_panel, stretch=1)

        main_layout.addWidget(left_widget, stretch=7)

        # Right side: Tabbed widget panel (hidden by default)
        self.right_panel_tabs = QTabWidget()
        self.right_panel_tabs.setVisible(False)

        # Add Analysis Panel tab
        self.analysis_panel = ThermalAnalysisPanel()
        self.right_panel_tabs.addTab(self.analysis_panel, "Analysis")

        # Add Anomaly Widget tab
        self.anomaly_widget = AnomalyWidget()
        self.right_panel_tabs.addTab(self.anomaly_widget, "Anomaly")

        # Add Boson Control Panel tab
        self.boson_panel = BosonControlPanel()
        self.right_panel_tabs.addTab(self.boson_panel, "Boson")

        main_layout.addWidget(self.right_panel_tabs, stretch=2)

        # Info panel (overlay on video widget)
        self.info_panel = InfoPanel(self.video_widget)
        self.info_panel.move(10, 10)  # Top-left corner

        # Connect signals
        self._connect_signals()

    def _connect_signals(self):
        """Connect control panel signals to handlers."""
        # Simple controls
        self.control_panel.palette_clicked.connect(self._on_palette_cycle)
        self.control_panel.view_mode_clicked.connect(self._on_view_mode_cycle)
        self.control_panel.day_night_clicked.connect(self._on_theme_cycle)

        # Recording
        self.control_panel.record_toggled.connect(self._on_record_toggle)
        self.control_panel.snapshot_clicked.connect(self._on_snapshot)
        self.control_panel.freeze_frame_toggled.connect(self._on_freeze_toggle)

        # ROI
        self.control_panel.auto_roi_clicked.connect(self._on_auto_roi)
        self.control_panel.draw_roi_clicked.connect(self._on_draw_roi)
        self.control_panel.clear_rois_clicked.connect(self._on_clear_rois)
        self.control_panel.save_rois_clicked.connect(self._on_save_rois)
        self.control_panel.load_rois_clicked.connect(self._on_load_rois)

        # Processing
        self.control_panel.device_clicked.connect(self._on_device_cycle)
        self.control_panel.motion_detection_toggled.connect(self._on_motion_toggle)
        self.control_panel.edge_detection_toggled.connect(self._on_edge_toggle)
        self.control_panel.anomaly_priority_toggled.connect(self._on_anomaly_priority_toggle)

        # Fusion
        self.control_panel.fusion_mode_clicked.connect(self._on_fusion_mode_cycle)
        self.control_panel.fusion_alpha_clicked.connect(self._on_fusion_alpha_cycle)
        self.control_panel.fusion_alpha_clicked.connect(self._on_fusion_alpha_cycle)
        self.control_panel.fusion_priority_clicked.connect(self._on_fusion_priority_cycle)
        
        # Analysis
        self.analysis_panel.baseline_toggled.connect(self._on_baseline_toggle)

        # Boson Control Panel
        self.boson_panel.ffc_triggered.connect(self._on_boson_ffc)
        self.boson_panel.gain_mode_changed.connect(self._on_boson_gain_mode)
        self.boson_panel.ffc_mode_changed.connect(self._on_boson_ffc_mode)

        # Anomaly Widget
        self.anomaly_widget.anomaly_priority_toggled.connect(self._on_anomaly_priority_toggle)
        self.anomaly_widget.anomaly_types_changed.connect(self._on_anomaly_types_changed)
        self.anomaly_widget.fade_strength_changed.connect(self._on_fade_strength_changed)
        self.anomaly_widget.fade_distance_changed.connect(self._on_fade_distance_changed)
        self.anomaly_widget.motion_threshold_changed.connect(self._on_motion_threshold_changed)
        self.anomaly_widget.edge_thresholds_changed.connect(self._on_edge_thresholds_changed)
        self.anomaly_widget.hot_spot_percentile_changed.connect(self._on_hot_spot_percentile_changed)
        self.anomaly_widget.cold_spot_percentile_changed.connect(self._on_cold_spot_percentile_changed)
        self.anomaly_widget.min_anomaly_size_changed.connect(self._on_min_anomaly_size_changed)

        # ROI Overlay signals
        if hasattr(self.video_widget, 'overlay'):
            self.video_widget.overlay.roi_created.connect(self._on_roi_created)
            self.video_widget.overlay.roi_selected.connect(self._on_roi_selected)

    def keyPressEvent(self, event):
        """Handle keyboard shortcuts."""
        key = event.key()
        modifiers = event.modifiers()

        # Ctrl+D: Toggle developer mode
        if key == Qt.Key.Key_D and modifiers == Qt.KeyboardModifier.ControlModifier:
            self._toggle_developer_mode()
        # Q/Esc: Quit
        elif key in (Qt.Key.Key_Q, Qt.Key.Key_Escape):
            self.close()
        # V: Cycle view mode
        elif key == Qt.Key.Key_V:
            self._on_view_mode_cycle()
        # C: Cycle palette
        elif key == Qt.Key.Key_C:
            self._on_palette_cycle()
        # T: Cycle theme
        elif key == Qt.Key.Key_T:
            self._on_theme_cycle()
        # R: Record toggle
        elif key == Qt.Key.Key_R:
            self.control_panel.record_btn.setChecked(not self.recording)
        # S: Snapshot
        elif key == Qt.Key.Key_S:
            self._on_snapshot()
        # Space: Freeze toggle
        elif key == Qt.Key.Key_Space:
            self.control_panel.freeze_btn.setChecked(not self.frozen)
        # A: Auto ROI
        elif key == Qt.Key.Key_A:
            self._on_auto_roi()
        else:
            super().keyPressEvent(event)

    def _toggle_developer_mode(self):
        """Toggle developer mode (show/hide advanced controls and analysis panel)."""
        self.developer_mode = not self.developer_mode
        self.control_panel.show_developer_controls(self.developer_mode)
        self.right_panel_tabs.setVisible(self.developer_mode)

        # Adjust window size
        if self.developer_mode:
            self.resize(self.width() + 350, self.height())
        else:
            self.resize(self.width() - 350, self.height())

        logger.info(f"Developer mode: {'ON' if self.developer_mode else 'OFF'}")

    def _apply_theme(self, theme: str):
        """Apply color theme."""
        self.current_theme = theme

        # Determine actual theme to apply
        actual_theme = theme
        if theme == "auto":
            # Auto mode: Use system time or config settings
            import datetime
            hour = datetime.datetime.now().hour
            # Day mode: 7 AM - 7 PM, Night mode: 7 PM - 7 AM
            actual_theme = "light" if 7 <= hour < 19 else "dark"

        if actual_theme == "dark":
            self.setStyleSheet(DARK_THEME)
        elif actual_theme == "light":
            self.setStyleSheet(LIGHT_THEME)
        elif actual_theme == "solarized":
            self.setStyleSheet(SOLARIZED_THEME)
        elif actual_theme == "colorful":
            self.setStyleSheet(COLORFUL_THEME)

        # Update button to show current mode
        if theme == "auto":
            self.control_panel.update_theme_button(f"auto ({actual_theme})")
        else:
            self.control_panel.update_theme_button(theme)

    def _on_theme_cycle(self):
        """Cycle through themes."""
        themes = ["light", "dark", "solarized", "colorful", "auto"]
        current_idx = themes.index(self.current_theme) if self.current_theme in themes else 0
        next_theme = themes[(current_idx + 1) % len(themes)]
        self._apply_theme(next_theme)
        logger.info(f"Theme: {next_theme}")

    def _on_palette_cycle(self):
        """Cycle through palettes."""
        if self.app:
            self.app.cycle_palette()
        logger.info("Palette cycle")

    def _on_view_mode_cycle(self):
        """Cycle through view modes."""
        if self.app:
            self.app.cycle_view_mode()
        logger.info("View mode cycle")

    def _on_record_toggle(self, enabled: bool):
        """Toggle recording."""
        self.recording = enabled
        self.control_panel.update_record_button(enabled)
        if self.app:
            self.app.toggle_recording(enabled)
        logger.info(f"Recording: {'ON' if enabled else 'OFF'}")

    def _on_snapshot(self):
        """Take a snapshot."""
        if self.app:
            self.app.capture_snapshot()
        logger.info("Snapshot captured")

    def _on_freeze_toggle(self, enabled: bool):
        """Toggle frame freeze."""
        self.frozen = enabled
        self.control_panel.update_freeze_button(enabled)
        if self.app:
            self.app.toggle_freeze(enabled)
        logger.info(f"Frame freeze: {'ON' if enabled else 'OFF'}")

    def _on_auto_roi(self):
        """Trigger automatic ROI detection."""
        if self.app and hasattr(self.app, 'auto_roi_detect'):
            self.app.auto_roi_detect()
            logger.info("Auto ROI detection triggered")
        else:
            logger.warning("Auto ROI detection not available")

    def _on_draw_roi(self):
        """Enter ROI drawing mode."""
        if self.video_widget and hasattr(self.video_widget, 'overlay'):
            # Enable drawing mode on the overlay (default: rectangle)
            self.video_widget.overlay.enable_drawing_mode(ROIType.RECTANGLE)
            logger.info("Draw ROI mode activated (rectangle)")
            # Update button state
            self.control_panel.draw_roi_btn.setChecked(True)
        else:
            logger.warning("Video widget overlay not available")

    def _on_clear_rois(self):
        """Clear all ROIs."""
        if self.app:
            self.app.clear_rois()
        logger.info("ROIs cleared")

    def _on_save_rois(self):
        """Save ROIs to file."""
        filename, _ = QFileDialog.getSaveFileName(
            self, "Save ROIs", "", "JSON Files (*.json)"
        )
        if filename:
            if self.app:
                self.app.save_rois(filename)
            else:
                logger.info(f"ROIs saved to {filename}")

    def _on_load_rois(self):
        """Load ROIs from file."""
        filename, _ = QFileDialog.getOpenFileName(
            self, "Load ROIs", "", "JSON Files (*.json)"
        )
        if filename:
            if self.app:
                self.app.load_rois(filename)
            else:
                logger.info(f"ROIs loaded from {filename}")

    def _on_device_cycle(self):
        """Cycle processing device."""
        if self.app:
            self.app.cycle_device()
        logger.info("Device cycle")

    def _on_motion_toggle(self, enabled: bool):
        """Toggle motion detection."""
        self.control_panel.update_motion_button(enabled)
        if self.app:
            self.app.toggle_motion(enabled)
        logger.info(f"Motion detection: {'ON' if enabled else 'OFF'}")

    def _on_edge_toggle(self, enabled: bool):
        """Toggle edge detection."""
        self.control_panel.update_edge_button(enabled)
        if self.app:
            self.app.toggle_edge(enabled)
        logger.info(f"Edge detection: {'ON' if enabled else 'OFF'}")

    def _on_anomaly_priority_toggle(self, enabled: bool):
        """Toggle anomaly priority mode."""
        self.control_panel.update_anomaly_priority_button(enabled)
        if self.app:
            self.app.toggle_anomaly_priority(enabled)
        logger.info(f"Anomaly priority: {'ON' if enabled else 'OFF'}")

    def _on_anomaly_types_changed(self, types_dict: dict):
        """Handle anomaly type selection changes."""
        if self.app:
            self.app.set_enabled_anomaly_types(types_dict)
        logger.info(f"Anomaly types changed: {types_dict}")

    def _on_fade_strength_changed(self, value: float):
        """Handle fade strength changes."""
        if self.app and hasattr(self.app, 'thermal_processor'):
            self.app.thermal_processor.anomaly_fade_strength = value
        logger.info(f"Fade strength: {value}")

    def _on_fade_distance_changed(self, value: int):
        """Handle fade distance changes."""
        if self.app and hasattr(self.app, 'thermal_processor'):
            self.app.thermal_processor.anomaly_max_distance = value
        logger.info(f"Fade distance: {value}px")

    def _on_motion_threshold_changed(self, value: int):
        """Handle motion threshold changes."""
        if self.app and hasattr(self.app, 'thermal_processor'):
            self.app.thermal_processor.motion_threshold = value
        logger.info(f"Motion threshold: {value}")

    def _on_edge_thresholds_changed(self, low: int, high: int):
        """Handle edge threshold changes."""
        if self.app and hasattr(self.app, 'thermal_processor'):
            self.app.thermal_processor.edge_threshold_low = low
            self.app.thermal_processor.edge_threshold_high = high
        logger.info(f"Edge thresholds: {low}/{high}")

    def _on_hot_spot_percentile_changed(self, value: int):
        """Handle hot spot percentile changes."""
        if self.app and hasattr(self.app, 'thermal_analyzer'):
            self.app.thermal_analyzer.hot_spot_percentile = value
        logger.info(f"Hot spot percentile: {value}")

    def _on_cold_spot_percentile_changed(self, value: int):
        """Handle cold spot percentile changes."""
        if self.app and hasattr(self.app, 'thermal_analyzer'):
            self.app.thermal_analyzer.cold_spot_percentile = value
        logger.info(f"Cold spot percentile: {value}")

    def _on_min_anomaly_size_changed(self, value: int):
        """Handle minimum anomaly size changes."""
        if self.app and hasattr(self.app, 'thermal_analyzer'):
            self.app.thermal_analyzer.min_anomaly_size = value
        logger.info(f"Min anomaly size: {value}px²")

    def _on_fusion_mode_cycle(self):
        """Cycle fusion mode."""
        if self.app:
            self.app.cycle_fusion_mode()
        logger.info("Fusion mode cycle")

    def _on_fusion_alpha_cycle(self):
        """Cycle fusion alpha."""
        if self.app:
            self.app.cycle_fusion_alpha()
        logger.info("Fusion alpha cycle")

    def _on_fusion_priority_cycle(self):
        """Cycle fusion priority."""
        if self.app:
            self.app.cycle_fusion_priority()
        logger.info("Fusion priority cycle")

    def _on_baseline_toggle(self, enabled: bool):
        """Toggle baseline lock for relative temperature."""
        if self.app:
            # Call app's baseline toggle method
            if hasattr(self.app, 'lock_baseline'):
                self.app.lock_baseline(enabled)
        logger.info(f"Baseline lock: {'ON' if enabled else 'OFF'}")

    def _on_boson_ffc(self):
        """Handle FFC trigger from Boson panel."""
        if self.app and hasattr(self.app, 'trigger_ffc'):
            self.app.trigger_ffc()

    def _on_boson_gain_mode(self, mode: str):
        """Handle gain mode change from Boson panel."""
        if self.app and hasattr(self.app, 'set_boson_gain_mode'):
            self.app.set_boson_gain_mode(mode)

    def _on_boson_ffc_mode(self, mode: str):
        """Handle FFC mode change from Boson panel."""
        if self.app and hasattr(self.app, 'set_boson_ffc_mode'):
            self.app.set_boson_ffc_mode(mode)

    def _on_roi_created(self, roi):
        """Handle new ROI created from overlay."""
        try:
            # Add to app's ROI manager if available
            if self.app and hasattr(self.app, 'roi_manager'):
                self.app.roi_manager.add_roi(roi)
                logger.info(f"ROI created: {roi.label} ({roi.roi_type})")
            else:
                logger.warning("ROI manager not available")

            # Disable drawing mode after creating one ROI
            if hasattr(self.video_widget, 'overlay'):
                self.video_widget.overlay.disable_drawing_mode()

            # Uncheck the draw button
            if hasattr(self, 'control_panel') and hasattr(self.control_panel, 'draw_roi_btn'):
                self.control_panel.draw_roi_btn.setChecked(False)

        except Exception as e:
            logger.error(f"Error in _on_roi_created: {e}", exc_info=True)

    def _on_roi_selected(self, roi_id: str):
        """Handle ROI selection from overlay."""
        logger.info(f"ROI selected: {roi_id}")
        # Update analysis panel to show selected ROI stats
        if self.app and hasattr(self.app, 'roi_manager'):
            roi = self.app.roi_manager.get_roi_by_id(roi_id)
            if roi:
                # Could update a detail panel here
                pass

    def update_frame(self, frame: np.ndarray):
        """Update video display."""
        self.video_widget.update_frame(frame)

    def update_metrics(self, fps: float, roi_count: int, thermal_connected: bool, rgb_connected: bool):
        """Update info panel metrics."""
        self.info_panel.update_info(fps, roi_count, thermal_connected, rgb_connected, self.recording)

    def update_rois(self, rois: List[ROI]):
        """Update ROI visualization and list."""
        self.video_widget.update_rois(rois)
        self.analysis_panel.update_rois(rois)

    def update_thermal_analysis(self, stats: Optional[ThermalStatistics],
                                hot_spots: List[HotSpot],
                                cold_spots: List[ColdSpot],
                                anomalies: List[ThermalAnomaly],
                                motion_detections: List = None,
                                edge_clusters: List = None,
                                trend: Optional[TemperatureTrend] = None):
        """Update thermal analysis displays."""
        self.video_widget.update_thermal_detections(hot_spots, cold_spots, anomalies)
        self.analysis_panel.update_statistics(stats)
        self.analysis_panel.update_hot_spots(hot_spots)
        self.analysis_panel.update_cold_spots(cold_spots)
        self.analysis_panel.update_anomalies(anomalies)
        self.analysis_panel.update_trend(trend)

        # Update Anomaly Widget counts
        counts = {
            "hot_spots": len(hot_spots),
            "cold_spots": len(cold_spots),
            "thermal_anomalies": len(anomalies),
            "motion": len(motion_detections) if motion_detections else 0,
            "edges": len(edge_clusters) if edge_clusters else 0
        }
        self.anomaly_widget.update_counts(counts)


# ============================================================================
# Standalone Test
# ============================================================================

def main():
    """Standalone test of inspection GUI."""
    if not PYQT_AVAILABLE:
        print("ERROR: PyQt5 is required. Install with: pip3 install PyQt5")
        sys.exit(1)

    app = QApplication(sys.argv)
    window = InspectionAppWindow()
    window.show()

    # Test with dummy data
    import time
    dummy_frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
    window.update_frame(dummy_frame)
    window.update_metrics(fps=30.0, roi_count=3, thermal_connected=True, rgb_connected=True)

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
