# Bug Fixes - Thermal Inspection Application

## Priority: CRITICAL (App Crashes)
- [x] **Bug #6: Auto-ROI crashes application** ✅ FIXED & TESTED
    - [x] Reproduce crash - `AttributeError: 'last_thermal_frame' not found`
    - [x] Find crash location - `inspection_main.py:2175`
    - [x] Fix crash - Added `last_thermal_frame` attribute and update in main loop
    - [x] Fix method calls - `analyze_frame`, `detect_temperature_rois`, `detect_gradient_rois`
    - [x] Test Auto-ROI functionality - Works, no crash

- [x] **Bug #8: Environmental tab crashes app** ✅ CLOSED (Settings have no effect)
    - [x] Get crash log from user - `AttributeError: 'ThermalInspectionFusion' object has no attribute 'boson_sdk'`
    - [x] Fix `set_emissivity` and other environmental methods - Updated to use `self.thermal_camera`
    - [x] DEBUG: Investigate why settings have no effect - Fixed backend to use `self.camera` instead of `self._sdk`
    - [x] Test Environmental tab controls - Verified no crash, but settings currently do not change image

## Priority: HIGH (Core Functionality Broken)
- [/] **Bug #1: Flirpy backend cannot control camera via COM port**
    - [ ] Investigate FlirpyThermalBackend SDK connection
    - [x] Fix FFC trigger for flirpy backend - Uses `camera.do_ffc()` directly
    - [x] Test FFC trigger works ✅ CONFIRMED WORKING
    - [ ] TODO: Verify full SDK (gain mode, sensor temps, color LUT, emissivity, etc.)
    - [ ] Test other SDK commands work via flirpy
    - [ ] Document which SDK methods are available

- [x] **Bug #7: Per-ROI tab not populated when drawing ROI** ✅ FIXED
    - [x] Check ROI drawing signal/slot connection
    - [x] Verify ROI data is being computed - Added `roi_temp_stats` to result
    - [x] Fix Per-ROI panel update mechanism - Added `update_roi_data` call in main loop
    - [x] DEBUG: Investigate why data isn't displaying - Found `result['rois']` was empty during analysis
    - [x] Fix data flow order in `inspection_main.py`
    - [x] Fix "General" Analysis tab ROI list not populating
    - [x] DEBUG: Found `FlirpyThermalBackend` missing `get_last_raw_frame` - Added method
    - [x] Fix ROI palette combo box not syncing with selection
    - [x] VERIFIED BY USER

## Priority: LOW (Missing Features)
- [x] **Bug #5: Sensor temperatures not implemented for 16-bit** ✅ FIXED
    - [x] Check if flirpy backend can read sensor temps - Uses `camera.get_fpa_temperature()`
    - [x] Implement sensor temperature reading - Fixed `get_fpa_temperature` and added `read_sensor_temperatures`
    - [x] Update GUI to display FPA/lens/shutter temps - Fixed `_update_sensor_temperatures` helper
    - [x] Test temperature readings display correctly

- [?] **Bug #9: Auto-ROI draws opaque black boxes (minor)**
    - [ ] Investigated: No filled rectangles (thickness=-1) in codebase
    - [ ] `draw_rois` only draws outlines, not filled boxes
    - [ ] NEEDS VERIFICATION: May be misreported or already fixed

- [x] **Bug #10: Auto-ROI metrics visibility** ✅ FIXED
    - [x] Verified: `get_all_rois(active_only=True)` returns ALL ROIs (auto + manual)
    - [x] All ROIs get thermal analysis (lines 1210-1250 in `inspection_main.py`)
    - [x] Fixed: Initialized `roi_radiometric_analyzer` at startup
    - [x] Fixed: Added fallback to standard stats if 16-bit analysis fails
    - [x] Fixed: ROI list now syncs correctly when clearing/deleting ROIs
    - [x] Fixed: Panel now clears correctly when last ROI is deleted
    - [x] VERIFIED BY USER

- [ ] **Bug #11: Per-ROI palette selector disconnected** ⏳ READY FOR VERIFICATION
    - [ ] Issue: Selecting an ROI in GUI doesn't enable/sync the "ROI Palette" selector in Analysis > General
    - [x] Fix: Connected `InspectionAppWindow._on_roi_selected` to `AnalysisPanel.select_roi`
    - [x] Fix: Implemented `AnalysisPanel.select_roi` to sync list selection and combo box
    - [ ] NEEDS USER VERIFICATION: Confirm clicking ROI in video updates palette combo

## Cleanup: Orphaned / Ghost Code
- [ ] Remove `_create_roi_temp_placeholder` in `inspection_gui_qt.py` (line ~6103, replaced by `ROITemperaturePanel`)
- [ ] Remove `BosonSDKPanel` in `inspection_gui_qt.py` (lines 4486-4615, replaced by `BosonControlPanel`)
- [ ] AlertOverlayWidget - Does not exist (was already removed/never existed)
- [ ] Remove/Implement placeholders in `inspection_gui_qt.py`:
    - [ ] `_on_spotmeter_enabled_changed` - Keep as placeholder (see Enhancement #1)
    - [ ] `_on_spotmeter_mode_changed` - Keep as placeholder (see Enhancement #1)
    - [x] `_on_sensor_temps_requested` - Now calls `app.read_sensor_temperatures()`
    - [ ] `placeholder_frames.py` - Actively used by `inspection_main.py` (keep)
- [x] **Maintenance: Clean up folder of outdated docs and test scripts**
    - [x] Identify and move/delete obsolete .md docs
    - [x] Archive old test scripts
    - [x] Update README if necessary

## Enhancements: Future Features
- [ ] **Enhancement #1: User-defined spot metering**
    - Allow user to click anywhere on thermal image to get spot temperature
    - Display crosshair/marker at measurement point
    - Show temperature reading in real-time overlay
    - Support multiple concurrent spot meters
    - Add spot meter data to export/logging
- [ ] **Enhancement #2: MiDaS depth estimation**
    - Implement MiDaS model loading in `parallax_compensator.py`
    - Add MiDaS inference for depth estimation
    - Use depth estimation for parallax compensation when stereo not available
- [ ] **Enhancement #3: OpenCV fallback GUI**
    - Create simple OpenCV GUI for headless/lightweight operation (`inspection_main.py:968`)
    - Useful for embedded systems without Qt
- [ ] **Enhancement #4: Radiometric panel signal handlers**
    - Connect radiometric panel signals to main app (`inspection_main.py:1021`)
    - Emissivity adjustment per-material
    - Atmospheric compensation controls
- [ ] **Enhancement #5: Full Boson SDK implementation** (see `bosonsdkraw.txt`)
    - AGC module: Mode, gain, gamma, DDE, headroom controls
    - Radiometry module: Full emissivity, atmospheric, flux controls
    - Isotherm module: Temperature-based highlighting
    - Spotmeter module: Hardware spot temperature measurement
    - Telemetry module: Frame-embedded data
    - Color LUT module: Full palette control
    - System info: Serial number, firmware, sensor info
- [ ] **Enhancement #6: Full Firefly SDK implementation** (see `archive/logs/flirsdkraw.txt`)
    - Full Spinnaker GenICam controls
    - Auto-exposure, gain, white balance
    - Trigger modes and frame timing
    - Color correction and HDR
    - Temperature monitoring

## Notes
- Start with CRITICAL bugs first (crashes)
- Then move to HIGH priority (broken core features)
- FFC control (Bug #1) is the most important non-crash bug
- Keep testing after each fix to avoid regressions
