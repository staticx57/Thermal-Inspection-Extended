"""Parallax correction and the static calibration homography must compose, not double-count the baseline shift.
Measured on the synthetic two-camera rig in alignment_rig.py (ground-truth geometry, phase-correlation residual)."""
import json
import logging

import cv2
import numpy as np
import pytest

from tests.unit import alignment_rig as rig
from thermal_inspection.cameras import camera_calibration as cc
from thermal_inspection.processing.fusion_processor import FusionProcessor

DEPTHS = (0.5, 1.0, 2.0, 3.0, 5.0)
CAL_AT = 2.0


def residual(depth, parallax, calibrated_at=None, target="thermal", compose=True, distance_known=True):
    thermal, rgb = rig.views(depth)
    fusion = FusionProcessor()
    comp = rig.make_compensator(depth)
    comp.correction_target = target
    if calibrated_at is not None:
        fusion.calibration_matrix = rig.homography_for(calibrated_at)
        if compose and parallax:
            fusion.set_parallax_composition(target, comp.geometric_shift_px_at(calibrated_at))
    if parallax:
        thermal, rgb = comp.apply_correction(thermal, rgb)
    return rig.residual_px(thermal, fusion.align_rgb_to_thermal(rgb, (rig.H, rig.W)))[0]


@pytest.mark.parametrize("depth", DEPTHS)
def test_parallax_alone_registers_at_every_depth(depth):
    assert abs(residual(depth, True)) < 1.0


@pytest.mark.parametrize("depth", DEPTHS)
def test_homography_alone_is_exact_only_at_its_calibration_distance(depth):
    expected = rig.F_PX * rig.BASELINE_M * (1 / depth - 1 / CAL_AT)
    assert residual(depth, False, CAL_AT) == pytest.approx(expected, abs=2.5)   # model + phase-correlation bias


@pytest.mark.parametrize("target", ["thermal", "rgb"])
def test_both_layers_without_composition_leave_a_constant_error(target):
    errs = [residual(d, True, CAL_AT, target, compose=False) for d in DEPTHS]
    assert all(abs(abs(e) - rig.shift_px(CAL_AT)) < 2.0 for e in errs), errs


@pytest.mark.parametrize("target", ["thermal", "rgb"])
@pytest.mark.parametrize("depth", DEPTHS)
def test_both_layers_with_composition_register(depth, target):
    assert abs(residual(depth, True, CAL_AT, target)) < 1.0


def test_shift_helper_matches_rounded_integer_version():
    comp = rig.make_compensator(2.0)
    for d in (0.4, 1.3, 2.0, 7.7):
        assert comp.compute_geometric_shift_px(d) == int(round(comp.geometric_shift_px_at(d)))
    assert comp.geometric_shift_px_at(CAL_AT) == pytest.approx(rig.shift_px(CAL_AT), abs=0.01)


def test_composition_is_identity_when_off_or_zero():
    f = FusionProcessor()
    f.calibration_matrix = rig.homography_for(CAL_AT)
    assert np.array_equal(f.effective_calibration_matrix(), f.calibration_matrix)
    f.set_parallax_composition("thermal", 0.0)
    assert np.array_equal(f.effective_calibration_matrix(), f.calibration_matrix)
    f.set_parallax_composition("thermal", 5.0)
    f.set_parallax_composition(None)
    assert np.array_equal(f.effective_calibration_matrix(), f.calibration_matrix)


def test_calibration_distance_round_trips_through_the_file(tmp_path):
    f = FusionProcessor()
    f.calibration_matrix = rig.homography_for(CAL_AT)
    f.calibration_distance_m = CAL_AT
    path = str(tmp_path / "c.json")
    assert f.save_calibration(path)
    g = FusionProcessor()
    assert g.load_calibration(path) and g.calibration_distance_m == CAL_AT
    legacy = tmp_path / "legacy.json"
    legacy.write_text(json.dumps({"homography": np.eye(3).tolist()}))
    h = FusionProcessor()
    assert h.load_calibration(str(legacy)) and h.calibration_distance_m is None


class _AppStub:
    from thermal_inspection.app import ThermalInspectionApp as _App
    _sync_alignment_composition = _App._sync_alignment_composition


def _stub(distance, parallax_on, target="thermal"):
    s = _AppStub()
    s._composition_warned = set()
    s.fusion_processor = FusionProcessor()
    s.fusion_processor.calibration_matrix = rig.homography_for(CAL_AT)
    s.fusion_processor.calibration_distance_m = distance
    s.parallax_compensator = rig.make_compensator(CAL_AT, enabled=parallax_on)
    s.parallax_compensator.correction_target = target
    return s


