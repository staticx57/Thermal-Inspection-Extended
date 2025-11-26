# FLIR Boson SDK Integration Plan

**Date**: 2025-11-24
**Version**: 1.0
**Status**: Implementation Roadmap

---

## Executive Summary

The FLIR Boson SDK provides 35 modules with hundreds of functions for advanced thermal camera control. Currently, the thermal inspection tool only uses **4 basic features**:
- Serial number reading
- FFC (Flat Field Correction) trigger
- Gain mode control (HIGH/LOW/AUTO)
- Color LUT control

This plan outlines a phased approach to integrate **essential SDK features** for professional thermal inspection, prioritizing capabilities that directly enhance defect detection and analysis.

---

## Current Implementation Status

### ✅ Already Implemented (v2.7.2)

**File**: `boson_sdk_wrapper.py`

```python
class BosonSDK:
    # Implemented features:
    - get_info()              # Camera serial, version, part numbers
    - run_ffc()               # Trigger Flat Field Correction
    - set_ffc_mode()          # AUTO/MANUAL/EXTERNAL
    - set_gain_mode()         # HIGH/LOW/AUTO/MANUAL
    - set_color_lut()         # 10 palette options
    - get_fpa_temperature()   # FPA temperature in K/C
```

### 📊 SDK Modules Available (35 Total)

From `flirsdkraw.txt` (17,066 lines, 340KB):

| Priority | Module | Functions | Purpose | Status |
|----------|--------|-----------|---------|--------|
| 🔴 **CRITICAL** | RADIOMETRY | 56 functions | Temperature measurement, calibration | ❌ Not implemented |
| 🔴 **CRITICAL** | AGC | 27 functions | Image enhancement, contrast | ❌ Not implemented |
| 🟡 **HIGH** | SPOTMETER | 9 functions | Point temperature reading | ❌ Not implemented |
| 🟡 **HIGH** | ISOTHERM | 16 functions | Temperature range visualization | ❌ Not implemented |
| 🟡 **HIGH** | TLINEAR | 4 functions | Temperature conversion LUT | ❌ Not implemented |
| 🟢 **MEDIUM** | COLORLUT | 6 functions | Palette control | ✅ Partially implemented |
| 🟢 **MEDIUM** | BOSON | 64 functions | Camera settings, FFC, gain | ✅ Partially implemented |
| 🟢 **MEDIUM** | SYSINFO | 13 functions | Camera info, diagnostics | ✅ Partially implemented |
| ⚪ **LOW** | SYMBOLOGY | 26 functions | Overlay graphics | ❌ Not implemented |
| ⚪ **LOW** | CAPTURE | 6 functions | Frame capture | ❌ Not implemented |
| ⚪ **LOW** | DVO | 28 functions | Digital video output | ❌ Not implemented |
| ⚪ **LOW** | SCALER | 5 functions | Image scaling | ❌ Not implemented |

**Additional modules** (24 more): BPR, DUMMY, FILEOPS, FLASHIO, FLASHMAPFS, GAO, IMAGESTATS, JFFS2, LFSR, MEM, ROIC, SCNR, SFFC, SPLASHSCREEN, SPNR, SRNR, SYSCTRL, SYSTEMSYMBOLS, TELEMETRY, TESTRAMP, TF, UART

---

## Phase 1: Essential Features (Week 1-2)

### 🔴 Priority 1A: RADIOMETRY Module

**Why Critical**: Enables accurate temperature measurement from thermal pixels.

**Key Functions to Implement**:

```python
# Temperature Measurement
radiometryGetTempStableEnable()          # Check if temps are stable
radiometryGetGlobalGainDesired()         # Get gain correction
radiometryGetGlobalOffsetDesired()       # Get offset correction
radiometryGetTempLensHousing()           # Lens housing temp
radiometryGetTempShutterHousing()        # Shutter housing temp
radiometryGetTempShutterPaddle()         # Shutter paddle temp

# Calibration Parameters
radiometryGetFNumberLens0()              # F-number for temp calculation
radiometryGetTauLens0()                  # Lens transmission
radiometrySetFNumberLens0(fnumber)       # Set F-number
radiometrySetTauLens0(tau)               # Set transmission

# Temperature Conversion
radiometryGetEmissivityShutterHousing()  # Emissivity values
radiometrySetDampingFactor(factor)       # Temporal smoothing
```

**Implementation**:

