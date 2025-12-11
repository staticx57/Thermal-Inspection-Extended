# Enhancement #12: Spot Meter Management and Data Export - Implementation Plan

> **Thermal Inspection Application**  
> Created: December 2024

This document provides a detailed implementation roadmap for Enhancement #12, which extends the existing spot metering functionality (Enhancement #1) with a full management panel, data export capabilities, and advanced features.

---

## Table of Contents

1. [Current Implementation Analysis](#current-implementation-analysis)
2. [Phase 1: SpotMeterPanel Widget](#phase-1-spotmeterpanel-widget)
3. [Phase 2: Selection and Navigation](#phase-2-selection-and-navigation)
4. [Phase 3: Spot Meter Actions](#phase-3-spot-meter-actions)
5. [Phase 4: Statistics Display](#phase-4-statistics-display)
6. [Phase 5: Data Export and Logging](#phase-5-data-export-and-logging)
7. [Phase 6: Advanced Features](#phase-6-advanced-features)
8. [Files to Create/Modify](#files-to-createmodify)
9. [Priority Matrix](#priority-matrix)
10. [Verification Plan](#verification-plan)

---

## Current Implementation Analysis

### Existing Spot Meter Features (Enhancement #1)

The application already has basic spot metering from Enhancement #1:

| Feature | Location | Status |
|---------|----------|--------|
| Add spot meter (click on video) | `InspectionOverlayWidget.mousePressEvent()` | ✅ Complete |
| Toggle spot meter mode | `RadiometricPanel.add_spot_meter_btn` | ✅ Complete |
| Clear all spot meters | `RadiometricPanel.clear_spot_meters_btn` | ✅ Complete |
| Spot meter overlay drawing | `InspectionOverlayWidget.paintEvent()` | ✅ Complete |
| Temperature reading updates | `inspection_main.py:process_frame()` | ✅ Complete |
| 3-tier fallback (16-bit/8-bit/raw) | `inspection_main.py:1781-1801` | ✅ Complete |

### Key Files

| File | Purpose |
|------|---------|
| `inspection_gui_qt.py` | `InspectionOverlayWidget` - renders spot meters on video |
| `radiometric_panel.py` | Basic add/clear buttons |
| `inspection_main.py` | Temperature extraction and updates |
| `measurement_points.py` | `MeasurementPoint` data class |

### Current Data Structures

```python
# measurement_points.py
@dataclass
class MeasurementPoint:
    x: int                          # Frame coordinate
    y: int                          # Frame coordinate
    label: str = ""                 # Display label (e.g., "Spot #1")
    temperature: Optional[float] = None
    unit: str = "°C"
    color: Tuple[int, int, int] = (255, 255, 0)  # Yellow default
    timestamp: float = field(default_factory=time.time)
```

---

## Phase 1: SpotMeterPanel Widget

### Goal
Create a dedicated panel in the Analysis > General tab (or new Spot Meters tab) for managing all spot meters.

### 1.1 Create SpotMeterPanel Widget

**File: `spot_meter_panel.py` (NEW)**

```python
#!/usr/bin/env python3
"""
Spot Meter Management Panel
Provides UI for viewing and managing all active spot meters.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QGroupBox, QMenu, QInputDialog,
    QMessageBox, QFrame, QSplitter, QAbstractItemView
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QColor, QIcon, QAction
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
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
    color: Tuple[int, int, int] = (255, 255, 0)  # Marker color
    visible: bool = True                 # Visibility toggle
    locked: bool = False                 # Position lock
    created_at: float = 0.0              # Creation timestamp
    updated_at: float = 0.0              # Last temperature update
    history: List[Tuple[float, float]] = None  # (timestamp, temp) history
    
    def __post_init__(self):
        if self.history is None:
            self.history = []
        if self.created_at == 0.0:
            self.created_at = time.time()


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
            
        # Format label with visibility/lock indicators
        indicators = ""
        if not data.visible:
            indicators += "👁️‍🗨️ "  # Hidden indicator
        if data.locked:
            indicators += "🔒 "  # Locked indicator
            
        # Build display text
        display_text = f"{indicators}{data.label}: {temp_str}  ({data.x}, {data.y})"
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
        self._connect_signals()
        
    def _setup_ui(self):
        """Build the panel UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(8)
        
        # Title
        title = QLabel("Spot Meters")
        title.setStyleSheet("font-weight: bold; font-size: 13px;")
        layout.addWidget(title)
        
        # Spot meter list
        self.spot_list = QListWidget()
        self.spot_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.spot_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.spot_list.customContextMenuRequested.connect(self._show_context_menu)
        self.spot_list.itemDoubleClicked.connect(self._on_item_double_clicked)
        self.spot_list.itemSelectionChanged.connect(self._on_selection_changed)
        layout.addWidget(self.spot_list, stretch=1)
        
        # Action buttons row 1
        btn_row1 = QHBoxLayout()
        
        self.rename_btn = QPushButton("Rename")
        self.rename_btn.setToolTip("Rename selected spot meter")
        self.rename_btn.clicked.connect(self._on_rename_clicked)
        btn_row1.addWidget(self.rename_btn)
        
        self.delete_btn = QPushButton("Delete")
        self.delete_btn.setToolTip("Delete selected spot meter(s)")
        self.delete_btn.clicked.connect(self._on_delete_clicked)
        btn_row1.addWidget(self.delete_btn)
        
        self.clear_btn = QPushButton("Clear All")
        self.clear_btn.setToolTip("Remove all spot meters")
        self.clear_btn.clicked.connect(self._on_clear_clicked)
        btn_row1.addWidget(self.clear_btn)
        
        layout.addLayout(btn_row1)
        
        # Action buttons row 2
        btn_row2 = QHBoxLayout()
        
        self.toggle_visibility_btn = QPushButton("👁️ Toggle")
        self.toggle_visibility_btn.setToolTip("Show/hide selected spot meter")
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
        layout.addWidget(line)
        
        # Statistics section
        stats_group = QGroupBox("Statistics")
        stats_layout = QVBoxLayout(stats_group)
        
        self.stats_count_label = QLabel("Count: 0")
        stats_layout.addWidget(self.stats_count_label)
        
        self.stats_min_label = QLabel("Min: --")
        stats_layout.addWidget(self.stats_min_label)
        
        self.stats_max_label = QLabel("Max: --")
        stats_layout.addWidget(self.stats_max_label)
        
        self.stats_avg_label = QLabel("Avg: --")
        stats_layout.addWidget(self.stats_avg_label)
        
        self.stats_delta_label = QLabel("ΔT: --")
        self.stats_delta_label.setToolTip("Temperature difference between hottest and coldest spots")
        stats_layout.addWidget(self.stats_delta_label)
        
        layout.addWidget(stats_group)
        
        # Export buttons
        export_row = QHBoxLayout()
        
        self.export_csv_btn = QPushButton("Export CSV")
        self.export_csv_btn.clicked.connect(lambda: self.export_requested.emit('csv'))
        export_row.addWidget(self.export_csv_btn)
        
        self.export_json_btn = QPushButton("Export JSON")
        self.export_json_btn.clicked.connect(lambda: self.export_requested.emit('json'))
        export_row.addWidget(self.export_json_btn)
        
        layout.addLayout(export_row)
        
        # Initial button state
        self._update_button_states()
        
    def _connect_signals(self):
        """Connect internal signals."""
        pass
        
    def add_spot(self, spot_id: str, x: int, y: int, label: str = None,
                 color: Tuple[int, int, int] = (255, 255, 0)):
        """Add a new spot meter to the panel."""
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
        
    def remove_spot(self, spot_id: str):
        """Remove a spot meter from the panel."""
        if spot_id not in self.spots:
            return
            
        del self.spots[spot_id]
        
        # Find and remove list item
        for i in range(self.spot_list.count()):
            item = self.spot_list.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == spot_id:
                self.spot_list.takeItem(i)
                break
                
        self._update_statistics()
        self._update_button_states()
        
    def update_temperature(self, spot_id: str, temperature: float, unit: str = "°C"):
        """Update temperature reading for a spot meter."""
        if spot_id not in self.spots:
            return
            
        data = self.spots[spot_id]
        data.temperature = temperature
        data.unit = unit
        data.updated_at = time.time()
        
        # Add to history (keep last 1000 readings)
        data.history.append((data.updated_at, temperature))
        if len(data.history) > 1000:
            data.history.pop(0)
        
        # Update list item display
        for i in range(self.spot_list.count()):
            item = self.spot_list.item(i)
            if isinstance(item, SpotMeterListItem) and item.spot_data.id == spot_id:
                item.spot_data = data
                item.update_display()
                break
                
        self._update_statistics()
        
    def update_spot_temperatures(self, values: List[Dict]):
        """Batch update temperatures from main loop.
        
        Args:
            values: List of {'label': str, 'temperature': float, 'unit': str}
        """
        for val in values:
            # Find spot by label
            for spot_id, data in self.spots.items():
                if data.label == val.get('label'):
                    self.update_temperature(
                        spot_id, 
                        val.get('temperature'), 
                        val.get('unit', '°C')
                    )
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
                
    def _show_context_menu(self, position):
        """Show context menu for spot meter actions."""
        item = self.spot_list.itemAt(position)
        if not item:
            return
            
        menu = QMenu(self)
        
        rename_action = menu.addAction("Rename...")
        rename_action.triggered.connect(self._on_rename_clicked)
        
        delete_action = menu.addAction("Delete")
        delete_action.triggered.connect(self._on_delete_clicked)
        
        menu.addSeparator()
        
        spot_id = item.data(Qt.ItemDataRole.UserRole)
        data = self.spots.get(spot_id)
        
        if data:
            visibility_text = "Hide" if data.visible else "Show"
            visibility_action = menu.addAction(f"{visibility_text}")
            visibility_action.triggered.connect(self._on_toggle_visibility)
            
            lock_text = "Unlock" if data.locked else "Lock Position"
            lock_action = menu.addAction(lock_text)
            lock_action.triggered.connect(self._on_toggle_lock)
            
        menu.exec(self.spot_list.mapToGlobal(position))
        
    def get_all_spots(self) -> List[SpotMeterData]:
        """Get all spot meter data for export."""
        return list(self.spots.values())
        
    def clear(self):
        """Clear all spot meters (for external use)."""
        self.spots.clear()
        self.spot_list.clear()
        self._update_statistics()
        self._update_button_states()
```

### 1.2 Integrate into Analysis Tab

**Modify: `inspection_gui_qt.py`**

Add `SpotMeterPanel` to the Analysis > General tab or create new "Spot Meters" sub-tab:

```python
# In ThermalAnalysisPanel or AnalysisGeneralTab

from spot_meter_panel import SpotMeterPanel

# In _setup_ui():
self.spot_meter_panel = SpotMeterPanel()
# Add to layout or as new tab in the analysis section
```

---

## Phase 2: Selection and Navigation

### Goal
Enable bidirectional selection between the list panel and the video overlay.

### 2.1 Click Spot in List → Highlight on Video

```python
# In SpotMeterPanel
self.spot_list.itemSelectionChanged.connect(self._on_selection_changed)

def _on_selection_changed(self):
    items = self.spot_list.selectedItems()
    if items:
        spot_id = items[0].data(Qt.ItemDataRole.UserRole)
        self.highlight_spot.emit(spot_id)  # → InspectionOverlayWidget
```

```python
# In InspectionOverlayWidget
def highlight_spot_meter(self, spot_id: str):
    """Temporarily highlight a spot meter with animation."""
    self.highlighted_spot_id = spot_id
    self.highlight_timer = QTimer.singleShot(2000, self._clear_highlight)
    self.update()
```

### 2.2 Click Spot on Video → Select in List

```python
# In InspectionOverlayWidget.mousePressEvent()
# After creating spot meter, emit signal with spot ID
self.spot_meter_selected.emit(spot_id)

# In InspectionAppWindow
spot_meter_panel.select_spot(spot_id)
```

### 2.3 Keyboard Navigation

```python
# In SpotMeterPanel
def keyPressEvent(self, event):
    if event.key() == Qt.Key.Key_Delete:
        self._on_delete_clicked()
    elif event.key() == Qt.Key.Key_F2:
        self._on_rename_clicked()
```

---

## Phase 3: Spot Meter Actions

### Goal
Implement rename, delete, visibility, and position lock features.

### 3.1 Rename (Double-click or Context Menu)

Already implemented in `SpotMeterPanel._on_rename_clicked()`.

### 3.2 Delete Individual / Clear All

Already implemented in `SpotMeterPanel._on_delete_clicked()` and `_on_clear_clicked()`.

### 3.3 Toggle Visibility

```python
# In InspectionOverlayWidget.paintEvent():
for point in self.measurement_points:
    if not getattr(point, 'visible', True):
        continue  # Skip hidden spots
    # ... draw spot
```

### 3.4 Lock Position

```python
# In InspectionOverlayWidget - prevent dragging locked spots
def mousePressEvent(self, event):
    if self.dragging_spot:
        spot_data = self.get_spot_data(self.dragging_spot_id)
        if spot_data and spot_data.locked:
            return  # Don't allow dragging
```

---

## Phase 4: Statistics Display

### Goal
Show aggregate statistics across all spot meters.

### 4.1 Min/Max/Average

Already implemented in `SpotMeterPanel._update_statistics()`.

### 4.2 Delta (ΔT)

Already implemented - shows difference between hottest and coldest spots.

### 4.3 Trend Indicator

Add trend calculation based on history:

```python
def _calculate_trend(self, data: SpotMeterData) -> str:
    """Calculate temperature trend for a spot meter."""
    if len(data.history) < 2:
        return "stable"
        
    # Compare last 5 readings average vs previous 5
    recent = [t for _, t in data.history[-5:]]
    previous = [t for _, t in data.history[-10:-5]] if len(data.history) >= 10 else recent
    
    recent_avg = sum(recent) / len(recent)
    previous_avg = sum(previous) / len(previous)
    
    diff = recent_avg - previous_avg
    
    if diff > 0.5:
        return "rising"    # ↑
    elif diff < -0.5:
        return "falling"   # ↓
    else:
        return "stable"    # →
```

Update list item display to show trend arrow:

```python
def update_display(self):
    # ... existing code ...
    trend = self._calculate_trend(self.spot_data)
    trend_icon = {"rising": "↑", "falling": "↓", "stable": "→"}.get(trend, "")
    display_text = f"{indicators}{data.label}: {temp_str} {trend_icon}  ({data.x}, {data.y})"
```

---

## Phase 5: Data Export and Logging

### Goal
Enable export of spot meter data to files and session logs.

### 5.1 Export to CSV

**File: `spot_meter_exporter.py` (NEW)**

```python
#!/usr/bin/env python3
"""
Spot Meter Data Export Utilities
"""

import csv
import json
from datetime import datetime
from typing import List, Dict
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class SpotMeterExporter:
    """Export spot meter data to various formats."""
    
    @staticmethod
    def export_to_csv(spots: List, filepath: str) -> bool:
        """Export spot meter data to CSV file.
        
        Args:
            spots: List of SpotMeterData objects
            filepath: Output file path
            
        Returns:
            True if successful
        """
        try:
            with open(filepath, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                
                # Header
                writer.writerow([
                    'ID', 'Label', 'X', 'Y', 
                    'Temperature', 'Unit',
                    'Created', 'Last Updated',
                    'Visible', 'Locked'
                ])
                
                # Data rows
                for spot in spots:
                    writer.writerow([
                        spot.id,
                        spot.label,
                        spot.x,
                        spot.y,
                        spot.temperature if spot.temperature is not None else '',
                        spot.unit,
                        datetime.fromtimestamp(spot.created_at).isoformat(),
                        datetime.fromtimestamp(spot.updated_at).isoformat() if spot.updated_at else '',
                        spot.visible,
                        spot.locked
                    ])
                    
            logger.info(f"Exported {len(spots)} spot meters to {filepath}")
            return True
            
        except Exception as e:
            logger.error(f"CSV export failed: {e}")
            return False
            
    @staticmethod
    def export_to_json(spots: List, filepath: str, include_history: bool = True) -> bool:
        """Export spot meter data to JSON file.
        
        Args:
            spots: List of SpotMeterData objects
            filepath: Output file path
            include_history: Include temperature history
            
        Returns:
            True if successful
        """
        try:
            data = {
                'export_time': datetime.now().isoformat(),
                'spot_count': len(spots),
                'spots': []
            }
            
            for spot in spots:
                spot_data = {
                    'id': spot.id,
                    'label': spot.label,
                    'coordinates': {'x': spot.x, 'y': spot.y},
                    'temperature': spot.temperature,
                    'unit': spot.unit,
                    'color': list(spot.color),
                    'visible': spot.visible,
                    'locked': spot.locked,
                    'created_at': datetime.fromtimestamp(spot.created_at).isoformat(),
                    'updated_at': datetime.fromtimestamp(spot.updated_at).isoformat() if spot.updated_at else None
                }
                
                if include_history and spot.history:
                    spot_data['history'] = [
                        {'timestamp': datetime.fromtimestamp(ts).isoformat(), 'temperature': temp}
                        for ts, temp in spot.history
                    ]
                    
                data['spots'].append(spot_data)
                
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
                
            logger.info(f"Exported {len(spots)} spot meters to {filepath}")
            return True
            
        except Exception as e:
            logger.error(f"JSON export failed: {e}")
            return False
            
    @staticmethod
    def export_history_to_csv(spots: List, filepath: str) -> bool:
        """Export temperature history to CSV for graphing.
        
        Creates a time-series format with columns for each spot meter.
        """
        try:
            # Collect all unique timestamps
            all_timestamps = set()
            for spot in spots:
                for ts, _ in spot.history:
                    all_timestamps.add(ts)
                    
            all_timestamps = sorted(all_timestamps)
            
            with open(filepath, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                
                # Header: Timestamp, Spot1, Spot2, ...
                header = ['Timestamp'] + [spot.label for spot in spots]
                writer.writerow(header)
                
                # Create lookup for each spot's history
                spot_histories = {}
                for spot in spots:
                    spot_histories[spot.id] = dict(spot.history)
                    
                # Data rows
                for ts in all_timestamps:
                    row = [datetime.fromtimestamp(ts).isoformat()]
                    for spot in spots:
                        temp = spot_histories[spot.id].get(ts, '')
                        row.append(temp if temp != '' else '')
                    writer.writerow(row)
                    
            logger.info(f"Exported history to {filepath}")
            return True
            
        except Exception as e:
            logger.error(f"History export failed: {e}")
            return False
```

### 5.2 Add to Snapshot Metadata

**Modify: `media_recorder.py`**

```python
class SnapshotManager:
    def save_snapshot(self, frame, metadata: dict = None, spot_meters: list = None):
        # ... existing code ...
        
        # Add spot meter data to metadata
        if spot_meters:
            metadata['spot_meters'] = [
                {
                    'label': s.label,
                    'x': s.x, 'y': s.y,
                    'temperature': s.temperature,
                    'unit': s.unit
                }
                for s in spot_meters
            ]
            
        # Write metadata JSON alongside image
        meta_path = image_path.replace('.png', '_metadata.json')
        with open(meta_path, 'w') as f:
            json.dump(metadata, f, indent=2)
```

### 5.3 Real-time Logging (Optional)

```python
class SpotMeterLogger:
    """Continuous logging of spot meter readings to file."""
    
    def __init__(self, filepath: str, interval_seconds: float = 1.0):
        self.filepath = filepath
        self.interval = interval_seconds
        self.running = False
        self.last_log_time = 0
        
        # Create file with header
        with open(filepath, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['Timestamp', 'SpotID', 'Label', 'Temperature', 'Unit'])
            
    def log(self, spots: List):
        """Log current spot meter readings if interval has passed."""
        current_time = time.time()
        if current_time - self.last_log_time < self.interval:
            return
            
        self.last_log_time = current_time
        timestamp = datetime.now().isoformat()
        
        with open(self.filepath, 'a', newline='') as f:
            writer = csv.writer(f)
            for spot in spots:
                if spot.temperature is not None:
                    writer.writerow([
                        timestamp,
                        spot.id,
                        spot.label,
                        spot.temperature,
                        spot.unit
                    ])
```

---

## Phase 6: Advanced Features

### Goal
Implement preset templates, compare mode, alerts, and history graph.

### 6.1 Preset Templates (e.g., "9-point grid")

```python
class SpotMeterPresets:
    """Pre-defined spot meter patterns."""
    
    PRESETS = {
        '3x3 Grid': lambda w, h: [
            (w//4, h//4), (w//2, h//4), (3*w//4, h//4),
            (w//4, h//2), (w//2, h//2), (3*w//4, h//2),
            (w//4, 3*h//4), (w//2, 3*h//4), (3*w//4, 3*h//4),
        ],
        'Center + Corners': lambda w, h: [
            (w//2, h//2),  # Center
            (w//8, h//8), (7*w//8, h//8),  # Top corners
            (w//8, 7*h//8), (7*w//8, 7*h//8),  # Bottom corners
        ],
        'Horizontal Line': lambda w, h: [
            (w//5, h//2), (2*w//5, h//2), (3*w//5, h//2), (4*w//5, h//2),
        ],
        'Vertical Line': lambda w, h: [
            (w//2, h//5), (w//2, 2*h//5), (w//2, 3*h//5), (w//2, 4*h//5),
        ],
    }
    
    @classmethod
    def apply_preset(cls, preset_name: str, frame_width: int, frame_height: int):
        """Get coordinates for a preset pattern."""
        generator = cls.PRESETS.get(preset_name)
        if generator:
            return generator(frame_width, frame_height)
        return []
```

### 6.2 Compare Mode (ΔT between two spots)

```python
# Add to SpotMeterPanel
def enable_compare_mode(self):
    """Enable mode to track temperature difference between two spots."""
    self.compare_mode = True
    self.compare_spots = []  # Will hold exactly 2 spot IDs
    
def _update_compare_display(self):
    """Update the compare mode display."""
    if len(self.compare_spots) == 2:
        spot1 = self.spots.get(self.compare_spots[0])
        spot2 = self.spots.get(self.compare_spots[1])
        
        if spot1 and spot2 and spot1.temperature and spot2.temperature:
            delta = abs(spot1.temperature - spot2.temperature)
            self.compare_label.setText(
                f"Compare: {spot1.label} vs {spot2.label} = Δ{delta:.1f}{spot1.unit}"
            )
```

### 6.3 Alert Thresholds

```python
@dataclass
class SpotMeterAlert:
    spot_id: str
    threshold_type: str  # 'above', 'below'
    threshold_value: float
    enabled: bool = True
    triggered: bool = False
    
class AlertManager:
    def check_alerts(self, spots: List[SpotMeterData], alerts: List[SpotMeterAlert]):
        """Check all alerts and emit signals for triggered ones."""
        triggered = []
        
        for alert in alerts:
            if not alert.enabled:
                continue
                
            spot = next((s for s in spots if s.id == alert.spot_id), None)
            if not spot or spot.temperature is None:
                continue
                
            if alert.threshold_type == 'above' and spot.temperature > alert.threshold_value:
                if not alert.triggered:
                    triggered.append((alert, spot))
                    alert.triggered = True
            elif alert.threshold_type == 'below' and spot.temperature < alert.threshold_value:
                if not alert.triggered:
                    triggered.append((alert, spot))
                    alert.triggered = True
            else:
                alert.triggered = False  # Reset when condition clears
                
        return triggered
```

### 6.4 Temperature History Graph (Optional)

Use PyQtGraph for real-time charting:

```python
from pyqtgraph import PlotWidget, mkPen

class SpotMeterHistoryGraph(QWidget):
    """Real-time temperature history graph for spot meters."""
    
    def __init__(self):
        super().__init__()
        self.plot = PlotWidget()
        self.curves = {}  # spot_id -> PlotCurve
        
        layout = QVBoxLayout(self)
        layout.addWidget(self.plot)
        
        self.plot.setLabel('left', 'Temperature', units='°C')
        self.plot.setLabel('bottom', 'Time', units='s')
        self.plot.addLegend()
        
    def update_spot_data(self, spot_id: str, history: List[Tuple[float, float]], 
                         label: str, color: Tuple[int, int, int]):
        """Update graph with new spot meter history."""
        if spot_id not in self.curves:
            pen = mkPen(color=color, width=2)
            self.curves[spot_id] = self.plot.plot([], [], name=label, pen=pen)
            
        # Convert timestamps to relative seconds
        if history:
            base_time = history[0][0]
            x_data = [t - base_time for t, _ in history]
            y_data = [temp for _, temp in history]
            self.curves[spot_id].setData(x_data, y_data)
```

---

## Files to Create/Modify

| Action | File | Purpose |
|--------|------|---------|
| **CREATE** | `spot_meter_panel.py` | Management panel widget |
| **CREATE** | `spot_meter_exporter.py` | CSV/JSON export utilities |
| MODIFY | `inspection_gui_qt.py` | Integrate panel, handle signals |
| MODIFY | `measurement_points.py` | Add visibility/lock/history fields |
| MODIFY | `inspection_main.py` | Wire export to snapshot, logging |
| MODIFY | `media_recorder.py` | Include spot data in snapshots |
| MODIFY | `radiometric_panel.py` | Add preset dropdown (optional) |

---

## Priority Matrix

| Priority | Feature | Effort | Impact |
|----------|---------|--------|--------|
| 🔴 **HIGH** | Phase 1: SpotMeterPanel | 4-6 hrs | Core management UI |
| 🔴 **HIGH** | Phase 2: Selection sync | 2-3 hrs | Usability |
| 🔴 **HIGH** | Phase 5: CSV/JSON export | 2-3 hrs | Data capture |
| 🟡 MEDIUM | Phase 3: All actions | 2-3 hrs | Full control |
| 🟡 MEDIUM | Phase 4: Statistics | 1-2 hrs | Quick insights |
| 🟢 LOW | Phase 6.1: Presets | 1-2 hrs | Convenience |
| 🟢 LOW | Phase 6.2: Compare mode | 2-3 hrs | Analysis |
| 🟢 LOW | Phase 6.3: Alerts | 3-4 hrs | Automation |
| 🟢 LOW | Phase 6.4: History graph | 4-6 hrs | Visualization |

---

## Verification Plan

### Functional Tests

| Feature | Test |
|---------|------|
| Add spot meter | Click on video → appears in list |
| Remove spot meter | Select and delete → removed from list and video |
| Rename spot meter | Double-click → enter new name → updated |
| Toggle visibility | Click eye icon → spot hidden/shown |
| Lock position | Lock button → cannot drag spot |
| Statistics | Add 3 spots → verify min/max/avg correct |
| Export CSV | Export → open file → verify data correct |
| Export JSON | Export → validate JSON schema |
| Selection sync | Click list → video highlights; click video → list selects |

### Integration Tests

1. Add 5 spot meters, rename 2, delete 1
2. Export to CSV and JSON, verify data
3. Take snapshot, verify metadata includes spots
4. Toggle visibility on 2 spots, verify overlay
5. Lock 1 spot, verify cannot move

### Performance Tests

1. Add 50 spot meters, verify no UI lag
2. Run with real-time logging for 5 minutes
3. Export history with 1000+ readings per spot

---

## Next Steps

1. **Create `spot_meter_panel.py`** with basic list and statistics
2. **Integrate into `inspection_gui_qt.py`** Analysis tab
3. **Connect signals** between panel, overlay, and main app
4. **Create `spot_meter_exporter.py`** for CSV/JSON export
5. **Add export buttons** and file dialogs
6. **Test end-to-end** with real camera

---

*Document created: December 2024*  
*Extends Enhancement #1 (User-defined spot metering)*
