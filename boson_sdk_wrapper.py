#!/usr/bin/env python3
"""
FLIR Boson SDK Wrapper
Uses the official FLIR Boson SDK from boson3dmapping project.
Provides simplified interface for inspection tool.
"""

import sys
import os
import logging
from typing import Optional, Tuple
from dataclasses import dataclass
from enum import Enum

# Add SDK path (local to inspection project)
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
SDK_BASE = os.path.join(CURRENT_DIR, '3.0 IDD & SDK', 'SDK_USER_PERMISSIONS')
SDK_PATH = os.path.join(SDK_BASE, 'SDK_USER_PERMISSIONS')

# Need to add base directory for relative imports to work
if os.path.exists(SDK_PATH):
    if SDK_BASE not in sys.path:
        sys.path.insert(0, SDK_BASE)
    if SDK_PATH not in sys.path:
        sys.path.insert(0, SDK_PATH)

    from SDK_USER_PERMISSIONS.ClientFiles_Python import Client_API
    from SDK_USER_PERMISSIONS.ClientFiles_Python.EnumTypes import (
        FLR_BOSON_GAINMODE_E,
        FLR_COLORLUT_ID_E
    )
    SDK_AVAILABLE = True
else:
    SDK_AVAILABLE = False
    print(f"WARNING: Boson SDK not found at {SDK_PATH}")

logger = logging.getLogger(__name__)


# ============================================================================
# Enumerations
# ============================================================================

class GainMode(Enum):
    """Boson gain modes."""
    HIGH = 0
    LOW = 1
    AUTO = 2
    MANUAL = 3


class FFCMode(Enum):
    """Boson FFC modes."""
    MANUAL = 0
    AUTO = 1
    EXTERNAL = 2


class ColorLUT(Enum):
    """Boson color lookup tables."""
    WHITE_HOT = 0
    BLACK_HOT = 1
    RAINBOW = 2
    RAINBOW_HC = 3
    IRONBOW = 4
    LAVA = 5
    ARCTIC = 6
    GLOBOW = 7
    GRADEDFIRE = 8
    HOTTEST = 9


@dataclass
class BosonInfo:
    """Boson camera information."""
    serial_number: Optional[str] = None
    camera_part_number: Optional[str] = None
    sensor_part_number: Optional[str] = None
    sensor_serial_number: Optional[str] = None
    software_version: Optional[str] = None
    fpa_temperature_k: Optional[float] = None
    gain_mode: Optional[GainMode] = None
    ffc_mode: Optional[FFCMode] = None
    frame_count: Optional[int] = None
    lens_number: Optional[int] = None
    table_number: Optional[int] = None


# ============================================================================
# Boson SDK Wrapper
# ============================================================================

