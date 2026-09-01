"""
Environmental Compensation Panel for Radiometric Accuracy.

Provides controls for:
- Target emissivity with material presets
- Atmospheric temperature
- Atmospheric transmission
- Real-time accuracy estimation
"""

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                             QSlider, QComboBox, QGroupBox, QDoubleSpinBox, QFrame)
from PyQt6.QtCore import pyqtSignal, Qt

from thermal_inspection.utils.materials import get_materials_by_category, DEFAULT_EMISSIVITY


class EnvironmentalCompensationPanel(QWidget):
    """Panel for environmental compensation controls."""

    # Signals
    emissivity_changed = pyqtSignal(float)
    atmospheric_temp_changed = pyqtSignal(float)
    atmospheric_transmission_changed = pyqtSignal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        # Header
        header = QLabel("Environmental Compensation")
        header.setStyleSheet("font-size: 14pt; font-weight: bold;")
        layout.addWidget(header)

        info = QLabel("Adjust parameters for accurate temperature measurement")
        info.setStyleSheet("color: #888888; font-size: 10pt;")
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
        self.setLayout(layout)

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
        self.emissivity_slider.setValue(int(DEFAULT_EMISSIVITY * 100))
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
        temp_layout.addWidget(QLabel("Ambient Temp (°C):"))
        self.ambient_temp_spinbox = QDoubleSpinBox()
        self.ambient_temp_spinbox.setRange(-40, 80)
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
        trans_desc.setStyleSheet("color: #888888; font-size: 9pt;")
        trans_desc.setWordWrap(True)
        layout.addWidget(trans_desc)

        group.setLayout(layout)
        return group

    def _create_accuracy_indicator(self):
        """Create accuracy estimate indicator."""
        group = QGroupBox("Estimated Accuracy")
        layout = QVBoxLayout()

        self.accuracy_label = QLabel("±0.5-1.0°C")
        self.accuracy_label.setStyleSheet("font-size: 16pt; font-weight: bold; color: #4CAF50;")
        self.accuracy_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.accuracy_label)

        self.accuracy_note = QLabel("With proper environmental compensation")
        self.accuracy_note.setStyleSheet("color: #888888; font-size: 9pt;")
        self.accuracy_note.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.accuracy_note)

        group.setLayout(layout)
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
            self.emissivity_slider.setValue(int(material.emissivity * 100))
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
        """Handle ambient temperature change."""
        self.atmospheric_temp_changed.emit(value)

    def _on_transmission_changed(self, value):
        """Handle transmission slider change."""
        transmission = value / 100.0
        self.transmission_value.setText(f"{transmission:.2f}")
        self.atmospheric_transmission_changed.emit(transmission)
        self._update_accuracy_estimate()

    def _update_accuracy_estimate(self):
        """Update accuracy estimate based on current settings."""
        emissivity = self.emissivity_slider.value() / 100.0
        transmission = self.transmission_slider.value() / 100.0

        # Simple heuristic for accuracy estimation
        if emissivity > 0.8 and transmission > 0.95:
            accuracy = "±0.5-1.0°C"
            color = "#4CAF50"  # Green - excellent
        elif emissivity > 0.5 and transmission > 0.85:
            accuracy = "±1.0-2.0°C"
            color = "#ffaa00"  # Orange - good
        else:
            accuracy = "±2.0-5.0°C"
            color = "#ff4444"  # Red - poor

        self.accuracy_label.setText(accuracy)
        self.accuracy_label.setStyleSheet(f"font-size: 16pt; font-weight: bold; color: {color};")

    # ========================================================================
    # Public Methods
    # ========================================================================

    def set_emissivity(self, emissivity: float):
        """Set emissivity value programmatically."""
        self.emissivity_slider.blockSignals(True)
        self.emissivity_slider.setValue(int(emissivity * 100))
        self.emissivity_slider.blockSignals(False)
        self.emissivity_value.setText(f"{emissivity:.2f}")
        self._update_accuracy_estimate()

    def get_emissivity(self) -> float:
        """Get current emissivity value."""
        return self.emissivity_slider.value() / 100.0

    def set_atmospheric_temperature(self, temp_c: float):
        """Set atmospheric temperature programmatically."""
        self.ambient_temp_spinbox.blockSignals(True)
        self.ambient_temp_spinbox.setValue(temp_c)
        self.ambient_temp_spinbox.blockSignals(False)

    def get_atmospheric_temperature(self) -> float:
        """Get current atmospheric temperature."""
        return self.ambient_temp_spinbox.value()

    def set_atmospheric_transmission(self, transmission: float):
        """Set atmospheric transmission programmatically."""
        self.transmission_slider.blockSignals(True)
        self.transmission_slider.setValue(int(transmission * 100))
        self.transmission_slider.blockSignals(False)
        self.transmission_value.setText(f"{transmission:.2f}")
        self._update_accuracy_estimate()

    def get_atmospheric_transmission(self) -> float:
        """Get current atmospheric transmission."""
        return self.transmission_slider.value() / 100.0
