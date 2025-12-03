"""
Camera Manager - Orchestrates multiple camera backends.

Provides unified interface for the application to access different camera backends
with runtime switching capabilities.
"""

from typing import Optional, Dict, List
import logging

from camera_backends import ThermalBackend, RGBBackend, BackendNotAvailableError, BackendInitializationError
from opencv_thermal_backend import OpenCVThermalBackend
from pyusb_thermal_backend import PyUSBThermalBackend
from flirpy_thermal_backend import FlirpyThermalBackend

logger = logging.getLogger(__name__)


class CameraManager:
    """
    Manages multiple cameras with different backends.

    Provides unified interface for application layer with support for:
    - Multiple thermal backends (OpenCV 8-bit, PyUSB 16-bit)
    - Runtime backend switching
    - Automatic fallback to available backends
    - Backend availability detection

    Usage:
        manager = CameraManager()

        # Initialize with OpenCV backend (8-bit, works now)
        manager.initialize_thermal(mode='opencv', device_id=1, com_port='COM6')

        # Read frames
        success, frame = manager.read_thermal()

        # Switch to USB backend (16-bit, requires WinUSB driver)
        manager.switch_thermal_backend('usb')

        # Get temperature map (only works with radiometric backends)
        temp_map = manager.get_thermal_temperature_map()
    """

    # Backend mode constants
    MODE_OPENCV = 'opencv'
    MODE_USB = 'usb'
    MODE_FLIRPY = 'flirpy'

    def __init__(self):
        """Initialize camera manager."""
        self.thermal_backend: Optional[ThermalBackend] = None
        self.thermal_mode: Optional[str] = None
        self._thermal_params: Dict = {}

    def get_available_thermal_backends(self) -> List[Dict]:
        """
        Detect which thermal backends are available on the system.

        Returns:
            list: List of available backends with info dicts
        """
        available = []

        # Check OpenCV backend
        opencv_backend = OpenCVThermalBackend()
        if opencv_backend.is_available():
            available.append({
                'mode': self.MODE_OPENCV,
                'name': 'OpenCV DirectShow (8-bit)',
                'description': '8-bit T-Linear AGC with SDK control',
                'radiometric': False,
                'available': True
            })

        # Check PyUSB backend
        pyusb_backend = PyUSBThermalBackend()
        if pyusb_backend.is_available():
            available.append({
                'mode': self.MODE_USB,
                'name': 'PyUSB Direct (16-bit)',
                'description': 'True 16-bit Y16 radiometric',
                'radiometric': True,
                'available': True
            })

        # Check flirpy backend
        flirpy_backend = FlirpyThermalBackend()
        if flirpy_backend.is_available():
            available.append({
                'mode': self.MODE_FLIRPY,
                'name': 'flirpy (16-bit Y16)',
                'description': '16-bit Y16 radiometric via flirpy (UVC driver)',
                'radiometric': True,
                'available': True
            })

        if not available:
            logger.warning("No thermal backends available!")

        return available

    def initialize_thermal(self, mode: str = MODE_OPENCV, device_id: int = 1,
                          com_port: str = 'COM6', enable_sdk: bool = True) -> bool:
        """
        Initialize thermal camera with specified backend.

        Args:
            mode: Backend mode ('opencv' or 'usb')
            device_id: Video device index (for OpenCV backend)
            com_port: COM port for SDK (for OpenCV backend)
            enable_sdk: Enable SDK features (for OpenCV backend)

        Returns:
            bool: True if initialization successful

        Raises:
            ValueError: If unknown mode specified
            BackendNotAvailableError: If backend is not available
            BackendInitializationError: If backend fails to initialize
        """
        # Store parameters for potential backend switching
        self._thermal_params = {
            'device_id': device_id,
            'com_port': com_port,
            'enable_sdk': enable_sdk
        }

        # Create backend based on mode
        if mode == self.MODE_OPENCV:
            backend = OpenCVThermalBackend(
                device_id=device_id,
                com_port=com_port,
                enable_sdk=enable_sdk
            )
        elif mode == self.MODE_USB:
            backend = PyUSBThermalBackend()
        elif mode == self.MODE_FLIRPY:
            backend = FlirpyThermalBackend()
        else:
            raise ValueError(f"Unknown thermal backend mode: {mode}. Use 'opencv', 'usb', or 'flirpy'")

        # Check availability
        if not backend.is_available():
            logger.error(f"Thermal backend '{mode}' not available on this system")
            raise BackendNotAvailableError(f"Backend '{mode}' not available")

        # Open backend
        try:
            success = backend.open()
            if success:
                self.thermal_backend = backend
                self.thermal_mode = mode
                logger.info(f"✓ Thermal camera initialized with {mode} backend")
                return True
            else:
                logger.error(f"✗ Failed to open thermal backend: {mode}")
                return False
        except Exception as e:
            logger.error(f"Error initializing thermal backend '{mode}': {e}")
            raise

    def switch_thermal_backend(self, mode: str) -> bool:
        """
        Switch thermal camera backend at runtime.

        This will:
        1. Release the current backend
        2. Initialize the new backend
        3. Preserve configuration where possible

        Args:
            mode: New backend mode ('opencv' or 'usb')

        Returns:
            bool: True if switch successful, False otherwise

        Note:
            Switching from OpenCV to USB requires WinUSB driver to be installed.
            Switching from USB to OpenCV requires UVC driver to be installed.
        """
        if self.thermal_mode == mode:
            logger.info(f"Already using {mode} backend, no switch needed")
            return True

        logger.info(f"Switching thermal backend: {self.thermal_mode} → {mode}")

        # Release current backend
        if self.thermal_backend:
            logger.info(f"Releasing current backend: {self.thermal_mode}")
            try:
                self.thermal_backend.release()
            except Exception as e:
                logger.warning(f"Error releasing backend: {e}")
            self.thermal_backend = None
            self.thermal_mode = None

        # Initialize new backend
        try:
            success = self.initialize_thermal(
                mode=mode,
                **self._thermal_params
            )

            if success:
                logger.info(f"✓ Successfully switched to {mode} backend")
            else:
                logger.error(f"✗ Failed to switch to {mode} backend")

            return success

        except BackendNotAvailableError as e:
            logger.error(f"Backend '{mode}' not available: {e}")
            return False
        except Exception as e:
            logger.error(f"Error switching to {mode} backend: {e}")
            return False

    def read_thermal(self):
        """
        Read frame from thermal camera.

        Returns:
            tuple: (success: bool, frame: np.ndarray or None)

        Note:
            Frame dtype depends on backend:
            - OpenCV: uint8 (0-255)
            - USB: uint16 (0-65535)
        """
        if not self.thermal_backend:
            logger.warning("Cannot read thermal: no backend initialized")
            return False, None

        return self.thermal_backend.read()

    def get_thermal_temperature_map(self):
        """
        Get temperature map from thermal camera (if radiometric).

        Returns:
            np.ndarray: Temperature map in Celsius (float32), or None if not radiometric

        Note:
            Only works with radiometric backends (PyUSB).
            Returns None for non-radiometric backends (OpenCV).
        """
        if not self.thermal_backend:
            logger.warning("Cannot get temperature map: no backend initialized")
            return None

        if not self.thermal_backend.is_radiometric():
            logger.debug("Current backend is not radiometric, cannot get temperature map")
            return None

        return self.thermal_backend.get_temperature_map()

    def get_thermal_fpa_temperature(self) -> Optional[float]:
        """
        Get FPA temperature from thermal camera (if available).

        Returns:
            float: FPA temperature in Celsius, or None if not available

        Note:
            Only available with OpenCV backend + SDK enabled.
            Not available with USB backend.
        """
        if not self.thermal_backend:
            return None

        return self.thermal_backend.get_fpa_temperature()

    def is_thermal_radiometric(self) -> bool:
        """
        Check if current thermal backend is radiometric.

        Returns:
            bool: True if radiometric, False otherwise
        """
        if not self.thermal_backend:
            return False

        return self.thermal_backend.is_radiometric()

    def get_thermal_info(self) -> Optional[Dict]:
        """
        Get information about current thermal backend.

        Returns:
            dict: Backend information, or None if no backend initialized
        """
        if not self.thermal_backend:
            return None

        info = self.thermal_backend.get_info()
        info['current_mode'] = self.thermal_mode
        return info

    def get_thermal_backend(self) -> Optional[ThermalBackend]:
        """
        Get the current thermal backend instance.

        This allows direct access to backend-specific features.

        Returns:
            ThermalBackend: Current backend, or None if not initialized
        """
        return self.thermal_backend

    def is_thermal_opened(self) -> bool:
        """
        Check if thermal camera is currently opened.

        Returns:
            bool: True if opened, False otherwise
        """
        if not self.thermal_backend:
            return False

        return self.thermal_backend.is_opened()

    def release_thermal(self):
        """Release thermal camera backend."""
        if self.thermal_backend:
            logger.info(f"Releasing thermal backend: {self.thermal_mode}")
            self.thermal_backend.release()
            self.thermal_backend = None
            self.thermal_mode = None

    def release_all(self):
        """Release all cameras."""
        self.release_thermal()

    def get_status_summary(self) -> Dict:
        """
        Get summary of camera manager status.

        Returns:
            dict: Status summary with info about all cameras
        """
        summary = {
            'thermal': {
                'initialized': self.thermal_backend is not None,
                'mode': self.thermal_mode,
                'opened': self.is_thermal_opened(),
                'radiometric': self.is_thermal_radiometric() if self.thermal_backend else None,
                'info': self.get_thermal_info()
            },
            'available_backends': self.get_available_thermal_backends()
        }

        return summary

    def __repr__(self) -> str:
        """String representation."""
        thermal_status = f"thermal={self.thermal_mode}" if self.thermal_mode else "thermal=None"
        return f"CameraManager({thermal_status})"
