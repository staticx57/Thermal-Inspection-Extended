"""
Firefly Camera Control Panel for GUI
Professional control panel for FLIR Firefly advanced features
"""
from PyQt6.QtWidgets import (
    QGroupBox, QVBoxLayout, QHBoxLayout, QLabel,
    QSlider, QPushButton, QRadioButton, QComboBox,
    QCheckBox, QButtonGroup, QWidget
)
from PyQt6.QtCore import pyqtSignal, Qt
import logging

logger = logging.getLogger(__name__)


class FireflyControlPanel(QGroupBox):
    """Advanced control panel for Firefly camera features"""

    # Signals
    exposure_mode_changed = pyqtSignal(str)  # 'Off', 'Once', 'Continuous'
    exposure_time_changed = pyqtSignal(float)  # microseconds
    gain_mode_changed = pyqtSignal(str)
    gain_changed = pyqtSignal(float)  # dB
    white_balance_mode_changed = pyqtSignal(str)
    white_balance_calibrate = pyqtSignal()
    white_balance_ratio_changed = pyqtSignal(str, float)  # color, ratio
    trigger_mode_changed = pyqtSignal(bool, str)  # enabled, source
    trigger_fire = pyqtSignal()
    gamma_changed = pyqtSignal(float)
    sharpness_changed = pyqtSignal(bool, float)  # enabled, value

    def __init__(self, parent=None):
        super().__init__("🎥 Firefly Camera Control", parent)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout()

        # === Camera Status Section ===
        self._create_status_section(layout)

        # === Exposure Control ===
        self._create_exposure_section(layout)

        # === Gain Control ===
        self._create_gain_section(layout)

        # === White Balance ===
        self._create_white_balance_section(layout)

        # === Trigger Configuration ===
        self._create_trigger_section(layout)

        # === Image Settings ===
        self._create_image_settings_section(layout)

        # === Preset Management ===
        preset_group = QGroupBox("Presets")
        preset_layout = QVBoxLayout()
        preset_layout.setSpacing(6)

        save_btn = QPushButton("Save Preset")
        save_btn.setToolTip("Save current settings as preset")

        load_btn = QPushButton("Load Preset")
        load_btn.setToolTip("Load preset settings")

        reset_btn = QPushButton("Reset to Defaults")
        reset_btn.setToolTip("Reset all settings to default values")

        preset_layout.addWidget(save_btn)
        preset_layout.addWidget(load_btn)
        preset_layout.addWidget(reset_btn)

        preset_group.setLayout(preset_layout)
        layout.addWidget(preset_group)

        self.setLayout(layout)

    def _create_status_section(self, parent_layout):
        """Create camera status display"""
        status_group = QGroupBox("Camera Status")
        layout = QVBoxLayout()

        self.status_label = QLabel("Not Connected")
        self.status_label.setStyleSheet("color: #888; font-weight: bold;")
        layout.addWidget(self.status_label)

        self.info_label = QLabel("")
        self.info_label.setStyleSheet("font-size: 9pt; color: #666;")
        layout.addWidget(self.info_label)

        status_group.setLayout(layout)
        parent_layout.addWidget(status_group)

    def _create_exposure_section(self, parent_layout):
        """Create exposure control widgets"""
        group = QGroupBox("📊 Exposure Control")
        layout = QVBoxLayout()

        # Mode selection
        mode_layout = QHBoxLayout()
        mode_layout.addWidget(QLabel("Mode:"))

        self.exp_mode_group = QButtonGroup()
        self.exp_auto_radio = QRadioButton("Auto")
        self.exp_manual_radio = QRadioButton("Manual")
        self.exp_auto_radio.setChecked(True)

        self.exp_mode_group.addButton(self.exp_auto_radio, 0)
        self.exp_mode_group.addButton(self.exp_manual_radio, 1)

        mode_layout.addWidget(self.exp_auto_radio)
        mode_layout.addWidget(self.exp_manual_radio)
        mode_layout.addStretch()
        layout.addLayout(mode_layout)

        # Exposure time slider
        time_layout = QHBoxLayout()
        time_layout.addWidget(QLabel("Time:"))

        self.exposure_slider = QSlider(Qt.Orientation.Horizontal)
        self.exposure_slider.setMinimum(100)  # 100 µs
        self.exposure_slider.setMaximum(30000)  # 30 ms
        self.exposure_slider.setValue(5000)  # 5 ms default
        self.exposure_slider.setEnabled(False)  # Disabled in auto mode

        self.exposure_label = QLabel("5000 µs")
        self.exposure_label.setMinimumWidth(80)

        time_layout.addWidget(self.exposure_slider)
        time_layout.addWidget(self.exposure_label)
        layout.addLayout(time_layout)

        # Connect signals
        self.exp_auto_radio.toggled.connect(self._on_exposure_mode_changed)
        self.exposure_slider.valueChanged.connect(self._on_exposure_time_changed)

        group.setLayout(layout)
        parent_layout.addWidget(group)

    def _on_exposure_mode_changed(self, checked):
        """Handle exposure mode change"""
        if checked:  # Auto mode
            self.exposure_slider.setEnabled(False)
            self.exposure_mode_changed.emit('Continuous')
        else:  # Manual mode
            self.exposure_slider.setEnabled(True)
            self.exposure_mode_changed.emit('Off')
            # Also emit current time value
            self.exposure_time_changed.emit(self.exposure_slider.value())

    def _on_exposure_time_changed(self, value):
        """Handle exposure time slider change"""
        self.exposure_label.setText(f"{value} µs")
        if self.exp_manual_radio.isChecked():
            self.exposure_time_changed.emit(float(value))

    def _create_gain_section(self, parent_layout):
        """Create gain control widgets"""
        group = QGroupBox("🔆 Gain Control")
        layout = QVBoxLayout()

        # Mode selection
        mode_layout = QHBoxLayout()
        mode_layout.addWidget(QLabel("Mode:"))

        self.gain_mode_group = QButtonGroup()
        self.gain_auto_radio = QRadioButton("Auto")
        self.gain_manual_radio = QRadioButton("Manual")
        self.gain_auto_radio.setChecked(True)

        self.gain_mode_group.addButton(self.gain_auto_radio, 0)
        self.gain_mode_group.addButton(self.gain_manual_radio, 1)

        mode_layout.addWidget(self.gain_auto_radio)
        mode_layout.addWidget(self.gain_manual_radio)
        mode_layout.addStretch()
        layout.addLayout(mode_layout)

        # Gain slider
        gain_layout = QHBoxLayout()
        gain_layout.addWidget(QLabel("Gain:"))

        self.gain_slider = QSlider(Qt.Orientation.Horizontal)
        self.gain_slider.setMinimum(0)  # 0 dB
        self.gain_slider.setMaximum(180)  # 18.0 dB (x10 for precision)
        self.gain_slider.setValue(60)  # 6.0 dB default
        self.gain_slider.setEnabled(False)

        self.gain_label = QLabel("6.0 dB")
        self.gain_label.setMinimumWidth(80)

        gain_layout.addWidget(self.gain_slider)
        gain_layout.addWidget(self.gain_label)
        layout.addLayout(gain_layout)

        # Connect signals
        self.gain_auto_radio.toggled.connect(self._on_gain_mode_changed)
        self.gain_slider.valueChanged.connect(self._on_gain_changed)

        group.setLayout(layout)
        parent_layout.addWidget(group)

    def _on_gain_mode_changed(self, checked):
        """Handle gain mode change"""
        if checked:  # Auto mode
            self.gain_slider.setEnabled(False)
            self.gain_mode_changed.emit('Continuous')
        else:  # Manual mode
            self.gain_slider.setEnabled(True)
            self.gain_mode_changed.emit('Off')
            self.gain_changed.emit(self.gain_slider.value() / 10.0)

    def _on_gain_changed(self, value):
        """Handle gain slider change"""
        gain_db = value / 10.0
        self.gain_label.setText(f"{gain_db:.1f} dB")
        if self.gain_manual_radio.isChecked():
            self.gain_changed.emit(gain_db)

    def _create_white_balance_section(self, parent_layout):
        """Create white balance control widgets"""
        group = QGroupBox("🎨 White Balance")
        layout = QVBoxLayout()

        # Mode selection
        mode_layout = QHBoxLayout()
        mode_layout.addWidget(QLabel("Mode:"))

        self.wb_mode_group = QButtonGroup()
        self.wb_auto_radio = QRadioButton("Auto")
        self.wb_manual_radio = QRadioButton("Manual")
        self.wb_auto_radio.setChecked(True)

        self.wb_mode_group.addButton(self.wb_auto_radio, 0)
        self.wb_mode_group.addButton(self.wb_manual_radio, 1)

        mode_layout.addWidget(self.wb_auto_radio)
        mode_layout.addWidget(self.wb_manual_radio)
        mode_layout.addStretch()
        layout.addLayout(mode_layout)

        # Calibrate button
        self.wb_calibrate_btn = QPushButton("🎯 Calibrate on White")
        self.wb_calibrate_btn.setToolTip("Point camera at white surface and click to calibrate")
        self.wb_calibrate_btn.clicked.connect(lambda: self.white_balance_calibrate.emit())
        layout.addWidget(self.wb_calibrate_btn)

        # Manual ratios (initially hidden)
        self.wb_manual_widget = QWidget()
        manual_layout = QVBoxLayout(self.wb_manual_widget)
        manual_layout.setContentsMargins(0, 0, 0, 0)

        # Red ratio
        red_layout = QHBoxLayout()
        red_layout.addWidget(QLabel("Red:"))
        self.red_slider = QSlider(Qt.Orientation.Horizontal)
        self.red_slider.setMinimum(50)  # 0.5 (x100 for precision)
        self.red_slider.setMaximum(300)  # 3.0
        self.red_slider.setValue(125)  # 1.25 default
        self.red_label = QLabel("1.25")
        red_layout.addWidget(self.red_slider)
        red_layout.addWidget(self.red_label)
        manual_layout.addLayout(red_layout)

        # Blue ratio
        blue_layout = QHBoxLayout()
        blue_layout.addWidget(QLabel("Blue:"))
        self.blue_slider = QSlider(Qt.Orientation.Horizontal)
        self.blue_slider.setMinimum(50)
        self.blue_slider.setMaximum(300)
        self.blue_slider.setValue(185)  # 1.85 default
        self.blue_label = QLabel("1.85")
        blue_layout.addWidget(self.blue_slider)
        blue_layout.addWidget(self.blue_label)
        manual_layout.addLayout(blue_layout)

        self.wb_manual_widget.setVisible(False)
        layout.addWidget(self.wb_manual_widget)

        # Connect signals
        self.wb_auto_radio.toggled.connect(self._on_wb_mode_changed)
        self.red_slider.valueChanged.connect(self._on_red_ratio_changed)
        self.blue_slider.valueChanged.connect(self._on_blue_ratio_changed)

        group.setLayout(layout)
        parent_layout.addWidget(group)

    def _on_wb_mode_changed(self, checked):
        """Handle white balance mode change"""
        if checked:  # Auto mode
            self.wb_manual_widget.setVisible(False)
            self.white_balance_mode_changed.emit('Continuous')
        else:  # Manual mode
            self.wb_manual_widget.setVisible(True)
            self.white_balance_mode_changed.emit('Off')
            # Emit current ratios
            self.white_balance_ratio_changed.emit('Red', self.red_slider.value() / 100.0)
            self.white_balance_ratio_changed.emit('Blue', self.blue_slider.value() / 100.0)

    def _on_red_ratio_changed(self, value):
        """Handle red ratio change"""
        ratio = value / 100.0
        self.red_label.setText(f"{ratio:.2f}")
        if self.wb_manual_radio.isChecked():
            self.white_balance_ratio_changed.emit('Red', ratio)

    def _on_blue_ratio_changed(self, value):
        """Handle blue ratio change"""
        ratio = value / 100.0
        self.blue_label.setText(f"{ratio:.2f}")
        if self.wb_manual_radio.isChecked():
            self.white_balance_ratio_changed.emit('Blue', ratio)

    def _create_trigger_section(self, parent_layout):
        """Create trigger configuration widgets"""
        group = QGroupBox("⚡ Trigger Configuration")
        layout = QVBoxLayout()

        # Trigger mode selection
        mode_layout = QHBoxLayout()
        mode_layout.addWidget(QLabel("Mode:"))

        self.trigger_mode_group = QButtonGroup()
        self.trigger_freerun_radio = QRadioButton("Free Run")
        self.trigger_software_radio = QRadioButton("Software")
        self.trigger_hardware_radio = QRadioButton("Hardware")
        self.trigger_freerun_radio.setChecked(True)

        self.trigger_mode_group.addButton(self.trigger_freerun_radio, 0)
        self.trigger_mode_group.addButton(self.trigger_software_radio, 1)
        self.trigger_mode_group.addButton(self.trigger_hardware_radio, 2)

        mode_layout.addWidget(self.trigger_freerun_radio)
        mode_layout.addWidget(self.trigger_software_radio)
        mode_layout.addWidget(self.trigger_hardware_radio)
        layout.addLayout(mode_layout)

        # Hardware source (initially hidden)
        self.trigger_hw_widget = QWidget()
        hw_layout = QHBoxLayout(self.trigger_hw_widget)
        hw_layout.setContentsMargins(0, 0, 0, 0)
        hw_layout.addWidget(QLabel("Source:"))

        self.trigger_source_combo = QComboBox()
        self.trigger_source_combo.addItems(['Line0', 'Line1', 'Line2', 'Line3'])
        hw_layout.addWidget(self.trigger_source_combo)
        hw_layout.addStretch()

        self.trigger_hw_widget.setVisible(False)
        layout.addWidget(self.trigger_hw_widget)

        # Software trigger button
        self.trigger_fire_btn = QPushButton("🎯 Fire Software Trigger")
        self.trigger_fire_btn.setEnabled(False)
        self.trigger_fire_btn.clicked.connect(lambda: self.trigger_fire.emit())
        layout.addWidget(self.trigger_fire_btn)

        # Connect signals
        self.trigger_freerun_radio.toggled.connect(self._on_trigger_mode_changed)
        self.trigger_software_radio.toggled.connect(self._on_trigger_mode_changed)
        self.trigger_hardware_radio.toggled.connect(self._on_trigger_mode_changed)
        self.trigger_source_combo.currentTextChanged.connect(self._on_trigger_source_changed)

        group.setLayout(layout)
        parent_layout.addWidget(group)

    def _on_trigger_mode_changed(self):
        """Handle trigger mode change"""
        if self.trigger_freerun_radio.isChecked():
            self.trigger_hw_widget.setVisible(False)
            self.trigger_fire_btn.setEnabled(False)
            self.trigger_mode_changed.emit(False, 'Software')
        elif self.trigger_software_radio.isChecked():
            self.trigger_hw_widget.setVisible(False)
            self.trigger_fire_btn.setEnabled(True)
            self.trigger_mode_changed.emit(True, 'Software')
        else:  # Hardware
            self.trigger_hw_widget.setVisible(True)
            self.trigger_fire_btn.setEnabled(False)
            source = self.trigger_source_combo.currentText()
            self.trigger_mode_changed.emit(True, source)

    def _on_trigger_source_changed(self, source):
        """Handle hardware trigger source change"""
        if self.trigger_hardware_radio.isChecked():
            self.trigger_mode_changed.emit(True, source)

    def _create_image_settings_section(self, parent_layout):
        """Create image settings widgets"""
        group = QGroupBox("🖼 Image Settings")
        layout = QVBoxLayout()

        # Gamma
        gamma_layout = QHBoxLayout()
        gamma_layout.addWidget(QLabel("Gamma:"))

        self.gamma_slider = QSlider(Qt.Orientation.Horizontal)
        self.gamma_slider.setMinimum(50)  # 0.5 (x100 for precision)
        self.gamma_slider.setMaximum(400)  # 4.0
        self.gamma_slider.setValue(100)  # 1.0 default

        self.gamma_label = QLabel("1.0")
        self.gamma_label.setMinimumWidth(60)

        gamma_layout.addWidget(self.gamma_slider)
        gamma_layout.addWidget(self.gamma_label)
        layout.addLayout(gamma_layout)

        # Sharpness
        sharpness_layout = QHBoxLayout()
        self.sharpness_checkbox = QCheckBox("Sharpness:")
        sharpness_layout.addWidget(self.sharpness_checkbox)

        self.sharpness_slider = QSlider(Qt.Orientation.Horizontal)
        self.sharpness_slider.setMinimum(0)
        self.sharpness_slider.setMaximum(400)  # 4.0 (x100)
        self.sharpness_slider.setValue(100)  # 1.0 default
        self.sharpness_slider.setEnabled(False)

        self.sharpness_label = QLabel("1.0")
        self.sharpness_label.setMinimumWidth(60)

        sharpness_layout.addWidget(self.sharpness_slider)
        sharpness_layout.addWidget(self.sharpness_label)
        layout.addLayout(sharpness_layout)

        # Connect signals
        self.gamma_slider.valueChanged.connect(self._on_gamma_changed)
        self.sharpness_checkbox.toggled.connect(self._on_sharpness_enable_changed)
        self.sharpness_slider.valueChanged.connect(self._on_sharpness_changed)

        group.setLayout(layout)
        parent_layout.addWidget(group)

    def _on_gamma_changed(self, value):
        """Handle gamma slider change"""
        gamma = value / 100.0
        self.gamma_label.setText(f"{gamma:.2f}")
        self.gamma_changed.emit(gamma)

    def _on_sharpness_enable_changed(self, enabled):
        """Handle sharpness enable checkbox"""
        self.sharpness_slider.setEnabled(enabled)
        value = self.sharpness_slider.value() / 100.0
        self.sharpness_changed.emit(enabled, value)

    def _on_sharpness_changed(self, value):
        """Handle sharpness slider change"""
        sharpness = value / 100.0
        self.sharpness_label.setText(f"{sharpness:.2f}")
        if self.sharpness_checkbox.isChecked():
            self.sharpness_changed.emit(True, sharpness)

    # ========================================================================
    # Status Update Methods
    # ========================================================================

    def set_camera_connected(self, connected: bool, info: dict = None):
        """Update UI for camera connection status"""
        if connected and info:
            self.status_label.setText(f"✅ Connected: {info.get('model', 'Firefly')}")
            self.status_label.setStyleSheet("color: #0a0; font-weight: bold;")

            info_text = f"Serial: {info.get('serial', 'Unknown')}\n"
            info_text += f"Resolution: {info.get('width', 0)}x{info.get('height', 0)} @ {info.get('fps', 0)} FPS\n"
            info_text += f"Pixel Format: {info.get('pixel_format', 'BGR8')}"
            self.info_label.setText(info_text)
        else:
            self.status_label.setText("❌ Not Connected")
            self.status_label.setStyleSheet("color: #f00; font-weight: bold;")
            self.info_label.setText("")

    def update_camera_parameters(self, params: dict):
        """Update UI to reflect current camera parameters"""
        if 'exposure_time' in params:
            self.exposure_slider.setValue(int(params['exposure_time']))

        if 'gain' in params:
            self.gain_slider.setValue(int(params['gain'] * 10))

        # Add more parameter updates as needed
