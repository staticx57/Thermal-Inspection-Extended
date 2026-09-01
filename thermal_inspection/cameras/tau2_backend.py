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
                 tlinear: bool = True, high_res: bool = True,
                 raw_mode: bool = False, byte_order: str = 'swap'):
        self.device_id = device_id
        self.resolution = resolution
        self.tlinear = tlinear
        self.high_res = high_res
        # See Tau2Camera's docstring for what these select - the confirmed-
        # working default onboard-colorized BGR passthrough (raw_mode=False)
        # vs. a genuine raw Y16 sensor stream.
        self.raw_mode = raw_mode
        self.byte_order = byte_order
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
                high_res=self.high_res,
                raw_mode=self.raw_mode,
                byte_order=self.byte_order
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

    def is_radiometric_capable(self) -> bool:
        # app.py's spot-meter unit-symbol logic checks this exact name
        # (matching FLIRBosonCamera's method), not is_radiometric() - without
        # it, Tau2 spot readings always showed the "C" default regardless of
        # the user's selected display unit.
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

    def get_spot_temperature(self, x: int, y: int) -> Optional[float]:
        """
        Get calibrated temperature (Celsius) at a pixel, from the current
        T-Linear frame. Without this, app.py's spot-meter code finds no
        get_spot_temperature on this backend and silently falls back to an
        AGC estimate/raw display for a camera that already has real data.
        """
        temp_map = self.get_temperature_map()
        if temp_map is None:
            return None
        h, w = temp_map.shape[:2]
        if not (0 <= x < w and 0 <= y < h):
            return None
        return float(temp_map[y, x])

    def get_roi_temperature_stats(self, roi_mask: np.ndarray) -> Optional[Dict]:
        """
        Get temperature statistics for a region of interest.

        Args:
            roi_mask: Boolean mask (H, W) where True = inside ROI

        Returns:
            Dict with min/max/mean/std_temp and min/max_location, or None.
        """
        temp_map = self.get_temperature_map()
        if temp_map is None:
            return None
        roi_values = temp_map[roi_mask]
        if roi_values.size == 0:
            return None
        min_idx = np.unravel_index(np.argmin(np.where(roi_mask, temp_map, np.inf)), temp_map.shape)
        max_idx = np.unravel_index(np.argmax(np.where(roi_mask, temp_map, -np.inf)), temp_map.shape)
        return {
            'min_temp': float(roi_values.min()),
            'max_temp': float(roi_values.max()),
            'mean_temp': float(roi_values.mean()),
            'std_temp': float(roi_values.std()),
            'min_location': (int(min_idx[1]), int(min_idx[0])),
            'max_location': (int(max_idx[1]), int(max_idx[0])),
        }
