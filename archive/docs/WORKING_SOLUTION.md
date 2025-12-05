# ✅ WORKING SOLUTION - Y16 16-bit Radiometric Capture from FLIR Boson

## Summary

**Goal**: Get TRUE 16-bit radiometric data from FLIR Boson on Windows (not 8-bit post-AGC)

**Solution**: Use `flirpy` library instead of OpenCV

**Status**: ✅ **WORKING**

## The Problem

- OpenCV with DirectShow on Windows **does not properly support Y16 format**
- Even after configuring the camera via SDK for Y16 output, OpenCV returns 8-bit RGB data
- This is a known limitation of the DirectShow backend

## The Solution

Use **flirpy** - a Python library specifically designed for FLIR cameras.

### Installation

```bash
pip install flirpy numpy
```

### Working Code

```python
from flirpy.camera.boson import Boson
import numpy as np

# Open camera
camera = Boson()

# Capture frame
frame = camera.grab()

# Verify it's 16-bit
print(f"Shape: {frame.shape}")        # (256, 320) for Boson 320
print(f"Dtype: {frame.dtype}")        # uint16
print(f"Min/Max: {frame.min()}/{frame.max()}")  # e.g., 28855/30165

# Convert to temperature (HIGH gain mode)
temp_celsius = (frame.astype(np.float32) / 100.0) - 273.15

# Save
np.save('boson_y16.npy', frame)

camera.close()
```

## Verified Results

### Captured Data:
- **Shape**: 256×320 pixels
- **Dtype**: `uint16` (TRUE 16-bit)
- **Value Range**: 28,855 - 30,165 (16-bit values, not 8-bit!)
- **Temperature Range**: 15.4°C to 28.5°C
- **Mean Temperature**: 21.85°C

### Key Verification Points:
✅ dtype == np.uint16 (not uint8)
✅ max value > 255 (proof of 16-bit range)
✅ Realistic temperature values
✅ Can convert to numpy for processing

## Quick Start

1. **Install requirements:**
   ```bash
   pip install flirpy numpy
   ```

2. **Run the working capture script:**
   ```bash
   python capture_flirpy.py
   ```

3. **Expected output:**
   ```
   Frame 1:
     Shape: (256, 320)
     Dtype: uint16
     Min: 28855
     Max: 30165
     [OK] TRUE 16-bit radiometric data!
     Temperature range: 15.4C to 28.5C
     [OK] Saved to boson_flirpy_y16.npy
   ```

## What We Tried (and why it didn't work)

### ❌ OpenCV + DirectShow
- **Tried**: Setting FOURCC to 'Y16 ', disabling RGB conversion
- **Result**: Still got uint8 RGB (480×640×3)
- **Why**: DirectShow backend doesn't properly expose Y16 format on Windows

### ❌ PyAV / FFmpeg
- **Tried**: Using FFmpeg backend to request gray16le format
- **Result**: Not tested fully, but flirpy worked first

### ✅ flirpy
- **Why it works**: Uses proper UVC interface wrapping
- **Result**: TRUE 16-bit uint16 data

## Temperature Conversion

For **HIGH gain mode** (temperatures -40°C to 120°C):
```python
temp_celsius = (pixel_value / 100.0) - 273.15
```

For **LOW gain mode** (temperatures > 120°C):
```python
temp_celsius = (pixel_value / 50.0) - 273.15
```

## Using the Data

### Load saved frame:
```python
frame = np.load('boson_flirpy_y16.npy')
```

### Get temperature at a specific pixel:
```python
pixel_value = frame[y, x]
temp_c = (pixel_value / 100.0) - 273.15
print(f"Temperature at ({x},{y}): {temp_c:.1f}°C")
```

### Find hottest spot:
```python
max_temp_value = frame.max()
max_loc = np.unravel_index(frame.argmax(), frame.shape)
max_temp_c = (max_temp_value / 100.0) - 273.15
print(f"Hottest spot: {max_temp_c:.1f}°C at {max_loc}")
```

### Get average temperature in ROI:
```python
roi = frame[100:200, 150:250]
avg_temp_c = (roi.mean() / 100.0) - 273.15
print(f"ROI average: {avg_temp_c:.1f}°C")
```

### Convert to 8-bit for visualization:
```python
# Normalize to 0-255 for display
norm = ((frame - frame.min()) / (frame.max() - frame.min()) * 255).astype(np.uint8)

# Apply colormap (optional)
import cv2
colored = cv2.applyColorMap(norm, cv2.COLORMAP_INFERNO)
cv2.imshow('Thermal', colored)
cv2.waitKey(0)
```

## Files

- **capture_flirpy.py** - ✅ WORKING capture script
- **boson_flirpy_y16.npy** - Sample captured 16-bit frame
- **find_boson_device.py** - Device scanner (for troubleshooting)
- **capture_with_opencv.py** - ❌ Non-working OpenCV attempt (for reference)

## Next Steps

Now that you have working Y16 capture, you can:

1. **Port to your main application**: Use the flirpy method
2. **Process temperature data**: Already in numpy format
3. **Feed to ML models**: 16-bit data ready for training/inference
4. **Real-time processing**: flirpy can capture continuously

## Technical Notes

- **Camera**: FLIR Boson 320 (SDK configured for T-Linear radiometric mode)
- **Output Format**: Y16 (16-bit grayscale, little-endian)
- **Resolution**: 320×256 for Boson 320, 640×512 for Boson 640
- **Gain Mode**: HIGH (for temps -40°C to 120°C)
- **SDK**: Used only for initial configuration (FFC, gain, radiometric mode)
- **Capture Library**: flirpy (handles UVC Y16 properly on Windows)

## Success Criteria Met

✅ TRUE 16-bit radiometric data (not 8-bit AGC)
✅ Stock drivers (no custom drivers needed)
✅ SDK for configuration (working)
✅ Python capture (working with flirpy)
✅ Numpy arrays ready for processing
✅ Temperature conversion working
✅ Can port to larger application

---

**Ready for production use!** 🎉
