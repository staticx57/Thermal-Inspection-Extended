"""MainWindow handlers behind the ROI Manager panel."""
from unittest.mock import MagicMock

import pytest
from PyQt6.QtWidgets import QFileDialog, QMessageBox

from thermal_inspection.gui.main_window import InspectionAppWindow as MainWindow


class _Win:
    def __init__(self):
        self.app = MagicMock()
        self.roi_temp_panel = MagicMock()
        self._sb = MagicMock()
        self.statusBar = lambda: self._sb


def test_actions_route_through_the_controller():
    w = _Win()
    MainWindow._roi_action(w, "rename_roi", "r1", "Busbar")
    MainWindow._roi_action(w, "set_roi_locked", "r1", True)
    w.app.roi_controller.rename_roi.assert_called_once_with("r1", "Busbar")
    w.app.roi_controller.set_roi_locked.assert_called_once_with("r1", True)
    w.app = MagicMock(spec=[])                               # no controller yet: must not raise
    MainWindow._roi_action(w, "rename_roi", "r1", "x")


def test_alert_goes_to_the_status_bar():
    w = _Win()
    MainWindow._on_roi_alert_triggered(w, "r1", "ROI alert: Panel A - Hottest pixel > 80 °C")
    w._sb.showMessage.assert_called_once()
    assert "Panel A" in w._sb.showMessage.call_args[0][0]


def test_update_rois_gives_the_panel_hidden_rois_too():
    w = _Win()
    w.video_widget, w.analysis_panel = MagicMock(), MagicMock()
    MainWindow.update_rois(w, ["visible"], ["visible", "hidden"])
    w.video_widget.update_rois.assert_called_once_with(["visible"])          # drawn: visible only
    w.roi_temp_panel.update_rois.assert_called_once_with(["visible", "hidden"])
    w2 = _Win()
    w2.video_widget, w2.analysis_panel = MagicMock(), MagicMock()
    MainWindow.update_rois(w2, ["only"])                                      # old call shape still works
    w2.roi_temp_panel.update_rois.assert_called_once_with(["only"])


def test_export_appends_extension_and_reports_errors(monkeypatch, tmp_path):
    w = _Win()
    target = str(tmp_path / "out")
    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (target, "JSON Files (*.json)")))
    MainWindow._on_roi_export_data(w)
    w.roi_temp_panel.export_data.assert_called_once_with(target + ".json")
    assert "exported" in w._sb.showMessage.call_args[0][0]

    w2 = _Win()
    w2.roi_temp_panel.export_data.side_effect = ValueError("No ROIs to export")
    MainWindow._on_roi_export_data(w2)
    assert "No ROIs to export" in w2._sb.showMessage.call_args[0][0]          # reported, not raised

    w3 = _Win()
    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: ("", "")))
    MainWindow._on_roi_export_data(w3)                                        # cancelled
    w3.roi_temp_panel.export_data.assert_not_called()


def test_save_set_needs_rois_and_load_set_confirms_replacement(monkeypatch, tmp_path):
    w = _Win()
    w.app.roi_controller.all_rois = []
    MainWindow._on_roi_save_set(w)
    w.app.roi_controller.save_rois.assert_not_called()
    assert "No ROIs" in w._sb.showMessage.call_args[0][0]

    w.app.roi_controller.all_rois = ["a", "b"]
    f = str(tmp_path / "set.json")
    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (f, "")))
    w.app.roi_controller.save_rois.return_value = True
    MainWindow._on_roi_save_set(w)
    w.app.roi_controller.save_rois.assert_called_once_with(f)

    monkeypatch.setattr(QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: (f, "")))
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.No))
    MainWindow._on_roi_load_set(w)
    w.app.roi_controller.load_rois.assert_not_called()                        # user said no to replacing 2 ROIs
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes))
    w.app.roi_controller.load_rois.return_value = True
    MainWindow._on_roi_load_set(w)
    w.app.roi_controller.load_rois.assert_called_once_with(f)
