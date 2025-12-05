# Backend Switching - Complete Implementation Checklist

## Flow Analysis

### Step 1: User clicks "Apply Backend Change" in GUI
**File**: `radiometric_panel.py`
**Method**: `_on_apply_backend_change()`

### Step 2: Signal emitted
**Signal**: `backend_changed.emit(mode)`
**Mode value**: 'opencv', 'flirpy', or 'usb'

### Step 3: GUI receives signal
**File**: `inspection_gui_qt.py`
**Method**: `_on_backend_changed(mode)`
**Line**: 2146

### Step 4: Set camera mode via SDK
**Lines**: 2166-2205
**Action**: Call `sdk.set_usb_video_ir16_mode()`

### Step 5: Switch backend
**Line**: 2210
**Action**: Call `app.switch_thermal_backend(mode)`

### Step 6: Backend switching logic
**File**: `inspection_main.py`
**Method**: `switch_thermal_backend(backend_type)`
**Line**: 3505

#### Step 6a: Pause main loop
**Line**: 3523
**Action**: Set `self.reconfiguring = True`

#### Step 6b: Stop threaded capture
**Lines**: 3528-3531
**Action**: `self.threaded_capture.stop()`

#### Step 6c: Release current camera
**Lines**: 3534-3537
**Action**: `self.thermal_camera.release()`

#### Step 6d: Auto-detect device
**Lines**: 3544-3553

#### Step 6e: Create new backend
**Lines**: 3556-3562
**Action**: Call `create_thermal_backend()`

#### Step 6f: Open new camera
**Lines**: 3565-3577

#### Step 6g: Detect radiometric mode
**Lines**: 3580-3583

#### Step 6h: Reset analyzer & processor
**Lines**: 3585-3593
**Action**: Reset background model and motion detection

#### Step 6i: Enable radiometric
**Lines**: 3596-3597 (MISSING!)

#### Step 6j: Update GUI
**Lines**: 3600-3608

#### Step 6k: Restart threaded capture
**Lines**: 3611-3615

#### Step 6l: Update args
**Line**: 3618

### Step 7: Update GUI status
**File**: `inspection_gui_qt.py`
**Lines**: 2217-2220
**Action**: Update radiometric panel

## Issues Found

### Issue 1: Missing `enable_radiometric` method
**Location**: Line 3596-3597 calls method that doesn't exist on FlirpyThermalBackend
**Fix needed**: Add method or remove call

### Issue 2: Wrong parameter type to update_backend_status
**Location**: Line 2218 (FIXED)
**Was**: Passing string `mode`
**Now**: Passing dict `backend_info`

### Issue 3: ThreadedCameraCapture compatibility
**Potential issue**: FlirpyThermalBackend may not be fully compatible
**Need to verify**: All required methods exist

## Next Steps

1. Check if FlirpyThermalBackend needs `enable_radiometric()` method
2. Verify ThreadedCameraCapture works with all backends
3. Test complete flow end-to-end
