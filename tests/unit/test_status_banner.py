"""The status banner (FPS / ROIs / connections) shows camera rate AND loop speed, and can be switched off."""
from unittest.mock import MagicMock

import pytest

from thermal_inspection.utils import config as config_module
from thermal_inspection.gui.main_window import InspectionAppWindow
from thermal_inspection.gui.widgets.info_panel import InfoPanel


@pytest.fixture
def cfg(tmp_path, monkeypatch):
    instance = config_module.Config(str(tmp_path / "config.json"))
    monkeypatch.setattr(config_module, "_config_instance", instance)
    return instance


def test_banner_shows_the_camera_rate_and_the_loop_speed(qapp):
    p = InfoPanel()
    p.update_info(59.9, 2, True, True, False, 312.4)
    assert "FPS: 59.9" in p.text() and "Loop: 312" in p.text()


def test_the_camera_rate_stays_when_there_is_no_loop_figure(qapp):
    p = InfoPanel()
    p.update_info(9.0, 0, True, False)
    assert "FPS: 9.0" in p.text() and "Loop" not in p.text()


def test_the_banner_explains_the_two_numbers(qapp):
    tip = InfoPanel().toolTip()
    assert "camera" in tip and "loop" in tip.lower()


def test_window_passes_both_rates_to_the_banner():
    w = MagicMock()
    w.recording = False
    InspectionAppWindow.update_metrics(w, 30.0, 1, True, True, loop_fps=250.0)
    assert w.info_panel.update_info.call_args[0][-1] == 250.0
    assert w.info_panel.update_info.call_args[0][0] == 30.0


def test_toggle_hides_and_shows_the_banner_and_remembers_it(qapp, cfg):
    w = MagicMock()
    w.info_panel = InfoPanel()
    w.info_panel.show()
    InspectionAppWindow._on_show_status_banner_toggled(w, False)
    assert w.info_panel.isHidden() and cfg.get("show_status_banner") is False
    InspectionAppWindow._on_show_status_banner_toggled(w, True)
    assert not w.info_panel.isHidden() and cfg.get("show_status_banner") is True


def test_saved_choice_is_applied_at_startup_without_re_saving(qapp, cfg):
    from thermal_inspection.gui.panels.thermal_analysis import ThermalAnalysisPanel
    cfg.set("show_status_banner", False)
    w = MagicMock()
    w.info_panel = InfoPanel()
    w.info_panel.show()
    w.analysis_panel = ThermalAnalysisPanel()
    InspectionAppWindow._restore_status_banner(w)
    assert w.info_panel.isHidden()
    assert not w.analysis_panel.show_status_banner_checkbox.isChecked()


def test_banner_is_shown_by_default(qapp, cfg):
    w = MagicMock()
    w.info_panel = InfoPanel()
    w.analysis_panel = None
    InspectionAppWindow._restore_status_banner(w)
    assert not w.info_panel.isHidden()                                   # never force-hidden by default
    assert cfg.get("show_status_banner", True) is True


def test_checkbox_emits_the_toggle(qapp):
    from thermal_inspection.gui.panels.thermal_analysis import ThermalAnalysisPanel
    panel = ThermalAnalysisPanel()
    got = []
    panel.show_status_banner_toggled.connect(got.append)
    assert panel.show_status_banner_checkbox.isChecked()
    panel.show_status_banner_checkbox.setChecked(False)
    assert got == [False]
