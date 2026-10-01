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

## New-machine readiness (audited 2026-10-01)

**Verified here:** a clean `git clone` of the committed code passes all 1073 unit tests and launches, running 40 s without errors, creating its own `config.json` + `camera_registry.json`; the same launch with torch, open3d, pyrealsense2, PyOpenGL, flirpy and scipy all absent also runs (warnings only). Optional hardware/vendor pieces (Boson vendor SDK, PySpin, VPI) just warn.

**NOT verified (could not be tested from this machine):**
- A from-scratch `pip install -r requirements.txt` (the sandbox has no PyPI access). Requirements are mostly lower bounds with no lock file, so a fresh install gets whatever is newest that day.
- Linux / Jetson / macOS. The Linux scripts pass a syntax check only; macOS has no camera backend (DirectShow / V4L2 only).
- Python versions other than 3.12.10.

**Machine-specific assumptions that remain:**
- [ ] No lock file: add `requirements-lock.txt` (or constraints) from the working environment (numpy 2.2.6, opencv 4.12.0, PyQt6 6.10.0, pyqtgraph 0.14.0, scipy 1.16.3, flirpy 0.3.0, setuptools 80.9.0) so installs are reproducible
- [x] `pygrabber` / `comtypes` are Windows-only: now carry `sys_platform == "win32"` markers
- [ ] Runtime data is written relative to the current directory (`config.json`, `camera_registry.json`, `recordings/`, `snapshots/`, `world_maps/`, `roi_sets/`): launching from another folder silently starts with fresh settings. Move to a per-user data dir (e.g. `platformdirs`) or anchor to the repo root
- [ ] `--boson-com-port` defaults to `COM7` (a Windows port from the dev machine); `app.py` and `flir_camera.py` hard-code it. Auto-detect, or default per platform (`/dev/ttyACM0` on Linux)
- [ ] `--device` defaults to `cuda`: confirm the fallback message on machines with no GPU/torch is clear
- [ ] The L515 needs a from-source pyrealsense2 build (`scripts/install_realsense_l515.ps1`, Windows only); D400 cameras use the pip package
- [ ] A first-run "doctor" (`python -m thermal_inspection --check-env`) listing which optional features are available (torch/CUDA, open3d, OpenGL, RealSense, flirpy, PySpin) and why, instead of scattered warnings

## Repository sprawl (audited 2026-10-01)

Done: `.gitignore` expanded (transient test/coverage/tool caches, `world_maps/`, `roi_sets/`, `*.ply`, `*.thermal.npz`, editor leftovers) and an `.egg-info/` rule that matched nothing fixed; ~90 stale Python 3.10 `.pyc` files, the per-user `settings_editor_theme.json` and `.claude/settings.local.json` untracked (files kept locally); `tests/unit/test_repo_hygiene.py` guards all of it. **Their content is still in git history** (the settings file contains local paths and a broad command allowlist): scrubbing it needs a history rewrite (git filter-repo) and a force-push: the user's decision.

Done 2026-10-01:
- [x] Removed 7 modules with no reference anywhere (~1,300 lines) and their re-exports: `gui/widgets/multi_row_tabwidget.py` (imported PyQt5, so it could never load), `utils/logging_setup.py` (replaced by `cli.configure_logging`), `utils/platform_detection.py`, `utils/performance_monitor.py`, `utils/placeholder_frames.py`, `gui/camera_control/boson_sdk_panel.py`, `utils/measurement_points.py`. Full suite still passes and the app starts clean
- [x] `Media/`: the 12 unreferenced concept images moved to `Media/concepts/` with tool-friendly names and a README (original names recorded); the 3 live assets stay in `Media/`
- [x] `sdk/__init__.py` exported `USBFSLPTransport`, a name that does not exist (class is `USBFslpTransport`), so its `try/except ImportError` silently hid the module forever: fixed
- [x] `pytest.ini`: `-v` and live `log_cli` removed (logs now show only for failures)
- [x] Verified NOT dead, kept: `themes/_instrument.py` (builds the Classic IBM/HP themes), `utils/preset_manager.py` (documented API, not exposed in the UI), `cameras/camera_calibration.py` (the producer of the homography JSON that `--calibration-file` reads, but it has no launcher/entry point), `sdk/usb_fslp_transport.py` (experimental Boson-over-USB protocol, now importable, not wired in or tested), `gui/widgets/spot_alert_dialog.py`

