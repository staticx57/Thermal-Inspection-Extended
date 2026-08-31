"""
GigE Vision Backend Adapter.

Adapts GigECamera to the unified CameraBackend / ThermalBackend interface.
"""
from __future__ import annotations

import logging
from typing import Tuple, Optional, Dict, Any
import numpy as np

from thermal_inspection.cameras.camera_backends import ThermalBackend, RGBBackend
from .gige_camera import GigECamera

logger = logging.getLogger(__name__)


class GigEBackend(ThermalBackend, RGBBackend):
    """
    Unified GigE Vision backend adapter supporting both Thermal and RGB modalities.
    """

    def __init__(
        self,
        ip_address: str = "192.168.1.100",
        device_index: int = 0,
        stream_url: Optional[str] = None,
        is_thermal: bool = False
    ):
        self.ip_address = ip_address
        self.device_index = device_index
        self.stream_url = stream_url
        self._is_thermal = is_thermal
        self._camera = GigECamera(
            ip_address=ip_address,
            device_index=device_index,
            stream_url=stream_url,
            is_thermal=is_thermal
        )

    def is_available(self) -> bool:
        return True

    def open(self) -> bool:
        return self._camera.open()

    def read(self, flush_buffer: bool = False) -> Tuple[bool, Optional[np.ndarray]]:
        return self._camera.read(flush_buffer=flush_buffer)

    def get_temperature_map(self) -> Optional[np.ndarray]:
        return self._camera.read_temperature_map()

    def is_radiometric(self) -> bool:
        return self._is_thermal

    def supports_sdk_control(self) -> bool:
        return True

    def supports_color(self) -> bool:
        return not self._is_thermal

    def get_exposure(self) -> Optional[float]:
        return 10.0

    def set_exposure(self, exposure_ms: float) -> bool:
        return True

    def get_fpa_temperature(self) -> Optional[float]:
        return None

    def get_info(self) -> Dict[str, Any]:
        return {
            "backend": "GigE Vision",
            "type": "thermal" if self._is_thermal else "rgb",
            "ip_address": self.ip_address,
            "bit_depth": 16 if self._is_thermal else 8,
            "radiometric": self._is_thermal,
            "resolution": (self._camera.width, self._camera.height),
            "features": ["gvcp", "force_ip", "genicam", "jumbo_frames"]
        }

    def get_resolution(self) -> Tuple[int, int]:
        return (self._camera.width, self._camera.height)

    def is_opened(self) -> bool:
        return self._camera.is_opened()

    def release(self):
        self._camera.release()
