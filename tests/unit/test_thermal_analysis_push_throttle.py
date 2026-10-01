"""
Regression test for a perf finding (2026-09-04): MainWindow.
update_thermal_analysis() rebuilt the hot/cold/anomaly QListWidgets and
rebinned the histogram from scratch on EVERY render tick (100+/s),
even though that data only actually changes at the background
ThreadedAnalyzer's own throttled rate (~30Hz) - continuous Qt
widget-rebuild cost for data that hadn't changed since the last push.

Confirmed this was a real, unaddressed cost: thermal_analysis.py's own
update_histogram() docstring already noted "this is called straight
from the render loop" as the reason for an earlier strided-sampling
optimization, without ever gating the call itself.

Fixed with a `results_changed` flag app.py computes by comparing
object identity against the last analysis_results it pushed to the
GUI (safe here since that object is kept alive by a persistent
instance attribute the whole time, unlike the earlier id()-on-a-
freed-array hazard fixed elsewhere this session).

Tests call MainWindow.update_thermal_analysis as an unbound function
against a lightweight stand-in object (not a real, expensive-to-build
QMainWindow) since the method only delegates to sub-widgets.
"""
from unittest.mock import MagicMock

from thermal_inspection.gui.main_window import InspectionAppWindow as MainWindow


class _FakeMainWindow:
    """Bare stand-in exposing only what update_thermal_analysis touches."""

    def __init__(self):
        self.video_widget = MagicMock()
        self.analysis_panel = MagicMock()
        self.anomaly_widget = MagicMock()
        self._update_colorbar = MagicMock()


def _call(fake, **kwargs):
    MainWindow.update_thermal_analysis(fake, **kwargs)


class TestResultsChangedGating:
    def test_results_changed_true_updates_everything(self):
        fake = _FakeMainWindow()
        _call(
            fake, stats="s", hot_spots=["h"], cold_spots=["c"], anomalies=["a"],
            trend="t", temp_array="temps", results_changed=True,
        )
        fake.analysis_panel.update_statistics.assert_called_once_with("s")
        fake.analysis_panel.update_hot_spots.assert_called_once_with(["h"])
        fake.analysis_panel.update_cold_spots.assert_called_once_with(["c"])
        fake.analysis_panel.update_anomalies.assert_called_once_with(["a"])
        fake.analysis_panel.update_trend.assert_called_once_with("t")
        fake.analysis_panel.update_histogram.assert_called_once_with("temps")

    def test_results_unchanged_skips_panel_and_histogram_rebuild(self):
        fake = _FakeMainWindow()
        _call(
            fake, stats="s", hot_spots=["h"], cold_spots=["c"], anomalies=["a"],
            trend="t", temp_array="temps", results_changed=False,
        )
        fake.analysis_panel.update_statistics.assert_not_called()
        fake.analysis_panel.update_hot_spots.assert_not_called()
        fake.analysis_panel.update_cold_spots.assert_not_called()
        fake.analysis_panel.update_anomalies.assert_not_called()
        fake.analysis_panel.update_trend.assert_not_called()
        fake.analysis_panel.update_histogram.assert_not_called()

    def test_video_overlay_always_updates_regardless_of_results_changed(self):
        """Video overlay markers and motion/edge counts must NOT be
        gated - the video itself redraws every tick regardless, and
        motion/edge detection updates independently of the throttled
        analyzer."""
        fake = _FakeMainWindow()
        _call(
            fake, stats="s", hot_spots=["h"], cold_spots=["c"], anomalies=["a"],
            motion_detections=["m"], edge_clusters=["e"], results_changed=False,
        )
        fake.video_widget.update_thermal_detections.assert_called_once_with(["h"], ["c"], ["a"])
        fake.anomaly_widget.update_counts.assert_called_once()
        counts = fake.anomaly_widget.update_counts.call_args[0][0]
        assert counts["motion"] == 1
        assert counts["edges"] == 1

    def test_palette_lut_and_unit_always_update_regardless_of_results_changed(self):
        """These are independent of the analyzer's own cadence (palette
        changes on its own schedule) - must never be gated."""
        fake = _FakeMainWindow()
        _call(
            fake, stats=None, hot_spots=[], cold_spots=[], anomalies=[],
            palette_lut="lut", is_radiometric=True, results_changed=False,
        )
        fake.analysis_panel.set_histogram_palette_lut.assert_called_once_with("lut")
        fake.analysis_panel.set_histogram_temperature_unit.assert_called_once_with("C")

    def test_default_is_true_for_backward_compatibility(self):
        """A caller that doesn't pass results_changed at all must keep
        the old always-update behavior."""
        fake = _FakeMainWindow()
        _call(fake, stats="s", hot_spots=["h"], cold_spots=["c"], anomalies=["a"])
        fake.analysis_panel.update_hot_spots.assert_called_once_with(["h"])


class TestColorbarFeed:
    def test_colorbar_is_fed_every_tick_with_the_results_flag(self):
        fake = _FakeMainWindow()
        _call(fake, stats="s", hot_spots=[], cold_spots=[], anomalies=[], palette_lut="lut",
              temp_array="temps", is_radiometric=True, results_changed=False)
        fake._update_colorbar.assert_called_once_with("lut", "temps", True, False)

