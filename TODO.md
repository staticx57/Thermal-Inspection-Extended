# TODO — Handoff Notes

Last updated: 2026-09-23. Read this first if picking up a new session on `camera-plugin-architecture-and-perf-fixes` — it points at everything else.

## Status

Two features are **code-complete, tested (625 passed / 8 skipped / 0 failed), reviewed, and merged** into `camera-plugin-architecture-and-perf-fixes` (local commits, not yet pushed to origin):

1. **Spot-meter distance** — Spot Meter reports distance-to-point whenever a RealSense camera is the active RGB source, any view mode.
2. **3D Mapping Fusion** — new persistent-world 3D mapping mode: scan once with a RealSense camera (Open3D RGB-D odometry), freeze the geometry, then track the camera and re-texture live without rebuilding. New "3D Mapping" tab.

Full design spec: `docs/superpowers/specs/2026-09-22-3d-mapping-fusion-design.md`
Full implementation plans (task-by-task, what was built and why): `docs/superpowers/plans/2026-09-22-spot-meter-distance.md`, `docs/superpowers/plans/2026-09-22-3d-mapping-fusion.md`

Both went through a subagent-driven build with per-task review AND a final whole-plan review. The 3D Mapping Fusion final review caught real, serious problems before merge — the mode was completely unreachable from the UI, the point-cloud viewport was permanently hidden, and texture sampling used the wrong resolution (silently wrong colors). All fixed and re-verified. Don't assume "merged" means "lightly checked" — it went through two review passes.

## 3D Mapping Fusion - status as of 2026-09-30 (NOT yet user-validated)

Open3D 0.20.0 is now installed and the feature was exercised against the real library and a real L515. Findings / changes:
- Pose direction bug fixed (`pose = kf_pose @ inv(T_odometry)`); synthetic ground-truth tests in `tests/unit/test_mapping_geometry.py`.
- Open3D must be imported BEFORE PyQt6/torch on Windows (else "DLL load failed ... pybind"): preloaded in `thermal_inspection/__main__.py` and `tests/conftest.py`.
- Live tracking is multi-scale robust ICP with plausibility gating and background FPFH+RANSAC re-localization (also used after Load).
- Scan tracking uses key-frame odometry (no drift while the camera is still) and runs on a background worker (`WorldMapper.submit_frame`, newest-frame-wins), because RGB-D odometry costs ~1 s at 640x480 regardless of iteration count/threads. A cheap held-still check skips it when nothing moved (thresholds `_static_color_diff`/`_static_depth_diff`, set from real L515 data: auto-exposure drifts colour by 10+ levels, so colour is mean-normalized).
- Real L515, static camera: scan tick 1.6 ms when still, no drift, Save -> Reset -> Load -> re-localizes in ~2 s (fitness ~0.99), live tick ~215 ms.
- Unverified on hardware: moving-camera scans, forced tracking loss, quality thresholds (0.3/0.1, scan floor 0.2), Thermal/RGB/Blend textures, existing 3D Fusion unaffected.
- Per-point temperatures (`processing/world_thermal.py`): latest/peak/baseline per world point, hotspots, change vs a loaded world, CSV export, sidecar `<ply>.thermal.npz`. Recorded only from an aligned, genuinely radiometric Y16 frame. Tested on the synthetic scene only - no thermal camera has been connected yet.
- IMU (`processing/imu_prior.py`, `RGBCameraRealSense.get_imu_sample`): gyro rotation head-start for odometry/ICP + gravity veto. Works on L515 (BMI085) and D435i/D455/D456 (BMI055 or BMI085; datasheet 337029-017 tables 4-24/4-25: all +-4 g, +-1000 deg/s). No RealSense camera does ICP in hardware. Synthetic fast pan: without gyro a 9 deg/frame pan silently ends 14 deg off, with gyro 0.3 deg. Verified live on the L515 only while held still.
- T265 would add on-board visual-inertial SLAM pose (a far stronger prior than the gyro) but needs a rigid mount + extrinsic calibration, is discontinued, and recent pyrealsense2 releases dropped it. Not built.
- Moving-camera behaviour on hardware is still UNTESTED: run `python tools/mapping_motion_test.py`.
- 3D world viewer in the main view (plan: docs/superpowers/plans/2026-09-30-3d-world-viewer.md): click-to-probe, two-point measure, hotspot snapping (toggle), markers, camera marker, legend, RGB inset. Smoke-tested live on the L515; needs the user's hands-on validation.
- ROI Manager + spot meter polish (2026-09-30): see README 'ROI Manager tab'. Built and unit-tested (991 tests), exercised in the real app (lock/hide/duplicate/delete/rename in sync with controller + overlay); NOT yet validated by the user, and the temperature columns/alerts have only been fed synthetic data (no thermal camera connected).
- Full unit suite: 991 passed.

