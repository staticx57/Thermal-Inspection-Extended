# flirpy Backend - Remaining Issues

## Status: Backend switching signal connected ✓, but additional issues found

---

## Issues to Fix

### 1. ❌ Boson SDK Panel - Camera Info Not Populating

**Location**: `Cameras Tab > Boson SDK Panel`

**Problem**: Camera info (serial number, firmware, etc.) is not displayed in the Boson SDK panel

**Root Cause**: The code at `inspection_gui_qt.py:5730-5735` expects `thermal_camera.get_camera_info()` to return camera information, but:
- The FLIR camera backend may not be exposing this properly
- The camera info retrieval happens during connection, not continuously updated

**Code Location**:
```python
# inspection_gui_qt.py:5730-5735
if hasattr(self.app.thermal_camera, 'get_camera_info'):
    info = self.app.thermal_camera.get_camera_info()
    if info:
        self.boson_panel.set_status(f"SN: {info.serial_number}")
        self.boson_panel.update_camera_info(info)
```

**Fix Needed**:
1. Verify `flir_camera.py` has a proper `get_camera_info()` method
2. Ensure the method returns camera information from the SDK
3. Make sure the GUI calls this method when the Boson panel is displayed
4. Add periodic refresh or update on connect

---

### 2. ❌ Radiometric Settings Panel Not Synced

**Location**: `Settings Tab > Radiometric Settings`

**Problem**: There appears to be a separate radiometric settings panel in the Settings tab that is not synced with the backend switching functionality

**Details Needed**:
- What radiometric settings are shown in the Settings tab?
- How should they interact with the backend selection in Analysis > Radiometric Panel?
- Should backend selection be shown in both places?

**Fix Needed**:
1. Find the radiometric settings panel in the Settings tab
2. Sync it with the new backend switching functionality
3. Ensure changes in one place update the other
4. Decide if backend selection should be in both places or just one

---

### 3. ⚠️ Backend Switching Implementation Incomplete

**Status**: Signal connected ✓, handler created ✓, but needs testing

**What Was Fixed**:
- Added signal connection: `self.radiometric_panel_general.backend_changed.connect(self._on_backend_changed)` (line 2033)
- Created handler: `_on_backend_changed(mode)` (lines 2146-2174)

**Still Needs**:
- Test that backend switching actually works
- Verify camera releases properly before switching
- Ensure SDK connection is maintained during switch
- Update radiometric panel status after successful switch

---

## Priority Order

1. **HIGH**: Fix backend switching (test and debug)
2. **MEDIUM**: Fix Boson SDK panel camera info display
3. **MEDIUM**: Sync radiometric settings in Settings tab
4. **LOW**: Verify long-term stability of flirpy backend

---

## Testing Checklist

### Backend Switching Test:
- [ ] Launch app with SDK: `python inspection_main.py --enable-boson-sdk --boson-com-port COM7`
- [ ] Go to Analysis > Radiometric Panel
- [ ] Select "16-bit flirpy (Best of Both)"
- [ ] Click "Apply Backend Change"
- [ ] Verify backend switches successfully
- [ ] Verify camera continues capturing frames
- [ ] Verify frame rate is correct (~9 FPS for radiometric)
- [ ] Verify temperature values are correct

### Camera Info Display Test:
- [ ] Launch app with SDK enabled
- [ ] Go to Cameras > Boson SDK Panel
- [ ] Verify camera info is displayed (serial number, firmware, etc.)
- [ ] Click "Connect" if not auto-connected
- [ ] Verify camera info updates after connection

### Radiometric Settings Sync Test:
- [ ] Find radiometric settings in Settings tab
- [ ] Change backend in Analysis > Radiometric Panel
- [ ] Verify Settings tab reflects the change
- [ ] Change settings in Settings tab
- [ ] Verify Analysis > Radiometric Panel reflects the change

---

## Next Steps

1. Restart application with camera connected
2. Test backend switching to see actual error/behavior
3. Navigate to Cameras > Boson panel to see what info is missing
4. Navigate to Settings > Radiometric to see what needs syncing
5. Fix issues one by one based on observations

---

## Files Modified So Far

### `flirpy_thermal_backend.py`
- Line 80: Fixed to use `Boson()` (no port parameter) instead of `port="DISABLED"`

### `inspection_gui_qt.py`
- Line 2033: Added `backend_changed` signal connection
- Lines 2146-2174: Added `_on_backend_changed()` handler method

---

## Additional Notes

- The flirpy backend itself works correctly (tested standalone)
- TRUE 16-bit Y16 capture is confirmed working
- SDK connection via COM7 is confirmed working
- The issues are all GUI integration related, not backend functionality

---

**Date**: 2025-12-03
**Status**: In Progress - Need user testing to identify remaining GUI issues
