#!/usr/bin/env python3
"""
Flirpy SDK Bridge - Inject Boson SDK commands via flirpy's serial connection

This module provides SDK control functionality for FlirpyThermalBackend by
injecting Boson SDK command packets through flirpy's existing COM port connection.

Architecture:
- Uses FLIR's official SDK Client_Packager for packet generation
- Captures packets via MockFSLP layer
- Injects packets via flirpy's send()/receive() methods
- Provides high-level methods matching BosonSDK wrapper API

Enhanced in Enhancement #5 with full AGC, Radiometry, Spotmeter, and Isotherm support.
"""

import sys
import os
import struct
import logging
from typing import Optional, Tuple, Any
from enum import Enum

logger = logging.getLogger(__name__)

# =============================================================================
# SDK Packager Integration
# =============================================================================

# Add SDK path
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
# When in playground, SDK is two levels up
PROJECT_ROOT = os.path.dirname(os.path.dirname(CURRENT_DIR))
SDK_BASE = os.path.join(PROJECT_ROOT, '3.0 IDD & SDK', 'SDK_USER_PERMISSIONS')
SDK_PATH = os.path.join(SDK_BASE, 'SDK_USER_PERMISSIONS')

SDK_PACKAGER_AVAILABLE = False
Client_Packager = None

if os.path.exists(SDK_PATH):
    if SDK_BASE not in sys.path:
        sys.path.insert(0, SDK_BASE)
    if SDK_PATH not in sys.path:
        sys.path.insert(0, SDK_PATH)
    
    try:
        from SDK_USER_PERMISSIONS.ClientFiles_Python import Client_Packager as _Client_Packager
        Client_Packager = _Client_Packager
        SDK_PACKAGER_AVAILABLE = True
        logger.info("✓ Boson SDK Packager loaded for packet generation")
    except ImportError as e:
        logger.warning(f"⚠ SDK Packager import failed: {e}")
else:
    logger.warning(f"⚠ SDK not found at {SDK_PATH}")


