"""
Interactive Radiometric Calibration Tool

Provides multi-point calibration for radiometric thermal cameras.
Allows users to calibrate against known reference temperatures to improve accuracy.
"""

import numpy as np
from typing import List, Dict
from dataclasses import dataclass
import logging
from datetime import datetime
import json

logger = logging.getLogger(__name__)


@dataclass
class CalibrationPoint:
    """
    Single calibration point.

    Attributes:
        reference_temp: Known reference temperature in Celsius
        measured_temp: Camera-measured temperature in Celsius
        x: X coordinate in frame
        y: Y coordinate in frame
        timestamp: When the measurement was taken
    """
    reference_temp: float
    measured_temp: float
    x: int
    y: int
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()

    @property
    def error(self) -> float:
        """Calculate measurement error."""
        return self.measured_temp - self.reference_temp


class RadiometricCalibrator:
    """
    Radiometric calibration manager.

    Supports multi-point calibration with linear and polynomial fitting.
    Helps correct systematic temperature measurement errors.
    """

    def __init__(self):
        """Initialize calibrator."""
        self.calibration_points: List[CalibrationPoint] = []
        self.calibration_curve = None  # Polynomial coefficients
        self.calibration_method = "linear"  # "linear" or "polynomial"
        self.polynomial_degree = 2
        self.is_calibrated = False

    def add_calibration_point(self, reference_temp: float, measured_temp: float,
                             x: int, y: int) -> CalibrationPoint:
        """
        Add a calibration point.

        Args:
            reference_temp: Known reference temperature (°C)
            measured_temp: Camera-measured temperature (°C)
            x: X coordinate in frame
            y: Y coordinate in frame

        Returns:
            Created CalibrationPoint
        """
        point = CalibrationPoint(
            reference_temp=reference_temp,
            measured_temp=measured_temp,
            x=x,
            y=y
        )

        self.calibration_points.append(point)
        logger.info(f"Added calibration point: {reference_temp:.1f}°C (ref) vs {measured_temp:.1f}°C (meas), error: {point.error:.2f}°C")

        # Invalidate calibration when new point added
        self.is_calibrated = False

        return point

    def remove_calibration_point(self, index: int) -> bool:
        """
        Remove a calibration point by index.

        Args:
            index: Index of point to remove

        Returns:
            True if removed, False if index invalid
        """
        if 0 <= index < len(self.calibration_points):
            point = self.calibration_points.pop(index)
            logger.info(f"Removed calibration point at index {index}")
            self.is_calibrated = False
            return True
        return False

    def clear_calibration_points(self):
        """Remove all calibration points."""
        count = len(self.calibration_points)
        self.calibration_points.clear()
        self.is_calibrated = False
        self.calibration_curve = None
        logger.info(f"Cleared {count} calibration points")

    def compute_calibration(self, method: str = "linear", degree: int = 2) -> bool:
        """
        Compute calibration curve from points.

        Args:
            method: "linear" or "polynomial"
            degree: Polynomial degree (if method="polynomial")

        Returns:
            True if successful
        """
        if len(self.calibration_points) < 2:
            logger.warning("Need at least 2 calibration points")
            return False

        self.calibration_method = method
        self.polynomial_degree = degree

        # Extract measured and reference temperatures
        measured = np.array([p.measured_temp for p in self.calibration_points])
        reference = np.array([p.reference_temp for p in self.calibration_points])

        try:
            if method == "linear":
                # Linear fit: reference = a * measured + b
                coeffs = np.polyfit(measured, reference, 1)
                self.calibration_curve = coeffs
                logger.info(f"Linear calibration computed: T_corrected = {coeffs[0]:.4f} * T_measured + {coeffs[1]:.2f}")

            elif method == "polynomial":
                # Polynomial fit
                if len(self.calibration_points) < degree + 1:
                    logger.warning(f"Need at least {degree + 1} points for degree {degree} polynomial")
                    return False

                coeffs = np.polyfit(measured, reference, degree)
                self.calibration_curve = coeffs
                logger.info(f"Polynomial (degree {degree}) calibration computed")

            else:
                logger.error(f"Unknown calibration method: {method}")
                return False

            self.is_calibrated = True
            return True

        except Exception as e:
            logger.error(f"Error computing calibration: {e}")
            return False

    def apply_calibration(self, measured_temp: float) -> float:
        """
        Apply calibration to a measured temperature.

        Args:
            measured_temp: Camera-measured temperature (°C)

        Returns:
            Calibrated temperature (°C)
        """
        if not self.is_calibrated or self.calibration_curve is None:
            return measured_temp

        # Apply polynomial correction
        corrected = np.polyval(self.calibration_curve, measured_temp)
        return float(corrected)

    def apply_calibration_to_frame(self, temp_frame: np.ndarray) -> np.ndarray:
        """
        Apply calibration to entire temperature frame.

        Args:
            temp_frame: Temperature frame (H, W) in Celsius

        Returns:
            Calibrated temperature frame
        """
        if not self.is_calibrated or self.calibration_curve is None:
            return temp_frame

        # Apply polynomial correction to entire frame
        corrected = np.polyval(self.calibration_curve, temp_frame)
        return corrected.astype(np.float32)

    def get_calibration_stats(self) -> Dict:
        """
        Get calibration statistics.

        Returns:
            Dictionary with calibration stats
        """
        if len(self.calibration_points) == 0:
            return {
                'point_count': 0,
                'is_calibrated': False
            }

        errors = np.array([p.error for p in self.calibration_points])

        stats = {
            'point_count': len(self.calibration_points),
            'is_calibrated': self.is_calibrated,
            'method': self.calibration_method,
            'mean_error': float(np.mean(errors)),
            'std_error': float(np.std(errors)),
            'max_error': float(np.max(np.abs(errors))),
            'rmse': float(np.sqrt(np.mean(errors**2)))
        }

        if self.is_calibrated and self.calibration_curve is not None:
            stats['coefficients'] = self.calibration_curve.tolist()

        return stats

    def export_calibration(self, filepath: str) -> bool:
        """
        Export calibration to JSON file.

        Args:
            filepath: Path to save calibration file

        Returns:
            True if successful
        """
        try:
            data = {
                'timestamp': datetime.now().isoformat(),
                'method': self.calibration_method,
                'polynomial_degree': self.polynomial_degree,
                'is_calibrated': self.is_calibrated,
                'coefficients': self.calibration_curve.tolist() if self.calibration_curve is not None else None,
                'calibration_points': [
                    {
                        'reference_temp': p.reference_temp,
                        'measured_temp': p.measured_temp,
                        'x': p.x,
                        'y': p.y,
                        'error': p.error,
                        'timestamp': p.timestamp
                    }
                    for p in self.calibration_points
                ],
                'statistics': self.get_calibration_stats()
            }

            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2)

            logger.info(f"Calibration exported to {filepath}")
            return True

        except Exception as e:
            logger.error(f"Error exporting calibration: {e}")
            return False

    def import_calibration(self, filepath: str) -> bool:
        """
        Import calibration from JSON file.

        Args:
            filepath: Path to calibration file

        Returns:
            True if successful
        """
        try:
            with open(filepath) as f:
                data = json.load(f)

            # Clear existing calibration
            self.clear_calibration_points()

            # Import points
            for point_data in data.get('calibration_points', []):
                self.calibration_points.append(CalibrationPoint(
                    reference_temp=point_data['reference_temp'],
                    measured_temp=point_data['measured_temp'],
                    x=point_data['x'],
                    y=point_data['y'],
                    timestamp=point_data.get('timestamp', '')
                ))

            # Import calibration curve
            self.calibration_method = data.get('method', 'linear')
            self.polynomial_degree = data.get('polynomial_degree', 2)
            self.is_calibrated = data.get('is_calibrated', False)

            if data.get('coefficients') is not None:
                self.calibration_curve = np.array(data['coefficients'])

            logger.info(f"Calibration imported from {filepath} ({len(self.calibration_points)} points)")
            return True

        except Exception as e:
            logger.error(f"Error importing calibration: {e}")
            return False


