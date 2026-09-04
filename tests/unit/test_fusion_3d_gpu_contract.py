"""
Contract test for fusion_3d_panel's tensor-core GPU mode functions
(_GPU_MODE_FN_TENSOR) - the exact bug class this guards against just
shipped silently: apply_3d_visualization_fused() always passes the full
mode-agnostic kwarg set (strength, near_m, far_m, interval_m,
gradient_style, fade_metric) to whichever tensor-core function the
current 3D mode maps to, the same way the numpy GPU/CPU functions each
swallow the kwargs they don't use via **_unused. _apply_depth_relief_gpu_tensor
was missing that catch-all, so every call raised TypeError, was caught by
apply_3d_visualization_fused's broad except Exception, and silently fell
back to the slower two-step path - PROFILE_3D_VIZ_FUSED never fired, and
nothing failed loudly enough to notice without an ad hoc log grep.

This test calls every _GPU_MODE_FN_TENSOR entry directly with that same
kwarg set on small CPU tensors, so it needs no real CUDA hardware and
would have caught the bug immediately (a raised TypeError, not a
swallowed one) before it ever reached apply_3d_visualization_fused.
"""
import cv2
import numpy as np
import pytest

torch = pytest.importorskip("torch")

import thermal_inspection.gui.panels.fusion_3d_panel as fusion_3d_panel


# The exact kwarg set apply_3d_visualization_fused always passes through,
# regardless of which mode is active - see its call site in app.py.
FULL_KWARG_SET = dict(
    strength=0.5,
    near_m=0.3,
    far_m=4.0,
    interval_m=0.5,
    gradient_style="color",
    fade_metric="distance",
)


@pytest.fixture(autouse=True)
def cpu_torch_device(monkeypatch):
    """
    The tensor-core functions read two module globals - _torch_device and
    _torch_kernels - that _resolve_3d_gpu() normally populates, but only
    after confirming torch.cuda.is_available(). Build the identical
    kernels on "cpu" instead (same construction as _resolve_3d_gpu's, see
    its docstring) so this test needs no real GPU.
    """
    gk_np = cv2.getGaussianKernel(5, 1.0).flatten()
    gk = torch.from_numpy(gk_np.astype(np.float32)).to("cpu")
    kx = gk.view(1, 1, 1, 5)
    ky = gk.view(1, 1, 5, 1)
    sobel_x = torch.tensor([[-1., 0., 1.], [-2., 0., 2.], [-1., 0., 1.]]).view(1, 1, 3, 3)
    sobel_y = torch.tensor([[-1., -2., -1.], [0., 0., 0.], [1., 2., 1.]]).view(1, 1, 3, 3)
    monkeypatch.setattr(fusion_3d_panel, "_torch_device", "cpu")
    monkeypatch.setattr(fusion_3d_panel, "_torch_kernels", (sobel_x, sobel_y, kx, ky))


@pytest.mark.unit
@pytest.mark.parametrize("mode", sorted(fusion_3d_panel._GPU_MODE_FN_TENSOR.keys()))
def test_tensor_core_function_accepts_full_kwarg_set(mode):
    tensor_fn = fusion_3d_panel._GPU_MODE_FN_TENSOR[mode]

    img_t = torch.zeros((1, 3, 8, 8), dtype=torch.float32)
    depth_t = torch.ones((1, 1, 8, 8), dtype=torch.float32)

    result = tensor_fn(img_t, depth_t, **FULL_KWARG_SET)

    assert result.shape == img_t.shape
    assert result.dtype == torch.float32
