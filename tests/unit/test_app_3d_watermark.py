"""
Unit test for ThermalInspectionApp._watermark_3d_rgb_only - the on-frame
label added for the THREE_D view's silent RGB-only fallback (see High #1
in the debt ledger: this fallback used to give zero visual feedback that
thermal had dropped out of the 3D Fusion view).
"""
import numpy as np
import pytest

from thermal_inspection.app import ThermalInspectionApp


@pytest.mark.unit
def test_watermark_draws_without_mutating_input():
    frame = np.zeros((100, 300, 3), dtype=np.uint8)
    original = frame.copy()

    result = ThermalInspectionApp._watermark_3d_rgb_only(frame)

    assert result.shape == frame.shape
    assert result.dtype == frame.dtype
    np.testing.assert_array_equal(frame, original)
    assert not np.array_equal(result, frame), "watermark must actually change pixel data"
