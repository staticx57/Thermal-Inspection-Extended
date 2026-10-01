"""
Gradient Overlay Panel
Phase 3 - Feature 11: Temperature gradient visualization

Visualizes temperature gradients (rate of change) on thermal images.
"""

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                              QCheckBox, QComboBox, QGroupBox, QSlider,
                              QDoubleSpinBox)
from PyQt6.QtCore import Qt, pyqtSignal
import logging

logger = logging.getLogger(__name__)


# Default min gradient in deg C/px; 8-bit AGC sources use counts/px, where the same scene is ~30x larger
DEFAULT_THRESHOLD = 0.2
AGC_COUNT_SCALE = 30.0

class GradientOverlayPanel(QWidget):
    """Panel for temperature gradient visualization controls."""

    # Signals
    gradient_enabled = pyqtSignal(bool)
    gradient_mode_changed = pyqtSignal(str)  # 'magnitude', 'horizontal', 'vertical', 'both'
    gradient_threshold_changed = pyqtSignal(float)  # Minimum gradient to display
    gradient_color_map_changed = pyqtSignal(str)  # Color map name
    gradient_sensitivity_changed = pyqtSignal(int)  # 1-100; higher = lower effective threshold

    # Gradient threshold is a *difference*, so converting between units is a pure scale (no offset).
    # Base unit (what the processor works in): deg C per pixel, or raw counts per pixel on 8-bit sources.
    _UNIT_SCALE = {"C": 1.0, "K": 1.0, "F": 1.8, "RAW": 100.0}     # displayed value = base value * scale
    _UNIT_SUFFIX = {"C": " °C/px", "K": " K/px", "F": " °F/px", "RAW": " Y16/px"}

    def __init__(self, parent=None):
        super().__init__(parent)
        self._unit = "C"
        self._radiometric = True
        self._setup_ui()

    def _scale(self) -> float:
        return 1.0 if not self._radiometric else self._UNIT_SCALE.get(self._unit, 1.0)

    def _suffix(self) -> str:
        return " counts/px" if not self._radiometric else self._UNIT_SUFFIX.get(self._unit, " °C/px")

    def threshold_base(self) -> float:
        """Threshold in the processor's units (deg C/px, or counts/px for a non-radiometric source)."""
        return self.threshold_spin.value() / self._scale()

    def _refresh_threshold_display(self, base_value: float) -> None:
        """Show base_value in the selected unit without emitting a change."""
        scale = self._scale()
        self.threshold_spin.blockSignals(True)
        self.threshold_spin.setRange(0.0, 50.0 * scale)
        self.threshold_spin.setSuffix(self._suffix())
        self.threshold_spin.setDecimals(0 if (self._radiometric and self._unit == "RAW") else 2)
        self.threshold_spin.setValue(base_value * scale)
        self.threshold_spin.blockSignals(False)

    def set_scene_stats(self, stats) -> None:
        """Show the current scene's typical/strong gradient in the panel's units (stats in processor units)."""
        if not stats:
            self.scene_label.setText("Scene gradient: --")
            return
        scale, suffix = self._scale(), self._suffix().strip()
        places = 0 if (self._radiometric and self._unit == "RAW") else 2
        self.scene_label.setText(
            f"Scene gradient: typical {stats['p50'] * scale:.{places}f}, "
            f"strong {stats['p99'] * scale:.{places}f} {suffix}")

    def set_temperature_unit(self, unit: str) -> None:
        """Follow the app's temperature unit ('C', 'F', 'K', 'RAW'): relabel and convert the threshold."""
        unit = (unit or "C").upper()
        if unit not in self._UNIT_SCALE or unit == self._unit:
            return
        base = self.threshold_base()
        self._unit = unit
        self._refresh_threshold_display(base)

    def set_radiometric(self, radiometric: bool) -> None:
        """8-bit AGC sources have no temperature: the threshold is then in raw counts per pixel."""
        radiometric = bool(radiometric)
        if radiometric == self._radiometric:
            return
        self._radiometric = radiometric
        # degrees and raw counts aren't comparable (8-bit AGC noise is ~1-2 counts): start from a sensible
        # default for the new kind of source and tell the processor
        base = DEFAULT_THRESHOLD * (1.0 if radiometric else AGC_COUNT_SCALE)
        self._refresh_threshold_display(base)
        self.gradient_threshold_changed.emit(base)

    def _setup_ui(self):
        """Build the panel UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(8)

        # Title
        title = QLabel("Temperature Gradient Overlay")
        title.setStyleSheet("font-weight: bold; font-size: 13px;")
        layout.addWidget(title)

        # Enable checkbox
        self.enable_cb = QCheckBox("Enable Gradient Visualization")
        self.enable_cb.setToolTip("Show temperature gradients (rate of change)")
        self.enable_cb.toggled.connect(self._on_enabled_toggled)
        layout.addWidget(self.enable_cb)

        # Description
        desc = QLabel("Visualizes areas of rapid temperature change. "
                     "Useful for detecting thermal boundaries and anomalies.")
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #888888; font-size: 10px;")
        layout.addWidget(desc)

        # Mode selection
        mode_group = QGroupBox("Gradient Mode")
        mode_layout = QVBoxLayout(mode_group)

        mode_layout.addWidget(QLabel("Display:"))
        self.mode_combo = QComboBox()
        self.mode_combo.addItems([
            "Magnitude (Overall Change)",
            "Horizontal (X-direction)",
            "Vertical (Y-direction)",
            "Both Directions (Arrows)"
        ])
        self.mode_combo.setToolTip("Choose which gradient component to visualize")
        self.mode_combo.currentTextChanged.connect(self._on_mode_changed)
        mode_layout.addWidget(self.mode_combo)

        layout.addWidget(mode_group)

        # Threshold settings
        threshold_group = QGroupBox("Threshold Settings")
        threshold_layout = QVBoxLayout(threshold_group)

        # Minimum gradient threshold
        threshold_label_layout = QHBoxLayout()
        threshold_label_layout.addWidget(QLabel("Min Gradient:"))

        self.threshold_spin = QDoubleSpinBox()
        self.threshold_spin.setRange(0.0, 50.0)
        self.threshold_spin.setValue(DEFAULT_THRESHOLD)
        self.threshold_spin.setSingleStep(0.05)
        self.threshold_spin.setSuffix(" °C/px")   # follows the selected unit - see set_temperature_unit
        self.threshold_spin.setToolTip(
            "Minimum gradient magnitude to display, in degrees C per pixel on a radiometric camera "
            "(raw counts per pixel on a non-radiometric one).\n"
            "Sensor noise is about 0.04 C/px, so values below ~0.1 just show noise; 0.2 picks out clear "
            "edges and 0.5+ only the strongest ones.")
        self.threshold_spin.valueChanged.connect(self._on_threshold_changed)
        threshold_label_layout.addWidget(self.threshold_spin)
        threshold_label_layout.addStretch()

        threshold_layout.addLayout(threshold_label_layout)

        # Live hint for choosing the threshold: what this scene's gradients actually look like
        self.scene_label = QLabel("Scene gradient: --")
        self.scene_label.setToolTip(
            "Typical = the median gradient (mostly sensor noise); strong = the 99th percentile (clear edges). "
            "A threshold a little above 'typical' shows edges without the noise.")
        self.scene_label.setStyleSheet("color: #888888; font-size: 10px;")
        threshold_layout.addWidget(self.scene_label)

        # Sensitivity slider
        sensitivity_layout = QHBoxLayout()
        sensitivity_layout.addWidget(QLabel("Sensitivity:"))

        self.sensitivity_slider = QSlider(Qt.Orientation.Horizontal)
        self.sensitivity_slider.setRange(1, 100)
        self.sensitivity_slider.setValue(50)
        self.sensitivity_slider.setToolTip("Adjust gradient visualization sensitivity")
        self.sensitivity_slider.valueChanged.connect(self._on_sensitivity_changed)
        sensitivity_layout.addWidget(self.sensitivity_slider)

        self.sensitivity_label = QLabel("50%")
        sensitivity_layout.addWidget(self.sensitivity_label)

        threshold_layout.addLayout(sensitivity_layout)

        layout.addWidget(threshold_group)

        # Color map selection
        colormap_group = QGroupBox("Color Map")
        colormap_layout = QHBoxLayout(colormap_group)

        self.colormap_combo = QComboBox()
        self.colormap_combo.addItems([
            "Hot (Red-Yellow)",
            "Cool (Blue-Cyan)",
            "Jet (Rainbow)",
            "Viridis (Smooth)",
            "Grayscale"
        ])
        self.colormap_combo.setToolTip("Color scheme for gradient visualization")
        self.colormap_combo.currentTextChanged.connect(self._on_colormap_changed)
        colormap_layout.addWidget(self.colormap_combo)

        layout.addWidget(colormap_group)

        # Presets
        preset_group = QGroupBox("Quick Presets")
        preset_layout = QVBoxLayout(preset_group)

        # Preset buttons
        # Base units (deg C/px; x AGC_COUNT_SCALE on a non-radiometric camera). Chosen from measured scene
        # statistics: effective threshold = threshold * (100 - sensitivity) / 50 -> ~0.12 (p90 of a typical
        # scene), 0.2, 0.5 (p99) and 0.16.
        presets = [
            ("High Sensitivity", 0.15, 60, "magnitude"),
            ("Medium (Default)", 0.2, 50, "magnitude"),
            ("Low (Major Changes)", 0.5, 50, "magnitude"),
            ("Edge Detection", 0.2, 60, "both")
        ]

        for name, threshold, sensitivity, mode in presets:
            btn_layout = QHBoxLayout()

            from PyQt6.QtWidgets import QPushButton
            btn = QPushButton(name)
            btn.clicked.connect(
                lambda checked, t=threshold, s=sensitivity, m=mode:
                self._apply_preset(t, s, m)
            )
            btn_layout.addWidget(btn)
            btn_layout.addStretch()

            preset_layout.addLayout(btn_layout)

        layout.addWidget(preset_group)

        layout.addStretch()

    def _on_enabled_toggled(self, checked: bool):
        """Handle enable/disable toggle."""
        logger.info(f"Gradient overlay enabled: {checked}")
        self.gradient_enabled.emit(checked)

    def _on_mode_changed(self, text: str):
        """Handle gradient mode change."""
        mode_map = {
            "Magnitude (Overall Change)": "magnitude",
            "Horizontal (X-direction)": "horizontal",
            "Vertical (Y-direction)": "vertical",
            "Both Directions (Arrows)": "both"
        }
        mode = mode_map.get(text, "magnitude")
        logger.debug(f"Gradient mode changed: {mode}")
        self.gradient_mode_changed.emit(mode)

    def _on_threshold_changed(self, value: float):
        """Handle threshold change."""
        base = value / self._scale()
        logger.debug(f"Gradient threshold: {value}{self._suffix().strip()} ({base:.3f} base units)")
        self.gradient_threshold_changed.emit(base)

    def _on_sensitivity_changed(self, value: int):
        """Handle sensitivity slider change."""
        self.sensitivity_label.setText(f"{value}%")
        self.gradient_sensitivity_changed.emit(value)
        # Sensitivity affects the threshold inversely
        # Higher sensitivity = lower threshold
        adjusted_threshold = self.threshold_base() * (100 - value) / 50.0
        logger.debug(f"Gradient sensitivity: {value}%, effective threshold: {adjusted_threshold:.2f}")

    def _on_colormap_changed(self, text: str):
        """Handle color map change."""
        colormap_map = {
            "Hot (Red-Yellow)": "hot",
            "Cool (Blue-Cyan)": "cool",
            "Jet (Rainbow)": "jet",
            "Viridis (Smooth)": "viridis",
            "Grayscale": "gray"
        }
        colormap = colormap_map.get(text, "hot")
        logger.debug(f"Gradient color map: {colormap}")
        self.gradient_color_map_changed.emit(colormap)

    def _apply_preset(self, threshold: float, sensitivity: int, mode: str):
        """Apply a preset configuration.

        Args:
            threshold: Gradient threshold
            sensitivity: Sensitivity percentage
            mode: Gradient mode
        """
        logger.info(f"Applying gradient preset: threshold={threshold}, sensitivity={sensitivity}, mode={mode}")

        if not self._radiometric:
            threshold *= AGC_COUNT_SCALE                                # same scene statistics, in raw counts
        self.threshold_spin.setValue(threshold * self._scale())     # presets are in deg C/px (counts/px on 8-bit)
        self.sensitivity_slider.setValue(sensitivity)

        # Set mode
        mode_text_map = {
            "magnitude": "Magnitude (Overall Change)",
            "horizontal": "Horizontal (X-direction)",
            "vertical": "Vertical (Y-direction)",
            "both": "Both Directions (Arrows)"
        }
        self.mode_combo.setCurrentText(mode_text_map.get(mode, "Magnitude (Overall Change)"))

        # Enable if not already
        if not self.enable_cb.isChecked():
            self.enable_cb.setChecked(True)

    def get_settings(self) -> dict:
        """Get current gradient settings.

        Returns:
            Dictionary with gradient configuration
        """
        mode_map = {
            "Magnitude (Overall Change)": "magnitude",
            "Horizontal (X-direction)": "horizontal",
            "Vertical (Y-direction)": "vertical",
            "Both Directions (Arrows)": "both"
        }

        colormap_map = {
            "Hot (Red-Yellow)": "hot",
            "Cool (Blue-Cyan)": "cool",
            "Jet (Rainbow)": "jet",
            "Viridis (Smooth)": "viridis",
            "Grayscale": "gray"
        }

        return {
            'enabled': self.enable_cb.isChecked(),
            'mode': mode_map.get(self.mode_combo.currentText(), 'magnitude'),
            'threshold': self.threshold_base(),
            'sensitivity': self.sensitivity_slider.value(),
            'colormap': colormap_map.get(self.colormap_combo.currentText(), 'hot')
        }

    def is_enabled(self) -> bool:
        """Check if gradient overlay is enabled."""
        return self.enable_cb.isChecked()
