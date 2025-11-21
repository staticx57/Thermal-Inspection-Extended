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
    from PyQt5.QtWidgets import (QMainWindow, QWidget, QLabel, QPushButton,
                                  QVBoxLayout, QHBoxLayout, QGridLayout, QApplication,
                                  QSizePolicy, QFileDialog, QListWidget, QListWidgetItem,
                                  QComboBox, QSpinBox, QDoubleSpinBox, QCheckBox,
                                  QGroupBox, QScrollArea, QTabWidget)
    from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QThread, QSize
    from PyQt5.QtGui import QImage, QPixmap, QFont, QPainter, QPen, QColor
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


# ============================================================================
# Inspection Overlay Widget
# ============================================================================

class InspectionOverlayWidget(QWidget):
    """
    Overlay widget for drawing ROIs, hot spots, cold spots, and anomalies.
    Replaces AlertOverlayWidget from ADAS system.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, False)  # Enable mouse interaction
        self.setStyleSheet("background: transparent;")

        self.rois: List[ROI] = []
        self.hot_spots: List[HotSpot] = []
        self.cold_spots: List[ColdSpot] = []
        self.anomalies: List[ThermalAnomaly] = []
        self.selected_roi_id: Optional[str] = None

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

    def set_selected_roi(self, roi_id: Optional[str]):
        """Highlight a specific ROI."""
        self.selected_roi_id = roi_id
        self.update()

    def paintEvent(self, event):
        """Draw ROIs and thermal detections."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

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

            # Draw based on ROI type
            if roi.roi_type == ROIType.RECTANGLE:
                x, y, w, h = roi.bounds
                painter.drawRect(int(x), int(y), int(w), int(h))
            elif roi.roi_type == ROIType.POLYGON and roi.polygon_points:
                from PyQt5.QtCore import QPoint
                points = [QPoint(int(p[0]), int(p[1])) for p in roi.polygon_points]
                from PyQt5.QtGui import QPolygon
                painter.drawPolygon(QPolygon(points))
            elif roi.roi_type == ROIType.ELLIPSE:
                x, y, w, h = roi.bounds
                painter.drawEllipse(int(x), int(y), int(w), int(h))
            elif roi.roi_type == ROIType.CIRCLE:
                x, y, w, h = roi.bounds
                radius = int(w / 2)
                center_x = int(x + radius)
                center_y = int(y + radius)
                painter.drawEllipse(center_x - radius, center_y - radius, radius * 2, radius * 2)

            # Draw label
            if roi.label:
                x, y, _, _ = roi.bounds
                painter.setPen(QPen(color, 1))
                painter.drawText(int(x), int(y) - 5, roi.label)

        # Draw hot spots
        for hot_spot in self.hot_spots:
            painter.setPen(QPen(QColor(255, 0, 0), 2))  # Red
            x, y = hot_spot.center
            painter.drawEllipse(int(x) - 5, int(y) - 5, 10, 10)
            painter.drawText(int(x) + 10, int(y), f"{hot_spot.temperature:.1f}°C")

        # Draw cold spots
        for cold_spot in self.cold_spots:
            painter.setPen(QPen(QColor(0, 128, 255), 2))  # Light blue
            x, y = cold_spot.center
            painter.drawEllipse(int(x) - 5, int(y) - 5, 10, 10)
            painter.drawText(int(x) + 10, int(y), f"{cold_spot.temperature:.1f}°C")

        # Draw anomalies
        for anomaly in self.anomalies:
            painter.setPen(QPen(QColor(255, 255, 0), 3))  # Yellow
            x, y = anomaly.location
            # Draw warning triangle
            painter.drawLine(int(x), int(y) - 10, int(x) - 8, int(y) + 6)
            painter.drawLine(int(x) - 8, int(y) + 6, int(x) + 8, int(y) + 6)
            painter.drawLine(int(x) + 8, int(y) + 6, int(x), int(y) - 10)
            painter.drawText(int(x) + 15, int(y), f"⚠ {anomaly.anomaly_type}")


# ============================================================================
# Video Display Widget
# ============================================================================

