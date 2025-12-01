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
    # RADIOMETRY - Temperature Measurement & Calibration (Phase 1)
    # ========================================================================

    def enable_radiometry(self) -> bool:
        """Enable radiometric temperature measurement."""
        if not self.connected or not self.camera:
            return False

        try:
            result = self.camera.radiometrySetTempStableEnable(1)
            if result.value == 0:
                logger.info("Radiometry enabled")
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to enable radiometry: {e}")
            return False

    def get_lens_temperature(self) -> Optional[float]:
        """Get lens housing temperature in Celsius."""
        if not self.connected or not self.camera:
            return None

        try:
            result, temp_k = self.camera.radiometryGetTempLensHousing()
            if result.value == 0:
                return (temp_k / 10.0) - 273.15
            return None
        except Exception as e:
            logger.error(f"Failed to get lens temperature: {e}")
            return None

    def get_shutter_temperature(self) -> Optional[float]:
        """Get shutter housing temperature in Celsius."""
        if not self.connected or not self.camera:
            return None

        try:
            result, temp_k = self.camera.radiometryGetTempShutterHousing()
            if result.value == 0:
                return (temp_k / 10.0) - 273.15
            return None
        except Exception as e:
            logger.error(f"Failed to get shutter temperature: {e}")
            return None

    def set_lens_parameters(self, f_number: float, transmission: float) -> bool:
        """
        Set lens optical parameters for accurate temperature calculation.

        Args:
            f_number: Lens F-number (e.g., 1.0, 1.4, 2.0)
            transmission: Lens transmission coefficient (0.0-1.0)

        Returns:
            True if successful
        """
        if not self.connected or not self.camera:
            return False

        try:
            # SDK expects f_number * 100 and transmission * 8192
            result1 = self.camera.radiometrySetFNumberLens0(int(f_number * 100))
            result2 = self.camera.radiometrySetTauLens0(int(transmission * 8192))

            if result1.value == 0 and result2.value == 0:
                logger.info(f"Lens parameters set: F/{f_number:.1f}, T={transmission:.2f}")
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to set lens parameters: {e}")
            return False

    def get_calibration_info(self) -> dict:
        """Get all radiometric calibration parameters."""
        info = {}

        if not self.connected or not self.camera:
            return info

        try:
            # Gain and offset
            result, gain = self.camera.radiometryGetGlobalGainDesired()
            if result.value == 0:
                info['global_gain'] = gain

            result, offset = self.camera.radiometryGetGlobalOffsetDesired()
            if result.value == 0:
                info['global_offset'] = offset

            # Lens parameters
            result, f_num = self.camera.radiometryGetFNumberLens0()
            if result.value == 0:
                info['f_number'] = f_num / 100.0

            result, tau = self.camera.radiometryGetTauLens0()
            if result.value == 0:
                info['transmission'] = tau / 8192.0

            # Temperatures
            info['lens_temp_c'] = self.get_lens_temperature()
            info['shutter_temp_c'] = self.get_shutter_temperature()
            info['fpa_temp_c'] = self.get_fpa_temperature()[1] if self.get_fpa_temperature() else None

        except Exception as e:
            logger.warning(f"Could not read full calibration info: {e}")

        return info

    # ========================================================================
    # Environmental Compensation (Phase 11)
    # ========================================================================

    def set_emissivity(self, emissivity: float) -> bool:
        """
        Set target emissivity for accurate temperature measurement.
        
        Emissivity (ε) represents how well a surface emits thermal radiation:
        - 1.0 = perfect blackbody (ideal emitter)
        - 0.9-0.98 = most non-metallic surfaces (paint, plastic, PCB)
        - 0.1-0.3 = oxidized metals
        - <0.1 = highly reflective polished metals
        
        Args:
            emissivity: Emissivity value (0.01-1.0)
        
        Returns:
            True if successful
        """
        if not self.connected or not self.camera:
            logger.warning("Camera not connected - cannot set emissivity")
            return False
        
        # Clamp to valid range
        emissivity = max(0.01, min(1.0, emissivity))
        
        try:
            result = self.camera.radiometrySetEmissivityTarget(emissivity)
            if result.value == 0:
                logger.info(f"✓ Target emissivity set to {emissivity:.2f}")
                return True
            else:
                logger.warning(f"Failed to set emissivity: SDK result {result.value}")
                return False
        except Exception as e:
            logger.error(f"Error setting emissivity: {e}")
            return False

    def get_emissivity(self) -> Optional[float]:
        """
        Get current target emissivity setting.
        
        Returns:
            Emissivity value (0.01-1.0) or None if error
        """
        if not self.connected or not self.camera:
            return None
        
        try:
            result, emissivity = self.camera.radiometryGetEmissivityTarget()
            if result.value == 0:
                return emissivity
            return None
        except Exception as e:
            logger.error(f"Error getting emissivity: {e}")
            return None

    def set_atmospheric_temperature(self, temp_celsius: float) -> bool:
        """
        Set atmospheric/ambient temperature for compensation.
        
        This helps compensate for atmospheric absorption and emission,
        especially important for long-distance measurements.
        
        Args:
            temp_celsius: Atmospheric temperature in °C (typically -40 to 80°C)
        
        Returns:
            True if successful
        """
        if not self.connected or not self.camera:
            logger.warning("Camera not connected - cannot set atmospheric temperature")
            return False
        
        try:
            # Convert to Kelvin
            temp_k = temp_celsius + 273.15
            result = self.camera.radiometrySetTempAtmosphere(temp_k)
            if result.value == 0:
                logger.info(f"✓ Atmospheric temperature set to {temp_celsius:.1f}°C")
                return True
            else:
                logger.warning(f"Failed to set atmospheric temperature: SDK result {result.value}")
                return False
        except Exception as e:
            logger.error(f"Error setting atmospheric temperature: {e}")
            return False

    def get_atmospheric_temperature(self) -> Optional[float]:
        """
        Get current atmospheric temperature setting.
        
        Returns:
            Temperature in °C or None if error
        """
        if not self.connected or not self.camera:
            return None
        
        try:
            result, temp_k = self.camera.radiometryGetTempAtmosphere()
            if result.value == 0:
                return temp_k - 273.15  # Convert to Celsius
            return None
        except Exception as e:
            logger.error(f"Error getting atmospheric temperature: {e}")
            return None

    def set_atmospheric_transmission(self, transmission: float) -> bool:
        """
        Set atmospheric transmission coefficient.
        
        Transmission represents the fraction of thermal radiation that reaches
        the camera through the atmosphere:
        - 1.0 = no atmospheric absorption (clear, short distance)
        - 0.95 = typical at 1-2m distance
        - 0.9 = moderate humidity or 2-5m distance
        - 0.8 = high humidity or long distance
        
        Args:
            transmission: Transmission value (0.7-1.0)
        
        Returns:
            True if successful
        """
        if not self.connected or not self.camera:
            logger.warning("Camera not connected - cannot set atmospheric transmission")
            return False
        
        # Clamp to reasonable range
        transmission = max(0.7, min(1.0, transmission))
        
        try:
            result = self.camera.radiometrySetTransmissionWindow(transmission)
            if result.value == 0:
                logger.info(f"✓ Atmospheric transmission set to {transmission:.2f}")
                return True
            else:
                logger.warning(f"Failed to set atmospheric transmission: SDK result {result.value}")
                return False
        except Exception as e:
            logger.error(f"Error setting atmospheric transmission: {e}")
            return False

    def get_atmospheric_transmission(self) -> Optional[float]:
        """
        Get current atmospheric transmission coefficient.
        
        Returns:
            Transmission value (0.7-1.0) or None if error
        """
        if not self.connected or not self.camera:
            return None
        
        try:
            result, transmission = self.camera.radiometryGetTransmissionWindow()
            if result.value == 0:
                return transmission
            return None
        except Exception as e:
            logger.error(f"Error getting atmospheric transmission: {e}")
            return None

    def get_environmental_settings(self) -> dict:
        """
        Get all environmental compensation settings.
        
        Returns:
            Dictionary with:
            {
                'emissivity': float - Target emissivity
                'atmospheric_temp_c': float - Atmospheric temp in °C
                'atmospheric_temp_k': float - Atmospheric temp in K
                'atmospheric_transmission': float - Transmission coefficient
            }
        """
        settings = {}
        
        if not self.connected or not self.camera:
            return settings
        
        try:
            # Emissivity
            emissivity = self.get_emissivity()
            if emissivity is not None:
                settings['emissivity'] = emissivity
            
            # Atmospheric temperature
            temp_c = self.get_atmospheric_temperature()
            if temp_c is not None:
                settings['atmospheric_temp_c'] = temp_c
                settings['atmospheric_temp_k'] = temp_c + 273.15
            
            # Atmospheric transmission
            transmission = self.get_atmospheric_transmission()
            if transmission is not None:
                settings['atmospheric_transmission'] = transmission
        
        except Exception as e:
            logger.warning(f"Could not read full environmental settings: {e}")
        
        return settings

    # ========================================================================
    # AGC - Automatic Gain Control (Phase 1)
    # ========================================================================

    def set_agc_max_gain(self, gain: float) -> bool:
        """
        Set maximum AGC gain (contrast limit).

        Args:
            gain: Max gain (1.0 = no limit, 2.0 = 2x max contrast, etc.)

        Returns:
            True if successful
        """
        if not self.connected or not self.camera:
            return False

        try:
            result = self.camera.agcSetMaxGain(gain)
            if result.value == 0:
                logger.info(f"AGC max gain set to {gain:.1f}")
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to set AGC max gain: {e}")
            return False

    def set_agc_gamma(self, gamma: float) -> bool:
        """
        Set gamma correction (ACE - Automatic Contrast Enhancement).

        Args:
            gamma: Gamma value (0.5-2.0, default 1.0)
                   - <1.0 = more contrast in hot areas
                   - >1.0 = more contrast in cold areas

        Returns:
            True if successful
        """
        if not self.connected or not self.camera:
            return False

        try:
            result = self.camera.agcSetGamma(gamma)
            if result.value == 0:
                logger.info(f"AGC gamma set to {gamma:.2f}")
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to set AGC gamma: {e}")
            return False

    def set_agc_linearity(self, percent: float) -> bool:
        """
        Set AGC linearity (histogram vs. linear mapping).

        Args:
            percent: Linearity (0-100%)
                     - 0% = fully adaptive (histogram-based)
                     - 100% = fully linear (no adaptation)

        Returns:
            True if successful
        """
        if not self.connected or not self.camera:
            return False

        try:
            result = self.camera.agcSetLinearPercent(percent)
            if result.value == 0:
                logger.info(f"AGC linearity set to {percent:.0f}%")
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to set AGC linearity: {e}")
            return False

    def set_detail_enhancement(self, dde_ratio: float) -> bool:
        """
        Set DDE (Digital Detail Enhancement).

        Args:
            dde_ratio: Detail-to-background ratio (0.0-3.0, typical 1.3)
                       - Higher = sharper edges, more detail

        Returns:
            True if successful
        """
        if not self.connected or not self.camera:
            return False

        try:
            result = self.camera.agcSetd2br(dde_ratio)
            if result.value == 0:
                logger.info(f"DDE ratio set to {dde_ratio:.2f}")
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to set DDE: {e}")
            return False

    def set_agc_roi(self, x_start: int, y_start: int, x_stop: int, y_stop: int) -> bool:
        """
        Set AGC region of interest.
        AGC will optimize contrast based on this region.

        Args:
            x_start, y_start: Top-left corner
            x_stop, y_stop: Bottom-right corner

        Returns:
            True if successful
        """
        if not self.connected or not self.camera:
            return False

        try:
            # Create ROI struct
            from ctypes import Structure, c_uint16

            class FLR_ROI_T(Structure):
                _fields_ = [
                    ("rowStart", c_uint16),
                    ("rowStop", c_uint16),
                    ("colStart", c_uint16),
                    ("colStop", c_uint16)
                ]

            roi = FLR_ROI_T()
            roi.rowStart = y_start
            roi.rowStop = y_stop
            roi.colStart = x_start
            roi.colStop = x_stop

            result = self.camera.agcSetROI(roi)
            if result.value == 0:
                logger.info(f"AGC ROI set to ({x_start},{y_start})-({x_stop},{y_stop})")
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to set AGC ROI: {e}")
            return False

    def get_agc_settings(self) -> dict:
        """Get all AGC settings."""
        settings = {}

        if not self.connected or not self.camera:
            return settings

        try:
            result, gain = self.camera.agcGetMaxGain()
            if result.value == 0:
                settings['max_gain'] = gain

            result, gamma = self.camera.agcGetGamma()
            if result.value == 0:
                settings['gamma'] = gamma

            result, linear = self.camera.agcGetLinearPercent()
            if result.value == 0:
                settings['linearity_percent'] = linear

            result, dde = self.camera.agcGetd2br()
            if result.value == 0:
                settings['dde_ratio'] = dde

        except Exception as e:
            logger.warning(f"Could not read full AGC settings: {e}")

        return settings

    # ========================================================================
    # Spotmeter - Hardware-Accelerated Temperature Reading
    # ========================================================================

    def spotmeter_enable(self, enable: bool) -> bool:
        """
        Enable/disable hardware spotmeter.
        
        Args:
            enable: True to enable, False to disable
            
        Returns:
            True if successful
        """
        if not self.connected or not self.camera:
            return False
            
        try:
            result = self.camera.bosonSetSpotmeterMode(1 if enable else 0)
            if result.value == 0:
                logger.info(f"Spotmeter {'enabled' if enable else 'disabled'}")
                return True
            return False
        except AttributeError:
            logger.warning("Spotmeter not supported by SDK version")
            return False
        except Exception as e:
            logger.error(f"Failed to set spotmeter mode: {e}")
            return False

    def spotmeter_set_roi(self, x: int, y: int, width: int = 4, height: int = 4) -> bool:
        """
        Set spotmeter region of interest.
        
        Args:
            x: X coordinate (pixel)
            y: Y coordinate (pixel)
            width: ROI width (default 4)
            height: ROI height (default 4)
            
        Returns:
            True if successful
        """
        if not self.connected or not self.camera:
            return False
            
        try:
            x_start = max(0, x - width // 2)
            y_start = max(0, y - height // 2)
            
            result = self.camera.bosonSetSpotmeterROI(x_start, y_start, width, height)
            if result.value == 0:
                return True
            return False
        except AttributeError:
            logger.debug("Spotmeter ROI not supported")
            return False
        except Exception as e:
            logger.error(f"Failed to set spotmeter ROI: {e}")
            return False

    def spotmeter_get_temperature(self) -> Optional[float]:
        """
        Get temperature from hardware spotmeter.
        
        Returns:
            Temperature in Celsius or None
        """
        if not self.connected or not self.camera:
            return None
            
        try:
            result, temp_k_x10 = self.camera.bosonGetSpotmeterTemp()
            if result.value == 0:
                temp_c = (temp_k_x10 / 10.0) - 273.15
                return temp_c
            return None
        except AttributeError:
            return None
        except Exception as e:
            logger.error(f"Failed to get spotmeter temperature: {e}")
            return None

    def spotmeter_set_statistics_mode(self, mode: str) -> bool:
        """
        Set spotmeter statistics mode.
        
        Args:
            mode: 'center', 'average', 'max', or 'min'
            
        Returns:
            True if successful
        """
        if not self.connected or not self.camera:
            return False
            
        mode_map = {
            'center': 0,
            'average': 1,
            'max': 2,
            'min': 3
        }
        
        if mode.lower() not in mode_map:
            return False
            
        try:
            result = self.camera.bosonSetSpotmeterStatisticsMode(mode_map[mode.lower()])
            if result.value == 0:
                logger.info(f"Spotmeter mode: {mode}")
                return True
            return False
        except AttributeError:
            logger.warning("Spotmeter statistics mode not supported")
            return False
        except Exception as e:
            logger.error(f"Failed to set spotmeter mode: {e}")
            return False

    # ========================================================================
    # Info Methods
    # ========================================================================

    def get_info(self) -> BosonInfo:
        """Get camera information."""
        return self.info

    # ========================================================================
    # Radiometric Support
    # ========================================================================

    def is_radiometric_capable(self) -> bool:
        """
        Check if camera supports radiometric mode (16-bit absolute temperature output)

        Radiometric Boson cameras have 'R' in their part number (e.g., 640-R)

        Returns:
            True if camera supports radiometric mode
        """
        if not self.is_connected():
            return False

        try:
            info = self.get_info()
            if info and info.camera_part_number:
                # Radiometric Bosons have 'R' in part number
                is_radiometric = 'R' in info.camera_part_number.upper()
                logger.info(f"Radiometric check: {'YES' if is_radiometric else 'NO'} (PN: {info.camera_part_number})")
                return is_radiometric
            return False
        except Exception as e:
            logger.error(f"Error checking radiometric capability: {e}")
            return False

    def get_radiometric_status(self) -> dict:
        """
        Get radiometric mode status and information

        Returns:
            Dictionary with:
            {
                'capable': bool - Camera supports radiometric
                'enabled': bool - Radiometric currently active
                'mode': str - Current output mode
                'bit_depth': int - 8 or 16
            }
        """
        status = {
            'capable': self.is_radiometric_capable(),
            'enabled': False,
            'mode': 'Unknown',
            'bit_depth': 8
        }

        if not self.is_connected():
            return status

        # Try to detect if currently in 16-bit mode
        # This would require frame analysis or SDK query
        # For now, mark as unknown
        status['mode'] = 'UVC' if not status['capable'] else 'Unknown'

        return status

    # ========================================================================
    # Extended BOSON Module Functions (Phase 10)
    # ========================================================================

    def get_frame_count(self) -> Optional[int]:
        """
        Get current frame count since camera boot.

        Returns:
            Frame count or None if error
        """
        if not self.is_connected():
            return None

        try:
            frame_count = Client_API.bosonGetISPFrameCount(self.camera_handle)
            return frame_count[1] if frame_count[0] == Client_API.FLR_OK else None
        except Exception as e:
            logger.error(f"Error getting frame count: {e}")
            return None

    def get_board_temperature(self) -> Optional[float]:
        """
        Get camera board temperature (Myriad processor).

        Returns:
            Temperature in Celsius or None if error
        """
        if not self.is_connected():
            return None

        try:
            # Myriad temp is returned in degrees C x10
            temp_result = Client_API.bosonGetMyriadTemp(self.camera_handle)
            if temp_result[0] == Client_API.FLR_OK:
                temp_cx10 = temp_result[1]
                return temp_cx10 / 10.0  # Convert to Celsius
            return None
        except Exception as e:
            logger.error(f"Error getting board temperature: {e}")
            return None

    def get_ffc_temp_delta(self) -> Optional[float]:
        """
        Get temperature change threshold for automatic FFC.

        Returns:
            Temperature delta in Celsius or None if error
        """
        if not self.is_connected():
            return None

        try:
            result = Client_API.bosonGetFFCTempThreshold(self.camera_handle)
            if result[0] == Client_API.FLR_OK:
                # Threshold is in Kelvin x100
                delta_kx100 = result[1]
                return delta_kx100 / 100.0  # Convert to Celsius
            return None
        except Exception as e:
            logger.error(f"Error getting FFC temp delta: {e}")
            return None

    def set_ffc_temp_delta(self, delta_celsius: float) -> bool:
        """
        Set temperature change threshold for automatic FFC.

        Args:
            delta_celsius: Temperature change in Celsius to trigger auto-FFC (e.g., 3.0)

        Returns:
            True if successful
        """
        if not self.is_connected():
            return False

        try:
            # Convert Celsius to Kelvin x100
            delta_kx100 = int(delta_celsius * 100)
            result = Client_API.bosonSetFFCTempThreshold(self.camera_handle, delta_kx100)
            success = (result == Client_API.FLR_OK)
            if success:
                logger.info(f"Set FFC temp delta: {delta_celsius}°C")
            return success
        except Exception as e:
            logger.error(f"Error setting FFC temp delta: {e}")
            return False

    def get_last_ffc_frame_count(self) -> Optional[int]:
        """
        Get frame count when last FFC was performed.

        Returns:
            Frame count at last FFC or None if error
        """
        if not self.is_connected():
            return None

        try:
            result = Client_API.bosonGetLastFFCFrameCount(self.camera_handle)
            return result[1] if result[0] == Client_API.FLR_OK else None
        except Exception as e:
            logger.error(f"Error getting last FFC frame count: {e}")
            return None

    def get_last_ffc_temp(self) -> Optional[float]:
        """
        Get FPA temperature when last FFC was performed.

        Returns:
            Temperature in Celsius or None if error
        """
        if not self.is_connected():
            return None

        try:
            result = Client_API.bosonGetLastFFCTempDegKx10(self.camera_handle)
            if result[0] == Client_API.FLR_OK:
                temp_kx10 = result[1]
                return (temp_kx10 / 10.0) - 273.15  # Convert to Celsius
            return None
        except Exception as e:
            logger.error(f"Error getting last FFC temperature: {e}")
            return None

    def get_ffc_statistics(self) -> Optional[dict]:
        """
        Get FFC statistics and timing information.

        Returns:
            Dictionary with:
            - last_ffc_frame: Frame count at last FFC
            - last_ffc_temp_c: FPA temperature at last FFC (°C)
            - frames_since_ffc: Frames elapsed since last FFC
            - temp_delta_c: Auto-FFC threshold (°C)
        """
        if not self.is_connected():
            return None

        try:
            current_frame = self.get_frame_count()
            last_ffc_frame = self.get_last_ffc_frame_count()
            last_ffc_temp = self.get_last_ffc_temp()
            temp_delta = self.get_ffc_temp_delta()

            if current_frame is None or last_ffc_frame is None:
                return None

            return {
                'last_ffc_frame': last_ffc_frame,
                'last_ffc_temp_c': last_ffc_temp,
                'frames_since_ffc': current_frame - last_ffc_frame,
                'temp_delta_c': temp_delta
            }
        except Exception as e:
            logger.error(f"Error getting FFC statistics: {e}")
            return None

    # ========================================================================
    # Additional Universal Features
    # ========================================================================

    def get_frame_rate(self) -> Optional[float]:
        """
        Get current frame rate (FPS).

        Returns:
            Frame rate in Hz, or None if failed
        """
        if not self.connected or not self.camera:
            return None

        try:
            # Try getting from camera info
            result, frame_rate = self.camera.bosonGetFrameRate()
            if result.value == 0:
                return float(frame_rate)

            # Fallback: Estimate from frame count over time
            logger.debug("Direct FPS query failed, using fallback")
            return None
        except Exception as e:
            logger.error(f"Error getting frame rate: {e}")
            return None

    def set_shutter_position(self, position: str) -> bool:
        """
        Set FFC shutter position.

        Args:
            position: "OPEN", "CLOSED", or "AUTO"

        Returns:
            True if successful
        """
        if not self.connected or not self.camera:
            return False

        try:
            position_map = {
                "OPEN": 0,
                "CLOSED": 1,
                "AUTO": 2
            }

            pos_val = position_map.get(position.upper())
            if pos_val is None:
                logger.error(f"Invalid shutter position: {position}")
                return False

            result = self.camera.bosonSetShutterPosition(pos_val)
            if result.value == 0:
                logger.info(f"Shutter position set to {position}")
                return True
            return False
        except Exception as e:
            logger.error(f"Error setting shutter position: {e}")
            return False

    def get_shutter_position(self) -> Optional[str]:
        """
        Get current FFC shutter position.

        Returns:
            "OPEN", "CLOSED", or "AUTO", or None if failed
        """
        if not self.connected or not self.camera:
            return None

        try:
            result, position = self.camera.bosonGetShutterPosition()
            if result.value == 0:
                position_map = {0: "OPEN", 1: "CLOSED", 2: "AUTO"}
                return position_map.get(position, "UNKNOWN")
            return None
        except Exception as e:
            logger.error(f"Error getting shutter position: {e}")
            return None

    def set_agc_plateau(self, histogram_percent: float) -> bool:
        """
        Set AGC plateau histogram equalization percentage.

        Args:
            histogram_percent: Percentage (0-100)

        Returns:
            True if successful
        """
        if not self.connected or not self.camera:
            return False

        try:
            result = self.camera.agcSetPlateau(int(histogram_percent))
            if result.value == 0:
                logger.info(f"AGC plateau set to {histogram_percent}%")
                return True
            return False
        except Exception as e:
            logger.error(f"Error setting AGC plateau: {e}")
            return False

    def set_agc_dampening(self, factor: float) -> bool:
        """
        Set AGC temporal dampening factor (smoothing).

        Args:
            factor: Dampening factor (typically 0-64)

        Returns:
            True if successful
        """
        if not self.connected or not self.camera:
            return False

        try:
            result = self.camera.agcSetDampingFactor(int(factor))
            if result.value == 0:
                logger.info(f"AGC dampening set to {factor}")
                return True
            return False
        except Exception as e:
            logger.error(f"Error setting AGC dampening: {e}")
            return False

    def get_system_status(self) -> Optional[dict]:
        """
        Get overall system health status.

        Returns:
            Dictionary with system status information
        """
        if not self.connected or not self.camera:
            return None

        try:
            status = {}

            # Frame count
            status['frame_count'] = self.get_frame_count()

            # FPA temperature
            fpa_temp = self.get_fpa_temperature()
            if fpa_temp:
                status['fpa_temp_c'] = fpa_temp[0]

            # Board temperature
            status['board_temp_c'] = self.get_board_temperature()

            # FFC statistics
            ffc_stats = self.get_ffc_statistics()
            if ffc_stats:
                status['frames_since_ffc'] = ffc_stats.get('frames_since_ffc')

            # Radiometric capable
            status['radiometric_capable'] = self.is_radiometric_capable()

            return status
        except Exception as e:
            logger.error(f"Error getting system status: {e}")
            return None

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
