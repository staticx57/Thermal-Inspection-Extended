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
    from boson_sdk_wrapper import BosonSDK, GainMode, FFCMode, ColorLUT, BosonInfo
    SDK_AVAILABLE = True
except ImportError:
    SDK_AVAILABLE = False
    logger.info("Boson SDK not available - serial control disabled (video-only mode)")


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

        # SDK integration (Phase 7)
        self.enable_sdk = enable_sdk and SDK_AVAILABLE
        self.com_port = com_port
        self.sdk: Optional[BosonSDK] = None
        self.sdk_connected = False

        if enable_sdk and not SDK_AVAILABLE:
            logger.warning("SDK requested but not available - continuing in video-only mode")

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
                # Windows: Try DirectShow first, then MSMF
                logger.info("Windows detected - trying DirectShow backend")
                try:
                    self.cap = cv2.VideoCapture(self.device_id, cv2.CAP_DSHOW)
                except:
                    logger.info("DirectShow failed, trying MSMF backend")
                    self.cap = cv2.VideoCapture(self.device_id, cv2.CAP_MSMF)
            else:
                # macOS or other: use default backend
                logger.info(f"{system} detected - using default backend")
                self.cap = cv2.VideoCapture(self.device_id)

            # Fallback to default backend if platform-specific failed
            if not self.cap.isOpened():
                logger.warning(f"Platform-specific backend failed, trying default backend")
                self.cap = cv2.VideoCapture(self.device_id)

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
                        self.sdk = BosonSDK(com_port=self.com_port or 'COM6')
                        if self.sdk.open():
                            self.sdk_connected = True
                            logger.info("✓ Boson SDK connected - serial control enabled")
                            logger.info(f"  Camera SN: {self.sdk.get_info().serial_number}")
                            logger.info(f"  FPA Temp: {self.sdk.get_info().fpa_temperature_k - 273.15:.1f}°C")
                        else:
                            logger.warning("SDK connection failed - continuing in video-only mode")
                    except Exception as e:
                        logger.warning(f"SDK initialization failed: {e} - continuing in video-only mode")

                return True
            else:
                logger.error(f"Failed to open camera on device {self.device_id}")
                return False

        except Exception as e:
            logger.error(f"Error opening camera: {e}")
            return False

    def read(self, flush_buffer: bool = False) -> Tuple[bool, Optional[np.ndarray]]:
        """
        Read frame from camera

        Args:
            flush_buffer: If True, grab and drop old frames to get the freshest frame

        Returns:
            Tuple of (success, frame) where frame is BGR format
        """
        if not self.is_opened or self.cap is None:
            return False, None

        # Flush old buffered frames to get fresher frames
        # This prevents lag when processing takes longer than frame interval
        if flush_buffer:
            # Only flush 1 frame - reduces latency by 16ms while still getting fresh frames
            # At 60 FPS, 1 frame = 16ms overhead
            for _ in range(1):
                if not self.cap.grab():
                    break
            # Retrieve the latest grabbed frame
            ret, frame = self.cap.retrieve()
        else:
            ret, frame = self.cap.read()

        if ret and frame is not None:
            # FLIR Boson outputs grayscale, convert to BGR for compatibility
            if len(frame.shape) == 2:
                frame = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)

        return ret, frame

    def read_thermal(self) -> Tuple[bool, Optional[np.ndarray]]:
        """
        Read raw thermal frame (grayscale)

        Returns:
            Tuple of (success, frame) where frame is grayscale thermal data
        """
        if not self.is_opened or self.cap is None:
            return False, None

        ret, frame = self.cap.read()

        if ret and frame is not None:
            # DIAGNOSTIC: Log frame format to determine camera mode
            if not hasattr(self, '_mode_logged') or not self._mode_logged:
                logger.info(f"Thermal camera mode detection:")
                logger.info(f"  Frame dtype: {frame.dtype}")
                logger.info(f"  Frame shape: {frame.shape}")
                if frame.dtype == np.uint16:
                    logger.info(f"  → RAW THERMAL MODE (16-bit radiometric data)")
                elif frame.dtype == np.uint8:
                    logger.info(f"  → UVC MODE (8-bit YUV/RGB converted)")
                self._mode_logged = True
            
            if len(frame.shape) == 3:
                # Convert to grayscale if needed
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        return ret, frame

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
            self.is_opened = False
            logger.info("FLIR Boson camera released")

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
        if not self.sdk_connected or not self.sdk:
            return None

        return self.sdk.get_info()

    def is_sdk_connected(self) -> bool:
        """Check if SDK is connected for serial control."""
        return self.sdk_connected

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