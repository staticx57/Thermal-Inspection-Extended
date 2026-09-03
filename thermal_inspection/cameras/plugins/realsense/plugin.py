"""
Intel RealSense Camera Plugin (D400/L500 series depth + color).
"""
from __future__ import annotations

import logging
from typing import Optional, List, Dict, Any, TYPE_CHECKING

from thermal_inspection.cameras.plugin.camera_plugin import (
    CameraPlugin, CameraRole, CameraPluginMatch, CameraCapabilities, CameraSDK
)
from thermal_inspection.cameras.realsense_camera import (
    RGBCameraRealSense, REALSENSE_AVAILABLE, detect_realsense_cameras
)

if TYPE_CHECKING:
    from PyQt6.QtWidgets import QWidget

logger = logging.getLogger(__name__)


class RealSenseSDK(CameraSDK):
    """CameraSDK implementation exposing RealSense's depth/point-cloud extras via generic commands."""

    def __init__(self, camera_obj: Optional[RGBCameraRealSense] = None):
        self.camera_obj = camera_obj
        self._is_connected = False

    def connect(self) -> bool:
        if self.camera_obj and self.camera_obj.is_opened():
            self._is_connected = True
            return True
        return False

    def disconnect(self):
        self._is_connected = False

    def is_connected(self) -> bool:
        return self._is_connected or (self.camera_obj is not None and self.camera_obj.is_opened())

    def execute(self, command: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        params = params or {}
        cam = self.camera_obj
        if not cam or not cam.is_opened():
            return {"success": False, "error": "Camera not opened"}

        try:
            if command == "get_camera_info":
                return {"success": True, **cam.get_info()}

            elif command == "get_depth_frame":
                depth = cam.get_depth_frame()
                if depth is None:
                    return {"success": False, "error": "No depth frame available"}
                return {"success": True, "depth_map": depth}

            elif command == "get_point_cloud":
                result = cam.get_point_cloud()
                if result is None:
                    return {"success": False, "error": "No point cloud available"}
                vertices, uv = result
                return {"success": True, "vertices": vertices, "uv": uv}

            elif command == "get_depth_intrinsics":
                intr = cam.get_depth_intrinsics()
                if intr is None:
                    return {"success": False, "error": "Intrinsics not available"}
                return {"success": True, **intr}

            elif command == "get_depth_sensor_options":
                return {"success": True, "options": cam.get_depth_sensor_options()}

            elif command == "set_depth_sensor_option":
                option = params.get("option")
                value = params.get("value")
                if option is None or value is None:
                    return {"success": False, "error": "Missing 'option' or 'value' param"}
                ok = cam.set_depth_sensor_option(option, value)
                return {"success": ok}

            else:
                return {"success": False, "error": f"Unknown RealSense command '{command}'"}

        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_supported_commands(self) -> List[str]:
        return ["get_camera_info", "get_depth_frame", "get_point_cloud", "get_depth_intrinsics",
                "get_depth_sensor_options", "set_depth_sensor_option"]


class RealSensePlugin(CameraPlugin):
    """CameraPlugin for Intel RealSense depth+color cameras (D400/L500 series)."""

    def __init__(self):
        self._last_cam: Optional[RGBCameraRealSense] = None

    @property
    def plugin_id(self) -> str:
        return "intel_realsense"

    @property
    def display_name(self) -> str:
        return "Intel RealSense"

    @property
    def camera_role(self) -> CameraRole:
        return CameraRole.RGB

    def detect(self) -> List[CameraPluginMatch]:
        if not REALSENSE_AVAILABLE:
            return []

        matches = []
        for device in detect_realsense_cameras():
            if not device['supported']:
                # T265 and similar - detected so it's visible in logs/scan
                # results, but no depth+color stream to back a match with.
                logger.info(f"RealSense {device['model']} (S/N {device['serial']}) has no depth+color stream - skipping")
                continue

            matches.append(CameraPluginMatch(
                plugin_id=self.plugin_id,
                device_index=-1,  # not an OS VideoCapture index - opened via librealsense directly
                name=device['model'],
                resolution=(0, 0),  # negotiated on open() - device picks its own default profile
                score=85,  # a genuine depth+color device outranks a generic UVC webcam guess
                extra={'serial_number': device['serial']},
            ))
        return matches

    def create_backend(self, match: CameraPluginMatch) -> RGBCameraRealSense:
        cam = RGBCameraRealSense(serial_number=match.extra.get('serial_number', ''))
        self._last_cam = cam
        return cam

    def create_sdk(self, match: CameraPluginMatch) -> RealSenseSDK:
        sdk = RealSenseSDK(camera_obj=self._last_cam)
        sdk.connect()
        return sdk

    def create_control_panel(self) -> Optional["QWidget"]:
        from thermal_inspection.gui.camera_control.realsense_control_panel import RealSenseControlPanel
        return RealSenseControlPanel()

    def get_capabilities(self, match: CameraPluginMatch) -> CameraCapabilities:
        return CameraCapabilities(
            bit_depth=8,
            radiometric=False,
            resolutions=[],  # negotiated by the device itself, not user-selectable here
            max_fps=30.0,
            model=match.name or "Intel RealSense",
        )

    def on_sdk_connected(self, sdk: CameraSDK, panel: Optional["QWidget"]):
        if panel and hasattr(panel, "update_camera_info"):
            res = sdk.execute("get_camera_info")
            if res.get("success"):
                panel.update_camera_info(res)
        if panel and hasattr(panel, "update_depth_sensor_options"):
            res = sdk.execute("get_depth_sensor_options")
            if res.get("success"):
                panel.update_depth_sensor_options(res.get("options", {}))
