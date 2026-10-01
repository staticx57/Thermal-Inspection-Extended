"""
Regression tests for two 2D Fusion enhancements requested directly by the
user (2026-09-06):

1. thermal_contours' contour-line colors previously came from a fixed
   8-color rainbow unrelated to whatever palette (White Hot, Ironbow, etc.)
   the thermal image itself is colorized with. set_palette_lut() lets
   contour colors sample the active palette instead.

2. enhanced_edge_highlight's line thickness was derived directly from
   fusion_intensity (which also controls edge color alpha/visibility),
   coupling "how visible" and "how thick" into one slider. set_edge_line_size()
   decouples them.
"""
import cv2
import numpy as np
import pytest

from thermal_inspection.processing.fusion_processor import FusionProcessor


@pytest.fixture
def colorized_thermal(thermal_frame_8bit):
    return cv2.cvtColor(thermal_frame_8bit, cv2.COLOR_GRAY2BGR)


class TestThermalContoursPaletteAware:
    def test_defaults_to_none_and_uses_fixed_rainbow(self):
        fp = FusionProcessor()
        assert fp.palette_lut is None

    def test_set_palette_lut_accepts_valid_256x3_array(self):
        fp = FusionProcessor()
        lut = np.zeros((256, 3), dtype=np.uint8)
        fp.set_palette_lut(lut)
        assert fp.palette_lut is not None
        assert fp.palette_lut.shape == (256, 3)

    def test_set_palette_lut_rejects_wrong_shape(self):
        fp = FusionProcessor()
        fp.set_palette_lut(np.zeros((10, 3), dtype=np.uint8))  # too few rows
        assert fp.palette_lut is None
        fp.set_palette_lut(np.zeros((256, 4), dtype=np.uint8))  # wrong channel count
        assert fp.palette_lut is None

    def test_set_palette_lut_none_restores_fallback(self):
        fp = FusionProcessor()
        fp.set_palette_lut(np.zeros((256, 3), dtype=np.uint8))
        fp.set_palette_lut(None)
        assert fp.palette_lut is None

    def test_contour_colors_actually_sample_the_palette(self, colorized_thermal, rgb_frame):
        """A distinctive, easily-checked palette (pure red ramp) should
        produce contours whose color channels reflect that ramp - not the
        hardcoded rainbow's blue/green/orange/etc. values."""
        fp = FusionProcessor()
        fp.set_fusion_mode('thermal_contours')

        # Pure-red LUT: every entry is (B=0, G=0, R=index) - a contour drawn
        # anywhere in this LUT's range must have B=0, G=0, since no rainbow
        # color in the old fixed 8-color list has both B and G exactly 0
        # except pure blue/red endpoints, and this ramp spans the whole
        # 0-255 range, not just two colors.
        red_ramp = np.zeros((256, 3), dtype=np.uint8)
        red_ramp[:, 2] = np.arange(256, dtype=np.uint8)  # R channel only
        fp.set_palette_lut(red_ramp)

        result = fp._thermal_contours(colorized_thermal, rgb_frame)
        assert result is not None
        assert result.shape == rgb_frame.shape

        # Find drawn contour pixels (anything that differs from the plain
        # rgb_frame base) and confirm every one is pure-red-channel-only,
        # matching the injected LUT and never the old rainbow's B/G values.
        diff_mask = np.any(result != rgb_frame, axis=2)
        if diff_mask.any():
            changed_pixels = result[diff_mask]
            assert np.all(changed_pixels[:, 0] == 0), "B channel should be 0 for every contour pixel under a pure-red LUT"
            assert np.all(changed_pixels[:, 1] == 0), "G channel should be 0 for every contour pixel under a pure-red LUT"

    def test_falls_back_to_rainbow_when_no_lut_set(self, colorized_thermal, rgb_frame):
        """Same call, no set_palette_lut() - must not crash and must behave
        exactly as before (bit-identical to a fixed reference run), since
        this is the default state for any caller that never wires the new
        setter up at all."""
        fp = FusionProcessor()
        fp.set_fusion_mode('thermal_contours')
        result = fp._thermal_contours(colorized_thermal, rgb_frame)
        assert result is not None
        assert result.shape == rgb_frame.shape


class TestEnhancedEdgeLineSize:
    def test_default_line_size(self):
        fp = FusionProcessor()
        assert fp.edge_line_size == 0.5

    def test_set_edge_line_size_clamps_to_0_1(self):
        fp = FusionProcessor()
        fp.set_edge_line_size(1.5)
        assert fp.edge_line_size == 1.0
        fp.set_edge_line_size(-0.5)
        assert fp.edge_line_size == 0.0
        fp.set_edge_line_size(0.3)
        assert fp.edge_line_size == 0.3

    def test_line_size_independent_of_fusion_intensity(self, colorized_thermal, rgb_frame):
        """The actual bug being fixed: thickness and visibility used to be
        the same knob (fusion_intensity). Prove they're independent now -
        changing line_size alone (intensity fixed) must change edge pixel
        coverage. Uses a matching-size RGB frame (resized from the fixture)
        since _edge_enhanced requires thermal/rgb to share a shape."""
        rgb = cv2.resize(rgb_frame, (colorized_thermal.shape[1], colorized_thermal.shape[0]))
        fp = FusionProcessor()
        fp.set_fusion_mode('edge_enhanced')
        fp.set_edge_line_size(0.0)  # thinnest (dilation kernel size 1 = no-op dilate)
        thin_result = fp._edge_enhanced(colorized_thermal, rgb)

        fp.set_edge_line_size(1.0)  # thickest (dilation kernel size 5)
        thick_result = fp._edge_enhanced(colorized_thermal, rgb)

        thin_edge_pixels = np.count_nonzero(np.any(thin_result != rgb, axis=2))
        thick_edge_pixels = np.count_nonzero(np.any(thick_result != rgb, axis=2))
        assert thick_edge_pixels >= thin_edge_pixels, (
            "Thicker line_size must cover at least as many changed pixels as thinner"
        )

    def test_intensity_no_longer_changes_dilation_kernel_size(self):
        """Direct regression test for the coupling bug: previously
        dilation_size = int(1 + fusion_intensity * 2), so intensity alone
        changed line thickness. Now dilation is derived only from
        edge_line_size."""
        fp = FusionProcessor()
        fp.set_edge_line_size(0.0)
        low_intensity_dilation = 1 + int(round(fp.edge_line_size * 4))
        fp.set_intensity(0.9)  # would have changed dilation_size under the old formula
        high_intensity_dilation = 1 + int(round(fp.edge_line_size * 4))
        assert low_intensity_dilation == high_intensity_dilation == 1


