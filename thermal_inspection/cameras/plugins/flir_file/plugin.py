"""
FLIR file playback as a thermal "camera": active only when a recording has been chosen (--playback-file, or
set_source() from code); otherwise it never matches, so live hardware discovery is unaffected.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from thermal_inspection.cameras.flir_file_backend import FlirFileBackend
from thermal_inspection.cameras.plugin.camera_plugin import (
    CameraCapabilities, CameraPlugin, CameraPluginMatch, CameraRole, CameraSDK,
)
from thermal_inspection.sdk.flir_file_reader import SUPPORTED_EXTENSIONS

if TYPE_CHECKING:
    from PyQt6.QtWidgets import QWidget

logger = logging.getLogger(__name__)

_source_path: Optional[str] = None
SCORE = 1000          # a file you explicitly asked for beats any live camera


def set_source(path: Optional[str]):
    """Choose the recording to play (None clears it)."""
    global _source_path
    _source_path = os.path.abspath(path) if path else None


def get_source() -> Optional[str]:
    return _source_path


class FlirFileSDK(CameraSDK):
    def __init__(self, backend: Optional[FlirFileBackend] = None):
        self.backend = backend

    def connect(self) -> bool:
        return self.is_connected()

    def disconnect(self):
        pass

    def is_connected(self) -> bool:
        return self.backend is not None and self.backend.is_opened()

    def get_supported_commands(self) -> List[str]:
        return ["get_camera_info", "seek", "set_loop", "set_radiometric_mode"]

    def execute(self, command: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        params = params or {}
        b = self.backend
        if b is None:
            return {"success": False, "error": "No recording loaded"}
        if command == "get_camera_info":
            info = b.get_info()
            info["success"] = True
            info["radiometric_capable"] = True
            return info
        if command == "seek":
            b.seek(int(params.get("frame", 0)))
            return {"success": True, "frame": b.position}
        if command == "set_radiometric_mode":
            # a recording is always radiometric: enabling is a no-op success (the app sends it on connect)
            if params.get("enabled", True):
                return {"success": True}
            return {"success": False, "error": "A FLIR recording is always radiometric"}
        if command == "set_loop":
            b.loop = bool(params.get("loop", True))
            return {"success": True, "loop": b.loop}
        return {"success": False, "error": f"Unknown command '{command}'"}


class FlirFilePlugin(CameraPlugin):
    def __init__(self):
        self._last_backend: Optional[FlirFileBackend] = None

    @property
    def plugin_id(self) -> str:
        return "flir_file"

    @property
    def display_name(self) -> str:
        return "FLIR Recording"

    @property
    def camera_role(self) -> CameraRole:
        return CameraRole.THERMAL

    def detect(self) -> List[CameraPluginMatch]:
        path = get_source()
        if not path:
            return []
        if not os.path.isfile(path) or os.path.splitext(path)[1].lower() not in SUPPORTED_EXTENSIONS:
            logger.warning(f"FLIR recording not usable: {path}")
            return []
        return [CameraPluginMatch(plugin_id=self.plugin_id, device_index=0, name=os.path.basename(path),
                                  resolution=(640, 512), score=SCORE, extra={"path": path})]

    def create_backend(self, match: CameraPluginMatch) -> FlirFileBackend:
        self._last_backend = FlirFileBackend(match.extra.get("path") or get_source())
        return self._last_backend

    def create_sdk(self, match: CameraPluginMatch) -> FlirFileSDK:
        return FlirFileSDK(self._last_backend)

    def create_control_panel(self) -> Optional[QWidget]:
        return None

    def get_capabilities(self, match: CameraPluginMatch) -> CameraCapabilities:
        return CameraCapabilities(bit_depth=16, radiometric=True, resolutions=[match.resolution or (640, 512)],
                                  max_fps=30.0, model=match.name or "FLIR recording")
