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

import numpy as np
import pytest

from thermal_inspection.core.fusion_controller import ViewMode
from thermal_inspection.gui.panels.fusion_3d_panel import THREE_D_MODES
from thermal_inspection.processing.fusion_processor import FusionProcessor

# Sourced from FusionProcessor.AVAILABLE_FUSION_MODES directly, not a
# separate hardcoded copy - this codebase has hit exactly this class of
# bug before (see FusionProcessor.set_mode()'s own docstring,
# FusionController's AVAILABLE_MODES comment): a copy of the mode list
# silently drifting out of sync, so a new or removed mode goes untested
# without anyone remembering to touch this file too.
_ALL_FUSION_MODES = list(FusionProcessor.AVAILABLE_FUSION_MODES)


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

    @pytest.mark.parametrize("mode", _ALL_FUSION_MODES)
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


@pytest.mark.integration
class TestParallaxAlignmentOverlayAndAutoCropSmoke:
    """2026-09-08: the new visual alignment aid, image-based auto-align
    refinement, and one-time Auto-Crop must all run through the real
    _process_frame_loop() without raising, in every view mode - not just
    in isolation against a bare ParallaxCompensator (see
    test_parallax_fixes.py's unit-level TestImageBasedAutoAlign/
    TestAutoCrop for the algorithmic correctness checks)."""

    @pytest.mark.parametrize("view_mode", [
        ViewMode.THERMAL_ONLY, ViewMode.RGB_ONLY, ViewMode.FUSION,
        ViewMode.SIDE_BY_SIDE, ViewMode.PICTURE_IN_PICTURE, ViewMode.THREE_D,
    ])
    def test_alignment_overlay_runs_in_every_view_mode(self, headless_app_with_fake_cameras, view_mode):
        app = headless_app_with_fake_cameras
        app.view_mode = view_mode
        app._show_parallax_alignment_overlay = True

        _tick_a_few_times(app)

        assert app._last_display_frame is not None
        assert app._last_display_frame.ndim == 3
        assert app._last_display_frame.shape[2] == 3

    def test_overlay_off_by_default_and_toggle_changes_output(self, headless_app_with_fake_cameras):
        app = headless_app_with_fake_cameras
        assert app._show_parallax_alignment_overlay is False
        app.view_mode = ViewMode.THERMAL_ONLY

        _tick_a_few_times(app, n=1)
        without_overlay = app._last_display_frame.copy()

        app._show_parallax_alignment_overlay = True
        _tick_a_few_times(app, n=1)
        with_overlay = app._last_display_frame

        assert not np.array_equal(without_overlay, with_overlay), (
            "toggling the overlay on must actually change what's displayed"
        )

    def test_auto_align_with_image_refinement_through_the_real_frame_loop(self, headless_app_with_fake_cameras):
        """Drives the actual bus handler app.py wires up, with real
        (fake-camera) frames flowing through _last_thermal_frame/
        _last_rgb_frame exactly as they would from a live camera."""
        app = headless_app_with_fake_cameras
        app.view_mode = ViewMode.FUSION
        _tick_a_few_times(app, n=2)  # populate _last_thermal_frame/_last_rgb_frame

        app._bus_parallax_auto_alignment_requested(
            working_distance_m=2.0, refine_with_depth=False, refine_from_image=True
        )

        _tick_a_few_times(app, n=2)
        assert app._last_display_frame is not None

    def test_auto_crop_then_reset_through_the_real_frame_loop(self, headless_app_with_fake_cameras):
        app = headless_app_with_fake_cameras
        app.view_mode = ViewMode.THREE_D
        app.parallax_compensator.enable(True)
        app.parallax_compensator.set_correction_target("thermal")
        _tick_a_few_times(app, n=3)  # let real correction run at least once

        app._bus_parallax_auto_crop_requested()
        _tick_a_few_times(app, n=2)
        assert app._last_display_frame is not None

        app._bus_parallax_crop_reset_requested()
        _tick_a_few_times(app, n=2)
        assert app._last_display_frame is not None
        assert app.parallax_compensator.get_crop_rect() is None


