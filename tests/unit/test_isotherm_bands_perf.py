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
was tried and measured SLOWER (97ms/call vs 44ms/call) at the time -
isotherm bands were assumed to be narrow temperature ranges covering a
small fraction of the frame, unlike those full-coverage overlays, so
the fancy-index gather/scatter's O(masked pixels) cost beat a
full-frame O(all pixels) blend. Reverted at the time.

Later found (2026-09-07 pipeline characterization) that this
assumption doesn't hold for the actually-shipped presets:
temperature_zones' 6 bands are contiguous and jointly cover the
ENTIRE temperature range, so "narrow range, small fraction of frame"
was never true for the app's own default config once its second bug
(see test_core_managers.py's TestIsothermManager multiband-unit-fix
tests) was fixed and the bands actually started rendering. Rewritten
to build one full-frame solid-color "paint layer" per call (still
O(masked pixels) per band) and composite it in a single
cv2.addWeighted, mirroring the thermal_contours fill fix's own
finding that one fused cv2 call beats N separate numpy blends even at
full-frame size. Measured ~3.1-3.4x faster on the 6-band preset,
confirmed via an interleaved comparison against the original
implementation (to cancel out unrelated machine load) rather than
two isolated timings.

Two small, intentional behavior changes versus the original
per-band-blend (both documented on apply_bands_to_frame itself):
overlapping bands now have the later band's color win outright
instead of compounding two blends together, and cv2.addWeighted
rounds where the old per-channel astype(uint8) truncated (max 1 LSB
difference). Neither is visible on any preset this app ships - the
presets are contiguous, not overlapping - so the tests below assert
the NEW behavior directly rather than pinning the old truncating
reference.
"""
import time
import numpy as np
import cv2
import pytest

from thermal_inspection.processing.isotherm_bands import (
    IsothermBandManager, ISOTHERM_PRESETS, load_preset,
)


def _naive_old_apply_bands_to_frame(manager: IsothermBandManager, thermal_frame, temp_map):
    """The ORIGINAL per-band fancy-indexing blend (pre-2026-09-07
    rewrite), kept only so the new implementation's max-deviation from
    it can be pinned to what the docstring promises (<=1 LSB, no
    compounding difference on non-overlapping bands) - not used as a
    bit-exact reference any more, since the two are no longer meant to
    agree bit-for-bit."""
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
    def test_matches_old_implementation_within_one_lsb_on_shipped_preset(self):
        """The shipped temperature_zones preset is contiguous (not
        overlapping), so the rewrite's only possible divergence from the
        old blend is the truncate-vs-round difference - never more than
        1 LSB per channel, and only on pixels an enabled band actually
        touches."""
        rng = np.random.default_rng(7)
        thermal_frame = rng.integers(0, 255, size=(512, 640, 3), dtype=np.uint8)
        temp_map = rng.uniform(-40, 100, size=(512, 640)).astype(np.float32)

        manager = IsothermBandManager()
        load_preset(manager, "temperature_zones")  # 6 contiguous bands

        new_result = manager.apply_bands_to_frame(thermal_frame, temp_map)
        old_result = _naive_old_apply_bands_to_frame(manager, thermal_frame, temp_map)

        diff = cv2.absdiff(new_result, old_result)
        assert diff.max() <= 1, (
            f"expected at most a 1 LSB rounding difference vs the old "
            f"truncating blend on a non-overlapping preset, got max diff {diff.max()}"
        )

    def test_overlapping_bands_let_the_later_band_win(self):
        """Documented behavior change: two bands covering the same
        temperature now composite as an override (later band's color),
        not a compounded double-blend of both colors."""
        thermal_frame = np.zeros((4, 4, 3), dtype=np.uint8)
        temp_map = np.full((4, 4), 25.0, dtype=np.float32)

        manager = IsothermBandManager()
        manager.add_band("A", 20, 30, (255, 0, 0), mode='between')  # first, red
        manager.add_band("B", 20, 30, (0, 255, 0), mode='between')  # later, green - should win

        result = manager.apply_bands_to_frame(thermal_frame, temp_map)
        expected = cv2.addWeighted(
            thermal_frame, 0.5,
            np.full((4, 4, 3), (0, 255, 0), dtype=np.uint8), 0.5, 0,
        )
        assert np.array_equal(result, expected)

    def test_disabled_band_is_skipped(self):
        thermal_frame = np.zeros((100, 100, 3), dtype=np.uint8)
        temp_map = np.full((100, 100), 50.0, dtype=np.float32)
        manager = IsothermBandManager()
        band_id = manager.add_band("Hot", 40, 60, (255, 0, 0), mode='between')
        manager.update_band(band_id, enabled=False)

        result = manager.apply_bands_to_frame(thermal_frame, temp_map)
        assert np.array_equal(result, thermal_frame)
        assert result is not thermal_frame, "must return a copy, not the same object, even as a no-op"

    def test_single_band_blend_math(self):
        """Sanity-check the actual blend values against hand computation."""
        thermal_frame = np.zeros((4, 4, 3), dtype=np.uint8)  # all black
        temp_map = np.full((4, 4), 50.0, dtype=np.float32)
        manager = IsothermBandManager()
        manager.add_band("Hot", 40, 60, (255, 0, 0), mode='between')  # RGB red

        result = manager.apply_bands_to_frame(thermal_frame, temp_map)
        # RGB (255,0,0) -> BGR (0,0,255); alpha=0.5 blend with black base.
        # 0.5*255 = 127.5 exactly - cv2.addWeighted's saturate_cast rounds
        # this to 128 (the old per-channel astype(uint8) truncated to 127).
        expected_pixel = np.array([0, 0, 128], dtype=np.uint8)
        assert np.all(result == expected_pixel)


class TestIsothermBandsPerf:
    def test_multiband_preset_is_faster_than_the_old_implementation(self):
        """This IS now a speed win (unlike when this test was first
        written - see module docstring): the shipped 6-band preset
        covers the whole frame, so the old per-band-blend's "narrow
        range" assumption never held for it. Compares interleaved
        against the original per-band blend rather than a fixed ms
        threshold, so the assertion holds regardless of the machine's
        absolute speed or background load."""
        rng = np.random.default_rng(3)
        thermal_frame = rng.integers(0, 255, size=(512, 640, 3), dtype=np.uint8)
        temp_map = rng.uniform(-40, 100, size=(512, 640)).astype(np.float32)

        manager = IsothermBandManager()
        load_preset(manager, "temperature_zones")  # 6 bands, full-range coverage

        manager.apply_bands_to_frame(thermal_frame, temp_map)  # warm up
        _naive_old_apply_bands_to_frame(manager, thermal_frame, temp_map)

        n = 15
        old_times, new_times = [], []
        for _ in range(n):
            t0 = time.perf_counter()
            _naive_old_apply_bands_to_frame(manager, thermal_frame, temp_map)
            old_times.append(time.perf_counter() - t0)

            t0 = time.perf_counter()
            manager.apply_bands_to_frame(thermal_frame, temp_map)
            new_times.append(time.perf_counter() - t0)

        old_median = sorted(old_times)[n // 2]
        new_median = sorted(new_times)[n // 2]
        assert new_median < old_median * 0.7, (
            f"expected a meaningful speedup over the old per-band blend - "
            f"old={old_median*1000:.2f}ms new={new_median*1000:.2f}ms"
        )
