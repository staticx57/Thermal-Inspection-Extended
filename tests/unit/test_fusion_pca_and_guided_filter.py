"""
Tests for two new fusion modes added 2026-09-07, following a direct
request to implement findings from a fusion-technique literature search
(logged as backlog ideas the prior round, not yet implemented):

- PCA Fusion: classical spatial-domain technique - blends the two
  sources using frame-global weights from a 2x2 PCA over their
  (thermal, rgb) grayscale intensity pairs, so a source with more
  overall frame variance (more "informative" globally) gets more weight
  automatically, without needing feature_weighted's per-pixel machinery.
- Guided Filter Fusion: a single-scale simplification of Li/Kang/Hu's
  guided-filter fusion scheme - saliency (local abs-Laplacian) per
  source, guided-filter-refined into a per-pixel blend weight.

Both were verified via direct debug scripts against synthetic scenes
before being written up as tests here (per this project's established
practice of proving numeric behavior rather than asserting on faith).
"""
import cv2
import numpy as np
import pytest

from thermal_inspection.processing.fusion_processor import FusionProcessor


@pytest.fixture
def colorized_thermal(thermal_frame_8bit):
    return cv2.cvtColor(thermal_frame_8bit, cv2.COLOR_GRAY2BGR)


class TestModesRegistered:
    def test_both_modes_in_available_modes(self):
        assert 'pca_fusion' in FusionProcessor.AVAILABLE_FUSION_MODES
        assert 'guided_filter_fusion' in FusionProcessor.AVAILABLE_FUSION_MODES

    def test_both_modes_have_human_readable_labels(self):
        assert FusionProcessor.FUSION_MODE_LABELS['pca_fusion'] == 'PCA Fusion'
        assert FusionProcessor.FUSION_MODE_LABELS['guided_filter_fusion'] == 'Guided Filter Fusion'