class BosonSDK:
    """
    Wrapper for FLIR Boson SDK.
    Provides simplified interface for inspection tool.
    """

    def __init__(self, com_port: str = 'COM6', baudrate: int = 921600):
        """
        Initialize Boson SDK wrapper.

        Args:
            com_port: COM port (e.g., 'COM6')
            baudrate: Baud rate (default: 921600)
        """
        if not SDK_AVAILABLE:
            raise RuntimeError(f"Boson SDK not found. Expected at: {SDK_PATH}")

        self.com_port = com_port
        self.baudrate = baudrate
        self.camera = None
        self.connected = False
        self.info = BosonInfo()

    def open(self) -> bool:
        """
        Connect to Boson camera.

        Returns:
            True if successful
        """
        try:
            logger.info(f"Connecting to Boson on {self.com_port} @ {self.baudrate} baud...")
            self.camera = Client_API.pyClient(
                manualport=self.com_port,
                manualbaud=self.baudrate,
                useDll=True
            )
            self.connected = True
            logger.info("✓ Boson SDK connected successfully")

            # Read camera info
            self._read_camera_info()

            return True

        except Exception as e:
            logger.error(f"Failed to connect to Boson: {e}")
            self.camera = None
            self.connected = False
            return False

    def close(self):
        """Close connection to camera."""
        if self.camera:
            try:
                self.camera.Close()
                logger.info("Boson SDK disconnected")
            except Exception as e:
                logger.warning(f"Error closing Boson SDK: {e}")

        self.connected = False
        self.camera = None

    def _read_camera_info(self):
        """Read camera information."""
        if not self.connected or not self.camera:
            return

        try:
            # Serial number
            result, sn = self.camera.bosonGetCameraSN()
            if result.value == 0:
                self.info.serial_number = sn
                logger.debug(f"Camera SN: {sn}")

            # Software version
            result, major, minor, patch = self.camera.bosonGetSoftwareRev()
            if result.value == 0:
                self.info.software_version = f"{major}.{minor}.{patch}"
                logger.debug(f"Software: {self.info.software_version}")

            # Part numbers
            result, pn = self.camera.bosonGetCameraPN()
            if result.value == 0:
                self.info.camera_part_number = pn

            result, pn = self.camera.bosonGetSensorPN()
            if result.value == 0:
                self.info.sensor_part_number = pn

            # Sensor serial number
            result, sn = self.camera.bosonGetSensorSN()
            if result.value == 0:
                self.info.sensor_serial_number = sn

            # Temperature
            result, temp = self.camera.bosonlookupFPATempDegKx10()
            if result.value == 0:
                self.info.fpa_temperature_k = temp / 10.0

            # Gain mode
            result, mode = self.camera.bosonGetGainMode()
            if result.value == 0:
                self.info.gain_mode = GainMode(mode)

            # FFC mode
            result, mode = self.camera.bosonGetFFCMode()
            if result.value == 0:
                self.info.ffc_mode = FFCMode(mode)

            # Frame count
            result, count = self.camera.bosonGetISPFrameCount()
            if result.value == 0:
                self.info.frame_count = count

            # Lens/Table numbers
            result, num = self.camera.bosonGetLensNumber()
            if result.value == 0:
                self.info.lens_number = num

            result, num = self.camera.bosonGetTableNumber()
            if result.value == 0:
                self.info.table_number = num

        except Exception as e:
            logger.warning(f"Could not read full camera info: {e}")

    # ========================================================================
    # FFC Control
    # ========================================================================

    def run_ffc(self) -> bool:
        """
        Run Flat Field Correction.

        Returns:
            True if successful
        """
        if not self.connected or not self.camera:
            logger.error("Camera not connected")
            return False

        try:
            logger.info("Running FFC...")
            result = self.camera.bosonRunFFC()

            if result.value == 0:
                logger.info("✓ FFC completed successfully")
                return True
            else:
                logger.error(f"FFC failed with result: {result.value}")
                return False

        except Exception as e:
            logger.error(f"FFC error: {e}")
            return False

    def set_ffc_mode(self, mode: FFCMode) -> bool:
        """
        Set FFC mode.

        Args:
            mode: FFC mode (MANUAL, AUTO, EXTERNAL)

        Returns:
            True if successful
        """
        if not self.connected or not self.camera:
            return False

        try:
            result = self.camera.bosonSetFFCMode(mode.value)
            if result.value == 0:
                self.info.ffc_mode = mode
                logger.info(f"FFC mode set to {mode.name}")
                return True
            return False

        except Exception as e:
            logger.error(f"Failed to set FFC mode: {e}")
            return False

    def get_ffc_mode(self) -> Optional[FFCMode]:
        """Get current FFC mode."""
        return self.info.ffc_mode

    # ========================================================================
    # Gain Control
    # ========================================================================

    def set_gain_mode(self, mode: GainMode) -> bool:
        """
        Set gain mode.

        Args:
            mode: Gain mode

        Returns:
            True if successful
        """
        if not self.connected or not self.camera:
            return False

        try:
            # Convert to SDK enum
            sdk_mode = getattr(FLR_BOSON_GAINMODE_E, f'FLR_BOSON_{mode.name}_GAIN')
            result = self.camera.bosonSetGainMode(sdk_mode)

            if result.value == 0:
                self.info.gain_mode = mode
                logger.info(f"Gain mode set to {mode.name}")
                return True
            return False

        except Exception as e:
            logger.error(f"Failed to set gain mode: {e}")
            return False

    def get_gain_mode(self) -> Optional[GainMode]:
        """Get current gain mode."""
        return self.info.gain_mode

    # ========================================================================
    # Color LUT Control
    # ========================================================================

    def set_color_lut(self, lut: ColorLUT) -> bool:
        """
        Set color lookup table.

        Args:
            lut: Color LUT

        Returns:
            True if successful
        """
        if not self.connected or not self.camera:
            return False

        try:
            # Map to SDK enum value
            lut_map = {
                ColorLUT.WHITE_HOT: FLR_COLORLUT_ID_E.FLR_COLORLUT_WHITEHOT,
                ColorLUT.BLACK_HOT: FLR_COLORLUT_ID_E.FLR_COLORLUT_BLACKHOT,
                ColorLUT.RAINBOW: FLR_COLORLUT_ID_E.FLR_COLORLUT_RAINBOW,
                ColorLUT.RAINBOW_HC: FLR_COLORLUT_ID_E.FLR_COLORLUT_RAINBOWHC,
                ColorLUT.IRONBOW: FLR_COLORLUT_ID_E.FLR_COLORLUT_IRONBOW,
                ColorLUT.LAVA: FLR_COLORLUT_ID_E.FLR_COLORLUT_LAVA,
                ColorLUT.ARCTIC: FLR_COLORLUT_ID_E.FLR_COLORLUT_ARCTIC,
                ColorLUT.GLOBOW: FLR_COLORLUT_ID_E.FLR_COLORLUT_GLOBOW,
                ColorLUT.GRADEDFIRE: FLR_COLORLUT_ID_E.FLR_COLORLUT_GRADEDFIRE,
                ColorLUT.HOTTEST: FLR_COLORLUT_ID_E.FLR_COLORLUT_HOTTEST,
            }

            sdk_lut = lut_map.get(lut)
            if sdk_lut is None:
                logger.warning(f"LUT {lut.name} not mapped")
                return False

            result = self.camera.colorlutSetControl(sdk_lut)
            if result.value == 0:
                logger.info(f"Color LUT set to {lut.name}")
                return True
            return False

        except Exception as e:
            logger.error(f"Failed to set color LUT: {e}")
            return False

    # ========================================================================
    # Temperature Reading
    # ========================================================================

    def get_fpa_temperature(self) -> Optional[Tuple[float, float]]:
        """
        Get FPA (Focal Plane Array) temperature.

        Returns:
            (temperature_kelvin, temperature_celsius) or None
        """
        if not self.connected or not self.camera:
            return None

        try:
            result, temp = self.camera.bosonlookupFPATempDegKx10()
            if result.value == 0:
                temp_k = temp / 10.0
                temp_c = temp_k - 273.15
                return (temp_k, temp_c)
            return None

        except Exception as e:
            logger.error(f"Failed to get FPA temperature: {e}")
            return None

    # ========================================================================
    # Info Methods
    # ========================================================================

    def get_info(self) -> BosonInfo:
        """Get camera information."""
        return self.info

    def is_connected(self) -> bool:
        """Check if connected."""
        return self.connected

    def __enter__(self):
        """Context manager entry."""
        self.open()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()


