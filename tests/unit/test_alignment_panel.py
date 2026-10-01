"""Alignment tab: the static camera-position corrections live here (moved from the Parallax tab), the calibration
manager drives the fusion processor, and --calibration-file actually reaches the app."""
import numpy as np
import pytest

pytest.importorskip("PyQt6")
from PyQt6.QtWidgets import QApplication

from tests.unit import alignment_rig as rig
from thermal_inspection.core.alignment_calibration import AlignmentCalibrationManager
from thermal_inspection.gui.panels.alignment_panel import AlignmentPanel
from thermal_inspection.gui.panels.parallax_panel import ParallaxPanel
from thermal_inspection.processing.fusion_processor import FusionProcessor

app = QApplication.instance() or QApplication([])


class FakeConfig:
    def __init__(self, **kv):
        self.d = dict(kv)

    def get(self, k, default=None):
        return self.d.get(k, default)

    def set(self, k, v, save=True):
        self.d[k] = v
        return True


def test_static_corrections_moved_out_of_the_parallax_tab():
    par, al = ParallaxPanel(), AlignmentPanel()
    for name in ("shift_x_spin", "shift_y_spin", "zoom_spin", "auto_align_btn", "auto_crop_btn",
                 "working_distance_spin"):
        assert not hasattr(par, name), f"{name} should no longer be on the Parallax tab"
        assert hasattr(al, name), f"{name} missing from the Alignment tab"
    for name in ("baseline_spin", "enable_checkbox", "show_depth_checkbox"):
        assert hasattr(par, name)


def test_moved_controls_still_emit_their_signals():
    al = AlignmentPanel()
    got = []
    al.shift_changed.connect(lambda x, y: got.append(("shift", x, y)))
    al.zoom_changed.connect(lambda z: got.append(("zoom", z)))
    al.auto_alignment_requested.connect(lambda d, a, b: got.append(("auto", d, a, b)))
    al.shift_x_spin.setValue(7)
    al.zoom_spin.setValue(1.25)
    al.auto_align_btn.click()
    al.set_auto_alignment_result(3, -2, 1.1)
    assert ("shift", 7, 0) in got and ("zoom", 1.25) in got and got[-1][0] == "auto"
    assert al.shift_x_spin.value() == 3 and "shift (3, -2)" in al.auto_align_result_label.text()
    al.set_auto_crop_result((1, 2, 3, 4))
    assert "top=1" in al.auto_crop_result_label.text()


def test_status_display_reflects_composition_state():
    al = AlignmentPanel()
    al.set_status({"loaded": False})
    assert al.status_label.text() == "Not calibrated" and not al.enable_checkbox.isEnabled()
    base = {"loaded": True, "enabled": True, "distance_m": 2.0, "rms_px": 0.4, "inliers": 50, "points": 60,
            "method": "features", "path": "x/cal.json"}
    al.set_status({**base, "parallax_on": True, "parallax_composed": True})
    assert "composed" in al.composition_label.text() and al.enable_checkbox.isChecked()
    al.set_status({**base, "distance_m": None, "parallax_on": True, "parallax_composed": False})
    assert "twice" in al.composition_label.text()


def _frames():
    """Corner-rich textured pair (ORB needs corners; the rig's smooth sinusoids have none)."""
    from tests.unit.test_alignment_composition import _shifted_pair
    t, r = _shifted_pair()
    return t, r


def test_manager_capture_applies_saves_and_restores(tmp_path, monkeypatch):
    monkeypatch.setenv("THERMAL_INSPECTION_HOME", str(tmp_path))
    cfg = FakeConfig()
    f = FusionProcessor()
    mgr = AlignmentCalibrationManager(f, cfg)
    thermal, rgb = _frames()
    assert mgr.capture(thermal, rgb, 2.0, "features")
    assert f.calibration_matrix is not None and f.calibration_distance_m == 2.0
    assert (tmp_path / "alignment_calibration.json").exists()
    assert cfg.d["alignment_calibration_file"].endswith("alignment_calibration.json")
    # restart: a new processor + manager restore it from the remembered file
    f2 = FusionProcessor()
    mgr2 = AlignmentCalibrationManager(f2, cfg)
    assert mgr2.restore() and f2.calibration_distance_m == 2.0 and f2.calibration_enabled
    # switched off survives a restart too
    mgr.set_enabled(False)
    f3 = FusionProcessor()
    assert AlignmentCalibrationManager(f3, cfg).restore() and not f3.calibration_enabled
    assert f3.effective_calibration_matrix() is None


def test_manager_refuses_bad_input_and_clears(tmp_path, monkeypatch):
    monkeypatch.setenv("THERMAL_INSPECTION_HOME", str(tmp_path))
    mgr = AlignmentCalibrationManager(FusionProcessor(), FakeConfig())
    t, r = _frames()
    assert not mgr.capture(t, None, 2.0) and "RGB" in mgr.last_error
    assert not mgr.capture(t, r, 0.0) and "distance" in mgr.last_error
    noise = np.random.default_rng(0).integers(0, 255, (200, 200), dtype=np.uint8)
    assert not mgr.capture(noise, noise[::-1].copy(), 1.0)
    assert mgr.fusion.calibration_matrix is None
    assert mgr.capture(t, r, 2.0)
    mgr.clear()
    assert mgr.fusion.calibration_matrix is None and not mgr.status()["loaded"]


