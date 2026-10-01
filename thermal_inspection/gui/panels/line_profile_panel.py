"""
Line Profile Panel UI
Phase 3 - Feature 10: Interactive line profile visualization

UI for drawing lines and viewing temperature profiles.
"""

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                              QPushButton, QListWidget, QListWidgetItem,
                              QGroupBox, QCheckBox, QSpinBox)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor
from thermal_inspection.processing.line_profile_tool import LineProfileAnalyzer
import logging

try:
    import pyqtgraph as pg
    HAS_PYQTGRAPH = True
except ImportError:
    HAS_PYQTGRAPH = False

logger = logging.getLogger(__name__)


class LineProfilePanel(QWidget):
    """Panel for line profile tool."""

    # Signals
    line_mode_toggled = pyqtSignal(bool)  # Enable/disable line drawing mode
    line_deleted = pyqtSignal(str)        # Emit line_id when deleted
    clear_all_requested = pyqtSignal()    # Request to clear all lines
    export_requested = pyqtSignal(str)    # Emit line_id to export

    def __init__(self, parent=None):
        super().__init__(parent)
        self.analyzer = LineProfileAnalyzer(num_samples=100)
        self._setup_ui()

    def _setup_ui(self):
        """Build the panel UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(8)

        # Title
        title = QLabel("Line Profile Tool")
        title.setStyleSheet("font-weight: bold; font-size: 13px;")
        layout.addWidget(title)

        # Enable line drawing mode
        self.enable_cb = QCheckBox("Enable Line Drawing Mode")
        self.enable_cb.setToolTip("Click to draw lines on thermal image")
        self.enable_cb.toggled.connect(self._on_mode_toggled)
        layout.addWidget(self.enable_cb)

        # Instructions
        instructions = QLabel("Click and drag to draw a line.\nRelease to analyze temperature profile.")
        instructions.setStyleSheet("color: #888888; font-size: 10px;")
        instructions.setWordWrap(True)
        layout.addWidget(instructions)

        # Line list
        list_group = QGroupBox("Active Lines")
        list_layout = QVBoxLayout(list_group)

        self.line_list = QListWidget()
        self.line_list.setMaximumHeight(120)
        self.line_list.itemSelectionChanged.connect(self._on_line_selected)
        list_layout.addWidget(self.line_list)

        # Line controls
        btn_layout = QHBoxLayout()

        self.delete_btn = QPushButton("Delete")
        self.delete_btn.clicked.connect(self._on_delete_clicked)
        self.delete_btn.setEnabled(False)
        btn_layout.addWidget(self.delete_btn)

        self.clear_btn = QPushButton("Clear All")
        self.clear_btn.clicked.connect(self._on_clear_clicked)
        btn_layout.addWidget(self.clear_btn)

        self.export_btn = QPushButton("Export CSV")
        self.export_btn.clicked.connect(self._on_export_clicked)
        self.export_btn.setEnabled(False)
        btn_layout.addWidget(self.export_btn)

        list_layout.addLayout(btn_layout)
        layout.addWidget(list_group)

        # Settings
        settings_group = QGroupBox("Settings")
        settings_layout = QHBoxLayout(settings_group)

        settings_layout.addWidget(QLabel("Sample Points:"))
        self.samples_spin = QSpinBox()
        self.samples_spin.setRange(10, 500)
        self.samples_spin.setValue(100)
        self.samples_spin.setSuffix(" pts")
        self.samples_spin.setToolTip("Number of temperature samples along line")
        self.samples_spin.valueChanged.connect(self._on_samples_changed)
        settings_layout.addWidget(self.samples_spin)

        settings_layout.addStretch()
        layout.addWidget(settings_group)

        # Plot area
        if HAS_PYQTGRAPH:
            self.plot = pg.PlotWidget(background='k')
            self.plot.setTitle("Temperature Profile", color='w', size='11pt')
            self.plot.setLabel('left', 'Temperature', units=self.analyzer.unit_label)
            self.plot.setLabel('bottom', 'Distance', units='px')
            self.plot.showGrid(x=True, y=True, alpha=0.3)
            self.plot.addLegend(offset=(10, 10))
            layout.addWidget(self.plot)

            self.plot_curves = {}  # line_id -> PlotDataItem
        else:
            no_plot_label = QLabel("PyQtGraph not installed.\nInstall to view profiles:\npip install pyqtgraph")
            no_plot_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(no_plot_label)
            self.plot = None

        # Statistics
        stats_group = QGroupBox("Selected Line Statistics")
        stats_layout = QVBoxLayout(stats_group)

        self.stats_label = QLabel("No line selected")
        self.stats_label.setWordWrap(True)
        stats_layout.addWidget(self.stats_label)

        layout.addWidget(stats_group)

    def _on_mode_toggled(self, checked: bool):
        """Handle line drawing mode toggle."""
        logger.info(f"Line drawing mode: {checked}")
        self.line_mode_toggled.emit(checked)

    def _on_line_selected(self):
        """Handle line selection."""
        has_selection = len(self.line_list.selectedItems()) > 0
        self.delete_btn.setEnabled(has_selection)
        self.export_btn.setEnabled(has_selection)

        if has_selection:
            item = self.line_list.selectedItems()[0]
            line_id = item.data(Qt.ItemDataRole.UserRole)
            profile = self.analyzer.get_profile(line_id)

            if profile:
                unit = self.analyzer.unit_label
                # Update statistics
                stats_text = (
                    f"<b>{profile.label}</b><br>"
                    f"Length: {profile.length:.1f} pixels<br>"
                    f"Min: {profile.min_temp:.1f} {unit}<br>"
                    f"Max: {profile.max_temp:.1f} {unit}<br>"
                    f"Avg: {profile.avg_temp:.1f} {unit}<br>"
                    f"StdDev: {profile.std_temp:.1f} {unit}<br>"
                    f"Points: {profile.num_points}"
                )
                self.stats_label.setText(stats_text)

                # Highlight curve in plot
                self._highlight_curve(line_id)
        else:
            self.stats_label.setText("No line selected")

    def _on_delete_clicked(self):
        """Delete selected line."""
        items = self.line_list.selectedItems()
        if not items:
            return

        item = items[0]
        line_id = item.data(Qt.ItemDataRole.UserRole)

        if self.analyzer.remove_line(line_id):
            self._update_line_list()
            self._update_plot()
            self.line_deleted.emit(line_id)

    def _on_clear_clicked(self):
        """Clear all lines."""
        self.analyzer.clear_all()
        self._update_line_list()
        self._update_plot()
        self.clear_all_requested.emit()

    def _on_export_clicked(self):
        """Export selected line to CSV."""
        items = self.line_list.selectedItems()
        if not items:
            return

        item = items[0]
        line_id = item.data(Qt.ItemDataRole.UserRole)
        self.export_requested.emit(line_id)

    def _on_samples_changed(self, value: int):
        """Handle sample count change."""
        self.analyzer.set_num_samples(value)
        logger.debug(f"Line profile samples set to {value}")

    def add_line(self, start: tuple, end: tuple, temp_map, label: str = None) -> str:
        """Add a new line profile.

        Args:
            start: Starting point (x, y)
            end: Ending point (x, y)
            temp_map: Temperature map in Celsius
            label: Optional line label

        Returns:
            line_id: Unique line identifier
        """
        line_id = self.analyzer.add_line(start, end, temp_map, label)
        self._update_line_list()
        self._update_plot()
        return line_id

    def set_unit_label(self, label: str):
        """Set the unit shown for profile values ('°C', '°F', 'K', 'Y16' or 'AGC')."""
        if label == self.analyzer.unit_label:
            return
        self.analyzer.unit_label = label
        if HAS_PYQTGRAPH and self.plot is not None:
            self.plot.setLabel('left', 'Value' if label in ('AGC', 'Y16') else 'Temperature', units=label)
        self._on_line_selected()

    def export_line(self, line_id: str, filepath: str):
        """Export one line's profile to CSV."""
        self.analyzer.export_profile_csv(line_id, filepath)

    def update_lines(self, temp_map):
        """Update all line profiles with new temperature data.

        Args:
            temp_map: Updated temperature map in Celsius
        """
        for profile in self.analyzer.get_all_profiles():
            self.analyzer.update_line(profile.line_id, temp_map)
        self._update_plot()

    def _update_line_list(self):
        """Update the line list widget."""
        self.line_list.clear()

        for profile in self.analyzer.get_all_profiles():
            display_text = f"{profile.label} ({profile.length:.0f}px)"
            item = QListWidgetItem(display_text)
            item.setData(Qt.ItemDataRole.UserRole, profile.line_id)

            # Set color
            color = QColor(*profile.color)
            item.setForeground(color)

            self.line_list.addItem(item)

    def _update_plot(self):
        """Update the temperature profile plot."""
        if not HAS_PYQTGRAPH or self.plot is None:
            return

        self.plot.clear()
        self.plot_curves.clear()

        # Plot all profiles
        for profile in self.analyzer.get_all_profiles():
            # Convert RGB to format PyQtGraph expects
            color = profile.color
            pen = pg.mkPen(color=color, width=2)

            curve = self.plot.plot(
                profile.distances,
                profile.temperatures,
                pen=pen,
                name=profile.label
            )

            self.plot_curves[profile.line_id] = curve

        # Auto-range
        if len(self.analyzer.profiles) > 0:
            self.plot.autoRange()

    def _highlight_curve(self, line_id: str):
        """Highlight a specific curve in the plot.

        Args:
            line_id: Line identifier to highlight
        """
        if not HAS_PYQTGRAPH or line_id not in self.plot_curves:
            return

        # Reset all curves to normal width
        for lid, curve in self.plot_curves.items():
            profile = self.analyzer.get_profile(lid)
            if profile:
                width = 3 if lid == line_id else 2
                pen = pg.mkPen(color=profile.color, width=width)
                curve.setPen(pen)

    def get_analyzer(self) -> LineProfileAnalyzer:
        """Get the line profile analyzer instance."""
        return self.analyzer

    def is_line_mode_enabled(self) -> bool:
        """Check if line drawing mode is enabled."""
        return self.enable_cb.isChecked()

    def clear(self):
        """Clear all lines and reset."""
        self.analyzer.clear_all()
        self._update_line_list()
        self._update_plot()
        self.stats_label.setText("No line selected")