# ============================================================================
# Test
# ============================================================================

def main():
    """Test Boson SDK wrapper."""
    logging.basicConfig(level=logging.INFO)

    print("="*80)
    print("FLIR Boson SDK Wrapper Test")
    print("="*80)

    if not SDK_AVAILABLE:
        print(f"\nERROR: Boson SDK not found at:")
        print(f"  {SDK_PATH}")
        print("\nPlease ensure the boson3dmapping project is available.")
        return 1

    print(f"\n✓ SDK found at: {SDK_PATH}")

    # Test connection
    with BosonSDK(com_port='COM6') as boson:
        if not boson.is_connected():
            print("\n✗ Failed to connect")
            return 1

        print("\n✓ Connected to Boson")

        # Display info
        info = boson.get_info()
        print("\nCamera Information:")
        print(f"  Serial Number: {info.serial_number}")
        print(f"  Software Version: {info.software_version}")
        print(f"  Camera PN: {info.camera_part_number}")
        print(f"  Sensor PN: {info.sensor_part_number}")
        print(f"  FPA Temp: {info.fpa_temperature_k:.1f}K ({info.fpa_temperature_k - 273.15:.1f}°C)")
        print(f"  Gain Mode: {info.gain_mode.name if info.gain_mode else 'Unknown'}")
        print(f"  FFC Mode: {info.ffc_mode.name if info.ffc_mode else 'Unknown'}")

        # Test FFC
        print("\n** Press Enter to trigger FFC (watch the camera shutter) **")
        input()

        if boson.run_ffc():
            print("✓ FFC triggered successfully!")
        else:
            print("✗ FFC failed")

    print("\n✓ Test complete!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
