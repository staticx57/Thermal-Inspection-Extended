"""
Smoke tests for FusionProcessor - the main render-loop fusion engine
(processing/fusion_processor.py, 1142 lines), which had zero test coverage.

These are deliberately shallow: for every mode FusionProcessor.get_available_modes()
advertises, process() must run without raising and return a frame of the
correct shape/dtype. This is not a check that any given algorithm is visually
"correct" - it's a floor that catches an algorithm crashing outright or
silently returning garbage-shaped output, which unit tests can catch cheaply
and a human staring at a live video feed would eventually notice, just much
later and with less specific information.

Note: process()'s own if/elif chain also handles 'detail_inject' and
'relief_fusion' (in fusion_processor.py's implementation), but neither is
in get_available_modes()'s return list, so neither is exercised here or
reachable via set_fusion_mode()/the GUI dropdown/get_available_modes()
consumers - only via directly constructing FusionProcessor(fusion_mode=...)
or setting .fusion_mode directly. That inconsistency is a separate, existing
finding, not something this test suite should paper over by inventing extra
coverage for a mode nothing can actually select through the normal API.
"""
import cv2
import numpy as np
import pytest

from thermal_inspection.processing.fusion_processor import FusionProcessor


@pytest.fixture
def colorized_thermal(thermal_frame_8bit):
    """FusionProcessor.process() expects an already-colorized (3-channel
    BGR) thermal frame, not the raw single-channel frame conftest's
    thermal_frame_8bit fixture provides."""
    return cv2.cvtColor(thermal_frame_8bit, cv2.COLOR_GRAY2BGR)


class TestFusionProcessorAllModes:
    """Every advertised fusion mode must run and produce a valid frame."""

    @pytest.mark.unit
    @pytest.mark.parametrize("mode", FusionProcessor().get_available_modes())
    def test_mode_runs_and_returns_valid_frame(self, mode, colorized_thermal, rgb_frame_matching_thermal):
        processor = FusionProcessor(fusion_mode=mode)

        result = processor.process(colorized_thermal, rgb_frame_matching_thermal)

        assert result is not None
        assert result.dtype == np.uint8
        assert result.ndim == 3
        assert result.shape[2] == 3
        # side_by_side legitimately doubles the width; every other mode
        # must match the thermal frame's own dimensions.
        if mode == 'side_by_side':
            assert result.shape[0] == colorized_thermal.shape[0]
        else:
            assert result.shape[:2] == colorized_thermal.shape[:2]

    @pytest.mark.unit
    def test_set_fusion_mode_matches_get_available_modes(self):
        """set_fusion_mode's own validation list must stay in sync with
        what get_available_modes() advertises - if these ever drift apart,
        a mode is either accepted-but-unadvertised or advertised-but-rejected."""
        processor = FusionProcessor()
        for mode in processor.get_available_modes():
            processor.set_fusion_mode(mode)
            assert processor.fusion_mode == mode, (
                f"set_fusion_mode rejected '{mode}', which get_available_modes() advertises"
            )


class TestFusionProcessorInvalidInput:
    @pytest.mark.unit
    def test_none_thermal_returns_rgb(self, rgb_frame_matching_thermal):
        processor = FusionProcessor()
        result = processor.process(None, rgb_frame_matching_thermal)
        assert result is rgb_frame_matching_thermal

    @pytest.mark.unit
    def test_none_rgb_returns_thermal(self, colorized_thermal):
        processor = FusionProcessor()
        result = processor.process(colorized_thermal, None)
        assert result is colorized_thermal
