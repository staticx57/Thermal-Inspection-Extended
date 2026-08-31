"""
Unit tests for Generic UVC Webcam plugin and GigE Vision / GVCP integration.
"""
import pytest
import struct
from unittest.mock import MagicMock, patch

from thermal_inspection.cameras.plugin import get_registry, CameraRole, CameraPluginMatch
from thermal_inspection.cameras.plugins.uvc.plugin import UVCPlugin, UVCCameraSDK
from thermal_inspection.cameras.plugins.gige.plugin import GigECameraSDK
from thermal_inspection.sdk.gige.gvcp import (
    GVCPProtocol, CMD_DISCOVERY_ACK, discover_gige_cameras
)
from thermal_inspection.cameras.gige_camera import GigECamera
from thermal_inspection.cameras.gige_backend import GigEBackend


class TestUVCPlugin:
    def test_uvc_plugin_registration(self):
        registry = get_registry()
        plugin = registry.get_plugin("generic_uvc")
        assert plugin is not None
        assert plugin.display_name == "USB Webcam"
        assert plugin.camera_role == CameraRole.RGB

    def test_uvc_capabilities(self):
        plugin = UVCPlugin()
        match = CameraPluginMatch(plugin_id="generic_uvc", device_index=0, name="Logitech BRIO", resolution=(640, 480))
        caps = plugin.get_capabilities(match)
        assert caps.bit_depth == 8
        assert caps.radiometric is False
        assert (1920, 1080) in caps.resolutions
        assert caps.has_exposure_control is True

    def test_uvc_sdk_execution(self):
        mock_cam = MagicMock()
        mock_cam.is_opened.return_value = True
        mock_cam.cap = MagicMock()
        mock_cam.cap.get.side_effect = lambda prop: 640 if prop == 3 else 480
        mock_cam.cap.set.return_value = True

        sdk = UVCCameraSDK(camera_obj=mock_cam)
        assert sdk.is_connected() is True

        res = sdk.execute("set_property", {"property": "brightness", "value": 150})
        assert res.get("success") is True

        res = sdk.execute("set_resolution", {"width": 1280, "height": 720})
        assert res.get("success") is True

        res = sdk.execute("set_auto_exposure", {"enabled": True})
        assert res.get("success") is True

        res = sdk.execute("get_camera_info")
        assert res.get("success") is True
        assert "resolution" in res


class TestGVCPProtocol:
    def test_gvcp_discovery_ack_parser(self):
        protocol = GVCPProtocol()

        # Construct a synthetic DISCOVERY_ACK packet (8B header + 216B payload)
        header = struct.pack(">HHHH", 0x0000, CMD_DISCOVERY_ACK, 216, 1)

        # Payload:
        # 0..8: Spec major/minor, DeviceMode
        # 8..14: MAC Address (00:11:22:33:44:55)
        # 14..24: IP Config
        # 24..36: IP, Subnet, Gateway
        # 36..68: Manufacturer ("FLIR Systems")
        # 68..100: Model ("A35")
        # 100..132: Version ("1.0")
        # 132..180: Specific
        # 180..196: Serial ("SN-12345")
        # 196..212: User Name ("InspectCam")

        payload = b'\x00' * 8
        payload += bytes.fromhex("001122334455")
        payload += b'\x00' * 10
        payload += struct.pack(">III", 0xC0A80164, 0xFFFFFF00, 0xC0A80101)  # 192.168.1.100, 255.255.255.0, 192.168.1.1
        payload += b"FLIR Systems".ljust(32, b'\x00')
        payload += b"FLIR A35".ljust(32, b'\x00')
        payload += b"v1.2".ljust(32, b'\x00')
        payload += b'\x00' * 48
        payload += b"72001-0101".ljust(16, b'\x00')
        payload += b"ThermalSensor1".ljust(16, b'\x00')
        payload += b'\x00' * 10

        packet = header + payload
        dev = protocol._parse_discovery_ack(packet, "192.168.1.100")

        assert dev is not None
        assert dev.ip_address == "192.168.1.100"
        assert dev.mac_address == "00:11:22:33:44:55"
        assert dev.manufacturer == "FLIR Systems"
        assert dev.model == "FLIR A35"
        assert dev.is_thermal is True
        assert dev.serial_number == "72001-0101"

    @patch("socket.socket")
    def test_gvcp_discovery_socket(self, mock_socket_cls):
        mock_sock = MagicMock()
        mock_socket_cls.return_value = mock_sock

        # Simulate timeout on recvfrom
        mock_sock.recvfrom.side_effect = TimeoutError()

        devices = discover_gige_cameras()
        assert isinstance(devices, list)


class TestGigEPlugin:
    def test_gige_plugin_registration(self):
        registry = get_registry()
        plugin = registry.get_plugin("gige_vision")
        assert plugin is not None
        assert plugin.display_name == "GigE Vision"
        assert plugin.camera_role == CameraRole.RGB

    def test_gige_backend_and_camera(self):
        cam = GigECamera(ip_address="192.168.1.100", is_thermal=True)
        assert cam.open() is True
        ret, frame = cam.read()
        assert ret is True
        assert frame.dtype == pytest.importorskip("numpy").uint16

        temp_map = cam.read_temperature_map()
        assert temp_map is not None
        assert temp_map.shape == (480, 640)
        cam.release()

        backend = GigEBackend(ip_address="192.168.1.100", is_thermal=True)
        assert backend.is_radiometric() is True
        info = backend.get_info()
        assert info["backend"] == "GigE Vision"
        assert info["bit_depth"] == 16

    def test_gige_sdk_commands(self):
        backend = GigEBackend(ip_address="192.168.1.100", is_thermal=False)
        sdk = GigECameraSDK(backend_obj=backend)

        res = sdk.execute("set_exposure_time", {"time_us": 25000.0})
        assert res.get("success") is True
        assert res.get("time_us") == 25000.0

        res = sdk.execute("set_gain", {"gain_db": 6.0})
        assert res.get("success") is True
        assert res.get("gain_db") == 6.0

        res = sdk.execute("set_packet_size", {"packet_size": 9000})
        assert res.get("success") is True

        res = sdk.execute("get_camera_info")
        assert res.get("success") is True
        assert res.get("ip_address") == "192.168.1.100"
