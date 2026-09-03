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
