"""
OpenCV DirectShow backend for FLIR Boson thermal camera.

Provides 8-bit T-Linear processed thermal images with SDK control.
"""

import cv2
import numpy as np
from typing import Optional, Dict, Tuple
import logging

from camera_backends import ThermalBackend, BackendInitializationError
from flir_camera import FLIRCamera

logger = logging.getLogger(__name__)


class OpenCVThermalBackend(ThermalBackend):
    """
    OpenCV backend for FLIR Boson thermal camera.

    This backend uses the existing FLIRCamera class which provides:
    - 8-bit T-Linear processed thermal images via DirectShow
    - SDK control via COM port (FFC, AGC modes, etc.)
    - Runtime mode switching
    - FPA temperature reading

    Characteristics:
    - Bit depth: 8-bit (0-255)
    - Radiometric: No (visual AGC processing)
    - Quality: Excellent for visual inspection
    - Accuracy: Relative only (not absolute temperatures)
    - SDK Control: Yes (via Boson SDK)
    """

    def __init__(self, device_id: int = 1, com_port: str = 'COM6', enable_sdk: bool = True):
        """
        Initialize OpenCV thermal backend.

        Args:
            device_id: Video device index (default: 1)
            com_port: COM port for SDK control (default: 'COM6')
            enable_sdk: Enable SDK control features (default: True)
        """
        self.device_id = device_id
        self.com_port = com_port
        self.enable_sdk = enable_sdk
        self.camera: Optional[FLIRCamera] = None
        self._is_opened = False

    def is_available(self) -> bool:
        """
        Check if OpenCV can access the thermal camera.

        Returns:
            bool: True if camera is accessible via OpenCV
        """
        try:
            # Quick test with DirectShow backend
            test_cap = cv2.VideoCapture(self.device_id, cv2.CAP_DSHOW)
            available = test_cap.isOpened()
            test_cap.release()

            if available:
                logger.info(f"OpenCV thermal backend available on device {self.device_id}")
            else:
                logger.warning(f"OpenCV thermal backend not available on device {self.device_id}")

            return available
        except Exception as e:
            logger.error(f"Error checking OpenCV thermal backend availability: {e}")
            return False

    def open(self) -> bool:
        """
        Open thermal camera with OpenCV DirectShow backend.

        Returns:
            bool: True if camera opened successfully

        Raises:
            BackendInitializationError: If camera fails to open
        """
        try:
            logger.info(f"Opening OpenCV thermal backend (device {self.device_id}, COM {self.com_port})")

            # Create and initialize FLIR camera
            self.camera = FLIRCamera(
                device_id=self.device_id,
                com_port=self.com_port,
                enable_sdk=self.enable_sdk
            )

            # Open camera
            success = self.camera.open()

            if success:
                self._is_opened = True
                logger.info(f"✓ OpenCV thermal backend opened successfully")
                logger.info(f"  Resolution: {self.camera.width}x{self.camera.height}")
                logger.info(f"  SDK enabled: {self.enable_sdk}")
                logger.info(f"  FPS: {self.camera.fps}")
                return True
            else:
                logger.error("✗ OpenCV thermal backend failed to open")
                return False

        except Exception as e:
            logger.error(f"OpenCV thermal backend initialization error: {e}")
            raise BackendInitializationError(f"Failed to open OpenCV thermal backend: {e}")

    def read(self) -> Tuple[bool, Optional[np.ndarray]]:
        """
        Read 8-bit thermal frame.

        Returns:
            tuple: (success: bool, frame: np.ndarray with dtype=uint8 or None)
        """
        if not self._is_opened or not self.camera:
            logger.warning("Cannot read: OpenCV thermal backend not opened")
            return False, None

        try:
            success, frame = self.camera.read()
            return success, frame
        except Exception as e:
            logger.error(f"Error reading from OpenCV thermal backend: {e}")
            return False, None

    def release(self):
        """Release camera resources and cleanup."""
        if self.camera:
            logger.info("Releasing OpenCV thermal backend")
            self.camera.release()
            self.camera = None
        self._is_opened = False

    def is_opened(self) -> bool:
        """
        Check if camera is currently opened.

        Returns:
            bool: True if camera is opened
        """
        return self._is_opened and self.camera is not None

    def get_info(self) -> Dict:
        """
        Get backend information.

        Returns:
            dict: Backend information
        """
        info = {
            'backend': 'OpenCV DirectShow',
            'type': 'thermal',
            'bit_depth': 8,
            'radiometric': False,
            'resolution': self.get_resolution(),
            'features': [
                'T-Linear AGC processing',
                'SDK control (FFC, AGC modes)',
                'Runtime mode switching',
                'FPA temperature reading',
                'Excellent visual quality'
            ],
            'device_id': self.device_id,
            'com_port': self.com_port,
            'sdk_enabled': self.enable_sdk
        }

        if self.camera and self._is_opened:
            info['fps'] = self.camera.fps
            info['mode'] = 'radiometric' if self.camera.is_radiometric else 'non-radiometric'

        return info

    def get_resolution(self) -> Optional[Tuple[int, int]]:
        """
        Get current resolution.

        Returns:
            tuple: (width, height) or None
        """
        if self.camera and self._is_opened:
            return (self.camera.width, self.camera.height)
        return None

    def is_radiometric(self) -> bool:
        """
        Check if backend provides true radiometric data.

        Returns:
            bool: False (OpenCV backend provides AGC-processed 8-bit data)
        """
        return False

    def get_temperature_map(self) -> Optional[np.ndarray]:
        """
        Get temperature map (not available for 8-bit AGC backend).

        Returns:
            None: This backend doesn't provide true temperature maps
        """
        # OpenCV backend provides AGC-processed visual data, not absolute temperatures
        # Use 8-bit temperature estimator for pseudo-radiometric conversion if needed
        return None

    def supports_sdk_control(self) -> bool:
        """
        Check if SDK control is available.

        Returns:
            bool: True if SDK is enabled
        """
        return self.enable_sdk and self.camera is not None

    def get_fpa_temperature(self) -> Optional[float]:
        """
        Get Focal Plane Array temperature in Celsius.

        Returns:
            float: FPA temperature in Celsius, or None if not available
        """
        if not self.camera or not self.enable_sdk:
            return None

        try:
            result = self.camera.get_fpa_temperature()
            if result and len(result) >= 2:
                return result[1]  # FPA temp in Celsius
            return None
        except Exception as e:
            logger.warning(f"Failed to get FPA temperature: {e}")
            return None

    def get_camera(self) -> Optional[FLIRCamera]:
        """
        Get the underlying FLIRCamera instance for direct access.

        This allows access to SDK-specific features not in the backend interface.

        Returns:
            FLIRCamera: The camera instance, or None if not opened
        """
        return self.camera

    def __repr__(self) -> str:
        """String representation."""
        status = "opened" if self._is_opened else "closed"
        return f"OpenCVThermalBackend(device={self.device_id}, com={self.com_port}, {status})"