def test_cli_file_wins_over_remembered_and_missing_file_is_not_fatal(tmp_path, monkeypatch):
    monkeypatch.setenv("THERMAL_INSPECTION_HOME", str(tmp_path))
    cfg = FakeConfig(alignment_calibration_file=str(tmp_path / "gone.json"))
    mgr = AlignmentCalibrationManager(FusionProcessor(), cfg)
    assert not mgr.restore() and "not found" in mgr.last_error.lower()
    t, r = _frames()
    donor = AlignmentCalibrationManager(FusionProcessor(), FakeConfig())
    assert donor.capture(t, r, 3.0)
    assert mgr.restore(str(tmp_path / "alignment_calibration.json")) and mgr.fusion.calibration_distance_m == 3.0


def test_calibration_matrix_rescales_to_other_resolutions():
    f = FusionProcessor()
    f.set_calibration(rig.homography_for(2.0), 2.0,
                      {"thermal_shape": [rig.H, rig.W], "rgb_shape": [rig.H, rig.W]})
    same = f.effective_calibration_matrix((rig.H, rig.W), (rig.H, rig.W))
    assert np.allclose(same, f.calibration_matrix)
    # live frames twice the calibrated size: a translation doubles
    big = f.effective_calibration_matrix((rig.H * 2, rig.W * 2), (rig.H * 2, rig.W * 2))
    assert big[0, 2] == pytest.approx(f.calibration_matrix[0, 2] * 2, rel=1e-4)


def test_calibration_file_reaches_the_app_config():
    from thermal_inspection.app import AppConfig
    from thermal_inspection.cli import build_parser
    args = build_parser().parse_args(["--calibration-file", "c.json"])
    assert AppConfig.from_args(args).calibration_file == "c.json"


# ---------------------------------------------------------------- redesigned Alignment tab

def test_one_tab_hosts_register_parallax_and_rig_with_one_shared_distance():
    from thermal_inspection.gui.panels.alignment_tab import AlignmentTab
    tab = AlignmentTab()
    assert [tab.pages.tabText(i) for i in range(tab.pages.count())] == ["1 Register", "2 Parallax", "3 Rig"]
    assert tab.register_panel.distance_spin is tab.distance_spin
    assert tab.register_panel.working_distance_spin is tab.distance_spin
    assert tab.parallax_panel.geometry_group.window() is tab.window() or tab.parallax_panel.geometry_group.parent()
    got = []
    tab.register_panel.capture_requested.connect(lambda d, m, c, r: got.append(d))
    tab.register_panel.auto_alignment_requested.connect(lambda d, a, b: got.append(d))
    tab.set_distance(3.5)
    tab.register_panel.capture_btn.click()
    tab.register_panel.auto_align_btn.click()
    assert got == [3.5, 3.5]


def test_summary_strip_tracks_registration_and_parallax():
    from thermal_inspection.gui.panels.alignment_tab import AlignmentTab
    tab = AlignmentTab()
    assert "not calibrated" in tab.summary_label.text()
    st = {"loaded": True, "enabled": True, "distance_m": 2.0, "rms_px": 0.5, "parallax_composed": False,
          "inliers": 9, "points": 10}
    tab.set_registration_status(st)
    tab.parallax_panel.enable_checkbox.setChecked(True)
    assert "Applied twice" in tab.summary_label.text()
    tab.set_registration_status({**st, "parallax_composed": True})
    assert "Combined correctly" in tab.summary_label.text()
    tab.parallax_panel.enable_checkbox.setChecked(False)
    assert "Combined" not in tab.summary_label.text()


def test_overlay_and_check_signals_come_from_the_strip():
    from thermal_inspection.gui.panels.alignment_tab import AlignmentTab
    tab = AlignmentTab()
    got = []
    tab.show_alignment_overlay_toggled.connect(lambda v: got.append(("overlay", v)))
    tab.check_alignment_requested.connect(lambda: got.append("check"))
    tab.measure_distance_requested.connect(lambda: got.append("measure"))
    tab.overlay_checkbox.setChecked(True)
    tab.check_btn.click()
    tab.measure_btn.click()
    assert got == [("overlay", True), "check", "measure"]
    assert not hasattr(tab.register_panel, "show_alignment_overlay_checkbox")


def test_measure_residual_reads_a_known_offset_and_refuses_featureless_scenes():
    import cv2
    from thermal_inspection.cameras.camera_calibration import measure_residual
    rng = np.random.default_rng(5)
    base = cv2.GaussianBlur(rng.integers(0, 255, (300, 380), dtype=np.uint8), (5, 5), 0)
    t = base[20:276, 30:350]
    for shift, level in ((0, "good"), (3, "ok"), (9, "poor")):
        r = base[20:276, 30 + shift:350 + shift]               # content moves LEFT by `shift` in r
        dx, dy, resp, lv, text = measure_residual(t, r)
        assert abs(abs(dx) - shift) < 1.0 and abs(dy) < 1.0 and lv == level, (shift, dx, dy, resp, lv)
    flat = np.full((256, 320), 120, np.uint8)
    assert measure_residual(flat, flat)[3] == "unknown"


def test_compensator_measures_scene_distance_from_the_depth_camera():
    comp = rig.make_compensator(2.5)
    assert comp.measure_scene_distance_m() == pytest.approx(2.5)
    comp.set_hardware_depth_source(None)
    assert comp.measure_scene_distance_m() is None
    comp.set_hardware_depth_source(lambda size=None: np.zeros((rig.H, rig.W), np.float32))
    assert comp.measure_scene_distance_m() is None             # no valid pixels