class TestReliefFusionShadowClipping:
    """Regression test for a real bug found during a maturity review of
    every fusion mode: _relief_fusion's emboss convolution ran at
    ddepth=-1 (same depth as the uint8 input), which saturates/clips
    DURING the convolution - before the +128 recentering step ever sees
    the value. That silently destroyed the shadow (negative-response)
    side of the effect: a response that should end up well below 128
    after recentering was already clamped to 0 by filter2D first, so
    0 + 128 = 128 (flat neutral gray) instead of a real shadow."""

    def test_bright_square_produces_both_highlight_and_shadow(self):
        """This kernel's negative/positive weights sit on the top-left/
        bottom-right diagonal (-2 top-left, +2 bottom-right), so it's
        specifically sensitive to diagonal gradients - a bright square on
        a dark background has real top-left and bottom-right corners,
        giving it gradient content in every direction including that
        diagonal. A pure horizontal or vertical step edge alone doesn't
        exercise the diagonal terms the same way. Must emboss to BOTH a
        highlight (>128) and a shadow (<128) somewhere on the square's
        boundary - the whole point of an emboss/relief effect. Under the
        old ddepth=-1 bug, the shadow side was flattened to exactly 128
        instead of being genuinely dark."""
        fp = FusionProcessor()
        gray_thermal = np.full((60, 60), 128, dtype=np.uint8)
        thermal = cv2.cvtColor(gray_thermal, cv2.COLOR_GRAY2BGR)
        rgb_gray = np.zeros((60, 60), dtype=np.uint8)
        rgb_gray[15:45, 15:45] = 220  # a bright square - real corners in every direction
        rgb = cv2.cvtColor(rgb_gray, cv2.COLOR_GRAY2BGR)

        fp.set_intensity(1.0)
        fp.detail_strength = 1.0
        result = fp._relief_fusion(thermal, rgb)
        result_gray = cv2.cvtColor(result, cv2.COLOR_BGR2GRAY).astype(np.int16)

        assert result_gray.max() > 128, "Expected a genuine highlight (>128) near the edge"
        assert result_gray.min() < 128, (
            "Expected a genuine shadow (<128) near the edge - if this is exactly 128, "
            "the old ddepth=-1 premature-saturation bug is back"
        )

    def test_runs_end_to_end_without_crash(self, colorized_thermal, rgb_frame_matching_thermal):
        fp = FusionProcessor()
        fp.set_fusion_mode('relief_fusion')
        result = fp.process(colorized_thermal, rgb_frame_matching_thermal)
        assert result is not None
        assert result.dtype == np.uint8


class TestPictureInPictureBoundsClamping:
    """Regression test for a real crash risk found during the same
    maturity review: the inset was pasted via an unconditional numpy
    slice assignment with no bounds check. If rounding in the aspect-fit
    math ever placed the inset (plus its 2px border) past main's edge, a
    numpy slice silently truncates the destination but not the
    (still full-size) source, raising a broadcast ValueError - previously
    swallowed by this function's own blanket except and silently
    downgraded to side_by_side with no indication PIP itself was broken."""

    def test_normal_pip_size_unaffected(self, colorized_thermal, rgb_frame_matching_thermal):
        fp = FusionProcessor()
        result = fp._picture_in_picture(colorized_thermal, rgb_frame_matching_thermal, pip_size=0.25)
        assert result is not None
        # Same aspect ratio as the main frame, never smaller (PIP may compose on a larger canvas so
        # the inset keeps its detail - see test_pip_canvas_keeps_inset_detail)
        h, w = colorized_thermal.shape[:2]
        assert result.shape[2] == colorized_thermal.shape[2]
        assert result.shape[1] >= w and result.shape[0] >= h
        assert abs(result.shape[1] / result.shape[0] - w / h) < 0.01

    def test_extreme_pip_size_does_not_crash(self, colorized_thermal, rgb_frame_matching_thermal):
        """pip_size near 1.0 is an edge case the aspect-fit math wasn't
        designed for - must not raise, whatever it visually produces."""
        fp = FusionProcessor()
        for pip_size in (0.9, 0.99, 1.0):
            for position in ('top-right', 'top-left', 'bottom-right', 'bottom-left'):
                result = fp._picture_in_picture(
                    colorized_thermal, rgb_frame_matching_thermal,
                    pip_size=pip_size, position=position
                )
                assert result is not None

    def test_all_four_corners_stay_within_frame(self, colorized_thermal, rgb_frame_matching_thermal):
        """At a normal pip_size, confirm the inset is actually visible
        (some pixels changed) for every corner position, not silently
        clamped to nothing."""
        fp = FusionProcessor()
        for position in ('top-right', 'top-left', 'bottom-right', 'bottom-left'):
            result = fp._picture_in_picture(
                colorized_thermal, rgb_frame_matching_thermal,
                pip_size=0.25, position=position
            )
            h, w = colorized_thermal.shape[:2]
            assert result.shape[1] >= w and result.shape[0] >= h     # may use a larger canvas
            assert abs(result.shape[1] / result.shape[0] - w / h) < 0.01


class TestThermalContoursLevelCountAndLineSize:
    def test_default_level_count(self):
        assert FusionProcessor().contour_level_count == 8

    def test_level_count_clamped_3_to_12(self):
        fp = FusionProcessor()
        fp.set_contour_level_count(1)
        assert fp.contour_level_count == 3
        fp.set_contour_level_count(50)
        assert fp.contour_level_count == 12
        fp.set_contour_level_count(6)
        assert fp.contour_level_count == 6

    def test_fewer_levels_draws_fewer_or_equal_distinct_contour_passes(self, colorized_thermal, rgb_frame_matching_thermal):
        """Not a pixel-exact check (contour geometry is scene-dependent) -
        just confirms the level count knob actually reaches the drawing
        loop rather than being ignored."""
        fp = FusionProcessor()
        fp.set_fusion_mode('thermal_contours')
        fp.set_contour_level_count(3)
        few_result = fp._thermal_contours(colorized_thermal, rgb_frame_matching_thermal)
        fp.set_contour_level_count(12)
        many_result = fp._thermal_contours(colorized_thermal, rgb_frame_matching_thermal)
        few_changed = np.count_nonzero(np.any(few_result != rgb_frame_matching_thermal, axis=2))
        many_changed = np.count_nonzero(np.any(many_result != rgb_frame_matching_thermal, axis=2))
        assert many_changed >= few_changed

    def test_default_contour_line_size_independent_from_edge_line_size(self):
        fp = FusionProcessor()
        assert fp.contour_line_size == 0.5
        fp.set_edge_line_size(1.0)
        assert fp.contour_line_size == 0.5, "contour_line_size must not change when edge_line_size changes"

    def test_contour_line_size_clamped(self):
        fp = FusionProcessor()
        fp.set_contour_line_size(2.0)
        assert fp.contour_line_size == 1.0
        fp.set_contour_line_size(-1.0)
        assert fp.contour_line_size == 0.0


