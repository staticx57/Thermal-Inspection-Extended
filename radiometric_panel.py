"""
Radiometric Temperature Panel
Displays absolute temperature measurements for radiometric Boson cameras
"""
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
                             QLabel, QPushButton, QDoubleSpinBox, QCheckBox,
                             QFrame, QComboBox, QRadioButton, QButtonGroup)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFont
import logging

logger = logging.getLogger(__name__)


class RadiometricPanel(QWidget):
    """
    GUI panel for radiometric temperature measurement and control.

    Features:
    - Status display (capable/enabled)
    - Enable/disable toggle
    - Live temperature readings (spot, center, frame stats)
    - Temperature range configuration
    - Hardware spotmeter controls
    - Sensor temperature monitoring
    """

    # Signals
    spotmeter_enabled_changed = pyqtSignal(bool)
    spotmeter_mode_changed = pyqtSignal(str)
    sensor_temps_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()

    def init_ui(self):
        """Initialize the user interface."""
        layout = QVBoxLayout()
        layout.setSpacing(8)
        layout.setContentsMargins(8, 8, 8, 8)

        # Status Group
        status_group = QGroupBox("Radiometric Status")
        status_layout = QVBoxLayout()
        status_layout.setSpacing(6)

        self.capability_label = QLabel("Camera Type: Checking...")
        self.capability_label.setStyleSheet("color: #666;")
        status_layout.addWidget(self.capability_label)

        self.mode_label = QLabel("Mode: Unknown")
        self.mode_label.setStyleSheet("color: #666;")
        status_layout.addWidget(self.mode_label)

        self.enable_checkbox = QCheckBox("Enable Radiometric Conversion")
        self.enable_checkbox.setToolTip("Enable absolute temperature measurement")
        self.enable_checkbox.setEnabled(False)
        status_layout.addWidget(self.enable_checkbox)

        status_group.setLayout(status_layout)
        layout.addWidget(status_group)

        # Temperature Range Configuration
        range_group = QGroupBox("Temperature Range")
        range_layout = QVBoxLayout()
        range_layout.setSpacing(6)

        min_layout = QHBoxLayout()
        min_layout.addWidget(QLabel("Min (°C):"))
        self.min_temp_spin = QDoubleSpinBox()
        self.min_temp_spin.setRange(-273.15, 1000.0)
        self.min_temp_spin.setValue(-40.0)
        self.min_temp_spin.setDecimals(1)
        self.min_temp_spin.setSingleStep(10.0)
        min_layout.addWidget(self.min_temp_spin)
        range_layout.addLayout(min_layout)

        max_layout = QHBoxLayout()
        max_layout.addWidget(QLabel("Max (°C):"))
        self.max_temp_spin = QDoubleSpinBox()
        self.max_temp_spin.setRange(-273.15, 1000.0)
        self.max_temp_spin.setValue(550.0)
        self.max_temp_spin.setDecimals(1)
        self.max_temp_spin.setSingleStep(10.0)
        max_layout.addWidget(self.max_temp_spin)
        range_layout.addLayout(max_layout)

        self.apply_range_btn = QPushButton("Apply Range")
        self.apply_range_btn.setEnabled(False)
        range_layout.addWidget(self.apply_range_btn)

        range_group.setLayout(range_layout)
        layout.addWidget(range_group)

        # Conversion Method Configuration
        method_group = QGroupBox("Conversion Method")
        method_layout = QVBoxLayout()
        method_layout.setSpacing(6)

        self.method_button_group = QButtonGroup()
        
        self.method_linear_radio = QRadioButton("Linear (Built-in)")
        self.method_linear_radio.setChecked(True)
        self.method_button_group.addButton(self.method_linear_radio, 0)
        method_layout.addWidget(self.method_linear_radio)

        self.method_lut_radio = QRadioButton("TLinear LUT (File)")
        self.method_button_group.addButton(self.method_lut_radio, 1)
        method_layout.addWidget(self.method_lut_radio)

        self.load_lut_btn = QPushButton("Load LUT File...")
        self.load_lut_btn.setEnabled(False)
        method_layout.addWidget(self.load_lut_btn)

        self.lut_status_label = QLabel("No LUT loaded")
        self.lut_status_label.setStyleSheet("color: #666; font-size: 9pt;")
        method_layout.addWidget(self.lut_status_label)

        method_group.setLayout(method_layout)
        layout.addWidget(method_group)

        # Live Temperature Readings
        readings_group = QGroupBox("Live Temperature Readings")
        readings_layout = QVBoxLayout()
        readings_layout.setSpacing(6)

        self.center_temp_label = QLabel("Center: --")
        self.center_temp_label.setStyleSheet("font-weight: bold; font-size: 14pt;")
        self.center_temp_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        readings_layout.addWidget(self.center_temp_label)

        separator1 = QFrame()
        separator1.setFrameShape(QFrame.Shape.HLine)
        separator1.setFrameShadow(QFrame.Shadow.Sunken)
        readings_layout.addWidget(separator1)

        self.cursor_temp_label = QLabel("Cursor: --")
        self.cursor_temp_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        readings_layout.addWidget(self.cursor_temp_label)

        separator2 = QFrame()
        separator2.setFrameShape(QFrame.Shape.HLine)
        separator2.setFrameShadow(QFrame.Shadow.Sunken)
        readings_layout.addWidget(separator2)

        stats_label = QLabel("Frame Statistics:")
        stats_label.setStyleSheet("font-weight: bold;")
        readings_layout.addWidget(stats_label)

        self.min_temp_label = QLabel("Min: --")
        readings_layout.addWidget(self.min_temp_label)

        self.max_temp_label = QLabel("Max: --")
        readings_layout.addWidget(self.max_temp_label)

        self.mean_temp_label = QLabel("Mean: --")
        readings_layout.addWidget(self.mean_temp_label)

        readings_group.setLayout(readings_layout)
        layout.addWidget(readings_group)

        # Hardware Spotmeter Section
        spotmeter_group = QGroupBox("⚡ Hardware Spotmeter")
        spotmeter_layout = QVBoxLayout()
        spotmeter_layout.setSpacing(6)

        self.hw_spotmeter_checkbox = QCheckBox("Use Hardware Spotmeter")
        self.hw_spotmeter_checkbox.setToolTip(
            "Use camera's onboard spotmeter (requires SDK).\\nFaster than software calculation."
        )
        self.hw_spotmeter_checkbox.setEnabled(False)
        self.hw_spotmeter_checkbox.toggled.connect(self._on_hw_spotmeter_toggled)
        spotmeter_layout.addWidget(self.hw_spotmeter_checkbox)

        mode_layout = QHBoxLayout()
        mode_layout.addWidget(QLabel("Mode:"))
        self.spotmeter_mode_combo = QComboBox()
        self.spotmeter_mode_combo.addItems(['Center', 'Average', 'Max', 'Min'])
        self.spotmeter_mode_combo.setEnabled(False)
        self.spotmeter_mode_combo.currentTextChanged.connect(
            lambda mode: self.spotmeter_mode_changed.emit(mode.lower())
        )
        mode_layout.addWidget(self.spotmeter_mode_combo)
        spotmeter_layout.addLayout(mode_layout)

        spotmeter_group.setLayout(spotmeter_layout)
        layout.addWidget(spotmeter_group)

        # Sensor Temperatures Section
        sensor_group = QGroupBox("🌡️ Sensor Temperatures")
        sensor_layout = QVBoxLayout()
        sensor_layout.setSpacing(6)

        temp_font = QFont("Consolas", 10)
        
        fpa_layout = QHBoxLayout()
        fpa_layout.addWidget(QLabel("FPA:"))
        self.fpa_temp_label = QLabel("--.-°C")
        self.fpa_temp_label.setFont(temp_font)
        fpa_layout.addWidget(self.fpa_temp_label)
        fpa_layout.addStretch()
        sensor_layout.addLayout(fpa_layout)

        lens_layout = QHBoxLayout()
        lens_layout.addWidget(QLabel("Lens:"))
        self.lens_temp_label = QLabel("--.-°C")
        self.lens_temp_label.setFont(temp_font)
        lens_layout.addWidget(self.lens_temp_label)
        lens_layout.addStretch()
        sensor_layout.addLayout(lens_layout)

        shutter_layout = QHBoxLayout()
        shutter_layout.addWidget(QLabel("Shutter:"))
        self.shutter_temp_label = QLabel("--.-°C")
        self.shutter_temp_label.setFont(temp_font)
        shutter_layout.addWidget(self.shutter_temp_label)
        shutter_layout.addStretch()
        sensor_layout.addLayout(shutter_layout)

        board_layout = QHBoxLayout()
        board_layout.addWidget(QLabel("Board:"))
        self.board_temp_label = QLabel("--.-°C")
        self.board_temp_label.setFont(temp_font)
        board_layout.addWidget(self.board_temp_label)
        board_layout.addStretch()
        sensor_layout.addLayout(board_layout)

        self.auto_refresh_sensor_temps = QCheckBox("Auto-refresh (1s)")
        self.auto_refresh_sensor_temps.setChecked(False)
        self.auto_refresh_sensor_temps.toggled.connect(self._on_auto_refresh_toggled)
        sensor_layout.addWidget(self.auto_refresh_sensor_temps)

        sensor_group.setLayout(sensor_layout)
        layout.addWidget(sensor_group)

        self.sensor_temp_timer = QTimer()
        self.sensor_temp_timer.timeout.connect(self.sensor_temps_requested.emit)
        self.sensor_temp_timer.setInterval(1000)

        # Info Section
        info_group = QGroupBox("Information")
        info_layout = QVBoxLayout()
        info_layout.setSpacing(4)

        info_text = QLabel(
            "Radiometric cameras output 16-bit absolute temperature data. "
            "Non-radiometric cameras output 8-bit AGC-processed images and "
            "cannot provide absolute temperature measurements."
        )
        info_text.setWordWrap(True)
        info_text.setStyleSheet("color: #666; font-size: 9pt;")
        info_layout.addWidget(info_text)

        info_group.setLayout(info_layout)
        layout.addWidget(info_group)

        layout.addStretch()
        self.setLayout(layout)

    def _on_hw_spotmeter_toggled(self, enabled: bool):
        """Handle hardware spotmeter toggle."""
        self.spotmeter_mode_combo.setEnabled(enabled)
        self.spotmeter_enabled_changed.emit(enabled)

    def _on_auto_refresh_toggled(self, enabled: bool):
        """Handle auto-refresh toggle."""
        if enabled:
            self.sensor_temp_timer.start()
            self.sensor_temps_requested.emit()
        else:
            self.sensor_temp_timer.stop()

    # Public Methods
    def set_radiometric_status(self, capable: bool, enabled: bool, mode: str = "Unknown"):
        """Update radiometric status display."""
        if capable:
            self.capability_label.setText("Camera Type: Radiometric (16-bit)")
            self.capability_label.setStyleSheet("color: #0a0; font-weight: bold;")
        else:
            self.capability_label.setText("Camera Type: Non-Radiometric (8-bit)")
            self.capability_label.setStyleSheet("color: #fa0;")

        self.mode_label.setText(f"Mode: {mode}")
        if enabled:
            self.mode_label.setStyleSheet("color: #0a0; font-weight: bold;")
        else:
            self.mode_label.setStyleSheet("color: #666;")

        self.enable_checkbox.setEnabled(capable)
        self.apply_range_btn.setEnabled(capable and enabled)
        self.enable_checkbox.setChecked(enabled)

    def set_center_temperature(self, temp_celsius: float):
        """Update center crosshair temperature display."""
        self.center_temp_label.setText(f"Center: {temp_celsius:.1f}°C")

        if temp_celsius < 20.0:
            self.center_temp_label.setStyleSheet("color: #08f; font-weight: bold; font-size: 14pt;")
        elif temp_celsius < 50.0:
            self.center_temp_label.setStyleSheet("color: #0a0; font-weight: bold; font-size: 14pt;")
        elif temp_celsius < 100.0:
            self.center_temp_label.setStyleSheet("color: #fa0; font-weight: bold; font-size: 14pt;")
        else:
            self.center_temp_label.setStyleSheet("color: #d00; font-weight: bold; font-size: 14pt;")

    def set_cursor_temperature(self, temp_celsius: float, x: int, y: int):
        """Update cursor position temperature display."""
        self.cursor_temp_label.setText(f"Cursor ({x}, {y}): {temp_celsius:.1f}°C")

    def set_frame_statistics(self, min_temp: float, max_temp: float, mean_temp: float):
        """Update frame temperature statistics."""
        self.min_temp_label.setText(f"Min: {min_temp:.1f}°C")
        self.max_temp_label.setText(f"Max: {max_temp:.1f}°C")
        self.mean_temp_label.setText(f"Mean: {mean_temp:.1f}°C")

    def clear_temperature_readings(self):
        """Clear all temperature readings."""
        self.center_temp_label.setText("Center: --")
        self.center_temp_label.setStyleSheet("font-weight: bold; font-size: 14pt;")
        self.cursor_temp_label.setText("Cursor: --")
        self.min_temp_label.setText("Min: --")
        self.max_temp_label.setText("Max: --")
        self.mean_temp_label.setText("Mean: --")

    def get_temperature_range(self) -> tuple:
        """Get configured temperature range."""
        return (self.min_temp_spin.value(), self.max_temp_spin.value())

    def set_temperature_range(self, min_celsius: float, max_celsius: float):
        """Set temperature range spinbox values."""
        self.min_temp_spin.setValue(min_celsius)
        self.max_temp_spin.setValue(max_celsius)

    def get_conversion_method(self) -> str:
        """Get selected conversion method."""
        return "linear" if self.method_linear_radio.isChecked() else "lut"

    def update_sensor_temperatures(self, fpa: float, lens: float, shutter: float, board: float):
        """Update sensor temperature displays."""
        self.fpa_temp_label.setText(f"{fpa:.1f}°C")
        self.lens_temp_label.setText(f"{lens:.1f}°C")
        self.shutter_temp_label.setText(f"{shutter:.1f}°C")
        self.board_temp_label.setText(f"{board:.1f}°C")
