# SDK Feature Categorization - Universal vs. Radiometric

**Date**: 2025-11-24
**Purpose**: Clean separation of SDK features by camera compatibility

---

## Overview

FLIR Boson cameras come in two variants:
- **Non-Radiometric**: AGC applied, 8-bit output, relative contrast only
- **Radiometric**: Raw 14-bit output, absolute temperature per pixel

This document categorizes SDK features into:
1. **Universal Features** - Work on ALL Boson cameras (both radiometric and non-radiometric)
2. **Radiometric-Only Features** - Require radiometric Boson

---

## 🌍 Universal Features (All Boson Cameras)

These features work on **ALL** Boson models, regardless of radiometric capability.

### ✅ Already Implemented

#### FFC (Flat Field Correction)
- `run_ffc()` - Trigger shutter correction
- `set_ffc_mode(mode)` - AUTO/MANUAL/EXTERNAL
- `get_ffc_mode()` - Get current mode

**Use Case**: Correct pixel non-uniformity, remove artifacts

---

#### Gain Control
- `set_gain_mode(mode)` - HIGH/LOW/AUTO/MANUAL
- `get_gain_mode()` - Get current mode

**Use Case**: Switch between sensitivity ranges

---

#### Color LUT
- `set_color_lut(lut)` - 10 palette options (WHITE_HOT, BLACK_HOT, RAINBOW, etc.)

**Use Case**: False color visualization

---

#### Camera Info
- `get_info()` - Serial number, firmware version, part numbers
- `get_fpa_temperature()` - Sensor temperature

**Use Case**: Diagnostics, logging

---

### ⏳ To Implement - Universal Features

#### AGC (Automatic Gain Control) - ✅ BACKEND DONE, GUI PENDING
**Module**: 0x09 (27 functions)
**Compatibility**: ALL Boson cameras

**Essential Functions** (already implemented in boson_sdk_wrapper.py):
- ✅ `set_agc_max_gain(gain)` - Limit contrast (1.0-4.0x)
- ✅ `set_agc_gamma(gamma)` - Gamma correction (0.5-2.0)
- ✅ `set_agc_linearity(percent)` - Histogram vs. linear (0-100%)
- ✅ `set_detail_enhancement(dde)` - Edge sharpness (0.0-3.0)
- ✅ `set_agc_roi(x1, y1, x2, y2)` - ROI-based AGC
- ✅ `get_agc_settings()` - Get all AGC params

**Use Case**:
- Improve image quality for defect detection
- Enhance contrast in challenging scenes
- Sharpen edges for better anomaly visibility

