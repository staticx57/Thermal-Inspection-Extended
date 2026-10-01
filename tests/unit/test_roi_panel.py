"""ROI Manager panel: table content, selection-driven actions, alerts, comparison, export, history."""
import csv

import pytest
from PyQt6.QtWidgets import QApplication, QMessageBox

from thermal_inspection.gui.panels import roi_temperature_panel as rp
from thermal_inspection.processing.roi_manager import ROIManager
from thermal_inspection.processing.roi_tracking import ROIAlert


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def stats(avg, lo, hi, unit="°C", pixels=500, frame=10000):
    return {"temp_avg": avg, "temp_min": lo, "temp_max": hi, "temp_std": 1.0, "pixel_count": pixels,
            "frame_pixels": frame, "unit": unit}


@pytest.fixture
def setup(qapp, monkeypatch):
    mgr = ROIManager()
    a = mgr.create_rectangle_roi(0, 0, 10, 10, label="Panel A")
    b = mgr.create_rectangle_roi(20, 20, 10, 10, label="Panel B")
    panel = rp.ROITemperaturePanel()
    panel.update_rois(mgr.get_all_rois(active_only=False))
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes)
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: None)
    monkeypatch.setattr(QApplication, "beep", staticmethod(lambda: None))
    return mgr, panel, a, b


def select(panel, *ids):
    panel.table.clearSelection()
    for i in ids:
        for row in range(panel.table.rowCount()):
            if panel.table.item(row, rp.COL_NAME).data(0x100) == i:
                panel.table.selectRow(row)
    # selectRow replaces the selection unless extended: use the model API for multi-select
    if len(ids) > 1:
        from PyQt6.QtCore import QItemSelectionModel
        panel.table.clearSelection()
        for row in range(panel.table.rowCount()):
            if panel.table.item(row, rp.COL_NAME).data(0x100) in ids:
                panel.table.selectionModel().select(
                    panel.table.model().index(row, 0),
                    QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows)


class TestTable:
    def test_lists_every_roi_including_hidden_with_markers(self, setup):
        mgr, panel, a, b = setup
        mgr.set_locked(a.roi_id, True)
        mgr.set_visible(b.roi_id, False)
        panel.update_rois(mgr.get_all_rois(active_only=False))
        assert panel.table.rowCount() == 2
        name_a, name_b = panel.table.item(0, rp.COL_NAME).text(), panel.table.item(1, rp.COL_NAME).text()
        assert "🔒" in name_a and "Panel A" in name_a
        assert "(hidden)" in name_b

    def test_readings_trend_peak_area_and_hottest(self, setup):
        mgr, panel, a, b = setup
        for i in range(10):
            panel.update_roi_data({a.roi_id: stats(40 + (5 if i >= 5 else 0), 30, 60 + i),
                                   b.roi_id: stats(30, 20, 50)})
        row = lambda r: [panel.table.item(r, c).text() for c in range(panel.table.columnCount())]   # noqa: E731
        ra, rb = row(0), row(1)
        assert ra[rp.COL_AVG] == "45.0 °C" and ra[rp.COL_MAX] == "69.0 °C" and ra[rp.COL_PEAK] == "69.0 °C"
        assert ra[rp.COL_TREND] == "▲" and rb[rp.COL_TREND] == "–"
        assert ra[rp.COL_AREA] == "500 px (5.0%)"
        assert panel.table.item(0, rp.COL_MAX).font().bold() and not panel.table.item(1, rp.COL_MAX).font().bold()
        assert "hottest: Panel A at 69.0 °C" in panel.stats_label.text()

    def test_peak_hold_survives_cooling(self, setup):
        mgr, panel, a, b = setup
        panel.update_roi_data({a.roi_id: stats(40, 30, 90)})
        panel.update_roi_data({a.roi_id: stats(40, 30, 55)})
        assert panel.table.item(0, rp.COL_MAX).text() == "55.0 °C"
        assert panel.table.item(0, rp.COL_PEAK).text() == "90.0 °C"

    def test_unmeasured_roi_shows_dashes_not_stale_numbers(self, setup):
        mgr, panel, a, b = setup
        panel.update_roi_data({a.roi_id: stats(40, 30, 60), b.roi_id: stats(30, 20, 50)})
        panel.update_roi_data({a.roi_id: stats(41, 31, 61)})                  # b dropped out of the push
        assert panel.table.item(1, rp.COL_AVG).text() == "-" and panel.table.item(1, rp.COL_TREND).text() == ""
        assert panel.table.item(1, rp.COL_PEAK).text() == "50.0 °C"           # but its peak is remembered

    def test_selection_is_kept_across_a_rebuild(self, setup):
        mgr, panel, a, b = setup
        select(panel, b.roi_id)
        mgr.rename_roi(b.roi_id, "Renamed")
        panel.update_rois(mgr.get_all_rois(active_only=False))
        assert panel.selected_ids() == [b.roi_id]
        assert "Renamed" in panel.table.item(1, rp.COL_NAME).text()

    def test_estimated_readings_get_a_tilde(self, setup):
        mgr, panel, a, b = setup
        panel.update_roi_data({a.roi_id: stats(40, 30, 60, unit="°C (est)")})
        assert panel.table.item(0, rp.COL_AVG).text() == "~40.0 °C"