# ============================================================================
# Test
# ============================================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("\n" + "="*70)
    print("RADIOMETRIC CALIBRATION TEST")
    print("="*70)

    calibrator = RadiometricCalibrator()

    # Simulate calibration points (measured temp is slightly off from reference)
    # Typical scenario: camera reads higher than actual
    test_points = [
        (20.0, 22.5),  # Reference, Measured
        (30.0, 32.3),
        (40.0, 42.1),
        (50.0, 52.0),
        (60.0, 61.8),
    ]

    print("\nAdding calibration points...")
    for i, (ref, meas) in enumerate(test_points):
        calibrator.add_calibration_point(ref, meas, x=100+i*10, y=100)

    # Compute linear calibration
    print("\nComputing linear calibration...")
    calibrator.compute_calibration(method="linear")

    # Get statistics
    stats = calibrator.get_calibration_stats()
    print("\nCalibration Statistics:")
    print(f"  Points: {stats['point_count']}")
    print(f"  Method: {stats['method']}")
    print(f"  Mean Error: {stats['mean_error']:.2f}°C")
    print(f"  RMSE: {stats['rmse']:.2f}°C")
    print(f"  Max Error: {stats['max_error']:.2f}°C")

    # Test correction
    print("\nTesting calibration correction:")
    test_temps = [25.0, 35.0, 45.0, 55.0]
    for temp in test_temps:
        corrected = calibrator.apply_calibration(temp)
        print(f"  Measured: {temp:.1f}°C → Corrected: {corrected:.1f}°C")

    # Test frame correction
    print("\nTesting frame calibration...")
    test_frame = np.array([[22.5, 32.3], [42.1, 52.0]], dtype=np.float32)
    corrected_frame = calibrator.apply_calibration_to_frame(test_frame)
    print(f"  Original frame:\n{test_frame}")
    print(f"  Corrected frame:\n{corrected_frame}")

    # Test export
    print("\nExporting calibration...")
    calibrator.export_calibration("test_calibration.json")

    print("\n" + "="*70)
    print("Test complete!")
    print("="*70 + "\n")