class VideoWidget(QLabel):
    """
    High-performance video display widget with embedded inspection overlay.
    Reuses frame buffers to reduce memory allocations on Jetson.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumSize(640, 480)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
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
        qimage = QImage(rgb_frame.data, width, height, bytes_per_line, QImage.Format_RGB888)

        # Deep copy to take ownership (crucial for thread safety)
        self._last_qimage = qimage.copy()

        # Scale to widget size and display
        self._last_qpixmap = QPixmap.fromImage(self._last_qimage).scaled(
            self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
        self.setPixmap(self._last_qpixmap)

    def update_rois(self, rois: List[ROI]):
        """Update ROIs on overlay."""
        self.overlay.update_rois(rois)

    def update_thermal_detections(self, hot_spots: List[HotSpot], cold_spots: List[ColdSpot], anomalies: List[ThermalAnomaly]):
        """Update thermal detections on overlay."""
        self.overlay.update_thermal_detections(hot_spots, cold_spots, anomalies)

    def resizeEvent(self, event):
        """Ensure overlay matches video widget size."""
        super().resizeEvent(event)
        self.overlay.setGeometry(self.rect())


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

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)

        # Main layout
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(10, 10, 10, 10)
        self.main_layout.setSpacing(10)

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

        self.dev_layout.addWidget(self.device_btn, 3, 0)
        self.dev_layout.addWidget(self.motion_btn, 3, 1)
        self.dev_layout.addWidget(self.edge_btn, 3, 2)

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
        self.palette_btn.clicked.connect(self.palette_clicked)
        self.view_btn.clicked.connect(self.view_mode_clicked)
        self.day_night_btn.clicked.connect(self.day_night_clicked)

        # Recording
        self.record_btn.toggled.connect(self.record_toggled)
        self.snapshot_btn.clicked.connect(self.snapshot_clicked)
        self.freeze_btn.toggled.connect(self.freeze_frame_toggled)

        # ROI
        self.auto_roi_btn.clicked.connect(self.auto_roi_clicked)
        self.draw_roi_btn.clicked.connect(self.draw_roi_clicked)
        self.clear_roi_btn.clicked.connect(self.clear_rois_clicked)
        self.save_roi_btn.clicked.connect(self.save_rois_clicked)
        self.load_roi_btn.clicked.connect(self.load_rois_clicked)

        # Processing
        self.device_btn.clicked.connect(self.device_clicked)
        self.motion_btn.toggled.connect(self.motion_detection_toggled)
        self.edge_btn.toggled.connect(self.edge_detection_toggled)

        # Fusion
        self.fusion_mode_btn.clicked.connect(self.fusion_mode_clicked)
        self.fusion_alpha_btn.clicked.connect(self.fusion_alpha_clicked)
        self.fusion_priority_btn.clicked.connect(self.fusion_priority_clicked)

    def show_developer_controls(self, show: bool):
        """Toggle developer controls visibility."""
        self.dev_controls.setVisible(show)

    def update_palette_button(self, palette: str):
        """Update palette button text."""
        self.palette_btn.setText(f"🎨 {palette.replace('_', ' ').title()}")

    def update_view_button(self, view: str):
        """Update view mode button text."""
        self.view_btn.setText(f"👁 {view.replace('_', ' ').title()}")

    def update_day_night_button(self, theme: str):
        """Update day/night button text."""
        if theme == "light":
            self.day_night_btn.setText("☀ Day")
        elif theme == "dark":
            self.day_night_btn.setText("🌙 Night")
        else:
            self.day_night_btn.setText("🌓 Auto")

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
        self.setAlignment(Qt.AlignLeft | Qt.AlignTop)
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

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(350)

        # Main layout with scroll area
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        content = QWidget()
        self.content_layout = QVBoxLayout(content)
        self.content_layout.setSpacing(10)

        # === ROI List ===
        roi_group = QGroupBox("Regions of Interest")
        roi_layout = QVBoxLayout(roi_group)

        self.roi_list = QListWidget()
        self.roi_list.setMaximumHeight(150)
        roi_layout.addWidget(self.roi_list)

        # ROI palette selector
        roi_palette_layout = QHBoxLayout()
        roi_palette_layout.addWidget(QLabel("ROI Palette:"))
        self.roi_palette_combo = QComboBox()
        # Populate with all 45 palettes
        for palette in PaletteType:
            self.roi_palette_combo.addItem(palette.value.replace('_', ' ').title(), palette.value)
        roi_palette_layout.addWidget(self.roi_palette_combo)
        roi_layout.addLayout(roi_palette_layout)

        self.content_layout.addWidget(roi_group)

        # === Temperature Statistics ===
        stats_group = QGroupBox("Temperature Statistics")
        stats_layout = QVBoxLayout(stats_group)

        self.stats_label = QLabel("No data")
        self.stats_label.setWordWrap(True)
        self.stats_label.setFont(QFont("Courier", 9))
        stats_layout.addWidget(self.stats_label)

        self.content_layout.addWidget(stats_group)

        # === Hot Spots ===
        hotspot_group = QGroupBox("Hot Spots")
        hotspot_layout = QVBoxLayout(hotspot_group)

        self.hotspot_list = QListWidget()
        self.hotspot_list.setMaximumHeight(100)
        hotspot_layout.addWidget(self.hotspot_list)

        self.content_layout.addWidget(hotspot_group)

        # === Cold Spots ===
        coldspot_group = QGroupBox("Cold Spots")
        coldspot_layout = QVBoxLayout(coldspot_group)

        self.coldspot_list = QListWidget()
        self.coldspot_list.setMaximumHeight(100)
        coldspot_layout.addWidget(self.coldspot_list)

        self.content_layout.addWidget(coldspot_group)

        # === Anomalies ===
        anomaly_group = QGroupBox("Thermal Anomalies")
        anomaly_layout = QVBoxLayout(anomaly_group)

        self.anomaly_list = QListWidget()
        self.anomaly_list.setMaximumHeight(120)
        anomaly_layout.addWidget(self.anomaly_list)

        self.content_layout.addWidget(anomaly_group)

        # === Temperature Trend ===
        trend_group = QGroupBox("Temperature Trend")
        trend_layout = QVBoxLayout(trend_group)

        self.trend_label = QLabel("No trend data")
        self.trend_label.setWordWrap(True)
        self.trend_label.setFont(QFont("Courier", 9))
        trend_layout.addWidget(self.trend_label)

        self.content_layout.addWidget(trend_group)

        self.content_layout.addStretch()

        scroll.setWidget(content)
        main_layout.addWidget(scroll)

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

        text = (
            f"Min:  {stats.min_temp:.1f}°C\n"
            f"Max:  {stats.max_temp:.1f}°C\n"
            f"Mean: {stats.mean_temp:.1f}°C\n"
            f"Std:  {stats.std_temp:.1f}°C"
        )
        self.stats_label.setText(text)

    def update_hot_spots(self, hot_spots: List[HotSpot]):
        """Update hot spot list."""
        self.hotspot_list.clear()
        for i, hs in enumerate(hot_spots, 1):
            self.hotspot_list.addItem(f"#{i}: {hs.temperature:.1f}°C at ({hs.center[0]:.0f}, {hs.center[1]:.0f})")

    def update_cold_spots(self, cold_spots: List[ColdSpot]):
        """Update cold spot list."""
        self.coldspot_list.clear()
        for i, cs in enumerate(cold_spots, 1):
            self.coldspot_list.addItem(f"#{i}: {cs.temperature:.1f}°C at ({cs.center[0]:.0f}, {cs.center[1]:.0f})")

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
# Main Inspection Window
# ============================================================================

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

        # Right side: Thermal Analysis Panel (hidden by default)
        self.analysis_panel = ThermalAnalysisPanel()
        self.analysis_panel.setVisible(False)
        main_layout.addWidget(self.analysis_panel, stretch=2)

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

        # Fusion
        self.control_panel.fusion_mode_clicked.connect(self._on_fusion_mode_cycle)
        self.control_panel.fusion_alpha_clicked.connect(self._on_fusion_alpha_cycle)
        self.control_panel.fusion_priority_clicked.connect(self._on_fusion_priority_cycle)

    def keyPressEvent(self, event):
        """Handle keyboard shortcuts."""
        key = event.key()
        modifiers = event.modifiers()

        # Ctrl+D: Toggle developer mode
        if key == Qt.Key_D and modifiers == Qt.ControlModifier:
            self._toggle_developer_mode()
        # Q/Esc: Quit
        elif key in (Qt.Key_Q, Qt.Key_Escape):
            self.close()
        # V: Cycle view mode
        elif key == Qt.Key_V:
            self._on_view_mode_cycle()
        # C: Cycle palette
        elif key == Qt.Key_C:
            self._on_palette_cycle()
        # T: Cycle theme
        elif key == Qt.Key_T:
            self._on_theme_cycle()
        # R: Record toggle
        elif key == Qt.Key_R:
            self.control_panel.record_btn.setChecked(not self.recording)
        # S: Snapshot
        elif key == Qt.Key_S:
            self._on_snapshot()
        # Space: Freeze toggle
        elif key == Qt.Key_Space:
            self.control_panel.freeze_btn.setChecked(not self.frozen)
        # A: Auto ROI
        elif key == Qt.Key_A:
            self._on_auto_roi()
        else:
            super().keyPressEvent(event)

    def _toggle_developer_mode(self):
        """Toggle developer mode (show/hide advanced controls and analysis panel)."""
        self.developer_mode = not self.developer_mode
        self.control_panel.show_developer_controls(self.developer_mode)
        self.analysis_panel.setVisible(self.developer_mode)

        # Adjust window size
        if self.developer_mode:
            self.resize(self.width() + 350, self.height())
        else:
            self.resize(self.width() - 350, self.height())

        logger.info(f"Developer mode: {'ON' if self.developer_mode else 'OFF'}")

    def _apply_theme(self, theme: str):
        """Apply color theme."""
        self.current_theme = theme
        if theme == "dark":
            self.setStyleSheet(DARK_THEME)
        elif theme == "light":
            self.setStyleSheet(LIGHT_THEME)
        self.control_panel.update_day_night_button(theme)

    def _on_theme_cycle(self):
        """Cycle through themes."""
        themes = ["light", "dark", "auto"]
        current_idx = themes.index(self.current_theme) if self.current_theme in themes else 0
        next_theme = themes[(current_idx + 1) % len(themes)]
        self._apply_theme(next_theme)
        logger.info(f"Theme: {next_theme}")

    def _on_palette_cycle(self):
        """Cycle through palettes."""
        if self.app:
            # Call app's palette cycle method
            pass
        logger.info("Palette cycle")

    def _on_view_mode_cycle(self):
        """Cycle through view modes."""
        if self.app:
            # Call app's view mode cycle method
            pass
        logger.info("View mode cycle")

    def _on_record_toggle(self, enabled: bool):
        """Toggle recording."""
        self.recording = enabled
        self.control_panel.update_record_button(enabled)
        if self.app:
            # Call app's record toggle method
            pass
        logger.info(f"Recording: {'ON' if enabled else 'OFF'}")

    def _on_snapshot(self):
        """Take a snapshot."""
        if self.app:
            # Call app's snapshot method
            pass
        logger.info("Snapshot captured")

    def _on_freeze_toggle(self, enabled: bool):
        """Toggle frame freeze."""
        self.frozen = enabled
        self.control_panel.update_freeze_button(enabled)
        if self.app:
            # Call app's freeze toggle method
            pass
        logger.info(f"Frame freeze: {'ON' if enabled else 'OFF'}")

    def _on_auto_roi(self):
        """Trigger automatic ROI detection."""
        if self.app:
            # Call app's auto ROI method
            pass
        logger.info("Auto ROI detection triggered")

    def _on_draw_roi(self):
        """Enter ROI drawing mode."""
        if self.app:
            # Call app's draw ROI method
            pass
        logger.info("Draw ROI mode activated")

    def _on_clear_rois(self):
        """Clear all ROIs."""
        if self.app:
            # Call app's clear ROIs method
            pass
        logger.info("ROIs cleared")

    def _on_save_rois(self):
        """Save ROIs to file."""
        filename, _ = QFileDialog.getSaveFileName(
            self, "Save ROIs", "", "JSON Files (*.json)"
        )
        if filename:
            if self.app:
                # Call app's save ROIs method with filename
                pass
            logger.info(f"ROIs saved to {filename}")

    def _on_load_rois(self):
        """Load ROIs from file."""
        filename, _ = QFileDialog.getOpenFileName(
            self, "Load ROIs", "", "JSON Files (*.json)"
        )
        if filename:
            if self.app:
                # Call app's load ROIs method with filename
                pass
            logger.info(f"ROIs loaded from {filename}")

    def _on_device_cycle(self):
        """Cycle processing device."""
        if self.app:
            # Call app's device cycle method
            pass
        logger.info("Device cycle")

    def _on_motion_toggle(self, enabled: bool):
        """Toggle motion detection."""
        self.control_panel.update_motion_button(enabled)
        if self.app:
            # Call app's motion toggle method
            pass
        logger.info(f"Motion detection: {'ON' if enabled else 'OFF'}")

    def _on_edge_toggle(self, enabled: bool):
        """Toggle edge detection."""
        self.control_panel.update_edge_button(enabled)
        if self.app:
            # Call app's edge toggle method
            pass
        logger.info(f"Edge detection: {'ON' if enabled else 'OFF'}")

    def _on_fusion_mode_cycle(self):
        """Cycle fusion mode."""
        if self.app:
            # Call app's fusion mode cycle method
            pass
        logger.info("Fusion mode cycle")

    def _on_fusion_alpha_cycle(self):
        """Cycle fusion alpha."""
        if self.app:
            # Call app's fusion alpha cycle method
            pass
        logger.info("Fusion alpha cycle")

    def _on_fusion_priority_cycle(self):
        """Cycle fusion priority."""
        if self.app:
            # Call app's fusion priority cycle method
            pass
        logger.info("Fusion priority cycle")

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
                                trend: Optional[TemperatureTrend] = None):
        """Update thermal analysis displays."""
        self.video_widget.update_thermal_detections(hot_spots, cold_spots, anomalies)
        self.analysis_panel.update_statistics(stats)
        self.analysis_panel.update_hot_spots(hot_spots)
        self.analysis_panel.update_cold_spots(cold_spots)
        self.analysis_panel.update_anomalies(anomalies)
        self.analysis_panel.update_trend(trend)


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
