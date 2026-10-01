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


# ---- behaviour added when the Gradient tab was actually wired into the frame loop ----

def _y16_step(delta_c_per_px_edge=2.0):
    """Y16 frame: 25 C on the left, 25 + delta on the right (sharp vertical edge)."""
    frame = np.full((64, 64), 29815, np.uint16)
    frame[:, 32:] = 29815 + int(delta_c_per_px_edge * 100)
    return frame


def test_gradient_is_measured_in_real_degrees_from_y16():
    gp = GradientProcessor()
    # A 10 C step: Sobel/8 over the blurred edge is a few C/px - far above 0.5, far below 50
    gp.update_settings(enabled=True, mode="magnitude", threshold=0.5, sensitivity=50)
    display = np.full((64, 64, 3), 80, np.uint8)
    out = gp.blend(display, _y16_step(10.0))
    assert not np.array_equal(out, display), "a 10 C edge must be visible at a 0.5 C/px threshold"

    gp.update_settings(threshold=50.0)
    np.testing.assert_array_equal(gp.blend(display, _y16_step(10.0)), display)   # 50 C/px: nothing passes


def test_threshold_is_in_degrees_not_raw_counts():
    """A 0.3 C edge is 30 raw counts: it must NOT pass a 1 C/px threshold just because the count is large."""
    gp = GradientProcessor()
    gp.update_settings(enabled=True, mode="magnitude", threshold=1.0, sensitivity=50)
    display = np.full((64, 64, 3), 80, np.uint8)
    np.testing.assert_array_equal(gp.blend(display, _y16_step(0.3)), display)


def test_only_pixels_above_threshold_are_tinted_even_for_colormaps_not_black_at_zero():
    gp = GradientProcessor()
    display = np.full((64, 64, 3), 100, np.uint8)
    for cmap in ("cool", "jet", "viridis"):
        gp.update_settings(enabled=True, mode="magnitude", threshold=1.0, sensitivity=50, colormap=cmap)
        out = gp.blend(display, _y16_step(10.0))
        far_from_edge = out[:, :8]                       # flat region: no gradient, must be untouched
        np.testing.assert_array_equal(far_from_edge, display[:, :8])
        assert not np.array_equal(out[:, 28:36], display[:, 28:36])   # the edge itself is tinted


def test_sensitivity_changes_what_is_shown():
    gp = GradientProcessor()
    display = np.full((64, 64, 3), 80, np.uint8)
    src = _y16_step(1.5)                                   # a modest edge
    gp.update_settings(enabled=True, mode="magnitude", threshold=3.0, sensitivity=1)
    low_sens = gp.blend(display, src)
    gp2 = GradientProcessor()
    gp2.update_settings(enabled=True, mode="magnitude", threshold=3.0, sensitivity=100)
    high_sens = gp2.blend(display, src)
    assert np.array_equal(low_sens, display)               # threshold ~6 C/px: nothing
    assert not np.array_equal(high_sens, display)          # threshold 0: the edge shows


def test_horizontal_and_vertical_modes_pick_their_own_direction():
    gp = GradientProcessor()
    display = np.full((64, 64, 3), 80, np.uint8)
    vertical_edge = _y16_step(10.0)                        # changes along x -> a horizontal gradient
    gp.update_settings(enabled=True, mode="horizontal", threshold=0.5)
    assert not np.array_equal(gp.blend(display, vertical_edge), display)
    gp.update_settings(mode="vertical")
    np.testing.assert_array_equal(gp.blend(display, vertical_edge), display)


def test_both_mode_draws_arrows_pointing_toward_increasing_temperature():
    gp = GradientProcessor()
    gp.update_settings(enabled=True, mode="both", threshold=0.5, colormap="gray")
    display = np.zeros((128, 128, 3), np.uint8)
    src = np.full((128, 128), 29815, np.uint16)
    src[:, 64:] += 1000                                    # 10 C hotter on the right
    out = gp.blend(display, src)
    assert out.any(), "arrow field should be drawn"
    # far from the edge there is no gradient, so no arrows
    assert not out[:, :20].any()


def test_source_of_a_different_size_is_resampled_to_the_display_frame():
    gp = GradientProcessor()
    gp.update_settings(enabled=True, mode="magnitude", threshold=0.5)
    display = np.full((128, 160, 3), 80, np.uint8)         # display larger than the 64x64 thermal data
    out = gp.blend(display, _y16_step(10.0))
    assert out.shape == display.shape
    assert not np.array_equal(out, display)


def test_8bit_source_is_in_counts_and_never_raises_on_flat_frames():
    gp = GradientProcessor()
    gp.update_settings(enabled=True, threshold=1.0)
    flat = np.full((32, 32), 120, np.uint8)
    display = np.full((32, 32, 3), 50, np.uint8)
    np.testing.assert_array_equal(gp.blend(display, flat), display)
    step = flat.copy(); step[:, 16:] = 220
    assert not np.array_equal(gp.blend(display, step), display)


def test_overlay_brightness_scale_is_smoothed_between_frames():
    """Per-frame max-normalisation made the overlay flicker; the scale is now smoothed across frames."""
    gp = GradientProcessor()
    gp.update_settings(enabled=True, threshold=0.5, colormap="gray")
    display = np.zeros((64, 64, 3), np.uint8)
    gp.blend(display, _y16_step(10.0))
    first = gp._norm_hi
    gp.blend(display, _y16_step(0.8))                      # much weaker edge next frame
    assert gp._norm_hi > 0.5 * first, "scale must not collapse to the weak frame immediately"
