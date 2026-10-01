"""
Radiometric Calibration Panel GUI

Interactive panel for calibrating radiometric cameras against known references.
"""

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
                             QLabel, QPushButton, QDoubleSpinBox, QTableWidget,
                             QTableWidgetItem, QHeaderView, QComboBox, QSpinBox,
                             QCheckBox, QScrollArea, QFrame)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor
import logging
from thermal_inspection.gui.themes import set_button_state

logger = logging.getLogger(__name__)


class CalibrationPanel(QWidget):
    """
    GUI panel for radiometric calibration.

    Features:
    - Add calibration points with reference temperatures
    - View calibration point table
    - Compute calibration (linear/polynomial)
    - Apply calibration to measurements
    - Import/export calibration files
    """

    # Signals
    add_point_mode_changed = pyqtSignal(bool, float)  # enabled, reference_temp
    compute_calibration_clicked = pyqtSignal(str, int)  # method, degree
    apply_calibration_toggled = pyqtSignal(bool)  # enabled
    clear_calibration_clicked = pyqtSignal()
    export_calibration_clicked = pyqtSignal()
    import_calibration_clicked = pyqtSignal()
    remove_point_clicked = pyqtSignal(int)  # index

    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()

    def init_ui(self):
        """Initialize the user interface."""
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setSpacing(8)
        layout.setContentsMargins(8, 8, 8, 8)

        # ====================================================================
        # Status Group
        # ====================================================================
        status_group = QGroupBox("Calibration Status")
        status_layout = QVBoxLayout()
        status_layout.setSpacing(6)

        self.status_label = QLabel("Not Calibrated")
        self.status_label.setStyleSheet("color: #ff4444; font-weight: bold; font-size: 11pt;")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        status_layout.addWidget(self.status_label)

        self.stats_label = QLabel("No calibration points")
        self.stats_label.setStyleSheet("color: #888888; font-size: 9pt;")
        self.stats_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        status_layout.addWidget(self.stats_label)

        status_group.setLayout(status_layout)
        layout.addWidget(status_group)

        # ====================================================================
        # Add Calibration Point
        # ====================================================================
        add_group = QGroupBox("Add Calibration Point")
        add_layout = QVBoxLayout()
        add_layout.setSpacing(6)

        # Instructions
        instructions = QLabel("1. Point camera at reference source\n2. Enter known temperature\n3. Click on thermal view")
        instructions.setWordWrap(True)
        instructions.setStyleSheet("color: #888888; font-size: 9pt;")
        add_layout.addWidget(instructions)

        # Reference temperature input
        ref_temp_layout = QHBoxLayout()
        ref_temp_layout.addWidget(QLabel("Reference Temperature:"))
        self.ref_temp_spin = QDoubleSpinBox()
        self.ref_temp_spin.setRange(-40.0, 200.0)
        self.ref_temp_spin.setValue(25.0)
        self.ref_temp_spin.setSuffix(" °C")
        self.ref_temp_spin.setDecimals(1)
        self.ref_temp_spin.setMinimumWidth(100)
        ref_temp_layout.addWidget(self.ref_temp_spin)
        ref_temp_layout.addStretch()
        add_layout.addLayout(ref_temp_layout)

        # Add point button
        self.add_point_btn = QPushButton("📍 Click Thermal View to Add Point")
        self.add_point_btn.setCheckable(True)
        self.add_point_btn.setMinimumHeight(35)
        self.add_point_btn.setToolTip("Enable click-to-add mode, then click on thermal view")
        add_layout.addWidget(self.add_point_btn)

        add_group.setLayout(add_layout)
        layout.addWidget(add_group)

        # ====================================================================
        # Calibration Points Table
        # ====================================================================
        table_group = QGroupBox("Calibration Points")
        table_layout = QVBoxLayout()
        table_layout.setSpacing(6)

        self.points_table = QTableWidget()
        self.points_table.setColumnCount(4)
        self.points_table.setHorizontalHeaderLabels(["Reference (°C)", "Measured (°C)", "Error (°C)", "Remove"])
        self.points_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.points_table.setMaximumHeight(150)
        self.points_table.setAlternatingRowColors(True)
        table_layout.addWidget(self.points_table)

        # Clear all button
        self.clear_points_btn = QPushButton("Clear All Points")
        self.clear_points_btn.setEnabled(False)
        table_layout.addWidget(self.clear_points_btn)

        table_group.setLayout(table_layout)
        layout.addWidget(table_group)

        # ====================================================================
        # Calibration Method
        # ====================================================================
        method_group = QGroupBox("Calibration Method")
        method_layout = QVBoxLayout()
        method_layout.setSpacing(6)

        # Method selection
        method_select_layout = QHBoxLayout()
        method_select_layout.addWidget(QLabel("Method:"))
        self.method_combo = QComboBox()
        self.method_combo.addItems(["Linear", "Polynomial"])
        self.method_combo.setToolTip("Linear: y = ax + b (2+ points)\nPolynomial: higher order fit (3+ points)")
        method_select_layout.addWidget(self.method_combo)
        method_select_layout.addStretch()
        method_layout.addLayout(method_select_layout)

        # Polynomial degree (only for polynomial method)
        degree_layout = QHBoxLayout()
        degree_layout.addWidget(QLabel("Polynomial Degree:"))
        self.degree_spin = QSpinBox()
        self.degree_spin.setRange(2, 5)
        self.degree_spin.setValue(2)
        self.degree_spin.setEnabled(False)
        degree_layout.addWidget(self.degree_spin)
        degree_layout.addStretch()
        method_layout.addLayout(degree_layout)

        # Compute button
        self.compute_btn = QPushButton("🔬 Compute Calibration")
        self.compute_btn.setMinimumHeight(35)
        self.compute_btn.setEnabled(False)
        method_layout.addWidget(self.compute_btn)

        method_group.setLayout(method_layout)
        layout.addWidget(method_group)

        # ====================================================================
        # Apply Calibration
        # ====================================================================
        apply_group = QGroupBox("Apply Calibration")
        apply_layout = QVBoxLayout()
        apply_layout.setSpacing(6)

        self.apply_calibration_checkbox = QCheckBox("Enable Calibration Correction")
        self.apply_calibration_checkbox.setToolTip("Apply calibration to all temperature measurements")
        self.apply_calibration_checkbox.setEnabled(False)
        apply_layout.addWidget(self.apply_calibration_checkbox)

        apply_group.setLayout(apply_layout)
        layout.addWidget(apply_group)

        # ====================================================================
        # Import/Export
        # ====================================================================
        io_group = QGroupBox("Import/Export")
        io_layout = QHBoxLayout()
        io_layout.setSpacing(6)

        self.export_btn = QPushButton("💾 Export")
        self.export_btn.setToolTip("Export calibration to JSON file")
        self.export_btn.setEnabled(False)
        io_layout.addWidget(self.export_btn)

        self.import_btn = QPushButton("📂 Import")
        self.import_btn.setToolTip("Import calibration from JSON file")
        io_layout.addWidget(self.import_btn)

        io_group.setLayout(io_layout)
        layout.addWidget(io_group)

        # Add stretch to push everything to top
        layout.addStretch()

        scroll.setWidget(content)
        outer_layout.addWidget(scroll)
        self._connect_signals()

    def _connect_signals(self):
        """Connect internal signals."""
        self.add_point_btn.toggled.connect(self._on_add_point_mode_toggled)
        self.clear_points_btn.clicked.connect(lambda: self.clear_calibration_clicked.emit())
        self.compute_btn.clicked.connect(self._on_compute_calibration)
        self.apply_calibration_checkbox.toggled.connect(self.apply_calibration_toggled.emit)
        self.export_btn.clicked.connect(lambda: self.export_calibration_clicked.emit())
        self.import_btn.clicked.connect(lambda: self.import_calibration_clicked.emit())
        self.method_combo.currentTextChanged.connect(self._on_method_changed)

    def _on_add_point_mode_toggled(self, checked: bool):
        """Handle add point mode toggle."""
        # No manual setStyleSheet() here - the button is already
        # setCheckable(True), so every theme's native QPushButton:checked
        # style already highlights it; a manual override on top both
        # duplicated that and discarded the theme's border-radius/padding.
        if checked:
            self.add_point_btn.setText("🎯 Click Thermal View (Active)")
        else:
            self.add_point_btn.setText("📍 Click Thermal View to Add Point")
        # Emitted on both directions (not just enabling) so the backend and
        # the video overlay's click routing (set_calibration_add_point_mode)
        # actually turn off when the user manually unchecks this button -
        # previously only the ON transition emitted anything at all.
        self.add_point_mode_changed.emit(checked, self.ref_temp_spin.value())

    def _on_compute_calibration(self):
        """Handle compute calibration button click."""
        method = self.method_combo.currentText().lower()
        degree = self.degree_spin.value() if method == "polynomial" else 2
        self.compute_calibration_clicked.emit(method, degree)

    def _on_method_changed(self, text: str):
        """Handle calibration method change."""
        self.degree_spin.setEnabled(text == "Polynomial")

    def update_calibration_points(self, points: list):
        """
        Update calibration points table.

        Args:
            points: List of CalibrationPoint objects
        """
        self.points_table.setRowCount(len(points))

        for i, point in enumerate(points):
            # Reference temperature
            ref_item = QTableWidgetItem(f"{point.reference_temp:.1f}")
            ref_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.points_table.setItem(i, 0, ref_item)

            # Measured temperature
            meas_item = QTableWidgetItem(f"{point.measured_temp:.1f}")
            meas_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.points_table.setItem(i, 1, meas_item)

            # Error
            error_item = QTableWidgetItem(f"{point.error:.2f}")
            error_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            # Color code error
            if abs(point.error) > 2.0:
                error_item.setForeground(QColor(255, 100, 100))
            elif abs(point.error) > 1.0:
                error_item.setForeground(QColor(255, 200, 100))
            else:
                error_item.setForeground(QColor(100, 255, 100))
            self.points_table.setItem(i, 2, error_item)

            # Remove button
            remove_btn = QPushButton("✕")
            remove_btn.setMaximumWidth(30)
            set_button_state(remove_btn, "compact", True)
            remove_btn.clicked.connect(lambda checked, idx=i: self.remove_point_clicked.emit(idx))
            self.points_table.setCellWidget(i, 3, remove_btn)

        # Enable/disable buttons
        has_points = len(points) > 0
        self.clear_points_btn.setEnabled(has_points)
        self.compute_btn.setEnabled(len(points) >= 2)

    def set_calibration_status(self, is_calibrated: bool, stats: dict = None):
        """
        Update calibration status display.

        Args:
            is_calibrated: True if calibration is computed
            stats: Dictionary with calibration statistics
        """
        if is_calibrated and stats:
            self.status_label.setText("✓ Calibrated")
            self.status_label.setStyleSheet("color: #4CAF50; font-weight: bold; font-size: 11pt;")

            stats_text = f"Points: {stats.get('point_count', 0)} | "
            stats_text += f"Method: {stats.get('method', 'unknown').capitalize()} | "
            stats_text += f"RMSE: {stats.get('rmse', 0):.2f}°C"
            self.stats_label.setText(stats_text)

            self.apply_calibration_checkbox.setEnabled(True)
            self.export_btn.setEnabled(True)
        else:
            self.status_label.setText("Not Calibrated")
            self.status_label.setStyleSheet("color: #ff4444; font-weight: bold; font-size: 11pt;")

            point_count = stats.get('point_count', 0) if stats else 0
            if point_count > 0:
                self.stats_label.setText(f"{point_count} point(s) added - click Compute")
            else:
                self.stats_label.setText("No calibration points")

            self.apply_calibration_checkbox.setEnabled(False)
            self.apply_calibration_checkbox.setChecked(False)
            self.export_btn.setEnabled(False)

    def is_add_point_mode(self) -> bool:
        """Check if add point mode is active."""
        return self.add_point_btn.isChecked()

    def get_reference_temperature(self) -> float:
        """Get current reference temperature."""
        return self.ref_temp_spin.value()

    def disable_add_point_mode(self):
        """Disable add point mode."""
        self.add_point_btn.setChecked(False)


# ============================================================================
# Standalone Test
# ============================================================================

if __name__ == "__main__":
    import sys
    from PyQt6.QtWidgets import QApplication

    app = QApplication(sys.argv)

    # Test the panel
    panel = CalibrationPanel()
    panel.setWindowTitle("Calibration Panel Test")
    panel.resize(400, 700)
    panel.show()

    # Simulate some calibration points
    from radiometric_calibration import CalibrationPoint
    test_points = [
        CalibrationPoint(20.0, 22.5, 100, 100),
        CalibrationPoint(30.0, 32.3, 110, 100),
        CalibrationPoint(40.0, 42.1, 120, 100),
    ]
    panel.update_calibration_points(test_points)

    # Simulate calibrated status
    stats = {
        'point_count': 3,
        'method': 'linear',
        'rmse': 1.23
    }
    panel.set_calibration_status(True, stats)

    sys.exit(app.exec())
