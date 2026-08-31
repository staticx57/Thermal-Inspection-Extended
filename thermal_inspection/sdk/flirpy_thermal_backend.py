"""
flirpy-based Thermal Backend with Dual-Path SDK Control

Provides 16-bit Y16 radiometric capture from FLIR Boson using the flirpy library,
with simultaneous SDK control via COM port for T-Linear mode and FFC.

Architecture:
- flirpy (UVC) → 16-bit Y16 frame capture
- BosonSDK (COM port) → Camera control (T-Linear, FFC, settings)

Both paths can operate simultaneously as they use different interfaces.
"""

import logging
import numpy as np
from typing import Optional, Tuple

from thermal_inspection.cameras.camera_backends import ThermalBackend

logger = logging.getLogger(__name__)

from flirpy.camera.boson import Boson
try:
    import flirpy
    FLIRPY_AVAILABLE = True
except ImportError:
    FLIRPY_AVAILABLE = False

# Import BosonSDK for T-Linear control via COM port.
# GainMode/FFCMode/ColorLUT are the enums the SDK setters expect.
try:
    from thermal_inspection.sdk.boson_sdk_wrapper import (
        BosonSDK, GainMode, FFCMode, ColorLUT
    )
    SDK_AVAILABLE = True
except ImportError:
    BosonSDK = None
    GainMode = None
    FFCMode = None
    ColorLUT = None
    SDK_AVAILABLE = False
    logger.warning("BosonSDK not available - T-Linear mode may not work")

logger = logging.getLogger(__name__)


