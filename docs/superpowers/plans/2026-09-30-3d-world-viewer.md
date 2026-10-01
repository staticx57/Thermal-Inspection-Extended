# 3D World Viewer - Plan

Date: 2026-09-30. Status: streams A, B and C are BUILT and unit-tested (917 tests pass); smoke-tested on the real L515
(world draws in the main view, click-to-probe returns a card with metric+imperial distances). NOT yet validated by the user,
and the thermal readouts have only been exercised on the synthetic scene (no thermal camera connected).

Built differently from the plan: Measure and Snap toggles live in the viewer's own toolbar (not the settings tab); the
settings tab has the hotspot list. The world is also drawn while scanning (worker publishes a copied preview).

## Goal

When the app is in 3D Mapping mode, the **main view** shows the mapped world full-size and is where you interact with
it: read a point's temperature, measure distances, jump to hotspots, see where the camera is. The 3D Mapping settings
tab keeps only controls and text. Today the main view shows the RGB feed as a stand-in and the settings tab holds a
small (min 220 px) point-cloud preview with no picking.

Out of scope: meshing/surface reconstruction, area/volume measurement, linking 2D spot meters/ROIs to the world,
thermal-over-time history, T265/external pose sources.

## What exists (do not rebuild)

- `WorldMapper` (`processing/world_mapper.py`): state, pose, `world` (points/colors/normals), `thermal`
  (`WorldThermalLayer`: latest/peak/baseline per point, `hotspots()`, `changes()`, `nearest()`, `colorize()`),
  `viewport_colors(mode)`, `thermal_summary()`.
- `Fusion3DPointCloudView` (`gui/panels/fusion_3d_panel.py`): pyqtgraph `GLViewWidget` + `GLScatterPlotItem`.
- App push path: `app.py` THREE_D_MAPPING branch -> `_gui_invoke("update_mapping_fusion_view", points, colors)`.
- Main video area: `VideoWidget` (2D frames). 3D Fusion mode also displays through it.

## Design

A new widget `WorldViewer` (`gui/widgets/world_viewer.py`) wraps a GLViewWidget and owns all 3D interaction. The main
window shows it in place of the video widget while `view_mode == THREE_D_MAPPING` (QStackedWidget swap), with the live
RGB feed as a small corner inset (same idea as PiP). The settings-tab preview is removed.

Interaction model (mouse):
- Left-drag orbit, wheel zoom, middle/right-drag pan (pyqtgraph defaults, kept).
- **Click** = probe: nearest world point within 12 px of the cursor -> info card (temperature live / peak / change,
  xyz in world frame, distance from camera now). Click empty space clears it.
- **Measure mode** (toolbar toggle, or hold Shift): click A then B -> line + label with straight-line distance and
  the temperature difference. Third click starts over. Esc cancels.
- **Hotspot markers**: top-N hotspots (and top changes when a baseline exists) drawn as labelled markers; clicking a
  marker selects it like a probe; list entries in the settings tab fly the camera to them.
