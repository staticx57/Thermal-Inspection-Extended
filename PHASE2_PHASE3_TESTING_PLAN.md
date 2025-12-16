# Phase 2 & Phase 3 Testing Plan
# Thermal Inspection Tool - Feature Validation

**Date Created:** December 16, 2025
**Features to Test:** 8 major features (Phase 2: 4, Phase 3: 4)
**Estimated Testing Time:** 8-10 hours
**Status:** Ready for Testing

---

## Table of Contents

1. [Testing Environment Setup](#testing-environment-setup)
2. [Phase 2 Feature Testing](#phase-2-feature-testing)
3. [Phase 3 Feature Testing](#phase-3-feature-testing)
4. [Integration Testing](#integration-testing)
5. [Performance Testing](#performance-testing)
6. [Regression Testing](#regression-testing)
7. [Bug Report Template](#bug-report-template)

---

## Testing Environment Setup

### Prerequisites

Before beginning tests, ensure:

- [ ] Application starts without errors
- [ ] Thermal camera connected and operational
- [ ] RGB camera connected and operational (if available)
- [ ] All dependencies installed (PyQt6, PyQtGraph, NumPy, OpenCV)
- [ ] Test thermal images/videos available
- [ ] Log file accessible for error tracking

### Launch Application

```bash
python inspection_main.py
# OR
cmd //c launch.bat
```

### Verify Basic Functionality

- [ ] GUI loads successfully
- [ ] Thermal video stream appears
- [ ] RGB video stream appears (if available)
- [ ] No console errors on startup
- [ ] Analysis panel tabs are accessible

---

## Phase 2 Feature Testing

### Feature 6: Multi-point Statistics

**Location:** Analysis → Spot Meters tab

**Estimated Test Time:** 15 minutes

#### Test Cases

##### TC-6.1: Statistics Display
- [ ] **Action:** Place 3+ spot meters on thermal image
- [ ] **Expected:** Statistics panel shows Min, Max, Avg, Median, StdDev
- [ ] **Verify:** All values update in real-time
- [ ] **Verify:** Units are correct (°C, °F, K based on selection)

##### TC-6.2: Median Calculation
- [ ] **Action:** Place 5 spots with temperatures: 20, 22, 25, 28, 30°C
- [ ] **Expected:** Median shows 25°C (middle value)
- [ ] **Verify:** Median updates when spot values change

##### TC-6.3: Standard Deviation
- [ ] **Action:** Place spots with varying temperatures (large spread)
- [ ] **Expected:** StdDev shows significant value (e.g., 5-10°C)
- [ ] **Action:** Place spots with similar temperatures (small spread)
- [ ] **Expected:** StdDev shows small value (e.g., 0.5-2°C)

##### TC-6.4: Edge Cases
- [ ] **Action:** Place only 1 spot
- [ ] **Expected:** StdDev shows 0.0 (or N/A)
- [ ] **Action:** Delete all spots
- [ ] **Expected:** Statistics show "--" or reset to defaults

##### TC-6.5: Unit Conversion
- [ ] **Action:** Change temperature unit (°C → °F → K)
- [ ] **Expected:** All statistics update correctly
- [ ] **Verify:** Median and StdDev values convert properly

**Pass Criteria:** All statistics display correctly, update in real-time, and handle edge cases gracefully.

---

### Feature 7: Enhanced Temperature Alerts

**Location:** Analysis → Spot Meters tab

**Estimated Test Time:** 20 minutes

#### Test Cases

##### TC-7.1: Alert Configuration Dialog
- [ ] **Action:** Right-click spot, select "Set Alert"
- [ ] **Expected:** Alert dialog opens
- [ ] **Verify:** Sound checkbox present and checked by default
- [ ] **Verify:** Flash checkbox present and checked by default
- [ ] **Verify:** Threshold and type (above/below) controls present

##### TC-7.2: Sound Alert
- [ ] **Action:** Set alert threshold below current temperature
- [ ] **Action:** Enable sound alert
- [ ] **Expected:** System beep plays ONCE when alert triggers
- [ ] **Verify:** No continuous beeping (only on rising edge)
- [ ] **Action:** Disable sound alert
- [ ] **Expected:** No beep when alert triggers

##### TC-7.3: Visual Flashing
- [ ] **Action:** Set alert threshold below current temperature
- [ ] **Action:** Enable flash indicator
- [ ] **Expected:** Spot meter flashes red every 0.5 seconds
- [ ] **Verify:** Original color alternates with red
- [ ] **Action:** Disable flash indicator
- [ ] **Expected:** No flashing when alert triggers

##### TC-7.4: Trigger Tracking
- [ ] **Action:** Set alert and trigger it 5 times (by moving spot or changing conditions)
- [ ] **Action:** Open alert dialog again
- [ ] **Expected:** "Triggered 5 times" statistic displayed
- [ ] **Verify:** Trigger count increments correctly

##### TC-7.5: Alert History
- [ ] **Action:** Trigger alert multiple times
- [ ] **Verify:** Last trigger time updates
- [ ] **Verify:** History limited to last 100 triggers (check internal logs)

##### TC-7.6: Multiple Alerts
- [ ] **Action:** Set alerts on 3 different spots with different thresholds
- [ ] **Expected:** Each alert triggers independently
- [ ] **Verify:** Sounds and flashing work for all active alerts
- [ ] **Verify:** No interference between alerts

##### TC-7.7: Alert Persistence
- [ ] **Action:** Set alert, close dialog, reopen dialog
- [ ] **Expected:** Sound and flash settings are preserved
- [ ] **Verify:** Trigger count persists

**Pass Criteria:** Alerts trigger correctly with sound and flash, tracking works, no performance issues with multiple alerts.

---

### Feature 8: Isotherm Bands

**Location:** Analysis → Isotherm tab

**Estimated Test Time:** 25 minutes

#### Test Cases

##### TC-8.1: Multi-Band Mode Toggle
- [ ] **Action:** Navigate to Isotherm tab
- [ ] **Verify:** "Enable Multi-Band Mode" checkbox present
- [ ] **Action:** Check multi-band mode checkbox
- [ ] **Expected:** Single-band controls disable (mode, threshold, color)
- [ ] **Expected:** Band list and controls enable

##### TC-8.2: Add Band
- [ ] **Action:** Enable multi-band mode
- [ ] **Action:** Click "Add Band"
- [ ] **Expected:** New band appears in list (e.g., "Band 1: 10.0°C - 50.0°C")
- [ ] **Verify:** Band has assigned color
- [ ] **Action:** Add 3 more bands
- [ ] **Expected:** Each band gets unique color

##### TC-8.3: Remove Band
- [ ] **Action:** Select band from list
- [ ] **Action:** Click "Remove" button
- [ ] **Expected:** Band removed from list
- [ ] **Verify:** Thermal overlay updates

##### TC-8.4: Preset Loading - Temperature Zones
- [ ] **Action:** Click "Temp Zones" preset button
- [ ] **Expected:** 6 bands loaded (Cold, Cool, Normal, Warm, Hot, Very Hot)
- [ ] **Expected:** Multi-band mode automatically enabled
- [ ] **Expected:** Bands appear on thermal image with colors:
  - Cold: Blue
  - Cool: Cyan
  - Normal: Green
  - Warm: Yellow
  - Hot: Orange
  - Very Hot: Red

##### TC-8.5: Preset Loading - Comfort Zones
- [ ] **Action:** Click "Comfort" preset button
- [ ] **Expected:** 3 bands loaded (Too Cold, Comfortable, Too Hot)
- [ ] **Verify:** Blue (cold), Green (comfortable), Red (hot)

##### TC-8.6: Preset Loading - Electronics
- [ ] **Action:** Click "Electronics" preset button
- [ ] **Expected:** 3 bands loaded (Normal, Warm, Overheating)
- [ ] **Verify:** Green (normal), Yellow (warm), Red (overheating)

##### TC-8.7: Band Visualization
- [ ] **Action:** Enable multi-band mode with Temperature Zones preset
- [ ] **Expected:** Thermal image shows colored regions for each band
- [ ] **Verify:** Colors match temperature ranges
- [ ] **Verify:** Bands overlay correctly on thermal image
- [ ] **Verify:** Semi-transparent (can see underlying thermal data)

##### TC-8.8: Single-Band Fallback
- [ ] **Action:** Disable multi-band mode
- [ ] **Expected:** Revert to original single-band isotherm controls
- [ ] **Verify:** Previous single-band settings restored

##### TC-8.9: View Mode Compatibility
- [ ] **Action:** Enable multi-band isotherm
- [ ] **Test in:** Thermal only mode → **Expected:** Bands visible
- [ ] **Test in:** Fusion mode → **Expected:** Bands visible on thermal
- [ ] **Test in:** PIP mode → **Expected:** Bands visible on thermal window
- [ ] **Test in:** Side-by-side → **Expected:** Bands visible on thermal side
- [ ] **Test in:** RGB only → **Expected:** Bands hidden (no thermal data)

**Pass Criteria:** Multi-band mode works, presets load correctly, bands visualize properly, no conflicts with single-band mode.

---

### Feature 9: Area Statistics/Histogram

**Location:** ROI analysis (integrated with existing ROI system)

**Estimated Test Time:** 20 minutes

#### Test Cases

##### TC-9.1: Histogram Widget Presence
- [ ] **Verify:** Histogram widget present in appropriate panel
- [ ] **Verify:** PyQtGraph plot visible (if PyQtGraph installed)
- [ ] **If no PyQtGraph:** Verify informational message displayed

##### TC-9.2: ROI Histogram Generation
- [ ] **Action:** Draw rectangle ROI on thermal image
- [ ] **Expected:** Histogram updates showing temperature distribution
- [ ] **Verify:** X-axis: Temperature (°C)
- [ ] **Verify:** Y-axis: Count (pixels)
- [ ] **Verify:** Histogram bars appear

##### TC-9.3: Histogram Statistics
- [ ] **Action:** Select ROI with histogram
- [ ] **Expected:** Statistics displayed below histogram:
  - Min temperature
  - Max temperature
  - Mean temperature
  - StdDev
- [ ] **Verify:** Values match ROI radiometric data

##### TC-9.4: Bin Count Adjustment
- [ ] **Action:** Change "Bins" dropdown (20, 50, 100, 200)
- [ ] **Expected:** Histogram regenerates with new bin count
- [ ] **Verify:** More bins = finer temperature resolution
- [ ] **Verify:** Fewer bins = coarser, smoother histogram

##### TC-9.5: Auto-Range
- [ ] **Action:** Enable "Auto Range" checkbox
- [ ] **Expected:** Histogram X-axis adjusts to min/max temperature
- [ ] **Action:** Disable auto-range
- [ ] **Expected:** Manual range control available

##### TC-9.6: Multiple ROIs
- [ ] **Action:** Draw 3 ROIs with different temperature ranges
- [ ] **Action:** Select each ROI
- [ ] **Expected:** Histogram updates for selected ROI
- [ ] **Verify:** Different ROIs show different distributions

##### TC-9.7: Real-time Updates
- [ ] **Action:** Keep ROI selected
- [ ] **Expected:** Histogram updates as thermal data changes
- [ ] **Verify:** Smooth updates (no lag/freezing)

##### TC-9.8: Temperature Unit Changes
- [ ] **Action:** Change temperature unit (°C → °F)
- [ ] **Expected:** Histogram X-axis updates to new unit
- [ ] **Verify:** Temperature values convert correctly

**Pass Criteria:** Histogram displays correctly, updates in real-time, handles multiple ROIs, statistics accurate.

---

## Phase 3 Feature Testing

### Feature 10: Line Profile Tool

**Location:** Analysis → (New Line Profile tab or integrated location)

**Estimated Test Time:** 30 minutes

#### Test Cases

##### TC-10.1: Line Drawing Mode
- [ ] **Action:** Navigate to Line Profile panel
- [ ] **Action:** Enable "Enable Line Drawing Mode" checkbox
- [ ] **Expected:** Cursor changes or mode indicator appears
- [ ] **Verify:** Can click and drag to draw line on thermal image

##### TC-10.2: Line Creation
- [ ] **Action:** Click at point A, drag to point B, release
- [ ] **Expected:** Line appears on thermal overlay
- [ ] **Expected:** Line profile graph updates showing temperature along line
- [ ] **Expected:** Line added to "Active Lines" list

##### TC-10.3: Line Profile Graph
- [ ] **Action:** Draw line across thermal gradient (cold to hot area)
- [ ] **Expected:** Graph shows temperature profile
- [ ] **Verify:** X-axis: Distance (pixels)
- [ ] **Verify:** Y-axis: Temperature (°C)
- [ ] **Verify:** Profile matches visual thermal gradient

##### TC-10.4: Multiple Lines
- [ ] **Action:** Draw 3 lines in different locations
- [ ] **Expected:** All 3 lines appear on overlay
- [ ] **Expected:** All 3 profiles appear in graph (different colors)
- [ ] **Expected:** All 3 listed in "Active Lines"

##### TC-10.5: Line Selection
- [ ] **Action:** Click line in list
- [ ] **Expected:** Corresponding line highlights on overlay
- [ ] **Expected:** Statistics update for selected line:
  - Line length (pixels)
  - Min temperature
  - Max temperature
  - Avg temperature
  - StdDev

##### TC-10.6: Line Deletion
- [ ] **Action:** Select line, click "Delete"
- [ ] **Expected:** Line removed from overlay
- [ ] **Expected:** Profile removed from graph
- [ ] **Expected:** Line removed from list

##### TC-10.7: Clear All Lines
- [ ] **Action:** Draw several lines, click "Clear All"
- [ ] **Expected:** All lines removed
- [ ] **Expected:** Graph cleared
- [ ] **Expected:** List emptied

##### TC-10.8: Sample Points Adjustment
- [ ] **Action:** Change "Sample Points" spinner (10, 100, 500)
- [ ] **Expected:** Profile smoothness changes
- [ ] **Verify:** More samples = smoother profile
- [ ] **Verify:** Fewer samples = more pixelated profile

##### TC-10.9: Export CSV
- [ ] **Action:** Select line, click "Export CSV"
- [ ] **Expected:** File save dialog opens
- [ ] **Action:** Save file
- [ ] **Verify:** CSV contains distance and temperature columns
- [ ] **Verify:** Data matches profile graph

##### TC-10.10: Real-time Updates
- [ ] **Action:** Draw line, keep it active
- [ ] **Expected:** Profile updates as thermal data changes
- [ ] **Verify:** No performance degradation

##### TC-10.11: View Mode Compatibility
- [ ] **Test in:** Thermal only → **Expected:** Lines draw and work correctly
- [ ] **Test in:** Fusion → **Expected:** Lines overlay on fused image
- [ ] **Test in:** PIP → **Expected:** Lines draw on thermal window only

**Pass Criteria:** Lines draw correctly, profiles accurate, multiple lines supported, export works, real-time updates smooth.

---

### Feature 11: Temperature Gradients Visualization

**Location:** Analysis → Overlays tab → Gradient section

**Estimated Test Time:** 25 minutes

#### Test Cases

##### TC-11.1: Gradient Enable
- [ ] **Action:** Navigate to gradient overlay panel
- [ ] **Action:** Enable "Enable Gradient Visualization" checkbox
- [ ] **Expected:** Gradient overlay appears on thermal image
- [ ] **Verify:** Shows areas of rapid temperature change

##### TC-11.2: Gradient Mode - Magnitude
- [ ] **Action:** Select "Magnitude (Overall Change)" mode
- [ ] **Expected:** Gradient shows overall temperature change rate
- [ ] **Verify:** Hottest gradients highlighted
- [ ] **Verify:** Flat temperature areas not highlighted

##### TC-11.3: Gradient Mode - Horizontal
- [ ] **Action:** Select "Horizontal (X-direction)" mode
- [ ] **Expected:** Shows only horizontal temperature changes
- [ ] **Verify:** Vertical gradients not highlighted

##### TC-11.4: Gradient Mode - Vertical
- [ ] **Action:** Select "Vertical (Y-direction)" mode
- [ ] **Expected:** Shows only vertical temperature changes
- [ ] **Verify:** Horizontal gradients not highlighted

##### TC-11.5: Gradient Mode - Both (Arrows)
- [ ] **Action:** Select "Both Directions (Arrows)" mode
- [ ] **Expected:** Direction arrows or combined gradient display
- [ ] **Verify:** Shows gradient direction and magnitude

##### TC-11.6: Threshold Adjustment
- [ ] **Action:** Set min gradient to 0.5°C/px
- [ ] **Expected:** Low gradients visible
- [ ] **Action:** Set min gradient to 5.0°C/px
- [ ] **Expected:** Only strong gradients visible

##### TC-11.7: Sensitivity Control
- [ ] **Action:** Move sensitivity slider from 0% to 100%
- [ ] **Expected:** Low sensitivity = fewer gradients shown
- [ ] **Expected:** High sensitivity = more gradients shown

##### TC-11.8: Color Map Selection
- [ ] **Test each color map:**
  - Hot (Red-Yellow)
  - Cool (Blue-Cyan)
  - Jet (Rainbow)
  - Viridis (Smooth)
  - Grayscale
- [ ] **Expected:** Gradient colors change accordingly
- [ ] **Verify:** Color maps applied correctly

##### TC-11.9: Presets
- [ ] **Test "High Sensitivity" preset**
  - **Expected:** threshold=0.5, sensitivity=80%, mode=magnitude
- [ ] **Test "Medium (Default)" preset**
  - **Expected:** threshold=1.0, sensitivity=50%, mode=magnitude
- [ ] **Test "Low (Major Changes)" preset**
  - **Expected:** threshold=3.0, sensitivity=30%, mode=magnitude
- [ ] **Test "Edge Detection" preset**
  - **Expected:** threshold=2.0, sensitivity=60%, mode=both

##### TC-11.10: Performance
- [ ] **Action:** Enable gradient overlay
- [ ] **Verify:** FPS remains above 20 FPS
- [ ] **Verify:** No significant lag or stuttering

**Pass Criteria:** Gradient visualization works in all modes, controls function properly, presets load correctly, acceptable performance.

---

### Feature 12: Thermal Contours on RGB

**Location:** Fusion panel → Fusion mode selection

**Estimated Test Time:** 20 minutes

#### Test Cases

##### TC-12.1: Fusion Mode Selection
- [ ] **Action:** Open fusion panel
- [ ] **Action:** Select "Thermal Contours" fusion mode
- [ ] **Expected:** Mode activates
- [ ] **Verify:** "thermal_contours" appears in fusion mode list

##### TC-12.2: Contour Visualization
- [ ] **Action:** Activate thermal_contours mode
- [ ] **Expected:** RGB image displayed as base
- [ ] **Expected:** Colored contour lines overlaid
- [ ] **Verify:** Contours follow temperature boundaries

##### TC-12.3: Contour Levels
- [ ] **Verify:** 8 temperature levels displayed
- [ ] **Verify:** Color progression from blue (cool) to red (hot):
  - Blue (coolest)
  - Cyan
  - Cyan-green
  - Green
  - Yellow-green
  - Yellow
  - Orange
  - Red (hottest)

##### TC-12.4: Contour Accuracy
- [ ] **Action:** Compare contours to thermal palette colorbar
- [ ] **Verify:** Contours align with temperature zones
- [ ] **Verify:** Hot areas have red contours
- [ ] **Verify:** Cool areas have blue contours

##### TC-12.5: RGB Base Visibility
- [ ] **Action:** View thermal_contours mode
- [ ] **Expected:** RGB image clearly visible beneath contours
- [ ] **Verify:** Contours not obscuring RGB detail
- [ ] **Verify:** Can identify objects in RGB with thermal boundaries

##### TC-12.6: Fusion Intensity Effect
- [ ] **Action:** Adjust fusion intensity parameter (if exposed)
- [ ] **Expected:** Higher intensity = more thermal color overlay
- [ ] **Expected:** Lower intensity = more prominent RGB base

##### TC-12.7: Temperature Variation
- [ ] **Test with:** High temperature variation scene
  - **Expected:** Many distinct contour levels visible
- [ ] **Test with:** Low temperature variation scene
  - **Expected:** Few or no contours (< 10°C range handled gracefully)

##### TC-12.8: Real-time Updates
- [ ] **Action:** Keep thermal_contours mode active
- [ ] **Expected:** Contours update as temperature changes
- [ ] **Verify:** Smooth updates, no flickering

**Pass Criteria:** Contours display correctly on RGB, color coding accurate, 8 levels visible, real-time updates smooth.

---

### Feature 13: Edge Highlight Fusion

**Location:** Fusion panel → Fusion mode selection

**Estimated Test Time:** 25 minutes

#### Test Cases

##### TC-13.1: Fusion Mode Selection
- [ ] **Action:** Select "Enhanced Edge Highlight" fusion mode
- [ ] **Expected:** Mode activates
- [ ] **Verify:** "enhanced_edge_highlight" in fusion mode list

##### TC-13.2: Multi-Scale Edge Detection
- [ ] **Action:** Activate enhanced_edge_highlight mode
- [ ] **Expected:** Edges detected at multiple scales:
  - Fine details (small features)
  - Medium structures
  - Large features
- [ ] **Verify:** More edges visible than basic edge_enhanced mode

##### TC-13.3: Edge Visibility
- [ ] **Action:** View scene with thermal and RGB cameras
- [ ] **Expected:** Prominent colored edges overlaid on base image
- [ ] **Verify:** Edges stand out clearly
- [ ] **Verify:** Edge connectivity maintained (continuous lines)

##### TC-13.4: Priority - Thermal Base
- [ ] **Action:** Set fusion priority to "Thermal"
- [ ] **Expected:** Thermal image as base
- [ ] **Expected:** RGB edges overlaid in cyan/yellow (default color)
- [ ] **Verify:** Edge color matches thermal_priority_edge_color config

##### TC-13.5: Priority - RGB Base
- [ ] **Action:** Set fusion priority to "RGB"
- [ ] **Expected:** RGB image as base
- [ ] **Expected:** Thermal edges overlaid in red (default color)
- [ ] **Verify:** Edge color matches rgb_priority_edge_color config

##### TC-13.6: Fusion Intensity Effect
- [ ] **Action:** Set fusion intensity to 0.0
- [ ] **Expected:** Thin, subtle edges
- [ ] **Action:** Set fusion intensity to 1.0
- [ ] **Expected:** Thick, prominent edges
- [ ] **Verify:** Edge alpha adjusts (0.6 to 1.0 range)

##### TC-13.7: Edge Morphology
- [ ] **Verify:** Edges are connected (not fragmented)
- [ ] **Verify:** Morphological closing applied (small gaps filled)
- [ ] **Verify:** Slight dilation for visibility

##### TC-13.8: Comparison to Basic Edge Enhanced
- [ ] **Action:** Switch between edge_enhanced and enhanced_edge_highlight
- [ ] **Expected:** Enhanced mode shows:
  - More edges
  - Better connectivity
  - Smoother appearance
  - Multi-scale details

##### TC-13.9: Performance
- [ ] **Action:** Enable enhanced_edge_highlight mode
- [ ] **Verify:** FPS remains above 15 FPS
- [ ] **Verify:** No significant lag

##### TC-13.10: Edge Threshold Parameters (Internal)
- [ ] **Verify in logs:** edge_threshold_low and edge_threshold_high used
- [ ] **Verify:** Adaptive thresholds for different scales (0.7x, 0.5x)

**Pass Criteria:** Enhanced edges visible and prominent, multi-scale detection working, better than basic edge mode, acceptable performance.

---

## Integration Testing

**Estimated Time:** 2 hours

### Multi-Feature Interactions

#### INT-1: Spot Meters + Alerts + Statistics
- [ ] **Action:** Place 5 spots, set alerts on 2, enable flashing
- [ ] **Expected:** Statistics show median/stddev
- [ ] **Expected:** Alerts trigger with sound and flash
- [ ] **Expected:** No interference between features

#### INT-2: Isotherm Bands + Spot Meters
- [ ] **Action:** Enable multi-band isotherm with Temperature Zones preset
- [ ] **Action:** Place spot meters in different bands
- [ ] **Expected:** Spots show temperatures matching band colors
- [ ] **Expected:** Both overlays visible and non-conflicting

#### INT-3: Line Profile + Gradient Overlay
- [ ] **Action:** Enable gradient overlay
- [ ] **Action:** Draw line profile across high-gradient area
- [ ] **Expected:** Line profile shows steep temperature change
- [ ] **Expected:** Profile matches gradient visualization

#### INT-4: Thermal Contours + ROI Histogram
- [ ] **Action:** Use thermal_contours fusion mode
- [ ] **Action:** Draw ROI, view histogram
- [ ] **Expected:** Histogram distribution matches contour levels
- [ ] **Expected:** Multi-modal histogram for multi-level temperatures

#### INT-5: Enhanced Edge Highlight + Isotherm Bands
- [ ] **Action:** Use enhanced_edge_highlight fusion
- [ ] **Action:** Enable multi-band isotherm on thermal
- [ ] **Expected:** Both overlays visible (edges on fusion, bands on thermal)
- [ ] **Verify:** No visual conflicts

#### INT-6: All Phase 2 Features Simultaneously
- [ ] **Enable:** Multi-point statistics (5 spots)
- [ ] **Enable:** Enhanced alerts (2 spots with sound/flash)
- [ ] **Enable:** Isotherm bands (Temperature Zones preset)
- [ ] **Enable:** ROI histogram (1 ROI)
- [ ] **Expected:** All features work without conflicts
- [ ] **Verify:** FPS > 15

#### INT-7: All Phase 3 Features Simultaneously
- [ ] **Enable:** Line profile (2 lines)
- [ ] **Enable:** Gradient overlay (magnitude mode)
- [ ] **Use:** Thermal contours fusion mode
- [ ] **Note:** Can't test enhanced_edge_highlight + thermal_contours (both are fusion modes)
- [ ] **Expected:** Features work together
- [ ] **Verify:** FPS > 15

#### INT-8: All Features (Mixed Phase 2 & 3)
- [ ] **Enable:** Everything possible:
  - 5 spots with alerts
  - Multi-band isotherm
  - 2 line profiles
  - Gradient overlay
  - ROI histogram
  - Thermal contours OR enhanced edge highlight fusion
- [ ] **Expected:** Application remains stable
- [ ] **Verify:** FPS > 10 (may be reduced with all features)
- [ ] **Verify:** No crashes or freezes

---

## Performance Testing

**Estimated Time:** 1 hour

### Performance Benchmarks

#### PERF-1: Baseline FPS
- [ ] **Action:** Disable all new features
- [ ] **Measure:** FPS with thermal + RGB
- [ ] **Record:** Baseline FPS (typically 13-14 FPS)

#### PERF-2: Phase 2 Features Overhead
- [ ] **Test:** Each Phase 2 feature individually
  - Multi-point statistics (5 spots)
  - Enhanced alerts (3 alerts flashing)
  - Isotherm bands (6 bands)
  - ROI histogram (1 ROI)
- [ ] **Measure:** FPS for each
- [ ] **Expected:** <2ms overhead per feature (<5% FPS drop)

#### PERF-3: Phase 3 Features Overhead
- [ ] **Test:** Each Phase 3 feature individually
  - Line profile (2 lines, 100 samples)
  - Gradient overlay (magnitude mode)
  - Thermal contours fusion
  - Enhanced edge highlight fusion
- [ ] **Measure:** FPS for each
- [ ] **Expected:** <5ms overhead per feature (<10% FPS drop)

#### PERF-4: Combined Overhead
- [ ] **Test:** All Phase 2 + Phase 3 features enabled
- [ ] **Measure:** FPS
- [ ] **Expected:** FPS > 10 (at least 75% of baseline)
- [ ] **Target:** FPS > 12

#### PERF-5: Memory Usage
- [ ] **Baseline:** Memory usage without new features
- [ ] **With Features:** Memory usage with all features enabled
- [ ] **Expected:** <50MB additional memory
- [ ] **Verify:** No memory leaks over 10-minute session

#### PERF-6: CPU Profiling
- [ ] **Use:** Python profiler (cProfile) on 30-second session
- [ ] **Identify:** Top 5 performance bottlenecks
- [ ] **Verify:** No single new feature consumes >10% CPU time

#### PERF-7: Stress Test
- [ ] **Action:** Enable all features and run for 30 minutes
- [ ] **Monitor:** FPS, memory, CPU temperature
- [ ] **Expected:** Stable performance, no degradation over time
- [ ] **Expected:** No memory leaks (memory remains constant)

---

## Regression Testing

**Estimated Time:** 1 hour

### Existing Features Validation

#### REG-1: Phase 1 Features Still Work
- [ ] **Test:** Cursor Temperature Readout
  - **Expected:** Still functional, no interference from new features
- [ ] **Test:** Colorbar/Legend
  - **Expected:** Updates with palette changes
- [ ] **Test:** Spot Meter Comparison Mode
  - **Expected:** Delta line displays correctly
- [ ] **Test:** Grid Overlay
  - **Expected:** Grid draws correctly on thermal

#### REG-2: Core Thermal Functionality
- [ ] **Test:** Thermal stream displays
- [ ] **Test:** Palette changes work
- [ ] **Test:** Temperature unit changes (°C, °F, K)
- [ ] **Test:** Radiometric conversion accurate
- [ ] **Test:** Spot meter temperature readings match colorbar

#### REG-3: Core Fusion Functionality
- [ ] **Test:** All original fusion modes still work:
  - Alpha blend
  - Detail inject
  - Relief fusion
  - Edge enhanced (original)
  - Thermal overlay
  - Side-by-side
  - Picture-in-picture
  - Max intensity
  - Feature weighted

#### REG-4: ROI System
- [ ] **Test:** Draw rectangle, polygon, ellipse, circle ROIs
- [ ] **Test:** ROI radiometric analysis
- [ ] **Test:** ROI-specific palettes
- [ ] **Test:** ROI export (CSV, JSON)

#### REG-5: Recording & Playback
- [ ] **Test:** Record thermal video
- [ ] **Test:** Playback recorded video
- [ ] **Test:** Snapshot capture
- [ ] **Test:** New features work during playback

#### REG-6: View Modes
- [ ] **Test:** Thermal only
- [ ] **Test:** RGB only
- [ ] **Test:** Fusion (various modes)
- [ ] **Test:** Picture-in-picture (thermal priority, RGB priority)
- [ ] **Test:** Side-by-side
- [ ] **Verify:** New features adapt to view mode changes

---

## Bug Report Template

When a test fails, document using this template:

```markdown
## Bug Report

**ID:** BUG-[Feature#]-[TC#]-[Sequence]
**Example:** BUG-7-3-1

**Date:** YYYY-MM-DD
**Tester:** [Your Name]
**Severity:** Critical / High / Medium / Low

### Feature
[Feature name and number]

### Test Case
[Test case ID and description]

### Steps to Reproduce
1. Step 1
2. Step 2
3. Step 3

### Expected Result
[What should happen]

### Actual Result
[What actually happened]

### Screenshots/Logs
[Attach screenshots if applicable]
[Include relevant log entries from thermal_inspection_debug.log]

### Environment
- OS: Windows/Linux
- Python Version:
- Thermal Camera: Boson / Other
- RGB Camera: Yes/No

### Additional Notes
[Any other relevant information]
```

---

## Test Results Summary

Fill out after completing all tests:

### Phase 2 Features

| Feature | Test Cases | Passed | Failed | Notes |
|---------|-----------|--------|--------|-------|
| F6: Multi-point Stats | 5 | __ | __ | |
| F7: Enhanced Alerts | 7 | __ | __ | |
| F8: Isotherm Bands | 9 | __ | __ | |
| F9: Histogram | 8 | __ | __ | |

### Phase 3 Features

| Feature | Test Cases | Passed | Failed | Notes |
|---------|-----------|--------|--------|-------|
| F10: Line Profile | 11 | __ | __ | |
| F11: Gradient Overlay | 10 | __ | __ | |
| F12: Thermal Contours | 8 | __ | __ | |
| F13: Enhanced Edge Highlight | 10 | __ | __ | |

### Integration & Performance

| Test Category | Test Cases | Passed | Failed | Notes |
|--------------|-----------|--------|--------|-------|
| Integration Tests | 8 | __ | __ | |
| Performance Tests | 7 | __ | __ | |
| Regression Tests | 6 | __ | __ | |

### Overall Summary

- **Total Test Cases:** ~107
- **Passed:** __
- **Failed:** __
- **Pass Rate:** __%
- **Critical Bugs:** __
- **High Priority Bugs:** __
- **Medium Priority Bugs:** __
- **Low Priority Bugs:** __

### Recommendation

- [ ] **PASS** - Features ready for production
- [ ] **PASS WITH MINOR ISSUES** - Non-critical bugs to be addressed
- [ ] **FAIL** - Critical issues require fixes before release

### Sign-off

**Tester:** ________________________
**Date:** ________________________
**Signature:** ________________________

---

## Notes for Testers

### Tips for Effective Testing

1. **Start with individual features** before testing combinations
2. **Test in order** (Phase 2 → Phase 3 → Integration)
3. **Document everything** - even minor glitches
4. **Use different thermal scenes** - hot spots, gradients, uniform temps
5. **Monitor console output** for errors and warnings
6. **Check log file** regularly for exceptions
7. **Take screenshots** of visual bugs
8. **Test with thermal camera AND recorded video**
9. **Try edge cases** - extreme values, empty states, rapid changes
10. **Be patient** - some features need time to stabilize

### Common Issues to Watch For

- **Performance:** FPS drops, lag, stuttering
- **Visual:** Overlays not appearing, incorrect colors, z-order issues
- **Data:** Incorrect calculations, missing updates, stale data
- **UI:** Disabled controls, missing labels, layout problems
- **Crashes:** Application hangs, segfaults, unhandled exceptions
- **Memory:** Leaks, excessive memory usage
- **Integration:** Feature conflicts, overlapping visuals, signal issues

### Quick Debugging Commands

```python
# Enable debug logging
logging.getLogger().setLevel(logging.DEBUG)

# Check feature state
print(f"Gradient enabled: {gradient_panel.is_enabled()}")
print(f"Multiband mode: {isotherm_panel.is_multiband_mode()}")

# Monitor FPS
# Check terminal output for FPS counter

# Memory usage (Windows)
# Task Manager → Performance → Memory

# Profile performance
python -m cProfile -o profile.stats inspection_main.py
# Analyze with: python -m pstats profile.stats
```

---

**End of Testing Plan**

Document Version: 1.0
Last Updated: December 16, 2025
Next Review: After Phase 2 & 3 Testing Complete
