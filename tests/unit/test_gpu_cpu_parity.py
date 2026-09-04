"""
GPU/CPU numerical-parity regression tests (Medium #3 in the debt
ledger). Two code paths in this codebase are explicitly documented as
"not bit-identical to their CPU counterpart, by design - strictly more
precise, not a different algorithm":

- FusionProcessor's feature_weighted mode: the GPU path uses a
  sigmoid-of-difference blend weight (_FEATURE_WEIGHTED_SIGMOID_K)
  instead of the CPU path's numerically ill-conditioned ratio, to avoid
  amplifying tiny floating-point rounding differences into large visible
  discrepancies.

Both of those claims were previously verified only once, by hand, in a
scratch script during the session that introduced them - nothing in the
test suite would notice if a future edit widened that gap past "more
precise" into "a different result". These tests pin the acceptable
divergence bound instead of leaving it purely in code comments.

Requires a real CUDA GPU (both paths hard-require torch.cuda.is_available()
- see _resolve_feature_weighted_gpu) - skipped automatically without one.
"""
import cv2
import numpy as np
import pytest

torch = pytest.importorskip("torch")

from thermal_inspection.processing.fusion_processor import FusionProcessor

requires_cuda = pytest.mark.skipif(
    not torch.cuda.is_available(), reason="requires a real CUDA GPU"
)


def _textured_frame(seed: int) -> np.ndarray:
    """
    A smooth gradient plus per-pixel noise, textured enough that Sobel
    edge magnitude is nonzero almost everywhere - unlike a flat or
    single-hard-edge frame, this actually exercises the near-tied
    thermal/rgb edge-strength regime the sigmoid reformulation targets
    (the CPU ratio's denominator approaches zero exactly when the two
    edge strengths are close, which is where it used to amplify tiny
    floating-point rounding noise into large visible discrepancies).
    """
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:512, 0:640]
    gradient = (xx / 640.0 * 128 + yy / 512.0 * 64)
    noise = rng.normal(0, 12, size=(512, 640))
    frame = np.clip(gradient + noise, 0, 255).astype(np.uint8)
    return frame


@pytest.fixture
def textured_colorized_thermal():
    return cv2.cvtColor(_textured_frame(seed=1), cv2.COLOR_GRAY2BGR)


@pytest.fixture
def textured_rgb_frame():
    gray = _textured_frame(seed=2)
    return cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)


@requires_cuda
@pytest.mark.unit
def test_feature_weighted_gpu_cpu_parity(textured_colorized_thermal, textured_rgb_frame):
    cpu_proc = FusionProcessor(fusion_mode="feature_weighted")
    cpu_proc.set_feature_weighted_gpu_enabled(False)
    cpu_result = cpu_proc.process(textured_colorized_thermal, textured_rgb_frame)

    gpu_proc = FusionProcessor(fusion_mode="feature_weighted")
    gpu_proc.set_feature_weighted_gpu_enabled(True)
    gpu_result = gpu_proc.process(textured_colorized_thermal, textured_rgb_frame)

    assert cpu_result.shape == gpu_result.shape == textured_colorized_thermal.shape
    assert cpu_result.dtype == gpu_result.dtype == np.uint8

    diff = np.abs(cpu_result.astype(np.int16) - gpu_result.astype(np.int16))
    # Bound taken from the session that introduced the sigmoid reformulation:
    # 0 pixels measured beyond 20/255 diff at K=2.0 on a realistic frame.
    assert diff.max() <= 20, (
        f"GPU/CPU feature_weighted max diff {diff.max()}/255 exceeds the "
        "documented 'more precise, not different' bound"
    )
    assert diff.mean() <= 3.0, (
        f"GPU/CPU feature_weighted mean diff {diff.mean():.2f}/255 exceeds "
        "the expected parity bound"
    )
