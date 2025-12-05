# Hybrid Radiometric Architecture Design

## Overview

Dual-mode radiometric system supporting both 8-bit pseudo-radiometric (estimation) and true 16-bit radiometric via direct USB backend.

## Architecture Goals

1. **Automatic Mode Detection**: System auto-selects best available method
2. **Graceful Fallback**: Falls back from 16-bit → 8-bit if USB backend unavailable
3. **Unified API**: Same interface for both modes from application perspective
4. **Live Switching**: Allow runtime switching between modes
5. **Clear User Feedback**: Status banner shows active mode and accuracy

## Mode Hierarchy (Priority Order)

```
┌─────────────────────────────────────────────────────┐
│          Radiometric Mode Selection                  │
└─────────────────────────────────────────────────────┘
                        │
                        ▼
         ┌──────────────────────────┐
         │  Is 16-bit USB Backend   │
         │  Available & Connected?  │
         └──────────────────────────┘
                 │              │
                YES            NO
                 │              │
                 ▼              ▼
    ┌────────────────────┐  ┌──────────────────┐
    │  16-BIT MODE       │  │  Is SDK          │
    │  True Radiometric  │  │  Connected?      │
    │  ±2°C accuracy     │  └──────────────────┘
    └────────────────────┘       │          │
                                YES        NO
                                 │          │
                                 ▼          ▼
                    ┌────────────────────┐  ┌────────────┐
                    │  8-BIT MODE        │  │  NO TEMP   │
                    │  Pseudo-Radiometric│  │  MODE      │
                    │  ±5-10°C accuracy  │  │  AGC only  │
                    └────────────────────┘  └────────────┘
```

## File Structure

```
thermal-inspection/
├── radiometric_core.py          # NEW: Unified radiometric interface
├── radiometric_usb_backend.py   # NEW: 16-bit USB direct access
├── thermal_estimator.py         # EXISTING: 8-bit estimation
├── flir_camera.py               # EXISTING: Camera interface
├── radiometric_panel.py         # UPDATED: Add 16-bit controls
└── inspection_main.py           # UPDATED: Mode management
```

## Core Components

### 1. RadiometricCore (radiometric_core.py)

**Purpose**: Unified interface that abstracts 8-bit vs 16-bit differences

```python
class RadiometricCore:
    """
    Unified radiometric interface supporting both 8-bit and 16-bit modes.

    Automatically selects best available mode and provides consistent API.
    """

    def __init__(self):
        self.active_mode = "none"  # "none", "8bit", "16bit"
        self.mode_16bit = None     # USB backend instance
        self.mode_8bit = None      # ThermalTemperatureEstimator instance

    def initialize(self, camera):
        """Auto-detect and initialize best available mode."""
        pass

    def get_temperature_map(self, frame) -> np.ndarray:
        """Get temperature map regardless of mode."""
        pass

    def get_pixel_temperature(self, x, y) -> float:
        """Get single pixel temperature."""
        pass

    def calibrate_single_point(self, ...):
        """Calibrate using single reference point."""
        pass

    def get_mode_info(self) -> dict:
        """Get current mode information."""
        pass
```

### 2. RadiometricUSBBackend (radiometric_usb_backend.py)

**Purpose**: Direct USB access for true 16-bit radiometric data

```python
class RadiometricUSBBackend:
    """
    Direct USB backend for 16-bit radiometric Boson cameras.

    Bypasses OpenCV to access raw 16-bit radiometric data via USB.
    Requires specialized USB library (e.g., libusb, pyflir).
    """

    def __init__(self):
        self.device = None
        self.is_radiometric = False

    def open(self, vid=0x09cb, pid=0x4007):
        """Open USB device directly."""
        pass

    def read_radiometric_frame(self) -> np.ndarray:
        """Read 16-bit radiometric frame (Kelvin x 10)."""
        pass

    def apply_calibration(self, raw_frame, fpa_temp) -> np.ndarray:
        """Apply factory calibration to get absolute temps."""
        pass
```

## Mode Characteristics

### 16-Bit Mode (True Radiometric)
- **Data Source**: Direct USB backend (bypasses OpenCV)
- **Accuracy**: ±2°C
- **Requirements**:
  - Radiometric-capable Boson (640-R, 320-R models)
  - USB backend library available
  - Factory calibration data accessible
- **Calibration**: Uses factory NIST-traceable calibration
- **FPA Compensation**: Automatic via SDK or USB metadata

### 8-Bit Mode (Pseudo-Radiometric)
- **Data Source**: OpenCV AGC frames
- **Accuracy**: ±5-10°C
- **Requirements**:
  - Any Boson camera (320, 640, -R variants)
  - SDK connection for FPA temperature
