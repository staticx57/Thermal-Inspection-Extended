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
from typing import Optional, Tuple, Dict
from pathlib import Path
import csv
from datetime import datetime

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
            method: Conversion method - "linear" or "lut"
            temperature_unit: Temperature unit - "C" (Celsius) or "F" (Fahrenheit)
        """
        self.method = method
        self.temperature_unit = temperature_unit
        self.lut = None  # Lookup table dict: {pixel_value: temperature}
        self.lut_size = 0

        # Linear conversion parameters (default for Boson 640)
        # These are approximate and should be calibrated
        self.min_temp_celsius = -40.0
        self.max_temp_celsius = 550.0
        self.min_pixel_value = 0
        self.max_pixel_value = 65535

        # Calibration parameters (computed from reference points)
        self.calibration_slope = None
        self.calibration_offset = None
        self.is_calibrated = False

        logger.info(f"Radiometric converter initialized (method: {method}, unit: {temperature_unit})")

    # Temperature Unit Conversion Methods
    
    def celsius_to_fahrenheit(self, temp_c: float) -> float:
        """Convert Celsius to Fahrenheit. Formula: F = C * 9/5 + 32"""
        return (temp_c * 9.0 / 5.0) + 32.0
    
    def fahrenheit_to_celsius(self, temp_f: float) -> float:
        """Convert Fahrenheit to Celsius. Formula: C = (F - 32) * 5/9"""
        return (temp_f - 32.0) * 5.0 / 9.0
    
    def convert_temperature(self, temp_c: float) -> float:
        """
        Convert temperature from Celsius to current unit setting.
        
        Args:
            temp_c: Temperature in Celsius
        
        Returns:
            Temperature in selected unit (C or F)
        """
        if self.temperature_unit == 'F':
            return self.celsius_to_fahrenheit(temp_c)
        return temp_c
    
    def get_temperature_unit_symbol(self) -> str:
        """Get temperature unit symbol for display"""
        return 'F' if self.temperature_unit == 'F' else 'C'
    
    def set_temperature_unit(self, unit: str):
        """
        Set temperature unit.
        
        Args:
            unit: 'C' for Celsius or 'F' for Fahrenheit
        """
        if unit not in ['C', 'F']:
            raise ValueError("Unit must be 'C' or 'F'")
        self.temperature_unit = unit
        logger.info(f"Temperature unit set to: {unit}")
    
    def get_temperature_unit(self) -> str:
        """Get current temperature unit"""
        return self.temperature_unit

    def set_temperature_range(self, min_temp: float, max_temp: float):
        """
        Set expected temperature range for linear conversion

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
        if self.lut is None:
            logger.warning("TLinear LUT not loaded, falling back to linear conversion")
            return self.pixel_to_temperature_linear(pixel_value)

        # Direct lookup
        if pixel_value in self.lut:
            return self.lut[pixel_value]

        # Interpolate if exact value not in LUT
        keys = sorted(self.lut.keys())

        # Clamp to LUT range
        if pixel_value < keys[0]:
            return self.lut[keys[0]]
        if pixel_value > keys[-1]:
            return self.lut[keys[-1]]

        # Find surrounding values and interpolate
        for i in range(len(keys) - 1):
            if keys[i] <= pixel_value <= keys[i+1]:
                # Linear interpolation
                x0, x1 = keys[i], keys[i+1]
                y0, y1 = self.lut[x0], self.lut[x1]

                if x1 == x0:  # Avoid division by zero
                    return y0

                t = (pixel_value - x0) / (x1 - x0)
                return y0 + t * (y1 - y0)

        return None

    def pixel_to_temperature(self, pixel_value: int) -> Optional[float]:
        """
        Convert pixel value to temperature using configured method

        Args:
            pixel_value: 16-bit raw pixel value

        Returns:
            Temperature in Celsius
        """
        if self.method == "lut" and self.lut is not None:
            return self.pixel_to_temperature_lut(pixel_value)
        else:
            return self.pixel_to_temperature_linear(pixel_value)

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
            # Vectorized LUT lookup (optimized)
            unique_values = np.unique(frame_16bit)

            for pixel_val in unique_values:
                mask = (frame_16bit == pixel_val)
                temp = self.pixel_to_temperature_lut(int(pixel_val))
                if temp is not None:
                    temp_frame[mask] = temp
        else:
            # Vectorized linear conversion
            if self.is_calibrated and self.calibration_slope is not None:
                temp_frame = self.calibration_slope * frame_16bit.astype(np.float32) + self.calibration_offset
            else:
                normalized = (frame_16bit.astype(np.float32) - self.min_pixel_value) / (self.max_pixel_value - self.min_pixel_value)
                temp_frame = self.min_temp_celsius + (normalized * (self.max_temp_celsius - self.min_temp_celsius))

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

            with open(filepath, 'r') as f:
                reader = csv.reader(f)

                for i, row in enumerate(reader):
                    if len(row) < 2:
                        continue

                    # Skip header if present
                    try:
                        pixel_val = int(row[0])
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

            self.lut = lut_dict
            self.lut_size = len(lut_dict)
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

        # Extract pixel values and temperatures
        pixels = np.array([p[0] for p in reference_points], dtype=np.float32)
        temps = np.array([p[1] for p in reference_points], dtype=np.float32)

        # Linear regression: temp = slope * pixel + offset
        slope, offset = np.polyfit(pixels, temps, 1)

        self.set_calibration(slope, offset)

        # Calculate calibration error
        predicted_temps = slope * pixels + offset
        errors = predicted_temps - temps
        rmse = np.sqrt(np.mean(errors ** 2))

        logger.info(f"Calibration complete:")
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


