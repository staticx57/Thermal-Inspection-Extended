"""A camera that cannot be opened must say why, in words a user can act on - not only in the (WARNING-only) log."""
import time
from unittest.mock import MagicMock

from thermal_inspection.cameras.plugin import CameraPluginHost, CameraPluginRegistry, CameraPluginMatch
from thermal_inspection.cameras.plugin import camera_plugin_host as host_module
from tests.unit.test_camera_plugin_system import MockThermalPlugin


def _host(open_behaviour):
    class Plugin(MockThermalPlugin):
        def create_backend(self, match):
            backend = MagicMock()
            if callable(open_behaviour):
                backend.open.side_effect = open_behaviour
            else:
                backend.open.return_value = open_behaviour
            return backend

    registry = CameraPluginRegistry()
    plugin = Plugin()
    registry.register(plugin)
    host = CameraPluginHost(registry=registry)
    seen = []
    host.camera_open_failed.connect(lambda role, name, reason: seen.append((role, name, reason)))
    return host, plugin.detect()[0], seen


def test_a_refused_open_says_the_device_may_be_busy_or_missing(qapp):
    host, match, seen = _host(False)
    assert host.activate_camera(match) is False
    role, name, reason = seen[0]
    assert (role, name) == ("thermal", "Mock Thermal")
    assert "in use by another program" in reason and "driver" in reason


def test_a_driver_exception_is_quoted(qapp):
    def boom():
        raise OSError("device is busy (0x80070020)")
    host, match, seen = _host(boom)
    assert host.activate_camera(match) is False
    assert "the driver reported: device is busy (0x80070020)" in seen[0][2]


def test_a_hung_open_reports_the_timeout(qapp, monkeypatch):
    monkeypatch.setattr(host_module, "BACKEND_OPEN_TIMEOUT_S", 0.2)
    host, match, seen = _host(lambda: time.sleep(1.0) or True)
    assert host.activate_camera(match) is False
    assert "did not open within 0 s" in seen[0][2] and "holding the device" in seen[0][2]


def test_an_unknown_plugin_is_reported(qapp):
    host, match, seen = _host(True)
    bad = CameraPluginMatch(plugin_id="no_such_plugin", device_index=3)
    assert host.activate_camera("thermal", bad) is False
    assert seen and seen[0][1] == "no_such_plugin" and "no driver plugin" in seen[0][2]


def test_failures_are_kept_for_a_why_isnt_my_camera_working_readout(qapp):
    host, match, _ = _host(False)
    host.activate_camera(match)
    host.activate_camera(match)
    text = host.describe_failures()
    assert text.count("Mock Thermal (device 0, thermal slot)") == 2
    assert len(host.failure_log) == 2


def test_success_records_nothing(qapp):
    host, match, seen = _host(True)
    assert host.activate_camera(match) is True
    assert seen == [] and host.describe_failures() == ""


def test_the_window_shows_the_reason_in_a_banner():
    from thermal_inspection.gui.main_window import InspectionAppWindow
    w = MagicMock()
    InspectionAppWindow._on_bus_camera_open_failed(w, "thermal", "FLIR Tau 2", "the device would not open")
    msg = w._show_hotplug_banner.call_args[0][0]
    assert "FLIR Tau 2" in msg and "Thermal slot" in msg and "would not open" in msg
    assert w._show_hotplug_banner.call_args[1]["warning"] is True
