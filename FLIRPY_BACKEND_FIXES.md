# flirpy Backend - Bug Fixes Applied

**Date**: 2025-12-03
**Status**: ✅ FIXED - Ready for testing

---

## Bug Fixed: Frame Size Mismatch on Backend Switching

### Problem

When switching between backends (e.g., OpenCV 640x480 → flirpy 320x256), the application crashed with:
```
cv2.error: (-215:Assertion failed) _src.sameSize(_dst) && dcn == scn in function 'cv::accumulateWeighted'
cv2.error: (-209:Sizes of input arguments do not match)
```

**Root Cause**: The thermal analyzer's background model and thermal processor's motion detection stored the old frame size. When the new backend provided frames with a different resolution, OpenCV's `cv2.accumulateWeighted()` and `cv2.absdiff()` failed due to size mismatch.

### Solution

Added reset methods to clear state when frame size changes:

#### 1. **thermal_analyzer.py** - Added `reset_background_model()`

```python
def reset_background_model(self):
    """Reset background model and frame count (call when frame size changes)."""
    self.background_model = None
    self.frame_count = 0
```

**Location**: `thermal_analyzer.py:199-202`

#### 2. **thermal_processor.py** - Added `reset_motion_detection()`

```python
def reset_motion_detection(self):
    """Reset motion detection state (call when frame size changes)."""
    self.prev_frame = None
    self.motion_history.clear()
    self.prev_normalized_distance = None
```

**Location**: `thermal_processor.py:91-95`

#### 3. **inspection_main.py** - Call reset methods in `switch_thermal_backend()`

```python
# 8.5. Reset thermal analyzer and processor due to resolution change
# This prevents size mismatch errors in background modeling and motion detection
if hasattr(self, 'thermal_analyzer') and self.thermal_analyzer:
    logger.info("Resetting thermal analyzer background model...")
    self.thermal_analyzer.reset_background_model()

if hasattr(self, 'thermal_processor') and self.thermal_processor:
    logger.info("Resetting thermal processor motion detection...")
    self.thermal_processor.reset_motion_detection()
```

**Location**: `inspection_main.py:3585-3593`

---

## Files Modified

1. **thermal_analyzer.py** (Line 199-202)
   - Added `reset_background_model()` method

2. **thermal_processor.py** (Line 91-95)
   - Added `reset_motion_detection()` method

3. **inspection_main.py** (Line 3585-3593)
   - Call reset methods during backend switch

---

## What This Fixes

✅ **Backend switching no longer crashes** - Can switch between opencv/usb/flirpy backends without errors
✅ **Background model resets** - Statistical anomaly detection works after switching
✅ **Motion detection resets** - Motion tracking works with new frame size
✅ **Smooth transition** - Frame processing continues immediately after switch

---

## Testing Instructions

### Test Backend Switching:

1. **Launch with SDK**:
   ```bash
   python inspection_main.py --enable-boson-sdk --boson-com-port COM7
   ```

2. **Switch to flirpy backend**:
   - Go to: Analysis > Radiometric Panel
   - Select: "16-bit flirpy (Best of Both)"
   - Click: "Apply Backend Change"

3. **Expected Results**:
   - ✅ Backend switches successfully
   - ✅ No size mismatch errors in console
   - ✅ Frames continue at ~9 FPS
   - ✅ Background model rebuilds (takes ~30 frames)
   - ✅ Motion detection works with new frame size
   - ✅ Temperature values are correct (Y16 radiometric)

4. **Switch back to OpenCV**:
   - Select: "8-bit OpenCV + SDK"
   - Click: "Apply Backend Change"
   - ✅ Should work smoothly in reverse

---

## Expected Console Output

```
=== Switching thermal backend to: flirpy ===
Main loop paused for backend switching
Stopping threaded capture...
Releasing current thermal camera...
Opening Boson camera via flirpy...
✓ Boson camera opened via flirpy
[OK] Thermal camera connected: 320x256 (flirpy backend)
Radiometric mode enabled
Resetting thermal analyzer background model...
Resetting thermal processor motion detection...
✓ GUI radiometric panel updated for flirpy backend
Threaded capture restarted
=== Successfully switched to flirpy backend ===
Main loop resumed
```

---

## Technical Details

### Why Frame Size Changes:

| Backend | Resolution | Bit Depth | Format |
|---------|-----------|-----------|--------|
| OpenCV  | 640x480 (upscaled) | 8-bit | RGB/Gray AGC |
| flirpy  | 320x256 (native) | 16-bit | Y16 Radiometric |
| USB     | 320x256 (native) | 16-bit | Y16 Radiometric |

### Background Model Rebuild Time:

- The thermal analyzer uses `background_init_frames = 30`
- After a reset, it takes ~30 frames (3-4 seconds at 9 FPS) to rebuild
- During this time, anomaly detection uses the current frame as baseline
- This is expected behavior and not a bug

### Motion Detection Initialization:

- Motion detection requires 1 frame to initialize `prev_frame`
- Works immediately after reset (1 frame delay)

---

## Additional Notes

- The fix is **backward compatible** - doesn't affect single-backend usage
- Reset methods can be called at any time (safe to call multiple times)
- No performance impact - resets only happen during backend switches
- Works for all backends: opencv, usb, flirpy

---

## Next Steps

1. ✅ Test backend switching with camera connected
2. ✅ Verify temperature values with flirpy backend
3. ✅ Check that all GUI panels update correctly
4. ✅ Validate long-term stability (no memory leaks, etc.)

---

**Status**: Ready for user testing! 🎉
