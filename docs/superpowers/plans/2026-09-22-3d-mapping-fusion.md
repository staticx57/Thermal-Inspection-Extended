# 3D Mapping Fusion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A new `ViewMode.THREE_D_MAPPING`: build a RealSense point-cloud world once during an explicit scan phase, freeze it, then track the moving camera against the frozen world and re-texture it live with thermal/RGB — no per-frame geometry rebuild.

**Architecture:** Three new GUI-agnostic processing classes (`PoseTracker`, `WorldPointCloud`, `WorldMapper`) built on Open3D, driven by `app.py`'s existing frame loop the same way `DepthEstimator`/`ParallaxCompensator` already are. A new settings tab reuses the *existing* `Fusion3DPointCloudView` widget (its `update_point_cloud(vertices, colors)` method is already fully generic, not RealSense-specific) as the live-navigable world viewport.

**Tech Stack:** Python, Open3D (new optional dependency), existing `RGBCameraRealSense` (`get_point_cloud`/`get_depth_intrinsics`/`get_depth_frame`), existing `pyqtgraph.opengl` point-cloud rendering, PyQt6.

**Spec:** `docs/superpowers/specs/2026-09-22-3d-mapping-fusion-design.md`

## Global Constraints

- Open3D is a new **optional** dependency, lazy-imported and hardware-gated exactly like this app's other heavy-optional deps (torch, transformers, PyOpenGL) — its absence must never break anything else, only show a graceful placeholder in the new tab.
- This plan must not modify any existing `ViewMode.THREE_D` code path, the `_thermal_aligned_realsense` gate, or any of `fusion_3d_panel.py`'s existing relief/fog/contours/anaglyph/colorize functions.
- Valid depth range is `MIN_VALID_DEPTH_M` (from `parallax_compensator.py`) to `MAX_VALID_DEPTH_M` (from `fusion_3d_panel.py`) — reuse these constants, don't redefine them.
- **Executor note on test tolerances**: Open3D isn't installed in this development environment as of plan-writing time, so the numeric tolerances in this plan's synthetic tests (e.g. `pytest.approx(..., abs=0.02)`) are reasoned starting points, not values verified against the real library. If a test fails only on tolerance (the transform/fitness is in the right ballpark but outside the stated bound), widen the tolerance and note why in a comment — don't treat the literal number as sacred. If a test fails because an Open3D API call doesn't exist or has a different signature than written here, fix the call to match the installed version's real API (check `python -c "import open3d as o3d; help(o3d.pipelines.odometry)"` etc.) and note the correction in the commit message.
- Follow this codebase's existing convention: BGR uint8 for color frames everywhere except at the Open3D boundary (Open3D wants RGB), and float32 meters for depth.

---

### Task 1: Optional `open3d` dependency + availability flag + API smoke test

**Files:**
- Modify: `requirements.txt`
- Create: `thermal_inspection/processing/open3d_support.py` (lazy-import helper, mirrors the `_TORCH_SPEC_AVAILABLE`/`GL_AVAILABLE` pattern in `fusion_3d_panel.py`)
- Test: `tests/unit/test_open3d_support.py`

**Interfaces:**
- Produces: `OPEN3D_AVAILABLE: bool`, `get_open3d()` (returns the imported module or raises a clear `ImportError` with an install hint) — consumed by every later task.

- [ ] **Step 1: Write the failing tests**

```python
def test_open3d_support_flag_matches_real_import():
    from thermal_inspection.processing.open3d_support import OPEN3D_AVAILABLE
    try:
        import open3d  # noqa: F401
        really_available = True
    except ImportError:
        really_available = False
    assert OPEN3D_AVAILABLE == really_available


def test_get_open3d_raises_clear_error_when_unavailable(monkeypatch):
    import thermal_inspection.processing.open3d_support as mod
    monkeypatch.setattr(mod, "OPEN3D_AVAILABLE", False)
    import pytest
    with pytest.raises(ImportError, match="pip install open3d"):
        mod.get_open3d()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_open3d_support.py -v`
Expected: FAIL — module doesn't exist yet.

- [ ] **Step 3: Implement**

`thermal_inspection/processing/open3d_support.py`:

```python
"""
Lazy-import gate for Open3D, this app's optional dependency for 3D Mapping
Fusion (PoseTracker/WorldPointCloud/WorldMapper - see world_mapper.py).
Same pattern as fusion_3d_panel.py's _TORCH_SPEC_AVAILABLE/GL_AVAILABLE -
importing Open3D eagerly at module load would slow every app startup (and
fail entirely on a machine that never installs it) for a feature most
users won't touch.
"""
import importlib.util

OPEN3D_AVAILABLE = importlib.util.find_spec("open3d") is not None


def get_open3d():
    """Import and return the open3d module, or raise a clear ImportError."""
    if not OPEN3D_AVAILABLE:
        raise ImportError(
            "open3d is not installed. 3D Mapping Fusion needs it - "
            "install with: pip install open3d"
        )
    import open3d as o3d
    return o3d
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/test_open3d_support.py -v`
Expected: PASS

- [ ] **Step 5: Add the requirements.txt entry**

Add near the existing RealSense section:

```
# ============================================================================
# Optional: Open3D (3D Mapping Fusion - persistent world point cloud)
# ============================================================================
# Uncomment to enable 3D Mapping Fusion (build-world-once + live-texture
# view mode, separate from the existing 3D Fusion per-frame shading).
# Needs an Intel RealSense camera (see the RealSense section above) - Open3D
# itself has no camera dependency, it just does the RGB-D odometry/point-
# cloud math.
#
# open3d>=0.18.0
```

- [ ] **Step 6: If open3d is actually installed in this environment, smoke-test its real API surface before building on it**

```bash
python -m pip show open3d >/dev/null 2>&1 && python -c "
import open3d as o3d
import numpy as np
intr = o3d.camera.PinholeCameraIntrinsic(64, 48, 50.0, 50.0, 32.0, 24.0)
print('focal:', intr.get_focal_length())
print('principal:', intr.get_principal_point())
color = o3d.geometry.Image(np.zeros((48, 64, 3), dtype=np.uint8))
depth = o3d.geometry.Image(np.ones((48, 64), dtype=np.float32))
rgbd = o3d.geometry.RGBDImage.create_from_color_and_depth(
    color, depth, depth_scale=1.0, depth_trunc=9.0, convert_rgb_to_intensity=False
)
option = o3d.pipelines.odometry.OdometryOption()
success, trans, info = o3d.pipelines.odometry.compute_rgbd_odometry(
    rgbd, rgbd, intr, np.eye(4),
    o3d.pipelines.odometry.RGBDOdometryJacobianFromHybridTerm(), option
)
print('odometry smoke test: success=', success)
pcd = o3d.geometry.PointCloud.create_from_rgbd_image(rgbd, intr)
print('point count:', len(pcd.points))
pcd.estimate_normals(search_param=o3d.geometry.KDTreeSearchParamHybrid(radius=0.1, max_nn=30))
print('normals ok:', len(pcd.normals) == len(pcd.points))
"
```

If this fails on a specific call, that's real signal about the installed version's actual API — fix Tasks 2-3's code to match before writing them, and note the discrepancy in this task's commit message. If `open3d` isn't installed at all, skip this step (Tasks 2-4's tests will just report 0 collected / skip via the same `OPEN3D_AVAILABLE` gate `test_realsense_camera.py` uses for `REALSENSE_AVAILABLE`).

- [ ] **Step 7: Commit**

```bash
git add requirements.txt thermal_inspection/processing/open3d_support.py tests/unit/test_open3d_support.py
git commit -m "feat: add optional open3d dependency for 3D Mapping Fusion"
```

---

### Task 2: `PoseTracker` — pose estimation only

**Files:**
- Create: `thermal_inspection/processing/pose_tracker.py`
- Test: `tests/unit/test_pose_tracker.py`