**GUI Integration**:
```
┌─────────────────────────────────────────────┐
│ Image Enhancement (AGC)                     │
│ Works on ALL Boson cameras                  │
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

#### BOSON Module (Extended)
**Module**: 0x05 (64 functions)
**Compatibility**: ALL Boson cameras

**Additional Functions to Implement**:
- `bosonGetFrameCount()` - Current frame count
- `bosonGetBoardTemp()` - Board temperature
- `bosonGetFFCStatus()` - Check if FFC in progress
- `bosonGetFFCTempDelta()` - Temp change since last FFC
- `bosonSetFFCTempDelta(delta)` - Set auto-FFC threshold
- `bosonGetLastFFC()` - Time since last FFC
- `bosonSetExtSyncMode(mode)` - External trigger sync
- `bosonGetExtSyncMode()`

**Use Case**:
- Monitor camera health
- Advanced FFC control
- External triggering for synchronized capture

---

#### COLORLUT Module (Extended)
**Module**: 0x0B (6 functions)
**Compatibility**: ALL Boson cameras

**Additional Functions** (beyond basic palette):
- `colorLutSetOutlineColor(r, g, b)` - Edge color for outlining
- `colorLutGetOutlineColor()` - Get current edge color

**Use Case**: Customize edge detection overlay colors

---

#### CAPTURE Module
**Module**: 0x07 (6 functions)
**Compatibility**: ALL Boson cameras

**Functions**:
- `captureSingleFrame()` - Capture current frame to camera memory
- `captureFrames(settings)` - Capture sequence
- `captureGetStatus()` - Get capture status

**Use Case**: Snapshot thermal frames for offline analysis

---

#### DVO (Digital Video Output)
**Module**: 0x06 (28 functions)
**Compatibility**: ALL Boson cameras

**Functions**:
- `dvoSetOutputFormat(format)` - RGB/YCbCr/IR16
- `dvoGetOutputFormat()`
- `dvoSetAnalogVideoState(enable)`
- `dvoGetAnalogVideoState()`

**Use Case**: Configure video output format

---

#### SYSINFO Module (Extended)
**Module**: 0x0A (13 functions)
**Compatibility**: ALL Boson cameras

**Additional Functions**:
- `sysinfoGetMonitorCount()` - Get error monitor count
- `sysinfoGetStatus()` - Get system status
- `sysinfoGetVersion()` - Get version info

**Use Case**: System diagnostics and health monitoring

---

#### SYSCTRL Module
**Module**: 0x0F (8 functions)
**Compatibility**: ALL Boson cameras

**Functions**:
- `sysctrlSetFreezeState(enable)` - Freeze video output
- `sysctrlDoReboot()` - Reboot camera
- `sysctrlSaveSettings()` - Save current settings to flash

**Use Case**: System control and settings persistence

---

## 🌡️ Radiometric-Only Features

These features **ONLY** work on radiometric Boson cameras. Non-radiometric cameras will gracefully disable these features.

### ⏳ To Implement - Radiometric Features

#### RADIOMETRY Module - ✅ BACKEND DONE, GUI PENDING
**Module**: 0x13 (56 functions)
**Compatibility**: **RADIOMETRIC ONLY**

**Essential Functions** (already implemented in boson_sdk_wrapper.py):
- ✅ `enable_radiometry()` - Enable radiometric measurement
- ✅ `get_lens_temperature()` - Lens housing temp
- ✅ `get_shutter_temperature()` - Shutter housing temp
- ✅ `set_lens_parameters(f_num, trans)` - Set optical params for accuracy
- ✅ `get_calibration_info()` - Get gain/offset/temps

**Additional Functions to Implement**:
- `radiometrySetEmissivity(emissivity)` - Set target emissivity (0.0-1.0)
- `radiometryGetEmissivity()` - Get current emissivity
- `radiometrySetAtmosphericTransmission(trans)` - Set atmospheric correction
- `radiometrySetReflectedTemp(temp)` - Set reflected background temp
- `radiometrySetDistance(meters)` - Set target distance

**Use Case**:
- Accurate temperature calibration
- Environmental compensation
- Professional thermal measurement

**GUI Integration**:
```
┌─────────────────────────────────────────────┐
│ Temperature Calibration                     │
│ ⚠️ RADIOMETRIC CAMERAS ONLY                 │
├─────────────────────────────────────────────┤
│ Lens F-number:      [1.0]                  │
│ Transmission:       [95%]                   │
│ Emissivity:         [0.95]                  │
│ Distance (m):       [1.0]                   │
│                                             │
│ Temperatures:                               │
│   FPA:     32.5°C                          │
│   Lens:    31.2°C                          │
│   Shutter: 32.1°C                          │
│                                             │
│ [Refresh Calibration]                       │
└─────────────────────────────────────────────┘
```

---

#### TLINEAR Module
**Module**: 0x0E (4 functions)
**Compatibility**: **RADIOMETRIC ONLY**

**Functions to Implement**:
- `TLinearSetControl(enable)` - Enable temperature conversion
- `TLinearGetControl()` - Get enable status
- `TLinearGetLUT(mode, offset)` - Get conversion lookup table
- `TLinearRefreshLUT(mode)` - Recalculate temperature mapping

**Use Case**:
- Convert raw 14-bit counts to Kelvin
- Temperature lookup table management
- Automatic temperature linearization

**Integration**: Used by RadiometricConverter class for pixel → temperature conversion

---

#### SPOTMETER Module
**Module**: 0x26 (9 functions)
**Compatibility**: **RADIOMETRIC ONLY** (requires absolute temperature)

**Functions to Implement**:
- `spotMeterSetEnable(enable)` - Enable spotmeter
- `spotMeterGetEnable()` - Get enable status
- `spotMeterSetRoi(roi)` - Set measurement location
- `spotMeterGetRoi()` - Get current ROI
- `spotMeterGetTempStats()` - Get temperature at spot (°C/°F/K)
- `spotMeterGetSpotStats()` - Get min/max/avg in spot
- `spotMeterSetStatsMode(mode)` - Set statistics mode

**Use Case**:
- Point temperature measurement
- Click-to-measure on thermal image
- Temperature probing for defects

**GUI Integration**:
```
┌─────────────────────────────────────────────┐
│ Spot Temperature Measurement                │
│ ⚠️ RADIOMETRIC CAMERAS ONLY                 │
├─────────────────────────────────────────────┤
│ ☑ Enable Spotmeter                         │
│                                             │
│ Click on image to measure temperature      │
│   X: [320]  Y: [256]                       │
│   Size: [10x10] pixels                     │
│                                             │
│ Temperature: 45.3°C (113.5°F)              │
│   Min: 44.1°C    Max: 46.8°C              │
│   Avg: 45.3°C    Std: 0.7°C               │
│                                             │
│ [Lock Measurement]                          │
└─────────────────────────────────────────────┘
```

---

#### ISOTHERM Module
**Module**: 0x15 (16 functions)
**Compatibility**: **RADIOMETRIC ONLY** (requires absolute temperature)

**Functions to Implement**:
- `isothermSetEnable(enable)` - Enable isotherm highlighting
- `isothermGetEnable()` - Get enable status
- `isothermSetTemps(low, mid, high)` - Set temperature thresholds
- `isothermGetTemps()` - Get current thresholds
- `isothermSetIsoColorValues(r, g, b)` - Set highlight color
- `isothermGetIsoColorValues()` - Get color
- `isothermSetRegionMode(mode)` - ABOVE/BELOW/BETWEEN
- `isothermGetRegionMode()` - Get mode
- `isothermSetUnit(unit)` - CELSIUS/FAHRENHEIT/KELVIN
- `isothermGetUnit()` - Get unit

**Use Case**:
- Highlight temperature ranges (e.g., "show all pixels >50°C")
- Visual anomaly detection
- Temperature-based segmentation

**GUI Integration**:
```
┌─────────────────────────────────────────────┐
│ Temperature Range Highlighting              │
│ ⚠️ RADIOMETRIC CAMERAS ONLY                 │
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

