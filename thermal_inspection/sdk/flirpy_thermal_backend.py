"""
flirpy-based Thermal Backend, Single Native Connection

Provides 16-bit Y16 radiometric capture from FLIR Boson using the flirpy
library, and drives all camera control (T-Linear mode, FFC, gain, palette,
emissivity, atmospheric compensation) over that SAME connection.

This used to be a dual-path design: flirpy for video, plus a second,
independent connection to the proprietary vendor BosonSDK for control -
opened briefly at startup to configure T-Linear mode, then closed so
flirpy could have the port, per the "Sequential Access Pattern" the old
open() used. That pattern only covered startup; anything opening a
*second* SDK connection later (the plugin's own control-panel SDK, or
this class's own control methods once self._sdk was discarded) collided
with flirpy's connection - confirmed live: flirpy.camera.core.Core.
connect() opens serial.Serial() in Boson.__init__ and holds it
exclusively for the object's whole life, so a second connection to the
same COM port always failed with "Failed to open port #6 with error
255!" for as long as this backend was streaming.

flirpy's own Boson class only implements a subset of the Boson CCI
command set (FFC, basic info, FPA temp, averager) - not gain mode,
palette, or radiometric/environmental compensation. Rather than keep
the vendor SDK around as a second connection for those,
BosonNative (thermal_inspection.sdk.boson_flirpy_ext) extends flirpy's
Boson with the missing commands using the exact same _send_packet/
_decode_packet primitives flirpy already uses - so ONE connection now
does everything, and there is no second owner of the COM port to
conflict with the control panel (see BosonPlugin.create_sdk(), which
delegates to this backend's own methods instead of opening its own
connection when this backend is active).
"""

import logging
import numpy as np
from typing import Optional, Tuple

from thermal_inspection.cameras.camera_backends import ThermalBackend
from thermal_inspection.sdk.boson_flirpy_ext import BosonNative

logger = logging.getLogger(__name__)

try:
    import flirpy
    FLIRPY_AVAILABLE = True
except ImportError:
    FLIRPY_AVAILABLE = False


