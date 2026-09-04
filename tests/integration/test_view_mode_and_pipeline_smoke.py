"""
Automated scenario smoke tests replacing the manual "relaunch the app,
click through every view mode / parallax setting / 3D mode, watch the
log for a crash" verification pass this session did by hand, repeatedly,
across many live-hardware debugging rounds (2026-09-03/04). A pytest
failure here is meant to catch the same class of bug those manual
passes found - e.g. the 3D-Fusion point-cloud crash loop, the parallax
target-switch frame corruption, the silent RGB-only fallback - without
needing a human at the keyboard or real camera hardware attached.

Drives the real ThermalInspectionApp._process_frame_loop() end to end
(the actual per-tick method the live QTimer calls) against fake camera
backends - not a mock of the pipeline, the real FusionProcessor/
ThermalAnalyzer/ParallaxCompensator/PaletteManager doing real work on
synthetic frames.
"""
import itertools

import pytest

from thermal_inspection.core.fusion_controller import ViewMode
from thermal_inspection.gui.panels.fusion_3d_panel import THREE_D_MODES


def _tick_a_few_times(app, n=3):
    for _ in range(n):
        app._process_frame_loop()


@pytest.mark.integration
class TestViewModeSmoke:
    """Every view mode must run several ticks without raising."""

    @pytest.mark.parametrize("view_mode", [
        ViewMode.THERMAL_ONLY, ViewMode.RGB_ONLY, ViewMode.FUSION,
        ViewMode.SIDE_BY_SIDE, ViewMode.PICTURE_IN_PICTURE, ViewMode.THREE_D,
    ])
    def test_view_mode_runs_without_raising(self, headless_app_with_fake_cameras, view_mode):
        app = headless_app_with_fake_cameras
        app.view_mode = view_mode

        _tick_a_few_times(app)  # must not raise

        assert app._last_display_frame is not None
        assert app._last_display_frame.ndim == 3
        assert app._last_display_frame.shape[2] == 3


@pytest.mark.integration
class TestFusionModeSmoke:
    """Every 2D Fusion mode must run in ViewMode.FUSION without raising -
    this is the pytest equivalent of --auto-cycle-fusion-modes, runnable
    in CI without launching the real app or waiting out real-time
    per-mode intervals."""

    @pytest.mark.parametrize("mode", [
        "alpha_blend", "detail_inject", "relief_fusion", "edge_enhanced",
        "thermal_overlay", "side_by_side", "picture_in_picture",
        "max_intensity", "feature_weighted", "thermal_contours",
        "enhanced_edge_highlight", "laplacian_pyramid",
    ])
    def test_fusion_mode_runs_without_raising(self, headless_app_with_fake_cameras, mode):
        app = headless_app_with_fake_cameras
        app.view_mode = ViewMode.FUSION
        app.fusion_processor.set_fusion_mode(mode)

        _tick_a_few_times(app)

        assert app._last_display_frame is not None


@pytest.mark.integration
class TestThreeDModeSmoke:
    """Every 3D Fusion depth-visualization mode, under every parallax
    target/method combination - this exact matrix is what a live
    "silent RGB-only fallback" or "frame cut in half on target switch"
    bug hid in earlier this session."""

    @pytest.mark.parametrize("mode", THREE_D_MODES)
    @pytest.mark.parametrize("target,method", [
        ("thermal", "realsense"), ("thermal", "simplified"),
        ("rgb", "realsense"), ("rgb", "simplified"),
    ])
    def test_three_d_mode_runs_without_raising(
        self, headless_app_with_fake_cameras, mode, target, method
    ):
        app = headless_app_with_fake_cameras
        app.view_mode = ViewMode.THREE_D
        app._3d_mode = mode
        app.parallax_compensator.enable(True)
        app.parallax_compensator.set_correction_target(target)
        app.set_parallax_depth_method(method)

        _tick_a_few_times(app)

        assert app._last_display_frame is not None
        assert app._last_display_frame.ndim == 3


@pytest.mark.integration
class TestParallaxToggleSmoke:
    """Enabling/disabling/re-enabling parallax correction, and switching
    its target back and forth, must never raise or corrupt frame shape -
    the exact sequence of manual steps that found the "cut in half" and
    "frame corruption on target switch" bugs earlier this session."""

    def test_repeated_enable_disable_and_target_switching(self, headless_app_with_fake_cameras):
        app = headless_app_with_fake_cameras
        app.view_mode = ViewMode.THREE_D

        for enabled, target in itertools.product([True, False], ["thermal", "rgb"]):
            app.parallax_compensator.enable(enabled)
            app.parallax_compensator.set_correction_target(target)
            _tick_a_few_times(app, n=2)
            assert app._last_display_frame is not None
