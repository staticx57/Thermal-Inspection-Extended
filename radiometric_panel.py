"""
Radiometric Temperature Panel
Displays absolute temperature measurements for radiometric Boson cameras
"""
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
                             QLabel, QPushButton, QDoubleSpinBox, QCheckBox,
                             QFrame)
from PyQt6.QtCore import Qt
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
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()

    def init_ui(self):
        """Initialize the user interface."""
        layout = QVBoxLayout()
        layout.setSpacing(8)
        layout.setContentsMargins(8, 8, 8, 8)

        # ====================================================================
        # Status Group
        # ====================================================================
        status_group = QGroupBox("Radiometric Status")
        status_layout = QVBoxLayout()
        status_layout.setSpacing(6)

        # Capability status
        self.capability_label = QLabel("Camera Type: Checking...")
        self.capability_label.setStyleSheet("color: #666;")
        status_layout.addWidget(self.capability_label)

        # Mode status
        self.mode_label = QLabel("Mode: Unknown")
        self.mode_label.setStyleSheet("color: #666;")
        status_layout.addWidget(self.mode_label)

        # Enable/disable toggle
        self.enable_checkbox = QCheckBox("Enable Radiometric Conversion")
        self.enable_checkbox.setToolTip("Enable absolute temperature measurement")
        self.enable_checkbox.setEnabled(False)  # Disabled until camera detected
        status_layout.addWidget(self.enable_checkbox)

        status_group.setLayout(status_layout)
        layout.addWidget(status_group)

        # ====================================================================
        # Temperature Range Configuration
        # ====================================================================
        range_group = QGroupBox("Temperature Range")
        range_layout = QVBoxLayout()
        range_layout.setSpacing(6)

        # Min temperature
        min_layout = QHBoxLayout()
        min_layout.addWidget(QLabel("Min (°C):"))
        self.min_temp_spin = QDoubleSpinBox()
        self.min_temp_spin.setRange(-273.15, 1000.0)
        self.min_temp_spin.setValue(-40.0)
        self.min_temp_spin.setDecimals(1)
        self.min_temp_spin.setSingleStep(10.0)
        self.min_temp_spin.setToolTip("Minimum expected temperature in scene")
        min_layout.addWidget(self.min_temp_spin)
        range_layout.addLayout(min_layout)

        # Max temperature
        max_layout = QHBoxLayout()
        max_layout.addWidget(QLabel("Max (°C):"))
        self.max_temp_spin = QDoubleSpinBox()
        self.max_temp_spin.setRange(-273.15, 1000.0)
        self.max_temp_spin.setValue(550.0)
        self.max_temp_spin.setDecimals(1)
        self.max_temp_spin.setSingleStep(10.0)
        self.max_temp_spin.setToolTip("Maximum expected temperature in scene")
        max_layout.addWidget(self.max_temp_spin)
        range_layout.addLayout(max_layout)

        # Apply button
        self.apply_range_btn = QPushButton("Apply Range")
        self.apply_range_btn.setToolTip("Apply temperature range to converter")
        self.apply_range_btn.setEnabled(False)
        range_layout.addWidget(self.apply_range_btn)

        range_group.setLayout(range_layout)
        layout.addWidget(range_group)

        # ====================================================================
        # Live Temperature Readings
        # ====================================================================
        readings_group = QGroupBox("Live Temperature Readings")
        readings_layout = QVBoxLayout()
        readings_layout.setSpacing(6)

        # Center crosshair temperature
        self.center_temp_label = QLabel("Center: --")
        self.center_temp_label.setStyleSheet("font-weight: bold; font-size: 14pt;")
        self.center_temp_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        readings_layout.addWidget(self.center_temp_label)

        # Add separator
        separator1 = QFrame()
        separator1.setFrameShape(QFrame.Shape.HLine)
        separator1.setFrameShadow(QFrame.Shadow.Sunken)
        readings_layout.addWidget(separator1)

        # Cursor position temperature
        self.cursor_temp_label = QLabel("Cursor: --")
        self.cursor_temp_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        readings_layout.addWidget(self.cursor_temp_label)

        # Add separator
        separator2 = QFrame()
        separator2.setFrameShape(QFrame.Shape.HLine)
        separator2.setFrameShadow(QFrame.Shadow.Sunken)
        readings_layout.addWidget(separator2)

        # Frame statistics
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

        # ====================================================================
        # Info Section
        # ====================================================================
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

        # Add stretch to push everything to top
        layout.addStretch()

        self.setLayout(layout)

    # ========================================================================
    # Public Methods - Called by main GUI
    # ========================================================================

    def set_radiometric_status(self, capable: bool, enabled: bool, mode: str = "Unknown"):
        """
        Update radiometric status display.

        Args:
            capable: True if camera supports radiometric mode
            enabled: True if radiometric conversion is active
            mode: Camera mode description (e.g., "16-bit Radiometric", "8-bit UVC")
        """
        # Update capability label
        if capable:
            self.capability_label.setText("Camera Type: Radiometric (16-bit)")
            self.capability_label.setStyleSheet("color: #0a0; font-weight: bold;")
        else:
            self.capability_label.setText("Camera Type: Non-Radiometric (8-bit)")
            self.capability_label.setStyleSheet("color: #fa0;")

        # Update mode label
        self.mode_label.setText(f"Mode: {mode}")
        if enabled:
            self.mode_label.setStyleSheet("color: #0a0; font-weight: bold;")
        else:
            self.mode_label.setStyleSheet("color: #666;")

        # Enable/disable controls based on capability
        self.enable_checkbox.setEnabled(capable)
        self.apply_range_btn.setEnabled(capable and enabled)

        # Set checkbox state
        self.enable_checkbox.setChecked(enabled)

    def set_center_temperature(self, temp_celsius: float):
        """
        Update center crosshair temperature display.

        Args:
            temp_celsius: Temperature in Celsius
        """
        self.center_temp_label.setText(f"Center: {temp_celsius:.1f}°C")

        # Color-code temperature (optional: adjust thresholds as needed)
        if temp_celsius < 20.0:
            self.center_temp_label.setStyleSheet("color: #08f; font-weight: bold; font-size: 14pt;")
        elif temp_celsius < 50.0:
            self.center_temp_label.setStyleSheet("color: #0a0; font-weight: bold; font-size: 14pt;")
        elif temp_celsius < 100.0:
            self.center_temp_label.setStyleSheet("color: #fa0; font-weight: bold; font-size: 14pt;")
        else:
            self.center_temp_label.setStyleSheet("color: #d00; font-weight: bold; font-size: 14pt;")

    def set_cursor_temperature(self, temp_celsius: float, x: int, y: int):
        """
        Update cursor position temperature display.

        Args:
            temp_celsius: Temperature in Celsius
            x: X coordinate
            y: Y coordinate
        """
        self.cursor_temp_label.setText(f"Cursor ({x}, {y}): {temp_celsius:.1f}°C")

    def set_frame_statistics(self, min_temp: float, max_temp: float, mean_temp: float):
        """
        Update frame temperature statistics.

        Args:
            min_temp: Minimum temperature in frame (°C)
            max_temp: Maximum temperature in frame (°C)
            mean_temp: Mean temperature in frame (°C)
        """
        self.min_temp_label.setText(f"Min: {min_temp:.1f}°C")
        self.max_temp_label.setText(f"Max: {max_temp:.1f}°C")
        self.mean_temp_label.setText(f"Mean: {mean_temp:.1f}°C")

    def clear_temperature_readings(self):
        """Clear all temperature readings (e.g., when radiometric disabled)."""
        self.center_temp_label.setText("Center: --")
        self.center_temp_label.setStyleSheet("font-weight: bold; font-size: 14pt;")
        self.cursor_temp_label.setText("Cursor: --")
        self.min_temp_label.setText("Min: --")
        self.max_temp_label.setText("Max: --")
        self.mean_temp_label.setText("Mean: --")

    def get_temperature_range(self) -> tuple:
        """
        Get configured temperature range.

        Returns:
            Tuple of (min_celsius, max_celsius)
        """
        return (self.min_temp_spin.value(), self.max_temp_spin.value())

    def set_temperature_range(self, min_celsius: float, max_celsius: float):
        """
        Set temperature range spinbox values.

        Args:
            min_celsius: Minimum temperature
            max_celsius: Maximum temperature
        """
        self.min_temp_spin.setValue(min_celsius)
        self.max_temp_spin.setValue(max_celsius)


# ============================================================================
# Standalone Test
# ============================================================================

if __name__ == "__main__":
    import sys
    from PyQt6.QtWidgets import QApplication

    app = QApplication(sys.argv)

    # Test the panel
    panel = RadiometricPanel()
    panel.setWindowTitle("Radiometric Panel Test")
    panel.resize(400, 600)

    # Simulate radiometric camera detected
    panel.set_radiometric_status(capable=True, enabled=True, mode="16-bit Radiometric")

    # Simulate temperature readings
    panel.set_center_temperature(45.3)
    panel.set_cursor_temperature(38.7, 320, 256)
    panel.set_frame_statistics(12.5, 89.2, 36.4)

    panel.show()
    sys.exit(app.exec())
