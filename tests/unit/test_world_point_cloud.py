import numpy as np
import pytest
import tempfile
import os
from thermal_inspection.processing.open3d_support import OPEN3D_AVAILABLE

# NOTE: a module-level `pytestmark` would skip every test in this file,
# including the ungated safety test at the bottom (pytest applies
# module-level pytestmark to ALL items in the module, not just the classes
# above it). So the skipif is applied per-class below instead, and the
# standalone test at the end is left deliberately unmarked.
_requires_open3d = pytest.mark.skipif(not OPEN3D_AVAILABLE, reason="open3d not installed")


def _flat_frame(w=32, h=24, depth_value=1.0):
    color = np.full((h, w, 3), 128, dtype=np.uint8)
    depth = np.full((h, w), depth_value, dtype=np.float32)
    return color, depth


def _intrinsic(w=32, h=24):
    from thermal_inspection.processing.open3d_support import get_open3d
    o3d = get_open3d()
    return o3d.camera.PinholeCameraIntrinsic(w, h, 30.0, 30.0, w / 2, h / 2)


@_requires_open3d
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


@_requires_open3d
class TestFreeze:
    def test_freeze_computes_normals(self):
        from thermal_inspection.processing.world_point_cloud import WorldPointCloud
        world = WorldPointCloud(voxel_size=0.01)
        color, depth = _flat_frame()
        world.integrate(color, depth, _intrinsic(), np.eye(4))
        world.freeze()
        assert world.frozen
        assert world.normals.shape[0] == world.point_count


@_requires_open3d
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


@_requires_open3d
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


@_requires_open3d
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
