"""
PyUSB Direct USB backend for FLIR Boson thermal camera.

Provides true 16-bit Y16 radiometric data via direct USB bulk transfers.

REQUIREMENTS:
- WinUSB driver (replaces UVC driver) installed via Zadig
- pyusb library: pip install pyusb
- libusb backend (automatically detected by pyusb)

WARNING:
- Installing WinUSB driver will break OpenCV/DirectShow access
- You cannot use both OpenCV and PyUSB simultaneously
- Use Zadig to switch drivers: UVC (for OpenCV) or WinUSB (for PyUSB)
"""

import numpy as np
from typing import Optional, Dict, Tuple
import logging

from camera_backends import ThermalBackend, BackendNotAvailableError, BackendInitializationError

logger = logging.getLogger(__name__)

# Try to import usb module
try:
    import usb.core
    import usb.util
    PYUSB_AVAILABLE = True
except ImportError:
    PYUSB_AVAILABLE = False
    logger.warning("PyUSB not installed. Install with: pip install pyusb")


class PyUSBThermalBackend(ThermalBackend):
    """
    Direct USB backend for FLIR Boson thermal camera.

    This backend bypasses the UVC driver and reads raw Y16 frames directly
    from USB bulk endpoints, providing true 16-bit radiometric data.

    Characteristics:
    - Bit depth: 16-bit (0-65535)
    - Radiometric: Yes (absolute temperature values)
    - Quality: True radiometric calibration
    - Accuracy: ±2°C absolute (per FLIR specs)
    - SDK Control: No (direct USB only)

    Temperature Conversion:
    - Pixel value represents Kelvin × 100
    - Formula: temp_celsius = (pixel_value / 100.0) - 273.15
    - Example: pixel=29815 → 298.15K → 25.0°C

    USB Details:
    - Vendor ID: 0x09CB (FLIR)
    - Product ID: 0x4007 (Boson 640)
    - Endpoint: EP1 IN (bulk transfer)
    - Frame size: 640×512×2 bytes + 12-byte UVC header
    """

    # FLIR USB identifiers
    VENDOR_ID = 0x09CB
    PRODUCT_ID_BOSON_640 = 0x4007

    # Frame parameters
    FRAME_WIDTH = 640
    FRAME_HEIGHT = 512
    BYTES_PER_PIXEL = 2  # 16-bit
    UVC_HEADER_SIZE = 12

    def __init__(self, vid: int = VENDOR_ID, pid: int = PRODUCT_ID_BOSON_640):
        """
        Initialize PyUSB thermal backend.

        Args:
            vid: USB Vendor ID (default: 0x09CB for FLIR)
            pid: USB Product ID (default: 0x4007 for Boson 640)
        """
        self.vid = vid
        self.pid = pid
        self.dev = None
        self.endpoint = None
        self._is_opened = False

        if not PYUSB_AVAILABLE:
            logger.error("PyUSB not available - cannot use direct USB backend")

    def is_available(self) -> bool:
        """
        Check if PyUSB can access the FLIR Boson.

        Returns:
            bool: True if camera is accessible via PyUSB

        Note:
            Requires WinUSB driver to be installed.
            Will return False if camera is using UVC driver.
        """
        if not PYUSB_AVAILABLE:
            logger.warning("PyUSB not installed")
            return False

        try:
            dev = usb.core.find(idVendor=self.vid, idProduct=self.pid)
            available = dev is not None

            if available:
                logger.info(f"PyUSB thermal backend available (VID:PID {self.vid:04X}:{self.pid:04X})")
            else:
                logger.warning(
                    f"PyUSB thermal backend not available - camera not found or using UVC driver\n"
                    f"To use 16-bit mode, install WinUSB driver with Zadig"
                )

            return available
        except Exception as e:
            logger.error(f"Error checking PyUSB thermal backend availability: {e}")
            return False

    def open(self) -> bool:
        """
        Open thermal camera via direct USB access.

        Returns:
            bool: True if camera opened successfully

        Raises:
            BackendNotAvailableError: If PyUSB is not installed
            BackendInitializationError: If camera fails to open
        """
        if not PYUSB_AVAILABLE:
            raise BackendNotAvailableError("PyUSB not installed. Install with: pip install pyusb")

        try:
            logger.info(f"Opening PyUSB thermal backend (VID:PID {self.vid:04X}:{self.pid:04X})")

            # Find device
            self.dev = usb.core.find(idVendor=self.vid, idProduct=self.pid)

            if self.dev is None:
                logger.error(
                    "✗ FLIR Boson not found via USB\n"
                    "  Possible causes:\n"
                    "  1. Camera not connected\n"
                    "  2. WinUSB driver not installed (use Zadig)\n"
                    "  3. Camera is using UVC driver (incompatible with PyUSB)"
                )
                return False

            # Get active configuration
            try:
                cfg = self.dev.get_active_configuration()
            except usb.core.USBError as e:
                # Try to set configuration
                logger.info("Setting USB configuration...")
                self.dev.set_configuration()
                cfg = self.dev.get_active_configuration()

            # Get video streaming interface
            intf = cfg[(0, 0)]  # Interface 0, alternate setting 0

            # Find bulk IN endpoint for video data
            for ep in intf:
                if usb.util.endpoint_direction(ep.bEndpointAddress) == usb.util.ENDPOINT_IN:
                    if usb.util.endpoint_type(ep.bmAttributes) == usb.util.ENDPOINT_TYPE_BULK:
                        self.endpoint = ep
                        break

            if self.endpoint is None:
                logger.error("✗ Could not find bulk IN endpoint for video data")
                return False

            self._is_opened = True
            logger.info("✓ PyUSB thermal backend opened successfully")
            logger.info(f"  Resolution: {self.FRAME_WIDTH}x{self.FRAME_HEIGHT}")
            logger.info(f"  Bit depth: 16-bit")
            logger.info(f"  Endpoint: 0x{self.endpoint.bEndpointAddress:02X}")
            logger.info(f"  Max packet size: {self.endpoint.wMaxPacketSize}")

            return True

        except usb.core.USBError as e:
            logger.error(f"USB error opening PyUSB thermal backend: {e}")
            raise BackendInitializationError(f"USB error: {e}")
        except Exception as e:
            logger.error(f"PyUSB thermal backend initialization error: {e}")
            raise BackendInitializationError(f"Failed to open PyUSB thermal backend: {e}")

    def read(self) -> Tuple[bool, Optional[np.ndarray]]:
        """
        Read 16-bit Y16 frame from USB.

        Returns:
            tuple: (success: bool, frame: np.ndarray with dtype=uint16 or None)

        Frame format:
            - UVC header: 12 bytes (skipped)
            - Pixel data: 640×512×2 bytes, little-endian uint16
        """
        if not self._is_opened or not self.dev or not self.endpoint:
            logger.warning("Cannot read: PyUSB thermal backend not opened")
            return False, None

        try:
            # Calculate expected data size
            frame_bytes = self.FRAME_WIDTH * self.FRAME_HEIGHT * self.BYTES_PER_PIXEL
            total_bytes = frame_bytes + self.UVC_HEADER_SIZE

            # Read bulk transfer
            data = self.dev.read(
                self.endpoint.bEndpointAddress,
                total_bytes,
                timeout=1000  # 1 second timeout
            )

            # Skip UVC header (first 12 bytes)
            frame_data = data[self.UVC_HEADER_SIZE:]

            # Convert to 16-bit array
            frame = np.frombuffer(frame_data, dtype=np.uint16)

            # Reshape to image dimensions
            frame = frame.reshape(self.FRAME_HEIGHT, self.FRAME_WIDTH)

            return True, frame

        except usb.core.USBError as e:
            logger.error(f"USB read error: {e}")
            return False, None
        except Exception as e:
            logger.error(f"Error reading from PyUSB thermal backend: {e}")
            return False, None

    def release(self):
        """Release USB device."""
        if self.dev:
            logger.info("Releasing PyUSB thermal backend")
            try:
                usb.util.dispose_resources(self.dev)
            except Exception as e:
                logger.warning(f"Error disposing USB resources: {e}")
            self.dev = None
            self.endpoint = None
        self._is_opened = False

    def is_opened(self) -> bool:
        """
        Check if camera is currently opened.

        Returns:
            bool: True if camera is opened
        """
        return self._is_opened and self.dev is not None

    def get_info(self) -> Dict:
        """
        Get backend information.

        Returns:
            dict: Backend information
        """
        info = {
            'backend': 'PyUSB Direct',
            'type': 'thermal',
            'bit_depth': 16,
            'radiometric': True,
            'resolution': (self.FRAME_WIDTH, self.FRAME_HEIGHT),
            'features': [
                'True 16-bit Y16 radiometric',
                'Absolute temperature values',
                '±2°C accuracy (per FLIR specs)',
                '65,536 gray levels',
                'Direct USB bulk transfer'
            ],
            'vid': f"0x{self.vid:04X}",
            'pid': f"0x{self.pid:04X}",
            'driver_required': 'WinUSB (install via Zadig)'
        }

        if self.endpoint and self._is_opened:
            info['endpoint'] = f"0x{self.endpoint.bEndpointAddress:02X}"
            info['max_packet_size'] = self.endpoint.wMaxPacketSize

        return info

    def get_resolution(self) -> Optional[Tuple[int, int]]:
        """
        Get current resolution.

        Returns:
            tuple: (width, height)
        """
        return (self.FRAME_WIDTH, self.FRAME_HEIGHT)

    def is_radiometric(self) -> bool:
        """
        Check if backend provides true radiometric data.

        Returns:
            bool: True (PyUSB backend provides true radiometric data)
        """
        return True

    def get_temperature_map(self) -> Optional[np.ndarray]:
        """
        Get temperature map in Celsius.

        Converts raw 16-bit Y16 values to temperature using FLIR formula:
        - temp_kelvin = pixel_value / 100.0
        - temp_celsius = temp_kelvin - 273.15

        Returns:
            np.ndarray: Temperature map in Celsius (float32), or None on error
        """
        ret, frame = self.read()
        if not ret or frame is None:
            return None

        try:
            # FLIR Y16 formula: pixel value = Kelvin × 100
            temp_k = frame.astype(np.float32) / 100.0
            temp_c = temp_k - 273.15

            return temp_c
        except Exception as e:
            logger.error(f"Error converting to temperature map: {e}")
            return None

    def supports_sdk_control(self) -> bool:
        """
        Check if SDK control is available.

        Returns:
            bool: False (PyUSB backend doesn't support SDK control)

        Note:
            Direct USB access is incompatible with SDK control via COM port.
            For SDK features (FFC, AGC modes), use OpenCV backend instead.
        """
        return False

    def get_fpa_temperature(self) -> Optional[float]:
        """
        Get FPA temperature (not available in USB mode).

        Returns:
            None: FPA temperature not available via direct USB

        Note:
            FPA temperature requires SDK access via COM port.
            Use OpenCV backend for FPA temperature reading.
        """
        return None

    def __repr__(self) -> str:
        """String representation."""
        status = "opened" if self._is_opened else "closed"
        return f"PyUSBThermalBackend(VID:PID {self.vid:04X}:{self.pid:04X}, {status})"