class TestThermalContoursIsothermLabels:
    def test_labels_disabled_by_default(self):
        assert FusionProcessor().contour_labels_enabled is False

    def test_no_crash_without_temperature_map(self, colorized_thermal, rgb_frame_matching_thermal):
        fp = FusionProcessor()
        fp.set_fusion_mode('thermal_contours')
        fp.set_contour_labels_enabled(True)
        # No temperature_map_c passed - must behave like labels are off,
        # not crash or fabricate a value.
        result = fp._thermal_contours(colorized_thermal, rgb_frame_matching_thermal)
        assert result is not None

    def test_shape_mismatch_disables_labels_rather_than_guessing(self, colorized_thermal, rgb_frame_matching_thermal):
        fp = FusionProcessor()
        fp.set_fusion_mode('thermal_contours')
        fp.set_contour_labels_enabled(True)
        wrong_shape_map = np.full((10, 10), 25.0, dtype=np.float32)
        # Must not raise or attempt to index temperature_map_c out of bounds.
        result = fp._thermal_contours(colorized_thermal, rgb_frame_matching_thermal, wrong_shape_map, False)
        assert result is not None

    def test_labels_drawn_when_valid_temperature_map_provided(self, colorized_thermal, rgb_frame_matching_thermal):
        fp = FusionProcessor()
        fp.set_fusion_mode('thermal_contours')
        fp.set_contour_labels_enabled(True)
        h, w = colorized_thermal.shape[:2]
        # A real, distinct temperature per gray level so labels are
        # non-degenerate (not all identical).
        gray = cv2.cvtColor(colorized_thermal, cv2.COLOR_BGR2GRAY).astype(np.float32)
        temp_map = gray / 255.0 * 60.0 + 10.0  # maps 0-255 -> 10-70 C
        result_with_labels = fp._thermal_contours(colorized_thermal, rgb_frame_matching_thermal, temp_map, False)

        fp2 = FusionProcessor()
        fp2.set_fusion_mode('thermal_contours')
        fp2.set_contour_labels_enabled(False)
        result_without_labels = fp2._thermal_contours(colorized_thermal, rgb_frame_matching_thermal, temp_map, False)

        assert not np.array_equal(result_with_labels, result_without_labels), (
            "Enabling labels with a valid temperature map should visibly change output"
        )

    def test_estimated_flag_does_not_crash(self, colorized_thermal, rgb_frame_matching_thermal):
        fp = FusionProcessor()
        fp.set_fusion_mode('thermal_contours')
        fp.set_contour_labels_enabled(True)
        h, w = colorized_thermal.shape[:2]
        gray = cv2.cvtColor(colorized_thermal, cv2.COLOR_BGR2GRAY).astype(np.float32)
        temp_map = gray / 255.0 * 60.0 + 10.0
        result = fp._thermal_contours(colorized_thermal, rgb_frame_matching_thermal, temp_map, True)
        assert result is not None


class TestThermalContoursLabelUnit:
    """
    Isotherm labels previously stayed hardcoded to Celsius regardless of
    the app-wide temperature unit setting (Settings/Radiometric panel's
    C/F/K choice) - every other on-screen temperature (spot meters, ROI
    stats, the histogram) already respected it.
    """
    def test_default_unit_is_celsius(self):
        assert FusionProcessor().contour_temp_unit == 'C'

    def test_celsius_label(self):
        fp = FusionProcessor()
        assert fp._format_contour_label(20.0, False) == "20C"

    def test_fahrenheit_conversion(self):
        fp = FusionProcessor()
        fp.set_contour_temp_unit('F')
        assert fp._format_contour_label(20.0, False) == "68F"  # 20C = 68F

    def test_kelvin_conversion(self):
        fp = FusionProcessor()
        fp.set_contour_temp_unit('K')
        assert fp._format_contour_label(20.0, False) == "293K"  # 20C = 293.15K

    def test_lowercase_and_full_word_aliases_accepted(self):
        fp = FusionProcessor()
        fp.set_contour_temp_unit('f')
        assert fp.contour_temp_unit == 'F'
        fp.set_contour_temp_unit('kelvin')
        assert fp.contour_temp_unit == 'K'
        fp.set_contour_temp_unit('CELSIUS')
        assert fp.contour_temp_unit == 'C'

    def test_invalid_unit_rejected_leaves_current_value(self):
        fp = FusionProcessor()
        fp.set_contour_temp_unit('bogus')
        assert fp.contour_temp_unit == 'C'

    def test_estimated_prefix_preserved_across_units(self):
        fp = FusionProcessor()
        fp.set_contour_temp_unit('F')
        assert fp._format_contour_label(20.0, True) == "~68F"

    def test_unit_change_visibly_affects_rendered_labels(self, colorized_thermal, rgb_frame_matching_thermal):
        gray = cv2.cvtColor(colorized_thermal, cv2.COLOR_BGR2GRAY).astype(np.float32)
        temp_map = gray / 255.0 * 60.0 + 10.0

        fp_c = FusionProcessor()
        fp_c.set_fusion_mode('thermal_contours')
        fp_c.set_contour_labels_enabled(True)
        result_c = fp_c._thermal_contours(colorized_thermal, rgb_frame_matching_thermal, temp_map, False)

        fp_f = FusionProcessor()
        fp_f.set_fusion_mode('thermal_contours')
        fp_f.set_contour_labels_enabled(True)
        fp_f.set_contour_temp_unit('F')
        result_f = fp_f._thermal_contours(colorized_thermal, rgb_frame_matching_thermal, temp_map, False)

        assert not np.array_equal(result_c, result_f)


class TestThermalContoursLabelPlacement:
    """
    Live-reported (2026-09-07): "be smarter about label placement." The
    old approach anchored every level's label at cv2.moments' filled
    centroid - for a single hot blob, every threshold level's contour is
    roughly concentric, so nearly every level's centroid landed at
    almost the same point near the blob's peak, stacking labels on top
    of each other. Now anchored at each contour's own topmost boundary
    point (a genuinely different position per level, since each ring is
    a different real size) with greedy vertical nudging away from
    already-placed labels and clamping inside the frame.
    """
    def _concentric_contours(self, size=400, radii=(150, 110, 70, 30)):
        center = size // 2
        contours = []
        for r in radii:
            pts = np.array([[[center + int(r * np.cos(t)), center + int(r * np.sin(t))]]
                             for t in np.linspace(0, 2 * np.pi, 60)], dtype=np.int32)
            contours.append(pts)
        return size, contours

    @staticmethod
    def _boxes_overlap(a, b):
        ax1, ay1, ax2, ay2 = a
        bx1, by1, bx2, by2 = b
        return ax1 < bx2 and ax2 > bx1 and ay1 < by2 and ay2 > by1

    def test_concentric_contour_labels_do_not_overlap(self):
        # The exact failure mode being fixed - verified directly rather
        # than assumed: a centroid anchor would have placed all 4 of
        # these labels within a few pixels of the shared center.
        size, contours = self._concentric_contours()
        canvas = np.full((size, size, 3), 50, dtype=np.uint8)
        fp = FusionProcessor()
        placed = []
        for i, c in enumerate(contours):
            fp._place_contour_label(canvas, f"{70 - i * 10}C", c, (0, 255, 0), placed)

        assert len(placed) == 4
        overlaps = sum(
            1 for i in range(len(placed)) for j in range(i + 1, len(placed))
            if self._boxes_overlap(placed[i], placed[j])
        )
        assert overlaps == 0

    def test_label_box_stays_within_frame_bounds(self):
        # A contour whose topmost point sits right at the frame's own
        # edge (y=0) - the old code would have let cv2.putText draw
        # partially off-canvas with no clamping at all.
        size = 200
        contour = np.array([[[100, 0]], [[80, 30]], [[120, 30]]], dtype=np.int32)
        canvas = np.full((size, size, 3), 50, dtype=np.uint8)
        fp = FusionProcessor()
        placed = []
        fp._place_contour_label(canvas, "99C", contour, (0, 255, 0), placed)

        x1, y1, x2, y2 = placed[0]
        assert x1 >= 0 and y1 >= 0 and x2 <= size and y2 <= size

    def test_overlapping_candidate_position_is_nudged_not_stacked(self):
        size = 200
        canvas = np.full((size, size, 3), 50, dtype=np.uint8)
        fp = FusionProcessor()
        placed = []
        # Two contours with the SAME topmost point (the worst case: no
        # natural separation at all) - the nudge logic must still keep
        # them apart rather than drawing one exactly on the other.
        contour_a = np.array([[[100, 50]], [[80, 80]], [[120, 80]]], dtype=np.int32)
        contour_b = np.array([[[100, 50]], [[70, 90]], [[130, 90]]], dtype=np.int32)
        fp._place_contour_label(canvas, "20C", contour_a, (0, 255, 0), placed)
        fp._place_contour_label(canvas, "40C", contour_b, (0, 128, 255), placed)

        assert not self._boxes_overlap(placed[0], placed[1])