**Interfaces:**
- Consumes: `get_open3d()` from Task 1.
- Produces: `PoseTracker(width, height, fx, fy, cx, cy)`, `.intrinsic` (an `o3d.camera.PinholeCameraIntrinsic`), `.track_frame_to_frame(color, depth_m, prev_color, prev_depth_m, init_transform) -> (success: bool, transform: np.ndarray[4,4], quality: float)`, `.track_frame_to_model(color, depth_m, world_points, world_normals, init_transform, max_correspondence_distance=0.05) -> (success, transform, quality)` — both consumed by `WorldMapper` in Task 4.

- [ ] **Step 1: Write the failing tests**

```python
import numpy as np
import pytest
from thermal_inspection.processing.open3d_support import OPEN3D_AVAILABLE

pytestmark = pytest.mark.skipif(not OPEN3D_AVAILABLE, reason="open3d not installed")


def _synthetic_frame(w=64, h=48, depth_value=1.0):
    """A flat textured plane - enough photometric structure (a checkerboard
    pattern) for RGB-D odometry to have something to lock onto, at constant
    depth."""
    color = np.zeros((h, w, 3), dtype=np.uint8)
    color[::4, ::4] = 255  # sparse bright grid points, not a flat blank image
    depth = np.full((h, w), depth_value, dtype=np.float32)
    return color, depth


class TestFrameToFrame:
    def test_identical_frames_recover_near_identity_transform(self):
        from thermal_inspection.processing.pose_tracker import PoseTracker
        tracker = PoseTracker(64, 48, fx=50.0, fy=50.0, cx=32.0, cy=24.0)
        color, depth = _synthetic_frame()

        success, transform, quality = tracker.track_frame_to_frame(
            color, depth, color, depth, np.eye(4)
        )

        assert success
        # Two identical frames -> recovered transform should be close to
        # identity (translation near zero, rotation near identity).
        assert np.allclose(transform[:3, 3], 0.0, atol=0.02)
        assert np.allclose(transform[:3, :3], np.eye(3), atol=0.05)


class TestFrameToModel:
    def test_icp_recovers_pure_depth_offset_against_flat_plane(self):
        from thermal_inspection.processing.pose_tracker import PoseTracker
        tracker = PoseTracker(64, 48, fx=50.0, fy=50.0, cx=32.0, cy=24.0)

        # World: a flat plane of points at z=1.0, facing the camera
        # (normal pointing back toward -z).
        xs, ys = np.meshgrid(np.linspace(-0.3, 0.3, 20), np.linspace(-0.3, 0.3, 20))
        world_points = np.stack([xs.ravel(), ys.ravel(), np.ones(400)], axis=1).astype(np.float64)
        world_normals = np.tile(np.array([0.0, 0.0, -1.0]), (400, 1))

        # Current frame: the same plane shifted 0.05m farther away.
        color, depth = _synthetic_frame(depth_value=1.05)

        success, transform, quality = tracker.track_frame_to_model(
            color, depth, world_points, world_normals, np.eye(4)
        )

        assert success
        # Recovered transform's Z-translation component should reflect the
        # ~0.05m depth offset (sign depends on convention - just check
        # magnitude is in the right ballpark, not exact).
        assert abs(abs(transform[2, 3]) - 0.05) < 0.03
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_pose_tracker.py -v`
Expected: FAIL — module doesn't exist.

- [ ] **Step 3: Implement**

`thermal_inspection/processing/pose_tracker.py`:

```python
"""
Pure camera-pose estimation for 3D Mapping Fusion (see world_mapper.py for
the orchestrator that drives this, and world_point_cloud.py for where the
tracked geometry actually lives). Knows nothing about how the world is
stored or rendered - just: given two RGB-D inputs (or an RGB-D frame plus a
target point cloud), what's the relative camera transform between them.

Two distinct tracking modes, matching two distinct Open3D algorithms:
- track_frame_to_frame: RGB-D odometry between two full color+depth images
  (scan phase, consecutive frames).
- track_frame_to_model: point-to-plane ICP of the current frame's point
  cloud against an already-built target point cloud with normals (live
  phase, tracking against the frozen world).
"""
from __future__ import annotations

from typing import Tuple

import cv2
import numpy as np

from thermal_inspection.processing.open3d_support import get_open3d


class PoseTracker:
    def __init__(self, width: int, height: int, fx: float, fy: float, cx: float, cy: float):
        o3d = get_open3d()
        self.intrinsic = o3d.camera.PinholeCameraIntrinsic(width, height, fx, fy, cx, cy)
        self._odometry_option = o3d.pipelines.odometry.OdometryOption()

    def _to_rgbd(self, color_bgr: np.ndarray, depth_m: np.ndarray, max_depth_m: float):
        o3d = get_open3d()
        color_rgb = cv2.cvtColor(color_bgr, cv2.COLOR_BGR2RGB)
        color_img = o3d.geometry.Image(np.ascontiguousarray(color_rgb))
        depth_img = o3d.geometry.Image(np.ascontiguousarray(depth_m.astype(np.float32)))
        return o3d.geometry.RGBDImage.create_from_color_and_depth(
            color_img, depth_img, depth_scale=1.0, depth_trunc=max_depth_m,
            convert_rgb_to_intensity=False,
        )

    def track_frame_to_frame(self, color: np.ndarray, depth_m: np.ndarray,
                              prev_color: np.ndarray, prev_depth_m: np.ndarray,
                              init_transform: np.ndarray,
                              max_depth_m: float = 9.0) -> Tuple[bool, np.ndarray, float]:
        """RGB-D odometry from prev_color/prev_depth_m to color/depth_m.
        Returns (success, 4x4 transform, quality). On failure, transform is
        init_transform unchanged and quality is 0.0."""
        o3d = get_open3d()
        source_rgbd = self._to_rgbd(prev_color, prev_depth_m, max_depth_m)
        target_rgbd = self._to_rgbd(color, depth_m, max_depth_m)
        success, transform, info = o3d.pipelines.odometry.compute_rgbd_odometry(
            source_rgbd, target_rgbd, self.intrinsic, init_transform,
            o3d.pipelines.odometry.RGBDOdometryJacobianFromHybridTerm(),
            self._odometry_option,
        )
        if not success:
            return False, init_transform, 0.0
        quality = float(np.trace(np.asarray(info)))
        return True, np.asarray(transform), quality

    def track_frame_to_model(self, color: np.ndarray, depth_m: np.ndarray,
                              world_points: np.ndarray, world_normals: np.ndarray,
                              init_transform: np.ndarray,
                              max_correspondence_distance: float = 0.05) -> Tuple[bool, np.ndarray, float]:
        """Point-to-plane ICP of this frame's depth-derived point cloud
        against the frozen world (world_points/world_normals). Returns
        (success, 4x4 transform, fitness). On failure (fitness == 0),
        transform is init_transform unchanged."""
        o3d = get_open3d()
        depth_img = o3d.geometry.Image(np.ascontiguousarray(depth_m.astype(np.float32)))
        source_pcd = o3d.geometry.PointCloud.create_from_depth_image(
            depth_img, self.intrinsic, depth_scale=1.0, depth_trunc=9.0
        )
        target_pcd = o3d.geometry.PointCloud()
        target_pcd.points = o3d.utility.Vector3dVector(world_points)
        target_pcd.normals = o3d.utility.Vector3dVector(world_normals)

        result = o3d.pipelines.registration.registration_icp(
            source_pcd, target_pcd, max_correspondence_distance, init_transform,
            o3d.pipelines.registration.TransformationEstimationPointToPlane(),
        )
        if result.fitness <= 0.0:
            return False, init_transform, 0.0
        return True, np.asarray(result.transformation), float(result.fitness)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/test_pose_tracker.py -v`
Expected: PASS (or SKIPPED if open3d isn't installed in this environment — that's fine, still commit; the live-hardware pass in Task 7 is the real bar).

- [ ] **Step 5: Commit**

```bash
git add thermal_inspection/processing/pose_tracker.py tests/unit/test_pose_tracker.py
git commit -m "feat: add PoseTracker for 3D Mapping Fusion RGB-D pose estimation"
```