## Pending: two manual live-hardware verification checklists

Neither feature should be considered actually done until these run against real hardware — this project's own standing practice (see memory: `feedback_verify_live_state_before_concluding`, and the L515 pyrealsense2 integration itself was held to the same bar).

### Spot-meter distance (L515 or D455 connected)
- [ ] Place a spot meter, confirm the list shows `@ X.XXm` alongside temperature
- [ ] Move closer/farther, confirm distance updates sensibly
- [ ] Switch to a non-Fusion view mode, confirm distance still shows
- [ ] Disconnect RealSense, confirm distance silently omits, temperature-only behavior unaffected

### 3D Mapping Fusion (L515 or D455, open3d installed per above)
- [ ] Switch to the new "3D Mapping" tab, click Start Mapping, pan the camera around a scene, click Finish
- [ ] Move the camera after Finish — confirm tracking quality updates sensibly and the world re-textures without the geometry changing shape
- [ ] Force tracking loss (fast motion / covered lens) — confirm it shows Lost and doesn't corrupt the model
- [ ] Try Thermal / RGB / Blend texture sources
- [ ] Save, restart the app, Load — confirm tracking resumes correctly
- [ ] Confirm the existing (unrelated) 3D Fusion mode is completely unaffected

## Polish backlog (found 2026-09-30 by git history, file size, imports and test mentions)

Ranked by value. "Untested" means no test mentions the module, not that it is broken; dates are last-commit dates. Items marked (headless) can be done and tested without any camera attached.

### 1. Radiometric accuracy (highest value) - headless
Files: `gui/panels/radiometric_panel.py` (813 lines), `processing/radiometric_converter.py` (815), `utils/radiometric_calibration.py` (374), `core/radiometric_controller.py` (450). Last touched 08-31/09-01; almost no tests; this is where earlier unit/disconnect bugs lived.
- [ ] Audit emissivity / atmospheric / reflected-temperature / distance correction math against the Boson/Tau docs; add tests with synthetic Y16 frames
- [ ] Unit handling end to end (C/F/K/raw): every readout path follows the app setting; nothing hard-codes C
- [ ] Calibration points UI: validation, clear errors, persistence across restarts
- [ ] Show which correction is active and whether readings are calibrated, estimated, or raw (never fake calibration)

### 2. Cameras tab and device handling
Files: `gui/camera_control/camera_manager_dialog.py` (626), the Firefly/Lepton/UVC/GigE/RealSense control panels, `cameras/camera_detector.py` (1262), `camera_factory.py` (479), `camera_monitor.py`. Essentially no tests.
- [ ] Surface device errors in the UI (open timeouts like the L515 hang, busy device, missing driver) instead of only logs; console logging is WARNING-only today
- [ ] Reconnect / hot-plug and a "why isn't my camera working" readout (what was tried, what failed)
- [ ] A hung or zombie owner process holding a camera should be reported, not silent
- [ ] Fake-backend tests for detector/factory/monitor (headless)

### 3. Fusion and Parallax panels
Files: `gui/panels/fusion_panel.py` (727), `gui/panels/parallax_panel.py` (861), `gui/panels/fusion_3d_panel.py`.
- [ ] 3D Fusion silently falls back to RGB-only unless parallax is enabled AND method=realsense AND target=thermal: show the reason in the UI (3D Mapping already does this for texture; see memory `project_3d_fusion_silent_gate`)
- [ ] Parallax: clearer alignment diagnostics, remember settings, test the settings round trip (headless)

