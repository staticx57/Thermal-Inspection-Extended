# Boson SDK - Gap Analysis & Implementation Roadmap

**Date**: 2025-11-26
**Purpose**: Identify remaining SDK features to implement
**Current Version**: v2.8.0 (Phase 9 - Radiometric in progress)

---

## Executive Summary

### Implementation Status

| Category | Backend (SDK Wrapper) | GUI Integration | Status |
|----------|----------------------|-----------------|---------|
| **Universal Features** | 80% | 60% | 🟡 Partial |
| **Radiometric Features** | 40% | 30% | 🟡 In Progress |
| **Advanced Features** | 0% | 0% | 🔴 Not Started |

### Quick Stats

- **Total SDK Modules Available**: ~15
- **Modules with Backend Support**: 6 (FFC, Gain, LUT, AGC, Radiometry basic, Camera Info)
- **Modules Fully Integrated (Backend + GUI)**: 3 (FFC, Gain, LUT)
- **Missing Critical Features**: 9 modules

---

## Currently Implemented Features

### ✅ Universal Features (Working on ALL Boson Cameras)

#### 1. FFC (Flat Field Correction)
**Backend**: ✅ Complete
**GUI**: ✅ Complete (Simple Controls tab)

**Methods**:
- `run_ffc()` - Trigger manual FFC
- `set_ffc_mode(mode)` - AUTO/MANUAL/EXTERNAL
- `get_ffc_mode()` - Get current mode

**GUI Location**: Boson Control → Simple Controls → "Run FFC" button

---

#### 2. Gain Control
**Backend**: ✅ Complete
**GUI**: ✅ Complete (Simple Controls tab)

**Methods**:
- `set_gain_mode(mode)` - HIGH/LOW/AUTO/MANUAL
- `get_gain_mode()` - Get current mode

**GUI Location**: Boson Control → Simple Controls → Gain Mode dropdown

---

#### 3. Color LUT (Palettes)
**Backend**: ✅ Complete
**GUI**: ✅ Complete (Simple Controls tab)

**Methods**:
- `set_color_lut(lut)` - 10 palettes available

**GUI Location**: Boson Control → Simple Controls → Color Palette dropdown

**Note**: This is SDK-level palette control. Application also has its own palette system in `palette_manager.py`.

---

#### 4. AGC (Automatic Gain Control)
**Backend**: ✅ Complete
**GUI**: ✅ Complete (Advanced Controls tab)

**Methods**:
- `set_agc_max_gain(gain)` - Max contrast (1.0-4.0x)
- `set_agc_gamma(gamma)` - Gamma correction (0.5-2.0)
- `set_agc_linearity(percent)` - Histogram vs linear (0-100%)
- `set_detail_enhancement(dde)` - Edge sharpness (0.0-3.0)
- `set_agc_roi(x1, y1, x2, y2)` - ROI-based AGC
- `get_agc_settings()` - Get all params

**GUI Location**: Boson Control → Advanced Controls → Image Enhancement section

**Impact**: Significant image quality improvement for defect detection

---

#### 5. Camera Information
**Backend**: ✅ Complete
**GUI**: ✅ Complete (Connection tab)

**Methods**:
- `get_info()` - Serial, part number, firmware, etc.
- `get_fpa_temperature()` - Sensor temperature

**GUI Location**: Boson Control → Connection → Camera Info section

---

### ⏳ Radiometric Features (Partially Implemented)

#### 6. Basic Radiometry
**Backend**: ✅ Partial (detection, lens params, calibration info)
**GUI**: ✅ Partial (Radiometric tab in main panel)

**Methods Implemented**:
- `is_radiometric_capable()` - Detect radiometric camera
- `get_radiometric_status()` - Get status dict
- `enable_radiometry()` - Enable temperature measurement
- `get_lens_temperature()` - Lens housing temp
- `get_shutter_temperature()` - Shutter housing temp
- `set_lens_parameters(f_num, trans)` - Optical params
- `get_calibration_info()` - Gain/offset/temps

**GUI Location**:
- Main right panel → Radiometric tab (new panel)
- Boson Control → Radiometric tab (SDK controls - placeholder)

**Status**: Core radiometric converter complete, basic GUI functional, advanced features pending

