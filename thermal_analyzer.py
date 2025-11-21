"""
Thermal Analysis Engine for Inspection Applications
Provides comprehensive temperature analysis, hot/cold spot detection, anomaly detection, and trend tracking.
"""

import numpy as np
import cv2
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional, Any
from enum import Enum
from collections import deque
import time


class TemperatureUnit(Enum):
    """Temperature unit enumeration."""
    CELSIUS = "C"
    FAHRENHEIT = "F"
    KELVIN = "K"


class AnomalyType(Enum):
    """Types of thermal anomalies."""
    NONE = "none"
    HOT_SPOT = "hot_spot"
    COLD_SPOT = "cold_spot"
    RAPID_INCREASE = "rapid_increase"
    RAPID_DECREASE = "rapid_decrease"
    GRADIENT_ANOMALY = "gradient_anomaly"
    STATISTICAL_OUTLIER = "statistical_outlier"


@dataclass
class ThermalStatistics:
    """Statistical data for a thermal region."""
    min_temp: float
    max_temp: float
    mean_temp: float
    median_temp: float
    std_temp: float
    temp_range: float
    percentile_95: float
    percentile_5: float
    pixel_count: int
    timestamp: float = field(default_factory=time.time)


@dataclass
class HotSpot:
    """Detected hot spot information."""
    centroid: Tuple[int, int]
    bbox: Tuple[int, int, int, int]  # x, y, w, h
    max_temp: float
    mean_temp: float
    area: int
    confidence: float
    timestamp: float = field(default_factory=time.time)


@dataclass
class ColdSpot:
    """Detected cold spot information."""
    centroid: Tuple[int, int]
    bbox: Tuple[int, int, int, int]  # x, y, w, h
    min_temp: float
    mean_temp: float
    area: int
    confidence: float
    timestamp: float = field(default_factory=time.time)


@dataclass
class ThermalAnomaly:
    """Detected thermal anomaly."""
    anomaly_type: AnomalyType
    location: Tuple[int, int]
    severity: float  # 0.0 to 1.0
    description: str
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TemperatureTrend:
    """Temperature trend data for a region."""
    roi_id: str
    timestamps: List[float]
    temperatures: List[float]
    trend_direction: str  # "increasing", "decreasing", "stable"
    rate_of_change: float  # degrees per second
    prediction: Optional[float] = None


