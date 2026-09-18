#!/usr/bin/env python3
"""
Fusion control panel for thermal inspection application.
Handles alpha blending, fusion modes, and enhancement settings.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QLabel, QComboBox, QSlider, QScrollArea, QCheckBox, QGraphicsOpacityEffect
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
    edge_line_size_changed = pyqtSignal(float)  # Edge Enhanced: line thickness, independent of Strength
    detail_strength_changed = pyqtSignal(float)  # Detail Injection/Relief Fusion strength
    detail_quality_changed = pyqtSignal(float)   # Detail Injection/Relief Fusion quality level
    laplacian_gpu_changed = pyqtSignal(bool)       # Laplacian Pyramid: GPU (CUDA) acceleration on/off
    laplacian_cpu_scale_changed = pyqtSignal(float)  # Laplacian Pyramid: CPU fallback internal resolution scale

    contour_line_size_changed = pyqtSignal(float)     # Thermal Contours: line thickness
    contour_level_count_changed = pyqtSignal(int)     # Thermal Contours: number of threshold levels
    contour_labels_changed = pyqtSignal(bool)         # Thermal Contours: isotherm value labels on/off
    contour_fill_changed = pyqtSignal(bool)           # Thermal Contours: translucent per-level fill on/off
    adaptive_canny_changed = pyqtSignal(bool)         # edge_enhanced: adaptive Canny thresholds
    edge_direction_changed = pyqtSignal(str)          # 'all', 'horizontal', 'vertical'
    sobel_alpha_changed = pyqtSignal(bool)            # Sobel-magnitude-modulated edge opacity
    edge_color_mode_changed = pyqtSignal(str)         # 'fixed' or 'palette'
    detail_balance_changed = pyqtSignal(float)        # Edge Enhanced: optional multi-scale consensus strictness
    relief_light_direction_changed = pyqtSignal(str)  # Relief Fusion: apparent light-source corner
    overlay_hot_percentile_changed = pyqtSignal(float)  # Thermal Overlay: hot/bright-mask percentile threshold
    pip_size_changed = pyqtSignal(float)              # Picture in Picture: inset size
    pip_position_changed = pyqtSignal(str)            # Picture in Picture: inset corner

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
        # strings (e.g. "guided_filter_fusion") directly to the user.
        for mode in FusionProcessor.AVAILABLE_FUSION_MODES:
            label = FusionProcessor.FUSION_MODE_LABELS.get(mode, mode)
            self.fusion_mode_combo.addItem(label, mode)
        self.fusion_mode_combo.currentIndexChanged.connect(self._on_fusion_mode_changed)
        mode_layout.addWidget(self.fusion_mode_combo)
        fusion_layout.addLayout(mode_layout)

        # Alpha - only alpha_blend actually reads this value; everywhere
        # else it's a dead control. Disabled per-mode in
        # _update_fusion_settings rather than hidden, so its existence
        # (and why it's greyed out) stays visible instead of silently
        # doing nothing.
        alpha_layout = QHBoxLayout()
        self.alpha_label = QLabel("Alpha:")
        alpha_layout.addWidget(self.alpha_label)
        self.alpha_slider = QSlider(Qt.Orientation.Horizontal)
        self.alpha_slider.setRange(0, 100)
        self.alpha_slider.setValue(50)
        self.alpha_slider.setToolTip("Alpha Blend's own mix ratio - only affects the Alpha Blend mode.")
        self.alpha_slider.valueChanged.connect(
            lambda v: self.fusion_alpha_changed.emit(v / 100.0)
        )
        alpha_layout.addWidget(self.alpha_slider)
        fusion_layout.addLayout(alpha_layout)

        # Priority - "Balanced" was removed: FusionProcessor.set_priority()
        # only ever accepted 'thermal'/'rgb', and main_window.py silently
        # mapped 'balanced' to 'thermal' - so it was never a real third
        # option, just a relabeled duplicate of "Thermal" that looked like
        # a distinct choice. Disabled (not hidden) per-mode below for the
        # 5 modes that don't read fusion_priority at all.
        priority_layout = QHBoxLayout()
        self.priority_label = QLabel("Priority:")
        priority_layout.addWidget(self.priority_label)
        self.priority_combo = QComboBox()
        self.priority_combo.setMinimumHeight(28)
        self.priority_combo.addItems(["Thermal", "RGB"])
        self.priority_combo.setToolTip("Which camera is treated as the base/biased source. Not used by every mode.")
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

        # Fusion Strength - default was 70, but FusionProcessor's own
        # fusion_intensity actually initializes to 0.5 (config.get(
        # 'fusion.intensity', 0.5), no matching config key ever set) with
        # nothing syncing the two - so a fresh launch actually ran at 50%
        # strength while this slider claimed 70%, until touched. Matched
        # to the engine's real initial value.
        strength_layout = QHBoxLayout()
        self.strength_label = QLabel("Strength:")
        strength_layout.addWidget(self.strength_label)
        self.fusion_strength_slider = QSlider(Qt.Orientation.Horizontal)
        self.fusion_strength_slider.setRange(0, 100)
        self.fusion_strength_slider.setValue(50)
        self.fusion_strength_slider.setToolTip("Fusion blending strength (0-100). Not used by every mode.")
        self.fusion_strength_value = QLabel("50")
        self.fusion_strength_slider.valueChanged.connect(
            lambda v: [self.fusion_strength_value.setText(str(v)),
                      self.fusion_strength_changed.emit(v / 100.0)]
        )
        strength_layout.addWidget(self.fusion_strength_slider)
        strength_layout.addWidget(self.fusion_strength_value)
        fusion_layout.addLayout(strength_layout)

        # Fusion Fuzziness - same default-mismatch issue as Strength:
        # FusionProcessor's edge_blur_kernel actually initializes to 0
        # (sharp edges), not the kernel size this slider's old default of
        # 30 (-> kernel_size=4) implied. Matched to the engine's real
        # initial value. Also only used by the 2 edge modes - dead
        # elsewhere, disabled per-mode below.
        fuzz_layout = QHBoxLayout()
        self.fuzz_label = QLabel("Fuzziness:")
        fuzz_layout.addWidget(self.fuzz_label)
        self.fusion_fuzziness_slider = QSlider(Qt.Orientation.Horizontal)
        self.fusion_fuzziness_slider.setRange(0, 100)
        self.fusion_fuzziness_slider.setValue(0)
        self.fusion_fuzziness_slider.setToolTip("Edge blending smoothness (0-100). Only affects Edge Enhanced / Enhanced Edge Highlight.")
        self.fusion_fuzziness_value = QLabel("0")
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

        # Edge Sensitivity - labeled "Strength" until 2026-09-07, renamed
        # to disambiguate from General Fusion Settings' own "Strength"
        # (fusion_intensity, which controls blend opacity - a completely
        # different concept from this slider's actual effect, Canny
        # threshold sensitivity/how many edges get detected at all).
        edge_strength_layout = QHBoxLayout()
        edge_strength_label = QLabel("Sensitivity:")
        edge_strength_layout.addWidget(edge_strength_label)
        self.edge_strength_slider = QSlider(Qt.Orientation.Horizontal)
        self.edge_strength_slider.setRange(0, 100)
        self.edge_strength_slider.setValue(50)
        self.edge_strength_slider.setToolTip("How many edges to detect (higher = more edges shown). No effect while Adaptive Thresholds is on.")
        self.edge_strength_value = QLabel("50")
        self.edge_strength_slider.valueChanged.connect(
            lambda v: [self.edge_strength_value.setText(str(v)),
                      self.edge_strength_changed.emit(v / 100.0)]
        )
        edge_strength_layout.addWidget(self.edge_strength_slider)
        edge_strength_layout.addWidget(self.edge_strength_value)
        edge_settings_layout.addLayout(edge_strength_layout)

        # Edge Fuzziness removed from here (2026-09-07): this mode-specific
        # slider and General Fusion Settings' own "Fuzziness" both set the
        # exact same edge_blur_kernel attribute - once General Fuzziness
        # was correctly gated to enable/disable per-mode (rather than
        # always shown regardless of relevance), Edge Enhanced ended up
        # showing BOTH sliders simultaneously, two independent, unsynced
        # QSlider widgets both claiming to represent one underlying value.
        # General Fusion Settings' Fuzziness is enabled for both edge
        # modes and is the sole control for it now - kept here only as
        # much history as this comment, not a second slider.

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

        # Edge Line Size - independent of Strength (visibility/alpha) and
        # Fuzziness (blur softness); previously edge_enhanced had no line
        # thickness control at all, Canny's raw thin edges were the only
        # option.
        edge_line_size_layout = QHBoxLayout()
        edge_line_size_label = QLabel("Line Size:")
        edge_line_size_layout.addWidget(edge_line_size_label)
        self.edge_line_size_slider = QSlider(Qt.Orientation.Horizontal)
        self.edge_line_size_slider.setRange(0, 100)
        self.edge_line_size_slider.setValue(50)
        self.edge_line_size_slider.setToolTip(
            "Edge line thickness, independent of Strength (visibility) and "
            "Fuzziness (softness). Higher = thicker, bolder lines."
        )
        self.edge_line_size_value = QLabel("50")
        self.edge_line_size_slider.valueChanged.connect(
            lambda v: [self.edge_line_size_value.setText(str(v)),
                      self.edge_line_size_changed.emit(v / 100.0)]
        )
        edge_line_size_layout.addWidget(self.edge_line_size_slider)
        edge_line_size_layout.addWidget(self.edge_line_size_value)
        edge_settings_layout.addLayout(edge_line_size_layout)

        # Detail Balance - how strictly this mode requires an edge to be
        # corroborated across scales before drawing it (a real consensus
        # filter, not a blend weight - see detail_balance's own docstring
        # in FusionProcessor.__init__). Formerly the whole reason a
        # separate "Enhanced Edge Highlight" mode existed; merged in here
        # 2026-09-07 after two rounds of trying to make that separate mode
        # read as genuinely distinct from this one on real camera footage
        # ("they are still the same mode... they do the same thing even
        # if the algorithm is slightly different") - it's a parameter of
        # this one detection strategy, not a second fusion concept.
        # Default 0 (off/single-scale) so Edge Enhanced's own long-standing
        # default behavior is unchanged unless this is deliberately raised.
        detail_balance_layout = QHBoxLayout()
        detail_balance_layout.addWidget(QLabel("Detail Balance:"))
        self.detail_balance_slider = QSlider(Qt.Orientation.Horizontal)
        self.detail_balance_slider.setRange(0, 100)
        self.detail_balance_slider.setValue(0)  # matches FusionProcessor's own default (off)
        self.detail_balance_slider.setToolTip(
            "Off (0) uses a single detection pass, same as this mode's classic behavior.\n"
            "Above 0 requires coarse-scale corroboration before drawing a fine edge - "
            "trades some detail for less fine-scale sensor/texture noise."
        )
        self.detail_balance_value = QLabel("0")
        self.detail_balance_slider.valueChanged.connect(
            lambda v: [self.detail_balance_value.setText(str(v)),
                      self.detail_balance_changed.emit(v / 100.0)]
        )
        detail_balance_layout.addWidget(self.detail_balance_slider)
        detail_balance_layout.addWidget(self.detail_balance_value)
        edge_settings_layout.addLayout(detail_balance_layout)

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

        # Light Direction - Relief Fusion only (Detail Injection has no
        # emboss step to direct). An emboss/"directional difference"
        # filter's apparent light source is set entirely by which corner
        # its negative weights sit in - a well-established technique, not
        # a cosmetic add-on (see Wikipedia's Image embossing article). The
        # 4 options are exact 90-degree rotations of the mode's one
        # original kernel (top_left), so top_left's own behavior is
        # unchanged. Row visibility is toggled per-mode in
        # _update_fusion_settings, not just this whole widget's, since
        # Detail Injection shares this group but has no use for it.
        self.relief_light_direction_row = QWidget()
        relief_light_direction_layout = QHBoxLayout(self.relief_light_direction_row)
        relief_light_direction_layout.setContentsMargins(0, 0, 0, 0)
        relief_light_direction_layout.addWidget(QLabel("Light Direction:"))
        self.relief_light_direction_combo = QComboBox()
        self.relief_light_direction_combo.setMinimumHeight(28)
        self.relief_light_direction_combo.addItem("Top Left", "top_left")
        self.relief_light_direction_combo.addItem("Top Right", "top_right")
        self.relief_light_direction_combo.addItem("Bottom Right", "bottom_right")
        self.relief_light_direction_combo.addItem("Bottom Left", "bottom_left")
        self.relief_light_direction_combo.setToolTip("Which corner the apparent light source sits in for the embossed relief effect")
        self.relief_light_direction_combo.currentIndexChanged.connect(
            lambda i: self.relief_light_direction_changed.emit(self.relief_light_direction_combo.itemData(i))
        )
        relief_light_direction_layout.addWidget(self.relief_light_direction_combo)
        detail_settings_layout.addWidget(self.relief_light_direction_row)

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

        # Thermal Contours Settings (initially hidden) - this mode
        # previously had zero mode-specific settings at all (fell into the
        # "Advanced Settings (None)" branch below).
        self.contour_settings_widget = QWidget()
        contour_settings_layout = QVBoxLayout(self.contour_settings_widget)
        contour_settings_layout.setContentsMargins(0, 0, 0, 0)
        contour_settings_layout.setSpacing(10)

        contour_line_size_layout = QHBoxLayout()
        contour_line_size_layout.addWidget(QLabel("Line Size:"))
        self.contour_line_size_slider = QSlider(Qt.Orientation.Horizontal)
        self.contour_line_size_slider.setRange(0, 100)
        self.contour_line_size_slider.setValue(50)
        self.contour_line_size_slider.setToolTip("Isotherm line thickness (independent of edge modes' Line Size).")
        self.contour_line_size_value = QLabel("50")
        self.contour_line_size_slider.valueChanged.connect(
            lambda v: [self.contour_line_size_value.setText(str(v)),
                      self.contour_line_size_changed.emit(v / 100.0)]
        )
        contour_line_size_layout.addWidget(self.contour_line_size_slider)
        contour_line_size_layout.addWidget(self.contour_line_size_value)
        contour_settings_layout.addLayout(contour_line_size_layout)

        contour_levels_layout = QHBoxLayout()
        contour_levels_layout.addWidget(QLabel("Levels:"))
        self.contour_levels_slider = QSlider(Qt.Orientation.Horizontal)
        self.contour_levels_slider.setRange(3, 12)
        self.contour_levels_slider.setValue(8)
        self.contour_levels_slider.setToolTip(
            "Number of temperature threshold levels. More = finer gradation "
            "but costs scale roughly linearly with level count."
        )
        self.contour_levels_value = QLabel("8")
        self.contour_levels_slider.valueChanged.connect(
            lambda v: [self.contour_levels_value.setText(str(v)),
                      self.contour_level_count_changed.emit(v)]
        )
        contour_levels_layout.addWidget(self.contour_levels_slider)
        contour_levels_layout.addWidget(self.contour_levels_value)
        contour_settings_layout.addLayout(contour_levels_layout)

        self.contour_labels_checkbox = QCheckBox("Show Temperature Labels")
        self.contour_labels_checkbox.setToolTip(
            "Labels each isotherm with its real temperature - only shows a "
            "value when the camera is radiometric or 8-bit estimation is "
            "enabled elsewhere in the app; otherwise this has no effect."
        )
        self.contour_labels_checkbox.toggled.connect(self.contour_labels_changed.emit)
        contour_settings_layout.addWidget(self.contour_labels_checkbox)

        self.contour_fill_checkbox = QCheckBox("Highlight Isotherm Regions")
        self.contour_fill_checkbox.setToolTip(
            "Tints each isotherm's own region with its contour color at low "
            "opacity, in addition to the line - since regions nest inside "
            "cooler ones, hotter areas end up more saturated, a graduated "
            "heat tint rather than one flat wash."
        )
        self.contour_fill_checkbox.toggled.connect(self.contour_fill_changed.emit)
        contour_settings_layout.addWidget(self.contour_fill_checkbox)

        # Thermal Overlay Settings (initially hidden) - this is the app's
        # DEFAULT fusion mode, and previously had zero mode-specific
        # settings at all: what counts as "hot" enough to overlay was a
        # hardcoded 70th percentile of the overlay source's own frame,
        # with no way to tune it per scene.
        self.overlay_settings_widget = QWidget()
        overlay_settings_layout = QVBoxLayout(self.overlay_settings_widget)
        overlay_settings_layout.setContentsMargins(0, 0, 0, 0)
        overlay_settings_layout.setSpacing(10)

        overlay_threshold_layout = QHBoxLayout()
        overlay_threshold_layout.addWidget(QLabel("Hot Threshold:"))
        self.overlay_threshold_slider = QSlider(Qt.Orientation.Horizontal)
        self.overlay_threshold_slider.setRange(1, 99)
        self.overlay_threshold_slider.setValue(70)
        self.overlay_threshold_slider.setToolTip(
            "Percentile of the overlay source's own brightness that counts as "
            "\"hot\"/bright enough to show through. Lower = more of the frame "
            "is highlighted; higher = only the most extreme values."
        )
        self.overlay_threshold_value = QLabel("70")
        self.overlay_threshold_slider.valueChanged.connect(
            lambda v: [self.overlay_threshold_value.setText(str(v)),
                      self.overlay_hot_percentile_changed.emit(float(v))]
        )
        overlay_threshold_layout.addWidget(self.overlay_threshold_slider)
        overlay_threshold_layout.addWidget(self.overlay_threshold_value)
        overlay_settings_layout.addLayout(overlay_threshold_layout)

        # Picture in Picture Settings (initially hidden) - pip_size/
        # position were real parameters (FusionProcessor._picture_in_picture's
        # own function signature) that were never exposed anywhere in the
        # GUI at all, permanently stuck at the function's own hardcoded
        # defaults (0.25, top-right).
        self.pip_settings_widget = QWidget()
        pip_settings_layout = QVBoxLayout(self.pip_settings_widget)
        pip_settings_layout.setContentsMargins(0, 0, 0, 0)
        pip_settings_layout.setSpacing(10)

        pip_size_layout = QHBoxLayout()
        pip_size_layout.addWidget(QLabel("Inset Size:"))
        self.pip_size_slider = QSlider(Qt.Orientation.Horizontal)
        self.pip_size_slider.setRange(10, 90)
        self.pip_size_slider.setValue(25)
        self.pip_size_slider.setToolTip("Inset size as a percentage of the main frame")
        self.pip_size_value = QLabel("25%")
        self.pip_size_slider.valueChanged.connect(
            lambda v: [self.pip_size_value.setText(f"{v}%"),
                      self.pip_size_changed.emit(v / 100.0)]
        )
        pip_size_layout.addWidget(self.pip_size_slider)
        pip_size_layout.addWidget(self.pip_size_value)
        pip_settings_layout.addLayout(pip_size_layout)

        pip_position_layout = QHBoxLayout()
        pip_position_layout.addWidget(QLabel("Position:"))
        self.pip_position_combo = QComboBox()
        self.pip_position_combo.setMinimumHeight(28)
        self.pip_position_combo.addItem("Top Right", "top-right")
        self.pip_position_combo.addItem("Top Left", "top-left")
        self.pip_position_combo.addItem("Bottom Right", "bottom-right")
        self.pip_position_combo.addItem("Bottom Left", "bottom-left")
        self.pip_position_combo.currentIndexChanged.connect(
            lambda i: self.pip_position_changed.emit(self.pip_position_combo.itemData(i))
        )
        pip_position_layout.addWidget(self.pip_position_combo)
        pip_settings_layout.addLayout(pip_position_layout)

        # Advanced Edge Options (initially hidden) - Edge Enhanced's own
        # Canny/Sobel detection options. Was shared across two edge modes
        # before Enhanced Edge Highlight was merged into Edge Enhanced
        # (2026-09-07); kept as its own widget since it's still logically
        # separate from the mode-specific settings above.
        self.edge_advanced_options_widget = QWidget()
        edge_advanced_layout = QVBoxLayout(self.edge_advanced_options_widget)
        edge_advanced_layout.setContentsMargins(0, 0, 0, 0)
        edge_advanced_layout.setSpacing(10)

        advanced_label = QLabel("Advanced Edge Options")
        advanced_label.setStyleSheet("font-weight: bold;")
        edge_advanced_layout.addWidget(advanced_label)

        self.adaptive_canny_checkbox = QCheckBox("Adaptive Thresholds")
        self.adaptive_canny_checkbox.setToolTip(
            "Per-frame median-based edge thresholds instead of fixed Strength - "
            "keeps detection density consistent as scene brightness shifts. "
            "Off by default: adds real per-frame cost (throttled, not every frame)."
        )
        self.adaptive_canny_checkbox.toggled.connect(self.adaptive_canny_changed.emit)
        edge_advanced_layout.addWidget(self.adaptive_canny_checkbox)

        direction_layout = QHBoxLayout()
        direction_layout.addWidget(QLabel("Direction:"))
        self.edge_direction_combo = QComboBox()
        self.edge_direction_combo.setMinimumHeight(28)
        self.edge_direction_combo.addItems(["All", "Horizontal", "Vertical"])
        self.edge_direction_combo.setToolTip(
            "Restrict detection to one gradient axis - useful for isolating "
            "linear structure (pipe/conduit runs) from ambient texture. "
            "'All' is the default, unchanged behavior."
        )
        self.edge_direction_combo.currentTextChanged.connect(
            lambda v: self.edge_direction_changed.emit(v.lower())
        )
        direction_layout.addWidget(self.edge_direction_combo)
        edge_advanced_layout.addLayout(direction_layout)

        self.sobel_alpha_checkbox = QCheckBox("Gradient-Weighted Opacity")
        self.sobel_alpha_checkbox.setToolTip(
            "Strong edges render more opaque than faint ones, instead of every "
            "edge pixel getting the same flat opacity. Off by default: adds "
            "real per-frame cost."
        )
        self.sobel_alpha_checkbox.toggled.connect(self.sobel_alpha_changed.emit)
        edge_advanced_layout.addWidget(self.sobel_alpha_checkbox)

        self.palette_edge_color_checkbox = QCheckBox("Palette-Aware Color")
        self.palette_edge_color_checkbox.setToolTip(
            "Samples the active palette at each edge pixel's own temperature "
            "instead of one fixed color. Works best with RGB Mode set to "
            "Grayscale - against a full-color base, a palette-matched edge "
            "can blend into its surroundings instead of standing out."
        )
        self.palette_edge_color_checkbox.toggled.connect(
            lambda checked: self.edge_color_mode_changed.emit('palette' if checked else 'fixed')
        )
        edge_advanced_layout.addWidget(self.palette_edge_color_checkbox)

        # Add widgets to fusion settings group
        self.fusion_settings_layout.addWidget(self.edge_settings_widget)
        self.fusion_settings_layout.addWidget(self.contour_settings_widget)
        self.fusion_settings_layout.addWidget(self.overlay_settings_widget)
        self.fusion_settings_layout.addWidget(self.pip_settings_widget)
        self.fusion_settings_layout.addWidget(self.edge_advanced_options_widget)
        self.fusion_settings_layout.addWidget(self.detail_settings_widget)
        self.fusion_settings_layout.addWidget(self.laplacian_settings_widget)
        self.contour_settings_widget.hide()  # Initially hidden
        self.overlay_settings_widget.hide()  # Initially hidden
        self.pip_settings_widget.hide()  # Initially hidden
        self.edge_advanced_options_widget.hide()  # Initially hidden
        self.detail_settings_widget.hide()  # Initially hidden
        self.laplacian_settings_widget.hide()  # Initially hidden


        layout.addWidget(self.fusion_settings_group)
        layout.addStretch()

        scroll.setWidget(content_widget)
        main_layout.addWidget(scroll)

        # QComboBox.addItem() fires currentIndexChanged synchronously for
        # the very first item added to an empty combo (verified directly),
        # so _on_fusion_mode_changed already ran once during the mode-combo
        # population loop above - but at that point in this same method's
        # execution, none of the widgets _update_fusion_settings references
        # (edge_settings_widget, overlay_settings_widget, etc.) existed
        # yet, since they're constructed further down in this same method.
        # The resulting AttributeError doesn't propagate normally (PyQt
        # slot exceptions go through sys.excepthook, not the caller), so it
        # silently no-opped rather than crashing - leaving the panel
        # showing its raw construction-time widget defaults (Edge
        # Enhanced's settings visible under the placeholder title "Advanced
        # Mode Settings") instead of the correct state for whichever mode
        # is actually selected. A pre-existing bug, not one introduced by
        # the enable/disable logic above - it just happened to go
        # unnoticed because nothing about it looked obviously broken until
        # a mode-specific enabled/disabled state needed to be correct at
        # startup. Re-running it now, with every widget actually built,
        # fixes the real initial state for whatever mode ends up selected
        # (index 0 today, but not hardcoded to 'alpha_blend' in case that
        # ever changes).
        self._update_fusion_settings(self.fusion_mode_combo.currentData())

    def _on_fusion_mode_changed(self, index: int):
        """Handle mode combo change - look up the real mode string from
        itemData (the combo displays a human-readable label, e.g. "Edge
        Enhanced", not the raw "edge_enhanced" mode string itself)."""
        mode = self.fusion_mode_combo.itemData(index)
        if not mode:
            return
        self._update_fusion_settings(mode)
        self.fusion_mode_changed.emit(mode)

    # Which mode-specific settings widget (attribute name) applies to each
    # mode, and the title to show above it. Modes absent from this dict
    # fall into the "no mode-specific settings" branch below.
    _MODE_SETTINGS = {
        "edge_enhanced": ("edge_settings_widget", "Edge Enhancement Settings"),
        "thermal_contours": ("contour_settings_widget", "Thermal Contours Settings"),
        "thermal_overlay": ("overlay_settings_widget", "Thermal Overlay Settings"),
        "picture_in_picture": ("pip_settings_widget", "Picture in Picture Settings"),
        "detail_inject": ("detail_settings_widget", "Detail Injection Settings"),
        "relief_fusion": ("detail_settings_widget", "Relief Fusion Settings"),
        "laplacian_pyramid": ("laplacian_settings_widget", "Laplacian Pyramid Settings"),
    }
    _ALL_MODE_WIDGETS = (
        "edge_settings_widget", "contour_settings_widget",
        "overlay_settings_widget", "pip_settings_widget", "detail_settings_widget",
        "laplacian_settings_widget",
    )

    # Which modes actually read each General Fusion Settings control -
    # the other modes leave it disabled rather than silently ignoring it
    # with no indication why (found during the 2026-09-06 maturity review).
    _ALPHA_MODES = {"alpha_blend"}
    _PRIORITY_MODES = {
        "alpha_blend", "edge_enhanced", "thermal_overlay", "side_by_side",
        "picture_in_picture", "feature_weighted",
        "pca_fusion", "guided_filter_fusion",
    }
    _STRENGTH_MODES = {
        "detail_inject", "relief_fusion", "edge_enhanced", "thermal_overlay",
        "feature_weighted", "thermal_contours", "laplacian_pyramid",
        "pca_fusion", "guided_filter_fusion",
    }
    _FUZZINESS_MODES = {"edge_enhanced"}

    def _update_fusion_settings(self, mode: str):
        """Update visible/enabled settings based on fusion mode."""
        # Advanced Edge Options is Edge Enhanced's own detection settings
        # (shown alongside its mode-specific widget, not merged into it,
        # since it's still logically separate - Canny/Sobel detection
        # config vs. line thickness/color/consensus settings).
        self.edge_advanced_options_widget.setVisible(mode == "edge_enhanced")

        for widget_name in self._ALL_MODE_WIDGETS:
            getattr(self, widget_name).hide()

        widget_name, title = self._MODE_SETTINGS.get(mode, (None, "Advanced Settings (None)"))
        if widget_name is not None:
            getattr(self, widget_name).show()
        self.fusion_settings_group.setTitle(title)

        # Detail Injection's group has no use for Relief Fusion's own
        # emboss-direction control (Detail Injection has no emboss step),
        # so this one row toggles independently of the shared widget above.
        self.relief_light_direction_row.setVisible(mode == "relief_fusion")

        # Disable (not hide) the General Fusion Settings controls this
        # mode doesn't actually read, so their existence - and that
        # they're currently inert - stays visible instead of a silent
        # no-op when turned. setEnabled() alone isn't enough here: none
        # of this app's 9 themes define a QSlider/QComboBox :disabled
        # style (only QPushButton does), so a disabled slider rendered
        # with this app's QSS looks pixel-identical to an enabled one -
        # confirmed live, the whole reason a user couldn't tell these
        # controls were inert in the first place. A QGraphicsOpacityEffect
        # dims the widget at the paint-compositing level, which no QSS
        # rule can override, so it works the same regardless of theme.
        for enabled, widget, label in (
            (mode in self._ALPHA_MODES, self.alpha_slider, self.alpha_label),
            (mode in self._PRIORITY_MODES, self.priority_combo, self.priority_label),
            (mode in self._STRENGTH_MODES, self.fusion_strength_slider, self.strength_label),
            (mode in self._FUZZINESS_MODES, self.fusion_fuzziness_slider, self.fuzz_label),
        ):
            widget.setEnabled(enabled)
            label.setEnabled(enabled)
            self._set_dimmed(widget, not enabled)
            self._set_dimmed(label, not enabled)

    @staticmethod
    def _set_dimmed(widget: QWidget, dimmed: bool) -> None:
        """Apply/clear a theme-independent visual dim - see the caller's own comment for why setEnabled() alone isn't enough."""
        if dimmed:
            effect = QGraphicsOpacityEffect(widget)
            effect.setOpacity(0.35)
            widget.setGraphicsEffect(effect)
        else:
            widget.setGraphicsEffect(None)