```python
class BosonSDK:
    # ========================================================================
    # RADIOMETRY - Temperature Measurement
    # ========================================================================

    def enable_radiometry(self) -> bool:
        """Enable radiometric temperature measurement."""
        result = self.camera.radiometrySetTempStableEnable(True)
        return result.value == 0

    def get_lens_temperature(self) -> Optional[float]:
        """Get lens housing temperature in Celsius."""
        result, temp_k = self.camera.radiometryGetTempLensHousing()
        if result.value == 0:
            return temp_k / 10.0 - 273.15
        return None

    def get_shutter_temperature(self) -> Optional[float]:
        """Get shutter housing temperature in Celsius."""
        result, temp_k = self.camera.radiometryGetTempShutterHousing()
        if result.value == 0:
            return temp_k / 10.0 - 273.15
        return None

    def set_lens_parameters(self, f_number: float, transmission: float) -> bool:
        """
        Set lens optical parameters for accurate temperature calculation.

        Args:
            f_number: Lens F-number (e.g., 1.0, 1.4, 2.0)
            transmission: Lens transmission coefficient (0.0-1.0)
        """
        result1 = self.camera.radiometrySetFNumberLens0(int(f_number * 100))
        result2 = self.camera.radiometrySetTauLens0(int(transmission * 8192))
        return result1.value == 0 and result2.value == 0

    def get_calibration_info(self) -> dict:
        """Get all radiometric calibration parameters."""
        info = {}

        # Gain and offset
        result, gain = self.camera.radiometryGetGlobalGainDesired()
        if result.value == 0:
            info['global_gain'] = gain

        result, offset = self.camera.radiometryGetGlobalOffsetDesired()
        if result.value == 0:
            info['global_offset'] = offset

        # Lens parameters
        result, f_num = self.camera.radiometryGetFNumberLens0()
        if result.value == 0:
            info['f_number'] = f_num / 100.0

        result, tau = self.camera.radiometryGetTauLens0()
        if result.value == 0:
            info['transmission'] = tau / 8192.0

        # Temperatures
        info['lens_temp_c'] = self.get_lens_temperature()
        info['shutter_temp_c'] = self.get_shutter_temperature()

        return info
```

**Impact**: Enables pixel-to-temperature conversion for hotspot detection.

---

### 🔴 Priority 1B: AGC Module

**Why Critical**: Controls image contrast and detail enhancement.

**Key Functions to Implement**:

```python
# AGC Mode Control
agcSetMaxGain(gain)                      # Limit contrast enhancement
agcGetMaxGain()                          # Get current max gain
agcSetGamma(gamma)                       # Contrast curve (ACE)
agcGetGamma()                            # Get gamma value

# Histogram Control
agcSetLinearPercent(percent)             # Linear vs. adaptive (0-100%)
agcGetLinearPercent()
agcSetOutlierCut(percent)                # Ignore pixel outliers
agcGetOutlierCut()

# Detail Enhancement (DDE)
agcSetd2br(ratio)                        # Detail-to-background ratio
agcGetd2br()
agcSetSigmaR(sigma)                      # Edge-preserving smoothing
agcGetSigmaR()

# ROI Processing
agcSetROI(roi)                           # AGC based on ROI
agcGetROI()
```

**Implementation**:

