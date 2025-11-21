# Spinnaker SDK Detection Issue - Diagnosis & Solution

## Problem Summary
Your FLIR Firefly camera requires the **Spinnaker SDK** and **PySpin** (Python wrapper) to function, but they are currently not installed on your system.

## Diagnosis Results

### ✗ Issue 1: PySpin Module Not Found
```
ModuleNotFoundError: No module named 'PySpin'
```
- **Status**: PySpin is NOT installed
- **Impact**: Python cannot communicate with FLIR cameras

### ✗ Issue 2: Spinnaker SDK Not Installed
- **Location checked**: `C:\Program Files\FLIR Systems\Spinnaker`
- **Status**: SDK not found
- **Impact**: Camera drivers and libraries are missing

## How the Application Tries to Access the Camera

The application uses this flow:
1. `main.py` → calls `create_rgb_camera()` from `camera_factory.py`
2. `camera_factory.py` → tries to import `PySpin` from `rgb_camera_firefly.py`
3. `rgb_camera_firefly.py:35` → attempts `import PySpin`
4. **If import fails** → `PYSPIN_AVAILABLE = False` → Falls back to generic UVC cameras

Currently, the application is falling back to UVC cameras because PySpin is not available.

## Solution: Install Spinnaker SDK + PySpin

### Step 1: Download Spinnaker SDK

1. Go to FLIR's official download page:
   **https://www.flir.com/products/spinnaker-sdk/**

2. Click "Download" and create a free account if you don't have one

3. Download the **Full Installation** package for Windows:
   - **Recommended**: `SpinnakerSDK_FULL_3.2.0.62_x64.exe` (or latest version)
   - Make sure you select the **FULL** version (not just runtime)

### Step 2: Install Spinnaker SDK

1. Run the downloaded `.exe` file as Administrator

2. **IMPORTANT**: Choose **"Full Installation"** when prompted
   - This includes:
     - Spinnaker SDK libraries
     - PySpin Python wrapper
     - Camera drivers
     - GenICam/GenTL transport layers

3. Accept the license agreement

4. Complete the installation (may take 5-10 minutes)

### Step 3: Install PySpin for Python

After installing Spinnaker SDK:

1. Open Command Prompt as Administrator

2. Navigate to the PySpin wheel location:
   ```cmd
   cd "C:\Program Files\FLIR Systems\Spinnaker\bin64\vs2015"
   ```

3. Find the `.whl` file matching your Python version:
   - You're using **Python 3.12**
   - Look for: `spinnaker_python-3.2.0.62-cp312-cp312-win_amd64.whl`
   - (The exact name may vary based on SDK version)

4. Install the wheel:
   ```cmd
   pip install spinnaker_python-3.2.0.62-cp312-cp312-win_amd64.whl
   ```

   **Note**: If there's no exact match for Python 3.12, you might need to:
   - Use Python 3.11 instead (PySpin wheels are typically available for 3.7-3.11)
   - OR wait for FLIR to release Python 3.12 compatible wheels

### Step 4: Verify Installation

Run this command to verify PySpin is installed:
```cmd
python -c "import PySpin; print('PySpin installed successfully!'); print('Version:', PySpin.System.GetInstance().GetLibraryVersion())"
```

If successful, you should see:
```
PySpin installed successfully!
Version: <version info>
```

### Step 5: Test Camera Detection

Run the test script:
```cmd
python rgb_camera_firefly.py
```

This will:
- Detect connected FLIR Firefly cameras
- Display camera model and serial number
- Capture and display test frames

## Python Version Compatibility Warning

**Important**: PySpin wheels are typically built for specific Python versions. As of January 2025:
- Python 3.7, 3.8, 3.9, 3.10, 3.11: Usually supported
- Python 3.12: May not have official wheels yet

**If you're using Python 3.12 and encounter issues:**

### Option A: Use Python 3.11 (Recommended)
1. Install Python 3.11 from python.org
2. Create a virtual environment with Python 3.11:
   ```cmd
   py -3.11 -m venv venv311
   venv311\Scripts\activate
   pip install -r requirements.txt
   ```
3. Install PySpin in this environment

### Option B: Check for Updated Wheels
- Visit FLIR's website to see if Python 3.12 wheels are available
- Or build PySpin from source (advanced)

## Alternative: Use Generic UVC Camera (Temporary Workaround)

While you're setting up Spinnaker, the application will automatically fall back to generic UVC cameras:

```cmd
python main.py --rgb-camera-type uvc
```

This will work with any standard USB webcam, but:
- ❌ No global shutter (rolling shutter artifacts possible)
- ❌ Less control over camera settings
- ✓ Works immediately without SDK

## Checking Installation Status

After installation, run this quick check:

```python
# Quick test script
python -c "
try:
    import PySpin
    system = PySpin.System.GetInstance()
    cam_list = system.GetCameras()
    print(f'PySpin OK - Found {cam_list.GetSize()} FLIR camera(s)')
    cam_list.Clear()
    system.ReleaseInstance()
except ImportError:
    print('ERROR: PySpin not installed')
except Exception as e:
    print(f'ERROR: {e}')
"
```

## Common Issues & Solutions

### Issue: "No FLIR cameras detected" (even after installing PySpin)

**Possible causes**:
1. **USB connection**: Use USB 3.0 port (blue port)
2. **Camera power**: Some Firefly cameras need external power
3. **Driver issues**: Check Device Manager → Imaging Devices
4. **USB driver**: May need to reinstall camera drivers

**Solution**:
```cmd
# In Device Manager, right-click camera → Update driver → Browse
# Point to: C:\Program Files\FLIR Systems\Spinnaker\driver
```

### Issue: "PySpin version mismatch"

**Solution**: Make sure Spinnaker SDK version matches PySpin wheel version

### Issue: "Access denied" or "Camera in use"

**Solution**:
- Close any other applications using the camera
- Restart computer
- Run Python script as Administrator

## Next Steps After Installation

1. ✓ Install Spinnaker SDK (Full Installation)
2. ✓ Install PySpin wheel for your Python version
3. ✓ Verify with: `python -c "import PySpin"`
4. ✓ Connect FLIR Firefly camera via USB 3.0
5. ✓ Test with: `python rgb_camera_firefly.py`
6. ✓ Run main application: `python main.py`

## Additional Resources

- **Spinnaker SDK Documentation**: Included with SDK installation
- **PySpin API Reference**: `C:\Program Files\FLIR Systems\Spinnaker\doc`
- **FLIR Support**: https://www.flir.com/support/
- **Project Documentation**: See `CROSS_PLATFORM.md` in this repository

## Summary

**The SDK is installed**: ❌ NO - SDK not found
**PySpin is installed**: ❌ NO - Module not found
**Camera can be detected**: ❌ NO - Cannot detect without SDK

**Action required**: Install Spinnaker SDK + PySpin following steps above

Once installed, the application will automatically detect and use your FLIR Firefly camera with its superior global shutter technology!
