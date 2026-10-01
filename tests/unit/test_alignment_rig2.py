"""Calibration + parallax on a rig that looks like the real hardware: different focal lengths and resolutions, a rolled RGB
camera (alignment_rig2.py). Residuals are phase-correlation measurements against exact geometry."""
import cv2
import numpy as np
import pytest

from tests.unit import alignment_rig2 as r2
from tests.unit.alignment_rig import residual_px
from thermal_inspection.cameras.camera_calibration import CameraCalibrator
from thermal_inspection.processing.fusion_processor import FusionProcessor

CAL_AT = 2.0


def calibrated_fusion(roll=0.0, edges=False):
    t, rg = r2.views(CAL_AT, roll)
    cal = CameraCalibrator()
    assert cal.calibrate_with_features(t, rg, use_edges=edges), "calibration failed"
    f = FusionProcessor()
    f.set_calibration(cal.homography_matrix, CAL_AT,
                      dict(cal.quality, thermal_shape=list(cal.thermal_shape), rgb_shape=list(cal.rgb_shape)))
    return f, cal


@pytest.mark.parametrize("roll", [0.0, 2.0, 5.0])
@pytest.mark.parametrize("edges", [False, True])
def test_feature_calibration_handles_different_fov_resolution_and_roll(roll, edges):
    f, cal = calibrated_fusion(roll, edges)
    assert cal.quality["rms_px"] < 1.0 and cal.quality["inliers"] >= 50
    t, rg = r2.views(CAL_AT, roll)
    dx, dy = residual_px(t, f.align_rgb_to_thermal(rg, (r2.TH, r2.TW)))
    assert abs(dx) < 1.0 and abs(dy) < 1.0, (dx, dy)


@pytest.mark.parametrize("target", ["thermal", "rgb"])
@pytest.mark.parametrize("depth", [0.7, 1.0, 4.0])
def test_composition_holds_with_scale_and_roll(depth, target):
    f, _ = calibrated_fusion(roll=2.0)
    t, rg = r2.views(depth, 2.0)
    comp = r2.make_compensator(depth, target)
    f.set_parallax_composition(target, comp.geometric_shift_px_at(CAL_AT))
    t2, rg2 = comp.apply_correction(t, rg)
    dx, dy = residual_px(t2, f.align_rgb_to_thermal(rg2, (t2.shape[0], t2.shape[1])))
    assert abs(dx) < 1.5 and abs(dy) < 1.5, (dx, dy)


def test_homography_alone_leaves_a_distance_dependent_error_that_composition_removes():
    f, _ = calibrated_fusion()
    t, rg = r2.views(0.7)
    uncorrected = residual_px(t, f.align_rgb_to_thermal(rg, (r2.TH, r2.TW)))[0]
    assert uncorrected > 8.0                                      # ~12 px at 0.7 m with a 2 m calibration


def test_calibration_rescales_to_a_higher_live_resolution():
    f, _ = calibrated_fusion()
    s = 2
    th = cv2.cvtColor(r2.render(r2.TW * s, r2.TH * s, r2.F_T * s, CAL_AT, 0.0), cv2.COLOR_GRAY2BGR)
    rg = cv2.cvtColor(r2.render(r2.RW * s, r2.RH * s, r2.F_R * s, CAL_AT, -r2.BASELINE_M), cv2.COLOR_GRAY2BGR)
    dx, dy = residual_px(th, f.align_rgb_to_thermal(rg, (th.shape[0], th.shape[1])), margin=100)
    assert abs(dx) < 2.0 and abs(dy) < 2.0, (dx, dy)               # measured in the larger thermal frame's pixels


# ---------------------------------------------------------------- auto fine-tune on top of a calibration

def test_auto_align_on_calibrated_frames_measures_only_the_residual():
    f, _ = calibrated_fusion()
    t, rg = r2.views(CAL_AT)
    registered = f.align_rgb_to_thermal(rg, (r2.TH, r2.TW))
    comp = r2.make_compensator(CAL_AT)
    comp.set_manual_shift(0, 0)
    comp.compute_auto_alignment(CAL_AT, registered, t, allow_geometry_fallback=False)
    assert comp.last_auto_alignment_source == "image"
    assert abs(comp.manual_shift_x) <= 1 and abs(comp.manual_shift_y) <= 1      # already registered: ~no fine-tune
    assert abs(comp.fov_zoom_factor - 1.0) < 0.02


def test_inconclusive_auto_align_does_not_apply_the_geometry_formula_when_calibrated():
    comp = r2.make_compensator(CAL_AT)
    comp.set_manual_shift(3, 4)
    flat = np.full((r2.TH, r2.TW, 3), 100, np.uint8)
    out = comp.compute_auto_alignment(CAL_AT, flat, flat, allow_geometry_fallback=False)
    assert comp.last_auto_alignment_source == "none"
    assert (comp.manual_shift_x, comp.manual_shift_y) == (3, 4) and out[0] == 3     # nothing changed
    comp.compute_auto_alignment(CAL_AT, flat, flat)                                   # default keeps the old fallback
    assert comp.last_auto_alignment_source == "geometry"
