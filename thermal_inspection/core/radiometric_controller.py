"""
Radiometric Controller for Thermal Inspection application.

Manages radiometric temperature measurement settings. (Reference-point temperature calibration lives in
core/calibration_manager.py; this controller no longer keeps a second, unused copy of it.)
Extracted from ThermalInspectionFusion class in inspection_main.py.
"""

import logging
from typing import Optional, Callable, Dict, Any
from dataclasses import dataclass
from enum import Enum, auto


logger = logging.getLogger(__name__)


class TemperatureUnit(Enum):
    """Temperature unit enumeration."""
    CELSIUS = auto()
    FAHRENHEIT = auto()
    KELVIN = auto()
    RAW = auto()  # Y16: Kelvin x 100


class RadiometricMethod(Enum):
    """Radiometric conversion method."""
    TLINEAR = auto()
    RAW_14BIT = auto()
    AGC_8BIT = auto()
    ESTIMATED_8BIT = auto()


@dataclass
class RadiometricState:
    """Current state of radiometric settings."""
    enabled: bool = False
    capable: bool = False
    mode: str = '8-bit AGC'
    temperature_unit: TemperatureUnit = TemperatureUnit.CELSIUS
    min_temp: float = -40.0
    max_temp: float = 150.0
    estimation_enabled: bool = False
    sdk_connected: bool = False


@dataclass
class EnvironmentalParams:
    """Environmental parameters for radiometric correction."""
    atmospheric_temp: float = 20.0  # Celsius
    emissivity: float = 0.95
    distance: float = 1.0  # meters
    humidity: float = 50.0  # percent
    reflected_temp: float = 20.0  # Celsius


