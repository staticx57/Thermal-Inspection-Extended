"""
Regression test for a major perf finding (2026-09-04): _thermal_overlay
is fusion_processor's DEFAULT mode (fusion_priority defaults to
'thermal', and it's what nearly every live session in this project has
actually run in FUSION view) - profiled at mean=20.4ms/call with wild
variance (6.8-40ms) even though an earlier fix had already moved it off
boolean-mask fancy indexing onto np.repeat + np.where. That variance
was allocator churn: np.repeat allocates a full (H,W,3) bool array,
np.where then allocates the full result array, every single call.

Fixed with cv2.copyTo(blended, mask, result) - "blended where mask,
else base" in one optimized in-place C op, no repeat and no second
full-array allocation for the select itself. Verified bit-identical
against the previous implementation.
"""
import time
import numpy as np
import cv2

from thermal_inspection.processing.fusion_processor import FusionProcessor


def _reference_repeat_where(fp, thermal, rgb):
    """Reproduces the previous (pre-cv2.copyTo) implementation exactly,
    to prove the new one is numerically identical, not just visually
    similar."""
    if fp.fusion_priority == 'rgb':
        thermal_gray = cv2.cvtColor(thermal, cv2.COLOR_BGR2GRAY)
        threshold = np.percentile(thermal_gray, 70)
        hot_mask = thermal_gray > threshold
        blended = cv2.addWeighted(thermal, fp.fusion_intensity, rgb, 1.0 - fp.fusion_intensity, 0)
        return np.where(np.repeat(hot_mask[:, :, np.newaxis], 3, axis=2), blended, rgb)
    else:
        rgb_gray = cv2.cvtColor(rgb, cv2.COLOR_BGR2GRAY)
        threshold = np.percentile(rgb_gray, 70)
        bright_mask = rgb_gray > threshold
        blended = cv2.addWeighted(rgb, fp.fusion_intensity, thermal, 1.0 - fp.fusion_intensity, 0)
        return np.where(np.repeat(bright_mask[:, :, np.newaxis], 3, axis=2), blended, thermal)


class TestThermalOverlayCorrectness:
    def test_thermal_priority_matches_reference(self):
        fp = FusionProcessor()
        fp.fusion_priority = 'thermal'
        rng = np.random.default_rng(5)
        thermal = rng.integers(0, 255, size=(512, 640, 3), dtype=np.uint8)
        rgb = rng.integers(0, 255, size=(512, 640, 3), dtype=np.uint8)

        result = fp._thermal_overlay(thermal, rgb)
        reference = _reference_repeat_where(fp, thermal, rgb)
        assert np.array_equal(result, reference)

    def test_rgb_priority_matches_reference(self):
        fp = FusionProcessor()
        fp.fusion_priority = 'rgb'
        rng = np.random.default_rng(6)
        thermal = rng.integers(0, 255, size=(512, 640, 3), dtype=np.uint8)
        rgb = rng.integers(0, 255, size=(512, 640, 3), dtype=np.uint8)

        result = fp._thermal_overlay(thermal, rgb)
        reference = _reference_repeat_where(fp, thermal, rgb)
        assert np.array_equal(result, reference)

    def test_does_not_mutate_inputs(self):
        """result = base.copy() then cv2.copyTo into it - must never
        touch the original thermal/rgb arrays the caller passed in."""
        fp = FusionProcessor()
        rng = np.random.default_rng(7)
        thermal = rng.integers(0, 255, size=(256, 256, 3), dtype=np.uint8)
        rgb = rng.integers(0, 255, size=(256, 256, 3), dtype=np.uint8)
        thermal_before = thermal.copy()
        rgb_before = rgb.copy()

        fp._thermal_overlay(thermal, rgb)

        assert np.array_equal(thermal, thermal_before)
        assert np.array_equal(rgb, rgb_before)


class TestThermalOverlayPerf:
    def test_completes_quickly_and_consistently(self):
        """Locks in the actual performance win - loose bound to avoid
        CI flakiness. Measured baseline: mean=20.4ms, max=40.1ms."""
        fp = FusionProcessor()
        rng = np.random.default_rng(8)
        thermal = rng.integers(0, 255, size=(512, 640, 3), dtype=np.uint8)
        rgb = rng.integers(0, 255, size=(512, 640, 3), dtype=np.uint8)

        fp._thermal_overlay(thermal, rgb)  # warm up

        n = 30
        t0 = time.perf_counter()
        for _ in range(n):
            fp._thermal_overlay(thermal, rgb)
        elapsed_ms = (time.perf_counter() - t0) * 1000 / n

        assert elapsed_ms < 16.0, (
            f"_thermal_overlay averaged {elapsed_ms:.2f}ms/call across "
            f"{n} calls - expected well under the pre-fix ~20.4ms mean"
        )
