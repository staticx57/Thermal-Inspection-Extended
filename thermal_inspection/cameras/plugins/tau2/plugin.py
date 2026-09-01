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
        # com_port intentionally stays None when the caller (Tau2Plugin,
        # after scanning live hardware) explicitly found no CCI serial port -
        # falling back to a configured default here would silently paper
        # over that and try to open the wrong device (previously a
        # Bluetooth virtual COM port on this machine).
        self.com_port = com_port
        self.baud_rate = baud_rate or get_serial_baud("flir_tau2", DEFAULT_BAUD_RATE)
        self.serial: Optional[Tau2Serial] = None
        self._is_connected = False

    def connect(self) -> bool:
        if not self.com_port:
            logger.warning("Tau 2 SDK connect: no CCI serial port available - video-only camera?")
            return False
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

            elif command in ("set_tlinear", "set_radiometric_mode"):
                # set_radiometric_mode is the canonical cross-plugin command
                # name (see BosonPlugin/LeptonPlugin) - the UI only ever
                # asks for "radiometric mode", not each camera's own term
                # for it. set_tlinear stays as Tau2's own historical name.
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
            "set_radiometric_mode", "get_tlinear", "get_fpa_temp",
            "get_camera_info", "set_shutter_position"
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
        all_devices = find_devices_by_resolution(TAU2_RESOLUTIONS)
        # Other thermal cores (Boson, Lepton breakout boards) commonly share
        # Tau2's 640x512/320x256 sensor resolutions, and find_devices_by_
        # resolution() can't tell cameras of the same resolution apart.
        # Prefer a device whose OS name self-identifies as a Tau2 (this
        # breakout board reports "THERMAL VISION CAMERA TAU-2"); fall back to
        # the plain resolution match for boards that don't brand the name.
        named_matches = [d for d in all_devices if 'tau' in d.name.lower()]
        devices = named_matches or all_devices

        com_port = self._resolve_com_port()
        matches = []
        for device in devices:
            matches.append(CameraPluginMatch(
                plugin_id=self.plugin_id,
                device_index=device.index,
                com_port=com_port,
                baud_rate=get_serial_baud(self.plugin_id, DEFAULT_BAUD_RATE),
                name=f"FLIR Tau 2 ({device.width}x{device.height})",
                resolution=device.resolution,
                score=100
            ))
        return matches

    def _resolve_com_port(self) -> Optional[str]:
        """
        Resolve the CCI control port: explicit user override first, then a
        live scan for a self-identifying Tau2 serial device. Returns None
        (not a guessed default) when nothing is found - some breakout
        boards (confirmed to exist in the wild) expose only UVC video with
        no CCI line at all.

        Deliberately does NOT fall back to the plugin's persisted
        ``serial_ports.flir_tau2.port`` config entry the way ``get_serial_
        port()`` does: that value is factory boilerplate (config.py's
        DEFAULT_CONFIG), not something this session verified, and on this
        exact hardware it pointed at "COM5" - a Bluetooth virtual serial
        port - so every SDK connect attempt tried the wrong device instead
        of failing cleanly with "no control port available". Only the
        explicit ``sdk_com_port`` override (a user deliberately forcing a
        specific port) is trusted as a non-scanned answer.
        """
        from thermal_inspection.utils.config import get_config
        if get_config().get('sdk_com_port'):
            return get_serial_port(self.plugin_id, DEFAULT_COM_PORT)

        found = scan_tau2_ports()
        return found[0] if found else None

    def create_backend(self, match: CameraPluginMatch) -> Tau2Backend:
        # T-Linear radiometric mode is a camera-side setting enabled over
        # CCI (set_tlinear_mode) - without a control port there is no way
        # to have actually put the camera into that mode, so whatever raw
        # counts the video stream carries are standard AGC-processed
        # imagery, not calibrated Kelvin data. Claiming tlinear=True anyway
        # (the previous unconditional default) meant this codebase's
        # Kelvin*100 scaling and Celsius conversion ran on non-radiometric
        # video and produced fabricated temperatures - confirmed live on a
        # video-only breakout board with no CCI line at all.
        has_cci = bool(match.com_port)

        # Selectable alternative to the default onboard-colorized BGR
        # passthrough: config-driven for now (tau2.raw_mode / tau2.byte_order
        # in config.json) rather than a GUI toggle, since raw_mode has no
        # temperature calibration yet - see Tau2Camera's docstring. Default
        # is the confirmed-working colorized passthrough.
        from thermal_inspection.utils.config import get_config
        config = get_config()
        raw_mode = bool(config.get('tau2', {}).get('raw_mode', False))
        byte_order = config.get('tau2', {}).get('byte_order', 'swap')

        return Tau2Backend(
            device_id=match.device_index,
            resolution=match.resolution or (640, 512),
            tlinear=has_cci,
            high_res=True,
            raw_mode=raw_mode,
            byte_order=byte_order
        )

    def create_sdk(self, match: CameraPluginMatch) -> Tau2CameraSDK:
        return Tau2CameraSDK(
            com_port=match.com_port or self._resolve_com_port(),
            baud_rate=match.baud_rate or get_serial_baud(self.plugin_id, DEFAULT_BAUD_RATE)
        )

    def create_control_panel(self) -> Optional[QWidget]:
        from thermal_inspection.gui.camera_control.tau2_control_panel import Tau2ControlPanel
        return Tau2ControlPanel()

    def get_capabilities(self, match: CameraPluginMatch) -> CameraCapabilities:
        # All of these are CCI-commanded features - none are actually
        # available without a control port (see create_backend()).
        has_cci = bool(match.com_port)
        return CameraCapabilities(
            bit_depth=16 if has_cci else 8,
            radiometric=has_cci,
            resolutions=TAU2_RESOLUTIONS,
            max_fps=60.0,
            has_ffc=has_cci,
            has_gain_mode=has_cci,
            has_palette_control=has_cci,
            has_tlinear=has_cci,
            has_serial_control=has_cci,
            has_shutter_control=has_cci,
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
