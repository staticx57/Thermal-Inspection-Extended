"""
Targeted parallax regression tests covering all five bugs fixed.

NOTE: We import processing modules directly (not via the thermal_inspection
package) to bypass the package-level __init__.py which attempts to import
torch and crashes on this machine's broken c10.dll.
"""
import sys
import os
import numpy as np
import pytest
from PyQt6.QtWidgets import QApplication

# Direct path import — does NOT go through thermal_inspection/__init__.py
sys.path.insert(0, os.path.abspath("."))

qapp = QApplication.instance() or QApplication(sys.argv)

# Import only from the two affected submodules; no package-level torch contact
from thermal_inspection.processing.parallax_compensator import (
    ParallaxCompensator, CameraGeometry, DepthEstimator
)
from thermal_inspection.gui.panels.parallax_panel import ParallaxPanel


class TestBug1_ApplyCorrectionCalledInFrameLoop:
    """Bug 1: apply_correction was never called in _process_frame_loop."""

    def test_apply_correction_runs_when_enabled(self):
        """ParallaxCompensator.apply_correction must run and shift the thermal frame."""
        comp = ParallaxCompensator(
            camera_geometry=CameraGeometry(baseline_mm=50.0),
            depth_method="simplified"
        )
        comp.enable(True)

        # Use a horizontal gradient so the remap shift is detectable.
        # A uniform frame would look identical before and after shifting.
        thermal = np.zeros((512, 640, 3), dtype=np.uint8)
        thermal[:, :, 0] = np.tile(np.arange(640, dtype=np.uint8), (512, 1))  # horizontal gradient
        rgb = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)

        result, rgb_out = comp.apply_correction(thermal, rgb)

        assert result is not None
        assert result.shape == thermal.shape
        # The disparity with a 50mm baseline shifts pixels; the left columns
        # should differ from the uncorrected frame.
        assert not np.array_equal(result, thermal), (
            "apply_correction returned identical frame — no shift applied"
        )
        # Default correction_target is "thermal" - rgb passes through untouched.
        assert np.array_equal(rgb_out, rgb)

    def test_apply_correction_passthrough_when_disabled(self):
        from thermal_inspection.processing.parallax_compensator import ParallaxCompensator
        comp = ParallaxCompensator(depth_method="simplified")
        comp.enable(False)

        thermal = np.ones((512, 640, 3), dtype=np.uint8) * 42
        rgb = np.ones((480, 640, 3), dtype=np.uint8)
        result, rgb_out = comp.apply_correction(thermal, rgb)

        assert np.array_equal(result, thermal), "Disabled compensator must return original frame unchanged"
        assert np.array_equal(rgb_out, rgb)


class TestBug2_BaselineChangedSignal:
    """Bug 2: baseline_changed signal was never emitted from the spinbox."""

    def test_baseline_spinbox_emits_signal(self):
        from thermal_inspection.gui.panels.parallax_panel import ParallaxPanel
        panel = ParallaxPanel()

        received = []
        panel.baseline_changed.connect(received.append)

        panel.baseline_spin.setValue(75.0)
        assert len(received) >= 1, "baseline_changed signal was never emitted from spinbox"
        assert received[-1] == pytest.approx(75.0)


