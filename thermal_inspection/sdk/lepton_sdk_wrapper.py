#!/usr/bin/env python3
"""
FLIR Lepton SDK Wrapper
Implements the FLIR Lepton Software Interface Description Document (IDD) protocol.
Provides a high-level interface for controlling Lepton cameras via CCI/TWI (I2C).
"""

import time
import struct
import logging
from enum import Enum
from typing import Optional, Tuple
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)

# ============================================================================
# Constants & Enums (from IDD)
# ============================================================================

class LeptonModule(Enum):
    """Lepton Module IDs (IDD 2.1.3.2)"""
    AGC = 0x0100
    SYS = 0x0200
    VID = 0x0300
    OEM = 0x0800
    RAD = 0x0E00

class CommandType(Enum):
    """Command Types (IDD 2.1.3.4)"""
    GET = 0x00
    SET = 0x01
    RUN = 0x02

class LeptonRegister(Enum):
    """CCI/TWI Registers (IDD 2.1)"""
    POWER_ON = 0x0000
    STATUS = 0x0002
    COMMAND = 0x0004
    DATA_LENGTH = 0x0006
    DATA_0 = 0x0008
    # Data registers go up to 0x0026 (DATA 15)
    # Block buffer starts at 0xF800

# ============================================================================
# Abstract Transport Layer
# ============================================================================

class LeptonTransport(ABC):
    """
    Abstract base class for Lepton communication transport.
    Implementations could be UVC XU, UART, I2C (on embedded), etc.
    """

    @abstractmethod
    def write_register(self, address: int, value: int) -> None:
        """Write a 16-bit value to a register address."""
        pass

    @abstractmethod
    def read_register(self, address: int) -> int:
        """Read a 16-bit value from a register address."""
        pass

    @abstractmethod
    def write_data(self, data: bytes) -> None:
        """Write data to the data buffer (registers or block)."""
        pass

    @abstractmethod
    def read_data(self, length: int) -> bytes:
        """Read data from the data buffer."""
        pass

# ============================================================================
# Mock Transport (for testing/development)
# ============================================================================

class MockLeptonTransport(LeptonTransport):
    """Mock transport that simulates a Lepton camera."""

    def __init__(self):
        self.registers = {
            LeptonRegister.STATUS.value: 0x0006,  # Booted + Ready
            LeptonRegister.DATA_LENGTH.value: 0
        }
        self.data_buffer = bytearray(1024)
        logger.info("Mock Lepton Transport initialized")

    def write_register(self, address: int, value: int) -> None:
        # logger.debug(f"Mock Write Reg: 0x{address:04X} = 0x{value:04X}")
        self.registers[address] = value

        # Simulate command processing
        if address == LeptonRegister.COMMAND.value:
            # Set BUSY bit
            self.registers[LeptonRegister.STATUS.value] |= 0x0001
            # Simulate processing time
            time.sleep(0.01)
            # Clear BUSY bit, set success (0 in high byte)
            self.registers[LeptonRegister.STATUS.value] &= ~0x0001

    def read_register(self, address: int) -> int:
        val = self.registers.get(address, 0)
        # logger.debug(f"Mock Read Reg: 0x{address:04X} -> 0x{val:04X}")
        return val

    def write_data(self, data: bytes) -> None:
        # logger.debug(f"Mock Write Data: {len(data)} bytes")
        self.data_buffer[:len(data)] = data

    def read_data(self, length: int) -> bytes:
        # logger.debug(f"Mock Read Data: {length} bytes")
        return bytes(self.data_buffer[:length])

# ============================================================================
# Lepton SDK
# ============================================================================

