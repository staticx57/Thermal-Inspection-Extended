"""
FLIR Tau 2 UVC Video Capture Driver.

Captures 16-bit Y16 radiometric video over UVC (via LVDS/USB bridge boards
such as TeAx ThermalCapture, GetThermal, Cypress FX3, or OEM USB adapters).

Features:
- Windows DirectShow (CAP_DSHOW) / Linux V4L2 (CAP_V4L2) backend selection
- FourCC 'Y16 ' format negotiation with CAP_PROP_CONVERT_RGB = 0
- Robust sanitization for 1D flattened arrays and YUYV container views
- Auto-alignment detection for 14-bit data packed into 16-bit buffers
- Advanced Radiometry T-Linear to Celsius conversion (0.04 K/count & 0.4 K/count)
"""
from __future__ import annotations

import logging
import platform
from typing import Optional, Tuple

import cv2
import numpy as np

logger = logging.getLogger(__name__)

TAU2_RESOLUTIONS = [
    (640, 512),   # Tau2 640
    (336, 256),   # Tau2 336
    (324, 256),   # Tau2 324
    (160, 128),   # Tau2 160
]


class Tau2Camera:
    """UVC Camera driver for FLIR Tau 2 thermal cameras."""

    def __init__(self, device_id: int = 0, resolution: Tuple[int, int] = (640, 512),
                 tlinear: bool = True, high_res: bool = True):
        self.device_id = device_id
        self.width, self.height = resolution
        self.tlinear = tlinear
        self.high_res = high_res
        self.cap: Optional[cv2.VideoCapture] = None
        self._is_opened = False
        self._fps = 30.0
        self._bit_depth = 16

    def open(self) -> bool:
        """Open UVC video stream for Tau 2."""
        try:
            logger.info(f"Opening Tau 2 UVC camera on device {self.device_id} ({self.width}x{self.height})...")

            # Choose DirectShow on Windows (MSMF truncates Y16 to 8-bit)
            if platform.system() == "Windows":
                self.cap = cv2.VideoCapture(self.device_id, cv2.CAP_DSHOW)
            else:
                self.cap = cv2.VideoCapture(self.device_id, cv2.CAP_V4L2)

            if not self.cap.isOpened():
                logger.error(f"Failed to open video device {self.device_id}")
                return False

            # Request 16-bit grayscale FOURCC
            self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'Y16 '))
            self.cap.set(cv2.CAP_PROP_CONVERT_RGB, 0)
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)

            actual_w = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            actual_h = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            if actual_w > 0 and actual_h > 0:
                self.width, self.height = actual_w, actual_h

            self._is_opened = True
            logger.info(f"[OK] Tau 2 camera opened successfully ({self.width}x{self.height})")
            return True

        except Exception as e:
            logger.error(f"Exception opening Tau 2 camera: {e}", exc_info=True)
            self.release()
            return False

    def is_opened(self) -> bool:
        return self._is_opened and self.cap is not None and self.cap.isOpened()

    def read(self) -> Tuple[bool, Optional[np.ndarray]]:
        """
        Grab and sanitize a raw frame from the Tau 2 camera.

        Returns:
            Tuple of (success, frame). Frame is typically 2D uint16 (or uint8 fallback).
        """
        if not self.is_opened():
            return False, None

        ret, raw_frame = self.cap.read()
        if not ret or raw_frame is None:
            return False, None

        frame = self._sanitize_frame(raw_frame)
        return True, frame

    def _sanitize_frame(self, raw_frame: np.ndarray) -> np.ndarray:
        """Handle OpenCV Y16 buffer representation quirks."""
        h, w = self.height, self.width

        # Case 1: Ideal 2D uint16 array
        if raw_frame.dtype == np.uint16 and raw_frame.ndim == 2:
            return self._normalize_14bit(raw_frame)

        # Case 2: Flattened 1D array bug
        if raw_frame.ndim == 1:
            if raw_frame.dtype == np.uint16:
                return self._normalize_14bit(raw_frame.reshape((h, w)))
            elif raw_frame.dtype == np.uint8 and raw_frame.size >= h * w * 2:
                return self._normalize_14bit(raw_frame[:h * w * 2].view(np.uint16).reshape((h, w)))

        # Case 3: 16-bit packed into (H, W, 2) uint8 YUYV buffer
        if raw_frame.ndim == 3 and raw_frame.shape[2] == 2 and raw_frame.dtype == np.uint8:
            return self._normalize_14bit(raw_frame.view(np.uint16).reshape((h, w)))

        # Case 4: Coerced to 3-channel 8-bit BGR
        if raw_frame.ndim == 3 and raw_frame.shape[2] == 3:
            self._bit_depth = 8
            return raw_frame[:, :, 0]  # take single channel grayscale

        return raw_frame

    def _normalize_14bit(self, frame_uint16: np.ndarray) -> np.ndarray:
        """Verify alignment of 14-bit data in 16-bit buffer."""
        # If bridge left-shifted by 2 bits, bits 0 and 1 are empty and values exceed 16383
        if np.max(frame_uint16) > 16383:
            return (frame_uint16 >> 2) & 0x3FFF
        return frame_uint16 & 0x3FFF

    def read_temperature_map(self) -> Optional[np.ndarray]:
        """
        Convert current frame to calibrated Celsius temperature map.

        Returns:
            float32 2D numpy array of temperatures in Celsius, or None.
        """
        if not self.tlinear:
            return None

        success, frame = self.read()
        if not success or frame is None or frame.dtype != np.uint16:
            return None

        scale = 0.04 if self.high_res else 0.40
        temp_kelvin = frame.astype(np.float32) * scale
        temp_celsius = temp_kelvin - 273.15
        return temp_celsius

    def set_tlinear(self, enabled: bool, high_res: bool = True):
        self.tlinear = enabled
        self.high_res = high_res

    def get_resolution(self) -> Tuple[int, int]:
        return (self.width, self.height)

    @property
    def fps(self) -> float:
        return self._fps

    def release(self):
        """Release camera resources."""
        if self.cap:
            try:
                self.cap.release()
            except Exception:
                pass
            self.cap = None
        self._is_opened = False
        logger.info(f"Tau 2 camera on device {self.device_id} released")