class TestActions:
    def test_buttons_follow_selection_and_state(self, setup):
        mgr, panel, a, b = setup
        assert not panel.rename_btn.isEnabled() and not panel.roi_delete_btn.isEnabled()
        select(panel, a.roi_id)
        assert panel.rename_btn.isEnabled() and panel.lock_btn.text() == "Lock" and panel.visible_btn.text() == "Hide"
        mgr.set_locked(a.roi_id, True)
        mgr.set_visible(a.roi_id, False)
        panel.update_rois(mgr.get_all_rois(active_only=False))
        select(panel, a.roi_id)
        assert panel.lock_btn.text() == "Unlock" and panel.visible_btn.text() == "Show"
        select(panel, a.roi_id, b.roi_id)
        assert not panel.rename_btn.isEnabled()                               # rename is one ROI at a time

    def test_lock_hide_duplicate_emit_per_selected_roi(self, setup):
        mgr, panel, a, b = setup
        got = {"lock": [], "vis": [], "dup": []}
        panel.roi_lock_changed.connect(lambda i, on: got["lock"].append((i, on)))
        panel.roi_visibility_changed.connect(lambda i, on: got["vis"].append((i, on)))
        panel.roi_duplicate_requested.connect(got["dup"].append)
        select(panel, a.roi_id, b.roi_id)
        panel.lock_btn.click()
        panel.visible_btn.click()
        panel.duplicate_btn.click()
        assert sorted(got["lock"]) == sorted([(a.roi_id, True), (b.roi_id, True)])
        assert sorted(got["vis"]) == sorted([(a.roi_id, False), (b.roi_id, False)])
        assert sorted(got["dup"]) == sorted([a.roi_id, b.roi_id])

    def test_delete_skips_locked_rois(self, setup):
        mgr, panel, a, b = setup
        mgr.set_locked(a.roi_id, True)
        panel.update_rois(mgr.get_all_rois(active_only=False))
        deleted = []
        panel.roi_deleted.connect(deleted.append)
        select(panel, a.roi_id, b.roi_id)
        panel.roi_delete_btn.click()
        assert deleted == [b.roi_id]
        deleted.clear()
        panel.roi_delete_all_btn.click()
        assert deleted == [b.roi_id]                                          # Delete All also keeps locked ROIs

    def test_rename_emits_new_name_and_refuses_locked(self, setup, monkeypatch):
        mgr, panel, a, b = setup
        names = []
        panel.roi_renamed.connect(lambda i, n: names.append((i, n)))
        monkeypatch.setattr(rp.QInputDialog, "getText", staticmethod(lambda *a, **k: ("  Busbar  ", True)))
        select(panel, a.roi_id)
        panel.rename_btn.click()
        assert names == [(a.roi_id, "Busbar")]
        mgr.set_locked(a.roi_id, True)
        panel.update_rois(mgr.get_all_rois(active_only=False))
        select(panel, a.roi_id)
        panel.rename_btn.click()
        assert len(names) == 1                                                # locked: shows a message, emits nothing