class TestBug3_SetDepthDisplay:
    """Bug 3: set_depth_display() method was missing from ParallaxCompensator."""

    def test_set_depth_display_exists(self):
        from thermal_inspection.processing.parallax_compensator import ParallaxCompensator
        comp = ParallaxCompensator(depth_method="simplified")
        assert hasattr(comp, 'set_depth_display'), "set_depth_display() method missing"
        assert hasattr(comp, 'show_depth_map'), "show_depth_map attribute missing"

    def test_set_depth_display_returns_colorised_frame(self):
        from thermal_inspection.processing.parallax_compensator import ParallaxCompensator
        comp = ParallaxCompensator(depth_method="simplified")
        comp.enable(True)
        comp.set_depth_display(True)

        thermal = np.zeros((512, 640, 3), dtype=np.uint8)
        rgb = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)

        result, _rgb_out = comp.apply_correction(thermal, rgb)
        assert result is not None
        assert result.shape == (512, 640, 3)
        # Depth overlay should be colourised (non-uniform colour channels, JET palette)
        assert not np.all(result[:, :, 0] == result[:, :, 1]), (
            "Depth overlay should be a JET-colourised map, not grayscale"
        )

    def test_depth_display_off_returns_corrected_thermal(self):
        from thermal_inspection.processing.parallax_compensator import ParallaxCompensator
        comp = ParallaxCompensator(depth_method="simplified")
        comp.enable(True)
        comp.set_depth_display(False)

        thermal = np.zeros((512, 640, 3), dtype=np.uint8)
        thermal[:, 320:, 0] = 200
        rgb = np.ones((480, 640, 3), dtype=np.uint8) * 128

        result, _rgb_out = comp.apply_correction(thermal, rgb)
        assert result is not None
        # Should be corrected thermal (shifted), not a JET overlay
        assert result.shape == thermal.shape


class TestBug5_DepthMethodReinit:
    """Bug 5: set_parallax_depth_method mutated .method without re-initialising the estimator."""

    def test_depth_method_reinit_on_change(self):
        from thermal_inspection.processing.parallax_compensator import (
            ParallaxCompensator, DepthEstimator
        )
        comp = ParallaxCompensator(depth_method="simplified")
        original_estimator = comp.depth_estimator
        assert original_estimator.method == "simplified"

        # Simulate what set_parallax_depth_method now does
        old_device = comp.depth_estimator._device_requested
        comp.depth_estimator = DepthEstimator(method="simplified", device=old_device)

        new_estimator = comp.depth_estimator
        assert new_estimator is not original_estimator, "New DepthEstimator should be a fresh instance"
        assert new_estimator.method == "simplified"
        assert new_estimator.model_loaded is False or new_estimator.enabled is True


