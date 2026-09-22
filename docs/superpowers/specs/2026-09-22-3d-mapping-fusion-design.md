# 3D Mapping Fusion + Spot-Meter Distance — Design Spec

**Date**: 2026-09-22
**Status**: Approved by user, ready for implementation planning

## Problem

Today's 3D Fusion mode (`thermal_inspection/gui/panels/fusion_3d_panel.py`) re-derives a depth-shaded flat 2D image (relief/fog/contours/anaglyph/colorize) from a live RealSense depth frame *every frame*. There is no persistent 3D model — the small `Fusion3DPointCloudView` point-cloud widget exists only as an alignment-verification tool, not a real scene.

The user wants a genuinely different mode: build the world's geometry once (a bounded scan phase), freeze it, and then on every subsequent frame just track where the camera currently is and re-texture the *already-built* static geometry with live thermal/RGB — no per-frame geometry rebuild. Camera movement after the scan must be supported (not just a fixed rig), which makes this a real-time visual/depth-odometry ("SLAM-adjacent") problem, since this app has no dedicated tracking camera (T265 unsupported/not owned) or usable IMU-based tracking path.

Separately: Spot Meter should report estimated distance-to-point whenever a RealSense camera (D400 or L515) is the active RGB source, independent of which view mode is active.

## Non-goals (v1)

- Full mesh reconstruction (Poisson/marching-cubes triangulated surfaces). Explicitly rejected — see "Point cloud vs. mesh" below.
- Automatic re-localization / loop closure after tracking is fully lost. Deferred — see "Tracking-quality UX."
- Multi-session map merging (stitching two separate scans of the same scene together).
- Any change to the *existing* 3D Fusion mode's behavior, code paths, or `_thermal_aligned_realsense` gate.

## Architecture

Three new modules, split for independent testability (each does one job, communicates through a narrow interface):

