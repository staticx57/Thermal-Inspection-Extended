"""
FLIR Tau 2 Serial Communication Module.

Implements the Camera Control Interface (CCI) protocol for FLIR / Teledyne Tau 2
thermal camera cores according to the Tau 2 / Quark Software IDD (102-PS242-43).

Features:
- Process Code 0x6E with two-stage 16-bit CRC-CCITT (polynomial 0x1021, seed 0x0000)
- Baud rate configuration (default 57600 baud, 8N1)
- Flat Field Correction (FFC / NUC) shutter control
- Gain mode (High / Low / Auto / Manual)
- Palette / Color LUT selection
- Radiometric T-Linear mode control (0.04 K / count and 0.4 K / count)
- Sensor telemetry & FPA temperature reading
"""
import binascii
import logging
import struct
from enum import IntEnum
from typing import Optional, Tuple, List

import serial
import serial.tools.list_ports

logger = logging.getLogger(__name__)

# Protocol Constants
TAU2_PROCESS_CODE = 0x6E

# Status Codes (Byte 1 in response header)
STATUS_CAM_OK = 0x00
STATUS_CAM_NOT_READY = 0x01
STATUS_CAM_RANGE_ERROR = 0x02
STATUS_CAM_CHECKSUM_ERROR = 0x03
STATUS_CAM_UNDEFINED_PROCESS_ERROR = 0x04
STATUS_CAM_UNDEFINED_FUNCTION_ERROR = 0x05
STATUS_CAM_TIMEOUT_ERROR = 0x06
STATUS_CAM_BYTE_COUNT_ERROR = 0x09
STATUS_CAM_FEATURE_NOT_ENABLED = 0x0A

# Function Opcodes (Byte 3)
CMD_NO_OP = 0x00
CMD_SET_DEFAULTS = 0x01
CMD_CAMERA_RESET = 0x02
CMD_RESTORE_FACTORY = 0x03
CMD_GET_SERIAL_NUMBER = 0x04
CMD_GET_REVISION = 0x05
CMD_BAUD_RATE = 0x07
CMD_GAIN_MODE = 0x0A
CMD_FFC_MODE = 0x0B
CMD_DO_FFC = 0x0C
CMD_AGC_TYPE = 0x0E
CMD_COLOR_LUT = 0x10
CMD_DIGITAL_OUTPUT_MODE = 0x11
CMD_DIGITAL_OUTPUT_FORMAT = 0x12
CMD_SHUTTER_POSITION = 0x1E
CMD_TLINEAR_MODE = 0x2A
CMD_SPOT_METER = 0x2B
CMD_SPOT_METER_DATA = 0x2C
CMD_READ_SENSOR = 0x4E


class Tau2StatusError(Exception):
    """Raised when Tau2 returns an error status code."""
    def __init__(self, status_code: int, message: str = ""):
        self.status_code = status_code
        super().__init__(f"Tau 2 Error [0x{status_code:02X}]: {message}")


class Tau2CRCError(Exception):
    """Raised when CRC verification fails on a received packet."""
    pass


class Tau2TimeoutError(Exception):
    """Raised when camera response times out."""
    pass


class GainMode(IntEnum):
    HIGH = 0
    LOW = 1
    AUTO = 2
    MANUAL = 3


class FFCMode(IntEnum):
    MANUAL = 0
    AUTO = 1
    EXTERNAL = 2


class AGCType(IntEnum):
    PLATEAU = 0
    LINEAR = 1
    AUTO_DYNAMIC = 2
    ONCE_BRIGHT = 3
    INFO_BASED = 4


class ColorLUT(IntEnum):
    WHITE_HOT = 0
    BLACK_HOT = 1
    FUSION = 2
    RAINBOW = 3
    GLOBOW = 4
    IRONBOW = 5
    COLOR1 = 6
    COLOR2 = 7
    ICE_FIRE = 8


