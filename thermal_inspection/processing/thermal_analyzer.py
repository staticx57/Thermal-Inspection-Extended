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

        # 8-bit estimation (non-radiometric cameras only) - set externally
        # by app.py once a ThermalTemperatureEstimator exists and the user
        # opts in. Without this, hot/cold-spot stats have no way to know
        # estimation exists at all and always fall back to raw AGC values.
        self.thermal_estimator = None
        self.estimation_enabled = False
        self.last_fpa_temp_c: Optional[float] = None
        self._est_map_cache_key: Optional[int] = None
        self._est_map_cache: Optional[np.ndarray] = None

        # Which anomaly-panel types are enabled - set externally by app.py
        # (mirrors AnomalyWidget's own checkboxes). Only consulted for
        # "enhanced_fusion" (see analyze()): hot_spots/cold_spots/
        # thermal_anomalies are always computed regardless of their own
        # checkbox state (existing behavior, unchanged) since they're
        # cheap; enhanced_fusion's Sobel+Canny+contour pipeline is
        # meaningfully more expensive and defaults OFF in the UI, so it's
        # not worth running every frame unless actually enabled.
        self.enabled_anomaly_types: Dict[str, bool] = {}

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

        # Motion guard: skip background model update when camera is panning
        # Threshold is in raw pixel units (default 15 = significant scene change)
        self._motion_guard_threshold = self.config.get("motion_guard_threshold", 15.0)

        # Grid-based rate-of-change: 8x8 grid tracks per-cell temperature history
        # so localised hotspots are not diluted by the global mean
        self._grid_size = self.config.get("grid_size", 8)
        self._grid_history: Optional[np.ndarray] = None   # (grid_h, grid_w) float32
        self._grid_last_time: Optional[float] = None
        # If more than this fraction of grid cells cross rapid_change_threshold
        # in the same tick, treat it as one whole-frame shift (AGC, panning)
        # rather than that many independent localised anomalies.
        self._grid_uniform_shift_fraction = self.config.get("grid_uniform_shift_fraction", 0.5)

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
        # detect_hot_spots/detect_cold_spots each convert a 3-channel frame
        # to grayscale internally, producing a fresh array each time. Doing
        # it once here means every downstream call shares the same array
        # object, so _estimated_map()'s identity-based cache actually hits
        # instead of recomputing the estimator's adaptive-range scan per call.
        if thermal_frame is not None and len(thermal_frame.shape) == 3:
            thermal_frame = cv2.cvtColor(thermal_frame, cv2.COLOR_BGR2GRAY)

        stats = self.compute_statistics(thermal_frame)
        hot_spots = self.detect_hot_spots(thermal_frame)
        cold_spots = self.detect_cold_spots(thermal_frame)
        anomalies = self.detect_anomalies(thermal_frame)

        # "Enhanced Fusion" anomaly type - the checkbox existed in the
        # panel but detect_enhanced_fusion_anomalies() was never called
        # anywhere in the pipeline, so it had no detection behind it at
        # all regardless of the checkbox. Gated on enabled_anomaly_types
        # (unlike the three detections above, which always run) since its
        # Sobel+Canny+contour pipeline costs meaningfully more and this
        # type defaults OFF in the UI.
        enhanced_fusion_anomalies: List[ThermalAnomaly] = []
        if self.enabled_anomaly_types.get('enhanced_fusion', False):
            try:
                enhanced_fusion_anomalies = self.detect_enhanced_fusion_anomalies(thermal_frame)
            except Exception as e:
                logger.error(f"Enhanced fusion anomaly detection error: {e}")

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
            'enhanced_fusion_anomalies': enhanced_fusion_anomalies,
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

    def _estimated_map(self, thermal_frame: np.ndarray) -> Optional[np.ndarray]:
        """
        Full-frame estimated Celsius map from the 8-bit estimator, or None
        if estimation isn't active (not enabled, no estimator wired, or the
        camera is actually radiometric and shouldn't use a guess at all).

        compute_statistics/detect_hot_spots/detect_cold_spots each call this
        once, and detect_anomalies calls compute_statistics again internally
        - a single analyze() pass was recomputing the estimator's adaptive-
        range percentile scan 4-5x on the same frame. Cached by frame
        identity (valid for the lifetime of one analyze() call, since a new
        frame object arrives each time the throttle in app.py lets one
        through).
        """
        if self.is_radiometric or not self.estimation_enabled or self.thermal_estimator is None:
            return None
        cache_key = id(thermal_frame)
        if self._est_map_cache_key == cache_key:
            return self._est_map_cache
        fpa = self.last_fpa_temp_c if self.last_fpa_temp_c is not None else 25.0
        try:
            est_map = self.thermal_estimator.estimate_temperature_map(thermal_frame, fpa)
        except Exception as e:
            logger.debug(f"8-bit estimation map failed: {e}")
            est_map = None
        self._est_map_cache_key = cache_key
        self._est_map_cache = est_map
        return est_map

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

    def analyze_frame(self, thermal_frame: np.ndarray,
                      roi_mask: Optional[np.ndarray] = None) -> ThermalStatistics:
        """
        Analyze a thermal frame and return comprehensive statistics.

        Public convenience alias for compute_statistics().

        Args:
            thermal_frame: Thermal image (grayscale, 8-bit or 16-bit)
            roi_mask: Optional mask to analyze specific region (same size as thermal_frame)

        Returns:
            ThermalStatistics object with all computed metrics, or None for invalid input
        """
        return self.compute_statistics(thermal_frame, roi_mask=roi_mask)

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
            # ravel(), not flatten(): flatten() always copies; the
            # astype() right below copies unconditionally too (copy=True
            # is astype's default regardless of whether dtype already
            # matches), so flatten()'s own copy was pure redundant work.
            pixels = thermal_frame.ravel()

        if pixels.size == 0:
            return None

        # Convert to float for accurate statistics
        pixels = pixels.astype(np.float32)

        # Apply calibration if using radiometric data
        if self.calibration_scale != 1.0 or self.calibration_offset != 0.0:
            pixels = pixels * self.calibration_scale + self.calibration_offset

        # Compute raw statistics first. min/max/median/p95/p5 were 5
        # separate calls, each independently sorting/partitioning the same
        # ~327K-element array (profiled: percentile+median machinery was
        # the single largest cost in the whole analysis pipeline, well
        # above hot/cold-spot detection). One combined percentile call does
        # one partition pass instead of five.
        min_raw, p5_raw, median_raw, p95_raw, max_raw = (
            float(v) for v in np.percentile(pixels, [0, 5, 50, 95, 100])
        )
        mean_raw = float(np.mean(pixels))
        std_raw = float(np.std(pixels))

        # Convert to Celsius if radiometric (Y16 format: value = Kelvin × 100)
        est_map = None
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
            est_map = self._estimated_map(thermal_frame)
            if est_map is not None:
                est_pixels = (est_map[roi_mask > 0] if roi_mask is not None else est_map.ravel()).astype(np.float32)
                min_val, p5_val, median_val, p95_val, max_val = (
                    float(v) for v in np.percentile(est_pixels, [0, 5, 50, 95, 100])
                )
                mean_val = float(np.mean(est_pixels))
                std_val = float(np.std(est_pixels))
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
            unit=unit_symbol if self.is_radiometric else (f"{unit_symbol} (est)" if est_map is not None else " (raw)"),
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

        # Computed once for the whole frame, not per-spot below.
        est_map = self._estimated_map(thermal_frame)

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

            # Calculate confidence based on how much hotter than threshold (in raw units).
            # threshold_value can legitimately be 0 (e.g. a mostly-black scene,
            # or non-radiometric video whose raw counts sit near zero) - divide
            # by it unconditionally warned every single frame instead of just
            # treating "no meaningful threshold" as full confidence.
            confidence = 1.0 if threshold_value <= 0 else min(1.0, (max_raw - threshold_value) / (threshold_value * 0.5))

            # Convert to Celsius if radiometric (Y16 format: value = Kelvin × 100)
            if self.is_radiometric:
                max_temp = self._y16_to_celsius(max_raw)
                mean_temp = self._y16_to_celsius(mean_raw)
            elif est_map is not None:
                est_roi = est_map[y:y+h, x:x+w]
                max_temp = float(np.max(est_roi))
                mean_temp = float(np.mean(est_roi))
            else:
                max_temp = max_raw
                mean_temp = mean_raw

            # Convert to target unit - estimated values are Celsius from the
            # estimator same as radiometric ones are from Y16, so both need
            # this, not just is_radiometric (raw AGC has no real unit to
            # convert from, so it's excluded).
            if self.is_radiometric or est_map is not None:
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
                unit=unit_symbol if self.is_radiometric else (f"{unit_symbol} (est)" if est_map is not None else " (raw)"),
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

        # Computed once for the whole frame, not per-spot below.
        est_map = self._estimated_map(thermal_frame)

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

            # Calculate confidence based on how much colder than threshold (in raw units).
            # See detect_hot_spots' identical guard - threshold_value can
            # legitimately be 0.
            confidence = 1.0 if threshold_value <= 0 else min(1.0, (threshold_value - min_raw) / (threshold_value * 0.5))

            # Convert to Celsius if radiometric (Y16 format: value = Kelvin × 100)
            if self.is_radiometric:
                min_temp = self._y16_to_celsius(min_raw)
                mean_temp = self._y16_to_celsius(mean_raw)
            elif est_map is not None:
                est_roi = est_map[y:y+h, x:x+w]
                min_temp = float(np.min(est_roi))
                mean_temp = float(np.mean(est_roi))
            else:
                min_temp = min_raw
                mean_temp = mean_raw

            # Convert to target unit - same as detect_hot_spots, estimated
            # values need this too, not just radiometric ones.
            if self.is_radiometric or est_map is not None:
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
                unit=unit_symbol if self.is_radiometric else (f"{unit_symbol} (est)" if est_map is not None else " (raw)"),
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

        # Only .mean_temp and .timestamp are ever read from this (below, and
        # next call's prev_stats comparison) - calling the full
        # compute_statistics() paid for percentile/median/std/min/max
        # (profiled as the single largest cost in the whole analysis
        # pipeline) on every detect_anomalies() call for values nothing
        # reads, and it ran unconditionally even when is_radiometric is
        # False, where the result is never read at all (the block that
        # consumes it is gated on that same flag below).
        mean_raw = float(np.mean(thermal_frame))
        current_stats = ThermalStatistics(
            min_temp=0.0, max_temp=0.0,
            mean_temp=self._y16_to_celsius(mean_raw) if self.is_radiometric else mean_raw,
            median_temp=0.0, std_temp=0.0, temp_range=0.0,
            percentile_95=0.0, percentile_5=0.0,
            pixel_count=thermal_frame.size,
        )

        # ── Fix 5: Grid-based rate-of-change (localised hotspot detection) ──────
        # Detects rapid heating in individual 8x8 grid cells, not just global mean.
        #
        # rapid_change_threshold/gradient_threshold below are calibrated in
        # actual degrees, which only means something once the frame holds
        # calibrated temperature values (radiometric mode). On a raw 8-bit
        # AGC frame, per-frame contrast re-stretching alone routinely swings
        # raw values by more than these thresholds, so every one of these
        # degree-based detectors floods the overlay with false positives.
        # Restrict them to radiometric frames; the statistical-outlier
        # background model below is scale-relative and stays on for both.
        if self.is_radiometric:
            anomalies.extend(self._detect_grid_rate_of_change(thermal_frame))

            # ── Global rate-of-change (kept as fast coarse filter) ──────────
            if roi_id in self.last_frame_stats:
                prev_stats = self.last_frame_stats[roi_id]

                temp_change = current_stats.mean_temp - prev_stats.mean_temp
                time_delta = current_stats.timestamp - prev_stats.timestamp
                if time_delta > 0:
                    rate_of_change = temp_change / time_delta

                    if rate_of_change > self.rapid_change_threshold:
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
                        h, w = thermal_frame.shape[:2]
                        anomalies.append(ThermalAnomaly(
                            anomaly_type=AnomalyType.RAPID_DECREASE,
                            location=(w//2, h//2),
                            bbox=(0, 0, w, h),
                            severity=min(1.0, abs(rate_of_change) / (self.rapid_change_threshold * 2)),
                            description=f"Rapid temperature decrease: {rate_of_change:.1f}°/s",
                            metadata={"rate": rate_of_change}
                        ))

        # Store current stats for next frame comparison regardless of mode,
        # so rate-of-change has a valid baseline the moment radiometric mode
        # is turned on mid-session.
        self.last_frame_stats[roi_id] = current_stats

        # ── Fix 3: Region-based gradient anomaly (replaces single-pixel argmax) ─
        gradient = self.compute_temperature_gradient(thermal_frame) if self.is_radiometric else None
        if gradient is not None:
            gradient_mask = (gradient > self.gradient_threshold).astype(np.uint8) * 255
            if gradient_mask.any():
                # Close small gaps so adjacent hot-edge pixels form one region
                kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
                gradient_mask = cv2.morphologyEx(gradient_mask, cv2.MORPH_CLOSE, kernel)
                contours, _ = cv2.findContours(
                    gradient_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
                )
                for contour in contours:
                    area = cv2.contourArea(contour)
                    if area < 50:   # ignore noise specks
                        continue
                    x, y, w, h = cv2.boundingRect(contour)
                    M = cv2.moments(contour)
                    if M["m00"] != 0:
                        cx = int(M["m10"] / M["m00"])
                        cy = int(M["m01"] / M["m00"])
                    else:
                        cx, cy = x + w // 2, y + h // 2
                    roi_grad = gradient[y:y+h, x:x+w]
                    max_grad = float(np.max(roi_grad))
                    severity = min(1.0, max_grad / (self.gradient_threshold * 2))
                    anomalies.append(ThermalAnomaly(
                        anomaly_type=AnomalyType.GRADIENT_ANOMALY,
                        location=(cx, cy),
                        bbox=(x, y, x+w, y+h),
                        severity=severity,
                        description=f"Gradient region: {max_grad:.1f}° over {area:.0f}px²",
                        metadata={"max_gradient": max_grad, "area": float(area)}
                    ))

        # ── Statistical Background Modeling ─────────────────────────────────────
        if thermal_frame is not None:
            thermal_float = thermal_frame.astype(np.float32)

            if self.background_model is None or self.background_model.shape != thermal_float.shape:
                self.background_model = thermal_float.copy()
                self.frame_count = 0
            else:
                # ── Fix 4: Motion guard ─────────────────────────────────────────
                # If the global mean diff is very high the camera is panning.
                # Skip the model update AND outlier detection for this frame to
                # avoid poisoning the background model and generating false flags.
                global_diff = float(np.mean(cv2.absdiff(thermal_float, self.background_model)))
                if global_diff > self._motion_guard_threshold:
                    return anomalies   # camera moving — no update, no outlier detection

                cv2.accumulateWeighted(thermal_float, self.background_model, self.background_alpha)

            self.frame_count += 1

            # Only detect after initialization period
            if self.frame_count > self.background_init_frames:
                diff = cv2.absdiff(thermal_float, self.background_model)
                mean_diff = np.mean(diff)
                std_diff = np.std(diff)
                threshold = mean_diff + (3.0 * std_diff)

                outlier_mask = (diff > threshold).astype(np.uint8) * 255
                kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
                outlier_mask = cv2.morphologyEx(outlier_mask, cv2.MORPH_OPEN, kernel)

                contours, _ = cv2.findContours(
                    outlier_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
                )

                for contour in contours:
                    area = cv2.contourArea(contour)
                    if area < 100:
                        continue
                    x, y, w, h = cv2.boundingRect(contour)
                    M = cv2.moments(contour)
                    if M["m00"] != 0:
                        cx = int(M["m10"] / M["m00"])
                        cy = int(M["m01"] / M["m00"])
                    else:
                        cx, cy = x + w//2, y + h//2
                    roi_diff = diff[y:y+h, x:x+w]
                    max_diff = np.max(roi_diff)
                    severity = min(1.0, max_diff / (threshold * 2))
                    anomalies.append(ThermalAnomaly(
                        anomaly_type=AnomalyType.STATISTICAL_OUTLIER,
                        location=(cx, cy),
                        bbox=(x, y, x+w, y+h),
                        severity=severity,
                        description=f"Statistical outlier (diff: {max_diff:.1f})",
                        metadata={"max_diff": float(max_diff), "threshold": float(threshold)}
                    ))

        return anomalies

    def _detect_grid_rate_of_change(
        self, thermal_frame: np.ndarray
    ) -> List["ThermalAnomaly"]:
        """
        Fix 5: Grid-based rate-of-change anomaly detection.

        Divides the frame into an N×N grid (default 8×8) and tracks the mean
        temperature of each cell between frames.  Cells that change faster than
        ``rapid_change_threshold`` degrees/second are reported as localised
        RAPID_INCREASE / RAPID_DECREASE anomalies.  This catches small hotspots
        (e.g. a single overheating component) that are invisible in the global
        frame mean.
        """
        anomalies: List[ThermalAnomaly] = []
        if thermal_frame is None or thermal_frame.size == 0:
            return anomalies

        now = time.time()
        g = self._grid_size
        h, w = thermal_frame.shape[:2]

        # Downsample to grid via area-averaging
        grid_now = cv2.resize(
            thermal_frame.astype(np.float32),
            (g, g),
            interpolation=cv2.INTER_AREA,
        )

        if self._grid_history is not None and self._grid_last_time is not None:
            dt = now - self._grid_last_time
            if dt > 0:
                rates = (grid_now - self._grid_history) / dt   # (g, g) rate map
                cell_h = h / g
                cell_w = w / g

                # Uniform-shift guard: a whole-frame brightness change — AGC
                # renormalizing (common on 8-bit non-radiometric backends,
                # especially while it's still converging right after FFC/
                # startup) or the camera panning — moves every cell's value
                # together. Per-cell thresholding alone can't tell that apart
                # from dozens of independent localised hotspots, and floods
                # the overlay with one label per grid cell. If most cells
                # cross the threshold in the same tick, it's one global event,
                # not (g*g) local ones, so skip emitting anomalies for it —
                # same intent as the motion guard below, extended to this
                # detector, which the original guard never covered.
                exceeding = np.abs(rates) > self.rapid_change_threshold
                if exceeding.mean() > self._grid_uniform_shift_fraction:
                    self._grid_history = grid_now
                    self._grid_last_time = now
                    return anomalies

                for gy in range(g):
                    for gx in range(g):
                        rate = float(rates[gy, gx])
                        if abs(rate) <= self.rapid_change_threshold:
                            continue

                        # Map grid cell back to pixel coordinates
                        px1 = int(gx * cell_w)
                        py1 = int(gy * cell_h)
                        px2 = int(min(w, (gx + 1) * cell_w))
                        py2 = int(min(h, (gy + 1) * cell_h))
                        cx = (px1 + px2) // 2
                        cy = (py1 + py2) // 2

                        severity = min(
                            1.0, abs(rate) / (self.rapid_change_threshold * 2)
                        )
                        atype = (
                            AnomalyType.RAPID_INCREASE
                            if rate > 0
                            else AnomalyType.RAPID_DECREASE
                        )
                        direction = "increase" if rate > 0 else "decrease"
                        anomalies.append(ThermalAnomaly(
                            anomaly_type=atype,
                            location=(cx, cy),
                            bbox=(px1, py1, px2, py2),
                            severity=severity,
                            description=(
                                f"Localised {direction}: {rate:.1f}°/s "
                                f"at grid ({gx},{gy})"
                            ),
                            metadata={"rate": rate, "grid": (gx, gy)},
                        ))

        self._grid_history = grid_now
        self._grid_last_time = now
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
            # Highlight anomaly regions with a distinct color tint rather
            # than a plain brightness boost - convertScaleAbs's +30/*1.3
            # boost clips to white on already-bright palette regions (e.g.
            # ironbow's hot end), and "Above Threshold" (the default
            # detection mode) selects exactly those brightest pixels by
            # definition - the effect was applying but visually
            # indistinguishable from doing nothing on typical palettes. A
            # hue shift stays visible regardless of the underlying
            # brightness at that pixel.
            #
            # Pure integer 50/50 blend (right-shift instead of a float
            # cast) - measured live at 8-16ms/frame with the float32 path
            # (colorized_frame.astype(float32) + two more full-frame float
            # arrays before the final astype back to uint8) on a 512x640
            # frame, versus <1ms for the equivalent uint8 arithmetic below.
            # Same visual result (a color tint independent of underlying
            # brightness), no precision the 8-bit output could show anyway.
            highlight_color = np.array([0, 255, 255], dtype=np.uint8)  # BGR: bright yellow
            tinted = (colorized_frame >> 1) + (highlight_color >> 1)

            output = np.where(mask[..., np.newaxis] > 0, tinted, colorized_frame)

        elif viz_mode == ThresholdVisualization.BINARY_MASK:
            # Pure black and white
            binary_3ch = cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR)
            output = binary_3ch

        elif viz_mode == ThresholdVisualization.GRADIENT_OVERLAY:
            # Distance-based gradient fade
            # Compute distance transform from anomaly edges
            mask_binary = (mask > 0).astype(np.uint8)
            dist_from_anomaly = cv2.distanceTransform(1 - mask_binary, cv2.DIST_L2, 5)
            dist_from_anomaly = np.clip(dist_from_anomaly / 50.0, 0.0, 1.0)  # Normalize to 0-1, stays float32

            # Create gradient overlay. Measured live at 27-43ms/frame on a
            # 512x640 frame before this rewrite - profiled down to the
            # (H,W,3)*(H,W,1) broadcast multiplies themselves: on this
            # NumPy build a broadcast elementwise multiply measured ~3x
            # slower than the equivalent same-shape multiply (6.4ms vs
            # 2.2ms for one array this size), not a memory-bandwidth
            # limit - the float64 upcast from mixing uint8 and float32
            # and the wasted np.ones_like(colorized_frame) allocation
            # this replaced were real but comparatively minor next to
            # that. A first fix split into per-channel cv2.split/merge
            # multiplies (no broadcast) - correct, but cv2.split/merge
            # themselves turned out to cost ~5.6ms of that (copying to 3
            # separate contiguous arrays and back), against ~0.07ms for
            # the actual multiply. Operating on strided views into the
            # interleaved array directly - no split/merge at all - is
            # bit-identical and cut isolated timing from ~10ms to ~4.4ms
            # (confirmed live: still noticeably faster). The overlay
            # color is pure red (BGR 0,0,255), so its contribution to
            # B/G is always zero - only the R view needs the alpha term.
            alpha = (1.0 - dist_from_anomaly) * 0.5  # float32, (H,W), in [0, 0.5]
            weight = 1.0 - alpha
            frame_f32 = colorized_frame.astype(np.float32)
            frame_f32[..., 0] *= weight
            frame_f32[..., 1] *= weight
            frame_f32[..., 2] *= weight
            frame_f32[..., 2] += 255.0 * alpha
            output = frame_f32.astype(np.uint8)

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
