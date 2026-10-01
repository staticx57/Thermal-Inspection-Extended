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

# Status Codes (Byte 1 in response header). Cross-checked against flirpy 0.6 (flirpy/camera/tau.py) and a second
# independent Tau 2 driver, both derived from the Tau 2 / Quark Software IDD (102-PS242-43). An earlier version of this
# table was shifted by one (NOT_READY=0x01, a CHECKSUM_ERROR=0x03 that the IDD does not have).
STATUS_CAM_OK = 0x00
STATUS_CAM_NOT_READY = 0x02
STATUS_CAM_RANGE_ERROR = 0x03
STATUS_CAM_UNDEFINED_ERROR = 0x04
STATUS_CAM_UNDEFINED_PROCESS_ERROR = 0x05
STATUS_CAM_UNDEFINED_FUNCTION_ERROR = 0x06
STATUS_CAM_TIMEOUT_ERROR = 0x07
STATUS_CAM_BYTE_COUNT_ERROR = 0x09
STATUS_CAM_FEATURE_NOT_ENABLED = 0x0A

STATUS_MESSAGES = {
    STATUS_CAM_NOT_READY: "camera not ready (try again in a moment)",
    STATUS_CAM_RANGE_ERROR: "argument out of range",
    STATUS_CAM_UNDEFINED_ERROR: "undefined error",
    STATUS_CAM_UNDEFINED_PROCESS_ERROR: "undefined process code",
    STATUS_CAM_UNDEFINED_FUNCTION_ERROR: "function not supported by this camera/firmware",
    STATUS_CAM_TIMEOUT_ERROR: "camera timed out",
    STATUS_CAM_BYTE_COUNT_ERROR: "wrong number of argument bytes",
    STATUS_CAM_FEATURE_NOT_ENABLED: "feature not enabled on this camera",
}

# Function Opcodes (Byte 3). Same provenance as the status table. The previous table put AGC at 0x0E (FFC temperature
# delta), digital output at 0x11 (video orientation), "shutter position" at 0x1E (LENS NUMBER), spot meter at 0x2B/0x2C and
# READ_SENSOR at 0x4E: writing any of those on a real camera would have changed an unrelated setting.
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
CMD_COLOR_LUT = 0x10                 # VIDEO_PALETTE
CMD_DIGITAL_OUTPUT_MODE = 0x12
CMD_AGC_TYPE = 0x13
CMD_LENS_NUMBER = 0x1E
CMD_SPOT_METER_MODE = 0x1F
CMD_READ_SENSOR = 0x20               # FPA / housing temperature, accelerometer, core status
CMD_TEST_PATTERN = 0x25
CMD_SHUTTER_POSITION = 0x79
CMD_TLINEAR = 0x8E                   # TLinear output resolution (sub-command 0x0010)

# READ_SENSOR arguments
SENSOR_FPA_TEMPERATURE = 0x0000
SENSOR_HOUSING_TEMPERATURE = 0x000A
SENSOR_CORE_STATUS = 0x0011
# TLINEAR sub-command and values: 0 = low resolution (0.4 K/count), 1 = high resolution (0.04 K/count)
TLINEAR_SUBCOMMAND_RESOLUTION = 0x0010
TLINEAR_KELVIN_PER_COUNT = {True: 0.04, False: 0.4}


class Tau2StatusError(Exception):
    """Raised when Tau2 returns an error status code."""
    def __init__(self, status_code: int, message: str = ""):
        self.status_code = status_code
        meaning = STATUS_MESSAGES.get(status_code, "unknown status")
        super().__init__(f"Tau 2 Error [0x{status_code:02X}] {meaning}: {message}")


class Tau2CRCError(Exception):
    """Raised when CRC verification fails on a received packet."""
    pass


class Tau2TimeoutError(Exception):
    """Raised when camera response times out."""
    pass


