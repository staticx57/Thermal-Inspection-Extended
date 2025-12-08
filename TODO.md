# Bug Fixes - Thermal Inspection Application

## Priority: CRITICAL (App Crashes)
- [ ] **Bug #6: Auto-ROI crashes application** ✅ FIXED & TESTED
    - [x] Reproduce crash - `AttributeError: 'last_thermal_frame' not found`
    - [x] Find crash location - `inspection_main.py:2175`
    - [x] Fix crash - Added `last_thermal_frame` attribute and update in main loop
    - [x] Fix method calls - `analyze_frame`, `detect_temperature_rois`, `detect_gradient_rois`
    - [x] Test Auto-ROI functionality - Works, no crash

## Priority: HIGH (Core Functionality Broken)
- [x] **Bug #13: 8-bit temperature estimation toggle not functional** ✅ FIXED
    - [x] Issue: "Enable 8-Bit Temperature Estimation" toggle in Radiometric panel cannot be enabled
    - [x] Fix: Enabled toggle programmatically in `RadiometricPanel.update_backend_status` when backend is active
    - [x] Verified: Toggle is now clickable and functional

- [/] **Bug #14: Isotherm controls not functional** (VERIFICATION FAILED)
    - [x] Issue: Buttons and controls in Analysis > Isotherm tab were not working
    - [x] Fix: Prioritized signal delivery and handlers
    - [x] Fix: Isotherm tab is now DISABLED in 8-bit mode (GUI robustness)
    - [/] Fix: Corrected backend logic for rendering overlay (Attempt 1: Raw-to-Celsius)
    - [ ] **DEBUG NOTE**: Verification failed - Highlighting not visible.
    - [ ] **DEBUG NOTE**: Root cause likely `thermal_frame` data mismatch (normalized vs raw).
    - [ ] Action: Retrieve raw radiometric frame inside `_apply_isotherm_overlay` instead of using processed frame.

## Priority: LOW (Missing Features)

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
- [ ] **Enhancement #2: MiDaS depth estimation**
    - Implement MiDaS model loading in `parallax_compensator.py`
    - Add MiDaS inference for depth estimation
    - Use depth estimation for parallax compensation when stereo not available
- [ ] **Enhancement #3: OpenCV fallback GUI**
    - Create simple OpenCV GUI for headless/lightweight operation (`inspection_main.py:968`)
    - Useful for embedded systems without Qt
- [ ] **Enhancement #5: Full Boson SDK implementation** (see `bosonsdkraw.txt`)
    - **DEPENDENCY**: Required for Enhancement #4 environmental compensation to affect displayed temperatures
    - AGC module: Mode, gain, gamma, DDE, headroom controls
    - Radiometry module: Full emissivity, atmospheric, flux controls ← *needed for Environmental panel to work*
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
- [ ] ** Enhancement #7: Performance Improvements
-   [ ] **Profiling and Benchmarking**
    - Use Python's cProfile or line_profiler to identify bottlenecks in the main processing loop.
    - Record FPS, CPU usage, and memory consumption for different camera resolutions and modes.
-   [ ] **Optimize Frame Processing Pipeline**
    - Move heavy image processing (e.g., palette application, anomaly detection) to a separate thread or process pool.
    - Leverage NumPy vectorized operations and avoid Python loops where possible.
    - Cache reusable intermediate results (e.g., resized frames) to reduce recomputation.
-   [ ] **GPU Acceleration**
    - Enable CUDA acceleration for thermal processing if a compatible GPU is detected.
    - Offload palette mapping and radiometric calculations to GPU using CuPy or Torch tensors.
-   [ ] **Reduce Camera Resolution Dynamically**
    - Implement adaptive resolution scaling based on current FPS target (e.g., drop to 640x480 when FPS < 30).
    - Allow user to select "Performance Mode" in settings to prioritize speed over detail.
-   [ ] **Threaded Capture Tuning**
    - Fine‑tune the DualThreadedCameraCapture buffers to minimize frame latency.
    - Experiment with different queue sizes and back‑pressure strategies.
-   [ ] **Memory Management**
    - Ensure frames are released promptly to avoid memory bloat.
    - Use weak references for large NumPy arrays when appropriate.
-   [ ] **Benchmark Reporting UI**
    - Add a simple overlay in the GUI showing real‑time FPS, processing time per stage, and GPU usage.
    - Provide a log export option for performance analysis.
-   [ ] **Testing and Validation**
    - Add automated tests that verify performance targets (e.g., ≥30 FPS at 1080p) on CI.
    - Validate that performance tweaks do not degrade detection accuracy.
- [ ] **Enhancement #8: Backend selector validation**
    - Prevent flirpy backend selection when no FLIR thermal camera (Boson/Lepton) is connected
    - Show warning dialog if user tries to select incompatible backend
    - Gray out unavailable backend options in GUI
