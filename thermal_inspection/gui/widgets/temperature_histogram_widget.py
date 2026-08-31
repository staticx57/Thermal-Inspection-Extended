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
        self.temp_unit = 'C'  # Default: Celsius
        self.current_palette_lut = None  # Store palette LUT for coloring
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

        # Plot widget - ensure it has sufficient size
        self.plot = pg.PlotWidget(background='k')
        self.plot.setTitle("Temperature Histogram", color='w', size='10pt')
        self.plot.setLabel('left', 'Count', units='pixels')
        self.plot.setLabel('bottom', 'Temperature', units='°C')
        self.plot.showGrid(x=True, y=True, alpha=0.3)
        self.plot.setMinimumHeight(80)  # Ensure plot has minimum height

        # Add plot with stretch to give it priority in layout
        layout.addWidget(self.plot, stretch=1)

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

    def set_temperature_unit(self, unit: str):
        """Set the temperature unit for display.

        Args:
            unit: 'C' for Celsius, 'F' for Fahrenheit, 'K' for Kelvin, 'RAW' for raw values
        """
        self.temp_unit = unit
        # Update axis label
        if HAS_PYQTGRAPH and self.plot:
            unit_labels = {
                'C': '°C', 'F': '°F', 'K': 'K', 'RAW': '(raw)'
            }
            self.plot.setLabel('bottom', 'Temperature', units=unit_labels.get(unit, '°C'))

        # Refresh if we have data
        if self.current_temps is not None:
            self.update_histogram(self.current_temps)

    def set_palette_lut(self, lut: np.ndarray):
        """Set the palette LUT for coloring histogram bars.

        Args:
            lut: 256x3 numpy array of RGB colors
        """
        self.current_palette_lut = lut
        # Refresh if we have data
        if self.current_temps is not None:
            self.update_histogram(self.current_temps)

    def _get_unit_symbol(self) -> str:
        """Get the unit symbol string."""
        symbols = {'C': '°C', 'F': '°F', 'K': 'K', 'RAW': ''}
        return symbols.get(self.temp_unit, '°C')

    def _on_settings_changed(self):
        """Handle settings change - recompute histogram."""
        if self.current_temps is not None:
            self._do_update_histogram(self.current_temps)

    def update_histogram(self, temperatures: np.ndarray):
        """Update histogram with new temperature data (throttled).

        Args:
            temperatures: 1D array of temperature values
        """
        import time

        # Throttle updates to max 5 per second for performance
        current_time = time.time()
        if hasattr(self, '_last_update_time'):
            if current_time - self._last_update_time < 0.2:  # 200ms minimum
                return
        self._last_update_time = current_time

        self._do_update_histogram(temperatures)

    def _do_update_histogram(self, temperatures: np.ndarray):
        """Actually update the histogram (unthrottled)."""
        if not HAS_PYQTGRAPH or self.plot is None:
            return

        if temperatures is None or len(temperatures) == 0:
            self.clear()
            return

        # Store for recomputation
        self.current_temps = temperatures

        # Compute statistics
        temp_min = float(np.min(temperatures))
        temp_max = float(np.max(temperatures))
        temp_mean = float(np.mean(temperatures))
        temp_std = float(np.std(temperatures))

        # Get unit symbol
        unit = self._get_unit_symbol()

        # Update labels with correct unit
        self.min_label.setText(f"Min: {temp_min:.1f}{unit}")
        self.max_label.setText(f"Max: {temp_max:.1f}{unit}")
        self.mean_label.setText(f"Mean: {temp_mean:.1f}{unit}")
        self.std_label.setText(f"StdDev: {temp_std:.1f}{unit}")

        # Compute histogram
        bins = int(self.bin_combo.currentText())
        counts, edges = np.histogram(temperatures, bins=bins)

        # Clear previous items
        self.plot.clear()

        # Choose brush color based on palette or fallback to orange
        if self.current_palette_lut is not None and len(self.current_palette_lut) >= 256:
            mid_color = self.current_palette_lut[128]
            # BGR to RGB conversion
            brush_color = (int(mid_color[2]), int(mid_color[1]), int(mid_color[0]))
        else:
            brush_color = (255, 165, 0)  # Orange fallback

        # Use PlotCurveItem with stepMode for reliable histogram rendering
        # This works better than BarGraphItem in many PyQtGraph versions
        curve = pg.PlotCurveItem(
            x=edges,
            y=np.append(counts, 0),  # Append 0 to match edge count
            stepMode='left',
            fillLevel=0,
            brush=pg.mkBrush(*brush_color, 180),  # Semi-transparent
            pen=pg.mkPen('w', width=1)
        )
        self.plot.addItem(curve)

        # Log for debugging
        max_count = int(max(counts)) if len(counts) > 0 else 0
        logger.info(f"Histogram: range={temp_min:.1f}-{temp_max:.1f}, bins={bins}, max_count={max_count}")

        # Auto-range if enabled
        if self.autorange_cb.isChecked():
            self.plot.autoRange()

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
            min_temp: Minimum temperature
            max_temp: Maximum temperature
        """
        if HAS_PYQTGRAPH and self.plot:
            self.plot.setXRange(min_temp, max_temp)
            self.autorange_cb.setChecked(False)

