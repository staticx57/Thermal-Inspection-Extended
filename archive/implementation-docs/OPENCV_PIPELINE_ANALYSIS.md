# OpenCV Pipeline Analysis - Channel Mismatch Issues

## Current Flow (BROKEN)

```
Non-Radiometric FLIR Boson Camera
          ↓
    8-bit YUV/Grayscale (1 channel)  ← Camera outputs PRE-COLORED or GRAYSCALE
          ↓
thermal_processor.process_frame(thermal_frame)
          ↓
    Expects BGR (3 channels)  ← BUG #1
    Tries: cv2.cvtColor(frame, COLOR_BGR2GRAY)
    Error: "Invalid number of channels: scn is 1"
```

## Root Causes

### Bug #1: thermal_processor assumes BGR input
**Location**: `thermal_processor.py` lines 254, 360
**Issue**: 
- `detect_motion()` does `cv2.cvtColor(frame, COLOR_BGR2GRAY)` 
- `detect_edges()` does `cv2.cvtColor(frame, COLOR_BGR2GRAY)`
- But camera gives **1-channel grayscale**!

### Bug #2: Palette application channel confusion  
**Fixed**: Already handled with LUT split

### Bug #3: ROI detection gets grayscale
**Location**: `roi_manager.py`
**Issue**: May expect BGR for certain operations

---

## Correct Flow Design

```
Camera Output
     ├─ Non-Radiometric: 8-bit Grayscale OR YUV (convert to grayscale)
     └─ Radiometric: 16-bit → convert to 8-bit grayscale
          ↓
[1] GRAYSCALE thermal_frame (H, W) - uint8
          ↓
[2] thermal_processor.process_frame(thermal_frame)
    - Accept GRAYSCALE input
    - Motion detection: already grayscale ✓
    - Edge detection: already grayscale ✓
          ↓
[3] palette_manager.apply_composite_palette(thermal_frame, roi_manager)
    Input: GRAYSCALE (H, W)
    Output: BGR (H, W, 3)  ← Colorized
          ↓
[4] thermal_colorized (H, W, 3) - BGR uint8
          ↓
[5] fusion_processor.fuse(thermal_colorized, rgb_frame)
    Input: Both BGR (H, W, 3)
    Output: BGR (H, W, 3)
          ↓
[6] display_frame - Ready for cv2.imshow() or Qt display
```

---

## Fixes Needed

### Fix #1: thermal_processor.detect_motion()
```python
# CURRENT (BROKEN):
def detect_motion(self, frame: np.ndarray):
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)  # ❌ Assumes BGR
    
# FIXED:
def detect_motion(self, frame: np.ndarray):
    # Accept grayscale OR BGR
    if len(frame.shape) == 3:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    else:
        gray = frame  # Already grayscale ✓
```

### Fix #2: thermal_processor.detect_edges()
Already partially fixed, but needs consistency:
```python
# Line 360-363 - NEEDS UPDATE:
if len(frame.shape) == 3:
    gray_np = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
else:
    gray_np = frame  # Already grayscale ✓
```

### Fix #3: Ensure camera outputs grayscale
```python
# flir_camera.py - ensure consistent output:
def read(self):
    frame = capture_from_hardware()
    
    # Convert to grayscale if needed
    if len(frame.shape) == 3:
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    
    return frame  # Always (H, W) uint8
```

---

## Testing Plan

### Test 1: Verify camera output format
```python
thermal = camera.read()
print(f"Shape: {thermal.shape}")  # Should be (H, W) not (H, W, 3)
print(f"Dtype: {thermal.dtype}")   # Should be uint8
```

### Test 2: Verify motion detection
```python
processor = ThermalProcessor()
gray_frame = np.random.randint(0, 256, (100, 100), dtype=np.uint8)
result = processor.detect_motion(gray_frame)  # Should NOT crash
```

### Test 3: Verify edge detection
```python
gray_frame = np.random.randint(0, 256, (100, 100), dtype=np.uint8)
edges, clusters = processor.detect_edges(gray_frame)  # Should work
```

### Test 4: Full pipeline
```python
thermal = camera.read()  # (H, W) grayscale
result = app.process_frame(thermal)  # Should produce BGR display
assert result['display_frame'].shape == (H, W, 3)
```

---

## Channel Format Contract

| Stage | Input | Output | Notes |
|-------|-------|--------|-------|
| Camera | - | (H,W) uint8 | Always grayscale |
| thermal_processor | (H,W) uint8 | Same + detections | Grayscale in/out |
| palette_manager | (H,W) uint8 | (H,W,3) BGR | Colorizes |
| fusion_processor | (H,W,3) BGR | (H,W,3) BGR | BGR in/out |
| Display | (H,W,3) BGR | - | Qt/OpenCV show |

---

## Priority Fixes

**Immediate**:
1. Fix `thermal_processor.detect_motion()` to handle grayscale
2. Verify `detect_edges()` grayscale handling  
3. Test with actual camera

**Later**:
4. Add input validation everywhere
5. Document expected formats in docstrings
6. Add assertions for channel counts

---

**Status**: Analysis complete, 3 bugs identified
**Next**: Apply fixes to thermal_processor.py