### `thermal_inspection/processing/pose_tracker.py` — `PoseTracker`
Pure pose estimation. Given `(color, depth, intrinsics)` and a reference (either the previous frame, for frame-to-frame tracking during scanning, or the frozen world cloud, for frame-to-model tracking after freeze), returns a 4×4 transform plus a tracking-quality score (from Open3D registration's fitness/inlier-ratio). Knows nothing about how the world is stored or rendered. Uses point-to-plane ICP (needs per-point normals, supplied by `WorldPointCloud`) for faster, more robust convergence than point-to-point.

### `thermal_inspection/processing/world_point_cloud.py` — `WorldPointCloud`
Owns the accumulated point data: positions, colors, normals. Responsibilities:
- `integrate(color, depth, intrinsics, pose)` — back-project depth to 3D world points via the given pose, append, voxel-downsample, update normals for new points. Scan-phase only.
- `freeze()` — stop accepting `integrate()` calls.
- `update_colors(pose, texture_frame, intrinsics)` — project each existing world point through the current pose into the live 2D frame, sample color. Live-phase only, called after freeze.
- `save(path)` / `load(path)` — PLY read/write via Open3D (`o3d.io.write_point_cloud`/`read_point_cloud`), positions + colors + normals.
- `reset()` — discard everything, back to empty/unfrozen.

Knows nothing about odometry.

### `thermal_inspection/processing/world_mapper.py` — `WorldMapper`
Thin orchestrator. Holds the state machine (`idle` → `scanning` → `mapped`), owns one `PoseTracker` + one `WorldPointCloud`, wires per-frame calls between them. This is the only class `app.py` talks to. Public API: `start_scan()`, `finish_scan()`, `reset()`, `track_and_texture(color, depth, intrinsics, texture_frame)` (called every throttled tick), plus read-only state (`state`, `tracking_quality`, `point_count`).

### GUI additions
- `thermal_inspection/gui/panels/mapping_fusion_panel.py` — new settings tab: Start/Finish/Reset, texture-source selector (thermal / RGB / blended — reuses `FusionProcessor`'s existing priority concept), tracking-quality indicator (Good/Degraded/Lost), Save/Load World.
- Extends the *existing* `Fusion3DPointCloudView` (`pyqtgraph.opengl` / `GLScatterPlotItem`) into the primary, continuously-orbitable output for this mode, rather than a new rendering widget.
- New `ViewMode.THREE_D_MAPPING` in `app.py`, sibling to `ViewMode.THREE_D`, own dispatch branch. Does not touch existing 3D Fusion code.

### Point cloud vs. mesh (explicitly decided)
A full triangulated mesh was considered and rejected: it doesn't reduce the two real per-frame costs (pose tracking operates on color+depth images, not mesh geometry; per-vertex coloring costs the same whether or not vertices are connected into faces), meshing a merged multi-viewpoint cloud needs its own reconstruction step (real one-time cost, not free), and a triangulated surface typically has ~2× the render primitives of the same point count. The actual lightweight wins — voxel-downsampling (shrinks N, speeds up everything downstream) and per-point normal estimation (enables point-to-plane ICP) — don't require mesh connectivity at all.

## Data Flow

**Scan phase** (every incoming RealSense color+depth+intrinsics frame):
1. `PoseTracker.track(color, depth, reference=previous_frame)` → frame-to-frame transform, composed into a running pose since scan start.
2. `WorldPointCloud.integrate(color, depth, intrinsics, pose)`.
3. Runs every frame while scanning — acceptable cost since it's bounded by Start→Finish, not indefinite.

**Finish**: `WorldPointCloud.freeze()`. `WorldMapper` state → `mapped`. Ready to save.

**Live phase** (every throttled tick, ~5–10Hz starting point — see "Open questions"):
1. `PoseTracker.track(color, depth, reference=frozen_world)` → frame-to-model pose via point-to-plane ICP.
2. If quality ≥ threshold: `WorldPointCloud.update_colors(pose, texture_frame, intrinsics)`, where `texture_frame` is thermal (sampled through the *existing* `ParallaxCompensator` RealSense↔thermal alignment — no new alignment path), RGB, or a blend per the panel's texture-source selector.
3. If quality < threshold: skip the color update (keep last-known colors), surface Degraded/Lost state.

## Spot-Meter Distance

Independent of `WorldMapper` — works in any view mode whenever RealSense is the active RGB camera. In `app.py`'s existing spot-meter update loop (~line 2373), for each measurement point: map thermal-frame coordinates to RealSense depth-frame coordinates via the same alignment already used elsewhere, sample `get_depth_frame()`, add `distance_m` to the emitted spot-value dict (only populated when the active camera exposes `get_depth_frame`). `SpotMeterPanel` gains a small display addition to show it alongside temperature.

## Persistence

Open3D writes PLY natively (position + color + normals). Save location follows `MediaManager`'s existing recordings-folder convention — a `world_maps/` subfolder, timestamped or user-labeled filename. The saved color is a snapshot at save time only; geometry is the reusable part, and texture resumes live updates immediately once tracking re-establishes after load.

## Tracking-Quality UX

Three states surfaced in `mapping_fusion_panel.py`, driven by Open3D registration's fitness/inlier-ratio score:
- **Good** — normal live updates.
- **Degraded** — still updating, but flagged.
- **Lost** — updates pause (last-known texture kept, never painted with a bad-pose sample), message: "Tracking lost — point the camera back at a mapped area, or Reset World."

Automatic re-localization (RANSAC-based global registration against the frozen model) is explicitly deferred, not built speculatively — ICP's natural capture range may self-recover often enough in practice; revisit only if real hardware testing shows it's needed.

## Testing

- **`PoseTracker`**: synthetic frame pairs with a known ground-truth transform, verify recovered pose is close. CPU-only, no camera/GPU needed.
- **`WorldPointCloud`**: integrate/downsample/freeze/update_colors/save-load round-trip against synthetic point sets.
- **`WorldMapper`**: state-machine transitions using fake `PoseTracker`/`WorldPointCloud` (dependency injection), matching this codebase's existing duck-typed-fake test style (see `test_realsense_camera.py`).
- **Spot-meter distance**: fake depth frame, assert `distance_m` appears correctly in emitted spot values.
- **Live hardware pass (manual, required before this is considered done)**: with the L515/D455 actually connected — scan produces a sane cloud, Finish freezes correctly, moving the camera after freeze tracks and re-textures reasonably, Lost/recovery behaves sanely rather than silently corrupting the model. Same bar this session already held the L515 pyrealsense2 integration itself to — no success claimed without a live confirmation.

## Dependencies

New optional dependency: `open3d` (pip-installable, MIT license). Lazy-imported and hardware-gated, same pattern as this app's other heavy-optional dependencies (torch, transformers, PyOpenGL) — its absence should degrade gracefully (3D Mapping Fusion tab shows a "python -m pip install open3d" placeholder, same style as the existing "PyOpenGL not installed" placeholder for 3D Fusion's point-cloud preview), not break anything else.

## Open Questions for Implementation Time

These are flagged rather than resolved here because they're better answered empirically once real code exists to test against real hardware, not guessed at design time:

- Exact live-phase throttle rate (5–10Hz starting point) — tune against measured frame time on real hardware, same as every other throttle constant in this codebase.
- Exact tracking-quality thresholds for Good/Degraded/Lost — need real fitness-score distributions from live tracking to calibrate, not a number to invent now.
- Voxel size for downsampling — trades off point density (visual/tracking quality) against point count (perf); needs live tuning.
