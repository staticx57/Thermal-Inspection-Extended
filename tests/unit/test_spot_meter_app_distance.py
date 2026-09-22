"""
Tests for thermal_inspection.app._compute_spot_distance_m - the pure-function
helper that reads a RealSense depth frame at a thermal-frame point and
returns a distance in meters (or None when unavailable/out of range).

These exercise the helper in isolation (no running app instance, no Qt
event loop, no real camera plumbing) with duck-typed fake RealSense
backends, matching the style of tests/unit/test_realsense_camera.py.
"""
import pytest


def test_spot_distance_reads_depth_at_point():
    from thermal_inspection.app import _compute_spot_distance_m

    class FakeRealSenseBackend:
        def get_depth_frame(self, resize_to=None):
            import numpy as np
            w, h = resize_to
            depth = np.full((h, w), 1.5, dtype=np.float32)
            return depth

    result = _compute_spot_distance_m(FakeRealSenseBackend(), point_x=5, point_y=5, thermal_w=10, thermal_h=10)
    assert result == pytest.approx(1.5)


def test_spot_distance_none_when_out_of_range():
    from thermal_inspection.app import _compute_spot_distance_m

    class FakeRealSenseBackend:
        def get_depth_frame(self, resize_to=None):
            import numpy as np
            w, h = resize_to
            return np.full((h, w), 50.0, dtype=np.float32)  # beyond MAX_VALID_DEPTH_M

    result = _compute_spot_distance_m(FakeRealSenseBackend(), point_x=5, point_y=5, thermal_w=10, thermal_h=10)
    assert result is None


def test_spot_distance_none_when_no_depth_frame():
    from thermal_inspection.app import _compute_spot_distance_m

    class FakeRealSenseBackend:
        def get_depth_frame(self, resize_to=None):
            return None

    result = _compute_spot_distance_m(FakeRealSenseBackend(), point_x=5, point_y=5, thermal_w=10, thermal_h=10)
    assert result is None


def test_spot_distance_none_when_point_out_of_bounds():
    from thermal_inspection.app import _compute_spot_distance_m

    class FakeRealSenseBackend:
        def get_depth_frame(self, resize_to=None):
            import numpy as np
            w, h = resize_to
            return np.full((h, w), 1.5, dtype=np.float32)

    result = _compute_spot_distance_m(FakeRealSenseBackend(), point_x=99, point_y=99, thermal_w=10, thermal_h=10)
    assert result is None