class TestPCAFusion:
    def test_zero_variance_source_gets_zero_weight(self):
        # rgb is perfectly flat (zero variance) - PCA has no information
        # to justify giving it any weight, so the result should be pure
        # thermal (verified directly: measured mean abs diff from thermal
        # is exactly 0.0 on this scene).
        thermal_gray = np.full((256, 320), 128, dtype=np.uint8)
        cv2.circle(thermal_gray, (160, 128), 60, 220, -1)
        thermal = cv2.cvtColor(thermal_gray, cv2.COLOR_GRAY2BGR)
        rgb_flat = np.full((256, 320, 3), 150, dtype=np.uint8)

        fp = FusionProcessor()
        fp.set_fusion_mode('pca_fusion')
        result = fp.process(thermal, rgb_flat)
        assert np.array_equal(result, thermal)

    def test_priority_bias_shifts_result_toward_preferred_source(self):
        size = 256
        thermal_gray = np.full((size, size), 128, dtype=np.uint8)
        cv2.circle(thermal_gray, (80, 128), 50, 200, -1)
        thermal = cv2.cvtColor(thermal_gray, cv2.COLOR_GRAY2BGR)

        rgb_gray = np.full((size, size), 128, dtype=np.uint8)
        cv2.circle(rgb_gray, (176, 128), 50, 200, -1)
        rgb = cv2.cvtColor(rgb_gray, cv2.COLOR_GRAY2BGR)

        fp = FusionProcessor()
        fp.set_fusion_mode('pca_fusion')

        fp.set_priority('thermal')
        r_thermal_biased = fp.process(thermal, rgb)
        fp.set_priority('rgb')
        r_rgb_biased = fp.process(thermal, rgb)

        diff_thermal_biased = np.abs(r_thermal_biased.astype(int) - thermal.astype(int)).mean()
        diff_rgb_biased = np.abs(r_rgb_biased.astype(int) - thermal.astype(int)).mean()
        assert diff_thermal_biased < diff_rgb_biased

    def test_degenerate_identical_flat_sources_does_not_crash(self):
        flat = np.full((64, 64, 3), 100, dtype=np.uint8)
        fp = FusionProcessor()
        fp.set_fusion_mode('pca_fusion')
        result = fp.process(flat, flat)
        assert result.shape == flat.shape
        assert not np.isnan(result.astype(np.float64)).any()

    def test_strength_has_real_effect_when_priority_opposes_pca(self):
        # Live-reported (2026-09-07): "the strength slider has very
        # minimal effect." Root cause: PCA's own weight is very often
        # already saturated near 0 or 1 (thermal and visible rarely have
        # comparable variance), so the OLD multiplier-based bias had
        # nothing left to boost when Priority already agreed with PCA -
        # confirmed directly on this same scene: bit-identical to pure
        # thermal at every intensity 0.0-1.0 before the fix. The fix is
        # only visible when Priority OPPOSES what PCA would pick on its
        # own (asking to force more RGB through when PCA's own weighting
        # already strongly favors thermal, or vice versa) - when Priority
        # agrees with PCA, both ends of the lerp are the same value and a
        # small Strength effect is the CORRECT result, not a bug.
        thermal_gray = np.full((512, 640), 120, dtype=np.uint8)
        cv2.circle(thermal_gray, (320, 256), 100, 210, -1)
        thermal = cv2.cvtColor(thermal_gray, cv2.COLOR_GRAY2BGR)
        rng = np.random.RandomState(0)
        rgb_gray = (rng.rand(512, 640) * 60 + 100).astype(np.uint8)
        rgb = cv2.cvtColor(rgb_gray, cv2.COLOR_GRAY2BGR)

        fp = FusionProcessor()
        fp.set_fusion_mode('pca_fusion')
        fp.set_priority('rgb')  # opposes PCA's natural preference for the hot-spot thermal image

        diffs = []
        for intensity in (0.0, 0.5, 1.0):
            fp.fusion_intensity = intensity
            result = fp.process(thermal, rgb)
            diffs.append(np.abs(result.astype(int) - thermal.astype(int)).mean())

        assert diffs[0] == pytest.approx(0.0, abs=0.5)  # intensity=0 -> pure PCA weighting (~all thermal here)
        assert diffs[1] > diffs[0] + 5.0
        assert diffs[2] > diffs[1] + 5.0  # monotonic, substantial increase - not "minimal effect"

    def test_runs_end_to_end_on_standard_fixtures(self, colorized_thermal, rgb_frame_matching_thermal):
        fp = FusionProcessor()
        fp.set_fusion_mode('pca_fusion')
        result = fp.process(colorized_thermal, rgb_frame_matching_thermal)
        assert result is not None
        assert result.dtype == np.uint8


