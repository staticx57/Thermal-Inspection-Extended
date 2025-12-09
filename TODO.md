# Bug Fixes - Thermal Inspection Application

## Priority: CRITICAL (App Crashes)
*(No open critical bugs)*

## Priority: HIGH (Core Functionality Broken)
- [ ] **Bug #24: Spot meter marks don't translate correctly in PIP, RGB, and Side-by-Side modes**
    - [ ] Issue: When switching view modes (PIP/RGB/Side-by-Side), spot meter marks remain positioned incorrectly
    - [ ] Root Cause: `InspectionApp.set_view_mode()` (inspection_main.py:2592) doesn't call `overlay.set_view_mode()`
    - [ ] The overlay's `current_view_mode` stays stale, so `_transform_thermal_coords()` uses wrong coordinate transformation
    - [ ] Fix: Add `self.gui.video_widget.overlay.set_view_mode()` call in `set_view_mode()` method
    - [ ] Similar to how `set_fusion_mode()` (line 2481) and `set_fusion_priority()` (line 2505) already do this
    - [ ] Location: inspection_main.py:2592-2606
    - [ ] Impact: Spot meters appear in wrong positions in PIP/Side-by-Side, hidden in RGB-only mode


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
- [ ] **Enhancement #7: Performance improvements**
    - [ ] **Profiling and benchmarking**
        - Use Python's cProfile or line_profiler to identify bottlenecks in the main processing loop
        - Record FPS, CPU usage, and memory consumption for different camera resolutions and modes
    - [ ] **Optimize frame processing pipeline**
        - Move heavy image processing (e.g., palette application, anomaly detection) to a separate thread or process pool
        - Leverage NumPy vectorized operations and avoid Python loops where possible
        - Cache reusable intermediate results (e.g., resized frames) to reduce recomputation
    - [ ] **GPU acceleration**
        - Enable CUDA acceleration for thermal processing if a compatible GPU is detected
        - Offload palette mapping and radiometric calculations to GPU using CuPy or Torch tensors
    - [ ] **Reduce camera resolution dynamically**
        - Implement adaptive resolution scaling based on current FPS target (e.g., drop to 640x480 when FPS < 30)
        - Allow user to select "Performance Mode" in settings to prioritize speed over detail
    - [ ] **Threaded capture tuning**
        - Fine‑tune the DualThreadedCameraCapture buffers to minimize frame latency
        - Experiment with different queue sizes and back‑pressure strategies
    - [ ] **Memory management**
        - Ensure frames are released promptly to avoid memory bloat
        - Use weak references for large NumPy arrays when appropriate
    - [ ] **Benchmark reporting UI**
        - Add a simple overlay in the GUI showing real‑time FPS, processing time per stage, and GPU usage
        - Provide a log export option for performance analysis
    - [ ] **Testing and validation**
        - Add automated tests that verify performance targets (e.g., ≥30 FPS at 1080p) on CI
        - Validate that performance tweaks do not degrade detection accuracy
- [ ] **Enhancement #11: RGB camera stability/reconnect**
    - [ ] Implement exponential backoff for connection failures
    - [ ] Add "Camera Busy" state handling (orphaned process detection)
    - [ ] Silence repetitive logs in ThreadedCameraCapture
- [x] **Enhancement #12: Spot meter management and data export** ✅ COMPLETED
    - [x] **GUI Panel: Spot Meter Management (Analysis > General tab)** ✅ PHASE 1 COMPLETE
        - [x] Create dedicated `SpotMeterPanel` widget (similar to ROI panels)
        - [x] List view showing all active spot meters with:
            - [x] Spot meter ID/Label (e.g., "Spot #1", custom names)
            - [x] Current temperature reading
            - [x] Coordinates (x, y)
            - [/] Timestamp of last update (stored but not displayed)
            - [/] Color indicator/marker style (stored but not displayed)
        - [x] Selection and navigation:
            - [x] Click spot meter in list to highlight on video feed
            - [x] Click spot meter on video to add (select sync TODO)
            - [x] Keyboard navigation (Delete key, F2 for rename)
            - [x] Fix Spot Meter List Item readability on light themes (Use color icons)
    - [x] **New Dependency**: `pyqtgraph` added for History Graph
    - [x] Implement History Graph for Spot Meters
        - [x] **Snapshot Metadata**
        - [x] Modify `media_recorder.py:SnapshotManager.capture_snapshot` to accept `spot_meters` argument
        - [x] Implement serialization of spot data to JSON metadata in `capture_snapshot`
        - [x] Update `inspection_main.py:_take_snapshot` to retrieve spot meters from panel
    - [x] **Session Logging**
        - [x] Add periodic logging of spot meter values to `inspection_main.py` main loop
        - [x] Log spot meter values when taking a snapshot
    - [x] **Advanced Features (Phase 6)**
        - [x] Spot Meter Presets (Grid, Lines, Center)
        - [x] Compare Mode (ΔT)
        - [x] Alert Thresholds with visual feedback
        - [x] History Graph (Real-time plotting with `pyqtgraph`)
        - [x] Resolved layout/scaling issues with History Graph
        - [x] Export to CSV/JSON (including history) meter
            - [x] Lock position (prevent accidental movement)
        - [x] Statistics display:
            - [x] Min/Max/Average across all spot meters
            - [x] Delta between hottest and coldest spots
            - [x] Trend indicator (rising/falling temperature)
    - [x] **Data Export and Logging** ✅ PHASE 1 COMPLETE
        - [ ] Add spot meter data to snapshot metadata (JSON/XML)
        - [ ] Include spot meter readings in session logs
        - [x] Export spot meter history to CSV/JSON format
        - [x] Add timestamps for each spot meter reading (in SpotMeterData)
        - [x] SpotMeterLogger class for real-time logging
    - [x] **Advanced Features** ✅ COMPLETED
        - [x] Spot meter templates/presets (e.g., "9-point grid")
        - [x] Compare mode: Track temperature difference between two spots
        - [x] Alert thresholds: Notify when spot exceeds/drops below temperature
        - [x] Spot meter history graph (temperature over time per spot)