class ThermalAnalyzer:
    """
    Comprehensive thermal analysis engine for inspection applications.

    Capabilities:
    - Absolute temperature measurement (from radiometric data)
    - Relative temperature analysis
    - Hot spot detection and tracking
    - Cold spot detection and tracking
    - Temperature gradient analysis
    - Thermal anomaly detection
    - Temperature trend tracking
    """

    def __init__(self, config: Optional[Dict] = None):
        """
        Initialize the thermal analyzer.

        Args:
            config: Configuration dictionary with analyzer settings
        """
        self.config = config or {}

        # Temperature settings
        self.temp_unit = TemperatureUnit(
            self.config.get("temperature_unit", "C")
        )

        # Hot spot detection settings
        self.hot_spot_threshold = self.config.get("hot_spot_threshold", 0.8)  # 80th percentile
        self.hot_spot_min_area = self.config.get("hot_spot_min_area", 100)  # pixels

        # Cold spot detection settings
        self.cold_spot_threshold = self.config.get("cold_spot_threshold", 0.2)  # 20th percentile
        self.cold_spot_min_area = self.config.get("cold_spot_min_area", 100)  # pixels

        # Anomaly detection settings
        self.anomaly_sensitivity = self.config.get("anomaly_sensitivity", 0.7)
        self.rapid_change_threshold = self.config.get("rapid_change_threshold", 5.0)  # degrees/sec
        self.gradient_threshold = self.config.get("gradient_threshold", 10.0)  # degrees over distance

        # Trend tracking settings
        self.trend_window_size = self.config.get("trend_window_size", 60)  # seconds
        self.trend_sample_rate = self.config.get("trend_sample_rate", 1.0)  # seconds

        # Internal state
        self.trend_data: Dict[str, deque] = {}  # roi_id -> deque of (timestamp, temp)
        self.last_frame_stats: Dict[str, ThermalStatistics] = {}
        self.calibration_offset = self.config.get("calibration_offset", 0.0)
        self.calibration_scale = self.config.get("calibration_scale", 1.0)

    def analyze_frame(self, thermal_frame: np.ndarray,
                     roi_mask: Optional[np.ndarray] = None) -> ThermalStatistics:
        """
        Analyze a thermal frame and return comprehensive statistics.

        Args:
            thermal_frame: Thermal image (grayscale, 8-bit or 16-bit)
            roi_mask: Optional mask to analyze specific region (same size as thermal_frame)

        Returns:
            ThermalStatistics object with all computed metrics
        """
        if thermal_frame is None or thermal_frame.size == 0:
            return None

        # Apply ROI mask if provided
        if roi_mask is not None:
            masked_frame = cv2.bitwise_and(thermal_frame, thermal_frame, mask=roi_mask)
            pixels = masked_frame[roi_mask > 0]
        else:
            pixels = thermal_frame.flatten()

        if pixels.size == 0:
            return None

        # Convert to float for accurate statistics
        pixels = pixels.astype(np.float32)

        # Apply calibration if using radiometric data
        if self.calibration_scale != 1.0 or self.calibration_offset != 0.0:
            pixels = pixels * self.calibration_scale + self.calibration_offset

        # Compute statistics
        stats = ThermalStatistics(
            min_temp=float(np.min(pixels)),
            max_temp=float(np.max(pixels)),
            mean_temp=float(np.mean(pixels)),
            median_temp=float(np.median(pixels)),
            std_temp=float(np.std(pixels)),
            temp_range=float(np.max(pixels) - np.min(pixels)),
            percentile_95=float(np.percentile(pixels, 95)),
            percentile_5=float(np.percentile(pixels, 5)),
            pixel_count=int(pixels.size)
        )

        return stats

    def detect_hot_spots(self, thermal_frame: np.ndarray,
                        absolute_threshold: Optional[float] = None) -> List[HotSpot]:
        """
        Detect hot spots in thermal frame.

        Args:
            thermal_frame: Thermal image (grayscale)
            absolute_threshold: Optional absolute temperature threshold (overrides percentile)

        Returns:
            List of detected HotSpot objects
        """
        if thermal_frame is None or thermal_frame.size == 0:
            return []

        # Determine threshold
        if absolute_threshold is not None:
            threshold_value = absolute_threshold
        else:
            # Use percentile-based threshold
            threshold_value = np.percentile(thermal_frame, self.hot_spot_threshold * 100)

        # Create binary mask of hot regions
        hot_mask = (thermal_frame >= threshold_value).astype(np.uint8) * 255

        # Find contours
        contours, _ = cv2.findContours(hot_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        hot_spots = []
        for contour in contours:
            area = cv2.contourArea(contour)
            if area < self.hot_spot_min_area:
                continue

            # Get bounding box
            x, y, w, h = cv2.boundingRect(contour)

            # Get moments for centroid
            M = cv2.moments(contour)
            if M["m00"] == 0:
                continue
            cx = int(M["m10"] / M["m00"])
            cy = int(M["m01"] / M["m00"])

            # Extract region statistics
            roi = thermal_frame[y:y+h, x:x+w]
            max_temp = float(np.max(roi))
            mean_temp = float(np.mean(roi))

            # Calculate confidence based on how much hotter than threshold
            confidence = min(1.0, (max_temp - threshold_value) / (threshold_value * 0.5))

            hot_spot = HotSpot(
                centroid=(cx, cy),
                bbox=(x, y, w, h),
                max_temp=max_temp,
                mean_temp=mean_temp,
                area=int(area),
                confidence=float(confidence)
            )
            hot_spots.append(hot_spot)

        # Sort by max temperature (hottest first)
        hot_spots.sort(key=lambda x: x.max_temp, reverse=True)

        return hot_spots

    def detect_cold_spots(self, thermal_frame: np.ndarray,
                         absolute_threshold: Optional[float] = None) -> List[ColdSpot]:
        """
        Detect cold spots in thermal frame.

        Args:
            thermal_frame: Thermal image (grayscale)
            absolute_threshold: Optional absolute temperature threshold (overrides percentile)

        Returns:
            List of detected ColdSpot objects
        """
        if thermal_frame is None or thermal_frame.size == 0:
            return []

        # Determine threshold
        if absolute_threshold is not None:
            threshold_value = absolute_threshold
        else:
            # Use percentile-based threshold
            threshold_value = np.percentile(thermal_frame, self.cold_spot_threshold * 100)

        # Create binary mask of cold regions
        cold_mask = (thermal_frame <= threshold_value).astype(np.uint8) * 255

        # Find contours
        contours, _ = cv2.findContours(cold_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        cold_spots = []
        for contour in contours:
            area = cv2.contourArea(contour)
            if area < self.cold_spot_min_area:
                continue

            # Get bounding box
            x, y, w, h = cv2.boundingRect(contour)

            # Get moments for centroid
            M = cv2.moments(contour)
            if M["m00"] == 0:
                continue
            cx = int(M["m10"] / M["m00"])
            cy = int(M["m01"] / M["m00"])

            # Extract region statistics
            roi = thermal_frame[y:y+h, x:x+w]
            min_temp = float(np.min(roi))
            mean_temp = float(np.mean(roi))

            # Calculate confidence based on how much colder than threshold
            confidence = min(1.0, (threshold_value - min_temp) / (threshold_value * 0.5))

            cold_spot = ColdSpot(
                centroid=(cx, cy),
                bbox=(x, y, w, h),
                min_temp=min_temp,
                mean_temp=mean_temp,
                area=int(area),
                confidence=float(confidence)
            )
            cold_spots.append(cold_spot)

        # Sort by min temperature (coldest first)
        cold_spots.sort(key=lambda x: x.min_temp)

        return cold_spots

    def compute_temperature_gradient(self, thermal_frame: np.ndarray) -> np.ndarray:
        """
        Compute temperature gradient magnitude.

        Args:
            thermal_frame: Thermal image (grayscale)

        Returns:
            Gradient magnitude image (same size as input)
        """
        if thermal_frame is None or thermal_frame.size == 0:
            return None

        # Convert to float for gradient computation
        thermal_float = thermal_frame.astype(np.float32)

        # Compute gradients using Sobel operators
        grad_x = cv2.Sobel(thermal_float, cv2.CV_32F, 1, 0, ksize=3)
        grad_y = cv2.Sobel(thermal_float, cv2.CV_32F, 0, 1, ksize=3)

        # Compute magnitude
        gradient_magnitude = np.sqrt(grad_x**2 + grad_y**2)

        return gradient_magnitude

    def detect_anomalies(self, thermal_frame: np.ndarray,
                        roi_id: str = "global") -> List[ThermalAnomaly]:
        """
        Detect thermal anomalies in the frame.

        Args:
            thermal_frame: Thermal image (grayscale)
            roi_id: Region ID for trend tracking

        Returns:
            List of detected ThermalAnomaly objects
        """
        anomalies = []

        if thermal_frame is None or thermal_frame.size == 0:
            return anomalies

        current_stats = self.analyze_frame(thermal_frame)
        if current_stats is None:
            return anomalies

        # Check for statistical outliers (compared to previous frame)
        if roi_id in self.last_frame_stats:
            prev_stats = self.last_frame_stats[roi_id]

            # Rapid temperature increase
            temp_change = current_stats.mean_temp - prev_stats.mean_temp
            time_delta = current_stats.timestamp - prev_stats.timestamp
            if time_delta > 0:
                rate_of_change = temp_change / time_delta

                if rate_of_change > self.rapid_change_threshold:
                    anomalies.append(ThermalAnomaly(
                        anomaly_type=AnomalyType.RAPID_INCREASE,
                        location=(thermal_frame.shape[1]//2, thermal_frame.shape[0]//2),
                        severity=min(1.0, rate_of_change / (self.rapid_change_threshold * 2)),
                        description=f"Rapid temperature increase: {rate_of_change:.1f}°/s",
                        metadata={"rate": rate_of_change}
                    ))

                elif rate_of_change < -self.rapid_change_threshold:
                    anomalies.append(ThermalAnomaly(
                        anomaly_type=AnomalyType.RAPID_DECREASE,
                        location=(thermal_frame.shape[1]//2, thermal_frame.shape[0]//2),
                        severity=min(1.0, abs(rate_of_change) / (self.rapid_change_threshold * 2)),
                        description=f"Rapid temperature decrease: {rate_of_change:.1f}°/s",
                        metadata={"rate": rate_of_change}
                    ))

        # Check for extreme gradient anomalies
        gradient = self.compute_temperature_gradient(thermal_frame)
        if gradient is not None:
            max_gradient = np.max(gradient)
            if max_gradient > self.gradient_threshold:
                # Find location of max gradient
                max_loc = np.unravel_index(np.argmax(gradient), gradient.shape)
                anomalies.append(ThermalAnomaly(
                    anomaly_type=AnomalyType.GRADIENT_ANOMALY,
                    location=(int(max_loc[1]), int(max_loc[0])),
                    severity=min(1.0, max_gradient / (self.gradient_threshold * 2)),
                    description=f"Extreme temperature gradient: {max_gradient:.1f}°",
                    metadata={"gradient": max_gradient}
                ))

        # Store current stats for next frame comparison
        self.last_frame_stats[roi_id] = current_stats

        return anomalies

    def update_trend(self, roi_id: str, temperature: float, timestamp: Optional[float] = None):
        """
        Update temperature trend data for a region.

        Args:
            roi_id: Region identifier
            temperature: Current temperature value
            timestamp: Optional timestamp (uses current time if None)
        """
        if timestamp is None:
            timestamp = time.time()

        # Initialize trend data for this ROI if needed
        if roi_id not in self.trend_data:
            self.trend_data[roi_id] = deque(maxlen=1000)  # Store up to 1000 samples

        # Add new data point
        self.trend_data[roi_id].append((timestamp, temperature))

        # Remove old data points outside the trend window
        cutoff_time = timestamp - self.trend_window_size
        while self.trend_data[roi_id] and self.trend_data[roi_id][0][0] < cutoff_time:
            self.trend_data[roi_id].popleft()

    def get_trend(self, roi_id: str) -> Optional[TemperatureTrend]:
        """
        Get temperature trend for a region.

        Args:
            roi_id: Region identifier

        Returns:
            TemperatureTrend object or None if insufficient data
        """
        if roi_id not in self.trend_data or len(self.trend_data[roi_id]) < 2:
            return None

        # Extract timestamps and temperatures
        data = list(self.trend_data[roi_id])
        timestamps = [t for t, _ in data]
        temperatures = [temp for _, temp in data]

        # Compute rate of change (linear regression slope)
        if len(data) >= 3:
            # Use simple linear regression
            n = len(timestamps)
            sum_t = sum(timestamps)
            sum_temp = sum(temperatures)
            sum_t_temp = sum(t * temp for t, temp in zip(timestamps, temperatures))
            sum_t_sq = sum(t**2 for t in timestamps)

            denominator = n * sum_t_sq - sum_t**2
            if denominator != 0:
                slope = (n * sum_t_temp - sum_t * sum_temp) / denominator
                rate_of_change = slope
            else:
                rate_of_change = 0.0
        else:
            # Simple difference
            rate_of_change = (temperatures[-1] - temperatures[0]) / (timestamps[-1] - timestamps[0])

        # Determine trend direction
        if abs(rate_of_change) < 0.1:  # Less than 0.1 degrees/second
            trend_direction = "stable"
        elif rate_of_change > 0:
            trend_direction = "increasing"
        else:
            trend_direction = "decreasing"

        # Simple prediction (extrapolate 10 seconds into future)
        prediction = temperatures[-1] + (rate_of_change * 10.0)

        return TemperatureTrend(
            roi_id=roi_id,
            timestamps=timestamps,
            temperatures=temperatures,
            trend_direction=trend_direction,
            rate_of_change=rate_of_change,
            prediction=prediction
        )

    def convert_temperature(self, temp: float,
                          from_unit: TemperatureUnit,
                          to_unit: TemperatureUnit) -> float:
        """
        Convert temperature between units.

        Args:
            temp: Temperature value
            from_unit: Source unit
            to_unit: Target unit

        Returns:
            Converted temperature
        """
        # Convert to Celsius first
        if from_unit == TemperatureUnit.CELSIUS:
            temp_c = temp
        elif from_unit == TemperatureUnit.FAHRENHEIT:
            temp_c = (temp - 32) * 5/9
        elif from_unit == TemperatureUnit.KELVIN:
            temp_c = temp - 273.15
        else:
            temp_c = temp

        # Convert from Celsius to target unit
        if to_unit == TemperatureUnit.CELSIUS:
            return temp_c
        elif to_unit == TemperatureUnit.FAHRENHEIT:
            return temp_c * 9/5 + 32
        elif to_unit == TemperatureUnit.KELVIN:
            return temp_c + 273.15
        else:
            return temp_c

    def set_calibration(self, offset: float, scale: float = 1.0):
        """
        Set calibration parameters for absolute temperature measurement.

        Args:
            offset: Temperature offset to add (in current temp unit)
            scale: Scale factor to multiply
        """
        self.calibration_offset = offset
        self.calibration_scale = scale

    def clear_trends(self, roi_id: Optional[str] = None):
        """
        Clear trend data.

        Args:
            roi_id: Specific ROI to clear, or None to clear all
        """
        if roi_id is None:
            self.trend_data.clear()
        elif roi_id in self.trend_data:
            del self.trend_data[roi_id]
