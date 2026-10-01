from thermal_inspection.gui.themes import set_role
"""
Environmental Compensation Panel for Radiometric Accuracy.

Provides controls for:
- Target emissivity with material presets
- Atmospheric (ambient) temperature, shown in the app's temperature unit
- Atmospheric transmission
- A plain-language check of whether those settings are sensible

Temperatures leave this panel in degrees Celsius whatever the display unit is. The check deliberately makes no claim
about absolute accuracy in degrees: that depends on the camera's own calibration, which this panel cannot see.
"""

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                             QSlider, QComboBox, QGroupBox, QDoubleSpinBox, QFrame)
from PyQt6.QtCore import pyqtSignal, Qt

from thermal_inspection.utils.materials import get_materials_by_category, DEFAULT_EMISSIVITY
from thermal_inspection.utils.temperature_units import from_celsius, to_celsius

AMBIENT_RANGE_C = (-40.0, 80.0)


class EnvironmentalCompensationPanel(QWidget):
    """Panel for environmental compensation controls."""

    # Signals
    emissivity_changed = pyqtSignal(float)
    atmospheric_temp_changed = pyqtSignal(float)
    atmospheric_transmission_changed = pyqtSignal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.unit = "C"                      # ambient temperature entry unit: 'C' | 'F' | 'K'
        self._ambient_c = 20.0
        self._init_ui()

    def _init_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self.not_radiometric_note = QLabel(
            "Emissivity and atmospheric compensation only apply to radiometric temperature readings. "
            "Connect a radiometric camera (or enable radiometric mode) to use them.")
        self.not_radiometric_note.setWordWrap(True)
        self.not_radiometric_note.setStyleSheet("color: #cc8800; padding: 10px 16px;")
        self.not_radiometric_note.setVisible(False)
        outer.addWidget(self.not_radiometric_note)
        self.controls = QWidget()                # disabled as a block when there is nothing to compensate
        outer.addWidget(self.controls)

        layout = QVBoxLayout()
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        # Header
        header = QLabel("Environmental Compensation")
        header.setStyleSheet("font-size: 14pt; font-weight: bold;")
        layout.addWidget(header)

        info = QLabel("Emissivity, ambient temperature and transmission are sent to the camera, which applies them to its "
                      "readings (the Boson's own Environment tab sets the same camera registers).")
        info.setWordWrap(True)
        set_role(info, "hint")
        layout.addWidget(info)

        layout.addWidget(self._create_separator())

        # Emissivity Section
        layout.addWidget(self._create_emissivity_section())

        layout.addWidget(self._create_separator())

        # Atmospheric Section
        layout.addWidget(self._create_atmospheric_section())

        layout.addWidget(self._create_separator())

        # Accuracy Indicator
        layout.addWidget(self._create_accuracy_indicator())

        layout.addStretch()
        self.controls.setLayout(layout)

    def set_radiometric(self, radiometric: bool):
        """Enable the controls only for a radiometric source, and say why when they are off."""
        self.controls.setEnabled(bool(radiometric))
        self.not_radiometric_note.setVisible(not radiometric)

    def _create_separator(self):
        """Create a horizontal separator line."""
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        return separator

    def _create_emissivity_section(self):
        """Create emissivity control section."""
        group = QGroupBox("Target Emissivity (ε)")
        layout = QVBoxLayout()
        layout.setSpacing(8)

        # Material preset dropdown
        preset_layout = QHBoxLayout()
        preset_layout.addWidget(QLabel("Material Preset:"))

        self.material_combo = QComboBox()
        self.material_combo.addItem("Custom", None)

        # Add materials by category
        categories = get_materials_by_category()
        for category in sorted(categories.keys()):
            for material in sorted(categories[category], key=lambda m: m.name):
                display = f"{material.name} ({material.emissivity:.2f})"
                self.material_combo.addItem(display, material)

        self.material_combo.currentIndexChanged.connect(self._on_material_selected)
        preset_layout.addWidget(self.material_combo)
        layout.addLayout(preset_layout)

        # Emissivity slider with value
        slider_layout = QHBoxLayout()
        self.emissivity_slider = QSlider(Qt.Orientation.Horizontal)
        self.emissivity_slider.setMinimum(1)  # 0.01
        self.emissivity_slider.setMaximum(100)  # 1.00
        self.emissivity_slider.setValue(round(DEFAULT_EMISSIVITY * 100))
        self.emissivity_slider.valueChanged.connect(self._on_emissivity_changed)
        slider_layout.addWidget(self.emissivity_slider)

        self.emissivity_value = QLabel(f"{DEFAULT_EMISSIVITY:.2f}")
        self.emissivity_value.setMinimumWidth(40)
        self.emissivity_value.setStyleSheet("font-weight: bold;")
        slider_layout.addWidget(self.emissivity_value)
        layout.addLayout(slider_layout)

        # Description
        self.material_description = QLabel("Emissivity: 1.0 = perfect blackbody, <0.1 = reflective metal")
        self.material_description.setWordWrap(True)
        self.material_description.setStyleSheet("color: #888888; font-size: 9pt;")
        layout.addWidget(self.material_description)

        group.setLayout(layout)
        return group

    def _create_atmospheric_section(self):
        """Create atmospheric parameters section."""
        group = QGroupBox("Atmospheric Parameters")
        layout = QVBoxLayout()
        layout.setSpacing(8)

        # Ambient temperature
        temp_layout = QHBoxLayout()
        self.ambient_label = QLabel("Ambient Temp:")
        temp_layout.addWidget(self.ambient_label)
        self.ambient_temp_spinbox = QDoubleSpinBox()
        self.ambient_temp_spinbox.setRange(*AMBIENT_RANGE_C)
        self.ambient_temp_spinbox.setSuffix(" °C")
        self.ambient_temp_spinbox.setValue(20.0)
        self.ambient_temp_spinbox.setSingleStep(0.5)
        self.ambient_temp_spinbox.setDecimals(1)
        self.ambient_temp_spinbox.valueChanged.connect(self._on_ambient_temp_changed)
        temp_layout.addWidget(self.ambient_temp_spinbox)
        temp_layout.addStretch()
        layout.addLayout(temp_layout)

        # Transmission slider
        trans_label_layout = QHBoxLayout()
        trans_label_layout.addWidget(QLabel("Transmission:"))
        trans_label_layout.addStretch()
        self.transmission_value = QLabel("1.00")
        self.transmission_value.setStyleSheet("font-weight: bold;")
        trans_label_layout.addWidget(self.transmission_value)
        layout.addLayout(trans_label_layout)

        self.transmission_slider = QSlider(Qt.Orientation.Horizontal)
        self.transmission_slider.setMinimum(70)  # 0.70
        self.transmission_slider.setMaximum(100)  # 1.00
        self.transmission_slider.setValue(100)
        self.transmission_slider.valueChanged.connect(self._on_transmission_changed)
        layout.addWidget(self.transmission_slider)

        trans_desc = QLabel("1.0 = clear, 0.9 = typical 1-2m, 0.8 = humid/far")
        set_role(trans_desc, "hint")
        trans_desc.setWordWrap(True)
        layout.addWidget(trans_desc)

        group.setLayout(layout)
        return group

    def _create_accuracy_indicator(self):
        """A plain-language check of the compensation settings (no invented accuracy numbers)."""
        group = QGroupBox("Settings Check")
        layout = QVBoxLayout()

        self.accuracy_label = QLabel("Settings look reasonable")
        self.accuracy_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.accuracy_label.setWordWrap(True)
        layout.addWidget(self.accuracy_label)

        self.accuracy_note = QLabel("")
        self.accuracy_note.setWordWrap(True)
        set_role(self.accuracy_note, "hint")
        layout.addWidget(self.accuracy_note)
        group.setLayout(layout)
        self._update_accuracy_estimate()
        return group

    # ========================================================================
    # Event Handlers
    # ========================================================================

    def _on_material_selected(self, index):
        """Handle material preset selection."""
        material = self.material_combo.currentData()
        if material:
            # Update slider to preset value
            self.emissivity_slider.blockSignals(True)
            self.emissivity_slider.setValue(round(material.emissivity * 100))
            self.emissivity_slider.blockSignals(False)

            # Update display
            self.emissivity_value.setText(f"{material.emissivity:.2f}")
            self.material_description.setText(f"{material.category}: {material.description}")

            # Emit signal
            self.emissivity_changed.emit(material.emissivity)
            self._update_accuracy_estimate()

    def _on_emissivity_changed(self, value):
        """Handle emissivity slider change."""
        emissivity = value / 100.0
        self.emissivity_value.setText(f"{emissivity:.2f}")

        # Set to "Custom" if manually adjusted
        if self.material_combo.currentIndex() != 0:
            self.material_combo.blockSignals(True)
            self.material_combo.setCurrentIndex(0)
            self.material_combo.blockSignals(False)
            self.material_description.setText("Custom emissivity value")

        self.emissivity_changed.emit(emissivity)
        self._update_accuracy_estimate()

    def _on_ambient_temp_changed(self, value):
        """The spin box edits the temperature in the display unit; the rest of the app always gets degrees Celsius."""
        self._ambient_c = to_celsius(value, self.unit)
        self.atmospheric_temp_changed.emit(self._ambient_c)

    def set_temperature_unit(self, unit: str):
        """The app's unit changed ('C', 'F' or 'K'): re-show the same physical ambient temperature in it."""
        unit = unit if unit in ("C", "F", "K") else "C"
        if unit == self.unit:
            return
        self.unit = unit
        self._show_ambient()

    def _show_ambient(self):
        lo, hi = (from_celsius(v, self.unit) for v in AMBIENT_RANGE_C)
        suffix = {"C": " °C", "F": " °F", "K": " K"}[self.unit]
        sb = self.ambient_temp_spinbox
        sb.blockSignals(True)
        sb.setRange(lo, hi)
        sb.setSuffix(suffix)
        sb.setValue(from_celsius(self._ambient_c, self.unit))
        sb.blockSignals(False)

    def _on_transmission_changed(self, value):
        """Handle transmission slider change."""
        transmission = value / 100.0
        self.transmission_value.setText(f"{transmission:.2f}")
        self.atmospheric_transmission_changed.emit(transmission)
        self._update_accuracy_estimate()

    ABSOLUTE_NOTE = ("Absolute accuracy is set by the camera's own calibration (see its datasheet), not by these "
                     "settings - use a known reference to check it.")

    def check_settings(self):
        """(level, headline, advice) for the current emissivity/transmission; level is 'good', 'fair' or 'poor'."""
        e = self.emissivity_slider.value() / 100.0
        t = self.transmission_slider.value() / 100.0
        problems = []
        if e < 0.5:
            problems.append("Low emissivity: shiny surfaces mostly reflect their surroundings, so readings can be far off. "
                            "Pick the right material, or put a patch of tape or matt paint on the target.")
        elif e < 0.8:
            problems.append("Moderate emissivity: readings depend noticeably on this value - make sure it matches the surface.")
        if t < 0.85:
            problems.append("Low transmission: a long or humid path absorbs signal, so distant targets read cold.")
        elif t < 0.95:
            problems.append("Transmission below 0.95: fine at close range, adjust it for longer distances.")
        if e < 0.5 or t < 0.85:
            return "poor", "Check these settings", " ".join(problems)
        if problems:
            return "fair", "Settings are usable", " ".join(problems)
        return "good", "Settings look reasonable", ""

    def _update_accuracy_estimate(self):
        """Refresh the settings check."""
        level, headline, advice = self.check_settings()
        color = {"good": "#4CAF50", "fair": "#ffaa00", "poor": "#ff4444"}[level]
        self.accuracy_label.setText(headline)
        self.accuracy_label.setStyleSheet(f"font-size: 13pt; font-weight: bold; color: {color};")
        self.accuracy_note.setText((advice + " " if advice else "") + self.ABSOLUTE_NOTE)

    # ========================================================================
    # Public Methods
    # ========================================================================

    def set_emissivity(self, emissivity: float):
        """Set emissivity value programmatically."""
        self.emissivity_slider.blockSignals(True)
        self.emissivity_slider.setValue(round(emissivity * 100))
        self.emissivity_slider.blockSignals(False)
        self.emissivity_value.setText(f"{emissivity:.2f}")
        self._sync_material_to(emissivity)
        self._update_accuracy_estimate()

    def _sync_material_to(self, emissivity: float):
        """After a programmatic emissivity change, make the preset box tell the truth: keep a preset whose value matches,
        otherwise show Custom (it used to keep naming whatever material was selected before)."""
        current = self.material_combo.currentData()
        if current is not None and round(current.emissivity * 100) == round(emissivity * 100):
            return
        self.material_combo.blockSignals(True)
        self.material_combo.setCurrentIndex(0)
        self.material_combo.blockSignals(False)
        self.material_description.setText("Custom emissivity value")

    def get_emissivity(self) -> float:
        """Get current emissivity value."""
        return self.emissivity_slider.value() / 100.0

    def set_atmospheric_temperature(self, temp_c: float):
        """Set atmospheric temperature programmatically."""
        self._ambient_c = float(temp_c)
        self._show_ambient()

    def get_atmospheric_temperature(self) -> float:
        """Current atmospheric temperature in degrees Celsius (whatever unit is displayed)."""
        return self._ambient_c

    def set_atmospheric_transmission(self, transmission: float):
        """Set atmospheric transmission programmatically."""
        self.transmission_slider.blockSignals(True)
        self.transmission_slider.setValue(round(transmission * 100))
        self.transmission_slider.blockSignals(False)
        self.transmission_value.setText(f"{transmission:.2f}")
        self._update_accuracy_estimate()

    def get_atmospheric_transmission(self) -> float:
        """Get current atmospheric transmission."""
        return self.transmission_slider.value() / 100.0
