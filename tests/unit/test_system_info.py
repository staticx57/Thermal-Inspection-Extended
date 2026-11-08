"""The machine report and the start-up dependency check: they must identify problems and never break the app."""
import inspect

from thermal_inspection import cli
from thermal_inspection.utils import system_info as si


def test_report_has_every_section_and_never_raises():
    text = si.collect_report(only_linux_sections=True)
    for title in ("System", "Python packages", "Linux access", "Serial ports", "Video devices", "Tau 2 detection"):
        assert f"== {title}" in text


def test_a_failing_section_does_not_stop_the_rest(monkeypatch):
    def boom():
        raise RuntimeError("probe broke")
    monkeypatch.setattr(si, "SECTIONS", [("System", boom), ("Tau 2 detection", lambda: ["still here"])])
    text = si.collect_report(only_linux_sections=False)
    assert "probe broke" in text and "still here" in text


def test_module_state_does_not_import_the_module():
    import sys
    sys.modules.pop("colorsys", None)
    assert si.module_state("colorsys").startswith("ok") and "colorsys" not in sys.modules
    assert si.module_state("definitely_not_a_module_xyz") == "not installed"


def test_preflight_blocks_only_on_hard_requirements(monkeypatch):
    missing = {"cv2", "serial"}
    monkeypatch.setattr(si, "module_state", lambda m: "not installed" if m in missing else "ok 1")
    blocking, warnings = si.preflight()
    assert any("opencv-python" in b for b in blocking)            # hard requirement: stop, with the pip command
    assert not any("pyserial" in b for b in blocking)             # optional-ish: warn only
    assert any("pyserial" in w for w in warnings)


def test_preflight_headless_does_not_need_qt(monkeypatch):
    monkeypatch.setattr(si, "module_state", lambda m: "not installed" if m.startswith(("PyQt6", "pyqtgraph")) else "ok 1")
    assert si.preflight(headless=True)[0] == []
    assert si.preflight(headless=False)[0] != []


def test_preflight_survives_a_broken_check(monkeypatch):
    def boom(_m):
        raise OSError("disk gone")
    monkeypatch.setattr(si, "module_state", boom)
    blocking, warnings = si.preflight()
    assert blocking == [] and any("could not finish" in w for w in warnings)


def test_tau2_keywords_match_the_real_scan():
    from thermal_inspection.sdk import tau2_serial
    source = inspect.getsource(tau2_serial.scan_tau2_ports)
    assert all(f'"{k}"' in source for k in si.TAU2_PORT_KEYWORDS)


def test_cli_system_info_exits_zero(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["thermal_inspection", "--system-info"])
    assert cli.main() == 0
    assert "== System ==" in capsys.readouterr().out


def test_cli_stops_with_a_clear_message_not_a_traceback(monkeypatch, capsys):
    monkeypatch.setattr(si, "preflight", lambda headless=False: (["numpy is not installed -> pip install numpy"], []))
    monkeypatch.setattr("sys.argv", ["thermal_inspection"])
    assert cli.main() == 1
    err = capsys.readouterr().err
    assert "cannot start" in err and "pip install numpy" in err and "--system-info" in err
