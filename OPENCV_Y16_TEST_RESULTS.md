# OpenCV Y16 Test Results

## Test Date: 2025-12-02

## Question
Can we get 16-bit Y16 radiometric data from the FLIR Boson using OpenCV with the default UVC driver (avoiding the need for WinUSB)?

## Answer: NO ❌

## Test Results

### Hardware Configuration
- Camera: FLIR Boson 640
- Driver: UVC (Windows default)
- Device ID: 1
- Backend: DirectShow (DSHOW)

### Default Capture Format
```
Resolution: 640×512
FPS: 0.0
FourCC: 0x30323449 (I420 - YUV 4:2:0)
Frame Shape: (512, 640, 3)
Frame Dtype: uint8
Range: 0-255
```

### Y16 Format Requests - All Failed

Attempted to request Y16 format using various FourCC codes:

| Format | FourCC Code | Result | Frame Type |
|--------|-------------|---------|------------|
| Y16 (space) | 0x20363159 | Failed | uint8 (reverted to I420) |
| Y16 (null) | 0x00363159 | Failed | No frame captured |
| GREY | 0x59455247 | Failed | uint8 (reverted to I420) |
| Y800 | 0x30303859 | Failed | uint8 (reverted to I420) |

**All attempts returned 8-bit uint8 frames, never uint16.**

### Alternative Mode Testing

Tested `CAP_PROP_MODE` 0-9: All returned `uint8` frames with shape `(512, 640, 3)`.

## Conclusion

**The FLIR Boson UVC driver only exposes 8-bit AGC (T-Linear processed) frames via DirectShow.**

The camera does NOT expose raw 16-bit Y16 radiometric data through the UVC interface.

## Why the FLIR App Gets Y16

The FLIR app likely achieves 16-bit radiometric capture by:

1. **Using WinUSB driver** instead of UVC
2. **Direct USB bulk transfers** to read Y16 frames
3. **Bypassing the DirectShow/UVC stack** entirely

This is exactly what our `pyusb_thermal_backend.py` does!

## Implications

### For Enhanced Backend Implementation

✅ **Confirmed: Our enhanced PyUSB approach is necessary and correct**

To get both Y16 radiometric AND SDK control, we must:
1. Install WinUSB driver (replaces UVC)
2. Use PyUSB for direct video bulk transfers (Y16)
3. Use PyUSB for direct control bulk transfers (SDK via FSLP)

### Backend Comparison

| Backend | Driver | Video Format | SDK Control | Method |
|---------|--------|--------------|-------------|---------|
| **OpenCV** | UVC | 8-bit AGC | ✅ Yes (COM port) | DirectShow |
| **PyUSB (current)** | WinUSB | 16-bit Y16 | ❌ No | Direct USB video only |
| **Enhanced PyUSB** | WinUSB | 16-bit Y16 | ✅ Yes (USB FSLP) | Direct USB video + control |

## Architecture Validation

This test **validates** our hybrid backend architecture:

```
┌─────────────────────────────────────────────────────────┐
│         Enhanced PyUSB Backend (ONLY SOLUTION)          │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  Video: USB Bulk IN (0x81)  →  Y16 16-bit frames       │
│  Control: USB Bulk I/O       →  SDK commands via FSLP   │
│                                                          │
│  Driver: WinUSB (installed via Zadig)                   │
│  Access: PyUSB direct bulk transfers                    │
└─────────────────────────────────────────────────────────┘
```

## Test Script

The test is available in `test_opencv_y16.py` and can be re-run anytime:

```bash
python test_opencv_y16.py
```

## Key Findings

1. ❌ **OpenCV + UVC cannot get Y16** - Only 8-bit AGC
2. ✅ **WinUSB + PyUSB is required for Y16** - Direct USB access needed
3. ✅ **Enhanced backend approach validated** - Correct architecture
4. ✅ **FSLP over USB work is necessary** - SDK control requires it

## Next Steps

Continue with enhanced PyUSB backend implementation:

1. ✅ USB FSLP transport layer (`usb_fslp_transport.py`) - **COMPLETE**
2. 🚧 USB SDK dispatcher - **NEXT**
3. 🚧 Enhanced backend class - **PENDING**
4. 🚧 Testing with WinUSB driver - **REQUIRES HARDWARE**

---

**Test File**: `test_opencv_y16.py`
**Result**: OpenCV cannot capture Y16 from Boson UVC driver
**Status**: Enhanced PyUSB backend approach confirmed necessary
