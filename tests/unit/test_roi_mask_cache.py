"""
Regression test for a Low-priority debt item (2026-09-04): ROI.get_mask()
allocated a fresh full-frame mask array and redrew it via cv2 on every
single call, even though ROI geometry rarely changes between calls -
unlike this codebase's usual pattern for per-process constant lookups.
Fixed with a cache keyed by (shape, points, roi_type), invalidated
whenever any of those actually change.
"""
import numpy as np

from thermal_inspection.processing.roi_manager import ROI, ROIType, ROISource


def _make_roi(roi_type=ROIType.RECTANGLE, points=None):
    return ROI(
        roi_id="test_roi",
        roi_type=roi_type,
        roi_source=ROISource.MANUAL,
        points=points if points is not None else [(10, 10), (50, 50)],
    )


class TestROIMaskCache:
    def test_same_shape_and_geometry_returns_cached_array(self):
        roi = _make_roi()
        first = roi.get_mask((100, 100))
        second = roi.get_mask((100, 100))
        assert first is second

    def test_shape_change_invalidates_cache(self):
        roi = _make_roi()
        first = roi.get_mask((100, 100))
        second = roi.get_mask((200, 200))
        assert first is not second
        assert second.shape == (200, 200)

    def test_points_change_invalidates_cache(self):
        roi = _make_roi()
        first = roi.get_mask((100, 100))
        roi.points = [(20, 20), (60, 60)]
        second = roi.get_mask((100, 100))
        assert first is not second
        assert not np.array_equal(first, second)

    def test_roi_type_change_invalidates_cache(self):
        roi = _make_roi(roi_type=ROIType.RECTANGLE, points=[(10, 10), (50, 50)])
        first = roi.get_mask((100, 100))
        roi.roi_type = ROIType.ELLIPSE
        second = roi.get_mask((100, 100))
        assert first is not second

    def test_mask_content_matches_uncached_rectangle(self):
        roi = _make_roi(roi_type=ROIType.RECTANGLE, points=[(10, 10), (50, 50)])
        mask = roi.get_mask((100, 100))
        # Inside the rectangle
        assert mask[30, 30] == 255
        # Outside the rectangle
        assert mask[5, 5] == 0

    def test_empty_points_returns_and_caches_a_blank_mask(self):
        roi = _make_roi(points=[])
        first = roi.get_mask((50, 50))
        second = roi.get_mask((50, 50))
        assert first is second
        assert not np.any(first)