def _use_uint16_radiometric_thermal_backend(app, monkeypatch, seed=9):
    """The default fake thermal backend emits plain uint8 grayscale, so
    app.py's `thermal_frame.dtype == np.uint16` check never sets
    thermal_16bit - which would make the isotherm-overlay skip test below
    vacuously true (skipped because it can never run at all, not because
    RGB_ONLY actually gates it). Swaps in a Y16-shaped (Kelvin x 100)
    uint16 backend instead, the same synchronous read_thermal monkeypatch
    the fixture itself uses."""
    rng = np.random.default_rng(seed)

    def read():
        # ~19-45C range, safely inside a wide-open isotherm/threshold band.
        frame = rng.integers(29200, 31800, size=(512, 640), dtype=np.uint16)
        return True, frame

    monkeypatch.setattr(app.plugin_host, "read_thermal", read)


@pytest.mark.integration
class TestRgbOnlySkipsUnusedColorizedThermalWork:
    """RGB_ONLY replaces display_frame with rgb_frame outright - painting
    colorized_thermal with anomaly-priority colorization, the isotherm
    overlay, or the threshold VISUALIZATION is real per-frame work with no
    consumer in that mode (found during the 2026-09-07 pipeline
    characterization: ~27ms/frame with isotherm+threshold both enabled,
    spent on a value nothing on screen reads). Threshold DETECTION must
    keep running regardless - the stats panel needs a fresh detection
    every frame independent of what view mode is showing."""

    def test_isotherm_overlay_skipped_in_rgb_only_resumes_in_thermal_only(
        self, headless_app_with_fake_cameras, monkeypatch
    ):
        app = headless_app_with_fake_cameras
        _use_uint16_radiometric_thermal_backend(app, monkeypatch)

        app.isotherm_manager.set_enabled(True)
        app.isotherm_manager.set_low_threshold(-40.0)
        app.isotherm_manager.set_high_threshold(200.0)  # matches every pixel

        calls = []
        original = app.isotherm_manager.apply_overlay
        monkeypatch.setattr(
            app.isotherm_manager, "apply_overlay",
            lambda *a, **kw: (calls.append(1), original(*a, **kw))[1],
        )

        app.view_mode = ViewMode.RGB_ONLY
        _tick_a_few_times(app)
        assert len(calls) == 0, (
            "isotherm overlay ran in RGB_ONLY, where nothing on screen "
            "reads colorized_thermal"
        )

        calls.clear()
        app.view_mode = ViewMode.THERMAL_ONLY
        _tick_a_few_times(app)
        assert len(calls) > 0, (
            "isotherm overlay must resume once a view mode actually "
            "displays colorized_thermal"
        )

    def test_anomaly_priority_colorization_skipped_in_rgb_only(
        self, headless_app_with_fake_cameras, monkeypatch
    ):
        app = headless_app_with_fake_cameras
        app.thermal_processor.set_anomaly_priority_enabled(True)

        calls = []
        original = app.thermal_processor.apply_anomaly_priority_colorization
        monkeypatch.setattr(
            app.thermal_processor, "apply_anomaly_priority_colorization",
            lambda *a, **kw: (calls.append(1), original(*a, **kw))[1],
        )

        app.view_mode = ViewMode.RGB_ONLY
        _tick_a_few_times(app)
        assert len(calls) == 0

        calls.clear()
        app.view_mode = ViewMode.THERMAL_ONLY
        _tick_a_few_times(app)
        assert len(calls) > 0

    def test_threshold_visualization_skipped_but_detection_and_stats_keep_running(
        self, headless_app_with_fake_cameras, monkeypatch
    ):
        app = headless_app_with_fake_cameras
        _use_uint16_radiometric_thermal_backend(app, monkeypatch)

        app.threshold_manager.set_enabled(True)
        app.threshold_manager.set_min(-40.0)
        app.threshold_manager.set_max(200.0)  # matches every pixel

        viz_calls = []
        original_viz = app.thermal_analyzer.apply_threshold_visualization
        monkeypatch.setattr(
            app.thermal_analyzer, "apply_threshold_visualization",
            lambda *a, **kw: (viz_calls.append(1), original_viz(*a, **kw))[1],
        )

        detect_calls = []
        original_detect = app.thermal_analyzer.detect_threshold_anomalies
        monkeypatch.setattr(
            app.thermal_analyzer, "detect_threshold_anomalies",
            lambda *a, **kw: (detect_calls.append(1), original_detect(*a, **kw))[1],
        )

        stats_events = []
        app.event_bus.threshold_stats_updated.connect(
            lambda *a: stats_events.append(a)
        )

        app.view_mode = ViewMode.RGB_ONLY
        _tick_a_few_times(app)

        assert len(viz_calls) == 0, (
            "threshold visualization painted colorized_thermal in "
            "RGB_ONLY, where nothing on screen reads it"
        )
        assert len(detect_calls) > 0, (
            "threshold detection must keep running in every view mode - "
            "the stats panel needs it independent of what's displayed"
        )
        assert len(stats_events) > 0, (
            "threshold_stats_updated must keep firing in every view mode"
        )

        viz_calls.clear()
        app.view_mode = ViewMode.THERMAL_ONLY
        _tick_a_few_times(app)
        assert len(viz_calls) > 0, (
            "threshold visualization must resume once a view mode "
            "actually displays colorized_thermal"
        )


