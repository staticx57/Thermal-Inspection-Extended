"""
Regression tests for parallax alignment persistence (2026-09-08): before
this, baseline_mm/manual_shift_x/y/fov_zoom_factor were pure in-memory
ParallaxCompensator() constructor defaults - a one-time Auto-Align or
Auto-Crop result reset back to those defaults on every app restart, which
defeats the point of a "one-time... unless summoned again" calibration
action.

Tests ThermalInspectionApp._save_parallax_alignment_to_config() and
_load_parallax_alignment_from_config() directly against a real,
tmp_path-backed Config instance (genuine JSON round-trip, not a mock) -
without constructing the full heavy ThermalInspectionApp, since both
methods only ever touch self.parallax_compensator and get_config().
"""
import sys
import os
import pytest

sys.path.insert(0, os.path.abspath("."))

from thermal_inspection.app import ThermalInspectionApp
from thermal_inspection.processing.parallax_compensator import ParallaxCompensator, CameraGeometry
from thermal_inspection.utils.config import Config


class _FakeApp:
    """Duck-typed stand-in exposing only what the two methods under test
    actually read - avoids constructing the full ThermalInspectionApp
    (real cameras, GUI, threads) for what is otherwise a two-attribute
    unit of behavior."""

    def __init__(self, parallax_compensator):
        self.parallax_compensator = parallax_compensator


@pytest.fixture
def real_config(tmp_path, monkeypatch):
    """A genuine Config instance backed by a tmp file - never the real
    project's config.json - patched in as the get_config() singleton
    both app.py methods import locally at call time."""
    cfg = Config(config_file=str(tmp_path / "test_config.json"))
    monkeypatch.setattr("thermal_inspection.utils.config.get_config", lambda: cfg)
    return cfg


class TestSaveParallaxAlignmentToConfig:
    def test_saves_shift_zoom_and_crop(self, real_config):
        comp = ParallaxCompensator(camera_geometry=CameraGeometry(baseline_mm=50.0),
                                  depth_method="simplified")
        comp.enable(False)
        comp.set_manual_shift(12, -7)
        comp.set_fov_zoom_factor(1.25)
        comp.set_crop_rect(1, 2, 3, 4)
        fake_app = _FakeApp(comp)

        ThermalInspectionApp._save_parallax_alignment_to_config(fake_app)

        assert real_config.get('parallax_shift_x') == 12
        assert real_config.get('parallax_shift_y') == -7
        assert real_config.get('parallax_fov_zoom_factor') == 1.25
        # Config.set() just stores the value in memory - it's still the
        # original tuple here (JSON only converts it to a list once an
        # actual save+load file round-trip happens, see the dedicated
        # restart-simulation test below).
        assert real_config.get('parallax_crop_rect') == (1, 2, 3, 4)

    def test_no_op_when_no_compensator(self, real_config):
        fake_app = _FakeApp(None)
        # Must not raise.
        ThermalInspectionApp._save_parallax_alignment_to_config(fake_app)
        assert real_config.get('parallax_shift_x') is None

    def test_persists_across_a_fresh_config_instance(self, tmp_path, monkeypatch):
        """The actual point: a value saved by one Config instance must be
        readable by an entirely new one loading the same file - simulating
        an app restart, not just an in-memory round-trip."""
        config_file = str(tmp_path / "test_config.json")
        cfg_before_restart = Config(config_file=config_file)
        monkeypatch.setattr("thermal_inspection.utils.config.get_config", lambda: cfg_before_restart)

        comp = ParallaxCompensator(camera_geometry=CameraGeometry(baseline_mm=50.0),
                                  depth_method="simplified")
        comp.set_manual_shift(9, 3)
        ThermalInspectionApp._save_parallax_alignment_to_config(_FakeApp(comp))

        # Simulate a restart: a brand new Config instance loading the same file.
        cfg_after_restart = Config(config_file=config_file)
        assert cfg_after_restart.get('parallax_shift_x') == 9
        assert cfg_after_restart.get('parallax_shift_y') == 3


class TestLoadParallaxAlignmentFromConfig:
    def test_restores_saved_shift_zoom_and_crop_via_real_setters(self, real_config):
        real_config.set('parallax_baseline_mm', 65.0, save=False)
        real_config.set('parallax_shift_x', 12, save=False)
        real_config.set('parallax_shift_y', -7, save=False)
        real_config.set('parallax_fov_zoom_factor', 1.25, save=False)
        real_config.set('parallax_crop_rect', [1, 2, 3, 4], save=True)

        comp = ParallaxCompensator(camera_geometry=CameraGeometry(baseline_mm=50.0),
                                  depth_method="simplified")
        fake_app = _FakeApp(comp)

        ThermalInspectionApp._load_parallax_alignment_from_config(fake_app)

        assert comp.geometry.baseline_mm == 65.0
        assert comp.get_manual_shift() == (12, -7)
        assert comp.fov_zoom_factor == 1.25
        assert comp.get_crop_rect() == (1, 2, 3, 4)

    def test_a_fresh_config_with_no_history_leaves_defaults_untouched(self, real_config):
        """No key has ever been saved - every DEFAULT_CONFIG parallax_*
        value is None (see config.py) - so this must be a complete no-op,
        not silently apply None/zero over the constructor's own real
        defaults."""
        comp = ParallaxCompensator(camera_geometry=CameraGeometry(baseline_mm=50.0),
                                  depth_method="simplified")
        fake_app = _FakeApp(comp)

        ThermalInspectionApp._load_parallax_alignment_from_config(fake_app)

        assert comp.geometry.baseline_mm == 50.0
        assert comp.get_manual_shift() == (0, 0)
        assert comp.fov_zoom_factor == 1.0
        assert comp.get_crop_rect() is None

    def test_shift_zoom_restored_before_crop_rect_is_applied(self, real_config):
        """crop_rect must survive being restored AFTER set_manual_shift/
        set_fov_zoom_factor, even though those calls invalidate crop_rect
        as a side effect for a LIVE shift/zoom change - load order in
        _load_parallax_alignment_from_config must apply crop_rect last so
        it isn't wiped out by its own sibling restores."""
        real_config.set('parallax_shift_x', 5, save=False)
        real_config.set('parallax_shift_y', 5, save=False)
        real_config.set('parallax_fov_zoom_factor', 1.1, save=False)
        real_config.set('parallax_crop_rect', [1, 1, 1, 1], save=True)

        comp = ParallaxCompensator(camera_geometry=CameraGeometry(baseline_mm=50.0),
                                  depth_method="simplified")
        ThermalInspectionApp._load_parallax_alignment_from_config(_FakeApp(comp))

        assert comp.get_crop_rect() == (1, 1, 1, 1)

    def test_end_to_end_save_then_load_round_trip(self, real_config):
        """The full loop: compute a result, save it, construct a NEW
        compensator (simulating a restart) and load it back."""
        comp_before = ParallaxCompensator(camera_geometry=CameraGeometry(baseline_mm=50.0),
                                         depth_method="simplified")
        comp_before.set_manual_shift(20, -10)
        comp_before.set_fov_zoom_factor(0.9)
        ThermalInspectionApp._save_parallax_alignment_to_config(_FakeApp(comp_before))

        comp_after = ParallaxCompensator(camera_geometry=CameraGeometry(baseline_mm=50.0),
                                        depth_method="simplified")
        ThermalInspectionApp._load_parallax_alignment_from_config(_FakeApp(comp_after))

        assert comp_after.get_manual_shift() == comp_before.get_manual_shift()
        assert comp_after.fov_zoom_factor == comp_before.fov_zoom_factor
