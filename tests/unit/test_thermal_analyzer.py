"""
Unit Tests for ThermalAnalyzer

Tests the thermal analysis engine including:
- Frame analysis (statistics)
- Hot spot detection
- Cold spot detection
- Anomaly detection
- Temperature unit conversion
"""

import pytest
import numpy as np
from thermal_inspection.processing.thermal_analyzer import (
    ThermalAnalyzer,
    ThermalStatistics,
    HotSpot,
    ColdSpot,
    ThermalAnomaly,
    TemperatureUnit,
    AnomalyType,
    ThresholdMode,
    ThresholdVisualization,
    ThresholdDetectionResult
)


class TestThermalAnalyzerInit:
    """Tests for ThermalAnalyzer initialization."""

    @pytest.mark.unit
    def test_default_initialization(self):
        """Test analyzer initializes with default config."""
        analyzer = ThermalAnalyzer()
        assert analyzer is not None
        assert analyzer.temp_unit == TemperatureUnit.CELSIUS
        assert analyzer.hot_spot_threshold == 0.8
        assert analyzer.cold_spot_threshold == 0.2
        assert analyzer.is_radiometric is False

    @pytest.mark.unit
    def test_custom_config_initialization(self, default_analyzer_config):
        """Test analyzer initializes with custom config."""
        analyzer = ThermalAnalyzer(config=default_analyzer_config)
        assert analyzer.hot_spot_threshold == 0.8
        assert analyzer.max_hot_spots == 5

    @pytest.mark.unit
    def test_radiometric_config(self, radiometric_analyzer_config):
        """Test analyzer initializes in radiometric mode."""
        analyzer = ThermalAnalyzer(config=radiometric_analyzer_config)
        assert analyzer.is_radiometric is True


class TestFrameAnalysis:
    """Tests for frame analysis (statistics calculation)."""

    @pytest.mark.unit
    def test_analyze_frame_basic(self, thermal_frame_8bit):
        """Test basic frame analysis on 8-bit frame."""
        analyzer = ThermalAnalyzer()
        stats = analyzer.analyze_frame(thermal_frame_8bit)

        assert isinstance(stats, ThermalStatistics)
        assert stats.min_temp <= stats.mean_temp <= stats.max_temp
        assert stats.std_temp >= 0
        assert stats.pixel_count == 512 * 640

    @pytest.mark.unit
    def test_analyze_frame_with_mask(self, thermal_frame_8bit):
        """Test frame analysis with ROI mask."""
        analyzer = ThermalAnalyzer()

        # Create mask for center region
        mask = np.zeros((512, 640), dtype=np.uint8)
        mask[200:300, 250:400] = 255

        stats = analyzer.analyze_frame(thermal_frame_8bit, roi_mask=mask)

        assert stats.pixel_count < 512 * 640  # Should be smaller due to mask
        assert stats.pixel_count == np.sum(mask > 0)

    @pytest.mark.unit
    def test_analyze_frame_uniform(self, uniform_frame):
        """Test frame analysis on uniform frame (no variation)."""
        analyzer = ThermalAnalyzer()
        stats = analyzer.analyze_frame(uniform_frame)

        assert stats.min_temp == stats.max_temp
        assert stats.std_temp == 0.0
        assert stats.temp_range == 0.0

    @pytest.mark.unit
    def test_analyze_frame_empty(self, empty_frame):
        """Test frame analysis on empty (all zeros) frame."""
        analyzer = ThermalAnalyzer()
        stats = analyzer.analyze_frame(empty_frame)

        assert stats.min_temp == 0
        assert stats.max_temp == 0
        assert stats.mean_temp == 0

    @pytest.mark.unit
    def test_analyze_frame_percentiles(self, thermal_frame_8bit):
        """Test that percentiles are calculated correctly."""
        analyzer = ThermalAnalyzer()
        stats = analyzer.analyze_frame(thermal_frame_8bit)

        assert stats.percentile_5 <= stats.percentile_95
        assert stats.percentile_5 >= stats.min_temp
        assert stats.percentile_95 <= stats.max_temp