def test_three_d_mapping_view_mode_exists():
    assert hasattr(ViewMode, "THREE_D_MAPPING")


@pytest.mark.integration
class TestThreeDMappingSmoke:
    """ViewMode.THREE_D_MAPPING wiring (Task 6) - a wiring smoke test,
    not a tracking-accuracy test. world_mapper.state defaults to "idle"
    (no scan started), so the dispatch branch's tracking body is a no-op
    here - this just proves the new elif branch itself, and its
    fallback display_frame assignment, never raise."""

    def test_three_d_mapping_dispatch_does_not_crash(self, headless_app_with_fake_cameras):
        app = headless_app_with_fake_cameras
        app.view_mode = ViewMode.THREE_D_MAPPING

        _tick_a_few_times(app)  # must not raise

        assert app._last_display_frame is not None
        assert app._last_display_frame.ndim == 3

    def test_three_d_mapping_dispatch_runs_tracking_while_scanning(self, headless_app_with_fake_cameras):
        """With world_mapper.state == "scanning" (as if Start Mapping had
        been clicked and a real PoseTracker were available), the
        throttled track_and_texture() call path must also run without
        raising against the fake RealSense RGB backend's depth frames."""
        app = headless_app_with_fake_cameras
        app.view_mode = ViewMode.THREE_D_MAPPING
        # Simulates "Start Mapping" was clicked without going through
        # WorldMapper.start_scan() itself (which would need a real
        # PoseTracker/open3d, unavailable in this environment) - just
        # the state flag the dispatch branch actually checks.
        # world_mapper._pose_tracker stays None (its __init__ default),
        # so world.integrate()'s call fails inside the dispatch block's
        # own try/except Exception - proving that failure path is
        # swallowed, not propagated, exactly as it must be with real
        # hardware mid-scan hiccups.
        app.world_mapper.state = "scanning"

        _tick_a_few_times(app, n=2)  # must not raise

        assert app._last_display_frame is not None


@pytest.mark.integration
class TestTemperatureUnitPropagation:
    """
    thermal_contours' isotherm labels previously stayed hardcoded to
    Celsius regardless of the app-wide temperature unit setting (Settings/
    Radiometric panel's C/F/K choice) - every other on-screen temperature
    already respected it. app.set_temperature_unit() is the real,
    single entry point the Radiometric panel's GUI control calls through
    (directly, or via event_bus) - verified here at that level, not just
    against FusionProcessor's own setter in isolation.
    """
    def test_set_temperature_unit_reaches_fusion_processor(self, headless_app_with_fake_cameras):
        app = headless_app_with_fake_cameras
        assert app.fusion_processor.contour_temp_unit == 'C'

        app.set_temperature_unit('fahrenheit')
        assert app.fusion_processor.contour_temp_unit == 'F'

        app.set_temperature_unit('kelvin')
        assert app.fusion_processor.contour_temp_unit == 'K'