Open (your decision):
- [x] `cameras/camera_calibration.py` (2026-10-01): NOT superseded; now has a real CLI (`python -m thermal_inspection.cameras.camera_calibration --thermal t.png --rgb r.png --distance METERS [--method features|checkerboard] [--edges] [--preview check.png]`), 16-bit input, RMS/inlier quality gate (refuses spurious fits), and records `working_distance_m` in the file.
- [x] Parallax and the homography DID double-count: a homography calibrated at Z0 already holds f*b/Z0 px of parallax, so with both on the measured error was a constant ~-5.4 px (rig: f=256 px, b=50 mm, Z0=2 m) at every depth. `FusionProcessor.set_parallax_composition` / `effective_calibration_matrix` (driven per frame by `App._sync_alignment_composition`) remove it: residual <0.7 px at 0.5-5 m for both correction targets (`tests/unit/test_alignment_composition.py`). Old calibration files without a distance only get a one-time warning (the shift is unknowable); re-create them with `--distance`.
- [x] Calibration brought up to parity with parallax (2026-10-01): `--calibration-file` was a dead flag (parsed, never passed on) - now wired via `AppConfig.calibration_file`; new `core/alignment_calibration.py` manager (capture from live feeds, load/save/clear, on/off, persisted in config, rescales to other resolutions); new Cameras > Camera Calibration tab (Register / Parallax / Rig pages, shared scene distance, Measure from depth camera, alignment overlay, Check alignment residual); the radiometric tab is now "Temp Calibration". Manual shift/zoom/auto-align/auto-crop/overlay moved there from the Parallax tab (they are static camera-position corrections, not parallax).
- [ ] Parallax tab still holds Camera Geometry (baseline, lens focal/sensor): inputs to the parallax math but also camera-position data; candidate to move to Alignment as a shared "rig geometry" group. (Radiometric panel also offers single/two-point offset calibration in its 8-bit estimation group, a second temperature-calibration mechanism next to the reference-point curve tab: decide whether to merge.)
- [ ] Not verified: real hardware (rig is equal-FOV, pure translation; scale/rotation/perspective and different-FOV cameras are not simulated); manual shift / FOV zoom on top of a homography is only warned about, not composed
- [ ] flirpy (checked 2026-10-01): not archived or deprecated. 0.3.0 (Sep 2021, what runs here) -> 0.6.2 (Apr 2026) after a 4.5-year gap; 0.6.2 needs Python >=3.10, dropped `pkg_resources` (then `setuptools<81` is unneeded) and requires `opencv-python-headless` (conflicts with `opencv-python`). `BosonNative` subclasses flirpy's `Boson` and relies on its PRIVATE `_send_packet` / `_decode_packet` (still present in 0.6.2 with the same `Boson(port, baudrate, loglevel)` constructor) so an upgrade is probably compatible but must be tested on the radiometric Boson before changing the pin
- [x] `utils/preset_manager.py` deleted (2026-10-01): a leftover from the ADAS project (its preset fields were `show_boxes`, `audio_enabled`, `frame_skip`), never wired in. README updated; there are no app-level settings presets
- [ ] `sdk/usb_fslp_transport.py`: Boson-over-USB protocol (no COM port), never wired in or tested; keep only if a COM-port-free Boson is wanted. flirpy is alive, so there is no urgency
- [ ] `gui/widgets/spot_alert_dialog.py` defines a second `SpotMeterAlert` that duplicates the one in the spot-meter panel: keep one
- [ ] Local disk only (untracked and ignored, not a repo problem): `recordings/` ~118 MB, `scratch/` ~27 MB, `snapshots/` ~3 MB
- [ ] `CHANGELOG.md` (151 KB) stops at 3.7.0 (2026-09-11); this session's work has no entry and `__version__` is still 3.7.0. Held back until you have validated the work (a changelog entry would claim it works)

## Also pending

- Push/merge-to-main decisions are the user's: the branch `camera-plugin-architecture-and-perf-fixes` was pushed to origin on 2026-09-30 at the user's request; merging to `main` has NOT been done.

