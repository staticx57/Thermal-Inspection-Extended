# Enhancement #5: Full Boson SDK Implementation via Flirpy

## Objective
Extend the flirpy-based thermal backend to support full Boson SDK functionality, enabling:
- **AGC module**: Mode, gain, gamma, DDE, headroom controls
- **Radiometry module**: Full emissivity, atmospheric, flux controls
- **Isotherm module**: Hardware temperature-based highlighting
- **Spotmeter module**: Hardware spot temperature measurement
- **Telemetry module**: Frame-embedded data extraction
- **Color LUT module**: Full palette control
- **System info**: Serial number, firmware, sensor info

---

## Files in This Playground

| File | Purpose |
|------|---------|
| `flirpy_thermal_backend.py` | Main backend - where extensions integrate |
| `flirpy_sdk_bridge.py` | **KEY FILE** - extend with raw packet injection |
| `boson_sdk_wrapper.py` | Working implementations to port to flirpy |
| `boson_control_panel.py` | GUI panel for Boson controls |
| `reference/bosonsdkraw.txt` | SDK documentation with Function IDs |

---

## Architecture: Flirpy SDK Extension

```
┌─────────────────────────────────────────────────────┐
│  FlirpyThermalBackend                               │
│  ├── camera = flirpy.camera.boson.Boson()           │
│  │   ├── grab() → 16-bit Y16 frames                 │
│  │   ├── do_ffc() → FFC trigger                     │
│  │   └── send()/receive() → RAW SDK PACKETS ←──┐    │
│  └── sdk_bridge = FlirpySDKBridge(camera)       │    │
│      └── AGC, Radiometry, Spotmeter, Isotherm ──┘    │
└─────────────────────────────────────────────────────┘
```

---

## Implementation Strategy

### Phase 1: Packet Injection Foundation
1. Study flirpy's `_send_packet()` and `_decode_packet()` methods
2. Implement `_build_sdk_packet(module, function, data)` helper
3. Test with a simple command (e.g., `get_serial_number`)

### Phase 2: AGC Module
Function IDs from `bosonsdkraw.txt`:
- `agcSetGamma` = 0x0009000D
- `agcGetGamma` = 0x0009000E  
- `agcSetMaxGain` = 0x00090009
- `agcSetd2br` (DDE) = 0x00090019

### Phase 3: Radiometry Module
Function IDs:
- `radiometrySetEmissivityTarget` = 0x001C0031
- `radiometryGetEmissivityTarget` = 0x001C0032
- `radiometrySetTAtmosphere` = 0x001C0033
- `radiometrySetTransmissionWindow` = 0x001C0045

### Phase 4: Hardware Spotmeter Module
Function IDs:
- `spotmeterSetEnable` = 0x00360001
- `spotmeterSetPosition` = 0x00360005
- `spotmeterGetValue` = 0x00360009 (returns raw temp in centiKelvin)

### Phase 5: Hardware Isotherm Module
Function IDs:
- `isothermSetEnable` = 0x00180001
- `isothermSetUnits` = 0x00180003
- `isothermSetThresholdLow` = 0x0018000D
- `isothermSetThresholdHigh` = 0x0018000F

### Phase 6: Telemetry Module
Function IDs:
- `telemetrySetState` = 0x000A0001
- `telemetrySetLocation` = 0x000A0005

---

## Testing Script Template

```python
#!/usr/bin/env python3
"""Test Boson SDK commands via flirpy"""
from flirpy.camera.boson import Boson

def test_sdk_commands():
    camera = Boson()
    
    # Test FFC (should already work)
    print("Testing FFC...")
    camera.do_ffc()
    
    # Test FPA temp (should already work)
    print(f"FPA Temp: {camera.get_fpa_temperature()}")
    
    # Test raw packet (new implementation)
    # TODO: Implement packet injection
    
    camera.close()

if __name__ == "__main__":
    test_sdk_commands()
```

---

## Key Reference: Packet Format

From `bosonsdkraw.txt`, SDK commands use:
- **Module ID**: 1 byte (e.g., 0x09 = AGC, 0x18 = Isotherm)
- **Function ID**: 2 bytes (e.g., 0x000D = SetGamma)
- **Data**: Variable length based on function

Flirpy likely uses the same CCI protocol as `boson_serial.py`:
- Start: 0x8E
- Channel ID: 0x00
- Sequence: 1 byte
- Length: 2 bytes (little-endian)
- Payload: Module + Function + Data
- CRC16: 2 bytes
- End: 0xAE

---

## Success Criteria

1. ✅ Can send/receive raw SDK packets via flirpy
2. ✅ AGC gamma/DDE controls work
3. ✅ Hardware spotmeter returns temperature
4. ✅ Hardware isotherm highlights correctly
5. ✅ Environmental settings affect temperature readings

---

## Integration Strategy (Back to Main App)

When proven working, integrate back into the main application following these guidelines:

### 1. Extend, Don't Replace
```python
# ✅ GOOD: Add new methods alongside existing ones
class FlirpySDKBridge:
    def set_agc_gamma_hw(self, gamma: float):  # New hardware method
        """Set AGC gamma via hardware SDK."""
        ...
    
    # Existing methods remain untouched
```

### 2. Feature Flags for New Functionality
```python
# In flirpy_thermal_backend.py
self.use_hardware_spotmeter = False  # Default OFF until proven
self.use_hardware_isotherm = False   # Default OFF until proven
```

### 3. Backward Compatibility
- New SDK methods should return `None` gracefully if camera doesn't support them
- GUI panels should handle missing SDK features (grayed out controls)
- Never break existing 8-bit or basic 16-bit functionality

### 4. Integration Checkpoints
| Step | Action | Verify |
|------|--------|--------|
| 1 | Copy new methods to main `flirpy_sdk_bridge.py` | App still launches |
| 2 | Add feature flags to `flirpy_thermal_backend.py` | Backend switches work |
| 3 | Wire GUI controls to new methods | GUI responsive |
| 4 | Enable feature flags one-by-one | Each feature works |
| 5 | Update `boson_control_panel.py` | Controls functional |

### 5. Files to Modify (in main app)
| File | Changes |
|------|---------|
| `flirpy_sdk_bridge.py` | Add new SDK methods |
| `flirpy_thermal_backend.py` | Add feature flags, wire methods |
| `boson_control_panel.py` | Add UI controls for new features |
| `inspection_gui_qt.py` | Wire new panel signals (if needed) |

---

## Notes

- **DO NOT** modify original project files - work only in this playground
- Once proven, integrate back into main `flirpy_sdk_bridge.py`
- Test with camera connected - SDK commands require active connection
