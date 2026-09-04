"""
Regression test for a Low-priority debt item (2026-09-04): parallax
correction's GPU (torch/CUDA) remap path (_remap_thermal_gpu) exists,
is kept "available" (see _remap_thermal's docstring - measured slower
than the CPU path in the real call chain, so not wired into the
default path), but had zero test coverage - the exact class of debt
this ledger already flags as risky ("hide real bugs" per media_recorder/
settings_manager's history). This doesn't change any behavior; it just
makes sure the dead-by-default path still actually works before it
silently bit-rots further.

Requires a real CUDA GPU (torch.cuda.is_available()) - skipped
automatically without one, matching this codebase's other GPU-parity
tests (test_gpu_cpu_parity.py, test_fusion_3d_gpu_contract.py).
"""
import numpy as np
import pytest

torch = pytest.importorskip("torch")

from thermal_inspection.processing.parallax_compensator import ParallaxCompensator

requires_cuda = pytest.mark.skipif(
    not torch.cuda.is_available(), reason="requires a real CUDA GPU"
)


def _make_flow_map(h, w, seed=1):
    rng = np.random.default_rng(seed)
    return rng.uniform(-8, 8, size=(h, w, 2)).astype(np.float32)


@requires_cuda
@pytest.mark.unit
def test_gpu_remap_matches_cpu_remap():
    comp = ParallaxCompensator(depth_method="simplified")
    comp._remap_gpu_device = "cuda"
    h, w = 128, 160
    rng = np.random.default_rng(2)
    thermal = rng.integers(0, 255, size=(h, w, 3), dtype=np.uint8)
    flow_map = _make_flow_map(h, w)

    cpu_result = comp._remap_thermal_cpu(thermal, flow_map, h, w)
    gpu_result = comp._remap_thermal_gpu(thermal, flow_map, h, w)

    assert cpu_result.shape == gpu_result.shape == thermal.shape
    assert cpu_result.dtype == gpu_result.dtype == np.uint8

    diff = np.abs(cpu_result.astype(np.int16) - gpu_result.astype(np.int16))
    # cv2.remap (CPU) and F.grid_sample (GPU) are different bilinear-
    # interpolation implementations - not bit-identical, but should agree
    # closely on the same shift field.
    assert diff.mean() <= 3.0, f"GPU/CPU remap mean diff {diff.mean():.2f}/255 too high"
    assert diff.max() <= 40, f"GPU/CPU remap max diff {diff.max()}/255 too high"


@requires_cuda
@pytest.mark.unit
def test_gpu_coord_grid_cached_by_shape():
    comp = ParallaxCompensator(depth_method="simplified")
    comp._remap_gpu_device = "cuda"
    h, w = 96, 112
    thermal = np.zeros((h, w, 3), dtype=np.uint8)
    flow_map = _make_flow_map(h, w)

    comp._remap_thermal_gpu(thermal, flow_map, h, w)
    cached_grid = comp._remap_gpu_coord_grid_xy
    cached_shape = comp._remap_gpu_coord_grid_shape

    comp._remap_thermal_gpu(thermal, flow_map, h, w)
    assert comp._remap_gpu_coord_grid_shape == cached_shape
    assert comp._remap_gpu_coord_grid_xy is cached_grid, (
        "a second call at the same (h, w) must reuse the cached coordinate "
        "grid tensors, not rebuild them"
    )

    h2, w2 = 64, 80
    comp._remap_thermal_gpu(np.zeros((h2, w2, 3), dtype=np.uint8), _make_flow_map(h2, w2), h2, w2)
    assert comp._remap_gpu_coord_grid_shape == (h2, w2)
    assert comp._remap_gpu_coord_grid_xy is not cached_grid
