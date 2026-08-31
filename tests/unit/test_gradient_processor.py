"""
Unit tests for GradientProcessor backend.
"""

import numpy as np
from thermal_inspection.processing.gradient_processor import GradientProcessor


def test_gradient_processor_initialization():
    gp = GradientProcessor()
    assert gp.enabled is False


def test_gradient_processor_disabled_returns_none():
    gp = GradientProcessor()
    frame = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
    assert gp.compute(frame) is None


def test_gradient_processor_enabled_magnitude():
    gp = GradientProcessor()
    gp.update_settings(enabled=True, mode="magnitude", threshold=1.0, sensitivity=50, colormap="hot")
    assert gp.enabled is True

    # High contrast step frame to ensure gradients are generated
    frame = np.zeros((100, 100), dtype=np.uint8)
    frame[:, 50:] = 255

    overlay = gp.compute(frame)
    assert overlay is not None
    assert overlay.shape == (100, 100, 3)
    assert overlay.dtype == np.uint8
    assert overlay.max() > 0


def test_gradient_processor_modes():
    gp = GradientProcessor()
    frame = np.zeros((100, 100), dtype=np.uint8)
    frame[:, 50:] = 255

    for mode in ["magnitude", "horizontal", "vertical", "both"]:
        gp.update_settings(enabled=True, mode=mode)
        overlay = gp.compute(frame)
        assert overlay is not None
        assert overlay.shape == (100, 100, 3)


def test_gradient_processor_colormaps():
    gp = GradientProcessor()
    frame = np.zeros((100, 100), dtype=np.uint8)
    frame[:, 50:] = 255

    for colormap in ["hot", "cool", "jet", "viridis", "gray"]:
        gp.update_settings(enabled=True, mode="magnitude", colormap=colormap)
        overlay = gp.compute(frame)
        assert overlay is not None
        assert overlay.shape == (100, 100, 3)


def test_gradient_processor_blend():
    gp = GradientProcessor()
    display_frame = np.ones((50, 50, 3), dtype=np.uint8) * 100

    # When disabled, blend returns original frame
    blended_disabled = gp.blend(display_frame)
    np.testing.assert_array_equal(blended_disabled, display_frame)

    # When enabled
    gp.update_settings(enabled=True, threshold=0.1)
    blended_enabled = gp.blend(display_frame)
    assert blended_enabled.shape == display_frame.shape