```python
class BosonSDK:
    # ========================================================================
    # AGC - Automatic Gain Control
    # ========================================================================

    def set_agc_max_gain(self, gain: float) -> bool:
        """
        Set maximum AGC gain (contrast limit).

        Args:
            gain: Max gain (1.0 = no limit, 2.0 = 2x max contrast, etc.)
        """
        result = self.camera.agcSetMaxGain(gain)
        return result.value == 0

    def set_agc_gamma(self, gamma: float) -> bool:
        """
        Set gamma correction (ACE - Automatic Contrast Enhancement).

        Args:
            gamma: Gamma value (0.5-2.0, default 1.0)
                   - <1.0 = more contrast in hot areas
                   - >1.0 = more contrast in cold areas
        """
        result = self.camera.agcSetGamma(gamma)
        return result.value == 0

    def set_agc_linearity(self, percent: float) -> bool:
        """
        Set AGC linearity (histogram vs. linear mapping).

        Args:
            percent: Linearity (0-100%)
                     - 0% = fully adaptive (histogram-based)
                     - 100% = fully linear (no adaptation)
        """
        result = self.camera.agcSetLinearPercent(percent)
        return result.value == 0

    def set_detail_enhancement(self, dde_ratio: float) -> bool:
        """
        Set DDE (Digital Detail Enhancement).

        Args:
            dde_ratio: Detail-to-background ratio (0.0-3.0, typical 1.3)
                       - Higher = sharper edges, more detail
        """
        result = self.camera.agcSetd2br(dde_ratio)
        return result.value == 0

    def set_agc_roi(self, x_start: int, y_start: int,
                    x_stop: int, y_stop: int) -> bool:
        """
        Set AGC region of interest.
        AGC will optimize contrast based on this region.
        """
        roi = {
            'rowStart': y_start,
            'rowStop': y_stop,
            'colStart': x_start,
            'colStop': x_stop
        }
        result = self.camera.agcSetROI(roi)
        return result.value == 0

    def get_agc_settings(self) -> dict:
        """Get all AGC settings."""
        settings = {}

        result, gain = self.camera.agcGetMaxGain()
        if result.value == 0:
            settings['max_gain'] = gain

        result, gamma = self.camera.agcGetGamma()
        if result.value == 0:
            settings['gamma'] = gamma

        result, linear = self.camera.agcGetLinearPercent()
        if result.value == 0:
            settings['linearity_percent'] = linear

        result, dde = self.camera.agcGetd2br()
        if result.value == 0:
            settings['dde_ratio'] = dde

        return settings
```

**Impact**: Dramatically improves image quality for defect detection.

---

## Phase 2: Advanced Inspection Features (Week 3-4)

### 🟡 Priority 2A: SPOTMETER Module

**Why Important**: Enables point temperature measurement at cursor location.

**Key Functions**:

```python
spotMeterSetEnable(enable)               # Enable/disable spotmeter
spotMeterGetEnable()
spotMeterSetRoi(roi)                     # Set measurement location
spotMeterGetRoi()
spotMeterGetTempStats()                  # Get temperature at spot
spotMeterGetSpotStats()                  # Get min/max/avg in spot
```

**Implementation**:

```python
class BosonSDK:
    # ========================================================================
    # SPOTMETER - Point Temperature Measurement
    # ========================================================================

    def enable_spotmeter(self, enable: bool = True) -> bool:
        """Enable/disable spot temperature measurement."""
        result = self.camera.spotMeterSetEnable(1 if enable else 0)
        return result.value == 0

    def set_spotmeter_location(self, x: int, y: int,
                               width: int = 10, height: int = 10) -> bool:
        """
        Set spotmeter measurement location.

        Args:
            x, y: Center coordinates
            width, height: ROI size for averaging
        """
        roi = {
            'rowStart': y - height // 2,
            'rowStop': y + height // 2,
            'colStart': x - width // 2,
            'colStop': x + width // 2
        }
        result = self.camera.spotMeterSetRoi(roi)
        return result.value == 0

    def get_spotmeter_temperature(self) -> Optional[dict]:
        """
        Get temperature at spotmeter location.

        Returns:
            {'temp_k', 'temp_c', 'temp_f', 'min', 'max', 'avg'}
        """
        result, temp_k, temp_c, temp_f = self.camera.spotMeterGetTempStats()
        if result.value == 0:
            return {
                'temp_k': temp_k / 100.0,
                'temp_c': temp_c / 100.0,
                'temp_f': temp_f / 100.0
            }

        # Fallback to spot stats
        result, min_val, max_val, avg_val = self.camera.spotMeterGetSpotStats()
        if result.value == 0:
            return {
                'min': min_val,
                'max': max_val,
                'avg': avg_val
            }

        return None
```

**GUI Integration**:
- Add crosshair overlay on thermal image
- Display temperature reading next to cursor
- Click to lock measurement location

---

### 🟡 Priority 2B: ISOTHERM Module

**Why Important**: Highlights temperature ranges (e.g., "show all pixels >50°C").

**Key Functions**:

```python
isothermSetEnable(enable)                # Enable/disable isotherm
isothermGetEnable()
isothermSetTemps(t_low, t_mid, t_high)   # Set temperature thresholds
isothermGetTemps()
isothermSetIsoColorValues(r, g, b)       # Set highlight color
isothermGetIsoColorValues()
isothermSetRegionMode(mode)              # ABOVE/BELOW/BETWEEN range
isothermGetRegionMode()
isothermSetUnit(unit)                    # KELVIN/CELSIUS/FAHRENHEIT
isothermGetUnit()
```

