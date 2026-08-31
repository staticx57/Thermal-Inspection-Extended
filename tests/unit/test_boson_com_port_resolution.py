"""
Regression coverage for the Boson COM port auto-detection gap found while
debugging a physically connected camera.

Two bugs, found together:

1. ``scan_boson_ports`` was imported by the plugin's "scan_ports" SDK command
   (thermal_inspection/cameras/plugins/boson/plugin.py) from
   thermal_inspection.sdk.boson_serial, but the function didn't exist there
   — only the underlying BosonSerialInterface.find_boson_com_ports()
   staticmethod did. Triggering that GUI action would have raised
   ImportError. No test imported boson_serial at all, so this was invisible.

2. BosonPlugin.detect() hardcoded the serial control port to a configured
   default (COM7) rather than ever using find_boson_com_ports() to find the
   camera's actual port. The video (UVC) and control (CCI/serial) interfaces
   enumerate as separate Windows devices with independent port assignment —
   on the machine this was debugged on, the real port was COM6. SDK-based
   features (FFC, AGC, palette control) would silently fail to connect on
   any machine where the real port isn't COM7, with no indication why.
"""
from unittest.mock import MagicMock

from thermal_inspection.sdk.boson_serial import scan_boson_ports, BosonSerialInterface
from thermal_inspection.cameras.plugins.boson.plugin import BosonPlugin


def test_scan_boson_ports_is_importable_and_callable():
    # The regression itself: this import used to raise ImportError.
    ports = scan_boson_ports()
    assert isinstance(ports, list)


def test_scan_boson_ports_wraps_find_boson_com_ports(monkeypatch):
    monkeypatch.setattr(
        BosonSerialInterface, "find_boson_com_ports", staticmethod(lambda: ["COM6"])
    )
    assert scan_boson_ports() == ["COM6"]


class TestBosonPluginComPortResolution:

    def test_prefers_scanned_port_over_hardcoded_default(self, monkeypatch):
        # _resolve_com_port imports get_config locally at call time, so the
        # patch target is the source module, not the plugin module.
        monkeypatch.setattr(
            "thermal_inspection.utils.config.get_config",
            lambda: MagicMock(get=lambda key, default=None: default),
        )
        monkeypatch.setattr(
            "thermal_inspection.sdk.boson_serial.scan_boson_ports", lambda: ["COM6"]
        )

        plugin = BosonPlugin()
        assert plugin._resolve_com_port() == "COM6"

    def test_explicit_user_override_wins_over_scan(self, monkeypatch):
        monkeypatch.setattr(
            "thermal_inspection.utils.config.get_config",
            lambda: MagicMock(get=lambda key, default=None: "COM9" if key == "sdk_com_port" else default),
        )
        monkeypatch.setattr(
            "thermal_inspection.sdk.boson_serial.scan_boson_ports", lambda: ["COM6"]
        )

        plugin = BosonPlugin()
        assert plugin._resolve_com_port() == "COM9"

    def test_falls_back_to_default_when_scan_finds_nothing(self, monkeypatch):
        # _resolve_com_port imports get_config locally at call time, so the
        # patch target is the source module, not the plugin module.
        monkeypatch.setattr(
            "thermal_inspection.utils.config.get_config",
            lambda: MagicMock(get=lambda key, default=None: default),
        )
        monkeypatch.setattr(
            "thermal_inspection.sdk.boson_serial.scan_boson_ports", lambda: []
        )

        plugin = BosonPlugin()
        assert plugin._resolve_com_port() == "COM7"

    def test_falls_back_to_default_when_scan_raises(self, monkeypatch):
        # _resolve_com_port imports get_config locally at call time, so the
        # patch target is the source module, not the plugin module.
        monkeypatch.setattr(
            "thermal_inspection.utils.config.get_config",
            lambda: MagicMock(get=lambda key, default=None: default),
        )

        def _raise():
            raise RuntimeError("no serial support in this environment")

        monkeypatch.setattr(
            "thermal_inspection.sdk.boson_serial.scan_boson_ports", _raise
        )

        plugin = BosonPlugin()
        assert plugin._resolve_com_port() == "COM7"
