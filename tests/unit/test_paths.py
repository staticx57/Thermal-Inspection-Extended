"""Per-user data directory and OS-aware defaults (portability: a fresh machine must not write into a random cwd or
default to a Windows COM port on Linux)."""
import importlib
from pathlib import Path

import pytest

from thermal_inspection.utils import paths


def test_env_override_wins(monkeypatch, tmp_path):
    monkeypatch.setenv(paths.ENV_VAR, str(tmp_path / "home"))
    assert paths.data_dir() == tmp_path / "home"
    assert paths.data_path("config.json") == tmp_path / "home" / "config.json"
    assert paths.data_path(str(tmp_path / "abs.json")) == tmp_path / "abs.json"      # absolute untouched


def test_dev_mode_keeps_the_current_directory(monkeypatch, tmp_path):
    monkeypatch.delenv(paths.ENV_VAR, raising=False)
    monkeypatch.chdir(tmp_path)
    assert paths.data_dir() != tmp_path                                 # empty dir: not dev mode
    (tmp_path / "config.json").write_text("{}")
    assert paths.data_dir() == tmp_path                                 # existing config: keep using it
    other = tmp_path / "checkout"
    (other / "thermal_inspection").mkdir(parents=True)
    (other / "pyproject.toml").write_text("")
    monkeypatch.chdir(other)
    assert paths.data_dir() == other                                    # source checkout


def test_user_data_dir_per_platform(monkeypatch):
    monkeypatch.setattr(paths.platform, "system", lambda: "Linux")
    monkeypatch.setenv("XDG_DATA_HOME", "/xdg")
    assert paths.user_data_dir() == Path("/xdg/thermal-inspection")
    monkeypatch.setattr(paths.platform, "system", lambda: "Windows")
    monkeypatch.setenv("APPDATA", "C:/Users/x/AppData/Roaming")
    assert paths.user_data_dir() == Path("C:/Users/x/AppData/Roaming/ThermalInspection")
    monkeypatch.setattr(paths.platform, "system", lambda: "Darwin")
    assert "Application Support" in str(paths.user_data_dir())


@pytest.mark.parametrize("plat,expected", [("win32", "COM7"), ("linux", "/dev/ttyACM0")])
def test_default_serial_port_is_os_appropriate(monkeypatch, plat, expected):
    monkeypatch.setattr(paths.sys, "platform", plat)
    assert paths.default_serial_port() == expected


def test_fresh_config_lands_in_the_data_dir(monkeypatch, tmp_path):
    from thermal_inspection.utils.config import Config
    monkeypatch.setenv(paths.ENV_VAR, str(tmp_path / "fresh"))
    cfg = Config()
    assert Path(cfg.config_file) == tmp_path / "fresh" / "config.json"
    cfg.set("palette_probe", 1)
    assert (tmp_path / "fresh" / "config.json").exists()


def test_alignment_calibration_and_recordings_follow_the_data_dir(monkeypatch, tmp_path):
    from thermal_inspection.core.alignment_calibration import default_calibration_path
    monkeypatch.setenv(paths.ENV_VAR, str(tmp_path / "h"))
    assert Path(default_calibration_path()) == tmp_path / "h" / "alignment_calibration.json"
    from thermal_inspection.utils.media_recorder import VideoRecorder
    VideoRecorder({"output_path": "recordings/"})
    assert (tmp_path / "h" / "recordings").is_dir()
