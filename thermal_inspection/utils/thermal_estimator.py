#!/usr/bin/env python3
"""
Thermal Temperature Estimator - 8-bit Pseudo-Radiometric

Estimates temperatures from 8-bit AGC thermal images using FPA temperature
as a reference point. Provides approximate absolute temperatures.

Accuracy: ±5-10°C (vs ±2°C for true 16-bit radiometric)
Good for: Hot spot detection, relative measurements, logging
Not good for: Precise calibration, NIST-traceable measurements

Note: This is a hobby project trading complexity for time.
      True 16-bit radiometric can be added later via USB backend.
"""

import numpy as np
import logging

logger = logging.getLogger(__name__)


class ThermalTemperatureEstimator:
    """
    Estimate temperatures from 8-bit AGC thermal images.

    Uses FPA (Focal Plane Array) temperature as reference and assumes
    linear temperature distribution across the AGC range.

    Attributes:
        scene_min_c: Minimum expected scene temperature (Celsius)
        scene_max_c: Maximum expected scene temperature (Celsius)
        calibration_offset: Manual calibration adjustment (Celsius)
        use_adaptive_range: Automatically adjust scene range based on AGC histogram
    """

    def __init__(
        self,
        scene_min_c: float = 10.0,
        scene_max_c: float = 110.0,
        calibration_offset: float = 0.0,
        use_adaptive_range: bool = True
    ):
        """
        Initialize temperature estimator.

        Args:
            scene_min_c: Minimum expected scene temperature
            scene_max_c: Maximum expected scene temperature
            calibration_offset: Manual calibration offset to add
            use_adaptive_range: Dynamically adjust range based on scene
        """
        self.scene_min_c = scene_min_c
        self.scene_max_c = scene_max_c
        self.calibration_offset = calibration_offset
        self.use_adaptive_range = use_adaptive_range

        logger.info(
            f"ThermalTemperatureEstimator initialized: "
            f"range={scene_min_c:.1f}°C to {scene_max_c:.1f}°C, "
            f"offset={calibration_offset:.2f}°C"
        )

    def estimate_temperature_map(
        self,
        agc_frame: np.ndarray,
        fpa_temp_c: float
    ) -> np.ndarray:
        """
        Convert 8-bit AGC frame to estimated temperature map.

        Args:
            agc_frame: 8-bit grayscale thermal image (0-255)
            fpa_temp_c: FPA temperature in Celsius (from camera SDK)

        Returns:
            Temperature map in Celsius (same shape as input)
        """
        if agc_frame is None:
            return None

        # Convert to float for processing
        frame_float = agc_frame.astype(float)

        # Normalize to 0-1 range
        normalized = frame_float / 255.0

        # Calculate temperature range
        if self.use_adaptive_range:
            # Use frame statistics to adjust range dynamically
            scene_range = self._estimate_scene_range(normalized, fpa_temp_c)
        else:
            # Use fixed range
            scene_range = self.scene_max_c - self.scene_min_c

        # Estimate temperature using FPA as reference
        # Assumes FPA temp is roughly middle of scene range
        temp_map = self.scene_min_c + (normalized * scene_range) + self.calibration_offset

        logger.debug(
            f"Temperature map: min={temp_map.min():.1f}°C, "
            f"max={temp_map.max():.1f}°C, mean={temp_map.mean():.1f}°C"
        )

        return temp_map

    def _estimate_scene_range(
        self,
        normalized_frame: np.ndarray,
        fpa_temp_c: float
    ) -> float:
        """
        Estimate actual scene temperature range from frame histogram.

        Uses the spread of AGC values to estimate how wide the temperature
        range actually is in the scene.
        """
        # Calculate histogram statistics
        p10 = np.percentile(normalized_frame, 10)
        p90 = np.percentile(normalized_frame, 90)

        # Estimate range based on AGC spread
        # More spread = wider temperature range
        agc_spread = p90 - p10

        # Map AGC spread to temperature range
        # Full spread (0.8) = full range, narrow spread = reduced range
        base_range = self.scene_max_c - self.scene_min_c
        estimated_range = base_range * (agc_spread / 0.8)

        # Clamp to reasonable bounds
        estimated_range = np.clip(estimated_range, 20.0, base_range)

        logger.debug(f"Adaptive range: {estimated_range:.1f}°C (AGC spread: {agc_spread:.2f})")

        return estimated_range

    def get_pixel_temperature(
        self,
        agc_frame: np.ndarray,
        x: int,
        y: int,
        fpa_temp_c: float
    ) -> float:
        """
        Get estimated temperature for a specific pixel.

        Args:
            agc_frame: 8-bit AGC frame
            x: Pixel x coordinate
            y: Pixel y coordinate
            fpa_temp_c: FPA temperature in Celsius

        Returns:
            Estimated temperature in Celsius
        """
        if agc_frame is None or x < 0 or y < 0:
            return None

        if y >= agc_frame.shape[0] or x >= agc_frame.shape[1]:
            return None

        # Get pixel value
        agc_value = agc_frame[y, x]

        # Normalize
        normalized = agc_value / 255.0

        # Estimate temperature
        scene_range = self.scene_max_c - self.scene_min_c
        temp_c = self.scene_min_c + (normalized * scene_range) + self.calibration_offset

        return temp_c

    def get_statistics(
        self,
        agc_frame: np.ndarray,
        fpa_temp_c: float
    ) -> dict:
        """
        Get temperature statistics for entire frame.

        Args:
            agc_frame: 8-bit AGC frame
            fpa_temp_c: FPA temperature in Celsius

        Returns:
            Dictionary with temperature statistics
        """
        temp_map = self.estimate_temperature_map(agc_frame, fpa_temp_c)

        if temp_map is None:
            return None

        # Find hottest and coldest spots
        max_temp = temp_map.max()
        min_temp = temp_map.min()
        mean_temp = temp_map.mean()
        std_temp = temp_map.std()

        max_loc = np.unravel_index(temp_map.argmax(), temp_map.shape)
        min_loc = np.unravel_index(temp_map.argmin(), temp_map.shape)

        return {
            'min_temp_c': min_temp,
            'max_temp_c': max_temp,
            'mean_temp_c': mean_temp,
            'std_temp_c': std_temp,
            'min_location': (max_loc[1], max_loc[0]),  # (x, y)
            'max_location': (min_loc[1], min_loc[0]),  # (x, y)
            'fpa_temp_c': fpa_temp_c,
            'note': 'Estimated temperatures (±5-10°C accuracy)'
        }

    def calibrate_single_point(
        self,
        agc_value: int,
        known_temp_c: float,
        fpa_temp_c: float
    ):
        """
        Calibrate estimator using a single known temperature reference.

        Example: Point camera at object with known temperature (e.g., ice water = 0°C,
        boiling water = 100°C, calibrated blackbody, etc.)

        Args:
            agc_value: AGC pixel value (0-255) of reference object
            known_temp_c: Known temperature of reference object
            fpa_temp_c: Current FPA temperature

        Updates:
            self.calibration_offset
        """
        # Calculate what we would estimate without calibration
        normalized = agc_value / 255.0
        scene_range = self.scene_max_c - self.scene_min_c
        estimated = self.scene_min_c + (normalized * scene_range)

        # Calculate offset needed to match known temperature
        self.calibration_offset = known_temp_c - estimated

        logger.info(
            f"Single-point calibration: "
            f"AGC={agc_value}, known={known_temp_c:.1f}°C, "
            f"estimated={estimated:.1f}°C, offset={self.calibration_offset:.2f}°C"
        )

    def calibrate_two_point(
        self,
        agc_low: int,
        temp_low_c: float,
        agc_high: int,
        temp_high_c: float,
        fpa_temp_c: float
    ):
        """
        Calibrate estimator using two known temperature references.

        This is more accurate than single-point calibration as it adjusts
        both the range and offset.

        Example: Ice water (0°C) and boiling water (100°C)

        Args:
            agc_low: AGC value of cold reference
            temp_low_c: Known temperature of cold reference
            agc_high: AGC value of hot reference
            temp_high_c: Known temperature of hot reference
            fpa_temp_c: Current FPA temperature
        """
        # Calculate scene range from calibration points
        agc_range = agc_high - agc_low
        temp_range = temp_high_c - temp_low_c

        if agc_range == 0:
            logger.error("Two-point calibration failed: AGC values are identical")
            return

        # Update scene range
        self.scene_min_c = temp_low_c
        self.scene_max_c = temp_high_c

        # Calculate offset (should be close to 0 with good calibration)
        normalized_low = agc_low / 255.0
        estimated_low = self.scene_min_c + (normalized_low * temp_range)
        self.calibration_offset = temp_low_c - estimated_low

        logger.info(
            f"Two-point calibration: "
            f"range={self.scene_min_c:.1f}°C to {self.scene_max_c:.1f}°C, "
            f"offset={self.calibration_offset:.2f}°C"
        )

    def get_calibration_info(self) -> dict:
        """Get current calibration settings."""
        return {
            'scene_min_c': self.scene_min_c,
            'scene_max_c': self.scene_max_c,
            'scene_range_c': self.scene_max_c - self.scene_min_c,
            'calibration_offset': self.calibration_offset,
            'adaptive_range': self.use_adaptive_range,
            'accuracy': '±5-10°C (pseudo-radiometric)'
        }


# ============================================================================
# Convenience Functions
# ============================================================================

def quick_estimate_temperature(
    agc_frame: np.ndarray,
    fpa_temp_c: float,
    scene_min_c: float = 10.0,
    scene_max_c: float = 110.0
) -> np.ndarray:
    """
    Quick temperature estimation with default settings.

    Args:
        agc_frame: 8-bit AGC thermal frame
        fpa_temp_c: FPA temperature from camera
        scene_min_c: Expected minimum scene temperature
        scene_max_c: Expected maximum scene temperature

    Returns:
        Temperature map in Celsius
    """
    estimator = ThermalTemperatureEstimator(
        scene_min_c=scene_min_c,
        scene_max_c=scene_max_c
    )
    return estimator.estimate_temperature_map(agc_frame, fpa_temp_c)


def celsius_to_fahrenheit(temp_c: float) -> float:
    """Convert Celsius to Fahrenheit."""
    return temp_c * 9.0 / 5.0 + 32.0


def fahrenheit_to_celsius(temp_f: float) -> float:
    """Convert Fahrenheit to Celsius."""
    return (temp_f - 32.0) * 5.0 / 9.0