---

## Missing Features - Priority Ranked

### 🔴 HIGH PRIORITY - Universal Features

These features work on **ALL Boson cameras** and provide immediate value to all users.

---

#### 1. Extended BOSON Module Functions

**Module**: 0x05 BOSON (64 functions available, only ~8 used)
**Compatibility**: ALL cameras
**Priority**: HIGH

**Missing Functions**:

```python
# System Status
def get_frame_count() -> int:
    """Get current frame number since boot."""

def get_board_temperature() -> float:
    """Get camera board temperature (°C)."""

# FFC Status & Control
def get_ffc_status() -> dict:
    """
    Check if FFC is currently running.
    Returns: {'in_progress': bool, 'progress': int}
    """

def get_ffc_temp_delta() -> float:
    """Get temperature change threshold for auto-FFC (°C)."""

def set_ffc_temp_delta(delta: float) -> bool:
    """Set auto-FFC temperature threshold (e.g., 3.0°C)."""

def get_last_ffc_time() -> float:
    """Get time since last FFC (seconds)."""

def get_ffc_statistics() -> dict:
    """
    Get FFC history and statistics.
    Returns: {'total_count': int, 'failed_count': int, 'avg_duration_ms': float}
    """

# External Sync
def set_ext_sync_mode(mode: str) -> bool:
    """
    Enable external trigger synchronization.
    Args:
        mode: 'master', 'slave', 'disabled'
    """

def get_ext_sync_mode() -> str:
    """Get current sync mode."""
```

**Use Cases**:
- Monitor camera health (board temp, frame count)
- Advanced FFC tuning (auto-FFC threshold)
- FFC progress indicator in GUI
- Synchronized multi-camera capture (ext sync)

**GUI Integration**:
```
┌─────────────────────────────────────────────┐
│ Camera Status & Diagnostics                 │
├─────────────────────────────────────────────┤
│ System:                                     │
│   Frame Count: 12,453                       │
│   Board Temp:  42.3°C                      │
│   FPA Temp:    32.5°C                      │
│                                             │
│ FFC Status:                                 │
│   Last FFC: 2 minutes ago                  │
│   Auto Threshold: 3.0°C                    │
│   Status: [████████──] 80%                 │
│   Total FFCs: 47 (0 failed)                │
│                                             │
│ [Refresh Status]                            │
└─────────────────────────────────────────────┘
```

**Implementation Effort**: 2-3 days (backend + GUI)

---

#### 2. CAPTURE Module - Frame Snapshot

**Module**: 0x07 CAPTURE (6 functions)
**Compatibility**: ALL cameras
**Priority**: HIGH

**Functions to Implement**:

```python
def capture_single_frame() -> bool:
    """Capture current thermal frame to camera memory."""

def capture_frames(count: int, interval_ms: int) -> bool:
    """
    Capture sequence of frames.
    Args:
        count: Number of frames to capture
        interval_ms: Time between captures
    """

def get_capture_status() -> dict:
    """
    Get capture progress.
    Returns: {'in_progress': bool, 'frames_captured': int, 'frames_total': int}
    """

def download_captured_frame(index: int) -> np.ndarray:
    """Download captured frame from camera memory."""

def clear_capture_buffer() -> bool:
    """Clear all captured frames from memory."""
```

**Use Cases**:
- Snapshot thermal frames for offline analysis
- Time-lapse thermal capture
- Defect documentation
- Before/after comparison

**GUI Integration**:
```
┌─────────────────────────────────────────────┐
│ Frame Capture                               │
├─────────────────────────────────────────────┤
│ Single Frame:                               │
│   [📷 Capture Now] → Save to memory        │
│                                             │
│ Sequence Capture:                           │
│   Frames: [10    ]                         │
│   Interval: [500 ] ms                      │
│   [▶ Start Sequence]                       │
│                                             │
│ Status: [████████──] 8/10 frames          │
│                                             │
│ [💾 Download All] [🗑️ Clear Buffer]       │
└─────────────────────────────────────────────┘
```

**Note**: This is camera-internal capture, separate from the application's snapshot feature.

**Implementation Effort**: 3-4 days (backend + GUI + file export)

---

#### 3. SYSCTRL Module - Settings Persistence

