"""Colorbar: round tick values, rendering orientation, sizing, visibility rules, and the main window's feed of it."""
from unittest.mock import MagicMock

import numpy as np
import pytest
from PyQt6.QtWidgets import QApplication

from thermal_inspection.gui.main_window import InspectionAppWindow as MainWindow
from thermal_inspection.gui.widgets import colorbar_widget as cb


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


class TestTicks:
    @pytest.mark.parametrize("lo,hi,expected", [
        (20, 80, [20, 30, 40, 50, 60, 70, 80]),
        (0, 100, [0, 20, 40, 60, 80, 100]),
        (23.7, 41.2, [25, 30, 35, 40]),
        (-5, 5, [-4, -2, 0, 2, 4]),
        (0.0, 1.0, [0, 0.2, 0.4, 0.6, 0.8, 1.0]),
    ])
    def test_round_values_inside_the_range(self, lo, hi, expected):
        got = cb.nice_ticks(lo, hi, max_ticks=7 if len(expected) == 7 else 6)
        assert got == pytest.approx(expected)
        assert all(lo - 1e-9 <= t <= hi + 1e-9 for t in got)

    def test_never_more_than_asked(self):
        for lo, hi in [(0, 1), (0, 3.7), (-40, 600), (29000, 31000), (0.01, 0.02)]:
            assert 1 <= len(cb.nice_ticks(lo, hi, 5)) <= 5 + 1

    def test_degenerate_and_bad_ranges(self):
        assert cb.nice_ticks(30, 30) == [30]
        assert cb.nice_ticks(5, 1) == cb.nice_ticks(1, 5)                    # reversed ends are tolerated
        assert cb.nice_ticks(float("nan"), 1) == []

    def test_label_decimals_follow_the_step(self):
        assert cb.format_tick(25.0, 5) == "25" and cb.format_tick(2.5, 2.5) == "2.5"
        assert cb.format_tick(0.2, 0.2) == "0.2" and cb.format_tick(0.25, 0.05) == "0.25"
        assert cb.format_tick(-0.0, 0.5) == "0"                              # no "-0.0"

    def test_relative_units(self):
        assert cb.is_relative_unit("AGC") and cb.is_relative_unit("AGC (raw)") and cb.is_relative_unit("")
        assert not cb.is_relative_unit("°C") and not cb.is_relative_unit("°F (est)")


def lut_gradient():
    lut = np.zeros((256, 3), np.uint8)
    lut[:, 0] = np.arange(256)                      # B rises with index
    lut[:, 2] = 255 - np.arange(256)                # R falls: index 0 = red-ish (cold), 255 = blue-ish (hot) in BGR
    return lut


