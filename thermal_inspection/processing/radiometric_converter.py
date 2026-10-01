"""
Radiometric Temperature Converter for FLIR Boson Cameras

Converts 16-bit raw radiometric pixel values to absolute temperature
using linear approximation or TLinear lookup table.

Supports:
- Linear pixel-to-temperature conversion
- TLinear LUT-based conversion (high accuracy)
- Spot temperature measurement
- Frame-wide temperature conversion
- Calibration file loading
"""

import numpy as np
import logging
from typing import Optional, Dict
from pathlib import Path
import csv

logger = logging.getLogger(__name__)


class TLinearConverter:
    """
    Converts raw 16-bit radiometric pixel values to temperature in Celsius

    Uses either linear approximation or TLinear lookup table for accurate conversion.
    """

    def __init__(self, method: str = "linear", temperature_unit: str = "C"):
        """
        Initialize radiometric converter

        Args:
            method: "linear" (T-Linear: Kelvin = count * kelvin_per_count, the camera's own radiometric output),
                "lut" (TLinear lookup table file) or "range" (map the full 16-bit span onto min/max temperature -
                only for sources that are NOT T-Linear, e.g. a scaled/AGC 16-bit stream; an estimate)
            temperature_unit: Temperature unit - "C" (Celsius), "F" (Fahrenheit), or "K" (Kelvin)
        """
        self.method = method
        self.temperature_unit = temperature_unit
        self.lut = None  # Lookup table dict: {pixel_value: temperature}
        self.lut_size = 0
        self._lut_x = None   # the same table as sorted arrays, for vectorised interpolation (see _set_lut)
        self._lut_y = None

        # T-Linear: the Boson's radiometric Y16 output is temperature in Kelvin / kelvin_per_count (0.01 K per count in
        # high-resolution mode, which is what flirpy_thermal_backend and the app's own conversions assume). A
        # linear mapping of the whole 0..65535 span onto -40..550 C (the previous default) is NOT this: it read
        # ~224 C for a 20 C scene and made the Temperature Range setting change the readings.
        self.kelvin_per_count = 0.01

        # Range mapping parameters (method="range" only; also the display range other widgets read)
        self.min_temp_celsius = -40.0
        self.max_temp_celsius = 550.0
        self.min_pixel_value = 0
        self.max_pixel_value = 65535

        # Calibration parameters (computed from reference points)
        self.calibration_slope = None
        self.calibration_offset = None
        self.is_calibrated = False

        # Environmental Compensation Parameters (Radiometric Planck / Stefan-Boltzmann model)
        self.emissivity = 0.95
        self.distance_m = 1.0
        self.atmospheric_temp_c = 20.0
        self.reflected_temp_c = 20.0
        self.atmospheric_transmission = 1.0
        self.enable_environmental_compensation = False

        logger.info(f"Radiometric converter initialized (method: {method}, unit: {temperature_unit})")

    def set_environmental_parameters(
        self,
        emissivity: Optional[float] = None,
        distance_m: Optional[float] = None,
        atmospheric_temp_c: Optional[float] = None,
        reflected_temp_c: Optional[float] = None,
        transmission: Optional[float] = None,
        enable: Optional[bool] = None,
    ):
        """
        Set environmental compensation parameters for thermal radiometric conversion.

        Args:
            emissivity: Target surface emissivity (0.01 - 1.00)
            distance_m: Distance to target in meters
            atmospheric_temp_c: Atmospheric temperature in Celsius
            reflected_temp_c: Reflected background temperature in Celsius
            transmission: Atmospheric transmission coefficient (0.01 - 1.00)
            enable: Enable or disable environmental compensation
        """
        if emissivity is not None:
            self.emissivity = float(np.clip(emissivity, 0.01, 1.00))
        if distance_m is not None:
            self.distance_m = max(0.1, float(distance_m))
        if atmospheric_temp_c is not None:
            self.atmospheric_temp_c = float(atmospheric_temp_c)
        if reflected_temp_c is not None:
            self.reflected_temp_c = float(reflected_temp_c)
        if transmission is not None:
            self.atmospheric_transmission = float(np.clip(transmission, 0.01, 1.00))
        if enable is not None:
            self.enable_environmental_compensation = bool(enable)

        logger.info(
            f"Environmental params set: emissivity={self.emissivity:.2f}, "
            f"dist={self.distance_m:.1f}m, T_atm={self.atmospheric_temp_c:.1f}°C, "
            f"T_refl={self.reflected_temp_c:.1f}°C, tau={self.atmospheric_transmission:.2f}, "
            f"enabled={self.enable_environmental_compensation}"
        )

    def apply_environmental_compensation(self, temp_c: float | np.ndarray) -> float | np.ndarray:
        """
        Apply Stefan-Boltzmann radiometric radiation law to compensate apparent
        temperature for emissivity, reflected background radiation, and atmospheric absorption.

        Formula:
            K_obj^4 = (K_apparent^4 - (1 - e)*tau*K_refl^4 - (1 - tau)*K_atm^4) / (e * tau)
            T_obj = K_obj - 273.15

        Args:
            temp_c: Apparent temperature (or float32 array) in Celsius

        Returns:
            True compensated object surface temperature in Celsius
        """
        if not self.enable_environmental_compensation:
            return temp_c

        e = self.emissivity
        tau = self.atmospheric_transmission
        k_refl_4 = (self.reflected_temp_c + 273.15) ** 4
        k_atm_4 = (self.atmospheric_temp_c + 273.15) ** 4

        is_array = isinstance(temp_c, np.ndarray)
        k_app = (temp_c + 273.15)
        k_app_4 = k_app ** 4

        # Compensate radiance in Kelvin^4 space
        k_obj_4 = (k_app_4 - (1.0 - e) * tau * k_refl_4 - (1.0 - tau) * k_atm_4) / (e * tau)

        # Clip to non-negative Kelvin^4 before 4th root
        if is_array:
            k_obj_4 = np.maximum(k_obj_4, 0.0)
            t_obj = np.power(k_obj_4, 0.25) - 273.15
        else:
            k_obj_4 = max(0.0, k_obj_4)
            t_obj = (k_obj_4 ** 0.25) - 273.15

        return t_obj


    # Temperature Unit Conversion Methods

    def celsius_to_fahrenheit(self, temp_c: float) -> float:
        """Convert Celsius to Fahrenheit. Formula: F = C * 9/5 + 32"""
        return (temp_c * 9.0 / 5.0) + 32.0

    def fahrenheit_to_celsius(self, temp_f: float) -> float:
        """Convert Fahrenheit to Celsius. Formula: C = (F - 32) * 5/9"""
        return (temp_f - 32.0) * 5.0 / 9.0

    def celsius_to_kelvin(self, temp_c: float) -> float:
        """Convert Celsius to Kelvin. Formula: K = C + 273.15"""
        return temp_c + 273.15

    def kelvin_to_celsius(self, temp_k: float) -> float:
        """Convert Kelvin to Celsius. Formula: C = K - 273.15"""
        return temp_k - 273.15

    def convert_temperature(self, temp_c: float) -> float:
        """
        Convert temperature from Celsius to current unit setting.

        Args:
            temp_c: Temperature in Celsius

        Returns:
            Temperature in selected unit (C, F, or K)
        """
        if self.temperature_unit == 'F':
            return self.celsius_to_fahrenheit(temp_c)
        elif self.temperature_unit == 'K':
            return self.celsius_to_kelvin(temp_c)
        return temp_c

    def get_temperature_unit_symbol(self) -> str:
        """Get temperature unit symbol for display"""
        if self.temperature_unit == 'F':
            return '°F'
        elif self.temperature_unit == 'K':
            return 'K'
        return '°C'

    def set_temperature_unit(self, unit: str):
        """
        Set temperature unit.

        Args:
            unit: 'C' for Celsius, 'F' for Fahrenheit, or 'K' for Kelvin
        """
        if unit not in ['C', 'F', 'K']:
            raise ValueError("Unit must be 'C', 'F', or 'K'")
        self.temperature_unit = unit
        logger.info(f"Temperature unit set to: {unit}")

    def get_temperature_unit(self) -> str:
        """Get current temperature unit"""
        return self.temperature_unit

    def set_temperature_range(self, min_temp: float, max_temp: float):
        """
        Set the expected temperature range. Only the "range" method converts with it; for T-Linear data it is the
        display/scene range and does not change any reading.

        Args:
            min_temp: Minimum temperature in Celsius
            max_temp: Maximum temperature in Celsius
        """
        self.min_temp_celsius = min_temp
        self.max_temp_celsius = max_temp
        logger.info(f"Temperature range set: {min_temp}°C to {max_temp}°C")

    def pixel_to_temperature_linear(self, pixel_value: int) -> float:
        """
        Convert pixel value to temperature using linear scaling

        Formula: temp = min_temp + (pixel / 65535) * (max_temp - min_temp)

        Args:
            pixel_value: 16-bit raw pixel value (0-65535)

        Returns:
            Temperature in Celsius
        """
        if self.is_calibrated and self.calibration_slope is not None:
            # Use calibrated parameters
            return self.calibration_slope * pixel_value + self.calibration_offset

        if self.method != "range":
            return float(pixel_value) * self.kelvin_per_count - 273.15

        # Normalize to 0-1
        normalized = (pixel_value - self.min_pixel_value) / (self.max_pixel_value - self.min_pixel_value)

        # Scale to temperature range
        temperature = self.min_temp_celsius + (normalized * (self.max_temp_celsius - self.min_temp_celsius))

        return temperature

    def pixel_to_temperature_lut(self, pixel_value: int) -> Optional[float]:
        """
        Convert pixel value to temperature using TLinear lookup table

        Args:
            pixel_value: 16-bit raw pixel value

        Returns:
            Temperature in Celsius, or None if LUT not loaded
        """
        if self.lut is None or self._lut_x is None:
            logger.warning("TLinear LUT not loaded, falling back to linear conversion")
            return self.pixel_to_temperature_linear(pixel_value)

        # Linear interpolation inside the table, clamped to its ends
        return float(np.interp(pixel_value, self._lut_x, self._lut_y))

    def pixel_to_temperature(self, pixel_value: int) -> Optional[float]:
        """
        Convert pixel value to temperature using configured method

        Args:
            pixel_value: 16-bit raw pixel value

        Returns:
            Temperature in Celsius
        """
        if self.method == "lut" and self.lut is not None:
            temp_c = self.pixel_to_temperature_lut(pixel_value)
        else:
            temp_c = self.pixel_to_temperature_linear(pixel_value)

        if temp_c is not None:
            temp_c = self.apply_environmental_compensation(temp_c)

        return temp_c

    def convert_frame(self, frame_16bit: np.ndarray) -> np.ndarray:
        """
        Convert entire 16-bit radiometric frame to temperature array

        Args:
            frame_16bit: (H, W) uint16 array of raw pixel values

        Returns:
            (H, W) float32 array of temperatures in Celsius
        """
        if frame_16bit is None:
            return None

        if frame_16bit.dtype != np.uint16:
            logger.warning(f"Expected uint16 frame, got {frame_16bit.dtype}")
            return None

        temp_frame = np.zeros_like(frame_16bit, dtype=np.float32)

        if self.method == "lut" and self.lut is not None:
            temp_frame = np.interp(frame_16bit, self._lut_x, self._lut_y).astype(np.float32)
        else:
            # Vectorized linear conversion
            if self.is_calibrated and self.calibration_slope is not None:
                temp_frame = self.calibration_slope * frame_16bit.astype(np.float32) + self.calibration_offset
            elif self.method != "range":
                temp_frame = frame_16bit.astype(np.float32) * np.float32(self.kelvin_per_count) - np.float32(273.15)
            else:
                normalized = (frame_16bit.astype(np.float32) - self.min_pixel_value) / (self.max_pixel_value - self.min_pixel_value)
                temp_frame = self.min_temp_celsius + (normalized * (self.max_temp_celsius - self.min_temp_celsius))

        if self.enable_environmental_compensation:
            temp_frame = self.apply_environmental_compensation(temp_frame)

        return temp_frame


    def get_spot_temperature(self, frame_16bit: np.ndarray, x: int, y: int) -> Optional[float]:
        """
        Get temperature at specific pixel coordinates

        Args:
            frame_16bit: Raw 16-bit frame
            x, y: Pixel coordinates (x=column, y=row)

        Returns:
            Temperature in Celsius, or None if coordinates invalid
        """
        if frame_16bit is None or frame_16bit.dtype != np.uint16:
            return None

        height, width = frame_16bit.shape

        if not (0 <= y < height and 0 <= x < width):
            logger.warning(f"Spot coordinates ({x}, {y}) out of bounds ({width}x{height})")
            return None

        pixel_value = int(frame_16bit[y, x])
        temperature = self.pixel_to_temperature(pixel_value)

        return temperature

    def get_roi_temperature_stats(self, frame_16bit: np.ndarray, roi_mask: np.ndarray) -> Optional[Dict]:
        """
        Get temperature statistics for region of interest

        Args:
            frame_16bit: Raw 16-bit frame
            roi_mask: Binary mask (H, W) where 1 = inside ROI

        Returns:
            Dictionary with temperature statistics:
            {
                'min_temp': float,
                'max_temp': float,
                'mean_temp': float,
                'median_temp': float,
                'std_temp': float,
                'min_location': (x, y),
                'max_location': (x, y),
                'pixel_count': int
            }
        """
        if frame_16bit is None or frame_16bit.dtype != np.uint16:
            return None

        if roi_mask is None or roi_mask.shape != frame_16bit.shape:
            logger.error("ROI mask shape mismatch or None")
            return None

        # Convert frame to temperature
        temp_frame = self.convert_frame(frame_16bit)

        if temp_frame is None:
            return None

        # Extract ROI temperatures
        roi_temps = temp_frame[roi_mask > 0]

        if len(roi_temps) == 0:
            logger.warning("ROI contains no pixels")
            return None

        # Find min/max locations within ROI
        roi_temp_frame = temp_frame.copy()
        roi_temp_frame[roi_mask == 0] = np.nan  # Mask out non-ROI

        # Find min/max coordinates
        min_idx = np.nanargmin(roi_temp_frame)
        max_idx = np.nanargmax(roi_temp_frame)

        min_y, min_x = np.unravel_index(min_idx, temp_frame.shape)
        max_y, max_x = np.unravel_index(max_idx, temp_frame.shape)

        stats = {
            'min_temp': float(np.min(roi_temps)),
            'max_temp': float(np.max(roi_temps)),
            'mean_temp': float(np.mean(roi_temps)),
            'median_temp': float(np.median(roi_temps)),
            'std_temp': float(np.std(roi_temps)),
            'min_location': (int(min_x), int(min_y)),
            'max_location': (int(max_x), int(max_y)),
            'pixel_count': len(roi_temps)
        }

        return stats

    def get_frame_temperature_stats(self, frame_16bit: np.ndarray) -> Optional[Dict]:
        """
        Get temperature statistics for entire frame

        Args:
            frame_16bit: Raw 16-bit frame

        Returns:
            Dictionary with temperature statistics
        """
        if frame_16bit is None or frame_16bit.dtype != np.uint16:
            return None

        # Create full-frame mask
        mask = np.ones_like(frame_16bit, dtype=np.uint8)

        return self.get_roi_temperature_stats(frame_16bit, mask)

    def _set_lut(self, lut_dict: dict):
        self.lut = lut_dict
        self.lut_size = len(lut_dict)
        keys = sorted(lut_dict)
        self._lut_x = np.asarray(keys, dtype=np.float64)
        self._lut_y = np.asarray([lut_dict[k] for k in keys], dtype=np.float64)

    def load_lut_from_file(self, filepath: str) -> bool:
        """
        Load TLinear lookup table from CSV file

        File format: Two columns (pixel_value, temperature_celsius)
        First row can be header (will be skipped if non-numeric)

        Args:
            filepath: Path to CSV file

        Returns:
            True if loaded successfully
        """
        try:
            filepath = Path(filepath)

            if not filepath.exists():
                logger.error(f"LUT file not found: {filepath}")
                return False

            lut_dict = {}

            with open(filepath) as f:
                reader = csv.reader(f)

                for i, row in enumerate(reader):
                    if len(row) < 2:
                        continue

                    # Skip header if present
                    try:
                        pixel_val = int(float(row[0]))
                        temp_c = float(row[1])
                    except ValueError:
                        if i == 0:  # Skip header row
                            continue
                        else:
                            logger.warning(f"Skipping invalid row {i}: {row}")
                            continue

                    lut_dict[pixel_val] = temp_c

            if len(lut_dict) < 2:
                logger.error(f"LUT has insufficient data points: {len(lut_dict)}")
                return False

            self._set_lut(lut_dict)
            self.method = "lut"

            logger.info(f"Loaded TLinear LUT from {filepath.name}: {self.lut_size} entries")
            logger.info(f"  Pixel range: {min(lut_dict.keys())} - {max(lut_dict.keys())}")
            logger.info(f"  Temp range: {min(lut_dict.values()):.1f}°C - {max(lut_dict.values()):.1f}°C")

            return True

        except Exception as e:
            logger.error(f"Error loading LUT from file: {e}")
            return False

    def save_lut_to_file(self, filepath: str) -> bool:
        """
        Save current LUT to CSV file

        Args:
            filepath: Output file path

        Returns:
            True if saved successfully
        """
        if self.lut is None or len(self.lut) == 0:
            logger.error("No LUT to save")
            return False

        try:
            filepath = Path(filepath)
            filepath.parent.mkdir(parents=True, exist_ok=True)

            with open(filepath, 'w', newline='') as f:
                writer = csv.writer(f)

                # Write header
                writer.writerow(['pixel_value', 'temperature_celsius'])

                # Write data sorted by pixel value
                for pixel_val in sorted(self.lut.keys()):
                    temp = self.lut[pixel_val]
                    writer.writerow([pixel_val, f"{temp:.4f}"])

            logger.info(f"Saved TLinear LUT to {filepath}: {len(self.lut)} entries")
            return True

        except Exception as e:
            logger.error(f"Error saving LUT to file: {e}")
            return False

    def set_calibration(self, slope: float, offset: float):
        """
        Set linear calibration parameters

        Formula: temperature = slope * pixel_value + offset

        Args:
            slope: Calibration slope (°C per pixel)
            offset: Calibration offset (°C)
        """
        self.calibration_slope = slope
        self.calibration_offset = offset
        self.is_calibrated = True

        logger.info(f"Calibration set: temp = {slope:.8f} * pixel + {offset:.4f}")

    def calibrate_from_references(self, reference_points: list) -> bool:
        """
        Calibrate using reference temperature measurements

        Args:
            reference_points: List of (pixel_value, known_temperature) tuples

        Returns:
            True if calibration successful
        """
        if len(reference_points) < 2:
            logger.error("Need at least 2 reference points for calibration")
            return False

        # Extract pixel values and temperatures (float64: counts near 30000 times a ~0.01 slope lose digits in float32)
        pixels = np.array([p[0] for p in reference_points], dtype=np.float64)
        temps = np.array([p[1] for p in reference_points], dtype=np.float64)

        if np.unique(pixels).size < 2:
            logger.error("Calibration needs reference points at two or more different pixel values "
                         "(all points read the same value, so no slope can be fitted)")
            return False

        # Linear regression: temp = slope * pixel + offset
        slope, offset = np.polyfit(pixels, temps, 1)
        if not (np.isfinite(slope) and np.isfinite(offset)) or slope <= 0:
            logger.error(f"Calibration rejected: fitted slope {slope} is not a positive finite value "
                         "(hotter references must read higher)")
            return False

        self.set_calibration(slope, offset)

        # Calculate calibration error
        predicted_temps = slope * pixels + offset
        errors = predicted_temps - temps
        rmse = np.sqrt(np.mean(errors ** 2))

        logger.info("Calibration complete:")
        logger.info(f"  Reference points: {len(reference_points)}")
        logger.info(f"  RMSE: {rmse:.3f}°C")
        logger.info(f"  Max error: {np.max(np.abs(errors)):.3f}°C")

        return True

    def get_info(self) -> Dict:
        """
        Get converter information

        Returns:
            Dictionary with converter status and parameters
        """
        info = {
            'method': self.method,
            'is_calibrated': self.is_calibrated,
            'lut_loaded': self.lut is not None,
            'lut_size': self.lut_size if self.lut else 0,
            'temp_range': (self.min_temp_celsius, self.max_temp_celsius),
        }

        if self.is_calibrated:
            info['calibration_slope'] = self.calibration_slope
            info['calibration_offset'] = self.calibration_offset

        return info


