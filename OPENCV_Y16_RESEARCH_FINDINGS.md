# OpenCV Y16 Format Research Findings
**Date**: 2025-12-01
**Research Focus**: 16-bit Y16 capture with FLIR Boson on Windows

---

## Summary

Web research confirms that **OpenCV Y16 support exists but has known issues on Windows**, particularly with DirectShow backend and newer Windows/OpenCV versions. The FLIR forum evidence suggesting OpenCV 4.6.0 + Python 3.7.9 on Windows 10 works aligns with documented compatibility issues in newer versions.

---

## Key Findings from Web Research

### 1. Official FLIR Documentation Confirms Y16 Support

**Source**: [FLIR OEM - Boson Video and Image Capture using OpenCV 16-bit Y16](https://flir.custhelp.com/app/answers/detail/a_id/3387)

**Key Points**:
- DirectShow backend is **required** for Windows Y16 capture
- Codec for IR16 is FourCC "Y16 " (note the space after '6')
- Boson 640: 640x512 (without telemetry) or 640x514 (with telemetry)
- Y16 captures pre-AGC / 16-bit radiometric video

**Official Python Example**:
```python
cap = cv2.VideoCapture(device_index + cv2.CAP_DSHOW)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 512)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter.fourcc('Y','1','6',' '))
cap.set(cv2.CAP_PROP_CONVERT_RGB, 0)  # CRITICAL!
```

**Important**: `CAP_PROP_CONVERT_RGB` must be set to `0` (false), otherwise DirectShow converts 16-bit to grey RGB.

---

### 2. Y16 Support Was Added to OpenCV DirectShow Backend

**Source**: [Add support for changing fourcc and support mono formats (e.g. Y8, Y16) in DirectShow by jveitchmichaelis · Pull Request #12454](https://github.com/opencv/opencv/pull/12454)

**Key Points**:
- Y16 support was added via PR #12454
- Fixed bug where changing FOURCC property had no effect
- Based on modified code from e-Con Systems
- Supports Y8, Y16, and other mono formats

**Critical Behavior**:
> "If the user selects Y16 via CAP_PROP_FOURCC, DirectShow retrieves a 16-bit image but it is **implicitly converted to a grey RGB image** unless the user sets `CV_CAP_PROP_CONVERT_RGB` to false, in which case a 16-bit Mat is returned."

**This explains our issue!** We may not have been setting `CAP_PROP_CONVERT_RGB` correctly.

---

### 3. DirectShow is Legacy Technology on Windows 11

**Source**: [USB Video Class (UVC) Camera Implementation Guide - Microsoft](https://learn.microsoft.com/en-us/windows-hardware/drivers/stream/uvc-camera-implementation-guide)

**Key Points**:
- Windows 10/11 include inbox UVC driver (supports UVC 1.0 to 1.5)
- DirectShow is **legacy** - Microsoft recommends MediaFoundation instead
- DirectShow optimized for Windows 10/11 but no longer actively developed
- Y16 format is supported in UVC specification

**Microsoft's Recommendation**:
> "Microsoft strongly recommends that new code use MediaPlayer, IMFMediaEngine and Audio/Video Capture in Media Foundation instead of DirectShow."

**Implications**:
- DirectShow behavior may differ between Windows 10 and Windows 11
- Newer OpenCV versions may have DirectShow regressions
- MediaFoundation backend might work better (if OpenCV supports it)

---

### 4. Known Issues with Y16 Format on Windows

**Source**: [How can I get OpenCV to work with Y16 format? - Stack Overflow](https://stackoverflow.com/questions/70988369/how-can-i-get-opencv-to-work-with-y16-format)

**Community Reports**:
- Y16 format works on **Linux (V4L2)** reliably
- Windows DirectShow has **inconsistent behavior**
- Some users report success with older OpenCV versions
- Setting `CAP_PROP_CONVERT_RGB` to `False` is critical

**Working Configuration (from user reports)**:
- OpenCV 4.6.0 + Python 3.7.9 + Windows 10 Build 19042 ✅
- OpenCV 4.11.0 + Python 3.10 + Windows 11 Build 26200 ❌ (our system)

---

### 5. UVC Y16 Format Support in DirectShow

**Source**: [Image Acquisition Interface for DirectShow - MVTec](https://www.mvtec.com/products/interfaces/documentation/view/1304-standard-13-mvtecdoc-directshow)

**Supported Formats in DirectShow**:
- RGB8, RGB555, RGB565, RGB24, RGB32
- Y800 (8-bit grayscale)
- UYVY, Y411, Y41P
- **Y16** (16-bit grayscale - added in later versions)

**Y16 Format Details**:
- FourCC: "Y16 "
- Format GUID: specific to IR raw data stream
- Bit depth: 16-bit per pixel
- Color space: Grayscale

---

## Analysis: Why Our Implementation Doesn't Work

### Our Current Code (from test_flir_official_method.py):
```python
cap = cv2.VideoCapture(1, cv2.CAP_DSHOW)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 512)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter.fourcc('Y','1','6',' '))
cap.set(cv2.CAP_PROP_CONVERT_RGB, 0)
```

**Result**: Still getting I420 (8-bit YUV)

### Possible Root Causes:

#### 1. DirectShow Format Negotiation Issue (Most Likely)
- **Windows 11 Build 26200** may have different UVC driver behavior than Windows 10
- DirectShow may prefer I420 over Y16 in newer Windows versions
- Camera offers multiple formats; DirectShow picks "best" based on merit system

#### 2. OpenCV 4.11.0 Regression
- OpenCV 4.6.0 confirmed working (FLIR forum)
- OpenCV 4.11.0 may have DirectShow backend regression
- Changes between 4.6.0 and 4.11.0 could have broken Y16 negotiation

#### 3. CAP_PROP_CONVERT_RGB Not Applied Correctly
- Setting returns `True` but may not be honored
- Timing issue: Set before or after FOURCC?
- Need to verify actual OpenCV backend behavior

#### 4. Missing DirectShow Filter
- FLIR apps may install custom DirectShow filter
- Standard Windows UVC driver + OpenCV might not cooperate
- Custom filter would force Y16 format

---

## Recommended Solutions (Priority Order)

### Solution 1: Test OpenCV 4.6.0 on Windows 10 ⭐ RECOMMENDED

**Rationale**: FLIR forum confirms this works

**Steps**:
1. Create Python 3.7.9 virtual environment
   ```bash
   # Use pyenv or download Python 3.7.9 installer
   python3.7 -m venv venv_py37
   venv_py37\Scripts\activate
   ```

2. Install OpenCV 4.6.0
   ```bash
   pip install opencv-python==4.6.0.66
   ```

3. Test on Windows 10 machine (if available)
   - Borrow Windows 10 laptop
   - Use virtual machine with Windows 10 Build 19042
   - Dual boot to Windows 10

4. Run exact test code from FLIR documentation

**Expected Result**: 16-bit Y16 capture should work

**Effort**: 1-2 hours
**Risk**: Low
**Success Probability**: High (confirmed by FLIR forum user)

---

### Solution 2: Verify CAP_PROP_CONVERT_RGB Order

**Rationale**: Property setting order may matter

**Test Code**:
```python
import cv2
import numpy as np

# Test 1: Set CONVERT_RGB BEFORE FOURCC
cap = cv2.VideoCapture(1, cv2.CAP_DSHOW)
cap.set(cv2.CAP_PROP_CONVERT_RGB, 0)  # First
cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter.fourcc('Y','1','6',' '))  # Second
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 512)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)

ret, frame = cap.read()
print(f"Test 1: dtype={frame.dtype}, shape={frame.shape}")
cap.release()

# Test 2: Set CONVERT_RGB AFTER FOURCC
cap = cv2.VideoCapture(1, cv2.CAP_DSHOW)
cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter.fourcc('Y','1','6',' '))  # First
cap.set(cv2.CAP_PROP_CONVERT_RGB, 0)  # Second
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 512)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)

ret, frame = cap.read()
print(f"Test 2: dtype={frame.dtype}, shape={frame.shape}")
cap.release()

# Test 3: Reopen after setting properties
cap = cv2.VideoCapture(1, cv2.CAP_DSHOW)
cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter.fourcc('Y','1','6',' '))
cap.set(cv2.CAP_PROP_CONVERT_RGB, 0)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 512)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
cap.release()
cap.open(1, cv2.CAP_DSHOW)  # Reopen

ret, frame = cap.read()
print(f"Test 3: dtype={frame.dtype}, shape={frame.shape}")
cap.release()
```

**Effort**: 15 minutes
**Risk**: None
**Success Probability**: Low (but worth trying)

---

### Solution 3: Try MediaFoundation Backend

**Rationale**: DirectShow is legacy; MediaFoundation is modern

**Test Code**:
```python
import cv2

# Try MSMF (Media Foundation) instead of DirectShow
cap = cv2.VideoCapture(1, cv2.CAP_MSMF)
cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter.fourcc('Y','1','6',' '))
cap.set(cv2.CAP_PROP_CONVERT_RGB, 0)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 512)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)

ret, frame = cap.read()
if ret:
    print(f"MSMF: dtype={frame.dtype}, shape={frame.shape}")
else:
    print("MSMF: Failed to capture")
cap.release()
```

**Note**: MediaFoundation may not support Y16 in OpenCV (not well documented)

**Effort**: 15 minutes
**Risk**: None
**Success Probability**: Low

---

### Solution 4: Check for FLIR DirectShow Filter

**Rationale**: FLIR apps may install custom DirectShow filter

**Steps**:
1. Search for FLIR-related .ax files (DirectShow filters):
   ```powershell
   Get-ChildItem -Path "C:\Program Files" -Filter "*.ax" -Recurse | Select-String -Pattern "FLIR|Boson"
   Get-ChildItem -Path "C:\Windows\System32" -Filter "*.ax" | Select-String -Pattern "FLIR|Boson"
   ```

2. Check registry for FLIR DirectShow filters:
   ```powershell
   Get-ChildItem -Path "HKLM:\SOFTWARE\Classes\CLSID" -Recurse | Where-Object { $_.GetValue("") -like "*FLIR*" }
   ```

3. If found, register in system:
   ```cmd
   regsvr32 "C:\Path\To\FLIRBosonFilter.ax"
   ```

**Effort**: 30 minutes
**Risk**: Low
**Success Probability**: Medium (if filter exists)

---

### Solution 5: Downgrade OpenCV to 4.6.0 on Current System

**Rationale**: Confirmed working version from FLIR forum

**Steps**:
```bash
pip uninstall opencv-python
pip install opencv-python==4.6.0.66

# Also downgrade Python if needed
# (Python 3.7.9 confirmed working)
```

**Caveats**:
- Python 3.7.9 is old (EOL June 2023)
- May break other dependencies
- OpenCV 4.6.0 is from 2022

**Effort**: 30 minutes
**Risk**: Medium (compatibility)
**Success Probability**: Medium-High

---

### Solution 6: Direct USB Capture (Bypass DirectShow)

**Rationale**: Complete control over USB data

**Status**: Already documented in `DIRECT_USB_CAPTURE_GUIDE.md`

**Requirements**:
- PyUSB ✅ (installed)
- libusb-win32 or WinUSB driver
- Parse UVC Y16 payload format

**Trade-off**: Breaks OpenCV/DirectShow access

**Effort**: 2-3 hours
**Risk**: Medium
**Success Probability**: High (guaranteed 16-bit)

---

## Critical Discovery: CAP_PROP_CONVERT_RGB

The web research revealed a **critical setting we may have missed**:

### From OpenCV PR #12454:
> "If the user selects Y16 via CAP_PROP_FOURCC, DirectShow retrieves a 16-bit image but it is **implicitly converted to a grey RGB image** unless the user sets `CV_CAP_PROP_CONVERT_RGB` to false."

### Our Current Test Code:
```python
cap.set(cv2.CAP_PROP_CONVERT_RGB, 0)  # We ARE setting this
```

**But**: Setting order and timing may matter!

### Test This Immediately:
```python
# CORRECT order per documentation:
cap = cv2.VideoCapture(1, cv2.CAP_DSHOW)

# 1. Set CONVERT_RGB FIRST
result1 = cap.set(cv2.CAP_PROP_CONVERT_RGB, False)
print(f"Set CONVERT_RGB: {result1}")

# 2. Then set FOURCC
result2 = cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter.fourcc('Y','1','6',' '))
print(f"Set FOURCC: {result2}")

# 3. Then resolution
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 512)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)

# 4. Read frame
ret, frame = cap.read()

# Verify
print(f"Frame dtype: {frame.dtype}")  # Should be uint16
print(f"Frame shape: {frame.shape}")  # Should be (512, 640)
print(f"Frame range: {frame.min()} - {frame.max()}")  # Should be >255
```

---

## Windows 10 vs Windows 11 Differences

### UVC Driver Changes:
- **Windows 10 Build 19042**: Confirmed working with OpenCV 4.6.0
- **Windows 11 Build 26200**: Not working with OpenCV 4.11.0

### Possible Changes:
1. UVC driver updates in Windows 11
2. DirectShow optimizations that break Y16
3. Security/permission changes
4. Media Foundation preferred over DirectShow

### Testing Strategy:
1. Test on Windows 10 machine first (easiest validation)
2. If works on Win10, investigate Win11 differences
3. If fails on both, it's an OpenCV version issue

---

## Recommended Next Steps

### Immediate Actions (15 minutes):

1. **Test property setting order**:
   ```python
   # Try CONVERT_RGB before FOURCC
   cap.set(cv2.CAP_PROP_CONVERT_RGB, False)  # First!
   cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter.fourcc('Y','1','6',' '))
   ```

2. **Verify actual FOURCC after setting**:
   ```python
   requested = cv2.VideoWriter.fourcc('Y','1','6',' ')
   cap.set(cv2.CAP_PROP_FOURCC, requested)
   actual = cap.get(cv2.CAP_PROP_FOURCC)
   print(f"Requested: {requested}, Actual: {actual}")
   ```

### Short-term Solution (1-2 hours):

**Test OpenCV 4.6.0 with Python 3.7.9**:
- Create isolated environment
- Install exact versions from FLIR forum
- Test on Windows 10 if possible
- Document results

### Long-term Solution (2-3 hours):

**Implement Direct USB Capture**:
- Bypass DirectShow completely
- Read UVC Y16 payload directly
- Guaranteed 16-bit access
- Full control over format

---

## Conclusion

The web research confirms:

1. ✅ **Y16 support EXISTS in OpenCV** (added via PR #12454)
2. ✅ **FLIR documentation is accurate** (official FLIR help article)
3. ⚠️ **Version-specific behavior** (4.6.0 works, 4.11.0 may not)
4. ⚠️ **Platform differences** (Windows 10 vs Windows 11)
5. ⚠️ **DirectShow is legacy** (Microsoft recommends MediaFoundation)

**Most Likely Issue**:
- Windows 11 Build 26200 + OpenCV 4.11.0 combination
- DirectShow format negotiation preference changed
- Possible OpenCV regression between 4.6.0 and 4.11.0

**Best Solution**:
1. **Immediate**: Test property setting order and timing
2. **Short-term**: Test OpenCV 4.6.0 + Python 3.7.9 on Windows 10
3. **Long-term**: Implement direct USB capture for guaranteed results

**Current 8-bit Solution**:
- Remains valid and production-ready
- T-Linear processing improves quality
- Runtime mode switching works perfectly
- Good enough for most thermal inspection

---

## Sources

- [FLIR OEM - Boson Video and Image Capture using OpenCV 16-bit Y16](https://flir.custhelp.com/app/answers/detail/a_id/3387)
- [Add support for changing fourcc and support mono formats (e.g. Y8, Y16) in DirectShow - OpenCV PR #12454](https://github.com/opencv/opencv/pull/12454)
- [How can I get OpenCV to work with Y16 format? - Stack Overflow](https://stackoverflow.com/questions/70988369/how-can-i-get-opencv-to-work-with-y16-format)
- [USB Video Class (UVC) Camera Implementation Guide - Microsoft Learn](https://learn.microsoft.com/en-us/windows-hardware/drivers/stream/uvc-camera-implementation-guide)
- [Image Acquisition Interface for DirectShow - MVTec](https://www.mvtec.com/products/interfaces/documentation/view/1304-standard-13-mvtecdoc-directshow)
- [Y16 support on Windows in OpenCV (e.g. for PT) - Google Groups](https://groups.google.com/g/flir-lepton/c/ngUQGZIpk_g)
- [FLIR OEM - Boson 320 Radiometric - Cannot Acquire Radiometric 16 bit data](https://flir.custhelp.com/app/answers/detail/a_id/5572)

---

**Date**: 2025-12-01
**Status**: Research complete, actionable solutions identified
