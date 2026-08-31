"""
Generic USB / UVC Webcam Plugin Implementation.
"""
from __future__ import annotations

import logging
from typing import Optional, List, Dict, Any, TYPE_CHECKING
import cv2  # UVCCameraSDK uses cv2.CAP_PROP_* constants

from thermal_inspection.cameras.plugin.camera_plugin import (
    CameraPlugin, CameraRole, CameraPluginMatch, CameraCapabilities, CameraSDK
)
from thermal_inspection.cameras.device_scanner import scan_video_devices
from thermal_inspection.cameras.rgb_camera_uvc import RGBCameraUVC

if TYPE_CHECKING:
    from PyQt6.QtWidgets import QWidget

logger = logging.getLogger(__name__)

# Thermal resolutions to avoid false-matching as a standard RGB webcam
THERMAL_RESOLUTIONS = {(640, 512), (320, 256), (336, 256), (324, 256), (160, 120), (80, 60)}


class UVCCameraSDK(CameraSDK):
    """CameraSDK implementation for Generic UVC Webcams."""

    def __init__(self, camera_obj: Optional[RGBCameraUVC] = None):
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
        if not cam or not cam.cap:
            return {"success": False, "error": "Camera not opened"}

        cap = cam.cap

        try:
            if command == "set_property":
                prop_name = params.get("property", "").lower()
                val = params.get("value", 0)
                prop_map = {
                    "brightness": cv2.CAP_PROP_BRIGHTNESS,
                    "contrast": cv2.CAP_PROP_CONTRAST,
                    "saturation": cv2.CAP_PROP_SATURATION,
                    "sharpness": cv2.CAP_PROP_SHARPNESS,
                    "gain": cv2.CAP_PROP_GAIN,
                    "exposure": cv2.CAP_PROP_EXPOSURE,
                    "focus": cv2.CAP_PROP_FOCUS,
                    "white_balance": cv2.CAP_PROP_WHITE_BALANCE_BLUE_U,
                }
                if prop_name in prop_map:
                    ok = cap.set(prop_map[prop_name], float(val))
                    return {"success": bool(ok)}
                return {"success": False, "error": f"Unknown property '{prop_name}'"}

            elif command == "set_resolution":
                w = params.get("width", 640)
                h = params.get("height", 480)
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, w)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, h)
                actual_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                actual_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                cam.width = actual_w
                cam.height = actual_h
                return {"success": True, "resolution": (actual_w, actual_h)}

            elif command == "set_auto_exposure":
                enabled = params.get("enabled", True)
                # DirectShow / V4L2 auto exposure convention
                val = 1 if enabled else 0.25
                ok = cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, val)
                return {"success": bool(ok)}

            elif command == "set_auto_focus":
                enabled = params.get("enabled", True)
                ok = cap.set(cv2.CAP_PROP_AUTOFOCUS, 1 if enabled else 0)
                return {"success": bool(ok)}

            elif command == "reset_defaults":
                cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 1)
                cap.set(cv2.CAP_PROP_AUTOFOCUS, 1)
                cap.set(cv2.CAP_PROP_BRIGHTNESS, 128)
                cap.set(cv2.CAP_PROP_CONTRAST, 128)
                cap.set(cv2.CAP_PROP_SATURATION, 128)
                return {"success": True}

            elif command == "get_camera_info":
                w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                fps = int(cap.get(cv2.CAP_PROP_FPS)) or 30
                return {
                    "success": True,
                    "model": getattr(cam, "camera_type", "USB Webcam"),
                    "resolution": (w, h),
                    "fps": fps,
                }

            else:
                return {"success": False, "error": f"Unknown UVC command '{command}'"}

        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_supported_commands(self) -> List[str]:
        return [
            "set_property", "set_resolution", "set_auto_exposure",
            "set_auto_focus", "reset_defaults", "get_camera_info"
        ]


class UVCPlugin(CameraPlugin):
    """CameraPlugin for standard USB / UVC Webcams."""

    def __init__(self):
        self._last_cam = None

    @property
    def plugin_id(self) -> str:
        return "generic_uvc"

    @property
    def display_name(self) -> str:
        return "USB Webcam"

    @property
    def camera_role(self) -> CameraRole:
        return CameraRole.RGB

    def detect(self) -> List[CameraPluginMatch]:
        # Reads the shared device scan; does not touch hardware itself.
        matches = []
        for device in scan_video_devices():
            # Skip anything whose resolution is a FLIR thermal fingerprint —
            # those belong to a thermal plugin, not the generic webcam plugin.
            if device.resolution in THERMAL_RESOLUTIONS:
                continue

            name = device.name
            score = 80 if "brio" in name.lower() or "camera" in name.lower() else 50
            matches.append(CameraPluginMatch(
                plugin_id=self.plugin_id,
                device_index=device.index,
                name=name,
                resolution=device.resolution,
                score=score,
                extra={'camera_type': 'uvc'}
            ))
        return matches

    def create_backend(self, match: CameraPluginMatch) -> RGBCameraUVC:
        cam = RGBCameraUVC(
            device_id=match.device_index,
            resolution=match.resolution,
            fps=30
        )
        self._last_cam = cam
        return cam

    def create_sdk(self, match: CameraPluginMatch) -> UVCCameraSDK:
        sdk = UVCCameraSDK(camera_obj=self._last_cam)
        sdk.connect()
        return sdk

    def create_control_panel(self) -> Optional[QWidget]:
        from thermal_inspection.gui.camera_control.uvc_control_panel import UVCControlPanel
        return UVCControlPanel()

    def get_capabilities(self, match: CameraPluginMatch) -> CameraCapabilities:
        return CameraCapabilities(
            bit_depth=8,
            radiometric=False,
            resolutions=[(640, 480), (1280, 720), (1920, 1080), (2560, 1440), (3840, 2160)],
            max_fps=60.0,
            has_exposure_control=True,
            model=match.name or "USB Webcam"
        )

    def on_sdk_connected(self, sdk: CameraSDK, panel: Optional[QWidget]):
        if panel and hasattr(panel, "update_camera_info"):
            res = sdk.execute("get_camera_info")
            if res.get("success"):
                panel.update_camera_info(res)
