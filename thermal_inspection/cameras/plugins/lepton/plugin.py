"""
FLIR Lepton Camera Plugin Implementation.
"""
from __future__ import annotations

import logging
from typing import Optional, List, Dict, Any, TYPE_CHECKING

from thermal_inspection.cameras.plugin.camera_plugin import (
    CameraPlugin, CameraRole, CameraPluginMatch, CameraCapabilities, CameraSDK
)
from thermal_inspection.cameras.device_scanner import find_devices_by_resolution
from thermal_inspection.cameras.opencv_thermal_backend import OpenCVThermalBackend

if TYPE_CHECKING:
    from PyQt6.QtWidgets import QWidget

logger = logging.getLogger(__name__)

LEPTON_RESOLUTIONS = [(160, 120), (80, 60), (120, 160), (60, 80)]


class LeptonCameraSDK(CameraSDK):
    """CameraSDK implementation for FLIR Lepton via Lepton SDK wrapper."""

    def __init__(self):
        self._sdk = None
        self._is_connected = False

    def _get_sdk(self):
        if self._sdk is None:
            try:
                from thermal_inspection.sdk.lepton_sdk_wrapper import LeptonSDK
                self._sdk = LeptonSDK()
            except ImportError:
                self._sdk = None
        return self._sdk

    def connect(self) -> bool:
        sdk = self._get_sdk()
        if sdk and hasattr(sdk, "connect"):
            try:
                self._is_connected = bool(sdk.connect())
                return self._is_connected
            except Exception as e:
                logger.error(f"Lepton SDK connect failed: {e}")
        self._is_connected = False
        return False

    def disconnect(self):
        sdk = self._get_sdk()
        if sdk and hasattr(sdk, "disconnect"):
            try:
                sdk.disconnect()
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
                ok = self.connect()
                return {"success": ok}

            elif command == "disconnect":
                self.disconnect()
                return {"success": True}

            elif command == "ffc":
                if sdk and hasattr(sdk, "trigger_ffc"):
                    ok = sdk.trigger_ffc()
                    return {"success": bool(ok)}
                return {"success": False, "error": "FFC not available on Lepton"}

            elif command == "set_radiometric":
                enabled = params.get("enabled", True)
                if sdk and hasattr(sdk, "set_radiometry"):
                    ok = sdk.set_radiometry(enabled)
                    return {"success": bool(ok)}
                return {"success": True}

            elif command == "get_camera_info":
                return {
                    "success": True,
                    "model": "FLIR Lepton",
                    "serial": "N/A",
                    "firmware": "N/A"
                }

            else:
                return {"success": False, "error": f"Unknown Lepton command '{command}'"}

        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_supported_commands(self) -> List[str]:
        return ["connect", "disconnect", "ffc", "set_radiometric", "get_camera_info"]


class LeptonPlugin(CameraPlugin):
    """CameraPlugin for FLIR Lepton thermal cameras."""

    @property
    def plugin_id(self) -> str:
        return "flir_lepton"

    @property
    def display_name(self) -> str:
        return "FLIR Lepton"

    @property
    def camera_role(self) -> CameraRole:
        return CameraRole.THERMAL

    def detect(self) -> List[CameraPluginMatch]:
        # Reads the shared device scan; does not touch hardware itself.
        matches = []
        for device in find_devices_by_resolution(LEPTON_RESOLUTIONS):
            matches.append(CameraPluginMatch(
                plugin_id=self.plugin_id,
                device_index=device.index,
                name=f"FLIR Lepton ({device.width}x{device.height})",
                resolution=device.resolution,
                score=90
            ))
        return matches

    def create_backend(self, match: CameraPluginMatch) -> OpenCVThermalBackend:
        return OpenCVThermalBackend(device_id=match.device_index, enable_sdk=False)

    def create_sdk(self, match: CameraPluginMatch) -> LeptonCameraSDK:
        return LeptonCameraSDK()

    def create_control_panel(self) -> Optional[QWidget]:
        from thermal_inspection.gui.camera_control.lepton_control_panel import LeptonControlPanel
        return LeptonControlPanel()

    def get_capabilities(self, match: CameraPluginMatch) -> CameraCapabilities:
        return CameraCapabilities(
            bit_depth=16,
            radiometric=True,
            resolutions=LEPTON_RESOLUTIONS,
            max_fps=9.0,
            has_ffc=True,
            model="FLIR Lepton"
        )
