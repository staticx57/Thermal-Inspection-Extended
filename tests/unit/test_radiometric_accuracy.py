"""Radiometric accuracy: the converter must agree with the camera's own T-Linear output, and the calibration tools must
refuse degenerate inputs instead of producing plausible-looking garbage."""
import json
import time

import numpy as np
import pytest

from thermal_inspection.processing.radiometric_converter import TLinearConverter
from thermal_inspection.utils.radiometric_calibration import RadiometricCalibrator

COUNTS_20C = int(round((20.0 + 273.15) * 100))            # Boson T-Linear: Kelvin * 100


class TestTLinearConversion:
    def test_default_conversion_is_kelvin_times_100(self):
        c = TLinearConverter()
        assert c.pixel_to_temperature(COUNTS_20C) == pytest.approx(20.0, abs=0.01)
        assert c.pixel_to_temperature(37315) == pytest.approx(100.0, abs=0.01)
        frame = np.full((4, 4), COUNTS_20C, np.uint16)
        assert c.convert_frame(frame) == pytest.approx(20.0, abs=0.01)
        assert c.get_spot_temperature(frame, 1, 2) == pytest.approx(20.0, abs=0.01)

    def test_temperature_range_setting_does_not_change_readings(self):
        c = TLinearConverter()
        before = c.pixel_to_temperature(COUNTS_20C)
        c.set_temperature_range(-20.0, 150.0)
        assert c.pixel_to_temperature(COUNTS_20C) == before
        assert c.convert_frame(np.full((2, 2), COUNTS_20C, np.uint16))[0, 0] == pytest.approx(before)

    def test_range_method_is_an_explicit_estimate(self):
        c = TLinearConverter(method="range")
        c.set_temperature_range(0.0, 100.0)
        assert c.pixel_to_temperature(0) == pytest.approx(0.0)
        assert c.pixel_to_temperature(65535) == pytest.approx(100.0)

    def test_camera_class_agrees_with_the_flirpy_backend_formula(self):
        from thermal_inspection.cameras.flir_camera import FLIRBosonCamera
        cam = FLIRBosonCamera.__new__(FLIRBosonCamera)
        FLIRBosonCamera.__init__(cam, enable_sdk=False)
        cam.radiometric_enabled = True
        cam.is_radiometric_enabled = lambda: True
        cam.last_frame_16bit = np.full((8, 8), COUNTS_20C, np.uint16)
        assert cam.get_spot_temperature(3, 3) == pytest.approx(COUNTS_20C / 100.0 - 273.15, abs=1e-3)
        assert cam.get_temperature_frame()[0, 0] == pytest.approx(20.0, abs=0.01)

    def test_calibration_slope_offset_still_wins(self):
        c = TLinearConverter()
        c.set_calibration(0.01, -273.15 + 1.5)
        assert c.pixel_to_temperature(COUNTS_20C) == pytest.approx(21.5, abs=0.01)


class TestLut:
    @staticmethod
    def write(path, step=1):
        rows = ["pixel_value,temperature_celsius"] + [f"{p},{p / 100.0 - 273.15:.4f}" for p in range(20000, 40001, step)]
        path.write_text("\n".join(rows))

    def test_vectorised_frame_matches_scalar_and_is_fast(self, tmp_path):
        f = tmp_path / "lut.csv"
        self.write(f, step=1)                                   # 20001 entries
        c = TLinearConverter()
        assert c.load_lut_from_file(str(f))
        frame = np.random.default_rng(0).integers(15000, 45000, (512, 640)).astype(np.uint16)
        t0 = time.time()
        out = c.convert_frame(frame)
        assert time.time() - t0 < 1.0, "LUT frame conversion must be vectorised"
        for (y, x) in ((0, 0), (100, 200), (511, 639)):
            assert out[y, x] == pytest.approx(c.pixel_to_temperature_lut(int(frame[y, x])), abs=1e-3)
        assert out.min() == pytest.approx(20000 / 100.0 - 273.15, abs=1e-3)       # clamped at the table ends

    def test_interpolates_between_entries_and_accepts_float_counts(self, tmp_path):
        f = tmp_path / "lut.csv"
        f.write_text("pixel_value,temp\n30000.0,0.0\n30100.0,10.0\n")
        c = TLinearConverter()
        assert c.load_lut_from_file(str(f))
        assert c.pixel_to_temperature(30050) == pytest.approx(5.0)


class TestReferenceCalibration:
    def test_two_references_fit_and_apply(self):
        c = TLinearConverter()
        assert c.calibrate_from_references([(27315, 0.0), (37315, 100.0)])
        assert c.pixel_to_temperature(32315) == pytest.approx(50.0, abs=1e-3)

    def test_degenerate_references_are_refused(self):
        c = TLinearConverter()
        assert not c.calibrate_from_references([(30000, 10.0), (30000, 20.0)])      # same count twice
        assert not c.calibrate_from_references([(27315, 100.0), (37315, 0.0)])      # hotter reads LOWER
        assert not c.is_calibrated


