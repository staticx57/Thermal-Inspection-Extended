#!/usr/bin/env python3
"""
Qt-based GUI for Thermal Fusion Driving Assist
Professional interface with proper theming, font rendering, and performance
Optimized for Jetson Orin and x86-64 platforms
"""
import sys
import numpy as np
from typing import List, Optional
import logging

try:
    from PyQt5.QtWidgets import (QMainWindow, QWidget, QLabel, QPushButton,
                                  QVBoxLayout, QHBoxLayout, QGridLayout, QApplication,
                                  QSizePolicy)
    from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QThread, QSize
    from PyQt5.QtGui import QImage, QPixmap, QFont
    PYQT_AVAILABLE = True
except ImportError:
    PYQT_AVAILABLE = False
    print("WARNING: PyQt5 not available. Install with: pip3 install PyQt5")

import cv2
from object_detector import Detection
# from road_analyzer import Alert, AlertLevel  # Commented out - road_analyzer removed

# Stub classes for compatibility
class AlertLevel:
    """Stub AlertLevel class for compatibility"""
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"

class Alert:
    """Stub Alert class for compatibility"""
    def __init__(self, level=AlertLevel.INFO, message="", detection=None):
        self.level = level
        self.message = message
        self.detection = detection
from view_mode import ViewMode
from developer_panel import DeveloperPanel
from alert_overlay import AlertOverlayWidget
from auto_daynight import get_detector as get_auto_daynight_detector

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
    color: #006600;
    border: 1px solid #404040;
    border-radius: 5px;
    padding: 10px;
    font-size: 12px;
    font-family: monospace;
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
    border: 2px solid #0066cc;
}

QPushButton:pressed {
    background-color: #e0e0e0;
}

QPushButton:checked {
    background-color: #0066cc;
    color: #ffffff;
    border: 2px solid #0088ff;
}

QPushButton:disabled {
    background-color: #f5f5f5;
    color: #999999;
    border: 2px solid #d0d0d0;
}

