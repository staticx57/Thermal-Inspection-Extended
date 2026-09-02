"""
Parallax Compensation Control Panel

GUI panel for configuring and controlling parallax correction between
thermal and RGB cameras.
"""
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
                             QLabel, QPushButton, QDoubleSpinBox, QCheckBox,
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

        # Apply button
        self.apply_geometry_btn = QPushButton("Apply Geometry")
        self.apply_geometry_btn.setToolTip("Apply camera geometry changes")
        self.apply_geometry_btn.setEnabled(False)
        geometry_layout.addWidget(self.apply_geometry_btn)

        geometry_group.setLayout(geometry_layout)
        layout.addWidget(geometry_group)

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
            "DepthAnything (Best)"
        ])
        self.depth_method_combo.setCurrentIndex(0)
        self.depth_method_combo.setToolTip(
            "Simplified: Fast geometric heuristics (no ML)\n"
            "MiDaS: Deep learning model (moderate accuracy)\n"
            "DepthAnything: Latest model (best accuracy, slowest)"
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
        self.show_displacement_checkbox.setToolTip("Visualize pixel displacement (debug)")
        self.show_displacement_checkbox.setEnabled(False)
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

        # Enable/disable controls
        self.apply_geometry_btn.setEnabled(enabled)
        self.show_depth_checkbox.setEnabled(enabled)
        self.show_displacement_checkbox.setEnabled(enabled)

        # Emit signal
        self.parallax_toggled.emit(enabled)

    def _on_baseline_changed(self, value: float):
        """Handle baseline spinbox change — emit signal live."""
        self.baseline_changed.emit(value)

    def _on_method_changed(self, index: int):
        """Handle depth method change."""
        method_map = {
            0: "simplified",
            1: "midas",
            2: "depthanything"
        }
        method = method_map.get(index, "simplified")
        self.depth_method_changed.emit(method)

    def _on_show_depth_changed(self, state: int):
        """Handle show depth map checkbox change."""
        enabled = (state == Qt.CheckState.Checked.value)
        self.show_depth_map_toggled.emit(enabled)

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

    def get_depth_method(self) -> str:
        """
        Get selected depth estimation method.

        Returns:
            "simplified", "midas", or "depthanything"
        """
        index = self.depth_method_combo.currentIndex()
        method_map = {0: "simplified", 1: "midas", 2: "depthanything"}
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
