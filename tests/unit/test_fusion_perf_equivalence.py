"""
Output-equivalence guards for the 2026-09-23 fusion-pipeline performance
pass. Each optimization there was verified bit-identical against the code
it replaced (project rule: a speedup must never silently change fused
output). These tests pin that down by comparing each optimized path
against a straight reference implementation of the ORIGINAL formula, so
a future edit that drifts the numbers fails here instead of being noticed
live as "the fusion looks different".

Also covers the one intentional behavior change in that pass:
apply_3d_visualization_fused only takes its feature_weighted GPU shortcut
when feature_weighted is actually the selected 2D Fusion mode.
"""
import cv2
import numpy as np
import pytest

from thermal_inspection.processing.fusion_processor import FusionProcessor
from thermal_inspection.processing.parallax_compensator import ParallaxCompensator
import thermal_inspection.gui.panels.fusion_3d_panel as fusion_3d_panel


def _scene(seed=0, h=512, w=640):
    rng = np.random.default_rng(seed)
    gray = cv2.GaussianBlur(rng.integers(0, 256, (h, w), dtype=np.uint8), (9, 9), 0)
    thermal = cv2.applyColorMap(gray, cv2.COLORMAP_INFERNO)
    rgb = np.full((h, w, 3), 90, np.uint8)
    for _ in range(30):
        x0, y0 = int(rng.integers(0, w)), int(rng.integers(0, h))
        color = tuple(int(c) for c in rng.integers(0, 256, 3))
        cv2.rectangle(rgb, (x0, y0), (x0 + int(rng.integers(10, 150)), y0 + int(rng.integers(10, 150))), color, -1)
    rgb = np.clip(rgb + rng.normal(0, 5, rgb.shape), 0, 255).astype(np.uint8)
    return thermal, rgb


def _reference_edge_blend(base, edges_normalized, color_img):
    """edge_enhanced's original full-frame lerp, verbatim."""
    alpha = np.repeat(edges_normalized[:, :, np.newaxis], 3, axis=2)
    base_f = base.astype(np.float32)
    diff = np.subtract(color_img, base_f)
    diff *= alpha
    base_f += diff
    return np.clip(base_f, 0, 255).astype(np.uint8)


@pytest.mark.unit
class TestEdgeEnhancedMaskedBlend:

    @pytest.mark.parametrize("priority", ["thermal", "rgb"])
    @pytest.mark.parametrize("palette", [False, True])
    @pytest.mark.parametrize("sobel_alpha", [False, True])
    def test_matches_full_frame_lerp(self, monkeypatch, priority, palette, sobel_alpha):
        thermal, rgb = _scene(seed=1)
        lut = cv2.applyColorMap(np.arange(256, dtype=np.uint8).reshape(256, 1),
                                cv2.COLORMAP_INFERNO).reshape(256, 3)
        proc = FusionProcessor()
        proc.set_fusion_mode("edge_enhanced")
        proc.set_priority(priority)
        proc.set_intensity(0.7)
        proc.set_edge_blur(9)
        proc.set_edge_line_size(0.4)
        proc.set_sobel_alpha_enabled(sobel_alpha)
        if palette:
            proc.set_palette_lut(lut)
            proc.set_edge_color_mode("palette")

        # Capture the exact alpha map the real code computes, by recording
        # what _detect_edges/_sobel_alpha feed into the blend - simplest is
        # to recompute it the same way _edge_enhanced does.
        base = rgb if priority == "rgb" else thermal
        source = thermal if priority == "rgb" else rgb
        gray = cv2.cvtColor(source, cv2.COLOR_BGR2GRAY)
        edges = proc._detect_edges(gray, *proc._get_canny_thresholds(gray))
        dilation = 1 + int(round(proc.edge_line_size * 4))
        if dilation > 1:
            edges = cv2.dilate(edges, proc._get_dilation_kernel(dilation))
        before = edges
        edges = cv2.GaussianBlur(edges, (proc.edge_blur_kernel, proc.edge_blur_kernel), 0)
        np.maximum(edges, before, out=edges)
        if sobel_alpha:
            alpha = proc._sobel_alpha_within_mask(gray, edges)
        else:
            alpha = edges.astype(np.float32) / 255.0
        alpha *= proc.fusion_intensity
        if palette:
            color_img = lut[gray].astype(np.float32)
        else:
            color = proc.rgb_priority_edge_color if priority == "rgb" else proc.thermal_priority_edge_color
            color_img = np.full(base.shape, color, dtype=np.float32)

        expected = _reference_edge_blend(base, alpha, color_img)
        actual = proc.process(thermal, rgb)
        assert np.array_equal(actual, expected)


@pytest.mark.unit
def test_pca_fusion_covariance_matches_np_cov():
    thermal, rgb = _scene(seed=3)
    proc = FusionProcessor()
    proc.set_fusion_mode("pca_fusion")
    t = cv2.cvtColor(thermal, cv2.COLOR_BGR2GRAY).astype(np.float32).reshape(-1)
    r = cv2.cvtColor(rgb, cv2.COLOR_BGR2GRAY).astype(np.float32).reshape(-1)
    _, vecs = np.linalg.eigh(np.cov(np.vstack([t, r])))
    weights = np.abs(vecs[:, -1])
    w_t, w_r = float(weights[0] / weights.sum()), float(weights[1] / weights.sum())
    w_t = (1.0 - proc.fusion_intensity) * w_t + proc.fusion_intensity * 1.0
    expected = cv2.addWeighted(thermal, w_t, rgb, 1.0 - w_t, 0)
    assert np.array_equal(proc.process(thermal, rgb), expected)