class TestHotSpotDetection:
    """Tests for hot spot detection."""

    @pytest.mark.unit
    def test_detect_hot_spots_basic(self, thermal_frame_8bit):
        """Test basic hot spot detection."""
        analyzer = ThermalAnalyzer()
        hot_spots = analyzer.detect_hot_spots(thermal_frame_8bit)

        assert isinstance(hot_spots, list)
        # Frame has a hot spot, should detect at least one
        assert len(hot_spots) >= 1

    @pytest.mark.unit
    def test_hot_spot_properties(self, thermal_frame_8bit):
        """Test that detected hot spots have correct properties."""
        analyzer = ThermalAnalyzer()
        hot_spots = analyzer.detect_hot_spots(thermal_frame_8bit)

        if len(hot_spots) > 0:
            spot = hot_spots[0]
            assert isinstance(spot, HotSpot)
            assert hasattr(spot, 'centroid')
            assert hasattr(spot, 'bbox')
            assert hasattr(spot, 'max_temp')
            assert hasattr(spot, 'area')
            assert spot.area > 0
            assert 0 <= spot.confidence <= 1

    @pytest.mark.unit
    def test_max_hot_spots_limit(self, thermal_frame_8bit):
        """Test that max_hot_spots config is respected."""
        config = {'max_hot_spots': 1}
        analyzer = ThermalAnalyzer(config=config)
        hot_spots = analyzer.detect_hot_spots(thermal_frame_8bit)

        assert len(hot_spots) <= 1

    @pytest.mark.unit
    def test_hot_spot_centroid_in_bounds(self, thermal_frame_8bit):
        """Test that hot spot centroids are within frame bounds."""
        analyzer = ThermalAnalyzer()
        hot_spots = analyzer.detect_hot_spots(thermal_frame_8bit)

        height, width = thermal_frame_8bit.shape
        for spot in hot_spots:
            cx, cy = spot.centroid
            assert 0 <= cx < width
            assert 0 <= cy < height


class TestColdSpotDetection:
    """Tests for cold spot detection."""

    @pytest.mark.unit
    def test_detect_cold_spots_basic(self, thermal_frame_8bit):
        """Test basic cold spot detection."""
        analyzer = ThermalAnalyzer()
        cold_spots = analyzer.detect_cold_spots(thermal_frame_8bit)

        assert isinstance(cold_spots, list)
        # Frame has a cold spot, should detect at least one
        assert len(cold_spots) >= 1

    @pytest.mark.unit
    def test_cold_spot_properties(self, thermal_frame_8bit):
        """Test that detected cold spots have correct properties."""
        analyzer = ThermalAnalyzer()
        cold_spots = analyzer.detect_cold_spots(thermal_frame_8bit)

        if len(cold_spots) > 0:
            spot = cold_spots[0]
            assert isinstance(spot, ColdSpot)
            assert hasattr(spot, 'centroid')
            assert hasattr(spot, 'min_temp')
            assert spot.area > 0


class TestAnomalyDetection:
    """Tests for thermal anomaly detection."""

    @pytest.mark.unit
    def test_detect_anomalies_basic(self, thermal_frame_8bit):
        """Test basic anomaly detection."""
        analyzer = ThermalAnalyzer()
        # Build background model by processing same frame multiple times
        for _ in range(35):
            analyzer.detect_anomalies(thermal_frame_8bit)

        anomalies = analyzer.detect_anomalies(thermal_frame_8bit)
        assert isinstance(anomalies, list)

    @pytest.mark.unit
    def test_anomaly_types(self):
        """Test that all anomaly types are defined."""
        assert AnomalyType.HOT_SPOT is not None
        assert AnomalyType.COLD_SPOT is not None
        assert AnomalyType.RAPID_INCREASE is not None
        assert AnomalyType.RAPID_DECREASE is not None

    @pytest.mark.unit
    def test_reset_background_model(self):
        """Test background model reset."""
        analyzer = ThermalAnalyzer()
        analyzer.reset_background_model()
        
        assert analyzer.background_model is None
        assert analyzer.frame_count == 0


class TestThresholdDetection:
    """Tests for manual threshold-based detection."""

    @pytest.mark.unit
    def test_threshold_above(self, thermal_frame_8bit):
        """Test threshold detection in ABOVE mode."""
        analyzer = ThermalAnalyzer()
        result = analyzer.detect_threshold_anomalies(
            thermal_frame_8bit,
            threshold_mode=ThresholdMode.ABOVE,
            min_threshold=150
        )

        assert result is not None
        assert isinstance(result, ThresholdDetectionResult)
        assert result.threshold_mode == ThresholdMode.ABOVE
        assert result.anomaly_count >= 0
        assert 0 <= result.anomaly_percentage <= 100

    @pytest.mark.unit
    def test_threshold_below(self, thermal_frame_8bit):
        """Test threshold detection in BELOW mode."""
        analyzer = ThermalAnalyzer()
        result = analyzer.detect_threshold_anomalies(
            thermal_frame_8bit,
            threshold_mode=ThresholdMode.BELOW,
            min_threshold=100
        )

        assert result.threshold_mode == ThresholdMode.BELOW
        assert result.anomaly_count >= 0

    @pytest.mark.unit
    def test_threshold_between(self, thermal_frame_8bit):
        """Test threshold detection in BETWEEN mode."""
        analyzer = ThermalAnalyzer()
        result = analyzer.detect_threshold_anomalies(
            thermal_frame_8bit,
            threshold_mode=ThresholdMode.BETWEEN,
            min_threshold=100,
            max_threshold=180
        )

        assert result.threshold_mode == ThresholdMode.BETWEEN


