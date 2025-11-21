# FLIR Boson SDK Integration - Usage Guide

## Phase 7: Advanced Camera Control

The Thermal Inspection Fusion Tool now includes full FLIR Boson SDK integration for advanced camera control over USB serial interface.

---

## 🎯 Features

### Video + Serial Control (Combined USB Interface)
- **Video Streaming**: OpenCV-based thermal video capture
- **Serial Control**: SDK-based command interface over COM port
- **Single USB Connection**: Both video and serial over one cable

### SDK Capabilities
- ✅ **FFC (Flat Field Correction)**: Trigger camera calibration
- ✅ **AGC Control**: Automatic Gain Control algorithms
- ✅ **Gain Modes**: HIGH, LOW, AUTO, MANUAL
- ✅ **Color LUTs**: White Hot, Ironbow, Rainbow, etc.
- ✅ **Temperature Monitoring**: FPA (sensor) temperature
- ✅ **Camera Info**: Serial number, software version, part numbers

---

## 📋 Requirements

### Hardware
- FLIR Boson 320x256 or 640x512 (radiometric or non-radiometric)
- USB connection (provides both video and COM port)

### Software
- Python 3.8-3.11
- PySerial (`pip install pyserial`)
- FLIR Boson SDK (included in `3.0 IDD & SDK/`)

---

## 🚀 Quick Start

### 1. Test SDK Connection

Test the SDK wrapper directly:

```bash
python boson_sdk_wrapper.py
```

**Expected Output:**
```
✓ SDK found at: 3.0 IDD & SDK\SDK_USER_PERMISSIONS\SDK_USER_PERMISSIONS
✓ Connected to Boson

Camera Information:
  Serial Number: 30149
  Software Version: 2.0.15223
  Camera PN: XXXXX
  FPA Temp: 314.4K (41.2°C)
  Gain Mode: HIGH
  FFC Mode: AUTO

** Press Enter to trigger FFC (watch the camera shutter) **
```

### 2. Run Inspection Tool with SDK

Enable SDK when running the main inspection application:

```bash
python inspection_main.py --enable-boson-sdk --boson-com-port COM6 --use-opencv-gui
```

**Arguments:**
- `--enable-boson-sdk`: Enable SDK for serial control
- `--boson-com-port COM6`: Specify COM port (default: COM6)
- `--use-opencv-gui`: Use simple OpenCV display

**Console Output:**
```
[OK] Thermal camera connected: 640x512
============================================================
✓ Boson SDK connected - serial control enabled
  Camera SN: 30149
  Software: 2.0.15223
  FPA Temp: 41.2°C
  Gain Mode: HIGH
  Press 'f' to trigger FFC (Flat Field Correction)
============================================================
```

### 3. Keyboard Controls (OpenCV GUI)

| Key | Function | Description |
|-----|----------|-------------|
| `q` | Quit | Exit application |
| `r` | Record | Toggle video recording |
| `s` | Snapshot | Capture snapshot with metadata |
| **`f`** | **FFC Trigger** | **Trigger Flat Field Correction (watch shutter close)** |
| **`t`** | **Temperature** | **Show FPA temperature in console** |

---

## 🔧 Programmatic Usage

### Example: Capture Video with FFC Control

```python
from flir_camera import FLIRBosonCamera

# Initialize with SDK enabled
camera = FLIRBosonCamera(
    device_id=0,
    resolution=(640, 512),
    enable_sdk=True,      # Enable SDK
    com_port='COM6'       # COM port
)

if camera.open():
    print(f"Camera connected: {camera.get_actual_resolution()}")

    # Check SDK status
    if camera.is_sdk_connected():
        print("✓ SDK connected")

        # Get camera info
        info = camera.get_camera_info()
        print(f"Serial Number: {info.serial_number}")
        print(f"Software: {info.software_version}")

        # Get FPA temperature
        temp = camera.get_fpa_temperature()
        print(f"FPA Temp: {temp[1]:.1f}°C")

        # Trigger FFC
        print("Triggering FFC...")
        if camera.trigger_ffc():
            print("✓ FFC completed")

    # Capture video frames
    import cv2
    while True:
        ret, frame = camera.read()
        if not ret:
            break

        cv2.imshow('Boson', frame)

        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            break
        elif key == ord('f'):
            # Trigger FFC on keypress
            camera.trigger_ffc()

    camera.release()
```

---

## 🎛️ Advanced SDK Controls

### Gain Mode Control

```python
from boson_sdk_wrapper import GainMode

# Set gain mode
camera.set_gain_mode(GainMode.HIGH)    # High sensitivity
camera.set_gain_mode(GainMode.LOW)     # Low sensitivity
camera.set_gain_mode(GainMode.AUTO)    # Automatic
```

### Color LUT (Lookup Table)

```python
from boson_sdk_wrapper import ColorLUT

# Change thermal color palette
camera.set_color_lut(ColorLUT.WHITE_HOT)
camera.set_color_lut(ColorLUT.IRONBOW)
camera.set_color_lut(ColorLUT.RAINBOW)
```

### FFC Mode

```python
from boson_sdk_wrapper import FFCMode

# Set FFC mode
camera.set_ffc_mode(FFCMode.AUTO)      # Automatic FFC
camera.set_ffc_mode(FFCMode.MANUAL)    # Manual only
camera.set_ffc_mode(FFCMode.EXTERNAL)  # External trigger
```