**Implementation**:

```python
class BosonSDK:
    # ========================================================================
    # ISOTHERM - Temperature Range Visualization
    # ========================================================================

    def enable_isotherm(self, enable: bool = True) -> bool:
        """Enable/disable isotherm highlighting."""
        result = self.camera.isothermSetEnable(1 if enable else 0)
        return result.value == 0

    def set_isotherm_range(self, temp_low_c: float, temp_high_c: float) -> bool:
        """
        Set temperature range to highlight.

        Args:
            temp_low_c: Lower threshold in Celsius
            temp_high_c: Upper threshold in Celsius
        """
        # Convert to Kelvin * 10 (SDK format)
        t_low = int((temp_low_c + 273.15) * 10)
        t_high = int((temp_high_c + 273.15) * 10)
        t_mid = (t_low + t_high) // 2

        result = self.camera.isothermSetTemps(t_low, t_mid, t_high)
        return result.value == 0

    def set_isotherm_color(self, r: int, g: int, b: int) -> bool:
        """
        Set color for highlighted temperature range.

        Args:
            r, g, b: Color values (0-255)
        """
        result = self.camera.isothermSetIsoColorValues(r, g, b)
        return result.value == 0

    def set_isotherm_mode(self, mode: str) -> bool:
        """
        Set isotherm region mode.

        Args:
            mode: 'above', 'below', or 'between'
        """
        mode_map = {
            'above': 0,    # Highlight pixels above threshold
            'below': 1,    # Highlight pixels below threshold
            'between': 2   # Highlight pixels between thresholds
        }

        sdk_mode = mode_map.get(mode.lower())
        if sdk_mode is None:
            return False

        result = self.camera.isothermSetRegionMode(sdk_mode)
        return result.value == 0

    def get_isotherm_settings(self) -> dict:
        """Get current isotherm settings."""
        settings = {}

        result, enabled = self.camera.isothermGetEnable()
        if result.value == 0:
            settings['enabled'] = bool(enabled)

        result, t_low, t_mid, t_high = self.camera.isothermGetTemps()
        if result.value == 0:
            settings['temp_low_c'] = (t_low / 10.0) - 273.15
            settings['temp_mid_c'] = (t_mid / 10.0) - 273.15
            settings['temp_high_c'] = (t_high / 10.0) - 273.15

        result, r, g, b = self.camera.isothermGetIsoColorValues()
        if result.value == 0:
            settings['color_rgb'] = (r, g, b)

        return settings
```

**GUI Integration**:
- Add "Isotherm" panel with:
  - Enable/disable checkbox
  - Low/high temperature sliders
  - Color picker for highlight color
  - Mode dropdown (Above/Below/Between)
  - Live preview showing highlighted regions

---

### 🟡 Priority 2C: TLINEAR Module

**Why Important**: Converts 16-bit thermal values to temperature.

**Key Functions**:

```python
TLinearSetControl(enable)                # Enable temperature conversion
TLinearGetControl()
TLinearGetLUT(mode, offset)              # Get conversion lookup table
TLinearRefreshLUT(mode)                  # Recalculate LUT
```

**Implementation**:

```python
class BosonSDK:
    # ========================================================================
    # TLINEAR - Temperature Conversion
    # ========================================================================

    def enable_tlinear(self, enable: bool = True) -> bool:
        """Enable TLinear temperature conversion mode."""
        result = self.camera.TLinearSetControl(1 if enable else 0)
        return result.value == 0

    def refresh_temperature_lut(self) -> bool:
        """
        Refresh temperature lookup table.
        Call after changing radiometry parameters.
        """
        # Mode 0 = default table type
        result = self.camera.TLinearRefreshLUT(0)
        return result.value == 0

    def get_temperature_lut(self, offset: int = 0) -> Optional[dict]:
        """
        Get temperature conversion coefficients.

        Returns:
            {'a': [coeff_a], 'b': [coeff_b]} for T = a * pixel + b
        """
        result, a_array, b_array = self.camera.TLinearGetLUT(0, offset)
        if result.value == 0:
            return {
                'a': list(a_array),
                'b': list(b_array)
            }
        return None
```

---

## Phase 3: Professional Features (Week 5-6)

### 🟢 Priority 3A: SYMBOLOGY Module

