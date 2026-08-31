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


def test_tau2_crc_calculation():
    """Test CRC-CCITT calculation on Tau2 serial packets."""
    # Process code 0x6E with no args header
    header = bytes([0x6E, 0x00, 0x00, 0x0C, 0x00, 0x00])
    crc = Tau2Serial._calc_crc(header)
    assert isinstance(crc, int)
    assert crc >= 0


def test_tau2_camera_frame_sanitization():
    """Test 14-bit alignment and Y16 normalization in Tau2Camera."""
    cam = Tau2Camera(device_id=0, resolution=(640, 512), tlinear=True, high_res=True)

    # Left-shifted 14-bit data (raw values > 16383)
    raw = np.array([[60000, 40000]], dtype=np.uint16)
    normalized = cam._normalize_14bit(raw)
    assert np.all(normalized <= 16383)
    assert normalized[0, 0] == (60000 >> 2) & 0x3FFF


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

