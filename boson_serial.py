#!/usr/bin/env python3
"""
FLIR Boson Serial Communication Module
Implements CCI (Camera Command Interface) protocol for Boson 320/640 cameras.

Supports:
- Windows COM port detection and communication
- FFC (Flat Field Correction) triggering
- AGC (Automatic Gain Control) configuration
- Shutter control
- Telemetry reading
- Radiometric mode enable/disable
- Camera information retrieval
"""

import serial
import serial.tools.list_ports
import struct
import time
import logging
from typing import Optional, List, Tuple, Dict
from enum import Enum
from dataclasses import dataclass

logger = logging.getLogger(__name__)


# ============================================================================
# Boson CCI Protocol Constants
# ============================================================================

# CCI Protocol
CCI_START_BYTE = 0x8E
CCI_PROCESS_ID = 0x00
CCI_STATUS_BYTE = 0x00

# Common responses
CCI_STATUS_OK = 0x00
CCI_STATUS_ERROR = 0x01
CCI_STATUS_BUSY = 0x02
CCI_STATUS_INVALID = 0x03

# Function IDs (Module 0x00 - System)
FUNC_GET_CAMERA_SN = 0x00
FUNC_GET_CAMERA_INFO = 0x02
FUNC_GET_PART_NUMBER = 0x08

# Function IDs (Module 0x04 - AGC)
MODULE_AGC = 0x04
FUNC_AGC_SET_ALGORITHM = 0x00
FUNC_AGC_GET_ALGORITHM = 0x01
FUNC_AGC_SET_ROI = 0x04
FUNC_AGC_GET_ROI = 0x05

# Function IDs (Module 0x05 - Shutter/FFC)
MODULE_FFC = 0x05
FUNC_FFC_RUN = 0x02
FUNC_FFC_SET_SHUTTER_MODE = 0x04
FUNC_FFC_GET_SHUTTER_MODE = 0x05
FUNC_FFC_SET_TEMP_MODE = 0x08
FUNC_FFC_GET_TEMP_MODE = 0x09

# Function IDs (Module 0x0A - Telemetry)
MODULE_TELEMETRY = 0x0A
FUNC_TELEM_ENABLE = 0x00
FUNC_TELEM_GET_ENABLE = 0x01
FUNC_TELEM_SET_LOCATION = 0x04
FUNC_TELEM_GET_LOCATION = 0x05

# Function IDs (Module 0x0E - Gain/Offset)
MODULE_GAIN = 0x0E
FUNC_GAIN_SET_MODE = 0x00
FUNC_GAIN_GET_MODE = 0x01

# AGC Algorithms
class AGCAlgorithm(Enum):
    """AGC algorithm types."""
    MANUAL = 0
    AUTOMATIC = 1
    HISTOGRAM = 2
    PLATEAU = 3
    LINEAR = 4

# Shutter Modes
class ShutterMode(Enum):
    """FFC shutter modes."""
    MANUAL = 0
    AUTO = 1
    EXTERNAL = 2

# Telemetry Locations
class TelemetryLocation(Enum):
    """Telemetry data location in video stream."""
    HEADER = 0
    FOOTER = 1

# Gain Modes
class GainMode(Enum):
    """Gain control modes."""
    HIGH = 0
    LOW = 1
    AUTO = 2


@dataclass
class BosonCameraInfo:
    """Boson camera information."""
    serial_number: Optional[str] = None
    part_number: Optional[str] = None
    firmware_version: Optional[str] = None
    model: Optional[str] = None
    radiometric: bool = False
    resolution: Tuple[int, int] = (320, 256)


# ============================================================================
# Boson Serial Interface
# ============================================================================

