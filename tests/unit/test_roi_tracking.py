"""ROI tracking: history, peak hold, trend, alerts, unit changes, comparison, export. Pure Python, no camera."""
import csv
import json

import pytest

from thermal_inspection.processing.roi_manager import ROIManager
from thermal_inspection.processing.roi_tracking import (
    ROIAlert, ROITracker, export_rows, trend_from_values, write_csv,
)


def stats(avg, lo, hi, unit="°C", pixels=100, frame=1000):
    return {"temp_avg": avg, "temp_min": lo, "temp_max": hi, "temp_std": 1.0, "pixel_count": pixels,
            "frame_pixels": frame, "unit": unit}


class TestTrend:
    def test_needs_enough_samples(self):
        assert trend_from_values([1, 2, 3]) == "stable"

    def test_rising_falling_stable(self):
        assert trend_from_values([20] * 5 + [25] * 5) == "rising"
        assert trend_from_values([25] * 5 + [20] * 5) == "falling"
        assert trend_from_values([20.0] * 10) == "stable"
        assert trend_from_values([20, 20.1, 20, 20.2, 20] * 2) == "stable"       # noise below the threshold


class TestHistoryAndPeaks:
    def test_history_peak_hold_and_series(self):
        t = ROITracker()
        for i, hi in enumerate([50, 80, 60]):
            t.update({"a": stats(40, 30, hi)}, now=100.0 + i)
        rec = t.records["a"]
        assert rec.peak_max == 80 and rec.peak_min == 30
        assert [v for _, v in t.series("a", "max")] == [50, 80, 60]
        assert rec.history[-1][3] == 60                     # latest is not the peak

    def test_history_is_bounded(self):
        t = ROITracker()
        for i in range(700):
            t.update({"a": stats(1, 1, 1)}, now=float(i))
        assert len(t.records["a"].history) == 600

    def test_samples_without_temperatures_are_ignored(self):
        t = ROITracker()
        t.update({"a": {"temp_avg": None, "temp_min": None, "temp_max": None, "unit": "°C"}})
        assert not t.records["a"].history and t.records["a"].peak_max is None

    def test_clear_history_one_or_all(self):
        t = ROITracker()
        t.update({"a": stats(1, 1, 5), "b": stats(2, 2, 6)})
        t.clear_history("a")
        assert not t.records["a"].history and t.records["a"].peak_max is None and t.records["b"].history
        t.clear_history()
        assert not t.records["b"].history

    def test_prune_forgets_deleted_rois(self):
        t = ROITracker()
        t.update({"a": stats(1, 1, 1), "b": stats(1, 1, 1)})
        t.prune(["a"])
        assert list(t.records) == ["a"]


class TestUnits:
    def test_unit_change_converts_history_and_peaks(self):
        t = ROITracker()
        t.update({"a": stats(20, 10, 100, "°C")}, now=1)
        t.update({"a": stats(68, 50, 212, "°F")}, now=2)          # user switched to Fahrenheit
        rec = t.records["a"]
        assert rec.unit == "°F"
        assert rec.history[0][1:] == pytest.approx((68.0, 50.0, 212.0))      # old degC samples re-expressed in degF
        assert rec.peak_max == pytest.approx(212.0) and rec.peak_min == pytest.approx(50.0)

    def test_unconvertible_unit_starts_over_rather_than_mixing_scales(self):
        t = ROITracker()
        t.update({"a": stats(20, 10, 100, "°C")}, now=1)
        t.update({"a": stats(9000, 8000, 9500, "AGC")}, now=2)
        rec = t.records["a"]
        assert len(rec.history) == 1 and rec.peak_max == 9500

    def test_trend_threshold_scales_for_fahrenheit(self):
        t = ROITracker()
        for i in range(10):
            t.update({"a": stats(68.0 + (0.7 if i >= 5 else 0), 60, 70, "°F")}, now=float(i))   # +0.7 F = +0.39 C
        assert t.trend("a") == "stable"                      # below 0.5 degC once the threshold is scaled