class GainMode(IntEnum):
    """Tau 2 IDD GAIN_MODE values: 0 automatic, 1 low gain only, 2 high gain only, 3 manual. (The Boson's numbering is
    HIGH=0, LOW=1, AUTO=2: this enum used to copy it, which on a Tau 2 would have selected the opposite gain.)"""
    AUTO = 0
    LOW = 1
    HIGH = 2
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

    def set_agc_type(self, agc_type: int) -> bool:
        """Set AGC algorithm type (0=Plateau, 1=Linear, 2=Auto Dynamic, 3=Once Bright, 4=Info-Based)."""
        status, _ = self.send_command(CMD_AGC_TYPE, struct.pack(">H", agc_type))
        return status == STATUS_CAM_OK

    def get_agc_type(self) -> int:
        """Query active AGC algorithm type."""
        _, data = self.send_command(CMD_AGC_TYPE)
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

    def set_tlinear_resolution(self, high_res: bool = True) -> bool:
        """Resolution of the TLinear digital output: high = 0.04 K/count, low = 0.4 K/count (IDD TLINEAR 0x8E)."""
        status, _ = self.send_command(CMD_TLINEAR, struct.pack(">HH", TLINEAR_SUBCOMMAND_RESOLUTION,
                                                               0x0001 if high_res else 0x0000))
        return status == STATUS_CAM_OK

    def get_tlinear_resolution(self) -> Optional[bool]:
        """True = high (0.04 K/count), False = low (0.4 K/count), None if the camera did not answer."""
        _, data = self.send_command(CMD_TLINEAR, struct.pack(">H", TLINEAR_SUBCOMMAND_RESOLUTION))
        if len(data) >= 2:
            return struct.unpack(">H", data[:2])[0] == 0x0001
        return None

    def set_tlinear_mode(self, enabled: bool, high_res: bool = True) -> bool:
        """
        Select the TLinear output resolution. The IDD's TLINEAR command only sets the RESOLUTION of the TLinear
        digital output; turning TLinear output on is part of the digital output format (DIGITAL_OUTPUT_MODE / the
        capture hardware), so `enabled=False` is not something this command can do and is reported as such.
        """
        if not enabled:
            logger.warning("Tau 2: TLinear output cannot be switched off through the TLINEAR command; "
                           "change the digital output format instead")
            return False
        return self.set_tlinear_resolution(high_res)

    def get_tlinear_mode(self) -> Tuple[bool, bool]:
        """Returns (enabled, is_high_res). `enabled` is assumed True when the camera answers (see set_tlinear_mode)."""
        high = self.get_tlinear_resolution()
        return (high is not None), (True if high is None else high)

    def _read_sensor(self, argument: int) -> Optional[int]:
        _, data = self.send_command(CMD_READ_SENSOR, struct.pack(">H", argument))
        return struct.unpack(">h", data[:2])[0] if len(data) >= 2 else None

    def get_fpa_temperature(self) -> float:
        """Returns Focal Plane Array (FPA) temperature in Celsius (the camera reports 0.1 C units)."""
        raw = self._read_sensor(SENSOR_FPA_TEMPERATURE)
        return raw / 10.0 if raw is not None else 0.0

    def get_housing_temperature(self) -> float:
        """Returns camera housing temperature in Celsius (the camera reports 0.01 C units)."""
        raw = self._read_sensor(SENSOR_HOUSING_TEMPERATURE)
        return raw / 100.0 if raw is not None else 0.0

    def get_core_status(self) -> dict:
        """Core health flags: overtemp (remove power!), needs_ffc, suggest_gain_switch, suggest_nuc_switch, ffc_in_progress."""
        _, data = self.send_command(CMD_READ_SENSOR, struct.pack(">H", SENSOR_CORE_STATUS))
        status = struct.unpack(">H", data[:2])[0] if len(data) >= 2 else 0
        return {"overtemp": bool(status & (1 << 0)), "needs_ffc": bool(status & (1 << 2)),
                "suggest_gain_switch": bool(status & (1 << 3)), "suggest_nuc_switch": bool(status & (1 << 5)),
                "ffc_in_progress": bool(status & (1 << 6)), "raw": status}

    def set_test_pattern(self, mode: int = 1) -> bool:
        """Built-in digital test pattern (0 = off): isolates video-path problems from the sensor."""
        status, _ = self.send_command(CMD_TEST_PATTERN, struct.pack(">H", int(mode)))
        return status == STATUS_CAM_OK

    def get_shutter_position(self) -> Optional[int]:
        """0 = open, 1 = closed."""
        _, data = self.send_command(CMD_SHUTTER_POSITION)
        return struct.unpack(">H", data[:2])[0] if len(data) >= 2 else None


def scan_tau2_ports() -> List[str]:
    """
    Find COM ports a Tau 2 breakout board's CCI serial interface is likely on.

    "flir" is deliberately excluded from the keyword match - a Boson's own
    serial control port also self-identifies as "FLIR Control", and with
    both cameras attached this keyword claimed the Boson's COM port as a
    Tau2 candidate too. Returns empty (not "every port on the system") when
    nothing matches: a Tau2 breakout board with no exposed CCI line (video-
    only, confirmed to exist in the wild) has no serial port at all, and
    guessing a random unrelated port (Bluetooth, AMT SOL) to connect to is
    worse than reporting none.
    """
    ports = serial.tools.list_ports.comports()
    results = []
    for p in ports:
        desc = (p.description or "").lower()
        hwid = (p.hwid or "").lower()
        if any(k in desc or k in hwid for k in ["tau", "ftdi", "thermalcapture"]):
            results.append(p.device)
    return results