# Convenience function for quick temperature conversion
def quick_convert_frame(frame_16bit: np.ndarray, min_temp: float = -40.0,
                       max_temp: float = 550.0) -> np.ndarray:
    """
    Quick conversion of a 16-bit frame by mapping its full span onto min_temp..max_temp (an estimate for streams that
    are not T-Linear; for a Boson's radiometric Y16 use TLinearConverter().convert_frame)

    Args:
        frame_16bit: Raw 16-bit frame
        min_temp: Minimum temperature in range
        max_temp: Maximum temperature in range

    Returns:
        Temperature frame in Celsius
    """
    converter = TLinearConverter(method="range")
    converter.set_temperature_range(min_temp, max_temp)
    return converter.convert_frame(frame_16bit)


if __name__ == "__main__":
    # Test the converter
    logging.basicConfig(level=logging.INFO)

    print("\n" + "="*60)
    print("RADIOMETRIC CONVERTER TEST")
    print("="*60)

    # Create converter
    converter = TLinearConverter(method="range")
    converter.set_temperature_range(-20.0, 150.0)

    # Test spot conversion
    test_pixel = 32768  # Mid-range
    temp = converter.pixel_to_temperature(test_pixel)
    print("\nSpot conversion test:")
    print(f"  Pixel value: {test_pixel}")
    print(f"  Temperature: {temp:.2f}°C")

    # Test frame conversion
    print("\nFrame conversion test:")
    test_frame = np.random.randint(10000, 40000, size=(512, 640), dtype=np.uint16)
    temp_frame = converter.convert_frame(test_frame)

    if temp_frame is not None:
        print(f"  Input frame: {test_frame.shape}, dtype={test_frame.dtype}")
        print(f"  Output frame: {temp_frame.shape}, dtype={temp_frame.dtype}")
        print(f"  Temperature range: {temp_frame.min():.1f}°C to {temp_frame.max():.1f}°C")
        print(f"  Mean temperature: {temp_frame.mean():.1f}°C")

    print("Test complete!")
    print("="*60 + "\n")
