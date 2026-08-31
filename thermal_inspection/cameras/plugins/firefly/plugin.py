"""
FLIR Firefly RGB Camera Plugin Implementation.
"""
from __future__ import annotations

import logging
from typing import Optional, List, Dict, Any, TYPE_CHECKING

from thermal_inspection.cameras.plugin.camera_plugin import (
    CameraPlugin, CameraRole, CameraPluginMatch, CameraCapabilities, CameraSDK
)
from thermal_inspection.cameras.camera_factory import (
    create_rgb_camera, detect_firefly_cameras, PYSPIN_AVAILABLE
)

if TYPE_CHECKING:
    from PyQt6.QtWidgets import QWidget

logger = logging.getLogger(__name__)


class FireflyCameraSDK(CameraSDK):
    """CameraSDK implementation for FLIR Firefly / Spinnaker cameras."""

    def __init__(self, camera_obj=None):
        self.camera_obj = camera_obj
        self._is_connected = False

    def connect(self) -> bool:
        self._is_connected = True
        return True

    def disconnect(self):
        self._is_connected = False

    def is_connected(self) -> bool:
        return self._is_connected

    def execute(self, command: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        params = params or {}
        cam = self.camera_obj

        try:
            if command == "set_exposure_mode":
                mode = params.get("mode", "auto")
                if cam and hasattr(cam, "set_exposure_mode"):
                    ok = cam.set_exposure_mode(mode)
                    return {"success": bool(ok)}
                return {"success": True}

            elif command == "set_exposure_time":
                time_us = params.get("time_us", 10000.0)
                if cam and hasattr(cam, "set_exposure_time"):
                    ok = cam.set_exposure_time(time_us)
                    return {"success": bool(ok)}
                return {"success": True}

            elif command == "set_gain_mode":
                mode = params.get("mode", "auto")
                if cam and hasattr(cam, "set_gain_mode"):
                    ok = cam.set_gain_mode(mode)
                    return {"success": bool(ok)}
                return {"success": True}

            elif command == "set_gain":
                gain_db = params.get("gain_db", 0.0)
                if cam and hasattr(cam, "set_gain"):
                    ok = cam.set_gain(gain_db)
                    return {"success": bool(ok)}
                return {"success": True}

            elif command == "set_white_balance_mode":
                mode = params.get("mode", "auto")
                if cam and hasattr(cam, "set_white_balance_mode"):
                    ok = cam.set_white_balance_mode(mode)
                    return {"success": bool(ok)}
                return {"success": True}

            elif command == "calibrate_white_balance":
                if cam and hasattr(cam, "calibrate_white_balance"):
                    ok = cam.calibrate_white_balance()
                    return {"success": bool(ok)}
                return {"success": True}

            elif command == "set_white_balance_ratio":
                color = params.get("color", "red")
                ratio = params.get("ratio", 1.0)
                if cam and hasattr(cam, "set_white_balance_ratio"):
                    ok = cam.set_white_balance_ratio(color, ratio)
                    return {"success": bool(ok)}
                return {"success": True}

            elif command == "set_trigger_mode":
                enabled = params.get("enabled", False)
                source = params.get("source", "Software")
                if cam and hasattr(cam, "set_trigger_mode"):
                    ok = cam.set_trigger_mode(enabled, source)
                    return {"success": bool(ok)}
                return {"success": True}

            elif command == "trigger_fire":
                if cam and hasattr(cam, "fire_software_trigger"):
                    ok = cam.fire_software_trigger()
                    return {"success": bool(ok)}
                return {"success": True}

            elif command == "set_gamma":
                gamma = params.get("gamma", 1.0)
                if cam and hasattr(cam, "set_gamma"):
                    ok = cam.set_gamma(gamma)
                    return {"success": bool(ok)}
                return {"success": True}

            elif command == "set_sharpness":
                enabled = params.get("enabled", True)
                val = params.get("value", 1.0)
                if cam and hasattr(cam, "set_sharpness"):
                    ok = cam.set_sharpness(enabled, val)
                    return {"success": bool(ok)}
                return {"success": True}

            elif command == "get_camera_info":
                return {
                    "success": True,
                    "model": "FLIR Firefly",
                    "serial": getattr(cam, "serial_number", "N/A") if cam else "N/A"
                }

            else:
                return {"success": False, "error": f"Unknown Firefly command '{command}'"}

        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_supported_commands(self) -> List[str]:
        return [
            "set_exposure_mode", "set_exposure_time", "set_gain_mode", "set_gain",
            "set_white_balance_mode", "calibrate_white_balance", "set_white_balance_ratio",
            "set_trigger_mode", "trigger_fire", "set_gamma", "set_sharpness", "get_camera_info"
        ]


class FireflyPlugin(CameraPlugin):
    """CameraPlugin for FLIR Firefly / RGB cameras."""

    def __init__(self):
        self._last_cam = None

    @property
    def plugin_id(self) -> str:
        return "flir_firefly"

    @property
    def display_name(self) -> str:
        return "FLIR Firefly RGB"

    @property
    def camera_role(self) -> CameraRole:
        return CameraRole.RGB

    def detect(self) -> List[CameraPluginMatch]:
        # Spinnaker is the only way to reach a Firefly; without it there is
        # nothing to find, and probing generic video devices here would just
        # duplicate the shared scan the UVC plugin already consumes.
        if not PYSPIN_AVAILABLE or detect_firefly_cameras is None:
            logger.debug("PySpin unavailable — skipping Firefly detection")
            return []

        matches = []
        try:
            for idx, fcam in enumerate(detect_firefly_cameras()):
                name = getattr(fcam, 'model_name', 'FLIR Firefly')
                serial = getattr(fcam, 'serial_number', f"FF-{idx}")
                matches.append(CameraPluginMatch(
                    plugin_id=self.plugin_id,
                    device_index=idx,
                    name=f"{name} ({serial})",
                    resolution=(1440, 1080),
                    score=100,
                    extra={'camera_type': 'firefly', 'spinnaker_index': idx}
                ))
        except Exception as e:
            logger.warning(f"Firefly (Spinnaker) detection failed: {e}")

        return matches

    def create_backend(self, match: CameraPluginMatch):
        cam_type = match.extra.get('camera_type', None)
        cam = create_rgb_camera(
            camera_type=cam_type,
            camera_index=match.device_index,
            resolution=match.resolution
        )
        self._last_cam = cam
        return cam

    def create_sdk(self, match: CameraPluginMatch) -> FireflyCameraSDK:
        return FireflyCameraSDK(camera_obj=self._last_cam)

    def create_control_panel(self) -> Optional[QWidget]:
        from thermal_inspection.gui.camera_control.firefly_control_panel import FireflyControlPanel
        return FireflyControlPanel()

    def get_capabilities(self, match: CameraPluginMatch) -> CameraCapabilities:
        return CameraCapabilities(
            bit_depth=8,
            radiometric=False,
            resolutions=[(1440, 1080), (1920, 1080), (640, 480)],
            max_fps=60.0,
            has_exposure_control=True,
            model="FLIR Firefly RGB"
        )
