from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSlider, 
    QComboBox, QGroupBox, QCheckBox, QPushButton, QSpinBox
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QColor

class IsothermPanel(QWidget):
    """
    Panel for isotherm temperature highlighting control.
    Allows highlighting regions above/below/between temperature thresholds.
    """
    
    # Signals
    enabled_changed = pyqtSignal(bool)
    mode_changed = pyqtSignal(str)  # "above", "below", "between", "outside"
    low_threshold_changed = pyqtSignal(float)
    high_threshold_changed = pyqtSignal(float)
    color_changed = pyqtSignal(str)  # Color name
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()
    
    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # === Header ===
        header = QLabel("🌡️ Isotherm Temperature Highlighting")
        font = QFont()
        font.setPointSize(12)
        font.setBold(True)
        header.setFont(font)
        layout.addWidget(header)
        
        # === Enable/Disable ===
        self.enable_check = QCheckBox("Enable Isotherm Highlighting")
        self.enable_check.toggled.connect(self._on_enabled_changed)
        layout.addWidget(self.enable_check)
        
        # === Mode Selection ===
        mode_group = QGroupBox("Detection Mode")
        mode_layout = QVBoxLayout(mode_group)

        mode_layout.addWidget(QLabel("Highlight pixels:"))
        self.mode_combo = QComboBox()
        self.mode_combo.addItems([
            "Above High (> High)",
            "Below Low (< Low)",
            "Between Range (Low ≤ T ≤ High)",
            "Outside Range (< Low OR > High)"
        ])
        self.mode_combo.currentTextChanged.connect(self._on_mode_changed)
        mode_layout.addWidget(self.mode_combo)
        
        layout.addWidget(mode_group)
        
        # === Thresholds ===
        threshold_group = QGroupBox("Temperature Thresholds")
        threshold_layout = QVBoxLayout(threshold_group)
        
        # Low Threshold
        low_layout = QHBoxLayout()
        low_layout.addWidget(QLabel("Low:"))
        self.low_spinbox = QSpinBox()
        self.low_spinbox.setRange(-40, 200)
        self.low_spinbox.setValue(10)
        self.low_spinbox.setSuffix("°C")
        self.low_spinbox.valueChanged.connect(lambda v: self.low_threshold_changed.emit(float(v)))
        low_layout.addWidget(self.low_spinbox)
        threshold_layout.addLayout(low_layout)
        
        # High Threshold
        high_layout = QHBoxLayout()
        high_layout.addWidget(QLabel("High:"))
        self.high_spinbox = QSpinBox()
        self.high_spinbox.setRange(-40, 200)
        self.high_spinbox.setValue(50)
        self.high_spinbox.setSuffix("°C")
        self.high_spinbox.valueChanged.connect(lambda v: self.high_threshold_changed.emit(float(v)))
        high_layout.addWidget(self.high_spinbox)
        threshold_layout.addLayout(high_layout)
        
        layout.addWidget(threshold_group)
        
        # === Color Selection ===
        color_group = QGroupBox("Highlight Color")
        color_layout = QHBoxLayout(color_group)
        
        self.color_combo = QComboBox()
        self.color_combo.addItems([
            "Red", "Yellow", "Green", "Blue", "Magenta", "Cyan", "White"
        ])
        self.color_combo.currentTextChanged.connect(self.color_changed.emit)
        color_layout.addWidget(self.color_combo)
        
        layout.addWidget(color_group)
        
        # === Presets ===
        preset_group = QGroupBox("Quick Presets")
        preset_layout = QVBoxLayout(preset_group)
        
        self.hotspot_btn = QPushButton("🔥 Hotspots (>50°C)")
        self.hotspot_btn.clicked.connect(lambda: self._apply_preset("above", 50, 100, "Red"))
        preset_layout.addWidget(self.hotspot_btn)
        
        self.coldspot_btn = QPushButton("❄️ Cold Spots (<10°C)")
        self.coldspot_btn.clicked.connect(lambda: self._apply_preset("below", 0, 10, "Blue"))
        preset_layout.addWidget(self.coldspot_btn)
        
        self.normal_btn = QPushButton("📏 Normal Range (20-30°C)")
        self.normal_btn.clicked.connect(lambda: self._apply_preset("between", 20, 30, "Green"))
        preset_layout.addWidget(self.normal_btn)
        
        layout.addWidget(preset_group)

        layout.addStretch()

        # Track current unit to enable proper conversion
        self.current_unit_index = 0  # Start with Celsius

    def set_temperature_unit(self, unit_index: int):
        """Update temperature unit and ranges.

        Args:
            unit_index: 0=Celsius, 1=Fahrenheit, 2=Kelvin, 3=Raw
        """
        unit_map = {
            0: ("°C", -40, 200),      # Celsius
            1: ("°F", -40, 400),      # Fahrenheit
            2: ("K", 233, 473),       # Kelvin (approx -40°C to 200°C)
            3: ("Y16", 0, 65535)      # Raw Y16 values
        }

        suffix, min_val, max_val = unit_map.get(unit_index, ("°C", -40, 200))

        # Get current values
        old_low = self.low_spinbox.value()
        old_high = self.high_spinbox.value()

        # Convert values from current unit to new unit
        if self.current_unit_index != unit_index:
            # Convert to Celsius first
            if self.current_unit_index == 0:  # Already Celsius
                low_c = old_low
                high_c = old_high
            elif self.current_unit_index == 1:  # From Fahrenheit
                low_c = (old_low - 32) * 5/9
                high_c = (old_high - 32) * 5/9
            elif self.current_unit_index == 2:  # From Kelvin
                low_c = old_low - 273.15
                high_c = old_high - 273.15
            else:  # From Raw - use defaults
                low_c = 10
                high_c = 50

            # Convert from Celsius to new unit
            if unit_index == 0:  # To Celsius
                new_low = low_c
                new_high = high_c
            elif unit_index == 1:  # To Fahrenheit
                new_low = low_c * 9/5 + 32
                new_high = high_c * 9/5 + 32
            elif unit_index == 2:  # To Kelvin
                new_low = low_c + 273.15
                new_high = high_c + 273.15
            else:  # To Raw - use defaults
                new_low = 29315  # 20°C in Y16
                new_high = 32315  # 50°C in Y16

            # Update spinbox suffixes and ranges
            self.low_spinbox.setRange(min_val, max_val)
            self.high_spinbox.setRange(min_val, max_val)
            self.low_spinbox.setSuffix(suffix)
            self.high_spinbox.setSuffix(suffix)

            # Set converted values
            self.low_spinbox.setValue(int(new_low))
            self.high_spinbox.setValue(int(new_high))

            # Update current unit tracker
            self.current_unit_index = unit_index
        else:
            # Just update suffix and range if already in this unit
            self.low_spinbox.setSuffix(suffix)
            self.high_spinbox.setSuffix(suffix)
            self.low_spinbox.setRange(min_val, max_val)
            self.high_spinbox.setRange(min_val, max_val)

    def _on_enabled_changed(self, checked):
        """Handle enable/disable toggle."""
        self.enabled_changed.emit(checked)
    
    def _on_mode_changed(self, text):
        """Handle mode change."""
        mode_map = {
            "Above High (> High)": "above",
            "Below Low (< Low)": "below",
            "Between Range (Low ≤ T ≤ High)": "between",
            "Outside Range (< Low OR > High)": "outside"
        }
        self.mode_changed.emit(mode_map.get(text, "above"))
    
    def _apply_preset(self, mode, low, high, color):
        """Apply a quick preset configuration."""
        self.low_spinbox.setValue(low)
        self.high_spinbox.setValue(high)
        self.color_combo.setCurrentText(color)

        mode_text_map = {
            "above": "Above High (> High)",
            "below": "Below Low (< Low)",
            "between": "Between Range (Low ≤ T ≤ High)",
            "outside": "Outside Range (< Low OR > High)"
        }
        self.mode_combo.setCurrentText(mode_text_map.get(mode, "Above High (> High)"))

        if not self.enable_check.isChecked():
            self.enable_check.setChecked(True)