**Purpose**: Overlay graphics, reticles, and indicators on thermal image.

**Key Functions**:

```python
symbologySetEnable(enable)
symbologyCreateBitmap(...)               # Create custom overlay
symbologyCreateText(...)                 # Add text annotations
symbologySetSpotmeterEnable(enable)      # Show spotmeter crosshair
symbologySetIsothermEnable(enable)       # Show isotherm overlay
```

**Use Cases**:
- Add measurement crosshairs
- Display temperature values on-screen
- Draw ROI boxes
- Show anomaly markers

---

### 🟢 Priority 3B: Enhanced BOSON Module

**Additional Functions to Implement**:

```python
# Lens Control
bosonSetExtSyncMode(mode)                # External trigger sync
bosonGetExtSyncMode()
bosonSetFrameRate(fps)                   # Frame rate control
bosonGetFrameRate()

# Advanced FFC
bosonGetFFCStatus()                      # Check if FFC in progress
bosonGetFFCTempDelta()                   # Temp change since last FFC
bosonSetFFCTempDelta(delta)              # Set auto-FFC trigger threshold

# Image Statistics
bosonGetLastFFC()                        # Time since last FFC
bosonGetFrameCount()                     # Current frame count
bosonGetBoardTemp()                      # Board temperature
```

---

### 🟢 Priority 3C: CAPTURE Module

**Purpose**: Save raw thermal frames to camera memory.

**Key Functions**:

```python
captureSingleFrame()                     # Capture current frame
captureFrames(settings)                  # Capture sequence
captureGetStatus()                       # Get capture status
```

**Use Cases**:
- Snapshot high-resolution thermal data
- Capture frame sequences for analysis
- Export raw radiometric data

---

## Phase 4: Advanced Features (Week 7-8)

### ⚪ Additional Modules (As Needed)

**SCALER** - Image resizing and cropping
**DVO** - Digital video output configuration
**TELEMETRY** - Metadata embedding
**SYSCTRL** - System control (reboot, save settings)
**FILEOPS** - File management on camera

---

## Implementation Priority Matrix

### 🔴 **MUST HAVE** (Phase 1) - 2 weeks
- ✅ RADIOMETRY: Temperature measurement and calibration
- ✅ AGC: Image contrast and enhancement

**Deliverable**: Accurate temperature readings and optimized image quality.

---

### 🟡 **SHOULD HAVE** (Phase 2) - 2 weeks
- ✅ SPOTMETER: Point temperature measurement
- ✅ ISOTHERM: Temperature range visualization
- ✅ TLINEAR: Temperature conversion LUT

**Deliverable**: Interactive temperature analysis and anomaly highlighting.

---

### 🟢 **NICE TO HAVE** (Phase 3) - 2 weeks
- ⚪ SYMBOLOGY: Overlay graphics and annotations
- ⚪ BOSON (Extended): Advanced FFC and frame control
- ⚪ CAPTURE: Frame capture to camera memory

**Deliverable**: Professional overlay graphics and capture capabilities.

---

### ⚪ **FUTURE** (Phase 4+) - As needed
- SCALER, DVO, TELEMETRY, SYSCTRL, etc.

---

## GUI Integration Plan

### Phase 1 GUI (Radiometry + AGC)

**New Panel**: "Temperature & Image Settings"

```
┌─────────────────────────────────────────────┐
│ Temperature Calibration                     │
├─────────────────────────────────────────────┤
│ Lens F-number:    [1.0]                    │
│ Transmission:     [95%]                     │
│ Emissivity:       [0.95]                    │
│                                             │
│ Temperatures:                               │
│   FPA:     32.5°C                          │
│   Lens:    31.2°C                          │
│   Shutter: 32.1°C                          │
│                                             │
│ [Refresh Calibration]                       │
├─────────────────────────────────────────────┤
│ Image Enhancement (AGC)                     │
├─────────────────────────────────────────────┤
│ Max Gain:         ──●────────── [2.0x]     │
│ Gamma (ACE):      ──────●────── [1.0]      │
│ Linearity:        ────●──────── [50%]      │
│ Detail (DDE):     ──────●────── [1.3]      │
│                                             │
│ [Reset to Defaults]                         │
└─────────────────────────────────────────────┘
```

---

### Phase 2 GUI (Spotmeter + Isotherm)

**New Panel**: "Temperature Analysis"