## 2026-10-02 remote-work pass (radiometric, rig, portability, sprawl)
- [x] Radiometric: `TLinearConverter` default mapped 0..65535 counts onto -40..550 C (read ~224 C for a 20 C scene on the OpenCV Boson path, and the Temperature Range box changed readings); now Kelvin x 0.01 like the flirpy backend and app.py. `method="range"` keeps the old map as an explicit estimate. LUT conversion vectorised (was quadratic). Reference fits refuse degenerate inputs; polynomial extrapolation bounded; stats gain `fit_rmse`.
- [x] The Temp Calibration curve was NEVER applied to any reading (the "Enable Calibration Correction" box did nothing). Now applied via `App._correct_temperature_c` to analyzer stats/spots, spot meters, contour labels and the 3D thermal layer. Not applied to: ROI std-dev (scales with slope), recorded/exported raw data, the 8-bit estimate path.
- [x] Temperature-calibration mechanisms reduced: removed the unused controller calibration points, `RadiometricCalibration` CSV class. Remaining: reference-point curve (16-bit, Temp Calibration tab) and single/two-point offset for the 8-bit ESTIMATE (relabelled "Offset").
- [ ] `apply_environmental_compensation` uses a Stefan-Boltzmann T^4 model over all wavelengths; real cameras are band-limited (Planck over 7.5-13.5 um). Fine for small corrections, an approximation for large ones: either document in the UI or implement the band-limited form with the camera's calibration constants.
- [x] Rig 2 (`tests/unit/alignment_rig2.py`): different focal length (1.5x), resolution and roll. ORB found 7 inliers on it; calibration now uses SIFT + ratio test (>1000 on edges). With a calibration at 2 m and composed parallax, residual <1.5 px at 0.7-4 m for both correction targets; resolution rescale verified. Auto fine-tune on a calibrated view measures only the residual shift (no scale search, no geometry-formula fallback).
- [x] Portability: `utils/paths.py` (THERMAL_INSPECTION_HOME > cwd dev mode > per-user data dir) for config.json, alignment_calibration.json, recordings, snapshots; OS-aware default serial port. Remaining Windows-isms: `flir_camera.py`/`flirpy_sdk_bridge.py`/`flirpy_thermal_backend.py` still default to COM7 internally (config overrides win).
- [x] Sprawl: removed `gui/widgets/spot_alert_dialog.py` (stale duplicate of the richer dialog in spot_meter_panel) and `sdk/usb_fslp_transport.py` (experimental, unwired, untested; recoverable from git history). FSLP implementations: boson_serial's remains the in-repo one, flirpy has its own.
- [x] flirpy 0.6.2 (what a fresh install resolves to) tested in a clean venv built from requirements.txt: Boson API identical to 0.3.0 plus gain-mode/external-sync methods (our gain methods are now redundant but harmless); `check_flirpy_compatibility()` passes; `tests/unit/test_flirpy_wire.py` (BosonNative on flirpy's real framing against a simulated Boson, incl. marker-byte stuffing) passes on 0.3.0 and 0.6.2. The clean venv also showed: a fresh install runs on OpenCV 5.0 + numpy 2.3 (suite: 1304 passed, 12 skipped for optional torch/pyrealsense2), PyOpenGL was only a comment so a fresh install had no 3D tabs (now an active requirement), one test depended on no camera at index 0, and flirpy brings opencv-python-headless next to opencv-python (startup warning added when the versions differ). NOT verified on a real radiometric Boson with 0.6.x.
- [ ] flirpy upstream sends the FSLP CRC without bit-stuffing (a CRC byte equal to 0x8E/0x9E/0xAE is sent raw while the camera's own replies stuff it): rare (about 3/256 per packet), not observed on hardware; if CCI commands ever fail intermittently, override `_send_packet` in BosonNative to stuff the CRC.
- [ ] History scrub of `.claude/settings.local.json` (24 commits): validated on a mirror clone (file gone from all history, 187 vs 190 commits as 3 became empty, trees otherwise identical, bundle backup made) but NOT pushed. Needs an explicit go-ahead because it force-pushes main and the branch and changes every commit hash.

## 2026-10-02 flirpy 0.6 features
- [x] Boson external frame sync (master/slave/disabled): BosonNative (works on any flirpy), backend, plugin commands, Boson panel group, camera-info readout, tests. NOT tried on hardware (needs a cable between two cameras' sync pins; pin-out per the Boson IDD).
- [x] FLIR `.seq`/`.fff` playback as a thermal source (`--playback-file`, which was previously parsed but never implemented): `sdk/flir_file_reader.py`, `cameras/flir_file_backend.py`, `plugins/flir_file`, synthetic-file fixture + tests, verified end-to-end in the running app. Requires flirpy >= 0.6 (0.3 cannot parse real files); requirements now `flirpy>=0.6.2` and the main environment was upgraded with `--no-deps` (opencv 4.12 untouched).
- [ ] Playback not yet verified on a REAL FLIR `.seq` (only synthetic files built to flirpy's parser layout): try one from FLIR Tools/ResearchIR. Known limits: whole file loaded into memory (flirpy), no GUI file picker/seek bar yet (CLI only), `.csq` unsupported, frame rate from the file's FrameRate field (default 9 fps).
- [ ] flirpy upstream reads camera serial/firmware at decimal offsets 104/114 (ExifTool says 0x104/0x114); worked around in our reader, worth an upstream issue.
- [ ] Not adopted from 0.6: `ExifToolSplitter`/`Splitter` (needs the external exiftool binary), pyftdi/Lepton/Tau changes (no API differences found).