**Module**: 0x0F SYSCTRL (8 functions)
**Compatibility**: ALL cameras
**Priority**: MEDIUM-HIGH

**Functions to Implement**:

```python
def save_settings_to_flash() -> bool:
    """
    Save current camera settings to non-volatile memory.
    Settings will persist after power cycle.
    """

def restore_factory_defaults() -> bool:
    """Reset camera to factory settings."""

def freeze_video_output(enable: bool) -> bool:
    """
    Freeze video output (camera continues capturing internally).
    Useful for stable frame analysis.
    """

def reboot_camera() -> bool:
    """
    Soft reboot camera.
    WARNING: Disconnects SDK. Must reconnect after ~5 seconds.
    """
```

**Use Cases**:
- Persist AGC/FFC/gain settings across reboots
- Factory reset for troubleshooting
- Freeze frame for analysis
- Recovery from hung state

**GUI Integration**:
```
┌─────────────────────────────────────────────┐
│ Camera System Control                       │
├─────────────────────────────────────────────┤
│ Settings Management:                        │
│   [💾 Save Settings to Camera]             │
│   ⚠️ Current settings will persist after    │
│   power cycle                               │
│                                             │
│   [⚙️ Restore Factory Defaults]            │
│   ⚠️ WARNING: Clears all custom settings   │
│                                             │
│ System:                                     │
│   [🔄 Reboot Camera]                       │
│   ⚠️ SDK will disconnect                    │
│                                             │
│   ☐ Freeze Video Output                    │
└─────────────────────────────────────────────┘
```

**Implementation Effort**: 2 days (backend + GUI + safety warnings)

---

#### 4. DVO (Digital Video Output) Configuration

**Module**: 0x06 DVO (28 functions)
**Compatibility**: ALL cameras
**Priority**: LOW-MEDIUM

**Functions to Implement**:

```python
def set_output_format(format: str) -> bool:
    """
    Set camera output format.
    Args:
        format: 'YCbCr', 'RGB888', 'IR16' (16-bit raw)
    """

def get_output_format() -> str:
    """Get current output format."""

def set_analog_video_state(enable: bool) -> bool:
    """Enable/disable analog video output (if hardware supports)."""
```

**Use Cases**:
- Switch between 8-bit AGC output and 16-bit raw for radiometric
- Configure video format for specific capture hardware
- Less critical for USB UVC capture

**Implementation Effort**: 1-2 days

---

### 🟡 MEDIUM PRIORITY - Radiometric-Only Features

These features **ONLY** work on radiometric Boson cameras. Non-radiometric cameras will have these features disabled/grayed out.

---

#### 5. TLINEAR Module - Temperature Linearization

**Module**: 0x0E TLINEAR (4 functions)
**Compatibility**: **RADIOMETRIC ONLY**
**Priority**: HIGH (for radiometric users)

**Status**: Backend partially implemented in `radiometric_converter.py`, SDK methods missing

**Functions to Implement**:

```python
def tlinear_enable(enable: bool) -> bool:
    """
    Enable camera-internal temperature linearization.
    When enabled, camera outputs temperature instead of raw counts.
    """

def tlinear_get_enable() -> bool:
    """Check if TLinear is enabled."""

def tlinear_get_lut(mode: str) -> np.ndarray:
    """
    Download TLinear lookup table from camera.
    Args:
        mode: 'high_gain' or 'low_gain'
    Returns:
        Array mapping raw counts → temperature (Kelvin)
    """

def tlinear_refresh_lut() -> bool:
    """
    Recalculate TLinear LUT based on current calibration.
    Run after changing lens parameters or environmental conditions.
    """
```

**Use Cases**:
- High-accuracy temperature conversion (±0.5°C vs. ±2-5°C linear)
- Factory calibration data utilization
- Critical for professional radiometric measurement

**Integration**: Load LUT into `TLinearConverter` class for improved accuracy

**Implementation Effort**: 2-3 days (SDK methods + integration with converter)

---

#### 6. Advanced RADIOMETRY Functions

**Module**: 0x13 RADIOMETRY (56 functions, only ~7 used)
**Compatibility**: **RADIOMETRIC ONLY**
**Priority**: MEDIUM-HIGH (for radiometric users)

