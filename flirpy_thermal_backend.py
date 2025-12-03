"""
flirpy-based Thermal Backend

Provides 16-bit Y16 radiometric capture from FLIR Boson using the flirpy library.
Works with default UVC driver (no WinUSB installation required).
"""

import logging
import numpy as np
from typing import Optional, Tuple

from camera_backends import ThermalBackend

logger = logging.getLogger(__name__)

try:
    from flirpy.camera.boson import Boson
    FLIRPY_AVAILABLE = True
except ImportError:
    FLIRPY_AVAILABLE = False
    logger.warning("flirpy library not available. Install with: pip install flirpy")


class FlirpyThermalBackend(ThermalBackend):
    """
    flirpy-based backend for FLIR Boson thermal camera.

    Features:
    - 16-bit Y16 radiometric capture
    - Works with default UVC driver
    - True absolute temperatures (±2°C accuracy)
    - Simple, reliable implementation

    Note: SDK control (FFC, AGC, etc.) should be done via separate
    BosonSDK wrapper using COM port when camera is not actively capturing.
    """

    def __init__(self):
        """Initialize flirpy backend."""
        self.camera = None
        self._is_opened = False
        self._frame_count = 0

    def is_available(self) -> bool:
        """
        Check if flirpy library is available and Boson can be detected.

        Returns:
            bool: True if backend is available
        """
        if not FLIRPY_AVAILABLE:
            logger.debug("flirpy library not installed")
            return False

        try:
            # Try to create camera instance (quick check)
            test_cam = Boson()
            test_cam.close()
            return True
        except Exception as e:
            logger.debug(f"Boson not available via flirpy: {e}")
            return False

    def open(self) -> bool:
        """
        Open FLIR Boson camera via flirpy.

        Returns:
            bool: True if successful
        """
        if not FLIRPY_AVAILABLE:
            logger.error("flirpy library not installed")
            return False

        try:
            logger.info("Opening Boson camera via flirpy...")
            # IMPORTANT: Do not pass port parameter (defaults to None)
            # This prevents flirpy from trying to open the COM port
            # Our separate BosonSDK wrapper will handle COM port communication
            self.camera = Boson()
            self._is_opened = True
            self._frame_count = 0

            logger.info("✓ Boson camera opened via flirpy")
            return True

        except Exception as e:
            logger.error(f"Failed to open Boson via flirpy: {e}")
            self.camera = None
            self._is_opened = False
            return False

    def read(self) -> Tuple[bool, Optional[np.ndarray]]:
        """
        Read 16-bit Y16 frame from camera.

        Returns:
            tuple: (success: bool, frame: np.ndarray or None)
                  Frame is uint16 with Y16 format (pixel_value = Kelvin × 100)
        """
        if not self._is_opened or not self.camera:
            logger.warning("Cannot read: camera not opened")
            return False, None

        try:
            frame = self.camera.grab()
            self._frame_count += 1

            if frame is None:
                logger.warning("Received None frame from flirpy")
                return False, None

            # Verify frame is uint16
            if frame.dtype != np.uint16:
                logger.warning(f"Expected uint16 frame, got {frame.dtype}")

            return True, frame

        except Exception as e:
            logger.error(f"Error reading frame from flirpy: {e}")
            return False, None

    def release(self):
        """Close camera and release resources."""
        if self.camera:
            try:
                logger.info(f"Closing flirpy camera (captured {self._frame_count} frames)")
                self.camera.close()
            except Exception as e:
                logger.warning(f"Error closing camera: {e}")
            finally:
                self.camera = None
                self._is_opened = False
                self._frame_count = 0

    def is_opened(self) -> bool:
        """
        Check if camera is currently opened.

        Returns:
            bool: True if opened
        """
        return self._is_opened and self.camera is not None

    def get_info(self) -> dict:
        """
        Get backend information.

        Returns:
            dict: Backend information
        """
        return {
            'backend': 'flirpy',
            'library': 'flirpy 0.3.0',
            'bit_depth': 16,
            'radiometric': True,
            'resolution': self.get_resolution(),
            'format': 'Y16 (uint16)',
            'driver': 'UVC (default)',
            'features': [
                '16-bit Y16',
                'True radiometric',
                'UVC driver',
                'No WinUSB needed'
            ]
        }

    def get_resolution(self) -> Tuple[int, int]:
        """
        Get camera resolution.

        Returns:
            tuple: (width, height)
        """
        if self._is_opened and self.camera:
            try:
                # Try to get actual resolution from a frame
                ret, frame = self.read()
                if ret and frame is not None:
                    return (frame.shape[1], frame.shape[0])  # (width, height)
            except:
                pass

        # Default Boson 320 resolution
        return (320, 256)

    # Thermal-specific methods

    def is_radiometric(self) -> bool:
        """
        Check if backend provides true radiometric data.

        Returns:
            bool: True (flirpy provides Y16 radiometric data)
        """
        return True

    def get_temperature_map(self) -> Optional[np.ndarray]:
        """
        Get temperature map in Celsius.

        Converts Y16 format to temperature using:
        temp_celsius = (pixel_value / 100.0) - 273.15

        Returns:
            np.ndarray: Temperature map in Celsius (float32), or None on error
        """
        ret, frame = self.read()

        if not ret or frame is None:
            return None

        try:
            # Y16 format: pixel_value = Kelvin × 100
            temp_k = frame.astype(np.float32) / 100.0
            temp_c = temp_k - 273.15
            return temp_c

        except Exception as e:
            logger.error(f"Error converting to temperature: {e}")
            return None

    def supports_sdk_control(self) -> bool:
        """
        Check if SDK control is supported.

        Returns:
            bool: True (via separate BosonSDK wrapper using COM port)

        Note: SDK control should be done via BosonSDK wrapper when
        camera is not actively capturing, as both cannot access
        the camera simultaneously.
        """
        return True

    def get_fpa_temperature(self) -> Optional[float]:
        """
        Get FPA (Focal Plane Array) temperature.

        Returns:
            float: FPA temperature in Celsius, or None

        Note: This requires SDK access. If using this backend,
        use a separate BosonSDK instance to read FPA temperature
        when camera is not capturing.
        """
        logger.warning("FPA temperature requires SDK access via COM port")
        logger.warning("Use BosonSDK wrapper separately when not capturing")
        return None

    def __repr__(self) -> str:
        """String representation."""
        status = "opened" if self._is_opened else "closed"
        return f"FlirpyThermalBackend(status={status}, frames={self._frame_count})"
