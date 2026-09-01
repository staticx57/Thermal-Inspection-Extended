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


class GradientOverlayPanel(QWidget):
    """Panel for temperature gradient visualization controls."""

    # Signals
    gradient_enabled = pyqtSignal(bool)
    gradient_mode_changed = pyqtSignal(str)  # 'magnitude', 'horizontal', 'vertical', 'both'
    gradient_threshold_changed = pyqtSignal(float)  # Minimum gradient to display
    gradient_color_map_changed = pyqtSignal(str)  # Color map name

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

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
        self.threshold_spin.setValue(1.0)
        self.threshold_spin.setSingleStep(0.5)
        self.threshold_spin.setSuffix(" °C/px")
        self.threshold_spin.setToolTip("Minimum gradient magnitude to display")
        self.threshold_spin.valueChanged.connect(self._on_threshold_changed)
        threshold_label_layout.addWidget(self.threshold_spin)
        threshold_label_layout.addStretch()

        threshold_layout.addLayout(threshold_label_layout)

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
        presets = [
            ("High Sensitivity", 0.5, 80, "magnitude"),
            ("Medium (Default)", 1.0, 50, "magnitude"),
            ("Low (Major Changes)", 3.0, 30, "magnitude"),
            ("Edge Detection", 2.0, 60, "both")
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
        logger.debug(f"Gradient threshold: {value}°C/px")
        self.gradient_threshold_changed.emit(value)

    def _on_sensitivity_changed(self, value: int):
        """Handle sensitivity slider change."""
        self.sensitivity_label.setText(f"{value}%")
        # Sensitivity affects the threshold inversely
        # Higher sensitivity = lower threshold
        adjusted_threshold = self.threshold_spin.value() * (100 - value) / 50.0
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

        self.threshold_spin.setValue(threshold)
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
            'threshold': self.threshold_spin.value(),
            'sensitivity': self.sensitivity_slider.value(),
            'colormap': colormap_map.get(self.colormap_combo.currentText(), 'hot')
        }

    def is_enabled(self) -> bool:
        """Check if gradient overlay is enabled."""
        return self.enable_cb.isChecked()
