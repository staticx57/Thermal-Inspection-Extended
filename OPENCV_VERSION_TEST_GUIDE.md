# Testing OpenCV 4.6.0 on Windows 11 - Quick Guide

**Goal**: Determine if OpenCV version is the issue for Y16 capture, independent of Windows version

**Evidence**: FLIR forum user confirmed OpenCV 4.6.0 works (they used Windows 10, but let's test on Windows 11)

---

## Quick Setup (5 minutes)

### Option A: Automated Setup (Recommended)

Run the setup script:
```bash
python setup_opencv_4.6.0_test.py
```

This will:
1. Create virtual environment `venv_opencv460`
2. Install OpenCV 4.6.0.66
3. Install dependencies (pyserial, numpy)
4. Copy test scripts
5. Verify installation

### Option B: Manual Setup

```bash
# Create virtual environment
python -m venv venv_opencv460

# Activate it
venv_opencv460\Scripts\activate

# Install OpenCV 4.6.0
pip install opencv-python==4.6.0.66

# Install dependencies
pip install pyserial numpy

# Verify
python -c "import cv2; print(cv2.__version__)"
# Should show: 4.6.0
```

---

## Testing (2 minutes)

### Step 1: Activate Virtual Environment
```bash
venv_opencv460\Scripts\activate
```

You should see `(venv_opencv460)` in your prompt.

### Step 2: Verify OpenCV Version
```bash
python -c "import cv2; print(f'OpenCV: {cv2.__version__}')"
```

**Expected**: `OpenCV: 4.6.0`

### Step 3: Run Y16 Test
```bash
python test_convert_rgb_order.py
```

**What to look for**:
```
Test 1: Set CAP_PROP_CONVERT_RGB BEFORE CAP_PROP_FOURCC
  dtype: uint16  <-- SUCCESS!
  shape: (512, 640)  <-- SUCCESS!
  ✓ SUCCESS - Got 16-bit Y16!
```

---

## Interpreting Results

### Scenario 1: ✅ Y16 Works with OpenCV 4.6.0

**Output**:
```
Test X: [some configuration]
  dtype: uint16
  shape: (512, 640)
  16-bit? True
  Grayscale? True
  ✓ SUCCESS - Got 16-bit Y16!
```

**Conclusion**: OpenCV version WAS the issue!

**Next Steps**:
1. Note which test succeeded (configuration that works)
2. Choose one of these options:

   **Option A**: Keep using 4.6.0 in virtual environment
   ```bash
   # Always activate venv before running thermal app
   venv_opencv460\Scripts\activate
   python inspection_main.py
   ```

   **Option B**: Downgrade main environment to 4.6.0
   ```bash
   # Deactivate venv first
   deactivate

   # Uninstall current OpenCV
   pip uninstall opencv-python

   # Install 4.6.0
   pip install opencv-python==4.6.0.66
   ```

   **Option C**: Wait for OpenCV fix
   - Use 4.6.0 venv for now
   - Watch OpenCV releases
   - Test newer versions as they come out

---

### Scenario 2: ❌ Y16 Still Fails with OpenCV 4.6.0

**Output**:
```
All tests:
  dtype: uint8
  shape: (512, 640, 3)
  ✗ FAILED - Still 8-bit or color
```

**Conclusion**: OpenCV version is NOT the issue. It's Windows 11 DirectShow.

**Next Steps**:
1. The issue is Windows 11 DirectShow behavior
2. FLIR forum user had Windows 10 + OpenCV 4.6.0 working
3. Your options:

   **Option A**: Accept 8-bit solution (production ready!)
   - Current implementation works great
   - T-Linear processing active
   - Good quality for thermal inspection

   **Option B**: Implement Direct USB Capture
   - Bypass DirectShow completely
   - Guaranteed 16-bit on Windows 11
   - See `DIRECT_USB_CAPTURE_GUIDE.md`
   - Effort: 3 hours

   **Option C**: Test on Windows 10 machine (future)
   - Confirms Windows 11 is the limitation
   - May need Win10 for production if 16-bit required

---

## Comparison Matrix

| Configuration | OS | OpenCV | Result |
|---------------|-----|---------|--------|
| **Your Current** | Win11 26200 | 4.11.0 | ❌ 8-bit I420 |
| **FLIR Forum** | Win10 19042 | 4.6.0 | ✅ 16-bit Y16 |
| **Test #1** | Win11 26200 | 4.6.0 | ??? **TEST THIS** |
| **Future Test** | Win10 19042 | 4.11.0 | ??? (isolate OS) |

We're testing configuration **Test #1** to isolate whether it's:
- ✅ OpenCV version issue → Solved by 4.6.0
- ❌ Windows 11 issue → Need direct USB or Win10

---

## What This Tests

**Hypothesis**: OpenCV 4.11.0 has a DirectShow regression for Y16 format

**Test**: Install OpenCV 4.6.0 (confirmed working version)

**Variables**:
- ✅ Keep: Windows 11, Python 3.10, DirectShow backend
- ⬇️ Change: OpenCV 4.11.0 → 4.6.0

**If successful**: Problem is OpenCV version, use 4.6.0

**If fails**: Problem is Windows 11 DirectShow, need different approach

---

## After Testing

### If OpenCV 4.6.0 Works:

Update `flir_camera.py` with the successful property order from test results, then use OpenCV 4.6.0 going forward.

### If OpenCV 4.6.0 Fails:

You have these documented options:

1. **Use current 8-bit solution** (recommended)
   - Production ready
   - Runtime mode switching works
   - T-Linear improves quality
   - See `README_THERMAL_CAMERA.md`

2. **Implement Direct USB Capture** (~3 hours)
   - Bypass DirectShow
   - Guaranteed 16-bit
   - See `DIRECT_USB_CAPTURE_GUIDE.md`

3. **Wait for hardware access to Windows 10**
   - Test Win10 + OpenCV 4.11.0 (isolate OS variable)
   - Or use Win10 + OpenCV 4.6.0 (known working)

---

## Quick Command Reference

```bash
# Create and setup venv (once)
python setup_opencv_4.6.0_test.py

# Activate venv
venv_opencv460\Scripts\activate

# Check OpenCV version
python -c "import cv2; print(cv2.__version__)"

# Run Y16 test
python test_convert_rgb_order.py

# Run your thermal app in this venv
python inspection_main.py

# Deactivate when done
deactivate
```

---

## Troubleshooting

### Issue: "python not found" when activating venv
**Solution**: Use full path:
```bash
C:\Users\stati\Desktop\Projects\Thermal-Inspection\venv_opencv460\Scripts\activate
```

### Issue: pip install fails
**Solution**: Upgrade pip first:
```bash
python -m pip install --upgrade pip
pip install opencv-python==4.6.0.66
```

### Issue: "opencv-python 4.6.0.66 not found"
**Solution**: Try without patch version:
```bash
pip install opencv-python==4.6.0
```

### Issue: Camera not found in venv
**Solution**: Camera access should work the same. If issues:
```bash
# List available cameras
python -c "import cv2; print([i for i in range(5) if cv2.VideoCapture(i).isOpened()])"
```

---

## Expected Timeline

- **Setup venv**: 2 minutes (automated) or 5 minutes (manual)
- **Install packages**: 1-2 minutes (downloads)
- **Run test**: 30 seconds
- **Analyze results**: 1 minute
- **Total**: ~5 minutes

---

## Files You'll Need

All in current directory:
- ✅ `setup_opencv_4.6.0_test.py` - Automated setup script
- ✅ `test_convert_rgb_order.py` - Y16 test (already fixed)
- ✅ `flir_camera.py` - Camera interface
- ✅ `boson_sdk_wrapper.py` - SDK wrapper

---

## Success Criteria

**For this test to be successful**, we need:

1. Virtual environment created ✓
2. OpenCV 4.6.0 installed ✓
3. Test runs without errors ✓
4. **At least ONE test shows**:
   - `dtype: uint16`
   - `shape: (512, 640)`
   - `✓ SUCCESS - Got 16-bit Y16!`

If all 4 criteria met → **OpenCV 4.6.0 solves the problem!**

---

## Why This Approach?

**Advantages**:
- ✅ Fast (5 minutes)
- ✅ No OS change needed
- ✅ Non-destructive (uses venv)
- ✅ Easy to revert (just deactivate)
- ✅ Tests specific variable (OpenCV version)
- ✅ Low risk

**Comparison to alternatives**:
- Windows 10 test: Requires different machine
- Direct USB: 3 hours implementation
- Stay with 8-bit: No testing needed

**This is the optimal next step!**

---

## Next Steps After Test

Based on results, see:
- **If successful**: Update main environment or use venv
- **If failed**: See `NEXT_STEPS_16BIT_CAPTURE.md` for alternatives
- **Questions**: Check `README_THERMAL_CAMERA.md` troubleshooting

---

**Ready to test? Run**: `python setup_opencv_4.6.0_test.py`

Good luck! 🎯