- **Calibration**: User calibration (1-point or 2-point)
- **FPA Compensation**: Uses FPA temp as reference point

### None Mode (AGC Only)
- **Data Source**: OpenCV AGC frames
- **Accuracy**: N/A (relative only)
- **Requirements**: None
- **Display**: AGC grayscale only, no temperatures

## GUI Updates

### Status Banner (Always Visible)

```
┌─────────────────────────────────────────────────────────────┐
│ Active Mode: 16-Bit Radiometric | Accuracy: ±2°C | NIST Cal │
└─────────────────────────────────────────────────────────────┘
```

States:
- `16-Bit Radiometric | ±2°C | Factory Calibrated`
- `8-Bit Estimation | ±5-10°C | User Calibrated`
- `AGC Only | No Temperature Measurement`

### Radiometric Panel Updates

**New Section: "16-Bit Direct USB" (above 8-Bit section)**

```
╔═══════════════════════════════════════════════╗
║  16-Bit Direct USB (True Radiometric)         ║
╠═══════════════════════════════════════════════╣
║  [ ] Enable 16-Bit Direct USB                 ║
║  ├─ USB Device: /dev/boson0                   ║
║  ├─ Factory Cal: LOADED ✓                     ║
║  └─ Status: Active, 60 FPS                    ║
║                                                ║
║  [Refresh USB Devices] [Test Connection]      ║
╚═══════════════════════════════════════════════╝
```

**Updated Section: "8-Bit Estimation"**

```
╔═══════════════════════════════════════════════╗
║  8-Bit Estimation (Fallback Mode)             ║
╠═══════════════════════════════════════════════╣
║  [✓] Enable 8-Bit Estimation                  ║
║      (Auto-enabled when 16-bit unavailable)    ║
║  ...                                           ║
╚═══════════════════════════════════════════════╝
```

## Implementation Phases

### Phase 1: Core Infrastructure (This Session)
- [x] Create `radiometric_core.py` stub
- [x] Create `radiometric_usb_backend.py` stub
- [ ] Update `inspection_main.py` to use RadiometricCore
- [ ] Update GUI status banner
- [ ] Add mode info to radiometric panel

### Phase 2: USB Backend (Next Session)
- [ ] Research USB library options (libusb, pyflir, custom)
- [ ] Implement USB device detection
- [ ] Implement 16-bit frame reading
- [ ] Parse factory calibration data
- [ ] Test with real hardware

### Phase 3: Mode Switching (Next Session)
- [ ] Implement automatic mode detection
- [ ] Add runtime mode switching UI
- [ ] Handle graceful fallback
- [ ] Test all mode transitions

### Phase 4: Calibration Integration
- [ ] 16-bit factory calibration loading
- [ ] 8-bit user calibration (already done)
- [ ] Calibration persistence
- [ ] Export/import calibration

## API Contract

All temperature methods return:
```python
{
    'temperature_c': float,      # Temperature in Celsius
    'mode': str,                 # "16bit", "8bit", or "none"
    'accuracy': str,             # "±2°C", "±5-10°C", or "N/A"
    'confidence': float,         # 0.0-1.0 confidence
    'source': str                # "usb_16bit", "sdk_8bit", or "agc"
}
```

## Testing Strategy

### Unit Tests
- Mode detection logic
- Fallback behavior
- Temperature conversion accuracy
- Calibration persistence

### Integration Tests
- Mode switching without restart
- 16-bit → 8-bit fallback
- SDK + USB coexistence
- Frame rate with both modes

### Hardware Tests
- Test with Boson 640
- Test with Boson 640-R (radiometric)
- Test with Boson 320
- Test SDK + OpenCV conflicts

## Migration Path

**Existing Users (8-bit estimation)**
- No changes required
- System automatically uses 8-bit mode
- Can upgrade to 16-bit by connecting USB backend

**New Users (16-bit capable)**
- System auto-detects radiometric capability
- Automatically uses best available mode
- Clear indication of active mode in UI

## Performance Considerations

- **16-bit mode**: May be slower due to USB overhead
- **8-bit mode**: Fast, uses existing OpenCV pipeline
- **Hybrid**: Allow user to prioritize speed vs accuracy

## Future Enhancements

- [ ] Confidence intervals for temperature readings
- [ ] Temperature uncertainty visualization
- [ ] Multi-point calibration for 8-bit mode
- [ ] Automatic calibration via known references
- [ ] Temperature measurement history/logging
