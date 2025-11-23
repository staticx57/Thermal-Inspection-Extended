# Anomaly Widget - Design Specification

**Purpose**: Centralized control panel for anomaly priority visualization system
**Location**: Right-side widget panel (or dedicated tab in multi-tab layout)
**Date Created**: 2025-11-22

---

## Widget Layout

```
┌─────────────────────────────────────────────┐
│   ANOMALY PRIORITY CONTROL                  │
├─────────────────────────────────────────────┤
│                                             │
│  ┌───────────────────────────────────────┐ │
│  │  🎯 Anomaly Priority                  │ │
│  │  [████████████████] ON                │ │
│  └───────────────────────────────────────┘ │
│                                             │
│  ┌─ ANOMALY TYPES ────────────────────────┐│
│  │                                         ││
│  │  Select which detections to highlight: ││
│  │                                         ││
│  │  ☑ Motion Detections        (12 found) ││
│  │  ☑ Edge Clusters            (8 found)  ││
│  │  ☑ Hot Spots                (5 found)  ││
│  │  ☑ Cold Spots               (3 found)  ││
│  │  ☑ Thermal Anomalies        (2 found)  ││
│  │                                         ││
│  │  Total: 30 anomalies                   ││
│  └─────────────────────────────────────────┘│
│                                             │
│  ┌─ GRADIENT FADE ────────────────────────┐│
│  │                                         ││
│  │  Fade Strength:  [▓▓▓▓▓░░░░] 1.0       ││
│  │  (0.5 soft ←──────────→ 2.0 sharp)     ││
│  │                                         ││
│  │  Fade Distance:  [▓▓▓▓▓░░░░] 100px     ││
│  │  (50px ←──────────────→ 200px)         ││
│  │                                         ││
│  │  Preview: [■■■▓▓▓▒▒▒░░░] ← gradient    ││
│  └─────────────────────────────────────────┘│
│                                             │
│  ┌─ DETECTION SETTINGS ───────────────────┐│
│  │                                         ││
│  │  [Expand/Collapse]                     ││
│  │                                         ││
│  │  Motion Threshold:    [▓▓░░] 20        ││
│  │  Edge Sensitivity:    [▓▓▓░] 50/150    ││
│  │  Hot Spot %ile:       [▓▓▓▓] 95        ││
│  │  Cold Spot %ile:      [░▓▓▓] 5         ││
│  │  Min Anomaly Size:    [▓▓░░] 400px²    ││
│  └─────────────────────────────────────────┘│
│                                             │
│  ┌─ PERFORMANCE ──────────────────────────┐│
│  │                                         ││
│  │  FPS: 28.5 (-1.5 from anomaly mode)    ││
│  │  Processing: 15.2ms per frame          ││
│  │  Overhead: ▓▓░░░░░░░░ 12%              ││
│  └─────────────────────────────────────────┘│
│                                             │
└─────────────────────────────────────────────┘
```

---

## Component Specifications

### 1. Main Toggle

**Type**: Large toggle switch or checkbox
**Label**: "🎯 Anomaly Priority"
**States**:
- OFF: Gray, text "OFF"
- ON: Green/Blue, text "ON"

**Signal**: `anomaly_priority_toggled(bool)`
**Default**: OFF

---

### 2. Anomaly Type Multi-Select

**Type**: Checkable list with live counts
**Purpose**: Enable/disable specific anomaly detection types

**Items**:
```python
[
    {"name": "Motion Detections", "key": "motion", "enabled": True},
    {"name": "Edge Clusters", "key": "edges", "enabled": True},
    {"name": "Hot Spots", "key": "hot_spots", "enabled": True},
    {"name": "Cold Spots", "key": "cold_spots", "enabled": True},
    {"name": "Thermal Anomalies", "key": "thermal_anomalies", "enabled": True}
]
```

**Features**:
- Each item has checkbox + label + live count
- "Select All" / "Deselect All" buttons (optional)
- Total anomaly count displayed below
- Counts update every frame

**Signals**:
- `anomaly_types_changed(dict)` - Emits enabled state for all types
- Example: `{"motion": True, "edges": False, "hot_spots": True, ...}`

---

### 3. Gradient Fade Controls

**Fade Strength Slider**:
- Range: 0.5 to 2.0
- Default: 1.0
- Step: 0.1
- Label: "Fade Strength"
- Tooltip: "Controls gradient steepness. Higher = sharper transition"

**Fade Distance Slider**:
- Range: 50 to 200 pixels
- Default: 100
- Step: 10
- Label: "Fade Distance"
- Tooltip: "Maximum distance for gradient fade effect"

**Gradient Preview**:
- Visual bar showing color-to-grayscale transition
- Updates in real-time as sliders move
- Shows current fade curve

**Signals**:
- `fade_strength_changed(float)` - Value 0.5-2.0
- `fade_distance_changed(int)` - Value 50-200

---

### 4. Detection Settings (Collapsible)

**Collapsed by Default**: Yes (to save space)
**Expand/Collapse**: Click header or arrow icon

**Settings**:

1. **Motion Threshold**
   - Range: 5 to 50
   - Default: 20
   - Label: "Motion Sensitivity"
   - Signal: `motion_threshold_changed(int)`

2. **Edge Sensitivity**
   - Two sliders: Low (10-100) and High (50-200)
   - Default: 50/150
   - Label: "Edge Detection"
   - Signal: `edge_thresholds_changed(int, int)`

