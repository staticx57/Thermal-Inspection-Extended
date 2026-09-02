#!/usr/bin/env python3
"""
Fusion control panel for thermal inspection application.
Handles alpha blending, fusion modes, and enhancement settings.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QLabel, QComboBox, QSlider, QScrollArea, QCheckBox
)
from PyQt6.QtCore import Qt, pyqtSignal

from thermal_inspection.processing.fusion_processor import FusionProcessor

class FusionPanel(QWidget):
    """Panel for fusion configuration settings."""

    # Signals
    fusion_mode_changed = pyqtSignal(str)
    fusion_alpha_changed = pyqtSignal(float)
    fusion_priority_changed = pyqtSignal(str)
    fusion_strength_changed = pyqtSignal(float)
    fusion_fuzziness_changed = pyqtSignal(float)
    fusion_color_mode_changed = pyqtSignal(str)  # "color" or "grayscale"
    edge_strength_changed = pyqtSignal(float)
    edge_fuzziness_changed = pyqtSignal(float)
    edge_color_changed = pyqtSignal(str)  # Color for edge overlay
    detail_strength_changed = pyqtSignal(float)  # Detail Injection/Relief Fusion strength
    detail_quality_changed = pyqtSignal(float)   # Detail Injection/Relief Fusion quality level
    laplacian_gpu_changed = pyqtSignal(bool)       # Laplacian Pyramid: GPU (CUDA) acceleration on/off
    laplacian_cpu_scale_changed = pyqtSignal(float)  # Laplacian Pyramid: CPU fallback internal resolution scale

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self):
        # Main layout with scroll area
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)

        content_widget = QWidget()
        layout = QVBoxLayout(content_widget)
        layout.setSpacing(12)
        layout.setContentsMargins(10, 10, 10, 10)

        # Fusion Settings Group
        fusion_group = QGroupBox("General Fusion Settings")
        fusion_layout = QVBoxLayout(fusion_group)
        fusion_layout.setSpacing(10)
        fusion_layout.setContentsMargins(8, 8, 8, 8)

        # Mode
        mode_layout = QHBoxLayout()
        mode_layout.addWidget(QLabel("Mode:"))
        self.fusion_mode_combo = QComboBox()
        self.fusion_mode_combo.setMinimumHeight(28)
        # Display the human-readable label, but keep the real mode string as
        # itemData - this dropdown used to show the raw snake_case mode
        # strings (e.g. "enhanced_edge_highlight") directly to the user.
        for mode in FusionProcessor.AVAILABLE_FUSION_MODES:
            label = FusionProcessor.FUSION_MODE_LABELS.get(mode, mode)
            self.fusion_mode_combo.addItem(label, mode)
        self.fusion_mode_combo.currentIndexChanged.connect(self._on_fusion_mode_changed)
        mode_layout.addWidget(self.fusion_mode_combo)
        fusion_layout.addLayout(mode_layout)

        # Alpha
        alpha_layout = QHBoxLayout()
        alpha_layout.addWidget(QLabel("Alpha:"))
        self.alpha_slider = QSlider(Qt.Orientation.Horizontal)
        self.alpha_slider.setRange(0, 100)
        self.alpha_slider.setValue(50)
        self.alpha_slider.valueChanged.connect(
            lambda v: self.fusion_alpha_changed.emit(v / 100.0)
        )
        alpha_layout.addWidget(self.alpha_slider)
        fusion_layout.addLayout(alpha_layout)

        # Priority
        priority_layout = QHBoxLayout()
        priority_layout.addWidget(QLabel("Priority:"))
        self.priority_combo = QComboBox()
        self.priority_combo.setMinimumHeight(28)
        self.priority_combo.addItems(["Thermal", "RGB", "Balanced"])
        self.priority_combo.currentTextChanged.connect(self.fusion_priority_changed.emit)
        priority_layout.addWidget(self.priority_combo)
        fusion_layout.addLayout(priority_layout)

        # RGB Color Mode (Grayscale vs Color)
        color_mode_layout = QHBoxLayout()
        color_mode_layout.addWidget(QLabel("RGB Mode:"))
        self.fusion_color_mode_combo = QComboBox()
        self.fusion_color_mode_combo.setMinimumHeight(28)
        self.fusion_color_mode_combo.addItems(["Color", "Grayscale"])
        self.fusion_color_mode_combo.setToolTip("Use color or grayscale from RGB camera for fusion")
        self.fusion_color_mode_combo.currentTextChanged.connect(
            lambda v: self.fusion_color_mode_changed.emit(v.lower())
        )
        color_mode_layout.addWidget(self.fusion_color_mode_combo)
        fusion_layout.addLayout(color_mode_layout)

        # Fusion Strength
        strength_layout = QHBoxLayout()
        strength_label = QLabel("Strength:")
        strength_layout.addWidget(strength_label)
        self.fusion_strength_slider = QSlider(Qt.Orientation.Horizontal)
        self.fusion_strength_slider.setRange(0, 100)
        self.fusion_strength_slider.setValue(70)
        self.fusion_strength_slider.setToolTip("Fusion blending strength (0-100)")
        self.fusion_strength_value = QLabel("70")
        self.fusion_strength_slider.valueChanged.connect(
            lambda v: [self.fusion_strength_value.setText(str(v)),
                      self.fusion_strength_changed.emit(v / 100.0)]
        )
        strength_layout.addWidget(self.fusion_strength_slider)
        strength_layout.addWidget(self.fusion_strength_value)
        fusion_layout.addLayout(strength_layout)

        # Fusion Fuzziness
        fuzz_layout = QHBoxLayout()
        fuzz_label = QLabel("Fuzziness:")
        fuzz_layout.addWidget(fuzz_label)
        self.fusion_fuzziness_slider = QSlider(Qt.Orientation.Horizontal)
        self.fusion_fuzziness_slider.setRange(0, 100)
        self.fusion_fuzziness_slider.setValue(30)
        self.fusion_fuzziness_slider.setToolTip("Edge blending smoothness (0-100)")
        self.fusion_fuzziness_value = QLabel("30")
        self.fusion_fuzziness_slider.valueChanged.connect(
            lambda v: [self.fusion_fuzziness_value.setText(str(v)),
                      self.fusion_fuzziness_changed.emit(v / 100.0)]
        )
        fuzz_layout.addWidget(self.fusion_fuzziness_slider)
        fuzz_layout.addWidget(self.fusion_fuzziness_value)
        fusion_layout.addLayout(fuzz_layout)

        layout.addWidget(fusion_group)

        # Adaptive Fusion Settings (changes based on selected fusion mode)
        self.fusion_settings_group = QGroupBox("Advanced Mode Settings")
        self.fusion_settings_layout = QVBoxLayout(self.fusion_settings_group)
        self.fusion_settings_layout.setSpacing(10)
        self.fusion_settings_layout.setContentsMargins(8, 8, 8, 8)

        # Edge Enhanced Settings (initially visible)
        self.edge_settings_widget = QWidget()
        edge_settings_layout = QVBoxLayout(self.edge_settings_widget)
        edge_settings_layout.setContentsMargins(0, 0, 0, 0)
        edge_settings_layout.setSpacing(10)

        # Edge Strength
        edge_strength_layout = QHBoxLayout()
        edge_strength_label = QLabel("Strength:")
        edge_strength_layout.addWidget(edge_strength_label)
        self.edge_strength_slider = QSlider(Qt.Orientation.Horizontal)
        self.edge_strength_slider.setRange(0, 100)
        self.edge_strength_slider.setValue(50)
        self.edge_strength_slider.setToolTip("How many edges to detect (higher = more edges shown)")
        self.edge_strength_value = QLabel("50")
        self.edge_strength_slider.valueChanged.connect(
            lambda v: [self.edge_strength_value.setText(str(v)),
                      self.edge_strength_changed.emit(v / 100.0)]
        )
        edge_strength_layout.addWidget(self.edge_strength_slider)
        edge_strength_layout.addWidget(self.edge_strength_value)
        edge_settings_layout.addLayout(edge_strength_layout)

        # Edge Fuzziness
        edge_fuzz_layout = QHBoxLayout()
        edge_fuzz_label = QLabel("Fuzziness:")
        edge_fuzz_layout.addWidget(edge_fuzz_label)
        self.edge_fuzziness_slider = QSlider(Qt.Orientation.Horizontal)
        self.edge_fuzziness_slider.setRange(0, 100)
        self.edge_fuzziness_slider.setValue(20)
        self.edge_fuzziness_slider.setToolTip("Edge sharpness (lower = sharper edges, more detail; higher = softer edges)")
        self.edge_fuzziness_value = QLabel("20")
        self.edge_fuzziness_slider.valueChanged.connect(
            lambda v: [self.edge_fuzziness_value.setText(str(v)),
                      self.edge_fuzziness_changed.emit(v / 100.0)]
        )
        edge_fuzz_layout.addWidget(self.edge_fuzziness_slider)
        edge_fuzz_layout.addWidget(self.edge_fuzziness_value)
        edge_settings_layout.addLayout(edge_fuzz_layout)

        # Edge Color
        edge_color_layout = QHBoxLayout()
        edge_color_layout.addWidget(QLabel("Edge Color:"))
        self.edge_color_combo = QComboBox()
        self.edge_color_combo.setMinimumHeight(28)
        self.edge_color_combo.addItems(["White", "Cyan", "Green", "Yellow", "Red", "Magenta"])
        self.edge_color_combo.setToolTip("Color for edge overlay visualization")
        self.edge_color_combo.currentTextChanged.connect(
            lambda v: self.edge_color_changed.emit(v.lower())
        )
        edge_color_layout.addWidget(self.edge_color_combo)
        edge_settings_layout.addLayout(edge_color_layout)

        # Detail Injection/Relief Fusion Settings (initially hidden)
        self.detail_settings_widget = QWidget()
        detail_settings_layout = QVBoxLayout(self.detail_settings_widget)
        detail_settings_layout.setContentsMargins(0, 0, 0, 0)
        detail_settings_layout.setSpacing(10)

        # Detail Strength
        detail_strength_layout = QHBoxLayout()
        detail_strength_label = QLabel("Strength:")
        detail_strength_layout.addWidget(detail_strength_label)
        self.detail_strength_slider = QSlider(Qt.Orientation.Horizontal)
        self.detail_strength_slider.setRange(0, 100)
        self.detail_strength_slider.setValue(70)
        self.detail_strength_slider.setToolTip("Detail overlay strength (higher = more visible structure)")
        self.detail_strength_value = QLabel("70")
        self.detail_strength_slider.valueChanged.connect(
            lambda v: [self.detail_strength_value.setText(str(v)),
                      self.detail_strength_changed.emit(v / 100.0)]
        )
        detail_strength_layout.addWidget(self.detail_strength_slider)
        detail_strength_layout.addWidget(self.detail_strength_value)
        detail_settings_layout.addLayout(detail_strength_layout)

        # Detail Quality
        detail_quality_layout = QHBoxLayout()
        detail_quality_label = QLabel("Quality:")
        detail_quality_layout.addWidget(detail_quality_label)
        self.detail_quality_slider = QSlider(Qt.Orientation.Horizontal)
        self.detail_quality_slider.setRange(0, 100)
        self.detail_quality_slider.setValue(50)
        self.detail_quality_slider.setToolTip("Detail quality/level (higher = more detail extraction)")
        self.detail_quality_value = QLabel("50")
        self.detail_quality_slider.valueChanged.connect(
            lambda v: [self.detail_quality_value.setText(str(v)),
                      self.detail_quality_changed.emit(v / 100.0)]
        )
        detail_quality_layout.addWidget(self.detail_quality_slider)
        detail_quality_layout.addWidget(self.detail_quality_value)
        detail_settings_layout.addLayout(detail_quality_layout)

        # Laplacian Pyramid Settings (initially hidden) - this mode's cost
        # is dominated by full-resolution work at its base pyramid level,
        # so it's the only mode with a real speed/quality knob: GPU
        # (torch/CUDA) keeps full resolution and full quality when a CUDA
        # GPU is available (~4x faster than CPU); the CPU fallback trades
        # a real, visible loss of edge/detail precision for speed via
        # internal resolution scale instead.
        self.laplacian_settings_widget = QWidget()
        laplacian_settings_layout = QVBoxLayout(self.laplacian_settings_widget)
        laplacian_settings_layout.setContentsMargins(0, 0, 0, 0)
        laplacian_settings_layout.setSpacing(10)

        self.laplacian_gpu_checkbox = QCheckBox("Use GPU acceleration (CUDA)")
        self.laplacian_gpu_checkbox.setChecked(True)
        self.laplacian_gpu_checkbox.setToolTip(
            "Keeps full resolution/quality at ~4x the speed of CPU processing.\n"
            "Falls back to CPU automatically if no CUDA GPU is available."
        )
        self.laplacian_gpu_checkbox.toggled.connect(self.laplacian_gpu_changed.emit)
        laplacian_settings_layout.addWidget(self.laplacian_gpu_checkbox)

        laplacian_scale_layout = QHBoxLayout()
        laplacian_scale_label = QLabel("CPU Quality:")
        laplacian_scale_layout.addWidget(laplacian_scale_label)
        self.laplacian_scale_slider = QSlider(Qt.Orientation.Horizontal)
        self.laplacian_scale_slider.setRange(25, 100)
        self.laplacian_scale_slider.setValue(50)
        self.laplacian_scale_slider.setToolTip(
            "Internal processing resolution when running on CPU (no effect while GPU "
            "acceleration is active/available). Lower = faster but softer edge detail."
        )
        self.laplacian_scale_value = QLabel("50%")
        self.laplacian_scale_slider.valueChanged.connect(
            lambda v: [self.laplacian_scale_value.setText(f"{v}%"),
                      self.laplacian_cpu_scale_changed.emit(v / 100.0)]
        )
        laplacian_scale_layout.addWidget(self.laplacian_scale_slider)
        laplacian_scale_layout.addWidget(self.laplacian_scale_value)
        laplacian_settings_layout.addLayout(laplacian_scale_layout)

        # Add widgets to fusion settings group
        self.fusion_settings_layout.addWidget(self.edge_settings_widget)
        self.fusion_settings_layout.addWidget(self.detail_settings_widget)
        self.fusion_settings_layout.addWidget(self.laplacian_settings_widget)
        self.detail_settings_widget.hide()  # Initially hidden
        self.laplacian_settings_widget.hide()  # Initially hidden


        layout.addWidget(self.fusion_settings_group)
        layout.addStretch()

        scroll.setWidget(content_widget)
        main_layout.addWidget(scroll)

    def _on_fusion_mode_changed(self, index: int):
        """Handle mode combo change - look up the real mode string from
        itemData (the combo displays a human-readable label, e.g. "Edge
        Enhanced", not the raw "edge_enhanced" mode string itself)."""
        mode = self.fusion_mode_combo.itemData(index)
        if not mode:
            return
        self._update_fusion_settings(mode)
        self.fusion_mode_changed.emit(mode)

    def _update_fusion_settings(self, mode: str):
        """Update visible settings based on fusion mode."""
        if mode == "edge_enhanced":
            self.edge_settings_widget.show()
            self.detail_settings_widget.hide()
            self.laplacian_settings_widget.hide()
            self.fusion_settings_group.setTitle("Edge Enhancement Settings")
        elif mode in ["detail_inject", "relief_fusion"]:
            self.edge_settings_widget.hide()
            self.detail_settings_widget.show()
            self.laplacian_settings_widget.hide()
            self.fusion_settings_group.setTitle("Detail Injection Settings")
        elif mode == "laplacian_pyramid":
            self.edge_settings_widget.hide()
            self.detail_settings_widget.hide()
            self.laplacian_settings_widget.show()
            self.fusion_settings_group.setTitle("Laplacian Pyramid Settings")
        else:
            self.edge_settings_widget.hide()
            self.detail_settings_widget.hide()
            self.laplacian_settings_widget.hide()
            self.fusion_settings_group.setTitle("Advanced Settings (None)")