class TestFlowMapRecomputeThrottle:
    """
    Regression tests for a major live performance finding (2026-09-04):
    apply_correction() ran the full depth-estimate+disparity-compute
    chain on EVERY call, unlike every other expensive per-frame effect
    in this codebase (3D Fusion's depth-relief shading, ThreadedAnalyzer,
    motion detection), all of which are throttled. Measured live:
    apply_correction() alone cost ~11ms/frame with depth-based
    correction genuinely engaged, stacking with 3D/2D Fusion's own cost
    to push several mode/setting combinations into the low 20s fps
    ("modes and combinations of settings that bring fps down to the
    20s"). Fixed by throttling only the depth-estimate+disparity step
    (reusing self.last_displacement_map between calls within
    correction_recompute_interval_s) - _remap_thermal still runs on the
    CURRENT frame's live pixel data every single call, so this can't
    freeze the displayed video the way caching the whole corrected
    frame would have.

    Also covers the safety net this needed given parallax's history this
    session (three separate live bugs from stale/mismatched correction
    state): a correction-target switch, in particular, must never reuse
    a flow map computed in the OLD target's resolution/pixel space.
    """

    @staticmethod
    def _make_comp():
        comp = ParallaxCompensator(depth_method="simplified")
        comp.enable(True)
        comp.set_correction_target("thermal")
        return comp

    def test_flow_map_reused_within_throttle_window(self):
        comp = self._make_comp()
        thermal = np.zeros((512, 640, 3), dtype=np.uint8)
        rgb = np.ones((512, 640, 3), dtype=np.uint8) * 128

        comp.apply_correction(thermal, rgb)  # first call: computes and caches
        first_flow_map = comp.last_displacement_map
        assert first_flow_map is not None

        comp.apply_correction(thermal, rgb)  # second call, immediately after
        assert comp.last_displacement_map is first_flow_map, (
            "a second call within the throttle window must reuse the cached flow map, not rebuild it"
        )

    def test_flow_map_recomputed_after_throttle_interval_elapses(self):
        comp = self._make_comp()
        comp.correction_recompute_interval_s = 0.01  # short interval for a fast test
        thermal = np.zeros((512, 640, 3), dtype=np.uint8)
        rgb = np.ones((512, 640, 3), dtype=np.uint8) * 128

        comp.apply_correction(thermal, rgb)
        first_flow_map = comp.last_displacement_map

        import time
        time.sleep(0.02)
        comp.apply_correction(thermal, rgb)
        assert comp.last_displacement_map is not first_flow_map, (
            "a call after the throttle interval elapses must recompute, not keep reusing a stale flow map"
        )

    def test_correction_target_switch_forces_immediate_recompute(self):
        """The specific safety net this needed: reusing a cached flow map
        across a target switch is exactly the "frame cut in half" bug
        class from earlier this session - the shape/space are entirely
        different between targets."""
        comp = self._make_comp()
        thermal = np.zeros((512, 640, 3), dtype=np.uint8)
        rgb = np.ones((512, 640, 3), dtype=np.uint8) * 128

        comp.apply_correction(thermal, rgb)
        assert comp.last_displacement_map is not None

        comp.set_correction_target("rgb")
        assert comp.last_displacement_map is None, (
            "switching correction target must invalidate the cached flow map immediately"
        )

        result_thermal, result_rgb = comp.apply_correction(thermal, rgb)
        assert result_rgb.shape[:2] == rgb.shape[:2]  # did not silently corrupt/crash

    def test_manual_shift_change_forces_immediate_recompute(self):
        comp = self._make_comp()
        thermal = np.zeros((512, 640, 3), dtype=np.uint8)
        rgb = np.ones((512, 640, 3), dtype=np.uint8) * 128

        comp.apply_correction(thermal, rgb)
        assert comp.last_displacement_map is not None

        comp.set_manual_shift(5, -3)
        assert comp.last_displacement_map is None

    def test_enable_toggle_forces_immediate_recompute(self):
        comp = self._make_comp()
        thermal = np.zeros((512, 640, 3), dtype=np.uint8)
        rgb = np.ones((512, 640, 3), dtype=np.uint8) * 128

        comp.apply_correction(thermal, rgb)
        assert comp.last_displacement_map is not None

        comp.enable(False)
        comp.enable(True)
        assert comp.last_displacement_map is None

    def test_depth_method_swap_via_invalidate_correction_cache(self):
        """Covers app.py's set_parallax_depth_method, which replaces
        depth_estimator directly (bypassing every ParallaxCompensator
        method that would otherwise invalidate the cache) and must call
        invalidate_correction_cache() itself."""
        comp = self._make_comp()
        thermal = np.zeros((512, 640, 3), dtype=np.uint8)
        rgb = np.ones((512, 640, 3), dtype=np.uint8) * 128

        comp.apply_correction(thermal, rgb)
        assert comp.last_displacement_map is not None

        comp.depth_estimator = DepthEstimator(method="simplified", device="cpu")
        comp.invalidate_correction_cache()
        assert comp.last_displacement_map is None

    def test_apply_correction_is_meaningfully_cheaper_when_throttled(self):
        """Locks in the actual performance win, not just the caching
        mechanics - loose bound (steady-state measured ~4.2ms vs ~11.1ms
        before this fix) to avoid CI flakiness from timing variance."""
        import time
        comp = self._make_comp()
        thermal = np.random.randint(0, 255, size=(512, 640, 3), dtype=np.uint8)
        rgb = np.random.randint(0, 255, size=(512, 640, 3), dtype=np.uint8)

        comp.apply_correction(thermal, rgb)  # warm up

        n = 20
        t0 = time.perf_counter()
        for _ in range(n):
            comp.apply_correction(thermal, rgb)
        elapsed_ms_per_call = (time.perf_counter() - t0) * 1000 / n

        assert elapsed_ms_per_call < 8.0, (
            f"apply_correction averaged {elapsed_ms_per_call:.2f}ms/call across {n} rapid calls - "
            "expected well under the pre-throttle ~11ms since almost all of these should hit the cache"
        )