class TestWidget:
    def _bar(self, qapp, **kw):
        w = cb.ColorbarWidget()
        w.set_palette_lut(lut_gradient())
        w.set_temperature_range(kw.get("lo", 20.0), kw.get("hi", 80.0), kw.get("unit", "°C"))
        return w

    def test_nothing_painted_without_a_palette(self, qapp):
        w = cb.ColorbarWidget()
        img = w.grab().toImage()
        assert img.pixelColor(5, 5).alpha() == 0 or img.pixelColor(5, 5).rgb() == img.pixelColor(1, 1).rgb()

    def test_hot_is_at_the_top_and_cold_at_the_bottom(self, qapp):
        w = self._bar(qapp)
        w.show()
        qapp.processEvents()
        img = w.grab().toImage()                                              # device pixels: may be scaled on HiDPI
        hot, cold = [], []
        for y in range(img.height()):
            for x in range(img.width()):
                c = img.pixelColor(x, y)
                if c.blue() > 200 and c.red() < 60:
                    hot.append(y)                                              # LUT[255]: blue-ish end
                elif c.red() > 200 and c.blue() < 60:
                    cold.append(y)                                             # LUT[0]: red-ish end
        assert hot and cold
        assert sum(hot) / len(hot) < sum(cold) / len(cold)                     # hot end sits above the cold end
        w.hide()

    def test_size_fits_the_widest_label_and_the_header(self, qapp):
        w = self._bar(qapp, lo=-273.15, hi=1234.5, unit="°F (est)")
        from PyQt6.QtGui import QFontMetrics
        fm = QFontMetrics(w.font)
        widest = max(fm.horizontalAdvance(t) for _, t in w._labels())
        assert w.width() >= 8 + w.bar_thickness + 11 + widest                  # nothing clipped on the right
        assert w._header() == "~°F"                                            # unit once, estimate marked

    def test_relative_mode_shows_no_numbers(self, qapp):
        w = self._bar(qapp, lo=0.0, hi=1.0, unit="AGC")
        assert [t for _, t in w._labels()] == ["hot", "cold"] and w._header() == ""

    def test_scales_with_the_video_area_within_limits(self, qapp):
        w = self._bar(qapp)
        w.set_available_size(1000, 300)
        small = w.height()
        w.set_available_size(2000, 1500)
        assert w.height() > small and w.bar_length <= cb.MAX_BAR_LENGTH
        w.set_available_size(100, 100)
        assert w.bar_length == cb.MIN_BAR_LENGTH

    def test_visibility_needs_user_choice_and_a_sensible_view(self, qapp):
        w = self._bar(qapp)
        w.show()
        w.set_view_allowed(False)
        assert w.isHidden()
        w.set_view_allowed(True)
        assert not w.isHidden()
        w.set_enabled(False)
        assert w.isHidden()
        w.set_view_allowed(False)
        w.set_enabled(True)
        assert w.isHidden()                                                    # still hidden: wrong view

    def test_same_palette_is_not_rebuilt(self, qapp):
        w = self._bar(qapp)
        first = w._gradient
        w.set_palette_lut(lut_gradient().copy())
        assert w._gradient is first
        w.set_palette_lut(np.zeros((10, 3), np.uint8))                         # bad shape ignored
        assert w._gradient is first

    def test_horizontal_layout_renders(self, qapp):
        w = self._bar(qapp)
        w.set_position("bottom")
        assert w.width() > w.height()
        w.show()
        assert not w.grab().isNull()


class _Win:
    def __init__(self, unit="C"):
        self.video_widget = MagicMock()
        self._temp_unit = unit


class TestMainWindowFeed:
    def _temps(self):
        t = np.full((64, 64), 30.0, np.float32)
        t[:, :32] = 20.0
        t[0, 0] = 500.0                                                       # one wild pixel
        return t

    def test_range_is_the_palette_stretch_not_the_scene_extremes(self):
        w = _Win()
        MainWindow._update_colorbar(w, np.zeros((256, 3), np.uint8), self._temps(), True, True)
        lo, hi, unit = w.video_widget.overlay.update_colorbar_range.call_args[0]
        assert unit == "°C" and lo == pytest.approx(20.0, abs=0.01) and hi < 100            # 500 C outlier ignored
        w.video_widget.overlay.update_colorbar_palette.assert_called_once()

    def test_range_follows_the_apps_unit(self):
        w = _Win("F")
        MainWindow._update_colorbar(w, None, self._temps(), True, True)
        lo, hi, unit = w.video_widget.overlay.update_colorbar_range.call_args[0]
        assert unit == "°F" and lo == pytest.approx(68.0, abs=0.1)

    def test_non_radiometric_gets_relative_ends(self):
        w = _Win()
        MainWindow._update_colorbar(w, None, self._temps(), False, True)
        assert w.video_widget.overlay.update_colorbar_range.call_args[0][2] == "AGC"

    def test_throttled_and_skipped_when_results_unchanged(self):
        w = _Win()
        MainWindow._update_colorbar(w, None, self._temps(), True, True)
        MainWindow._update_colorbar(w, None, self._temps(), True, True)       # within 0.5 s: skipped
        assert w.video_widget.overlay.update_colorbar_range.call_count == 1
        w2 = _Win()
        MainWindow._update_colorbar(w2, None, self._temps(), True, False)     # analyzer result not new
        w2.video_widget.overlay.update_colorbar_range.assert_not_called()

    def test_no_overlay_is_safe(self):
        w = _Win()
        w.video_widget = object()
        MainWindow._update_colorbar(w, None, self._temps(), True, True)       # must not raise
