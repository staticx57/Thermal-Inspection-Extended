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
        self._last_frame = None  # Store last captured frame

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

            # Store last frame for later access
            self._last_frame = frame

            return True, frame

        except Exception as e:
            logger.error(f"Error reading frame from flirpy: {e}")
            return False, None

    def read_thermal(self) -> Tuple[bool, Optional[np.ndarray]]:
        """
        Alias for read() - read thermal frame.

        Returns:
            tuple: (success: bool, frame: np.ndarray or None)
        """
        return self.read()

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

    def enable_radiometric(self, enable: bool = True):
        """
        Enable/disable radiometric mode.

        Note: flirpy backend is always radiometric (Y16 format).
        This method exists for API compatibility but does nothing.

        Args:
            enable: Ignored (always radiometric)
        """
        if not enable:
            logger.warning("flirpy backend is always radiometric - cannot disable")
        # flirpy is always in radiometric mode, nothing to do

    def is_radiometric_enabled(self) -> bool:
        """
        Check if radiometric features are currently enabled.

        Returns:
            True (flirpy always provides radiometric Y16 data)
        """
        return self._is_opened  # Always radiometric when camera is open

    def get_spot_temperature(self, x: int, y: int) -> Optional[float]:
        """
        Get temperature at a specific pixel coordinate.

        Args:
            x: X coordinate
            y: Y coordinate

        Returns:
            Temperature in Celsius, or None if not available
        """
        if not self._is_opened:
            return None

        ret, frame = self.read()
        if not ret or frame is None:
            return None

        try:
            h, w = frame.shape[:2]
            if 0 <= x < w and 0 <= y < h:
                # Y16 format: pixel_value = Kelvin * 100
                pixel_value = frame[y, x]
                temp_k = pixel_value / 100.0
                temp_c = temp_k - 273.15
                return float(temp_c)
            return None
        except Exception as e:
            logger.error(f"Error getting spot temperature: {e}")
            return None

    def get_temperature_frame(self) -> Optional[np.ndarray]:
        """
        Convert the last captured frame to temperature values.

        Returns:
            Temperature array (H, W) in Celsius (float32), or None if not available
        """
        return self.get_temperature_map()

    def get_roi_temperature_stats(self, roi_mask: np.ndarray) -> Optional[dict]:
        """
        Get temperature statistics for a region of interest.

        Args:
            roi_mask: Boolean mask (H, W) where True = inside ROI

        Returns:
            Dictionary with temperature statistics, or None if not available
        """
        if not self._is_opened:
            return None

        ret, frame = self.read()
        if not ret or frame is None:
            return None

        try:
            # Y16 format: pixel_value = Kelvin * 100
            temp_k = frame.astype(np.float32) / 100.0
            temp_c = temp_k - 273.15

            # Apply ROI mask
            if roi_mask.shape != temp_c.shape:
                logger.warning(f"ROI mask shape {roi_mask.shape} doesn't match frame shape {temp_c.shape}")
                return None

            roi_temps = temp_c[roi_mask]
            if len(roi_temps) == 0:
                return None

            min_temp = float(np.min(roi_temps))
            max_temp = float(np.max(roi_temps))

            # Find min/max locations
            min_loc = np.unravel_index(np.argmin(temp_c * roi_mask.astype(float) + (~roi_mask) * 1e6), temp_c.shape)
            max_loc = np.unravel_index(np.argmax(temp_c * roi_mask.astype(float) + (~roi_mask) * -1e6), temp_c.shape)

            return {
                'min_temp': min_temp,
                'max_temp': max_temp,
                'mean_temp': float(np.mean(roi_temps)),
                'median_temp': float(np.median(roi_temps)),
                'std_temp': float(np.std(roi_temps)),
                'min_location': (int(min_loc[1]), int(min_loc[0])),  # (x, y)
                'max_location': (int(max_loc[1]), int(max_loc[0]))   # (x, y)
            }
        except Exception as e:
            logger.error(f"Error computing ROI temperature stats: {e}")
            return None

    def __repr__(self) -> str:
        """String representation."""
        status = "opened" if self._is_opened else "closed"
        return f"FlirpyThermalBackend(status={status}, frames={self._frame_count})"

    # Additional compatibility methods for inspection_main.py

    def is_sdk_connected(self) -> bool:
        """
        Check if SDK is connected.

        Returns:
            False (flirpy uses UVC, not SDK - SDK control via separate wrapper)
        """
        return False

    def is_radiometric_capable(self) -> bool:
        """
        Check if camera supports radiometric mode.

        Returns:
            True (flirpy always provides Y16 radiometric data)
        """
        return True

    def get_actual_resolution(self) -> Tuple[int, int]:
        """
        Get actual camera resolution.

        Returns:
            tuple: (width, height)
        """
        return self.get_resolution()

    def get_last_raw_frame(self) -> Optional[np.ndarray]:
        """
        Get the last captured raw 16-bit frame.

        Returns:
            np.ndarray: Last captured frame (uint16), or None
        """
        return self._last_frame

    def get_frame_temperature_stats(self) -> Optional[dict]:
        """
        Get temperature statistics for the entire frame.

        Returns:
            Dictionary with temperature statistics, or None if not available
        """
        if self._last_frame is None:
            ret, frame = self.read()
            if not ret or frame is None:
                return None
        else:
            frame = self._last_frame

        try:
            # Y16 format: pixel_value = Kelvin * 100
            temp_k = frame.astype(np.float32) / 100.0
            temp_c = temp_k - 273.15

            min_temp = float(np.min(temp_c))
            max_temp = float(np.max(temp_c))

            # Find min/max locations
            min_loc = np.unravel_index(np.argmin(temp_c), temp_c.shape)
            max_loc = np.unravel_index(np.argmax(temp_c), temp_c.shape)

            return {
                'min_temp': min_temp,
                'max_temp': max_temp,
                'mean_temp': float(np.mean(temp_c)),
                'median_temp': float(np.median(temp_c)),
                'std_temp': float(np.std(temp_c)),
                'min_location': (int(min_loc[1]), int(min_loc[0])),  # (x, y)
                'max_location': (int(max_loc[1]), int(max_loc[0]))   # (x, y)
            }
        except Exception as e:
            logger.error(f"Error computing frame temperature stats: {e}")
            return None

    def get_camera_info(self) -> dict:
        """
        Get camera information.

        Returns:
            dict: Camera information
        """
        return self.get_info()

    # SDK stub methods - flirpy uses UVC, not SDK
    # These stubs prevent crashes when code tries to use SDK features

    @property
    def device_id(self) -> int:
        """Device ID (stub - returns 0 for flirpy)."""
        return 0

    @property
    def radiometric_converter(self):
        """Radiometric converter (stub - returns None for flirpy)."""
        return None

    @property
    def last_frame_16bit(self) -> Optional[np.ndarray]:
        """Last 16-bit frame (alias for _last_frame)."""
        return self._last_frame

    @property
    def sdk(self):
        """SDK object (stub - returns None for flirpy)."""
        return None

    def trigger_ffc(self) -> bool:
        """
        Trigger Flat Field Correction.

        Returns:
            False (not supported via flirpy - use SDK wrapper)
        """
        logger.warning("FFC trigger not available via flirpy backend - use SDK wrapper")
        return False

    def connect_sdk(self, com_port: str) -> bool:
        """
        Connect to SDK via COM port.

        Args:
            com_port: COM port string

        Returns:
            False (flirpy uses UVC, not SDK)
        """
        logger.warning("SDK connection not available via flirpy backend")
        return False

    def disconnect_sdk(self):
        """Disconnect SDK (no-op for flirpy)."""
        pass

    def set_gain_mode(self, mode: int) -> bool:
        """
        Set gain mode.

        Returns:
            False (not supported via flirpy)
        """
        logger.warning("Gain mode setting not available via flirpy backend")
        return False

    def set_ffc_mode(self, mode: int) -> bool:
        """
        Set FFC mode.

        Returns:
            False (not supported via flirpy)
        """
        logger.warning("FFC mode setting not available via flirpy backend")
        return False

    def spotmeter_enable(self, enabled: bool) -> bool:
        """
        Enable/disable spotmeter.

        Returns:
            False (not supported via flirpy)
        """
        logger.warning("Spotmeter control not available via flirpy backend")
        return False

    def spotmeter_set_statistics_mode(self, mode: int) -> bool:
        """
        Set spotmeter statistics mode.

        Returns:
            False (not supported via flirpy)
        """
        logger.warning("Spotmeter statistics mode not available via flirpy backend")
        return False

    def get_lens_temperature(self) -> Optional[float]:
        """
        Get lens temperature.

        Returns:
            None (not available via flirpy)
        """
        return None

    def get_shutter_temperature(self) -> Optional[float]:
        """
        Get shutter temperature.

        Returns:
            None (not available via flirpy)
        """
        return None

    def get_board_temperature(self) -> Optional[float]:
        """
        Get board temperature.

        Returns:
            None (not available via flirpy)
        """
        return None

    def set_color_lut(self, lut: int) -> bool:
        """
        Set color lookup table.

        Returns:
            False (not supported via flirpy)
        """
        logger.warning("Color LUT setting not available via flirpy backend")
        return False

    def set_agc_max_gain(self, gain: float) -> bool:
        """
        Set AGC max gain.

        Returns:
            False (not supported via flirpy)
        """
        logger.warning("AGC max gain setting not available via flirpy backend")
        return False

    def set_agc_gamma(self, gamma: float) -> bool:
        """
        Set AGC gamma.

        Returns:
            False (not supported via flirpy)
        """
        logger.warning("AGC gamma setting not available via flirpy backend")
        return False

    def set_agc_linearity(self, percent: float) -> bool:
        """
        Set AGC linearity.

        Returns:
            False (not supported via flirpy)
        """
        logger.warning("AGC linearity setting not available via flirpy backend")
        return False

    def set_detail_enhancement(self, dde: float) -> bool:
        """
        Set detail enhancement (DDE).

        Returns:
            False (not supported via flirpy)
        """
        logger.warning("Detail enhancement setting not available via flirpy backend")
        return False

    def enable_tlinear_mode(self) -> bool:
        """
        Enable TLinear mode.

        Returns:
            False (not supported via flirpy - already radiometric)
        """
        logger.warning("TLinear mode not needed for flirpy - already radiometric Y16")
        return False

    def set_temperature_range(self, min_celsius: float, max_celsius: float) -> bool:
        """
        Set temperature range for display.

        Args:
            min_celsius: Minimum temperature
            max_celsius: Maximum temperature

        Returns:
            False (not supported via flirpy)
        """
        logger.warning("Temperature range setting not available via flirpy backend")
        return False
