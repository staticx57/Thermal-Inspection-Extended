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
import logging

logger = logging.getLogger(__name__)


class TemperatureUnit(Enum):
    """Temperature unit enumeration."""
    CELSIUS = "C"
    FAHRENHEIT = "F"
    KELVIN = "K"
    RAW = "RAW"  # Y16 raw values (Kelvin × 100)


class AnomalyType(Enum):
    """Types of thermal anomalies."""
    NONE = "none"
    HOT_SPOT = "hot_spot"
    COLD_SPOT = "cold_spot"
    RAPID_INCREASE = "rapid_increase"
    RAPID_DECREASE = "rapid_decrease"
    GRADIENT_ANOMALY = "gradient_anomaly"
    STATISTICAL_OUTLIER = "statistical_outlier"


class ThresholdMode(Enum):
    """Manual threshold detection modes."""
    ABOVE = "above"  # Highlight values above threshold
    BELOW = "below"  # Highlight values below threshold
    BETWEEN = "between"  # Highlight values between min and max
    OUTSIDE = "outside"  # Highlight values outside min/max range


class ThresholdVisualization(Enum):
    """Visualization modes for threshold-based detection."""
    GRAYSCALE_NON_ANOMALY = "grayscale_non_anomaly"  # Normal areas grayscale, anomalies in color
    COLOR_NON_ANOMALY = "color_non_anomaly"  # Normal areas in color, anomalies highlighted
    BINARY_MASK = "binary_mask"  # Black/white binary visualization
    GRADIENT_OVERLAY = "gradient_overlay"  # Smooth gradient based on distance from threshold


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
    unit: str = "°C"
    relative_mean: Optional[float] = None
    timestamp: float = field(default_factory=time.time)


@dataclass
class HotSpot:
    """Detected hot spot information."""
    centroid: Tuple[int, int]
    bbox: Tuple[int, int, int, int]  # x1, y1, x2, y2 (for anomaly priority compatibility)
    max_temp: float
    mean_temp: float
    area: int
    confidence: float
    unit: str = "°C"
    raw_value: Optional[float] = None  # Raw pixel value (Y16: kelvin×100 for 16-bit)
    timestamp: float = field(default_factory=time.time)


@dataclass
class ColdSpot:
    """Detected cold spot information."""
    centroid: Tuple[int, int]
    bbox: Tuple[int, int, int, int]  # x1, y1, x2, y2 (for anomaly priority compatibility)
    min_temp: float
    mean_temp: float
    area: int
    confidence: float
    unit: str = "°C"
    raw_value: Optional[float] = None  # Raw pixel value (Y16: kelvin×100 for 16-bit)
    timestamp: float = field(default_factory=time.time)


@dataclass
class ThermalAnomaly:
    """Detected thermal anomaly."""
    anomaly_type: AnomalyType
    location: Tuple[int, int]
    bbox: Tuple[int, int, int, int] = (0, 0, 0, 0)  # x1, y1, x2, y2 (for anomaly priority compatibility)
    severity: float = 0.0  # 0.0 to 1.0
    description: str = ""
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