class RadiometricCalibration:
    """
    Tool for calibrating radiometric temperature conversion

    Helps create calibration curves from known reference temperatures.
    """

    def __init__(self):
        self.reference_points = []  # List of (pixel_value, known_temp, timestamp)

    def add_reference_point(self, pixel_value: int, known_temp: float):
        """
        Add calibration reference point

        Args:
            pixel_value: Raw pixel value measured at known temperature
            known_temp: Known reference temperature in Celsius
        """
        timestamp = datetime.now()
        self.reference_points.append((pixel_value, known_temp, timestamp))

        logger.info(f"Added calibration point: pixel={pixel_value} -> temp={known_temp}°C")

    def clear_points(self):
        """Clear all reference points"""
        self.reference_points = []
        logger.info("Calibration points cleared")

    def compute_calibration(self, converter: TLinearConverter) -> bool:
        """
        Compute and apply calibration to converter

        Args:
            converter: TLinearConverter instance to calibrate

        Returns:
            True if successful
        """
        if len(self.reference_points) < 2:
            logger.error("Need at least 2 reference points")
            return False

        # Extract data
        ref_data = [(p[0], p[1]) for p in self.reference_points]

        # Apply to converter
        return converter.calibrate_from_references(ref_data)

    def save_calibration_file(self, filepath: str) -> bool:
        """
        Save calibration reference points to file

        Args:
            filepath: Output file path

        Returns:
            True if saved successfully
        """
        try:
            filepath = Path(filepath)
            filepath.parent.mkdir(parents=True, exist_ok=True)

            with open(filepath, 'w', newline='') as f:
                writer = csv.writer(f)

                # Write header
                writer.writerow(['pixel_value', 'temperature_celsius', 'timestamp'])

                # Write reference points
                for pixel_val, temp, timestamp in self.reference_points:
                    writer.writerow([pixel_val, temp, timestamp.isoformat()])

            logger.info(f"Calibration saved: {len(self.reference_points)} points to {filepath}")
            return True

        except Exception as e:
            logger.error(f"Error saving calibration: {e}")
            return False

    def load_calibration_file(self, filepath: str) -> bool:
        """
        Load calibration reference points from file

        Args:
            filepath: Input file path

        Returns:
            True if loaded successfully
        """
        try:
            filepath = Path(filepath)

            if not filepath.exists():
                logger.error(f"Calibration file not found: {filepath}")
                return False

            self.reference_points = []

            with open(filepath, 'r') as f:
                reader = csv.reader(f)
                next(reader)  # Skip header

                for row in reader:
                    if len(row) < 2:
                        continue

                    pixel_val = int(row[0])
                    temp = float(row[1])

                    # Parse timestamp if present
                    if len(row) >= 3:
                        try:
                            timestamp = datetime.fromisoformat(row[2])
                        except:
                            timestamp = datetime.now()
                    else:
                        timestamp = datetime.now()

                    self.reference_points.append((pixel_val, temp, timestamp))

            logger.info(f"Loaded calibration: {len(self.reference_points)} points from {filepath}")
            return True

        except Exception as e:
            logger.error(f"Error loading calibration: {e}")
            return False


# Convenience function for quick temperature conversion
def quick_convert_frame(frame_16bit: np.ndarray, min_temp: float = -40.0,
                       max_temp: float = 550.0) -> np.ndarray:
    """
    Quick conversion of 16-bit frame to temperature using linear method

    Args:
        frame_16bit: Raw 16-bit frame
        min_temp: Minimum temperature in range
        max_temp: Maximum temperature in range

    Returns:
        Temperature frame in Celsius
    """
    converter = TLinearConverter(method="linear")
    converter.set_temperature_range(min_temp, max_temp)
    return converter.convert_frame(frame_16bit)


if __name__ == "__main__":
    # Test the converter
    logging.basicConfig(level=logging.INFO)

    print("\n" + "="*60)
    print("RADIOMETRIC CONVERTER TEST")
    print("="*60)

    # Create converter
    converter = TLinearConverter(method="linear")
    converter.set_temperature_range(-20.0, 150.0)

    # Test spot conversion
    test_pixel = 32768  # Mid-range
    temp = converter.pixel_to_temperature(test_pixel)
    print(f"\nSpot conversion test:")
    print(f"  Pixel value: {test_pixel}")
    print(f"  Temperature: {temp:.2f}°C")

    # Test frame conversion
    print(f"\nFrame conversion test:")
    test_frame = np.random.randint(10000, 40000, size=(512, 640), dtype=np.uint16)
    temp_frame = converter.convert_frame(test_frame)

    if temp_frame is not None:
        print(f"  Input frame: {test_frame.shape}, dtype={test_frame.dtype}")
        print(f"  Output frame: {temp_frame.shape}, dtype={temp_frame.dtype}")
        print(f"  Temperature range: {temp_frame.min():.1f}°C to {temp_frame.max():.1f}°C")
        print(f"  Mean temperature: {temp_frame.mean():.1f}°C")

    # Test calibration
    print(f"\nCalibration test:")
    calib = RadiometricCalibration()
    calib.add_reference_point(7500, 0.0)    # Ice water
    calib.add_reference_point(45000, 100.0)  # Boiling water

    if calib.compute_calibration(converter):
        print(f"  Calibration applied successfully")

        # Test calibrated conversion
        temp_calibrated = converter.pixel_to_temperature(test_pixel)
        print(f"  Calibrated temperature at {test_pixel}: {temp_calibrated:.2f}°C")

    print("\n" + "="*60)
    print("Test complete!")
    print("="*60 + "\n")
