# Radiometric Boson Integration Plan

**Date**: 2025-11-24
**Version**: 3.0.0 (Proposed)
**Status**: Planning Phase

---

## Executive Summary

This document outlines the plan to integrate full radiometric temperature measurement support for the FLIR Boson 640 radiometric camera model. The current system supports percentage-based (0-100%) and raw 14-bit values (0-16383), but lacks true absolute temperature measurement in Celsius, Fahrenheit, or Kelvin.

### Current State: 40% Complete
- ✅ Raw 14-bit value processing infrastructure
- ✅ Percentage normalization (0-100%)
- ✅ GUI controls for raw/percentage toggle
- ✅ Boson SDK serial communication framework
- ⚠️ Radiometric flag exists but not fully implemented
- ❌ No temperature conversion from raw counts
- ❌ No radiometric mode detection
- ❌ No FPA temperature compensation

### Target State: Full Radiometric Support
- ✅ Automatic radiometric vs non-radiometric detection
- ✅ Raw counts → Celsius/Fahrenheit/Kelvin conversion
- ✅ FPA temperature compensation
- ✅ Per-pixel absolute temperature measurement
- ✅ Proper unit display throughout UI (°C, °F, K)
- ✅ Calibration file support for accuracy
- ✅ Temperature range configuration per camera model

---

## Table of Contents

