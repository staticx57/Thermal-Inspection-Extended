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
    QCheckBox, QDialog, QFormLayout, QSpinBox, QDoubleSpinBox,
    QScrollArea
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QColor, QAction, QIcon, QPixmap, QBrush
from typing import List, Dict, Optional, Tuple, Callable
from dataclasses import dataclass, field
import logging
import time
try:
    import pyqtgraph as pg
    HAS_PYQTGRAPH = True
except ImportError:
    HAS_PYQTGRAPH = False

logger = logging.getLogger(__name__)


@dataclass
class SpotMeterAlert:
    """Alert configuration for a spot meter."""
    threshold: float
    type: str = 'above'  # 'above' or 'below'
    enabled: bool = True
    triggered: bool = False
    
    def check(self, value: float) -> bool:
        """Check if alert should trigger."""
        if not self.enabled:
            return False
            
        is_triggered = False
        if self.type == 'above':
            is_triggered = value > self.threshold
        elif self.type == 'below':
            is_triggered = value < self.threshold
            
        return is_triggered


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
            self.plot.removeItem(self.curves[spot_id])
            del self.curves[spot_id]
            
        # Update or add curves
        for spot in selected_spots:
            if not spot.history:
                continue
                
            times, temps = zip(*spot.history)
            # Normalize time to relative (0 = now)
            now = time.time()
            rel_times = [t - now for t in times]
            
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
    color: Tuple[int, int, int] = (255, 255, 0)  # Marker color (BGR)
    visible: bool = True                 # Visibility toggle
    locked: bool = False                 # Position lock
    created_at: float = 0.0              # Creation timestamp
    updated_at: float = 0.0              # Last temperature update
    history: List[Tuple[float, float]] = field(default_factory=list)  # (timestamp, temp) history
    alert: Optional[SpotMeterAlert] = None # Alert configuration
    
    def __post_init__(self):
        if self.created_at == 0.0:
            self.created_at = time.time()
            
    def add_history(self, temperature: float):
        """Add a temperature reading to history (keeps last 1000)."""
        self.history.append((time.time(), temperature))
        if len(self.history) > 1000:
            self.history.pop(0)
            
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
            
        # Build display text
        display_text = f"{indicators}{data.label}: {temp_str}{trend_icon}  ({data.x}, {data.y})"
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

    def __init__(self, parent=None):
        super().__init__(parent)
        self.spots: Dict[str, SpotMeterData] = {}
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
        title.setStyleSheet("font-weight: bold; font-size: 13px;")
        layout.addWidget(title)
        
        # Spot meter list
        self.spot_list = QListWidget()
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

        # Compare Mode
        self.compare_cb = QCheckBox("Compare Mode (Select 2)")
        self.compare_cb.setToolTip("Show delta between exactly 2 selected spots")
        self.compare_cb.toggled.connect(self._on_compare_toggled)
        adv_layout.addWidget(self.compare_cb)

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
        layout.addWidget(self.history_graph)
        
        # Add stretch to keep items at top
        layout.addStretch()
        
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
        
    def update_temperature(self, spot_id: str, temperature: float, unit: str = "°C"):
        """Update temperature reading for a spot meter.
        
        Args:
            spot_id: Spot meter ID
            temperature: New temperature value
            unit: Temperature unit string
        """
        if spot_id not in self.spots:
            return
            
        data = self.spots[spot_id]
        data.temperature = temperature
        data.unit = unit
        data.updated_at = time.time()
        data.add_history(temperature)
        
        # Check alerts (Phase 6)
        self.check_alerts(spot_id, temperature)
        
        # Update list item display
        self._refresh_list_item(spot_id)
        self._update_statistics()
        
        # Update history graph
        self._update_graph()
        
    def update_spot_temperatures(self, values: List[Dict]):
        """Batch update temperatures from main loop.
        
        Args:
            values: List of {'label': str, 'temperature': float, 'unit': str}
        """
        for val in values:
            label = val.get('label', '')
            # Find spot by label
            for spot_id, data in self.spots.items():
                if data.label == label:
                    self.update_temperature(
                        spot_id, 
                        val.get('temperature'), 
                        val.get('unit', '°C')
                    )
                    break
                    
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
                    delta = abs(spot1.temperature - spot2.temperature)
                    self.stats_delta_label.setText(f"Comp ({spot1.label[-4:]} vs {spot2.label[-4:]}): Δ{delta:.1f}{spot1.unit}")
                    # Clear other stats to focus on comparison or keep them?
                    # Let's keep them but maybe dim them? For now just show Comp.
                else:
                    self.stats_delta_label.setText("Comp: --")
            else:
                 self.stats_delta_label.setText("Select 2 spots")
                 
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
            
            # Update labels (unless overridden by compare mode for delta)
            # Find unit (assume all same)
            unit = next(iter(self.spots.values())).unit if self.spots else "°C"
            
            self.stats_min_label.setText(f"Min: {min_temp:.1f}{unit}")
            self.stats_max_label.setText(f"Max: {max_temp:.1f}{unit}")
            self.stats_avg_label.setText(f"Avg: {avg_temp:.1f}{unit}")
            
            if not self.compare_cb.isChecked():
                delta = max_temp - min_temp
                self.stats_delta_label.setText(f"ΔT: {delta:.1f}{unit}")
        else:
            self.stats_min_label.setText("Min: --")
            self.stats_max_label.setText("Max: --")
            self.stats_avg_label.setText("Avg: --")
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
            if SpotMeterExporter.export_to_csv(spots, filepath):
                QMessageBox.information(
                    self, "Export Complete",
                    f"Exported {len(spots)} spot meters to:\n{filepath}"
                )
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
        from datetime import datetime
        
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
            
    def _on_set_alert(self):
        """Configure alert for selected spot(s). (New in Phase 6)"""
        items = self.spot_list.selectedItems()
        if not items:
            return
            
        item = items[0]
        spot_id = item.data(Qt.ItemDataRole.UserRole)
        data = self.spots.get(spot_id)
        
        if data:
            # Dialog to get threshold
            dialog = QDialog(self)
            dialog.setWindowTitle("Set Alert Threshold")
            form = QFormLayout(dialog)
            
            spin = QDoubleSpinBox()
            spin.setRange(-50, 500)
            spin.setValue(data.alert.threshold if data.alert else 30.0)
            spin.setSuffix(data.unit)
            
            type_combo = QComboBox()
            type_combo.addItems(["Above (>)", "Below (<)"])
            if data.alert and data.alert.type == 'below':
                type_combo.setCurrentIndex(1)
                
            enable_cb = QCheckBox("Enable Alert")
            enable_cb.setChecked(data.alert.enabled if data.alert else True)
            
            form.addRow("Threshold:", spin)
            form.addRow("Condition:", type_combo)
            form.addRow(enable_cb)
            
            btns = QHBoxLayout()
            ok_btn = QPushButton("OK")
            ok_btn.clicked.connect(dialog.accept)
            btns.addWidget(ok_btn)
            form.addRow(btns)
            
            if dialog.exec() == QDialog.DialogCode.Accepted:
                threshold = spin.value()
                c_type = "above" if type_combo.currentIndex() == 0 else "below"
                enabled = enable_cb.isChecked()
                
                # Apply to all selected? For now, just first one or loop
                for it in items:
                    sid = it.data(Qt.ItemDataRole.UserRole)
                    sdata = self.spots.get(sid)
                    if sdata:
                        sdata.alert = SpotMeterAlert(threshold=threshold, type=c_type, enabled=enabled)
                        logger.info(f"Alert set for {sdata.label}: {c_type} {threshold}")
                        
    def check_alerts(self, spot_id: str, temperature: float):
        """Check alert for specific spot."""
        data = self.spots.get(spot_id)
        if data and data.alert:
             if data.alert.check(temperature):
                 logger.warning(f"ALERT: {data.label} is {data.alert.type} {data.alert.threshold} (Val: {temperature})")
                 self.alert_triggered.emit(spot_id, data.alert.type, temperature)
                
    def _show_context_menu(self, position):
        """Show context menu for spot meter actions."""
        item = self.spot_list.itemAt(position)
        if not item:
            return
            
        menu = QMenu(self)
        
        rename_action = menu.addAction("✏️ Rename...")
        rename_action.triggered.connect(self._on_rename_clicked)
        
        delete_action = menu.addAction("🗑️ Delete")
        delete_action.triggered.connect(self._on_delete_clicked)
        
        menu.addSeparator()
        
        # New: Alert
        alert_action = menu.addAction("⚠️ Set Alert...")
        alert_action.triggered.connect(self._on_set_alert)
        
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
            
        menu.exec(self.spot_list.mapToGlobal(position))
        
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