class TestAlerts:
    def test_alert_fires_signal_once_tints_row_and_summarises(self, setup):
        mgr, panel, a, b = setup
        fired = []
        panel.roi_alert_triggered.connect(lambda i, t: fired.append((i, t)))
        panel.apply_alert([a.roi_id], ROIAlert(threshold=80, metric="max"))
        assert "Hottest pixel > 80 °C" in panel.table.item(0, rp.COL_ALERT).text()
        panel.update_roi_data({a.roi_id: stats(40, 30, 70)})
        assert fired == []
        panel.update_roi_data({a.roi_id: stats(40, 30, 85)})
        panel.update_roi_data({a.roi_id: stats(40, 30, 90)})
        assert len(fired) == 1 and fired[0][0] == a.roi_id and "Panel A" in fired[0][1]
        assert panel.table.item(0, rp.COL_ALERT).text().startswith("⚠")
        assert panel.table.item(0, rp.COL_ALERT).background().color().alpha() > 0
        assert "1 alert firing" in panel.stats_label.text()

    def test_alert_survives_a_saved_roi_set_via_metadata(self, setup, qapp):
        mgr, panel, a, b = setup
        panel.apply_alert([a.roi_id], ROIAlert(threshold=55, metric="avg", type="below", sound_enabled=False))
        # round-trip the ROI through its JSON form (what Save/Load ROI Set does)
        from thermal_inspection.processing.roi_manager import ROI
        restored = ROI.from_dict(a.to_dict())
        fresh = rp.ROITemperaturePanel()
        fresh.update_rois([restored])
        al = fresh.tracker.alert(restored.roi_id)
        assert al is not None and (al.threshold, al.metric, al.type, al.sound_enabled) == (55, "avg", "below", False)
        assert not al.triggered and al.trigger_count == 0                    # runtime state is not persisted

    def test_remove_alert(self, setup):
        mgr, panel, a, b = setup
        panel.apply_alert([a.roi_id], ROIAlert(threshold=1))
        panel.apply_alert([a.roi_id], None)
        assert panel.tracker.alert(a.roi_id) is None and "alert" not in a.metadata
        assert panel.table.item(0, rp.COL_ALERT).text() == ""

    def test_same_alert_applied_to_several_rois_is_independent(self, setup):
        mgr, panel, a, b = setup
        panel.apply_alert([a.roi_id, b.roi_id], ROIAlert(threshold=50))
        panel.update_roi_data({a.roi_id: stats(1, 1, 60), b.roi_id: stats(1, 1, 40)})
        assert panel.tracker.alert(a.roi_id).triggered and not panel.tracker.alert(b.roi_id).triggered


class TestCompareExportHistory:
    def test_compare_two_selected(self, setup):
        mgr, panel, a, b = setup
        panel.update_roi_data({a.roi_id: stats(20, 10, 30), b.roi_id: stats(26, 12, 41)})
        select(panel, a.roi_id, b.roi_id)
        assert panel.compare_label.text() == "Panel B − Panel A:  avg +6.0 °C   max +11.0 °C   min +2.0 °C"
        select(panel, a.roi_id)
        assert panel.compare_label.text() == ""

    def test_export_csv_and_clear_history(self, setup, tmp_path):
        mgr, panel, a, b = setup
        panel.update_roi_data({a.roi_id: stats(40, 30, 90)})
        path = str(tmp_path / "rois.csv")
        panel.export_data(path)
        with open(path, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        assert [r["name"] for r in rows] == ["Panel A", "Panel B"] and float(rows[0]["peak_max"]) == 90.0
        panel.clear_roi_history("all")
        assert panel.table.item(0, rp.COL_PEAK).text() == "-"
        assert not panel.clear_btn.isEnabled()

    def test_export_with_no_rois_raises_for_the_window_to_report(self, qapp, tmp_path):
        with pytest.raises(ValueError):
            rp.ROITemperaturePanel().export_data(str(tmp_path / "x.csv"))

    def test_history_graph_toggle_builds_lazily(self, setup):
        mgr, panel, a, b = setup
        assert panel._graph is None
        panel.update_roi_data({a.roi_id: stats(40, 30, 90)})
        panel.graph_check.setChecked(True)
        assert panel._graph is not None
        panel.update_roi_data({a.roi_id: stats(41, 30, 91)})                   # updating with a graph open must not raise
        panel.graph_check.setChecked(False)
        assert panel._graph.isHidden()

    def test_save_and_load_set_buttons_emit(self, setup):
        mgr, panel, a, b = setup
        got = []
        panel.save_set_requested.connect(lambda: got.append("save"))
        panel.load_set_requested.connect(lambda: got.append("load"))
        panel.save_set_btn.click()
        panel.load_set_btn.click()
        assert got == ["save", "load"]


class TestSelectFromTheVideo:
    def test_select_roi_selects_the_row_and_reports_missing(self, setup):
        mgr, panel, a, b = setup
        assert panel.select_roi(b.roi_id)
        assert panel.selected_ids() == [b.roi_id]
        assert panel.select_roi(a.roi_id) and panel.selected_ids() == [a.roi_id]       # replaces, not adds
        assert not panel.select_roi("nope") and panel.selected_ids() == [a.roi_id]

    def test_selection_enables_the_row_actions(self, setup):
        mgr, panel, a, b = setup
        assert not panel.rename_btn.isEnabled()
        panel.select_roi(a.roi_id)
        assert panel.rename_btn.isEnabled()