3. **Hot Spot Percentile**
   - Range: 85 to 99
   - Default: 95
   - Label: "Hot Spot Threshold"
   - Signal: `hot_spot_percentile_changed(int)`

4. **Cold Spot Percentile**
   - Range: 1 to 15
   - Default: 5
   - Label: "Cold Spot Threshold"
   - Signal: `cold_spot_percentile_changed(int)`

5. **Minimum Anomaly Size**
   - Range: 100 to 2000 pixels²
   - Default: 400
   - Label: "Min Size Filter"
   - Signal: `min_anomaly_size_changed(int)`

---

### 5. Performance Display

**Type**: Read-only status display
**Updates**: Every frame

**Metrics**:
- Current FPS
- FPS impact (difference from baseline)
- Processing time per frame (ms)
- Overhead percentage bar

**Color Coding**:
- Green: < 10% overhead
- Yellow: 10-20% overhead
- Red: > 20% overhead

---

## Implementation Details

### PyQt6 Widgets to Use

```python
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QCheckBox, QSlider, QLabel, QPushButton,
    QGroupBox, QProgressBar, QSpinBox
)
from PyQt6.QtCore import pyqtSignal, Qt
```

### Class Structure

```python
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
        self._init_ui()
        self._connect_signals()

        # State
        self.enabled_types = {
            "motion": True,
            "edges": True,
            "hot_spots": True,
            "cold_spots": True,
            "thermal_anomalies": True
        }

    def _init_ui(self):
        """Initialize widget UI components."""
        layout = QVBoxLayout(self)

        # 1. Main toggle
        self._create_main_toggle(layout)

        # 2. Anomaly types
        self._create_type_selector(layout)

        # 3. Gradient controls
        self._create_gradient_controls(layout)

        # 4. Detection settings (collapsible)
        self._create_detection_settings(layout)

        # 5. Performance display
        self._create_performance_display(layout)

    def update_counts(self, counts: dict):
        """Update live anomaly counts.

        Args:
            counts: Dict with keys matching enabled_types
        """
        pass

    def update_performance(self, fps: float, processing_time: float):
        """Update performance metrics."""
        pass
```

---

## Integration with Main App

### inspection_main.py Changes

```python
class InspectionMain:
    def __init__(self):
        # ...existing code...

        # Anomaly type filtering
        self.enabled_anomaly_types = {
            "motion": True,
            "edges": True,
            "hot_spots": True,
            "cold_spots": True,
            "thermal_anomalies": True
        }

    def _process_thermal_frame(self, thermal_frame, rgb_frame):
        # ...existing detection code...

        # Filter anomalies by enabled types (NEW)
        if self.thermal_processor.anomaly_priority_enabled:
            all_anomalies = []

            # Add only enabled types
            if self.enabled_anomaly_types["motion"]:
                all_anomalies.extend(result['motion_detections'])

            if self.enabled_anomaly_types["edges"]:
                all_anomalies.extend(result['edge_clusters'])

            if self.enabled_anomaly_types["hot_spots"]:
                all_anomalies.extend(result['hot_spots'])

            if self.enabled_anomaly_types["cold_spots"]:
                all_anomalies.extend(result['cold_spots'])

            if self.enabled_anomaly_types["thermal_anomalies"]:
                all_anomalies.extend(result['anomalies'])

            # Apply gradient fade with filtered anomalies
            thermal_colorized = self.thermal_processor.apply_anomaly_priority_colorization(
                thermal_frame, all_anomalies, thermal_colorized
            )
```

### Signal Connections

```python
# In InspectionAppWindow or InspectionMain
self.anomaly_widget.anomaly_types_changed.connect(self._on_anomaly_types_changed)
self.anomaly_widget.fade_strength_changed.connect(self._on_fade_strength_changed)
self.anomaly_widget.fade_distance_changed.connect(self._on_fade_distance_changed)

def _on_anomaly_types_changed(self, types_dict: dict):
    """Handle anomaly type selection changes."""
    self.enabled_anomaly_types = types_dict
    logger.info(f"Anomaly types updated: {types_dict}")

def _on_fade_strength_changed(self, value: float):
    """Update fade strength parameter."""
    if self.thermal_processor:
        self.thermal_processor.anomaly_fade_strength = value

def _on_fade_distance_changed(self, value: int):
    """Update fade distance parameter."""
    if self.thermal_processor:
        self.thermal_processor.anomaly_max_distance = value
```

---

## Testing Checklist

- [ ] Widget displays correctly in right panel
- [ ] Main toggle enables/disables anomaly priority
- [ ] Checkboxes filter anomaly types correctly
- [ ] Live counts update every frame
- [ ] Sliders update gradient fade in real-time
- [ ] Detection settings affect anomaly detection
- [ ] Performance metrics are accurate
- [ ] All signals emit correctly
- [ ] Widget persists settings across sessions
- [ ] Responsive to theme changes
- [ ] Tooltips are helpful and accurate

---

## Future Enhancements

1. **Presets**: Save/load anomaly configuration presets
2. **Per-Type Colors**: Different colors for different anomaly types
3. **Anomaly Visualization**: Mini-map showing anomaly locations
4. **Export**: Export anomaly statistics to CSV
5. **Alerts**: Trigger alerts when specific anomaly counts exceeded
6. **ROI Integration**: Per-ROI anomaly type filtering

---

**Status**: Specification Complete
**Ready for Implementation**: Yes
**Estimated Effort**: 3-4 hours
**Priority**: HIGH