@dataclass
class ThresholdDetectionResult:
    """Results from manual threshold-based anomaly detection."""
    mask: np.ndarray  # Binary mask of detected anomalies
    anomaly_percentage: float  # Percentage of pixels flagged as anomalies
    anomaly_count: int  # Number of anomaly pixels
    total_pixels: int  # Total number of pixels analyzed
    threshold_mode: ThresholdMode
    min_threshold: float
    max_threshold: Optional[float] = None
    timestamp: float = field(default_factory=time.time)


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
        self.max_hot_spots = self.config.get("max_hot_spots", 3)  # Maximum number of hot spots to return

        # Cold spot detection settings
        self.cold_spot_threshold = self.config.get("cold_spot_threshold", 0.2)  # 20th percentile
        self.cold_spot_min_area = self.config.get("cold_spot_min_area", 100)  # pixels
        self.max_cold_spots = self.config.get("max_cold_spots", 3)  # Maximum number of cold spots to return

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
        
        # Background modeling for anomaly detection
        self.background_model: Optional[np.ndarray] = None
        self.background_alpha = self.config.get("background_alpha", 0.01)  # Learning rate
        self.background_init_frames = 30
        self.frame_count = 0
        
        # Radiometric mode
        self.is_radiometric = self.config.get("radiometric", False)
        if not self.is_radiometric:
            self.temp_unit = TemperatureUnit.CELSIUS # Placeholder, will be treated as Raw
            
        # Baseline for relative measurements
        self.baseline_value: Optional[float] = None

    def set_baseline(self, value: float):
        """Set baseline value for relative measurements."""
        self.baseline_value = value

    def set_radiometric_mode(self, enabled: bool):
        """
        Enable or disable radiometric mode.
        
        Args:
            enabled: True for radiometric (temperature), False for raw (AGC)
        """
        self.is_radiometric = enabled
        # Update unit based on mode
        if not self.is_radiometric:
            # If not radiometric, we can't display temperature units
            # We'll stick to the configured unit preference but output will be raw
            pass

    def set_temperature_unit(self, unit: str):
        """
        Set temperature unit preference.

        Args:
            unit: 'C', 'F', 'K', or 'RAW'
        """
        try:
            # Map string to enum
            unit_map = {
                'C': TemperatureUnit.CELSIUS,
                'F': TemperatureUnit.FAHRENHEIT,
                'K': TemperatureUnit.KELVIN,
                'RAW': TemperatureUnit.RAW
            }
            if unit in unit_map:
                self.temp_unit = unit_map[unit]
                logger.info(f"[THERMAL_ANALYZER] Temperature unit set to: {unit}")
        except Exception as e:
            logger.error(f"[THERMAL_ANALYZER] Error setting temperature unit: {e}")

    def _get_unit_symbol(self) -> str:
        """Get the unit symbol string for the current temperature unit."""
        if self.temp_unit == TemperatureUnit.FAHRENHEIT:
            return "°F"
        elif self.temp_unit == TemperatureUnit.KELVIN:
            return "K"
        elif self.temp_unit == TemperatureUnit.RAW:
            return " (Y16)"
        else:
            return "°C"

    def analyze(self, thermal_frame: np.ndarray) -> Dict[str, Any]:
        """
        Convenience wrapper to run all standard analysis methods.
        
        Args:
            thermal_frame: Grayscale thermal frame (8-bit or 16-bit)
            
        Returns:
            Dict containing stats, hot_spots, cold_spots, anomalies, etc.
        """
        stats = self.compute_statistics(thermal_frame)
        hot_spots = self.detect_hot_spots(thermal_frame)
        cold_spots = self.detect_cold_spots(thermal_frame)
        anomalies = self.detect_anomalies(thermal_frame)
        
        # For histogram: convert to float temperature array
        temp_array = None
        if thermal_frame is not None:
            if thermal_frame.dtype == np.uint16:
                # Y16 format: Kelvin * 100 -> Celsius
                temp_array = (thermal_frame.astype(np.float32) / 100.0) - 273.15
            else:
                # 8-bit frame: use raw values (0-255 range)
                temp_array = thermal_frame.astype(np.float32)
        
        return {
            'stats': stats,
            'hot_spots': hot_spots,
            'cold_spots': cold_spots,
            'anomalies': anomalies,
            'motion_detections': [], # Filled by ThermalProcessor
            'edge_clusters': [],     # Filled by ThermalProcessor
            'trend': None,           # Placeholder
            'temp_array': temp_array, # For histogram
            'is_radiometric': self.is_radiometric  # For histogram unit display
        }

    def _y16_to_celsius(self, value: float) -> float:
        """
        Convert Y16 radiometric value to Celsius.

        Y16 format: pixel_value = Kelvin × 100

        Args:
            value: Y16 pixel value

        Returns:
            Temperature in Celsius
        """
        return (value / 100.0) - 273.15

    def reset_background_model(self):
        """Reset background model and frame count (call when frame size changes)."""
        self.background_model = None
        self.frame_count = 0

    def get_baseline(self) -> Optional[float]:
        """Get current baseline value."""
        return self.baseline_value

    def calculate_spot_temperature(self, raw_val: float, converter=None, force_estimation: bool = False) -> Tuple[float, str]:
        """
        Calculate temperature and unit string for a single spot.
        
        Args:
            raw_val: Raw pixel value
            converter: Optional radiometric converter (pixel_to_temperature)
            force_estimation: If True, force estimation mode even if radiometric
            
        Returns:
            (temperature_value, unit_string)
        """
        temp = 0.0
        unit = ''
        
        # Decide mode based on capabilities
        # Decide mode based on capabilities
        if self.is_radiometric and not force_estimation:
            # === STATE 1: 16-BIT RADIOMETRIC (REAL DATA) ===
            # Get base temperature in Celsius
            try:
                if converter:
                    temp_c = converter.pixel_to_temperature(raw_val)
                else:
                    # Fallback to standard Y16 (used by hot/cold spots)
                    temp_c = self._y16_to_celsius(raw_val)
            except Exception:
                # Fallback if calculation fails (rare)
                # Just treat as raw counts scaled down slightly to avoid massive numbers
                temp_c = (float(raw_val) - 0) * 0.1
                
            # Apply target unit conversion
            temp = self.convert_temperature(temp_c, TemperatureUnit.CELSIUS, self.temp_unit)
            unit = self._get_unit_symbol()
                
        elif force_estimation:
            # === STATE 2: 8-BIT ESTIMATION (APPROXIMATE) ===
            # This state is ONLY entered if explicitly forced (e.g. by 8-bit estimation toggle)
            
            # Simple linear mapping (fallback)
            temp_c = (float(raw_val) - 0) * 0.1
            
            # Apply conversion
            temp = self.convert_temperature(temp_c, TemperatureUnit.CELSIUS, self.temp_unit)
            
            # Add (est) suffix
            symbol = self._get_unit_symbol()
            unit = f"{symbol} (est)"

        else:
            # === STATE 3: AGC / RAW (NO RADIOMETRY) ===
            # Just show the raw pixel value
            temp = float(raw_val)
            unit = ' (AGC)'
            
        return temp, unit

    def convert_temperature(self, value: float, from_unit: TemperatureUnit, to_unit: TemperatureUnit) -> float:
        """Helper to convert temperature between units."""
        if from_unit == to_unit:
            return value
            
        # First convert to Celsius
        celsius = value
        if from_unit == TemperatureUnit.FAHRENHEIT:
            celsius = (value - 32) * 5/9
        elif from_unit == TemperatureUnit.KELVIN:
            celsius = value - 273.15
        elif from_unit == TemperatureUnit.RAW:
             # Y16 to Celsius
             celsius = (value / 100.0) - 273.15

        # Then convert to target
        if to_unit == TemperatureUnit.CELSIUS:
            return celsius
        elif to_unit == TemperatureUnit.FAHRENHEIT:
            return (celsius * 9/5) + 32
        elif to_unit == TemperatureUnit.KELVIN:
            return celsius + 273.15
        elif to_unit == TemperatureUnit.RAW:
            # Celsius to Y16
            return (celsius + 273.15) * 100.0
            
        return celsius


    def compute_statistics(self, thermal_frame: np.ndarray,
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

        # Compute raw statistics first
        min_raw = float(np.min(pixels))
        max_raw = float(np.max(pixels))
        mean_raw = float(np.mean(pixels))
        median_raw = float(np.median(pixels))
        std_raw = float(np.std(pixels))
        p95_raw = float(np.percentile(pixels, 95))
        p5_raw = float(np.percentile(pixels, 5))

        # Convert to Celsius if radiometric (Y16 format: value = Kelvin × 100)
        if self.is_radiometric:
            min_val = self._y16_to_celsius(min_raw)
            max_val = self._y16_to_celsius(max_raw)
            mean_val = self._y16_to_celsius(mean_raw)
            median_val = self._y16_to_celsius(median_raw)
            # Std dev doesn't need offset adjustment, just scale
            std_val = std_raw / 100.0
            p95_val = self._y16_to_celsius(p95_raw)
            p5_val = self._y16_to_celsius(p5_raw)
            temp_range = max_val - min_val
        else:
            min_val = min_raw
            max_val = max_raw
            mean_val = mean_raw
            median_val = median_raw
            std_val = std_raw
            p95_val = p95_raw
            p5_val = p5_raw
            temp_range = max_raw - min_raw

        relative_mean = None
        if self.baseline_value is not None:
            relative_mean = mean_val - self.baseline_value

        # Convert to target unit
        min_val = self.convert_temperature(min_val, TemperatureUnit.CELSIUS, self.temp_unit)
        max_val = self.convert_temperature(max_val, TemperatureUnit.CELSIUS, self.temp_unit)
        mean_val = self.convert_temperature(mean_val, TemperatureUnit.CELSIUS, self.temp_unit)
        median_val = self.convert_temperature(median_val, TemperatureUnit.CELSIUS, self.temp_unit)
        p95_val = self.convert_temperature(p95_val, TemperatureUnit.CELSIUS, self.temp_unit)
        p5_val = self.convert_temperature(p5_val, TemperatureUnit.CELSIUS, self.temp_unit)
        
        # Scale relative values (std dev, range)
        # Note: These are differences, so we only apply scaling factor, not offset
        if self.temp_unit == TemperatureUnit.FAHRENHEIT:
            std_val = std_val * 1.8
            temp_range = temp_range * 1.8
            if relative_mean is not None:
                relative_mean = relative_mean * 1.8
        elif self.temp_unit == TemperatureUnit.RAW:
            # RAW is Y16 (Kelvin × 100), so scale by 100
            std_val = std_val * 100
            temp_range = temp_range * 100
            if relative_mean is not None:
                relative_mean = relative_mean * 100

        unit_symbol = self._get_unit_symbol()

        stats = ThermalStatistics(
            min_temp=min_val,
            max_temp=max_val,
            mean_temp=mean_val,
            median_temp=median_val,
            std_temp=std_val,
            temp_range=temp_range,
            percentile_95=p95_val,
            percentile_5=p5_val,
            pixel_count=int(pixels.size),
            unit=unit_symbol if self.is_radiometric else " (raw)",
            relative_mean=relative_mean
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

        # Ensure grayscale input
        if len(thermal_frame.shape) == 3:
            thermal_frame = cv2.cvtColor(thermal_frame, cv2.COLOR_BGR2GRAY)

        # PERFORMANCE OPTIMIZATION: Use simple percentile thresholding instead of adaptive
        # Adaptive threshold is VERY slow (~30-50ms), simple threshold is <1ms
        if absolute_threshold is not None:
            threshold_value = absolute_threshold
        else:
            threshold_value = np.percentile(thermal_frame, self.hot_spot_threshold * 100)

        # Create binary mask - simple and fast
        hot_mask = (thermal_frame >= threshold_value).astype(np.uint8) * 255

        # Optimization: Morphological opening to remove small noise before contour finding
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        hot_mask = cv2.morphologyEx(hot_mask, cv2.MORPH_OPEN, kernel)

        # Find contours with SIMPLE approximation for speed
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
            max_raw = float(np.max(roi))
            mean_raw = float(np.mean(roi))

            # Calculate confidence based on how much hotter than threshold (in raw units)
            confidence = min(1.0, (max_raw - threshold_value) / (threshold_value * 0.5))

            # Convert to Celsius if radiometric (Y16 format: value = Kelvin × 100)
            if self.is_radiometric:
                max_temp = self._y16_to_celsius(max_raw)
                mean_temp = self._y16_to_celsius(mean_raw)
            else:
                max_temp = max_raw
                mean_temp = mean_raw

            # Convert to target unit
            if self.is_radiometric:
                max_temp = self.convert_temperature(max_temp, TemperatureUnit.CELSIUS, self.temp_unit)
                mean_temp = self.convert_temperature(mean_temp, TemperatureUnit.CELSIUS, self.temp_unit)

            unit_symbol = self._get_unit_symbol()

            hot_spot = HotSpot(
                centroid=(cx, cy),
                bbox=(x, y, x+w, y+h),  # Convert to x1,y1,x2,y2 format
                max_temp=max_temp,
                mean_temp=mean_temp,
                area=int(area),
                confidence=confidence,
                unit=unit_symbol if self.is_radiometric else " (raw)",
                raw_value=max_raw  # Store raw Y16 value (kelvin×100)
            )
            hot_spots.append(hot_spot)

        # Sort by max temperature (hottest first)
        hot_spots.sort(key=lambda x: x.max_temp, reverse=True)

        # Limit to max_hot_spots (0 means no limit)
        if self.max_hot_spots > 0 and len(hot_spots) > self.max_hot_spots:
            hot_spots = hot_spots[:self.max_hot_spots]

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

        # Ensure grayscale input
        if len(thermal_frame.shape) == 3:
            thermal_frame = cv2.cvtColor(thermal_frame, cv2.COLOR_BGR2GRAY)

        # PERFORMANCE OPTIMIZATION: Use simple percentile thresholding instead of adaptive
        # Adaptive threshold is VERY slow (~30-50ms), simple threshold is <1ms
        if absolute_threshold is not None:
            threshold_value = absolute_threshold
        else:
            threshold_value = np.percentile(thermal_frame, self.cold_spot_threshold * 100)

        # Create binary mask - simple and fast
        cold_mask = (thermal_frame <= threshold_value).astype(np.uint8) * 255

        # Morphological opening
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        cold_mask = cv2.morphologyEx(cold_mask, cv2.MORPH_OPEN, kernel)

        # Find contours with SIMPLE approximation for speed
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
            min_raw = float(np.min(roi))
            mean_raw = float(np.mean(roi))

            # Calculate confidence based on how much colder than threshold (in raw units)
            confidence = min(1.0, (threshold_value - min_raw) / (threshold_value * 0.5))

            # Convert to Celsius if radiometric (Y16 format: value = Kelvin × 100)
            if self.is_radiometric:
                min_temp = self._y16_to_celsius(min_raw)
                mean_temp = self._y16_to_celsius(mean_raw)
            else:
                min_temp = min_raw
                mean_temp = mean_raw

            # Convert to target unit
            if self.is_radiometric:
                min_temp = self.convert_temperature(min_temp, TemperatureUnit.CELSIUS, self.temp_unit)
                mean_temp = self.convert_temperature(mean_temp, TemperatureUnit.CELSIUS, self.temp_unit)

            unit_symbol = self._get_unit_symbol()

            cold_spot = ColdSpot(
                centroid=(cx, cy),
                bbox=(x, y, x+w, y+h),  # Convert to x1,y1,x2,y2 format
                min_temp=min_temp,
                mean_temp=mean_temp,
                area=int(area),
                confidence=float(confidence),
                unit=unit_symbol if self.is_radiometric else " (raw)",
                raw_value=min_raw  # Store raw Y16 value (kelvin×100)
            )
            cold_spots.append(cold_spot)

        # Sort by min temperature (coldest first)
        cold_spots.sort(key=lambda x: x.min_temp)

        # Limit to max_cold_spots (0 means no limit)
        if self.max_cold_spots > 0 and len(cold_spots) > self.max_cold_spots:
            cold_spots = cold_spots[:self.max_cold_spots]

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

        current_stats = self.compute_statistics(thermal_frame)
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
                    # Whole frame anomaly - use full frame bbox
                    h, w = thermal_frame.shape[:2]
                    anomalies.append(ThermalAnomaly(
                        anomaly_type=AnomalyType.RAPID_INCREASE,
                        location=(w//2, h//2),
                        bbox=(0, 0, w, h),
                        severity=min(1.0, rate_of_change / (self.rapid_change_threshold * 2)),
                        description=f"Rapid temperature increase: {rate_of_change:.1f}°/s",
                        metadata={"rate": rate_of_change}
                    ))

                elif rate_of_change < -self.rapid_change_threshold:
                    # Whole frame anomaly - use full frame bbox
                    h, w = thermal_frame.shape[:2]
                    anomalies.append(ThermalAnomaly(
                        anomaly_type=AnomalyType.RAPID_DECREASE,
                        location=(w//2, h//2),
                        bbox=(0, 0, w, h),
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
                # Create a small bbox around the gradient point (20x20 px)
                cx, cy = int(max_loc[1]), int(max_loc[0])
                bbox_size = 20
                x1 = max(0, cx - bbox_size//2)
                y1 = max(0, cy - bbox_size//2)
                x2 = min(thermal_frame.shape[1], cx + bbox_size//2)
                y2 = min(thermal_frame.shape[0], cy + bbox_size//2)
                anomalies.append(ThermalAnomaly(
                    anomaly_type=AnomalyType.GRADIENT_ANOMALY,
                    location=(cx, cy),
                    bbox=(x1, y1, x2, y2),
                    severity=min(1.0, max_gradient / (self.gradient_threshold * 2)),
                    description=f"Extreme temperature gradient: {max_gradient:.1f}°",
                    metadata={"gradient": max_gradient}
                ))

        # Store current stats for next frame comparison
        self.last_frame_stats[roi_id] = current_stats

        # --- Statistical Background Modeling ---
        # Only update background if we have a valid frame
        if thermal_frame is not None:
            thermal_float = thermal_frame.astype(np.float32)
            
            if self.background_model is None or self.background_model.shape != thermal_float.shape:
                self.background_model = thermal_float.copy()
                self.frame_count = 0  # Reset initialization counter on size change
            else:
                # Update background model (running average)
                cv2.accumulateWeighted(thermal_float, self.background_model, self.background_alpha)

            self.frame_count += 1

            # Only detect after initialization period
            if self.frame_count > self.background_init_frames:
                # Calculate absolute difference
                diff = cv2.absdiff(thermal_float, self.background_model)
                
                # Calculate dynamic threshold (mean diff + 3 std devs)
                mean_diff = np.mean(diff)
                std_diff = np.std(diff)
                threshold = mean_diff + (3.0 * std_diff)
                
                # Find outliers
                outlier_mask = (diff > threshold).astype(np.uint8) * 255
                
                # Filter noise
                kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
                outlier_mask = cv2.morphologyEx(outlier_mask, cv2.MORPH_OPEN, kernel)
                
                # Find contours of anomalies
                contours, _ = cv2.findContours(outlier_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                
                for contour in contours:
                    area = cv2.contourArea(contour)
                    if area < 100:  # Minimum anomaly size
                        continue
                        
                    # Get bounding box and centroid
                    x, y, w, h = cv2.boundingRect(contour)
                    M = cv2.moments(contour)
                    if M["m00"] != 0:
                        cx = int(M["m10"] / M["m00"])
                        cy = int(M["m01"] / M["m00"])
                    else:
                        cx, cy = x + w//2, y + h//2
                        
                    # Calculate severity based on max difference in region
                    roi_diff = diff[y:y+h, x:x+w]
                    max_diff = np.max(roi_diff)
                    severity = min(1.0, max_diff / (threshold * 2))
                    
                    anomalies.append(ThermalAnomaly(
                        anomaly_type=AnomalyType.STATISTICAL_OUTLIER,
                        location=(cx, cy),
                        bbox=(x, y, x+w, y+h),  # Use contour bounding box
                        severity=severity,
                        description=f"Statistical outlier (diff: {max_diff:.1f})",
                        metadata={"max_diff": float(max_diff), "threshold": float(threshold)}
                    ))

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
        # RAW mode: return Y16 value (Kelvin × 100) without conversion
        if to_unit == TemperatureUnit.RAW:
            # Convert from Celsius to Y16 (Kelvin × 100)
            if from_unit == TemperatureUnit.CELSIUS:
                return (temp + 273.15) * 100
            elif from_unit == TemperatureUnit.FAHRENHEIT:
                temp_c = (temp - 32) * 5/9
                return (temp_c + 273.15) * 100
            elif from_unit == TemperatureUnit.KELVIN:
                return temp * 100
            else:
                return temp  # Already raw

        # Convert to Celsius first
        if from_unit == TemperatureUnit.CELSIUS:
            temp_c = temp
        elif from_unit == TemperatureUnit.FAHRENHEIT:
            temp_c = (temp - 32) * 5/9
        elif from_unit == TemperatureUnit.KELVIN:
            temp_c = temp - 273.15
        elif from_unit == TemperatureUnit.RAW:
            # RAW is Y16 (Kelvin × 100), convert to Celsius
            temp_c = (temp / 100) - 273.15
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

    # ========================================================================
    # Manual Threshold Detection
    # ========================================================================

    def detect_threshold_anomalies(
        self,
        thermal_frame: np.ndarray,
        threshold_mode: ThresholdMode,
        min_threshold: float,
        max_threshold: Optional[float] = None,
        use_raw_values: bool = True
    ) -> ThresholdDetectionResult:
        """
        Detect anomalies based on user-defined thresholds.

        Args:
            thermal_frame: Thermal image (14-bit raw or temperature values)
            threshold_mode: Detection mode (ABOVE, BELOW, BETWEEN, OUTSIDE)
            min_threshold: Minimum threshold value (percentage 0-100 if use_raw_values=False)
            max_threshold: Maximum threshold value (percentage 0-100 if use_raw_values=False)
            use_raw_values: If True, thresholds are raw 14-bit values; if False, percentage values (0-100)

        Returns:
            ThresholdDetectionResult with binary mask and statistics
        """
        if thermal_frame is None or thermal_frame.size == 0:
            # Return empty result
            empty_mask = np.zeros_like(thermal_frame, dtype=np.uint8)
            return ThresholdDetectionResult(
                mask=empty_mask,
                anomaly_percentage=0.0,
                anomaly_count=0,
                total_pixels=0,
                threshold_mode=threshold_mode,
                min_threshold=min_threshold,
                max_threshold=max_threshold
            )

        # Convert percentage to actual values if needed
        if not use_raw_values:
            frame_min = np.min(thermal_frame)
            frame_max = np.max(thermal_frame)
            frame_range = frame_max - frame_min

            # Convert percentage (0-100) to actual value
            min_threshold = frame_min + (min_threshold / 100.0) * frame_range
            if max_threshold is not None:
                max_threshold = frame_min + (max_threshold / 100.0) * frame_range

        # Apply threshold based on mode
        if threshold_mode == ThresholdMode.ABOVE:
            mask = (thermal_frame >= min_threshold).astype(np.uint8) * 255

        elif threshold_mode == ThresholdMode.BELOW:
            mask = (thermal_frame <= min_threshold).astype(np.uint8) * 255

        elif threshold_mode == ThresholdMode.BETWEEN:
            if max_threshold is None:
                max_threshold = min_threshold + 1000  # Default range
            mask = ((thermal_frame >= min_threshold) & (thermal_frame <= max_threshold)).astype(np.uint8) * 255

        elif threshold_mode == ThresholdMode.OUTSIDE:
            if max_threshold is None:
                max_threshold = min_threshold + 1000  # Default range
            mask = ((thermal_frame < min_threshold) | (thermal_frame > max_threshold)).astype(np.uint8) * 255

        else:
            mask = np.zeros_like(thermal_frame, dtype=np.uint8)

        # Calculate statistics
        total_pixels = thermal_frame.size
        anomaly_count = np.count_nonzero(mask)
        anomaly_percentage = (anomaly_count / total_pixels * 100.0) if total_pixels > 0 else 0.0

        return ThresholdDetectionResult(
            mask=mask,
            anomaly_percentage=anomaly_percentage,
            anomaly_count=anomaly_count,
            total_pixels=total_pixels,
            threshold_mode=threshold_mode,
            min_threshold=min_threshold,
            max_threshold=max_threshold
        )

    def apply_threshold_visualization(
        self,
        thermal_frame: np.ndarray,
        colorized_frame: np.ndarray,
        detection_result: ThresholdDetectionResult,
        viz_mode: ThresholdVisualization,
        anomaly_palette: Optional[np.ndarray] = None
    ) -> np.ndarray:
        """
        Apply threshold visualization to colorized thermal frame.

        Args:
            thermal_frame: Raw thermal frame
            colorized_frame: Colorized thermal frame (BGR)
            detection_result: Threshold detection result with mask
            viz_mode: Visualization mode
            anomaly_palette: Optional custom palette for anomaly regions

        Returns:
            Visualized frame with threshold highlighting
        """
        if thermal_frame is None or colorized_frame is None:
            return colorized_frame

        mask = detection_result.mask
        output = colorized_frame.copy()

        if viz_mode == ThresholdVisualization.GRAYSCALE_NON_ANOMALY:
            # Convert non-anomaly regions to grayscale
            gray = cv2.cvtColor(colorized_frame, cv2.COLOR_BGR2GRAY)
            gray_3ch = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)

            # Anomaly regions keep color, non-anomaly regions become grayscale
            output = np.where(mask[..., np.newaxis] > 0, colorized_frame, gray_3ch)

        elif viz_mode == ThresholdVisualization.COLOR_NON_ANOMALY:
            # Highlight anomaly regions with different processing
            # Apply brightness boost to anomaly regions
            anomaly_boost = colorized_frame.copy()
            anomaly_boost = cv2.convertScaleAbs(anomaly_boost, alpha=1.3, beta=30)

            output = np.where(mask[..., np.newaxis] > 0, anomaly_boost, colorized_frame)

        elif viz_mode == ThresholdVisualization.BINARY_MASK:
            # Pure black and white
            binary_3ch = cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR)
            output = binary_3ch

        elif viz_mode == ThresholdVisualization.GRADIENT_OVERLAY:
            # Distance-based gradient fade
            # Compute distance transform from anomaly edges
            mask_binary = (mask > 0).astype(np.uint8)
            dist_from_anomaly = cv2.distanceTransform(1 - mask_binary, cv2.DIST_L2, 5)
            dist_from_anomaly = np.clip(dist_from_anomaly / 50.0, 0, 1)  # Normalize to 0-1

            # Create gradient overlay
            gradient_alpha = (1 - dist_from_anomaly)[..., np.newaxis]
            overlay_color = np.array([0, 0, 255], dtype=np.uint8)  # Red overlay
            overlay = np.ones_like(colorized_frame) * overlay_color

            output = (colorized_frame * (1 - gradient_alpha * 0.5) + overlay * gradient_alpha * 0.5).astype(np.uint8)

        return output

    # ========================================================================
    # Enhanced Thermal+Edge Fusion Detection
    # ========================================================================

    def detect_enhanced_fusion_anomalies(
        self,
        thermal_frame: np.ndarray,
        edge_weight: float = 0.5,
        min_edge_strength: int = 50,
        thermal_deviation_multiplier: float = 1.5
    ) -> List[ThermalAnomaly]:
        """
        Detect anomalies using enhanced thermal+edge fusion.
        Combines temperature analysis with edge detection for intelligent anomaly detection.

        Args:
            thermal_frame: Thermal image (raw 14-bit or normalized)
            edge_weight: Balance between thermal (0.0) and edge (1.0) importance
            min_edge_strength: Minimum edge strength to consider
            thermal_deviation_multiplier: Multiplier for thermal statistical deviation

        Returns:
            List of ThermalAnomaly objects
        """
        if thermal_frame is None or thermal_frame.size == 0:
            return []

        anomalies = []

        # 1. Compute thermal statistics
        stats = self.compute_statistics(thermal_frame)
        thermal_threshold = stats.mean_temp + (stats.std_temp * thermal_deviation_multiplier)

        # 2. Normalize thermal frame for edge detection
        thermal_norm = cv2.normalize(thermal_frame.astype(np.float32), None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)

        # 3. Compute thermal gradient magnitude
        grad_x = cv2.Sobel(thermal_norm, cv2.CV_64F, 1, 0, ksize=3)
        grad_y = cv2.Sobel(thermal_norm, cv2.CV_64F, 0, 1, ksize=3)
        gradient_magnitude = np.sqrt(grad_x**2 + grad_y**2)
        gradient_magnitude = cv2.normalize(gradient_magnitude, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)

        # 4. Run Canny edge detection
        edges = cv2.Canny(thermal_norm, min_edge_strength, min_edge_strength * 2)

        # 5. Identify thermal anomalies (hot regions)
        thermal_anomaly_mask = (thermal_frame > thermal_threshold).astype(np.uint8) * 255

        # 6. Combine thermal anomalies with edge information
        # Weight: edge_weight controls balance between thermal and edges
        thermal_component = thermal_anomaly_mask * (1 - edge_weight)
        edge_component = gradient_magnitude * edge_weight
        combined_score = (thermal_component + edge_component).astype(np.uint8)

        # 7. Threshold combined score
        _, combined_mask = cv2.threshold(combined_score, 100, 255, cv2.THRESH_BINARY)

        # 8. Find contours in combined mask
        contours, _ = cv2.findContours(combined_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        # 9. Filter and create anomaly objects
        for contour in contours:
            area = cv2.contourArea(contour)
            if area < 400:  # Min size filter
                continue

            # Get bounding box
            x, y, w, h = cv2.boundingRect(contour)
            bbox = (x, y, x + w, y + h)

            # Calculate centroid
            M = cv2.moments(contour)
            if M['m00'] > 0:
                cx = int(M['m10'] / M['m00'])
                cy = int(M['m01'] / M['m00'])
            else:
                cx, cy = x + w//2, y + h//2

            # Calculate severity (based on both thermal and edge strength)
            roi_thermal = thermal_frame[y:y+h, x:x+w]
            roi_edges = edges[y:y+h, x:x+w]

            thermal_score = (np.mean(roi_thermal) - stats.mean_temp) / (stats.std_temp + 1e-6)
            edge_score = np.mean(roi_edges) / 255.0

            severity = (thermal_score * (1 - edge_weight) + edge_score * edge_weight)
            severity = np.clip(severity, 0.0, 1.0)

            anomaly = ThermalAnomaly(
                anomaly_type=AnomalyType.GRADIENT_ANOMALY,
                location=(cx, cy),
                bbox=bbox,
                severity=severity,
                description=f"Thermal+Edge fusion anomaly (thermal:{thermal_score:.2f}, edge:{edge_score:.2f})",
                metadata={
                    'area': area,
                    'thermal_score': thermal_score,
                    'edge_score': edge_score,
                    'edge_weight': edge_weight
                }
            )
            anomalies.append(anomaly)

        return anomalies

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
