"""
Mock-backend tests for Fusion3DPointCloudView.update_from_realsense
(High #3 in the debt ledger: camera-plugin/parallax/3D-Fusion code paths
had no automated coverage, and every real defect this session shipped -
a crash loop, a swallowed TypeError, a silent alignment gate - was found
by driving live hardware by hand, not by CI). Exercises the function
with fake point-cloud data shaped like RGBCameraRealSense.get_point_cloud()
actually returns, so shape/gating regressions in this specific path
(previously the site of a live crash-loop bug) can be caught without a
RealSense or thermal camera attached.
"""
import numpy as np
import pytest

from thermal_inspection.gui.panels.fusion_3d_panel import (
    Fusion3DPointCloudView, GL_AVAILABLE, MAX_PREVIEW_POINTS,
)

requires_gl = pytest.mark.skipif(not GL_AVAILABLE, reason="requires PyOpenGL")


def _fake_point_cloud(n_points: int, seed: int = 0):
    """Mimics RGBCameraRealSense.get_point_cloud()'s contract: (N,3) XYZ
    meters and (N,2) UV texture fractions in [0, 1]."""
    rng = np.random.default_rng(seed)
    vertices = np.zeros((n_points, 3), dtype=np.float32)
    vertices[:, 2] = rng.uniform(0.2, 4.0, size=n_points).astype(np.float32)  # valid depth range
    vertices[:, 0] = rng.uniform(-1, 1, size=n_points).astype(np.float32)
    vertices[:, 1] = rng.uniform(-1, 1, size=n_points).astype(np.float32)
    uv = rng.uniform(0, 1, size=(n_points, 2)).astype(np.float32)
    return vertices, uv


@requires_gl
@pytest.mark.unit
class TestUpdateFromRealsense:

    @pytest.mark.parametrize("color_mode", ["fusion", "rgb_only", "thermal_only"])
    def test_runs_without_crashing_on_realistic_input(self, qapp, color_mode):
        """The exact shape this crashed on live: a RealSense RGB stream at
        one resolution, a Boson thermal stream at a different (smaller)
        one - color modes must all handle that mismatch without error."""
        view = Fusion3DPointCloudView()
        view.color_mode = color_mode
        vertices, uv = _fake_point_cloud(5000)
        rgb_frame = np.random.randint(0, 255, size=(800, 1280, 3), dtype=np.uint8)
        thermal_colorized = np.random.randint(0, 255, size=(512, 640, 3), dtype=np.uint8)

        view.update_from_realsense(vertices, uv, rgb_frame, thermal_colorized)  # must not raise

    def test_single_channel_thermal_does_not_crash(self, qapp):
        """Regression test for the live crash: a single-channel-uint8
        thermal_colorized (e.g. Tau2's video-only raw output, passed
        through without colorizing) used to crash update_from_realsense
        with "operands could not be broadcast together with shapes (N,)
        (N,3)" - now defended against directly in the method (see its
        own ndim==2 check) as well as fixed upstream in app.py."""
        view = Fusion3DPointCloudView()
        view.color_mode = "fusion"
        vertices, uv = _fake_point_cloud(2000)
        rgb_frame = np.random.randint(0, 255, size=(480, 640, 3), dtype=np.uint8)
        thermal_colorized_2d = np.random.randint(0, 255, size=(512, 640), dtype=np.uint8)

        view.update_from_realsense(vertices, uv, rgb_frame, thermal_colorized_2d)  # must not raise

    def test_empty_point_cloud_does_not_crash(self, qapp):
        view = Fusion3DPointCloudView()
        vertices = np.zeros((0, 3), dtype=np.float32)
        uv = np.zeros((0, 2), dtype=np.float32)
        rgb_frame = np.random.randint(0, 255, size=(480, 640, 3), dtype=np.uint8)
        thermal_colorized = np.random.randint(0, 255, size=(512, 640, 3), dtype=np.uint8)

        view.update_from_realsense(vertices, uv, rgb_frame, thermal_colorized)  # must not raise

    def test_point_count_is_stable_when_downsampled(self, qapp):
        """Regression test for the VBO-reallocation-churn fix earlier this
        session: GLScatterPlotItem.upload_vbo() only reuses the GPU vertex
        buffer when the byte size matches exactly, so the downsample must
        produce a FIXED point count across frames whose raw valid-point
        count fluctuates - not a stride-based [::stride] slice, whose
        result length drifts by one or more points as that count changes."""
        view = Fusion3DPointCloudView()
        rgb_frame = np.random.randint(0, 255, size=(480, 640, 3), dtype=np.uint8)
        thermal_colorized = np.random.randint(0, 255, size=(512, 640, 3), dtype=np.uint8)

        counts = []
        for n_points, seed in [(30000, 1), (30017, 2), (29984, 3)]:
            vertices, uv = _fake_point_cloud(n_points, seed=seed)
            view.update_from_realsense(vertices, uv, rgb_frame, thermal_colorized)
            counts.append(view._scatter.pos.shape[0])

        assert counts == [MAX_PREVIEW_POINTS] * len(counts), (
            f"expected a fixed {MAX_PREVIEW_POINTS}-point count every frame, got {counts}"
        )