### 4. Smaller UI pieces - DONE 2026-10-01 (built + unit-tested + smoke-tested in the real app; not yet validated by the user)
- [x] `gui/widgets/colorbar_widget.py`: was never fed a palette or range by anything outside the overlay, so it never showed. Now wired (palette + the 1st-99th percentile range the palette actually stretches over, in the app's unit), redrawn from a cached image with round tick values, sized from the font and video area, hidden in views where it means nothing (RGB, side-by-side, PIP, 3D), relative cold/hot ends for non-radiometric cameras, and a "Show Temperature Scale" checkbox (Analysis > General)
- [x] `gui/panels/anomaly_widgets.py` (manual threshold): raw mode was capped at 0-16383 but Y16 radiometric counts are Kelvin x 100 (~29,000-31,000), so it could not express a room-temperature threshold. Added a real **Temperature** mode in the app's unit (sent to the detector as Y16), raw range now 0-65535, modes fall back to percentage without a radiometric source. The automatic `AnomalyWidget` half of this file was not reviewed
- [x] `gui/panels/environmental_compensation_panel.py`: presets loaded one step low (`int(0.29*100)` = 28), ambient temperature was hard-coded to degC (now follows the unit, always emits degC), the "Estimated Accuracy +-0.5-1.0 C" figure was an invented heuristic (replaced by a plain-language settings check that makes no absolute-accuracy claim), `set_emissivity` left a stale preset name, and the panel greyed out with no explanation on non-radiometric sources
- [x] `gui/panels/grid_overlay_panel.py`: "Custom (64x51) for Boson" assumed a 640x512 sensor; replaced by 3x3 / 4x4 / 10x10 cell presets computed from the real thermal resolution, plus a cell-count readout
- [x] `gui/panels/thermal_analysis.py` kept a dead second ROI list, and clicking an ROI on the video called its `select_roi()` which read a list that no longer exists (it raised). Dead handlers removed; the click now selects the row in the ROI Manager
- [ ] Still open from this group: the automatic `AnomalyWidget` (type toggles, fade/percentile controls) has not been audited; the colorbar has not been seen on a real radiometric camera

### 5. Persistence and dead/duplicate code - headless
- [ ] `utils/settings_manager.py` defaults to a relative `config.json`: confirm where settings land depending on the working directory; make the location explicit
- [ ] `utils/preset_manager.py` (300, 0 tests): validation and round-trip tests
- [ ] `utils/measurement_points.py` (oldest file, 2025-12) overlaps spot meters: consolidate or delete
- [ ] `utils/spot_meter_exporter.py` (342, 0 tests) vs the spot panel's own CSV/JSON fallback exporters: keep one
- [ ] `gui/widgets/multi_row_tabwidget.py` is imported by one module and may be superseded by `PagedTabWidget`: confirm and remove
- [ ] Tests dir has stale-looking `__pycache__` for Python 3.10: ignore in git if tracked

### 6. Back-end robustness (hard to test without hardware; use fakes)
- [ ] `sdk/boson_sdk_wrapper.py` (49 broad `except`s), `sdk/flirpy_thermal_backend.py` (28), `cameras/flir_camera.py` (21): errors are swallowed; narrow them and report failures
- [ ] `cameras/rgb_camera_firefly.py` (1089), `rgb_camera_uvc.py` (541): same review

### 7. The monolith
- [ ] `app.py` is ~3000 lines with ~39 TODO/placeholder markers; split the per-frame loop into view-mode handlers (3D Mapping branch is the template: it is already self-contained)
- [ ] Narrow broad `except Exception` in `main_window.py` / `app.py` (17 each)

### Also still open from the 3D Mapping / ROI work
- [ ] Moving-camera validation on the L515: `python tools/mapping_motion_test.py`
- [ ] Real thermal temperatures into the 3D world and ROI alerts (needs a connected, aligned, radiometric thermal camera)
- [ ] Combined spot-meter + ROI comparison table (spot compare and ROI compare exist separately)

## Also pending

- Push/merge-to-main decisions are the user's: the branch `camera-plugin-architecture-and-perf-fixes` was pushed to origin on 2026-09-30 at the user's request; merging to `main` has NOT been done.