QLabel#info_panel {
    background-color: rgba(255, 255, 255, 220);
    color: #00ff00;
    border: 1px solid #c0c0c0;
    border-radius: 5px;
    padding: 10px;
    font-size: 12px;
    font-family: monospace;
}
"""


# ============================================================================
# Video Display Widget
# ============================================================================

class VideoWidget(QLabel):
    """
    High-performance video display widget with ADAS alert overlay
    Optimized for Jetson with frame buffer reuse
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignCenter)
        self.setScaledContents(False)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setStyleSheet("background-color: #000000;")

        # Performance optimization: Reuse buffers
        self._frame_buffer = None
        self._qimage_buffer = None

        # Alert overlay (ADAS-compliant)
        self.alert_overlay = AlertOverlayWidget(self)
        self.alert_overlay.setGeometry(self.rect())  # Cover entire video widget

        # Placeholder
        self._show_placeholder()

    def _show_placeholder(self):
        """Show placeholder when no video available"""
        placeholder = np.zeros((480, 640, 3), dtype=np.uint8)
        cv2.putText(placeholder, "Waiting for video...", (150, 240),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (128, 128, 128), 2)
        self.update_frame(placeholder)

    def update_frame(self, frame: np.ndarray):
        """
        Update displayed frame efficiently

        Args:
            frame: BGR numpy array (from OpenCV)
        """
        if frame is None or frame.size == 0:
            return

        try:
            # Convert BGR to RGB
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb.shape

            # Update alert overlay with actual frame dimensions
            # Detection bboxes are in video coordinates, not widget coordinates
            if hasattr(self, 'alert_overlay') and self.alert_overlay:
                self.alert_overlay.set_frame_dimensions(w, h)

            # CRITICAL FIX: Create QImage with proper data ownership
            # Problem: QImage(data, w, h, ...) doesn't copy - just holds pointer to numpy buffer
            # Solution: Convert to bytes() which creates a true copy that QImage owns
            bytes_per_line = ch * w

            # Make contiguous copy and convert to bytes for QImage to own
            rgb_bytes = rgb.tobytes()
            qimg = QImage(rgb_bytes, w, h, bytes_per_line, QImage.Format_RGB888).copy()

            # .copy() at end ensures QImage has its own deep copy of pixel data
            # Now completely isolated from worker thread's frame buffer

            # Convert to pixmap and scale to fit widget
            pixmap = QPixmap.fromImage(qimg)
            scaled_pixmap = pixmap.scaled(
                self.size(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation  # High quality scaling
            )

            self.setPixmap(scaled_pixmap)

        except Exception as e:
            logger.error(f"Error updating video frame: {e}")

    def update_alerts(self, alerts: List[Alert], detections: List[Detection]):
        """
        Update ADAS alert overlay

        Args:
            alerts: List of Alert objects from RoadAnalyzer
            detections: List of Detection objects for proximity zones
        """
        if self.alert_overlay:
            self.alert_overlay.update_alerts(alerts, detections)

    def resizeEvent(self, event):
        """Handle resize to keep alert overlay sized correctly"""
        super().resizeEvent(event)
        if hasattr(self, 'alert_overlay') and self.alert_overlay:
            self.alert_overlay.setGeometry(self.rect())

    def sizeHint(self):
        """Suggest reasonable default size"""
        return QSize(1280, 1024)


# ============================================================================
# Control Panel Widget
# ============================================================================

class ControlPanel(QWidget):
    """
    Control buttons for driving mode
    Emits signals for button clicks
    """

    # Simple mode signals (driving-relevant controls)
    palette_clicked = pyqtSignal()  # Thermal palette cycling
    audio_toggled = pyqtSignal(bool)  # Audio alerts toggle
    day_night_clicked = pyqtSignal()  # Day/Night brightness mode

    # Developer control signals (configuration, not for use while driving)
    view_mode_clicked = pyqtSignal()
    yolo_toggled = pyqtSignal(bool)
    retry_sensors_clicked = pyqtSignal()
    buffer_flush_toggled = pyqtSignal(bool)
    frame_skip_clicked = pyqtSignal()
    detection_toggled = pyqtSignal(bool)
    device_clicked = pyqtSignal()
    model_clicked = pyqtSignal()
    fusion_mode_clicked = pyqtSignal()
    fusion_alpha_clicked = pyqtSignal()
    fusion_priority_clicked = pyqtSignal()  # Toggle fusion priority
    fusion_intensity_clicked = pyqtSignal()  # Fusion intensity control
    sim_thermal_toggled = pyqtSignal(bool)  # Simulated thermal camera
    motion_detection_toggled = pyqtSignal(bool)  # Motion detection toggle
    object_detection_toggled = pyqtSignal(bool)  # Object detection toggle
    alert_override_clicked = pyqtSignal()  # Alert override toggle (3-state: AUTO/ON/OFF)
    thermal_colorize_toggled = pyqtSignal(bool)  # Thermal colorization mode toggle

    def __init__(self, parent=None):
        super().__init__(parent)

        # Simple mode buttons (always visible, driving-relevant)
        self.palette_btn = QPushButton("🌡️ Palette: IRONBOW")
        self.audio_btn = QPushButton("🔊 Audio: ON")
        self.day_night_btn = QPushButton("☀️ Day")

        # Developer control buttons (visible only in dev mode)
        self.view_btn = QPushButton("🎥 View: Thermal")
        self.yolo_btn = QPushButton("🎯 YOLO: OFF")
        self.retry_btn = QPushButton("🔄 Retry Sensors")
        self.buffer_flush_btn = QPushButton("💾 Flush: OFF")
        self.frame_skip_btn = QPushButton("⏩ Skip: 1")
        self.detection_btn = QPushButton("📦 BOX: ON")
        self.device_btn = QPushButton("🖥️ DEV: CPU")
        self.model_btn = QPushButton("🤖 MDL: V8N")
        self.fusion_mode_btn = QPushButton("🔀 FUS: ALPHA")
        self.fusion_alpha_btn = QPushButton("⚖️ α: 0.50")
        self.fusion_priority_btn = QPushButton("🎯 PRI: THRM")
        self.fusion_intensity_btn = QPushButton("💪 INT: 0.50")
        self.sim_thermal_btn = QPushButton("🧪 SIM: OFF")
        self.motion_detect_btn = QPushButton("🏃 MOT: ON")
        self.object_detect_btn = QPushButton("🎯 OBJ: ON")
        self.alert_override_btn = QPushButton("🔔 ALRT: AUTO")
        self.thermal_colorize_btn = QPushButton("🎨 TCLR: OFF")

        # Hide all developer controls by default
        self.view_btn.hide()
        self.yolo_btn.hide()
        self.retry_btn.hide()
        self.buffer_flush_btn.hide()
        self.frame_skip_btn.hide()
        self.detection_btn.hide()
        self.device_btn.hide()
        self.model_btn.hide()
        self.fusion_mode_btn.hide()
        self.fusion_alpha_btn.hide()
        self.fusion_priority_btn.hide()
        self.fusion_intensity_btn.hide()
        self.sim_thermal_btn.hide()
        self.motion_detect_btn.hide()
        self.object_detect_btn.hide()
        self.alert_override_btn.hide()
        self.thermal_colorize_btn.hide()

        # Make toggle buttons checkable
        self.yolo_btn.setCheckable(True)
        self.audio_btn.setCheckable(True)
        self.buffer_flush_btn.setCheckable(True)
        self.detection_btn.setCheckable(True)
        self.sim_thermal_btn.setCheckable(True)
        self.motion_detect_btn.setCheckable(True)
        self.object_detect_btn.setCheckable(True)
        self.thermal_colorize_btn.setCheckable(True)

        # Set initial checked states
        self.audio_btn.setChecked(True)  # Audio on by default
        self.motion_detect_btn.setChecked(True)  # Motion detection on by default
        self.object_detect_btn.setChecked(True)  # Object detection on by default

        # Simple mode signal connections (always visible)
        self.palette_btn.clicked.connect(self.palette_clicked.emit)
        self.audio_btn.toggled.connect(self._on_audio_toggled)
        self.day_night_btn.clicked.connect(self.day_night_clicked.emit)

        # Developer control signal connections (visible only in dev mode)
        self.view_btn.clicked.connect(self.view_mode_clicked.emit)
        self.yolo_btn.toggled.connect(self._on_yolo_toggled)
        self.retry_btn.clicked.connect(self.retry_sensors_clicked.emit)
        self.buffer_flush_btn.toggled.connect(self._on_buffer_flush_toggled)
        self.frame_skip_btn.clicked.connect(self.frame_skip_clicked.emit)
        self.detection_btn.toggled.connect(self._on_detection_toggled)
        self.device_btn.clicked.connect(self.device_clicked.emit)
        self.model_btn.clicked.connect(self.model_clicked.emit)
        self.fusion_mode_btn.clicked.connect(self.fusion_mode_clicked.emit)
        self.fusion_alpha_btn.clicked.connect(self.fusion_alpha_clicked.emit)
        self.fusion_priority_btn.clicked.connect(self.fusion_priority_clicked.emit)
        self.fusion_intensity_btn.clicked.connect(self.fusion_intensity_clicked.emit)
        self.sim_thermal_btn.toggled.connect(self._on_sim_thermal_toggled)
        self.motion_detect_btn.toggled.connect(self._on_motion_detect_toggled)
        self.object_detect_btn.toggled.connect(self._on_object_detect_toggled)
        self.alert_override_btn.clicked.connect(self._on_alert_override_clicked)
        self.thermal_colorize_btn.toggled.connect(self._on_thermal_colorize_toggled)

        # Main layout: Simple mode controls (SAE J2400 compliant - minimal, driving-relevant)
        main_layout = QHBoxLayout()
        main_layout.addWidget(self.palette_btn)
        main_layout.addWidget(self.audio_btn)
        main_layout.addStretch()  # Push day/night to right
        main_layout.addWidget(self.day_night_btn)

        # Developer controls: 6x3 grid layout (18 buttons)
        dev_controls_widget = QWidget()
        dev_grid = QGridLayout()
        dev_grid.setSpacing(5)
        dev_grid.setContentsMargins(5, 5, 5, 5)

        # Column 1: View & Detection
        dev_grid.addWidget(self.view_btn, 0, 0)
        dev_grid.addWidget(self.detection_btn, 1, 0)
        dev_grid.addWidget(self.device_btn, 2, 0)
        dev_grid.addWidget(self.motion_detect_btn, 3, 0)
        dev_grid.addWidget(self.retry_btn, 4, 0)  # Retry sensors button
        dev_grid.addWidget(self.alert_override_btn, 5, 0)  # Alert override toggle

        # Column 2: YOLO & Performance
        dev_grid.addWidget(self.yolo_btn, 0, 1)
        dev_grid.addWidget(self.buffer_flush_btn, 1, 1)
        dev_grid.addWidget(self.frame_skip_btn, 2, 1)
        dev_grid.addWidget(self.object_detect_btn, 3, 1)
        dev_grid.addWidget(self.fusion_intensity_btn, 4, 1)  # Fusion intensity control

        # Column 3: Model, Fusion & Debug
        dev_grid.addWidget(self.model_btn, 0, 2)
        dev_grid.addWidget(self.fusion_mode_btn, 1, 2)
        dev_grid.addWidget(self.fusion_alpha_btn, 2, 2)
        dev_grid.addWidget(self.fusion_priority_btn, 3, 2)
        dev_grid.addWidget(self.sim_thermal_btn, 4, 2)
        dev_grid.addWidget(self.thermal_colorize_btn, 5, 2)  # Thermal colorization mode

        dev_controls_widget.setLayout(dev_grid)
        dev_controls_widget.hide()  # Hidden by default
        self.dev_controls_widget = dev_controls_widget

        # Combine: Main controls + dev controls
        layout = QVBoxLayout()
        layout.addLayout(main_layout)
        layout.addWidget(dev_controls_widget)
        layout.setSpacing(5)
        layout.setContentsMargins(5, 5, 5, 5)

        self.setLayout(layout)

    def _on_yolo_toggled(self, checked: bool):
        """Update button text when toggled"""
        self.yolo_btn.setText(f"🎯 YOLO: {'ON' if checked else 'OFF'}")
        self.yolo_toggled.emit(checked)

    def _on_audio_toggled(self, checked: bool):
        """Update button text when toggled"""
        self.audio_btn.setText(f"{'🔊' if checked else '🔇'} Audio: {'ON' if checked else 'OFF'}")
        self.audio_toggled.emit(checked)

    def update_view_mode(self, mode: ViewMode):
        """Update view mode button text"""
        mode_text = {
            ViewMode.THERMAL_ONLY: "Thermal",
            ViewMode.RGB_ONLY: "RGB",
            ViewMode.FUSION: "Fusion",
            ViewMode.SIDE_BY_SIDE: "Side-by-Side",
            ViewMode.PICTURE_IN_PICTURE: "PiP"
        }.get(mode, "Unknown")
        self.view_btn.setText(f"🎥 View: {mode_text}")

    def update_theme_mode(self, theme: str):
        """Update theme button text"""
        # Map theme to display format
        theme_icons = {
            'dark': '🌙',
            'light': '☀️',
            'auto': '🌗'
        }
        theme_names = {
            'dark': 'Night',
            'light': 'Day',
            'auto': 'Auto'
        }
        icon = theme_icons.get(theme, '🎨')
        name = theme_names.get(theme, theme.title())
        self.day_night_btn.setText(f"{icon} {name}")

    def set_yolo_enabled(self, enabled: bool):
        """Set YOLO button state"""
        self.yolo_btn.setChecked(enabled)

    def set_audio_enabled(self, enabled: bool):
        """Set audio button state"""
        self.audio_btn.setChecked(enabled)

    def _on_buffer_flush_toggled(self, checked: bool):
        """Update buffer flush button text when toggled"""
        self.buffer_flush_btn.setText(f"💾 Flush: {'ON' if checked else 'OFF'}")
        self.buffer_flush_toggled.emit(checked)

    def set_buffer_flush_enabled(self, enabled: bool):
        """Set buffer flush button state"""
        self.buffer_flush_btn.setChecked(enabled)

    def set_frame_skip_value(self, value: int):
        """Update frame skip button text"""
        self.frame_skip_btn.setText(f"⏩ Skip: {value}")

    def _on_detection_toggled(self, checked: bool):
        """Update detection toggle button text when toggled"""
        self.detection_btn.setText(f"📦 BOX: {'ON' if checked else 'OFF'}")
        self.detection_toggled.emit(checked)

    def _on_sim_thermal_toggled(self, checked: bool):
        """Update simulated thermal button text when toggled"""
        self.sim_thermal_btn.setText(f"🧪 SIM: {'ON' if checked else 'OFF'}")
        self.sim_thermal_toggled.emit(checked)

    def _on_motion_detect_toggled(self, checked: bool):
        """Update motion detection button text when toggled"""
        self.motion_detect_btn.setText(f"🏃 MOT: {'ON' if checked else 'OFF'}")
        self.motion_detection_toggled.emit(checked)

    def _on_object_detect_toggled(self, checked: bool):
        """Update object detection button text when toggled"""
        self.object_detect_btn.setText(f"🎯 OBJ: {'ON' if checked else 'OFF'}")
        self.object_detection_toggled.emit(checked)

    def _on_alert_override_clicked(self):
        """Cycle through alert override modes: AUTO → ON → OFF → AUTO"""
        current_text = self.alert_override_btn.text()
        if "AUTO" in current_text:
            next_mode = "ON"
        elif "ON" in current_text:
            next_mode = "OFF"
        else:
            next_mode = "AUTO"

        self.alert_override_btn.setText(f"🔔 ALRT: {next_mode}")
        self.alert_override_clicked.emit()

    def _on_thermal_colorize_toggled(self, checked: bool):
        """Update thermal colorization button text when toggled"""
        self.thermal_colorize_btn.setText(f"🎨 TCLR: {'ON' if checked else 'OFF'}")
        self.thermal_colorize_toggled.emit(checked)

    def set_palette(self, palette_name: str):
        """Update palette button text"""
        # Truncate palette name to fit button (8 chars max)
        short_name = palette_name[:8].upper()
        self.palette_btn.setText(f"🎨 PAL: {short_name}")

    def set_detection_enabled(self, enabled: bool):
        """Set detection toggle button state"""
        self.detection_btn.setChecked(enabled)

    def set_device(self, device: str):
        """Update device button text"""
        self.device_btn.setText(f"🖥️ DEV: {device.upper()}")

    def set_model(self, model_name: str):
        """Update model button text"""
        # Convert yolov8n.pt -> V8N
        short_name = model_name.replace('.pt', '').replace('yolov8', 'V8').upper()
        self.model_btn.setText(f"🤖 MDL: {short_name}")

    def set_fusion_mode(self, mode: str):
        """Update fusion mode button text with proper abbreviations"""
        # Map full mode names to clear abbreviations
        mode_abbrev = {
            'alpha_blend': 'ALPHA',
            'edge_enhanced': 'EDGE',
            'thermal_overlay': 'OVERLY',
            'side_by_side': 'SIDE',
            'picture_in_picture': 'PIP',
            'max_intensity': 'MAX',
            'feature_weighted': 'WEIGHT'
        }
        short_name = mode_abbrev.get(mode, mode[:6].upper())
        self.fusion_mode_btn.setText(f"🔀 FUS: {short_name}")

    def set_fusion_alpha(self, alpha: float):
        """Update fusion alpha button text"""
        self.fusion_alpha_btn.setText(f"⚖️ α: {alpha:.2f}")

    def set_fusion_priority(self, priority: str):
        """Update fusion priority button text"""
        short_name = "THRM" if priority == "thermal" else "RGB"
        self.fusion_priority_btn.setText(f"🎯 PRI: {short_name}")

    def set_fusion_intensity(self, intensity: float):
        """Update fusion intensity button text"""
        self.fusion_intensity_btn.setText(f"💪 INT: {intensity:.2f}")

    def set_sim_thermal_enabled(self, enabled: bool):
        """Set simulated thermal camera button state"""
        self.sim_thermal_btn.setChecked(enabled)

    def show_developer_controls(self, show: bool):
        """Show or hide developer control buttons widget"""
        if show:
            self.dev_controls_widget.show()
            # Explicitly show all individual buttons (required in Qt - hidden children stay hidden)
            self.view_btn.show()
            self.yolo_btn.show()
            self.retry_btn.show()
            self.buffer_flush_btn.show()
            self.frame_skip_btn.show()
            self.detection_btn.show()
            self.device_btn.show()
            self.model_btn.show()
            self.fusion_mode_btn.show()
            self.fusion_alpha_btn.show()
            self.fusion_priority_btn.show()
            self.fusion_intensity_btn.show()
            self.sim_thermal_btn.show()
            self.motion_detect_btn.show()
            self.object_detect_btn.show()
            self.alert_override_btn.show()
            self.thermal_colorize_btn.show()
            # Force layout update to ensure visibility
            self.layout().invalidate()
            self.layout().activate()
            logger.info("Developer controls shown (18 controls in 6x3 grid)")
        else:
            self.dev_controls_widget.hide()
            # Hide individual buttons
            self.view_btn.hide()
            self.yolo_btn.hide()
            self.retry_btn.hide()
            self.buffer_flush_btn.hide()
            self.frame_skip_btn.hide()
            self.detection_btn.hide()
            self.device_btn.hide()
            self.model_btn.hide()
            self.fusion_mode_btn.hide()
            self.fusion_alpha_btn.hide()
            self.fusion_priority_btn.hide()
            self.fusion_intensity_btn.hide()
            self.sim_thermal_btn.hide()
            self.motion_detect_btn.hide()
            self.object_detect_btn.hide()
            self.alert_override_btn.hide()
            self.thermal_colorize_btn.hide()
            self.layout().invalidate()
            self.layout().activate()
            logger.info("Developer controls hidden")


# ============================================================================
# Info Panel Overlay Widget
# ============================================================================

class InfoPanel(QLabel):
    """
    Minimal ADAS-compliant status overlay
    Shows only essential driving-relevant information:
    - Performance quality (color-coded: green=good, yellow=degraded, red=critical)
    - System health (FPS)
    - Threat awareness (Active detections)
    - Sensor status (Critical alerts only)
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("info_panel")
        self.setAlignment(Qt.AlignCenter)  # Center text
        self.setWordWrap(True)  # Allow wrapping for long text

        # Fixed size for stable positioning (SAE J2400: peripheral, non-moving)
        self.setFixedSize(280, 70)

        # Will be positioned in resizeEvent (top-right corner per SAE J2400)
        # Always visible in simple mode - essential safety info
        self.show()

    def update_info(self, fps: float, detections: int,
                    thermal_connected: bool, rgb_connected: bool):
        """
        Update minimal status display with performance quality indicator

        Performance Quality Thresholds:
        - Green (●): FPS ≥ 20, all sensors nominal
        - Yellow (●): FPS 10-19 or sensor degraded (prompts: check dev mode)
        - Red (●): FPS < 10 or critical sensor failure (prompts: adjust settings)
        """
        # Determine performance quality
        performance_critical = fps < 10
        performance_degraded = (10 <= fps < 20) or not thermal_connected

        # Color-coded status indicator
        if performance_critical:
            status_icon = "🔴"  # Critical - immediate action needed
            hint = " (⚙ Ctrl+D)"  # Prompt to open dev mode
        elif performance_degraded or not rgb_connected:
            status_icon = "🟡"  # Degraded - consider tweaking
            hint = " (⚙)"  # Subtle hint
        else:
            status_icon = "🟢"  # Good - system nominal
            hint = ""  # No action needed

        # Two-row layout: Detection first (safety-critical), then system info

        # Row 1: DETECTION METRICS (most important - what driver needs)
        if detections > 0:
            row1 = f"🎯 {detections} Objects Detected"
        else:
            row1 = "[OK] Clear"

        # Row 2: SYSTEM STATUS (diagnostic info)
        # Build compact status line
        row2 = f"{status_icon} {fps:.0f}fps"

        # Add sensor warnings if critical
        if not thermal_connected and not rgb_connected:
            row2 += " | ⚠ NoCam"
        elif not thermal_connected:
            row2 += " | ⚠ NoThr"
        elif not rgb_connected:
            row2 += " | ⚠ NoRGB"

        # Add hint if performance degraded
        if hint:
            row2 += hint

        # Combine rows (simple concatenation)
        self.setText(f"{row1}\n{row2}")


# ============================================================================
# Main Application Window
# ============================================================================

class DriverAppWindow(QMainWindow):
    """
    Main Qt window for Thermal Fusion Driving Assist
    Handles video display, controls, and application state
    """

    def __init__(self, app=None):
        super().__init__()

        if not PYQT_AVAILABLE:
            raise ImportError("PyQt5 is required. Install with: pip3 install PyQt5")

        self.setWindowTitle("Thermal Fusion Driving Assist - Qt Edition")

        # Reference to main application (for button callbacks)
        self.app = app

        # Application state
        self.current_theme = 'dark'
        self.view_mode = ViewMode.THERMAL_ONLY
        self.developer_mode = False  # Developer panel hidden by default

        # Auto day/night detection
        self.auto_mode_enabled = False  # Auto theme switching disabled by default
        self.auto_daynight_detector = get_auto_daynight_detector()
        self.last_rgb_frame = None  # Store latest RGB frame for ambient light detection

        # Create central widget and layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Horizontal layout: Main content | Developer Panel
        horizontal_layout = QHBoxLayout()
        horizontal_layout.setContentsMargins(0, 0, 0, 0)
        horizontal_layout.setSpacing(0)
        # CRITICAL: Prevent layout from resizing window when widgets are shown/hidden
        horizontal_layout.setSizeConstraint(QHBoxLayout.SetNoConstraint)

        # Left side: Video + Controls (vertical layout)
        left_widget = QWidget()
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Video display (most of the space)
        self.video_widget = VideoWidget()
        main_layout.addWidget(self.video_widget, stretch=9)

        # Control panel (bottom area)
        self.control_panel = ControlPanel()
        main_layout.addWidget(self.control_panel, stretch=1)

        left_widget.setLayout(main_layout)
        horizontal_layout.addWidget(left_widget)

        # Right side: Developer Panel (initially hidden)
        self.developer_panel = DeveloperPanel()
        self.developer_panel.set_app_reference(app)
        self.developer_panel.hide()  # Hidden by default
        horizontal_layout.addWidget(self.developer_panel)

        central_widget.setLayout(horizontal_layout)

        # Info panel overlay (on top of video widget)
        self.info_panel = InfoPanel(self.video_widget)

        # Connect control panel signals
        self._connect_controls()

        # Apply initial theme
        self.apply_theme(self.current_theme)

        # Set window size
        self.resize(1280, 960)

        # CRITICAL: Initialize stored window sizes NOW (at creation, not first toggle)
        # This ensures we capture the INTENDED base size, not a grown size
        PANEL_WIDTH = 300
        self._base_window_size = QSize(1280, 960)  # Initial size
        self._expanded_window_size = QSize(1280 + PANEL_WIDTH, 960)  # With dev panel
        logger.info(f"Initialized window sizes - Base: {self._base_window_size.width()}x{self._base_window_size.height()}, "
                   f"Expanded: {self._expanded_window_size.width()}x{self._expanded_window_size.height()}")

        logger.info("Qt GUI initialized successfully")

    def set_app(self, app):
        """Set reference to main application after initialization"""
        self.app = app
        self._initialize_control_states()
        logger.info("Application reference set in Qt GUI")

    def _initialize_control_states(self):
        """Initialize all control button states from app configuration"""
        if not self.app:
            return

        # Standard controls
        self.control_panel.set_yolo_enabled(getattr(self.app, 'yolo_enabled', True))
        self.control_panel.set_audio_enabled(getattr(self.app, 'audio_enabled', True))
        self.control_panel.update_view_mode(getattr(self.app, 'view_mode', ViewMode.THERMAL_ONLY))

        # Developer controls - initial states
        self.control_panel.set_buffer_flush_enabled(getattr(self.app, 'buffer_flush_enabled', False))
        self.control_panel.set_frame_skip_value(getattr(self.app, 'frame_skip_value', 1))
        self.control_panel.set_detection_enabled(getattr(self.app, 'show_detections', True))
        self.control_panel.set_device(getattr(self.app, 'device', 'cpu'))

        # Get palette from detector if available
        if self.app.detector and hasattr(self.app.detector, 'palette_name'):
            self.control_panel.set_palette(self.app.detector.palette_name)
        else:
            self.control_panel.set_palette('ironbow')

        # Get model name
        model_name = getattr(self.app, 'model_name', 'yolov8n.pt')
        self.control_panel.set_model(model_name)

        # Get fusion settings
        fusion_mode = getattr(self.app, 'fusion_mode', 'alpha_blend')
        fusion_alpha = getattr(self.app, 'fusion_alpha', 0.5)
        fusion_priority = 'thermal'  # Default priority
        fusion_intensity = 0.5  # Default intensity
        if hasattr(self.app, 'fusion_processor') and self.app.fusion_processor:
            fusion_priority = getattr(self.app.fusion_processor, 'fusion_priority', 'thermal')
            fusion_intensity = getattr(self.app.fusion_processor, 'fusion_intensity', 0.5)
        self.control_panel.set_fusion_mode(fusion_mode)
        self.control_panel.set_fusion_alpha(fusion_alpha)
        self.control_panel.set_fusion_priority(fusion_priority)
        self.control_panel.set_fusion_intensity(fusion_intensity)

        # Simulated thermal camera (debug mode)
        sim_thermal = getattr(self.app, 'use_simulated_thermal', False)
        self.control_panel.set_sim_thermal_enabled(sim_thermal)

        logger.info("All control states initialized from app configuration")

    def _connect_controls(self):
        """Connect control panel button signals to handlers"""
        # Simple mode controls (always visible)
        self.control_panel.palette_clicked.connect(self._on_palette_cycle)
        self.control_panel.audio_toggled.connect(self._on_audio_toggle)
        self.control_panel.day_night_clicked.connect(self._on_day_night_toggle)

        # Developer controls (visible only in dev mode)
        self.control_panel.view_mode_clicked.connect(self._on_view_mode_cycle)
        self.control_panel.yolo_toggled.connect(self._on_yolo_toggle)
        self.control_panel.retry_sensors_clicked.connect(self._on_retry_sensors)
        self.control_panel.buffer_flush_toggled.connect(self._on_buffer_flush_toggle)
        self.control_panel.frame_skip_clicked.connect(self._on_frame_skip_cycle)
        self.control_panel.detection_toggled.connect(self._on_detection_toggle)
        self.control_panel.device_clicked.connect(self._on_device_toggle)
        self.control_panel.model_clicked.connect(self._on_model_cycle)
        self.control_panel.fusion_mode_clicked.connect(self._on_fusion_mode_cycle)
        self.control_panel.fusion_alpha_clicked.connect(self._on_fusion_alpha_adjust)
        self.control_panel.fusion_priority_clicked.connect(self._on_fusion_priority_toggle)
        self.control_panel.fusion_intensity_clicked.connect(self._on_fusion_intensity_adjust)
        self.control_panel.sim_thermal_toggled.connect(self._on_sim_thermal_toggle)
        self.control_panel.motion_detection_toggled.connect(self._on_motion_detection_toggle)
        self.control_panel.object_detection_toggled.connect(self._on_object_detection_toggle)
        self.control_panel.alert_override_clicked.connect(self._on_alert_override_toggle)
        self.control_panel.thermal_colorize_toggled.connect(self._on_thermal_colorize_toggle)
        
        # Connect developer panel signals
        if hasattr(self.developer_panel, 'palette_selected'):
            self.developer_panel.palette_selected.connect(self._on_palette_selected_from_dev_panel)
            
        logger.info("Control panel signals connected (all 22 controls)")

    def _on_view_mode_cycle(self):
        """Cycle through view modes"""
        if not self.app:
            return

        view_modes = [ViewMode.THERMAL_ONLY, ViewMode.RGB_ONLY, ViewMode.FUSION,
                      ViewMode.SIDE_BY_SIDE, ViewMode.PICTURE_IN_PICTURE]
        current_idx = view_modes.index(self.app.view_mode) if self.app.view_mode in view_modes else 0
        next_idx = (current_idx + 1) % len(view_modes)
        self.app.view_mode = view_modes[next_idx]
        self.set_view_mode(view_modes[next_idx])
        logger.info(f"View mode changed to: {view_modes[next_idx]}")

    def _on_yolo_toggle(self, enabled: bool):
        """Toggle YOLO detection - switches detector between model and edge modes"""
        if not self.app or not self.app.detector:
            return

        self.app.yolo_enabled = enabled

        # Switch detector mode dynamically
        if enabled:
            # Switch to YOLO model mode
            model_path = getattr(self.app, 'model_path', 'yolov8n.pt')
            success = self.app.detector.set_detection_mode('model', model_path)
            if success:
                logger.info(f"YOLO detection enabled (model mode with {model_path})")
            else:
                logger.error("Failed to enable YOLO - model loading failed")
                self.app.yolo_enabled = False
                self.control_panel.set_yolo_enabled(False)
        else:
            # Switch to edge detection mode
            self.app.detector.set_detection_mode('edge')
            logger.info("YOLO detection disabled (edge detection mode)")

    def _on_audio_toggle(self, enabled: bool):
        """Toggle audio alerts"""
        if not self.app:
            return
        self.app.audio_enabled = enabled
        logger.info(f"Audio alerts: {'enabled' if enabled else 'disabled'}")


    def _on_day_night_toggle(self):
        """Cycle between Day (light), Night (dark), and Auto modes for driving visibility"""
        # Cycle: Day → Night → Auto
        themes = ['light', 'dark', 'auto']
        theme_names = {'light': 'Day', 'dark': 'Night', 'auto': 'Auto'}
        theme_icons = {'light': '☀️', 'dark': '🌙', 'auto': '🌓'}

        current_idx = themes.index(self.current_theme) if self.current_theme in themes else 0
        next_idx = (current_idx + 1) % len(themes)
        new_theme = themes[next_idx]

        self.apply_theme(new_theme)

        # Update button text
        button_text = f"{theme_icons[new_theme]} {theme_names[new_theme]}"
        self.control_panel.day_night_btn.setText(button_text)

        logger.info(f"{theme_names[new_theme]} mode enabled (theme: {new_theme})")

    def _on_retry_sensors(self):
        """Retry sensor connections"""
        if not self.app:
            return
        logger.info("Retry sensors requested from GUI")
        # Reset scan timers to force immediate retry
        self.app.last_thermal_scan_time = 0
        if hasattr(self.app, 'frame_count'):
            self.app.frame_count = 0  # Trigger RGB retry on next frame

    def _on_buffer_flush_toggle(self, enabled: bool):
        """Toggle buffer flush"""
        if not self.app:
            return
        self.app.buffer_flush_enabled = enabled
        logger.info(f"Buffer flush: {'enabled' if enabled else 'disabled'}")

    def _on_frame_skip_cycle(self):
        """Cycle through frame skip values (1, 2, 3, 5, back to 1)"""
        if not self.app:
            return
        skip_values = [1, 2, 3, 5]
        current_idx = skip_values.index(self.app.frame_skip_value) if self.app.frame_skip_value in skip_values else 0
        next_idx = (current_idx + 1) % len(skip_values)
        self.app.frame_skip_value = skip_values[next_idx]
        self.control_panel.set_frame_skip_value(skip_values[next_idx])
        logger.info(f"Frame skip set to: {skip_values[next_idx]}")

    def _on_palette_cycle(self):
        """Cycle through thermal color palettes (mode-aware: Simple=6 palettes, Developer=24 palettes)"""
        if not self.app or not self.app.detector:
            return

        # Simple mode: ADAS-focused palettes (6 total)
        simple_mode_palettes = [
            'white_hot', 'black_hot', 'ironbow',
            'arctic', 'cividis', 'outdoor_alert'
        ]

        # Developer mode: All 24 palettes (ADAS + Scientific + Experimental)
        all_palettes = [
            # ADAS-Critical (Simple mode)
            'white_hot', 'black_hot', 'ironbow', 'arctic', 'cividis', 'outdoor_alert',
            # Scientific / Perceptually Uniform
            'viridis', 'plasma', 'lava', 'magma', 'bone', 'parula',
            # General Purpose
            'rainbow', 'rainbow_hc', 'sepia', 'gray', 'amber', 'ocean', 'feather',
            # Fun / Experimental
            'twilight', 'twilight_shifted', 'deepgreen', 'hsv', 'pink'
        ]

        # Select palette list based on mode
        if self.developer_mode:
            palettes = all_palettes
            mode_label = "Developer"
        else:
            palettes = simple_mode_palettes
            mode_label = "Simple"

        current = getattr(self.app.detector, 'thermal_palette', 'white_hot')
        current_idx = palettes.index(current) if current in palettes else 0
        next_idx = (current_idx + 1) % len(palettes)
        next_palette = palettes[next_idx]

        # Update detector palette
        if hasattr(self.app.detector, 'set_palette'):
            self.app.detector.set_palette(next_palette)
        self.control_panel.set_palette(next_palette)

        # Sync developer panel
        if hasattr(self.developer_panel, 'update_palette_selection'):
            self.developer_panel.update_palette_selection(next_palette)

        logger.info(f"Thermal palette [{mode_label} mode]: {next_palette} ({current_idx + 1}/{len(palettes)})")

    def _on_palette_selected_from_dev_panel(self, palette_name):
        """Handle palette selection from developer panel"""
        if not self.app or not self.app.detector:
            return
            
        # Update detector
        if hasattr(self.app.detector, 'set_palette'):
            self.app.detector.set_palette(palette_name)
            
        # Update simple control panel button
        self.control_panel.set_palette(palette_name)
        
        logger.info(f"Thermal palette set from dev panel: {palette_name}")

    def _on_detection_toggle(self, enabled: bool):
        """Toggle detection bounding box display"""
        if not self.app:
            return
        self.app.show_detections = enabled
        logger.info(f"Detection bounding boxes: {'shown' if enabled else 'hidden'}")

    def _on_device_toggle(self):
        """Toggle between CPU and CUDA for detection"""
        if not self.app:
            return
        current_device = getattr(self.app, 'device', 'cpu')
        new_device = 'cuda' if current_device == 'cpu' else 'cpu'

        # Update device (requires detector reload)
        self.app.device = new_device
        if self.app.detector and hasattr(self.app.detector, 'model'):
            try:
                self.app.detector.model.to(new_device)
                logger.info(f"Detection device switched to: {new_device.upper()}")
            except Exception as e:
                logger.error(f"Failed to switch device to {new_device}: {e}")
                # Revert on failure
                self.app.device = current_device
                new_device = current_device

        self.control_panel.set_device(new_device)

    def _on_model_cycle(self):
        """Cycle through YOLO model variants (presets + custom models from config)"""
        if not self.app:
            return

        # Get models from config
        from config import get_config
        config = get_config()

        # Build list of available models: presets + custom
        model_presets = config.get('model_presets', {})
        preset_models = list(model_presets.values())
        custom_models = config.get('custom_models', [])
        all_models = preset_models + custom_models

        if not all_models:
            all_models = ['yolov8n.pt', 'yolov8s.pt', 'yolov8m.pt', 'yolov8l.pt']  # Fallback

        # Get current model
        current = getattr(self.app, 'model_name', all_models[0])
        current_idx = all_models.index(current) if current in all_models else 0
        next_idx = (current_idx + 1) % len(all_models)
        next_model = all_models[next_idx]

        # Update model (requires detector reload)
        self.app.model_name = next_model
        config.set('yolo_model', next_model, save=True)

        # Check if it's a custom model
        is_custom = next_model in custom_models
        model_source = "Custom" if is_custom else "Preset"

        logger.info(f"YOLO model changed to: {next_model} ({model_source}) - restart detector to apply")
        self.control_panel.set_model(next_model)

    def _on_fusion_mode_cycle(self):
        """Cycle through fusion blend modes"""
        if not self.app:
            return
        # All 7 fusion modes from FusionProcessor (match actual implementation)
        modes = ['alpha_blend', 'edge_enhanced', 'thermal_overlay',
                 'side_by_side', 'picture_in_picture', 'max_intensity', 'feature_weighted']
        current = getattr(self.app, 'fusion_mode', 'alpha_blend')
        current_idx = modes.index(current) if current in modes else 0
        next_idx = (current_idx + 1) % len(modes)
        next_mode = modes[next_idx]

        self.app.fusion_mode = next_mode
        if self.app.fusion_processor and hasattr(self.app.fusion_processor, 'set_mode'):
            self.app.fusion_processor.set_mode(next_mode)

        self.control_panel.set_fusion_mode(next_mode)
        logger.info(f"Fusion mode: {next_mode}")

    def _on_fusion_alpha_adjust(self):
        """Adjust fusion alpha value (0.3, 0.5, 0.7, 0.9, back to 0.3)"""
        if not self.app:
            return
        alpha_values = [0.3, 0.5, 0.7, 0.9]
        current = getattr(self.app, 'fusion_alpha', 0.5)
        # Find closest value
        current_idx = min(range(len(alpha_values)), key=lambda i: abs(alpha_values[i] - current))
        next_idx = (current_idx + 1) % len(alpha_values)
        next_alpha = alpha_values[next_idx]

        self.app.fusion_alpha = next_alpha
        if self.app.fusion_processor and hasattr(self.app.fusion_processor, 'set_alpha'):
            self.app.fusion_processor.set_alpha(next_alpha)

        self.control_panel.set_fusion_alpha(next_alpha)
        logger.info(f"Fusion alpha: {next_alpha}")

    def _on_fusion_priority_toggle(self):
        """Toggle fusion priority between thermal and RGB"""
        if not self.app:
            return

        # Get current priority from fusion processor
        current_priority = 'thermal'
        if hasattr(self.app, 'fusion_processor') and self.app.fusion_processor:
            current_priority = getattr(self.app.fusion_processor, 'fusion_priority', 'thermal')

        # Toggle priority
        next_priority = 'rgb' if current_priority == 'thermal' else 'thermal'

        # Update fusion processor
        if self.app.fusion_processor and hasattr(self.app.fusion_processor, 'set_priority'):
            self.app.fusion_processor.set_priority(next_priority)

        # Update button display
        self.control_panel.set_fusion_priority(next_priority)
        logger.info(f"Fusion priority: {next_priority}")

    def _on_fusion_intensity_adjust(self):
        """Adjust fusion intensity value (0.2, 0.4, 0.6, 0.8, 1.0, back to 0.2)"""
        if not self.app:
            return

        intensity_values = [0.2, 0.4, 0.6, 0.8, 1.0]
        current = getattr(self.app.fusion_processor, 'fusion_intensity', 0.5) if hasattr(self.app, 'fusion_processor') and self.app.fusion_processor else 0.5
        # Find closest value
        current_idx = min(range(len(intensity_values)), key=lambda i: abs(intensity_values[i] - current))
        next_idx = (current_idx + 1) % len(intensity_values)
        next_intensity = intensity_values[next_idx]

        if self.app.fusion_processor and hasattr(self.app.fusion_processor, 'set_intensity'):
            self.app.fusion_processor.set_intensity(next_intensity)

        self.control_panel.set_fusion_intensity(next_intensity)
        logger.info(f"Fusion intensity: {next_intensity}")

    def _on_sim_thermal_toggle(self, enabled: bool):
        """Toggle simulated thermal camera for debugging"""
        if not self.app:
            return
        self.app.use_simulated_thermal = enabled
        logger.info(f"Simulated thermal camera: {'enabled' if enabled else 'disabled'}")

    def _on_motion_detection_toggle(self, enabled: bool):
        """Toggle motion detection"""
        if not self.app or not self.app.detector:
            return
        self.app.detector.set_motion_detection_enabled(enabled)
        logger.info(f"Motion detection: {'enabled' if enabled else 'disabled'}")

    def _on_object_detection_toggle(self, enabled: bool):
        """Toggle object detection (YOLO/edge)"""
        if not self.app or not self.app.detector:
            return
        self.app.detector.set_object_detection_enabled(enabled)
        logger.info(f"Object detection: {'enabled' if enabled else 'disabled'}")

    def _on_alert_override_toggle(self):
        """Cycle alert override through AUTO/ON/OFF modes"""
        if not self.app:
            return
        # Get current state from button text
        current_text = self.control_panel.alert_override_btn.text()
        if "AUTO" in current_text:
            mode = "auto"
        elif "ON" in current_text:
            mode = "on"
        else:
            mode = "off"

        # Store override state in app
        self.app.alert_override_mode = mode
        logger.info(f"Alert override: {mode.upper()} - {'follows detections' if mode == 'auto' else ('always show' if mode == 'on' else 'always hide')}")

    def _on_thermal_colorize_toggle(self, enabled: bool):
        """
        Toggle thermal colorization mode
        When enabled: switches to thermal view with white-hot palette and colors detections by warning level
        When disabled: restores previous settings
        """
        if not self.app:
            return

        if enabled:
            # Save current state
            self.thermal_colorize_saved_state = {
                'view_mode': self.app.view_mode,
                'palette': getattr(self.app.detector, 'thermal_palette', 'ironbow') if self.app.detector else 'ironbow',
                'show_detections': self.app.show_detections,
            }

            # Activate thermal colorization mode
            self.app.view_mode = ViewMode.THERMAL_ONLY
            self.set_view_mode(ViewMode.THERMAL_ONLY)

            # Set whitehot palette for better contrast
            if self.app.detector and hasattr(self.app.detector, 'set_thermal_palette'):
                self.app.detector.set_thermal_palette('whitehot')
                self.control_panel.set_palette('WHITEHOT')

            # Enable detections
            self.app.show_detections = True
            self.control_panel.set_detection_enabled(True)

            # Enable thermal colorization flag
            self.app.thermal_colorize_mode = True

            logger.info("Thermal colorization mode ENABLED (thermal view, whitehot palette, colored detections)")
        else:
            # Restore previous state
            if hasattr(self, 'thermal_colorize_saved_state'):
                saved = self.thermal_colorize_saved_state

                # Restore view mode
                self.app.view_mode = saved['view_mode']
                self.set_view_mode(saved['view_mode'])

                # Restore palette
                if self.app.detector and hasattr(self.app.detector, 'set_thermal_palette'):
                    self.app.detector.set_thermal_palette(saved['palette'])
                    self.control_panel.set_palette(saved['palette'])

                # Restore detection visibility
                self.app.show_detections = saved['show_detections']
                self.control_panel.set_detection_enabled(saved['show_detections'])

                # Clear saved state
                delattr(self, 'thermal_colorize_saved_state')

            # Disable thermal colorization flag
            self.app.thermal_colorize_mode = False

            logger.info("Thermal colorization mode DISABLED (restored previous settings)")

    def toggle_fullscreen(self):
        """Toggle fullscreen mode (F key)"""
        if self.isFullScreen():
            self.showNormal()
            logger.info("Fullscreen mode: OFF")
        else:
            self.showFullScreen()
            logger.info("Fullscreen mode: ON")

    def toggle_developer_mode(self):
        """
        Toggle developer mode panel and controls (Ctrl+D)
        Manages info panel visibility (hidden in dev mode, shown in simple mode)
        Note: Developer panel not intended for use while driving

        Uses stored window sizes to prevent growth on repeated toggles.
        Updates stored sizes when user manually resizes the window.
        """
        from PyQt5.QtCore import QSize

        self.developer_mode = not self.developer_mode

        # Unlock size constraints before resizing
        self.setMinimumSize(0, 0)
        self.setMaximumSize(16777215, 16777215)  # QWIDGETSIZE_MAX

        if self.developer_mode:
            # ENABLE: Show panel first, then resize
            # Show panel and controls
            self.developer_panel.show()
            # Initialize camera list when panel is shown
            if hasattr(self.developer_panel, 'update_camera_list'):
                try:
                    self.developer_panel.update_camera_list()
                except Exception as e:
                    logger.warning(f"Could not update camera list on panel show: {e}")
            self.control_panel.show_developer_controls(True)
            self.info_panel.hide()

            # Process pending events to ensure panel is fully shown
            from PyQt5.QtWidgets import QApplication
            QApplication.processEvents()

            # Now resize to expanded size
            self._programmatic_resize = True
            self.resize(self._expanded_window_size)
            self._programmatic_resize = False

            logger.info(f"[OK] Developer mode ENABLED | Window: {self._expanded_window_size.width()}x{self._expanded_window_size.height()}")
        else:
            # DISABLE: Hide panel FIRST, then resize to allow proper shrinking
            # Hide panel and controls
            self.developer_panel.hide()
            self.control_panel.show_developer_controls(False)
            self.info_panel.show()

            # CRITICAL: Process events to ensure Qt recalculates layout WITHOUT dev panel
            from PyQt5.QtWidgets import QApplication
            QApplication.processEvents()

            # Force layout to recalculate minimum size
            self.layout().invalidate()
            self.layout().activate()

            # Get the current minimum size hint from the layout
            min_size = self.minimumSizeHint()
            logger.debug(f"Layout minimum size hint: {min_size.width()}x{min_size.height()}")

            # Calculate target size: stored base width, minimum viable height
            target_width = self._base_window_size.width()
            # Use the smaller of: stored base height OR minimum size hint height
            target_height = min(self._base_window_size.height(), min_size.height())

            # If minimum size is reasonable, use it; otherwise use stored base
            if min_size.height() > 0 and min_size.height() < self._base_window_size.height():
                target_height = min_size.height()
                logger.debug(f"Using minimum height {target_height} (smaller than base {self._base_window_size.height()})")
            else:
                target_height = self._base_window_size.height()
                logger.debug(f"Using stored base height {target_height}")

            # Now resize to calculated size
            self._programmatic_resize = True
            self.resize(target_width, target_height)
            self.updateGeometry()  # Force geometry recalculation
            self._programmatic_resize = False

            # One more processEvents to apply the resize
            QApplication.processEvents()

            logger.info(f"[X] Developer mode DISABLED | Window: {target_width}x{target_height}")

    def keyPressEvent(self, event):
        """Handle keyboard shortcuts"""
        key = event.key()
        modifiers = event.modifiers()

        # Ctrl+D: Toggle developer mode
        if key == Qt.Key_D and modifiers & Qt.ControlModifier:
            self.toggle_developer_mode()
            return

        if key == Qt.Key_Q or key == Qt.Key_Escape:
            # Quit
            if self.app:
                self.app.running = False
            self.close()

        elif key == Qt.Key_V:
            # Cycle view mode
            self._on_view_mode_cycle()

        elif key == Qt.Key_Y:
            # Toggle YOLO
            if self.app:
                new_state = not self.app.yolo_enabled
                self.control_panel.yolo_btn.setChecked(new_state)
                # This will trigger _on_yolo_toggle() which handles mode switching

        elif key == Qt.Key_A:
            # Toggle audio
            if self.app:
                self.app.audio_enabled = not self.app.audio_enabled
                self.control_panel.set_audio_enabled(self.app.audio_enabled)

        # Key 'I' removed - info panel now auto-managed (always visible in simple mode)

        elif key == Qt.Key_T:
            # Cycle theme
            self._on_theme_toggle()

        elif key == Qt.Key_D:
            # Toggle detections display
            if self.app:
                self.app.show_detections = not self.app.show_detections
                logger.info(f"Show detections: {self.app.show_detections}")

        elif key == Qt.Key_R:
            # Retry sensors
            self._on_retry_sensors()

        elif key == Qt.Key_F:
            # Toggle fullscreen
            self.toggle_fullscreen()

        else:
            # Pass to parent
            super().keyPressEvent(event)

    def apply_theme(self, theme_name: str):
        """
        Apply color theme

        Design principle for ADAS driving safety:
        - 'light' mode = BRIGHT display for DAYTIME (offsets glare)
        - 'dark' mode = DARK display for NIGHTTIME (preserves night vision)
        - 'auto' mode = AUTOMATIC switching based on ambient/time/sunset
        """
        self.current_theme = theme_name

        # Enable/disable auto detection based on theme
        if theme_name == 'auto':
            self.auto_mode_enabled = True
            # Initial detection (will be updated regularly)
            detected_theme, method = self.auto_daynight_detector.detect_theme(self.last_rgb_frame)
            logger.info(f"Auto mode enabled: detected '{detected_theme}' via {method}")
            # Apply detected theme
            if detected_theme == 'dark':
                self.setStyleSheet(DARK_THEME)
            else:
                self.setStyleSheet(LIGHT_THEME)
        else:
            self.auto_mode_enabled = False
            if theme_name == 'dark':
                # Night mode: DARK display to preserve night vision
                self.setStyleSheet(DARK_THEME)
            elif theme_name == 'light':
                # Day mode: BRIGHT display to offset glare
                self.setStyleSheet(LIGHT_THEME)

        self.control_panel.update_theme_mode(theme_name)
        logger.info(f"Applied '{theme_name}' theme (Day=bright, Night=dark, Auto=intelligent)")

    def connect_worker_signals(self, worker):
        """
        Connect VideoProcessorWorker signals to GUI slots (Phase 3)
        This enables thread-safe communication from worker to GUI
        """
        worker.frame_ready.connect(self._on_frame_ready)
        worker.metrics_update.connect(self._on_metrics_update)
        logger.info("Worker signals connected to GUI")

    def _on_frame_ready(self, frame):
        """Handle frame_ready signal from worker thread (runs in main thread)"""
        self.update_frame(frame)

    def _on_metrics_update(self, metrics):
        """Handle metrics_update signal from worker thread (runs in main thread)"""
        self.update_metrics(
            fps=metrics.get('fps', 0.0),
            detections=metrics.get('detections', 0),
            thermal_connected=metrics.get('thermal_connected', False),
            rgb_connected=metrics.get('rgb_connected', False)
        )
        # Update control panel states
        if self.app:
            self.set_view_mode(self.app.view_mode)
            self.control_panel.set_yolo_enabled(self.app.yolo_enabled)
            self.control_panel.set_audio_enabled(self.app.audio_enabled)

        # Update ADAS alert overlay
        # IMPORTANT: Always call update_alerts, even with empty lists, to trigger timeout clearing
        alerts = metrics.get('alerts', [])
        detections_list = metrics.get('detections_list', [])

        # Respect alert override mode
        if self.app and hasattr(self.app, 'alert_override_mode'):
            mode = self.app.alert_override_mode
            if mode == "off":
                # Force alerts off regardless of detections
                self.video_widget.update_alerts([], [])
            elif mode == "on":
                # Force alerts on with current detections
                self.video_widget.update_alerts(alerts, detections_list)
            else:  # "auto"
                # Normal behavior - show alerts based on detections
                self.video_widget.update_alerts(alerts, detections_list)
        else:
            # Default behavior if override not set
            self.video_widget.update_alerts(alerts, detections_list)

        # Update developer panel if enabled
        if self.developer_mode and self.developer_panel:
            self.developer_panel.update_metrics(metrics)

        # Auto day/night detection (when enabled)
        if self.auto_mode_enabled:
            # Get RGB frame from metrics if available (for ambient light detection)
            rgb_frame = metrics.get('rgb_frame', None)
            if rgb_frame is not None:
                self.last_rgb_frame = rgb_frame

            # Detect optimal theme
            detected_theme, method = self.auto_daynight_detector.detect_theme(self.last_rgb_frame)

            # Apply detected theme if it changed
            # Compare against actual applied theme (not self.current_theme which is 'auto')
            current_applied = 'dark' if DARK_THEME in self.styleSheet() else 'light'
            if detected_theme != current_applied:
                logger.info(f"Auto theme switch: {current_applied} -> {detected_theme} (method: {method})")
                if detected_theme == 'dark':
                    self.setStyleSheet(DARK_THEME)
                else:
                    self.setStyleSheet(LIGHT_THEME)

    def update_frame(self, frame: np.ndarray):
        """Update video display (called from main loop)"""
        self.video_widget.update_frame(frame)

    def update_metrics(self, fps: float, detections: int,
                       thermal_connected: bool, rgb_connected: bool):
        """
        Update minimal info panel (ADAS-essential status)
        Hidden in developer mode - detailed metrics shown in dev panel instead
        """
        if not self.developer_mode:
            # Simple mode: Show minimal ADAS info
            self.info_panel.update_info(fps, detections,
                                        thermal_connected, rgb_connected)
            self.info_panel.show()
        else:
            # Developer mode: Hide basic info (dev panel has everything)
            self.info_panel.hide()

    def set_view_mode(self, mode: ViewMode):
        """Update view mode"""
        self.view_mode = mode
        self.control_panel.update_view_mode(mode)

    def resizeEvent(self, event):
        """
        Handle window resize - reposition info panel and track manual resizes

        When user manually resizes the window, update stored sizes to maintain
        the 300px delta between base and expanded sizes.
        """
        super().resizeEvent(event)

        # Reposition info panel
        if self.info_panel:
            # Top-right corner with fixed offset (SAE J2400: peripheral, stable position)
            # Panel is 280px wide, position 10px from right edge
            panel_x = self.video_widget.width() - 290  # 280px width + 10px margin
            self.info_panel.move(panel_x, 10)

        # Track manual resizes and update stored sizes
        # Only update if:
        # 1. Stored sizes are initialized
        # 2. This resize wasn't triggered by toggle_developer_mode()
        if hasattr(self, '_base_window_size') and not getattr(self, '_programmatic_resize', False):
            PANEL_WIDTH = 300
            new_size = self.size()

            if self.developer_mode:
                # User resized while dev panel is shown
                # Update expanded size, recalculate base (expanded - panel width)
                self._expanded_window_size = new_size
                self._base_window_size = QSize(
                    new_size.width() - PANEL_WIDTH,
                    new_size.height()
                )
                logger.debug(f"[RESIZE] Manual resize in dev mode - Updated sizes: "
                           f"Base: {self._base_window_size.width()}x{self._base_window_size.height()}, "
                           f"Expanded: {self._expanded_window_size.width()}x{self._expanded_window_size.height()}")
            else:
                # User resized while dev panel is hidden
                # Update base size, recalculate expanded (base + panel width)
                self._base_window_size = new_size
                self._expanded_window_size = QSize(
                    new_size.width() + PANEL_WIDTH,
                    new_size.height()
                )
                logger.debug(f"[RESIZE] Manual resize in simple mode - Updated sizes: "
                           f"Base: {self._base_window_size.width()}x{self._base_window_size.height()}, "
                           f"Expanded: {self._expanded_window_size.width()}x{self._expanded_window_size.height()}")

    def closeEvent(self, event):
        """Handle window close"""
        logger.info("Qt GUI closing...")
        event.accept()


# ============================================================================
# Standalone Test
# ============================================================================

def main():
    """Test Qt GUI with dummy video"""
    app = QApplication(sys.argv)

    window = DriverAppWindow()
    window.show()

    # Dummy video timer
    def update_test_frame():
        import time
        frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
        cv2.putText(frame, f"Test Frame {int(time.time())}", (50, 240),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        window.update_frame(frame)
        window.update_metrics(fps=30.0, detections=5,
                              thermal_connected=True, rgb_connected=False)

    timer = QTimer()
    timer.timeout.connect(update_test_frame)
    timer.start(33)  # ~30 FPS

    sys.exit(app.exec_())


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    main()