def test_app_sync_composes_when_distance_is_known():
    s = _stub(CAL_AT, True)
    s._sync_alignment_composition()
    assert s.fusion_processor._parallax_composition[0] == "thermal"
    assert s.fusion_processor._parallax_composition[1] == pytest.approx(rig.shift_px(CAL_AT), abs=0.01)
    s.parallax_compensator.enable(False)
    s._sync_alignment_composition()
    assert s.fusion_processor._parallax_composition is None


def test_app_warns_once_for_a_calibration_without_distance(caplog):
    s = _stub(None, True)
    with caplog.at_level(logging.WARNING):
        s._sync_alignment_composition()
        s._sync_alignment_composition()
    assert [r for r in caplog.records if "applied twice" in r.getMessage()].__len__() == 1


# ---------------------------------------------------------------- calibration module on rig images

def _shifted_pair():
    """Thermal/RGB snapshots of a richly textured scene with a known RGB->thermal translation."""
    rng = np.random.default_rng(3)
    base = cv2.GaussianBlur(rng.integers(0, 255, (rig.H + 40, rig.W + 40), dtype=np.uint8), (5, 5), 0)
    base = cv2.normalize(base, None, 0, 255, cv2.NORM_MINMAX)
    rgb = base[20:20 + rig.H, 20:20 + rig.W]
    thermal = base[20:20 + rig.H, 14:14 + rig.W]            # content 6 px further right in thermal... see test
    return thermal, rgb


def test_feature_calibration_recovers_a_known_translation(tmp_path):
    thermal, rgb = _shifted_pair()
    cal = cc.CameraCalibrator()
    assert cal.calibrate_with_features(thermal, rgb)
    H = cal.homography_matrix
    assert H[0, 2] == pytest.approx(6.0, abs=0.5) and abs(H[1, 2]) < 0.5
    assert cal.quality["rms_px"] < 1.0 and cal.quality["inliers"] >= cc.MIN_INLIERS


def test_sixteen_bit_input_is_accepted():
    thermal, rgb = _shifted_pair()
    cal = cc.CameraCalibrator()
    assert cal.calibrate_with_features(thermal.astype(np.uint16) * 200, rgb)


def test_cli_writes_a_file_the_app_loads_with_its_distance(tmp_path, capsys):
    thermal, rgb = _shifted_pair()
    t, r, out = str(tmp_path / "t.png"), str(tmp_path / "r.png"), str(tmp_path / "cal.json")
    cv2.imwrite(t, thermal)
    cv2.imwrite(r, rgb)
    assert cc.main(["--thermal", t, "--rgb", r, "--distance", "2.5", "--out", out,
                    "--preview", str(tmp_path / "p.png")]) == 0
    f = FusionProcessor()
    assert f.load_calibration(out) and f.calibration_distance_m == 2.5
    assert f.calibration_info["rms_px"] < 1.0
    assert (tmp_path / "p.png").exists()


def test_cli_refuses_unrelated_images_and_missing_files(tmp_path):
    rng = np.random.default_rng(1)
    t, r, out = str(tmp_path / "t.png"), str(tmp_path / "r.png"), str(tmp_path / "cal.json")
    cv2.imwrite(t, rng.integers(0, 255, (200, 200), dtype=np.uint8))
    cv2.imwrite(r, rng.integers(0, 255, (200, 200), dtype=np.uint8))
    assert cc.main(["--thermal", t, "--rgb", r, "--distance", "1", "--out", out]) == 1
    assert not (tmp_path / "cal.json").exists()
    assert cc.main(["--thermal", str(tmp_path / "nope.png"), "--rgb", r, "--distance", "1", "--out", out]) == 2


# ---------------------------------------------------------------- flirpy compatibility guard

def test_flirpy_guard_accepts_the_installed_version_and_flags_changes(monkeypatch):
    from thermal_inspection.sdk import boson_flirpy_ext as ext
    assert ext.check_flirpy_compatibility() == []
    monkeypatch.setattr(ext.Boson, "_decode_packet", lambda self, payload: None)
    assert any("_decode_packet" in p for p in ext.check_flirpy_compatibility())
    monkeypatch.delattr(ext.Boson, "_send_packet")
    assert any("no _send_packet" in p for p in ext.check_flirpy_compatibility())
