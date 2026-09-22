"""
Tests for thermal_inspection.app._compute_spot_distance_m - the pure-function
helper that reads an already-fetched RealSense depth map at a thermal-frame
point and returns a distance in meters (or None when unavailable/out of
range).

_compute_spot_distance_m takes the depth_map array directly (not a backend)
because the real per-frame code path in app.py fetches the depth frame
exactly ONCE per frame (rs_backend.get_depth_frame(resize_to=...)) and
passes the same array to every spot-meter point - see the spot-meter update
loop in thermal_inspection/app.py. These tests exercise the helper in
isolation (no running app instance, no Qt event loop, no real camera
plumbing, no backend object at all).
"""
import numpy as np
import pytest


def test_spot_distance_reads_depth_at_point():
    from thermal_inspection.app import _compute_spot_distance_m

    depth_map = np.full((10, 10), 1.5, dtype=np.float32)

    result = _compute_spot_distance_m(depth_map, point_x=5, point_y=5, thermal_w=10, thermal_h=10)
    assert result == pytest.approx(1.5)


def test_spot_distance_none_when_out_of_range():
    from thermal_inspection.app import _compute_spot_distance_m

    depth_map = np.full((10, 10), 50.0, dtype=np.float32)  # beyond MAX_VALID_DEPTH_M

    result = _compute_spot_distance_m(depth_map, point_x=5, point_y=5, thermal_w=10, thermal_h=10)
    assert result is None


def test_spot_distance_none_when_no_depth_frame():
    from thermal_inspection.app import _compute_spot_distance_m

    result = _compute_spot_distance_m(None, point_x=5, point_y=5, thermal_w=10, thermal_h=10)
    assert result is None


def test_spot_distance_none_when_point_out_of_bounds():
    from thermal_inspection.app import _compute_spot_distance_m

    depth_map = np.full((10, 10), 1.5, dtype=np.float32)

    result = _compute_spot_distance_m(depth_map, point_x=99, point_y=99, thermal_w=10, thermal_h=10)
    assert result is None


def _coordinate_encoded_depth_map(thermal_w: int, thermal_h: int) -> np.ndarray:
    """
    A depth map where every cell encodes its own (row, col) position, so an
    axis swap anywhere in the read chain (depth_map[y, x] vs
    depth_map[x, y], a transposed resize_to, w/h mixed up in a bounds
    check) produces a detectably wrong value instead of silently passing on
    a symmetric fixture.
    """
    depth = np.zeros((thermal_h, thermal_w), dtype=np.float32)
    for y in range(thermal_h):
        for x in range(thermal_w):
            depth[y, x] = 1.0 + y / 100.0 + x / 1000.0
    return depth


def test_spot_distance_axis_order_not_transposed():
    """
    Asymmetric (20 wide x 10 high) frame with a coordinate-encoded value at
    every cell. point_x=15, point_y=3 is only valid if width/height and
    x/y are never swapped anywhere in the chain:
      - thermal_w=20, thermal_h=10 (asymmetric - w != h)
      - depth_map shape is (thermal_h, thermal_w) = (10, 20)
      - correct read is depth_map[point_y, point_x] = depth_map[3, 15]
        = 1.0 + 3/100 + 15/1000 = 1.045
    If x/y (or w/h) were swapped anywhere, this would either read a
    different cell's value (wrong result) or index depth_map[15, 3] against
    a (10, 20) array, which raises IndexError (row index 15 >= 10 rows).
    """
    from thermal_inspection.app import _compute_spot_distance_m

    thermal_w, thermal_h = 20, 10
    depth_map = _coordinate_encoded_depth_map(thermal_w, thermal_h)

    result = _compute_spot_distance_m(
        depth_map, point_x=15, point_y=3, thermal_w=thermal_w, thermal_h=thermal_h
    )
    assert result == pytest.approx(1.045)


def test_spot_distance_bounds_check_single_axis_out_of_range():
    """
    point_x=15 is out of range against thermal_w=10 (x-axis violation);
    point_y=5 is in range against thermal_h=20 (y-axis is fine). Only
    catches an axis-swapped bounds check (e.g. comparing point_x against
    thermal_h and point_y against thermal_w) - a swapped check would see
    15 < 20 and 5 < 10, both true, and incorrectly return a reading instead
    of None.
    """
    from thermal_inspection.app import _compute_spot_distance_m

    thermal_w, thermal_h = 10, 20
    depth_map = _coordinate_encoded_depth_map(thermal_w, thermal_h)

    result = _compute_spot_distance_m(
        depth_map, point_x=15, point_y=5, thermal_w=thermal_w, thermal_h=thermal_h
    )
    assert result is None
