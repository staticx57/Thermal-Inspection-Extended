"""
Parallax Compensation Control Panel

GUI panel for configuring and controlling parallax correction between
thermal and RGB cameras.
"""
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
                             QLabel, QPushButton, QDoubleSpinBox, QSpinBox, QCheckBox,
                             QComboBox, QScrollArea, QFrame)
from PyQt6.QtCore import Qt, pyqtSignal
import logging

logger = logging.getLogger(__name__)


class ParallaxPanel(QWidget):
    """
    GUI panel for parallax compensation control.

    Features:
    - Enable/disable toggle
    - Baseline distance configuration
    - Depth estimation method selection
    - Visualization options
    - Status display
    """

    # Signals
    parallax_toggled = pyqtSignal(bool)
    baseline_changed = pyqtSignal(float)
    depth_method_changed = pyqtSignal(str)
    show_depth_map_toggled = pyqtSignal(bool)
    show_displacement_toggled = pyqtSignal(bool)
    shift_changed = pyqtSignal(int, int)  # (dx, dy) pixels
    auto_alignment_requested = pyqtSignal(float, bool)  # working_distance_m, refine_with_depth
    zoom_changed = pyqtSignal(float)  # crop-in zoom factor, 1.0 = none
    geometry_optics_changed = pyqtSignal(dict)  # thermal/rgb focal_length_mm + sensor_width_mm
    correction_target_changed = pyqtSignal(str)  # "thermal" or "rgb"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()

    def init_ui(self):
        """Initialize the user interface."""
        from PyQt6.QtWidgets import QSizePolicy

        # Outer layout — zero margins so the scroll area fills the whole panel
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        # Zero margins on the scroll viewport itself — eliminates the offset
        # layer that causes hit-rects to diverge from visual positions.
        scroll.setContentsMargins(0, 0, 0, 0)

        content = QWidget()
        # Fixed vertical policy: the content grows as its children demand but
        # never contracts below that — keeps Qt's geometry calculation stable.
        content.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Fixed,
        )

        layout = QVBoxLayout(content)
        layout.setSpacing(8)
        layout.setContentsMargins(8, 8, 8, 8)

        # ====================================================================
        # Status and Enable/Disable
        # ====================================================================
        status_group = QGroupBox("Parallax Compensation")
        status_layout = QVBoxLayout()
        status_layout.setSpacing(6)
        status_layout.setContentsMargins(8, 8, 8, 8)

        # Status label
        self.status_label = QLabel("Status: DISABLED")
        self.status_label.setStyleSheet("color: #ffaa00; font-weight: bold;")
        status_layout.addWidget(self.status_label)

        # Enable/disable toggle
        self.enable_checkbox = QCheckBox("Enable Parallax Correction")
        self.enable_checkbox.setToolTip(
            "Enable depth-based parallax correction for better thermal-RGB alignment.\n"
            "WARNING: Adds computational overhead. Disable for maximum performance."
        )
        self.enable_checkbox.setChecked(False)  # DISABLED BY DEFAULT
        self.enable_checkbox.stateChanged.connect(self._on_enable_changed)
        status_layout.addWidget(self.enable_checkbox)

        # Info text
        info_label = QLabel(
            "Parallax occurs when thermal and RGB cameras are separated.\n"
            "This correction uses depth estimation to align the views."
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: #888888; font-size: 9pt;")
        status_layout.addWidget(info_label)

        status_group.setLayout(status_layout)
        layout.addWidget(status_group)

        # ====================================================================
        # Correction Target
        # ====================================================================
        # Which frame actually gets warped/cropped to align with the other.
        # RGB is generally the better choice: every RGB source this app
        # supports has substantially more native resolution than the
        # thermal side, so RGB's spare pixels absorb the crop/warp loss -
        # and thermal pixel values are real radiometric measurements, not
        # just cosmetic appearance, so leaving thermal untouched means
        # spot meter/isotherm/calibration/anomaly detection all read the
        # sensor's actual per-pixel measurement instead of a bilinear
        # blend of neighboring readings.
        target_group = QGroupBox("Correction Target")
        target_layout = QVBoxLayout()
        target_layout.setSpacing(6)
        target_layout.setContentsMargins(8, 8, 8, 8)

        target_info = QLabel(
            "Which camera's view gets warped/cropped to align with the other.\n"
            "RGB usually preserves more real detail (more native pixels to\n"
            "spare) and keeps thermal's temperature data completely raw."
        )
        target_info.setWordWrap(True)
        target_info.setStyleSheet("color: #888888; font-size: 9pt;")
        target_layout.addWidget(target_info)

        target_row = QHBoxLayout()
        target_row.setContentsMargins(0, 0, 0, 0)
        target_row.addWidget(QLabel("Correct:"))
        self.correction_target_combo = QComboBox()
        self.correction_target_combo.addItems(["Thermal (legacy)", "RGB (recommended)"])
        self.correction_target_combo.setCurrentIndex(0)
        self.correction_target_combo.setToolTip(
            "Thermal: this module's original behavior - warps the (lower-resolution) "
            "thermal frame to match RGB.\n"
            "RGB: warps the (higher-resolution) RGB frame to match thermal instead - "
            "preserves more detail and keeps thermal's radiometric data completely raw, "
            "but costs more CPU per frame (RGB is usually much larger) and its "
            "alignment direction hasn't been confirmed against real hardware yet."
        )
        self.correction_target_combo.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.correction_target_combo.currentIndexChanged.connect(self._on_correction_target_changed)
        target_row.addWidget(self.correction_target_combo)
        target_layout.addLayout(target_row)

        target_group.setLayout(target_layout)
        layout.addWidget(target_group)

        # ====================================================================
        # Camera Geometry Configuration
        # ====================================================================
        geometry_group = QGroupBox("Camera Geometry")
        geometry_layout = QVBoxLayout()
        geometry_layout.setSpacing(6)
        geometry_layout.setContentsMargins(8, 8, 8, 8)

        # Baseline distance
        baseline_layout = QHBoxLayout()
        baseline_layout.setContentsMargins(0, 0, 0, 0)
        baseline_layout.addWidget(QLabel("Baseline:"))
        self.baseline_spin = QDoubleSpinBox()
        self.baseline_spin.setRange(10.0, 200.0)
        self.baseline_spin.setValue(50.0)
        self.baseline_spin.setDecimals(1)
        self.baseline_spin.setSuffix(" mm")
        self.baseline_spin.setSingleStep(5.0)
        self.baseline_spin.setToolTip("Distance between thermal and RGB camera centers")
        self.baseline_spin.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.baseline_spin.valueChanged.connect(self._on_baseline_changed)
        baseline_layout.addWidget(self.baseline_spin)
        geometry_layout.addLayout(baseline_layout)

        # Per-camera lens optics - drive both the disparity calculation
        # (needs thermal focal length in pixels) and the FOV crop-zoom
        # factor (needs both cameras' FOV, from focal length + sensor
        # width). Defaults match a FLIR Boson 9mm lens / a typical Firefly
        # C-mount lens - editable here since actual hardware varies (Boson
        # ships with 6.3/7.5/9/13/19/24/35/50/100mm lens options, and RGB
        # lenses are often swappable third-party glass with no way for this
        # app to read their specs from the camera SDK).
        optics_note = QLabel(
            "Lens specs (from your camera/lens datasheet) - needed for FOV "
            "crop-zoom and geometric auto-alignment to be accurate:"
        )
        optics_note.setWordWrap(True)
        optics_note.setStyleSheet("color: #888888; font-size: 9pt;")
        geometry_layout.addWidget(optics_note)

        def _make_optics_row(label_text, default_val, tooltip):
            row = QHBoxLayout()
            row.setContentsMargins(0, 0, 0, 0)
            row.addWidget(QLabel(label_text))
            spin = QDoubleSpinBox()
            spin.setRange(0.5, 200.0)
            spin.setValue(default_val)
            spin.setDecimals(2)
            spin.setSuffix(" mm")
            spin.setSingleStep(0.5)
            spin.setToolTip(tooltip)
            spin.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
            row.addWidget(spin)
            geometry_layout.addLayout(row)
            return spin

        self.thermal_focal_spin = _make_optics_row(
            "Thermal Focal Length:", 9.0, "Thermal camera lens focal length (mm)")
        self.thermal_sensor_width_spin = _make_optics_row(
            "Thermal Sensor Width:", 10.88, "Thermal sensor physical width (mm)")
        self.rgb_focal_spin = _make_optics_row(
            "RGB Focal Length:", 6.0, "RGB camera lens focal length (mm)")
        self.rgb_sensor_width_spin = _make_optics_row(
            "RGB Sensor Width:", 6.784, "RGB sensor physical width (mm)")

        self.fov_display_label = QLabel("")
        self.fov_display_label.setStyleSheet("color: #888888; font-size: 9pt;")
        self.fov_display_label.setWordWrap(True)
        geometry_layout.addWidget(self.fov_display_label)

        for spin in (self.thermal_focal_spin, self.thermal_sensor_width_spin,
                     self.rgb_focal_spin, self.rgb_sensor_width_spin):
            spin.valueChanged.connect(self._update_fov_display)

        # Apply button
        self.apply_geometry_btn = QPushButton("Apply Geometry")
        self.apply_geometry_btn.setToolTip("Apply camera geometry changes")
        self.apply_geometry_btn.setEnabled(True)
        geometry_layout.addWidget(self.apply_geometry_btn)

        geometry_group.setLayout(geometry_layout)
        layout.addWidget(geometry_group)
        self._update_fov_display()

        # ====================================================================
        # Manual Alignment Shift
        # ====================================================================
        # A fixed mounting offset between the two cameras doesn't vary with
        # distance, so depth-based correction (which only handles the X-axis
        # baseline disparity) can't and shouldn't try to correct for it -
        # this is a plain constant translation, independent of and additive
        # to whatever depth-based correction does. Works even when
        # depth-based correction (above) is disabled.
        shift_group = QGroupBox("Manual Alignment Shift")
        shift_layout = QVBoxLayout()
        shift_layout.setSpacing(6)
        shift_layout.setContentsMargins(8, 8, 8, 8)

        shift_info_label = QLabel(
            "Fine-tune registration with a constant pixel shift - useful for\n"
            "a fixed mounting offset that doesn't change with distance."
        )
        shift_info_label.setWordWrap(True)
        shift_info_label.setStyleSheet("color: #888888; font-size: 9pt;")
        shift_layout.addWidget(shift_info_label)

        shift_x_layout = QHBoxLayout()
        shift_x_layout.setContentsMargins(0, 0, 0, 0)
        shift_x_layout.addWidget(QLabel("Horizontal:"))
        self.shift_x_spin = QSpinBox()
        self.shift_x_spin.setRange(-200, 200)
        self.shift_x_spin.setValue(0)
        self.shift_x_spin.setSuffix(" px")
        self.shift_x_spin.setToolTip("Positive shifts the thermal image right")
        self.shift_x_spin.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.shift_x_spin.valueChanged.connect(self._on_shift_changed)
        shift_x_layout.addWidget(self.shift_x_spin)
        shift_layout.addLayout(shift_x_layout)

        shift_y_layout = QHBoxLayout()
        shift_y_layout.setContentsMargins(0, 0, 0, 0)
        shift_y_layout.addWidget(QLabel("Vertical:"))
        self.shift_y_spin = QSpinBox()
        self.shift_y_spin.setRange(-200, 200)
        self.shift_y_spin.setValue(0)
        self.shift_y_spin.setSuffix(" px")
        self.shift_y_spin.setToolTip("Positive shifts the thermal image down")
        self.shift_y_spin.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.shift_y_spin.valueChanged.connect(self._on_shift_changed)
        shift_y_layout.addWidget(self.shift_y_spin)
        shift_layout.addLayout(shift_y_layout)

        self.reset_shift_btn = QPushButton("Reset Shift")
        self.reset_shift_btn.setToolTip("Reset horizontal/vertical shift to 0")
        self.reset_shift_btn.clicked.connect(self._on_reset_shift)
        shift_layout.addWidget(self.reset_shift_btn)

        # Manual zoom / crop factor - the same crop-and-resize mechanism
        # Auto-Calculate Alignment uses to correct a real FOV mismatch
        # (fov_zoom_factor), but directly user-settable for cases the
        # geometric calculation can't cover on its own: correcting for
        # inaccurate/unknown lens specs by eye, or a deliberate manual
        # crop-in. 1.0 = no crop; higher crops in (zooms) further.
        zoom_layout = QHBoxLayout()
        zoom_layout.setContentsMargins(0, 0, 0, 0)
        zoom_layout.addWidget(QLabel("Zoom / Crop-In:"))
        self.zoom_spin = QDoubleSpinBox()
        self.zoom_spin.setRange(1.0, 3.0)
        self.zoom_spin.setValue(1.0)
        self.zoom_spin.setDecimals(3)
        self.zoom_spin.setSuffix("x")
        self.zoom_spin.setSingleStep(0.01)
        self.zoom_spin.setToolTip(
            "Manually crop the thermal frame in and rescale to fill - for "
            "correcting FOV mismatch by eye, independent of the geometry "
            "fields above. 1.0 = no crop."
        )
        self.zoom_spin.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.zoom_spin.valueChanged.connect(self._on_zoom_changed)
        zoom_layout.addWidget(self.zoom_spin)
        shift_layout.addLayout(zoom_layout)

        self.reset_zoom_btn = QPushButton("Reset Zoom")
        self.reset_zoom_btn.setToolTip("Reset zoom/crop factor to 1.0x (no crop)")
        self.reset_zoom_btn.clicked.connect(lambda: self.zoom_spin.setValue(1.0))
        shift_layout.addWidget(self.reset_zoom_btn)

        # ----------------------------------------------------------------
        # Auto-Calculate Alignment - a one-time calculation from camera
        # baseline + FOV difference (not a per-frame process), optionally
        # refined by a single depth-estimation call. Sets the shift/zoom
        # above rather than replacing them - the manual controls stay
        # available for further fine-tuning afterward.
        # ----------------------------------------------------------------
        auto_align_label = QLabel(
            "Or auto-calculate from camera geometry (baseline + FOV) -\n"
            "runs once, not every frame:"
        )
        auto_align_label.setWordWrap(True)
        auto_align_label.setStyleSheet("color: #888888; font-size: 9pt;")
        shift_layout.addWidget(auto_align_label)

        distance_layout = QHBoxLayout()
        distance_layout.setContentsMargins(0, 0, 0, 0)
        distance_layout.addWidget(QLabel("Working Distance:"))
        self.working_distance_spin = QDoubleSpinBox()
        self.working_distance_spin.setRange(0.1, 20.0)
        self.working_distance_spin.setValue(2.0)
        self.working_distance_spin.setDecimals(1)
        self.working_distance_spin.setSuffix(" m")
        self.working_distance_spin.setSingleStep(0.1)
        self.working_distance_spin.setToolTip("Assumed subject distance - ignored if refined by depth estimation below")
        self.working_distance_spin.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        distance_layout.addWidget(self.working_distance_spin)
        shift_layout.addLayout(distance_layout)

        self.refine_with_depth_checkbox = QCheckBox("Refine using depth estimation")
        self.refine_with_depth_checkbox.setToolTip(
            "Run the selected depth estimation method once on the current frame "
            "to measure the actual scene distance instead of the assumed value above"
        )
        shift_layout.addWidget(self.refine_with_depth_checkbox)

        self.auto_align_btn = QPushButton("Auto-Calculate Alignment")
        self.auto_align_btn.setToolTip("Compute shift + FOV crop-zoom once from camera geometry")
        self.auto_align_btn.clicked.connect(self._on_auto_align_clicked)
        shift_layout.addWidget(self.auto_align_btn)

        self.auto_align_result_label = QLabel("")
        self.auto_align_result_label.setWordWrap(True)
        self.auto_align_result_label.setStyleSheet("color: #4CAF50; font-size: 9pt;")
        shift_layout.addWidget(self.auto_align_result_label)

        shift_group.setLayout(shift_layout)
        layout.addWidget(shift_group)

        # ====================================================================
        # Depth Estimation Configuration
        # ====================================================================
        depth_group = QGroupBox("Depth Estimation")
        depth_layout = QVBoxLayout()
        depth_layout.setSpacing(6)
        depth_layout.setContentsMargins(8, 8, 8, 8)

        # Method selection
        method_layout = QHBoxLayout()
        method_layout.setContentsMargins(0, 0, 0, 0)
        method_layout.addWidget(QLabel("Method:"))
        self.depth_method_combo = QComboBox()
        self.depth_method_combo.addItems([
            "Simplified (Fast)",
            "MiDaS (Accurate)",
            "DepthAnything (Best)",
            "Intel RealSense (Real Depth)",
        ])
        self.depth_method_combo.setCurrentIndex(0)
        self.depth_method_combo.setToolTip(
            "Simplified: Fast geometric heuristics (no ML)\n"
            "MiDaS: Deep learning model (moderate accuracy)\n"
            "DepthAnything: Latest model (best accuracy, slowest)\n"
            "Intel RealSense: Real measured depth from an active RealSense "
            "camera (most accurate - not an estimate - but requires the "
            "RealSense camera to be connected and active as the RGB source)"
        )
        self.depth_method_combo.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.depth_method_combo.currentIndexChanged.connect(self._on_method_changed)
        method_layout.addWidget(self.depth_method_combo)
        depth_layout.addLayout(method_layout)

        # Method status
        self.method_status_label = QLabel("Status: Ready")
        self.method_status_label.setStyleSheet("color: #4CAF50; font-size: 9pt;")
        depth_layout.addWidget(self.method_status_label)

        depth_group.setLayout(depth_layout)
        layout.addWidget(depth_group)

        # ====================================================================
        # Visualization Options
        # ====================================================================
        viz_group = QGroupBox("Visualization")
        viz_layout = QVBoxLayout()
        viz_layout.setSpacing(6)
        viz_layout.setContentsMargins(8, 8, 8, 8)

        # Show depth map checkbox
        self.show_depth_checkbox = QCheckBox("Show Depth Map")
        self.show_depth_checkbox.setToolTip("Overlay estimated depth map on video")
        self.show_depth_checkbox.setEnabled(False)
        self.show_depth_checkbox.stateChanged.connect(self._on_show_depth_changed)
        viz_layout.addWidget(self.show_depth_checkbox)

        # Show displacement vectors checkbox
        self.show_displacement_checkbox = QCheckBox("Show Displacement Vectors")
        self.show_displacement_checkbox.setToolTip("Overlay a sparse grid of arrows showing per-pixel shift (debug)")
        self.show_displacement_checkbox.setEnabled(False)
        self.show_displacement_checkbox.stateChanged.connect(self._on_show_displacement_changed)
        viz_layout.addWidget(self.show_displacement_checkbox)

        viz_group.setLayout(viz_layout)
        layout.addWidget(viz_group)

        # ====================================================================
        # Performance Metrics
        # ====================================================================
        metrics_group = QGroupBox("Performance")
        metrics_layout = QVBoxLayout()
        metrics_layout.setSpacing(4)
        metrics_layout.setContentsMargins(8, 8, 8, 8)

        self.depth_time_label = QLabel("Depth estimation: --")
        self.depth_time_label.setStyleSheet("font-size: 9pt;")
        metrics_layout.addWidget(self.depth_time_label)

        self.correction_time_label = QLabel("Correction: --")
        self.correction_time_label.setStyleSheet("font-size: 9pt;")
        metrics_layout.addWidget(self.correction_time_label)

        self.total_overhead_label = QLabel("Total overhead: --")
        self.total_overhead_label.setStyleSheet("font-weight: bold; font-size: 9pt;")
        metrics_layout.addWidget(self.total_overhead_label)

        metrics_group.setLayout(metrics_layout)
        layout.addWidget(metrics_group)

        # No addStretch() — with SizePolicy.Fixed the content widget already
        # stops at its natural height; a stretch would expand it needlessly and
        # re-introduce the geometry mismatch on some Qt themes.

        scroll.setWidget(content)
        outer_layout.addWidget(scroll)

    # ========================================================================
    # Signal Handlers (Internal)
    # ========================================================================

    def _on_enable_changed(self, state: int):
        """Handle enable/disable checkbox change."""
        enabled = (state == Qt.CheckState.Checked.value)

        # Update status label
        if enabled:
            self.status_label.setText("Status: ENABLED")
            self.status_label.setStyleSheet("color: #4CAF50; font-weight: bold;")
        else:
            self.status_label.setText("Status: DISABLED")
            self.status_label.setStyleSheet("color: #ffaa00; font-weight: bold;")

        # Enable/disable controls - apply_geometry_btn is deliberately NOT
        # gated on this: baseline/lens optics/zoom feed the manual-shift-
        # only and auto-alignment paths too, which work even with
        # depth-based correction (this checkbox) turned off.
        self.show_depth_checkbox.setEnabled(enabled)
        self.show_displacement_checkbox.setEnabled(enabled)

        # Emit signal
        self.parallax_toggled.emit(enabled)

    def _on_baseline_changed(self, value: float):
        """Handle baseline spinbox change — emit signal live."""
        self.baseline_changed.emit(value)

    def _update_fov_display(self):
        """Recompute and show each camera's horizontal FOV from its focal length/sensor width fields."""
        import math

        def hfov_deg(focal_mm, sensor_width_mm):
            return math.degrees(2 * math.atan2(sensor_width_mm / 2.0, focal_mm))

        thermal_fov = hfov_deg(self.thermal_focal_spin.value(), self.thermal_sensor_width_spin.value())
        rgb_fov = hfov_deg(self.rgb_focal_spin.value(), self.rgb_sensor_width_spin.value())
        self.fov_display_label.setText(
            f"Computed FOV — Thermal: {thermal_fov:.1f}°, RGB: {rgb_fov:.1f}°"
        )

    def _on_method_changed(self, index: int):
        """Handle depth method change."""
        method_map = {
            0: "simplified",
            1: "midas",
            2: "depthanything",
            3: "realsense",
        }
        method = method_map.get(index, "simplified")
        self.depth_method_changed.emit(method)

    def _on_show_depth_changed(self, state: int):
        """Handle show depth map checkbox change."""
        enabled = (state == Qt.CheckState.Checked.value)
        self.show_depth_map_toggled.emit(enabled)

    def _on_show_displacement_changed(self, state: int):
        """Handle show displacement vectors checkbox change."""
        enabled = (state == Qt.CheckState.Checked.value)
        self.show_displacement_toggled.emit(enabled)

    def _on_shift_changed(self, _value: int):
        """Handle horizontal/vertical shift spinbox change — emit combined (dx, dy)."""
        self.shift_changed.emit(self.shift_x_spin.value(), self.shift_y_spin.value())

    def _on_reset_shift(self):
        """Reset both shift spinboxes to 0 (each valueChanged emits shift_changed)."""
        self.shift_x_spin.setValue(0)
        self.shift_y_spin.setValue(0)

    def _on_zoom_changed(self, value: float):
        """Handle manual zoom/crop-factor spinbox change — emit signal live."""
        self.zoom_changed.emit(value)

    def _on_correction_target_changed(self, index: int):
        """Handle Correction Target combo change — emit signal live."""
        target = "rgb" if index == 1 else "thermal"
        self.correction_target_changed.emit(target)

    def _on_auto_align_clicked(self):
        """Request a one-time auto-alignment calculation."""
        self.auto_alignment_requested.emit(
            self.working_distance_spin.value(),
            self.refine_with_depth_checkbox.isChecked()
        )

    # ========================================================================
    # Public Methods - Called by main GUI
    # ========================================================================

    def set_parallax_status(self, enabled: bool):
        """
        Update parallax status display.

        Args:
            enabled: True if parallax correction is active
        """
        self.enable_checkbox.setChecked(enabled)

    def set_performance_metrics(self, depth_time_ms: float, correction_time_ms: float):
        """
        Update performance metrics display.

        Args:
            depth_time_ms: Depth estimation time (milliseconds)
            correction_time_ms: Correction application time (milliseconds)
        """
        total_ms = depth_time_ms + correction_time_ms

        self.depth_time_label.setText(f"Depth estimation: {depth_time_ms:.1f} ms")
        self.correction_time_label.setText(f"Correction: {correction_time_ms:.1f} ms")
        self.total_overhead_label.setText(f"Total overhead: {total_ms:.1f} ms")

        # Color-code total overhead
        if total_ms < 10.0:
            self.total_overhead_label.setStyleSheet("color: #4CAF50; font-weight: bold; font-size: 9pt;")
        elif total_ms < 30.0:
            self.total_overhead_label.setStyleSheet("color: #ffaa00; font-weight: bold; font-size: 9pt;")
        else:
            self.total_overhead_label.setStyleSheet("color: #ff4444; font-weight: bold; font-size: 9pt;")

    def set_method_status(self, status: str, is_error: bool = False):
        """
        Update depth method status.

        Args:
            status: Status message
            is_error: True if this is an error message
        """
        self.method_status_label.setText(f"Status: {status}")
        if is_error:
            self.method_status_label.setStyleSheet("color: #ff4444; font-size: 9pt;")
        else:
            self.method_status_label.setStyleSheet("color: #4CAF50; font-size: 9pt;")

    def get_baseline(self) -> float:
        """Get configured baseline distance in millimeters."""
        return self.baseline_spin.value()

    def get_correction_target(self) -> str:
        """Get which frame ("thermal" or "rgb") is set to be warped/cropped."""
        return "rgb" if self.correction_target_combo.currentIndex() == 1 else "thermal"

    def get_camera_optics(self) -> dict:
        """Get configured lens optics for both cameras (mm)."""
        return {
            'thermal_focal_length_mm': self.thermal_focal_spin.value(),
            'thermal_sensor_width_mm': self.thermal_sensor_width_spin.value(),
            'rgb_focal_length_mm': self.rgb_focal_spin.value(),
            'rgb_sensor_width_mm': self.rgb_sensor_width_spin.value(),
        }

    def get_depth_method(self) -> str:
        """
        Get selected depth estimation method.

        Returns:
            "simplified", "midas", "depthanything", or "realsense"
        """
        index = self.depth_method_combo.currentIndex()
        method_map = {0: "simplified", 1: "midas", 2: "depthanything", 3: "realsense"}
        return method_map.get(index, "simplified")

    def is_show_depth_enabled(self) -> bool:
        """Check if depth map visualization is enabled."""
        return self.show_depth_checkbox.isChecked()

    def is_show_displacement_enabled(self) -> bool:
        """Check if displacement visualization is enabled."""
        return self.show_displacement_checkbox.isChecked()

    def get_manual_shift(self) -> tuple:
        """Get the current (dx, dy) manual alignment shift in pixels."""
        return (self.shift_x_spin.value(), self.shift_y_spin.value())

    def set_auto_alignment_result(self, dx: int, dy: int, fov_zoom_factor: float):
        """
        Reflect a completed auto-alignment calculation: syncs the manual
        shift spinboxes and the Zoom/Crop-In spinbox to the computed
        values, so they show what's actually active and can be fine-tuned
        further with the same controls a user would use manually.
        """
        self.shift_x_spin.blockSignals(True)
        self.shift_y_spin.blockSignals(True)
        self.zoom_spin.blockSignals(True)
        self.shift_x_spin.setValue(dx)
        self.shift_y_spin.setValue(dy)
        self.zoom_spin.setValue(fov_zoom_factor)
        self.shift_x_spin.blockSignals(False)
        self.shift_y_spin.blockSignals(False)
        self.zoom_spin.blockSignals(False)

        zoom_note = (f", zoom {fov_zoom_factor:.3f}x"
                    if abs(fov_zoom_factor - 1.0) > 1e-3 else "")
        self.auto_align_result_label.setText(
            f"Applied: shift ({dx}, {dy})px{zoom_note}"
        )


# ============================================================================
# Standalone Test
# ============================================================================

if __name__ == "__main__":
    import sys
    from PyQt6.QtWidgets import QApplication

    app = QApplication(sys.argv)

    # Test the panel
    panel = ParallaxPanel()
    panel.setWindowTitle("Parallax Panel Test")
    panel.resize(400, 700)

    # Connect signals for testing
    panel.parallax_toggled.connect(lambda x: print(f"Parallax toggled: {x}"))
    panel.baseline_changed.connect(lambda x: print(f"Baseline changed: {x}mm"))
    panel.depth_method_changed.connect(lambda x: print(f"Method changed: {x}"))

    # Simulate performance metrics
    panel.set_performance_metrics(15.3, 2.1)

    panel.show()
    sys.exit(app.exec())