---

### Task 3: `WorldPointCloud` — accumulated geometry, texture updates, persistence

**Files:**
- Create: `thermal_inspection/processing/world_point_cloud.py`
- Test: `tests/unit/test_world_point_cloud.py`

**Interfaces:**
- Consumes: `get_open3d()` from Task 1; a `PoseTracker.intrinsic` object (Task 2) passed into `integrate`/`update_colors`.
- Produces: `WorldPointCloud(voxel_size=0.01)`, `.integrate(color, depth_m, intrinsic, pose)`, `.freeze()`, `.reset()`, `.update_colors(pose, texture_frame, intrinsic) -> int`, `.save(path)`, `.load(path)`, properties `.points`, `.colors`, `.normals`, `.point_count`, `.frozen: bool` — all consumed by `WorldMapper` in Task 4.

- [ ] **Step 1: Write the failing tests**

```python
import numpy as np
import pytest
import tempfile
import os
from thermal_inspection.processing.open3d_support import OPEN3D_AVAILABLE

pytestmark = pytest.mark.skipif(not OPEN3D_AVAILABLE, reason="open3d not installed")


def _flat_frame(w=32, h=24, depth_value=1.0):
    color = np.full((h, w, 3), 128, dtype=np.uint8)
    depth = np.full((h, w), depth_value, dtype=np.float32)
    return color, depth


def _intrinsic(w=32, h=24):
    from thermal_inspection.processing.open3d_support import get_open3d
    o3d = get_open3d()
    return o3d.camera.PinholeCameraIntrinsic(w, h, 30.0, 30.0, w / 2, h / 2)


class TestIntegrate:
    def test_integrate_adds_points(self):
        from thermal_inspection.processing.world_point_cloud import WorldPointCloud
        world = WorldPointCloud(voxel_size=0.01)
        color, depth = _flat_frame()
        world.integrate(color, depth, _intrinsic(), np.eye(4))
        assert world.point_count > 0

    def test_integrate_raises_when_frozen(self):
        from thermal_inspection.processing.world_point_cloud import WorldPointCloud
        world = WorldPointCloud()
        color, depth = _flat_frame()
        world.integrate(color, depth, _intrinsic(), np.eye(4))
        world.freeze()
        with pytest.raises(RuntimeError, match="frozen"):
            world.integrate(color, depth, _intrinsic(), np.eye(4))


class TestFreeze:
    def test_freeze_computes_normals(self):
        from thermal_inspection.processing.world_point_cloud import WorldPointCloud
        world = WorldPointCloud(voxel_size=0.01)
        color, depth = _flat_frame()
        world.integrate(color, depth, _intrinsic(), np.eye(4))
        world.freeze()
        assert world.frozen
        assert world.normals.shape[0] == world.point_count


class TestUpdateColors:
    def test_update_colors_samples_new_texture(self):
        from thermal_inspection.processing.world_point_cloud import WorldPointCloud
        world = WorldPointCloud(voxel_size=0.01)
        color, depth = _flat_frame()
        world.integrate(color, depth, _intrinsic(), np.eye(4))
        world.freeze()

        # A distinctly-colored new texture frame, same resolution.
        new_texture = np.zeros((24, 32, 3), dtype=np.uint8)
        new_texture[:, :, 2] = 200  # strong red (BGR)

        updated_count = world.update_colors(np.eye(4), new_texture, _intrinsic())

        assert updated_count > 0
        colors = world.colors  # Open3D convention: (N, 3) RGB in [0, 1]
        # At least some points should now read close to red (R high, G/B low).
        assert np.mean(colors[:, 0]) > 0.5


class TestPersistence:
    def test_save_and_load_round_trip(self):
        from thermal_inspection.processing.world_point_cloud import WorldPointCloud
        world = WorldPointCloud(voxel_size=0.01)
        color, depth = _flat_frame()
        world.integrate(color, depth, _intrinsic(), np.eye(4))
        world.freeze()
        original_count = world.point_count

        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "world.ply")
            world.save(path)
            assert os.path.exists(path)

            loaded = WorldPointCloud()
            loaded.load(path)
            assert loaded.frozen
            assert loaded.point_count == original_count


class TestReset:
    def test_reset_clears_and_unfreezes(self):
        from thermal_inspection.processing.world_point_cloud import WorldPointCloud
        world = WorldPointCloud(voxel_size=0.01)
        color, depth = _flat_frame()
        world.integrate(color, depth, _intrinsic(), np.eye(4))
        world.freeze()

        world.reset()

        assert world.point_count == 0
        assert not world.frozen


# NOT gated by the open3d skip marker - this is the whole point of the
# test: constructing a WorldPointCloud (which WorldMapper does eagerly at
# app startup, regardless of whether the user ever touches 3D Mapping
# Fusion) must be safe even when open3d isn't installed at all. Only
# actually USING it (integrate/freeze/save/load) should require open3d.
def test_construction_and_readonly_access_safe_without_open3d():
    from thermal_inspection.processing.world_point_cloud import WorldPointCloud
    world = WorldPointCloud(voxel_size=0.01)  # must not raise even if open3d is missing
    assert world.point_count == 0
    assert world.points.shape == (0, 3)
    assert world.colors.shape == (0, 3)
    assert world.normals.shape == (0, 3)
    assert not world.frozen
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_world_point_cloud.py -v`
Expected: FAIL — module doesn't exist.

- [ ] **Step 3: Implement**

`thermal_inspection/processing/world_point_cloud.py`:

```python
"""
Accumulated/frozen world geometry for 3D Mapping Fusion. Owns point
positions, colors, and normals - integration during the scan phase,
per-vertex color re-sampling during the live phase, and PLY persistence.
Knows nothing about odometry (see pose_tracker.py for that) or the
scan/track/freeze state machine (see world_mapper.py for that).
"""
from __future__ import annotations

import numpy as np

from thermal_inspection.processing.open3d_support import get_open3d


class WorldPointCloud:
    def __init__(self, voxel_size: float = 0.01):
        # Deliberately does NOT call get_open3d() here - WorldMapper
        # constructs a WorldPointCloud eagerly at app startup regardless of
        # whether the user ever touches 3D Mapping Fusion, so this
        # constructor must succeed even when open3d isn't installed at all
        # (see the Global Constraints' "graceful placeholder, not a hard
        # failure" requirement). The actual o3d.geometry.PointCloud only
        # gets created in _ensure_pcd(), called from methods that need it -
        # those are only reached once the user explicitly starts a scan.
        self.voxel_size = voxel_size
        self._pcd = None
        self.frozen = False

    def _ensure_pcd(self):
        if self._pcd is None:
            o3d = get_open3d()
            self._pcd = o3d.geometry.PointCloud()
        return self._pcd

    def integrate(self, color: np.ndarray, depth_m: np.ndarray, intrinsic, pose: np.ndarray):
        """Back-project a color+depth frame through `pose` (camera-to-world
        4x4) into world space and merge into the accumulated cloud,
        downsampling afterward to bound growth. Scan-phase only."""
        if self.frozen:
            raise RuntimeError("Cannot integrate into a frozen WorldPointCloud - call reset() first")
        o3d = get_open3d()
        self._ensure_pcd()
        import cv2
        color_rgb = cv2.cvtColor(color, cv2.COLOR_BGR2RGB)
        color_img = o3d.geometry.Image(np.ascontiguousarray(color_rgb))
        depth_img = o3d.geometry.Image(np.ascontiguousarray(depth_m.astype(np.float32)))
        rgbd = o3d.geometry.RGBDImage.create_from_color_and_depth(
            color_img, depth_img, depth_scale=1.0, depth_trunc=9.0, convert_rgb_to_intensity=False,
        )
        frame_pcd = o3d.geometry.PointCloud.create_from_rgbd_image(rgbd, intrinsic)
        frame_pcd.transform(pose)
        self._pcd += frame_pcd
        self._pcd = self._pcd.voxel_down_sample(self.voxel_size)

    def freeze(self):
        """Stop accepting integrate() calls, compute normals for point-to-
        plane ICP (see pose_tracker.track_frame_to_model)."""
        o3d = get_open3d()
        pcd = self._ensure_pcd()
        pcd.estimate_normals(
            search_param=o3d.geometry.KDTreeSearchParamHybrid(radius=self.voxel_size * 2, max_nn=30)
        )
        self.frozen = True

    def update_colors(self, pose: np.ndarray, texture_frame: np.ndarray, intrinsic) -> int:
        """Re-sample this point cloud's colors from a new 2D BGR frame,
        given the camera's current pose (camera-to-world 4x4). Points that
        project outside the frame or land behind the camera keep their
        previous color. Live-phase only. Returns how many points were
        actually updated (diagnostics/tests)."""
        o3d = get_open3d()
        pcd = self._ensure_pcd()
        points = np.asarray(pcd.points)
        if points.shape[0] == 0:
            return 0

        inv_pose = np.linalg.inv(pose)
        ones = np.ones((points.shape[0], 1), dtype=points.dtype)
        points_h = np.hstack([points, ones])
        cam_pts = (inv_pose @ points_h.T).T[:, :3]

        fx, fy = intrinsic.get_focal_length()
        cx, cy = intrinsic.get_principal_point()
        z = cam_pts[:, 2]
        valid = z > 1e-6
        u = np.zeros_like(z)
        v = np.zeros_like(z)
        u[valid] = (cam_pts[valid, 0] * fx / z[valid]) + cx
        v[valid] = (cam_pts[valid, 1] * fy / z[valid]) + cy

        h, w = texture_frame.shape[:2]
        in_bounds = valid & (u >= 0) & (u < w) & (v >= 0) & (v < h)

        colors = np.asarray(pcd.colors)
        if colors.shape[0] != points.shape[0]:
            colors = np.zeros((points.shape[0], 3), dtype=np.float64)

        idx = np.where(in_bounds)[0]
        if idx.shape[0] == 0:
            return 0
        px = u[idx].astype(np.int32)
        py = v[idx].astype(np.int32)
        # texture_frame is BGR uint8 (this codebase's convention) - Open3D wants RGB [0, 1].
        sampled_bgr = texture_frame[py, px].astype(np.float64) / 255.0
        colors[idx, 0] = sampled_bgr[:, 2]
        colors[idx, 1] = sampled_bgr[:, 1]
        colors[idx, 2] = sampled_bgr[:, 0]
        pcd.colors = o3d.utility.Vector3dVector(colors)
        return int(idx.shape[0])

    def reset(self):
        # Safe even if open3d was never imported (self._pcd is already
        # None) - just re-affirms the empty/unfrozen state rather than
        # forcing an import that isn't otherwise needed.
        self._pcd = None
        self.frozen = False

    def save(self, path: str):
        o3d = get_open3d()
        o3d.io.write_point_cloud(path, self._ensure_pcd())

    def load(self, path: str):
        o3d = get_open3d()
        self._pcd = o3d.io.read_point_cloud(path)
        self.frozen = True

    @property
    def points(self) -> np.ndarray:
        return np.asarray(self._pcd.points) if self._pcd is not None else np.zeros((0, 3))

    @property
    def colors(self) -> np.ndarray:
        return np.asarray(self._pcd.colors) if self._pcd is not None else np.zeros((0, 3))

    @property
    def normals(self) -> np.ndarray:
        return np.asarray(self._pcd.normals) if self._pcd is not None else np.zeros((0, 3))

    @property
    def point_count(self) -> int:
        return len(self._pcd.points) if self._pcd is not None else 0
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/test_world_point_cloud.py -v`
Expected: PASS (or SKIPPED if open3d isn't installed).

- [ ] **Step 5: Commit**

```bash
git add thermal_inspection/processing/world_point_cloud.py tests/unit/test_world_point_cloud.py
git commit -m "feat: add WorldPointCloud for 3D Mapping Fusion's persistent geometry"
```

---

### Task 4: `WorldMapper` — state machine orchestrator

**Files:**
- Create: `thermal_inspection/processing/world_mapper.py`
- Test: `tests/unit/test_world_mapper.py`

**Interfaces:**
- Consumes: `PoseTracker` (Task 2, via injectable `pose_tracker_factory`), `WorldPointCloud` (Task 3, via injectable `world_factory`) — dependency-injected so this task's tests use fakes and need no real Open3D.
- Produces: `WorldMapper(voxel_size=0.01, quality_good_threshold=0.3, quality_degraded_threshold=0.1, pose_tracker_factory=PoseTracker, world_factory=WorldPointCloud)`, `.state: str` (`"idle"|"scanning"|"mapped"`), `.tracking_quality: float`, `.quality_state: str` (`"n/a"|"good"|"degraded"|"lost"`), `.start_scan(width, height, fx, fy, cx, cy)`, `.finish_scan()`, `.reset()`, `.track_and_texture(color, depth_m, texture_frame=None)`, `.point_count: int`, `.world: WorldPointCloud` — consumed by `mapping_fusion_panel.py` (Task 5) and `app.py` (Task 6).

- [ ] **Step 1: Write the failing tests**

```python
import numpy as np
import pytest


class _FakePoseTracker:
    """Records calls, returns a canned (success, transform, quality)."""
    def __init__(self, width, height, fx, fy, cx, cy):
        self.init_args = (width, height, fx, fy, cx, cy)
        self.frame_to_frame_calls = 0
        self.frame_to_model_calls = 0
        self.next_result = (True, np.eye(4), 0.5)

    def track_frame_to_frame(self, color, depth_m, prev_color, prev_depth_m, init_transform):
        self.frame_to_frame_calls += 1
        return self.next_result

    def track_frame_to_model(self, color, depth_m, world_points, world_normals, init_transform,
                              max_correspondence_distance=0.05):
        self.frame_to_model_calls += 1
        return self.next_result


class _FakeWorldPointCloud:
    def __init__(self, voxel_size=0.01):
        self.voxel_size = voxel_size
        self.frozen = False
        self.integrate_calls = 0
        self.update_colors_calls = 0
        self._point_count = 0
        self.points = np.zeros((0, 3))
        self.normals = np.zeros((0, 3))

    def integrate(self, color, depth_m, intrinsic, pose):
        self.integrate_calls += 1
        self._point_count += 10

    def freeze(self):
        self.frozen = True

    def update_colors(self, pose, texture_frame, intrinsic):
        self.update_colors_calls += 1
        return 5

    def reset(self):
        self.frozen = False
        self._point_count = 0

    @property
    def point_count(self):
        return self._point_count


def _make_mapper(**overrides):
    from thermal_inspection.processing.world_mapper import WorldMapper
    kwargs = dict(pose_tracker_factory=_FakePoseTracker, world_factory=_FakeWorldPointCloud)
    kwargs.update(overrides)
    return WorldMapper(**kwargs)


class TestStateMachine:
    def test_starts_idle(self):
        mapper = _make_mapper()
        assert mapper.state == "idle"

    def test_start_scan_transitions_to_scanning(self):
        mapper = _make_mapper()
        mapper.start_scan(64, 48, 50.0, 50.0, 32.0, 24.0)
        assert mapper.state == "scanning"

    def test_finish_scan_transitions_to_mapped_and_freezes_world(self):
        mapper = _make_mapper()
        mapper.start_scan(64, 48, 50.0, 50.0, 32.0, 24.0)
        mapper.finish_scan()
        assert mapper.state == "mapped"
        assert mapper.world.frozen

    def test_finish_scan_raises_when_not_scanning(self):
        mapper = _make_mapper()
        with pytest.raises(RuntimeError, match="scanning"):
            mapper.finish_scan()

    def test_reset_returns_to_idle(self):
        mapper = _make_mapper()
        mapper.start_scan(64, 48, 50.0, 50.0, 32.0, 24.0)
        mapper.finish_scan()
        mapper.reset()
        assert mapper.state == "idle"
        assert not mapper.world.frozen


class TestTrackAndTextureScanPhase:
    def test_calls_integrate_every_frame(self):
        mapper = _make_mapper()
        mapper.start_scan(64, 48, 50.0, 50.0, 32.0, 24.0)
        color = np.zeros((48, 64, 3), dtype=np.uint8)
        depth = np.ones((48, 64), dtype=np.float32)

        mapper.track_and_texture(color, depth)
        mapper.track_and_texture(color, depth)

        assert mapper.world.integrate_calls == 2

    def test_raises_when_called_in_idle_state(self):
        mapper = _make_mapper()
        color = np.zeros((48, 64, 3), dtype=np.uint8)
        depth = np.ones((48, 64), dtype=np.float32)
        with pytest.raises(RuntimeError, match="idle"):
            mapper.track_and_texture(color, depth)


class TestTrackAndTextureLivePhase:
    def test_good_quality_updates_colors(self):
        mapper = _make_mapper(quality_good_threshold=0.3, quality_degraded_threshold=0.1)
        mapper.start_scan(64, 48, 50.0, 50.0, 32.0, 24.0)
        mapper.finish_scan()
        mapper._pose_tracker.next_result = (True, np.eye(4), 0.5)  # >= good threshold

        color = np.zeros((48, 64, 3), dtype=np.uint8)
        depth = np.ones((48, 64), dtype=np.float32)
        mapper.track_and_texture(color, depth, texture_frame=color)

        assert mapper.world.update_colors_calls == 1
        assert mapper.quality_state == "good"

    def test_lost_quality_skips_color_update(self):
        mapper = _make_mapper(quality_good_threshold=0.3, quality_degraded_threshold=0.1)
        mapper.start_scan(64, 48, 50.0, 50.0, 32.0, 24.0)
        mapper.finish_scan()
        mapper._pose_tracker.next_result = (True, np.eye(4), 0.02)  # below degraded threshold

        color = np.zeros((48, 64, 3), dtype=np.uint8)
        depth = np.ones((48, 64), dtype=np.float32)
        mapper.track_and_texture(color, depth, texture_frame=color)

        assert mapper.world.update_colors_calls == 0
        assert mapper.quality_state == "lost"

    def test_degraded_quality_still_updates_but_flags_degraded(self):
        mapper = _make_mapper(quality_good_threshold=0.3, quality_degraded_threshold=0.1)
        mapper.start_scan(64, 48, 50.0, 50.0, 32.0, 24.0)
        mapper.finish_scan()
        mapper._pose_tracker.next_result = (True, np.eye(4), 0.2)  # between thresholds

        color = np.zeros((48, 64, 3), dtype=np.uint8)
        depth = np.ones((48, 64), dtype=np.float32)
        mapper.track_and_texture(color, depth, texture_frame=color)

        assert mapper.world.update_colors_calls == 1
        assert mapper.quality_state == "degraded"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_world_mapper.py -v`
Expected: FAIL — module doesn't exist. (These tests use fakes, no open3d needed — no skip marker.)

- [ ] **Step 3: Implement**

`thermal_inspection/processing/world_mapper.py`:

```python
"""
Thin state-machine orchestrator for 3D Mapping Fusion. The only class
app.py talks to directly - owns one PoseTracker (pose_tracker.py) and one
WorldPointCloud (world_point_cloud.py), wires per-frame calls between them.
Neither of those two knows about the other or about this state machine.
"""
from __future__ import annotations

import numpy as np

from thermal_inspection.processing.pose_tracker import PoseTracker
from thermal_inspection.processing.world_point_cloud import WorldPointCloud


class WorldMapper:
    def __init__(self, voxel_size: float = 0.01,
                 quality_good_threshold: float = 0.3,
                 quality_degraded_threshold: float = 0.1,
                 pose_tracker_factory=PoseTracker,
                 world_factory=WorldPointCloud):
        self.state = "idle"
        self.tracking_quality = 0.0
        self._pose_tracker_factory = pose_tracker_factory
        self._pose_tracker = None
        self.world = world_factory(voxel_size=voxel_size)
        self._pose = np.eye(4)
        self._prev_color = None
        self._prev_depth = None
        self._quality_good = quality_good_threshold
        self._quality_degraded = quality_degraded_threshold

    def start_scan(self, width: int, height: int, fx: float, fy: float, cx: float, cy: float):
        """Begin a new scan - resets any previous world."""
        self._pose_tracker = self._pose_tracker_factory(width, height, fx, fy, cx, cy)
        self.world.reset()
        self._pose = np.eye(4)
        self._prev_color = None
        self._prev_depth = None
        self.tracking_quality = 0.0
        self.state = "scanning"

    def finish_scan(self):
        if self.state != "scanning":
            raise RuntimeError(f"finish_scan() called in state '{self.state}', expected 'scanning'")
        self.world.freeze()
        self.state = "mapped"

    def reset(self):
        self.world.reset()
        self._pose = np.eye(4)
        self.tracking_quality = 0.0
        self.state = "idle"

    def track_and_texture(self, color: np.ndarray, depth_m: np.ndarray, texture_frame: np.ndarray = None):
        """Call once per (throttled) frame. Scan phase: tracks + integrates
        geometry every call. Live phase (mapped): tracks against the frozen
        world and, if quality allows, re-textures it from texture_frame."""
        if self.state == "scanning":
            if self._prev_color is not None:
                success, transform, quality = self._pose_tracker.track_frame_to_frame(
                    color, depth_m, self._prev_color, self._prev_depth, np.eye(4)
                )
                if success:
                    self._pose = self._pose @ transform
                    self.tracking_quality = quality
            self.world.integrate(color, depth_m, self._pose_tracker.intrinsic, self._pose)
            self._prev_color, self._prev_depth = color, depth_m
        elif self.state == "mapped":
            success, transform, quality = self._pose_tracker.track_frame_to_model(
                color, depth_m, self.world.points, self.world.normals, self._pose
            )
            self.tracking_quality = quality
            if success and quality >= self._quality_degraded:
                self._pose = transform
                if texture_frame is not None:
                    self.world.update_colors(self._pose, texture_frame, self._pose_tracker.intrinsic)
        else:
            raise RuntimeError(f"track_and_texture() called in state '{self.state}', expected 'scanning' or 'mapped'")

    @property
    def point_count(self) -> int:
        return self.world.point_count

    @property
    def quality_state(self) -> str:
        if self.state != "mapped":
            return "n/a"
        if self.tracking_quality >= self._quality_good:
            return "good"
        if self.tracking_quality >= self._quality_degraded:
            return "degraded"
        return "lost"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/test_world_mapper.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add thermal_inspection/processing/world_mapper.py tests/unit/test_world_mapper.py
git commit -m "feat: add WorldMapper state-machine orchestrator"
```

---

### Task 5: `mapping_fusion_panel.py` — new settings tab

**Files:**
- Create: `thermal_inspection/gui/panels/mapping_fusion_panel.py`
- Test: `tests/unit/test_mapping_fusion_panel.py`

**Interfaces:**
- Consumes: `Fusion3DPointCloudView` from `thermal_inspection/gui/panels/fusion_3d_panel.py` (reused as-is, its `update_point_cloud(vertices, colors)` and `set_hardware_available(bool)` methods — no modification to that file).
- Produces: `MappingFusionPanel` (QWidget) with signals `start_scan_requested = pyqtSignal()`, `finish_scan_requested = pyqtSignal()`, `reset_requested = pyqtSignal()`, `texture_source_changed = pyqtSignal(str)` (values: `"thermal"`, `"rgb"`, `"blend"`), `save_requested = pyqtSignal()`, `load_requested = pyqtSignal()`, methods `set_status(state: str, quality_state: str, point_count: int)` and `update_point_cloud(vertices, colors)` (delegates to its internal `Fusion3DPointCloudView`) — consumed by `main_window.py` in Task 6. Save/Load buttons emit bare signals rather than carrying a path — `main_window.py`'s handlers own the file dialog (QFileDialog), keeping this panel free of file-system/dialog concerns, same separation of concerns this codebase applies elsewhere between a settings panel (emits intent) and main_window (owns OS-level interaction).

- [ ] **Step 1: Write the failing tests**

```python
import pytest
from PyQt6.QtWidgets import QApplication


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def test_panel_constructs(qapp):
    from thermal_inspection.gui.panels.mapping_fusion_panel import MappingFusionPanel
    panel = MappingFusionPanel()
    assert panel is not None


def test_start_button_emits_signal(qapp):
    from thermal_inspection.gui.panels.mapping_fusion_panel import MappingFusionPanel
    panel = MappingFusionPanel()
    received = []
    panel.start_scan_requested.connect(lambda: received.append(True))
    panel._start_button.click()
    assert received == [True]


def test_finish_button_emits_signal(qapp):
    from thermal_inspection.gui.panels.mapping_fusion_panel import MappingFusionPanel
    panel = MappingFusionPanel()
    received = []
    panel.finish_scan_requested.connect(lambda: received.append(True))
    panel._finish_button.click()
    assert received == [True]


def test_reset_button_emits_signal(qapp):
    from thermal_inspection.gui.panels.mapping_fusion_panel import MappingFusionPanel
    panel = MappingFusionPanel()
    received = []
    panel.reset_requested.connect(lambda: received.append(True))
    panel._reset_button.click()
    assert received == [True]


def test_texture_source_combo_emits_signal(qapp):
    from thermal_inspection.gui.panels.mapping_fusion_panel import MappingFusionPanel
    panel = MappingFusionPanel()
    received = []
    panel.texture_source_changed.connect(received.append)
    panel._texture_source_combo.setCurrentIndex(1)
    assert len(received) == 1
    assert received[0] in ("thermal", "rgb", "blend")


def test_set_status_updates_label_text(qapp):
    from thermal_inspection.gui.panels.mapping_fusion_panel import MappingFusionPanel
    panel = MappingFusionPanel()
    panel.set_status("mapped", "good", 12345)
    assert "mapped" in panel._status_label.text().lower()
    assert "12345" in panel._status_label.text() or "12,345" in panel._status_label.text()
    assert "good" in panel._status_label.text().lower()


def test_update_point_cloud_delegates_to_view(qapp):
    import numpy as np
    from thermal_inspection.gui.panels.mapping_fusion_panel import MappingFusionPanel
    panel = MappingFusionPanel()
    vertices = np.zeros((10, 3), dtype=np.float32)
    colors = np.ones((10, 4), dtype=np.float32)
    # Should not raise - actual rendering is Fusion3DPointCloudView's own
    # already-tested responsibility.
    panel.update_point_cloud(vertices, colors)


def test_save_button_emits_signal(qapp):
    from thermal_inspection.gui.panels.mapping_fusion_panel import MappingFusionPanel
    panel = MappingFusionPanel()
    received = []
    panel.save_requested.connect(lambda: received.append(True))
    panel._save_button.click()
    assert received == [True]


def test_load_button_emits_signal(qapp):
    from thermal_inspection.gui.panels.mapping_fusion_panel import MappingFusionPanel
    panel = MappingFusionPanel()
    received = []
    panel.load_requested.connect(lambda: received.append(True))
    panel._load_button.click()
    assert received == [True]


def test_set_status_shows_lost_message(qapp):
    from thermal_inspection.gui.panels.mapping_fusion_panel import MappingFusionPanel
    panel = MappingFusionPanel()
    panel.set_status("mapped", "lost", 500)
    assert "mapped area" in panel._status_label.text().lower() or "reset world" in panel._status_label.text().lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_mapping_fusion_panel.py -v`
Expected: FAIL — module doesn't exist.

- [ ] **Step 3: Implement**

`thermal_inspection/gui/panels/mapping_fusion_panel.py`:

```python
"""
3D Mapping Fusion settings tab - Start/Finish/Reset scan controls, texture-
source selector, tracking-quality status, and the live world viewport.

Reuses Fusion3DPointCloudView (fusion_3d_panel.py) as-is for rendering -
its update_point_cloud(vertices, colors) method is already fully generic
(not RealSense-alignment-specific), so this panel just feeds it the frozen
WorldPointCloud's points/colors instead of a per-frame throwaway preview
cloud. This mode's state semantics (idle/scanning/mapped, tracking
good/degraded/lost) are different enough from the existing 3D Fusion tab's
(hardware-available/thermal-aligned) that they're tracked here, in this
panel, rather than added onto Fusion3DPointCloudView itself.
"""
from __future__ import annotations

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox
)
from PyQt6.QtCore import pyqtSignal

from thermal_inspection.gui.panels.fusion_3d_panel import Fusion3DPointCloudView

TEXTURE_SOURCES = ["thermal", "rgb", "blend"]
TEXTURE_SOURCE_LABELS = {
    "thermal": "Thermal",
    "rgb": "RGB",
    "blend": "Blend",
}


class MappingFusionPanel(QWidget):
    start_scan_requested = pyqtSignal()
    finish_scan_requested = pyqtSignal()
    reset_requested = pyqtSignal()
    texture_source_changed = pyqtSignal(str)
    save_requested = pyqtSignal()
    load_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        controls = QHBoxLayout()
        self._start_button = QPushButton("Start Mapping")
        self._finish_button = QPushButton("Finish Mapping")
        self._reset_button = QPushButton("Reset World")
        self._start_button.clicked.connect(self.start_scan_requested.emit)
        self._finish_button.clicked.connect(self.finish_scan_requested.emit)
        self._reset_button.clicked.connect(self.reset_requested.emit)
        controls.addWidget(self._start_button)
        controls.addWidget(self._finish_button)
        controls.addWidget(self._reset_button)
        layout.addLayout(controls)

        persistence_row = QHBoxLayout()
        self._save_button = QPushButton("Save World...")
        self._load_button = QPushButton("Load World...")
        self._save_button.clicked.connect(self.save_requested.emit)
        self._load_button.clicked.connect(self.load_requested.emit)
        persistence_row.addWidget(self._save_button)
        persistence_row.addWidget(self._load_button)
        layout.addLayout(persistence_row)

        texture_row = QHBoxLayout()
        texture_row.addWidget(QLabel("Texture source:"))
        self._texture_source_combo = QComboBox()
        for key in TEXTURE_SOURCES:
            self._texture_source_combo.addItem(TEXTURE_SOURCE_LABELS[key], key)
        self._texture_source_combo.currentIndexChanged.connect(self._on_texture_source_changed)
        texture_row.addWidget(self._texture_source_combo)
        layout.addLayout(texture_row)

        self._status_label = QLabel("State: idle")
        layout.addWidget(self._status_label)

        self.point_cloud_view = Fusion3DPointCloudView()
        layout.addWidget(self.point_cloud_view)

    def _on_texture_source_changed(self, index: int):
        key = self._texture_source_combo.itemData(index)
        if key:
            self.texture_source_changed.emit(key)

    def set_status(self, state: str, quality_state: str, point_count: int):
        """state: 'idle'|'scanning'|'mapped'. quality_state: 'n/a'|'good'|'degraded'|'lost'."""
        text = f"State: {state}  |  Tracking: {quality_state}  |  Points: {point_count:,}"
        if quality_state == "lost":
            text += "\nTracking lost - point the camera back at a mapped area, or Reset World."
        self._status_label.setText(text)

    def update_point_cloud(self, vertices, colors):
        """Delegates straight to the embedded Fusion3DPointCloudView."""
        self.point_cloud_view.update_point_cloud(vertices, colors)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/test_mapping_fusion_panel.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add thermal_inspection/gui/panels/mapping_fusion_panel.py tests/unit/test_mapping_fusion_panel.py
git commit -m "feat: add MappingFusionPanel GUI tab for 3D Mapping Fusion"
```

---

### Task 6: Wire `ViewMode.THREE_D_MAPPING` end-to-end

**Files:**
- Modify: `thermal_inspection/core/fusion_controller.py` (add `THREE_D_MAPPING = auto()` to the `ViewMode` enum, right after `THREE_D`)
- Modify: `thermal_inspection/gui/main_window.py` — add the new tab (mirror lines ~440-444's `Fusion3DSettingsPanel` pattern), signal connections (mirror lines ~583-590's `_safe_connect` pattern), and forwarding methods (mirror lines ~2777-2796's `set_fusion_3d_hardware_available`/`update_fusion_3d_view` pattern)
- Modify: `thermal_inspection/app.py` — new `WorldMapper` instance, new dispatch branch after the existing `THREE_D` block (after line ~2247, before `elif self.view_mode == ViewMode.PICTURE_IN_PICTURE:`), and add `ViewMode.THREE_D_MAPPING` to the `_main_view_needs_thermal_rgb_alignment` tuple at line ~1567-1568 (this mode needs the same thermal-RealSense alignment 3D Fusion already uses for its texture sourcing)
- Test: `tests/unit/test_view_mode_and_pipeline_smoke.py` (this file already smoke-tests view-mode dispatch end-to-end — follow its existing fixture pattern)

**Interfaces:**
- Consumes: `WorldMapper` (Task 4), `MappingFusionPanel` (Task 5).
- Produces: nothing further downstream — this is the final integration point.

- [ ] **Step 1: Write the failing test**

Add to `tests/unit/test_view_mode_and_pipeline_smoke.py` (check its existing imports/fixtures for constructing a minimal app+fake-RealSense-camera harness before writing this — it likely already has one, given it tests `ViewMode.THREE_D` dispatch):

```python
def test_three_d_mapping_view_mode_exists():
    from thermal_inspection.core.fusion_controller import ViewMode
    assert hasattr(ViewMode, "THREE_D_MAPPING")


def test_three_d_mapping_dispatch_does_not_crash(app_with_fake_realsense):
    # Reuse whatever fixture this file already uses to construct an app
    # instance with a fake RealSense-backed RGB camera (the same one the
    # existing ViewMode.THREE_D smoke test uses) - adjust the fixture name
    # to match what's actually defined at the top of this file.
    from thermal_inspection.core.fusion_controller import ViewMode
    app = app_with_fake_realsense
    app.view_mode = ViewMode.THREE_D_MAPPING
    app._process_frame_loop()  # however this file's existing tests drive one tick
    # No assertion beyond "didn't raise" - this is a wiring smoke test,
    # not a tracking-accuracy test (that's Task 7's live-hardware pass).
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_view_mode_and_pipeline_smoke.py -v -k three_d_mapping`
Expected: FAIL — `ViewMode.THREE_D_MAPPING` doesn't exist yet.

- [ ] **Step 3: Implement**

In `thermal_inspection/core/fusion_controller.py`:

```python
class ViewMode(Enum):
    """View mode enumeration."""
    THERMAL_ONLY = auto()
    RGB_ONLY = auto()
    FUSION = auto()
    SIDE_BY_SIDE = auto()
    PICTURE_IN_PICTURE = auto()
    THREE_D = auto()  # Live RGB+thermal+depth point cloud - real hardware depth only, see Fusion3DViewWidget
    THREE_D_MAPPING = auto()  # Persistent world point cloud, built once then live-textured - see WorldMapper
```

In `thermal_inspection/app.py`, near where `self.parallax_compensator` etc. are constructed in `__init__` (find that section and add alongside it):

```python
        from thermal_inspection.processing.world_mapper import WorldMapper
        self.world_mapper = WorldMapper()
        self._mapping_texture_source = "thermal"
        # Throttle live-phase tracking+recolor the same way the existing
        # ViewMode.THREE_D block throttles its own relief-shading recompute
        # (self._3d_fusion_update_interval_s, 15Hz) - per the spec, 5-10Hz
        # is the starting point; tune against real measured frame time
        # during Task 7's live-hardware pass, don't treat 10Hz as final.
        self._mapping_fusion_update_interval_s = 1.0 / 10.0
        self._last_mapping_fusion_update_time = 0.0
```

Note: `WorldMapper()` is constructed eagerly here (unlike `RGBCameraRealSense`, which only exists once hardware is detected) because it's always safe to construct regardless of whether Open3D is installed — `WorldPointCloud.__init__` (Task 3) deliberately defers its actual `get_open3d()` call until first real use, precisely so this eager construction can't crash app startup on a machine without Open3D. `PoseTracker` (Task 2) is different: it calls `get_open3d()` in its own `__init__`, but it's only ever constructed inside `WorldMapper.start_scan()` — an explicit user action (clicking "Start Mapping"), the right point to fail loudly and catchably rather than silently. Task 6's `_on_mapping_start_scan` handler (below) must catch that `ImportError` and surface it as a status message rather than let it propagate and crash the app.

At line ~1567-1568, add the new mode to the alignment-needed tuple:

```python
            _main_view_needs_thermal_rgb_alignment = self.view_mode in (
                ViewMode.FUSION, ViewMode.THREE_D, ViewMode.THREE_D_MAPPING,
            )
```

After the existing `THREE_D` block ends (after line ~2247, before `elif self.view_mode == ViewMode.PICTURE_IN_PICTURE:`), add:

```python
            elif self.view_mode == ViewMode.THREE_D_MAPPING:
                if _rs_backend is not None and self.world_mapper.state in ("scanning", "mapped"):
                    # Throttled the same way as the existing ViewMode.THREE_D
                    # block (self._3d_fusion_update_interval_s / 15Hz) -
                    # tracking+recolor doesn't need to run faster than a
                    # human can perceive it changing, and Open3D's odometry/
                    # ICP calls are real per-frame cost. See this task's
                    # note above on tuning the interval against real
                    # hardware during Task 7.
                    _now_mapping = time.time()
                    if _now_mapping - self._last_mapping_fusion_update_time >= self._mapping_fusion_update_interval_s:
                        self._last_mapping_fusion_update_time = _now_mapping
                        depth_map = _rs_backend.get_depth_frame(resize_to=(rgb_frame.shape[1], rgb_frame.shape[0])) if rgb_frame is not None else None
                        if depth_map is not None and rgb_frame is not None:
                            texture = colorized_thermal if self._mapping_texture_source == "thermal" else rgb_frame
                            try:
                                self.world_mapper.track_and_texture(rgb_frame, depth_map, texture_frame=texture)
                            except Exception as e:
                                logger.debug(f"3D Mapping Fusion track_and_texture failed: {e}")

                            self._gui_invoke(
                                "set_mapping_fusion_status",
                                self.world_mapper.state, self.world_mapper.quality_state, self.world_mapper.point_count,
                            )
                            if self.world_mapper.state == "mapped":
                                self._gui_invoke(
                                    "update_mapping_fusion_view",
                                    self.world_mapper.world.points, self.world_mapper.world.colors,
                                )
                # Display: same RGB-only-depth-shaded fallback the existing
                # THREE_D branch uses when nothing better is available -
                # this mode's real output is the point-cloud viewport tab,
                # not the main video widget, but the main widget still needs
                # SOMETHING to show.
                display_frame = rgb_frame if rgb_frame is not None else colorized_thermal
```

In `thermal_inspection/gui/main_window.py`, mirror the existing `Fusion3DSettingsPanel` wiring (~line 440-444):

```python
            logger.info("Creating 3D Mapping Fusion settings tab...")
            from thermal_inspection.gui.panels.mapping_fusion_panel import MappingFusionPanel
            self.mapping_fusion_panel = MappingFusionPanel()
            self.right_panel_tabs.addTab(self.mapping_fusion_panel, "3D Mapping")
            logger.info("[OK] 3D Mapping Fusion settings tab added to right panel")
```

Signal connections (mirror ~line 583-590):

```python
        self._safe_connect("mapping_fusion_panel", "start_scan_requested", self._on_mapping_start_scan, "(3d mapping)")
        self._safe_connect("mapping_fusion_panel", "finish_scan_requested", self._on_mapping_finish_scan, "(3d mapping)")
        self._safe_connect("mapping_fusion_panel", "reset_requested", self._on_mapping_reset, "(3d mapping)")
        self._safe_connect("mapping_fusion_panel", "texture_source_changed", self._on_mapping_texture_source_changed, "(3d mapping)")
        self._safe_connect("mapping_fusion_panel", "save_requested", self._on_mapping_save, "(3d mapping)")
        self._safe_connect("mapping_fusion_panel", "load_requested", self._on_mapping_load, "(3d mapping)")
```

Handler + forwarding methods (mirror ~line 2777-2796's pattern — add near those). `_on_mapping_start_scan` must catch the `ImportError` `PoseTracker.__init__` raises via `get_open3d()` when Open3D isn't installed (see Task 6's note above `WorldMapper()`'s construction) rather than let it propagate:

```python
    def _on_mapping_start_scan(self):
        if hasattr(self.app_ref, 'world_mapper') and hasattr(self.app_ref, 'rgb_camera'):
            backend = getattr(self.app_ref.rgb_camera, 'backend', None)
            intrinsics = backend.get_depth_intrinsics() if backend and hasattr(backend, 'get_depth_intrinsics') else None
            if intrinsics:
                try:
                    self.app_ref.world_mapper.start_scan(
                        int(intrinsics['width']), int(intrinsics['height']),
                        intrinsics['fx'], intrinsics['fy'], intrinsics['cx'], intrinsics['cy'],
                    )
                except ImportError as e:
                    if hasattr(self, 'mapping_fusion_panel'):
                        self.mapping_fusion_panel.set_status("idle", "n/a", 0)
                        self.mapping_fusion_panel._status_label.setText(str(e))
                    logger.warning(f"3D Mapping Fusion: cannot start scan: {e}")

    def _on_mapping_finish_scan(self):
        if hasattr(self.app_ref, 'world_mapper'):
            self.app_ref.world_mapper.finish_scan()

    def _on_mapping_reset(self):
        if hasattr(self.app_ref, 'world_mapper'):
            self.app_ref.world_mapper.reset()

    def _on_mapping_texture_source_changed(self, source: str):
        if hasattr(self.app_ref, '_mapping_texture_source'):
            self.app_ref._mapping_texture_source = source

    def _on_mapping_save(self):
        """Save the frozen world to disk. Follows MediaManager's existing
        recordings-folder convention (thermal_inspection/core/media_manager.py's
        config 'output_path' entries, e.g. 'recordings/', 'snapshots/') -
        a sibling 'world_maps/' folder, created on demand rather than
        requiring it to pre-exist."""
        if not hasattr(self.app_ref, 'world_mapper') or self.app_ref.world_mapper.state != "mapped":
            return
        import os
        from PyQt6.QtWidgets import QFileDialog
        os.makedirs("world_maps", exist_ok=True)
        default_path = os.path.join("world_maps", "world.ply")
        path, _ = QFileDialog.getSaveFileName(self, "Save World", default_path, "Point Cloud (*.ply)")
        if path:
            self.app_ref.world_mapper.world.save(path)

    def _on_mapping_load(self):
        """Load a previously-saved world. Puts WorldMapper straight into
        'mapped' state - the loaded geometry is already frozen (see
        WorldPointCloud.load(), which sets frozen=True)."""
        if not hasattr(self.app_ref, 'world_mapper'):
            return
        import os
        from PyQt6.QtWidgets import QFileDialog
        os.makedirs("world_maps", exist_ok=True)
        path, _ = QFileDialog.getOpenFileName(self, "Load World", "world_maps", "Point Cloud (*.ply)")
        if path:
            self.app_ref.world_mapper.world.load(path)
            self.app_ref.world_mapper.state = "mapped"

    def set_mapping_fusion_status(self, state: str, quality_state: str, point_count: int):
        if hasattr(self, 'mapping_fusion_panel'):
            self.mapping_fusion_panel.set_status(state, quality_state, point_count)

    def update_mapping_fusion_view(self, points, colors_rgb):
        """points: (N,3) float64/float32 XYZ. colors_rgb: (N,3) float64 RGB in [0,1]
        from WorldPointCloud (Open3D convention) - Fusion3DPointCloudView.update_point_cloud
        wants (N,4) float32 RGBA in [0,1], so convert here at the GUI boundary."""
        if hasattr(self, 'mapping_fusion_panel'):
            import numpy as np
            n = colors_rgb.shape[0]
            rgba = np.ones((n, 4), dtype=np.float32)
            rgba[:, :3] = colors_rgb.astype(np.float32)
            self.mapping_fusion_panel.update_point_cloud(points.astype(np.float32), rgba)
```

Note: `_on_mapping_load` directly setting `self.app_ref.world_mapper.state = "mapped"` reaches into `WorldMapper`'s state attribute from outside rather than through a method — acceptable here since `state` is a plain public attribute (not property-guarded) and this is the one legitimate "external" state transition (loading a previously-built world skips the normal scan/finish flow entirely). If a cleaner API is preferred, add a small `WorldMapper.load_from_path(path)` method in Task 4 that does `self.world.load(path); self.state = "mapped"` internally instead — either is fine, pick one and keep it consistent with the rest of `WorldMapper`'s public surface.

Check `self.app_ref` is the actual attribute name `main_window.py` uses to reach the `ThermalInspectionApp` instance (grep for how `_on_3d_*` handlers in the existing `Fusion3DSettingsPanel` wiring reach app state, e.g. search for `self.app_ref` vs `self._app` vs a callback-based pattern — match whatever's actually there, don't assume).

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/test_view_mode_and_pipeline_smoke.py -v -k three_d_mapping`
Expected: PASS

- [ ] **Step 5: Run the full existing view-mode and 3D Fusion test suites to confirm no regression**

Run: `pytest tests/unit -k "view_mode or fusion_3d or three_d" -v`
Expected: all PASS — the existing `ViewMode.THREE_D` path must be completely untouched.

- [ ] **Step 6: Commit**

```bash
git add thermal_inspection/core/fusion_controller.py thermal_inspection/app.py thermal_inspection/gui/main_window.py tests/unit/test_view_mode_and_pipeline_smoke.py
git commit -m "feat: wire ViewMode.THREE_D_MAPPING end-to-end"
```

---

### Task 7: Manual live-hardware verification (required before calling this done)

Not a code task — a verification gate, per this session's own established practice (the L515 pyrealsense2 integration itself was held to exactly this bar before being called working).

- [ ] Install open3d in the real environment: `pip install open3d`, confirm Task 1's smoke-test script (Step 6) passes against the real library — fix any API mismatches found here first, before trusting Tasks 2-4's code.
- [ ] Launch the app with an L515 or D455 connected, switch to the new "3D Mapping" tab.
- [ ] Click Start Mapping, pan the camera around a real object/scene for a few seconds, click Finish Mapping. Confirm the point-cloud viewport shows a recognizable, densely-populated scan (not empty, not a degenerate single plane).
- [ ] Move the camera after Finish. Confirm the tracking-quality status updates sensibly (Good under normal motion) and the world's texture visibly updates to reflect what the live camera now sees, without the geometry itself changing shape.
- [ ] Deliberately move the camera very fast or cover the lens to force tracking loss. Confirm the status shows Lost, color updates pause (no visible corruption/garbage painted onto the model), and it's possible to recover by pointing back at a known part of the scene (or by using Reset World to start over if it doesn't self-recover).
- [ ] Switch texture source between Thermal/RGB/Blend, confirm the world's coloring changes accordingly.
- [ ] Save the world, restart the app, load it back, confirm geometry matches and live tracking/texturing resumes correctly.
- [ ] Switch away to a different view mode and back, confirm nothing crashes and existing `ViewMode.THREE_D` still behaves exactly as before this plan (unaffected).
- [ ] Report results back before this plan is considered complete — do not mark it done from unit tests alone.