## Implementation Strategy

### Phase 1: Universal Features (All Cameras)
**Target**: v2.8.x
**Duration**: 2 weeks

1. ✅ RADIOMETRY backend (lens params, calibration info) - DONE
2. ✅ AGC backend (max gain, gamma, DDE) - DONE
3. ⏳ AGC GUI panel - NEXT
4. ⏳ Extended BOSON functions (frame count, board temp, FFC status)
5. ⏳ CAPTURE module (frame snapshot)

**Deliverable**: Enhanced image quality and camera control for ALL users

---

### Phase 2: Radiometric Features (Radiometric Cameras Only)
**Target**: v2.9.x
**Duration**: 2 weeks

1. ⏳ TLINEAR module (temperature conversion)
2. ⏳ RadiometricConverter class (raw → °C/°F/K)
3. ⏳ RADIOMETRY GUI panel (calibration settings)
4. ⏳ SPOTMETER module + GUI
5. ⏳ ISOTHERM module + GUI
6. ⏳ Temperature unit switching (°C ↔ °F ↔ K)

**Deliverable**: Professional temperature measurement for radiometric users

---

### Phase 3: Advanced Features (Mixed)
**Target**: v3.0.x
**Duration**: 2 weeks

**Universal**:
- SYMBOLOGY module (overlays, graphics)
- DVO module (video output control)
- SYSCTRL module (settings persistence)

**Radiometric-Only**:
- Advanced RADIOMETRY (emissivity, distance, atmospheric correction)
- Calibration file support
- Temperature accuracy validation

---

## Feature Detection & Graceful Degradation