class Tau2Serial:
    """
    Serial controller interface for FLIR Tau 2 cameras.
    """

    def __init__(self, port: str, baudrate: int = 57600, timeout: float = 1.5):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.ser: Optional[serial.Serial] = None
        self._open()

    def _open(self):
        try:
            self.ser = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=self.timeout
            )
            logger.info(f"Tau 2 serial port {self.port} opened at {self.baudrate} baud")
        except Exception as e:
            logger.error(f"Failed to open Tau 2 serial port {self.port}: {e}")
            self.ser = None
            raise

    def is_open(self) -> bool:
        return self.ser is not None and self.ser.is_open

    def close(self):
        if self.ser and self.ser.is_open:
            self.ser.close()
            logger.info(f"Tau 2 serial port {self.port} closed")
        self.ser = None

    @staticmethod
    def _calc_crc(data: bytes) -> int:
        """Computes 16-bit CRC-CCITT (poly 0x1021, seed 0x0000)."""
        return binascii.crc_hqx(data, 0)

    def send_command(self, func_code: int, arg_bytes: bytes = b"") -> Tuple[int, bytes]:
        """
        Send a formatted Tau 2 packet and read back response payload.

        Args:
            func_code: Opcode byte.
            arg_bytes: Argument bytes (big-endian).

        Returns:
            Tuple of (status_code, response_argument_bytes).
        """
        if not self.is_open():
            raise RuntimeError("Tau 2 serial port is not open")

        byte_count = len(arg_bytes)

        # 1. Construct 6-byte header
        header = struct.pack(">BBBBH", TAU2_PROCESS_CODE, 0x00, 0x00, func_code, byte_count)
        crc1 = self._calc_crc(header)
        header_packet = header + struct.pack(">H", crc1)

        # 2. Append arguments and CRC2 if payload present
        packet = bytearray(header_packet)
        if byte_count > 0:
            crc2 = self._calc_crc(arg_bytes)
            packet.extend(arg_bytes)
            packet.extend(struct.pack(">H", crc2))

        # 3. Transmit
        self.ser.reset_input_buffer()
        self.ser.write(packet)
        self.ser.flush()

        # 4. Read 8-byte response header
        resp_header = self.ser.read(8)
        if len(resp_header) < 8:
            raise Tau2TimeoutError("Tau 2 command timed out waiting for header")

        resp_proc, resp_status, _, resp_func, resp_count, resp_crc1 = struct.unpack(">BBBBHH", resp_header)

        # Verify CRC1
        expected_crc1 = self._calc_crc(resp_header[:6])
        if resp_crc1 != expected_crc1:
            raise Tau2CRCError(f"Header CRC mismatch: got 0x{resp_crc1:04X}, expected 0x{expected_crc1:04X}")

        if resp_status != STATUS_CAM_OK:
            raise Tau2StatusError(resp_status, f"Command 0x{func_code:02X} failed")

        # 5. Read argument bytes if present
        resp_args = b""
        if resp_count > 0:
            resp_args = self.ser.read(resp_count)
            resp_crc2_bytes = self.ser.read(2)
            if len(resp_args) < resp_count or len(resp_crc2_bytes) < 2:
                raise Tau2TimeoutError("Tau 2 command timed out waiting for payload")
            resp_crc2 = struct.unpack(">H", resp_crc2_bytes)[0]
            expected_crc2 = self._calc_crc(resp_args)
            if resp_crc2 != expected_crc2:
                raise Tau2CRCError(f"Payload CRC mismatch: got 0x{resp_crc2:04X}, expected 0x{expected_crc2:04X}")

        return resp_status, resp_args

    def ping(self) -> bool:
        """Ping camera core via NO_OP command."""
        try:
            status, _ = self.send_command(CMD_NO_OP)
            return status == STATUS_CAM_OK
        except Exception:
            return False

    def get_serial_number(self) -> Tuple[int, int]:
        """Returns (camera_sn, sensor_sn)."""
        _, data = self.send_command(CMD_GET_SERIAL_NUMBER)
        if len(data) >= 8:
            return struct.unpack(">II", data[:8])
        return 0, 0

    def get_revision(self) -> str:
        """Returns firmware build revision string."""
        _, data = self.send_command(CMD_GET_REVISION)
        if len(data) >= 4:
            sw_major, sw_minor, f_major, f_minor = struct.unpack(">BBBB", data[:4])
            return f"v{sw_major}.{sw_minor} (FW v{f_major}.{f_minor})"
        return "Unknown"

    def do_ffc(self) -> bool:
        """Trigger Flat Field Correction (NUC) shutter cycle."""
        status, _ = self.send_command(CMD_DO_FFC)
        return status == STATUS_CAM_OK

    def set_gain_mode(self, mode: int) -> bool:
        """Set sensor gain mode (0=HIGH, 1=LOW, 2=AUTO, 3=MANUAL)."""
        status, _ = self.send_command(CMD_GAIN_MODE, struct.pack(">H", mode))
        return status == STATUS_CAM_OK

    def get_gain_mode(self) -> int:
        """Query current sensor gain mode."""
        _, data = self.send_command(CMD_GAIN_MODE)
        if len(data) >= 2:
            return struct.unpack(">H", data[:2])[0]
        return 0

    def set_ffc_mode(self, mode: int) -> bool:
        """Set FFC mode (0=MANUAL, 1=AUTO, 2=EXTERNAL)."""
        status, _ = self.send_command(CMD_FFC_MODE, struct.pack(">H", mode))
        return status == STATUS_CAM_OK

    def get_ffc_mode(self) -> int:
        """Query current FFC mode."""
        _, data = self.send_command(CMD_FFC_MODE)
        if len(data) >= 2:
            return struct.unpack(">H", data[:2])[0]
        return 0

    def set_color_lut(self, lut_id: int) -> bool:
        """Set hardware palette / Color LUT."""
        status, _ = self.send_command(CMD_COLOR_LUT, struct.pack(">H", lut_id))
        return status == STATUS_CAM_OK

    def get_color_lut(self) -> int:
        """Query active hardware palette."""
        _, data = self.send_command(CMD_COLOR_LUT)
        if len(data) >= 2:
            return struct.unpack(">H", data[:2])[0]
        return 0

    def set_shutter_position(self, position: int) -> bool:
        """0=OPEN, 1=CLOSED."""
        status, _ = self.send_command(CMD_SHUTTER_POSITION, struct.pack(">H", position))
        return status == STATUS_CAM_OK

    def set_tlinear_mode(self, enabled: bool, high_res: bool = True) -> bool:
        """Configure Advanced Radiometry T-Linear mode."""
        en_val = 0x0001 if enabled else 0x0000
        res_val = 0x0000 if high_res else 0x0001
        status, _ = self.send_command(CMD_TLINEAR_MODE, struct.pack(">HH", en_val, res_val))
        return status == STATUS_CAM_OK

    def get_tlinear_mode(self) -> Tuple[bool, bool]:
        """Returns (enabled, is_high_res)."""
        _, data = self.send_command(CMD_TLINEAR_MODE)
        if len(data) >= 4:
            en_val, res_val = struct.unpack(">HH", data[:4])
            return (en_val == 0x0001), (res_val == 0x0000)
        return False, True

    def get_fpa_temperature(self) -> float:
        """Returns Focal Plane Array (FPA) temperature in Celsius."""
        _, data = self.send_command(CMD_READ_SENSOR, struct.pack(">H", 0x0000))
        if len(data) >= 2:
            counts_tenth_k = struct.unpack(">H", data[:2])[0]
            temp_k = counts_tenth_k / 10.0
            return temp_k - 273.15
        return 0.0

    def get_housing_temperature(self) -> float:
        """Returns camera housing temperature in Celsius."""
        _, data = self.send_command(CMD_READ_SENSOR, struct.pack(">H", 0x0001))
        if len(data) >= 2:
            counts_tenth_k = struct.unpack(">H", data[:2])[0]
            temp_k = counts_tenth_k / 10.0
            return temp_k - 273.15
        return 0.0


def scan_tau2_ports() -> List[str]:
    """Scan available serial ports for potential Tau 2 camera interfaces."""
    ports = serial.tools.list_ports.comports()
    results = []
    for p in ports:
        desc = (p.description or "").lower()
        hwid = (p.hwid or "").lower()
        if any(k in desc or k in hwid for k in ["tau", "flir", "ftdi", "thermalcapture", "usb serial"]):
            results.append(p.device)
    return results if results else [p.device for p in ports]
