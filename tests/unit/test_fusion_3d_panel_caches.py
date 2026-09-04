"""
Unit tests for two module-level caches in fusion_3d_panel.py, both fixed
during a general best-practices self-audit (2026-09-03):

- _get_turbo_lut_gpu used a single unkeyed global - a second device would
  silently get back a LUT tensor built for the FIRST device ever seen.
  Now keyed by device.
- _compute_motion_normalized_cpu's previous-frame cache used to be a dict
  keyed by frame shape that never evicted (a session that changes
  resolution repeatedly accumulates one stale full-frame array per
  resolution forever). Now holds only the single most recent (shape,
  frame) pair, and treats a shape change as "no previous frame" rather
  than looking up (and never evicting) a per-shape entry.
"""
import numpy as np
import pytest

import thermal_inspection.gui.panels.fusion_3d_panel as fusion_3d_panel

torch = pytest.importorskip("torch")


@pytest.mark.unit
def test_turbo_lut_cached_per_device_not_globally():
    fusion_3d_panel._turbo_lut_gpu_cache.clear()

    lut_cpu_1 = fusion_3d_panel._get_turbo_lut_gpu("cpu")
    lut_cpu_2 = fusion_3d_panel._get_turbo_lut_gpu("cpu")
    assert lut_cpu_1 is lut_cpu_2, "same device must reuse the cached tensor"

    lut_meta = fusion_3d_panel._get_turbo_lut_gpu("meta")
    assert lut_meta is not lut_cpu_1, (
        "a different device must get its OWN cached tensor, not the first device's"
    )
    assert lut_cpu_1.device.type == "cpu"
    assert lut_meta.device.type == "meta"


@pytest.mark.unit
class TestMotionNormalizedCache:

    def setup_method(self):
        fusion_3d_panel._fog_motion_prev = None

    def teardown_method(self):
        fusion_3d_panel._fog_motion_prev = None

    def test_first_call_has_no_motion(self):
        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        result = fusion_3d_panel._compute_motion_normalized_cpu(frame)
        assert np.all(result == 0)

    def test_detects_real_frame_to_frame_change(self):
        frame1 = np.zeros((100, 100, 3), dtype=np.uint8)
        frame2 = np.full((100, 100, 3), 80, dtype=np.uint8)
        fusion_3d_panel._compute_motion_normalized_cpu(frame1)
        result = fusion_3d_panel._compute_motion_normalized_cpu(frame2)
        assert np.all(result > 0)

    def test_shape_change_treated_as_no_previous_frame(self):
        """A resolution change must not compare against a stale
        differently-shaped frame - it should reset cleanly instead."""
        frame_a = np.full((100, 100, 3), 200, dtype=np.uint8)
        frame_b = np.zeros((50, 50, 3), dtype=np.uint8)
        fusion_3d_panel._compute_motion_normalized_cpu(frame_a)
        result = fusion_3d_panel._compute_motion_normalized_cpu(frame_b)
        assert result.shape == (50, 50)
        assert np.all(result == 0)

    def test_only_holds_the_single_most_recent_frame(self):
        """Regression guard for the unbounded per-shape dict this used
        to be - after several different shapes, state must still be a
        single (shape, frame) pair, not an ever-growing collection."""
        for size in (10, 20, 30, 10, 20):
            fusion_3d_panel._compute_motion_normalized_cpu(
                np.zeros((size, size, 3), dtype=np.uint8)
            )
        assert isinstance(fusion_3d_panel._fog_motion_prev, tuple)
        assert len(fusion_3d_panel._fog_motion_prev) == 2
