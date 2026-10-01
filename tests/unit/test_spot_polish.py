"""Spot meter polish: snap to hottest pixel, rate-of-change alerts, peak hold, unit-switch keeps history."""
import numpy as np
import pytest
from PyQt6.QtWidgets import QApplication

from thermal_inspection.gui.panels.spot_meter_panel import (
    SpotMeterAlert, SpotMeterAlertDialog, SpotMeterData, SpotMeterListItem, SpotMeterPanel,
)
from thermal_inspection.processing.spot_tracking import convert_delta, rate_per_minute, snap_to_hottest


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


class TestSnap:
    def _frame(self):
        f = np.full((60, 80), 100, np.uint16)
        f[30, 40] = 500                                   # the real peak
        f[31, 41] = 400
        return f

    def test_click_next_to_the_peak_lands_on_it(self):
        assert snap_to_hottest(self._frame(), 37, 33, radius=6) == (40, 30)

    def test_outside_the_radius_or_frame_is_unchanged(self):
        f = self._frame()
        assert snap_to_hottest(f, 5, 5, radius=3) == (5, 5)                 # flat window: nothing to snap to
        assert snap_to_hottest(f, 500, 500) == (500, 500) and snap_to_hottest(f, -1, 3) == (-1, 3)

    def test_ties_keep_the_pixel_nearest_the_click(self):
        f = np.zeros((20, 20), np.uint8)
        f[5, 5] = f[5, 12] = 9
        assert snap_to_hottest(f, 11, 6, radius=8) == (12, 5)

    def test_edges_and_colour_frames(self):
        f = np.zeros((10, 10), np.uint8)
        f[0, 0] = 200
        assert snap_to_hottest(f, 2, 2, radius=4) == (0, 0)                 # window clipped at the frame edge
        rgb = np.zeros((10, 10, 3), np.uint8)
        rgb[4, 6] = (255, 255, 255)
        assert snap_to_hottest(rgb, 5, 5, radius=3) == (6, 4)
        assert snap_to_hottest(None, 1, 1) == (1, 1)


class TestRate:
    def _hist(self, slope_per_min, seconds=20, step=1.0, base=20.0):
        return [(t, base + slope_per_min * t / 60.0) for t in np.arange(0, seconds, step)]

    def test_slope_recovered(self):
        assert rate_per_minute(self._hist(6.0)) == pytest.approx(6.0, abs=1e-6)
        assert rate_per_minute(self._hist(-3.0)) == pytest.approx(-3.0, abs=1e-6)

    def test_not_enough_history_is_none(self):
        assert rate_per_minute([(0, 1), (1, 2)]) is None
        assert rate_per_minute([(0, 1), (0.5, 1), (1.0, 1)]) is None         # spans under 3 s

    def test_only_the_recent_window_counts(self):
        old_flat = [(t, 20.0) for t in range(0, 60)]
        rising = [(60 + t, 20.0 + t * 0.5) for t in range(0, 60)]          # the last 30 s are all rising
        assert rate_per_minute(old_flat + rising) == pytest.approx(30.0, abs=1e-6)       # 0.5/s over the last 30 s

    def test_delta_units(self):
        assert convert_delta(10.0, "°C", "°F") == pytest.approx(18.0)
        assert convert_delta(18.0, "°F", "°C") == pytest.approx(10.0)
        assert convert_delta(5.0, "°C", "K") == pytest.approx(5.0)
        assert convert_delta(5.0, "°C", "AGC") is None