**Currently Missing**:

```python
# Environmental Compensation
def set_emissivity(emissivity: float) -> bool:
    """
    Set target emissivity (0.0-1.0).
    Examples: Polished aluminum=0.05, Matte paint=0.95
    """

def get_emissivity() -> float:
    """Get current emissivity setting."""

def set_atmospheric_transmission(transmission: float) -> bool:
    """
    Set atmospheric transmission factor (0.0-1.0).
    Compensates for humidity and distance.
    """

def set_reflected_temperature(temp_c: float) -> bool:
    """
    Set reflected background temperature.
    Used for accurate measurement of reflective surfaces.
    """

def set_target_distance(meters: float) -> bool:
    """
    Set distance to target.
    Affects atmospheric and lens transmission compensation.
    """

def get_radiometry_parameters() -> dict:
    """
    Get all radiometric compensation parameters.
    Returns: {
        'emissivity': float,
        'atmospheric_transmission': float,
        'reflected_temp_c': float,
        'distance_m': float
    }
    """

# Calibration
def set_radiometry_rbfo(gain: float, offset: float) -> bool:
    """Set custom gain/offset for temperature conversion."""

def get_radiometry_rbfo() -> dict:
    """Get current gain/offset values."""
```

**Use Cases**:
- Professional-grade temperature accuracy
- Material-specific emissivity correction
- Long-distance measurement compensation
- Reflective surface measurement

**GUI Integration**:
```
┌─────────────────────────────────────────────┐
│ Advanced Temperature Calibration            │
│ ⚠️ RADIOMETRIC CAMERAS ONLY                 │
├─────────────────────────────────────────────┤
│ Material Properties:                        │
│   Emissivity:       ──●──────── [0.95]     │
│   Presets: [Aluminum▾] [Apply]             │
│                                             │
│ Environmental:                              │
│   Distance (m):     ──●──────── [1.0]      │
│   Atm. Trans.:      ──────●──── [0.95]     │
│   Reflected Temp:   [25.0] °C              │
│                                             │
│ Sensor Temperatures:                        │
│   FPA:     32.5°C                          │
│   Lens:    31.2°C                          │
│   Shutter: 32.1°C                          │
│                                             │
│ [Apply Calibration] [Reset to Defaults]    │
└─────────────────────────────────────────────┘
```

**Implementation Effort**: 4-5 days (backend + GUI + emissivity presets)

---

#### 7. SPOTMETER Module - Point Temperature Measurement

**Module**: 0x26 SPOTMETER (9 functions)
**Compatibility**: **RADIOMETRIC ONLY**
**Priority**: HIGH (for radiometric users)

**Status**: Application has basic spotmeter in radiometric_panel.py, but not using SDK spotmeter

**Functions to Implement**:

```python
def spotmeter_enable(enable: bool) -> bool:
    """Enable SDK spotmeter (hardware-accelerated)."""

def spotmeter_set_roi(x: int, y: int, width: int, height: int) -> bool:
    """Set spotmeter ROI (e.g., 10x10 pixel window)."""

def spotmeter_get_temperature() -> float:
    """Get temperature at spotmeter location (°C)."""

def spotmeter_get_statistics() -> dict:
    """
    Get spotmeter statistics.
    Returns: {
        'temp_c': float,
        'min_c': float,
        'max_c': float,
        'avg_c': float,
        'std_c': float
    }
    """

def spotmeter_set_stats_mode(mode: str) -> bool:
    """Set spotmeter calculation mode: 'center', 'average', 'max', 'min'."""
```

**Use Cases**:
- Click-to-measure temperature
- Hardware-accelerated (faster than software)
- Multi-pixel averaging for stability

**Note**: Current radiometric_panel.py uses software spotmeter. SDK spotmeter would be faster but requires integration.

**Implementation Effort**: 2-3 days (SDK integration + GUI update)

---

#### 8. ISOTHERM Module - Temperature Range Highlighting

**Module**: 0x15 ISOTHERM (16 functions)
**Compatibility**: **RADIOMETRIC ONLY**
**Priority**: MEDIUM

**Functions to Implement**:

```python
def isotherm_enable(enable: bool) -> bool:
    """Enable isotherm highlighting."""

def isotherm_set_thresholds(low_c: float, high_c: float) -> bool:
    """Set temperature thresholds for highlighting."""

def isotherm_set_color(r: int, g: int, b: int) -> bool:
    """Set highlight color (RGB 0-255)."""

def isotherm_set_region_mode(mode: str) -> bool:
    """
    Set highlight mode.
    Args:
        mode: 'above' - highlight pixels > high_temp
              'below' - highlight pixels < low_temp
              'between' - highlight pixels in range
    """

def isotherm_set_unit(unit: str) -> bool:
    """Set temperature unit: 'celsius', 'fahrenheit', 'kelvin'."""

def isotherm_get_settings() -> dict:
    """Get all isotherm settings."""
```

**Use Cases**:
- Visual anomaly detection (e.g., "show all pixels >50°C in red")
- Temperature-based segmentation
- Quick hotspot identification

**GUI Integration**:
```
┌─────────────────────────────────────────────┐
│ Temperature Highlighting                    │
│ ⚠️ RADIOMETRIC CAMERAS ONLY                 │
├─────────────────────────────────────────────┤
│ ☑ Enable Isotherm                          │
│                                             │
│ Low Threshold:  ──●──────── [40°C]         │
│ High Threshold: ────────●── [60°C]         │
│                                             │
│ Highlight Mode:                             │
│   ◉ Between thresholds                      │
│   ○ Above high threshold                    │
│   ○ Below low threshold                     │
│                                             │
│ Highlight Color: [🎨 Red]                  │
│                                             │
│ [Apply] [Clear]                             │
└─────────────────────────────────────────────┘
```

**Implementation Effort**: 3-4 days (backend + GUI + color picker)

---

### 🔵 LOW PRIORITY - Advanced Features

#### 9. SYMBOLOGY Module - On-Camera Graphics

**Module**: 0x17 SYMBOLOGY (12 functions)
**Compatibility**: ALL cameras
**Priority**: LOW

**Functions**: Draw text/shapes directly on camera output (before USB)

**Use Case**: Overlay timestamp/temp directly in camera stream

**Note**: Application already has overlay system. Camera-level overlays are less flexible.

**Implementation Effort**: 3 days

---

#### 10. SYSINFO Module - Extended Diagnostics

**Module**: 0x0A SYSINFO (13 functions, only ~3 used)
**Compatibility**: ALL cameras
**Priority**: LOW

**Functions**: Error counters, system status flags, detailed version info

**Use Case**: Advanced diagnostics and troubleshooting

**Implementation Effort**: 2 days

---

## Implementation Roadmap

### Phase 9 Completion (Current) - 1 Week

**Goal**: Finish radiometric temperature measurement

- ✅ Radiometric converter (DONE)
- ✅ Basic radiometric GUI (DONE)
- ⏳ TLinear LUT loading from camera
- ⏳ Test with real radiometric camera
- ⏳ Documentation and user guide

---

### Phase 10: Essential Universal Features - 2 Weeks

**Goal**: Features that benefit ALL users

**Week 1**:
1. Extended BOSON functions (frame count, board temp, FFC status)
2. SYSCTRL module (save settings, freeze, reboot)

**Week 2**:
3. CAPTURE module (frame snapshot, sequence)
4. GUI integration and testing

**Deliverables**:
- Camera diagnostics panel
- Frame capture tool
- Settings persistence
- System control panel

---

### Phase 11: Advanced Radiometric - 2 Weeks

**Goal**: Professional temperature measurement for radiometric cameras

**Week 1**:
1. TLinear LUT SDK integration
2. Advanced radiometry (emissivity, distance, atmospheric compensation)

**Week 2**:
3. SDK spotmeter integration
4. Isotherm highlighting
5. Temperature accuracy validation

**Deliverables**:
- High-accuracy temperature conversion (±0.5°C)
- Environmental compensation controls
- Temperature range highlighting
- Calibration GUI

---

### Phase 12: Polish & Optional Features - 1 Week

**Goal**: Remaining low-priority features

1. DVO module (output format control)
2. Extended SYSINFO (diagnostics)
3. Documentation updates
4. Performance optimization

---

## Feature Priority Matrix