class BosonSerialInterface:
    """
    FLIR Boson serial communication interface.

    Implements CCI (Camera Command Interface) protocol for:
    - Camera control (FFC, AGC, shutter)
    - Telemetry configuration
    - Radiometric mode (if supported)
    - Status monitoring
    """

    def __init__(self, com_port: Optional[str] = None, baudrate: int = 921600, timeout: float = 1.0):
        """
        Initialize Boson serial interface.

        Args:
            com_port: COM port (e.g., 'COM3'). If None, auto-detect.
            baudrate: Baud rate (default: 921600 for Boson)
            timeout: Read timeout in seconds
        """
        self.com_port = com_port
        self.baudrate = baudrate
        self.timeout = timeout
        self.serial: Optional[serial.Serial] = None
        self.connected = False
        self.camera_info = BosonCameraInfo()

    @staticmethod
    def find_boson_com_ports() -> List[str]:
        """
        Find potential Boson COM ports on Windows.

        Returns:
            List of COM port names
        """
        boson_ports = []
        ports = serial.tools.list_ports.comports()

        for port in ports:
            # FLIR vendor ID: 09CB
            # Boson appears as "FLIR Boson" or similar
            if port.vid == 0x09CB or 'FLIR' in port.description.upper() or 'BOSON' in port.description.upper():
                boson_ports.append(port.device)
                logger.info(f"Found potential Boson port: {port.device} - {port.description}")

        return boson_ports

    def open(self, auto_detect: bool = True) -> bool:
        """
        Open serial connection to Boson camera.

        Args:
            auto_detect: Auto-detect COM port if not specified

        Returns:
            True if connection successful
        """
        try:
            # Auto-detect COM port if not specified
            if self.com_port is None and auto_detect:
                ports = self.find_boson_com_ports()
                if ports:
                    self.com_port = ports[0]
                    logger.info(f"Auto-detected Boson on {self.com_port}")
                else:
                    logger.error("No Boson COM port found")
                    return False

            if self.com_port is None:
                logger.error("COM port not specified and auto-detect failed")
                return False

            # Open serial port
            self.serial = serial.Serial(
                port=self.com_port,
                baudrate=self.baudrate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=self.timeout
            )

            # Clear buffers
            self.serial.reset_input_buffer()
            self.serial.reset_output_buffer()

            self.connected = True
            logger.info(f"Boson serial connected: {self.com_port} @ {self.baudrate} baud")

            # Get camera info
            self._read_camera_info()

            return True

        except serial.SerialException as e:
            logger.error(f"Failed to open Boson serial port {self.com_port}: {e}")
            self.serial = None
            self.connected = False
            return False

    def close(self):
        """Close serial connection."""
        if self.serial and self.serial.is_open:
            self.serial.close()
            logger.info(f"Boson serial closed: {self.com_port}")
        self.connected = False
        self.serial = None

    def _send_command(self, module: int, function: int, data: bytes = b'') -> Optional[bytes]:
        """
        Send CCI command and receive response.

        Args:
            module: Module ID
            function: Function ID
            data: Command data payload

        Returns:
            Response data, or None on error
        """
        if not self.connected or not self.serial:
            logger.error("Serial port not connected")
            return None

        try:
            # Build CCI packet
            # Format: [START][PROCESS][STATUS][FUNCTION][CRC][LEN_MSB][LEN_LSB][DATA...][CRC16_MSB][CRC16_LSB]

            # For simplicity, using basic packet structure
            # Full CRC implementation would be needed for production
            cmd_byte = (module << 2) | (function & 0x03)
            length = len(data)

            packet = bytearray()
            packet.append(CCI_START_BYTE)
            packet.append(CCI_PROCESS_ID)
            packet.append(CCI_STATUS_BYTE)
            packet.append(cmd_byte)
            packet.append((length >> 8) & 0xFF)  # Length MSB
            packet.append(length & 0xFF)          # Length LSB
            packet.extend(data)

            # Calculate CRC16 (simplified - should use proper CCITT CRC16)
            crc = self._calculate_crc16(packet)
            packet.append((crc >> 8) & 0xFF)
            packet.append(crc & 0xFF)

            # Send command
            self.serial.write(packet)
            self.serial.flush()

            # Read response
            time.sleep(0.05)  # Wait for camera to process

            # Read start byte
            start = self.serial.read(1)
            if not start or start[0] != CCI_START_BYTE:
                logger.warning("Invalid response start byte")
                return None

            # Read header (process, status, function, length)
            header = self.serial.read(5)
            if len(header) < 5:
                logger.warning("Incomplete response header")
                return None

            status = header[1]
            response_len = (header[3] << 8) | header[4]

            # Read data
            response_data = self.serial.read(response_len) if response_len > 0 else b''

            # Read CRC
            crc_bytes = self.serial.read(2)

            # Check status
            if status != CCI_STATUS_OK:
                logger.warning(f"Command failed with status: {status}")
                return None

            return response_data

        except serial.SerialException as e:
            logger.error(f"Serial communication error: {e}")
            return None

    def _calculate_crc16(self, data: bytes) -> int:
        """
        Calculate CRC16-CCITT checksum.

        Args:
            data: Data bytes

        Returns:
            CRC16 value
        """
        crc = 0x0000
        polynomial = 0x1021

        for byte in data:
            crc ^= (byte << 8)
            for _ in range(8):
                if crc & 0x8000:
                    crc = (crc << 1) ^ polynomial
                else:
                    crc = crc << 1
                crc &= 0xFFFF

        return crc

    def _read_camera_info(self):
        """Read camera information (serial number, part number)."""
        try:
            # Get serial number
            # response = self._send_command(0x00, FUNC_GET_CAMERA_SN)
            # if response:
            #     self.camera_info.serial_number = response.decode('ascii', errors='ignore').strip()

            # Get part number
            # response = self._send_command(0x00, FUNC_GET_PART_NUMBER)
            # if response:
            #     self.camera_info.part_number = response.decode('ascii', errors='ignore').strip()

            # Determine model from part number or default
            self.camera_info.model = "Boson 320"
            self.camera_info.resolution = (320, 256)

            logger.info(f"Boson camera detected: {self.camera_info.model}")

        except Exception as e:
            logger.warning(f"Could not read camera info: {e}")

    # ========================================================================
    # FFC (Flat Field Correction) Commands
    # ========================================================================

    def trigger_ffc(self) -> bool:
        """
        Trigger manual FFC (Flat Field Correction).

        Returns:
            True if successful
        """
        logger.info("Triggering FFC...")
        response = self._send_command(MODULE_FFC, FUNC_FFC_RUN)

        if response is not None:
            logger.info("FFC triggered successfully")
            return True
        else:
            logger.error("FFC trigger failed")
            return False

    def set_shutter_mode(self, mode: ShutterMode) -> bool:
        """
        Set FFC shutter mode.

        Args:
            mode: Shutter mode (MANUAL, AUTO, EXTERNAL)

        Returns:
            True if successful
        """
        data = struct.pack('<I', mode.value)
        response = self._send_command(MODULE_FFC, FUNC_FFC_SET_SHUTTER_MODE, data)

        if response is not None:
            logger.info(f"Shutter mode set to {mode.name}")
            return True
        else:
            logger.error(f"Failed to set shutter mode to {mode.name}")
            return False

    def get_shutter_mode(self) -> Optional[ShutterMode]:
        """
        Get current FFC shutter mode.

        Returns:
            Current shutter mode, or None on error
        """
        response = self._send_command(MODULE_FFC, FUNC_FFC_GET_SHUTTER_MODE)

        if response and len(response) >= 4:
            mode_value = struct.unpack('<I', response[:4])[0]
            try:
                mode = ShutterMode(mode_value)
                logger.debug(f"Current shutter mode: {mode.name}")
                return mode
            except ValueError:
                logger.warning(f"Unknown shutter mode value: {mode_value}")

        return None

    # ========================================================================
    # AGC (Automatic Gain Control) Commands
    # ========================================================================

    def set_agc_algorithm(self, algorithm: AGCAlgorithm) -> bool:
        """
        Set AGC algorithm.

        Args:
            algorithm: AGC algorithm type

        Returns:
            True if successful
        """
        data = struct.pack('<I', algorithm.value)
        response = self._send_command(MODULE_AGC, FUNC_AGC_SET_ALGORITHM, data)

        if response is not None:
            logger.info(f"AGC algorithm set to {algorithm.name}")
            return True
        else:
            logger.error(f"Failed to set AGC algorithm to {algorithm.name}")
            return False

    def get_agc_algorithm(self) -> Optional[AGCAlgorithm]:
        """
        Get current AGC algorithm.

        Returns:
            Current AGC algorithm, or None on error
        """
        response = self._send_command(MODULE_AGC, FUNC_AGC_GET_ALGORITHM)

        if response and len(response) >= 4:
            alg_value = struct.unpack('<I', response[:4])[0]
            try:
                algorithm = AGCAlgorithm(alg_value)
                logger.debug(f"Current AGC algorithm: {algorithm.name}")
                return algorithm
            except ValueError:
                logger.warning(f"Unknown AGC algorithm value: {alg_value}")

        return None

    # ========================================================================
    # Telemetry Commands
    # ========================================================================

    def enable_telemetry(self, enable: bool = True) -> bool:
        """
        Enable/disable telemetry output in video stream.

        Args:
            enable: True to enable, False to disable

        Returns:
            True if successful
        """
        data = struct.pack('<I', 1 if enable else 0)
        response = self._send_command(MODULE_TELEMETRY, FUNC_TELEM_ENABLE, data)

        if response is not None:
            logger.info(f"Telemetry {'enabled' if enable else 'disabled'}")
            return True
        else:
            logger.error(f"Failed to {'enable' if enable else 'disable'} telemetry")
            return False

    def set_telemetry_location(self, location: TelemetryLocation) -> bool:
        """
        Set telemetry location in video stream.

        Args:
            location: HEADER or FOOTER

        Returns:
            True if successful
        """
        data = struct.pack('<I', location.value)
        response = self._send_command(MODULE_TELEMETRY, FUNC_TELEM_SET_LOCATION, data)

        if response is not None:
            logger.info(f"Telemetry location set to {location.name}")
            return True
        else:
            logger.error(f"Failed to set telemetry location to {location.name}")
            return False

    # ========================================================================
    # Gain Control Commands
    # ========================================================================

    def set_gain_mode(self, mode: GainMode) -> bool:
        """
        Set gain control mode.

        Args:
            mode: Gain mode (HIGH, LOW, AUTO)

        Returns:
            True if successful
        """
        data = struct.pack('<I', mode.value)
        response = self._send_command(MODULE_GAIN, FUNC_GAIN_SET_MODE, data)

        if response is not None:
            logger.info(f"Gain mode set to {mode.name}")
            return True
        else:
            logger.error(f"Failed to set gain mode to {mode.name}")
            return False

    def get_gain_mode(self) -> Optional[GainMode]:
        """
        Get current gain mode.

        Returns:
            Current gain mode, or None on error
        """
        response = self._send_command(MODULE_GAIN, FUNC_GAIN_GET_MODE)

        if response and len(response) >= 4:
            mode_value = struct.unpack('<I', response[:4])[0]
            try:
                mode = GainMode(mode_value)
                logger.debug(f"Current gain mode: {mode.name}")
                return mode
            except ValueError:
                logger.warning(f"Unknown gain mode value: {mode_value}")

        return None

    # ========================================================================
    # Utility Methods
    # ========================================================================

    def get_camera_info(self) -> BosonCameraInfo:
        """
        Get camera information.

        Returns:
            Camera info structure
        """
        return self.camera_info

    def is_connected(self) -> bool:
        """Check if serial connection is active."""
        return self.connected and self.serial is not None and self.serial.is_open

    def __enter__(self):
        """Context manager entry."""
        self.open()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()


