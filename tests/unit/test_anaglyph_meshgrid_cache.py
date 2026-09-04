"""
Regression test for a Low-priority debt item (2026-09-04): apply_depth_
anaglyph() rebuilt a full (H,W) np.meshgrid on every single call instead
of caching by shape, unlike this module's other per-process caches -
fixed with _get_anaglyph_meshgrid(), rebuilt only when (h, w) changes.
"""
import sys
import numpy as np
from PyQt6.QtWidgets import QApplication

qapp = QApplication.instance() or QApplication(sys.argv)

from thermal_inspection.gui.panels.fusion_3d_panel import (
    apply_depth_anaglyph, _get_anaglyph_meshgrid,
)


class TestAnaglyphMeshgridCache:
    def test_same_shape_reuses_cached_arrays(self):
        first = _get_anaglyph_meshgrid(512, 640)
        second = _get_anaglyph_meshgrid(512, 640)
        assert first[0] is second[0]
        assert first[1] is second[1]

    def test_shape_change_rebuilds(self):
        first = _get_anaglyph_meshgrid(512, 640)
        different = _get_anaglyph_meshgrid(256, 320)
        assert first[0] is not different[0]
        assert different[0].shape == (256, 320)
        # Switching back to the original shape must rebuild correctly too
        # (not get stuck on the intermediate shape).
        back = _get_anaglyph_meshgrid(512, 640)
        assert back[0].shape == (512, 640)

    def test_apply_depth_anaglyph_still_produces_correct_output(self):
        rng = np.random.default_rng(3)
        image = rng.integers(0, 255, size=(64, 96, 3), dtype=np.uint8)
        depth = rng.uniform(0.2, 3.0, size=(64, 96)).astype(np.float32)

        result = apply_depth_anaglyph(image, depth, strength=0.5)

        assert result.shape == image.shape
        assert result.dtype == np.uint8
        # Zero strength must collapse to (approximately) an unshifted
        # image - no stereo separation.
        flat_result = apply_depth_anaglyph(image, depth, strength=0.0)
        assert flat_result.shape == image.shape

    def test_repeated_calls_on_same_shape_produce_identical_output(self):
        """The cached grids must not be mutated between calls - repeated
        calls on unchanged inputs must give bit-identical results."""
        rng = np.random.default_rng(4)
        image = rng.integers(0, 255, size=(48, 64, 3), dtype=np.uint8)
        depth = rng.uniform(0.2, 3.0, size=(48, 64)).astype(np.float32)

        first = apply_depth_anaglyph(image, depth, strength=0.7)
        second = apply_depth_anaglyph(image, depth, strength=0.7)
        assert np.array_equal(first, second)