class TestAlerts:
    def test_triggers_once_per_crossing_and_reports_transition(self):
        t = ROITracker()
        t.set_alert("a", ROIAlert(threshold=80, metric="max", type="above"))
        assert t.update({"a": stats(40, 30, 70)}) == []
        assert t.update({"a": stats(40, 30, 85)}) == ["a"]              # crossed: reported
        assert t.update({"a": stats(40, 30, 90)}) == []                 # still above: not reported again
        assert t.alert("a").triggered and t.alert("a").trigger_count == 1
        assert t.update({"a": stats(40, 30, 70)}) == [] and not t.alert("a").triggered
        assert t.update({"a": stats(40, 30, 95)}) == ["a"] and t.alert("a").trigger_count == 2

    def test_metric_selection_and_below(self):
        t = ROITracker()
        t.set_alert("a", ROIAlert(threshold=10, metric="min", type="below"))
        assert t.update({"a": stats(40, 30, 90)}) == []
        assert t.update({"a": stats(40, 5, 90)}) == ["a"]
        t.set_alert("b", ROIAlert(threshold=50, metric="avg", type="above"))
        assert t.update({"b": stats(60, 1, 2)}) == ["b"]               # average, not max

    def test_threshold_unit_conversion(self):
        a = ROIAlert(threshold=50.0, unit="°C")
        assert a.check(122.1, "°F")                                    # 50.06 degC > 50
        a2 = ROIAlert(threshold=50.0, unit="°C")
        assert not a2.check(121.0, "°F")

    def test_disabled_alert_never_fires(self):
        t = ROITracker()
        t.set_alert("a", ROIAlert(threshold=0, enabled=False))
        assert t.update({"a": stats(1, 1, 99)}) == []

    def test_describe(self):
        assert ROIAlert(threshold=85, metric="max", type="above", unit="°C").describe() == "Hottest pixel > 85 °C"


class TestCompareAndHottest:
    def test_compare_in_first_rois_unit(self):
        t = ROITracker()
        t.update({"a": stats(20, 10, 30, "°C"), "b": stats(26, 12, 41, "°C")})
        d = t.compare("a", "b")
        assert d["avg"] == pytest.approx(6) and d["max"] == pytest.approx(11) and d["min"] == pytest.approx(2)
        assert t.compare("a", "missing") is None

    def test_hottest_across_units_and_among(self):
        t = ROITracker()
        t.update({"a": stats(20, 10, 90, "°C"), "b": stats(60, 50, 200, "°F")})       # 200 F = 93.3 C
        assert t.hottest() == "b"
        assert t.hottest(among=["a"]) == "a"
        assert ROITracker().hottest() is None


class TestRowsAndExport:
    def _rows(self):
        mgr = ROIManager()
        r1 = mgr.create_rectangle_roi(0, 0, 10, 10, label="Panel A")
        r2 = mgr.create_rectangle_roi(20, 20, 10, 10, label="")
        mgr.set_locked(r1.roi_id, True)
        t = ROITracker()
        t.set_alert(r1.roi_id, ROIAlert(threshold=50))
        t.update({r1.roi_id: stats(40, 30, 60, pixels=250, frame=1000)})
        return t.rows([r1, r2]), r1, r2

    def test_rows_content(self):
        rows, r1, r2 = self._rows()
        a, b = rows
        assert a["name"] == "Panel A" and a["locked"] is True and a["visible"] is True
        assert a["max"] == 60 and a["peak_max"] == 60 and a["pixels"] == 250 and a["percent_of_frame"] == 25.0
        assert a["alert"] == "Hottest pixel > 50 °C" and a["alert_triggered"] is True and a["alert_count"] == 1
        assert b["name"] == r2.roi_id and b["max"] is None and b["unit"] == ""     # never measured

    def test_csv_and_json_by_extension(self, tmp_path):
        rows, *_ = self._rows()
        export_rows(str(tmp_path / "r.csv"), rows)
        with open(tmp_path / "r.csv", newline="", encoding="utf-8") as f:
            back = list(csv.DictReader(f))
        assert back[0]["name"] == "Panel A" and float(back[0]["max"]) == 60.0 and back[1]["max"] == ""       # None -> blank
        export_rows(str(tmp_path / "r.json"), rows)
        data = json.loads((tmp_path / "r.json").read_text(encoding="utf-8"))
        assert data["rois"][0]["alert_triggered"] is True and len(data["rois"]) == 2

    def test_export_with_no_rois_is_an_error(self, tmp_path):
        with pytest.raises(ValueError):
            write_csv(str(tmp_path / "x.csv"), [])
