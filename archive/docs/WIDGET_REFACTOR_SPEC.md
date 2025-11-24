# Widget Refactor and Enhancement Specification

## Overview
This document outlines the comprehensive refactoring of the Thermal Inspection GUI, focusing on anomaly detection modes, widget organization, and Boson SDK expansion.

## 1. Anomaly Detection Mode Split

### Current State
- Single "Anomaly Priority" mode with automatic detection (motion, edges, hot/cold spots, thermal anomalies)
- Detection settings are collapsed in a single section
- Gradient fade controls for visualization

### New Design: Dual Mode System

#### 1.1 Automatic Mode (Image Analysis-Based)
**Detection Types:**
- Motion Detection (temporal changes)
- Edge Clusters (thermal boundaries)
- Hot Spots (95th percentile)
- Cold Spots (5th percentile)
- Thermal Anomalies (statistical outliers)
- **NEW: Enhanced Thermal+Edge Fusion** (intelligent combination of thermal data + edge detection)

**Features:**
- Multi-select checkboxes for detection types
- Live count display for each type
- Configurable thresholds (motion, edge, percentiles, min size)
- Gradient fade visualization

#### 1.2 Manual Mode (Threshold-Based)
**Purpose:** Allow user-defined temperature/raw value thresholds for custom anomaly highlighting

**Features:**
- Temperature threshold input (min/max in °C or °F)
- Raw value threshold input (14-bit thermal values)
- Threshold mode selection:
  - **Above Threshold:** Highlight values above threshold
  - **Below Threshold:** Highlight values below threshold
  - **Between Thresholds:** Highlight values in range
  - **Outside Thresholds:** Highlight values outside range
- Color scheme selection:
  - **Grayscale Non-Anomalies:** Normal areas in grayscale, anomalies in color
  - **Color Non-Anomalies:** Normal areas in color, anomalies highlighted/inverted
  - **Binary Mask:** Black/white binary visualization
  - **Gradient Overlay:** Smooth gradient based on distance from threshold

**UI Layout:**
```
┌─ MANUAL THRESHOLD MODE ─────────────────────┐
│ ○ Temperature-based  ● Raw Value-based      │
│                                              │
│ Threshold Type:                              │
│ [▼ Above Threshold        ]                  │
│                                              │
│ Min Threshold: [____] Raw (0-16383)          │
│ Max Threshold: [____] Raw (0-16383)          │
│                                              │
│ Visualization:                               │
│ [▼ Grayscale Non-Anomalies]                  │
│                                              │
│ Color Palette (for anomalies):               │
│ [▼ Hot Iron            ]                     │
│                                              │
│ [✓] Show threshold lines on image           │
│ [✓] Display anomaly percentage              │
└──────────────────────────────────────────────┘
```

## 2. Enhanced Thermal+Edge Fusion Mode

**Algorithm Design:**
1. Compute thermal gradient magnitude
2. Run Canny edge detection on thermal data
3. Identify edge clusters with high thermal contrast
4. Weight anomalies by both temperature deviation AND edge strength
5. Prioritize regions with sharp thermal boundaries + statistical outliers

**Parameters:**
- Edge weight factor (0.0-1.0): Balance between thermal and edge importance
- Min edge strength threshold
- Thermal deviation multiplier

## 3. Tab Organization and Widget Layout

### 3.1 Current Tabs
1. **Analysis** - Thermal statistics, ROI analysis, trends
2. **Anomaly** - Anomaly detection controls
3. **Boson** - SDK controls for FLIR Boson

### 3.2 Proposed Tab Reorganization

#### Tab 1: Display & Palettes
- View mode selection (thermal, RGB, fusion, side-by-side)
- Palette selection and configuration
- Composite palette settings
- Display scaling options
- Moved from scattered locations

#### Tab 2: ROI Management
- ROI creation tools
- ROI list with multi-select
- Per-ROI palette assignment
- ROI statistics
- Auto-ROI controls
- Consolidates all ROI functionality

#### Tab 3: Analysis
- Overall thermal statistics
- Temperature trends
- Histogram
- Performance metrics
- Keep focused on data analysis

#### Tab 4: Anomaly Detection
**Sub-sections:**
- Mode selector: ○ Automatic  ● Manual
- Automatic Mode section (collapsible when not selected)
- Manual Mode section (collapsible when not selected)
- Visualization settings (gradient fade, overlay options)
- Performance impact display

#### Tab 5: Boson SDK
- Expanded controls (see section 4)

#### Tab 6: Recording & Export
- Snapshot controls
- Recording controls
- Export settings
- Moved from main panel for better organization

### 3.3 Widget Formatting Standards

**Consistency Rules:**
1. All group boxes use consistent padding (10px)
2. All labels use consistent font sizing:
   - Section headers: 12pt bold
   - Field labels: 10pt normal
   - Hints: 9pt italic, gray