class MockFSLP:
    """
    Mock FSLP (FLIR Serial Line Protocol) layer to capture bytes from SDK Packager.
    
    The SDK Packager normally sends bytes to a real FSLP layer connected to hardware.
    This mock captures those bytes so we can inject them via flirpy's connection instead.
    """
    
    def __init__(self):
        self.last_sent_bytes: Optional[bytes] = None
        self.last_response: Optional[bytes] = None
        self.port_id = 0
        self.portID = 0  # Some SDK versions use this
        
    def sendToCamera(self, portID: int, data: Any, numBytes: int) -> int:
        """Capture bytes sent by Packager (matches FSLP signature)."""
        if isinstance(data, (bytes, bytearray)):
            self.last_sent_bytes = bytes(data[:numBytes])
        elif hasattr(data, '__iter__'):
            self.last_sent_bytes = bytes(list(data)[:numBytes])
        else:
            self.last_sent_bytes = bytes(data)
        return 0  # Success
        
    def sendFrame(self, *args) -> int:
        """Alternative signature used by some SDK versions."""
        for arg in args:
            if isinstance(arg, (bytes, bytearray)):
                self.last_sent_bytes = bytes(arg)
                break
            elif isinstance(arg, list) and len(arg) > 0 and isinstance(arg[0], int):
                self.last_sent_bytes = bytes(arg)
                break
        return 0
        
    def readFrame(self, portID: int = 0, numBytes: int = 32) -> bytes:
        """Return captured response (set by send_and_receive)."""
        if self.last_response:
            return self.last_response
        # Return dummy bytes to satisfy SDK dispatcher length checks
        return bytes(numBytes)
    
    def set_response(self, response: bytes):
        """Set the response to return on next readFrame call."""
        self.last_response = response
        
    def get_last_packet(self) -> Optional[bytes]:
        """Get the last captured packet."""
        return self.last_sent_bytes
        
    def clear(self):
        """Clear captured data."""
        self.last_sent_bytes = None
        self.last_response = None

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
        camera = Boson(port='COM7')
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
        
        # Initialize SDK Packager with MockFSLP for packet generation
        self._mock_fslp: Optional[MockFSLP] = None
        self._packager = None
        self._sdk_available = False
        
        if SDK_PACKAGER_AVAILABLE and Client_Packager:
            try:
                self._mock_fslp = MockFSLP()
                self._packager = Client_Packager.Packager(self._mock_fslp)
                self._sdk_available = True
                logger.info("SDK Packager initialized for advanced commands")
            except Exception as e:
                logger.warning(f"SDK Packager init failed: {e}")
        
        if not self._connected:
            logger.warning("Flirpy camera lacks send/receive methods - SDK bridge unavailable")
        else:
            logger.info("FlirpySDKBridge initialized with access to serial connection")
    
    def is_available(self) -> bool:
        """Check if SDK bridge is available."""
        return self._connected and self.camera is not None
    
    def is_sdk_available(self) -> bool:
        """Check if advanced SDK commands are available."""
        return self._sdk_available and self._packager is not None
    
    # =========================================================================
    # Core SDK Packet Injection
    # =========================================================================
    
    def _send_sdk_command(self, packager_method_name: str, *args) -> Tuple[bool, Optional[Any]]:
        """
        Execute SDK command via packet injection through flirpy.
        
        Args:
            packager_method_name: Name of CLIENT_pkg_* method on Packager
            *args: Arguments to pass to the packager method
            
        Returns:
            (success: bool, result: Any or None)
        """
        if not self.is_sdk_available():
            logger.warning(f"SDK not available for {packager_method_name}")
            return (False, None)
        
        if not self.is_available():
            logger.warning(f"Camera not connected for {packager_method_name}")
            return (False, None)
        
        try:
            # 1. Clear previous packet
            self._mock_fslp.clear()
            
            # 2. Get packager method
            method = getattr(self._packager, packager_method_name, None)
            if method is None:
                logger.error(f"Packager method not found: {packager_method_name}")
                return (False, None)
            
            # 3. First, send the packet and get response from camera
            # We need to do this in two stages:
            #   Stage 1: Generate packet (capture via MockFSLP)
            #   Stage 2: Send via flirpy and receive response
            #   Stage 3: Feed response back and let Packager parse it

            # Stage 1: Generate packet by calling packager method
            # This will call MockFSLP.sendToCamera() which captures the bytes
            # The method call will also try to read via MockFSLP.readFrame(),
            # which returns dummy bytes initially
            if args:
                # First call to generate packet
                self._mock_fslp.clear()
                method(*args)  # Discard result, we just want the packet
                packet = self._mock_fslp.get_last_packet()
            else:
                self._mock_fslp.clear()
                method()  # Discard result, we just want the packet
                packet = self._mock_fslp.get_last_packet()

            if packet is None:
                logger.warning(f"No packet generated by {packager_method_name}")
                return (False, None)

            logger.debug(f"SDK packet ({len(packet)} bytes): {packet.hex()[:40]}...")

            # Stage 2: Send packet via flirpy and get real response
            self.camera.send(packet)
            response = self.camera.receive()

            # Check if we got a response (even if it's all zeros)
            has_response = response is not None and len(response) > 0

            if not has_response:
                # Some SET commands don't return data, just success
                logger.debug(f"SDK command sent (no response data)")
                return (True, None)

            logger.debug(f"SDK response ({len(response)} bytes): {response.hex()[:40] if len(response) > 0 else 'empty'}...")

            # Stage 3: Feed response back to MockFSLP and call packager again
            # This time the packager will read the real response and parse it
            self._mock_fslp.clear()
            self._mock_fslp.set_response(response)

            if args:
                packager_result = method(*args)
            else:
                packager_result = method()

            logger.debug(f"Packager parsed result: {packager_result}")
            return (True, packager_result)
                
        except Exception as e:
            logger.error(f"SDK command {packager_method_name} failed: {e}")
            return (False, None)
    
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
    # Advanced SDK Commands (via packet injection)
    # =========================================================================
    
    def set_gain_mode(self, mode: GainMode) -> bool:
        """
        Set camera gain mode via SDK packet injection.
        
        Args:
            mode: GainMode.HIGH (-40 to 120C), LOW (up to 400C), or AUTO
            
        Returns:
            bool: True if successful
        """
        success, _ = self._send_sdk_command('CLIENT_pkg_boson_SetGainMode', mode.value)
        if success:
            logger.info(f"Gain mode set to {mode.name}")
        return success
    
    def get_gain_mode(self) -> Optional[int]:
        """
        Get current gain mode via SDK.
        
        Returns:
            int: 0=HIGH, 1=LOW, 2=AUTO, or None if error
        """
        success, response = self._send_sdk_command('CLIENT_pkg_boson_GetGainMode')
        if success and response is not None:
            return response
        return None
    
    # =========================================================================
    # AGC Controls
    # =========================================================================
    
    def set_agc_gamma(self, gamma: float) -> bool:
        """
        Set AGC gamma correction (ACE - Automatic Contrast Enhancement).
        
        Args:
            gamma: Gamma value (0.5-2.0, default 1.0)
                   - <1.0 = more contrast in hot areas
                   - >1.0 = more contrast in cold areas
        
        Returns:
            bool: True if successful
        """
        gamma = max(0.5, min(2.0, gamma))  # Clamp to valid range
        success, _ = self._send_sdk_command('CLIENT_pkg_agc_SetGamma', gamma)
        if success:
            logger.info(f"✓ AGC gamma set to {gamma:.2f}")
        return success
    
    def get_agc_gamma(self) -> Optional[float]:
        """Get current AGC gamma value."""
        success, response = self._send_sdk_command('CLIENT_pkg_agc_GetGamma')
        if success and response is not None:
            return response
        return None
    
    def set_agc_max_gain(self, gain: float) -> bool:
        """
        Set maximum AGC gain (contrast limit).
        
        Args:
            gain: Max gain (1.0 = no limit, higher = more contrast)
        
        Returns:
            bool: True if successful
        """
        gain = max(0.1, min(10.0, gain))  # Reasonable limits
        success, _ = self._send_sdk_command('CLIENT_pkg_agc_SetMaxGain', gain)
        if success:
            logger.info(f"✓ AGC max gain set to {gain:.2f}")
        return success
    
    def set_detail_enhancement(self, dde_ratio: float) -> bool:
        """
        Set DDE (Digital Detail Enhancement) ratio.
        
        Also known as d2br (detail-to-background ratio).
        
        Args:
            dde_ratio: Detail ratio (0.0-3.0, typical 1.3)
                       Higher = sharper edges, more detail
        
        Returns:
            bool: True if successful
        """
        dde_ratio = max(0.0, min(3.0, dde_ratio))
        success, _ = self._send_sdk_command('CLIENT_pkg_agc_Setd2br', dde_ratio)
        if success:
            logger.info(f"✓ DDE ratio set to {dde_ratio:.2f}")
        return success
    
    def set_agc_linearity(self, percent: float) -> bool:
        """
        Set AGC linearity (histogram vs. linear mapping).
        
        Args:
            percent: Linearity (0-100%)
                     - 0% = fully adaptive (histogram-based)
                     - 100% = fully linear (no adaptation)
        
        Returns:
            bool: True if successful
        """
        percent = max(0.0, min(100.0, percent))
        success, _ = self._send_sdk_command('CLIENT_pkg_agc_SetLinearPercent', percent)
        if success:
            logger.info(f"✓ AGC linearity set to {percent:.1f}%")
        return success
    
    def set_color_lut(self, lut: ColorLUT) -> bool:
        """
        Set camera color LUT via SDK packet injection.
        
        Args:
            lut: ColorLUT enum value
            
        Returns:
            bool: True if successful
        """
        success, _ = self._send_sdk_command('CLIENT_pkg_colorLut_SetControl', lut.value)
        if success:
            logger.info(f"Color LUT set to {lut.name}")
        return success
    
    # =========================================================================
    # Radiometry Controls
    # =========================================================================
    
    def set_emissivity(self, emissivity: float) -> bool:
        """
        Set target emissivity for temperature measurement.
        
        Args:
            emissivity: Emissivity value (0.01-1.0)
                        1.0 = perfect blackbody
                        0.95 = most non-metallic surfaces
                        0.1-0.3 = oxidized metals
            
        Returns:
            bool: True if successful
        """
        emissivity = max(0.01, min(1.0, emissivity))
        success, _ = self._send_sdk_command('CLIENT_pkg_radiometry_SetEmissivityTarget', emissivity)
        if success:
            logger.info(f"Emissivity set to {emissivity:.2f}")
        return success
    
    def get_emissivity(self) -> Optional[float]:
        """Get current target emissivity setting."""
        success, response = self._send_sdk_command('CLIENT_pkg_radiometry_GetEmissivityTarget')
        if success and response is not None:
            return response
        return None
    
    def set_atmospheric_temperature(self, temp_celsius: float) -> bool:
        """
        Set atmospheric/ambient temperature for compensation.
        
        Args:
            temp_celsius: Atmospheric temperature in Celsius
            
        Returns:
            bool: True if successful
        """
        # SDK expects temperature in Kelvin * 10 or raw Kelvin depending on method
        temp_k = temp_celsius + 273.15
        success, _ = self._send_sdk_command('CLIENT_pkg_radiometry_SetTAtmosphere', temp_k)
        if success:
            logger.info(f"Atmospheric temperature set to {temp_celsius:.1f}C")
        return success
    
    def set_atmospheric_transmission(self, transmission: float) -> bool:
        """
        Set atmospheric transmission coefficient.
        
        Args:
            transmission: Transmission (0.7-1.0)
                          1.0 = no absorption
                          0.9 = moderate humidity
            
        Returns:
            bool: True if successful
        """
        transmission = max(0.7, min(1.0, transmission))
        success, _ = self._send_sdk_command('CLIENT_pkg_radiometry_SetTransmissionWindow', transmission)
        if success:
            logger.info(f"Atmospheric transmission set to {transmission:.2f}")
        return success
    
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

