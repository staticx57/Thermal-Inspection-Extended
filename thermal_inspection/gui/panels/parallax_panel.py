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
from thermal_inspection.gui.themes import set_role

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
    geometry_optics_changed = pyqtSignal(dict)  # thermal/rgb focal_length_mm + sensor_width_mm
    correction_target_changed = pyqtSignal(str)  # "thermal" or "rgb"
    rgb_target_max_width_changed = pyqtSignal(object)  # int px, or None for uncapped

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
        set_role(self.status_label, "warn-strong")
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
        set_role(info_label, "hint")
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
        set_role(target_info, "hint")
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

        # RGB target's working resolution - warping at full native RGB
        # resolution is the whole point of this mode, but that cost scales
        # with RGB's resolution, and even a "modest" 720p RGB source can
        # be more than modest hardware can sustain every frame. Defaults
        # to a real cap (640px), not best-case, for exactly that reason.
        cap_row = QHBoxLayout()
        cap_row.setContentsMargins(0, 0, 0, 0)
        cap_row.addWidget(QLabel("RGB Working Width:"))
        self.rgb_target_cap_spin = QSpinBox()
        self.rgb_target_cap_spin.setRange(160, 3840)
        self.rgb_target_cap_spin.setValue(640)
        self.rgb_target_cap_spin.setSingleStep(80)
        self.rgb_target_cap_spin.setSuffix(" px")
        self.rgb_target_cap_spin.setToolTip(
            "Only applies when Correct=RGB. Caps how large a resolution the RGB "
            "warp actually processes at (result is resized back to native "
            "resolution) - lower this if RGB-target correction is too slow for "
            "your hardware, at the cost of some fine detail/precision."
        )
        self.rgb_target_cap_spin.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.rgb_target_cap_spin.valueChanged.connect(self._on_rgb_target_cap_changed)
        cap_row.addWidget(self.rgb_target_cap_spin)
        target_layout.addLayout(cap_row)

        self.rgb_target_no_cap_checkbox = QCheckBox("No cap (full native resolution)")
        self.rgb_target_no_cap_checkbox.setToolTip(
            "Warp at RGB's full native resolution, uncapped - best quality, but "
            "the most CPU-expensive option."
        )
        self.rgb_target_no_cap_checkbox.toggled.connect(self._on_rgb_target_no_cap_toggled)
        target_layout.addWidget(self.rgb_target_no_cap_checkbox)

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
        set_role(optics_note, "hint")
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
        set_role(self.fov_display_label, "hint")
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
        self.geometry_group = geometry_group      # hosted on the Alignment tab's Rig page
        self._update_fov_display()

        # ====================================================================
        # Depth Estimation Configuration
        # ====================================================================
        # Placed before Manual/Auto Alignment below (not after, as it used
        # to be) - "Refine using depth estimation" in the Auto-Detect group
        # references this method selection, so it should be defined before
        # it's referenced, not scrolled past afterward.
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
        set_role(self.method_status_label, "ok")
        depth_layout.addWidget(self.method_status_label)

        depth_group.setLayout(depth_layout)
        layout.addWidget(depth_group)

        # ====================================================================
        # Manual Alignment
        # ====================================================================

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
        set_role(self.depth_time_label, "small")
        metrics_layout.addWidget(self.depth_time_label)

        self.correction_time_label = QLabel("Correction: --")
        set_role(self.correction_time_label, "small")
        metrics_layout.addWidget(self.correction_time_label)

        self.total_overhead_label = QLabel("Total overhead: --")
        set_role(self.total_overhead_label, "emph")
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
            set_role(self.status_label, "ok-strong")
        else:
            self.status_label.setText("Status: DISABLED")
            set_role(self.status_label, "warn-strong")

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

    def _on_correction_target_changed(self, index: int):
        """Handle Correction Target combo change — emit signal live."""
        target = "rgb" if index == 1 else "thermal"
        self.correction_target_changed.emit(target)

    def _on_rgb_target_cap_changed(self, value: int):
        """Handle RGB Working Width spinbox change — ignored while "No cap" is checked."""
        if not self.rgb_target_no_cap_checkbox.isChecked():
            self.rgb_target_max_width_changed.emit(value)

    def _on_rgb_target_no_cap_toggled(self, checked: bool):
        """Handle "No cap" checkbox toggle — emit signal live."""
        self.rgb_target_cap_spin.setEnabled(not checked)
        self.rgb_target_max_width_changed.emit(None if checked else self.rgb_target_cap_spin.value())

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
            set_role(self.total_overhead_label, "ok-strong")
        elif total_ms < 30.0:
            set_role(self.total_overhead_label, "warn-strong")
        else:
            set_role(self.total_overhead_label, "error-strong")

    def set_method_status(self, status: str, is_error: bool = False):
        """
        Update depth method status.

        Args:
            status: Status message
            is_error: True if this is an error message
        """
        self.method_status_label.setText(f"Status: {status}")
        if is_error:
            set_role(self.method_status_label, "error")
        else:
            set_role(self.method_status_label, "ok")

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