- [x] **Enhancement #9: Windows XP Theme (Refinement)** ✅ COMPLETED
    - [x] Create Windows XP-inspired theme stylesheet
    - [x] Add classic Windows XP colors (Fisher-Price blue/green/silver)
    - [x] Wire theme to GUI settings and theme selector
    - [x] Test theme application across all panels
    - [x] Fix checkbox size inconsistency (Olive vs Silver) - Standardized to 20px
    - [x] Improve checkbox readability across all themes - Implemented high-contrast solid accents
    - [x] Improve Radio Button visibility - Standardized to 20px solid circles

- [ ] **Enhancement #11: RGB Camera Stability/Reconnect**
    - [ ] Implement exponential backoff for connection failures
    - [ ] Add "Camera Busy" state handling (orphaned process detection)
    - [ ] Silence repetitive logs in ThreadedCameraCapture

## Recently Completed Enhancements
- [x] **Enhancement #1: User-defined spot metering** ✅ COMPLETED
    - [x] Allow user to click anywhere on thermal image to get spot temperature
    - [x] Display crosshair/marker at measurement point
    - [x] Show temperature reading in real-time overlay
    - [x] Support multiple concurrent spot meters
    - [x] 3-tier fallback: 16-bit radiometric → 8-bit estimation → raw values
    - [x] Tested with 16-bit radiometric mode
    - [ ] Add spot meter data to export/logging (future enhancement)
