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
