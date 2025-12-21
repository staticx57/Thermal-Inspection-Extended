"""
Control panel widget with inspection-specific buttons.
"""

from PyQt6.QtWidgets import (
    QWidget, QPushButton, QVBoxLayout, QGridLayout, QSizePolicy
)
from PyQt6.QtCore import pyqtSignal


class ControlPanel(QWidget):
    """
    Control panel with inspection-specific buttons.
    Streamlined to 7 core functions.
    """

    # Signals
    record_toggled = pyqtSignal(bool)
    snapshot_clicked = pyqtSignal()
    freeze_frame_toggled = pyqtSignal(bool)
    camera_clicked = pyqtSignal()
    auto_roi_clicked = pyqtSignal()
    draw_roi_clicked = pyqtSignal()
    clear_rois_clicked = pyqtSignal()
    view_mode_clicked = pyqtSignal()
    day_night_clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)

        # Main layout
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(10, 10, 10, 10)
        self.main_layout.setSpacing(12)

        # Controls Layout (Grid)
        self.controls_layout = QGridLayout()
        self.controls_layout.setSpacing(10)

        # Row 0: Capture & Camera
        self.record_btn = QPushButton("⏺ Record")
        self.record_btn.setCheckable(True)
        self.record_btn.setMinimumWidth(100)
        self.record_btn.setToolTip("Toggle video recording")

        self.snapshot_btn = QPushButton("📷 Snapshot")
        self.snapshot_btn.setMinimumWidth(100)
        self.snapshot_btn.setToolTip("Capture snapshot")

        self.freeze_btn = QPushButton("⏸ Freeze")
        self.freeze_btn.setCheckable(True)
        self.freeze_btn.setMinimumWidth(100)
        self.freeze_btn.setToolTip("Freeze/Unfreeze frame")

        self.camera_btn = QPushButton("🎥 Cameras")
        self.camera_btn.setMinimumWidth(100)
        self.camera_btn.setToolTip("Manage camera connections")

        self.controls_layout.addWidget(self.record_btn, 0, 0)
        self.controls_layout.addWidget(self.snapshot_btn, 0, 1)
        self.controls_layout.addWidget(self.freeze_btn, 0, 2)
        self.controls_layout.addWidget(self.camera_btn, 0, 3)

        # Row 1: ROI Controls
        self.auto_roi_btn = QPushButton("🔍 Auto ROI")
        self.auto_roi_btn.setMinimumWidth(100)
        self.auto_roi_btn.setToolTip("Automatically detect ROIs")

        self.draw_roi_btn = QPushButton("✏ Draw ROI")
        self.draw_roi_btn.setCheckable(True)
        self.draw_roi_btn.setMinimumWidth(100)
        self.draw_roi_btn.setToolTip("Manually draw ROI")

        self.clear_roi_btn = QPushButton("🗑 Clear ROIs")
        self.clear_roi_btn.setMinimumWidth(100)
        self.clear_roi_btn.setToolTip("Clear all ROIs")

        self.controls_layout.addWidget(self.auto_roi_btn, 1, 0)
        self.controls_layout.addWidget(self.draw_roi_btn, 1, 1)
        self.controls_layout.addWidget(self.clear_roi_btn, 1, 2)

        # Row 2: View Controls
        self.view_mode_btn = QPushButton("👁 View Mode")
        self.view_mode_btn.setMinimumWidth(100)
        self.view_mode_btn.setToolTip("Cycle view mode (Thermal/RGB/Fusion/Side-by-Side/PiP)")

        self.theme_btn = QPushButton("🌓 Theme")
        self.theme_btn.setMinimumWidth(100)
        self.theme_btn.setToolTip("Toggle dark/light theme")

        self.controls_layout.addWidget(self.view_mode_btn, 2, 0)
        self.controls_layout.addWidget(self.theme_btn, 2, 1)

        self.main_layout.addLayout(self.controls_layout)

        # Connect signals
        self._connect_signals()

    def _connect_signals(self):
        """Connect button signals."""
        self.record_btn.toggled.connect(self.record_toggled.emit)
        self.snapshot_btn.clicked.connect(lambda: self.snapshot_clicked.emit())
        self.freeze_btn.toggled.connect(self.freeze_frame_toggled.emit)
        self.camera_btn.clicked.connect(lambda: self.camera_clicked.emit())
        self.auto_roi_btn.clicked.connect(lambda: self.auto_roi_clicked.emit())
        self.draw_roi_btn.clicked.connect(lambda: self.draw_roi_clicked.emit())
        self.clear_roi_btn.clicked.connect(lambda: self.clear_rois_clicked.emit())
        self.view_mode_btn.clicked.connect(lambda: self.view_mode_clicked.emit())
        self.theme_btn.clicked.connect(lambda: self.day_night_clicked.emit())

    def update_record_button(self, recording: bool):
        """Update record button state."""
        if recording:
            self.record_btn.setText("⏹ Stop")
            self.record_btn.setStyleSheet("background-color: #ff4444; color: white;")
        else:
            self.record_btn.setText("⏺ Record")
            self.record_btn.setStyleSheet("")
        self.record_btn.setChecked(recording)

    def update_freeze_button(self, frozen: bool):
        """Update freeze button state."""
        if frozen:
            self.freeze_btn.setText("▶ Resume")
            self.freeze_btn.setStyleSheet("background-color: #4444ff; color: white;")
        else:
            self.freeze_btn.setText("⏸ Freeze")
            self.freeze_btn.setStyleSheet("")
        self.freeze_btn.setChecked(frozen)

    def update_theme_button(self, theme: str):
        """Update theme button display - shows current theme."""
        # Theme icons and display names
        theme_info = {
            "Dark Mode": ("🌙", "Dark"),
            "Light Mode": ("☀", "Light"),
            "Solarized": ("🌅", "Solarized"),
            "Colorful": ("🎨", "Colorful"),
            "Win XP Luna": ("🖼", "XP Luna"),
            "Silver": ("💿", "XP Silver"),
            "Olive": ("🌿", "XP Olive"),
            "auto": ("🔄", "Auto")
        }

        # Handle auto mode with actual theme in parentheses
        display_theme = theme
        if "auto (" in theme:
            # Extract actual theme from "auto (dark)" or "auto (light)"
            display_theme = "auto"
            icon, name = theme_info.get("auto", ("🔄", "Auto"))
            self.theme_btn.setText(f"{icon} {theme.replace('auto ', 'Auto ')}")
            self.theme_btn.setToolTip(f"Theme: {theme} - Click to cycle")
        else:
            icon, name = theme_info.get(theme, ("🌓", "Theme"))
            self.theme_btn.setText(f"{icon} {name}")
            self.theme_btn.setToolTip(f"Theme: {name} - Click to cycle")

    def update_view_button(self, view_mode):
        """Update view mode button display."""
        from view_mode import ViewMode
        mode_names = {
            ViewMode.THERMAL_ONLY: "Thermal",
            ViewMode.RGB_ONLY: "RGB",
            ViewMode.FUSION: "Fusion",
            ViewMode.SIDE_BY_SIDE: "Side-by-Side",
            ViewMode.PICTURE_IN_PICTURE: "PiP"
        }
        mode_name = mode_names.get(view_mode, "View")
        self.view_mode_btn.setText(f"👁 {mode_name}")

    def show_developer_controls(self, show: bool):
        """Legacy method compatibility."""
        pass
