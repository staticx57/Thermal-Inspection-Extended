"""
Tau2 Thermal Camera Backend.

Implements ThermalBackend for FLIR / Teledyne Tau 2 thermal cameras over UVC.
"""
from __future__ import annotations

import logging
from typing import Optional, Dict, Tuple
import numpy as np

from thermal_inspection.cameras.camera_backends import ThermalBackend, BackendInitializationError
from thermal_inspection.cameras.tau2_camera import Tau2Camera

logger = logging.getLogger(__name__)


class Tau2Backend(ThermalBackend):
    """
    ThermalBackend implementation for FLIR Tau 2 cameras.
    """

    def __init__(self, device_id: int = 0, resolution: Tuple[int, int] = (640, 512),
                 tlinear: bool = True, high_res: bool = True):
        self.device_id = device_id
        self.resolution = resolution
        self.tlinear = tlinear
        self.high_res = high_res
        self.camera: Optional[Tau2Camera] = None
        self._is_opened = False

    def is_available(self) -> bool:
        """Check if Tau 2 camera is accessible."""
        try:
            import cv2
            import platform
            backend = cv2.CAP_DSHOW if platform.system() == "Windows" else cv2.CAP_V4L2
            cap = cv2.VideoCapture(self.device_id, backend)
            available = cap.isOpened()
            cap.release()
            return available
        except Exception as e:
            logger.debug(f"Error checking Tau2 backend availability: {e}")
            return False

    def open(self) -> bool:
        """Open Tau 2 camera backend."""
        try:
            logger.info(f"Opening Tau 2 thermal backend (device {self.device_id})...")
            self.camera = Tau2Camera(
                device_id=self.device_id,
                resolution=self.resolution,
                tlinear=self.tlinear,
                high_res=self.high_res
            )
            success = self.camera.open()
            if success:
                self._is_opened = True
                logger.info("[OK] Tau 2 thermal backend opened successfully")
                return True
            else:
                logger.error("Failed to open Tau 2 camera")
                return False
        except Exception as e:
            logger.error(f"Tau 2 backend initialization error: {e}")
            raise BackendInitializationError(f"Failed to open Tau 2 backend: {e}")

    def read(self) -> Tuple[bool, Optional[np.ndarray]]:
        """Grab a frame."""
        if not self._is_opened or not self.camera:
            return False, None
        return self.camera.read()

    def release(self):
        """Release camera."""
        if self.camera:
            self.camera.release()
            self.camera = None
        self._is_opened = False

    def is_opened(self) -> bool:
        return self._is_opened and self.camera is not None and self.camera.is_opened()

    def get_info(self) -> Dict:
        """Get backend information dict."""
        res = self.get_resolution()
        return {
            'backend': 'Tau 2 UVC',
            'type': 'thermal',
            'bit_depth': 16 if self.tlinear else 14,
            'radiometric': self.is_radiometric(),
            'resolution': res,
            'features': [
                '14-bit / 16-bit Y16 capture',
                'Advanced Radiometry T-Linear decoding',
                'CCI Serial Control (57600 baud)',
                'FFC / NUC shutter cycle'
            ],
            'device_id': self.device_id,
            'tlinear': self.tlinear,
            'high_res': self.high_res,
        }

    def get_resolution(self) -> Optional[Tuple[int, int]]:
        if self.camera and self._is_opened:
            return self.camera.get_resolution()
        return self.resolution

    def is_radiometric(self) -> bool:
        return self.tlinear

    def get_temperature_map(self) -> Optional[np.ndarray]:
        """Returns float32 temperature map in Celsius."""
        if not self.camera or not self._is_opened:
            return None
        return self.camera.read_temperature_map()

    def supports_sdk_control(self) -> bool:
        return True

    def get_fpa_temperature(self) -> Optional[float]:
        # FPA temperature on Tau2 is retrieved via Tau2Serial SDK
        return None