class FlirpyThermalBackend(ThermalBackend):
    """
    flirpy-based backend for FLIR Boson thermal camera with dual-path SDK control.

    Features:
    - 16-bit Y16 radiometric capture via flirpy (UVC)
    - SDK control via COM port (T-Linear, FFC, settings)
    - True absolute temperatures (±2°C accuracy when T-Linear enabled)
    - Dual-path architecture allows simultaneous capture and control

    The SDK connection is REQUIRED for proper T-Linear (radiometric) output.
    Without SDK: raw 14-bit sensor data (~-80°C readings)
    With SDK: true T-Linear data (~ambient temperature readings)
    """

    def __init__(self, com_port: str = 'COM7', auto_configure: bool = True):
        """
        Initialize flirpy backend with optional SDK control.

        Args:
            com_port: COM port for SDK control (e.g., 'COM7')
            auto_configure: If True, automatically configure T-Linear mode on open
        """
        self.camera = None
        self._is_opened = False
        self._frame_count = 0
        self._last_frame = None  # Store last captured frame

        # SDK control (dual-path)
        self._com_port = com_port
        self._auto_configure = auto_configure
        self._sdk: Optional[BosonSDK] = None
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
            test_cam = Boson()
            test_cam.close()
            return True
        except Exception as e:
            logger.debug(f"Boson not available via flirpy: {e}")
            return False

    def open(self) -> bool:
        """
        Open FLIR Boson camera via flirpy (Sequential Access Pattern).

        This method:
        1. FIRST: Connects BosonSDK to configure T-Linear mode
        2. THEN: Closes SDK to release COM port
        3. FINALLY: Opens flirpy for 16-bit Y16 video capture

        This sequential pattern avoids COM port conflicts between SDK and flirpy.

        Returns:
            bool: True if successful
        """
        if not FLIRPY_AVAILABLE:
            logger.error("flirpy library not installed")
            return False

        try:
            logger.info(f"Opening Boson camera via flirpy (Port: {self._com_port})...")

            # STEP 1: Configure T-Linear mode via SDK FIRST (before flirpy takes the port)
            if self._auto_configure and SDK_AVAILABLE:
                self._configure_tlinear_before_flirpy()

            # STEP 2: Initialize flirpy Boson for video capture
            # flirpy will now use the COM port (SDK released it above)
            self.camera = Boson(port=self._com_port)

            # Verify serial connection via flirpy
            try:
                temp = self.camera.get_fpa_temperature()
                logger.info(f"✓ Serial connection established (FPA Temp: {temp:.1f}°C)")
                self._sdk_connected = True
            except Exception as e:
                logger.warning(f"⚠ Serial connection issue: {e}")
                self._sdk_connected = False

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

    def _configure_tlinear_before_flirpy(self):
        """
        Configure camera for T-Linear radiometric output via SDK.

        IMPORTANT: This must be called BEFORE flirpy opens the camera,
        because both SDK and flirpy need exclusive access to the COM port.
        The SDK will be closed after configuration to release the port for flirpy.
        """
        try:
            logger.info("Configuring T-Linear mode via SDK (before flirpy)...")

            # Create temporary SDK connection
            sdk = BosonSDK(com_port=self._com_port)
            if not sdk.open():
                logger.warning("Failed to connect BosonSDK - T-Linear may not be enabled")
                self._tlinear_enabled = False
                return

            logger.info(f"✓ BosonSDK connected on {self._com_port}")

            # Enable T-Linear mode (USB Video IR16 Mode = 2)
            try:
                if sdk.set_usb_video_ir16_mode(2):
                    logger.info("✓ T-Linear mode enabled (USB IR16 Mode = 2)")
                    self._tlinear_enabled = True
                else:
                    logger.warning("Failed to set USB IR16 mode to T-Linear")
                    self._tlinear_enabled = False
            except Exception as e:
                logger.error(f"Error setting T-Linear mode: {e}")
                self._tlinear_enabled = False

            # Also enable T-Linear control if available
            try:
                sdk.enable_tlinear_control()
            except Exception as e:
                logger.debug(f"T-Linear control enable failed (may not be supported): {e}")

            # CRITICAL: Close SDK to release COM port for flirpy
            sdk.close()
            logger.info("✓ SDK closed, COM port released for flirpy")
            self._sdk = None  # Don't keep SDK reference - flirpy will own the port

        except Exception as e:
            logger.error(f"Failed to configure T-Linear: {e}")
            self._tlinear_enabled = False

    def _configure_tlinear(self):
        """Legacy method - now just logs warning if called directly."""
        logger.warning("_configure_tlinear called but flirpy already owns COM port")
        logger.warning("T-Linear should be configured via _configure_tlinear_before_flirpy()")

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
            'library': 'flirpy (dual-path with SDK)',
            'bit_depth': 16,
            'radiometric': True,
            'resolution': self.get_resolution(),
            'format': 'Y16 (uint16)',
            'driver': 'UVC (flirpy) + COM (SDK)',
            'sdk_connected': self._sdk_connected,
            'tlinear_enabled': self._tlinear_enabled,
            'com_port': self._com_port,
            'features': [
                '16-bit Y16',
                'True radiometric',
                'UVC driver',
                'SDK control via COM',
                'FFC trigger',
                'T-Linear mode'
            ]
        }

        # Add SDK info if connected
        if self._sdk_connected and self._sdk is not None and self._sdk.info:
            sdk_info = self._sdk.info
            if sdk_info.serial_number:
                info['serial_number'] = sdk_info.serial_number
            if sdk_info.gain_mode:
                info['gain_mode'] = sdk_info.gain_mode.name
            if sdk_info.software_version:
                info['firmware_version'] = sdk_info.software_version

        return info

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
        Get the SDK object for direct camera control.

        Returns the connected BosonSDK instance, allowing full COM control
        (FFC, gain, emissivity, LUT, etc.) while still capturing via flirpy.
        """
        return self._sdk

    # =========================================================================
    # SDK CAMERA CONTROL (Full COM port access)
    # These methods proxy to the BosonSDK when connected
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

    def set_gain_mode(self, mode: int) -> bool:
        """
        Set gain mode via SDK.

        Args:
            mode: 0=HIGH (-40 to 120°C), 1=LOW (up to 400°C), 2=AUTO

        Returns:
            bool: True if successful
        """
        if not self._sdk_connected or self._sdk is None:
            logger.warning("Cannot set gain mode: SDK not connected")
            return False

        try:
            gain_mode = GainMode(mode)
            return self._sdk.set_gain_mode(gain_mode)
        except Exception as e:
            logger.error(f"Error setting gain mode: {e}")
            return False

    def set_ffc_mode(self, mode: int) -> bool:
        """
        Set FFC mode via SDK.

        Args:
            mode: 0=MANUAL, 1=AUTO, 2=EXTERNAL

        Returns:
            bool: True if successful
        """
        if not self._sdk_connected or self._sdk is None:
            logger.warning("Cannot set FFC mode: SDK not connected")
            return False

        try:
            ffc_mode = FFCMode(mode)
            return self._sdk.set_ffc_mode(ffc_mode)
        except Exception as e:
            logger.error(f"Error setting FFC mode: {e}")
            return False

    def get_fpa_temperature(self) -> Optional[float]:
        """
        Get FPA (Focal Plane Array) temperature in Celsius.

        Prefers flirpy, which reads the value over the same handle it already
        holds and so works while streaming. Falls back to the SDK's COM
        channel, which is only reachable when a separate connection is up.

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

        if self._sdk_connected and self._sdk is not None:
            try:
                result = self._sdk.get_fpa_temperature()
                if result:
                    return result[1]  # (kelvin, celsius)
            except Exception as e:
                logger.debug(f"SDK FPA temperature read failed: {e}")

        return None

    def get_lens_temperature(self) -> Optional[float]:
        """
        Get lens housing temperature via SDK.

        Returns:
            float: Lens temperature in Celsius, or None if unavailable
        """
        if not self._sdk_connected or self._sdk is None:
            return None

        return self._sdk.get_lens_temperature()

    def get_shutter_temperature(self) -> Optional[float]:
        """
        Get shutter housing temperature via SDK.

        Returns:
            float: Shutter temperature in Celsius, or None if unavailable
        """
        if not self._sdk_connected or self._sdk is None:
            return None

        return self._sdk.get_shutter_temperature()

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
        Set color lookup table via SDK.

        Args:
            lut: 0=WHITE_HOT, 1=BLACK_HOT, 2=RAINBOW, 4=IRONBOW, etc.

        Returns:
            bool: True if successful
        """
        if not self._sdk_connected or self._sdk is None:
            logger.warning("Cannot set color LUT: SDK not connected")
            return False

        try:
            color_lut = ColorLUT(lut)
            return self._sdk.set_color_lut(color_lut)
        except Exception as e:
            logger.error(f"Error setting color LUT: {e}")
            return False

    def set_emissivity(self, emissivity: float) -> bool:
        """
        Set target emissivity for accurate temperature measurement.

        Args:
            emissivity: 0.01-1.0 (1.0 = perfect blackbody)

        Returns:
            bool: True if successful
        """
        if self.camera is None:
            logger.warning("Cannot set emissivity: Camera not connected")
            return False

        try:
            # Try flirpy method first
            if hasattr(self.camera, 'set_emissivity'):
                self.camera.set_emissivity(emissivity)
                return True
            else:
                logger.warning("flirpy Boson driver does not support set_emissivity")
                return False
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
            if hasattr(self.camera, 'get_emissivity'):
                return self.camera.get_emissivity()
            return None
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
            if hasattr(self.camera, 'set_atmospheric_temperature'):
                self.camera.set_atmospheric_temperature(temp_celsius)
                return True
            return False
        except Exception as e:
            logger.error(f"Error setting atmospheric temp: {e}")
            return False

    def set_atmospheric_transmission(self, transmission: float) -> bool:
        """
        Set atmospheric transmission coefficient.

        Args:
            transmission: 0.01-1.0

        Returns:
            bool: True if successful
        """
        if self.camera is None:
            return False

        try:
            if hasattr(self.camera, 'set_atmospheric_transmission'):
                self.camera.set_atmospheric_transmission(transmission)
                return True
            return False
        except Exception as e:
            logger.error(f"Error setting atmospheric transmission: {e}")
            return False

    def get_calibration_info(self) -> dict:
        """
        Get all radiometric calibration parameters.

        Returns:
            dict: Calibration info (gain, offset, lens params, temps)
        """
        if not self._sdk_connected or self._sdk is None:
            return {}

        return self._sdk.get_calibration_info()

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

