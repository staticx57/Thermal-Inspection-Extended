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
from thermal_inspection.utils.paths import default_serial_port

DEFAULT_COM_PORT = default_serial_port()


class BosonCameraSDK(CameraSDK):
    """CameraSDK implementation for FLIR Boson using BosonSDKWrapper."""

    def __init__(self, com_port: Optional[str] = None):
        self.com_port = com_port or get_serial_port("flir_boson", DEFAULT_COM_PORT)
        self._sdk = None
        self._is_connected = False

    def _get_sdk(self):
        if self._sdk is None:
            from thermal_inspection.sdk.boson_sdk_wrapper import BosonSDK
            self._sdk = BosonSDK(com_port=self.com_port)
        return self._sdk

    def connect(self) -> bool:
        sdk = self._get_sdk()
        try:
            ok = sdk.open()
            self._is_connected = bool(ok)
            return self._is_connected
        except Exception as e:
            logger.error(f"Boson SDK connect error on {self.com_port}: {e}")
            self._is_connected = False
            return False

    def disconnect(self):
        if self._sdk:
            try:
                self._sdk.close()
            except Exception as e:
                logger.debug(f"Error closing Boson SDK connection: {e}")
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
                # get_fpa_temperature() returns (kelvin, celsius) or None.
                temp = sdk.get_fpa_temperature()
                celsius = temp[1] if temp is not None else 0.0
                return {"success": temp is not None, "celsius": celsius}

            elif command == "get_camera_info":
                info = sdk.get_info()
                if info:
                    return {
                        "success": True,
                        "serial": info.serial_number,
                        "firmware": info.software_version,
                        "model": "FLIR Boson",
                        "part_number": info.camera_part_number,
                        "lens_number": info.lens_number,
                        "table_number": info.table_number,
                        "gain_mode": info.gain_mode.name if info.gain_mode else None,
                        "radiometric_capable": bool(info.camera_part_number and 'R' in info.camera_part_number.upper()),
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
                    sdk.set_detail_enhancement(params["dde"])
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
                if not enabled:
                    # The Boson SDK exposes no radiometry-disable call.
                    return {"success": False, "error": "Boson SDK cannot disable radiometry once enabled"}
                ok = sdk.enable_radiometry()
                return {"success": bool(ok)}

            elif command == "set_environmental":
                ok = True
                if "emissivity" in params:
                    ok = sdk.set_emissivity(params["emissivity"]) and ok
                if "atm_temp" in params:
                    ok = sdk.set_atmospheric_temperature(params["atm_temp"]) and ok
                if "atm_transmission" in params:
                    ok = sdk.set_atmospheric_transmission(params["atm_transmission"]) and ok
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


class BosonFlirpyNativeSDK(CameraSDK):
    """
    CameraSDK adapter for a radiometric Boson already active via
    FlirpyThermalBackend.

    Delegates every command to that backend's own control methods (which
    run over its one native flirpy connection - see
    flirpy_thermal_backend.py's module docstring) instead of opening a
    second, independent connection, which always lost the COM port race:
    confirmed live, a plain BosonCameraSDK here failed every time with
    "Failed to open port #6 with error 255!" while the backend streamed.
    """

    _GAIN_MODE_MAP = {"high": 0, "low": 1, "auto": 2}
    _FFC_MODE_MAP = {"manual": 0, "auto": 1, "external": 2}
    _SYNC_MODE_MAP = {"disabled": 0, "master": 1, "slave": 2}
    _SYNC_MODE_NAMES = {0: "disabled", 1: "master", 2: "slave"}
    _PALETTE_MAP = {
        "white_hot": 0, "black_hot": 1, "rainbow": 2, "rainbow_hc": 3,
        "ironbow": 4, "lava": 5, "arctic": 6, "globow": 7,
        "gradedfire": 8, "hottest": 9,
    }
    _GAIN_MODE_NAMES = {0: "HIGH", 1: "LOW", 2: "AUTO"}

    def __init__(self, backend):
        self._backend = backend

    def connect(self) -> bool:
        return self._backend.is_opened()

    def disconnect(self):
        # The connection's lifecycle belongs to the video backend
        # (camera_plugin_host releases it on deactivate) - closing it
        # here would also kill the live video feed, so this is a no-op.
        pass

    def is_connected(self) -> bool:
        return self._backend.is_opened()

    def get_supported_commands(self) -> List[str]:
        return [
            "connect", "disconnect", "scan_ports", "ffc", "set_gain_mode",
            "set_ffc_mode", "set_palette", "get_fpa_temp", "get_camera_info",
            "set_radiometric_mode", "set_environmental",
            "set_external_sync_mode", "get_external_sync_mode",
        ]

    def execute(self, command: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        params = params or {}
        try:
            if command == "connect":
                return {"success": self.connect(), "info": self.execute("get_camera_info")}

            elif command == "disconnect":
                self.disconnect()
                return {"success": True}

            elif command == "scan_ports":
                from thermal_inspection.sdk.boson_serial import scan_boson_ports
                return {"success": True, "ports": scan_boson_ports()}

            elif command == "ffc":
                return {"success": self._backend.trigger_ffc()}

            elif command == "set_gain_mode":
                mode = self._GAIN_MODE_MAP.get(str(params.get("mode", "auto")).lower(), 2)
                return {"success": self._backend.set_gain_mode(mode)}

            elif command == "set_ffc_mode":
                mode = self._FFC_MODE_MAP.get(str(params.get("mode", "manual")).lower(), 0)
                return {"success": self._backend.set_ffc_mode(mode)}

            elif command == "set_external_sync_mode":
                name = str(params.get("mode", "disabled")).lower()
                if name not in self._SYNC_MODE_MAP:
                    return {"success": False, "error": f"Unknown sync mode '{name}' (disabled, master, slave)"}
                return {"success": self._backend.set_external_sync_mode(self._SYNC_MODE_MAP[name]), "mode": name}

            elif command == "get_external_sync_mode":
                mode = self._backend.get_external_sync_mode()
                return {"success": mode is not None, "mode": self._SYNC_MODE_NAMES.get(mode)}

            elif command == "set_palette":
                lut = self._PALETTE_MAP.get(str(params.get("palette", "white_hot")).lower(), 0)
                return {"success": self._backend.set_color_lut(lut)}

            elif command == "get_fpa_temp":
                temp = self._backend.get_fpa_temperature()
                return {"success": temp is not None, "celsius": temp if temp is not None else 0.0}

            elif command == "get_camera_info":
                cam = self._backend.camera
                info = {"success": True, "model": "FLIR Boson", "radiometric_capable": True}
                for key, getter in (
                    ("serial", "get_camera_serial"),
                    ("firmware", "get_firmware_revision"),
                    ("part_number", "get_part_number"),
                    ("lens_number", "get_lens_number"),
                    ("table_number", "get_table_number"),
                ):
                    try:
                        info[key] = getattr(cam, getter)()
                    except Exception as e:
                        logger.debug(f"get_camera_info: {getter} failed: {e}")
                gain_mode = self._backend.get_gain_mode()
                if gain_mode is not None:
                    info["gain_mode"] = self._GAIN_MODE_NAMES.get(gain_mode)
                sync_mode = self._backend.get_external_sync_mode()
                if sync_mode is not None:
                    info["external_sync"] = self._SYNC_MODE_NAMES.get(sync_mode)
                return info

            elif command == "set_radiometric_mode":
                enabled = params.get("enabled", True)
                if not enabled:
                    return {"success": False, "error": "Boson cannot disable radiometry once enabled"}
                self._backend.camera.set_radiometry_enable(True)
                return {"success": True}

            elif command == "set_environmental":
                ok = True
                if "emissivity" in params:
                    ok = self._backend.set_emissivity(params["emissivity"]) and ok
                if "atm_temp" in params:
                    ok = self._backend.set_atmospheric_temperature(params["atm_temp"]) and ok
                if "atm_transmission" in params:
                    ok = self._backend.set_atmospheric_transmission(params["atm_transmission"]) and ok
                return {"success": bool(ok)}

            else:
                return {"success": False, "error": f"Unknown command '{command}'"}

        except Exception as e:
            logger.error(f"Boson native SDK execute '{command}' failed: {e}")
            return {"success": False, "error": str(e)}


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

    # Other thermal camera families (Tau2, Lepton breakout boards) commonly
    # share Boson's 640x512/320x256 sensor resolutions, and find_devices_by_
    # resolution() has no way to tell cameras of the same resolution apart.
    # Boson's own UVC descriptor doesn't reliably self-identify by name on
    # every machine, but a competing thermal core that DOES self-identify
    # (e.g. "THERMAL VISION CAMERA TAU-2") must be excluded explicitly -
    # confirmed live: with only a Tau2 attached, this plugin claimed its
    # video feed as "FLIR Boson (640x512)" purely from the resolution match.
    _OTHER_THERMAL_NAME_MARKERS = ('tau', 'lepton')

    def detect(self) -> List[CameraPluginMatch]:
        # Reads the shared device scan; does not touch hardware itself.
        matches = []
        thermal_devices = find_devices_by_resolution(BOSON_RESOLUTIONS, tolerance=10)
        thermal_devices = [
            d for d in thermal_devices
            if not any(marker in d.name.lower() for marker in self._OTHER_THERMAL_NAME_MARKERS)
        ]
        if not thermal_devices:
            return matches

        com_port = self._resolve_com_port()
        for device in thermal_devices:
            matches.append(CameraPluginMatch(
                plugin_id=self.plugin_id,
                device_index=device.index,
                com_port=com_port,
                baud_rate=get_serial_baud(self.plugin_id, 921600),
                name=f"FLIR Boson ({device.width}x{device.height})",
                resolution=device.resolution,
                score=100
            ))
        return matches

    def _resolve_com_port(self) -> str:
        """
        Resolve the serial control port: explicit user override first, then
        a live scan for the actual FLIR/Boson serial device (the video
        interface and the CCI control interface enumerate as separate
        Windows devices, and the control COM port is not derivable from the
        video device index — it varies per machine/USB topology), falling
        back to the configured default only if nothing is found.
        """
        from thermal_inspection.utils.config import get_config
        if get_config().get('sdk_com_port'):
            return get_serial_port(self.plugin_id, DEFAULT_COM_PORT)

        try:
            from thermal_inspection.sdk.boson_serial import scan_boson_ports
            found = scan_boson_ports()
            if found:
                return found[0]
        except Exception as e:
            logger.debug(f"Boson COM port auto-detect failed: {e}")

        return get_serial_port(self.plugin_id, DEFAULT_COM_PORT)

    def _probe_radiometric_capable(self, com_port: str) -> bool:
        """
        Check the -R part-number flag via a throwaway SDK connection.

        Boson ships in both radiometric (-R, has T-Linear/absolute temp) and
        non-radiometric SKUs; only the SDK can tell them apart (BosonSDK.
        is_radiometric_capable() reads the part number). This must run and
        fully close BEFORE create_sdk()'s persistent connection or
        FlirpyThermalBackend's own probe — the COM port is exclusive, so
        only one caller may hold it at a time. Same "connect, ask, close"
        pattern FlirpyThermalBackend already uses for the same reason.
        """
        try:
            from thermal_inspection.sdk.boson_sdk_wrapper import BosonSDK
            sdk = BosonSDK(com_port=com_port)
            if not sdk.open():
                return False
            try:
                return sdk.is_radiometric_capable()
            finally:
                sdk.close()
        except Exception as e:
            logger.debug(f"Boson radiometric capability probe failed on {com_port}: {e}")
            return False

    def create_backend(self, match: CameraPluginMatch):
        com_port = match.com_port or self._resolve_com_port()
        # Cached for get_capabilities(), which the host calls right after
        # this for the same match/activation — avoids probing twice.
        self._last_probed_radiometric = self._probe_radiometric_capable(com_port)
        # Cached for create_sdk(), called right after this in the same
        # activation (see camera_plugin_host.activate_camera) - lets the
        # control-panel SDK delegate to this exact backend instead of
        # opening its own independent connection to the same COM port.
        self._last_backend = None

        if self._last_probed_radiometric:
            from thermal_inspection.sdk.flirpy_thermal_backend import FlirpyThermalBackend
            logger.info(f"Boson on {com_port} is a radiometric (-R) unit — using flirpy 16-bit backend")
            backend = FlirpyThermalBackend(com_port=com_port, auto_configure=True)
            self._last_backend = backend
            return backend

        # Non-radiometric (or undetermined): 8-bit AGC via OpenCV.
        # enable_sdk=False: the video backend must not open its own serial
        # connection to the Boson. create_sdk() below opens the one serial
        # connection for this camera (FFC/gain/palette control) - two
        # independent BosonSDK instances on the same COM port fight over
        # exclusive access and the second one always fails to open.
        return OpenCVThermalBackend(
            device_id=match.device_index,
            com_port=com_port,
            enable_sdk=False
        )

    def create_sdk(self, match: CameraPluginMatch):
        # The radiometric path already has an open connection (the flirpy
        # backend created above, in the same activation) - flirpy holds
        # the COM port exclusively for its whole life (see
        # flirpy_thermal_backend.py's module docstring), so a second,
        # independent BosonCameraSDK here would just fail to open it.
        # Delegate to the live backend instead of opening another one.
        from thermal_inspection.sdk.flirpy_thermal_backend import FlirpyThermalBackend
        backend = getattr(self, '_last_backend', None)
        if isinstance(backend, FlirpyThermalBackend):
            return BosonFlirpyNativeSDK(backend)

        return BosonCameraSDK(
            com_port=match.com_port or self._resolve_com_port()
        )

    def create_control_panel(self) -> Optional[QWidget]:
        from thermal_inspection.gui.camera_control.boson_control_panel import BosonControlPanel
        panel = BosonControlPanel()
        return panel

    def get_capabilities(self, match: CameraPluginMatch) -> CameraCapabilities:
        is_radiometric = getattr(self, '_last_probed_radiometric', False)
        return CameraCapabilities(
            bit_depth=16 if is_radiometric else 8,
            radiometric=is_radiometric,
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