1. [Current Implementation Analysis](#current-implementation-analysis)
2. [Radiometric Camera Technical Background](#radiometric-camera-technical-background)
3. [Architecture Design](#architecture-design)
4. [Implementation Phases](#implementation-phases)
5. [Testing Strategy](#testing-strategy)
6. [Risk Assessment](#risk-assessment)
7. [Success Criteria](#success-criteria)

---

## Current Implementation Analysis

### 1. Percentage & Raw Value Features (✅ Functional)

**Location**: `inspection_gui_qt.py:1914-1929`

```python
# Value type selection in ManualThresholdWidget
self.percent_radio = QPushButton("Percentage")
self.percent_radio.setCheckable(True)
self.percent_radio.setChecked(True)  # Default

self.advanced_radio = QPushButton("Advanced (Raw)")
self.advanced_radio.setCheckable(True)
self.advanced_radio.setToolTip("Use raw 14-bit thermal values (0-16383)")
```

**Signal**: `use_raw_values_changed = pyqtSignal(bool)` (line 1878)

**Functionality**:
- Users can toggle between percentage (0-100%) and raw 14-bit values (0-16383)
- Used for manual threshold anomaly detection
- Properly wired through signal/slot architecture

**Status**: ✅ Working as designed for non-radiometric mode

---

### 2. Thermal Analyzer Radiometric Placeholder

**Location**: `thermal_analyzer.py:185-189`

```python
# Radiometric mode
self.is_radiometric = self.config.get("radiometric", False)
if not self.is_radiometric:
    self.temp_unit = TemperatureUnit.CELSIUS # Placeholder, will be treated as Raw
```

**Calibration Support**: Lines 944-953
```python
def set_calibration(self, offset: float, scale: float = 1.0):
    """Set calibration parameters for absolute temperature measurement."""
    self.calibration_offset = offset
    self.calibration_scale = scale
```

**Issues**:
- `is_radiometric` flag exists but no conversion logic
- Calibration exists but no source for offset/scale values
- Unit displayed as "°C" even for raw values when radiometric=False
- No FPA temperature compensation

**Status**: ⚠️ Partial implementation (placeholder)

---

### 3. Boson Serial Communication

**Location**: `boson_serial.py:0-199`

**Capabilities**:
- ✅ CCI protocol implementation
- ✅ FFC triggering
- ✅ AGC control
- ✅ Gain mode switching
- ✅ Camera info retrieval
- ✅ Telemetry configuration

**Radiometric Support**: Line 111
```python
@dataclass
class BosonCameraInfo:
    radiometric: bool = False  # Flag exists but never populated
```

**Missing**:
- ❌ No CCI commands to detect radiometric mode
- ❌ No FPA temperature reading
- ❌ No lookup table (LUT) retrieval
- ❌ No TLinear parameters reading

**Status**: ⚠️ Framework ready, radiometric commands needed

---

### 4. FLIR Camera Interface

**Location**: `flir_camera.py:165-193`

```python
def read_thermal(self) -> Tuple[bool, Optional[np.ndarray]]:
    # Diagnostic logging for frame type detection
    if frame.dtype == np.uint16:
        logger.info(f"  -> RAW THERMAL MODE (16-bit radiometric data)")
    elif frame.dtype == np.uint8:
        logger.info(f"  -> UVC MODE (8-bit YUV/RGB converted)")
```

**Observations**:
- ✅ Can detect 16-bit vs 8-bit frame format
- ❌ No handling of radiometric metadata (telemetry footer)
- ❌ Normalizes 16-bit to 8-bit (loses temperature precision)
- ❌ No per-pixel temperature extraction

**Status**: ⚠️ Detects format but doesn't preserve radiometric data

---

### 5. GUI Temperature Display

**Location**: `inspection_gui_qt.py:1814-1843`

```python
def update_statistics(self, stats: Optional[ThermalStatistics]):
    unit = stats.unit  # "°C" or " (raw)"
    text = (
        f"Min:  {stats.min_temp:.1f}{unit}\n"
        f"Max:  {stats.max_temp:.1f}{unit}\n"
        f"Mean: {stats.mean_temp:.1f}{unit}\n"
        f"Std:  {stats.std_temp:.1f}{unit}"
    )

def update_hot_spots(self, hot_spots: List[HotSpot]):
    self.hotspot_list.addItem(f"#{i}: {hs.max_temp:.1f}{hs.unit} at ...")
```

**Status**: ✅ Unit display infrastructure ready (just needs proper units)

---

## Radiometric Camera Technical Background

### What is a Radiometric Camera?

A **radiometric thermal camera** measures absolute temperature at each pixel by:

1. **Capturing Raw Counts**: 14-bit ADC values (0-16383) per pixel
2. **Applying Calibration**: Converting counts → radiance → temperature
3. **Compensating FPA Temperature**: Adjusting for sensor temperature drift
4. **Outputting Kelvin**: Absolute temperature in Kelvin (or Celsius/Fahrenheit)

### Boson Radiometric Models

| Model | Resolution | Raw Data | Temperature Range | Accuracy |
|-------|-----------|----------|-------------------|----------|
| Boson 320 | 320x256 | 14-bit | -40°C to +550°C | ±5°C or 5% |
| Boson 640 | 640x512 | 14-bit | -40°C to +550°C | ±5°C or 5% |

**Non-Radiometric**: AGC applied, 8-bit output, relative contrast only
**Radiometric**: Raw 14-bit output, absolute temperature per pixel

---

### Temperature Conversion Formula

For FLIR Boson radiometric cameras:

```
T_kelvin = (raw_counts - offset) / gain

Where:
- raw_counts: 14-bit ADC value (0-16383)
- offset: Camera-specific calibration offset
- gain: Camera-specific calibration gain (counts per Kelvin)
- T_kelvin: Absolute temperature in Kelvin
```

**Typical Values** (Boson 640):
- Gain: ~160 counts/K
- Offset: ~8000 counts (at FPA temp = 30°C)
- Valid range: 233K - 823K (-40°C to +550°C)

**Note**: FLIR provides these values via:
1. **Telemetry data** (embedded in video stream footer)
2. **CCI commands** (via serial SDK)
3. **Calibration files** (factory calibration)

---

### FPA Temperature Compensation

The **Focal Plane Array (FPA)** temperature affects the offset:

```
offset_compensated = offset_base + (T_fpa - T_fpa_ref) * fpa_coeff
```

**Why Important**:
- FPA temperature drifts during operation (warming up)
- Uncompensated offset causes ±5-10°C errors
- FFC (Flat Field Correction) recalibrates periodically

---

## Architecture Design

### Component Overview

```
┌──────────────────────────────────────────────────────────────┐
│                    Inspection Main GUI                        │
│  - Display temperature with proper units (°C/°F/K)           │
│  - Toggle between Celsius/Fahrenheit/Kelvin                  │
│  - Show radiometric status indicator                         │
└────────────────────┬─────────────────────────────────────────┘
                     │
                     ▼
┌──────────────────────────────────────────────────────────────┐
│              Thermal Analyzer (Enhanced)                      │
│  - is_radiometric: bool (auto-detected)                      │
│  - temp_unit: TemperatureUnit (C/F/K)                        │
│  - conversion_params: RadiometricParams                      │
│  - convert_raw_to_temp(raw_frame) -> temp_frame             │
└────────────────────┬─────────────────────────────────────────┘
                     │
                     ▼
┌──────────────────────────────────────────────────────────────┐
│           FLIR Camera (Enhanced) + Boson SDK                  │
│  - Detect radiometric mode (16-bit frame + telemetry)       │
│  - Extract telemetry footer (gain, offset, FPA temp)        │
│  - Read TLinear params via CCI                               │
│  - Return raw 16-bit frames (no normalization)              │
└────────────────────┬─────────────────────────────────────────┘
                     │
                     ▼
┌──────────────────────────────────────────────────────────────┐
│              Boson Serial (Enhanced)                          │
│  - Add CCI commands for radiometric detection                │
│  - Add CCI commands for TLinear params                       │
│  - Add FPA temperature reading                               │
│  - Add telemetry parsing                                     │
└──────────────────────────────────────────────────────────────┘
```

---

### New Data Structures

```python
@dataclass
class RadiometricParams:
    """Radiometric calibration parameters."""
    enabled: bool = False
    gain: float = 160.0  # counts per Kelvin
    offset: float = 8000.0  # counts at reference temp
    fpa_temp_k: float = 303.15  # FPA temperature in Kelvin (30°C)
    fpa_temp_ref_k: float = 303.15  # Reference FPA temp
    fpa_coeff: float = 1.0  # FPA temperature compensation coefficient
    valid_range_k: Tuple[float, float] = (233.15, 823.15)  # -40°C to +550°C

    def convert_to_kelvin(self, raw_counts: np.ndarray) -> np.ndarray:
        """Convert raw 14-bit counts to Kelvin."""
        # Compensate offset for FPA temperature drift
        offset_compensated = self.offset + (self.fpa_temp_k - self.fpa_temp_ref_k) * self.fpa_coeff

        # Convert to Kelvin
        temp_k = (raw_counts.astype(np.float32) - offset_compensated) / self.gain

        # Clamp to valid range
        temp_k = np.clip(temp_k, self.valid_range_k[0], self.valid_range_k[1])

        return temp_k

    def kelvin_to_celsius(self, temp_k: np.ndarray) -> np.ndarray:
        """Convert Kelvin to Celsius."""
        return temp_k - 273.15

    def kelvin_to_fahrenheit(self, temp_k: np.ndarray) -> np.ndarray:
        """Convert Kelvin to Fahrenheit."""
        return (temp_k - 273.15) * 9/5 + 32
```

---

### GUI Enhancements

#### 1. Temperature Unit Selector

**Location**: Analysis Panel → Statistics section

```python
class AnalysisPanel(QWidget):
    temp_unit_changed = pyqtSignal(str)  # "celsius", "fahrenheit", "kelvin"

    def _create_temp_unit_selector(self):
        """Add temperature unit toggle."""
        unit_group = QGroupBox("Temperature Unit")
        layout = QHBoxLayout(unit_group)

        self.celsius_btn = QPushButton("°C")
        self.fahrenheit_btn = QPushButton("°F")
        self.kelvin_btn = QPushButton("K")

        # Make checkable and mutually exclusive
        for btn in [self.celsius_btn, self.fahrenheit_btn, self.kelvin_btn]:
            btn.setCheckable(True)

        self.celsius_btn.setChecked(True)  # Default

        # Connect signals
        self.celsius_btn.clicked.connect(lambda: self.temp_unit_changed.emit("celsius"))
        self.fahrenheit_btn.clicked.connect(lambda: self.temp_unit_changed.emit("fahrenheit"))
        self.kelvin_btn.clicked.connect(lambda: self.temp_unit_changed.emit("kelvin"))
```

#### 2. Radiometric Status Indicator

**Location**: Analysis Panel → Header

```python
def _create_radiometric_indicator(self):
    """Show radiometric mode status."""
    self.radiometric_label = QLabel("Mode: Non-Radiometric (Relative)")
    self.radiometric_label.setStyleSheet("color: #888; font-size: 10px;")

def update_radiometric_status(self, is_radiometric: bool, params: RadiometricParams):
    """Update radiometric status display."""
    if is_radiometric:
        self.radiometric_label.setText(
            f"Mode: Radiometric (Absolute)\n"
            f"Range: {params.valid_range_k[0]-273.15:.0f}°C to {params.valid_range_k[1]-273.15:.0f}°C"
        )
        self.radiometric_label.setStyleSheet("color: #0a0; font-size: 10px;")
    else:
        self.radiometric_label.setText("Mode: Non-Radiometric (Relative)")
        self.radiometric_label.setStyleSheet("color: #888; font-size: 10px;")
```

#### 3. Enhanced Threshold Widget

**Update**: `ManualThresholdWidget`

Current states:
- Percentage (0-100%)
- Advanced (Raw 14-bit: 0-16383)

New states (if radiometric):
- Percentage (0-100%)
- Temperature (°C/°F/K)
- Advanced (Raw 14-bit: 0-16383)

```python
def _create_value_type_selection(self):
    """Create value type selection (updated for radiometric)."""
    if self.is_radiometric:
        self.percent_radio = QPushButton("Percentage")
        self.temp_radio = QPushButton("Temperature (°C)")  # NEW
        self.advanced_radio = QPushButton("Advanced (Raw)")
    else:
        # Keep existing UI for non-radiometric
        self.percent_radio = QPushButton("Percentage")
        self.advanced_radio = QPushButton("Advanced (Raw)")
```

---

## Implementation Phases

### Phase 1: Boson SDK Radiometric Commands (Week 1)

**Goal**: Extend Boson serial communication with radiometric CCI commands

**Files Modified**:
- `boson_serial.py`

**Tasks**:

1. **Add CCI Function IDs** (30 min)
```python
# Module 0x0E - TLinear (Radiometric)
MODULE_TLINEAR = 0x0E
FUNC_TLINEAR_ENABLE = 0x00
FUNC_TLINEAR_GET_ENABLE = 0x01
FUNC_TLINEAR_SET_MODE = 0x02
FUNC_TLINEAR_GET_MODE = 0x03
FUNC_TLINEAR_GET_PARAMS = 0x08  # Get gain, offset
```

2. **Implement Radiometric Detection** (2 hours)
```python
def get_radiometric_enabled(self) -> bool:
    """Check if radiometric mode is enabled."""
    packet = self._build_packet(MODULE_TLINEAR, FUNC_TLINEAR_GET_ENABLE, get=True)
    response = self._send_and_receive(packet)
    if response and len(response) >= 2:
        return response[1] == 0x01
    return False
```

3. **Read TLinear Parameters** (3 hours)
```python
def get_tlinear_params(self) -> Optional[Dict]:
    """Get radiometric calibration parameters."""
    packet = self._build_packet(MODULE_TLINEAR, FUNC_TLINEAR_GET_PARAMS, get=True)
    response = self._send_and_receive(packet)

    if response and len(response) >= 12:
        # Parse gain and offset from response
        gain = struct.unpack('>f', bytes(response[2:6]))[0]
        offset = struct.unpack('>f', bytes(response[6:10]))[0]

        return {
            'gain': gain,
            'offset': offset
        }
    return None
```

4. **Read FPA Temperature** (2 hours)
```python
MODULE_SENSOR = 0x08
FUNC_SENSOR_GET_FPA_TEMP = 0x00

def get_fpa_temperature_k(self) -> Optional[float]:
    """Get FPA temperature in Kelvin."""
    packet = self._build_packet(MODULE_SENSOR, FUNC_SENSOR_GET_FPA_TEMP, get=True)
    response = self._send_and_receive(packet)

    if response and len(response) >= 4:
        # Parse temperature (usually returned as uint16 in centi-Kelvin)
        temp_centi_k = struct.unpack('>H', bytes(response[2:4]))[0]
        return temp_centi_k / 100.0
    return None
```

5. **Update BosonCameraInfo** (1 hour)
```python
@dataclass
class BosonCameraInfo:
    serial_number: Optional[str] = None
    part_number: Optional[str] = None
    firmware_version: Optional[str] = None
    model: Optional[str] = None
    radiometric: bool = False
    resolution: Tuple[int, int] = (320, 256)
    # NEW radiometric fields
    tlinear_gain: Optional[float] = None
    tlinear_offset: Optional[float] = None
    fpa_temperature_k: Optional[float] = None
```

**Deliverable**: Boson SDK can detect radiometric mode and retrieve calibration params

**Testing**:
- Connect to radiometric Boson 640
- Verify `get_radiometric_enabled()` returns True
- Verify `get_tlinear_params()` returns valid gain/offset
- Verify `get_fpa_temperature_k()` returns FPA temp (~303K)

---

### Phase 2: FLIR Camera Raw Frame Preservation (Week 1)

**Goal**: Preserve 16-bit raw frames without normalization

**Files Modified**:
- `flir_camera.py`

**Tasks**:

1. **Add Radiometric Mode Flag** (30 min)
```python
class FLIRBosonCamera:
    def __init__(self, ...):
        self.is_radiometric = False
        self.radiometric_params = None
```

2. **Detect Radiometric Mode** (1 hour)
```python
def detect_radiometric_mode(self) -> bool:
    """Detect if camera is in radiometric mode."""
    if not self.sdk_connected or not self.sdk:
        return False

    # Check via SDK
    self.is_radiometric = self.sdk.get_radiometric_enabled()

    if self.is_radiometric:
        # Retrieve calibration params
        params = self.sdk.get_tlinear_params()
        fpa_temp = self.sdk.get_fpa_temperature_k()

        if params:
            self.radiometric_params = {
                'gain': params['gain'],
                'offset': params['offset'],
                'fpa_temp_k': fpa_temp or 303.15
            }
            logger.info(f"✓ Radiometric mode detected")
            logger.info(f"  Gain: {params['gain']:.2f} counts/K")
            logger.info(f"  Offset: {params['offset']:.1f} counts")
            logger.info(f"  FPA Temp: {fpa_temp-273.15:.1f}°C")

    return self.is_radiometric
```

3. **Preserve 16-bit Frames** (2 hours)
```python
def read_thermal_raw(self) -> Tuple[bool, Optional[np.ndarray]]:
    """
    Read raw thermal frame WITHOUT normalization.

    Returns:
        Tuple of (success, frame) where:
        - Non-radiometric: 8-bit grayscale (0-255)
        - Radiometric: 16-bit raw counts (0-16383)
    """
    if not self.is_opened or self.cap is None:
        return False, None

    ret, frame = self.cap.read()

    if not ret or frame is None:
        return False, None

    # Convert to grayscale if color
    if len(frame.shape) == 3:
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    # CRITICAL: Preserve 16-bit for radiometric
    if self.is_radiometric and frame.dtype == np.uint16:
        # Keep as 16-bit, do NOT normalize
        return ret, frame
    else:
        # Non-radiometric: ensure 8-bit
        if frame.dtype != np.uint8:
            frame = cv2.normalize(frame, None, 0, 255, cv2.NORM_MINMAX)
            frame = frame.astype(np.uint8)
        return ret, frame
```

4. **Auto-Detection on Open** (1 hour)
```python
def open(self) -> bool:
    """Open camera connection (enhanced with radiometric detection)."""
    # ... existing video capture code ...

    if self.is_opened:
        # Detect radiometric mode if SDK connected
        if self.sdk_connected:
            self.detect_radiometric_mode()

        return True
```

**Deliverable**: Camera returns 16-bit raw frames for radiometric cameras

**Testing**:
- Open radiometric Boson 640
- Verify `is_radiometric == True`
- Verify `read_thermal_raw()` returns np.uint16 frames
- Verify frame values in range 0-16383

---

### Phase 3: Thermal Analyzer Temperature Conversion (Week 2)

**Goal**: Convert raw 14-bit counts to absolute temperature

**Files Modified**:
- `thermal_analyzer.py` (new file: `radiometric_converter.py`)

**Tasks**:

1. **Create RadiometricConverter Class** (3 hours)

Create new file: `radiometric_converter.py`

```python
"""
Radiometric Temperature Conversion
Converts raw 14-bit counts to absolute temperature (Celsius/Fahrenheit/Kelvin)
"""
import numpy as np
from dataclasses import dataclass
from typing import Tuple, Optional

@dataclass
class RadiometricParams:
    """Radiometric calibration parameters."""
    enabled: bool = False
    gain: float = 160.0
    offset: float = 8000.0
    fpa_temp_k: float = 303.15
    fpa_temp_ref_k: float = 303.15
    fpa_coeff: float = 1.0
    valid_range_k: Tuple[float, float] = (233.15, 823.15)

    def convert_to_kelvin(self, raw_counts: np.ndarray) -> np.ndarray:
        """Convert raw counts to Kelvin."""
        offset_comp = self.offset + (self.fpa_temp_k - self.fpa_temp_ref_k) * self.fpa_coeff
        temp_k = (raw_counts.astype(np.float32) - offset_comp) / self.gain
        return np.clip(temp_k, self.valid_range_k[0], self.valid_range_k[1])

class RadiometricConverter:
    """Temperature conversion for radiometric cameras."""

    def __init__(self, params: RadiometricParams):
        self.params = params

    def raw_to_kelvin(self, raw_frame: np.ndarray) -> np.ndarray:
        """Convert 16-bit raw frame to Kelvin."""
        return self.params.convert_to_kelvin(raw_frame)

    def raw_to_celsius(self, raw_frame: np.ndarray) -> np.ndarray:
        """Convert 16-bit raw frame to Celsius."""
        temp_k = self.raw_to_kelvin(raw_frame)
        return temp_k - 273.15

    def raw_to_fahrenheit(self, raw_frame: np.ndarray) -> np.ndarray:
        """Convert 16-bit raw frame to Fahrenheit."""
        temp_k = self.raw_to_kelvin(raw_frame)
        return (temp_k - 273.15) * 9/5 + 32

    def update_fpa_temp(self, fpa_temp_k: float):
        """Update FPA temperature for compensation."""
        self.params.fpa_temp_k = fpa_temp_k
```

2. **Integrate into ThermalAnalyzer** (3 hours)
```python
class ThermalAnalyzer:
    def __init__(self, config: Optional[Dict] = None):
        # ... existing code ...

        # Radiometric support
        self.is_radiometric = self.config.get("radiometric", False)
        self.radiometric_converter: Optional[RadiometricConverter] = None

        if self.is_radiometric:
            params = RadiometricParams(
                enabled=True,
                gain=self.config.get("radiometric_gain", 160.0),
                offset=self.config.get("radiometric_offset", 8000.0),
                fpa_temp_k=self.config.get("fpa_temp_k", 303.15)
            )
            self.radiometric_converter = RadiometricConverter(params)

    def convert_frame_to_temperature(self, raw_frame: np.ndarray) -> np.ndarray:
        """Convert raw frame to temperature in current unit."""
        if not self.is_radiometric or not self.radiometric_converter:
            # Non-radiometric: return as-is (raw values)
            return raw_frame.astype(np.float32)

        # Radiometric: convert based on temp_unit
        if self.temp_unit == TemperatureUnit.CELSIUS:
            return self.radiometric_converter.raw_to_celsius(raw_frame)
        elif self.temp_unit == TemperatureUnit.FAHRENHEIT:
            return self.radiometric_converter.raw_to_fahrenheit(raw_frame)
        elif self.temp_unit == TemperatureUnit.KELVIN:
            return self.radiometric_converter.raw_to_kelvin(raw_frame)
        else:
            return raw_frame.astype(np.float32)

    def analyze_frame(self, thermal_frame: np.ndarray,
                     roi_mask: Optional[np.ndarray] = None) -> ThermalStatistics:
        """Analyze thermal frame (enhanced for radiometric)."""

        # Convert to temperature if radiometric
        if self.is_radiometric:
            temp_frame = self.convert_frame_to_temperature(thermal_frame)
        else:
            temp_frame = thermal_frame.astype(np.float32)

        # ... existing statistics computation on temp_frame ...

        # Set proper unit string
        if self.is_radiometric:
            unit = f"°{self.temp_unit.value}"
        else:
            unit = " (raw)"

        return ThermalStatistics(..., unit=unit)
```

3. **Add Temperature Unit Switching** (1 hour)
```python
def set_temperature_unit(self, unit: TemperatureUnit):
    """Change temperature display unit (Celsius/Fahrenheit/Kelvin)."""
    if not self.is_radiometric:
        logger.warning("Temperature unit only applicable in radiometric mode")
        return

    self.temp_unit = unit
    logger.info(f"Temperature unit set to {unit.value}")
```

**Deliverable**: Thermal analyzer converts raw frames to absolute temperature

**Testing**:
- Feed 16-bit raw frame to analyzer
- Verify `convert_frame_to_temperature()` returns sensible temps (20-40°C room temp)
- Verify unit switching (Celsius ↔ Fahrenheit ↔ Kelvin)
- Verify hot spot detection uses absolute temps

---

### Phase 4: Main Application Integration (Week 2)

**Goal**: Wire radiometric pipeline through main application

**Files Modified**:
- `inspection_main.py`

**Tasks**:

1. **Initialize Radiometric Pipeline** (2 hours)
```python
class ThermalInspectionFusion:
    def __init__(self, ...):
        # ... existing init ...

        self.is_radiometric = False
        self.radiometric_params = None

    def _initialize_thermal_camera(self):
        """Initialize thermal camera (enhanced for radiometric)."""
        # ... existing camera init ...

        if self.thermal_camera.is_opened:
            # Detect radiometric mode
            if hasattr(self.thermal_camera, 'is_radiometric'):
                self.is_radiometric = self.thermal_camera.is_radiometric
                self.radiometric_params = self.thermal_camera.radiometric_params

                if self.is_radiometric:
                    # Configure thermal analyzer for radiometric
                    self.thermal_analyzer.is_radiometric = True
                    self.thermal_analyzer.radiometric_converter = RadiometricConverter(
                        RadiometricParams(
                            enabled=True,
                            gain=self.radiometric_params['gain'],
                            offset=self.radiometric_params['offset'],
                            fpa_temp_k=self.radiometric_params['fpa_temp_k']
                        )
                    )

                    logger.info("✓ Radiometric pipeline initialized")

                    # Update GUI
                    if self.gui:
                        self.gui.analysis_panel.update_radiometric_status(True, ...)
```

2. **Process Raw Frames** (2 hours)
```python
def _process_thermal_frame(self):
    """Process thermal frame (enhanced for radiometric)."""

    # Read raw frame (16-bit for radiometric, 8-bit otherwise)
    ret, raw_frame = self.thermal_camera.read_thermal_raw()

    if not ret or raw_frame is None:
        return

    # For display: convert to 8-bit visualization
    if self.is_radiometric and raw_frame.dtype == np.uint16:
        # Convert to temperature first
        temp_frame = self.thermal_analyzer.convert_frame_to_temperature(raw_frame)

        # Normalize temperature for display (auto-contrast)
        display_frame = cv2.normalize(temp_frame, None, 0, 255, cv2.NORM_MINMAX)
        display_frame = display_frame.astype(np.uint8)
    else:
        display_frame = raw_frame

    # Apply palette to display frame
    colored_frame = self.palette_manager.apply_palette(display_frame, ...)

    # Analyze using raw frame (preserves precision)
    stats = self.thermal_analyzer.analyze_frame(raw_frame)

    # ... rest of processing ...
```

3. **Add Temperature Unit Control** (1 hour)
```python
def set_temperature_unit(self, unit_str: str):
    """Set temperature display unit."""
    unit_map = {
        'celsius': TemperatureUnit.CELSIUS,
        'fahrenheit': TemperatureUnit.FAHRENHEIT,
        'kelvin': TemperatureUnit.KELVIN
    }

    if unit_str in unit_map:
        self.thermal_analyzer.set_temperature_unit(unit_map[unit_str])
        logger.info(f"Temperature unit: {unit_str}")
```

4. **FPA Temperature Updates** (1 hour)
```python
def update_fpa_temperature(self):
    """Periodically update FPA temperature for compensation."""
    if not self.is_radiometric or not self.thermal_camera.sdk_connected:
        return

    fpa_temp = self.thermal_camera.sdk.get_fpa_temperature_k()

    if fpa_temp and self.thermal_analyzer.radiometric_converter:
        self.thermal_analyzer.radiometric_converter.update_fpa_temp(fpa_temp)
```

**Deliverable**: Full radiometric pipeline operational

**Testing**:
- Launch with radiometric Boson 640
- Verify absolute temperatures displayed (°C/°F/K)
- Verify hot spots show actual temperatures
- Verify unit switching works
- Compare with FLIR ResearchIR for accuracy

---

### Phase 5: GUI Enhancements (Week 3)

**Goal**: Add radiometric-specific UI controls

**Files Modified**:
- `inspection_gui_qt.py`

**Tasks**:

1. **Temperature Unit Selector** (2 hours)
   - Add Celsius/Fahrenheit/Kelvin toggle buttons
   - Connect to `temp_unit_changed` signal
   - Update all temperature displays when unit changes

2. **Radiometric Status Indicator** (1 hour)
   - Show "Radiometric (Absolute)" vs "Non-Radiometric (Relative)"
   - Display temperature range
   - Color-coded (green for radiometric)

3. **Enhanced Threshold Widget** (2 hours)
   - Add "Temperature" option (°C/°F/K) when radiometric
   - Auto-adjust spin box range based on mode
   - Show unit suffix dynamically

4. **FPA Temperature Display** (1 hour)
   - Add to Boson Control Panel
   - Show current FPA temp
   - Update every 5 seconds

**Deliverable**: Polished UI for radiometric features

**Testing**:
- Test all UI controls
- Verify unit switching updates all displays
- Test threshold widget in all modes

---

### Phase 6: Calibration File Support (Week 3)

**Goal**: Load factory calibration files for improved accuracy

**Files Modified**:
- `camera_calibration.py` (new methods)
- `inspection_main.py`

**Tasks**:

1. **Calibration File Format** (2 hours)

Create JSON format:
```json
{
  "camera_serial": "12345678",
  "model": "Boson 640",
  "radiometric": true,
  "calibration_date": "2025-11-24",
  "tlinear": {
    "gain": 159.8,
    "offset": 8012.3,
    "fpa_temp_ref_k": 303.15,
    "fpa_coeff": 0.95
  },
  "temperature_range": {
    "min_k": 233.15,
    "max_k": 823.15
  },
  "accuracy": {
    "absolute_c": 5.0,
    "percent": 5.0
  }
}
```

2. **Calibration Loader** (2 hours)
```python
def load_radiometric_calibration(filepath: str) -> Optional[RadiometricParams]:
    """Load calibration from JSON file."""
    try:
        with open(filepath, 'r') as f:
            data = json.load(f)

        return RadiometricParams(
            enabled=data['radiometric'],
            gain=data['tlinear']['gain'],
            offset=data['tlinear']['offset'],
            fpa_temp_ref_k=data['tlinear']['fpa_temp_ref_k'],
            fpa_coeff=data['tlinear']['fpa_coeff'],
            valid_range_k=(data['temperature_range']['min_k'],
                          data['temperature_range']['max_k'])
        )
    except Exception as e:
        logger.error(f"Failed to load calibration: {e}")
        return None
```

3. **CLI Argument** (1 hour)
```python
parser.add_argument('--radiometric-cal',
                   help='Path to radiometric calibration file (JSON)')
```

4. **Override SDK Params** (1 hour)
```python
# If calibration file provided, override SDK params
if args.radiometric_cal:
    cal_params = load_radiometric_calibration(args.radiometric_cal)
    if cal_params:
        self.radiometric_params = cal_params
        logger.info("✓ Using calibration file instead of SDK params")
```

**Deliverable**: Support for factory calibration files

**Testing**:
- Create test calibration file
- Launch with `--radiometric-cal boson_cal.json`
- Verify params loaded correctly
- Compare accuracy with/without calibration file

---

### Phase 7: Radiometric Detection & Feature Lockout (Week 3-4)

**Goal**: Detect camera type and disable radiometric-only features for non-radiometric cameras

**Files Modified**:
- `boson_serial.py`
- `flir_camera.py`
- `inspection_gui_qt.py`
- `inspection_main.py`

**Tasks**:

1. **Enhanced Radiometric Detection** (3 hours)

**Location**: `boson_serial.py`

```python
def detect_camera_capabilities(self) -> Dict[str, Any]:
    """
    Comprehensive camera capability detection.

    Returns:
        Dictionary with camera capabilities:
        - is_radiometric: bool
        - has_tlinear: bool
        - has_agc: bool
        - model: str ('Boson 320', 'Boson 640', etc.)
        - resolution: tuple
    """
    capabilities = {
        'is_radiometric': False,
        'has_tlinear': False,
        'has_agc': True,
        'model': 'Unknown',
        'resolution': (320, 256)
    }

    # Method 1: Check TLinear enable status
    try:
        tlinear_enabled = self.get_radiometric_enabled()
        capabilities['is_radiometric'] = tlinear_enabled
        capabilities['has_tlinear'] = True
    except Exception as e:
        logger.debug(f"TLinear check failed: {e}")

    # Method 2: Try to read TLinear params
    if not capabilities['has_tlinear']:
        try:
            params = self.get_tlinear_params()
            if params and params.get('gain', 0) > 0:
                capabilities['has_tlinear'] = True
                capabilities['is_radiometric'] = True
        except Exception as e:
            logger.debug(f"TLinear params check failed: {e}")

    # Method 3: Check part number for radiometric suffix
    try:
        part_number = self.get_camera_part_number()
        if part_number:
            # Radiometric models typically have '-R' suffix
            if '-R' in part_number or 'RADIOMETRIC' in part_number.upper():
                capabilities['is_radiometric'] = True
                capabilities['has_tlinear'] = True

            # Parse resolution from part number
            if '640' in part_number:
                capabilities['resolution'] = (640, 512)
                capabilities['model'] = 'Boson 640'
            elif '320' in part_number:
                capabilities['resolution'] = (320, 256)
                capabilities['model'] = 'Boson 320'
    except Exception as e:
        logger.debug(f"Part number check failed: {e}")

    logger.info(f"Camera capabilities detected:")
    logger.info(f"  Model: {capabilities['model']}")
    logger.info(f"  Radiometric: {capabilities['is_radiometric']}")
    logger.info(f"  Resolution: {capabilities['resolution']}")

    return capabilities
```

2. **Camera Detection on Open** (2 hours)

**Location**: `flir_camera.py`

```python
class FLIRBosonCamera:
    def __init__(self, ...):
        # ... existing init ...
        self.is_radiometric = False
        self.camera_capabilities = None

    def open(self) -> bool:
        """Open camera connection (enhanced with capability detection)."""
        # ... existing video capture code ...

        if self.is_opened and self.sdk_connected:
            # Detect camera capabilities
            self.camera_capabilities = self.sdk.detect_camera_capabilities()
            self.is_radiometric = self.camera_capabilities['is_radiometric']

            if self.is_radiometric:
                logger.info("✓ Radiometric Boson detected - absolute temperature enabled")
                self.detect_radiometric_mode()
            else:
                logger.info("ℹ Non-radiometric Boson detected - relative mode only")

        return True

    def get_camera_capabilities(self) -> Dict[str, Any]:
        """Get detected camera capabilities."""
        if self.camera_capabilities:
            return self.camera_capabilities
        else:
            # Return default non-radiometric capabilities
            return {
                'is_radiometric': False,
                'has_tlinear': False,
                'has_agc': True,
                'model': 'Unknown',
                'resolution': self.resolution
            }
```

3. **Feature Lockout Implementation** (4 hours)

**Location**: `inspection_gui_qt.py`

```python
class ManualThresholdWidget(QWidget):
    """Enhanced with radiometric detection."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.is_radiometric = False  # Will be updated by main app
        # ... existing init ...

    def set_radiometric_mode(self, is_radiometric: bool):
        """
        Configure widget based on camera capabilities.

        Args:
            is_radiometric: True if camera supports absolute temperature
        """
        self.is_radiometric = is_radiometric

        if not is_radiometric:
            # LOCKOUT: Disable temperature mode, only allow percentage/raw
            if hasattr(self, 'temp_radio'):
                self.temp_radio.setEnabled(False)
                self.temp_radio.setToolTip(
                    "Temperature thresholds require radiometric Boson camera.\n"
                    "Current camera: Non-radiometric (relative mode only)"
                )

                # Force switch to percentage if temperature was selected
                if self.temp_radio.isChecked():
                    self.percent_radio.setChecked(True)
                    self.use_raw_values_changed.emit(False)

            # Update value type group label
            if hasattr(self, 'value_type_group'):
                self.value_type_group.setTitle("VALUE TYPE (Relative Mode)")
        else:
            # Enable all features for radiometric cameras
            if hasattr(self, 'temp_radio'):
                self.temp_radio.setEnabled(True)
                self.temp_radio.setToolTip("Use absolute temperature values (°C/°F/K)")

            if hasattr(self, 'value_type_group'):
                self.value_type_group.setTitle("VALUE TYPE (Absolute Mode)")

    def _create_value_type_selection(self):
        """Create value type selection with radiometric support."""
        value_type_group = QGroupBox("VALUE TYPE")
        value_type_layout = QVBoxLayout(value_type_group)

        self.percent_radio = QPushButton("Percentage")
        self.percent_radio.setCheckable(True)
        self.percent_radio.setChecked(True)
        self.percent_radio.setToolTip("Use percentage values (0-100%)")

        # Temperature mode (will be locked out if non-radiometric)
        self.temp_radio = QPushButton("Temperature (°C)")
        self.temp_radio.setCheckable(True)
        self.temp_radio.setToolTip("Use absolute temperature values (°C/°F/K)")

        self.advanced_radio = QPushButton("Advanced (Raw)")
        self.advanced_radio.setCheckable(True)
        self.advanced_radio.setToolTip("Use raw 14-bit thermal values (0-16383)")

        value_type_layout.addWidget(self.percent_radio)
        value_type_layout.addWidget(self.temp_radio)
        value_type_layout.addWidget(self.advanced_radio)

        self.value_type_group = value_type_group
        return value_type_group


class AnalysisPanel(QWidget):
    """Enhanced with radiometric indicator."""

    def update_radiometric_status(self, is_radiometric: bool, model: str = "Unknown"):
        """
        Update radiometric status indicator.

        Args:
            is_radiometric: Camera radiometric capability
            model: Camera model name
        """
        if is_radiometric:
            self.radiometric_label.setText(
                f"✓ {model} - Radiometric (Absolute Temperature)\n"
                f"Range: -40°C to +550°C (±5°C accuracy)"
            )
            self.radiometric_label.setStyleSheet(
                "color: #0a0; font-weight: bold; font-size: 10px; "
                "background-color: #1a1a1a; padding: 5px; border-radius: 3px;"
            )
        else:
            self.radiometric_label.setText(
                f"ℹ {model} - Non-Radiometric (Relative Mode)\n"
                f"Temperature values are relative (not calibrated)"
            )
            self.radiometric_label.setStyleSheet(
                "color: #fa0; font-weight: bold; font-size: 10px; "
                "background-color: #1a1a1a; padding: 5px; border-radius: 3px;"
            )
```

4. **Main Application Detection Flow** (2 hours)

**Location**: `inspection_main.py`

```python
class ThermalInspectionFusion:
    def _initialize_thermal_camera(self):
        """Initialize thermal camera with capability detection."""
        # ... existing camera init ...

        if self.thermal_camera.is_opened:
            # Get camera capabilities
            capabilities = self.thermal_camera.get_camera_capabilities()
            self.is_radiometric = capabilities['is_radiometric']

            logger.info("=" * 60)
            logger.info("CAMERA CAPABILITIES")
            logger.info("=" * 60)
            logger.info(f"Model: {capabilities['model']}")
            logger.info(f"Resolution: {capabilities['resolution']}")
            logger.info(f"Radiometric: {'YES ✓' if self.is_radiometric else 'NO ✗'}")
            logger.info(f"Absolute Temperature: {'ENABLED' if self.is_radiometric else 'DISABLED'}")
            logger.info("=" * 60)

            # Configure thermal analyzer
            if self.is_radiometric:
                self._configure_radiometric_mode(capabilities)
            else:
                self._configure_nonradiometric_mode()

            # Update GUI
            if self.gui:
                self.gui.analysis_panel.update_radiometric_status(
                    self.is_radiometric,
                    capabilities['model']
                )

                # Configure threshold widget based on capabilities
                if hasattr(self.gui, 'threshold_widget'):
                    self.gui.threshold_widget.set_radiometric_mode(self.is_radiometric)

    def _configure_radiometric_mode(self, capabilities: Dict):
        """Configure for radiometric camera."""
        # ... radiometric setup from Phase 4 ...
        pass

    def _configure_nonradiometric_mode(self):
        """Configure for non-radiometric camera."""
        self.thermal_analyzer.is_radiometric = False
        self.thermal_analyzer.temp_unit = TemperatureUnit.CELSIUS  # Placeholder
        logger.info("Non-radiometric mode: Using relative temperature values")
```

**Deliverable**: Automatic detection with feature lockout

**Testing**:
- Test with radiometric Boson 640: All features enabled
- Test with non-radiometric Boson 320: Temperature thresholds disabled
- Test without SDK: Graceful fallback to non-radiometric
- Verify UI shows correct status indicator

---

### Phase 8: Documentation & Testing (Week 4)

**Goal**: Comprehensive documentation and validation

**Deliverables**:

1. **User Documentation** (1 day)
   - Update README.md with radiometric features
   - Create RADIOMETRIC_USER_GUIDE.md
   - Add calibration file creation guide
   - Update command-line help
   - Document feature lockout behavior

2. **Developer Documentation** (1 day)
   - Document radiometric API
   - Add code examples
   - Update architecture diagrams
   - Document detection logic

3. **Test Suite** (2 days)
   - Unit tests for RadiometricConverter
   - Integration tests for full pipeline
   - Validation against known temperatures
   - Cross-check with FLIR ResearchIR
   - Test feature lockout scenarios

4. **Performance Testing** (1 day)
   - Measure conversion overhead
   - Verify real-time performance (60 FPS)
   - Memory profiling

---

## Testing Strategy

### Unit Tests

```python
def test_radiometric_conversion():
    """Test raw counts to temperature conversion."""
    params = RadiometricParams(
        enabled=True,
        gain=160.0,
        offset=8000.0,
        fpa_temp_k=303.15,
        fpa_temp_ref_k=303.15
    )

    converter = RadiometricConverter(params)

    # Test room temperature (25°C = 298.15K)
    raw_counts = np.array([8000 + 160 * 298.15], dtype=np.uint16)
    temp_k = converter.raw_to_kelvin(raw_counts)

    assert np.isclose(temp_k[0], 298.15, atol=0.1), f"Expected 298.15K, got {temp_k[0]}K"
```

### Integration Tests

1. **Radiometric Detection Test**
   - Connect radiometric Boson 640
   - Verify auto-detection
   - Verify SDK params retrieval

2. **Temperature Accuracy Test**
   - Use reference blackbody source (if available)
   - Measure known temperature
   - Compare with displayed value
   - Tolerance: ±5°C or 5%

3. **Unit Switching Test**
   - Capture frame in Celsius
   - Switch to Fahrenheit
   - Verify: F = C × 9/5 + 32

4. **Performance Test**
   - Run for 2 minutes
   - Verify FPS ≥ 30
   - Check memory usage stable

---

## Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| SDK commands differ from expected | Medium | High | Test with actual hardware early, consult FLIR docs |
| FPA compensation inaccurate | Medium | Medium | Validate with blackbody, implement auto-FFC |
| Performance degradation | Low | Medium | Optimize conversion (vectorized NumPy) |
| Non-radiometric cameras break | Low | High | Thorough backward compatibility testing |
| Calibration file format changes | Low | Low | Version field in JSON |

---

## Success Criteria

### Minimum Viable Product (MVP)

✅ Radiometric mode auto-detected
✅ Raw counts converted to Celsius
✅ Absolute temperatures displayed in GUI
✅ Hot/cold spots show °C values
✅ Non-radiometric cameras still work

### Full Release

✅ All MVP criteria
✅ Celsius/Fahrenheit/Kelvin switching
✅ FPA temperature compensation
✅ Calibration file support
✅ ±5°C accuracy validation
✅ Full documentation
✅ 60 FPS sustained performance

---

## Implementation Timeline

| Phase | Duration | Start | End | Status |
|-------|----------|-------|-----|--------|
| 1. Boson SDK Commands | 1 week | Week 1 | Week 1 | ⏳ Not Started |
| 2. Raw Frame Preservation | 1 week | Week 1 | Week 1 | ⏳ Not Started |
| 3. Temperature Conversion | 1 week | Week 2 | Week 2 | ⏳ Not Started |
| 4. Main App Integration | 1 week | Week 2 | Week 2 | ⏳ Not Started |
| 5. GUI Enhancements | 1 week | Week 3 | Week 3 | ⏳ Not Started |
| 6. Calibration Files | 1 week | Week 3 | Week 3 | ⏳ Not Started |
| 7. Detection & Lockout | 3 days | Week 3-4 | Week 4 | ⏳ Not Started |
| 8. Documentation & Testing | 4 days | Week 4 | Week 4 | ⏳ Not Started |

**Total Duration**: 4 weeks (1 month)

---

## Conclusion

This plan provides a comprehensive roadmap to integrate full radiometric temperature measurement support for FLIR Boson 640 radiometric cameras. The phased approach ensures:

1. **Backward Compatibility**: Non-radiometric cameras continue working
2. **Incremental Validation**: Each phase has clear deliverables and tests
3. **Professional Quality**: Proper FPA compensation and calibration
4. **User Experience**: Intuitive UI with Celsius/Fahrenheit/Kelvin support

### Current Status: 40% Complete
- ✅ Infrastructure ready (raw value processing, SDK framework)
- ⚠️ Partial implementation (radiometric flag exists)
- ❌ No temperature conversion implemented

### Next Step: Phase 1
Begin with Boson SDK radiometric commands (Week 1) to establish foundation for temperature conversion.

---

## References

- FLIR Boson Integration Guide
- FLIR IDD (Interface Design Description) v3.0
- Boson CCI Protocol Specification
- TLinear Calibration Technical Note
- FLIR ResearchIR Software (validation reference)

---

**Document Version**: 1.0
**Last Updated**: 2025-11-24
**Author**: Claude Code
**Status**: Ready for Review
