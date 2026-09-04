"""
Unit tests for SettingsManager.save() - had zero prior test coverage.
Covers a narrow atomic-write gap found during a general best-practices
audit (2026-09-03): on Windows, save() used to unlink() the destination
file and then rename() the temp file as two separate steps (worked
around because Path.rename() doesn't overwrite on Windows) - a crash
between those two lines would leave no config file at all. Switched to
os.replace(), which is atomic and overwrites on both platforms.
"""
import json

import pytest

from thermal_inspection.utils.settings_manager import SettingsManager


def _make_manager(tmp_path):
    return SettingsManager(
        config_file=str(tmp_path / "config.json"),
        schema_file=str(tmp_path / "nonexistent_schema.json"),  # falls back to built-in defaults
    )


@pytest.mark.unit
class TestSettingsManagerSave:

    def test_save_produces_valid_json_matching_current_settings(self, tmp_path):
        manager = _make_manager(tmp_path)
        manager._settings["camera.thermal.width"] = 800

        assert manager.save() is True

        saved = json.loads((tmp_path / "config.json").read_text(encoding="utf-8"))
        assert saved["camera.thermal.width"] == 800

    def test_save_overwrites_an_existing_file(self, tmp_path):
        """The exact case the old unlink()-then-rename() dance was
        working around on Windows - save() must succeed even when the
        destination already exists."""
        config_path = tmp_path / "config.json"
        config_path.write_text('{"stale": true}', encoding="utf-8")

        manager = _make_manager(tmp_path)
        manager._settings = {"fresh": True}

        assert manager.save() is True
        saved = json.loads(config_path.read_text(encoding="utf-8"))
        assert saved == {"fresh": True}

    def test_save_leaves_no_stray_temp_file(self, tmp_path):
        manager = _make_manager(tmp_path)
        manager.save()
        assert not (tmp_path / "config.tmp").exists()
