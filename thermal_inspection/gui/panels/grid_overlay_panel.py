"""
Grid Overlay Panel for Thermal Inspection Tool
Phase 1 - Feature 4: Configurable Measurement Grid

Provides UI controls for displaying a measurement grid over the thermal image.
"""

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                              QCheckBox, QSpinBox, QPushButton, QGroupBox,
                              QColorDialog)
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QColor
import logging
from thermal_inspection.gui.themes import set_button_state

logger = logging.getLogger(__name__)


class GridOverlayPanel(QWidget):
    """
    Panel for configuring grid overlay settings.
    """

    # Signals
    grid_enabled = pyqtSignal(bool)
    grid_spacing_changed = pyqtSignal(int, int)  # (x_spacing, y_spacing)
    grid_color_changed = pyqtSignal(QColor)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        """Build the panel UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(8)

        # Title
        title = QLabel("Grid Overlay")
        title.setStyleSheet("font-weight: bold; font-size: 13px;")
        layout.addWidget(title)

        # Enable checkbox
        self.enable_cb = QCheckBox("Enable Grid Overlay")
        self.enable_cb.setToolTip("Show measurement grid over thermal image")
        self.enable_cb.setChecked(False)
        self.enable_cb.toggled.connect(self._on_enabled_toggled)
        layout.addWidget(self.enable_cb)

        # Grid spacing group
        spacing_group = QGroupBox("Grid Spacing (pixels)")
        spacing_layout = QVBoxLayout(spacing_group)

        # X spacing
        x_layout = QHBoxLayout()
        x_layout.addWidget(QLabel("Horizontal:"))
        self.x_spacing_spin = QSpinBox()
        self.x_spacing_spin.setRange(10, 500)
        self.x_spacing_spin.setValue(50)
        self.x_spacing_spin.setSuffix(" px")
        self.x_spacing_spin.setToolTip("Horizontal grid line spacing")
        self.x_spacing_spin.valueChanged.connect(self._on_spacing_changed)
        x_layout.addWidget(self.x_spacing_spin)
        x_layout.addStretch()
        spacing_layout.addLayout(x_layout)

        # Y spacing
        y_layout = QHBoxLayout()
        y_layout.addWidget(QLabel("Vertical:"))
        self.y_spacing_spin = QSpinBox()
        self.y_spacing_spin.setRange(10, 500)
        self.y_spacing_spin.setValue(50)
        self.y_spacing_spin.setSuffix(" px")
        self.y_spacing_spin.setToolTip("Vertical grid line spacing")
        self.y_spacing_spin.valueChanged.connect(self._on_spacing_changed)
        y_layout.addWidget(self.y_spacing_spin)
        y_layout.addStretch()
        spacing_layout.addLayout(y_layout)

        layout.addWidget(spacing_group)

        # Color selection
        color_layout = QHBoxLayout()
        color_layout.addWidget(QLabel("Grid Color:"))

        self.color_btn = QPushButton()
        self.color_btn.setFixedSize(60, 25)
        set_button_state(self.color_btn, "compact", True)
        self.grid_color = QColor(255, 255, 255, 128)  # Semi-transparent white
        self._update_color_button()
        self.color_btn.setToolTip("Click to choose grid color")
        self.color_btn.clicked.connect(self._on_color_clicked)
        color_layout.addWidget(self.color_btn)
        color_layout.addStretch()

        layout.addLayout(color_layout)

        # Presets
        preset_group = QGroupBox("Presets")
        preset_layout = QVBoxLayout(preset_group)

        # Preset buttons
        preset_btn_layout = QHBoxLayout()

        fine_btn = QPushButton("Fine (25px)")
        fine_btn.setToolTip("25x25 pixel grid")
        fine_btn.clicked.connect(lambda: self._apply_preset(25, 25))
        preset_btn_layout.addWidget(fine_btn)

        medium_btn = QPushButton("Medium (50px)")
        medium_btn.setToolTip("50x50 pixel grid")
        medium_btn.clicked.connect(lambda: self._apply_preset(50, 50))
        preset_btn_layout.addWidget(medium_btn)

        preset_layout.addLayout(preset_btn_layout)

        coarse_btn_layout = QHBoxLayout()

        coarse_btn = QPushButton("Coarse (100px)")
        coarse_btn.setToolTip("100x100 pixel grid")
        coarse_btn.clicked.connect(lambda: self._apply_preset(100, 100))
        coarse_btn_layout.addWidget(coarse_btn)

        custom_btn = QPushButton("Custom (64x51)")
        custom_btn.setToolTip("640/10 x 512/10 grid for Boson")
        custom_btn.clicked.connect(lambda: self._apply_preset(64, 51))
        coarse_btn_layout.addWidget(custom_btn)

        preset_layout.addLayout(coarse_btn_layout)

        layout.addWidget(preset_group)

        layout.addStretch()

    def _update_color_button(self):
        """Update color button appearance."""
        r, g, b, a = self.grid_color.getRgb()
        self.color_btn.setStyleSheet(
            f"background-color: rgba({r}, {g}, {b}, {a}); "
            f"border: 1px solid #888;"
        )

    def _on_enabled_toggled(self, checked: bool):
        """Handle enable checkbox toggle."""
        logger.info(f"Grid overlay enabled: {checked}")
        self.grid_enabled.emit(checked)

    def _on_spacing_changed(self):
        """Handle spacing value changes."""
        x = self.x_spacing_spin.value()
        y = self.y_spacing_spin.value()
        logger.debug(f"Grid spacing changed: {x}x{y}")
        self.grid_spacing_changed.emit(x, y)

    def _on_color_clicked(self):
        """Handle color button click."""
        color = QColorDialog.getColor(
            self.grid_color,
            self,
            "Select Grid Color",
            QColorDialog.ColorDialogOption.ShowAlphaChannel
        )
        if color.isValid():
            self.grid_color = color
            self._update_color_button()
            logger.info(f"Grid color changed: {color.name()}")
            self.grid_color_changed.emit(color)

    def _apply_preset(self, x: int, y: int):
        """Apply a spacing preset."""
        logger.info(f"Applying grid preset: {x}x{y}")
        self.x_spacing_spin.setValue(x)
        self.y_spacing_spin.setValue(y)
        # Signal will be emitted automatically by valueChanged

    def get_spacing(self):
        """Get current grid spacing."""
        return (self.x_spacing_spin.value(), self.y_spacing_spin.value())

    def get_color(self):
        """Get current grid color."""
        return self.grid_color

    def is_enabled(self):
        """Check if grid is enabled."""
        return self.enable_cb.isChecked()