```
┌─────────────────────────────────────────────┐
│ Spot Measurement                            │
├─────────────────────────────────────────────┤
│ ☑ Enable Spotmeter                         │
│                                             │
│ Location: Click on image or enter below    │
│   X: [320]  Y: [256]                       │
│   Size: [10x10] pixels                     │
│                                             │
│ Temperature: 45.3°C (113.5°F)              │
│   Min: 44.1°C    Max: 46.8°C              │
│   Avg: 45.3°C    Std: 0.7°C               │
│                                             │
│ [Lock Measurement]                          │
├─────────────────────────────────────────────┤
│ Temperature Range Highlighting (Isotherm)   │
├─────────────────────────────────────────────┤
│ ☑ Enable Isotherm                          │
│                                             │
│ Low Temp:  ──●──────────── [40°C]         │
│ High Temp: ────────●────── [60°C]         │
│                                             │
│ Mode: ◉ Between  ○ Above  ○ Below         │
│                                             │
│ Highlight Color: [🎨] (Red)                │
│                                             │
│ [Apply]                                     │
└─────────────────────────────────────────────┘
```

---

## Testing Strategy

### Phase 1 Testing (Radiometry + AGC)

**Test Cases**:
1. ✅ Verify temperature calibration parameters read correctly
2. ✅ Test lens F-number and transmission adjustments
3. ✅ Validate FPA/lens/shutter temperature readings
4. ✅ Verify AGC settings affect image contrast
5. ✅ Test gamma correction (ACE) on hot/cold scenes
6. ✅ Validate DDE enhances edge detail

**Test Equipment**:
- Known-temperature targets (blackbody or boiling water)
- Various thermal scenes (hot/cold objects)
- Thermal reference thermometer

---

### Phase 2 Testing (Spotmeter + Isotherm)

**Test Cases**:
1. ✅ Verify spotmeter reports accurate temperature
2. ✅ Test spotmeter at various image locations
3. ✅ Validate min/max/avg calculations in ROI
4. ✅ Test isotherm highlighting at different thresholds
5. ✅ Verify isotherm modes (above/below/between)
6. ✅ Test color customization

**Validation**:
- Compare spotmeter readings with reference thermometer
- Verify isotherm highlights match expected pixel ranges

---

## Performance Considerations

### SDK Call Overhead

Each SDK function call has ~5-10ms latency due to serial communication.

**Optimization Strategies**:

1. **Batch Settings**: Group related settings together, apply once
2. **Cache Values**: Store frequently-used values locally
3. **Background Thread**: Run SDK calls in separate thread
4. **Rate Limiting**: Update SDK settings max 10 Hz (every 100ms)

**Example**:

```python
class BosonSDKOptimized:
    def __init__(self):
        self._settings_cache = {}
        self._last_update = 0
        self._update_interval = 0.1  # 100ms

    def set_agc_settings(self, **kwargs):
        """Batch update AGC settings."""
        current_time = time.time()

        # Rate limit updates
        if current_time - self._last_update < self._update_interval:
            # Queue for next update
            self._settings_cache.update(kwargs)
            return

        # Apply all cached settings at once
        for key, value in self._settings_cache.items():
            if key == 'max_gain':
                self.camera.agcSetMaxGain(value)
            elif key == 'gamma':
                self.camera.agcSetGamma(value)
            # ... etc

        self._settings_cache.clear()
        self._last_update = current_time
```

---

## File Structure Updates

### New Files to Create

```
boson_sdk_wrapper.py          # Update with new modules
├── radiometry_module.py       # RADIOMETRY implementation
├── agc_module.py              # AGC implementation
├── spotmeter_module.py        # SPOTMETER implementation
├── isotherm_module.py         # ISOTHERM implementation
└── tlinear_module.py          # TLINEAR implementation

inspection_gui_qt.py           # Add new panels
├── TemperatureCalibrationPanel
├── AGCControlPanel
├── SpotMeterPanel
└── IsothermPanel

inspection_main.py             # Connect SDK to GUI
└── Wire SDK callbacks to panel controls
```

---

## Risk Assessment

### Technical Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| SDK documentation incomplete | HIGH | MEDIUM | Test each function, document behavior |
| Serial communication timeouts | MEDIUM | MEDIUM | Implement retry logic, error handling |
| Temperature calibration errors | MEDIUM | HIGH | Validate against known targets |
| GUI becomes too complex | LOW | MEDIUM | Use tabs, collapsible sections |