class TestGuidedFilterFusion:
    def test_output_is_valid_no_nan_correct_range(self, colorized_thermal, rgb_frame_matching_thermal):
        fp = FusionProcessor()
        fp.set_fusion_mode('guided_filter_fusion')
        result = fp.process(colorized_thermal, rgb_frame_matching_thermal)
        assert result.dtype == np.uint8
        assert not np.isnan(result.astype(np.float64)).any()
        assert result.min() >= 0
        assert result.max() <= 255

    def test_priority_bias_shifts_result_toward_preferred_source(self):
        # A blend against a uniform priority prior, not a multiplier on
        # raw (near-zero-almost-everywhere) saliency - see the method's
        # own comment for why the multiplier approach was tried first and
        # measured to barely move the result (87.8 vs 88.0 mean diff at
        # max bias) before being replaced with this blend.
        size = 256
        thermal_gray = np.full((size, size), 128, dtype=np.uint8)
        cv2.circle(thermal_gray, (80, 128), 50, 200, -1)
        thermal = cv2.cvtColor(thermal_gray, cv2.COLOR_GRAY2BGR)

        rgb_gray = np.full((size, size), 128, dtype=np.uint8)
        cv2.circle(rgb_gray, (176, 128), 50, 200, -1)
        rgb = cv2.cvtColor(rgb_gray, cv2.COLOR_GRAY2BGR)

        fp = FusionProcessor()
        fp.set_fusion_mode('guided_filter_fusion')
        fp.fusion_intensity = 1.0  # maximum bias

        fp.set_priority('thermal')
        r_thermal_biased = fp.process(thermal, rgb)
        fp.set_priority('rgb')
        r_rgb_biased = fp.process(thermal, rgb)

        # At maximum bias, priority should completely override saliency -
        # thermal-biased reproduces pure thermal exactly.
        assert np.array_equal(r_thermal_biased, thermal)
        diff_rgb_biased = np.abs(r_rgb_biased.astype(int) - thermal.astype(int)).mean()
        assert diff_rgb_biased > 5.0  # a real, substantial difference, not noise

    def test_degenerate_identical_flat_sources_does_not_crash(self):
        flat = np.full((64, 64, 3), 100, dtype=np.uint8)
        fp = FusionProcessor()
        fp.set_fusion_mode('guided_filter_fusion')
        result = fp.process(flat, flat)
        assert result.shape == flat.shape
        assert not np.isnan(result.astype(np.float64)).any()

    def test_unknown_fusion_mode_never_hit_since_both_are_dispatched(self, colorized_thermal, rgb_frame_matching_thermal):
        # Regression guard: process() has a fallback "unknown mode ->
        # alpha_blend" branch that would silently mask a typo in the
        # dispatch chain - confirm both new modes actually reach their
        # own implementation, not that fallback.
        fp = FusionProcessor()
        fp.set_fusion_mode('guided_filter_fusion')
        result_gf = fp.process(colorized_thermal, rgb_frame_matching_thermal)
        fp.set_fusion_mode('alpha_blend')
        result_alpha = fp.process(colorized_thermal, rgb_frame_matching_thermal)
        assert not np.array_equal(result_gf, result_alpha)

    def test_default_scale_is_half_and_clamped(self):
        fp = FusionProcessor()
        assert fp.guided_filter_scale == 0.5
        fp.set_guided_filter_scale(0.0)
        assert fp.guided_filter_scale == 0.25
        fp.set_guided_filter_scale(5.0)
        assert fp.guided_filter_scale == 1.0

    def test_downscaled_processing_stays_real_time_viable(self, colorized_thermal, rgb_frame_matching_thermal):
        # Full internal resolution measured at ~69ms/frame mean (up to
        # 109ms) on a 640x512 frame - would cap this mode under 15fps.
        # The default 0.5 scale measured at ~15.8ms/frame mean (up to
        # ~19ms) on the same frame size - a real, substantial fix, not a
        # marginal tweak. Asserting a generous upper bound here (not the
        # exact measured number, which will vary by machine) so this
        # guards against a future regression back toward the full-res
        # cost without being flaky on slower CI hardware.
        import time
        fp = FusionProcessor()
        fp.set_fusion_mode('guided_filter_fusion')
        for _ in range(3):
            fp.process(colorized_thermal, rgb_frame_matching_thermal)  # warmup
        times = []
        for _ in range(10):
            t0 = time.perf_counter()
            fp.process(colorized_thermal, rgb_frame_matching_thermal)
            times.append((time.perf_counter() - t0) * 1000)
        assert max(times) < 50.0, f"guided_filter_fusion took {max(times):.1f}ms, expected well under the full-res ~69-109ms range"

    def test_downscaled_and_full_res_produce_similar_but_not_identical_output(self, colorized_thermal, rgb_frame_matching_thermal):
        fp = FusionProcessor()
        fp.set_fusion_mode('guided_filter_fusion')
        fp.set_guided_filter_scale(1.0)
        result_full = fp.process(colorized_thermal, rgb_frame_matching_thermal)
        fp.set_guided_filter_scale(0.5)
        result_half = fp.process(colorized_thermal, rgb_frame_matching_thermal)
        # Not bit-identical (a real resolution/interpolation difference),
        # but should stay a reasonably close approximation, not wildly diverge.
        mean_diff = np.abs(result_full.astype(int) - result_half.astype(int)).mean()
        assert mean_diff < 15.0