class LeptonSDK:
    """
    High-level interface for Lepton camera control.
    """

    def __init__(self, transport: Optional[LeptonTransport] = None):
        self.transport = transport or MockLeptonTransport()
        self.timeout = 1.0  # seconds

    def _wait_for_ready(self) -> bool:
        """Wait for the camera to be ready (BUSY bit clear)."""
        start_time = time.time()
        while time.time() - start_time < self.timeout:
            status = self.transport.read_register(LeptonRegister.STATUS.value)
            if not (status & 0x0001):  # Check Bit 0 (BUSY)
                return True
            time.sleep(0.01)
        logger.error("Timeout waiting for Lepton ready")
        return False

    def run_command(self, module: LeptonModule, command_id: int,
                   cmd_type: CommandType,
                   data: Optional[bytes] = None,
                   data_len_words: int = 0) -> Tuple[bool, Optional[bytes]]:
        """
        Execute a Lepton CCI command.

        Args:
            module: Target module (AGC, SYS, etc.)
            command_id: Command ID (6 bits)
            cmd_type: GET, SET, or RUN
            data: Data bytes to write (for SET commands)
            data_len_words: Number of 16-bit words to read (for GET commands)

        Returns:
            (success, response_data)
        """
        if not self._wait_for_ready():
            return False, None

        # 1. Setup Data (if SET)
        if cmd_type == CommandType.SET and data:
            if len(data) % 2 != 0:
                logger.warning("Data length must be even (16-bit words)")
                # Pad if necessary
                data += b'\x00'

            word_count = len(data) // 2
            self.transport.write_register(LeptonRegister.DATA_LENGTH.value, word_count)
            self.transport.write_data(data)

        # 2. Setup Data Length (if GET)
        if cmd_type == CommandType.GET:
            self.transport.write_register(LeptonRegister.DATA_LENGTH.value, data_len_words)

        # 3. Issue Command
        # Command Register Format:
        # [15:14] Protection (OEM=1 for OEM/RAD)
        # [13:12] Reserved
        # [11:8]  Module ID
        # [7:2]   Command ID
        # [1:0]   Type

        cmd_reg_val = 0

        # Set Protection Bit for OEM and RAD modules
        if module in [LeptonModule.OEM, LeptonModule.RAD]:
            cmd_reg_val |= (1 << 14)

        # Module ID (masked to 4 bits)
        module_nibble = (module.value >> 8) & 0x0F
        cmd_reg_val |= (module_nibble << 8)

        # Command ID (masked to 6 bits)
        cmd_reg_val |= ((command_id & 0x3F) << 2)

        # Type
        cmd_reg_val |= (cmd_type.value & 0x03)

        self.transport.write_register(LeptonRegister.COMMAND.value, cmd_reg_val)

        # 4. Wait for Completion
        if not self._wait_for_ready():
            return False, None

        # 5. Check Status
        status = self.transport.read_register(LeptonRegister.STATUS.value)
        error_code = (status >> 8) & 0xFF
        # Convert 8-bit signed to int
        if error_code > 127:
            error_code -= 256

        if error_code != 0:
            logger.error(f"Lepton command error: {error_code}")
            return False, None

        # 6. Read Data (if GET)
        if cmd_type == CommandType.GET and data_len_words > 0:
            # Read back bytes (words * 2)
            return True, self.transport.read_data(data_len_words * 2)

        return True, None

    # ========================================================================
    # SYS Module (0x0200)
    # ========================================================================

    def get_serial_number(self) -> Optional[int]:
        """Get Camera Serial Number (SYS 0x0208)."""
        # Command ID 0x02 (SYS FLIR Serial Number) -> 0x08 / 4 = 0x02?
        # IDD 4.5.3: Command ID 0x02
        success, data = self.run_command(LeptonModule.SYS, 0x02, CommandType.GET, data_len_words=4)
        if success and data:
            # 64-bit int
            return struct.unpack('<Q', data)[0]
        return None

    def get_uptime(self) -> Optional[int]:
        """Get Camera Uptime in ms (SYS 0x0C)."""
        # IDD 4.5.4: Command ID 0x03
        success, data = self.run_command(LeptonModule.SYS, 0x03, CommandType.GET, data_len_words=2)
        if success and data:
            return struct.unpack('<I', data)[0]
        return None

    def get_fpa_temperature_celsius(self) -> Optional[float]:
        """Get FPA Temperature in Celsius (SYS 0x14)."""
        # IDD 4.5.6: Command ID 0x05 (Kelvin)
        # Value is in Kelvin * 100
        success, data = self.run_command(LeptonModule.SYS, 0x05, CommandType.GET, data_len_words=1)
        if success and data:
            kelvin_x100 = struct.unpack('<H', data)[0]
            celsius = (kelvin_x100 / 100.0) - 273.15
            return celsius
        return None

    def run_ffc(self) -> bool:
        """Run Flat Field Correction (SYS 0x42)."""
        # IDD 4.5.17: Command ID 0x10
        success, _ = self.run_command(LeptonModule.SYS, 0x10, CommandType.RUN)
        return success

    def get_ffc_status(self) -> Optional[str]:
        """Get FFC Status (SYS 0x44)."""
        # IDD 4.5.18: Command ID 0x11
        success, data = self.run_command(LeptonModule.SYS, 0x11, CommandType.GET, data_len_words=2)
        if success and data:
            status_val = struct.unpack('<I', data)[0]
            status_map = {
                0: "Ready",
                1: "Busy",
                2: "Frame Average",
                3: "Error"
            }
            return status_map.get(status_val, "Unknown")
        return None

    # ========================================================================
    # AGC Module (0x0100)
    # ========================================================================

    def set_agc_enable(self, enable: bool) -> bool:
        """Enable/Disable AGC (AGC 0x00)."""
        # IDD 4.4.1: Command ID 0x00
        val = 1 if enable else 0
        data = struct.pack('<I', val) # 32-bit enum
        success, _ = self.run_command(LeptonModule.AGC, 0x00, CommandType.SET, data=data)
        return success

    def get_agc_enable(self) -> Optional[bool]:
        """Get AGC Enable State."""
        success, data = self.run_command(LeptonModule.AGC, 0x00, CommandType.GET, data_len_words=2)
        if success and data:
            val = struct.unpack('<I', data)[0]
            return bool(val)
        return None

    def set_agc_policy(self, policy: str) -> bool:
        """Set AGC Policy (Linear or HEQ)."""
        # IDD 4.4.2: Command ID 0x01
        # 0=Linear, 1=HEQ
        val = 1 if policy.lower() == "heq" else 0
        data = struct.pack('<I', val)
        success, _ = self.run_command(LeptonModule.AGC, 0x01, CommandType.SET, data=data)
        return success

    # ========================================================================
    # RAD Module (0x0E00) - Radiometry
    # ========================================================================

    def set_rad_enable(self, enable: bool) -> bool:
        """Enable/Disable Radiometry (RAD 0x10)."""
        # IDD 4.8.3: Command ID 0x04 (Radiometry Control Enable)
        # Note: Requires Protection Bit
        val = 1 if enable else 0
        data = struct.pack('<I', val)
        success, _ = self.run_command(LeptonModule.RAD, 0x04, CommandType.SET, data=data)
        return success

    def set_tlinear_enable(self, enable: bool) -> bool:
        """Enable/Disable T-Linear Output (RAD 0xC0)."""
        # IDD 4.8.9: Command ID 0x30
        # 0=Disabled, 1=Enabled
        val = 1 if enable else 0
        data = struct.pack('<H', val) # 16-bit
        success, _ = self.run_command(LeptonModule.RAD, 0x30, CommandType.SET, data=data)
        return success

    def get_spotmeter_value(self) -> Optional[float]:
        """Get Spotmeter Value in Celsius (RAD 0xD0)."""
        # IDD 4.8.13: Command ID 0x34
        # Returns Kelvin * 100, Mean, Max, Min, Pop
        success, data = self.run_command(LeptonModule.RAD, 0x34, CommandType.GET, data_len_words=4)
        if success and data:
            # struct: mean, max, min, count (all uint16)
            mean_k, max_k, min_k, count = struct.unpack('<HHHH', data)
            celsius = (mean_k / 100.0) - 273.15
            return celsius
        return None

    def set_emissivity(self, emissivity: float) -> bool:
        """Set Emissivity (0.0 - 1.0)."""
        # Part of RAD Flux Linear Parameters (IDD 4.8.8)
        # This is a complex struct, for simplicity we might just set the one field if possible
        # or we need to read-modify-write.
        # Structure: SceneEmissivity (uint16, 0-8192 mapped to 0-1), TBkgK, TAuxK, etc.

        # 1. Get current params
        success, data = self.run_command(LeptonModule.RAD, 0x2C, CommandType.GET, data_len_words=8)
        if not success or not data:
            return False

        # Unpack
        # 0: SceneEmissivity (0-8192)
        # 1: TBkgK
        # 2: TWindowK
        # 3: TAtmK
        # 4: AtmTrans (0-8192)
        # 5: WindowTrans (0-8192)
        # 6: TObjK
        # 7: Reserved
        params = list(struct.unpack('<HHHHHHHH', data))

        # Update Emissivity
        # 8192 = 1.0, 82 = 0.01
        emiss_int = int(max(0.01, min(1.0, emissivity)) * 8192)
        params[0] = emiss_int

        # Pack and Set
        new_data = struct.pack('<HHHHHHHH', *params)
        success, _ = self.run_command(LeptonModule.RAD, 0x2C, CommandType.SET, data=new_data)
        return success

# ============================================================================
# Test / Usage Example
# ============================================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # Use Mock Transport
    sdk = LeptonSDK()

    logger.info("Connecting to (Mock) Lepton...")

    # Test SYS
    sn = sdk.get_serial_number()
    logger.info(f"Serial Number: {sn}")

    temp = sdk.get_fpa_temperature_celsius()
    logger.info(f"FPA Temp: {temp:.1f}°C")

    # Test FFC
    logger.info("Running FFC...")
    sdk.run_ffc()
    status = sdk.get_ffc_status()
    logger.info(f"FFC Status: {status}")

    # Test Radiometry
    logger.info("Enabling Radiometry...")
    sdk.set_rad_enable(True)
    sdk.set_tlinear_enable(True)

    logger.info("Setting Emissivity to 0.95...")
    sdk.set_emissivity(0.95)

    spot = sdk.get_spotmeter_value()
    logger.info(f"Spotmeter: {spot:.1f}°C")
