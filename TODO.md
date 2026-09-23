# TODO — Handoff Notes

Last updated: 2026-09-23. Read this first if picking up a new session on `camera-plugin-architecture-and-perf-fixes` — it points at everything else.

## Status

Two features are **code-complete, tested (625 passed / 8 skipped / 0 failed), reviewed, and merged** into `camera-plugin-architecture-and-perf-fixes` (local commits, not yet pushed to origin):

1. **Spot-meter distance** — Spot Meter reports distance-to-point whenever a RealSense camera is the active RGB source, any view mode.
2. **3D Mapping Fusion** — new persistent-world 3D mapping mode: scan once with a RealSense camera (Open3D RGB-D odometry), freeze the geometry, then track the camera and re-texture live without rebuilding. New "3D Mapping" tab.

Full design spec: `docs/superpowers/specs/2026-09-22-3d-mapping-fusion-design.md`
Full implementation plans (task-by-task, what was built and why): `docs/superpowers/plans/2026-09-22-spot-meter-distance.md`, `docs/superpowers/plans/2026-09-22-3d-mapping-fusion.md`

Both went through a subagent-driven build with per-task review AND a final whole-plan review. The 3D Mapping Fusion final review caught real, serious problems before merge — the mode was completely unreachable from the UI, the point-cloud viewport was permanently hidden, and texture sampling used the wrong resolution (silently wrong colors). All fixed and re-verified. Don't assume "merged" means "lightly checked" — it went through two review passes.

## Real, standing risk — do this first

**Open3D was never installed in this development environment**, across the entire build. `thermal_inspection/processing/pose_tracker.py` and `world_point_cloud.py`'s Open3D-dependent code (RGB-D odometry, ICP, PLY I/O) is carefully transcribed and reviewed, but genuinely **unverified against the real library**. This is the single most important thing to check before trusting 3D Mapping Fusion at all:

```
pip install open3d
```

Then run the smoke-test script in `docs/superpowers/plans/2026-09-22-3d-mapping-fusion.md`'s Task 1, Step 6 — it exercises the exact Open3D API calls this feature depends on. If any call doesn't match the real installed API, fix it there before doing anything else; it'll be a quick, localized fix, not a redesign.

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

## Also pending

- **Not pushed to origin.** `camera-plugin-architecture-and-perf-fixes` is well ahead of `origin/camera-plugin-architecture-and-perf-fixes` (includes this work plus everything from before it) and `main` is behind too. Push/merge-to-main is a separate decision — ask before doing either, per this repo's standing git-safety practice.
- Working tree is otherwise clean as of this doc's writing — nothing else uncommitted.
