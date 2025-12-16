"""
Temperature Histogram Widget
Phase 2 - Feature 9: Temperature distribution visualization

Displays histogram of temperature values for ROIs or entire thermal image.
"""

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QCheckBox, QComboBox, QGroupBox
from PyQt6.QtCore import Qt
import numpy as np
import logging

try:
    import pyqtgraph as pg
    HAS_PYQTGRAPH = True
except ImportError:
    HAS_PYQTGRAPH = False

logger = logging.getLogger(__name__)


class TemperatureHistogramWidget(QWidget):
    """Widget for displaying temperature histogram."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        """Build the widget UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)

        # Title
        title = QLabel("Temperature Distribution")
        title.setStyleSheet("font-weight: bold; font-size: 12px;")
        layout.addWidget(title)

        if not HAS_PYQTGRAPH:
            label = QLabel("PyQtGraph not installed.\nInstall to view histogram:\npip install pyqtgraph")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(label)
            self.plot = None
            return

        # Controls
        controls_group = QGroupBox("Options")
        controls_layout = QHBoxLayout(controls_group)

        # Bin count
        controls_layout.addWidget(QLabel("Bins:"))
        self.bin_combo = QComboBox()
        self.bin_combo.addItems(["20", "50", "100", "200"])
        self.bin_combo.setCurrentText("50")
        self.bin_combo.currentTextChanged.connect(self._on_settings_changed)
        controls_layout.addWidget(self.bin_combo)

        # Auto-range
        self.autorange_cb = QCheckBox("Auto Range")
        self.autorange_cb.setChecked(True)
        self.autorange_cb.toggled.connect(self._on_settings_changed)
        controls_layout.addWidget(self.autorange_cb)

        controls_layout.addStretch()
        layout.addWidget(controls_group)

        # Plot widget
        self.plot = pg.PlotWidget(background='k')
        self.plot.setTitle("Temperature Histogram", color='w', size='10pt')
        self.plot.setLabel('left', 'Count', units='pixels')
        self.plot.setLabel('bottom', 'Temperature', units='°C')
        self.plot.showGrid(x=True, y=True, alpha=0.3)

        layout.addWidget(self.plot)

        # Stats labels
        stats_layout = QHBoxLayout()

        self.min_label = QLabel("Min: --")
        self.max_label = QLabel("Max: --")
        self.mean_label = QLabel("Mean: --")
        self.std_label = QLabel("StdDev: --")

        stats_layout.addWidget(self.min_label)
        stats_layout.addWidget(self.max_label)
        stats_layout.addWidget(self.mean_label)
        stats_layout.addWidget(self.std_label)
        stats_layout.addStretch()

        layout.addLayout(stats_layout)

        # Current histogram data
        self.current_temps = None
        self.histogram_item = None

    def _on_settings_changed(self):
        """Handle settings change - recompute histogram."""
        if self.current_temps is not None:
            self.update_histogram(self.current_temps)

    def update_histogram(self, temperatures: np.ndarray):
        """Update histogram with new temperature data.

        Args:
            temperatures: 1D array of temperature values in Celsius
        """
        if not HAS_PYQTGRAPH or self.plot is None:
            return

        if temperatures is None or len(temperatures) == 0:
            self.clear()
            return

        # Store for recomputation
        self.current_temps = temperatures

        # Compute statistics
        temp_min = np.min(temperatures)
        temp_max = np.max(temperatures)
        temp_mean = np.mean(temperatures)
        temp_std = np.std(temperatures)

        # Update labels
        self.min_label.setText(f"Min: {temp_min:.1f}°C")
        self.max_label.setText(f"Max: {temp_max:.1f}°C")
        self.mean_label.setText(f"Mean: {temp_mean:.1f}°C")
        self.std_label.setText(f"StdDev: {temp_std:.1f}°C")

        # Compute histogram
        bins = int(self.bin_combo.currentText())
        counts, edges = np.histogram(temperatures, bins=bins)

        # Create bar graph
        self.plot.clear()

        # Calculate bar width
        width = (edges[1] - edges[0]) * 0.8

        # Create bargraph item
        bargraph = pg.BarGraphItem(
            x=edges[:-1] + (edges[1] - edges[0]) / 2,  # Center of bins
            height=counts,
            width=width,
            brush='y',
            pen='w'
        )

        self.plot.addItem(bargraph)

        # Auto-range if enabled
        if self.autorange_cb.isChecked():
            self.plot.autoRange()

        logger.debug(f"Histogram updated: {len(temperatures)} pixels, "
                    f"range={temp_min:.1f}-{temp_max:.1f}°C, "
                    f"bins={bins}")

    def update_from_roi_stats(self, roi_stats: dict):
        """Update histogram from ROI statistics dictionary.

        Args:
            roi_stats: Dictionary with 'histogram' key containing temperature array
        """
        if 'histogram' in roi_stats:
            self.update_histogram(roi_stats['histogram'])
        elif 'temp_array' in roi_stats:
            self.update_histogram(roi_stats['temp_array'])

    def clear(self):
        """Clear the histogram."""
        if HAS_PYQTGRAPH and self.plot:
            self.plot.clear()

        self.min_label.setText("Min: --")
        self.max_label.setText("Max: --")
        self.mean_label.setText("Mean: --")
        self.std_label.setText("StdDev: --")
        self.current_temps = None

    def set_temperature_range(self, min_temp: float, max_temp: float):
        """Manually set temperature range for histogram.

        Args:
            min_temp: Minimum temperature in Celsius
            max_temp: Maximum temperature in Celsius
        """
        if HAS_PYQTGRAPH and self.plot:
            self.plot.setXRange(min_temp, max_temp)
            self.autorange_cb.setChecked(False)
