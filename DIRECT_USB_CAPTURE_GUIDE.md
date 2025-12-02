# Direct USB Capture Implementation Guide

## Current Situation

Your FLIR Boson is currently using the **Windows UVC (USB Video Class) driver**, which is why:
- ✅ OpenCV/DirectShow works (8-bit capture)
- ✅ SDK via COM port works
- ❌ PyUSB cannot access the device (UVC driver has exclusive access)

## Three Approaches to Get 16-bit Data

### Approach A: Install WinUSB Driver (Breaks OpenCV)

**What it does**: Replaces UVC driver with WinUSB
**Pros**: Full control, direct USB access, 16-bit capture
**Cons**: OpenCV/DirectShow stops working

**Steps**:
1. Download Zadig: https://zadig.akeo.ie/
2. Run as Administrator
3. Options → List All Devices
4. Find "FLIR Boson" (may show as camera device)
5. Select WinUSB driver
6. Click "Replace Driver"

**Restoration**: Use Device Manager → Update Driver → Browse → Let Windows choose

---

### Approach B: USB Filter Driver (Best of Both Worlds)

**What it does**: Intercepts USB traffic while keeping UVC driver
**Pros**: Both PyUSB AND OpenCV work simultaneously
**Cons**: More complex setup

**Tools**:
- USBPcap (Wireshark component)
- libusb filter driver

**Not recommended for hobby project** - complex setup

---

### Approach C: Hybrid Solution (RECOMMENDED)

**What it does**: Use OpenCV for capture, but with custom processing

**Implementation**:
1. Keep current 8-bit OpenCV capture
2. Apply advanced AGC algorithms that mimic 16-bit quality
3. Use SDK FPA temperature for pseudo-radiometric calibration
4. Create lookup tables (LUTs) for temperature estimation

**Pros**:
- No driver changes
- Works right now
- Better than basic 8-bit
- Runtime mode switching intact

**Cons**:
- Not true 16-bit
- ±5-10°C accuracy (vs ±2°C for true radiometric)

---

## Recommendation for Your Project

Since this is a hobby project and you have **working runtime mode switching** already, I recommend:

### **Option 1**: Enhanced 8-bit Processing (No Driver Change)

Implement advanced processing on top of your current 8-bit capture:

```python
class EnhancedThermalProcessor:
    """
    Process 8-bit AGC data with radiometric-quality enhancements.
    """

    def __init__(self, camera):
        self.camera = camera
        self.fpa_temp_history = []
        self.calibration_lut = None

    def capture_calibrated_frame(self):
        """
        Capture and process frame with temperature calibration.
        """
        # Get raw AGC frame
        ret, agc_frame = self.camera.read()

        # Get FPA temperature
        fpa_temp = self.camera.sdk.get_fpa_temperature()

        # Apply calibration
        calibrated = self._apply_calibration(agc_frame, fpa_temp)

        return ret, calibrated

    def estimate_temperature_map(self, agc_frame):
        """
        Convert AGC frame to temperature estimates.
        Returns: numpy array with estimated temperatures in Celsius
        """
        # Implementation here
        pass
```

### **Option 2**: Install WinUSB for True 16-bit (Breaks OpenCV)

If you absolutely need true 16-bit and are willing to lose OpenCV:

**Procedure**:
1. Backup current driver: Device Manager → Export driver
2. Install WinUSB via Zadig
3. Implement direct USB capture (I'll provide full code)
4. Get true uint16 frames

**Time**: 2-3 hours implementation + testing
**Complexity**: Medium
**Result**: True 16-bit radiometric

---

## What Would You Prefer?

### Choice A: Enhanced 8-bit (Keep Everything Working)
- Implement advanced processing
- No driver changes
- Working in 30 minutes
- Good enough for most thermal inspection

### Choice B: True 16-bit (Break OpenCV, Gain USB Access)
- Install WinUSB driver
- Implement USB capture from scratch
- Working in 2-3 hours
- Best accuracy for temperature measurement

---

## If You Choose True 16-bit...

I'll implement:

1. **BosonUSBCapture** class
   - Direct USB bulk transfer reading
   - UVC payload header parsing
   - Y16 frame extraction
   - 16-bit numpy array output

2. **Integration with existing code**
   - Drop-in replacement for VideoCapture
   - Same API (open, read, release)
   - Automatically detects USB vs OpenCV

3. **Dual-mode support**
   - Switch between USB (16-bit) and OpenCV (8-bit) at runtime
   - Use USB hub: one port for SDK, one for video

**Example usage**:
```python
from boson_usb_capture import BosonUSBCapture

# Use direct USB for 16-bit
usb_cap = BosonUSBCapture()
usb_cap.open()

ret, frame = usb_cap.read()
print(f"dtype: {frame.dtype}")  # uint16
print(f"shape: {frame.shape}")  # (512, 640)

# Convert to temperature
temp_c = (frame / 100.0) - 273.15
```

---

## Decision Point

Which approach would you like me to implement?

**A**: Enhanced 8-bit processing (no driver changes)
**B**: True 16-bit USB capture (requires WinUSB driver)

Let me know and I'll proceed with full implementation!
