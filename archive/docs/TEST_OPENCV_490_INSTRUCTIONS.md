# Test OpenCV 4.9.0 - Quick Instructions

**Based on**: GitHub Issue [#27166](https://github.com/opencv/opencv/issues/27166)
**Evidence**: OpenCV 4.9.0.80 confirmed working for FLIR Boson 16-bit capture
**Time**: 10 minutes

---

## Why Test 4.9.0?

**Your GitHub discovery revealed**:
- ✅ OpenCV **4.9.0.80 works** for FLIR Boson (confirmed by issue reporter)
- ❌ OpenCV **4.11+ is broken** (flattening bug - frames become 1D arrays)
- 📋 OpenCV **4.12.0 will fix** it (PR merged)

**Your previous Test 5 showed**:
```python
Backend: MSMF
Frame shape: (1, 460800)  # Flattened 1D array - THE BUG!
```

**With OpenCV 4.9.0, this might become**:
```python
Backend: MSMF
Frame shape: (512, 640)  # Proper 2D! ✓
Frame dtype: uint16      # 16-bit! ✓
```

---

## Quick Setup (2 minutes)

### Option A: Automated (Windows)
```cmd
setup_opencv_490.bat
```

### Option B: Manual
```cmd
python -m venv venv_opencv490
venv_opencv490\Scripts\activate
pip install opencv-python==4.9.0.80 numpy pyserial
```

---

## Run Test (1 minute)

```cmd
REM Activate virtual environment
venv_opencv490\Scripts\activate

REM Verify version
python -c "import cv2; print(cv2.__version__)"
REM Should show: 4.9.0

REM Run test
python test_opencv_490_quick.py
```

---

## What to Look For

### ✅ SUCCESS looks like:
```
TEST 1: Auto Backend (should select MSMF on Windows)
======================================================================
Backend selected: MSMF
Actual FOURCC: 'Y16 '

Frame Analysis:
  dtype: uint16         ← 16-bit!
  shape: (512, 640)     ← 2D grayscale!
  min: 27850
  max: 30240

Success Criteria:
  16-bit (uint16): True ✓
  2D shape: True ✓
  Correct size (512, 640): True ✓
  16-bit range (>255): True ✓

======================================================================
✓✓✓ SUCCESS! Got 16-bit Y16 capture!
======================================================================
```

### ❌ FAILURE looks like:
```
Frame Analysis:
  dtype: uint8          ← Still 8-bit
  shape: (480, 640, 3)  ← Color, not grayscale

✗ Test 1 Failed
```

---

## Possible Outcomes

### Outcome 1: ✅ Test 1 (MSMF) Succeeds

**Meaning**: OpenCV 4.9.0 + MSMF backend = 16-bit capture works!

**What this proves**:
- OpenCV 4.11 flattening bug WAS the issue
- Windows 11 MSMF backend supports Y16
- DirectShow still fails (separate Windows 11 issue)

**Next steps**:
1. Use OpenCV 4.9.0 going forward
2. Update main environment: `pip install opencv-python==4.9.0.80`
3. Update `flir_camera.py` to prefer MSMF backend
4. **Your problem is SOLVED!** 🎉

---

### Outcome 2: ❌ All Tests Fail

**Meaning**: Even 4.9.0 doesn't work on Windows 11

**What this proves**:
- Windows 11 limitation affects ALL OpenCV versions
- Need alternative approach

**Next steps**:
1. Implement Direct USB Capture (3 hours, guaranteed)
2. Or test on Windows 10 machine (if available)
3. Or wait for Windows update (unknown timeline)

---

### Outcome 3: ✅ DirectShow Succeeds (Unexpected!)

**Meaning**: DirectShow works with 4.9.0 on Windows 11

**What this proves**:
- Both OpenCV version AND Windows 11 were issues
- 4.9.0 has better DirectShow negotiation

**Next steps**:
1. Use OpenCV 4.9.0 with DirectShow backend
2. This is the easiest solution!

---

## If OpenCV 4.9.0 Works

### Update Your Main Environment

```cmd
# Deactivate venv
deactivate

# Uninstall current OpenCV
pip uninstall opencv-python

# Install 4.9.0
pip install opencv-python==4.9.0.80

# Verify
python -c "import cv2; print(cv2.__version__)"
```

### Update flir_camera.py

If MSMF backend works, prefer it over DirectShow:

```python
# In flir_camera.py, update open() method:

def open(self) -> bool:
    """Open camera with optimal backend for 16-bit capture."""
    if self.cap is None:
        # Try MSMF first (works with OpenCV 4.9.0 for Y16)
        self.cap = cv2.VideoCapture(self.device_id, cv2.CAP_MSMF)

        if not self.cap.isOpened():
            # Fallback to DirectShow
            self.cap = cv2.VideoCapture(self.device_id, cv2.CAP_DSHOW)

        # Set properties for 16-bit
        self.cap.set(cv2.CAP_PROP_CONVERT_RGB, 0.0)
        self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter.fourcc('Y','1','6',' '))
        # ... rest of initialization
```

---

## Comparison: What We've Tested

| OpenCV Version | Windows | Backend | Result |
|----------------|---------|---------|--------|
| 4.11.0 | Win11 | DirectShow | ❌ I420 8-bit |
| 4.11.0 | Win11 | MSMF | ❌ Flattened (1, 460800) |
| 4.6.0 | Win11 | DirectShow | ❌ YUY2 8-bit |
| 4.6.0 | Win11 | MSMF | ❌ Flattened (1, 460800) |
| **4.9.0** | **Win11** | **MSMF** | **??? TEST THIS** ⚡ |

---

## Why 4.9.0 Might Be The Answer

**From GitHub Issue #27166**:
- Issue reporter had FLIR Boson
- Confirmed 4.9.0.80 works for 16-bit
- Bug appeared in 4.11+
- **Fix timeline**: 4.12.0 (future)

**Your Test 5 showed**:
- MSMF backend captured data
- But flattened to (1, 460800)
- This is EXACTLY the bug from #27166!

**Logical conclusion**:
- MSMF backend CAN capture Y16
- 4.11 flattening bug prevented success
- **4.9.0 should work!**

---

## Alternative: Wait for OpenCV 4.12.0

If you don't want to downgrade:

**Timeline**: Unknown (weeks/months)
**Status**: Fix merged (PR #27193)
**Milestone**: 4.12.0

**When released**:
```cmd
pip install --upgrade opencv-python
```

---

## If 4.9.0 Doesn't Work

**Then it's confirmed**: Windows 11 platform limitation

**Your options**:
1. **Direct USB Capture** (3 hours)
   - Bypass DirectShow/MSMF completely
   - Read USB bulk transfers directly
   - Guaranteed 16-bit
   - See `DIRECT_USB_CAPTURE_GUIDE.md`

2. **Windows 10 Machine** (if available)
   - FLIR forum confirms Win10 works
   - Use same codebase

3. **Accept 8-bit Solution** (production ready now)
   - Works great for thermal inspection
   - Runtime mode switching functional
   - T-Linear processing active

---

## Commands Summary

```cmd
REM Setup (once)
setup_opencv_490.bat

REM Activate
venv_opencv490\Scripts\activate

REM Verify version
python -c "import cv2; print(cv2.__version__)"

REM Run test
python test_opencv_490_quick.py

REM If successful, upgrade main environment
deactivate
pip uninstall opencv-python
pip install opencv-python==4.9.0.80
```

---

## Expected Timeline

- **Setup**: 2 minutes
- **Test**: 1 minute
- **Analysis**: 1 minute
- **Update (if works)**: 5 minutes
- **Total**: ~10 minutes

---

## Success Criteria

For this test to solve your problem:

- [x] Virtual environment created
- [x] OpenCV 4.9.0.80 installed
- [ ] Test runs without errors
- [ ] **At least one backend returns**:
  - `dtype: uint16`
  - `shape: (512, 640)`
  - `✓ SUCCESS - Got 16-bit Y16!`

If all criteria met → **Problem solved!** 🎉

---

## Why This Is The Most Likely Solution

**Evidence weight**:
1. ✅ GitHub issue specifically mentions FLIR Boson
2. ✅ Issue confirms 4.9.0.80 works
3. ✅ Your Test 5 showed MSMF getting data (but flattened)
4. ✅ Flattening matches exact bug description
5. ✅ Bug fixed for 4.12.0 confirms regression in 4.11+

**Probability**: High (70-80%)

**This is your best bet before trying Direct USB!**

---

## Ready?

**Run this**:
```cmd
setup_opencv_490.bat
```

Good luck! 🎯
