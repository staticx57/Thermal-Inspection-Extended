# Thermal Inspection Extended - TODO List

**Project**: Thermal Inspection Tool with PyQt6 GUI
**Last Updated**: 2025-11-22
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

- [x] **Anomaly Priority Feature - Complete Implementation**
  - GUI Integration: `inspection_gui_qt.py`
    - Created `anomaly_priority_toggled` pyqtSignal in ControlPanel (line 1026)
    - Added anomaly priority button to Row 3, Column 3 (lines 1091-1098)
    - Button is checkable with initial state OFF
    - Connected signal to emit toggle events (line 1138)
    - Added `update_anomaly_priority_button(enabled: bool)` method (lines 1213-1218)
    - Button text: "🎯 Anomaly: ON" / "🎯 Anomaly: OFF"

  - Signal Wiring: `inspection_gui_qt.py` + `inspection_main.py`
    - Connected signal in InspectionAppWindow._connect_signals (line 1585)
    - Added handler `_on_anomaly_priority_toggle` (lines 1787-1792)
    - Added `toggle_anomaly_priority` method in InspectionMain (lines 966-970)

  - Gradient Fade Algorithm: `thermal_processor.py`
    - State variables initialized (lines 94-97):
      - `anomaly_priority_enabled` (default: False)
      - `anomaly_fade_strength` (default: 1.0, range 0.5-2.0)
      - `anomaly_max_distance` (default: 100 pixels)
    - Implemented `apply_anomaly_priority_colorization()` (lines 532-629)
      - Uses scipy `distance_transform_edt` for smooth gradients
      - Creates binary mask from anomaly bounding boxes
      - Applies weighted blend: colored (anomalies) → grayscale (non-anomalies)
    - Added setter `set_anomaly_priority_enabled()` (lines 631-634)

  - Processing Pipeline Integration: `inspection_main.py` (lines 625-655)
    - **Frame-by-Frame Anomaly Tracking** (Enhanced 2025-11-22):
      - Positioned AFTER all anomaly detections complete
      - Aggregates ALL anomaly types each frame:
        * Motion detections (MotionDetection.bbox)
        * Edge clusters (EdgeCluster.bbox)
        * Hot spots (HotSpot.bbox)
        * Cold spots (ColdSpot.bbox)
        * Thermal anomalies (ThermalAnomaly.bbox)
      - Recalculates gradient fade every frame with latest anomalies
      - Updates thermal_colorized before fusion processing
    - Automatically applies to ALL thermal views (thermal, fusion, quad, etc.)

  - **Key Features**:
    - Comprehensive: 5 anomaly detection sources
    - Dynamic: Updates every frame
    - Global: Affects all thermal-contributing views
    - Efficient: ~10-15ms overhead per frame

  - Status: COMPLETE (ready for tuning controls and testing)
  - Date Completed: 2025-11-22

## 🔄 In Progress

None currently - anomaly priority core feature is complete

---

## 📋 Pending Tasks

### Priority 1: Anomaly Priority Enhancements

#### Task 1.0: Create Dedicated Anomaly Widget Panel
- [ ] **Build comprehensive Anomaly Control Widget**
  - **Location**: Right-side widget panel (or new tab in multi-tab layout)
  - **Purpose**: Centralize all anomaly-related settings and controls

  - **Widget Components**:
    1. **Anomaly Priority Toggle**
       - Main ON/OFF switch (large, prominent)
       - Currently: button in developer panel (keep both or move?)

    2. **Anomaly Type Multi-Select** (CORE FEATURE)
       - Checkboxes to enable/disable each anomaly type:
         - ☐ Motion Detections (temporal changes)
         - ☐ Edge Clusters (thermal boundaries)
         - ☐ Hot Spots (95th percentile temperature)
         - ☐ Cold Spots (5th percentile temperature)
         - ☐ Thermal Anomalies (statistical outliers)
       - Allow any combination of types
       - Default: All enabled
       - Updates gradient fade in real-time

    3. **Gradient Fade Controls**
       - Fade Strength slider (0.5-2.0, default: 1.0)
       - Max Distance slider (50-200px, default: 100)
       - Real-time preview of gradient curve

    4. **Anomaly Detection Settings** (per type)
       - Motion threshold adjustment
       - Edge detection sensitivity
       - Hot/cold spot percentile controls
       - Minimum anomaly size filters

    5. **Anomaly Statistics Display**
       - Live count of each anomaly type detected
       - FPS impact meter
       - Total anomalies highlighted

  - **Implementation**:
    - Create `AnomalyWidget` class in `inspection_gui_qt.py`
    - Add signals for anomaly type selection changes
    - Store enabled types in `inspection_main.py` state
    - Filter anomalies before gradient fade based on enabled types
    - Update `inspection_main.py:625-655` to check enabled types

  - **Files to create/modify**:
    - `inspection_gui_qt.py` - New AnomalyWidget class
    - `inspection_main.py` - Anomaly type filtering logic
    - `thermal_processor.py` - Optional: per-type sensitivity controls

  - **Estimated effort**: 3-4 hours
  - **Priority**: HIGH
  - **Benefits**:
    - User control over what constitutes an "anomaly"
    - Reduce false positives by disabling noisy detectors
    - Customize for different inspection scenarios
    - Better organization of related controls

#### Task 1.1: Add GUI Controls for Fade Strength and Distance
- [ ] **Add sliders to control anomaly priority parameters**
  - Add slider for `anomaly_fade_strength` (range: 0.5-2.0, default: 1.0)
    - Label: "Fade Strength" or "Gradient Steepness"
    - Effect: Controls how quickly the color fades to grayscale
  - Add slider for `anomaly_max_distance` (range: 50-200px, default: 100)
    - Label: "Fade Distance" or "Gradient Extent"
    - Effect: Controls how far the gradient extends from anomalies
  - Location: Developer controls panel or settings tab
  - Connect sliders to thermal_processor parameter updates
  - Files to modify: `inspection_gui_qt.py`, `inspection_main.py`
  - Estimated effort: 1-2 hours
  - Priority: HIGH

#### Task 1.2: Research and Implement Anomaly Detection Tuning
- [ ] **Improve anomaly detection sensitivity controls**
  - Document current anomaly sources:
    - Motion detection (temporal differencing)
    - Edge detection (Canny edges + clustering)
  - Research alternative anomaly detection methods:
    - Statistical outliers (temperature deviation)
    - Gradient magnitude thresholding
    - Texture analysis
  - Add configurable thresholds for:
    - Motion detection sensitivity (current: `motion_threshold=20`)
    - Edge detection thresholds (current: `edge_threshold_low=50`, `edge_threshold_high=150`)
    - Minimum anomaly size filters
  - Files to modify: `thermal_processor.py`, `inspection_gui_qt.py`
  - Estimated effort: 3-4 hours
  - Priority: MEDIUM

#### Task 1.3: Test Across All Views
- [ ] **Verify anomaly priority works in all display modes**
  - Test scenarios:
    1. Thermal-only view
    2. Each fusion mode (alpha_blend, edge_enhanced, thermal_overlay, etc.)
    3. Quad view
    4. Side-by-side view
    5. Picture-in-picture
  - Verify:
    - Gradient fade is smooth and natural
    - Performance impact <10% FPS (currently using distance_transform_edt)
    - Anomalies clearly highlighted
    - Non-anomaly areas properly desaturated
    - Toggle on/off works instantly
  - Test with motion and edge detection enabled/disabled
  - Files: Integration testing
  - Estimated effort: 1-2 hours
  - Priority: HIGH

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
