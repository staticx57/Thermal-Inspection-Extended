"""
Regression test tied to a live performance investigation (2026-09-04):
a user reported the app pinned at <12fps in a specific settings state
(3D Fusion tab, multiband isotherm active). IsothermBandManager.
apply_bands_to_frame() was the prime suspect - it runs once per
enabled band (a typical preset has 5-6), completely unthrottled, and
had zero profiling instrumentation, so it never showed up in any
PROFILE_* log despite being a real contender for the missing
~50ms/frame.

A rewrite to a full-frame np.where() (mirroring the fix already
applied to fusion_processor's _thermal_overlay/_enhanced_edge_highlight)
was tried and measured SLOWER (97ms/call vs 44ms/call) - isotherm bands
are narrow temperature ranges covering a small fraction of the frame,
unlike those full-coverage overlays, so the original fancy-index
gather/scatter's O(masked pixels) cost beats a full-frame O(all
pixels) blend here. Reverted; app.py now has PROFILE_ISOTHERM
instrumentation on this call so its real per-frame cost is visible
going forward instead of hiding inside the unattributed "preprocess"
stage bucket. These tests lock in correctness and give a generous
regression ceiling, not a specific improvement claim.
"""
import time
import numpy as np
import pytest

from thermal_inspection.processing.isotherm_bands import (
    IsothermBandManager, ISOTHERM_PRESETS, load_preset,
)


def _naive_apply_bands_to_frame(manager: IsothermBandManager, thermal_frame, temp_map):
    """Independent reimplementation of the same fancy-indexing blend,
    to check apply_bands_to_frame's output against a second source
    rather than just calling it twice."""
    output = thermal_frame.copy()
    for band in manager.bands:
        if not band.enabled:
            continue
        if band.mode == 'between':
            mask = (temp_map >= band.low_temp) & (temp_map <= band.high_temp)
        elif band.mode == 'above':
            mask = temp_map > band.high_temp
        elif band.mode == 'below':
            mask = temp_map < band.low_temp
        else:
            continue
        if np.any(mask):
            b, g, r = band.color[2], band.color[1], band.color[0]
            alpha = 0.5
            output[mask] = (
                alpha * np.array([b, g, r], dtype=np.uint8) +
                (1 - alpha) * output[mask]
            ).astype(np.uint8)
    return output


class TestIsothermBandsCorrectness:
    def test_multiband_output_matches_naive_fancy_index_reference(self):
        """The fast np.where rewrite must produce bit-identical output
        to the original fancy-indexing approach."""
        rng = np.random.default_rng(7)
        thermal_frame = rng.integers(0, 255, size=(512, 640, 3), dtype=np.uint8)
        temp_map = rng.uniform(-40, 100, size=(512, 640)).astype(np.float32)

        manager = IsothermBandManager()
        load_preset(manager, "temperature_zones")  # 6 overlapping bands

        fast_result = manager.apply_bands_to_frame(thermal_frame, temp_map)
        naive_result = _naive_apply_bands_to_frame(manager, thermal_frame, temp_map)

        assert np.array_equal(fast_result, naive_result), (
            "np.where rewrite must be numerically identical to the "
            "original fancy-indexing blend, not just visually similar"
        )

    def test_disabled_band_is_skipped(self):
        thermal_frame = np.zeros((100, 100, 3), dtype=np.uint8)
        temp_map = np.full((100, 100), 50.0, dtype=np.float32)
        manager = IsothermBandManager()
        band_id = manager.add_band("Hot", 40, 60, (255, 0, 0), mode='between')
        manager.update_band(band_id, enabled=False)

        result = manager.apply_bands_to_frame(thermal_frame, temp_map)
        assert np.array_equal(result, thermal_frame)

    def test_single_band_blend_math(self):
        """Sanity-check the actual blend values against hand computation."""
        thermal_frame = np.zeros((4, 4, 3), dtype=np.uint8)  # all black
        temp_map = np.full((4, 4), 50.0, dtype=np.float32)
        manager = IsothermBandManager()
        manager.add_band("Hot", 40, 60, (255, 0, 0), mode='between')  # RGB red

        result = manager.apply_bands_to_frame(thermal_frame, temp_map)
        # RGB (255,0,0) -> BGR (0,0,255); alpha=0.5 blend with black base
        expected_pixel = np.array([0, 0, 127], dtype=np.uint8)  # 0.5*255=127.5 -> truncates to 127
        assert np.all(result == expected_pixel)


class TestIsothermBandsPerf:
    def test_multiband_preset_does_not_regress_further(self):
        """Not a speed win (see module docstring) - just a ceiling so a
        future change doesn't make this call even slower without
        anyone noticing, now that PROFILE_ISOTHERM makes its real cost
        visible in the live app."""
        rng = np.random.default_rng(3)
        thermal_frame = rng.integers(0, 255, size=(512, 640, 3), dtype=np.uint8)
        temp_map = rng.uniform(-40, 100, size=(512, 640)).astype(np.float32)

        manager = IsothermBandManager()
        load_preset(manager, "temperature_zones")  # 6 bands, full-range coverage

        manager.apply_bands_to_frame(thermal_frame, temp_map)  # warm up

        n = 20
        t0 = time.perf_counter()
        for _ in range(n):
            manager.apply_bands_to_frame(thermal_frame, temp_map)
        elapsed_ms = (time.perf_counter() - t0) * 1000 / n

        assert elapsed_ms < 80.0, (
            f"apply_bands_to_frame averaged {elapsed_ms:.2f}ms/call across "
            f"{n} calls with a 6-band preset - measured baseline was "
            "~44ms/call, this is a regression ceiling not a target"
        )
