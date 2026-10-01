"""
Unit tests for the Camera Plugin Architecture and FLIR Tau2 Driver.
"""
import numpy as np
from unittest.mock import MagicMock

from thermal_inspection.cameras.plugin import (
    CameraPlugin, CameraRole, CameraPluginMatch, CameraCapabilities, CameraSDK,
    CameraPluginRegistry, get_registry,
    CameraPluginHost
)
from thermal_inspection.sdk.tau2_serial import (
    Tau2Serial
)
from thermal_inspection.cameras.tau2_camera import Tau2Camera


class MockThermalPlugin(CameraPlugin):
    @property
    def plugin_id(self) -> str:
        return "mock_thermal"

    @property
    def display_name(self) -> str:
        return "Mock Thermal"

    @property
    def camera_role(self) -> CameraRole:
        return CameraRole.THERMAL

    def detect(self):
        return [CameraPluginMatch(
            plugin_id=self.plugin_id,
            device_index=0,
            com_port="COM9",
            score=100
        )]

    def create_backend(self, match):
        backend = MagicMock()
        backend.open.return_value = True
        backend.is_opened.return_value = True
        backend.read.return_value = (True, np.zeros((512, 640), dtype=np.uint16))
        backend.get_temperature_map.return_value = np.full((512, 640), 25.0, dtype=np.float32)
        return backend

    def create_sdk(self, match):
        sdk = MagicMock(spec=CameraSDK)
        sdk.is_connected.return_value = True
        sdk.execute.side_effect = lambda cmd, params=None: {
            "success": True, "cmd": cmd, "params": params or {}
        }
        return sdk

    def create_control_panel(self):
        return None

    def get_capabilities(self, match):
        return CameraCapabilities(
            bit_depth=16,
            radiometric=True,
            has_ffc=True,
            has_gain_mode=True,
            model="Mock Thermal Model"
        )


def test_plugin_registry():
    """Test registering and discovering camera plugins."""
    registry = CameraPluginRegistry()
    plugin = MockThermalPlugin()

    registry.register(plugin)
    assert registry.get_plugin("mock_thermal") is plugin
    assert "mock_thermal" in registry.list_registered()

    plugins = registry.get_plugins_for_role(CameraRole.THERMAL)
    assert len(plugins) == 1

    matches = registry.discover()
    assert len(matches) == 1
    assert matches[0].plugin_id == "mock_thermal"
    assert matches[0].device_index == 0


def test_plugin_host_lifecycle():
    """Test activating camera and generic command dispatch on host."""
    registry = CameraPluginRegistry()
    plugin = MockThermalPlugin()
    registry.register(plugin)

    host = CameraPluginHost(registry=registry)
    match = plugin.detect()[0]

    # Activate
    ok = host.activate_camera(match)
    assert ok is True
    assert host.is_connected("thermal") is True

    # Read frame
    ret, frame = host.read_thermal()
    assert ret is True
    assert frame.shape == (512, 640)

    # Read temp map
    tmap = host.get_temperature_map()
    assert tmap is not None
    assert tmap[0, 0] == 25.0

    # Generic command execution
    res = host.execute_command("thermal", "ffc", {})
    assert res.get("success") is True
    assert res.get("cmd") == "ffc"

    # Deactivate
    host.deactivate_camera("thermal")
    assert host.is_connected("thermal") is False


class MockDualRolePlugin(CameraPlugin):
    """
    A plugin whose declared camera_role is fixed (like GigEPlugin), but whose
    detected matches can individually be either role via extra['is_thermal']
    — the shape that exposed the _match_is_role bug.
    """

    @property
    def plugin_id(self) -> str:
        return "mock_dual_role"

    @property
    def display_name(self) -> str:
        return "Mock Dual-Role"

    @property
    def camera_role(self) -> CameraRole:
        return CameraRole.RGB  # fixed, like GigEPlugin

    def detect(self):
        return [
            CameraPluginMatch(
                plugin_id=self.plugin_id, device_index=0, score=100,
                extra={"is_thermal": True},
            ),
            CameraPluginMatch(
                plugin_id=self.plugin_id, device_index=1, score=90,
                extra={"is_thermal": False},
            ),
        ]

    def create_backend(self, match):
        backend = MagicMock()
        backend.open.return_value = True
        return backend

    def create_sdk(self, match):
        return None

    def create_control_panel(self):
        return None

    def get_capabilities(self, match):
        return CameraCapabilities()


