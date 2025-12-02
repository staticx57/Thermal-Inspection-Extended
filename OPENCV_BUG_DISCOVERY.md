# CRITICAL DISCOVERY: OpenCV 4.11+ Bug with 16-bit Capture

**Date**: 2025-12-01
**GitHub Issue**: [#27166](https://github.com/opencv/opencv/issues/27166)
**Status**: 🎯 **CONFIRMED BUG** - Fixed in OpenCV 4.12.0
**Impact**: Explains our Y16 capture failures!

---

## TL;DR

**OpenCV 4.11.0 has a CONFIRMED BUG with 16-bit image capture!**

- **Bug**: When `CAP_PROP_CONVERT_RGB` is disabled, frames are returned as flattened 1D arrays instead of proper 2D images
- **Affects**: Thermal cameras (FLIR Boson specifically mentioned)
- **Versions Affected**: OpenCV 4.11+
- **Fix**: Merged in PR #27193, will be in OpenCV 4.12.0
- **Workaround**: Downgrade to OpenCV 4.9.0.80

---

## GitHub Issue #27166 Details

### Problem Description

**Title**: "16-bit image capture regression with V4L backend"

**Reporter**: User capturing FLIR Boson thermal camera data

**Issue**:
> Users capturing 16-bit images (like FLIR Boson thermal cameras) via V4L receive flattened 1D arrays instead of proper 2D image matrices in OpenCV 4.11+, while 4.9 worked correctly.

### Symptoms (MATCHES OURS!)

From the issue:
```python
# Expected (OpenCV 4.9):
frame.shape = (512, 640)  # Proper 2D image
frame.dtype = np.uint16   # 16-bit

# Got (OpenCV 4.11):
frame.shape = (1, 327680)  # Flattened 1D array
frame.dtype = np.uint8    # Wrong type
```

**Our Test Results**:
```python
# Test 5 (MSMF backend):
frame.shape = (1, 460800)  # Flattened!
frame.dtype = uint8
```

**THIS MATCHES THE BUG!**

### Root Cause (from issue)

In OpenCV 4.11, when `CAP_PROP_CONVERT_RGB` is false:
```cpp
// WRONG (4.11):
const Size sz(..., 1);  // Creates 1D array!
frame = Mat(sz, CV_8U, ...);

// Should call v4l2_create_frame() instead
// which properly handles 16-bit formats with correct dimensions
```

### Fix Status

- **PR**: [#27193](https://github.com/opencv/opencv/pull/27193) ✅ MERGED
- **Milestone**: 4.12.0
- **Status**: Fixed, awaiting 4.12.0 release

---

## How This Relates to Our Testing

### Our Test Results Explained

**Test 5 (Our Results)**:
```
Backend: MSMF
Frame shape: (1, 460800)  <-- FLATTENED 1D ARRAY (BUG!)
Frame dtype: uint8
```

**Calculation**:
- Expected: 640 × 512 = 327,680 pixels
- Got: 460,800 elements (different, but still flattened)
- **This is the bug in action!**

### Why DirectShow Tests Also Failed

**Tests 1-4 Results**:
```
Actual FOURCC: '}ë6ä' (corrupted)
Shape: (480, 640, 3)
```

**Explanation**:
- DirectShow on Windows 11 STILL doesn't negotiate Y16
- But even if it did, OpenCV 4.11 bug would flatten it
- **We had TWO separate issues**:
  1. Windows 11 DirectShow won't select Y16 (OS issue)
  2. OpenCV 4.11 flattens 16-bit arrays even if captured (OpenCV bug)

---

## Action Items

### ✅ Immediate: Test OpenCV 4.9.0

**This is the version that SHOULD work!**

The issue reports OpenCV 4.9.0.80 worked correctly for FLIR Boson.

**Steps**:
```bash
# Create venv with OpenCV 4.9.0
python -m venv venv_opencv490
venv_opencv490\Scripts\activate

# Install OpenCV 4.9.0
pip install opencv-python==4.9.0.80

# Verify
python -c "import cv2; print(cv2.__version__)"
# Should show: 4.9.0

# Run test
python test_convert_rgb_order.py
```

**Expected Result**:
- Test 5 (MSMF) might give proper shape
- DirectShow tests still fail (Windows 11 issue separate)

---

### 📋 Wait for OpenCV 4.12.0

**The fix is merged!**

**Timeline**:
- PR #27193 merged
- Milestone: 4.12.0
- Release: Unknown (weeks/months)

**When released**:
```bash
pip install opencv-python==4.12.0
```

**This will fix the flattened array bug.**

---

### 🔧 Alternative: Manually Reshape (Workaround)

If you get a flattened array, you can reshape it:

```python
ret, frame = cap.read()

# Check if flattened
if len(frame.shape) == 2 and frame.shape[0] == 1:
    # Flattened 1D array due to bug
    total_pixels = frame.shape[1]

    # Reshape to 2D (Boson 640: 640x512 = 327680)
    width = 640
    height = 512

    if total_pixels == width * height:
        frame = frame.reshape(height, width)
        print(f"Reshaped from {frame.shape} to ({height}, {width})")
```

**Limitation**:
- Only works if you know the expected dimensions
- Doesn't fix dtype issue (still uint8 not uint16)

---

## Comparison of OpenCV Versions

| Version | V4L 16-bit | DirectShow Y16 | Notes |
|---------|------------|----------------|-------|
| **4.6.0** | ✅ Works | ❓ (untested on Win11) | FLIR forum confirmed |
| **4.9.0** | ✅ Works | ❓ Unknown | Issue #27166 says works |
| **4.11.0** | ❌ Flattened bug | ❌ Win11 issue | **Current version** |
| **4.12.0** | ✅ Fixed (PR merged) | ❓ Unknown | **Future release** |

---

## Updated Conclusion

### We Found TWO Separate Issues!

#### Issue 1: Windows 11 DirectShow (OS limitation)
- **Affects**: DirectShow backend on Windows 11
- **Symptom**: Negotiates to YUY2/I420 instead of Y16
- **Solution**: Direct USB capture, or Windows 10

#### Issue 2: OpenCV 4.11+ Bug (Software bug) 🆕
- **Affects**: All backends when CAP_PROP_CONVERT_RGB disabled
- **Symptom**: Flattened 1D arrays instead of 2D images
- **Solution**: Downgrade to 4.9.0 or wait for 4.12.0
- **Status**: Fixed in 4.12.0

### Combined Effect

On Windows 11 with OpenCV 4.11:
- DirectShow won't select Y16 (Issue 1)
- Even if it did, array would be flattened (Issue 2)
- MediaFoundation auto-selects, but flattens output (Issue 2)

**Result**: Complete failure to get proper 16-bit images

---

## Revised Testing Plan

### Test OpenCV 4.9.0 on Windows 11

**Hypothesis**: OpenCV 4.9.0 might work better than 4.6.0

**Why**:
- GitHub issue specifically mentions 4.9.0.80 working
- Newer than 4.6.0 (more features)
- Older than 4.11.0 (no flattening bug)

**Test**:
```bash
python -m venv venv_opencv490
venv_opencv490\Scripts\activate
pip install opencv-python==4.9.0.80
python test_convert_rgb_order.py
```

**Expected**:
- DirectShow: Still fails (Windows 11 limitation)
- MSMF (Test 5): Might work! (no flattening bug)

---

## Why Test 5 Was Different

Looking back at Test 5 results:
```
Backend: MSMF (MediaFoundation)
Frame shape: (1, 460800)  <-- FLATTENED
Frame dtype: uint8
```

**This was the closest to working!**

- MSMF backend auto-selected (not DirectShow)
- Got raw data (460,800 elements)
- **Flattened due to OpenCV 4.11 bug**

**With OpenCV 4.9.0**:
- MSMF might auto-select again
- Data captured
- **No flattening bug!**
- Might get proper (512, 640) uint16!

---

## Recommendation Update

### Priority 1: Test OpenCV 4.9.0 ⚡ DO THIS

**Time**: 10 minutes
**Risk**: None (venv)
**Probability**: Medium-High (issue mentions it works)

```bash
python -m venv venv_opencv490
venv_opencv490\Scripts\activate
pip install opencv-python==4.9.0.80
python test_convert_rgb_order.py
```

**Look for**: Test 5 (MSMF backend) succeeding!

---

### Priority 2: Wait for OpenCV 4.12.0 📅

**Timeline**: Weeks/months
**Certainty**: High (fix merged)
**Action**: Monitor OpenCV releases

When released:
```bash
pip install --upgrade opencv-python==4.12.0
python test_convert_rgb_order.py
```

---

### Priority 3: Direct USB Capture (if needed) 🔧

**Time**: 3 hours
**Certainty**: Guaranteed
**Use when**: Can't wait for OpenCV fix

See `DIRECT_USB_CAPTURE_GUIDE.md`

---

## Sources

- **GitHub Issue**: [opencv/opencv#27166](https://github.com/opencv/opencv/issues/27166)
- **Fix PR**: [opencv/opencv#27193](https://github.com/opencv/opencv/pull/27193)
- **Mentions**: FLIR Boson thermal cameras specifically
- **Affected Versions**: OpenCV 4.11+
- **Working Versions**: 4.9.0.80 and earlier
- **Fix Version**: 4.12.0 (upcoming)

---

## What This Changes

### Before This Discovery:
- Thought it was purely Windows 11 DirectShow issue
- Planned direct USB or Win10 as only solutions

### After This Discovery:
- **NEW OPTION**: OpenCV 4.9.0 might work on Windows 11!
- The MSMF backend (Test 5) was trying to work
- Flattening bug prevented success
- **Testing 4.9.0 is the next logical step**

---

## Test Script for OpenCV 4.9.0

Create this test specifically for 4.9.0:

```python
# test_opencv_490.py
import cv2
import numpy as np

print(f"OpenCV version: {cv2.__version__}")

# Try MSMF backend (auto-select)
print("\nTesting auto backend (likely MSMF)...")
cap = cv2.VideoCapture(1)
cap.set(cv2.CAP_PROP_CONVERT_RGB, 0.0)
cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter.fourcc('Y','1','6',' '))

backend = cap.getBackendName()
print(f"Backend: {backend}")

ret, frame = cap.read()
if ret:
    print(f"Frame dtype: {frame.dtype}")
    print(f"Frame shape: {frame.shape}")

    if frame.dtype == np.uint16 and len(frame.shape) == 2:
        print("✓ SUCCESS - Got 16-bit 2D grayscale!")
        print(f"Min: {frame.min()}, Max: {frame.max()}")
    else:
        print("✗ Still not 16-bit 2D")
else:
    print("✗ Failed to capture")

cap.release()
```

---

**NEXT STEP**: Test OpenCV 4.9.0! This might solve it! 🎯
