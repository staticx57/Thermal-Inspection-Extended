"""Manual threshold widget: percentage / real-temperature / raw Y16 modes, unit handling, and the detector end to end."""
import numpy as np
import pytest
from PyQt6.QtWidgets import QApplication

from thermal_inspection.gui.panels.anomaly_widgets import ManualThresholdWidget
from thermal_inspection.processing.thermal_analyzer import ThermalAnalyzer, ThresholdMode


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def w(qapp):
    widget = ManualThresholdWidget()
    widget.set_raw_mode_available(True)
    return widget


def record(widget):
    events = []
    widget.use_raw_values_changed.connect(lambda v: events.append(("raw", v)))
    widget.min_threshold_changed.connect(lambda v: events.append(("min", round(v, 3))))
    widget.max_threshold_changed.connect(lambda v: events.append(("max", round(v, 3))))
    return events


class TestModes:
    def test_starts_in_percentage_and_non_radiometric_cannot_leave_it(self, qapp):
        widget = ManualThresholdWidget()
        assert widget.value_mode == "percent"
        assert not widget.temperature_radio.isEnabled() and not widget.advanced_radio.isEnabled()
        widget._set_value_mode("temperature")
        assert widget.value_mode == "percent"                                # refused: an 8-bit frame has no temperatures

    def test_radiometric_enables_both_and_losing_it_falls_back(self, w):
        assert w.temperature_radio.isEnabled() and w.advanced_radio.isEnabled()
        w.temperature_radio.click()
        assert w.value_mode == "temperature"
        w.set_raw_mode_available(False)
        assert w.value_mode == "percent" and not w.temperature_radio.isEnabled()

    def test_temperature_mode_sends_y16_counts_to_the_detector(self, w):
        events = record(w)
        w.temperature_radio.click()
        assert events[0] == ("raw", True)                                    # tells the detector how to read numbers first
        assert ("min", 31315.0) in events and ("max", 33315.0) in events       # 40 C and 60 C as Kelvin x 100
        events.clear()
        w.min_threshold_spin.setValue(25.0)
        assert events == [("min", 29815.0)]

    def test_each_mode_remembers_its_own_thresholds(self, w):
        w.min_threshold_spin.setValue(10)                                    # percentage
        w.temperature_radio.click()
        w.min_threshold_spin.setValue(55.5)
        w.percent_radio.click()
        assert w.min_threshold_spin.value() == 10
        w.temperature_radio.click()
        assert w.min_threshold_spin.value() == pytest.approx(55.5)

    def test_raw_range_covers_real_y16_counts(self, w):
        w.advanced_radio.click()
        assert w.min_threshold_spin.maximum() == 65535
        w.min_threshold_spin.setValue(30000)                                  # impossible under the old 0-16383 cap
        assert w.min_threshold_spin.value() == 30000

    def test_percent_mode_is_unchanged(self, w):
        events = record(w)
        w.min_threshold_spin.setValue(20)
        assert events == [("min", 20.0)]
        assert "Percentage" in w.threshold_hint.text()


class TestUnits:
    def test_unit_switch_keeps_the_physical_threshold(self, w):
        w.temperature_radio.click()
        w.min_threshold_spin.setValue(50.0)                                   # 50 C
        events = record(w)
        w.set_temperature_unit("F")
        assert w.min_threshold_spin.value() == pytest.approx(122.0)
        assert w.min_threshold_spin.suffix() == " °F"
        assert events == []                                                   # the detector's counts did not change
        assert w.backend_value(0) == pytest.approx((50 + 273.15) * 100)
        w.min_threshold_spin.setValue(212.0)                                  # edited in F: 100 C
        assert w.backend_value(0) == pytest.approx((100 + 273.15) * 100)
        w.set_temperature_unit("K")
        assert w.min_threshold_spin.value() == pytest.approx(373.15, abs=0.06)

    def test_unit_chosen_before_entering_temperature_mode(self, w):
        w.set_temperature_unit("F")
        w.temperature_radio.click()
        assert w.min_threshold_spin.value() == pytest.approx(104.0) and w.min_threshold_spin.suffix() == " °F"

    def test_unknown_unit_is_celsius(self, w):
        w.set_temperature_unit("Y16")
        assert w.unit == "C"

    def test_range_follows_the_unit(self, w):
        w.temperature_radio.click()
        assert w.min_threshold_spin.minimum() == pytest.approx(-100.0)
        w.set_temperature_unit("F")
        assert w.min_threshold_spin.minimum() == pytest.approx(-148.0)


class TestWithTheRealDetector:
    def _frame(self):
        frame = np.full((40, 40), 29815, np.uint16)                            # 25 C scene
        frame[10:20, 10:20] = 34815                                            # a 75 C patch (100 pixels)
        return frame

    def test_a_temperature_threshold_finds_the_hot_patch(self, w):
        w.temperature_radio.click()
        w.min_threshold_spin.setValue(60.0)
        res = ThermalAnalyzer().detect_threshold_anomalies(
            self._frame(), ThresholdMode.ABOVE, w.backend_value(0), use_raw_values=True)
        assert res.anomaly_count == 100

    def test_the_same_threshold_entered_in_fahrenheit(self, w):
        w.set_temperature_unit("F")
        w.temperature_radio.click()
        w.min_threshold_spin.setValue(140.0)                                    # 60 C
        res = ThermalAnalyzer().detect_threshold_anomalies(
            self._frame(), ThresholdMode.ABOVE, w.backend_value(0), use_raw_values=True)
        assert res.anomaly_count == 100

    def test_between_uses_both_ends(self, w):
        w.temperature_radio.click()
        w.min_threshold_spin.setValue(70.0)
        w.max_threshold_spin.setValue(80.0)
        res = ThermalAnalyzer().detect_threshold_anomalies(
            self._frame(), ThresholdMode.BETWEEN, w.backend_value(0), w.backend_value(1), use_raw_values=True)
        assert res.anomaly_count == 100
