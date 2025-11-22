# Thermal Inspection Extended - TODO List

**Project**: Thermal Inspection Tool with PyQt6 GUI
**Last Updated**: 2025-11-21
**Current Version**: In Development

---

## ✅ Completed Tasks

### GUI Theme System
- [x] **Fix solarized theme text colors**
  - Fixed CSS syntax error on line 373 (extra colon in border property)
  - File: `inspection_gui_qt.py:373`
  - Status: COMPLETE

- [x] **Widget box theme cycling**
  - Added `QWidget { background-color: ... }` to all 4 themes
  - DARK_THEME: #1a1a1a
  - LIGHT_THEME: #f5f5f5
  - SOLARIZED_THEME: #fdf6e3
  - COLORFUL_THEME: #0f1e2e
  - Files: `inspection_gui_qt.py` (lines 44-46, 199-201, 356-358, 435-437)
  - Status: COMPLETE

---

## 🔄 In Progress

### Anomaly Priority Feature
- [ ] **Add anomaly priority as global toggle button** (IN PROGRESS)
  - [x] Created `anomaly_priority_toggled` pyqtSignal in ControlPanel
  - [x] Added anomaly priority button to Row 3 (processing controls) at column 3
  - [x] Button is checkable with initial state OFF
  - [x] Connected button signal to `anomaly_priority_toggled.emit()`
  - [x] Added `update_anomaly_priority_button(enabled: bool)` method
  - [x] Button text: "🎯 Anomaly: ON" / "🎯 Anomaly: OFF"
  - [ ] **NEXT**: Wire up signal handler in `inspection_main.py`
  - [ ] Add `anomaly_priority_enabled` state flag
  - [ ] Update button text when toggled
  - Files:
    - Modified: `inspection_gui_qt.py` (lines 1026, 1091-1093, 1098, 1138, 1213-1218)
  - Priority: HIGH
  - Status: 70% COMPLETE (GUI done, needs backend wiring)

---

## 📋 Pending Tasks

### Priority 1: Complete Anomaly Priority Feature

#### Task 1.1: Connect Button in inspection_main.py
- [ ] **Wire anomaly priority signal to handler**
  - Connect `ControlPanel.anomaly_priority_toggled` signal to handler method
  - Add `self.anomaly_priority_enabled = False` to InspectionMain state
  - Handler should:
    - Update `self.anomaly_priority_enabled` flag
    - Call `control_panel.update_anomaly_priority_button(enabled)`
    - Log state change
  - Files to modify: `inspection_main.py`
  - Estimated effort: 30 minutes
  - Priority: HIGH

#### Task 1.2: Implement Gradient Fade Algorithm
- [ ] **Create anomaly-aware colorization in thermal_processor.py**
  - Method: `apply_anomaly_priority_colorization(thermal_frame, anomalies, palette_type)`
  - Steps:
    1. Create binary mask from anomaly bounding boxes
    2. Apply distance transform to get distance from anomalies
    3. Normalize distance to 0-1 range (0=anomaly, 1=far from anomaly)
    4. For each pixel:
       - If anomaly region: apply full color palette
       - If non-anomaly: blend colored palette with grayscale based on distance
       - Gradient formula: `color_weight = 1.0 - (distance * fade_factor)`
    5. Return blended frame
  - Parameters:
    - `fade_factor`: Controls gradient steepness (0.5-2.0 range)
    - `max_fade_distance`: Max pixel distance for gradient (50-200px)
  - Files to create/modify: `thermal_processor.py`
  - Estimated effort: 2-3 hours
  - Priority: HIGH
  - Dependencies: Task 1.1 complete

#### Task 1.3: Integrate with Processing Pipeline
- [ ] **Apply anomaly priority mode in frame processing**
  - In `inspection_main.py` processing loop:
    - Check `if self.anomaly_priority_enabled:`
    - Call anomaly priority colorization AFTER palette application
    - Pass `self.latest_anomalies` to colorization function
  - Apply to ALL thermal views:
    - Thermal view
    - Fusion views (where thermal contributes)
    - Quad view (thermal quadrant)
  - Files to modify: `inspection_main.py`, `thermal_processor.py`
  - Estimated effort: 1-2 hours
  - Priority: HIGH
  - Dependencies: Task 1.2 complete

#### Task 1.4: Test Across All Views
- [ ] **Verify anomaly priority works in all display modes**
  - Test scenarios:
    1. Thermal-only view
    2. Each fusion mode (alpha_blend, edge_enhanced, thermal_overlay, etc.)
    3. Quad view
    4. Side-by-side view
    5. Picture-in-picture
  - Verify:
    - Gradient fade is smooth and natural
    - Performance impact <10% FPS
    - Anomalies clearly highlighted
    - Non-anomaly areas properly desaturated
    - Toggle on/off works instantly
  - Files: Integration testing
  - Estimated effort: 1-2 hours
  - Priority: HIGH
  - Dependencies: Task 1.3 complete

---

### Priority 2: ROI Enhancements

#### Task 2.1: Add Anomaly Priority to Individual ROIs
- [ ] **Per-ROI anomaly priority toggle**
  - Add checkbox to ROI widget: "Anomaly Priority"
  - Each ROI can independently enable/disable anomaly priority
  - Apply anomaly priority colorization within ROI bounds only
  - Store setting in ROI object: `roi.anomaly_priority_enabled`
  - Files to modify: ROI widget, ROI rendering code
  - Estimated effort: 2-3 hours
  - Priority: MEDIUM
  - Dependencies: Anomaly priority feature complete

