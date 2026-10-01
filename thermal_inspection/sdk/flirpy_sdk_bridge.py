#!/usr/bin/env python3
"""
Flirpy SDK Bridge - Inject Boson SDK commands via flirpy's serial connection

This module provides SDK control functionality for FlirpyThermalBackend by
injecting Boson SDK command packets through flirpy's existing COM port connection.

Architecture:
- Uses flirpy.camera.boson.Boson's send() and receive() methods
- Does NOT create a separate COM port connection
- Reuses the packet encoding/decoding from flirpy internals
- Provides high-level methods matching BosonSDK wrapper API

Safety: All operations are tested to not interfere with Y16 video capture.
"""

import logging
from thermal_inspection.utils.paths import default_serial_port
from typing import Optional
from enum import Enum

logger = logging.getLogger(__name__)

# Enumerations matching BosonSDK
class GainMode(Enum):
    """Boson gain modes."""
    HIGH = 0  # -40 to 120°C
    LOW = 1   # up to 400°C
    AUTO = 2

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


class FlirpySDKBridge:
    """
    Bridge for sending Boson SDK commands through flirpy's serial connection.

    This class provides SDK control methods (gain mode, FFC, emissivity, etc.)
    without creating a separate COM port connection. Instead, it uses the
    existing flirpy.Boson camera's send/receive methods.

    Usage:
        camera = Boson(port=default_serial_port())
        bridge = FlirpySDKBridge(camera)
        bridge.set_gain_mode(GainMode.HIGH)
    """

    def __init__(self, flirpy_camera):
        """
        Initialize SDK bridge with an active flirpy camera instance.

        Args:
            flirpy_camera: Active flirpy.camera.boson.Boson instance
        """
        self.camera = flirpy_camera
        self._connected = hasattr(flirpy_camera, 'send') and hasattr(flirpy_camera, 'receive')

        if not self._connected:
            logger.warning("Flirpy camera lacks send/receive methods - SDK bridge unavailable")
        else:
            logger.info("✓ FlirpySDKBridge initialized with access to serial connection")

    def is_available(self) -> bool:
        """Check if SDK bridge is available."""
        return self._connected and self.camera is not None

    # =========================================================================
    # FFC Control (using native flirpy methods where possible)
    # =========================================================================

    def trigger_ffc(self) -> bool:
        """
        Trigger Flat Field Correction.

        Uses flirpy's native do_ffc() method for maximum compatibility.

        Returns:
            bool: True if successful
        """
        if not self.is_available():
            logger.warning("SDK bridge not available")
            return False

        try:
            self.camera.do_ffc()
            logger.info("✓ FFC triggered via flirpy")
            return True
        except Exception as e:
            logger.error(f"FFC failed: {e}")
            return False

    def set_ffc_mode(self, mode: FFCMode) -> bool:
        """
        Set FFC mode (AUTO/MANUAL/EXTERNAL).

        Args:
            mode: FFC mode enum

        Returns:
            bool: True if successful
        """
        if not self.is_available():
            logger.warning("SDK bridge not available")
            return False

        try:
            # Use flirpy's native FFC mode methods
            if mode == FFCMode.AUTO:
                self.camera.set_ffc_auto()
                logger.info("✓ FFC mode set to AUTO")
                return True
            elif mode == FFCMode.MANUAL:
                self.camera.set_ffc_manual()
                logger.info("✓ FFC mode set to MANUAL")
                return True
            else:
                logger.warning(f"FFC mode {mode.name} not natively supported by flirpy")
                # For EXTERNAL mode, would need to send raw SDK command
                return False

        except Exception as e:
            logger.error(f"Failed to set FFC mode: {e}")
            return False

    def get_ffc_mode(self) -> Optional[int]:
        """
        Get current FFC mode.

        Returns:
            int: FFC mode (0=MANUAL, 1=AUTO, 2=EXTERNAL) or None
        """
        if not self.is_available():
            return None

        try:
            mode = self.camera.get_ffc_mode()
            return mode
        except Exception as e:
            logger.error(f"Failed to get FFC mode: {e}")
            return None

    # =========================================================================
    # Temperature Queries (using native flirpy methods)
    # =========================================================================

    def get_fpa_temperature(self) -> Optional[float]:
        """
        Get FPA (Focal Plane Array) temperature in Celsius.

        Returns:
            float: FPA temperature or None
        """
        if not self.is_available():
            return None

        try:
            temp = self.camera.get_fpa_temperature()
            return temp
        except Exception as e:
            logger.debug(f"Could not get FPA temperature: {e}")
            return None

    # =========================================================================
    # Advanced SDK Commands (require raw packet injection)
    # =========================================================================

    def set_gain_mode(self, mode: GainMode) -> bool:
        """
        Set gain mode using raw SDK command packet.

        NOTE: This requires implementing raw SDK packet injection via
        camera.send(). Currently returns False as not implemented.

        Args:
            mode: Gain mode enum

        Returns:
            bool: True if successful
        """
        logger.warning(f"set_gain_mode({mode.name}) not yet implemented - requires raw SDK packet")
        logger.info("  Gain mode control will be available in Phase 2 implementation")
        return False

    def set_color_lut(self, lut: ColorLUT) -> bool:
        """
        Set color LUT using raw SDK command packet.

        NOTE: Not implemented - requires raw SDK packet injection.

        Args:
            lut: Color LUT enum

        Returns:
            bool: False (not implemented)
        """
        logger.warning(f"set_color_lut({lut.name}) not yet implemented - requires raw SDK packet")
        logger.info("  Color LUT control will be available in Phase 2 implementation")
        return False

    def set_emissivity(self, emissivity: float) -> bool:
        """
        Set target emissivity for temperature measurement.

        NOTE: Not implemented - requires raw SDK packet injection.

        Args:
            emissivity: Emissivity value (0.01-1.0)

        Returns:
            bool: False (not implemented)
        """
        logger.warning(f"set_emissivity({emissivity}) not yet implemented - requires raw SDK packet")
        logger.info("  Emissivity control will be available in Phase 2 implementation")
        return False

    # =========================================================================
    # Camera Information (using native flirpy methods)
    # =========================================================================

    def get_camera_serial(self) -> Optional[int]:
        """Get camera serial number."""
        if not self.is_available():
            return None

        try:
            return self.camera.get_camera_serial()
        except Exception as e:
            logger.debug(f"Could not get camera serial: {e}")
            return None

    def get_firmware_version(self) -> Optional[tuple]:
        """Get firmware version as (major, minor, patch)."""
        if not self.is_available():
            return None

        try:
            return self.camera.get_firmware_revision()
        except Exception as e:
            logger.debug(f"Could not get firmware version: {e}")
            return None


# Phase 2: Advanced SDK packet injection (to be implemented)
#
# The following methods will require implementing raw SDK command packet
# construction and injection via camera.send()/receive():
#
# - set_gain_mode() - Priority: HIGH
# - set_color_lut() - Priority: MEDIUM
# - set_emissivity() - Priority: HIGH
# - get_lens_temperature() - Priority: LOW
# - get_shutter_temperature() - Priority: LOW
#
# Implementation approach:
# 1. Study flirpy's _send_packet() and _decode_packet() methods
# 2. Reverse-engineer packet format or use SDK Client_Packager
# 3. Implement packet construction for each command
# 4. Add error handling and response validation