class TestPointCalibrator:
    @staticmethod
    def points(pairs):
        cal = RadiometricCalibrator()
        for i, (ref, meas) in enumerate(pairs):
            cal.add_calibration_point(ref, meas, 10 + i, 10)
        return cal

    def test_linear_fit_corrects_a_known_gain_and_offset(self):
        cal = self.points([(20, 22.5), (40, 42.5), (60, 62.5)])
        assert cal.compute_calibration("linear")
        assert cal.apply_calibration(32.5) == pytest.approx(30.0, abs=1e-6)
        s = cal.get_calibration_stats()
        assert s["rmse"] == pytest.approx(2.5) and s["fit_rmse"] < 1e-6          # raw error vs what is left

    def test_identical_measured_values_are_refused(self):
        cal = self.points([(20, 25.0), (40, 25.0)])
        assert not cal.compute_calibration("linear")
        cal = self.points([(0, 1), (10, 11), (10, 11), (20, 21)])
        assert not cal.compute_calibration("polynomial", 3)                       # 3 distinct values < degree + 1

    def test_polynomial_does_not_run_away_outside_the_fitted_range(self):
        cal = self.points([(0, 0), (25, 27), (50, 51), (75, 79), (100, 101)])
        assert cal.compute_calibration("polynomial", 4)
        far = cal.apply_calibration(300.0)
        assert abs(far - 300.0) < 10, far                      # unbounded extrapolation of a quartic gives thousands
        assert cal.apply_calibration(-100.0) == pytest.approx(-100.0, abs=10)
        assert cal.apply_calibration(50.0) == pytest.approx(cal.apply_calibration_to_frame(np.array([50.0]))[0], abs=1e-4)

    def test_import_is_atomic_and_round_trips(self, tmp_path):
        cal = self.points([(20, 22.5), (40, 42.5)])
        cal.compute_calibration("linear")
        good = tmp_path / "c.json"
        assert cal.export_calibration(str(good))
        other = RadiometricCalibrator()
        assert other.import_calibration(str(good)) and other.apply_calibration(32.5) == pytest.approx(30.0, abs=1e-6)
        data = json.loads(good.read_text())
        data["calibration_points"][0].pop("measured_temp")
        broken = tmp_path / "broken.json"
        broken.write_text(json.dumps(data))
        assert not other.import_calibration(str(broken))
        assert len(other.calibration_points) == 2 and other.is_calibrated      # untouched by the failed import


class TestCorrectionIsActuallyApplied:
    """The Temp Calibration tab computed a curve that nothing ever applied: the 'Enable Calibration Correction' box had
    no effect on any reading."""

    @staticmethod
    def stub():
        from thermal_inspection.app import ThermalInspectionApp
        from thermal_inspection.core.calibration_manager import CalibrationManager

        class S:
            _correct_temperature_c = ThermalInspectionApp._correct_temperature_c
        s = S()
        s.calibration_manager = CalibrationManager()
        cal = s.calibration_manager.radiometric_calibrator
        for ref, meas in ((20, 22.5), (40, 42.5), (60, 62.5)):
            cal.add_calibration_point(ref, meas, 1, 1)
        return s, cal

    def test_off_until_computed_and_enabled(self):
        s, cal = self.stub()
        assert s._correct_temperature_c(32.5) == 32.5                       # not computed
        assert cal.compute_calibration("linear")
        assert s._correct_temperature_c(32.5) == 32.5                       # computed but not enabled
        s.calibration_manager.set_calibration_enabled(True)
        assert s._correct_temperature_c(32.5) == pytest.approx(30.0, abs=1e-6)
        assert s._correct_temperature_c(None) is None
        arr = s._correct_temperature_c(np.array([[22.5, 62.5]], np.float32))
        assert arr.dtype == np.float32 and arr[0].tolist() == pytest.approx([20.0, 60.0], abs=1e-4)
        s.calibration_manager.set_calibration_enabled(False)
        assert s._correct_temperature_c(32.5) == 32.5

    def test_analyzer_readings_follow_the_correction(self):
        from thermal_inspection.processing.thermal_analyzer import ThermalAnalyzer
        a = ThermalAnalyzer()
        raw = (32.5 + 273.15) * 100
        assert a._y16_to_celsius(raw) == pytest.approx(32.5, abs=1e-3)
        s, cal = self.stub()
        cal.compute_calibration("linear")
        s.calibration_manager.set_calibration_enabled(True)
        a.temperature_correction = s._correct_temperature_c
        assert a._y16_to_celsius(raw) == pytest.approx(30.0, abs=1e-3)