class RadiometricController:
    """
    Manages radiometric temperature measurement settings.

    This controller handles:
    - Radiometric mode enable/disable
    - Temperature unit conversion
    - Temperature range settings
    - Environmental parameters
    - 8-bit estimation settings
    
    Usage:
        controller = RadiometricController()
        controller.set_thermal_camera(camera)
        controller.on_state_change = my_callback
        controller.enable_radiometric(True)
    """

    # Temperature conversion constants
    KELVIN_OFFSET = 273.15

    def __init__(self):
        """Initialize RadiometricController."""
        self.state = RadiometricState()
        self.environmental = EnvironmentalParams()

        # External instances (set by main app)
        self.thermal_camera = None
        self.thermal_analyzer = None

        # Callbacks
        self.on_state_change: Optional[Callable[[RadiometricState], None]] = None
        self.on_temperature_update: Optional[Callable[[Dict[str, float]], None]] = None

    def set_thermal_camera(self, camera):
        """
        Set the thermal camera instance.

        Args:
            camera: Thermal camera instance
        """
        self.thermal_camera = camera
        self._update_capability_state()

    def set_thermal_analyzer(self, analyzer):
        """
        Set the thermal analyzer instance.

        Args:
            analyzer: ThermalAnalyzer instance
        """
        self.thermal_analyzer = analyzer

    def _update_capability_state(self):
        """Update state based on camera capabilities."""
        if not self.thermal_camera:
            self.state.capable = False
            self.state.enabled = False
            return

        if hasattr(self.thermal_camera, 'is_radiometric_capable'):
            self.state.capable = self.thermal_camera.is_radiometric_capable()

        if hasattr(self.thermal_camera, 'is_radiometric_enabled'):
            self.state.enabled = self.thermal_camera.is_radiometric_enabled()

        self.state.mode = "16-bit Radiometric" if self.state.capable else "8-bit AGC"

        if hasattr(self.thermal_camera, 'is_sdk_connected'):
            self.state.sdk_connected = self.thermal_camera.is_sdk_connected

    def _notify_state_change(self):
        """Notify listeners of state change."""
        if self.on_state_change:
            self.on_state_change(self.state)

    def enable_radiometric(self, enable: bool) -> bool:
        """
        Enable/disable radiometric temperature conversion.

        Args:
            enable: True to enable, False to disable

        Returns:
            True if successful
        """
        if not self.thermal_camera:
            logger.warning("No thermal camera available for radiometric control")
            return False

        try:
            if hasattr(self.thermal_camera, 'enable_radiometric'):
                self.thermal_camera.enable_radiometric(enable)

            self.state.enabled = enable
            self._update_capability_state()
            self._notify_state_change()

            logger.info(f"Radiometric mode {'enabled' if enable else 'disabled'}")
            return True

        except Exception as e:
            logger.error(f"Error enabling radiometric: {e}")
            return False

    def set_temperature_unit(self, unit: str):
        """
        Set temperature display unit.

        Args:
            unit: 'celsius', 'fahrenheit', 'kelvin', or 'raw' (Y16, Kelvin x 100)
        """
        unit_map = {
            'celsius': TemperatureUnit.CELSIUS,
            'c': TemperatureUnit.CELSIUS,
            'fahrenheit': TemperatureUnit.FAHRENHEIT,
            'f': TemperatureUnit.FAHRENHEIT,
            'kelvin': TemperatureUnit.KELVIN,
            'k': TemperatureUnit.KELVIN,
            'raw': TemperatureUnit.RAW,
            'y16': TemperatureUnit.RAW,
        }

        temp_unit = unit_map.get(unit.lower())
        if temp_unit:
            self.state.temperature_unit = temp_unit

            # Update thermal analyzer if available
            if self.thermal_analyzer and hasattr(self.thermal_analyzer, 'set_temperature_unit'):
                self.thermal_analyzer.set_temperature_unit(unit)

            logger.info(f"Temperature unit set to: {temp_unit.name}")
            self._notify_state_change()

    def set_temperature_range(self, min_c: float, max_c: float) -> bool:
        """
        Set expected temperature range.

        Args:
            min_c: Minimum expected temperature (Celsius)
            max_c: Maximum expected temperature (Celsius)

        Returns:
            True if successful
        """
        if min_c >= max_c:
            logger.warning("Invalid temperature range: min must be less than max")
            return False

        self.state.min_temp = min_c
        self.state.max_temp = max_c

        if self.thermal_camera and hasattr(self.thermal_camera, 'set_temperature_range'):
            try:
                self.thermal_camera.set_temperature_range(min_c, max_c)
            except Exception as e:
                logger.error(f"Error setting camera temperature range: {e}")
                return False

        logger.info(f"Temperature range set to: {min_c:.1f}°C - {max_c:.1f}°C")
        self._notify_state_change()
        return True

    # Environmental parameters
    def set_atmospheric_temperature(self, temp_celsius: float):
        """
        Set atmospheric temperature for radiometric correction.

        Args:
            temp_celsius: Atmospheric temperature in Celsius
        """
        self.environmental.atmospheric_temp = temp_celsius

        if self.thermal_camera and hasattr(self.thermal_camera, 'set_atmospheric_temperature'):
            try:
                self.thermal_camera.set_atmospheric_temperature(temp_celsius)
            except Exception as e:
                logger.debug(f"Could not set atmospheric temp on camera: {e}")

        logger.info(f"Atmospheric temperature set to: {temp_celsius:.1f}°C")

    def set_emissivity(self, emissivity: float):
        """
        Set surface emissivity for radiometric correction.

        Args:
            emissivity: Emissivity value (0.0 to 1.0)
        """
        self.environmental.emissivity = max(0.01, min(1.0, emissivity))

        if self.thermal_camera and hasattr(self.thermal_camera, 'set_emissivity'):
            try:
                self.thermal_camera.set_emissivity(self.environmental.emissivity)
            except Exception as e:
                logger.debug(f"Could not set emissivity on camera: {e}")

        logger.info(f"Emissivity set to: {self.environmental.emissivity:.2f}")

    def set_distance(self, meters: float):
        """
        Set distance to target.

        Args:
            meters: Distance in meters
        """
        self.environmental.distance = max(0.1, meters)
        logger.info(f"Distance set to: {self.environmental.distance:.1f}m")

    def set_humidity(self, percent: float):
        """
        Set relative humidity.

        Args:
            percent: Humidity percentage (0-100)
        """
        self.environmental.humidity = max(0, min(100, percent))
        logger.info(f"Humidity set to: {self.environmental.humidity:.0f}%")

    def set_reflected_temperature(self, temp_celsius: float):
        """
        Set reflected apparent temperature.

        Args:
            temp_celsius: Reflected temperature in Celsius
        """
        self.environmental.reflected_temp = temp_celsius
        logger.info(f"Reflected temperature set to: {temp_celsius:.1f}°C")

    # 8-bit estimation
    def set_estimation_enabled(self, enabled: bool):
        """
        Enable/disable 8-bit temperature estimation.

        Args:
            enabled: True to enable estimation
        """
        self.state.estimation_enabled = enabled
        logger.info(f"8-bit temperature estimation {'enabled' if enabled else 'disabled'}")
        self._notify_state_change()

    def celsius_to_fahrenheit(self, celsius: float) -> float:
        """Convert Celsius to Fahrenheit."""
        return celsius * 9.0 / 5.0 + 32.0

    def celsius_to_kelvin(self, celsius: float) -> float:
        """Convert Celsius to Kelvin."""
        return celsius + self.KELVIN_OFFSET

    def convert_temperature(self, temp_celsius: float) -> float:
        """
        Convert temperature from Celsius to current unit.

        Args:
            temp_celsius: Temperature in Celsius

        Returns:
            Temperature in current unit
        """
        if self.state.temperature_unit == TemperatureUnit.FAHRENHEIT:
            return self.celsius_to_fahrenheit(temp_celsius)
        elif self.state.temperature_unit == TemperatureUnit.KELVIN:
            return self.celsius_to_kelvin(temp_celsius)
        elif self.state.temperature_unit == TemperatureUnit.RAW:
            return self.celsius_to_kelvin(temp_celsius) * 100.0
        return temp_celsius

    def get_unit_symbol(self) -> str:
        """Get current temperature unit symbol."""
        symbols = {
            TemperatureUnit.CELSIUS: "°C",
            TemperatureUnit.FAHRENHEIT: "°F",
            TemperatureUnit.KELVIN: "K",
            TemperatureUnit.RAW: " (Y16)",
        }
        return symbols.get(self.state.temperature_unit, "°C")

    def get_active_mode(self) -> Dict[str, Any]:
        """
        Get information about the active temperature measurement mode.

        Returns:
            Dict with mode, accuracy, and description
        """
        if self.state.enabled and self.state.capable:
            return {
                'mode': 'radiometric',
                'accuracy': 'high',
                'description': '16-bit T-Linear radiometric'
            }
        elif self.state.estimation_enabled:
            return {
                'mode': 'estimated',
                'accuracy': 'medium',
                'description': '8-bit estimation with calibration'
            }
        else:
            return {
                'mode': 'agc',
                'accuracy': 'relative',
                'description': '8-bit AGC (relative only)'
            }

    # Properties
    @property
    def is_radiometric(self) -> bool:
        """Check if radiometric mode is active."""
        return self.state.enabled and self.state.capable

    @property
    def unit(self) -> TemperatureUnit:
        """Get current temperature unit."""
        return self.state.temperature_unit
