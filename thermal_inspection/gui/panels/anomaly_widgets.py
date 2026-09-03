"""
Anomaly detection widgets for thermal inspection.

Contains:
- ManualThresholdWidget: Manual threshold-based anomaly detection
- AnomalyWidget: Automatic anomaly priority control
- CombinedAnomalyWidget: Combined automatic + manual modes
"""

import logging

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel,
    QPushButton, QCheckBox, QComboBox, QSpinBox, QSlider,
    QScrollArea, QFrame, QProgressBar, QTabWidget
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont

logger = logging.getLogger(__name__)


class ManualThresholdWidget(QWidget):
    """Manual threshold-based anomaly detection widget."""

    # Signals
    threshold_mode_changed = pyqtSignal(str)  # "above", "below", "between", "outside"
    min_threshold_changed = pyqtSignal(float)
    max_threshold_changed = pyqtSignal(float)
    visualization_mode_changed = pyqtSignal(str)
    use_raw_values_changed = pyqtSignal(bool)
    enabled_changed = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.enabled = False
        self._init_ui()
        self._connect_signals()

    def _init_ui(self):
        """Initialize widget UI components."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(5, 5, 5, 5)
        content_layout.setSpacing(10)

        # Enable/Disable toggle
        enable_group = QGroupBox("MANUAL THRESHOLD MODE")
        enable_layout = QVBoxLayout(enable_group)

        self.enable_toggle = QPushButton("Manual Mode: OFF")
        self.enable_toggle.setCheckable(True)
        self.enable_toggle.setMinimumHeight(35)
        self.enable_toggle.setToolTip("Enable manual threshold-based anomaly detection")
        enable_layout.addWidget(self.enable_toggle)

        content_layout.addWidget(enable_group)

        # Threshold configuration (initially hidden)
        self.config_widget = QWidget()
        config_layout = QVBoxLayout(self.config_widget)
        config_layout.setContentsMargins(0, 0, 0, 0)
        config_layout.setSpacing(10)

        # Value type selection
        value_type_group = QGroupBox("VALUE TYPE")
        value_type_layout = QHBoxLayout(value_type_group)

        self.percent_radio = QPushButton("Percentage")
        self.percent_radio.setCheckable(True)
        self.percent_radio.setChecked(True)
        self.percent_radio.setToolTip("Use percentage values (0-100%)")

        self.advanced_radio = QPushButton("Advanced (Raw)")
        self.advanced_radio.setCheckable(True)
        self.advanced_radio.setToolTip("Use raw 14-bit thermal values (0-16383)")

        value_type_layout.addWidget(self.percent_radio)
        value_type_layout.addWidget(self.advanced_radio)
        config_layout.addWidget(value_type_group)

        # Threshold mode selection
        mode_group = QGroupBox("THRESHOLD MODE")
        mode_layout = QVBoxLayout(mode_group)

        mode_label = QLabel("Detection Mode:")
        mode_layout.addWidget(mode_label)

        self.threshold_mode_combo = QComboBox()
        self.threshold_mode_combo.addItems([
            "Above Threshold",
            "Below Threshold",
            "Between Thresholds",
            "Outside Thresholds"
        ])
        self.threshold_mode_combo.setToolTip("Select how to detect anomalies")
        mode_layout.addWidget(self.threshold_mode_combo)

        config_layout.addWidget(mode_group)

        # Threshold values
        threshold_group = QGroupBox("THRESHOLD VALUES")
        threshold_layout = QVBoxLayout(threshold_group)

        # Min threshold
        min_layout = QHBoxLayout()
        min_layout.addWidget(QLabel("Min Threshold:"))
        self.min_threshold_spin = QSpinBox()
        self.min_threshold_spin.setRange(0, 100)
        self.min_threshold_spin.setValue(50)
        self.min_threshold_spin.setSuffix("%")
        self.min_threshold_spin.setToolTip("Minimum threshold percentage")
        min_layout.addWidget(self.min_threshold_spin)
        threshold_layout.addLayout(min_layout)

        # Max threshold
        max_layout = QHBoxLayout()
        max_layout.addWidget(QLabel("Max Threshold:"))
        self.max_threshold_spin = QSpinBox()
        self.max_threshold_spin.setRange(0, 100)
        self.max_threshold_spin.setValue(75)
        self.max_threshold_spin.setSuffix("%")
        self.max_threshold_spin.setToolTip("Maximum threshold percentage")
        max_layout.addWidget(self.max_threshold_spin)
        threshold_layout.addLayout(max_layout)

        self.threshold_hint = QLabel("Using percentage (0-100%)")
        self.threshold_hint.setStyleSheet("font-size: 9px; color: #888888;")
        threshold_layout.addWidget(self.threshold_hint)

        config_layout.addWidget(threshold_group)

        # Visualization mode
        viz_group = QGroupBox("VISUALIZATION")
        viz_layout = QVBoxLayout(viz_group)

        viz_label = QLabel("Display Mode:")
        viz_layout.addWidget(viz_label)

        self.viz_mode_combo = QComboBox()
        self.viz_mode_combo.addItems([
            "Grayscale Non-Anomalies",
            "Highlight Anomalies",
            "Binary Mask",
            "Gradient Overlay"
        ])
        self.viz_mode_combo.setToolTip("Choose how to visualize detected anomalies")
        viz_layout.addWidget(self.viz_mode_combo)

        config_layout.addWidget(viz_group)

        # Statistics display
        stats_group = QGroupBox("DETECTION STATISTICS")
        stats_layout = QVBoxLayout(stats_group)

        self.anomaly_percentage_label = QLabel("Anomalies: 0.0%")
        self.anomaly_percentage_label.setStyleSheet("font-size: 12px; font-weight: bold;")
        stats_layout.addWidget(self.anomaly_percentage_label)

        self.anomaly_count_label = QLabel("0 / 0 pixels")
        self.anomaly_count_label.setStyleSheet("font-size: 10px; color: #888888;")
        stats_layout.addWidget(self.anomaly_count_label)

        config_layout.addWidget(stats_group)

        content_layout.addWidget(self.config_widget)
        self.config_widget.setVisible(False)

        content_layout.addStretch()

        scroll.setWidget(content)
        main_layout.addWidget(scroll)

    def _connect_signals(self):
        """Connect internal signals."""
        self.enable_toggle.toggled.connect(self._on_enable_toggled)
        self.percent_radio.clicked.connect(lambda: self._on_value_type_changed(False))
        self.advanced_radio.clicked.connect(lambda: self._on_value_type_changed(True))
        self.threshold_mode_combo.currentTextChanged.connect(self._on_threshold_mode_changed)
        self.min_threshold_spin.valueChanged.connect(self.min_threshold_changed.emit)
        self.max_threshold_spin.valueChanged.connect(self.max_threshold_changed.emit)
        self.viz_mode_combo.currentTextChanged.connect(self._on_viz_mode_changed)

    def _on_enable_toggled(self, checked: bool):
        """Handle enable/disable toggle."""
        self.enabled = checked
        self.enable_toggle.setText(f"Manual Mode: {'ON' if checked else 'OFF'}")
        self.config_widget.setVisible(checked)
        self.enabled_changed.emit(checked)

    def _on_value_type_changed(self, use_raw: bool):
        """Handle value type radio button change."""
        self.percent_radio.setChecked(not use_raw)
        self.advanced_radio.setChecked(use_raw)

        if use_raw:
            self.min_threshold_spin.setRange(0, 16383)
            self.max_threshold_spin.setRange(0, 16383)
            self.min_threshold_spin.setSuffix("")
            self.max_threshold_spin.setSuffix("")
            self.min_threshold_spin.setValue(8000)
            self.max_threshold_spin.setValue(12000)
            self.threshold_hint.setText("Using raw values (0-16383) - Advanced mode")
        else:
            self.min_threshold_spin.setRange(0, 100)
            self.max_threshold_spin.setRange(0, 100)
            self.min_threshold_spin.setSuffix("%")
            self.max_threshold_spin.setSuffix("%")
            self.min_threshold_spin.setValue(50)
            self.max_threshold_spin.setValue(75)
            self.threshold_hint.setText("Using percentage (0-100%)")

        self.use_raw_values_changed.emit(use_raw)

    def _on_threshold_mode_changed(self, text: str):
        """Handle threshold mode combo change."""
        mode_map = {
            "Above Threshold": "above",
            "Below Threshold": "below",
            "Between Thresholds": "between",
            "Outside Thresholds": "outside"
        }
        mode = mode_map.get(text, "above")
        needs_max = mode in ["between", "outside"]
        self.max_threshold_spin.setEnabled(needs_max)
        self.threshold_mode_changed.emit(mode)

    def _on_viz_mode_changed(self, text: str):
        """Handle visualization mode combo change."""
        viz_map = {
            "Grayscale Non-Anomalies": "grayscale_non_anomaly",
            "Highlight Anomalies": "color_non_anomaly",
            "Binary Mask": "binary_mask",
            "Gradient Overlay": "gradient_overlay"
        }
        mode = viz_map.get(text, "grayscale_non_anomaly")
        self.visualization_mode_changed.emit(mode)

    def update_statistics(self, anomaly_percentage: float, anomaly_count: int, total_pixels: int):
        """Update detection statistics display."""
        self.anomaly_percentage_label.setText(f"Anomalies: {anomaly_percentage:.2f}%")
        self.anomaly_count_label.setText(f"{anomaly_count:,} / {total_pixels:,} pixels")

    def set_raw_mode_available(self, available: bool):
        """
        Enable/disable "Advanced (Raw)" mode based on whether the active
        thermal source is actually producing 16-bit radiometric frames.
        Raw-value thresholds (e.g. 8000) are compared directly against
        whatever frame reaches detect_threshold_anomalies() - against an
        8-bit AGC-processed frame (0-255, from a non-radiometric camera or
        8-bit estimation mode) they can never match, silently making
        detection permanently a no-op rather than erroring. Percentage
        mode is unaffected - it derives its actual thresholds from
        whatever min/max the current frame contains, at any bit depth.
        """
        self.advanced_radio.setEnabled(available)
        if not available and self.advanced_radio.isChecked():
            self.percent_radio.click()


class AnomalyWidget(QWidget):
    """Anomaly priority control panel widget."""

    # Signals
    anomaly_priority_toggled = pyqtSignal(bool)
    anomaly_types_changed = pyqtSignal(dict)
    fade_strength_changed = pyqtSignal(float)
    fade_distance_changed = pyqtSignal(int)
    motion_threshold_changed = pyqtSignal(int)
    edge_thresholds_changed = pyqtSignal(int, int)
    hot_spot_percentile_changed = pyqtSignal(int)
    cold_spot_percentile_changed = pyqtSignal(int)
    min_anomaly_size_changed = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.enabled_types = {
            "motion": True,
            "edges": True,
            "hot_spots": True,
            "cold_spots": True,
            "thermal_anomalies": True,
            "enhanced_fusion": False
        }

        self.anomaly_counts = {
            "motion": 0,
            "edges": 0,
            "hot_spots": 0,
            "cold_spots": 0,
            "thermal_anomalies": 0,
            "enhanced_fusion": 0
        }

        self._init_ui()
        self._connect_signals()

    def _init_ui(self):
        """Initialize widget UI components."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(15)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget()
        self.content_layout = QVBoxLayout(content)
        self.content_layout.setSpacing(15)
        self.content_layout.setContentsMargins(5, 5, 5, 5)

        self._create_main_toggle()
        self._create_type_selector()
        self._create_gradient_controls()
        self._create_detection_settings()
        self._create_performance_display()

        self.content_layout.addStretch()

        scroll.setWidget(content)
        main_layout.addWidget(scroll)

    def _create_main_toggle(self):
        """Create main anomaly priority ON/OFF toggle."""
        toggle_group = QGroupBox("ANOMALY PRIORITY CONTROL")
        toggle_layout = QVBoxLayout(toggle_group)

        self.main_toggle = QPushButton("Anomaly Priority: OFF")
        self.main_toggle.setCheckable(True)
        self.main_toggle.setMinimumHeight(40)
        self.main_toggle.setToolTip("Enable/disable anomaly priority gradient fade")

        toggle_layout.addWidget(self.main_toggle)
        self.content_layout.addWidget(toggle_group)

    def _create_type_selector(self):
        """Create anomaly type multi-select checkboxes."""
        type_group = QGroupBox("ANOMALY TYPES")
        type_layout = QVBoxLayout(type_group)

        info_label = QLabel("Select which detections to highlight:")
        info_label.setWordWrap(True)
        type_layout.addWidget(info_label)

        self.type_checkboxes = {}
        self.type_count_labels = {}

        anomaly_type_configs = [
            ("motion", "Motion Detections", "Temporal changes between frames"),
            ("edges", "Edge Clusters", "Thermal boundary edges"),
            ("hot_spots", "Hot Spots", "95th percentile temperature"),
            ("cold_spots", "Cold Spots", "5th percentile temperature"),
            ("thermal_anomalies", "Thermal Anomalies", "Statistical outliers"),
            ("enhanced_fusion", "Enhanced Thermal+Edge Fusion", "Intelligent combination")
        ]

        for key, label, tooltip in anomaly_type_configs:
            row_layout = QHBoxLayout()

            checkbox = QCheckBox(label)
            checkbox.setChecked(True)
            checkbox.setToolTip(tooltip)
            self.type_checkboxes[key] = checkbox

            count_label = QLabel("(0 found)")
            count_label.setStyleSheet("font-size: 10px;")
            self.type_count_labels[key] = count_label

            row_layout.addWidget(checkbox)
            row_layout.addWidget(count_label)
            row_layout.addStretch()

            type_layout.addLayout(row_layout)

        self.total_count_label = QLabel("Total: 0 anomalies")
        font = QFont()
        font.setBold(True)
        self.total_count_label.setFont(font)
        type_layout.addWidget(self.total_count_label)

        self.content_layout.addWidget(type_group)

    def _create_gradient_controls(self):
        """Create gradient fade control sliders."""
        gradient_group = QGroupBox("GRADIENT FADE")
        gradient_layout = QVBoxLayout(gradient_group)

        # Fade Strength slider
        strength_label = QLabel("Fade Strength:")
        gradient_layout.addWidget(strength_label)

        strength_row = QHBoxLayout()
        self.fade_strength_slider = QSlider(Qt.Orientation.Horizontal)
        self.fade_strength_slider.setMinimum(5)
        self.fade_strength_slider.setMaximum(20)
        self.fade_strength_slider.setValue(10)
        self.fade_strength_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.fade_strength_slider.setTickInterval(5)
        self.fade_strength_slider.setToolTip("Controls gradient steepness (0.5 soft - 2.0 sharp)")

        self.fade_strength_value = QLabel("1.0")
        self.fade_strength_value.setMinimumWidth(35)

        strength_row.addWidget(self.fade_strength_slider)
        strength_row.addWidget(self.fade_strength_value)
        gradient_layout.addLayout(strength_row)

        # Fade Distance slider
        distance_label = QLabel("Fade Distance:")
        gradient_layout.addWidget(distance_label)

        distance_row = QHBoxLayout()
        self.fade_distance_slider = QSlider(Qt.Orientation.Horizontal)
        self.fade_distance_slider.setMinimum(50)
        self.fade_distance_slider.setMaximum(200)
        self.fade_distance_slider.setValue(100)
        self.fade_distance_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.fade_distance_slider.setTickInterval(50)
        self.fade_distance_slider.setToolTip("Maximum distance for gradient fade (pixels)")

        self.fade_distance_value = QLabel("100px")
        self.fade_distance_value.setMinimumWidth(50)

        distance_row.addWidget(self.fade_distance_slider)
        distance_row.addWidget(self.fade_distance_value)
        gradient_layout.addLayout(distance_row)

        self.content_layout.addWidget(gradient_group)

    def _create_detection_settings(self):
        """Create collapsible detection settings section."""
        self.detection_group = QGroupBox("DETECTION SETTINGS")
        detection_layout = QVBoxLayout(self.detection_group)

        self.detection_expand_btn = QPushButton("Expand Settings")
        self.detection_expand_btn.setCheckable(True)
        self.detection_expand_btn.setMaximumHeight(28)
        detection_layout.addWidget(self.detection_expand_btn)

        self.detection_content = QWidget()
        self.detection_content.setVisible(False)
        settings_layout = QVBoxLayout(self.detection_content)
        settings_layout.setContentsMargins(0, 0, 0, 0)

        # Motion Threshold
        motion_layout = QHBoxLayout()
        motion_layout.addWidget(QLabel("Motion Threshold:"))
        self.motion_threshold_spin = QSpinBox()
        self.motion_threshold_spin.setRange(5, 50)
        self.motion_threshold_spin.setValue(20)
        motion_layout.addWidget(self.motion_threshold_spin)
        settings_layout.addLayout(motion_layout)

        # Edge Thresholds
        edge_low_layout = QHBoxLayout()
        edge_low_layout.addWidget(QLabel("Edge Low:"))
        self.edge_low_spin = QSpinBox()
        self.edge_low_spin.setRange(10, 100)
        self.edge_low_spin.setValue(50)
        edge_low_layout.addWidget(self.edge_low_spin)
        settings_layout.addLayout(edge_low_layout)

        edge_high_layout = QHBoxLayout()
        edge_high_layout.addWidget(QLabel("Edge High:"))
        self.edge_high_spin = QSpinBox()
        self.edge_high_spin.setRange(50, 200)
        self.edge_high_spin.setValue(150)
        edge_high_layout.addWidget(self.edge_high_spin)
        settings_layout.addLayout(edge_high_layout)

        # Hot Spot Percentile
        hot_layout = QHBoxLayout()
        hot_layout.addWidget(QLabel("Hot Spot %ile:"))
        self.hot_spot_spin = QSpinBox()
        self.hot_spot_spin.setRange(85, 99)
        self.hot_spot_spin.setValue(95)
        hot_layout.addWidget(self.hot_spot_spin)
        settings_layout.addLayout(hot_layout)

        # Cold Spot Percentile
        cold_layout = QHBoxLayout()
        cold_layout.addWidget(QLabel("Cold Spot %ile:"))
        self.cold_spot_spin = QSpinBox()
        self.cold_spot_spin.setRange(1, 15)
        self.cold_spot_spin.setValue(5)
        cold_layout.addWidget(self.cold_spot_spin)
        settings_layout.addLayout(cold_layout)

        # Min Anomaly Size
        size_layout = QHBoxLayout()
        size_layout.addWidget(QLabel("Min Size (px):"))
        self.min_size_spin = QSpinBox()
        self.min_size_spin.setRange(100, 2000)
        self.min_size_spin.setValue(400)
        self.min_size_spin.setSingleStep(100)
        size_layout.addWidget(self.min_size_spin)
        settings_layout.addLayout(size_layout)

        detection_layout.addWidget(self.detection_content)
        self.content_layout.addWidget(self.detection_group)

    def _create_performance_display(self):
        """Create performance metrics display."""
        perf_group = QGroupBox("PERFORMANCE")
        perf_layout = QVBoxLayout(perf_group)

        self.fps_label = QLabel("FPS: --")
        self.processing_time_label = QLabel("Processing: --")
        self.overhead_label = QLabel("Overhead: --")

        self.overhead_bar = QProgressBar()
        self.overhead_bar.setRange(0, 100)
        self.overhead_bar.setValue(0)
        self.overhead_bar.setTextVisible(True)
        self.overhead_bar.setFormat("%p%")
        self.overhead_bar.setMaximumHeight(20)

        perf_layout.addWidget(self.fps_label)
        perf_layout.addWidget(self.processing_time_label)
        perf_layout.addWidget(self.overhead_label)
        perf_layout.addWidget(self.overhead_bar)

        self.content_layout.addWidget(perf_group)

    def _connect_signals(self):
        """Connect internal widget signals."""
        self.main_toggle.toggled.connect(self._on_main_toggle_changed)

        for key, checkbox in self.type_checkboxes.items():
            checkbox.stateChanged.connect(self._on_type_checkbox_changed)

        self.fade_strength_slider.valueChanged.connect(self._on_fade_strength_changed)
        self.fade_distance_slider.valueChanged.connect(self._on_fade_distance_changed)
        self.detection_expand_btn.toggled.connect(self._on_detection_expand_toggled)
        self.motion_threshold_spin.valueChanged.connect(self.motion_threshold_changed.emit)
        self.edge_low_spin.valueChanged.connect(self._on_edge_thresholds_changed)
        self.edge_high_spin.valueChanged.connect(self._on_edge_thresholds_changed)
        self.hot_spot_spin.valueChanged.connect(self.hot_spot_percentile_changed.emit)
        self.cold_spot_spin.valueChanged.connect(self.cold_spot_percentile_changed.emit)
        self.min_size_spin.valueChanged.connect(self.min_anomaly_size_changed.emit)

    def _on_main_toggle_changed(self, checked: bool):
        """Handle main toggle state change."""
        self.main_toggle.setText(f"Anomaly Priority: {'ON' if checked else 'OFF'}")
        self.anomaly_priority_toggled.emit(checked)

    def _on_type_checkbox_changed(self):
        """Handle anomaly type checkbox changes."""
        for key, checkbox in self.type_checkboxes.items():
            self.enabled_types[key] = checkbox.isChecked()
        self.anomaly_types_changed.emit(self.enabled_types)
        self._update_total_count()

    def _on_fade_strength_changed(self, value: int):
        """Handle fade strength slider change."""
        strength = value / 10.0
        self.fade_strength_value.setText(f"{strength:.1f}")
        self.fade_strength_changed.emit(strength)

    def _on_fade_distance_changed(self, value: int):
        """Handle fade distance slider change."""
        self.fade_distance_value.setText(f"{value}px")
        self.fade_distance_changed.emit(value)

    def _on_detection_expand_toggled(self, expanded: bool):
        """Handle detection settings expand/collapse."""
        self.detection_content.setVisible(expanded)
        self.detection_expand_btn.setText("Collapse Settings" if expanded else "Expand Settings")

    def _on_edge_thresholds_changed(self):
        """Handle edge threshold changes."""
        low = self.edge_low_spin.value()
        high = self.edge_high_spin.value()
        self.edge_thresholds_changed.emit(low, high)

    def update_counts(self, counts: dict):
        """Update live anomaly counts."""
        for key, count in counts.items():
            if key in self.anomaly_counts:
                self.anomaly_counts[key] = count
                if key in self.type_count_labels:
                    self.type_count_labels[key].setText(f"({count} found)")
        self._update_total_count()

    def _update_total_count(self):
        """Update total anomaly count display."""
        total = sum(
            self.anomaly_counts[key]
            for key in self.enabled_types
            if self.enabled_types[key]
        )
        self.total_count_label.setText(f"Total: {total} anomalies")

    def update_performance(self, fps: float, processing_time: float, overhead: float = 0.0):
        """Update performance metrics."""
        self.fps_label.setText(f"FPS: {fps:.1f}")
        self.processing_time_label.setText(f"Processing: {processing_time:.1f}ms")
        self.overhead_label.setText(f"Overhead: {overhead:.1f}%")
        self.overhead_bar.setValue(int(overhead))

        if overhead < 10:
            color = "#4CAF50"
        elif overhead < 20:
            color = "#FFC107"
        else:
            color = "#F44336"

        self.overhead_bar.setStyleSheet(f"QProgressBar::chunk {{ background-color: {color}; }}")

    def set_anomaly_priority_enabled(self, enabled: bool):
        """Programmatically set anomaly priority state."""
        self.main_toggle.setChecked(enabled)


class CombinedAnomalyWidget(QWidget):
    """
    Combined anomaly detection widget with automatic and manual modes.
    Uses tabs to switch between automatic (image analysis) and manual (threshold) modes.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self):
        """Initialize widget UI components."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.mode_tabs = QTabWidget()
        self.mode_tabs.setDocumentMode(False)

        self.automatic_widget = AnomalyWidget()
        self.mode_tabs.addTab(self.automatic_widget, "Automatic")

        self.manual_widget = ManualThresholdWidget()
        self.mode_tabs.addTab(self.manual_widget, "Manual")

        main_layout.addWidget(self.mode_tabs)
