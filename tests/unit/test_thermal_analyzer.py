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


class TestGridRateOfChangeUniformShiftGuard:
    """
    Regression coverage for a real bug found debugging a live camera: an
    AGC brightness renormalization (or the camera panning) shifts every
    pixel together, and the un-guarded per-cell grid detector read that as
    dozens of simultaneous independent "localised" hotspots — one label per
    8x8 grid cell, up to 64 in a single frame, making the overlay unreadable.
    A uniform whole-frame shift must be recognized as one event, not (grid
    size squared) separate anomalies.
    """

    @pytest.mark.unit
    def test_uniform_frame_shift_does_not_flood_grid_anomalies(self):
        analyzer = ThermalAnalyzer({"rapid_change_threshold": 5.0, "grid_size": 8})
        base = np.full((256, 320), 128, dtype=np.uint8)

        # Seed grid history with the base frame.
        analyzer._detect_grid_rate_of_change(base)
        analyzer._grid_last_time -= 0.1  # realistic inter-frame delta

        # Simulate an AGC-style whole-frame brightness shift: every pixel
        # moves the same amount, nothing localized.
        shifted = np.clip(base.astype(np.int16) + 40, 0, 255).astype(np.uint8)
        anomalies = analyzer._detect_grid_rate_of_change(shifted)

        assert anomalies == [], (
            "A uniform whole-frame shift must not produce per-cell anomalies"
        )

    @pytest.mark.unit
    def test_genuine_localized_hotspot_is_still_detected(self):
        # A real, spatially confined hotspot must still be caught — the
        # guard should only suppress whole-frame shifts, not real anomalies.
        analyzer = ThermalAnalyzer({"rapid_change_threshold": 5.0, "grid_size": 8})
        base = np.full((256, 320), 128, dtype=np.uint8)
        analyzer._detect_grid_rate_of_change(base)
        # Force a realistic inter-frame delta — back-to-back calls in a test
        # can land microseconds apart, which turns any pixel noise into an
        # enormous (diff / dt) rate and defeats the point of this test.
        analyzer._grid_last_time -= 0.1

        hotspot = base.copy()
        hotspot[100:140, 100:140] = 255  # one small region heats up sharply

        anomalies = analyzer._detect_grid_rate_of_change(hotspot)

        assert len(anomalies) > 0
        assert len(anomalies) < 10, (
            "A single localized hotspot should flag a handful of cells, "
            "not most of the grid"
        )

    @pytest.mark.unit
    def test_uniform_shift_still_updates_grid_history(self):
        # The guard must not stall tracking — history/timestamp should
        # advance even on a suppressed (uniform-shift) tick, so the next
        # real frame is compared against current state, not stale state.
        analyzer = ThermalAnalyzer({"rapid_change_threshold": 5.0, "grid_size": 8})
        base = np.full((256, 320), 128, dtype=np.uint8)
        analyzer._detect_grid_rate_of_change(base)
        analyzer._grid_last_time -= 0.1

        shifted = np.clip(base.astype(np.int16) + 40, 0, 255).astype(np.uint8)
        analyzer._detect_grid_rate_of_change(shifted)

        assert analyzer._grid_history is not None
        assert np.allclose(analyzer._grid_history, 168.0, atol=1.0)


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


def _reference_gradient_overlay(thermal_frame, colorized_frame, mask, threshold_mode,
                                 min_t, max_t, frame_min, frame_max):
    """
    Pre-LUT reference implementation of GRADIENT_OVERLAY - full per-pixel
    float32 arithmetic, no quantization. Kept only so the LUT-based
    version can be checked against it; not itself the code under test.
    """
    _MAX_ALPHA = 0.5
    _HOT, _COLD, _BAND = (0, 0, 255), (255, 0, 0), (255, 0, 255)
    severity = ThermalAnalyzer._gradient_severity(
        thermal_frame, threshold_mode, min_t, max_t, frame_min, frame_max
    )
    mask_binary = (mask > 0).astype(np.float32)
    alpha = severity * mask_binary * _MAX_ALPHA
    weight = 1.0 - alpha
    if threshold_mode == ThresholdMode.OUTSIDE:
        is_below = thermal_frame < min_t
        b = np.where(is_below, _COLD[0], _HOT[0]).astype(np.float32)
        g = np.where(is_below, _COLD[1], _HOT[1]).astype(np.float32)
        r = np.where(is_below, _COLD[2], _HOT[2]).astype(np.float32)
    else:
        color = {ThresholdMode.ABOVE: _HOT, ThresholdMode.BELOW: _COLD,
                  ThresholdMode.BETWEEN: _BAND}.get(threshold_mode, _HOT)
        b, g, r = float(color[0]), float(color[1]), float(color[2])
    f32 = colorized_frame.astype(np.float32)
    f32[..., 0] *= weight; f32[..., 0] += b * alpha
    f32[..., 1] *= weight; f32[..., 1] += g * alpha
    f32[..., 2] *= weight; f32[..., 2] += r * alpha
    return f32.astype(np.uint8)


