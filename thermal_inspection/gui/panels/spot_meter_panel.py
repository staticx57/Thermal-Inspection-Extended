#!/usr/bin/env python3
"""
Spot Meter Management Panel
Provides UI for viewing and managing all active spot meters.

Part of Enhancement #12: Spot Meter Management and Data Export
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QGroupBox, QMenu, QInputDialog,
    QMessageBox, QFrame, QAbstractItemView, QFileDialog, QComboBox,
    QCheckBox, QDialog, QDoubleSpinBox,
    QScrollArea, QSizePolicy, QRadioButton, QDialogButtonBox, QApplication
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QIcon, QPixmap, QBrush
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
import logging
import time
import statistics  # Phase 2 - Feature 6: Multi-point Statistics
from thermal_inspection.processing.spot_tracking import RATE_TYPES, convert_delta, rate_per_minute
from thermal_inspection.gui.widgets.empty_hint import HintListWidget, HintTableWidget
try:
    import pyqtgraph as pg
    HAS_PYQTGRAPH = True
except ImportError:
    HAS_PYQTGRAPH = False

logger = logging.getLogger(__name__)


@dataclass
class SpotMeterAlert:
    """Alert configuration for a spot meter (Phase 2 - Feature 7: Enhanced)."""
    threshold: float
    type: str = 'above'  # 'above' or 'below'
    unit: str = '°C'  # Unit symbol the threshold was entered in
    enabled: bool = True
    triggered: bool = False
    sound_enabled: bool = True  # Phase 2 - Feature 7: Sound alerts
    flash_enabled: bool = True  # Phase 2 - Feature 7: Visual flashing
    trigger_count: int = 0  # Phase 2 - Feature 7: How many times triggered
    last_trigger_time: float = 0.0  # Phase 2 - Feature 7: Last trigger timestamp
    trigger_history: List[float] = field(default_factory=list)  # Phase 2 - Feature 7: Trigger timestamps

    def check(self, value: float, unit: Optional[str] = None, history=None) -> bool:
        """Check if alert should trigger. `history` ([(timestamp, reading)] in the spot's display unit) is only needed
        for the rate-of-change types ('rising_fast' / 'falling_fast': degrees per MINUTE, threshold in self.unit).

        value is in `unit` (the reading's display unit). The threshold was
        entered in self.unit, which may differ if the user switched units
        since - convert the reading to the threshold's unit first so a 50 degC
        alert doesn't compare against 29815 (Y16) or 122 (degF).
        """
        if not self.enabled:
            return False

        if self.type in RATE_TYPES:
            return self._check_rate(history, unit)

        if unit is not None:
            from thermal_inspection.utils.temperature_units import convert
            converted = convert(value, unit, self.unit)
            if converted is not None:
                value = converted

        is_triggered = False
        if self.type == 'above':
            is_triggered = value > self.threshold
        elif self.type == 'below':
            is_triggered = value < self.threshold

        # Track trigger state changes (Phase 2 - Feature 7)
        if is_triggered and not self.triggered:
            # Alert just triggered
            self.trigger_count += 1
            self.last_trigger_time = time.time()
            self.trigger_history.append(self.last_trigger_time)
            # Keep only last 100 triggers
            if len(self.trigger_history) > 100:
                self.trigger_history = self.trigger_history[-100:]

        self.triggered = is_triggered
        return is_triggered


    def _check_rate(self, history, unit: Optional[str]) -> bool:
        rate = rate_per_minute(history or [])
        hit = False
        if rate is not None:
            if unit is not None and unit != self.unit:
                rate = convert_delta(rate, unit, self.unit)       # a rate converts by scale only; None = raw counts
            if rate is not None:
                hit = rate > self.threshold if self.type == "rising_fast" else -rate > self.threshold
        if hit and not self.triggered:
            self.trigger_count += 1
            self.last_trigger_time = time.time()
            self.trigger_history.append(self.last_trigger_time)
            self.trigger_history = self.trigger_history[-100:]
        self.triggered = hit
        return hit

    def describe(self) -> str:
        if self.type in RATE_TYPES:
            return f"{'rises' if self.type == 'rising_fast' else 'falls'} faster than {self.threshold:g} {self.unit}/min"
        return f"{'above' if self.type == 'above' else 'below'} {self.threshold:g} {self.unit}"


class TemperatureHistoryGraph(QWidget):
    """Real-time temperature history graph for selected spot meters."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)

        if not HAS_PYQTGRAPH:
            self.label = QLabel("PyQtGraph not installed.\nInstall to view history.")
            self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.layout.addWidget(self.label)
            self.plot = None
            return

        # Configure PlotWidget
        self.plot = pg.PlotWidget(background='k')
        self.plot.setTitle("Temperature History", color='w', size='10pt')
        self.plot.setLabel('left', 'Temp', units='C')
        self.plot.setLabel('bottom', 'Time', units='s')
        self.plot.showGrid(x=True, y=True, alpha=0.3)
        self.plot.addLegend(offset=(10, 10))

        self.layout.addWidget(self.plot)
        self.curves = {}  # spot_id -> PlotDataItem

    def update_data(self, selected_spots: List['SpotMeterData']):
        """Update graph with data from selected spots."""
        if not self.plot:
            return

        current_ids = {s.id for s in selected_spots}
        existing_ids = set(self.curves.keys())

        # Remove curves for deselected spots
        for spot_id in existing_ids - current_ids:
            if spot_id in self.curves: # Check existence defensively
                self.plot.removeItem(self.curves[spot_id])
                del self.curves[spot_id]

        if not selected_spots:
            return

        # Determine unit from first selected spot
        unit = selected_spots[0].unit
        if "AGC" in unit:
             self.plot.setLabel('left', 'Raw Value', units='AGC')
        else:
             self.plot.setLabel('left', 'Temperature', units=unit.replace("°",""))

        # Update or add curves
        for spot in selected_spots:
            if not spot.history:
                continue

            times, temps = zip(*spot.history)
            # Normalize time to relative (0 = start of history)
            start_t = times[0]
            rel_times = [t - start_t for t in times]

            # DEBUG: Check if we have variation
            if len(temps) > 10:
                logger.debug(f"Spot {spot.label} history (last 5): {temps[-5:]} | Range: {min(temps)} - {max(temps)}")

            spot_color = spot.color # (r, g, b)

            if spot.id not in self.curves:
                # Create new curve
                pen = pg.mkPen(color=spot_color, width=2)
                curve = self.plot.plot(rel_times, temps, pen=pen, name=spot.label)
                self.curves[spot.id] = curve
            else:
                # Update existing curve
                self.curves[spot.id].setData(rel_times, temps)
                # Update color/name if changed (optional optimization: check first)
                pen = pg.mkPen(color=spot_color, width=2)
                self.curves[spot.id].setPen(pen)



@dataclass
class SpotMeterData:
    """Extended spot meter data for management panel."""
    id: str                              # Unique identifier
    label: str                           # Display name
    x: int                               # Frame X coordinate
    y: int                               # Frame Y coordinate
    temperature: Optional[float] = None  # Current temperature
    unit: str = "°C"                     # Temperature unit
    distance_m: Optional[float] = None   # Real depth-camera distance to this point, meters; None if no RealSense
    color: Tuple[int, int, int] = (255, 255, 0)  # Marker color (BGR)
    visible: bool = True                 # Visibility toggle
    locked: bool = False                 # Position lock
    created_at: float = 0.0              # Creation timestamp
    updated_at: float = 0.0              # Last temperature update
    history: List[Tuple[float, float]] = field(default_factory=list)  # (timestamp, temp) history
    alert: Optional[SpotMeterAlert] = None # Alert configuration
    peak: Optional[float] = None         # Hottest reading since placed / last reset (peak hold), in `unit`
    trough: Optional[float] = None       # Coldest reading since placed / last reset

    def __post_init__(self):
        if self.created_at == 0.0:
            self.created_at = time.time()

    def add_history(self, temperature: float):
        """Add a temperature reading to history (keeps last 1000)."""
        if temperature is None:
            return

        # Optional: Filter obvious outliers if needed (e.g. <-200C)
        # For now, just ensure it's a number
        try:
            val = float(temperature)
        except (ValueError, TypeError):
            return

        self.history.append((time.time(), val))
        if len(self.history) > 1000:
            self.history.pop(0)

    def record_extremes(self, temperature: float):
        """Update the peak-hold / trough values with a new reading."""
        if temperature is None:
            return
        self.peak = temperature if self.peak is None else max(self.peak, temperature)
        self.trough = temperature if self.trough is None else min(self.trough, temperature)

    def reset_peak(self):
        """Forget the held peak/trough (they restart from the next reading)."""
        self.peak = self.trough = None

    def convert_unit(self, new_unit: str):
        """Re-express history, peak and trough in a new display unit so switching degC/degF/K keeps the graph and the
        held peak; if the units can't be converted (raw counts) start over rather than mix scales."""
        from thermal_inspection.utils.temperature_units import convert
        if convert(0.0, self.unit, new_unit) is None:
            self.history.clear()
            self.reset_peak()
        else:
            self.history = [(t, convert(v, self.unit, new_unit)) for t, v in self.history]
            self.peak = None if self.peak is None else convert(self.peak, self.unit, new_unit)
            self.trough = None if self.trough is None else convert(self.trough, self.unit, new_unit)
        self.unit = new_unit

    def get_trend(self) -> str:
        """Calculate temperature trend based on recent history.

        Returns:
            'rising', 'falling', or 'stable'
        """
        if len(self.history) < 5:
            return "stable"

        # Compare last 5 readings average vs previous 5
        recent = [t for _, t in self.history[-5:]]
        previous = [t for _, t in self.history[-10:-5]] if len(self.history) >= 10 else recent

        recent_avg = sum(recent) / len(recent)
        previous_avg = sum(previous) / len(previous)

        diff = recent_avg - previous_avg

        if diff > 0.5:
            return "rising"
        elif diff < -0.5:
            return "falling"
        else:
            return "stable"


class SpotMeterPresets:
    """Generates coordinate patterns for spot meters."""

    @staticmethod
    def get_presets() -> List[str]:
        return ["Grid 3x3", "Center + Corners", "Horizontal Line", "Vertical Line", "Crosshair"]

    @staticmethod
    def generate(preset: str, w: int, h: int) -> List[Tuple[int, int]]:
        """Generate (x, y) coordinates for a preset."""
        coords = []
        margin_x = w // 10
        margin_y = h // 10

        if preset == "Grid 3x3":
            step_x = (w - 2*margin_x) // 2
            step_y = (h - 2*margin_y) // 2
            for i in range(3):
                for j in range(3):
                    coords.append((margin_x + i*step_x, margin_y + j*step_y))

        elif preset == "Center + Corners":
            cx, cy = w // 2, h // 2
            coords = [
                (cx, cy),
                (margin_x, margin_y), (w - margin_x, margin_y),
                (margin_x, h - margin_y), (w - margin_x, h - margin_y)
            ]

        elif preset == "Horizontal Line":
            y = h // 2
            step = (w - 2*margin_x) // 4
            for i in range(5):
                coords.append((margin_x + i*step, y))

        elif preset == "Vertical Line":
            x = w // 2
            step = (h - 2*margin_y) // 4
            for i in range(5):
                coords.append((x, margin_y + i*step))

        elif preset == "Crosshair":
            cx, cy = w // 2, h // 2
            step_x = w // 8
            step_y = h // 8
            coords = [
                (cx, cy),
                (cx - step_x, cy), (cx + step_x, cy),
                (cx, cy - step_y), (cx, cy + step_y)
            ]

        return coords


class SpotMeterListItem(QListWidgetItem):
    """Custom list item for spot meter display."""

    def __init__(self, spot_data: SpotMeterData):
        super().__init__()
        self.spot_data = spot_data
        self.update_display()

    def update_display(self):
        """Update the list item text and appearance."""
        data = self.spot_data

        # Format temperature
        if data.temperature is not None:
            temp_str = f"{data.temperature:.1f}{data.unit}"
        else:
            temp_str = "--"

        # Format indicators
        indicators = ""
        if not data.visible:
            indicators += "🙈 "  # Hidden indicator
        if data.locked:
            indicators += "🔒 "  # Locked indicator

        # Trend arrow
        trend = data.get_trend()
        trend_icon = {"rising": " ↑", "falling": " ↓", "stable": ""}.get(trend, "")

        # Distance (real depth-camera reading, RealSense only - resize-only
        # approximation, not parallax-shift-corrected, see app.py's
        # spot-meter loop for why)
        dist_str = f" @ {data.distance_m:.2f}m" if data.distance_m is not None else ""

        # Held peak, only when it says something the current reading doesn't
        peak_str = ""
        if data.peak is not None and data.temperature is not None and data.peak - data.temperature >= 0.1:
            peak_str = f"  ⌃{data.peak:.1f}"
        alert_str = " ⚠" if data.alert and data.alert.triggered else ""

        # Build display text
        display_text = f"{indicators}{data.label}: {temp_str}{trend_icon}{peak_str}{alert_str}{dist_str}  ({data.x}, {data.y})"
        self.setText(display_text)

        # Set color indicator as icon, keep text color default for readability
        r, g, b = data.color

        # Create a solid color icon
        pixmap = QPixmap(12, 12)
        pixmap.fill(QColor(r, g, b))
        self.setIcon(QIcon(pixmap))

        # Reset text color to use theme default (handled by QListWidget)
        self.setForeground(QBrush()) # Reset to default brush


class SpotMeterPanel(QWidget):
    """Panel for managing spot meters."""

    # Signals
    spot_selected = pyqtSignal(str)           # Emit spot ID when selected in list
    spot_renamed = pyqtSignal(str, str)       # Emit (spot_id, new_name)
    spot_deleted = pyqtSignal(str)            # Emit spot ID to delete
    spot_visibility_changed = pyqtSignal(str, bool)  # (spot_id, visible)
    spot_locked_changed = pyqtSignal(str, bool)      # (spot_id, locked)
    clear_all_requested = pyqtSignal()
    export_requested = pyqtSignal(str)        # Export format ('csv', 'json')
    highlight_spot = pyqtSignal(str)          # Highlight spot on video
    preset_requested = pyqtSignal(str)        # Request to apply preset
    alert_triggered = pyqtSignal(str, str, float) # (spot_id, type, val)
    comparison_changed = pyqtSignal(str, str, float)  # (spot1_id, spot2_id, delta) - Phase 1 Feature 3
    snap_to_hottest_changed = pyqtSignal(bool)        # place new spots on the hottest nearby pixel

    def __init__(self, parent=None):
        super().__init__(parent)
        self.spots: Dict[str, SpotMeterData] = {}
        self.start_time = time.time()
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._setup_ui()

    def _setup_ui(self):
        """Build the panel UI."""
        # Main layout for the panel (holds the scroll area)
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Scroll Area
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        main_layout.addWidget(scroll_area)

        # Content Widget (holds the actual controls)
        content_widget = QWidget()
        scroll_area.setWidget(content_widget)

        # Content Layout
        layout = QVBoxLayout(content_widget)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(6)

        # Title
        title = QLabel("📍 Spot Meters")
        title.setStyleSheet("font-weight: bold; font-size: 9.75pt;")
        layout.addWidget(title)

        # Spot meter list
        self.spot_list = HintListWidget("No spot meters yet. Click Add Spot Meter, then click the video.")
        self.spot_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.spot_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.spot_list.customContextMenuRequested.connect(self._show_context_menu)
        self.spot_list.itemDoubleClicked.connect(self._on_item_double_clicked)
        self.spot_list.itemSelectionChanged.connect(self._on_selection_changed)
        self.spot_list.setMinimumHeight(120)
        self.spot_list.setMaximumHeight(200)
        layout.addWidget(self.spot_list)

        # Action buttons row 1
        btn_row1 = QHBoxLayout()
        btn_row1.setSpacing(4)

        self.rename_btn = QPushButton("✏️ Rename")
        self.rename_btn.setToolTip("Rename selected spot meter (F2)")
        self.rename_btn.clicked.connect(self._on_rename_clicked)
        btn_row1.addWidget(self.rename_btn)

        self.delete_btn = QPushButton("🗑️ Delete")
        self.delete_btn.setToolTip("Delete selected spot meter(s) (Del)")
        self.delete_btn.clicked.connect(self._on_delete_clicked)
        btn_row1.addWidget(self.delete_btn)

        self.clear_btn = QPushButton("Clear All")
        self.clear_btn.setToolTip("Remove all spot meters")
        self.clear_btn.clicked.connect(self._on_clear_clicked)
        btn_row1.addWidget(self.clear_btn)

        layout.addLayout(btn_row1)

        # Action buttons row 2
        btn_row2 = QHBoxLayout()
        btn_row2.setSpacing(4)

        self.toggle_visibility_btn = QPushButton("👁️ Show/Hide")
        self.toggle_visibility_btn.setToolTip("Toggle visibility of selected spot meter")
        self.toggle_visibility_btn.clicked.connect(self._on_toggle_visibility)
        btn_row2.addWidget(self.toggle_visibility_btn)

        self.lock_btn = QPushButton("🔒 Lock")
        self.lock_btn.setToolTip("Lock/unlock position of selected spot meter")
        self.lock_btn.clicked.connect(self._on_toggle_lock)
        btn_row2.addWidget(self.lock_btn)

        layout.addLayout(btn_row2)

        # Separator
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(line)

        # Statistics section
        stats_group = QGroupBox("Statistics")
        stats_layout = QVBoxLayout(stats_group)
        stats_layout.setSpacing(2)
        stats_layout.setContentsMargins(8, 8, 8, 8)

        self.stats_count_label = QLabel("Count: 0")
        stats_layout.addWidget(self.stats_count_label)

        # Min/Max/Avg on same line
        minmax_layout = QHBoxLayout()
        self.stats_min_label = QLabel("Min: --")
        minmax_layout.addWidget(self.stats_min_label)
        self.stats_max_label = QLabel("Max: --")
        minmax_layout.addWidget(self.stats_max_label)
        stats_layout.addLayout(minmax_layout)

        avg_delta_layout = QHBoxLayout()
        self.stats_avg_label = QLabel("Avg: --")
        avg_delta_layout.addWidget(self.stats_avg_label)
        self.stats_delta_label = QLabel("ΔT: --")
        self.stats_delta_label.setToolTip("Temperature difference between hottest and coldest spots")
        avg_delta_layout.addWidget(self.stats_delta_label)
        stats_layout.addLayout(avg_delta_layout)

        # Median/StdDev layout (Phase 2 - Feature 6: Multi-point Statistics)
        median_stddev_layout = QHBoxLayout()
        self.stats_median_label = QLabel("Median: --")
        self.stats_median_label.setToolTip("Middle value when spots are ordered by temperature")
        median_stddev_layout.addWidget(self.stats_median_label)
        self.stats_stddev_label = QLabel("StdDev: --")
        self.stats_stddev_label.setToolTip("Standard deviation of temperatures (measure of variation)")
        median_stddev_layout.addWidget(self.stats_stddev_label)
        stats_layout.addLayout(median_stddev_layout)

        layout.addWidget(stats_group)

        # Export buttons
        export_row = QHBoxLayout()
        export_row.setSpacing(4)

        self.export_csv_btn = QPushButton("📊 Export CSV")
        self.export_csv_btn.setToolTip("Export spot meter data to CSV file")
        self.export_csv_btn.clicked.connect(self._on_export_csv)
        export_row.addWidget(self.export_csv_btn)

        self.export_json_btn = QPushButton("📋 Export JSON")
        self.export_json_btn.setToolTip("Export spot meter data to JSON file")
        self.export_json_btn.clicked.connect(self._on_export_json)
        export_row.addWidget(self.export_json_btn)

        layout.addLayout(export_row)

        # Advanced Features Group
        adv_group = QGroupBox("Advanced")
        adv_layout = QVBoxLayout(adv_group)
        adv_layout.setSpacing(4)
        adv_layout.setContentsMargins(8, 8, 8, 8)

        # Presets
        preset_layout = QHBoxLayout()
        self.preset_combo = QComboBox()
        self.preset_combo.addItems(SpotMeterPresets.get_presets())
        preset_layout.addWidget(self.preset_combo)

        self.apply_preset_btn = QPushButton("Apply")
        self.apply_preset_btn.setToolTip("Apply selected spot meter pattern")
        self.apply_preset_btn.clicked.connect(self._on_apply_preset)
        preset_layout.addWidget(self.apply_preset_btn)
        adv_layout.addLayout(preset_layout)

        # Snap to hottest pixel when placing
        self.snap_cb = QCheckBox("Snap new spots to the hottest nearby pixel")
        self.snap_cb.setToolTip("When placing a spot meter, move it to the hottest pixel within a few pixels of the click")
        self.snap_cb.toggled.connect(self.snap_to_hottest_changed.emit)
        adv_layout.addWidget(self.snap_cb)

        # Compare Mode
        self.compare_cb = QCheckBox("Compare Mode (Select 2)")
        self.compare_cb.setToolTip("Show delta between exactly 2 selected spots")
        self.compare_cb.toggled.connect(self._on_compare_toggled)
        adv_layout.addWidget(self.compare_cb)

        # Cursor Temperature Readout (Phase 1 - Feature 1)
        self.cursor_readout_cb = QCheckBox("Cursor Temperature Readout")
        self.cursor_readout_cb.setToolTip("Show real-time temperature at cursor position with crosshair")
        self.cursor_readout_cb.setChecked(False)
        # Signal will be connected by parent GUI
        adv_layout.addWidget(self.cursor_readout_cb)

        # History Graph Toggle
        self.show_graph_btn = QPushButton("Show History Graph")
        self.show_graph_btn.setCheckable(True)
        self.show_graph_btn.setChecked(False)
        self.show_graph_btn.clicked.connect(self._on_toggle_graph)
        adv_layout.addWidget(self.show_graph_btn)

        layout.addWidget(adv_group)

        # History Graph Widget (Initially hidden)
        self.history_graph = TemperatureHistoryGraph()
        self.history_graph.setVisible(False)
        self.history_graph.setMinimumHeight(200)
        self.history_graph.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        # Pass start_time to graph for relative calculation
        self.history_graph.start_time = self.start_time
        layout.addWidget(self.history_graph)

        # Initial button state
        self._update_button_states()

    def _on_toggle_graph(self, checked: bool):
        """Toggle history graph visibility."""
        self.history_graph.setVisible(checked)
        if checked:
            self._update_graph()

    def _update_graph(self):
        """Update history graph with current selection."""
        if not self.history_graph.isVisible():
            return

        items = self.spot_list.selectedItems()
        selected_spots = []
        for item in items:
            spot_id = item.data(Qt.ItemDataRole.UserRole)
            if spot_id in self.spots:
                selected_spots.append(self.spots[spot_id])

        self.history_graph.update_data(selected_spots)

    def keyPressEvent(self, event):
        """Handle keyboard shortcuts."""
        if event.key() == Qt.Key.Key_Delete:
            self._on_delete_clicked()
        elif event.key() == Qt.Key.Key_F2:
            self._on_rename_clicked()
        else:
            super().keyPressEvent(event)

    def add_spot(self, spot_id: str, x: int, y: int, label: str = None,
                 color: Tuple[int, int, int] = (255, 255, 0)) -> SpotMeterData:
        """Add a new spot meter to the panel.

        Args:
            spot_id: Unique identifier for the spot
            x: X coordinate in frame
            y: Y coordinate in frame
            label: Display label (auto-generated if None)
            color: RGB color tuple

        Returns:
            The created SpotMeterData object
        """
        if label is None:
            label = f"Spot #{len(self.spots) + 1}"

        data = SpotMeterData(
            id=spot_id,
            label=label,
            x=x,
            y=y,
            color=color
        )
        self.spots[spot_id] = data

        item = SpotMeterListItem(data)
        item.setData(Qt.ItemDataRole.UserRole, spot_id)
        self.spot_list.addItem(item)

        self._update_statistics()
        self._update_button_states()
        logger.info(f"Spot meter added: {label} at ({x}, {y})")

        return data

    def remove_spot(self, spot_id: str):
        """Remove a spot meter from the panel."""
        if spot_id not in self.spots:
            return

        del self.spots[spot_id]

        # Find and remove list item
        for i in range(self.spot_list.count()):
            item = self.spot_list.item(i)
            if item and item.data(Qt.ItemDataRole.UserRole) == spot_id:
                self.spot_list.takeItem(i)
                break

        self._update_statistics()
        self._update_button_states()
        logger.info(f"Spot meter removed: {spot_id}")

    def get_all_spots(self) -> List[SpotMeterData]:
        """Get list of all spot meter data objects."""
        return list(self.spots.values())

    def clear(self):
        """Remove all spot meters."""
        self.spots.clear()
        self.spot_list.clear() # Qt ListWidget clearing
        self._update_statistics()
        self._update_button_states()
        logger.info("All spot meters cleared")


    def update_temperature(self, spot_id: str, temperature: float, unit: str = "°C"):
        """Update temperature reading for a single spot meter.

        Args:
            spot_id: Spot meter ID
            temperature: New temperature value
            unit: Temperature unit string
        """
        if not self._apply_temperature(spot_id, temperature, unit):
            return
        self._update_statistics()
        self._update_graph()

    def _apply_temperature(self, spot_id: str, temperature: float, unit: str = "°C",
                            distance_m: Optional[float] = None) -> bool:
        """Store a new reading and refresh just this spot's own list item -
        the aggregate stats/graph refresh is the caller's job (a single
        call after every spot in a batch is done, not once per spot)."""
        if spot_id not in self.spots:
            return False

        data = self.spots[spot_id]
        if data.unit != unit:
            # Unit changed: re-express the old readings (and the held peak) in the new unit so the graph and peak
            # survive a degC/degF/K switch; raw-count units can't be converted, so those start over.
            data.convert_unit(unit)
            if hasattr(data, 'timestamps'):
                data.timestamps.clear()
        data.temperature = temperature
        data.unit = unit
        data.distance_m = distance_m
        data.updated_at = time.time()
        data.add_history(temperature)
        data.record_extremes(temperature)

        # Check alerts (Phase 6)
        self.check_alerts(spot_id, temperature)

        # Update list item display
        self._refresh_list_item(spot_id)
        return True

    def update_spot_temperatures(self, values: List[Dict]):
        """Batch update temperatures from main loop.

        Refreshes aggregate statistics and the history graph exactly
        once after every spot's reading is applied, instead of once per
        spot (update_temperature()'s single-spot path did that
        redundantly - N active spot meters meant the same aggregate
        stats labels and history graph got rebuilt N times on a single
        render tick, confirmed live as this loop runs unconditionally
        every frame from the main loop).

        Args:
            values: List of {'label': str, 'temperature': float, 'unit': str}
        """
        any_updated = False
        for val in values:
            label = val.get('label', '')
            # Find spot by label
            for spot_id, data in self.spots.items():
                if data.label == label:
                    if self._apply_temperature(
                        spot_id,
                        val.get('temperature'),
                        val.get('unit', '°C'),
                        distance_m=val.get('distance_m')
                    ):
                        any_updated = True
                    break

        if any_updated:
            self._update_statistics()
            self._update_graph()

    def _refresh_list_item(self, spot_id: str):
        """Refresh the display of a specific list item."""
        for i in range(self.spot_list.count()):
            item = self.spot_list.item(i)
            if isinstance(item, SpotMeterListItem) and item.data(Qt.ItemDataRole.UserRole) == spot_id:
                item.spot_data = self.spots[spot_id]
                item.update_display()
                break

    def _update_statistics(self):
        """Recalculate and display statistics."""
        temps = [
            data.temperature for data in self.spots.values()
            if data.temperature is not None and data.visible
        ]

        count = len(self.spots)
        self.stats_count_label.setText(f"Count: {count}")

        if temps:
            min_temp = min(temps)
            max_temp = max(temps)
            avg_temp = sum(temps) / len(temps)
            delta = max_temp - min_temp

            # Find unit (assume all same)
            unit = next(iter(self.spots.values())).unit if self.spots else "°C"

            self.stats_min_label.setText(f"Min: {min_temp:.1f}{unit}")
            self.stats_max_label.setText(f"Max: {max_temp:.1f}{unit}")
            self.stats_avg_label.setText(f"Avg: {avg_temp:.1f}{unit}")
            self.stats_delta_label.setText(f"ΔT: {delta:.1f}{unit}")
        else:
            self.stats_min_label.setText("Min: --")
            self.stats_max_label.setText("Max: --")
            self.stats_avg_label.setText("Avg: --")
            self.stats_delta_label.setText("ΔT: --")

    def _on_apply_preset(self):
        """Apply selected preset."""
        preset = self.preset_combo.currentText()
        if preset:
            self.preset_requested.emit(preset)

    def _on_compare_toggled(self, checked: bool):
        """Handle compare mode toggle."""
        if not checked:
            # Clear comparison visualization when disabled
            self.comparison_changed.emit("", "", 0.0)
        self._update_statistics()

    def _update_statistics(self):
        """Recalculate and display statistics."""
        # Check compare mode first
        if hasattr(self, 'compare_cb') and self.compare_cb.isChecked():
            selected = self.spot_list.selectedItems()
            if len(selected) == 2:
                id1 = selected[0].data(Qt.ItemDataRole.UserRole)
                id2 = selected[1].data(Qt.ItemDataRole.UserRole)
                spot1 = self.spots.get(id1)
                spot2 = self.spots.get(id2)

                if spot1 and spot2 and spot1.temperature is not None and spot2.temperature is not None:
                    delta = spot2.temperature - spot1.temperature  # Preserve sign for visualization
                    self.stats_delta_label.setText(f"Comp ({spot1.label[-4:]} vs {spot2.label[-4:]}): Δ{delta:.1f}{spot1.unit}")
                    # Emit signal for overlay visualization (Phase 1 - Feature 3)
                    self.comparison_changed.emit(id1, id2, delta)
                else:
                    self.stats_delta_label.setText("Comp: --")
                    self.comparison_changed.emit("", "", 0.0)  # Clear comparison
            else:
                 self.stats_delta_label.setText("Select 2 spots")
                 self.comparison_changed.emit("", "", 0.0)  # Clear comparison

            # Still show global min/max

        temps = [
            data.temperature for data in self.spots.values()
            if data.temperature is not None and data.visible
        ]

        count = len(self.spots)
        self.stats_count_label.setText(f"Count: {count}")

        if temps:
            min_temp = min(temps)
            max_temp = max(temps)
            avg_temp = sum(temps) / len(temps)

            # Phase 2 - Feature 6: Multi-point Statistics
            # Calculate median and standard deviation
            median_temp = statistics.median(temps)
            stddev_temp = statistics.stdev(temps) if len(temps) > 1 else 0.0

            # Update labels (unless overridden by compare mode for delta)
            # Find unit (assume all same)
            unit = next(iter(self.spots.values())).unit if self.spots else "°C"

            self.stats_min_label.setText(f"Min: {min_temp:.1f}{unit}")
            self.stats_max_label.setText(f"Max: {max_temp:.1f}{unit}")
            self.stats_avg_label.setText(f"Avg: {avg_temp:.1f}{unit}")
            self.stats_median_label.setText(f"Median: {median_temp:.1f}{unit}")
            self.stats_stddev_label.setText(f"StdDev: {stddev_temp:.1f}{unit}")

            if not self.compare_cb.isChecked():
                delta = max_temp - min_temp
                self.stats_delta_label.setText(f"ΔT: {delta:.1f}{unit}")
        else:
            self.stats_min_label.setText("Min: --")
            self.stats_max_label.setText("Max: --")
            self.stats_avg_label.setText("Avg: --")
            self.stats_median_label.setText("Median: --")  # Phase 2 - Feature 6
            self.stats_stddev_label.setText("StdDev: --")  # Phase 2 - Feature 6
            if not self.compare_cb.isChecked():
                self.stats_delta_label.setText("ΔT: --")

    def _update_button_states(self):
        """Enable/disable buttons based on selection."""
        has_selection = len(self.spot_list.selectedItems()) > 0
        has_spots = self.spot_list.count() > 0

        self.rename_btn.setEnabled(has_selection)
        self.delete_btn.setEnabled(has_selection)
        self.clear_btn.setEnabled(has_spots)
        self.toggle_visibility_btn.setEnabled(has_selection)
        self.lock_btn.setEnabled(has_selection)
        self.export_csv_btn.setEnabled(has_spots)
        self.export_json_btn.setEnabled(has_spots)

    def _on_selection_changed(self):
        """Handle list selection change."""
        self._update_button_states()

        # If compare mode is on, update stats to show comp
        if hasattr(self, 'compare_cb') and self.compare_cb.isChecked():
            self._update_statistics()

        items = self.spot_list.selectedItems()
        if items:
            spot_id = items[0].data(Qt.ItemDataRole.UserRole)
            self.spot_selected.emit(spot_id)
            self.highlight_spot.emit(spot_id)

    def _on_item_double_clicked(self, item: QListWidgetItem):
        """Handle double-click to rename."""
        self._on_rename_clicked()

    def _on_rename_clicked(self):
        """Rename selected spot meter."""
        items = self.spot_list.selectedItems()
        if not items:
            return

        item = items[0]
        spot_id = item.data(Qt.ItemDataRole.UserRole)
        data = self.spots.get(spot_id)

        if data:
            new_name, ok = QInputDialog.getText(
                self, "Rename Spot Meter",
                "Enter new name:",
                text=data.label
            )
            if ok and new_name:
                data.label = new_name
                if isinstance(item, SpotMeterListItem):
                    item.update_display()
                self.spot_renamed.emit(spot_id, new_name)
                logger.info(f"Spot meter renamed: {spot_id} -> {new_name}")

    def _on_set_alert(self):
        """Configure alert for selected spot meter."""
        items = self.spot_list.selectedItems()
        if not items:
            return

        spot_id = items[0].data(Qt.ItemDataRole.UserRole)
        data = self.spots.get(spot_id)
        if not data:
            return

        dialog = SpotMeterAlertDialog(data.alert, unit=data.unit, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data.alert = dialog.result_alert
            # Check immediately
            if data and data.alert:
             if data.alert.check(data.temperature, data.unit, data.history):
                 logger.warning(f"ALERT: {data.label} {data.alert.describe()} (Val: {data.temperature})")
                 self.alert_triggered.emit(spot_id, data.alert.type, data.temperature)
            logger.info(f"Alert configured for {data.label}: {data.alert}")

    def _on_reset_peak(self):
        """Reset the held peak/trough of the selected spot meters (all of them when none is selected)."""
        ids = [i.data(Qt.ItemDataRole.UserRole) for i in self.spot_list.selectedItems()] or list(self.spots)
        for spot_id in ids:
            if spot_id in self.spots:
                self.spots[spot_id].reset_peak()
                self._refresh_list_item(spot_id)

    def check_alerts(self, spot_id: str, temperature: float):
        """Check alert for specific spot (Phase 2 - Feature 7: Enhanced with sound/flash)."""
        data = self.spots.get(spot_id)
        if data and data.alert:
            # Store previous trigger state to detect rising edge
            was_triggered = data.alert.triggered

            if data.alert.check(temperature, data.unit, data.history):
                logger.warning(f"ALERT: {data.label} {data.alert.describe()} (Val: {temperature}{data.unit})")
                self.alert_triggered.emit(spot_id, data.alert.type, temperature)

                # Play sound on rising edge only (not continuously)
                if not was_triggered and data.alert.sound_enabled:
                    try:
                        QApplication.beep()  # System beep
                        logger.debug(f"Alert sound played for {data.label}")
                    except Exception as e:
                        logger.warning(f"Failed to play alert sound: {e}")

    def _on_delete_clicked(self):
        """Delete selected spot meter(s)."""
        items = self.spot_list.selectedItems()
        for item in items:
            spot_id = item.data(Qt.ItemDataRole.UserRole)
            self.spot_deleted.emit(spot_id)
            self.remove_spot(spot_id)

    def _on_clear_clicked(self):
        """Clear all spot meters."""
        if self.spots:
            reply = QMessageBox.question(
                self, "Clear All Spot Meters",
                f"Remove all {len(self.spots)} spot meters?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.spots.clear()
                self.spot_list.clear()
                self._update_statistics()
                self._update_button_states()
                self.clear_all_requested.emit()
                logger.info("All spot meters cleared")

    def _on_toggle_visibility(self):
        """Toggle visibility of selected spot meter."""
        items = self.spot_list.selectedItems()
        for item in items:
            spot_id = item.data(Qt.ItemDataRole.UserRole)
            data = self.spots.get(spot_id)
            if data:
                data.visible = not data.visible
                if isinstance(item, SpotMeterListItem):
                    item.update_display()
                self.spot_visibility_changed.emit(spot_id, data.visible)
                logger.debug(f"Spot {spot_id} visibility: {data.visible}")

    def _on_toggle_lock(self):
        """Toggle position lock of selected spot meter."""
        items = self.spot_list.selectedItems()
        for item in items:
            spot_id = item.data(Qt.ItemDataRole.UserRole)
            data = self.spots.get(spot_id)
            if data:
                data.locked = not data.locked
                if isinstance(item, SpotMeterListItem):
                    item.update_display()
                self.spot_locked_changed.emit(spot_id, data.locked)
                logger.debug(f"Spot {spot_id} locked: {data.locked}")

    def _on_export_csv(self):
        """Export spot meters to CSV file."""
        if not self.spots:
            return

        filepath, _ = QFileDialog.getSaveFileName(
            self, "Export Spot Meters to CSV",
            "spot_meters.csv",
            "CSV Files (*.csv);;All Files (*)"
        )
        if filepath:
            self.export_requested.emit('csv')
            self._do_export_csv(filepath)

    def _on_export_json(self):
        """Export spot meters to JSON file."""
        if not self.spots:
            return

        filepath, _ = QFileDialog.getSaveFileName(
            self, "Export Spot Meters to JSON",
            "spot_meters.json",
            "JSON Files (*.json);;All Files (*)"
        )
        if filepath:
            self.export_requested.emit('json')
            self._do_export_json(filepath)

    def _do_export_csv(self, filepath: str):
        """Perform CSV export."""
        try:
            from spot_meter_exporter import SpotMeterExporter
            spots = list(self.spots.values())

            # Export Snapshot
            success = SpotMeterExporter.export_to_csv(spots, filepath)

            # Export History (if available)
            history_path = filepath.replace('.csv', '_history.csv')
            history_success = SpotMeterExporter.export_history_to_csv(spots, history_path)

            msg = f"Exported {len(spots)} spot meters to:\n{filepath}"
            if history_success:
                msg += f"\n\nMap history exported to:\n{history_path}"

            if success:
                QMessageBox.information(self, "Export Complete", msg)
        except ImportError:
            # Fallback if exporter not available
            self._export_csv_fallback(filepath)
        except Exception as e:
            QMessageBox.warning(self, "Export Failed", f"Error: {e}")

    def _do_export_json(self, filepath: str):
        """Perform JSON export."""
        try:
            from spot_meter_exporter import SpotMeterExporter
            spots = list(self.spots.values())
            if SpotMeterExporter.export_to_json(spots, filepath):
                QMessageBox.information(
                    self, "Export Complete",
                    f"Exported {len(spots)} spot meters to:\n{filepath}"
                )
        except ImportError:
            # Fallback if exporter not available
            self._export_json_fallback(filepath)
        except Exception as e:
            QMessageBox.warning(self, "Export Failed", f"Error: {e}")

    def _export_csv_fallback(self, filepath: str):
        """Simple CSV export fallback."""
        import csv

        try:
            with open(filepath, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['ID', 'Label', 'X', 'Y', 'Temperature', 'Unit', 'Visible', 'Locked'])
                for spot in self.spots.values():
                    writer.writerow([
                        spot.id, spot.label, spot.x, spot.y,
                        spot.temperature if spot.temperature else '',
                        spot.unit, spot.visible, spot.locked
                    ])
            QMessageBox.information(self, "Export Complete", f"Exported to:\n{filepath}")
        except Exception as e:
            QMessageBox.warning(self, "Export Failed", f"Error: {e}")

    def _export_json_fallback(self, filepath: str):
        """Simple JSON export fallback."""
        import json
        from datetime import datetime

        try:
            data = {
                'export_time': datetime.now().isoformat(),
                'spot_count': len(self.spots),
                'spots': [
                    {
                        'id': s.id, 'label': s.label,
                        'x': s.x, 'y': s.y,
                        'temperature': s.temperature,
                        'unit': s.unit,
                        'visible': s.visible, 'locked': s.locked
                    }
                    for s in self.spots.values()
                ]
            }
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
            QMessageBox.information(self, "Export Complete", f"Exported to:\n{filepath}")
        except Exception as e:
            QMessageBox.warning(self, "Export Failed", f"Error: {e}")

    def _show_context_menu(self, position):
        """Show context menu for spot meter actions."""
        item = self.spot_list.itemAt(position)
        if not item:
            return

        menu = QMenu(self)

        rename_action = menu.addAction("✏️ Rename...")
        rename_action.triggered.connect(self._on_rename_clicked)

        selected_items = self.spot_list.selectedItems()
        if selected_items:
            menu.addSeparator()
            menu.addAction("⚠️ Set Alert...", self._on_set_alert)
            menu.addSeparator()
            delete_action = menu.addAction("🗑️ Delete")
            delete_action.triggered.connect(self._on_delete_clicked)

        menu.addSeparator()

        spot_id = item.data(Qt.ItemDataRole.UserRole)
        data = self.spots.get(spot_id)

        if data:
            visibility_text = "🙈 Hide" if data.visible else "👁️ Show"
            visibility_action = menu.addAction(visibility_text)
            visibility_action.triggered.connect(self._on_toggle_visibility)

            lock_text = "🔓 Unlock" if data.locked else "🔒 Lock Position"
            lock_action = menu.addAction(lock_text)
            lock_action.triggered.connect(self._on_toggle_lock)

            menu.addSeparator()
            menu.addAction("♻ Reset Peak Hold", self._on_reset_peak)

        menu.exec(self.spot_list.mapToGlobal(position))

class SpotMeterAlertDialog(QDialog):
    """Dialog to configure spot meter alert."""

    def __init__(self, current_alert: Optional[SpotMeterAlert], unit: str = "°C", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configure Alert")
        self.setModal(True)
        self.result_alert = None

        layout = QVBoxLayout(self)

        # Threshold
        thresh_layout = QHBoxLayout()
        thresh_layout.addWidget(QLabel(f"Threshold ({unit}):"))
        self.thresh_spin = QDoubleSpinBox()
        self._unit = unit
        from thermal_inspection.utils.temperature_units import convert, from_celsius, unit_code
        code = unit_code(unit)
        if code == 'Y16':
            self.thresh_spin.setRange(0.0, 100000.0)
        elif code is None:
            self.thresh_spin.setRange(0.0, 255.0)  # AGC counts
        else:
            self.thresh_spin.setRange(-100.0, 1000.0)
        self.thresh_spin.setDecimals(1)
        if current_alert:
            # Show the existing threshold in the unit currently displayed
            shown = convert(current_alert.threshold, current_alert.unit, unit)
            self.thresh_spin.setValue(shown if shown is not None else current_alert.threshold)
        elif code is None:
            self.thresh_spin.setValue(128.0)
        else:
            self.thresh_spin.setValue(from_celsius(30.0, code))
        thresh_layout.addWidget(self.thresh_spin)
        layout.addLayout(thresh_layout)

        # Type (Above/Below)
        type_group = QGroupBox("Condition")
        type_layout = QVBoxLayout(type_group)
        self.above_radio = QRadioButton("Alert when ABOVE threshold")
        self.below_radio = QRadioButton("Alert when BELOW threshold")
        self.rising_radio = QRadioButton("Alert when it RISES faster than the threshold, per minute")
        self.falling_radio = QRadioButton("Alert when it FALLS faster than the threshold, per minute")

        kind = current_alert.type if current_alert else 'above'
        {'below': self.below_radio, 'rising_fast': self.rising_radio,
         'falling_fast': self.falling_radio}.get(kind, self.above_radio).setChecked(True)

        type_layout.addWidget(self.above_radio)
        type_layout.addWidget(self.below_radio)
        type_layout.addWidget(self.rising_radio)
        type_layout.addWidget(self.falling_radio)
        layout.addWidget(type_group)

        # Enabled
        self.enabled_cb = QCheckBox("Enable Alert")
        self.enabled_cb.setChecked(current_alert.enabled if current_alert else True)
        layout.addWidget(self.enabled_cb)

        # Phase 2 - Feature 7: Enhanced Alert Options
        options_group = QGroupBox("Alert Options")
        options_layout = QVBoxLayout(options_group)

        self.sound_cb = QCheckBox("🔊 Play Sound on Trigger")
        self.sound_cb.setChecked(current_alert.sound_enabled if current_alert else True)
        self.sound_cb.setToolTip("Play audible beep when alert triggers")
        options_layout.addWidget(self.sound_cb)

        self.flash_cb = QCheckBox("💡 Flash Visual Indicator")
        self.flash_cb.setChecked(current_alert.flash_enabled if current_alert else True)
        self.flash_cb.setToolTip("Flash spot meter color when alert is active")
        options_layout.addWidget(self.flash_cb)

        layout.addWidget(options_group)

        # Alert Statistics (if available)
        if current_alert and current_alert.trigger_count > 0:
            stats_label = QLabel(f"📊 Triggered {current_alert.trigger_count} times")
            stats_label.setStyleSheet("color: #888888; font-size: 7.5pt;")
            layout.addWidget(stats_label)

        # Buttons
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self._on_accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _on_accept(self):
        alert_type = ('rising_fast' if self.rising_radio.isChecked() else
                      'falling_fast' if self.falling_radio.isChecked() else
                      'below' if self.below_radio.isChecked() else 'above')
        self.result_alert = SpotMeterAlert(
            threshold=self.thresh_spin.value(),
            unit=self._unit,
            type=alert_type,
            enabled=self.enabled_cb.isChecked(),
            sound_enabled=self.sound_cb.isChecked(),  # Phase 2 - Feature 7
            flash_enabled=self.flash_cb.isChecked()   # Phase 2 - Feature 7
        )
        self.accept()







    def get_all_spots(self) -> List[SpotMeterData]:
        """Get all spot meter data for export."""
        return list(self.spots.values())

    def get_spot(self, spot_id: str) -> Optional[SpotMeterData]:
        """Get a specific spot meter by ID."""
        return self.spots.get(spot_id)

    def select_spot(self, spot_id: str):
        """Select a spot meter in the list (called from video click)."""
        for i in range(self.spot_list.count()):
            item = self.spot_list.item(i)
            if item and item.data(Qt.ItemDataRole.UserRole) == spot_id:
                self.spot_list.setCurrentItem(item)
                break

    def clear(self):
        """Clear all spot meters (for external use, no confirmation)."""
        self.spots.clear()
        self.spot_list.clear()
        self._update_statistics()
        self._update_button_states()

    def get_coords_for_main_loop(self) -> List[Tuple[int, int, str]]:
        """Get coordinates in format expected by main processing loop.

        Returns:
            List of (x, y, label) tuples for visible spots
        """
        return [
            (data.x, data.y, data.label)
            for data in self.spots.values()
            if data.visible
        ]