- [x] **Enhancement #4: Radiometric and Environmental panel signal handlers** ✅ IMPLEMENTED
    - [x] Connect radiometric panel signals to main app (temperature unit, hot/cold spots, backend selector)
    - [x] Connect environmental compensation panel signals (emissivity, atmospheric temp/transmission)
    - [x] Implement 12 missing handler methods in GUI
    - [x] Implement 11 backend methods in InspectionApp
    - [ ] Full testing (temperature readings update, SDK integration)
    - **KNOWN LIMITATION**: Values stored but not applied to temperature display (requires Enhancement #5)

- [x] **Enhancement #10: Global Settings Tab Refactor** ✅ COMPLETED
    - [x] Create implementation plan
    - [x] Separate Fusion controls into dedicated `FusionPanel`
    - [x] Remove outdated ROI buttons from Settings
    - [x] Migrate `SettingsPanel` signals to `FusionPanel`
    - [x] Verify functionality

## Notes
- Start with CRITICAL bugs first (crashes)
- Then move to HIGH priority (broken core features)
- FFC control (Bug #1) is the most important non-crash bug
- Keep testing after each fix to avoid regressions

## Recently Closed / Verified Fixed
- [x] **Bug #16: Backend switch 16-bit→8-bit broken** ✅ FIXED
    - [x] Issue: Switching from flirpy (16-bit) back to opencv (8-bit) causes multiple issues
    - [x] **Root Cause 1**: Double switch trigger - backend_changed signal fires twice, causing race condition
    - [x] **Root Cause 2**: Wrong device ID preserved - uses device 0 instead of original device 2
    - [x] **Root Cause 3**: Frame size changes to RGB resolution (3840x2160) instead of thermal (640x512)
    - [x] **Fix**: Added mutex/flag to prevent double switch, preserve correct device ID, robust COM port detection
    - [x] **Fix**: Added frame size validation and restoration

- [x] **Bug #17: GUI Status Stuck "Switching..."** ✅ FIXED
    - [x] Issue: "Switching to..." label remains forever, overwriting success status
    - [x] **Root Cause**: Race condition - Label update happened AFTER blocking signal emit returned, overwriting success message
    - [x] **Fix**: Moved label update BEFORE signal emit and forced UI repaint

- [x] **Bug #1: Flirpy backend cannot control camera via COM port** ✅ FIXED
    - [x] Investigate FlirpyThermalBackend SDK connection
    - [x] Fix FFC trigger for flirpy backend - Uses `camera.do_ffc()` directly
    - [x] Test FFC trigger works ✅ CONFIRMED WORKING
    - [x] T-Linear radiometric mode validated (SDK command `sysctrlSetUsbVideoIR16Mode(2)`)
    - [x] Sequential access pattern verified (SDK -> configure -> flirpy for video)

- [x] **Bug #5: Sensor temperatures not implemented for 16-bit** ✅ FIXED
    - [x] Check if flirpy backend can read sensor temps - Uses `camera.get_fpa_temperature()`
    - [x] Implement sensor temperature reading - Fixed `get_fpa_temperature` and added `read_sensor_temperatures`
    - [x] Update GUI to display FPA/lens/shutter temps - Fixed `_update_sensor_temperatures` helper
    - [x] Test temperature readings display correctly

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

- [x] **Bug #8: Environmental tab crashes app** ✅ CLOSED (Settings have no effect)
    - [x] Get crash log from user - `AttributeError: 'ThermalInspectionFusion' object has no attribute 'boson_sdk'`
    - [x] Fix `set_emissivity` and other environmental methods - Updated to use `self.thermal_camera`
    - [x] DEBUG: Investigate why settings have no effect - Fixed backend to use `self.camera` instead of `self._sdk`
    - [x] Test Environmental tab controls - Verified no crash, but settings currently do not change image

- [x] **Bug #9: Auto-ROI excessive clutter/overlap** ✅ FIXED
    - [x] Issue: Multiple detectors (gradient, temp, motion) create overlapping boxes for same object
    - [x] Fix: Implemented Non-Maximum Suppression (NMS) with aggressive threshold (0.05)
    - [x] Fix: Added Containment Check to remove small boxes inside larger ones (>70%)
    - [x] Fix: Added priority system (Manual > Temp > Gradient > Motion > Edge)
    - [x] VERIFIED BY USER

- [x] **Bug #10: Auto-ROI metrics visibility** ✅ FIXED
    - [x] Verified: `get_all_rois(active_only=True)` returns ALL ROIs (auto + manual)
    - [x] All ROIs get thermal analysis (lines 1210-1250 in `inspection_main.py`)
    - [x] Fixed: Initialized `roi_radiometric_analyzer` at startup
    - [x] Fixed: Added fallback to standard stats if 16-bit analysis fails
    - [x] Fixed: ROI list now syncs correctly when clearing/deleting ROIs
    - [x] Fixed: Panel now clears correctly when last ROI is deleted
    - [x] VERIFIED BY USER

- [x] **Bug #11: Per-ROI palette selector disconnected** ✅ FIXED
    - [x] Issue: Selecting an ROI in GUI doesn't enable/sync the "ROI Palette" selector in Analysis > General
    - [x] Fix: Connected `InspectionAppWindow._on_roi_selected` to `AnalysisPanel.select_roi`
    - [x] Fix: Implemented `AnalysisPanel.select_roi` to sync list selection and combo box
    - [x] Fix: Connected `roi_palette_changed` signal app-side and `currentTextChanged` widget-side
    - [x] Fix: Prevented `update_rois` from clearing selection every frame (infinite loop fix)
    - [x] Fix: Fixed right-click context menu handler
    - [x] VERIFIED BY USER: Dropdown and Context Menu both working

- [x] **Bug #12: RGB camera detected but not utilized** ✅ FIXED
    - [x] Issue: RGB camera initialized successfully but video feed/fusion shows only thermal (or placeholder)
    - [x] Fix: Corrected frame synchronization and fusion processor inputs
    - [x] RGB camera now properly utilized in fusion mode

- [x] **Bug #15: Radiometric panel status not updated after backend change** ✅ FIXED
    - [x] Issue: Status labels didn't refresh after switching backends
    - [x] Fix: Implemented status method `RadiometricPanel.update_backend_status`
    - [x] Fix: Called update method in `InspectionAppWindow._on_backend_changed`
    - [x] Fix: Banner now turns Green/Gray correctly based on mode

- [x] **Bug #17: Backend Status Not Initialized at Startup** ✅ FIXED
    - [x] Root cause: GUI updates executed before Qt event loop fully initialized
    - [x] Solution: Implemented deferred GUI initialization in `_perform_deferred_initialization()`
    - [x] Added `update_connection_status()` method to `BosonControlPanel`
    - [x] Auto-connect SDK on startup (default `enable_sdk=True`)
    - [x] Fix: Backend status, Active Mode banner, Connection Status, and Camera Info all populate correctly at launch
    - [x] VERIFIED BY USER: All startup GUI elements now display correctly
```

## Enhancements

- [x] **Enhancement #10: Global Settings Tab Refactor** ✅ COMPLETED (2025-12-08)
    - [x] Created dedicated `FusionPanel` for all fusion-related controls (7 modes + edge/detail)
    - [x] Moved to top-level "🧬 Fusion" tab in main window
    - [x] Enhanced `SettingsPanel` with System Configuration:
        - [x] Backend selector (OpenCV 8-bit / Flirpy 16-bit radiometric)
        - [x] COM Port input for Boson SDK
        - [x] Storage paths (Snapshots / Recordings directories)
        - [x] Performance settings (Parallel processing toggle, Worker count)
    - [x] Cleaned up duplicate controls:
        - [x] Removed backend selector from `RadiometricPanel`
        - [x] Renamed `BosonSDKPanel` → `BosonControlPanel`
        - [x] Removed duplicate COM port selector from `BosonControlPanel`
    - [x] Updated signal connections and handler stubs in `InspectionAppWindow`
    - [x] VERIFIED: Application launches successfully with new UI structure