class TestGradientOverlayLUT:
    """
    Tests for apply_threshold_visualization's GRADIENT_OVERLAY LUT
    optimization. Previously this branch recomputed severity, the mask
    multiply, and (for OUTSIDE) per-pixel color selection as full (H,W)
    numpy passes on every single frame, which cost ~25-35ms/frame
    regardless of any other feature enabled and single-handedly capped
    FPS to the low 20s ("manual threshold with nothing else applied...
    20s fps, major bug" / "gradient overlay is slow in all 4 modes",
    2026-09-03). Those quantities are pure functions of a pixel's raw
    value plus the threshold configuration, so they're now a cached
    256-entry LUT (_get_gradient_luts) expanded per-frame via cv2.LUT -
    these tests pin both the caching behavior and that the quantization
    this introduces stays within a small, documented tolerance of the
    original per-pixel formula (not bit-identical - see
    _get_gradient_luts' docstring).
    """

    @staticmethod
    def _make_case(mode, seed=0):
        rng = np.random.default_rng(seed)
        h, w = 128, 160
        thermal = (20000 + rng.normal(0, 2000, size=(h, w))).astype(np.float32)
        colorized = rng.integers(0, 255, size=(h, w, 3), dtype=np.uint8)
        frame_min, frame_max = float(thermal.min()), float(thermal.max())

        if mode in (ThresholdMode.BETWEEN, ThresholdMode.OUTSIDE):
            min_t = float(np.percentile(thermal, 30))
            max_t = float(np.percentile(thermal, 70))
        else:
            min_t = float(np.percentile(thermal, 50))
            max_t = None

        if mode == ThresholdMode.ABOVE:
            mask = ((thermal >= min_t).astype(np.uint8)) * 255
        elif mode == ThresholdMode.BELOW:
            mask = ((thermal <= min_t).astype(np.uint8)) * 255
        elif mode == ThresholdMode.BETWEEN:
            mask = (((thermal >= min_t) & (thermal <= max_t)).astype(np.uint8)) * 255
        else:
            mask = (((thermal < min_t) | (thermal > max_t)).astype(np.uint8)) * 255

        detection = ThresholdDetectionResult(
            mask=mask, anomaly_count=int((mask > 0).sum()), total_pixels=h * w,
            anomaly_percentage=float((mask > 0).mean() * 100),
            min_threshold=min_t, max_threshold=max_t, threshold_mode=mode,
            timestamp=0.0, frame_min=frame_min, frame_max=frame_max,
        )
        return thermal, colorized, mask, min_t, max_t, frame_min, frame_max, detection

    @pytest.mark.unit
    @pytest.mark.parametrize("mode", [
        ThresholdMode.ABOVE, ThresholdMode.BELOW, ThresholdMode.BETWEEN, ThresholdMode.OUTSIDE,
    ])
    def test_matches_reference_within_quantization_tolerance(self, mode):
        thermal, colorized, mask, min_t, max_t, frame_min, frame_max, detection = self._make_case(mode)
        analyzer = ThermalAnalyzer()

        result = analyzer.apply_threshold_visualization(
            thermal, colorized, detection, ThresholdVisualization.GRADIENT_OVERLAY
        )
        reference = _reference_gradient_overlay(
            thermal, colorized, mask, mode, min_t, max_t, frame_min, frame_max
        )

        diff = np.abs(result.astype(np.int16) - reference.astype(np.int16))
        # 256-level quantization of the [frame_min, frame_max] value range
        # introduces small rounding differences - bound generously above
        # what's actually observed (max ~5/255) rather than pinned exactly,
        # so this doesn't become flaky if the RNG seed or frame size changes.
        assert diff.max() <= 10, f"{mode}: max diff {diff.max()}/255 exceeds quantization tolerance"

    @pytest.mark.unit
    def test_severity_is_zero_outside_mask(self):
        """output must equal the input exactly wherever the mask is 0 -
        the LUT's in_mask predicate must mirror detect_threshold_anomalies'
        own comparisons exactly, or this guarantee silently breaks."""
        thermal, colorized, mask, *_, detection = self._make_case(ThresholdMode.ABOVE)
        analyzer = ThermalAnalyzer()

        result = analyzer.apply_threshold_visualization(
            thermal, colorized, detection, ThresholdVisualization.GRADIENT_OVERLAY
        )

        outside = mask == 0
        np.testing.assert_array_equal(result[outside], colorized[outside])

    @pytest.mark.unit
    def test_lut_cache_reused_across_calls_with_same_config(self):
        thermal, colorized, mask, min_t, max_t, frame_min, frame_max, detection = self._make_case(
            ThresholdMode.OUTSIDE
        )
        analyzer = ThermalAnalyzer()

        analyzer.apply_threshold_visualization(
            thermal, colorized, detection, ThresholdVisualization.GRADIENT_OVERLAY
        )
        cached_key = analyzer._gradient_lut_cache_key
        cached_luts = analyzer._gradient_lut_cache

        analyzer.apply_threshold_visualization(
            thermal, colorized, detection, ThresholdVisualization.GRADIENT_OVERLAY
        )

        assert analyzer._gradient_lut_cache_key == cached_key
        assert analyzer._gradient_lut_cache is cached_luts, (
            "same threshold config on the next call must reuse the cached LUT tuple, not rebuild it"
        )

    @pytest.mark.unit
    def test_lut_cache_invalidated_when_threshold_changes(self):
        thermal, colorized, mask, min_t, max_t, frame_min, frame_max, detection = self._make_case(
            ThresholdMode.ABOVE
        )
        analyzer = ThermalAnalyzer()

        analyzer.apply_threshold_visualization(
            thermal, colorized, detection, ThresholdVisualization.GRADIENT_OVERLAY
        )
        first_luts = analyzer._gradient_lut_cache

        detection.min_threshold = min_t + 500  # simulate the user moving the slider
        analyzer.apply_threshold_visualization(
            thermal, colorized, detection, ThresholdVisualization.GRADIENT_OVERLAY
        )

        assert analyzer._gradient_lut_cache is not first_luts

    @pytest.mark.unit
    def test_reused_frame_min_max_matches_a_fresh_recompute(self):
        """Debt-ledger item: percentage-mode detection_result.frame_min/
        frame_max (computed by an earlier detect_threshold_anomalies()
        call) is reused here rather than recomputed from THIS call's own
        thermal_frame argument, on the assumption both calls in app.py's
        only real call path always receive the exact same frame object.
        Not runtime-validated (nothing to validate against if it were
        ever violated - there's no second frame to compare to), so this
        pins the actual invariant instead: reusing detection_result's
        values must produce byte-identical output to a fresh recompute
        from the same frame data, so the two code paths can never
        silently diverge even though only one of them normally runs."""
        thermal, colorized, mask, min_t, max_t, frame_min, frame_max, detection = self._make_case(
            ThresholdMode.BETWEEN
        )
        analyzer = ThermalAnalyzer()

        with_reused_values = analyzer.apply_threshold_visualization(
            thermal, colorized, detection, ThresholdVisualization.GRADIENT_OVERLAY
        )

        detection_without_cache = ThresholdDetectionResult(
            mask=detection.mask, anomaly_count=detection.anomaly_count,
            total_pixels=detection.total_pixels, anomaly_percentage=detection.anomaly_percentage,
            min_threshold=detection.min_threshold, max_threshold=detection.max_threshold,
            threshold_mode=detection.threshold_mode, timestamp=0.0,
            frame_min=None, frame_max=None,  # forces a fresh recompute from `thermal` below
        )
        analyzer2 = ThermalAnalyzer()  # fresh LUT cache, same frame
        with_fresh_recompute = analyzer2.apply_threshold_visualization(
            thermal, colorized, detection_without_cache, ThresholdVisualization.GRADIENT_OVERLAY
        )

        assert np.array_equal(with_reused_values, with_fresh_recompute), (
            "reusing detection_result's frame_min/frame_max must be "
            "byte-identical to recomputing them from the same frame - "
            "the two code paths are currently only equivalent because "
            "app.py's single caller always passes the same frame to "
            "both detect_threshold_anomalies() and this method"
        )