#### Task 2.2: ROI Palette Selection
- [ ] **Allow different palette per ROI**
  - Add palette dropdown to ROI widget
  - Options: All available palettes (ironbow, white_hot, black_hot, rainbow, etc.)
  - Apply selected palette only within ROI bounds
  - Store setting in ROI object: `roi.palette_type`
  - Handle palette rendering priority (ROI palette overrides global palette)
  - Files to modify: ROI widget, palette manager, ROI rendering
  - Estimated effort: 3-4 hours
  - Priority: MEDIUM

#### Task 2.3: Multi-Select ROI Deletion
- [ ] **Enable multi-select in ROI list widget**
  - Change QListWidget selection mode to MultiSelection
  - Add "Delete Selected" button
  - Delete all selected ROIs on button click
  - Confirm deletion if >1 ROI selected (safety)
  - Update display after deletion
  - Files to modify: ROI widget, ROI manager
  - Estimated effort: 1-2 hours
  - Priority: MEDIUM

---

### Priority 3: GUI Organization

#### Task 3.1: Organize Widgets in Multitabs
- [ ] **Create tabbed interface for right-side widgets**
  - Replace stacked widget layout with QTabWidget
  - Organize related widgets into logical tabs:
    - **Analysis Tab**: Thermal analysis panel (stats, min/max temp, etc.)
    - **ROI Tab**: ROI management (list, creation, settings)
    - **Recording Tab**: Snapshot/recording controls
    - **Settings Tab**: Application settings and preferences
  - Benefits:
    - Better space utilization
    - Cleaner interface
    - Easier navigation between widget groups
    - Scalable for adding new widget panels
  - Files to modify: `inspection_gui_qt.py`, widget panel classes
  - Estimated effort: 3-4 hours
  - Priority: MEDIUM

---

## 🎯 Technical Design Notes

### Anomaly Priority Gradient Fade Algorithm

**Concept**: Create a smooth transition from colored (anomalies) to grayscale (non-anomalies)

**Implementation**:
```python
import cv2
import numpy as np
from scipy.ndimage import distance_transform_edt

def apply_anomaly_priority_colorization(thermal_frame, anomalies, colored_frame, fade_factor=1.0):
    """
    Apply anomaly priority: color anomalies, fade non-anomalies to grayscale.

    Args:
        thermal_frame: Original grayscale thermal frame (H, W)
        anomalies: List of anomaly dicts with 'bbox' key
        colored_frame: Thermal frame with palette applied (H, W, 3)
        fade_factor: Gradient steepness (0.5-2.0)

    Returns:
        Blended frame (H, W, 3)
    """
    h, w = thermal_frame.shape[:2]

    # Create binary mask of anomaly regions
    anomaly_mask = np.zeros((h, w), dtype=np.uint8)
    for anomaly in anomalies:
        x1, y1, x2, y2 = anomaly['bbox']
        anomaly_mask[y1:y2, x1:x2] = 255

    # Compute distance transform (distance from nearest anomaly pixel)
    distance_map = distance_transform_edt(anomaly_mask == 0)  # Distance from anomalies

    # Normalize distance to 0-1 range
    max_distance = 100  # Pixels - tune this for gradient extent
    normalized_distance = np.clip(distance_map / max_distance, 0, 1) ** fade_factor

    # Create grayscale version of thermal frame
    grayscale_frame = cv2.cvtColor(thermal_frame, cv2.COLOR_GRAY2BGR)

    # Blend: 0=full color (anomaly), 1=full grayscale (far from anomaly)
    blend_weight = normalized_distance[:, :, np.newaxis]  # (H, W, 1)
    blended = (colored_frame * (1 - blend_weight) + grayscale_frame * blend_weight).astype(np.uint8)

    return blended
```

**Performance Considerations**:
- Distance transform: ~5-10ms for 640x512 frame (acceptable)
- Blending operation: <1ms (vectorized numpy)
- Total overhead: ~10-15ms per frame
- Target: <20ms to maintain >30 FPS

**Tunable Parameters**:
- `max_distance`: How far the gradient extends (50-200px typical)
- `fade_factor`: Gradient steepness (1.0=linear, 2.0=sharp, 0.5=soft)

---

## 📊 Progress Tracking

### Overall Progress
- **GUI Integration**: 70% complete (button added, needs wiring)
- **Algorithm Development**: 0% complete (pending)
- **Testing**: 0% complete (pending)
- **ROI Enhancements**: 0% complete (not started)

### Estimated Total Effort
- Anomaly Priority Feature: 6-8 hours remaining
- ROI Enhancements: 6-9 hours
- **Total**: 12-17 hours

---

## 🐛 Known Issues

None currently - new feature development in progress.

---

## 📝 Notes

### Design Decisions
1. **Global Toggle vs Fusion Mode**: User correctly identified that anomaly priority should be a global toggle (like day/night mode) rather than a fusion mode, as it's a visualization filter that applies across all views.

2. **Distance Transform**: Using `scipy.ndimage.distance_transform_edt` for efficient gradient calculation. Alternative: precompute distance maps for common ROI sizes (optimization if needed).

3. **ROI Priority**: When anomaly priority is enabled per-ROI, it only affects the ROI region, not the entire frame. This allows selective highlighting of different inspection areas.

---

## 🔗 Related Files

### Modified Files (This Session)
- `inspection_gui_qt.py` - Added anomaly priority button and signal
  - Line 1026: Added `anomaly_priority_toggled` signal
  - Lines 1091-1093: Created anomaly priority button
  - Line 1098: Added button to grid layout (Row 3, Col 3)
  - Line 1138: Connected button signal
  - Lines 1213-1218: Added update method for button text

### Files To Be Modified
- `inspection_main.py` - Wire button signal, add state flag
- `thermal_processor.py` - Implement gradient fade algorithm
- ROI-related files - Add per-ROI settings

---

**End of TODO List**
**Next Steps**: Complete Task 1.1 (Wire button in inspection_main.py)