---

## 🐛 Troubleshooting

### SDK Connection Failed

**Symptom:** "SDK was requested but connection failed"

**Solutions:**
1. Check COM port in Device Manager (Windows)
   - `Win + X` → Device Manager → Ports (COM & LPT)
   - Look for "USB Serial Port (COMX)" or "FLIR Boson"

2. Update `--boson-com-port` argument:
   ```bash
   python inspection_main.py --enable-boson-sdk --boson-com-port COM5
   ```

3. Verify SDK files:
   ```bash
   dir "3.0 IDD & SDK\SDK_USER_PERMISSIONS\SDK_USER_PERMISSIONS\ClientFiles_Python"
   ```

### Video Works but SDK Doesn't

**This is normal!** The camera supports two modes:

| Mode | Video | Serial Control |
|------|-------|----------------|
| **Video-Only** | ✅ OpenCV | ❌ No SDK |
| **Video + SDK** | ✅ OpenCV | ✅ Full control |

Use `--enable-boson-sdk` to enable SDK.

### FFC Command Has No Effect

**Possible causes:**
1. **SDK not connected**: Check for "✓ Boson SDK connected" message
2. **Camera busy**: Wait a few seconds and try again
3. **Non-radiometric model**: Some commands may have limited support

---

## 📊 Feature Matrix

| Feature | Non-Radiometric | Radiometric |
|---------|-----------------|-------------|
| Video Streaming | ✅ Full | ✅ Full |
| FFC Trigger | ✅ Full | ✅ Full |
| Gain Control | ⚠️ Limited | ✅ Full |
| AGC Algorithms | ⚠️ Limited | ✅ Full |
| Color LUT | ✅ Full | ✅ Full |
| Temperature Reading | ✅ FPA only | ✅ FPA + Radiometric |
| 16-bit Radiometric Data | ❌ Not available | ✅ Full (Phase 7 - pending) |

**Legend:**
- ✅ **Full**: Feature fully supported
- ⚠️ **Limited**: Feature may have reduced functionality
- ❌ **Not available**: Feature not supported on this model

---

## 🔬 Testing Non-Radiometric Camera

Your current Boson 320x256 is **non-radiometric**. This means:

### What Works ✅
- Video streaming (8-bit grayscale/YUV)
- FFC trigger (shutter calibration)
- FPA temperature reading (sensor temp)
- Color LUT control
- Camera info (serial number, software version)

### What's Limited ⚠️
- AGC algorithms (may not respond)
- Gain mode switching (may not affect video)

### What's Not Available ❌
- 16-bit radiometric data (absolute temperature)
- Spot temperature measurements
- Radiometric frame analysis

**Next Step:** Test with your **radiometric Boson** to unlock full capabilities!

---

## 🎯 Next Steps (Phase 7 Continuation)

### Radiometric Support (Pending)
When you connect your radiometric Boson:

1. **16-bit Radiometric Data**
   - Extract absolute temperature values
   - Spot temperature measurements
   - Temperature histograms

2. **Advanced Thermal Analysis**
   - Precise hot/cold spot detection
   - Temperature trend analysis
   - Calibrated thermal measurements

3. **GUI Integration**
   - Qt GUI with SDK controls
   - Live temperature display
   - FFC trigger button
   - Gain mode selector

---

## 📝 Notes

### COM Port Detection

Windows automatically assigns a COM port when Boson connects via USB. Check Device Manager:

```
Device Manager → Ports (COM & LPT) → USB Serial Port (COM6)
```

### Single USB Cable

The Boson USB interface provides **both** video and serial:
- **Video**: UVC (USB Video Class) - OpenCV can read
- **Serial**: Virtual COM port - SDK communicates here

### SDK vs. UVC Mode

The camera can operate in two modes:

1. **UVC Mode** (Default)
   - Video only via UVC
   - 8-bit AGC-processed output
   - No radiometric data

2. **VPC Mode** (With SDK)
   - Video + serial control
   - Can access 16-bit radiometric (if available)
   - Full camera configuration

Current implementation supports **VPC mode** with optional SDK.

---

## 🔗 References

- **FLIR Boson Datasheet**: See `3.0 IDD & SDK/` folder
- **SDK Documentation**: `Boson_SDK_Documentation_rev300.pdf`
- **Integration Design Document**: See Phase 7 in `INSPECTION_TRANSFORMATION_PLAN.md`

---

## ✅ Verification Checklist

Before proceeding to GUI integration:

- [x] SDK wrapper created (`boson_sdk_wrapper.py`)
- [x] FLIRBosonCamera enhanced with SDK support
- [x] SDK tested with non-radiometric camera
- [x] FFC trigger works (shutter closes visibly)
- [x] Camera info retrieved successfully
- [x] inspection_main.py integrated with SDK
- [x] Keyboard shortcuts added (f = FFC, t = temp)
- [ ] Test with radiometric camera
- [ ] GUI integration (Qt)
- [ ] Radiometric data extraction

---

**Status:** Phase 7 SDK integration complete for non-radiometric mode ✅
**Next:** Test with radiometric Boson + GUI integration
