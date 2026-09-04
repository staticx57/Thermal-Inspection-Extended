"""
Unit tests for utils/profiling.py - the shared [PROFILE_*] print helper
that replaced 12 independently hand-rolled print sites across app.py and
fusion_3d_panel.py (see Medium #1 in the debt ledger). Covers the
formatting contract and the THERMAL_PROFILE on/off switch.
"""
import importlib

import pytest


@pytest.mark.unit
def test_profile_log_formats_tag_and_fields(capsys):
    from thermal_inspection.utils import profiling
    profiling.profile_log("PARALLAX", target="thermal", depth_ms="1.23")
    out = capsys.readouterr().out
    assert out == "[PROFILE_PARALLAX] target=thermal depth_ms=1.23\n"


@pytest.mark.unit
def test_profile_log_silenced_by_env_var(monkeypatch, capsys):
    monkeypatch.setenv("THERMAL_PROFILE", "0")
    from thermal_inspection.utils import profiling
    importlib.reload(profiling)
    try:
        profiling.profile_log("PARALLAX", target="thermal")
        assert capsys.readouterr().out == ""
    finally:
        monkeypatch.delenv("THERMAL_PROFILE", raising=False)
        importlib.reload(profiling)  # restore default-on state for later tests


@pytest.mark.unit
def test_profile_log_enabled_by_default(monkeypatch, capsys):
    monkeypatch.delenv("THERMAL_PROFILE", raising=False)
    from thermal_inspection.utils import profiling
    importlib.reload(profiling)
    profiling.profile_log("PARALLAX", target="thermal")
    assert capsys.readouterr().out != ""