3. All sliders have value labels on the right (min 35px wide)
4. All combo boxes have tooltips
5. All spin boxes have appropriate ranges and step sizes
6. Spacing between sections: 15px
7. Button minimum height: 32px (important actions: 40px)

## 4. Boson SDK Feature Expansion

### Current Features
- FFC trigger
- FFC mode selection
- Gain mode control
- Color LUT selection
- FPA temperature display
- Camera information display

### New Features to Add

#### 4.1 Video Processing Controls
- **Contrast Enhancement**
  - Enable/disable
  - Strength slider (0-100%)
- **Spatial Spectral Offset (SSO)**
  - Enable/disable SSO
  - SSO mode selection
- **Temporal Filtering**
  - Enable/disable
  - Filter strength

#### 4.2 Digital Detail Enhancement (DDE)
- DDE enable/disable
- DDE gain slider
- DDE threshold adjustment

#### 4.3 AGC (Automatic Gain Control)
- AGC algorithm selection
  - Linear
  - Histogram Equalization
  - Plateau Equalization
  - Contrast Enhancement
- AGC ROI selection (Full Image, Center, Custom)
- Max/Min gain limits

#### 4.4 Advanced Settings (Collapsible)
- Frame rate display
- Shutter temperature
- Lens parameters
- Sensor configuration
- Boot parameters (read-only)

#### 4.5 Calibration & Diagnostics
- Calibration status display
- Built-in test (BIT) status
- Error log display (if available)
- Factory reset warning (with confirmation)

### UI Layout for Boson Tab
```
┌─ SDK CONNECTION ─────────────────────────────┐
│ ● Connected                                  │
└──────────────────────────────────────────────┘

┌─ CAMERA INFORMATION ─────────────────────────┐
│ (existing info fields)                       │
└──────────────────────────────────────────────┘

┌─ FFC & CALIBRATION ──────────────────────────┐
│ (existing FFC controls)                      │
└──────────────────────────────────────────────┘

┌─ VIDEO PROCESSING ───────────────────────────┐
│ DDE (Digital Detail Enhancement):            │
│ [✓] Enable DDE                               │
│ Gain: [slider] 50                            │
│                                              │
│ [✓] Contrast Enhancement                     │
│ Strength: [slider] 75%                       │
│                                              │
│ [✓] Spatial Spectral Offset (SSO)           │
└──────────────────────────────────────────────┘

┌─ AGC CONTROL ────────────────────────────────┐
│ Algorithm: [▼ Histogram Equalization]        │
│ ROI: [▼ Full Image]                          │
│ Max Gain: [slider] 100%                      │
│ Min Gain: [slider] 10%                       │
└──────────────────────────────────────────────┘

┌─ GAIN & COLOR LUT ───────────────────────────┐
│ (existing controls)                          │
└──────────────────────────────────────────────┘

┌─ ADVANCED SETTINGS ──────────────────────────┐
│ [Expand Settings ▼]                          │
│ (collapsible content)                        │
└──────────────────────────────────────────────┘
```

## 5. Implementation Plan

### Phase 1: Anomaly Mode Split
1. Create `ManualThresholdWidget` class
2. Modify `AnomalyControlWidget` to support mode switching
3. Add threshold processing to `thermal_analyzer.py`
4. Implement grayscale/color visualization modes

### Phase 2: Enhanced Fusion Mode
1. Add edge-weighted anomaly detection to `thermal_analyzer.py`
2. Create UI controls for edge fusion parameters
3. Integrate with existing anomaly priority system

### Phase 3: Widget Reorganization
1. Create new tab structure
2. Move widgets to appropriate tabs
3. Apply consistent formatting
4. Update signal connections

### Phase 4: Boson SDK Expansion
1. Add new SDK wrapper methods to `boson_sdk_wrapper.py`
2. Create new UI controls in `BosonControlPanel`
3. Wire up signals to inspection_main
4. Test with actual hardware

### Phase 5: Testing & Refinement
1. Test all new features
2. Verify 30 FPS performance maintained
3. Refine UI based on usage
4. Update documentation

## 6. Files to Modify

1. **inspection_gui_qt.py**
   - Refactor `AnomalyControlWidget`
   - Add `ManualThresholdWidget`
   - Reorganize tabs
   - Expand `BosonControlPanel`

2. **thermal_analyzer.py**
   - Add manual threshold detection
   - Add enhanced thermal+edge fusion
   - Add threshold visualization modes

3. **boson_sdk_wrapper.py**
   - Add DDE controls
   - Add SSO controls
   - Add AGC controls
   - Add video processing controls

4. **inspection_main.py**
   - Wire new signals
   - Integrate manual threshold mode
   - Connect new Boson SDK features

## 7. Backward Compatibility

- All existing features remain functional
- New features are additive
- Configuration file updated to save new settings
- Default values preserve current behavior