@pytest.mark.unit
class TestParallaxRemapCache:

    def test_manual_shift_change_is_not_served_from_stale_cache(self):
        thermal, rgb = _scene(seed=4)
        comp = ParallaxCompensator()
        comp.set_correction_target("thermal")
        comp.set_manual_shift(6, -3)
        comp.apply_correction(thermal, rgb)
        comp.set_manual_shift(-9, 5)
        out, _ = comp.apply_correction(thermal, rgb)

        fresh = ParallaxCompensator()
        fresh.set_correction_target("thermal")
        fresh.set_manual_shift(-9, 5)
        expected, _ = fresh.apply_correction(thermal, rgb)
        assert np.array_equal(out, expected)

    def test_repeated_calls_track_live_frame_content(self):
        """Cached remap coordinates must never mean a cached OUTPUT - each
        call still warps the frame it's given."""
        thermal_a, rgb = _scene(seed=5)
        thermal_b, _ = _scene(seed=6)
        comp = ParallaxCompensator()
        comp.set_correction_target("thermal")
        comp.set_manual_shift(4, 2)
        out_a, _ = comp.apply_correction(thermal_a, rgb)
        out_b, _ = comp.apply_correction(thermal_b, rgb)

        fresh = ParallaxCompensator()
        fresh.set_correction_target("thermal")
        fresh.set_manual_shift(4, 2)
        expected_b, _ = fresh.apply_correction(thermal_b, rgb)
        assert not np.array_equal(out_a, out_b)
        assert np.array_equal(out_b, expected_b)


@pytest.mark.unit
def test_point_cloud_preview_selects_same_points_as_mask_then_subsample():
    """update_from_realsense now subsamples valid INDICES rather than
    boolean-mask-copying every valid point first - same selected points."""
    class _Recorder:
        alpha = 0.5
        color_mode = "fusion"
        last = None

        def update_point_cloud(self, vertices, colors):
            self.last = (vertices, colors)

    rng = np.random.default_rng(7)
    n = 200_000
    vertices = np.column_stack([
        rng.normal(0, 1, n), rng.normal(0, 1, n), rng.uniform(-0.5, 12, n),
    ]).astype(np.float32)
    uv = rng.uniform(0, 1, (n, 2)).astype(np.float32)
    thermal, rgb = _scene(seed=8)

    rec = _Recorder()
    fusion_3d_panel.Fusion3DPointCloudView.update_from_realsense(rec, vertices, uv, rgb, thermal)

    valid = (vertices[:, 2] > 0) & (vertices[:, 2] <= fusion_3d_panel.MAX_VALID_DEPTH_M)
    ref_v = vertices[valid]
    idx = np.linspace(0, ref_v.shape[0] - 1, fusion_3d_panel.MAX_PREVIEW_POINTS).astype(np.int64)
    assert np.array_equal(rec.last[0], ref_v[idx])


@pytest.mark.unit
class TestFused3DRespectsSelected2DMode:

    def _patch_gpu_ready(self, monkeypatch, proc, fw_calls):
        monkeypatch.setattr(fusion_3d_panel, "_resolve_3d_gpu", lambda: True)
        monkeypatch.setattr(proc, "_resolve_feature_weighted_gpu", lambda: True)

        def _fw_tensor(*_a, **_k):
            fw_calls.append(1)
            raise RuntimeError("stop after proving the fused path was taken")
        monkeypatch.setattr(proc, "_feature_weighted_gpu_tensor", _fw_tensor)
        monkeypatch.setattr(
            fusion_3d_panel, "apply_3d_visualization",
            lambda mode, image, depth, **kw: ("two-step", image),
        )

    def test_non_feature_weighted_mode_uses_its_own_blend(self, monkeypatch):
        pytest.importorskip("torch")
        thermal, rgb = _scene(seed=9)
        depth = np.full(thermal.shape[:2], 2.0, np.float32)
        proc = FusionProcessor()
        proc.set_fusion_mode("alpha_blend")
        fw_calls = []
        self._patch_gpu_ready(monkeypatch, proc, fw_calls)

        tag, base = fusion_3d_panel.apply_3d_visualization_fused("relief", thermal, rgb, depth, proc)

        assert fw_calls == [], "fused path must not blend with feature_weighted when alpha_blend is selected"
        assert tag == "two-step"
        assert np.array_equal(base, proc.process(thermal, rgb))

    def test_feature_weighted_mode_still_takes_fused_path(self, monkeypatch):
        pytest.importorskip("torch")
        thermal, rgb = _scene(seed=10)
        depth = np.full(thermal.shape[:2], 2.0, np.float32)
        proc = FusionProcessor()
        proc.set_fusion_mode("feature_weighted")
        proc._fw_torch_device = "cpu"
        fw_calls = []
        self._patch_gpu_ready(monkeypatch, proc, fw_calls)

        fusion_3d_panel.apply_3d_visualization_fused("relief", thermal, rgb, depth, proc)

        # >= 1, not == 1: the patched tensor core raises, so the fused path
        # falls back to process(), whose own feature_weighted GPU dispatch
        # calls the same patched function once more.
        assert len(fw_calls) >= 1