def test_host_activate_camera_returns_bool_not_exception():
    """
    activate_camera() must never raise for a well-formed match — this is the
    call assign_camera_to_slot() (app.py) depends on downstream of
    registry.discover(), and a regression here previously surfaced as an
    AttributeError several frames away.
    """
    registry = CameraPluginRegistry()
    plugin = MockThermalPlugin()
    registry.register(plugin)
    host = CameraPluginHost(registry=registry)

    match = plugin.detect()[0]
    assert hasattr(match, "device_index"), "CameraPluginMatch must expose device_index"

    ok = host.activate_camera(match)
    assert ok is True


def test_autodiscover_return_value_lacks_device_index():
    """
    Documents the exact type mismatch behind the app.py assign_camera_to_slot
    bug: autodiscover() returns ActiveCamera objects, which have no
    device_index — callers must go through registry.discover() (or
    match.device_index off an ActiveCamera's .match field) to look up a
    device by index, never off autodiscover()'s own return value directly.
    """
    registry = CameraPluginRegistry()
    plugin = MockThermalPlugin()
    registry.register(plugin)
    host = CameraPluginHost(registry=registry)

    activated = host.autodiscover()
    assert len(activated) == 1
    assert not hasattr(activated[0], "device_index")
    assert hasattr(activated[0], "match")
    assert activated[0].match.device_index == 0

    # The fix: raw candidates from the registry DO have device_index.
    matches = host.registry.discover()
    assert all(hasattr(m, "device_index") for m in matches)


def test_match_is_role_respects_per_match_is_thermal_override():
    """
    A plugin whose camera_role is fixed to RGB (like GigEPlugin) must still
    be selectable for the THERMAL role when a specific detected match is
    flagged is_thermal=True — otherwise a real thermal GigE camera can never
    fill the THERMAL slot.
    """
    registry = CameraPluginRegistry()
    plugin = MockDualRolePlugin()
    registry.register(plugin)
    host = CameraPluginHost(registry=registry)

    thermal_match, rgb_match = plugin.detect()

    assert host._match_is_role(thermal_match, CameraRole.THERMAL) is True
    assert host._match_is_role(thermal_match, CameraRole.RGB) is False
    assert host._match_is_role(rgb_match, CameraRole.RGB) is True
    assert host._match_is_role(rgb_match, CameraRole.THERMAL) is False


def test_autodiscover_assigns_thermal_match_to_thermal_role():
    """End-to-end: a dual-role plugin's thermal-flagged match must land in
    the THERMAL slot via autodiscover(), not be silently stuck in RGB."""
    registry = CameraPluginRegistry()
    plugin = MockDualRolePlugin()
    registry.register(plugin)
    host = CameraPluginHost(registry=registry)

    activated = host.autodiscover()
    roles_by_device_index = {a.match.device_index: a for a in activated}

    assert host.is_connected("thermal") is True
    assert roles_by_device_index[0].match.extra["is_thermal"] is True


def test_tau2_crc_calculation():
    """Test CRC-CCITT calculation on Tau2 serial packets."""
    # Process code 0x6E with no args header
    header = bytes([0x6E, 0x00, 0x00, 0x0C, 0x00, 0x00])
    crc = Tau2Serial._calc_crc(header)
    assert isinstance(crc, int)
    assert crc >= 0