class TestRateAlerts:
    def _hist(self, slope):
        return [(float(t), 20.0 + slope * t / 60.0) for t in range(0, 20)]

    def test_rising_fast_fires_only_above_the_rate(self):
        a = SpotMeterAlert(threshold=5.0, type="rising_fast", unit="°C")
        assert not a.check(20.0, "°C", self._hist(3.0))
        assert a.check(26.0, "°C", self._hist(8.0)) and a.trigger_count == 1
        assert a.check(26.0, "°C", self._hist(9.0)) and a.trigger_count == 1       # still firing: counted once
        assert not a.check(20.0, "°C", self._hist(0.0)) and not a.triggered

    def test_falling_fast_and_unit_conversion_of_the_rate(self):
        a = SpotMeterAlert(threshold=5.0, type="falling_fast", unit="°C")
        assert not a.check(0, "°C", self._hist(-3.0))
        assert a.check(0, "°C", self._hist(-8.0))
        f = SpotMeterAlert(threshold=5.0, type="rising_fast", unit="°C")
        hist_f = [(t, 68.0 + 18.0 * t / 60.0) for t in range(0, 20)]                # +18 F/min = +10 C/min
        assert f.check(0, "°F", hist_f)

    def test_no_history_never_fires_and_old_types_unchanged(self):
        assert not SpotMeterAlert(threshold=1, type="rising_fast").check(99, "°C", [])
        assert SpotMeterAlert(threshold=50, type="above").check(60, "°C")
        assert SpotMeterAlert(threshold=50, type="below").check(40, "°C")

    def test_describe(self):
        assert SpotMeterAlert(threshold=5, type="rising_fast").describe() == "rises faster than 5 °C/min"
        assert SpotMeterAlert(threshold=80, type="above").describe() == "above 80 °C"

    def test_dialog_round_trips_the_new_types(self, qapp):
        dlg = SpotMeterAlertDialog(SpotMeterAlert(threshold=4.0, type="falling_fast"), "°C")
        assert dlg.falling_radio.isChecked()
        dlg.rising_radio.setChecked(True)
        dlg._on_accept()
        assert dlg.result_alert.type == "rising_fast" and dlg.result_alert.threshold == 4.0


class TestPeakHoldAndUnits:
    def test_peak_and_trough_hold_then_reset(self):
        d = SpotMeterData(id="s", label="SP1", x=1, y=1)
        for v in (30, 55, 40):
            d.record_extremes(v)
        assert (d.peak, d.trough) == (55, 30)
        d.reset_peak()
        assert d.peak is None and d.trough is None

    def test_unit_switch_converts_history_and_peak(self):
        d = SpotMeterData(id="s", label="SP1", x=1, y=1, unit="°C")
        for v in (20.0, 100.0):
            d.add_history(v)
            d.record_extremes(v)
        d.convert_unit("°F")
        assert [round(v, 1) for _, v in d.history] == [68.0, 212.0] and d.peak == pytest.approx(212.0)
        d.convert_unit("AGC")                                                  # not convertible: start over
        assert d.history == [] and d.peak is None

    def test_panel_holds_peak_shows_it_and_survives_a_unit_switch(self, qapp):
        panel = SpotMeterPanel()
        data = panel.add_spot("s1", 5, 5, "SP1")
        for v in (30.0, 80.0, 50.0):
            panel._apply_temperature("s1", v, "°C")
        item = SpotMeterListItem(data)
        assert "⌃80.0" in item.text() and "50.0" in item.text()
        panel._apply_temperature("s1", 122.0, "°F")                            # 50 C shown in F
        assert data.unit == "°F" and data.peak == pytest.approx(176.0) and len(data.history) == 4
        panel.spot_list.setCurrentRow(0)
        panel._on_reset_peak()
        assert data.peak is None

    def test_alert_flag_shows_in_the_list(self, qapp):
        panel = SpotMeterPanel()
        data = panel.add_spot("s1", 5, 5, "SP1")
        data.alert = SpotMeterAlert(threshold=50, type="above", sound_enabled=False)
        panel._apply_temperature("s1", 60.0, "°C")
        assert "⚠" in SpotMeterListItem(data).text()

    def test_snap_toggle_emits(self, qapp):
        panel = SpotMeterPanel()
        seen = []
        panel.snap_to_hottest_changed.connect(seen.append)
        panel.snap_cb.setChecked(True)
        assert seen == [True]
