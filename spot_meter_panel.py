#!/usr/bin/env python3
"""
Spot Meter Management Panel
Provides UI for viewing and managing all active spot meters.

Part of Enhancement #12: Spot Meter Management and Data Export
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QGroupBox, QMenu, QInputDialog,
    QMessageBox, QFrame, QAbstractItemView, QFileDialog
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QColor, QAction
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
import time
import logging

logger = logging.getLogger(__name__)


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
        
        # Set color indicator
        r, g, b = data.color
        self.setForeground(QColor(r, g, b))


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
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.spots: Dict[str, SpotMeterData] = {}
        self._setup_ui()
        
    def _setup_ui(self):
        """Build the panel UI."""
        layout = QVBoxLayout(self)
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
        
        # Initial button state
        self._update_button_states()
        
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
        
        # Update list item display
        self._refresh_list_item(spot_id)
        self._update_statistics()
        
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
