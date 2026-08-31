import logging

logger = logging.getLogger(__name__)

class CalibrationManager:
    """Manages radiometric calibration state and logic."""

    def __init__(self):
        self.calibration_enabled: bool = False
        self.calibration_add_point_mode: bool = False
        self.calibration_reference_temp: float = 25.0

        # Initialize radiometric calibrator
        try:
            from thermal_inspection.utils.radiometric_calibration import RadiometricCalibrator
            self.radiometric_calibrator = RadiometricCalibrator()
            logger.info("RadiometricCalibrator initialized")
        except ImportError as e:
            logger.warning(f"RadiometricCalibrator not available: {e}")
            self.radiometric_calibrator = None

    def clear_calibration(self):
        """Clear all radiometric calibration points."""
        if self.radiometric_calibrator:
            self.radiometric_calibrator.clear_calibration_points()
            logger.info("Calibration points cleared")

    def compute_calibration(self, method: str = 'linear', degree: int = 2) -> bool:
        """Compute calibration from current points.

        Args:
            method: 'linear' or 'polynomial'
            degree: Polynomial degree (used when method='polynomial')

        Returns:
            True if calibration computed successfully
        """
        if not self.radiometric_calibrator:
            logger.warning("No radiometric calibrator available")
            return False
        return self.radiometric_calibrator.compute_calibration(method=method, degree=degree)

    def import_calibration(self, filepath: str) -> bool:
        """Import calibration from JSON file."""
        if not self.radiometric_calibrator:
            return False
        return self.radiometric_calibrator.import_calibration(filepath)

    def export_calibration(self, filepath: str) -> bool:
        """Export current calibration to JSON file."""
        if not self.radiometric_calibrator:
            return False
        return self.radiometric_calibrator.export_calibration(filepath)

    def set_calibration_enabled(self, enabled: bool):
        """Enable or disable application of the radiometric calibration."""
        self.calibration_enabled = enabled
        logger.info(f"Radiometric calibration application: {'ON' if enabled else 'OFF'}")

    def set_calibration_add_point_mode(self, enabled: bool, reference_temp: float = 25.0):
        """Enter or exit calibration point-add mode.

        When active, the next click on the video will add a calibration point
        at the clicked location using the given reference temperature.

        Args:
            enabled: True to enter add-point mode
            reference_temp: Known reference temperature in Celsius
        """
        self.calibration_add_point_mode = enabled
        self.calibration_reference_temp = reference_temp
        logger.info(
            f"Calibration add-point mode: {'ON' if enabled else 'OFF'}, "
            f"ref={reference_temp:.1f}°C"
        )

    def remove_calibration_point(self, index: int) -> bool:
        """Remove a calibration point by index."""
        if not self.radiometric_calibrator:
            return False
        return self.radiometric_calibrator.remove_calibration_point(index)

    def add_calibration_point(self, x: int, y: int, thermal_camera, thermal_analyzer, last_thermal_frame):
        """Add a calibration point at the given pixel coordinates.

        Reads the measured temperature from the camera's last radiometric frame
        (or falls back to the thermal analyzer's spot estimate) and registers a
        calibration point with the known reference temperature.

        Args:
            x: Pixel x-coordinate
            y: Pixel y-coordinate
            thermal_camera: The thermal camera object
            thermal_analyzer: The thermal analyzer object
            last_thermal_frame: The last thermal frame from the camera
        """
        if not self.radiometric_calibrator:
            logger.warning("Cannot add calibration point — no calibrator available")
            return

        # Exit add-point mode immediately so only one point is added per activation
        self.calibration_add_point_mode = False

        # Try to get measured temperature from camera
        measured_temp = None
        raw_val = None

        if thermal_camera and hasattr(thermal_camera, 'get_spot_temperature'):
            measured_temp = thermal_camera.get_spot_temperature(x, y)

        if measured_temp is None and thermal_analyzer:
            # Fallback: estimate from 8-bit pixel value via analyzer
            if last_thermal_frame is not None:
                h, w = last_thermal_frame.shape[:2]
                if 0 <= x < w and 0 <= y < h:
                    raw_val = float(last_thermal_frame[y, x])
                    measured_temp, _ = thermal_analyzer.calculate_spot_temperature(raw_val)

        if measured_temp is None:
            logger.warning(f"Could not read temperature at ({x}, {y}) — calibration point not added")
            return

        self.radiometric_calibrator.add_calibration_point(
            reference_temp=self.calibration_reference_temp,
            measured_temp=measured_temp,
            raw_value=raw_val,
        )
        logger.info(
            f"Calibration point added: ref={self.calibration_reference_temp:.1f}°C, "
            f"measured={measured_temp:.1f}°C at ({x}, {y})"
        )

    def get_calibration_stats(self) -> dict:
        """Return the current calibration statistics."""
        if not self.radiometric_calibrator:
            return {}
        return self.radiometric_calibrator.get_calibration_stats()
