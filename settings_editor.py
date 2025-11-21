#!/usr/bin/env python3
"""
Settings Editor - Qt GUI for ThermalFusionDrivingAssist Configuration
Comprehensive settings management interface with category tabs and live preview

Cross-platform: Windows + Linux compatible
"""

import sys
import logging
from pathlib import Path
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTabWidget, QGroupBox, QLabel, QLineEdit, QSpinBox, QDoubleSpinBox,
    QComboBox, QCheckBox, QSlider, QPushButton, QFileDialog,
    QMessageBox, QScrollArea, QFormLayout, QSplitter, QTableWidget,
    QTableWidgetItem, QHeaderView
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont

# Import theme manager and multi-row tab widget
try:
    from theme_manager import get_theme_manager
    from multi_row_tabwidget import MultiRowTabWidget
except ImportError as e:
    print(f"Error importing new modules: {e}")
    print("Please ensure theme_manager.py and multi_row_tabwidget.py are in the same directory.")
    sys.exit(1)

# Import settings manager
try:
    from settings_manager import SettingsManager, get_settings
except ImportError:
    print("Error: settings_manager.py not found. Please ensure it's in the same directory.")
    sys.exit(1)

# Import camera registry
try:
    from camera_registry import get_camera_registry, CameraRole
except ImportError:
    logger = logging.getLogger(__name__)
    logger.warning("camera_registry.py not found - camera registry tab will be unavailable")
    get_camera_registry = None
    CameraRole = None

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SettingsEditorWindow(QMainWindow):
    """Main settings editor window with category tabs"""

    settings_changed = pyqtSignal()

    def __init__(self):
        super().__init__()

        self.setWindowTitle("ThermalFusionDrivingAssist - Settings Editor")
        self.setGeometry(100, 100, 1000, 700)

        # Load settings
        self.settings = get_settings()
        
        # Initialize theme manager
        self.theme_manager = get_theme_manager()
        
        # Load camera registry if available
        if get_camera_registry:
            self.camera_registry = get_camera_registry()
        else:
            self.camera_registry = None

        # Track unsaved changes
        self.has_unsaved_changes = False

        # Build UI
        self._create_ui()
        
        # Apply theme
        self._apply_current_theme()

        # Load current values
        self._load_all_values()

        logger.info("Settings Editor initialized")

    def _create_ui(self):
        """Create main user interface"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout()
        central_widget.setLayout(main_layout)

        # Title
        title = QLabel("ThermalFusionDrivingAssist Configuration Editor")
        title.setFont(QFont("Arial", 16, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title)

        # Status bar with keyboard hints
        from multi_row_tabwidget import NavigationHintWidget
        hint_text = NavigationHintWidget.get_short_hint()
        self.statusBar().showMessage(f"Ready | {hint_text}")

        # Multi-row tab widget for categories
        self.tab_widget = MultiRowTabWidget()
        main_layout.addWidget(self.tab_widget)

        # Create tabs for each category
        self._create_camera_tab()
        self._create_detection_tab()
        self._create_gui_tab()
        self._create_theme_auto_tab()
        self._create_display_tab()
        self._create_fusion_tab()
        self._create_adas_tab()
        self._create_audio_tab()
        self._create_object_importance_tab()
        self._create_performance_tab()
        self._create_logging_tab()
        
        # Add camera registry tab if available
        if self.camera_registry:
            self._create_camera_registry_tab()

        # Bottom buttons
        button_layout = QHBoxLayout()

        self.save_btn = QPushButton("💾 Save Settings")
        self.save_btn.clicked.connect(self._save_settings)
        self.save_btn.setStyleSheet("background-color: #4CAF50; color: white; padding: 10px; font-weight: bold;")

        self.reset_btn = QPushButton("🔄 Reset to Defaults")
        self.reset_btn.clicked.connect(self._reset_to_defaults)

        self.export_btn = QPushButton("📤 Export")
        self.export_btn.clicked.connect(self._export_settings)

        self.import_btn = QPushButton("📥 Import")
        self.import_btn.clicked.connect(self._import_settings)

        self.validate_btn = QPushButton("✓ Validate")
        self.validate_btn.clicked.connect(self._validate_settings)

        button_layout.addWidget(self.validate_btn)
        button_layout.addWidget(self.reset_btn)
        button_layout.addWidget(self.import_btn)
        button_layout.addWidget(self.export_btn)
        button_layout.addStretch()
        button_layout.addWidget(self.save_btn)

        main_layout.addLayout(button_layout)

    def _create_scrollable_tab(self, title: str) -> tuple:
        """
        Create a scrollable tab with form layout

        Returns:
            (scroll_widget, form_layout) tuple
        """
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        container = QWidget()
        layout = QFormLayout()
        container.setLayout(layout)
        scroll.setWidget(container)

        self.tab_widget.addTab(scroll, title)

        return container, layout

    def _create_camera_tab(self):
        """Camera settings tab"""
        container, layout = self._create_scrollable_tab("📷 Camera")

        # Thermal camera group
        thermal_group = QGroupBox("Thermal Camera Settings")
        thermal_layout = QFormLayout()

        self.thermal_device_id = QSpinBox()
        self.thermal_device_id.setRange(-1, 10)
        self.thermal_device_id.setSpecialValueText("Auto-detect")
        self.thermal_device_id.valueChanged.connect(self._mark_unsaved)
        thermal_layout.addRow("Device ID:", self.thermal_device_id)

        self.thermal_width = QComboBox()
        self.thermal_width.addItems(["320", "640"])
        self.thermal_width.currentTextChanged.connect(self._mark_unsaved)
        thermal_layout.addRow("Width:", self.thermal_width)

        self.thermal_height = QComboBox()
        self.thermal_height.addItems(["256", "512"])
        self.thermal_height.currentTextChanged.connect(self._mark_unsaved)
        thermal_layout.addRow("Height:", self.thermal_height)

        self.thermal_fps = QSpinBox()
        self.thermal_fps.setRange(1, 60)
        self.thermal_fps.valueChanged.connect(self._mark_unsaved)
        thermal_layout.addRow("FPS:", self.thermal_fps)

        self.thermal_buffer_flush = QCheckBox("Enable buffer flushing (reduced latency)")
        self.thermal_buffer_flush.stateChanged.connect(self._mark_unsaved)
        thermal_layout.addRow("", self.thermal_buffer_flush)

        self.thermal_retry_interval = QDoubleSpinBox()
        self.thermal_retry_interval.setRange(1.0, 30.0)
        self.thermal_retry_interval.setSingleStep(0.5)
        self.thermal_retry_interval.setSuffix(" seconds")
        self.thermal_retry_interval.valueChanged.connect(self._mark_unsaved)
        thermal_layout.addRow("Retry Interval:", self.thermal_retry_interval)

        thermal_group.setLayout(thermal_layout)
        layout.addRow(thermal_group)

        # RGB camera group
        rgb_group = QGroupBox("RGB Camera Settings")
        rgb_layout = QFormLayout()

        self.rgb_enabled = QCheckBox("Enable RGB camera")
        self.rgb_enabled.stateChanged.connect(self._mark_unsaved)
        rgb_layout.addRow("", self.rgb_enabled)

        self.rgb_camera_type = QComboBox()
        self.rgb_camera_type.addItems(["auto", "usb", "csi", "firefly"])
        self.rgb_camera_type.currentTextChanged.connect(self._mark_unsaved)
        rgb_layout.addRow("Camera Type:", self.rgb_camera_type)

        self.rgb_width = QSpinBox()
        self.rgb_width.setRange(320, 1920)
        self.rgb_width.setSingleStep(160)
        self.rgb_width.valueChanged.connect(self._mark_unsaved)
        rgb_layout.addRow("Width:", self.rgb_width)

        self.rgb_height = QSpinBox()
        self.rgb_height.setRange(240, 1080)
        self.rgb_height.setSingleStep(120)
        self.rgb_height.valueChanged.connect(self._mark_unsaved)
        rgb_layout.addRow("Height:", self.rgb_height)

        self.rgb_fps = QSpinBox()
        self.rgb_fps.setRange(1, 60)
        self.rgb_fps.valueChanged.connect(self._mark_unsaved)
        rgb_layout.addRow("FPS:", self.rgb_fps)

        self.rgb_auto_retry = QCheckBox("Auto-retry connection on failure")
        self.rgb_auto_retry.stateChanged.connect(self._mark_unsaved)
        rgb_layout.addRow("", self.rgb_auto_retry)

        self.rgb_retry_interval = QSpinBox()
        self.rgb_retry_interval.setRange(10, 1000)
        self.rgb_retry_interval.setSuffix(" frames")
        self.rgb_retry_interval.valueChanged.connect(self._mark_unsaved)
        rgb_layout.addRow("Retry Interval:", self.rgb_retry_interval)

        rgb_group.setLayout(rgb_layout)
        layout.addRow(rgb_group)

    def _create_detection_tab(self):
        """Detection settings tab"""
        container, layout = self._create_scrollable_tab("🎯 Detection")

        # Detection mode
        mode_group = QGroupBox("Detection Mode")
        mode_layout = QFormLayout()

        self.detection_mode = QComboBox()
        self.detection_mode.addItems(["edge", "model"])
        self.detection_mode.currentTextChanged.connect(self._mark_unsaved)
        mode_layout.addRow("Mode:", self.detection_mode)

        self.show_boxes = QCheckBox("Show detection bounding boxes")
        self.show_boxes.stateChanged.connect(self._mark_unsaved)
        mode_layout.addRow("", self.show_boxes)

        self.frame_skip = QSpinBox()
        self.frame_skip.setRange(1, 10)
        self.frame_skip.valueChanged.connect(self._mark_unsaved)
        mode_layout.addRow("Frame Skip:", self.frame_skip)

        mode_group.setLayout(mode_layout)
        layout.addRow(mode_group)

        # YOLO settings
        yolo_group = QGroupBox("YOLO Object Detection")
        yolo_layout = QFormLayout()

        self.yolo_enabled = QCheckBox("Enable YOLO detection")
        self.yolo_enabled.stateChanged.connect(self._mark_unsaved)
        yolo_layout.addRow("", self.yolo_enabled)

        self.yolo_model = QComboBox()
        self.yolo_model.addItems(["yolov8n.pt", "yolov8s.pt", "yolov8m.pt", "yolov8l.pt"])
        self.yolo_model.currentTextChanged.connect(self._mark_unsaved)
        yolo_layout.addRow("Model:", self.yolo_model)

        self.yolo_confidence = QDoubleSpinBox()
        self.yolo_confidence.setRange(0.1, 0.95)
        self.yolo_confidence.setSingleStep(0.05)
        self.yolo_confidence.setDecimals(2)
        self.yolo_confidence.valueChanged.connect(self._mark_unsaved)
        yolo_layout.addRow("Confidence Threshold:", self.yolo_confidence)

        self.yolo_device = QComboBox()
        self.yolo_device.addItems(["cuda", "cpu"])
        self.yolo_device.currentTextChanged.connect(self._mark_unsaved)
        yolo_layout.addRow("Device:", self.yolo_device)

        # Custom RGB Model
        rgb_model_layout = QHBoxLayout()
        self.yolo_rgb_model = QLineEdit()
        self.yolo_rgb_model.setPlaceholderText("e.g., models/rgb_model.pt (relative path)")
        self.yolo_rgb_model.textChanged.connect(self._mark_unsaved)
        rgb_model_layout.addWidget(self.yolo_rgb_model)

        rgb_browse_btn = QPushButton("Browse...")
        rgb_browse_btn.clicked.connect(lambda: self._browse_model_file(self.yolo_rgb_model))
        rgb_model_layout.addWidget(rgb_browse_btn)

        yolo_layout.addRow("RGB Camera Model:", rgb_model_layout)

        # Custom Thermal Model
        thermal_model_layout = QHBoxLayout()
        self.yolo_thermal_model = QLineEdit()
        self.yolo_thermal_model.setPlaceholderText("e.g., models/thermal_model.pt (relative path)")
        self.yolo_thermal_model.textChanged.connect(self._mark_unsaved)
        thermal_model_layout.addWidget(self.yolo_thermal_model)

        thermal_browse_btn = QPushButton("Browse...")
        thermal_browse_btn.clicked.connect(lambda: self._browse_model_file(self.yolo_thermal_model))
        thermal_model_layout.addWidget(thermal_browse_btn)

        yolo_layout.addRow("Thermal Camera Model:", thermal_model_layout)

        yolo_group.setLayout(yolo_layout)
        layout.addRow(yolo_group)

        # Motion detection
        motion_group = QGroupBox("Motion Detection")
        motion_layout = QFormLayout()

        self.motion_enabled = QCheckBox("Enable motion detection")
        self.motion_enabled.stateChanged.connect(self._mark_unsaved)
        motion_layout.addRow("", self.motion_enabled)

        self.motion_threshold = QSpinBox()
        self.motion_threshold.setRange(5, 100)
        self.motion_threshold.valueChanged.connect(self._mark_unsaved)
        motion_layout.addRow("Threshold:", self.motion_threshold)

        self.motion_min_area = QSpinBox()
        self.motion_min_area.setRange(100, 5000)
        self.motion_min_area.setSingleStep(100)
        self.motion_min_area.valueChanged.connect(self._mark_unsaved)
        motion_layout.addRow("Min Area (pixels):", self.motion_min_area)

        motion_group.setLayout(motion_layout)
        layout.addRow(motion_group)

    def _create_gui_tab(self):
        """GUI settings tab"""
        container, layout = self._create_scrollable_tab("🖥️ GUI")

        # Theme
        theme_group = QGroupBox("Theme Settings")
        theme_layout = QFormLayout()

        self.gui_theme = QComboBox()
        self.gui_theme.addItems(["dark", "light", "auto"])
        self.gui_theme.currentTextChanged.connect(self._mark_unsaved)
        theme_layout.addRow("Main App Theme:", self.gui_theme)
        
        # Settings Editor Theme (new)
        theme_divider = QLabel("─" * 40)
        theme_layout.addRow("", theme_divider)
        
        theme_info = QLabel("<i>Settings Editor Theme (independent from main app):</i>")
        theme_layout.addRow("", theme_info)
        
        self.settings_editor_theme = QComboBox()
        self.settings_editor_theme.addItems(self.theme_manager.get_theme_names())
        self.settings_editor_theme.setCurrentText(self.theme_manager.get_current_theme_name())
        self.settings_editor_theme.currentTextChanged.connect(self._on_theme_changed)
        theme_layout.addRow("Editor Theme:", self.settings_editor_theme)

        self.developer_mode = QCheckBox("Enable developer mode by default")
        self.developer_mode.stateChanged.connect(self._mark_unsaved)
        theme_layout.addRow("", self.developer_mode)

        self.show_info_panel = QCheckBox("Show info panel in simple mode")
        self.show_info_panel.stateChanged.connect(self._mark_unsaved)
        theme_layout.addRow("", self.show_info_panel)

        theme_group.setLayout(theme_layout)
        layout.addRow(theme_group)

        # Window settings
        window_group = QGroupBox("Window Settings")
        window_layout = QFormLayout()

        self.window_width = QSpinBox()
        self.window_width.setRange(800, 3840)
        self.window_width.setSingleStep(160)
        self.window_width.valueChanged.connect(self._mark_unsaved)
        window_layout.addRow("Width:", self.window_width)

        self.window_height = QSpinBox()
        self.window_height.setRange(600, 2160)
        self.window_height.setSingleStep(120)
        self.window_height.valueChanged.connect(self._mark_unsaved)
        window_layout.addRow("Height:", self.window_height)

        self.fullscreen = QCheckBox("Start in fullscreen mode")
        self.fullscreen.stateChanged.connect(self._mark_unsaved)
        window_layout.addRow("", self.fullscreen)

        window_group.setLayout(window_layout)
        layout.addRow(window_group)

    def _create_theme_auto_tab(self):
        """Auto theme switching settings tab"""
        container, layout = self._create_scrollable_tab("🌗 Auto Theme")

        # Enable/disable
        auto_group = QGroupBox("Auto Theme Switching")
        auto_layout = QFormLayout()

        self.theme_auto_enabled = QCheckBox("Enable automatic theme switching")
        self.theme_auto_enabled.stateChanged.connect(self._mark_unsaved)
        auto_layout.addRow("", self.theme_auto_enabled)

        auto_group.setLayout(auto_layout)
        layout.addRow(auto_group)

        # Ambient light
        ambient_group = QGroupBox("Ambient Light Detection")
        ambient_layout = QFormLayout()

        self.ambient_enabled = QCheckBox("Use RGB camera for ambient light")
        self.ambient_enabled.stateChanged.connect(self._mark_unsaved)
        ambient_layout.addRow("", self.ambient_enabled)

        self.ambient_threshold = QSpinBox()
        self.ambient_threshold.setRange(0, 255)
        self.ambient_threshold.valueChanged.connect(self._mark_unsaved)
        ambient_layout.addRow("Brightness Threshold:", self.ambient_threshold)

        ambient_group.setLayout(ambient_layout)
        layout.addRow(ambient_group)

        # Astronomical
        astro_group = QGroupBox("Astronomical (Sunrise/Sunset)")
        astro_layout = QFormLayout()

        self.astro_enabled = QCheckBox("Use sunrise/sunset calculations")
        self.astro_enabled.stateChanged.connect(self._mark_unsaved)
        astro_layout.addRow("", self.astro_enabled)

        self.latitude = QDoubleSpinBox()
        self.latitude.setRange(-90.0, 90.0)
        self.latitude.setDecimals(4)
        self.latitude.valueChanged.connect(self._mark_unsaved)
        astro_layout.addRow("Latitude:", self.latitude)

        self.longitude = QDoubleSpinBox()
        self.longitude.setRange(-180.0, 180.0)
        self.longitude.setDecimals(4)
        self.longitude.valueChanged.connect(self._mark_unsaved)
        astro_layout.addRow("Longitude:", self.longitude)

        # Sync button
        sync_btn = QPushButton("🌄 Sync Time Settings with Sunrise/Sunset")
        sync_btn.clicked.connect(self._sync_astronomical_times)
        sync_btn.setStyleSheet("background-color: #2196F3; color: white; padding: 8px; font-weight: bold;")
        astro_layout.addRow("", sync_btn)

        astro_group.setLayout(astro_layout)
        layout.addRow(astro_group)

        # Time-based
        time_group = QGroupBox("Time-Based Fallback")
        time_layout = QFormLayout()

        self.day_start_hour = QSpinBox()
        self.day_start_hour.setRange(0, 23)
        self.day_start_hour.setSuffix(":00")
        self.day_start_hour.valueChanged.connect(self._mark_unsaved)
        time_layout.addRow("Day Start Hour:", self.day_start_hour)

        self.night_start_hour = QSpinBox()
        self.night_start_hour.setRange(0, 23)
        self.night_start_hour.setSuffix(":00")
        self.night_start_hour.valueChanged.connect(self._mark_unsaved)
        time_layout.addRow("Night Start Hour:", self.night_start_hour)

        time_group.setLayout(time_layout)
        layout.addRow(time_group)

    def _create_display_tab(self):
        """Display settings tab"""
        container, layout = self._create_scrollable_tab("📺 Display")

        display_group = QGroupBox("View Settings")
        display_layout = QFormLayout()

        self.view_mode = QComboBox()
        self.view_mode.addItems(["thermal", "rgb", "fusion", "side_by_side", "picture_in_picture"])
        self.view_mode.currentTextChanged.connect(self._mark_unsaved)
        display_layout.addRow("View Mode:", self.view_mode)

        self.thermal_palette = QComboBox()
        self.thermal_palette.addItems(["white_hot", "black_hot", "ironbow", "rainbow", "arctic", "lava", "medical", "plasma"])
        self.thermal_palette.currentTextChanged.connect(self._mark_unsaved)
        display_layout.addRow("Thermal Palette:", self.thermal_palette)

        display_group.setLayout(display_layout)
        layout.addRow(display_group)

    def _create_fusion_tab(self):
        """Fusion settings tab"""
        container, layout = self._create_scrollable_tab("🔀 Fusion")

        fusion_group = QGroupBox("Fusion Mode")
        fusion_layout = QFormLayout()

        self.fusion_mode = QComboBox()
        self.fusion_mode.addItems(["alpha_blend", "edge_enhanced", "thermal_overlay", "side_by_side", "picture_in_picture", "max_intensity", "feature_weighted"])
        self.fusion_mode.currentTextChanged.connect(self._mark_unsaved)
        fusion_layout.addRow("Mode:", self.fusion_mode)

        self.fusion_alpha = QSlider(Qt.Horizontal)
        self.fusion_alpha.setRange(0, 100)
        self.fusion_alpha.setValue(50)
        self.fusion_alpha.setTickPosition(QSlider.TicksBelow)
        self.fusion_alpha.setTickInterval(10)
        self.fusion_alpha.valueChanged.connect(self._mark_unsaved)
        self.fusion_alpha_label = QLabel("0.50")
        self.fusion_alpha.valueChanged.connect(lambda v: self.fusion_alpha_label.setText(f"{v/100:.2f}"))

        alpha_layout = QHBoxLayout()
        alpha_layout.addWidget(self.fusion_alpha)
        alpha_layout.addWidget(self.fusion_alpha_label)

        fusion_layout.addRow("Alpha (0=RGB, 1=Thermal):", alpha_layout)

        self.fusion_intensity = QSlider(Qt.Horizontal)
        self.fusion_intensity.setRange(0, 100)
        self.fusion_intensity.setValue(50)
        self.fusion_intensity.setTickPosition(QSlider.TicksBelow)
        self.fusion_intensity.setTickInterval(10)
        self.fusion_intensity.valueChanged.connect(self._mark_unsaved)
        self.fusion_intensity_label = QLabel("0.50")
        self.fusion_intensity.valueChanged.connect(lambda v: self.fusion_intensity_label.setText(f"{v/100:.2f}"))

        intensity_layout = QHBoxLayout()
        intensity_layout.addWidget(self.fusion_intensity)
        intensity_layout.addWidget(self.fusion_intensity_label)

        fusion_layout.addRow("Intensity (0=Minimal, 1=Maximum):", intensity_layout)

        fusion_group.setLayout(fusion_layout)
        layout.addRow(fusion_group)

    def _create_adas_tab(self):
        """ADAS settings tab"""
        container, layout = self._create_scrollable_tab("🚗 ADAS")

        distance_group = QGroupBox("Distance Estimation")
        distance_layout = QFormLayout()

        self.distance_enabled = QCheckBox("Enable distance estimation")
        self.distance_enabled.stateChanged.connect(self._mark_unsaved)
        distance_layout.addRow("", self.distance_enabled)

        self.camera_focal_length = QDoubleSpinBox()
        self.camera_focal_length.setRange(100.0, 2000.0)
        self.camera_focal_length.setSuffix(" pixels")
        self.camera_focal_length.valueChanged.connect(self._mark_unsaved)
        distance_layout.addRow("Focal Length:", self.camera_focal_length)

        self.camera_height = QDoubleSpinBox()
        self.camera_height.setRange(0.5, 3.0)
        self.camera_height.setSingleStep(0.1)
        self.camera_height.setSuffix(" meters")
        self.camera_height.valueChanged.connect(self._mark_unsaved)
        distance_layout.addRow("Camera Height:", self.camera_height)

        distance_group.setLayout(distance_layout)
        layout.addRow(distance_group)

        # Alerts
        alert_group = QGroupBox("ADAS Alerts")
        alert_layout = QFormLayout()

        self.alerts_enabled = QCheckBox("Enable ADAS alerts")
        self.alerts_enabled.stateChanged.connect(self._mark_unsaved)
        alert_layout.addRow("", self.alerts_enabled)

        self.alert_cooldown = QDoubleSpinBox()
        self.alert_cooldown.setRange(0.1, 10.0)
        self.alert_cooldown.setSingleStep(0.1)
        self.alert_cooldown.setSuffix(" seconds")
        self.alert_cooldown.valueChanged.connect(self._mark_unsaved)
        alert_layout.addRow("Alert Cooldown:", self.alert_cooldown)

        alert_group.setLayout(alert_layout)
        layout.addRow(alert_group)

    def _create_audio_tab(self):
        """Audio settings tab"""
        container, layout = self._create_scrollable_tab("🔊 Audio")

        audio_group = QGroupBox("Audio Alerts")
        audio_layout = QFormLayout()

        self.audio_enabled = QCheckBox("Enable audio alerts")
        self.audio_enabled.stateChanged.connect(self._mark_unsaved)
        audio_layout.addRow("", self.audio_enabled)

        self.audio_volume = QSlider(Qt.Horizontal)
        self.audio_volume.setRange(0, 100)
        self.audio_volume.setValue(70)
        self.audio_volume.setTickPosition(QSlider.TicksBelow)
        self.audio_volume.setTickInterval(10)
        self.audio_volume.valueChanged.connect(self._mark_unsaved)
        self.audio_volume_label = QLabel("0.70")
        self.audio_volume.valueChanged.connect(lambda v: self.audio_volume_label.setText(f"{v/100:.2f}"))

        volume_layout = QHBoxLayout()
        volume_layout.addWidget(self.audio_volume)
        volume_layout.addWidget(self.audio_volume_label)

        audio_layout.addRow("Volume:", volume_layout)

        self.audio_frequency = QSpinBox()
        self.audio_frequency.setRange(500, 3000)
        self.audio_frequency.setSingleStep(100)
        self.audio_frequency.setSuffix(" Hz")
        self.audio_frequency.valueChanged.connect(self._mark_unsaved)
        audio_layout.addRow("Frequency:", self.audio_frequency)

        self.audio_stereo = QCheckBox("Enable stereo panning")
        self.audio_stereo.stateChanged.connect(self._mark_unsaved)
        audio_layout.addRow("", self.audio_stereo)

        audio_group.setLayout(audio_layout)
        layout.addRow(audio_group)

    def _create_object_importance_tab(self):
        """Object importance/priority settings tab"""
        container, layout = self._create_scrollable_tab("⚠️ Object Priority")

        importance_group = QGroupBox("Detection Priority Levels")
        importance_layout = QFormLayout()

        # Priority options
        priority_options = ["critical", "high", "medium", "low", "info", "ignore"]

        # Vulnerable road users
        vru_group = QGroupBox("Vulnerable Road Users")
        vru_layout = QFormLayout()

        self.importance_person = QComboBox()
        self.importance_person.addItems(priority_options)
        self.importance_person.currentTextChanged.connect(self._mark_unsaved)
        vru_layout.addRow("Person:", self.importance_person)

        self.importance_bicycle = QComboBox()
        self.importance_bicycle.addItems(priority_options)
        self.importance_bicycle.currentTextChanged.connect(self._mark_unsaved)
        vru_layout.addRow("Bicycle:", self.importance_bicycle)

        self.importance_motorcycle = QComboBox()
        self.importance_motorcycle.addItems(priority_options)
        self.importance_motorcycle.currentTextChanged.connect(self._mark_unsaved)
        vru_layout.addRow("Motorcycle:", self.importance_motorcycle)

        self.importance_dog = QComboBox()
        self.importance_dog.addItems(priority_options)
        self.importance_dog.currentTextChanged.connect(self._mark_unsaved)
        vru_layout.addRow("Dog:", self.importance_dog)

        self.importance_cat = QComboBox()
        self.importance_cat.addItems(priority_options)
        self.importance_cat.currentTextChanged.connect(self._mark_unsaved)
        vru_layout.addRow("Cat:", self.importance_cat)

        self.importance_horse = QComboBox()
        self.importance_horse.addItems(priority_options)
        self.importance_horse.currentTextChanged.connect(self._mark_unsaved)
        vru_layout.addRow("Horse:", self.importance_horse)

        self.importance_cow = QComboBox()
        self.importance_cow.addItems(priority_options)
        self.importance_cow.currentTextChanged.connect(self._mark_unsaved)
        vru_layout.addRow("Cow:", self.importance_cow)

        self.importance_sheep = QComboBox()
        self.importance_sheep.addItems(priority_options)
        self.importance_sheep.currentTextChanged.connect(self._mark_unsaved)
        vru_layout.addRow("Sheep:", self.importance_sheep)

        self.importance_elephant = QComboBox()
        self.importance_elephant.addItems(priority_options)
        self.importance_elephant.currentTextChanged.connect(self._mark_unsaved)
        vru_layout.addRow("Elephant:", self.importance_elephant)

        self.importance_bear = QComboBox()
        self.importance_bear.addItems(priority_options)
        self.importance_bear.currentTextChanged.connect(self._mark_unsaved)
        vru_layout.addRow("Bear:", self.importance_bear)

        self.importance_zebra = QComboBox()
        self.importance_zebra.addItems(priority_options)
        self.importance_zebra.currentTextChanged.connect(self._mark_unsaved)
        vru_layout.addRow("Zebra:", self.importance_zebra)

        self.importance_giraffe = QComboBox()
        self.importance_giraffe.addItems(priority_options)
        self.importance_giraffe.currentTextChanged.connect(self._mark_unsaved)
        vru_layout.addRow("Giraffe:", self.importance_giraffe)

        vru_group.setLayout(vru_layout)
        layout.addRow(vru_group)

        # Vehicles
        vehicle_group = QGroupBox("Vehicles")
        vehicle_layout = QFormLayout()

        self.importance_car = QComboBox()
        self.importance_car.addItems(priority_options)
        self.importance_car.currentTextChanged.connect(self._mark_unsaved)
        vehicle_layout.addRow("Car:", self.importance_car)

        self.importance_truck = QComboBox()
        self.importance_truck.addItems(priority_options)
        self.importance_truck.currentTextChanged.connect(self._mark_unsaved)
        vehicle_layout.addRow("Truck:", self.importance_truck)

        self.importance_bus = QComboBox()
        self.importance_bus.addItems(priority_options)
        self.importance_bus.currentTextChanged.connect(self._mark_unsaved)
        vehicle_layout.addRow("Bus:", self.importance_bus)

        vehicle_group.setLayout(vehicle_layout)
        layout.addRow(vehicle_group)

        # Infrastructure and other
        other_group = QGroupBox("Infrastructure & Other")
        other_layout = QFormLayout()

        self.importance_traffic_light = QComboBox()
        self.importance_traffic_light.addItems(priority_options)
        self.importance_traffic_light.currentTextChanged.connect(self._mark_unsaved)
        other_layout.addRow("Traffic Light:", self.importance_traffic_light)

        self.importance_stop_sign = QComboBox()
        self.importance_stop_sign.addItems(priority_options)
        self.importance_stop_sign.currentTextChanged.connect(self._mark_unsaved)
        other_layout.addRow("Stop Sign:", self.importance_stop_sign)

        self.importance_bird = QComboBox()
        self.importance_bird.addItems(priority_options)
        self.importance_bird.currentTextChanged.connect(self._mark_unsaved)
        other_layout.addRow("Bird:", self.importance_bird)

        self.importance_motion = QComboBox()
        self.importance_motion.addItems(priority_options)
        self.importance_motion.currentTextChanged.connect(self._mark_unsaved)
        other_layout.addRow("Motion (Unidentified):", self.importance_motion)

        other_group.setLayout(other_layout)
        layout.addRow(other_group)

    def _create_performance_tab(self):
        """Performance settings tab"""
        container, layout = self._create_scrollable_tab("⚡ Performance")

        fps_group = QGroupBox("Target FPS")
        fps_layout = QFormLayout()

        self.target_fps_jetson = QSpinBox()
        self.target_fps_jetson.setRange(5, 60)
        self.target_fps_jetson.valueChanged.connect(self._mark_unsaved)
        fps_layout.addRow("Jetson:", self.target_fps_jetson)

        self.target_fps_x86 = QSpinBox()
        self.target_fps_x86.setRange(5, 60)
        self.target_fps_x86.valueChanged.connect(self._mark_unsaved)
        fps_layout.addRow("x86:", self.target_fps_x86)

        fps_group.setLayout(fps_layout)
        layout.addRow(fps_group)

    def _create_logging_tab(self):
        """Logging settings tab"""
        container, layout = self._create_scrollable_tab("📝 Logging")

        log_group = QGroupBox("Logging Settings")
        log_layout = QFormLayout()

        self.log_level = QComboBox()
        self.log_level.addItems(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
        self.log_level.currentTextChanged.connect(self._mark_unsaved)
        log_layout.addRow("Log Level:", self.log_level)

        self.log_file = QLineEdit()
        self.log_file.textChanged.connect(self._mark_unsaved)
        log_layout.addRow("Log File:", self.log_file)

        self.log_max_size = QSpinBox()
        self.log_max_size.setRange(1, 100)
        self.log_max_size.setSuffix(" MB")
        self.log_max_size.valueChanged.connect(self._mark_unsaved)
        log_layout.addRow("Max File Size:", self.log_max_size)

        self.log_backup_count = QSpinBox()
        self.log_backup_count.setRange(1, 20)
        self.log_backup_count.valueChanged.connect(self._mark_unsaved)
        log_layout.addRow("Backup Count:", self.log_backup_count)

        log_group.setLayout(log_layout)
        layout.addRow(log_group)

    def _load_all_values(self):
        """Load all current values from settings"""
        try:
            # Camera
            self.thermal_device_id.setValue(self.settings.get('camera.thermal.device_id') or -1)
            self.thermal_width.setCurrentText(str(self.settings.get('camera.thermal.width', 640)))
            self.thermal_height.setCurrentText(str(self.settings.get('camera.thermal.height', 512)))
            self.thermal_fps.setValue(self.settings.get('camera.thermal.fps', 60))
            self.thermal_buffer_flush.setChecked(self.settings.get('camera.thermal.buffer_flush_enabled', False))
            self.thermal_retry_interval.setValue(self.settings.get('camera.thermal.retry_interval', 3.0))

            self.rgb_enabled.setChecked(self.settings.get('camera.rgb.enabled', True))
            self.rgb_camera_type.setCurrentText(self.settings.get('camera.rgb.camera_type', 'auto'))
            self.rgb_width.setValue(self.settings.get('camera.rgb.width', 640))
            self.rgb_height.setValue(self.settings.get('camera.rgb.height', 480))
            self.rgb_fps.setValue(self.settings.get('camera.rgb.fps', 30))
            self.rgb_auto_retry.setChecked(self.settings.get('camera.rgb.auto_retry', True))
            self.rgb_retry_interval.setValue(self.settings.get('camera.rgb.retry_interval', 100))

            # Detection
            self.detection_mode.setCurrentText(self.settings.get('detection.mode', 'model'))
            self.show_boxes.setChecked(self.settings.get('detection.show_boxes', True))
            self.frame_skip.setValue(self.settings.get('detection.frame_skip', 1))

            self.yolo_enabled.setChecked(self.settings.get('detection.yolo.enabled', True))
            self.yolo_model.setCurrentText(self.settings.get('detection.yolo.model', 'yolov8n.pt'))
            self.yolo_confidence.setValue(self.settings.get('detection.yolo.confidence_threshold', 0.25))
            self.yolo_device.setCurrentText(self.settings.get('detection.yolo.device', 'cuda'))
            self.yolo_rgb_model.setText(self.settings.get('detection.yolo.rgb_model') or "")
            self.yolo_thermal_model.setText(self.settings.get('detection.yolo.thermal_model') or "")

            self.motion_enabled.setChecked(self.settings.get('detection.motion_detection.enabled', True))
            self.motion_threshold.setValue(self.settings.get('detection.motion_detection.threshold', 20))
            self.motion_min_area.setValue(self.settings.get('detection.motion_detection.min_area', 400))

            # GUI
            self.gui_theme.setCurrentText(self.settings.get('gui.theme', 'dark'))
            self.developer_mode.setChecked(self.settings.get('gui.developer_mode', False))
            self.show_info_panel.setChecked(self.settings.get('gui.show_info_panel', True))
            self.window_width.setValue(self.settings.get('gui.window.width', 1280))
            self.window_height.setValue(self.settings.get('gui.window.height', 960))
            self.fullscreen.setChecked(self.settings.get('gui.window.fullscreen', False))

            # Theme auto
            self.theme_auto_enabled.setChecked(self.settings.get('theme_auto.enabled', True))
            self.ambient_enabled.setChecked(self.settings.get('theme_auto.ambient.enabled', True))
            self.ambient_threshold.setValue(self.settings.get('theme_auto.ambient.threshold', 80))
            self.astro_enabled.setChecked(self.settings.get('theme_auto.astronomical.enabled', True))
            self.latitude.setValue(self.settings.get('theme_auto.astronomical.latitude', 37.7749))
            self.longitude.setValue(self.settings.get('theme_auto.astronomical.longitude', -122.4194))
            self.day_start_hour.setValue(self.settings.get('theme_auto.time_based.day_start_hour', 7))
            self.night_start_hour.setValue(self.settings.get('theme_auto.time_based.night_start_hour', 19))

            # Display
            self.view_mode.setCurrentText(self.settings.get('display.view_mode', 'thermal'))
            self.thermal_palette.setCurrentText(self.settings.get('display.thermal_palette', 'ironbow'))

            # Fusion
            self.fusion_mode.setCurrentText(self.settings.get('fusion.mode', 'alpha_blend'))
            alpha = self.settings.get('fusion.alpha', 0.5)
            self.fusion_alpha.setValue(int(alpha * 100))
            intensity = self.settings.get('fusion.intensity', 0.5)
            self.fusion_intensity.setValue(int(intensity * 100))

            # ADAS
            self.distance_enabled.setChecked(self.settings.get('adas.distance_estimation.enabled', True))
            self.camera_focal_length.setValue(self.settings.get('adas.distance_estimation.camera_focal_length', 640.0))
            self.camera_height.setValue(self.settings.get('adas.distance_estimation.camera_height', 1.2))
            self.alerts_enabled.setChecked(self.settings.get('adas.alerts.enabled', True))
            self.alert_cooldown.setValue(self.settings.get('adas.alerts.cooldown', 1.0))

            # Audio
            self.audio_enabled.setChecked(self.settings.get('audio.enabled', True))
            volume = self.settings.get('audio.volume', 0.7)
            self.audio_volume.setValue(int(volume * 100))
            self.audio_frequency.setValue(self.settings.get('audio.frequency_hz', 1800))
            self.audio_stereo.setChecked(self.settings.get('audio.stereo', True))

            # Object Importance
            self.importance_person.setCurrentText(self.settings.get('object_importance.person', 'critical'))
            self.importance_bicycle.setCurrentText(self.settings.get('object_importance.bicycle', 'critical'))
            self.importance_motorcycle.setCurrentText(self.settings.get('object_importance.motorcycle', 'critical'))
            self.importance_dog.setCurrentText(self.settings.get('object_importance.dog', 'critical'))
            self.importance_cat.setCurrentText(self.settings.get('object_importance.cat', 'critical'))
            self.importance_horse.setCurrentText(self.settings.get('object_importance.horse', 'critical'))
            self.importance_cow.setCurrentText(self.settings.get('object_importance.cow', 'critical'))
            self.importance_sheep.setCurrentText(self.settings.get('object_importance.sheep', 'critical'))
            self.importance_elephant.setCurrentText(self.settings.get('object_importance.elephant', 'critical'))
            self.importance_bear.setCurrentText(self.settings.get('object_importance.bear', 'critical'))
            self.importance_zebra.setCurrentText(self.settings.get('object_importance.zebra', 'critical'))
            self.importance_giraffe.setCurrentText(self.settings.get('object_importance.giraffe', 'critical'))
            self.importance_car.setCurrentText(self.settings.get('object_importance.car', 'high'))
            self.importance_truck.setCurrentText(self.settings.get('object_importance.truck', 'high'))
            self.importance_bus.setCurrentText(self.settings.get('object_importance.bus', 'high'))
            self.importance_traffic_light.setCurrentText(self.settings.get('object_importance.traffic light', 'medium'))
            self.importance_stop_sign.setCurrentText(self.settings.get('object_importance.stop sign', 'medium'))
            self.importance_bird.setCurrentText(self.settings.get('object_importance.bird', 'low'))
            self.importance_motion.setCurrentText(self.settings.get('object_importance.motion', 'high'))

            # Performance
            self.target_fps_jetson.setValue(self.settings.get('performance.target_fps.jetson', 20))
            self.target_fps_x86.setValue(self.settings.get('performance.target_fps.x86', 30))

            # Logging
            self.log_level.setCurrentText(self.settings.get('logging.level', 'INFO'))
            self.log_file.setText(self.settings.get('logging.file', 'thermal_fusion_debug.log'))
            self.log_max_size.setValue(self.settings.get('logging.max_file_size_mb', 10))
            self.log_backup_count.setValue(self.settings.get('logging.backup_count', 5))

            self.has_unsaved_changes = False
            self._update_save_button()

            logger.info("Settings values loaded")

        except Exception as e:
            logger.error(f"Error loading values: {e}")
            QMessageBox.warning(self, "Load Error", f"Error loading settings: {e}")

    def _save_all_values(self):
        """Save all values to settings"""
        try:
            # Camera
            device_id = self.thermal_device_id.value()
            self.settings.set('camera.thermal.device_id', None if device_id == -1 else device_id)
            self.settings.set('camera.thermal.width', int(self.thermal_width.currentText()))
            self.settings.set('camera.thermal.height', int(self.thermal_height.currentText()))
            self.settings.set('camera.thermal.fps', self.thermal_fps.value())
            self.settings.set('camera.thermal.buffer_flush_enabled', self.thermal_buffer_flush.isChecked())
            self.settings.set('camera.thermal.retry_interval', self.thermal_retry_interval.value())

            self.settings.set('camera.rgb.enabled', self.rgb_enabled.isChecked())
            self.settings.set('camera.rgb.camera_type', self.rgb_camera_type.currentText())
            self.settings.set('camera.rgb.width', self.rgb_width.value())
            self.settings.set('camera.rgb.height', self.rgb_height.value())
            self.settings.set('camera.rgb.fps', self.rgb_fps.value())
            self.settings.set('camera.rgb.auto_retry', self.rgb_auto_retry.isChecked())
            self.settings.set('camera.rgb.retry_interval', self.rgb_retry_interval.value())

            # Detection
            self.settings.set('detection.mode', self.detection_mode.currentText())
            self.settings.set('detection.show_boxes', self.show_boxes.isChecked())
            self.settings.set('detection.frame_skip', self.frame_skip.value())

            self.settings.set('detection.yolo.enabled', self.yolo_enabled.isChecked())
            self.settings.set('detection.yolo.model', self.yolo_model.currentText())
            self.settings.set('detection.yolo.confidence_threshold', self.yolo_confidence.value())
            self.settings.set('detection.yolo.device', self.yolo_device.currentText())
            # Save model paths, converting empty string to None
            rgb_model = self.yolo_rgb_model.text().strip()
            self.settings.set('detection.yolo.rgb_model', rgb_model if rgb_model else None)
            thermal_model = self.yolo_thermal_model.text().strip()
            self.settings.set('detection.yolo.thermal_model', thermal_model if thermal_model else None)

            self.settings.set('detection.motion_detection.enabled', self.motion_enabled.isChecked())
            self.settings.set('detection.motion_detection.threshold', self.motion_threshold.value())
            self.settings.set('detection.motion_detection.min_area', self.motion_min_area.value())

            # GUI
            self.settings.set('gui.theme', self.gui_theme.currentText())
            self.settings.set('gui.developer_mode', self.developer_mode.isChecked())
            self.settings.set('gui.show_info_panel', self.show_info_panel.isChecked())
            self.settings.set('gui.window.width', self.window_width.value())
            self.settings.set('gui.window.height', self.window_height.value())
            self.settings.set('gui.window.fullscreen', self.fullscreen.isChecked())

            # Theme auto
            self.settings.set('theme_auto.enabled', self.theme_auto_enabled.isChecked())
            self.settings.set('theme_auto.ambient.enabled', self.ambient_enabled.isChecked())
            self.settings.set('theme_auto.ambient.threshold', self.ambient_threshold.value())
            self.settings.set('theme_auto.astronomical.enabled', self.astro_enabled.isChecked())
            self.settings.set('theme_auto.astronomical.latitude', self.latitude.value())
            self.settings.set('theme_auto.astronomical.longitude', self.longitude.value())
            self.settings.set('theme_auto.time_based.day_start_hour', self.day_start_hour.value())
            self.settings.set('theme_auto.time_based.night_start_hour', self.night_start_hour.value())

            # Display
            self.settings.set('display.view_mode', self.view_mode.currentText())
            self.settings.set('display.thermal_palette', self.thermal_palette.currentText())

            # Fusion
            self.settings.set('fusion.mode', self.fusion_mode.currentText())
            self.settings.set('fusion.alpha', self.fusion_alpha.value() / 100.0)
            self.settings.set('fusion.intensity', self.fusion_intensity.value() / 100.0)

            # ADAS
            self.settings.set('adas.distance_estimation.enabled', self.distance_enabled.isChecked())
            self.settings.set('adas.distance_estimation.camera_focal_length', self.camera_focal_length.value())
            self.settings.set('adas.distance_estimation.camera_height', self.camera_height.value())
            self.settings.set('adas.alerts.enabled', self.alerts_enabled.isChecked())
            self.settings.set('adas.alerts.cooldown', self.alert_cooldown.value())

            # Audio
            self.settings.set('audio.enabled', self.audio_enabled.isChecked())
            self.settings.set('audio.volume', self.audio_volume.value() / 100.0)
            self.settings.set('audio.frequency_hz', self.audio_frequency.value())
            self.settings.set('audio.stereo', self.audio_stereo.isChecked())

            # Object Importance
            self.settings.set('object_importance.person', self.importance_person.currentText())
            self.settings.set('object_importance.bicycle', self.importance_bicycle.currentText())
            self.settings.set('object_importance.motorcycle', self.importance_motorcycle.currentText())
            self.settings.set('object_importance.dog', self.importance_dog.currentText())
            self.settings.set('object_importance.cat', self.importance_cat.currentText())
            self.settings.set('object_importance.horse', self.importance_horse.currentText())
            self.settings.set('object_importance.cow', self.importance_cow.currentText())
            self.settings.set('object_importance.sheep', self.importance_sheep.currentText())
            self.settings.set('object_importance.elephant', self.importance_elephant.currentText())
            self.settings.set('object_importance.bear', self.importance_bear.currentText())
            self.settings.set('object_importance.zebra', self.importance_zebra.currentText())
            self.settings.set('object_importance.giraffe', self.importance_giraffe.currentText())
            self.settings.set('object_importance.car', self.importance_car.currentText())
            self.settings.set('object_importance.truck', self.importance_truck.currentText())
            self.settings.set('object_importance.bus', self.importance_bus.currentText())
            self.settings.set('object_importance.traffic light', self.importance_traffic_light.currentText())
            self.settings.set('object_importance.stop sign', self.importance_stop_sign.currentText())
            self.settings.set('object_importance.bird', self.importance_bird.currentText())
            self.settings.set('object_importance.motion', self.importance_motion.currentText())

            # Performance
            self.settings.set('performance.target_fps.jetson', self.target_fps_jetson.value())
            self.settings.set('performance.target_fps.x86', self.target_fps_x86.value())

            # Logging
            self.settings.set('logging.level', self.log_level.currentText())
            self.settings.set('logging.file', self.log_file.text())
            self.settings.set('logging.max_file_size_mb', self.log_max_size.value())
            self.settings.set('logging.backup_count', self.log_backup_count.value())

            logger.info("All settings values saved to manager")

        except Exception as e:
            logger.error(f"Error saving values: {e}")
            raise

    def _sync_astronomical_times(self):
        """
        Sync time-based settings with calculated sunrise/sunset times
        based on current latitude/longitude
        """
        try:
            from auto_daynight import AutoDayNightDetector
            from datetime import datetime

            # Get current location settings
            lat = self.latitude.value()
            lon = self.longitude.value()

            # Create detector with current location
            detector = AutoDayNightDetector(latitude=lat, longitude=lon)

            # Calculate sunrise/sunset for today
            today = datetime.now()
            sunrise, sunset = detector._calculate_sunrise_sunset(today)

            if sunrise and sunset:
                # Update time fields with calculated values
                sunrise_hour = sunrise.hour
                sunset_hour = sunset.hour

                self.day_start_hour.setValue(sunrise_hour)
                self.night_start_hour.setValue(sunset_hour)

                # Show success message
                QMessageBox.information(
                    self,
                    "Astronomical Sync Complete",
                    f"Time settings updated based on location ({lat:.2f}, {lon:.2f}):\n\n"
                    f"Sunrise: {sunrise.strftime('%I:%M %p')} → Day starts at {sunrise_hour}:00\n"
                    f"Sunset: {sunset.strftime('%I:%M %p')} → Night starts at {sunset_hour}:00\n\n"
                    f"These times will be used as fallback when astronomical calculations are unavailable."
                )
                logger.info(f"Synced astronomical times: sunrise={sunrise_hour}:00, sunset={sunset_hour}:00")
            else:
                QMessageBox.warning(
                    self,
                    "Calculation Failed",
                    "Could not calculate sunrise/sunset times for the given location.\n"
                    "Please verify your latitude and longitude values."
                )
        except Exception as e:
            logger.error(f"Error syncing astronomical times: {e}")
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to sync astronomical times:\n{str(e)}"
            )

    def _browse_model_file(self, line_edit):
        """
        Open file dialog to browse for YOLO model file and set relative path

        Args:
            line_edit: QLineEdit widget to update with selected path
        """
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select YOLO Model File",
            "",
            "YOLO Models (*.pt);;All Files (*.*)"
        )

        if file_path:
            # Convert to relative path from current directory
            try:
                path_obj = Path(file_path)
                current_dir = Path.cwd()

                # Try to get relative path, fallback to absolute if not possible
                try:
                    relative_path = path_obj.relative_to(current_dir)
                    line_edit.setText(str(relative_path))
                    logger.info(f"Selected model: {relative_path}")
                except ValueError:
                    # File is not relative to current directory, use absolute path
                    line_edit.setText(str(path_obj))
                    logger.warning(f"Model file not in project directory, using absolute path: {path_obj}")
            except Exception as e:
                logger.error(f"Error processing model path: {e}")
                line_edit.setText(file_path)

    def _mark_unsaved(self):
        """Mark that there are unsaved changes"""
        self.has_unsaved_changes = True
        self._update_save_button()

    def _update_save_button(self):
        """Update save button appearance based on unsaved changes"""
        if self.has_unsaved_changes:
            self.save_btn.setText("💾 Save Settings *")
            self.save_btn.setStyleSheet("background-color: #FF9800; color: white; padding: 10px; font-weight: bold;")
            self.statusBar().showMessage("Unsaved changes", 3000)
        else:
            self.save_btn.setText("💾 Save Settings")
            self.save_btn.setStyleSheet("background-color: #4CAF50; color: white; padding: 10px; font-weight: bold;")

    def _save_settings(self):
        """Save settings to file"""
        try:
            # Save all values to settings manager
            self._save_all_values()

            # Write to file
            if self.settings.save():
                self.has_unsaved_changes = False
                self._update_save_button()
                self.statusBar().showMessage("Settings saved successfully!", 5000)
                QMessageBox.information(self, "Success", "Settings saved to config.json!")
                logger.info("Settings saved to file")
            else:
                QMessageBox.warning(self, "Save Error", "Failed to save settings to file.")

        except Exception as e:
            logger.error(f"Error saving settings: {e}")
            QMessageBox.critical(self, "Error", f"Error saving settings:\n{e}")

    def _reset_to_defaults(self):
        """Reset all settings to defaults"""
        reply = QMessageBox.question(
            self,
            "Confirm Reset",
            "Reset all settings to default values?\nThis cannot be undone.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            self.settings.reset_to_defaults()
            self._load_all_values()
            self.has_unsaved_changes = True
            self._update_save_button()
            self.statusBar().showMessage("Settings reset to defaults (not saved yet)", 5000)
            logger.info("Settings reset to defaults")

    def _export_settings(self):
        """Export settings to file"""
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Export Settings",
            "config_export.json",
            "JSON Files (*.json)"
        )

        if filename:
            if self.settings.export_to_file(filename):
                self.statusBar().showMessage(f"Settings exported to {filename}", 5000)
                QMessageBox.information(self, "Success", f"Settings exported to:\n{filename}")
            else:
                QMessageBox.warning(self, "Export Error", "Failed to export settings.")

    def _import_settings(self):
        """Import settings from file"""
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Import Settings",
            "",
            "JSON Files (*.json)"
        )

        if filename:
            reply = QMessageBox.question(
                self,
                "Confirm Import",
                "Import settings from file?\nCurrent settings will be overwritten.",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )

            if reply == QMessageBox.Yes:
                if self.settings.import_from_file(filename, merge=True):
                    self._load_all_values()
                    self.has_unsaved_changes = True
                    self._update_save_button()
                    self.statusBar().showMessage(f"Settings imported from {filename}", 5000)
                    QMessageBox.information(self, "Success", f"Settings imported from:\n{filename}")
                else:
                    QMessageBox.warning(self, "Import Error", "Failed to import settings.")

    def _validate_settings(self):
        """Validate current settings"""
        self._save_all_values()  # Update settings manager with current values
        is_valid, errors = self.settings.validate()

        if is_valid:
            QMessageBox.information(self, "Validation Success", "All settings are valid!")
            self.statusBar().showMessage("Validation passed", 5000)
        else:
            error_msg = "\n".join(f"• {err}" for err in errors)
            QMessageBox.warning(self, "Validation Errors", f"Settings validation failed:\n\n{error_msg}")
            self.statusBar().showMessage(f"Validation failed: {len(errors)} error(s)", 5000)
    
    def _apply_current_theme(self):
        """Apply the current theme to the settings editor"""
        stylesheet = self.theme_manager.generate_stylesheet()
        self.setStyleSheet(stylesheet)
        logger.info(f"Applied theme: {self.theme_manager.get_current_theme_name()}")
    
    def _on_theme_changed(self, theme_name: str):
        """Handle theme selection change"""
        if self.theme_manager.set_theme(theme_name):
            self._apply_current_theme()
            self.statusBar().showMessage(f"Theme changed to: {theme_name}", 3000)
    
    def _create_camera_registry_tab(self):
        """Create camera registry management tab"""
        container, layout = self._create_scrollable_tab("📷 Camera Registry")
        
        # Info section
        info_group = QGroupBox("Camera Registry Information")
        info_layout = QVBoxLayout()
        
        info_label = QLabel(
            "<b>Camera Registry</b> tracks detected cameras and their assigned roles (Thermal/RGB/Unassigned).\\n"
            "The system automatically detects and remembers cameras, even across reconnections.\\n"
            "Camera assignments are saved to camera_registry.json."
        )
        info_label.setWordWrap(True)
        info_layout.addWidget(info_label)
        
        info_group.setLayout(info_layout)
        layout.addRow(info_group)
        
        # Registered cameras table
        cameras_group = QGroupBox("Registered Cameras")
        cameras_layout = QVBoxLayout()
        
        self.camera_table = QTableWidget()
        self.camera_table.setColumnCount(6)
        self.camera_table.setHorizontalHeaderLabels([
            "Device ID", "Name", "Resolution", "Driver", "Role", "Status"
        ])
        self.camera_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.camera_table.setAlternatingRowColors(True)
        self.camera_table.setEditTriggers(QTableWidget.NoEditTriggers)
        
        cameras_layout.addWidget(self.camera_table)
        
        # Refresh button
        refresh_btn = QPushButton("🔄 Refresh Camera List")
        refresh_btn.clicked.connect(self._refresh_camera_registry)
        cameras_layout.addWidget(refresh_btn)
        
        cameras_group.setLayout(cameras_layout)
        layout.addRow(cameras_group)
        
        # Load initial camera data
        self._refresh_camera_registry()
    
    def _refresh_camera_registry(self):
        """Refresh camera registry table"""
        if not self.camera_registry:
            return
        
        cameras = self.camera_registry.get_all_cameras()
        self.camera_table.setRowCount(len(cameras))
        
        for row, cam in enumerate(cameras):
            self.camera_table.setItem(row, 0, QTableWidgetItem(str(cam.device_id)))
            self.camera_table.setItem(row, 1, QTableWidgetItem(cam.name))
            self.camera_table.setItem(row, 2, QTableWidgetItem(f"{cam.resolution[0]}x{cam.resolution[1]}"))
            self.camera_table.setItem(row, 3, QTableWidgetItem(cam.driver))
            self.camera_table.setItem(row, 4, QTableWidgetItem(cam.role.value))
            
            status = "✅ Connected" if cam.is_connected else "❌ Disconnected"
            self.camera_table.setItem(row, 5, QTableWidgetItem(status))
        
        self.statusBar().showMessage(f"Camera registry refreshed: {len(cameras)} camera(s) found", 3000)
        logger.debug(f"Refreshed camera registry with {len(cameras)} cameras")

    def closeEvent(self, event):
        """Handle window close event"""
        if self.has_unsaved_changes:
            reply = QMessageBox.question(
                self,
                "Unsaved Changes",
                "You have unsaved changes. Save before closing?",
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
                QMessageBox.Save
            )

            if reply == QMessageBox.Save:
                self._save_settings()
                event.accept()
            elif reply == QMessageBox.Discard:
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()


def main():
    """Main entry point"""
    app = QApplication(sys.argv)

    # Set application info
    app.setApplicationName("ThermalFusionDrivingAssist Settings Editor")
    app.setOrganizationName("ThermalFusion")

    # Create and show window
    window = SettingsEditorWindow()
    window.show()

    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