class FlirpyThermalBackend(ThermalBackend):
    """
    flirpy-based backend for FLIR Boson thermal camera, single native connection.

    Features:
    - 16-bit Y16 radiometric capture via flirpy (UVC)
    - Full camera control (T-Linear, FFC, gain, palette, environmental
      compensation) over that same connection - see module docstring.
    - True absolute temperatures (±2°C accuracy when T-Linear enabled)
    """

    def __init__(self, com_port: str = 'COM7', auto_configure: bool = True):
        """
        Initialize flirpy backend.

        Args:
            com_port: COM port for the camera (e.g., 'COM7')
            auto_configure: If True, automatically configure T-Linear mode on open
        """
        self.camera: Optional[BosonNative] = None
        self._is_opened = False
        self._frame_count = 0
        self._last_frame = None  # Store last captured frame

        self._com_port = com_port
        self._auto_configure = auto_configure
        self._sdk_connected = False
        self._tlinear_enabled = False

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
            test_cam = BosonNative()
            test_cam.close()
            return True
        except Exception as e:
            logger.debug(f"Boson not available via flirpy: {e}")
            return False

    def open(self) -> bool:
        """
        Open FLIR Boson camera via flirpy, single native connection.

        flirpy's Boson.__init__ opens the serial connection but does not
        touch video (setup_video()/grab() are separate, lazy calls) - so
        T-Linear mode is configured here, on the one connection, strictly
        before the first grab() triggers video setup. See module docstring
        for why this replaced the old two-connection open/close dance.

        Returns:
            bool: True if successful
        """
        if not FLIRPY_AVAILABLE:
            logger.error("flirpy library not installed")
            return False

        try:
            logger.info(f"Opening Boson camera via flirpy (Port: {self._com_port})...")

            self.camera = BosonNative(port=self._com_port)

            # Verify serial connection
            try:
                temp = self.camera.get_fpa_temperature()
                logger.info(f"✓ Serial connection established (FPA Temp: {temp:.1f}°C)")
                self._sdk_connected = True
            except Exception as e:
                logger.warning(f"⚠ Serial connection issue: {e}")
                self._sdk_connected = False

            # Configure T-Linear mode before any frame is grabbed.
            if self._auto_configure and self._sdk_connected:
                self._configure_tlinear_native()

            self._is_opened = True
            self._frame_count = 0
            logger.info("✓ Boson camera opened via flirpy")

            # Run FFC for clean calibration
            if self._sdk_connected:
                try:
                    self.camera.do_ffc()
                    logger.info("FFC triggered")
                except Exception as e:
                    logger.warning(f"FFC failed: {e}")

                # Verify T-Linear mode is working
                if self._tlinear_enabled:
                    import time
                    time.sleep(0.3)  # Allow frames to stabilize after FFC
                    if self._verify_tlinear():
                        logger.info("✓ Radiometric output verified")
                    else:
                        logger.warning("⚠ T-Linear verification failed - may be in AGC mode")

            return True

        except Exception as e:
            logger.error(f"Failed to open Boson via flirpy: {e}")
            self.camera = None
            self._is_opened = False
            return False

    def _configure_tlinear_native(self):
        """
        Configure camera for T-Linear radiometric output, on the connection
        flirpy already has open. Must run before the first grab() (which
        lazily calls setup_video()) - open() guarantees that ordering.
        """
        try:
            self.camera.set_usb_video_ir16_mode(2)
            logger.info("✓ T-Linear mode enabled (USB IR16 Mode = 2)")
            self._tlinear_enabled = True
        except Exception as e:
            logger.error(f"Error setting T-Linear mode: {e}")
            self._tlinear_enabled = False

        try:
            self.camera.set_radiometry_enable(True)
        except Exception as e:
            logger.debug(f"Radiometry enable failed (may not be supported): {e}")

    def _configure_tlinear(self):
        """Legacy method - now just logs warning if called directly."""
        logger.warning("_configure_tlinear called but flirpy already owns COM port")
        logger.warning("T-Linear should be configured via _configure_tlinear_native()")

    def _verify_tlinear(self) -> bool:
        """Verify T-Linear mode is active by checking frame properties.

        T-Linear Y16 format: pixel values represent Kelvin * 100
        Expected room temp range: 20000-35000 (~0°C to 75°C)

        Returns:
            bool: True if T-Linear appears to be working correctly
        """
        try:
            ret, frame = self.read()
            if not ret or frame is None:
                logger.warning("⚠ Cannot verify T-Linear: no frame available")
                return False

            # Must be 16-bit
            if frame.dtype != np.uint16:
                logger.warning(f"⚠ Expected uint16, got {frame.dtype} - not T-Linear")
                return False

            min_val = int(frame.min())
            max_val = int(frame.max())

            # T-Linear Y16 range check (Kelvin * 100)
            # Typical room temps: 20000-35000 (approx -73°C to 77°C covers most cases)
            if 20000 < min_val < 35000 and 25000 < max_val < 40000:
                temp_min = (min_val / 100.0) - 273.15
                temp_max = (max_val / 100.0) - 273.15
                logger.info(f"✓ T-Linear verified: {temp_min:.1f}°C to {temp_max:.1f}°C")
                return True

            # AGC/raw 14-bit range: typically 0-16383
            if max_val < 20000:
                logger.warning(f"⚠ Likely 14-bit AGC data (range: {min_val}-{max_val})")
                return False

            # Unusual range but could still be valid
            temp_min = (min_val / 100.0) - 273.15
            temp_max = (max_val / 100.0) - 273.15
            logger.info(f"Frame range: {min_val}-{max_val} ({temp_min:.1f}°C to {temp_max:.1f}°C)")
            return True

        except Exception as e:
            logger.error(f"T-Linear verification failed: {e}")
            return False

    def close(self):
        """Close camera."""
        self.release()

    def _connect_sdk(self) -> bool:
        """Deprecated - SDK connection handled by flirpy."""
        return self._sdk_connected

    def disconnect_sdk(self):
        """Deprecated - SDK connection handled by flirpy."""
        pass

    def reconnect_sdk(self, com_port: str = None) -> bool:
        """Reconnect camera with new settings."""
        if com_port:
            self._com_port = com_port
        self.release()
        return self.open()

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
        """Close camera and release resources (including SDK)."""
        # Close flirpy camera
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

        # Disconnect SDK
        self.disconnect_sdk()
        self._tlinear_enabled = False

    def is_opened(self) -> bool:
        """
        Check if camera is currently opened.

        Returns:
            bool: True if opened
        """
        return self._is_opened and self.camera is not None

    def get_info(self) -> dict:
        """
        Get backend information including SDK status.

        Returns:
            dict: Backend information
        """
        info = {
            'backend': 'flirpy',
            'library': 'flirpy (native, single connection)',
            'bit_depth': 16,
            'radiometric': True,
            'resolution': self.get_resolution(),
            'format': 'Y16 (uint16)',
            'driver': 'UVC + COM, one flirpy connection',
            'sdk_connected': self._sdk_connected,
            'tlinear_enabled': self._tlinear_enabled,
            'com_port': self._com_port,
            'features': [
                '16-bit Y16',
                'True radiometric',
                'UVC driver',
                'Native control via same connection',
                'FFC trigger',
                'T-Linear mode'
            ]
        }

        if self._sdk_connected and self.camera is not None:
            try:
                info['serial_number'] = self.camera.get_camera_serial()
            except Exception as e:
                logger.debug(f"Could not read camera serial for get_info(): {e}")
            try:
                gain_mode = self.camera.get_gain_mode()
                if gain_mode is not None:
                    info['gain_mode'] = gain_mode
            except Exception as e:
                logger.debug(f"Could not read gain mode for get_info(): {e}")
            try:
                info['firmware_version'] = self.camera.get_firmware_revision()
            except Exception as e:
                logger.debug(f"Could not read firmware version for get_info(): {e}")

        return info

    def get_resolution(self) -> Tuple[int, int]:
        """
        Get camera resolution.

        Returns:
            tuple: (width, height)
        """
        # Prefer the already-captured frame over a fresh read() - see
        # get_spot_temperature() for why a second grab() here would race
        # the background capture thread.
        if self._last_frame is not None:
            return (self._last_frame.shape[1], self._last_frame.shape[0])

        if self._is_opened and self.camera:
            try:
                ret, frame = self.read()
                if ret and frame is not None:
                    return (frame.shape[1], frame.shape[0])  # (width, height)
            except Exception:
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

        Uses the already-captured last frame - see get_spot_temperature()
        for why calling read() again here is wrong.
        """
        frame = self._last_frame

        if frame is None:
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
            bool: True (control methods on this class use the same native
                connection as video capture - see module docstring)
        """
        return True

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

        Uses the already-captured last frame rather than calling read()
        again - this is called from the main-thread frame loop once a spot
        meter exists, and a second grab() there raced the background
        ThreadedCameraCapture thread's own continuous grab() calls on the
        same cv2.VideoCapture, blocking the GUI thread for up to a full
        camera period (confirmed live: placing a spot meter on the 9Hz
        radiometric Boson visibly coupled the whole UI to that rate;
        removing it restored normal responsiveness).
        """
        if not self._is_opened:
            return None

        frame = self._last_frame
        if frame is None:
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
        if self._last_frame is None:
            return None

        try:
            # Y16 format: pixel_value = Kelvin × 100
            temp_k = self._last_frame.astype(np.float32) / 100.0
            temp_c = temp_k - 273.15
            return temp_c

        except Exception as e:
            logger.error(f"Error converting to temperature: {e}")
            return None

    def get_roi_temperature_stats(self, roi_mask: np.ndarray) -> Optional[dict]:
        """
        Get temperature statistics for a region of interest.

        Args:
            roi_mask: Boolean mask (H, W) where True = inside ROI

        Returns:
            Dictionary with temperature statistics, or None if not available

        Uses the already-captured last frame - see get_spot_temperature()
        for why calling read() again here is wrong.
        """
        if not self._is_opened:
            return None

        frame = self._last_frame
        if frame is None:
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
        """
        Get the native camera connection for direct control.

        There is only one connection now (see module docstring) - this
        returns the same BosonNative instance backing video capture.
        """
        return self.camera

    # =========================================================================
    # CAMERA CONTROL - all over the one native flirpy connection
    # =========================================================================

    def trigger_ffc(self) -> bool:
        """
        Trigger Flat Field Correction via SDK.

        FFC corrects for non-uniformity in the sensor response.
        Recommended after temperature changes or every 10-15 minutes.

        Returns:
            bool: True if FFC completed successfully
        """
        if not self._sdk_connected or self.camera is None:
            logger.warning("Cannot trigger FFC: SDK not connected")
            return False

        try:
            # Use flirpy's Boson class do_ffc method
            self.camera.do_ffc()
            logger.info("✓ FFC triggered successfully")
            return True
        except Exception as e:
            logger.error(f"FFC failed: {e}")
            return False

    def connect_sdk(self, com_port: str) -> bool:
        """
        Connect to SDK via COM port (reconnect with new port).

        Args:
            com_port: COM port string (e.g., 'COM7')

        Returns:
            bool: True if connected
        """
        self._com_port = com_port
        return self.reconnect_sdk(com_port)

    def get_gain_mode(self) -> Optional[int]:
        """Get gain mode: 0=HIGH, 1=LOW, 2=AUTO, or None if unavailable."""
        if not self._sdk_connected or self.camera is None:
            return None
        try:
            return self.camera.get_gain_mode()
        except Exception as e:
            logger.error(f"Error getting gain mode: {e}")
            return None

    def set_gain_mode(self, mode: int) -> bool:
        """
        Set gain mode.

        Args:
            mode: 0=HIGH (-40 to 120°C), 1=LOW (up to 400°C), 2=AUTO

        Returns:
            bool: True if successful
        """
        if not self._sdk_connected or self.camera is None:
            logger.warning("Cannot set gain mode: camera not connected")
            return False

        try:
            self.camera.set_gain_mode(mode)
            return True
        except Exception as e:
            logger.error(f"Error setting gain mode: {e}")
            return False

    def set_ffc_mode(self, mode: int) -> bool:
        """
        Set FFC mode.

        Args:
            mode: 0=MANUAL, 1=AUTO, 2=EXTERNAL

        Returns:
            bool: True if successful
        """
        if not self._sdk_connected or self.camera is None:
            logger.warning("Cannot set FFC mode: camera not connected")
            return False

        try:
            self.camera.set_ffc_mode(mode)
            return True
        except Exception as e:
            logger.error(f"Error setting FFC mode: {e}")
            return False

    def get_fpa_temperature(self) -> Optional[float]:
        """
        Get FPA (Focal Plane Array) temperature in Celsius.

        Returns:
            float: FPA temperature in Celsius, or None if unavailable
        """
        if self._is_opened and self.camera:
            try:
                temp = self.camera.get_fpa_temperature()
                if temp is not None:
                    return temp
            except Exception as e:
                logger.debug(f"flirpy FPA temperature read failed: {e}")

        return None

    def get_lens_temperature(self) -> Optional[float]:
        """
        Get lens housing temperature.

        Not yet implemented natively (see module docstring) - the CCI
        commands for this exist but weren't ported when the vendor SDK's
        second connection was removed. Returns None rather than a stale
        or fabricated reading.
        """
        return None

    def get_shutter_temperature(self) -> Optional[float]:
        """
        Get shutter housing temperature.

        Not yet implemented natively - see get_lens_temperature().
        """
        return None

    def get_board_temperature(self) -> Optional[float]:
        """
        Get board temperature (not directly available via SDK).

        Returns:
            None (use FPA temperature instead)
        """
        # Board temperature not directly exposed in SDK
        # Return FPA as proxy
        return self.get_fpa_temperature()

    def set_color_lut(self, lut: int) -> bool:
        """
        Set color lookup table (palette).

        Args:
            lut: 0=WHITE_HOT, 1=BLACK_HOT, 2=RAINBOW, 4=IRONBOW, etc.
                 (FLR_COLORLUT_ID_E value)

        Returns:
            bool: True if successful
        """
        if not self._sdk_connected or self.camera is None:
            logger.warning("Cannot set color LUT: camera not connected")
            return False

        try:
            self.camera.set_color_lut_id(lut)
            return True
        except Exception as e:
            logger.error(f"Error setting color LUT: {e}")
            return False

    def set_emissivity(self, emissivity: float) -> bool:
        """
        Set target emissivity for accurate temperature measurement.

        Args:
            emissivity: 0.01-1.0 (1.0 = perfect blackbody) - converted to
                the percent (0-100) the camera actually expects; see
                boson_flirpy_ext.py.

        Returns:
            bool: True if successful
        """
        if self.camera is None:
            logger.warning("Cannot set emissivity: Camera not connected")
            return False

        try:
            self.camera.set_emissivity_pct(max(0.01, min(1.0, emissivity)) * 100.0)
            return True
        except Exception as e:
            logger.error(f"Error setting emissivity: {e}")
            return False

    def get_emissivity(self) -> Optional[float]:
        """
        Get current emissivity setting.

        Returns:
            float: Current emissivity (0.01-1.0), or None if unavailable
        """
        if self.camera is None:
            return None

        try:
            pct = self.camera.get_emissivity_pct()
            return pct / 100.0 if pct is not None else None
        except Exception as e:
            logger.error(f"Error getting emissivity: {e}")
            return None

    def set_atmospheric_temperature(self, temp_celsius: float) -> bool:
        """
        Set atmospheric temperature for compensation.

        Args:
            temp_celsius: Temperature in Celsius

        Returns:
            bool: True if successful
        """
        if self.camera is None:
            return False

        try:
            self.camera.set_atmospheric_temperature_k(temp_celsius + 273.15)
            return True
        except Exception as e:
            logger.error(f"Error setting atmospheric temp: {e}")
            return False

    def set_atmospheric_transmission(self, transmission: float) -> bool:
        """
        Set atmospheric transmission coefficient.

        Args:
            transmission: 0.01-1.0 - converted to percent; see set_emissivity.

        Returns:
            bool: True if successful
        """
        if self.camera is None:
            return False

        try:
            self.camera.set_atmospheric_transmission_pct(max(0.01, min(1.0, transmission)) * 100.0)
            return True
        except Exception as e:
            logger.error(f"Error setting atmospheric transmission: {e}")
            return False

    def get_calibration_info(self) -> dict:
        """
        Get all radiometric calibration parameters.

        Not yet implemented natively (global gain/offset, lens F-number/
        transmission aren't ported - see module docstring). Returns {}
        rather than a fabricated result.
        """
        return {}

    def spotmeter_enable(self, enabled: bool) -> bool:
        """
        Enable/disable hardware spotmeter.

        Returns:
            bool: True if successful (not fully implemented in SDK wrapper)
        """
        logger.info(f"Spotmeter {'enabled' if enabled else 'disabled'} (software mode)")
        return True  # Software spotmeter always works

    def spotmeter_set_statistics_mode(self, mode: int) -> bool:
        """Set spotmeter statistics mode (placeholder)."""
        return True

    def set_agc_max_gain(self, gain: float) -> bool:
        """AGC max gain (not needed in radiometric mode)."""
        logger.info("AGC settings not applicable in T-Linear radiometric mode")
        return True

    def set_agc_gamma(self, gamma: float) -> bool:
        """AGC gamma (not needed in radiometric mode)."""
        return True

    def set_agc_linearity(self, percent: float) -> bool:
        """AGC linearity (not needed in radiometric mode)."""
        return True

    def set_detail_enhancement(self, dde: float) -> bool:
        """Detail enhancement (not needed in radiometric mode)."""
        return True

    def enable_tlinear_mode(self) -> bool:
        """
        Enable TLinear mode (reconfigure if needed).

        Returns:
            bool: True if T-Linear is enabled
        """
        if self._tlinear_enabled:
            return True

        return self._configure_tlinear()

    def set_temperature_range(self, min_celsius: float, max_celsius: float) -> bool:
        """
        Set temperature range (for gain mode selection).

        High gain: -40°C to 120°C
        Low gain: up to 400°C

        Args:
            min_celsius: Minimum expected temperature
            max_celsius: Maximum expected temperature

        Returns:
            bool: True if gain mode was adjusted
        """
        if max_celsius > 120:
            return self.set_gain_mode(1)  # LOW gain
        return self.set_gain_mode(0)  # HIGH gain

    # =========================================================================
    # SDK STATUS PROPERTIES
    # =========================================================================

    @property
    def is_sdk_connected(self) -> bool:
        """Check if SDK is connected."""
        return self._sdk_connected

    @property
    def is_tlinear_enabled(self) -> bool:
        """Check if T-Linear mode is enabled."""
        return self._tlinear_enabled

    @property
    def com_port(self) -> str:
        """Get current COM port."""
        return self._com_port