### Automatic Feature Locking

The application will automatically detect camera type and enable/disable features:

```python
class ThermalInspectionFusion:
    def _initialize_camera(self):
        """Initialize camera with feature detection."""
        # Detect radiometric capability
        capabilities = self.thermal_camera.get_camera_capabilities()
        self.is_radiometric = capabilities['is_radiometric']

        # Configure UI based on capabilities
        if self.is_radiometric:
            # Enable all features
            self.gui.radiometry_panel.setEnabled(True)
            self.gui.spotmeter_panel.setEnabled(True)
            self.gui.isotherm_panel.setEnabled(True)
            self.gui.temp_unit_selector.setEnabled(True)

            logger.info("✓ RADIOMETRIC mode - All features enabled")
        else:
            # Disable radiometric-only features
            self.gui.radiometry_panel.setEnabled(False)
            self.gui.spotmeter_panel.setEnabled(False)
            self.gui.isotherm_panel.setEnabled(False)
            self.gui.temp_unit_selector.setEnabled(False)

            # Show tooltips explaining why disabled
            self.gui.spotmeter_panel.setToolTip(
                "⚠️ SPOTMETER requires radiometric Boson camera\n"
                "Current camera: Non-radiometric (relative mode)"
            )

            logger.info("ℹ NON-RADIOMETRIC mode - Temperature features disabled")
```

### Visual Indicators

**Radiometric Camera Connected**:
```
┌─────────────────────────────────────────────┐
│ ✓ Boson 640 - RADIOMETRIC                  │
│ Absolute temperature measurement enabled    │
│ Range: -40°C to +550°C (±5°C accuracy)     │
└─────────────────────────────────────────────┘
```

**Non-Radiometric Camera Connected**:
```
┌─────────────────────────────────────────────┐
│ ℹ Boson 320 - NON-RADIOMETRIC               │
│ Relative mode only (no absolute temp)      │
│ Temperature features disabled               │
└─────────────────────────────────────────────┘
```

---

## Summary Tables

### Universal Features (All Boson Cameras)

| Module | Functions | Status | Priority | Use Case |
|--------|-----------|--------|----------|----------|
| AGC | 6 essential | ✅ Backend done | 🔴 HIGH | Image enhancement |
| BOSON | 8 extended | ⏳ Not started | 🟡 MEDIUM | Camera control |
| COLORLUT | 2 extended | ⏳ Not started | 🟢 LOW | Edge coloring |
| CAPTURE | 3 | ⏳ Not started | 🟢 LOW | Frame snapshot |
| DVO | 4 essential | ⏳ Not started | ⚪ FUTURE | Video output |
| SYSCTRL | 3 | ⏳ Not started | ⚪ FUTURE | Settings save |

**Total Universal Features**: ~26 functions

---

### Radiometric-Only Features

| Module | Functions | Status | Priority | Use Case |
|--------|-----------|--------|----------|----------|
| RADIOMETRY | 5 essential | ✅ Backend done | 🔴 HIGH | Temperature calibration |
| TLINEAR | 4 | ⏳ Not started | 🔴 HIGH | Temp conversion |
| SPOTMETER | 7 | ⏳ Not started | 🟡 MEDIUM | Point measurement |
| ISOTHERM | 10 | ⏳ Not started | 🟡 MEDIUM | Range highlighting |

**Total Radiometric Features**: ~26 functions

---

## Conclusion

**Clean Separation**:
- **Universal features** benefit ALL Boson users (better image quality, camera control)
- **Radiometric features** unlock professional temperature measurement for radiometric cameras

**User Experience**:
- Non-radiometric users: Get image enhancement and camera control
- Radiometric users: Get everything above PLUS absolute temperature measurement

**Development Strategy**:
- **Phase 1**: Implement universal features first (broader impact)
- **Phase 2**: Add radiometric features (specialized capability)
- **Graceful degradation**: Features auto-disable on incompatible hardware

---

**Document Version**: 1.0
**Last Updated**: 2025-11-24
**Author**: Claude Code
**Next Step**: Implement AGC GUI panel (universal feature for all cameras)
