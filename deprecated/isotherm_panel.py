from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSlider,
    QComboBox, QGroupBox, QCheckBox, QPushButton, QSpinBox,
    QListWidget, QListWidgetItem, QColorDialog  # Phase 2 - Feature 8: Multi-band support
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QColor
from isotherm_bands import IsothermBandManager, IsothermBand, ISOTHERM_PRESETS, load_preset  # Phase 2 - Feature 8

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
    bands_changed = pyqtSignal(object)  # Phase 2 - Feature 8: Emits IsothermBandManager

    def __init__(self, parent=None):
        super().__init__(parent)
        self.band_manager = IsothermBandManager()  # Phase 2 - Feature 8
        self.multi_band_mode = False  # Phase 2 - Feature 8: Toggle between single/multi-band
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

        # === Phase 2 - Feature 8: Multi-Band Mode ===
        multiband_group = QGroupBox("Multi-Band Mode (Advanced)")
        multiband_layout = QVBoxLayout(multiband_group)

        # Toggle multi-band mode
        self.multiband_cb = QCheckBox("Enable Multi-Band Mode")
        self.multiband_cb.setToolTip("Show multiple temperature bands simultaneously")
        self.multiband_cb.toggled.connect(self._on_multiband_toggled)
        multiband_layout.addWidget(self.multiband_cb)

        # Band list
        list_label = QLabel("Active Bands:")
        multiband_layout.addWidget(list_label)

        self.band_list = QListWidget()
        self.band_list.setMaximumHeight(150)
        self.band_list.itemSelectionChanged.connect(self._on_band_selected)
        multiband_layout.addWidget(self.band_list)

        # Band controls
        band_btn_layout = QHBoxLayout()

        self.add_band_btn = QPushButton("+ Add Band")
        self.add_band_btn.clicked.connect(self._on_add_band)
        self.add_band_btn.setEnabled(False)
        band_btn_layout.addWidget(self.add_band_btn)

        self.remove_band_btn = QPushButton("- Remove")
        self.remove_band_btn.clicked.connect(self._on_remove_band)
        self.remove_band_btn.setEnabled(False)
        band_btn_layout.addWidget(self.remove_band_btn)

        multiband_layout.addLayout(band_btn_layout)

        # Preset loader
        preset_label = QLabel("Load Preset:")
        multiband_layout.addWidget(preset_label)

        preset_btn_layout = QHBoxLayout()

        zones_btn = QPushButton("Temp Zones")
        zones_btn.setToolTip("Load temperature zones preset (6 bands)")
        zones_btn.clicked.connect(lambda: self._load_multiband_preset("temperature_zones"))
        preset_btn_layout.addWidget(zones_btn)

        comfort_btn = QPushButton("Comfort")
        comfort_btn.setToolTip("Load comfort zones preset (3 bands)")
        comfort_btn.clicked.connect(lambda: self._load_multiband_preset("comfort_zones"))
        preset_btn_layout.addWidget(comfort_btn)

        electronics_btn = QPushButton("Electronics")
        electronics_btn.setToolTip("Load electronics temperature preset (3 bands)")
        electronics_btn.clicked.connect(lambda: self._load_multiband_preset("electronics"))
        preset_btn_layout.addWidget(electronics_btn)

        multiband_layout.addLayout(preset_btn_layout)

        layout.addWidget(multiband_group)

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

    # === Phase 2 - Feature 8: Multi-Band Mode Methods ===

    def _on_multiband_toggled(self, checked: bool):
        """Handle multi-band mode toggle."""
        self.multi_band_mode = checked
        self.add_band_btn.setEnabled(checked)

        # Enable/disable single-band controls
        self.mode_combo.setEnabled(not checked)
        self.low_spinbox.setEnabled(not checked)
        self.high_spinbox.setEnabled(not checked)
        self.color_combo.setEnabled(not checked)
        self.hotspot_btn.setEnabled(not checked)
        self.coldspot_btn.setEnabled(not checked)
        self.normal_btn.setEnabled(not checked)

        if checked:
            # Emit band manager when switching to multi-band mode
            self.bands_changed.emit(self.band_manager)
        else:
            # Revert to single-band mode - emit standard signals
            self._on_enabled_changed(self.enable_check.isChecked())

    def _on_band_selected(self):
        """Handle band selection in list."""
        has_selection = len(self.band_list.selectedItems()) > 0
        self.remove_band_btn.setEnabled(has_selection and self.multi_band_mode)

    def _on_add_band(self):
        """Add a new isotherm band."""
        # Use current single-band settings as defaults
        low = float(self.low_spinbox.value())
        high = float(self.high_spinbox.value())

        # Cycle through colors
        colors = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0), (255, 0, 255), (0, 255, 255)]
        color = colors[len(self.band_manager.bands) % len(colors)]

        band_id = self.band_manager.add_band(
            label=f"Band {len(self.band_manager.bands) + 1}",
            low_temp=low,
            high_temp=high,
            color=color,
            mode='between'
        )

        self._update_band_list()
        self.bands_changed.emit(self.band_manager)

    def _on_remove_band(self):
        """Remove selected band."""
        selected_items = self.band_list.selectedItems()
        if not selected_items:
            return

        item = selected_items[0]
        band_id = item.data(Qt.ItemDataRole.UserRole)

        if self.band_manager.remove_band(band_id):
            self._update_band_list()
            self.bands_changed.emit(self.band_manager)

    def _update_band_list(self):
        """Update the band list widget."""
        self.band_list.clear()

        for band in self.band_manager.get_all_bands():
            # Format: "Band Name: 20°C - 30°C"
            display_text = f"{band.label}: {band.low_temp:.1f}°C - {band.high_temp:.1f}°C"
            item = QListWidgetItem(display_text)
            item.setData(Qt.ItemDataRole.UserRole, band.band_id)

            # Set item color based on band color
            color = QColor(*band.color)
            item.setForeground(color)

            # Indicate if disabled
            if not band.enabled:
                display_text += " (disabled)"
                item.setText(display_text)

            self.band_list.addItem(item)

    def _load_multiband_preset(self, preset_name: str):
        """Load a multi-band preset."""
        load_preset(self.band_manager, preset_name)
        self._update_band_list()

        # Enable multi-band mode if not already
        if not self.multiband_cb.isChecked():
            self.multiband_cb.setChecked(True)

        self.bands_changed.emit(self.band_manager)

    def get_band_manager(self) -> IsothermBandManager:
        """Get the band manager instance."""
        return self.band_manager

    def is_multiband_mode(self) -> bool:
        """Check if multi-band mode is active."""
        return self.multi_band_mode