def test_tau2_camera_frame_sanitization():
    """
    Test Y16 decoding in Tau2Camera across all three supported byte_order
    values. 'swap' is the default and the one confirmed against real
    hardware (see _decode_byte_swapped's docstring: it turned a
    low-coherence, effectively-blank-looking buffer into a clearly
    recognizable thermal image) - it's a full 16-bit high/low byte swap,
    not a 14-bit clamp, so unlike 'split' its output is not guaranteed
    <= 16383. This previously asserted a >>2 & 0x3FFF bit-packing scheme
    that predates that hardware finding and doesn't match any of the
    three modes _normalize_14bit actually implements.
    """
    raw = np.array([[60000, 40000]], dtype=np.uint16)

    cam_swap = Tau2Camera(device_id=0, resolution=(640, 512), tlinear=True,
                           high_res=True, byte_order='swap')
    swapped = cam_swap._normalize_14bit(raw)
    np.testing.assert_array_equal(swapped, np.array([[24810, 16540]], dtype=np.uint16))

    cam_native = Tau2Camera(device_id=0, resolution=(640, 512), tlinear=True,
                             high_res=True, byte_order='native')
    np.testing.assert_array_equal(cam_native._normalize_14bit(raw), raw)

    cam_split = Tau2Camera(device_id=0, resolution=(640, 512), tlinear=True,
                            high_res=True, byte_order='split')
    split = cam_split._normalize_14bit(raw)
    assert np.all(split <= 16383)


def test_builtin_plugins_auto_registered():
    """Verify built-in plugins register in default registry."""
    reg = get_registry()
    registered_ids = reg.list_registered()
    assert "flir_boson" in registered_ids
    assert "flir_tau2" in registered_ids
    assert "flir_lepton" in registered_ids
    assert "flir_firefly" in registered_ids


def test_app_plugin_host_integration():
    """Test ThermalInspectionApp initialization with CameraPluginHost and mock cameras."""
    from thermal_inspection.app import ThermalInspectionApp, AppConfig

    app = ThermalInspectionApp(AppConfig(headless=True))
    assert app.plugin_host is not None
    assert hasattr(app, "camera_state")
    assert app.camera_state.thermal_connected is False
    assert app.camera_state.rgb_available is False

    # Simulate camera connected event
    app._on_camera_connected("thermal", {"radiometric": True})
    assert app.camera_state.thermal_connected is True
    assert app.camera_state.is_radiometric is True

    # Simulate camera disconnected event
    app._on_camera_disconnected("thermal")
    assert app.camera_state.thermal_connected is False
    assert app.camera_state.is_radiometric is False



class TestLeptonDetection:
    """PureThermal boards are found by name (flirpy's own VID/PID rule), not only by frame size."""

    @staticmethod
    def devices(*specs):
        from thermal_inspection.cameras.device_scanner import VideoDevice
        return [VideoDevice(index=i, name=n, width=w, height=h) for i, (n, w, h) in enumerate(specs)]

    def detect(self, monkeypatch, *specs):
        from thermal_inspection.cameras.plugins.lepton import plugin as lp
        devs = self.devices(*specs)
        monkeypatch.setattr(lp, "scan_video_devices", lambda: devs)
        monkeypatch.setattr(lp, "find_devices_by_resolution",
                            lambda res, tolerance=0: [d for d in devs if d.resolution in res])
        return lp.LeptonPlugin().detect()

    def test_purethermal_with_telemetry_rows_is_found_by_name(self, monkeypatch):
        (m,) = self.detect(monkeypatch, ("PureThermal (fw:v1.3.0)", 160, 122))
        assert m.score == 100 and m.extra["matched_by"] == "name" and m.resolution == (160, 122)

    def test_a_named_board_is_not_listed_twice(self, monkeypatch):
        ms = self.detect(monkeypatch, ("PureThermal (fw:v1.3.0)", 160, 120))
        assert len(ms) == 1 and ms[0].score == 100

    def test_size_only_match_is_kept_as_the_lower_confidence_fallback(self, monkeypatch):
        ms = self.detect(monkeypatch, ("USB Camera", 160, 120), ("Integrated Webcam", 1280, 720))
        assert [(m.device_index, m.score, m.extra["matched_by"]) for m in ms] == [(0, 90, "resolution")]