## Recently Completed Enhancements
- [x] **Enhancement #1: User-defined spot metering** ✅ COMPLETED
    - [x] Allow user to click anywhere on thermal image to get spot temperature
    - [x] Display crosshair/marker at measurement point
    - [x] Show temperature reading in real-time overlay
    - [x] Support multiple concurrent spot meters
    - [x] 3-tier fallback: 16-bit radiometric → 8-bit estimation → raw values
    - [x] Tested with 16-bit radiometric mode
- [x] **Enhancement #4: Radiometric and environmental panel signal handlers** ✅ IMPLEMENTED
    - [x] Connect radiometric panel signals to main app (temperature unit, hot/cold spots, backend selector)
    - [x] Connect environmental compensation panel signals (emissivity, atmospheric temp/transmission)
    - [x] Implement 12 missing handler methods in GUI
    - [x] Implement 11 backend methods in InspectionApp
    - [ ] Full testing (temperature readings update, SDK integration)
    - **KNOWN LIMITATION**: Values stored but not applied to temperature display (requires Enhancement #5)
- [x] **Enhancement #8: Backend selector validation** ✅ COMPLETED
    - [x] Validate Flirpy backend selection requires FLIR Boson/Lepton thermal camera
    - [x] Show warning dialog when selecting incompatible backend
    - [x] Automatically revert to OpenCV if user declines
    - [x] Distinguish FLIR Boson/Lepton (thermal) from FLIR Firefly (RGB)
    - [x] Allow user override to proceed despite warning
    - [x] Implemented in `SettingsPanel._on_backend_selection_changed()`
- [x] **Enhancement #9: Windows XP theme (refinement)** ✅ COMPLETED
    - [x] Create Windows XP-inspired theme stylesheet
    - [x] Add classic Windows XP colors (Fisher-Price blue/green/silver)
    - [x] Wire theme to GUI settings and theme selector
    - [x] Test theme application across all panels
    - [x] Fix checkbox size inconsistency (Olive vs Silver) - Standardized to 20px
    - [x] Improve checkbox readability across all themes - Implemented high-contrast solid accents
    - [x] Improve Radio Button visibility - Standardized to 20px solid circles
- [x] **Enhancement #13: ROI Management Polish** ✅ COMPLETED
    - [x] **Analysis Panel**: Added Multi-select support to ROI list
    - [x] **Analysis Panel**: Added "Delete Selected" and "Delete All" buttons
    - [x] **Aesthetics**: Removed large intrusive centered labels from video overlay (kept small top-left labels)
    - [x] **Bug Fix**: Fixed `PaletteManager` warning during ROI deletion (added cleanup)
    - [x] **Bug Fix**: Connected ROI list selection to video verification (highlighting)
    - [x] **Bug Fix**: Fixed ROI palette selector sync (Combo box <-> ROI)
    - [x] **Bug Fix**: Implemented robust, case-insensitive palette matching
- [x] **Enhancement #10: Global settings tab refactor** ✅ COMPLETED
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
- [x] **Bug #21: Spot meters positioned incorrectly in PIP mode** ✅ FIXED
    - [x] Issue: Spot markers positioned incorrectly in PIP mode
    - [x] Fix: Applied `_transform_thermal_coords()` in `InspectionOverlayWidget`
    - [x] Verified by user: Fixed in previous session
- [x] **Bug #20: Detection overlays positioned incorrectly in PIP/RGB modes** ✅ FIXED
    - [x] Issue: Hot/cold spots and anomaly markers at wrong coordinates in PIP mode
    - [x] Issue: Detection overlays showing when in RGB-only mode
    - [x] Fix: Added `set_view_mode()` to `InspectionOverlayWidget` for mode tracking
    - [x] Fix: Added `_transform_thermal_coords()` for PIP coordinate mapping
    - [x] Fix: Added `_should_draw_thermal_overlays()` to skip overlays in RGB mode
    - [x] Updated `set_fusion_mode()` and `set_fusion_priority()` to sync overlay widget
- [x] **Bug #6: Auto-ROI crashes application** ✅ FIXED & TESTED
    - [x] Reproduce crash - `AttributeError: 'last_thermal_frame' not found`
    - [x] Find crash location - `inspection_main.py:2175`
    - [x] Fix crash - Added `last_thermal_frame` attribute and update in main loop
    - [x] Fix method calls - `analyze_frame`, `detect_temperature_rois`, `detect_gradient_rois`
    - [x] Test Auto-ROI functionality - Works, no crash

- [x] **Bug #13: 8-bit temperature estimation toggle not functional** ✅ FIXED
    - [x] Issue: "Enable 8-Bit Temperature Estimation" toggle in Radiometric panel cannot be enabled
    - [x] Fix: Enabled toggle programmatically in `RadiometricPanel.update_backend_status` when backend is active
    - [x] Verified: Toggle is now clickable and functional

- [x] **Bug #14: Isotherm controls not functional** ✅ FIXED
    - [x] Issue: Buttons and controls in Analysis > Isotherm tab were not working
    - [x] Fix: Prioritized signal delivery and handlers
    - [x] Fix: Isotherm tab is now DISABLED in 8-bit mode (GUI robustness)
    - [x] Fix: Corrected backend logic for rendering overlay
    - [x] Fix: Retrieved raw radiometric frame inside `_apply_isotherm_overlay` instead of using processed frame
    - [x] Verified: Isotherm highlighting now visible and functional

- [x] **Bug #19: Radiometric status banner incorrect in 8-bit mode** ✅ FIXED
    - [x] Issue: Status banner shows gray "No temperature measurement" in 8-bit mode
    - [x] Expected: Orange banner showing "8-bit AGC" or "8-bit Estimation" based on toggle state
    - [x] 16-bit mode works correctly (shows green banner)
    - [x] Fix: Updated `RadiometricPanel.update_backend_status` to distinguish 8-bit modes
    - [x] Fix: Changed banner color to orange (#cc8800) for 8-bit modes
    - [x] Fix: Display correct mode text based on estimation toggle state
    - [x] Fix: Added `_on_8bit_estimation_toggled` handler to update banner in real-time

- [x] **Bug #16: Backend switch 16-bit→8-bit broken** ✅ FIXED
    - [x] Issue: Switching from flirpy (16-bit) back to opencv (8-bit) causes multiple issues
    - [x] **Root Cause 1**: Double switch trigger - backend_changed signal fires twice, causing race condition
    - [x] **Root Cause 2**: Wrong device ID preserved - uses device 0 instead of original device 2
    - [x] **Root Cause 3**: Frame size changes to RGB resolution (3840x2160) instead of thermal (640x512)
    - [x] **Fix**: Added mutex/flag to prevent double switch, preserve correct device ID, robust COM port detection
    - [x] **Fix**: Added frame size validation and restoration

- [x] **Bug #17: GUI status stuck "Switching..."** ✅ FIXED
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

- [x] **Bug #18: Backend status not initialized at startup** ✅ FIXED
    - [x] Root cause: GUI updates executed before Qt event loop fully initialized
    - [x] Solution: Implemented deferred GUI initialization in `_perform_deferred_initialization()`
    - [x] Added `update_connection_status()` method to `BosonControlPanel`
    - [x] Auto-connect SDK on startup (default `enable_sdk=True`)
    - [x] Fix: Backend status, Active Mode banner, Connection Status, and Camera Info all populate correctly at launch
        - [x] Performance settings (Parallel processing toggle, Worker count)
    - [x] Cleaned up duplicate controls:
        - [x] Removed backend selector from `RadiometricPanel`
        - [x] Renamed `BosonSDKPanel` → `BosonControlPanel`
        - [x] Removed duplicate COM port selector from `BosonControlPanel`
    - [x] Updated signal connections and handler stubs in `InspectionAppWindow`
    - [x] VERIFIED: Application launches successfully with new UI structure