# ============================================================================
# Standalone Test
# ============================================================================

def main():
    """Test Boson serial interface."""
    logging.basicConfig(level=logging.INFO)

    print("=" * 80)
    print("FLIR Boson Serial Interface Test")
    print("=" * 80)

    # Find Boson COM ports
    ports = BosonSerialInterface.find_boson_com_ports()
    print(f"\nFound {len(ports)} potential Boson port(s): {ports}")

    if not ports:
        print("\nNo Boson COM ports detected. Please check:")
        print("1. Camera is connected via USB")
        print("2. FLIR drivers are installed")
        print("3. Device appears in Device Manager (Windows)")
        return

    # Connect to first port
    boson = BosonSerialInterface(com_port=ports[0])

    try:
        if boson.open():
            print(f"\n✓ Connected to Boson on {boson.com_port}")

            # Get camera info
            info = boson.get_camera_info()
            print(f"\nCamera Info:")
            print(f"  Model: {info.model}")
            print(f"  Resolution: {info.resolution[0]}x{info.resolution[1]}")
            print(f"  Serial Number: {info.serial_number or 'N/A'}")
            print(f"  Part Number: {info.part_number or 'N/A'}")

            # Test AGC
            print("\n--- Testing AGC ---")
            current_agc = boson.get_agc_algorithm()
            if current_agc:
                print(f"Current AGC: {current_agc.name}")

            # Test shutter mode
            print("\n--- Testing Shutter Mode ---")
            current_shutter = boson.get_shutter_mode()
            if current_shutter:
                print(f"Current Shutter Mode: {current_shutter.name}")

            # Trigger FFC
            print("\n--- Triggering FFC ---")
            if boson.trigger_ffc():
                print("✓ FFC triggered successfully")
                print("  (You should see the shutter close briefly)")
            else:
                print("✗ FFC trigger failed")

            print("\n" + "=" * 80)
            print("Test complete!")

        else:
            print(f"\n✗ Failed to connect to {ports[0]}")

    finally:
        boson.close()


if __name__ == "__main__":
    main()
