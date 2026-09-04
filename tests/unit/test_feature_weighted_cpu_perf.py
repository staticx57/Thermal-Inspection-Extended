"""
Regression test for a Low-priority debt item (2026-09-04): re-examined
after "work on all Low items" - _feature_weighted_cpu's real-but-modest
timing variance (measured mean=19.5ms, min=15.1ms/max=33.5ms) turned out
to have an actual fixable cause after all: the blend step built a full
(H,W,3) weight array via np.repeat specifically to avoid a documented
(H,W,1)-broadcast slow path, but paid for allocating and filling that
whole extra array in exchange. Multiplying each of the 3 channels by the
plain (H,W) weight directly avoids both the broadcast slow path AND the
repeat allocation - measured ~36% faster (14.7ms -> 9.4ms mean) and
bit-identical, since it's the same arithmetic either way.
"""
import time
import numpy as np

from thermal_inspection.processing.fusion_processor import FusionProcessor


def _reference_repeat_based(fp, thermal, rgb):
    """Reproduces the previous (np.repeat-based) implementation exactly,
    to prove the new one is numerically identical, not just visually
    similar."""
    thermal_gray = __import__("cv2").cvtColor(thermal, __import__("cv2").COLOR_BGR2GRAY)
    rgb_gray = __import__("cv2").cvtColor(rgb, __import__("cv2").COLOR_BGR2GRAY)
    import cv2
    thermal_strength = cv2.Sobel(thermal_gray, cv2.CV_32F, 1, 1, ksize=3)
    rgb_strength = cv2.Sobel(rgb_gray, cv2.CV_32F, 1, 1, ksize=3)
    np.abs(thermal_strength, out=thermal_strength)
    np.abs(rgb_strength, out=rgb_strength)
    thermal_strength /= (thermal_strength.max() + 1e-6)
    rgb_strength /= (rgb_strength.max() + 1e-6)

    bias_multiplier = 1.0 + fp.fusion_intensity
    if fp.fusion_priority == 'thermal':
        thermal_strength *= bias_multiplier
    else:
        rgb_strength *= bias_multiplier

    from thermal_inspection.processing.fusion_processor import _FEATURE_WEIGHTED_SIGMOID_K
    thermal_strength -= rgb_strength
    thermal_strength *= _FEATURE_WEIGHTED_SIGMOID_K
    np.negative(thermal_strength, out=thermal_strength)
    np.exp(thermal_strength, out=thermal_strength)
    thermal_strength += 1.0
    np.reciprocal(thermal_strength, out=thermal_strength)

    weight_full = np.repeat(thermal_strength[:, :, np.newaxis], 3, axis=2)
    thermal_f = thermal.astype(np.float32)
    rgb_f = rgb.astype(np.float32)
    diff = np.subtract(thermal_f, rgb_f)
    diff *= weight_full
    rgb_f += diff
    return np.clip(rgb_f, 0, 255).astype(np.uint8)


class TestFeatureWeightedCpuCorrectness:
    def test_matches_repeat_based_reference_bit_identical(self):
        fp = FusionProcessor()
        fp.set_feature_weighted_gpu_enabled(False)
        rng = np.random.default_rng(9)
        yy, xx = np.mgrid[0:256, 0:320]
        gradient = (xx / 320.0 * 128 + yy / 256.0 * 64)
        noise = rng.normal(0, 12, size=(256, 320))
        thermal_gray = np.clip(gradient + noise, 0, 255).astype(np.uint8)
        rgb_gray = np.clip(gradient + rng.normal(0, 12, size=(256, 320)), 0, 255).astype(np.uint8)
        import cv2
        thermal = cv2.cvtColor(thermal_gray, cv2.COLOR_GRAY2BGR)
        rgb = cv2.cvtColor(rgb_gray, cv2.COLOR_GRAY2BGR)

        result = fp._feature_weighted_cpu(thermal, rgb)
        reference = _reference_repeat_based(fp, thermal, rgb)

        assert np.array_equal(result, reference)


class TestFeatureWeightedCpuPerf:
    def test_completes_quickly(self):
        """This function's whole-call timing has always had real,
        system-load-dependent variance (documented range 15-33ms even
        before this fix) that isn't really about this function itself -
        Sobel/cvtColor overhead swings with what else the machine is
        doing. This is a generous regression ceiling to catch a real
        slowdown, not a pinned target - see
        test_blend_step_isolated_is_faster_than_repeat_based below for
        the actual, reproducible improvement this fix measured."""
        fp = FusionProcessor()
        fp.set_feature_weighted_gpu_enabled(False)
        rng = np.random.default_rng(10)
        thermal = rng.integers(0, 255, size=(512, 640, 3), dtype=np.uint8)
        rgb = rng.integers(0, 255, size=(512, 640, 3), dtype=np.uint8)

        fp._feature_weighted_cpu(thermal, rgb)  # warm up
        n = 20
        t0 = time.perf_counter()
        for _ in range(n):
            fp._feature_weighted_cpu(thermal, rgb)
        elapsed_ms = (time.perf_counter() - t0) * 1000 / n

        assert elapsed_ms < 45.0, (
            f"_feature_weighted_cpu averaged {elapsed_ms:.2f}ms/call - "
            f"well above even this function's documented historical range"
        )

    def test_blend_step_isolated_is_faster_than_repeat_based(self):
        """Isolates just the fixed arithmetic (excludes Sobel/cvtColor,
        whose own cost swings with system load and would otherwise mask
        this comparison) - the per-channel-multiply blend must measurably
        beat the old np.repeat-based one on the exact same inputs, run
        back-to-back in the same process so both see the same load."""
        rng = np.random.default_rng(11)
        thermal = rng.integers(0, 255, size=(512, 640, 3), dtype=np.uint8)
        rgb = rng.integers(0, 255, size=(512, 640, 3), dtype=np.uint8)
        weight = rng.uniform(0, 1, size=(512, 640)).astype(np.float32)

        def repeat_based():
            weight_full = np.repeat(weight[:, :, np.newaxis], 3, axis=2)
            thermal_f = thermal.astype(np.float32)
            rgb_f = rgb.astype(np.float32)
            diff = np.subtract(thermal_f, rgb_f)
            diff *= weight_full
            rgb_f += diff
            return np.clip(rgb_f, 0, 255).astype(np.uint8)

        def per_channel():
            thermal_f = thermal.astype(np.float32)
            rgb_f = rgb.astype(np.float32)
            diff = np.subtract(thermal_f, rgb_f)
            diff[:, :, 0] *= weight
            diff[:, :, 1] *= weight
            diff[:, :, 2] *= weight
            rgb_f += diff
            np.clip(rgb_f, 0, 255, out=rgb_f)
            return rgb_f.astype(np.uint8)

        assert np.array_equal(repeat_based(), per_channel())

        n = 30
        repeat_based(); per_channel()  # warm up both
        t0 = time.perf_counter()
        for _ in range(n):
            repeat_based()
        repeat_ms = (time.perf_counter() - t0) * 1000 / n

        t0 = time.perf_counter()
        for _ in range(n):
            per_channel()
        per_channel_ms = (time.perf_counter() - t0) * 1000 / n

        assert per_channel_ms < repeat_ms, (
            f"per-channel blend ({per_channel_ms:.2f}ms) must beat the "
            f"old repeat-based one ({repeat_ms:.2f}ms) run in the same "
            "process under the same load"
        )