| Feature | Users Impacted | Implementation Effort | Priority Score | Rank |
|---------|---------------|----------------------|----------------|------|
| Extended BOSON (status, FFC) | ALL | Low | HIGH | 1 |
| CAPTURE (frame snapshot) | ALL | Medium | HIGH | 2 |
| SYSCTRL (save settings) | ALL | Low | HIGH | 3 |
| TLinear LUT loading | Radiometric | Medium | HIGH | 4 |
| Advanced RADIOMETRY | Radiometric | High | MEDIUM | 5 |
| SDK Spotmeter | Radiometric | Medium | MEDIUM | 6 |
| Isotherm highlighting | Radiometric | Medium | MEDIUM | 7 |
| DVO (output format) | ALL | Low | LOW | 8 |
| SYMBOLOGY (overlays) | ALL | Medium | LOW | 9 |
| SYSINFO (extended) | ALL | Low | LOW | 10 |

**Priority Score** = (Users Impacted × Value) / Implementation Effort

---

## Technical Debt & Refactoring

### Current Issues

1. **Dual Spotmeter Systems**
   - Application has software spotmeter (radiometric_panel.py)
   - SDK has hardware spotmeter (faster, but unused)
   - **Action**: Migrate to SDK spotmeter or clearly document why software is used

2. **Palette System Confusion**
   - SDK controls camera-internal palettes
   - Application has separate palette_manager.py
   - **Action**: Document which system is authoritative, or unify

3. **Temperature Conversion**
   - radiometric_converter.py uses linear approximation
   - SDK has TLinear LUT (higher accuracy)
   - **Action**: Integrate TLinear LUT as primary method

4. **Settings Persistence**
   - Application settings stored in config files
   - Camera settings not persisted to camera flash
   - **Action**: Add "Save to Camera" button to persist AGC/FFC/gain

---

## Documentation Needs

### User-Facing

1. **Feature Compatibility Table**
   - Which features work on which camera models
   - Clear "Radiometric Only" indicators in GUI

2. **Temperature Measurement Guide**
   - How to achieve accurate temperature readings
   - Emissivity table for common materials
   - Calibration procedure

3. **Camera Settings Guide**
   - What each AGC parameter does
   - When to use different gain modes
   - FFC best practices

### Developer-Facing

1. **SDK Integration Guide**
   - How to add new SDK functions
   - Testing procedure without hardware
   - Error handling patterns

2. **Architecture Documentation**
   - Flow diagram: SDK → Wrapper → Main → GUI
   - Where to add new features

---

## Testing Requirements

### Phase 10 (Universal Features)

**Required Hardware**: Any Boson camera

**Test Cases**:
1. Frame capture and download
2. Settings save/restore across reboot
3. Board temperature monitoring
4. FFC status tracking
5. Video freeze function

---

### Phase 11 (Radiometric Features)

**Required Hardware**: Radiometric Boson (e.g., 640-R)

**Test Cases**:
1. TLinear LUT download and accuracy
2. Emissivity compensation (test with aluminum vs. painted surface)
3. Distance compensation (measure at 1m vs. 5m)
4. SDK spotmeter vs. software spotmeter comparison
5. Isotherm highlighting accuracy
6. Temperature accuracy validation (blackbody reference)

---

## Conclusion

### Summary

- **9 major SDK modules** remain unimplemented or partially implemented
- **Phase 10** will add critical features for ALL users (diagnostics, capture, persistence)
- **Phase 11** will complete professional radiometric capabilities
- **Estimated Total**: 5-6 weeks for full SDK integration

### Next Immediate Action

After Phase 9 (radiometric basic) completion:
1. Implement extended BOSON functions (frame count, board temp, FFC status)
2. Add camera diagnostics panel to GUI
3. Test with actual hardware

### Long-Term Vision

A fully-featured thermal inspection tool with:
- ✅ Professional camera control for ALL Boson models
- ✅ High-accuracy radiometric temperature measurement
- ✅ Complete SDK feature coverage
- ✅ Intuitive GUI with clear capability indication
- ✅ Comprehensive documentation

---

**Document Version**: 1.0
**Last Updated**: 2025-11-26
**Next Review**: After Phase 9 completion