- **Camera marker**: frustum/axes at the tracked pose; colour reflects tracking quality (good/degraded/lost).
- **Colour scale legend** for temperature / peak / change modes (min..max, units follow the app's temperature unit).

## Interfaces (the contract between streams)

These are fixed up front so streams can be built and tested independently with fakes.

### Viewer <- app/mapper (data in)
```
WorldViewer.set_world(points: (N,3) float32, colors: (N,3|4) float32)    # throttled by caller, <= MAX_PREVIEW_POINTS
WorldViewer.set_camera_pose(pose: 4x4 | None, quality_state: str)
WorldViewer.set_markers(hotspots: list[Marker])         # Marker = (label: str, xyz, value: float, kind: 'hot'|'warm'|'cool')
WorldViewer.set_legend(mode: str, lo: float, hi: float, unit: str) # lo/hi None hides it
WorldViewer.set_inset(frame_bgr: ndarray | None)
```
### Viewer -> app (events out)
```
probe_requested(index: int)            # index into the FULL world arrays (not the decimated preview)
measure_completed(index_a: int, index_b: int)
```
Because the preview is stride-decimated (MAX_PREVIEW_POINTS), the viewer must be given the **index map** of the points it
draws: `set_world(points, colors, indices)` where `indices[i]` is the full-world index of preview point i. Picking returns
full-world indices; the app resolves them to readings. (Picking on the decimated cloud is fine at 12 px tolerance; the
reading comes from the full cloud at that index.)

### Mapper additions (backend stream)
```
WorldMapper.probe(index) -> ProbeResult(xyz, temp, peak, change, distance_from_camera, has_temp)
WorldMapper.measure(i, j) -> MeasureResult(distance_m, dtemp)
WorldMapper.markers(count) -> list[Marker]                      # hotspots + changes, for set_markers
WorldMapper.camera_pose() -> 4x4 copy ; .quality_state (exists)
WorldMapper.legend(mode) -> (lo, hi) | None
```
All read-only and safe to call from the GUI thread while the tracking worker runs (take `_state_lock` briefly, copy).

### Settings tab <- -> app
Keeps: Start/Finish/Reset, Save/Load, Texture source, Show mode, Export, status/summary text.
Adds: Measure toggle, "Hotspots" list (click -> `fly_to(index)`), Reset view button.
Removes: the embedded `point_cloud_view`.

## Streams (parallel)

Three streams that can proceed at the same time because they only touch their own files and meet at the interfaces
above. Each ends with its own tests passing before integration.

### Stream A - Viewer widget (`gui/widgets/world_viewer.py`, `tests/unit/test_world_viewer.py`)
1. Skeleton: GLViewWidget, scatter, grid off, axes, background, GL-unavailable placeholder (match
   `Fusion3DPointCloudView` fallback text). `set_world/set_camera_pose/set_markers/set_legend/set_inset`.
2. **Picking**: project all drawn points with `projectionMatrix() * viewMatrix()` to pixel coordinates, vectorised;
   nearest point within 12 px, nearer-to-camera wins ties (cheap occlusion). Pure function
   `pick_nearest(points, mvp, viewport, cursor, radius)` so it is testable without a GL context.
3. Probe card overlay + selection ring; measure mode with line item and distance label; Esc/Shift handling.
4. Hotspot markers (text items + spheres), camera frustum marker, legend overlay, corner inset (QLabel overlay).
5. `fly_to(xyz)` and `reset_view()` (auto-frame on first data, as today).
Tests: `pick_nearest` against a known projection (hit, miss, tie-break, behind-camera ignored); marker/legend state; the
widget constructs headless (offscreen Qt) and degrades cleanly when GL is unavailable.

### Stream B - Backend (`processing/world_mapper.py`, `world_thermal.py`, `tests/unit/test_world_thermal.py`)
1. `probe/measure/markers/legend/camera_pose` on `WorldMapper` per the contract above (+ `ProbeResult`, `MeasureResult`,
   `Marker` dataclasses in `world_thermal.py`). Reuse `nearest`, `hotspots`, `changes`, `colorize` ranges.
2. Preview decimation moves into the mapper: `preview_cloud(max_points) -> (points, colors, indices)` so the index map is
   always consistent with what the viewer draws; replaces the ad-hoc `np.linspace` in `app.py`.
3. Unit tests on the synthetic scene: probe returns the known temperature at a known point; measure matches ground-truth
   distance between two surface points; markers sorted and de-duplicated; indices round-trip.

### Stream C - Settings tab + main-window integration (`gui/panels/mapping_fusion_panel.py`, `gui/main_window.py`, `app.py`)
1. Remove the embedded point cloud view; add Measure toggle, Hotspots list, Reset view.
2. `QStackedWidget` in the main window: index 0 = existing `VideoWidget`, index 1 = `WorldViewer`; switch on view-mode
   change (`_sync_view_mode_button` already runs on every change). Keep the keyboard/overlay logic that assumes the
   video widget unaffected (the 2D overlay widget stays with the video widget).
3. App push path: THREE_D_MAPPING branch calls `world_mapper.preview_cloud()` + `set_world`, `set_camera_pose`,
   `set_markers` (throttled 1-2 Hz for markers), `set_legend`, `set_inset(rgb_frame)`.
4. Wire `probe_requested` / `measure_completed` to `world_mapper.probe/measure` and show the result on the viewer card.
Tests: panel signals, view-mode switching shows the right stacked page, no references to the removed preview remain
(grep guard), existing wiring tests updated.

## Integration order
1. Land the contract (dataclasses + method stubs raising `NotImplementedError`) so all streams import cleanly.
2. A, B, C in parallel against fakes (a `FakeMapper` in tests implements the contract with canned data).
3. Merge B -> C -> A (backend first, then wiring, then the widget goes live); run the full suite after each merge.
4. Live check on the L515 (see below), then remove the old tab viewer.

## Live verification (needs hardware + the user)
- World shows full-size in the main view; orbit/zoom/pan smooth with a ~50-500k point world (target >= 30 fps on this PC).
- Click a surface: card appears at the right place; a known distance (tape measure between two wall marks) matches the
  measured distance within the L515's accuracy (~1% at close range).
- With a radiometric thermal camera aligned (not available on this machine yet): clicked temperature matches the spot
  meter at the same point, within the camera's accuracy.
- Camera marker follows a hand-held move; goes red when tracking is lost.
- Settings tab no longer contains a point cloud; Start/Finish/Save/Load/Export still work.

## Risks / open questions
- **GL picking accuracy**: projecting with pyqtgraph's matrices must account for the widget's devicePixelRatio (the
  user's display is scaled) - test on the real 4K display, not only offscreen.
- **Decimation vs picking**: picks land on the decimated preview; the index map keeps readings exact, but a pick may be
  a few mm from the point the user "meant". Acceptable; surfaced in the card as "nearest sample".
- **Thermal temperatures**: only present with an aligned radiometric camera; the card must say "no temperature
  recorded" rather than show nothing, and never show an estimate.
- **Main-view swap**: other code reads `video_widget` assuming it is always visible (overlay sync, recording,
  snapshot). Snapshot/record in this mode should capture the viewer (`grab()`) - decide with the user; default is
  recording the RGB feed as today.
- **Performance of re-pushing the cloud**: only re-send colours/points when the world revision or colour mode changes,
  not every tick (today it is pushed at ~10 Hz).

## Decisions (confirmed by the user 2026-09-30)
- Snapshot and record in this mode use the **RGB feed**, as today (not the 3D viewer).
- Measure/probe **snap to hotspot markers**, with a toggle (default on) to turn snapping off.
- Temperatures follow the app's temperature-unit setting (deltas convert without the offset). Distances are shown in
  **both metric and imperial**, e.g. `1.25 m (4 ft 1 in)`, `38 cm (1 ft 3 in)`.
