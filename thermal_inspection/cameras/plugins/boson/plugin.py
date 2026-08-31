"""
FLIR Boson Camera Plugin Implementation.
"""
from __future__ import annotations

import logging
from typing import Optional, List, Dict, Any, TYPE_CHECKING

from thermal_inspection.cameras.plugin.camera_plugin import (
    CameraPlugin, CameraRole, CameraPluginMatch, CameraCapabilities, CameraSDK
)
from thermal_inspection.cameras.device_scanner import find_devices_by_resolution
from thermal_inspection.cameras.opencv_thermal_backend import OpenCVThermalBackend
from thermal_inspection.utils.config import get_serial_port, get_serial_baud

if TYPE_CHECKING:
    from PyQt6.QtWidgets import QWidget

logger = logging.getLogger(__name__)

BOSON_RESOLUTIONS = [(640, 512), (320, 256), (512, 640), (256, 320)]
DEFAULT_COM_PORT = "COM7"


class BosonCameraSDK(CameraSDK):
    """CameraSDK implementation for FLIR Boson using BosonSDKWrapper."""

    def __init__(self, com_port: Optional[str] = None):
        self.com_port = com_port or get_serial_port("flir_boson", DEFAULT_COM_PORT)
        self._sdk = None
        self._is_connected = False

    def _get_sdk(self):
        if self._sdk is None:
            from thermal_inspection.sdk.boson_sdk_wrapper import BosonSDK
            self._sdk = BosonSDK()
        return self._sdk

    def connect(self) -> bool:
        sdk = self._get_sdk()
        try:
            ok = sdk.connect(self.com_port)
            self._is_connected = bool(ok)
            return self._is_connected
        except Exception as e:
            logger.error(f"Boson SDK connect error on {self.com_port}: {e}")
            self._is_connected = False
            return False

    def disconnect(self):
        if self._sdk:
            try:
                self._sdk.disconnect()
            except Exception:
                pass
        self._is_connected = False

    def is_connected(self) -> bool:
        return self._is_connected

    def execute(self, command: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        params = params or {}
        sdk = self._get_sdk()

        try:
            if command == "connect":
                port = params.get("com_port", self.com_port)
                self.com_port = port
                ok = self.connect()
                info = self.execute("get_camera_info") if ok else {}
                return {"success": ok, "info": info}

            elif command == "disconnect":
                self.disconnect()
                return {"success": True}

            elif command == "scan_ports":
                from thermal_inspection.sdk.boson_serial import scan_boson_ports
                ports = scan_boson_ports()
                return {"success": True, "ports": ports}

            elif command == "ffc":
                ok = sdk.run_ffc()
                return {"success": bool(ok)}

            elif command == "set_gain_mode":
                mode = params.get("mode", "high")
                ok = sdk.set_gain_mode(mode)
                return {"success": bool(ok)}

            elif command == "set_ffc_mode":
                mode = params.get("mode", "manual")
                ok = sdk.set_ffc_mode(mode)
                return {"success": bool(ok)}

            elif command == "set_palette":
                lut = params.get("palette", "white_hot")
                ok = sdk.set_color_lut(lut)
                return {"success": bool(ok)}

            elif command == "get_fpa_temp":
                temp = sdk.get_fpa_temperature()
                return {"success": temp is not None, "celsius": temp or 0.0}

            elif command == "get_camera_info":
                info = sdk.get_camera_info()
                if info:
                    return {
                        "success": True,
                        "serial": getattr(info, "serial_number", str(info.get("serial_number", "N/A") if isinstance(info, dict) else "N/A")),
                        "firmware": getattr(info, "software_version", "N/A"),
                        "model": "FLIR Boson",
                    }
                return {"success": False, "error": "No camera info"}

            elif command == "set_agc":
                if "max_gain" in params:
                    sdk.set_agc_max_gain(params["max_gain"])
                if "gamma" in params:
                    sdk.set_agc_gamma(params["gamma"])
                if "linearity" in params:
                    sdk.set_agc_linearity(params["linearity"])
                if "dde" in params:
                    sdk.set_agc_dde(params["dde"])
                if "plateau" in params:
                    sdk.set_agc_plateau(params["plateau"])
                if "dampening" in params:
                    sdk.set_agc_dampening(params["dampening"])
                return {"success": True}

            elif command == "set_shutter_position":
                pos = params.get("position", "auto")
                ok = sdk.set_shutter_position(pos)
                return {"success": bool(ok)}

            elif command == "set_radiometric_mode":
                enabled = params.get("enabled", True)
                ok = sdk.set_radiometric_mode(enabled)
                return {"success": bool(ok)}

            elif command == "set_environmental":
                ok = sdk.set_environmental_compensation(params)
                return {"success": bool(ok)}

            else:
                return {"success": False, "error": f"Unknown command '{command}'"}

        except Exception as e:
            logger.error(f"Boson SDK execute '{command}' failed: {e}")
            return {"success": False, "error": str(e)}

    def get_supported_commands(self) -> List[str]:
        return [
            "connect", "disconnect", "scan_ports", "ffc", "set_gain_mode",
            "set_ffc_mode", "set_palette", "get_fpa_temp", "get_camera_info",
            "set_agc", "set_shutter_position", "set_radiometric_mode", "set_environmental"
        ]


class BosonPlugin(CameraPlugin):
    """CameraPlugin for FLIR Boson thermal cameras."""

    @property
    def plugin_id(self) -> str:
        return "flir_boson"

    @property
    def display_name(self) -> str:
        return "FLIR Boson"

    @property
    def camera_role(self) -> CameraRole:
        return CameraRole.THERMAL

    def detect(self) -> List[CameraPluginMatch]:
        # Reads the shared device scan; does not touch hardware itself.
        matches = []
        for device in find_devices_by_resolution(BOSON_RESOLUTIONS, tolerance=10):
            matches.append(CameraPluginMatch(
                plugin_id=self.plugin_id,
                device_index=device.index,
                com_port=get_serial_port(self.plugin_id, DEFAULT_COM_PORT),
                baud_rate=get_serial_baud(self.plugin_id, 921600),
                name=f"FLIR Boson ({device.width}x{device.height})",
                resolution=device.resolution,
                score=100
            ))
        return matches

    def create_backend(self, match: CameraPluginMatch) -> OpenCVThermalBackend:
        return OpenCVThermalBackend(
            device_id=match.device_index,
            com_port=match.com_port or get_serial_port(self.plugin_id, DEFAULT_COM_PORT),
            enable_sdk=True
        )

    def create_sdk(self, match: CameraPluginMatch) -> BosonCameraSDK:
        return BosonCameraSDK(
            com_port=match.com_port or get_serial_port(self.plugin_id, DEFAULT_COM_PORT)
        )

    def create_control_panel(self) -> Optional[QWidget]:
        from thermal_inspection.gui.camera_control.boson_control_panel import BosonControlPanel
        panel = BosonControlPanel()
        return panel

    def get_capabilities(self, match: CameraPluginMatch) -> CameraCapabilities:
        return CameraCapabilities(
            bit_depth=8,
            radiometric=True,
            resolutions=[(640, 512), (320, 256)],
            max_fps=60.0,
            has_ffc=True,
            has_gain_mode=True,
            has_agc_control=True,
            has_palette_control=True,
            has_serial_control=True,
            has_shutter_control=True,
            model="FLIR Boson"
        )

    def on_sdk_connected(self, sdk: CameraSDK, panel: Optional[QWidget]) -> None:
        if panel and hasattr(panel, "update_connection_status"):
            panel.update_connection_status(True)
            res = sdk.execute("get_camera_info")
            if res.get("success") and hasattr(panel, "update_camera_info"):
                panel.update_camera_info(res)

    def on_sdk_disconnected(self, panel: Optional[QWidget]) -> None:
        if panel and hasattr(panel, "update_connection_status"):
            panel.update_connection_status(False)
