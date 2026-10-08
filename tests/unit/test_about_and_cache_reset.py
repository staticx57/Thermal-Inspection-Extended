"""Help > About content and the --reset-camera-cache repair flag."""
from unittest.mock import MagicMock

import pytest

from thermal_inspection import cli
from thermal_inspection.utils import about_info
from thermal_inspection.utils import config as config_module


@pytest.fixture
def cfg(tmp_path, monkeypatch):
    instance = config_module.Config(str(tmp_path / "config.json"))
    monkeypatch.setattr(config_module, "_config_instance", instance)
    return instance


def test_about_lists_version_environment_data_folder_and_features():
    text = about_info.about_html("9.9.9", "C:/data/<x>", packages={"flirpy": True, "open3d": False},
                                 env=["Python 3.12", "Qt 6"])
    assert "Version 9.9.9" in text and "Python 3.12" in text and "Qt 6" in text
    assert "C:/data/&lt;x&gt;" in text                                   # escaped, not rendered as markup
    assert "available" in text and "not installed" in text
    assert "none since the app started" in text


def test_about_shows_recent_camera_problems():
    text = about_info.about_html("1", "d", failures="12:00:01  FLIR Tau 2 (device 2, thermal slot): it would not open\nline2",
                                 packages={}, env=[])
    assert "FLIR Tau 2 (device 2, thermal slot)" in text and "line2" in text and "none since" not in text


def test_about_reports_the_real_environment_without_importing_optional_packages():
    found = about_info.optional_packages()
    assert set(found) == {label for label, _ in about_info.OPTIONAL_PACKAGES}
    assert all(isinstance(v, bool) for v in found.values())
    env = about_info.environment_lines()
    assert env[0].startswith("Python ") and any(line.startswith("OpenCV") for line in env)


def test_help_menu_has_about(qapp):
    from thermal_inspection.gui.main_window import InspectionAppWindow
    w = MagicMock()
    w.app.plugin_host.describe_failures.return_value = ""
    shown = []
    import thermal_inspection.gui.main_window as mw
    mw_about = mw.QMessageBox.about
    mw.QMessageBox.about = staticmethod(lambda parent, title, text: shown.append((title, text)))
    try:
        InspectionAppWindow._show_about(w)
    finally:
        mw.QMessageBox.about = mw_about
    assert shown and shown[0][0] == "About" and "Version" in shown[0][1]


def test_reset_camera_cache_removes_only_the_saved_scan(cfg):
    cfg.set("video_device_cache", {"device_names": ["a"], "devices": []})
    cfg.set("show_status_banner", False)
    assert cli.reset_camera_cache() is True
    reloaded = config_module.Config(cfg.config_file)
    assert reloaded.get("video_device_cache") is None and reloaded.get("show_status_banner") is False


def test_reset_camera_cache_is_harmless_when_there_is_nothing_to_reset(cfg):
    assert cli.reset_camera_cache() is False


def test_flag_runs_the_reset_and_exits_without_starting_the_app(cfg, capsys):
    cfg.set("video_device_cache", {"device_names": ["a"], "devices": []})
    import sys
    argv, sys.argv = sys.argv, ["thermal_inspection", "--reset-camera-cache"]
    try:
        assert cli.main() == 0
    finally:
        sys.argv = argv
    assert "cleared" in capsys.readouterr().out and cfg.get("video_device_cache") is None
