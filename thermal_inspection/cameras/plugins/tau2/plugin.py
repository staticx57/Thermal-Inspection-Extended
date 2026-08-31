"""
FLIR Tau 2 Camera Plugin Implementation.
"""
from __future__ import annotations

import logging
from typing import Optional, List, Dict, Any, TYPE_CHECKING

from thermal_inspection.cameras.plugin.camera_plugin import (
    CameraPlugin, CameraRole, CameraPluginMatch, CameraCapabilities, CameraSDK
)
from thermal_inspection.cameras.device_scanner import find_devices_by_resolution
from thermal_inspection.cameras.tau2_backend import Tau2Backend
from thermal_inspection.cameras.tau2_camera import TAU2_RESOLUTIONS
from thermal_inspection.sdk.tau2_serial import Tau2Serial, scan_tau2_ports, GainMode, FFCMode, ColorLUT
from thermal_inspection.utils.config import get_serial_port, get_serial_baud

if TYPE_CHECKING:
    from PyQt6.QtWidgets import QWidget

logger = logging.getLogger(__name__)

DEFAULT_COM_PORT = "COM5"
DEFAULT_BAUD_RATE = 57600


class Tau2CameraSDK(CameraSDK):
    """CameraSDK implementation for FLIR Tau 2 using Tau2Serial CCI protocol."""

    def __init__(self, com_port: Optional[str] = None, baud_rate: Optional[int] = None):
        self.com_port = com_port or get_serial_port("flir_tau2", DEFAULT_COM_PORT)
        self.baud_rate = baud_rate or get_serial_baud("flir_tau2", DEFAULT_BAUD_RATE)
        self.serial: Optional[Tau2Serial] = None
        self._is_connected = False

    def connect(self) -> bool:
        try:
            if self.serial:
                self.disconnect()
            self.serial = Tau2Serial(port=self.com_port, baudrate=self.baud_rate)
            self._is_connected = self.serial.is_open()
            return self._is_connected
        except Exception as e:
            logger.error(f"Tau 2 SDK connect error on {self.com_port}: {e}")
            self.serial = None
            self._is_connected = False
            return False

    def disconnect(self):
        if self.serial:
            try:
                self.serial.close()
            except Exception:
                pass
        self.serial = None
        self._is_connected = False

    def is_connected(self) -> bool:
        return self._is_connected and self.serial is not None and self.serial.is_open()

    def execute(self, command: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        params = params or {}

        try:
            if command == "connect":
                port = params.get("com_port", self.com_port)
                baud = int(params.get("baud_rate", self.baud_rate))
                self.com_port = port
                self.baud_rate = baud
                ok = self.connect()
                info = self.execute("get_camera_info") if ok else {}
                return {"success": ok, "info": info}

            elif command == "disconnect":
                self.disconnect()
                return {"success": True}

            elif command == "scan_ports":
                ports = scan_tau2_ports()
                return {"success": True, "ports": ports}

            if not self.is_connected():
                return {"success": False, "error": "Tau 2 serial port is not connected"}

            if command == "ffc":
                ok = self.serial.do_ffc()
                return {"success": ok}

            elif command == "set_gain_mode":
                mode_str = params.get("mode", "high").upper()
                mode_val = getattr(GainMode, mode_str, GainMode.HIGH)
                ok = self.serial.set_gain_mode(int(mode_val))
                return {"success": ok}

            elif command == "get_gain_mode":
                mode_int = self.serial.get_gain_mode()
                return {"success": True, "mode": GainMode(mode_int).name.lower()}

            elif command == "set_ffc_mode":
                mode_str = params.get("mode", "manual").upper()
                mode_val = getattr(FFCMode, mode_str, FFCMode.MANUAL)
                ok = self.serial.set_ffc_mode(int(mode_val))
                return {"success": ok}

            elif command == "set_palette":
                lut_str = params.get("palette", "white_hot").upper().replace(" ", "_")
                lut_val = getattr(ColorLUT, lut_str, ColorLUT.WHITE_HOT)
                ok = self.serial.set_color_lut(int(lut_val))
                return {"success": ok}

            elif command == "set_tlinear":
                enabled = params.get("enabled", True)
                high_res = params.get("resolution", "high").lower() == "high"
                ok = self.serial.set_tlinear_mode(enabled, high_res)
                return {"success": ok}

            elif command == "get_tlinear":
                enabled, high_res = self.serial.get_tlinear_mode()
                return {"success": True, "enabled": enabled, "high_res": high_res}

            elif command == "get_fpa_temp":
                temp = self.serial.get_fpa_temperature()
                return {"success": True, "celsius": temp}

            elif command == "get_camera_info":
                cam_sn, sensor_sn = self.serial.get_serial_number()
                rev = self.serial.get_revision()
                fpa = self.serial.get_fpa_temperature()
                return {
                    "success": True,
                    "serial": str(cam_sn),
                    "sensor_serial": str(sensor_sn),
                    "firmware": rev,
                    "celsius": fpa,
                    "model": "FLIR Tau 2",
                }

            elif command == "set_shutter_position":
                pos_str = params.get("position", "open").lower()
                pos_val = 1 if pos_str == "closed" else 0
                ok = self.serial.set_shutter_position(pos_val)
                return {"success": ok}

            else:
                return {"success": False, "error": f"Unsupported Tau 2 command: '{command}'"}

        except Exception as e:
            logger.error(f"Tau 2 SDK command '{command}' error: {e}")
            return {"success": False, "error": str(e)}

    def get_supported_commands(self) -> List[str]:
        return [
            "connect", "disconnect", "scan_ports", "ffc", "set_gain_mode",
            "get_gain_mode", "set_ffc_mode", "set_palette", "set_tlinear",
            "get_tlinear", "get_fpa_temp", "get_camera_info", "set_shutter_position"
        ]


class Tau2Plugin(CameraPlugin):
    """CameraPlugin for FLIR Tau 2 thermal cameras."""

    @property
    def plugin_id(self) -> str:
        return "flir_tau2"

    @property
    def display_name(self) -> str:
        return "FLIR Tau 2"

    @property
    def camera_role(self) -> CameraRole:
        return CameraRole.THERMAL

    def detect(self) -> List[CameraPluginMatch]:
        # Reads the shared device scan; does not touch hardware itself.
        matches = []
        for device in find_devices_by_resolution(TAU2_RESOLUTIONS):
            matches.append(CameraPluginMatch(
                plugin_id=self.plugin_id,
                device_index=device.index,
                com_port=get_serial_port(self.plugin_id, DEFAULT_COM_PORT),
                baud_rate=get_serial_baud(self.plugin_id, DEFAULT_BAUD_RATE),
                name=f"FLIR Tau 2 ({device.width}x{device.height})",
                resolution=device.resolution,
                score=100
            ))
        return matches

    def create_backend(self, match: CameraPluginMatch) -> Tau2Backend:
        return Tau2Backend(
            device_id=match.device_index,
            resolution=match.resolution or (640, 512),
            tlinear=True,
            high_res=True
        )

    def create_sdk(self, match: CameraPluginMatch) -> Tau2CameraSDK:
        return Tau2CameraSDK(
            com_port=match.com_port or get_serial_port(self.plugin_id, DEFAULT_COM_PORT),
            baud_rate=match.baud_rate or get_serial_baud(self.plugin_id, DEFAULT_BAUD_RATE)
        )

    def create_control_panel(self) -> Optional[QWidget]:
        from thermal_inspection.gui.camera_control.tau2_control_panel import Tau2ControlPanel
        return Tau2ControlPanel()

    def get_capabilities(self, match: CameraPluginMatch) -> CameraCapabilities:
        return CameraCapabilities(
            bit_depth=16,
            radiometric=True,
            resolutions=TAU2_RESOLUTIONS,
            max_fps=60.0,
            has_ffc=True,
            has_gain_mode=True,
            has_palette_control=True,
            has_tlinear=True,
            has_serial_control=True,
            has_shutter_control=True,
            model="FLIR Tau 2"
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
