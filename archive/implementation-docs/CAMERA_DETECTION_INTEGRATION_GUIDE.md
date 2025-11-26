# Camera Detection Integration Guide

## Summary of Improvements

### 1. Enhanced Camera Detection System ✅ COMPLETE
- **File**: `camera_detector.py`
- **Features**:
  - Spinnaker camera detection (FLIR Firefly RGB)
  - UVC camera detection (Boson thermal, generic USB, built-in webcams)
  - Frame-based thermal detection (640x512, low saturation analysis)
  - Separate priority systems for thermal and RGB (coequal importance)

### 2. Maximum Resolution Support ✅ COMPLETE
- **Files**: `rgb_camera_firefly.py`, `rgb_camera_uvc.py`, `camera_factory.py`
- **Features**:
  - Auto-detect and use maximum available resolution
  - Preserves detail before downstream resizing
  - Firefly: Query max width/height from Spinnaker nodemap
  - UVC: Use camera's default (max) resolution

### 3. Priority System ✅ COMPLETE
**Thermal Cameras (0-99):**
- Priority 0: FLIR Boson
- Priority 1: Generic thermal

**RGB Cameras (0-99):**
- Priority 0: FLIR Firefly (Spinnaker) - Global shutter, best
- Priority 1: External USB UVC
- Priority 2: Built-in webcam

## Integration into inspection_main.py

### Current Camera Initialization
Currently uses:
```python
# Thermal (line ~357)
self.thermal_camera = FLIRBosonCamera(
    device_id=getattr(self.args, 'thermal_device', 0),
    ...
)

# RGB (line ~470)
self.rgb_camera = create_rgb_camera(
    resolution=(640, 480),
    camera_index=rgb_device_id,
    ...
)
```

### Recommended Integration Approach

**Option 1: Enhanced Auto-Detection (Recommended)**
Add new method to `ThermalInspectionFusion` class:

```python
def _init_cameras_auto(self):
    """
    Initialize cameras using enhanced detection system

    Returns:
        (thermal_success, rgb_success) tuple
    """
    import time

    logger.info("="*70)
    logger.info("ENHANCED CAMERA AUTO-DETECTION")
    logger.info("="*70)

    # Detect all cameras
    thermal_cam_info = CameraDetector.find_thermal_camera()
    rgb_cam_info = CameraDetector.find_rgb_camera()

    thermal_success = False
    rgb_success = False

    # Initialize thermal camera
    if thermal_cam_info:
        logger.info(f"Initializing thermal: {thermal_cam_info.name}")

        enable_sdk = getattr(self.args, 'enable_boson_sdk', False)
        com_port = getattr(self.args, 'boson_com_port', 'COM6')

        self.thermal_camera = FLIRBosonCamera(
            device_id=thermal_cam_info.device_id,
            resolution=thermal_cam_info.resolution,
            enable_sdk=enable_sdk,
            com_port=com_port
        )

        if self.thermal_camera.open():
            logger.info("[OK] Thermal camera connected")
            self.thermal_connected = True
            thermal_success = True

    # Small delay between camera initializations
    time.sleep(0.5)

    # Initialize RGB camera
    if rgb_cam_info:
        logger.info(f"Initializing RGB: {rgb_cam_info.name}")

        if rgb_cam_info.interface == 'spinnaker':
            # FLIR Firefly via Spinnaker
            from rgb_camera_firefly import RGBCameraFirefly

            self.rgb_camera = RGBCameraFirefly(
                camera_index=rgb_cam_info.spinnaker_index,
                resolution=(0, 0),  # Use max resolution
                fps=30,
                pixel_format="BGR8"
            )
        else:
            # UVC camera
            self.rgb_camera = create_rgb_camera(
                resolution=(0, 0),  # Use max resolution
                fps=30,
                camera_type="uvc",
                camera_index=rgb_cam_info.device_id,
                thermal_device_id=thermal_cam_info.device_id if thermal_cam_info else None
            )

        if self.rgb_camera.open():
            logger.info("[OK] RGB camera connected")
            self.rgb_available = True
            rgb_success = True

    return (thermal_success, rgb_success)
```

**Usage in `__init__` or startup:**
```python
# Replace existing camera initialization with:
thermal_ok, rgb_ok = self._init_cameras_auto()

if not thermal_ok:
    logger.warning("Thermal camera not detected - using placeholder")
if not rgb_ok:
    logger.warning("RGB camera not detected - thermal-only mode")
```

### Manual Override Support (Fail-Safe)

Keep existing manual device ID specification as fallback:
```python
def _init_cameras_manual(self, thermal_device=None, rgb_device=None):
    """
    Initialize cameras with manual device IDs (fail-safe)
    """
    # Existing initialization code...
```

### GUI Integration

Add to Developer Panel or Settings:
- Button: "Re-detect Cameras" → calls `_init_cameras_auto()`
- Dropdown: Manual camera selection (fallback)
- Display: Detected camera info (model, serial, resolution)

## Testing

Test script created: `test_camera_detection.py`

**Run test:**
```bash
python test_camera_detection.py
```

**Expected output:**
```
[OK] Thermal camera: FLIR Boson 640x512 (Camera 0) [FLIR Boson - BEST]
     (Thermal priority 0)
[OK] RGB camera: Firefly FFY-U3-16S2C-DL [Firefly (Spinnaker) - BEST]
     (RGB priority 0 - graded separately from thermal)
```

## Benefits

1. **Robust Detection**: Proper identification of Firefly vs Boson
2. **No Conflicts**: Spinnaker cameras use separate index space
3. **Best Quality**: Uses highest resolution, prioritizes global shutter
4. **Fail-Safe**: Falls back to manual assignment if auto-detection fails
5. **User-Friendly**: Clear logging of what was detected and why

## Next Steps

1. Add `_init_cameras_auto()` method to `ThermalInspectionFusion` class
2. Update startup to try auto-detection first
3. Add GUI controls for manual override
4. Test with both cameras connected
5. Test with only thermal or only RGB connected
6. Test with neither camera connected (placeholder mode)
