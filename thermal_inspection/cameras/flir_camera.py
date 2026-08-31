"""
FLIR Boson Thermal Camera Interface
Optimized for Jetson Orin with GPU acceleration
Enhanced with Boson SDK for serial control (Phase 7)
"""
import cv2
import numpy as np
from typing import Optional, Tuple
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Optional: Boson SDK integration for advanced control
try:
    from thermal_inspection.sdk.boson_sdk_wrapper import BosonSDK, GainMode, FFCMode, ColorLUT, BosonInfo
    SDK_AVAILABLE = True
except ImportError:
    SDK_AVAILABLE = False
    logger.info("Boson SDK not available - serial control disabled (video-only mode)")

# Optional: Radiometric temperature conversion
try:
    from thermal_inspection.processing.radiometric_converter import TLinearConverter
    RADIOMETRIC_AVAILABLE = True
except ImportError:
    RADIOMETRIC_AVAILABLE = False
    logger.info("Radiometric converter not available")


class FLIRBosonCamera:
    """
    Interface for FLIR Boson thermal camera.

    Supports:
    - Video streaming via OpenCV (all platforms)
    - Optional serial control via Boson SDK (Windows/Linux)
    """

    def __init__(self, device_id: int = 0, resolution: Tuple[int, int] = (640, 512),
                 enable_sdk: bool = False, com_port: Optional[str] = None):
        """
        Initialize FLIR Boson camera

        Args:
            device_id: Video device ID (usually /dev/video0 or 0)
            resolution: Camera resolution (640x512 for Boson 640, 320x256 for Boson 320)
            enable_sdk: Enable Boson SDK for serial control (FFC, AGC, etc.)
            com_port: COM port for SDK (e.g., 'COM6'). Auto-detect if None.
        """
        self.device_id = device_id
        self.resolution = resolution
        self.cap = None
        self.is_opened = False
        self.sdk: Optional[BosonSDK] = None
        self.sdk_connected = False
        self.radiometric_capable = False
        self.last_frame_16bit: Optional[np.ndarray] = None
        self._consecutive_failures = 0
        self._MAX_CONSECUTIVE_FAILURES = 10

        # SDK integration (Phase 7)
        self.enable_sdk = enable_sdk and SDK_AVAILABLE
        # Get default COM port from centralized config
        if com_port:
            self.com_port = com_port
        else:
            try:
                from thermal_inspection.utils.config import get_config
                config = get_config()
                import sys
                if sys.platform.startswith('win'):
                    self.com_port = config.get('sdk_com_port') or config.get('sdk_com_port_default', 'COM7')
                else:
                    self.com_port = config.get('sdk_com_port') or config.get('sdk_com_port_linux', '/dev/ttyACM0')
            except ImportError:
                self.com_port = 'COM7' if __import__('sys').platform.startswith('win') else '/dev/ttyACM0'
        self.sdk: Optional[BosonSDK] = None
        self.sdk_connected = False

        if enable_sdk and not SDK_AVAILABLE:
            logger.warning("SDK requested but not available - continuing in video-only mode")

        # Radiometric support
        self.radiometric_converter: Optional[TLinearConverter] = None
        self.radiometric_enabled = False
        self.radiometric_capable = False
        self.last_frame_16bit: Optional[np.ndarray] = None  # Store raw 16-bit frame

        if RADIOMETRIC_AVAILABLE:
            self.radiometric_converter = TLinearConverter(method="linear")
            # Set default temperature range for Boson
            self.radiometric_converter.set_temperature_range(-40.0, 550.0)

    def open(self) -> bool:
        """Open camera connection (cross-platform: Linux/Windows)"""
        try:
            import platform
            system = platform.system()

            # Try platform-specific backend first
            if system == "Linux":
                # Linux: Use V4L2 backend
                logger.info("Linux detected - trying V4L2 backend")
                self.cap = cv2.VideoCapture(self.device_id, cv2.CAP_V4L2)
            elif system == "Windows":
                # Windows: Try MSMF first, fall back to DSHOW.
                logger.info("Windows detected - trying MSMF backend")
                self.cap = cv2.VideoCapture(self.device_id, cv2.CAP_MSMF)
                if not self.cap.isOpened():
                    self.cap.release()
                    logger.info("MSMF failed - trying DirectShow backend")
                    self.cap = cv2.VideoCapture(self.device_id, cv2.CAP_DSHOW)
            else:
                # macOS or other: use default backend
                logger.info(f"{system} detected - using default backend")
                self.cap = cv2.VideoCapture(self.device_id)

            if not self.cap.isOpened():
                logger.warning("Failed to open thermal camera — not available")
                return False

            if self.cap.isOpened():
                # Set camera properties for optimal performance
                self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.resolution[0])
                self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.resolution[1])
                self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # Minimize latency

                # Try to maximize frame rate
                self.cap.set(cv2.CAP_PROP_FPS, 60)

                self.is_opened = True
                logger.info(f"FLIR Boson camera opened successfully on device {self.device_id}")
                logger.info(f"Resolution: {self.get_actual_resolution()}")
                logger.info(f"FPS: {self.cap.get(cv2.CAP_PROP_FPS)}")

                # Open SDK connection for serial control (Phase 7)
                if self.enable_sdk:
                    try:
                        self.sdk = BosonSDK(com_port=self.com_port or 'COM7')
                        if self.sdk.open():
                            self.sdk_connected = True
                            logger.info("[OK] Boson SDK connected - serial control enabled")
                            logger.info(f"  Camera SN: {self.sdk.get_info().serial_number}")

                            # Enable T-Linear mode (Radiometry)
                            if self.enable_tlinear_mode():
                                logger.info("[OK] T-Linear mode enabled via SDK")

                                # CRITICAL: Restart video capture to apply T-Linear format change
                                # The camera needs to be closed and reopened to switch from 8-bit AGC to 16-bit radiometric
                                logger.info("  -> Restarting video capture to apply T-Linear format...")
                                self.cap.release()

                                # Small delay to allow camera to apply the mode change
                                import time
                                time.sleep(0.5)

                                # Reopen video capture with Y16 format for radiometric data
                                import platform
                                system = platform.system()
                                if system == "Windows":
                                    try:
                                        self.cap = cv2.VideoCapture(self.device_id, cv2.CAP_MSMF)
                                        if not self.cap.isOpened():
                                            self.cap.release()
                                            self.cap = cv2.VideoCapture(self.device_id, cv2.CAP_DSHOW)
                                    except Exception:
                                        try:
                                            self.cap = cv2.VideoCapture(self.device_id, cv2.CAP_DSHOW)
                                        except Exception:
                                            self.cap = None
                                else:
                                    self.cap = cv2.VideoCapture(self.device_id, cv2.CAP_V4L2 if system == "Linux" else 0)

                                if not self.cap.isOpened():
                                    logger.error("Failed to reopen video capture after T-Linear mode")
                                    return False

                                # CRITICAL: Set Y16 format BEFORE setting other properties
                                # This must happen immediately after opening to capture 16-bit radiometric data
                                try:
                                    self.cap.set(cv2.CAP_PROP_CONVERT_RGB, 0)  # Disable RGB conversion
                                    self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc('Y','1','6',' '))
                                    logger.info("  -> Y16 format requested for radiometric mode")
                                except Exception as e:
                                    logger.warning(f"  -> Failed to set Y16 format: {e}")

                                # Reconfigure camera properties
                                self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.resolution[0])
                                self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.resolution[1])
                                self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                                self.cap.set(cv2.CAP_PROP_FPS, 60)

                                logger.info("  -> Video capture restarted successfully")
                                logger.info(f"  -> Resolution: {int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))}x{int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))}")
                            else:
                                logger.warning("Failed to enable T-Linear mode")

                        else:
                            logger.warning("SDK connection failed - continuing in video-only mode")
                    except Exception as e:
                        logger.warning(f"SDK initialization failed: {e} - continuing in video-only mode")

                # Force Y16 format if possible (for radiometric data)
                try:
                    self.cap.set(cv2.CAP_PROP_CONVERT_RGB, 0)
                    self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'Y16 '))
                    logger.info("Requested Y16 format from OpenCV")
                except Exception as e:
                    logger.warning(f"Failed to set Y16 format: {e}")

                return True
            else:
                logger.error(f"Failed to open camera on device {self.device_id}")
                return False

        except Exception as e:
            logger.error(f"Error opening camera: {e}")
            return False

    def read(self, flush_buffer: bool = False) -> Tuple[bool, Optional[np.ndarray]]:
        """
        Read frame from camera (BGR 8-bit, normalised).

        Returns (False, None) on any read failure. After
        _MAX_CONSECUTIVE_FAILURES consecutive failures marks is_opened=False
        so the health-check can detect a hot-unplug.
        """
        if not self.is_opened or self.cap is None:
            return False, None

        try:
            if flush_buffer:
                for _ in range(1):
                    if not self.cap.grab():
                        break
                ret, frame = self.cap.retrieve()
            else:
                ret, frame = self.cap.read()

            if ret and frame is not None:
                # Convert to grayscale for thermal pipeline
                if len(frame.shape) == 3:
                    frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

                if frame.dtype == np.uint16:
                    self.last_frame_16bit = frame.copy()
                    self.radiometric_capable = True
                    frame = cv2.normalize(frame, None, 0, 255, cv2.NORM_MINMAX)
                    frame = frame.astype(np.uint8)
                elif frame.dtype != np.uint8:
                    frame = cv2.normalize(frame, None, 0, 255, cv2.NORM_MINMAX)
                    frame = frame.astype(np.uint8)

                self._consecutive_failures = 0
                return True, frame

            # Read returned False / None frame
            self._consecutive_failures += 1
            if self._consecutive_failures >= self._MAX_CONSECUTIVE_FAILURES:
                logger.warning(
                    f"FLIRBoson camera {self.device_id}: "
                    f"{self._consecutive_failures} consecutive read failures — "
                    "marking as disconnected"
                )
                self.is_opened = False
            return False, None

        except Exception as e:
            self._consecutive_failures += 1
            logger.error(f"FLIRBoson camera {self.device_id} read error: {e}")
            if self._consecutive_failures >= self._MAX_CONSECUTIVE_FAILURES:
                self.is_opened = False
            return False, None

    def read_thermal(self) -> Tuple[bool, Optional[np.ndarray]]:
        """
        Read raw thermal frame (grayscale, preserves 16-bit if available).

        Returns (False, None) on any failure. Counts consecutive failures and
        marks is_opened=False after _MAX_CONSECUTIVE_FAILURES to allow
        health-check-based hot-unplug detection.
        """
        if not self.is_opened or self.cap is None:
            return False, None

        try:
            ret, frame = self.cap.read()

            if not (ret and frame is not None):
                self._consecutive_failures += 1
                if self._consecutive_failures >= self._MAX_CONSECUTIVE_FAILURES:
                    logger.warning(
                        f"FLIRBoson camera {self.device_id}: "
                        f"{self._consecutive_failures} consecutive thermal read failures — "
                        "marking as disconnected"
                    )
                    self.is_opened = False
                return False, None

            # Mode detection (first frame only)
            if not getattr(self, '_mode_logged', False):
                logger.info(
                    f"Thermal camera mode: dtype={frame.dtype} shape={frame.shape} "
                    f"-> {'RADIOMETRIC (16-bit)' if frame.dtype == np.uint16 else 'UVC (8-bit)'}"
                )
                self.radiometric_capable = (frame.dtype == np.uint16)
                self._mode_logged = True

            if len(frame.shape) == 3:
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

            if frame.dtype == np.uint16:
                self.last_frame_16bit = frame.copy()

            self._consecutive_failures = 0
            return True, frame

        except Exception as e:
            self._consecutive_failures += 1
            logger.error(f"FLIRBoson camera {self.device_id} read_thermal error: {e}")
            if self._consecutive_failures >= self._MAX_CONSECUTIVE_FAILURES:
                self.is_opened = False
            return False, None

    def get_actual_resolution(self) -> Tuple[int, int]:
        """Get actual camera resolution"""
        if self.cap is None:
            return (0, 0)

        width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        return (width, height)

    def release(self):
        """Release camera resources"""
        # Close SDK connection first
        if self.sdk and self.sdk_connected:
            try:
                self.sdk.close()
                logger.info("Boson SDK disconnected")
            except Exception as e:
                logger.warning(f"Error closing SDK: {e}")

        # Release video capture
        if self.cap is not None:
            self.cap.release()
            self.cap = None
            self.is_opened = False
            logger.info("FLIR Boson camera released")

            # Small delay to ensure resource cleanup
            import time
            time.sleep(0.1)

    # ========================================================================
    # SDK Control Methods (Phase 7)
    # ========================================================================

    def trigger_ffc(self) -> bool:
        """
        Trigger Flat Field Correction (FFC).

        Returns:
            True if successful (requires SDK)
        """
        if not self.sdk_connected or not self.sdk:
            logger.warning("FFC requires SDK - not available")
            return False

        return self.sdk.run_ffc()

    def set_gain_mode(self, mode: 'GainMode') -> bool:
        """
        Set camera gain mode.

        Args:
            mode: GainMode (HIGH, LOW, AUTO, MANUAL)

        Returns:
            True if successful (requires SDK)
        """
        if not self.sdk_connected or not self.sdk:
            logger.warning("Gain control requires SDK - not available")
            return False

        return self.sdk.set_gain_mode(mode)

    def set_color_lut(self, lut: 'ColorLUT') -> bool:
        """
        Set camera color lookup table.

        Args:
            lut: ColorLUT (WHITE_HOT, BLACK_HOT, IRONBOW, etc.)

        Returns:
            True if successful (requires SDK)
        """
        if not self.sdk_connected or not self.sdk:
            logger.warning("Color LUT control requires SDK - not available")
            return False

        return self.sdk.set_color_lut(lut)

    def set_ffc_mode(self, mode: 'FFCMode') -> bool:
        """
        Set FFC mode.

        Args:
            mode: FFCMode (MANUAL, AUTO, EXTERNAL)

        Returns:
            True if successful (requires SDK)
        """
        if not self.sdk_connected or not self.sdk:
            logger.warning("FFC mode control requires SDK - not available")
            return False

        return self.sdk.set_ffc_mode(mode)

    def get_fpa_temperature(self) -> Optional[Tuple[float, float]]:
        """
        Get FPA (Focal Plane Array) temperature.

        Returns:
            (temp_kelvin, temp_celsius) or None (requires SDK)
        """
        if not self.sdk_connected or not self.sdk:
            return None

        return self.sdk.get_fpa_temperature()

    def get_camera_info(self) -> Optional['BosonInfo']:
        """
        Get detailed camera information.

        Returns:
            BosonInfo object or None (requires SDK)
        """
        if self.sdk and self.sdk_connected:
            return self.sdk.get_info()
        return None

    # ========================================================================
    # AGC (Automatic Gain Control) - Universal (ALL Boson cameras)
    # ========================================================================

    def set_agc_max_gain(self, gain: float) -> bool:
        """Set AGC maximum gain (contrast limit). Works on ALL Boson cameras."""
        if self.sdk and self.sdk_connected:
            return self.sdk.set_agc_max_gain(gain)
        return False

    def set_agc_gamma(self, gamma: float) -> bool:
        """Set AGC gamma correction. Works on ALL Boson cameras."""
        if self.sdk and self.sdk_connected:
            return self.sdk.set_agc_gamma(gamma)
        return False

    def set_agc_linearity(self, percent: float) -> bool:
        """Set AGC linearity (histogram vs. linear). Works on ALL Boson cameras."""
        if self.sdk and self.sdk_connected:
            return self.sdk.set_agc_linearity(percent)
        return False

    def set_detail_enhancement(self, dde: float) -> bool:
        """Set DDE (Digital Detail Enhancement). Works on ALL Boson cameras."""
        if self.sdk and self.sdk_connected:
            return self.sdk.set_detail_enhancement(dde)
        return False

    def is_sdk_connected(self) -> bool:
        """Check if SDK is connected for serial control."""
        return self.sdk_connected

    # ========================================================================
    # Radiometric Temperature Measurement (Phase 9)
    # ========================================================================

    def is_radiometric_capable(self) -> bool:
        """
        Check if camera supports radiometric temperature measurement.

        Returns:
            True if camera outputs 16-bit radiometric data
        """
        return self.radiometric_capable

    def is_radiometric_enabled(self) -> bool:
        """
        Check if radiometric features are currently enabled.

        Returns:
            True if radiometric conversion is active
        """
        return self.radiometric_enabled and self.radiometric_capable and RADIOMETRIC_AVAILABLE

    def enable_radiometric(self, enable: bool = True):
        """
        Enable/disable radiometric temperature conversion.

        Args:
            enable: True to enable, False to disable
        """
        if not RADIOMETRIC_AVAILABLE:
            logger.warning("Cannot enable radiometric - converter not available")
            return

        if not self.radiometric_capable:
            logger.warning("Cannot enable radiometric - camera does not output 16-bit data")
            return

        self.radiometric_enabled = enable
        logger.info(f"Radiometric conversion {'enabled' if enable else 'disabled'}")

    def get_spot_temperature(self, x: int, y: int) -> Optional[float]:
        """
        Get temperature at a specific pixel coordinate.

        Args:
            x: X coordinate
            y: Y coordinate

        Returns:
            Temperature in Celsius, or None if not available
        """
        if not self.is_radiometric_enabled() or self.last_frame_16bit is None:
            return None

        if not self.radiometric_converter:
            return None

        try:
            return self.radiometric_converter.get_spot_temperature(self.last_frame_16bit, x, y)
        except Exception as e:
            logger.debug(f"Error getting spot temperature: {e}")
            return None

    def get_temperature_frame(self) -> Optional[np.ndarray]:
        """
        Convert the last captured frame to temperature values.

        Returns:
            Temperature array (H, W) in Celsius (float32), or None if not available
        """
        if not self.is_radiometric_enabled() or self.last_frame_16bit is None:
            return None

        if not self.radiometric_converter:
            return None

        try:
            return self.radiometric_converter.convert_frame(self.last_frame_16bit)
        except Exception as e:
            logger.error(f"Error converting temperature frame: {e}")
            return None

    def get_roi_temperature_stats(self, roi_mask: np.ndarray) -> Optional[dict]:
        """
        Get temperature statistics for a region of interest.

        Args:
            roi_mask: Boolean mask (H, W) where True = inside ROI

        Returns:
            Dictionary with keys: min_temp, max_temp, mean_temp, median_temp, std_temp,
            min_location, max_location, or None if not available
        """
        if not self.is_radiometric_enabled() or self.last_frame_16bit is None:
            return None

        if not self.radiometric_converter:
            return None

        try:
            return self.radiometric_converter.get_roi_temperature_stats(self.last_frame_16bit, roi_mask)
        except Exception as e:
            logger.error(f"Error computing ROI temperature stats: {e}")
            return None

    def get_frame_temperature_stats(self) -> Optional[dict]:
        """
        Get temperature statistics for the entire frame.

        Returns:
            Dictionary with keys: min_temp, max_temp, mean_temp, median_temp, std_temp,
            min_location, max_location, or None if not available
        """
        if not self.is_radiometric_enabled() or self.last_frame_16bit is None:
            return None

        if not self.radiometric_converter:
            return None

        try:
            # Create full-frame mask
            h, w = self.last_frame_16bit.shape
            full_mask = np.ones((h, w), dtype=bool)
            return self.radiometric_converter.get_roi_temperature_stats(self.last_frame_16bit, full_mask)
        except Exception as e:
            logger.error(f"Error computing frame temperature stats: {e}")
            return None

    def set_temperature_range(self, min_celsius: float, max_celsius: float) -> bool:
        """
        Set expected temperature range for linear conversion.

        Args:
            min_celsius: Minimum expected temperature (C)
            max_celsius: Maximum expected temperature (C)

        Returns:
            True if successful
        """
        if not self.radiometric_converter:
            logger.warning("No radiometric converter available")
            return False

        try:
            self.radiometric_converter.set_temperature_range(min_celsius, max_celsius)
            logger.info(f"Temperature range set to {min_celsius}C - {max_celsius}C")
            return True
        except Exception as e:
            logger.error(f"Error setting temperature range: {e}")
            return False

    def enable_radiometric_mode(self) -> bool:
        """
        Enable radiometric mode on the camera (16-bit temperature output).
        Alias for enable_tlinear_mode()
        """
        return self.enable_tlinear_mode()

    def enable_tlinear_mode(self) -> bool:
        """
        Enable T-Linear (Radiometric) mode via SDK.

        This enables T-Linear processing and sets USB output to radiometric mode.

        Note on Windows:
            Due to DirectShow limitations, OpenCV will still capture 8-bit YUV data
            even after enabling this mode. The camera is configured correctly, but
            Windows DirectShow prefers color formats over Y16.

            The AGC output will reflect T-Linear processing, providing better
            thermal data quality even in 8-bit format.

        Returns:
            True if successful
        """
        if not self.sdk_connected or not self.sdk:
            logger.warning("SDK not connected - cannot enable T-Linear mode")
            return False

        try:
            # Step 1: Enable T-Linear control
            if not self.sdk.enable_tlinear_control():
                logger.error("Failed to enable T-Linear control")
                return False

            # Step 2: Set USB video output to T-Linear mode (mode 2)
            if not self.sdk.set_usb_video_ir16_mode(2):
                logger.warning("Failed to set USB IR16 mode, but T-Linear control is active")
                # Don't fail completely - T-Linear control is still useful

            self.radiometric_enabled = True
            logger.info("T-Linear mode enabled successfully")
            return True

        except Exception as e:
            logger.error(f"Error enabling T-Linear mode: {e}")
            return False

    def disable_tlinear_mode(self) -> bool:
        """
        Disable T-Linear mode and return to standard AGC processing.

        Returns:
            True if successful
        """
        if not self.sdk_connected or not self.sdk:
            logger.warning("SDK not connected - cannot disable T-Linear mode")
            return False

        try:
            # Disable T-Linear control
            if not self.sdk.disable_tlinear_control():
                logger.error("Failed to disable T-Linear control")
                return False

            # Set USB video to standard 16-bit raw mode (mode 0)
            if not self.sdk.set_usb_video_ir16_mode(0):
                logger.warning("Failed to reset USB IR16 mode")

            self.radiometric_enabled = False
            logger.info("T-Linear mode disabled")
            return True

        except Exception as e:
            logger.error(f"Error disabling T-Linear mode: {e}")
            return False

    def get_video_mode_status(self) -> dict:
        """
        Get current video mode status.

        Returns:
            Dictionary with mode information
        """
        status = {
            'sdk_connected': self.sdk_connected,
            'tlinear_enabled': False,
            'usb_ir16_mode': None,
            'usb_ir16_mode_name': 'Unknown',
            'radiometric_capable': self.radiometric_capable,
            'note': ''
        }

        if not self.sdk_connected or not self.sdk:
            status['note'] = 'SDK not connected'
            return status

        try:
            # Get T-Linear control state
            tlinear_state = self.sdk.get_tlinear_control_state()
            status['tlinear_enabled'] = tlinear_state if tlinear_state is not None else False

            # Get USB IR16 mode
            ir16_mode = self.sdk.get_usb_video_ir16_mode()
            status['usb_ir16_mode'] = ir16_mode

            mode_names = {
                0: '16-bit raw',
                1: '14-bit raw',
                2: 'T-Linear radiometric'
            }
            status['usb_ir16_mode_name'] = mode_names.get(ir16_mode, 'Unknown')

            # Add note about Windows limitation
            if ir16_mode == 2:
                status['note'] = 'T-Linear mode active. Note: Windows DirectShow captures 8-bit YUV.'

        except Exception as e:
            status['note'] = f'Error reading status: {e}'

        return status

    def switch_to_agc_mode(self) -> bool:
        """
        Switch camera to AGC (8-bit processed) mode at runtime.

        This disables T-Linear and returns to standard AGC processing.
        Video capture does NOT need to be restarted.

        Returns:
            True if successful
        """
        return self.disable_tlinear_mode()

    def switch_to_radiometric_mode(self) -> bool:
        """
        Switch camera to radiometric (T-Linear) mode at runtime.

        This enables T-Linear processing. On Windows with OpenCV,
        the output will still be 8-bit YUV, but with T-Linear processing
        providing better thermal data quality.

        Video capture does NOT need to be restarted.

        Returns:
            True if successful
        """
        return self.enable_tlinear_mode()

    # ========================================================================
    # Runtime SDK Connection (Phase 7 Enhancement - v2.7.0)
    # ========================================================================

    def connect_sdk(self, com_port: Optional[str] = None) -> bool:
        """
        Connect to Boson SDK at runtime.

        Args:
            com_port: COM port (e.g., 'COM6'). None for auto-detect.

        Returns:
            True if connection successful, False otherwise
        """
        if not SDK_AVAILABLE:
            logger.error("Boson SDK not available - cannot connect")
            return False

        if self.sdk_connected:
            logger.warning("SDK already connected")
            return True

        try:
            logger.info(f"Attempting to connect Boson SDK{f' on {com_port}' if com_port else ' (auto-detect)'}...")

            # Normalize COM port input (handle "6" -> "COM6")
            if com_port:
                com_port = com_port.strip().upper()
                # If user typed just a number, prepend "COM"
                if com_port.isdigit():
                    com_port = f"COM{com_port}"
                # Ensure it starts with "COM"
                elif not com_port.startswith("COM"):
                    com_port = f"COM{com_port}"

            # Create SDK instance
            actual_port = com_port or 'COM7'
            self.sdk = BosonSDK(com_port=actual_port)

            # Attempt connection
            if self.sdk.open():
                self.sdk_connected = True
                # Store the successfully connected COM port
                self.com_port = actual_port
                logger.info("[OK] Boson SDK connected successfully")

                # Log camera info
                try:
                    info = self.sdk.get_info()
                    if info:
                        logger.info(f"  Camera SN: {info.serial_number}")
                        logger.info(f"  FPA Temp: {info.fpa_temperature_k - 273.15:.1f}C")
                except Exception as e:
                    logger.debug(f"Could not retrieve camera info: {e}")

                return True
            else:
                logger.error("[ERROR] Failed to open SDK connection")
                self.sdk = None
                return False

        except Exception as e:
            logger.error(f"[ERROR] SDK connection error: {e}")
            self.sdk = None
            self.sdk_connected = False
            return False

    def disconnect_sdk(self) -> bool:
        """
        Disconnect from Boson SDK.

        Returns:
            True if disconnection successful
        """
        if not self.sdk_connected or not self.sdk:
            logger.info("SDK not connected - nothing to disconnect")
            return True

        try:
            logger.info("Disconnecting Boson SDK...")
            self.sdk.close()
            self.sdk_connected = False
            self.sdk = None
            logger.info("[OK] Boson SDK disconnected")
            return True

        except Exception as e:
            logger.error(f"[ERROR] SDK disconnection error: {e}")
            # Force disconnect state even on error
            self.sdk_connected = False
            self.sdk = None
            return False

    @staticmethod
    def scan_com_ports() -> list:
        """
        Scan for available COM ports that might be Boson cameras.

        Returns:
            List of potential COM port strings
        """
        if not SDK_AVAILABLE:
            logger.warning("Boson SDK not available - cannot scan ports")
            return []

        try:
            # Try to use BosonSerialInterface if available
            try:
                from boson_serial import BosonSerialInterface
                ports = BosonSerialInterface.find_boson_com_ports()
                logger.info(f"Found {len(ports)} potential Boson COM ports: {ports}")
                return ports
            except ImportError:
                logger.warning("boson_serial module not available for port scanning")
                return []

        except Exception as e:
            logger.error(f"Error scanning COM ports: {e}")
            return []

    # ========================================================================
    # Context Manager
    # ========================================================================

    def __enter__(self):
        """Context manager entry"""
        self.open()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.release()
