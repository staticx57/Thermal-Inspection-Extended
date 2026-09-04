"""
Regression test for a major performance bug found during a systematic
rendering-performance investigation (2026-09-03): FusionProcessor's
thermal_contours mode thresholded raw (unblurred) thermal data at 8
levels before calling cv2.findContours/drawContours. A thermal sensor's
per-pixel read noise thresholded directly produces a "salt and pepper"
binary pattern with an enormous number of tiny disconnected contours -
findContours' cost scales with contour count/boundary complexity, not
just pixel count. Measured live: pure noise cost ~920-1400ms/frame at
512x640 (216k contours found) - effectively freezing the app if this
mode were selected on a noisy scene, and even smooth/realistic thermal
data cost ~115-160ms/frame, an order of magnitude slower than every
other fusion mode (~18-40ms).

Fixed with a light Gaussian blur before thresholding (removes
single-pixel noise while preserving genuine temperature-boundary edges,
the mode's actual purpose) plus a minimum contour-area filter (skips
specks invisible at the mode's fixed 2px line width anyway). Measured
after the fix: realistic thermal-like data dropped to ~17-24ms/frame,
matching every other mode; the pathological pure-noise worst case
dropped to ~140-200ms - not fully fixed for that unrealistic input, but
no longer freezes the app for a full second.
"""
import time

import cv2
import numpy as np
import pytest

from thermal_inspection.processing.fusion_processor import FusionProcessor


@pytest.mark.unit
@pytest.mark.slow
def test_thermal_contours_completes_quickly_even_on_pure_noise():
    """The pathological worst case: no blur/filter took ~920-1400ms here
    before the fix. 300ms is a generous bound - well above the ~140-200ms
    measured after the fix, well below the ~920ms+ measured before it."""
    rng = np.random.default_rng(0)
    thermal = rng.integers(0, 255, size=(512, 640, 3), dtype=np.uint8)
    rgb = rng.integers(0, 255, size=(512, 640, 3), dtype=np.uint8)
    processor = FusionProcessor(fusion_mode="thermal_contours")

    t0 = time.perf_counter()
    result = processor.process(thermal, rgb)
    elapsed_ms = (time.perf_counter() - t0) * 1000

    assert result is not None
    assert elapsed_ms < 300, f"thermal_contours took {elapsed_ms:.0f}ms on noisy input, expected < 300ms"


@pytest.mark.unit
def test_thermal_contours_still_detects_real_temperature_bands():
    """Correctness check for the blur + area filter: a frame with a few
    large, well-defined temperature bands must still produce a visibly
    different, non-trivial contour overlay - the fix must not blur away
    or area-filter out genuine temperature boundaries, only noise."""
    h, w = 512, 640
    yy, xx = np.mgrid[0:h, 0:w]
    # Three large, sharply-separated horizontal bands - unambiguous
    # boundaries a long way past the noise-scale the blur/filter target.
    thermal_gray = np.where(yy < h // 3, 30, np.where(yy < 2 * h // 3, 140, 250)).astype(np.uint8)
    thermal = cv2.cvtColor(thermal_gray, cv2.COLOR_GRAY2BGR)
    rgb = np.full((h, w, 3), 128, dtype=np.uint8)

    processor = FusionProcessor(fusion_mode="thermal_contours")
    result = processor.process(thermal, rgb)

    assert result is not None
    assert result.shape == rgb.shape
    # The result must differ from the plain rgb base - i.e. something
    # was actually drawn on top of it.
    assert not np.array_equal(result, rgb)