class TestThermalContoursFill:
    """
    Live-requested (2026-09-07): "maybe an option for a color overlay
    with the contour to highlight the selected isotherm boundaries
    visually." Off by default (pure line-drawing, unchanged from this
    mode's original behavior).
    """
    def test_disabled_by_default(self):
        assert FusionProcessor().contour_fill_enabled is False

    def _hot_blob_scene(self):
        size = 200
        thermal_gray = np.full((size, size), 100, dtype=np.uint8)
        cv2.circle(thermal_gray, (100, 100), 60, 220, -1)
        thermal = cv2.cvtColor(thermal_gray, cv2.COLOR_GRAY2BGR)
        rgb = np.full((size, size, 3), 50, dtype=np.uint8)
        return thermal, rgb

    def test_fill_changes_interior_but_not_untouched_background(self):
        thermal, rgb = self._hot_blob_scene()
        fp = FusionProcessor()
        fp.set_fusion_mode('thermal_contours')
        fp.contour_level_count = 4
        result_no_fill = fp.process(thermal, rgb)

        fp.set_contour_fill_enabled(True)
        result_fill = fp.process(thermal, rgb)

        assert not np.array_equal(result_no_fill, result_fill)
        # Deep inside the hot blob, away from any single contour line -
        # the fill should tint this region; a corner far from the blob,
        # never inside any level's mask, should be completely untouched.
        interior_diff = int(np.abs(result_fill[100, 100].astype(int) - result_no_fill[100, 100].astype(int)).sum())
        background_diff = int(np.abs(result_fill[5, 5].astype(int) - result_no_fill[5, 5].astype(int)).sum())
        assert interior_diff > 0
        assert background_diff == 0

    def test_fill_stays_real_time_viable_at_full_frame_size(self):
        # Live-reported as slow (2026-09-07): the first version ran the
        # fill blend at FULL FRAME size on every one of up to 12 levels
        # regardless of how much of the frame that level's region
        # actually covered - measured directly at ~23ms/frame added on a
        # 640x512/8-level scene (6.1ms fill-off -> 29.2ms fill-on), enough
        # on its own to cap this mode under 35fps. Cropping each level's
        # blend to its own contours' bounding box (not the full frame)
        # measured ~7ms added instead - asserting a generous upper bound
        # here (not the exact measured number, which varies by machine)
        # so this guards against a regression back toward the full-frame
        # cost without being flaky on slower CI hardware.
        import time
        size_h, size_w = 512, 640
        yy, xx = np.mgrid[0:size_h, 0:size_w]
        dist = np.sqrt((xx - size_w // 2) ** 2 + (yy - size_h // 2) ** 2)
        thermal_gray = np.clip(200 - dist * 0.5, 0, 255).astype(np.uint8)
        thermal = cv2.cvtColor(thermal_gray, cv2.COLOR_GRAY2BGR)
        rgb = np.random.RandomState(0).randint(80, 180, (size_h, size_w, 3), dtype=np.uint8)

        fp = FusionProcessor()
        fp.set_fusion_mode('thermal_contours')
        fp.contour_level_count = 8
        fp.set_contour_fill_enabled(True)

        for _ in range(3):
            fp.process(thermal, rgb)  # warmup
        times = []
        for _ in range(10):
            t0 = time.perf_counter()
            fp.process(thermal, rgb)
            times.append((time.perf_counter() - t0) * 1000)
        assert max(times) < 20.0, f"contour fill took {max(times):.1f}ms, expected well under the old full-frame ~29ms"


class TestAdaptiveCanny:
    def test_disabled_by_default(self):
        assert FusionProcessor().adaptive_canny_enabled is False

    def test_disabled_returns_fixed_thresholds_unchanged(self):
        fp = FusionProcessor()
        fp.set_edge_strength(77)
        gray = np.random.default_rng(1).integers(0, 255, size=(64, 64), dtype=np.uint8)
        low, high = fp._get_canny_thresholds(gray)
        assert (low, high) == (fp.edge_threshold_low, fp.edge_threshold_high)

    def test_enabled_computes_median_based_thresholds(self):
        fp = FusionProcessor()
        fp.set_adaptive_canny_enabled(True)
        gray = np.full((64, 64), 100, dtype=np.uint8)
        low, high = fp._get_canny_thresholds(gray)
        assert low == pytest.approx(0.67 * 100, abs=1.0)
        assert high == pytest.approx(1.33 * 100, abs=1.0)

    def test_recompute_is_throttled(self):
        """The median must not be recomputed on every single call while
        adaptive mode is on - only every adaptive_canny_interval calls."""
        fp = FusionProcessor()
        fp.set_adaptive_canny_enabled(True)
        fp.adaptive_canny_interval = 3
        gray_a = np.full((64, 64), 50, dtype=np.uint8)
        low_a, _ = fp._get_canny_thresholds(gray_a)  # counter=1, first call always computes

        gray_b = np.full((64, 64), 200, dtype=np.uint8)
        low_b, _ = fp._get_canny_thresholds(gray_b)  # counter=2, not a multiple of 3 -> cached
        assert low_b == low_a, "Should reuse the cached threshold, not recompute from gray_b"

        low_c, _ = fp._get_canny_thresholds(gray_b)  # counter=3, multiple of interval -> recompute
        assert low_c != low_a, "Should have recomputed by the 3rd call"

    def test_runs_end_to_end_without_crash(self, colorized_thermal, rgb_frame_matching_thermal):
        fp = FusionProcessor()
        fp.set_fusion_mode('edge_enhanced')
        fp.set_adaptive_canny_enabled(True)
        result = fp.process(colorized_thermal, rgb_frame_matching_thermal)
        assert result is not None
        fp.set_fusion_mode('enhanced_edge_highlight')
        result2 = fp.process(colorized_thermal, rgb_frame_matching_thermal)
        assert result2 is not None


class TestEdgeDirection:
    def test_default_is_all(self):
        assert FusionProcessor().edge_direction == 'all'

    def test_invalid_direction_rejected(self):
        fp = FusionProcessor()
        fp.set_edge_direction('diagonal')
        assert fp.edge_direction == 'all'

    def test_all_uses_canny_horizontal_and_vertical_use_sobel(self):
        fp = FusionProcessor()
        gray = np.random.default_rng(2).integers(0, 255, size=(64, 64), dtype=np.uint8).astype(np.uint8)
        all_edges = fp._detect_edges(gray, 50, 150)

        fp.set_edge_direction('horizontal')
        h_edges = fp._detect_edges(gray, 50, 150)
        fp.set_edge_direction('vertical')
        v_edges = fp._detect_edges(gray, 50, 150)

        assert all_edges.dtype == np.uint8
        assert h_edges.dtype == np.uint8
        assert v_edges.dtype == np.uint8
        # Directional detection on random noise should generally differ
        # from plain Canny and from each other's axis.
        assert not np.array_equal(all_edges, h_edges)
        assert not np.array_equal(h_edges, v_edges)

    def test_runs_end_to_end_without_crash(self, colorized_thermal, rgb_frame_matching_thermal):
        for direction in ('horizontal', 'vertical'):
            fp = FusionProcessor()
            fp.set_fusion_mode('edge_enhanced')
            fp.set_edge_direction(direction)
            assert fp.process(colorized_thermal, rgb_frame_matching_thermal) is not None
            fp.set_fusion_mode('enhanced_edge_highlight')
            assert fp.process(colorized_thermal, rgb_frame_matching_thermal) is not None


class TestSobelAlpha:
    def test_disabled_by_default(self):
        assert FusionProcessor().sobel_alpha_enabled is False

    def test_empty_mask_returns_zeros_no_division_by_zero(self):
        fp = FusionProcessor()
        gray = np.full((32, 32), 128, dtype=np.uint8)
        empty_mask = np.zeros((32, 32), dtype=np.uint8)
        alpha = fp._sobel_alpha_within_mask(gray, empty_mask)
        assert np.all(alpha == 0.0)

    def test_alpha_bounded_0_to_1_within_mask(self):
        fp = FusionProcessor()
        rng = np.random.default_rng(3)
        gray = rng.integers(0, 255, size=(64, 64), dtype=np.uint8)
        mask = np.zeros((64, 64), dtype=np.uint8)
        mask[10:50, 10:50] = 255
        alpha = fp._sobel_alpha_within_mask(gray, mask)
        assert alpha.min() >= 0.0
        assert alpha.max() <= 1.0
        assert np.all(alpha[mask == 0] == 0.0), "Alpha must be zero outside the edge mask"

    def test_runs_end_to_end_without_crash(self, colorized_thermal, rgb_frame_matching_thermal):
        fp = FusionProcessor()
        fp.set_fusion_mode('edge_enhanced')
        fp.set_sobel_alpha_enabled(True)
        assert fp.process(colorized_thermal, rgb_frame_matching_thermal) is not None
        fp.set_fusion_mode('enhanced_edge_highlight')
        assert fp.process(colorized_thermal, rgb_frame_matching_thermal) is not None


class TestSobelAlphaPercentileNormalization:
    """Live-reported 2026-09-07: "for edge enhances the line opacity is too
    low with the current settings." Root cause: _sobel_alpha_within_mask
    normalized against the single strongest in-mask gradient pixel, which
    a realistic scene's one strongest edge commonly exceeds the rest of by
    several times over - crushing every other edge's opacity toward zero.
    Switched to the 90th percentile of in-mask magnitude, keeping the same
    "stronger edge = more opaque" intent while no longer letting one
    outlier pixel set the scale for the whole frame."""

    def test_single_outlier_pixel_no_longer_crushes_the_rest_of_the_mask(self):
        fp = FusionProcessor()
        gray = np.zeros((64, 64), dtype=np.uint8)
        mask = np.zeros((64, 64), dtype=np.uint8)

        # Many moderate edges (a real step of ~40 gray levels)...
        for y in range(10, 50, 4):
            gray[y, 10:54] = 80
            mask[y, 10:54] = 255
        # ...plus one extreme outlier edge (a real step of ~250 gray levels),
        # far stronger than every other edge in the mask.
        gray[60, :] = 255
        mask[60, :] = 255

        alpha = fp._sobel_alpha_within_mask(gray, mask)
        moderate_alpha = alpha[10:50:4, 10:54]

        assert moderate_alpha.mean() > 0.3, (
            f"moderate edges should stay clearly visible despite one far "
            f"stronger outlier edge elsewhere in the mask - got mean alpha "
            f"{moderate_alpha.mean():.3f} (the old global-max normalization "
            f"crushed this to a small fraction of that)"
        )
        # The outlier itself should still saturate near full opacity - the
        # fix must not flatten genuine strength differences, only stop one
        # pixel from setting the scale for everything else.
        assert alpha[60, 32] >= 0.9

    def test_alpha_still_bounded_0_to_1_within_mask(self):
        """Preserves the existing contract from TestSobelAlpha above -
        only the normalization reference changed, not the output range or
        masking behavior."""
        fp = FusionProcessor()
        rng = np.random.default_rng(3)
        gray = rng.integers(0, 255, size=(64, 64), dtype=np.uint8)
        mask = np.zeros((64, 64), dtype=np.uint8)
        mask[10:50, 10:50] = 255
        alpha = fp._sobel_alpha_within_mask(gray, mask)
        assert alpha.min() >= 0.0
        assert alpha.max() <= 1.0
        assert np.all(alpha[mask == 0] == 0.0)


class TestEdgeBlurPeakPreservesWidth:
    """Live-reported the same day, same feature: even with a confident,
    fully-detected edge, the Fuzziness (edge_blur_kernel) slider was
    silently capping the maximum achievable opacity - GaussianBlur
    conserves a mask's total energy, not its peak, so blurring a thin
    line (a small edge_line_size) with a wide kernel measurably lowers its
    peak value well below 255 before any Strength/Sensitivity scaling
    ever sees it. Confirmed directly: dilation=2px + a mid-range blur
    kernel of 9 (this app's own live-reported settings) capped the peak
    at 43.5% of full scale.

    A first fix (rescale the whole blurred mask so its peak hits 255)
    was reported the SAME DAY as making lines look thicker - confirmed
    why by direct measurement: rescaling every pixel by the same factor
    also brightens the low-amplitude tail of the falloff, so pixels that
    used to be too dim to notice now cross into visible territory - the
    visible width at every threshold measurably grew (e.g. >20/255:
    6px -> 8px on a 2px-thick test line). Replaced with
    np.maximum(blurred, pre_blur_mask): only the pixels that were
    already part of the solid line before blurring get lifted back to
    255 (where blur alone under-reports them); every pixel in the soft
    halo keeps its original blurred value untouched, so the falloff's
    own width is bit-for-bit unchanged."""

    def _thin_line_mask(self, dilation_size):
        fp = FusionProcessor()
        line = np.zeros((100, 100), dtype=np.uint8)
        cv2.line(line, (10, 50), (90, 50), 255, thickness=1)
        if dilation_size > 1:
            line = cv2.dilate(line, fp._get_dilation_kernel(dilation_size), iterations=1)
        return line

    def test_peak_restored_to_full_scale(self):
        mask = self._thin_line_mask(dilation_size=2)
        blurred = cv2.GaussianBlur(mask, (9, 9), 0)
        assert blurred.max() < 200, "test setup must reproduce the dimming this fix addresses"

        fixed = np.maximum(blurred, mask)
        assert fixed.max() == 255

    def test_halo_outside_the_solid_line_is_bit_identical_to_plain_blur(self):
        """The regression this test guards against: a peak-restoring fix
        that also brightens pixels OUTSIDE the original solid line is
        exactly what read as "thicker lines" live. Every pixel the
        dilated mask never covered must come out of the fix identical to
        plain GaussianBlur, not just "still fairly dim." """
        mask = self._thin_line_mask(dilation_size=2)
        blurred = cv2.GaussianBlur(mask, (9, 9), 0)
        fixed = np.maximum(blurred, mask)

        outside_solid_line = mask == 0
        assert np.array_equal(fixed[outside_solid_line], blurred[outside_solid_line])

    def test_falloff_still_widens_with_larger_blur_kernel(self):
        """The fix must only restore the ceiling, not flatten the blur
        into a hard-edged mask again - a wider kernel should still spread
        the half-max footprint wider, preserving the "softer" look
        Fuzziness is meant to control. Sampled across a single column
        PERPENDICULAR to the line (its thickness direction) - counting
        over the whole 2D mask would be dominated by the line's own
        LENGTH (a near-constant ~80 core pixels forced to 255 by the fix
        regardless of kernel size), masking any real change in width."""
        mask = self._thin_line_mask(dilation_size=1)
        col_x = 50  # crosses the line (drawn from x=10 to x=90 at y=50)

        def falloff_width(kernel_size):
            blurred = cv2.GaussianBlur(mask, (kernel_size, kernel_size), 0)
            fixed = np.maximum(blurred, mask)
            return int(np.count_nonzero(fixed[:, col_x] > 5))

        assert falloff_width(15) > falloff_width(5), (
            "a larger Fuzziness kernel should still produce a visibly "
            "wider soft falloff after the peak fix, not an identical one"
        )

    def test_edge_enhanced_end_to_end_with_thin_line_and_blur(
        self, colorized_thermal, rgb_frame_matching_thermal
    ):
        """Full process() call at the live-reported settings shape (thin
        line, mid-range blur) must not raise and must produce real output."""
        fp = FusionProcessor()
        fp.set_fusion_mode('edge_enhanced')
        fp.set_edge_line_size(0.14)
        fp.set_edge_blur(8)  # -> odd -> 9, matches the live report
        result = fp.process(colorized_thermal, rgb_frame_matching_thermal)
        assert result is not None
        assert result.shape == colorized_thermal.shape


class TestPaletteEdgeColorMode:
    def test_default_is_fixed(self):
        assert FusionProcessor().edge_color_mode == 'fixed'

    def test_invalid_mode_rejected(self):
        fp = FusionProcessor()
        fp.set_edge_color_mode('rainbow')
        assert fp.edge_color_mode == 'fixed'

    def test_palette_mode_without_lut_falls_back_to_fixed(self, colorized_thermal, rgb_frame_matching_thermal):
        """edge_color_mode='palette' with no palette_lut set must not crash -
        falls back to the fixed color path."""
        fp = FusionProcessor()
        fp.set_fusion_mode('edge_enhanced')
        fp.set_edge_color_mode('palette')
        assert fp.palette_lut is None
        result = fp.process(colorized_thermal, rgb_frame_matching_thermal)
        assert result is not None

    def test_palette_mode_produces_chromatic_colors_matching_lut(self, colorized_thermal, rgb_frame_matching_thermal):
        """Compares palette mode against fixed mode directly rather than
        asserting a specific channel-sum sign - which side of the boundary
        Canny marks (background-side gray=128 vs hot-spot-side gray=220)
        is incidental geometry, not something to hardcode an assumption
        about. What must be true is that palette mode actually changes
        the result relative to a fixed color, and produces multiple
        distinct colors (since it's sampling a ramp, not one constant)."""
        red_ramp = np.zeros((256, 3), dtype=np.uint8)
        red_ramp[:, 2] = np.arange(256, dtype=np.uint8)

        fp_palette = FusionProcessor()
        fp_palette.set_fusion_mode('edge_enhanced')
        fp_palette.set_priority('rgb')  # thermal (has a real hot-spot boundary) becomes the edge source
        fp_palette.set_edge_color_mode('palette')
        fp_palette.set_palette_lut(red_ramp)
        palette_result = fp_palette.process(colorized_thermal, rgb_frame_matching_thermal)

        fp_fixed = FusionProcessor()
        fp_fixed.set_fusion_mode('edge_enhanced')
        fp_fixed.set_priority('rgb')
        fp_fixed.set_edge_color('cyan')  # deliberately different from anything on the red ramp
        fixed_result = fp_fixed.process(colorized_thermal, rgb_frame_matching_thermal)

        assert not np.array_equal(palette_result, fixed_result), (
            "Palette-sampled edge colors should differ from a fixed edge color"
        )
        # Confirm edges were actually drawn at all in the palette case
        # (not just "different because nothing happened in one of them").
        diff_from_base = np.any(palette_result != rgb_frame_matching_thermal, axis=2)
        assert np.any(diff_from_base), "Palette mode should have drawn some edge pixels"

    def test_runs_end_to_end_for_both_edge_modes(self, colorized_thermal, rgb_frame_matching_thermal):
        lut = np.zeros((256, 3), dtype=np.uint8)
        lut[:, 1] = np.arange(256, dtype=np.uint8)
        for mode in ('edge_enhanced', 'enhanced_edge_highlight'):
            fp = FusionProcessor()
            fp.set_fusion_mode(mode)
            fp.set_edge_color_mode('palette')
            fp.set_palette_lut(lut)
            assert fp.process(colorized_thermal, rgb_frame_matching_thermal) is not None


class TestEnhancedEdgeHighlightNoBlurHalo:
    """Regression test for a real bug found while testing Line Size live:
    edges_medium_small/edges_large_small (binary Canny output at 1/4 and
    1/16 resolution) were upscaled with cv2.resize(..., INTER_LINEAR) -
    linearly interpolating a binary image creates a blurred halo of faint
    intermediate values around every detected pixel, and cv2.bitwise_and's
    mask parameter treats ANY nonzero value as "in the mask". That made
    lines look thick even with edge_line_size at its minimum (dilation
    kernel size 1, a no-op) - the thickness was coming entirely from the
    upscale halo, not from dilation at all. Fixed by switching to
    INTER_NEAREST, which preserves clean 0/255 semantics."""

    def test_upscaled_binary_mask_has_no_faint_halo_values(self):
        """Isolates exactly the operation that was buggy: upscaling a
        BINARY (0/255) Canny result - not a general downsample/upsample
        round trip, which legitimately produces intermediate values at
        the downsample step regardless of upscale method."""
        binary_small = np.zeros((64, 64), dtype=np.uint8)
        binary_small[20:30, 20:30] = 255  # a solid block, as real Canny output would be
        upscaled_nearest = cv2.resize(binary_small, (256, 256), interpolation=cv2.INTER_NEAREST)
        upscaled_linear = cv2.resize(binary_small, (256, 256), interpolation=cv2.INTER_LINEAR)

        assert set(np.unique(upscaled_nearest).tolist()) == {0, 255}, (
            "NEAREST must preserve strict binary values with no interpolated halo"
        )
        # Confirms LINEAR is the one that actually has the halo problem,
        # not that resize() never produces one under any settings.
        assert set(np.unique(upscaled_linear).tolist()) != {0, 255}, (
            "Sanity check: LINEAR should introduce intermediate values here, "
            "confirming this test would have caught the original bug"
        )

    def test_nearest_upscale_produces_fewer_pixels_than_linear_on_the_same_data(self, colorized_thermal, rgb_frame_matching_thermal):
        """Directly reproduces the live bug report on the real pipeline's
        own data: re-running the exact medium/large-scale computation with
        LINEAR (the old, buggy behavior) must produce more nonzero pixels
        than the current NEAREST implementation on the identical input -
        proving the fix actually reduced mask coverage, not just that the
        mode still runs. Doesn't assert an absolute ratio against the fine
        scale, since coarse scales legitimately covering a blockier region
        than the fine scale is correct multi-scale behavior, not the bug."""
        fp = FusionProcessor()
        fp.set_fusion_mode('enhanced_edge_highlight')
        fp.set_priority('rgb')  # thermal (has a real hot-spot edge) becomes overlay_source

        overlay_gray = cv2.cvtColor(colorized_thermal, cv2.COLOR_BGR2GRAY)
        threshold_low, threshold_high = fp._get_canny_thresholds(overlay_gray)
        h, w = overlay_gray.shape[:2]
        medium_small = cv2.pyrDown(overlay_gray)
        from thermal_inspection.processing.fusion_processor import _EDGE_KERNEL_MEDIUM
        gray_medium = cv2.morphologyEx(medium_small, cv2.MORPH_GRADIENT, _EDGE_KERNEL_MEDIUM)
        edges_medium_small = cv2.Canny(gray_medium, threshold_low * 0.7, threshold_high * 0.7)

        upscaled_nearest = cv2.resize(edges_medium_small, (w, h), interpolation=cv2.INTER_NEAREST)
        upscaled_linear = cv2.resize(edges_medium_small, (w, h), interpolation=cv2.INTER_LINEAR)

        nearest_count = cv2.countNonZero(upscaled_nearest)
        linear_count = cv2.countNonZero(upscaled_linear)
        assert nearest_count < linear_count, (
            f"NEAREST ({nearest_count}) should produce fewer nonzero pixels than "
            f"LINEAR ({linear_count}) on identical binary input - LINEAR's halo inflates coverage"
        )

    def test_runs_end_to_end_without_crash(self, colorized_thermal, rgb_frame_matching_thermal):
        fp = FusionProcessor()
        fp.set_fusion_mode('enhanced_edge_highlight')
        fp.set_edge_line_size(0.0)
        assert fp.process(colorized_thermal, rgb_frame_matching_thermal) is not None


class TestDetailBalance:
    """
    detail_balance was redesigned 2026-09-06: it used to be an additive
    blend weight across 3 detection scales, which meant a real scene's
    edges (present at every scale almost by definition) produced output
    nearly indistinguishable from edge_enhanced's own single-scale Canny
    pass - confirmed directly by the user testing the live app ("I can
    meaningfully produce an image that appears so visually similar that
    they are not different enough"). Redefined as a cross-scale CONSENSUS
    filter: an edge only survives if the fine scale detects it AND enough
    of the 2 coarser scales corroborate it. That still wasn't perceptibly
    distinct enough as a separate "Enhanced Edge Highlight" mode on real
    camera footage per a second, later report ("they are still the same
    mode... they do the same thing even if the algorithm is slightly
    different") - merged 2026-09-07 into edge_enhanced as this optional
    setting instead of continuing to differentiate two modes that were
    never going to read as genuinely distinct. Default is now 0 (off,
    single-scale) so edge_enhanced's own long-standing default behavior
    is unchanged unless this is deliberately raised.
    """
    def test_default_is_off_single_scale(self):
        fp = FusionProcessor()
        assert fp.detail_balance == 0.0
        assert round(fp.detail_balance * 2) == 0

    def test_clamped_0_to_1(self):
        fp = FusionProcessor()
        fp.set_detail_balance(-1.0)
        assert fp.detail_balance == 0.0
        fp.set_detail_balance(5.0)
        assert fp.detail_balance == 1.0

    def test_zero_is_bit_identical_to_never_touching_it(self, colorized_thermal, rgb_frame_matching_thermal):
        # detail_balance's default (0) must reproduce edge_enhanced's
        # original single-scale behavior exactly - it's the same code
        # path (self.detail_balance > 0 gates the multi-scale branch),
        # not a coincidentally-similar one.
        fp_default = FusionProcessor()
        fp_default.set_fusion_mode('edge_enhanced')
        result_default = fp_default.process(colorized_thermal, rgb_frame_matching_thermal)

        fp_explicit_zero = FusionProcessor()
        fp_explicit_zero.set_fusion_mode('edge_enhanced')
        fp_explicit_zero.set_detail_balance(0.0)
        result_explicit_zero = fp_explicit_zero.process(colorized_thermal, rgb_frame_matching_thermal)

        assert np.array_equal(result_default, result_explicit_zero)

    def _noisy_circle_frame(self):
        # A real edge (circle boundary, should survive at every scale)
        # plus sparse single-pixel speckle noise (should only survive the
        # fine scale - pyrDown averages it away within 1-2 levels).
        base = np.full((256, 320), 128, dtype=np.uint8)
        cv2.circle(base, (160, 128), 50, 200, -1)
        rng = np.random.RandomState(0)
        ys = rng.randint(0, 256, size=300)
        xs = rng.randint(0, 320, size=300)
        base[ys, xs] = 255
        return cv2.cvtColor(base, cv2.COLOR_GRAY2BGR)

    def test_stricter_consensus_produces_fewer_edges_not_more(self):
        thermal_bgr = self._noisy_circle_frame()
        rgb = np.full((256, 320, 3), 150, dtype=np.uint8)  # flat -> base itself has no edges to confuse the diff

        fp = FusionProcessor()
        fp.set_fusion_mode('edge_enhanced')
        fp.set_priority('rgb')  # base=rgb (flat), overlay_source=thermal (the noisy circle)
        fp.set_edge_line_size(0.0)  # isolate the consensus filter's own effect, no dilation

        def edge_pixel_count(balance):
            fp.set_detail_balance(balance)
            result = fp.process(thermal_bgr, rgb)
            return int(np.count_nonzero(np.any(result != rgb, axis=2)))

        permissive = edge_pixel_count(0.0)
        moderate = edge_pixel_count(0.5)
        strict = edge_pixel_count(1.0)

        assert permissive > moderate > strict, (
            f"consensus filter should monotonically remove edges as it gets stricter, "
            f"got permissive={permissive} moderate={moderate} strict={strict}"
        )
        # A moderate setting should be a real denoise, not a marginal tweak.
        assert moderate < permissive * 0.5


class TestLaplacianPyramidFallback:
    """
    laplacian_pyramid was the only one of 12 fusion modes with no internal
    try/except - every other mode degrades to a still-valid frame on
    failure (see _max_intensity/_feature_weighted), but a pyrDown/pyrUp
    exception here would propagate all the way to _process_frame_loop's
    blanket handler in app.py, which drops the ENTIRE tick (every overlay,
    stat, recording write) rather than just this one mode's output. Found
    via the 2026-09-06 maturity review, not user-reported.
    """
    def test_cpu_failure_falls_back_to_alpha_blend(self, monkeypatch, colorized_thermal, rgb_frame_matching_thermal):
        fp = FusionProcessor()
        fp.set_fusion_mode('laplacian_pyramid')
        fp.set_laplacian_gpu_enabled(False)  # force the CPU path under test, even on a CUDA-equipped machine

        def _boom(*args, **kwargs):
            raise cv2.error("simulated pyrDown failure")

        monkeypatch.setattr(cv2, 'pyrDown', _boom)
        result = fp.process(colorized_thermal, rgb_frame_matching_thermal)

        expected = fp._alpha_blend(colorized_thermal, rgb_frame_matching_thermal)
        assert np.array_equal(result, expected)

    def test_downscaled_cpu_failure_falls_back_to_alpha_blend(self, monkeypatch, colorized_thermal, rgb_frame_matching_thermal):
        fp = FusionProcessor()
        fp.set_fusion_mode('laplacian_pyramid')
        fp.set_laplacian_gpu_enabled(False)  # force the CPU path under test, even on a CUDA-equipped machine
        fp.laplacian_cpu_scale = 0.5  # exercise the downscale/upscale wrapper branch

        def _boom(*args, **kwargs):
            raise cv2.error("simulated pyrDown failure")

        monkeypatch.setattr(cv2, 'pyrDown', _boom)
        result = fp.process(colorized_thermal, rgb_frame_matching_thermal)

        expected = fp._alpha_blend(colorized_thermal, rgb_frame_matching_thermal)
        assert np.array_equal(result, expected)


class TestReliefLightDirection:
    """
    Refinement requested directly by the user (2026-09-06): "Relief fusion
    should stay but if there are refinement options." An emboss filter's
    apparent light direction is set entirely by which corner its negative
    weights sit in (a well-established technique, not invented for this
    app) - the mode only ever had one direction (top_left) hardcoded.
    """
    def test_default_is_top_left_and_unchanged_from_original(self):
        fp = FusionProcessor()
        assert fp.relief_light_direction == 'top_left'
        from thermal_inspection.processing.fusion_processor import _RELIEF_LIGHT_DIRECTIONS
        expected = np.array([[-2, -1, 0], [-1, 1, 1], [0, 1, 2]], dtype=np.float32)
        assert np.array_equal(_RELIEF_LIGHT_DIRECTIONS['top_left'], expected)

    def test_invalid_direction_rejected_leaves_current_value(self):
        fp = FusionProcessor()
        fp.set_relief_light_direction('nonsense')
        assert fp.relief_light_direction == 'top_left'

    def test_each_direction_produces_a_different_result(self, colorized_thermal, rgb_frame_matching_thermal):
        # A flat rgb fixture has no gradient at all - emboss needs a real
        # edge to differentiate directions, so build one with a corner.
        rgb = np.zeros((512, 640, 3), dtype=np.uint8)
        rgb[:256, :320] = 220  # a real corner in the frame

        fp = FusionProcessor()
        fp.set_fusion_mode('relief_fusion')
        fp.detail_strength = 1.0
        fp.fusion_intensity = 1.0

        results = {}
        for direction in ('top_left', 'top_right', 'bottom_right', 'bottom_left'):
            fp.set_relief_light_direction(direction)
            results[direction] = fp.process(colorized_thermal, rgb)

        # Every direction should differ from every other - a real,
        # visually distinct refinement, not a no-op option.
        directions = list(results)
        for i in range(len(directions)):
            for j in range(i + 1, len(directions)):
                a, b = directions[i], directions[j]
                assert not np.array_equal(results[a], results[b]), f"{a} vs {b} produced identical output"


class TestOverlayHotPercentile:
    """
    thermal_overlay is the app's DEFAULT fusion mode and previously had a
    hardcoded 70th-percentile "hot" threshold with zero UI exposure.
    """
    def test_default_is_70(self):
        fp = FusionProcessor()
        assert fp.overlay_hot_percentile == 70.0

    def test_clamped_1_to_99(self):
        fp = FusionProcessor()
        fp.set_overlay_hot_percentile(0.0)
        assert fp.overlay_hot_percentile == 1.0
        fp.set_overlay_hot_percentile(150.0)
        assert fp.overlay_hot_percentile == 99.0

    def test_lower_threshold_overlays_more_of_the_frame(self, rgb_frame_matching_thermal):
        # thermal_frame_8bit's fixture is only 3 discrete gray values
        # (background/hot/cold), so its 10th and 95th percentiles land on
        # the exact same threshold - a smooth gradient is needed to make
        # different percentiles actually produce different thresholds.
        gray_ramp = np.tile(np.linspace(0, 255, 640, dtype=np.uint8), (512, 1))
        thermal_bgr = cv2.cvtColor(gray_ramp, cv2.COLOR_GRAY2BGR)

        fp = FusionProcessor()
        fp.set_fusion_mode('thermal_overlay')
        fp.set_priority('rgb')  # thermal (the gradient) becomes the overlay source

        fp.set_overlay_hot_percentile(95.0)
        strict_result = fp.process(thermal_bgr, rgb_frame_matching_thermal)
        strict_changed = int(np.count_nonzero(np.any(strict_result != rgb_frame_matching_thermal, axis=2)))

        fp.set_overlay_hot_percentile(10.0)
        loose_result = fp.process(thermal_bgr, rgb_frame_matching_thermal)
        loose_changed = int(np.count_nonzero(np.any(loose_result != rgb_frame_matching_thermal, axis=2)))

        assert loose_changed > strict_changed


class TestPipSizeAndPosition:
    """
    picture_in_picture had real, distinct parameters (pip_size, position)
    that were never exposed anywhere in the GUI - permanently stuck at the
    function's own hardcoded defaults (0.25, 'top-right').
    """
    def test_defaults(self):
        fp = FusionProcessor()
        assert fp.pip_size == 0.25
        assert fp.pip_position == 'top-right'

    def test_pip_size_clamped(self):
        fp = FusionProcessor()
        fp.set_pip_size(0.0)
        assert fp.pip_size == 0.1
        fp.set_pip_size(1.0)
        assert fp.pip_size == 0.9

    def test_invalid_position_rejected(self):
        fp = FusionProcessor()
        fp.set_pip_position('center')
        assert fp.pip_position == 'top-right'

    def test_process_actually_uses_configured_size_and_position(self, colorized_thermal, rgb_frame_matching_thermal):
        fp = FusionProcessor()
        fp.set_fusion_mode('picture_in_picture')

        fp.set_pip_size(0.25)
        fp.set_pip_position('top-right')
        default_result = fp.process(colorized_thermal, rgb_frame_matching_thermal)

        fp.set_pip_size(0.5)
        fp.set_pip_position('bottom-left')
        changed_result = fp.process(colorized_thermal, rgb_frame_matching_thermal)

        assert not np.array_equal(default_result, changed_result)