---

## Success Metrics

### Phase 1 Success Criteria
- ✅ Temperature readings accurate within ±2°C
- ✅ AGC improves defect visibility (subjective)
- ✅ Settings saved/restored correctly
- ✅ No performance degradation (<5% FPS drop)

### Phase 2 Success Criteria
- ✅ Spotmeter accuracy ±1°C vs. reference
- ✅ Isotherm correctly highlights temperature ranges
- ✅ GUI responsive (<100ms for setting changes)
- ✅ Real-time updates without flicker

---

## Implementation Checklist

### Phase 1: RADIOMETRY + AGC (Week 1-2)

- [ ] Study RADIOMETRY SDK functions in detail
- [ ] Implement radiometry wrapper methods
- [ ] Test temperature calibration with known targets
- [ ] Implement AGC wrapper methods
- [ ] Create TemperatureCalibrationPanel GUI
- [ ] Create AGCControlPanel GUI
- [ ] Wire GUI controls to SDK
- [ ] Test with live camera
- [ ] Document all functions
- [ ] Update CHANGELOG.md

### Phase 2: SPOTMETER + ISOTHERM + TLINEAR (Week 3-4)

- [ ] Implement spotmeter wrapper methods
- [ ] Create SpotMeterPanel GUI with crosshair
- [ ] Add click-to-measure on thermal image
- [ ] Implement isotherm wrapper methods
- [ ] Create IsothermPanel GUI
- [ ] Implement TLINEAR for temperature conversion
- [ ] Test accuracy vs. reference thermometer
- [ ] Add config file persistence
- [ ] Update user documentation
- [ ] Update CHANGELOG.md

---

## Configuration File Support

### config.json Example (Full SDK Integration)

```json
{
  "sdk": {
    "enabled": true,
    "com_port": "COM6",
    "baudrate": 921600,

    "radiometry": {
      "enabled": true,
      "lens_f_number": 1.0,
      "lens_transmission": 0.95,
      "emissivity": 0.95,
      "damping_factor": 0.5
    },

    "agc": {
      "max_gain": 2.0,
      "gamma": 1.0,
      "linearity_percent": 50.0,
      "dde_ratio": 1.3,
      "outlier_cut_percent": 2.0
    },

    "spotmeter": {
      "enabled": false,
      "x": 320,
      "y": 256,
      "width": 10,
      "height": 10
    },

    "isotherm": {
      "enabled": false,
      "temp_low_c": 40.0,
      "temp_high_c": 60.0,
      "color_rgb": [255, 0, 0],
      "mode": "between",
      "unit": "celsius"
    },

    "tlinear": {
      "enabled": false
    }
  }
}
```

---

## Documentation Updates

### Files to Update

1. **README.md**
   - Add SDK features section
   - Update installation instructions
   - Document new GUI panels

2. **CHANGELOG.md**
   - Add v2.8.0 entry with SDK integration

3. **SDK_USAGE_GUIDE.md** (NEW)
   - Complete SDK function reference
   - Usage examples for each module
   - Troubleshooting guide

4. **TEMPERATURE_CALIBRATION_GUIDE.md** (NEW)
   - How to calibrate temperature readings
   - F-number and transmission values
   - Accuracy validation procedures

---

## Conclusion

This plan outlines a **phased, prioritized approach** to integrating the FLIR Boson SDK:

**Phase 1 (2 weeks)**: Essential temperature measurement and image quality (RADIOMETRY + AGC)
**Phase 2 (2 weeks)**: Interactive analysis tools (SPOTMETER + ISOTHERM + TLINEAR)
**Phase 3 (2 weeks)**: Professional overlays and capture (SYMBOLOGY + BOSON + CAPTURE)
**Phase 4 (As needed)**: Additional advanced features

Each phase builds on the previous, ensuring the tool remains functional throughout development while systematically adding professional thermal inspection capabilities.

---

**Next Step**: Begin Phase 1 implementation by adding RADIOMETRY functions to `boson_sdk_wrapper.py`.

**Estimated Total Time**: 6-8 weeks for Phases 1-3
**Version Target**: v2.8.0 (Phase 1), v2.9.0 (Phase 2), v3.0.0 (Phase 3)

---

**Document Version**: 1.0
**Last Updated**: 2025-11-24
**Author**: Claude Code