class TestTemperatureConversion:
    """Tests for temperature unit conversion."""

    @pytest.mark.unit
    def test_celsius_to_fahrenheit(self):
        """Test Celsius to Fahrenheit conversion."""
        analyzer = ThermalAnalyzer()
        # 0°C = 32°F
        result = analyzer.convert_temperature(0, TemperatureUnit.CELSIUS, TemperatureUnit.FAHRENHEIT)
        assert abs(result - 32.0) < 0.01
        # 100°C = 212°F
        result = analyzer.convert_temperature(100, TemperatureUnit.CELSIUS, TemperatureUnit.FAHRENHEIT)
        assert abs(result - 212.0) < 0.01

    @pytest.mark.unit
    def test_celsius_to_kelvin(self):
        """Test Celsius to Kelvin conversion."""
        analyzer = ThermalAnalyzer()
        # 0°C = 273.15K
        result = analyzer.convert_temperature(0, TemperatureUnit.CELSIUS, TemperatureUnit.KELVIN)
        assert abs(result - 273.15) < 0.01
        # 25°C = 298.15K
        result = analyzer.convert_temperature(25, TemperatureUnit.CELSIUS, TemperatureUnit.KELVIN)
        assert abs(result - 298.15) < 0.01

    @pytest.mark.unit
    def test_same_unit_conversion(self):
        """Test that same-unit conversion returns original value."""
        analyzer = ThermalAnalyzer()
        assert analyzer.convert_temperature(50, TemperatureUnit.CELSIUS, TemperatureUnit.CELSIUS) == 50
        assert analyzer.convert_temperature(100, TemperatureUnit.FAHRENHEIT, TemperatureUnit.FAHRENHEIT) == 100


class TestRadiometricMode:
    """Tests for radiometric (16-bit) mode."""

    @pytest.mark.unit
    def test_16bit_statistics(self, thermal_frame_16bit, radiometric_analyzer_config):
        """Test frame analysis on 16-bit radiometric frame."""
        analyzer = ThermalAnalyzer(config=radiometric_analyzer_config)
        stats = analyzer.analyze_frame(thermal_frame_16bit)

        assert stats is not None
        # Values should be in reasonable temperature range for T-Linear
        # Background is ~25°C, hot spot ~50°C, cold spot ~10°C

    @pytest.mark.unit
    def test_16bit_hot_spot_detection(self, thermal_frame_16bit, radiometric_analyzer_config):
        """Test hot spot detection on 16-bit frame."""
        analyzer = ThermalAnalyzer(config=radiometric_analyzer_config)
        hot_spots = analyzer.detect_hot_spots(thermal_frame_16bit)

        # Should detect the 50°C hot spot
        assert len(hot_spots) >= 1


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    @pytest.mark.unit
    def test_single_pixel_frame(self):
        """Test handling of 1x1 frame."""
        analyzer = ThermalAnalyzer()
        frame = np.array([[128]], dtype=np.uint8)
        stats = analyzer.analyze_frame(frame)

        assert stats.pixel_count == 1
        assert stats.min_temp == stats.max_temp == 128

    @pytest.mark.unit
    def test_very_small_frame(self):
        """Test handling of very small frame (2x2)."""
        analyzer = ThermalAnalyzer()
        frame = np.array([[100, 200], [150, 175]], dtype=np.uint8)
        stats = analyzer.analyze_frame(frame)

        assert stats.min_temp == 100
        assert stats.max_temp == 200
        assert stats.pixel_count == 4

    @pytest.mark.unit
    def test_empty_mask(self, thermal_frame_8bit):
        """Test analysis with all-zero mask."""
        analyzer = ThermalAnalyzer()
        mask = np.zeros((512, 640), dtype=np.uint8)

        # Should handle gracefully (return None)
        stats = analyzer.analyze_frame(thermal_frame_8bit, roi_mask=mask)
        # Empty mask means 0 pixels - returns None
        assert stats is None

    @pytest.mark.unit
    def test_none_frame(self):
        """Test analysis with None frame."""
        analyzer = ThermalAnalyzer()
        stats = analyzer.analyze_frame(None)
        assert stats is None


class TestPerformance:
    """Performance-related tests."""

    @pytest.mark.unit
    @pytest.mark.slow
    def test_large_frame_performance(self, large_thermal_frame):
        """Test that large frames are processed in reasonable time."""
        import time
        analyzer = ThermalAnalyzer()

        start = time.time()
        stats = analyzer.analyze_frame(large_thermal_frame)
        elapsed = time.time() - start

        assert stats is not None
        assert elapsed < 1.0  # Should complete in under 1 second

    @pytest.mark.unit
    def test_repeated_analysis_stability(self, thermal_frame_8bit):
        """Test that repeated analysis produces consistent results."""
        analyzer = ThermalAnalyzer()

        stats1 = analyzer.analyze_frame(thermal_frame_8bit)
        stats2 = analyzer.analyze_frame(thermal_frame_8bit)

        assert stats1.min_temp == stats2.min_temp
        assert stats1.max_temp == stats2.max_temp
        assert stats1.mean_temp == stats2.mean_temp
