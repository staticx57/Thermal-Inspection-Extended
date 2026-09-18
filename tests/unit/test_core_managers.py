"""
Unit tests for the core state managers and the event bus.

These were introduced with the camera plugin architecture and previously had
no direct coverage — they were only exercised incidentally through the GUI.
"""
from dataclasses import FrozenInstanceError

import numpy as np
import pytest

from thermal_inspection.core.camera_state import CameraConfig, CameraState
from thermal_inspection.core.event_bus import AppEventBus
from thermal_inspection.core.isotherm_manager import IsothermManager, IsothermState
from thermal_inspection.processing.isotherm_bands import IsothermBandManager, load_preset
from thermal_inspection.core.threshold_manager import ThresholdManager, ThresholdState


# =====================================================================
# CameraState / CameraConfig
# =====================================================================

class TestCameraState:

    def test_defaults_are_disconnected(self):
        state = CameraState()
        assert state.thermal_connected is False
        assert state.rgb_available is False
        assert state.thermal_device_id is None
        assert state.rgb_device_id is None
        assert state.reconfiguring is False

    def test_fields_are_mutable(self):
        # The frame loop mutates this in place, so it must not be frozen.
        state = CameraState()
        state.thermal_connected = True
        state.thermal_device_id = 2
        assert state.thermal_connected is True
        assert state.thermal_device_id == 2

    def test_config_defaults_match_boson_640(self):
        config = CameraConfig()
        assert (config.width, config.height) == (640, 512)
        assert config.thermal_backend == 'opencv'
        assert config.disable_rgb is False


# =====================================================================
# ThresholdManager
# =====================================================================

class TestThresholdManager:

    def test_initial_state(self):
        mgr = ThresholdManager()
        state = mgr.get_state()
        assert isinstance(state, ThresholdState)
        assert state.enabled is False
        assert state.mode == "above"
        assert state.min_val == 50.0
        assert state.max_val == 75.0

    def test_get_state_returns_immutable_snapshot(self):
        mgr = ThresholdManager()
        snapshot = mgr.get_state()

        mgr.set_min(10.0)

        # The previously handed-out snapshot must not have changed underneath
        # the frame loop that is reading it.
        assert snapshot.min_val == 50.0
        assert mgr.get_state().min_val == 10.0

    def test_frozen_state_cannot_be_mutated(self):
        state = ThresholdManager().get_state()
        with pytest.raises(FrozenInstanceError):
            state.min_val = 1.0

    def test_set_enabled_coerces_to_bool(self):
        mgr = ThresholdManager()
        mgr.set_enabled(1)
        assert mgr.get_state().enabled is True

    @pytest.mark.parametrize("mode", ["above", "below", "between", "outside"])
    def test_valid_modes_accepted(self, mode):
        mgr = ThresholdManager()
        mgr.set_mode(mode)
        assert mgr.get_state().mode == mode

    def test_invalid_mode_is_ignored(self):
        mgr = ThresholdManager()
        mgr.set_mode("sideways")
        assert mgr.get_state().mode == "above"  # unchanged

    def test_invalid_viz_mode_is_ignored(self):
        mgr = ThresholdManager()
        original = mgr.get_state().viz_mode
        mgr.set_viz_mode("not_a_real_mode")
        assert mgr.get_state().viz_mode == original

    def test_state_changed_signal_fires_on_change(self, qtbot=None):
        mgr = ThresholdManager()
        fired = []
        mgr.state_changed.connect(lambda: fired.append(True))

        mgr.set_enabled(True)
        mgr.set_min(20.0)

        assert len(fired) == 2

    def test_state_changed_not_emitted_for_rejected_value(self):
        mgr = ThresholdManager()
        fired = []
        mgr.state_changed.connect(lambda: fired.append(True))

        mgr.set_mode("bogus")

        assert fired == []


# =====================================================================
# IsothermManager
# =====================================================================

class TestIsothermManager:

    def test_initial_state(self):
        mgr = IsothermManager()
        state = mgr.get_state()
        assert isinstance(state, IsothermState)
        assert state.enabled is False
        assert state.mode == "single"
        assert state.color == "red"

    def test_invalid_mode_and_color_ignored(self):
        mgr = IsothermManager()
        mgr.set_mode("quantum")
        mgr.set_color("ultraviolet")
        state = mgr.get_state()
        assert state.mode == "single"
        assert state.color == "red"

    def test_thresholds_round_trip(self):
        mgr = IsothermManager()
        mgr.set_low_threshold(35.5)
        mgr.set_high_threshold(80.25)
        state = mgr.get_state()
        assert state.low_threshold == pytest.approx(35.5)
        assert state.high_threshold == pytest.approx(80.25)

    def test_overlay_is_noop_when_disabled(self):
        mgr = IsothermManager()
        frame = np.zeros((8, 8, 3), dtype=np.uint8)
        temps = np.full((8, 8), 5000, dtype=np.uint16)

        result = mgr.apply_overlay(frame, temps)

        assert np.array_equal(result, frame)

    def test_overlay_is_noop_when_temp_frame_missing(self):
        mgr = IsothermManager()
        mgr.set_enabled(True)
        frame = np.zeros((4, 4, 3), dtype=np.uint8)

        assert np.array_equal(mgr.apply_overlay(frame, None), frame)

    def test_overlay_colors_pixels_inside_band(self):
        mgr = IsothermManager()
        mgr.set_enabled(True)
        mgr.set_color("red")
        mgr.set_low_threshold(20.0)
        mgr.set_high_threshold(30.0)

        frame = np.zeros((2, 2, 3), dtype=np.uint8)
        # Y16 is Kelvin x 100. 25 C -> 298.15 K -> 29815; 80 C -> 35315.
        temps = np.array([[29815, 29815],
                          [35315, 35315]], dtype=np.uint16)

        result = mgr.apply_overlay(frame, temps)

        # Top row (25 C) is inside [20, 30] and must be recolored;
        # bottom row (80 C) is outside and must be untouched.
        assert not np.array_equal(result[0], frame[0])
        assert np.array_equal(result[1], frame[1])

    def test_overlay_does_not_mutate_input_frame(self):
        mgr = IsothermManager()
        mgr.set_enabled(True)
        mgr.set_low_threshold(-50.0)
        mgr.set_high_threshold(500.0)

        frame = np.zeros((4, 4, 3), dtype=np.uint8)
        original = frame.copy()
        temps = np.full((4, 4), 29815, dtype=np.uint16)

        mgr.apply_overlay(frame, temps)

        assert np.array_equal(frame, original)

    def test_overlay_survives_malformed_input(self):
        # Shape mismatch must degrade to returning the original frame
        # rather than propagating out of the frame loop.
        mgr = IsothermManager()
        mgr.set_enabled(True)
        frame = np.zeros((4, 4, 3), dtype=np.uint8)
        temps = np.full((9, 9), 29815, dtype=np.uint16)

        result = mgr.apply_overlay(frame, temps)

        assert result.shape == frame.shape

    def test_multiband_actually_renders_on_a_real_radiometric_frame(self):
        """Regression for a real bug found during the 2026-09-07 pipeline
        characterization: the multiband path handed IsothermBandManager
        the raw Y16 frame (Kelvin x 100, e.g. ~29315 for 20C) instead of
        converting it to Celsius first, the way the single-threshold path
        below already did. IsothermBand thresholds are always Celsius, so
        every band's low/high compare was against a value on a completely
        different scale - every mask came back empty and the overlay
        silently rendered nothing, regardless of settings. Verified
        directly before fixing: 0 of 81920 pixels changed on this exact
        frame; this test pins the fixed behavior.
        """
        bands = IsothermBandManager()
        load_preset(bands, "temperature_zones")

        mgr = IsothermManager()
        mgr.set_band_manager(bands)
        mgr.set_enabled(True)
        mgr.set_multiband_mode(True)

        h, w = 256, 320
        # Y16 = Kelvin x 100. 20C -> 29315 (falls in the "Normal" 20-30C
        # band); 70C -> 34315 (falls in "Very Hot" 60-100C).
        thermal_16 = np.full((h, w), 29315, dtype=np.uint16)
        thermal_16[50:150, 50:200] = 34315
        colorized = np.zeros((h, w, 3), dtype=np.uint8)

        result = mgr.apply_overlay(colorized, thermal_16)

        assert not np.array_equal(result, colorized), (
            "multiband overlay rendered nothing on a real Y16 radiometric "
            "frame - the raw-value/Celsius unit mismatch regressed"
        )
        # Every pixel is inside SOME band (Normal or Very Hot both cover
        # this frame's two regions), so the whole frame should be tinted.
        changed = np.count_nonzero(np.any(result != colorized, axis=2))
        assert changed == h * w

    def test_multiband_and_single_threshold_use_the_same_conversion(self):
        """Both paths must classify the identical Y16 value identically -
        multiband isn't allowed to have its own, different idea of what
        temperature a given raw value represents."""
        h, w = 8, 8
        # 25C -> 29815, safely inside both a single-threshold [20,30] band
        # and the multiband "Normal" 20-30C band.
        temps = np.full((h, w), 29815, dtype=np.uint16)
        colorized = np.zeros((h, w, 3), dtype=np.uint8)

        single = IsothermManager()
        single.set_enabled(True)
        single.set_low_threshold(20.0)
        single.set_high_threshold(30.0)
        single_result = single.apply_overlay(colorized, temps)

        bands = IsothermBandManager()
        load_preset(bands, "temperature_zones")
        multi = IsothermManager()
        multi.set_band_manager(bands)
        multi.set_enabled(True)
        multi.set_multiband_mode(True)
        multi_result = multi.apply_overlay(colorized, temps)

        assert not np.array_equal(single_result, colorized)
        assert not np.array_equal(multi_result, colorized)


# =====================================================================
# AppEventBus
# =====================================================================

class TestAppEventBus:

    def test_signals_carry_payloads(self):
        bus = AppEventBus()
        received = []
        bus.camera_command_requested.connect(
            lambda role, cmd, params: received.append((role, cmd, params))
        )

        bus.camera_command_requested.emit("thermal", "ffc", {"force": True})

        assert received == [("thermal", "ffc", {"force": True})]

    def test_multiple_subscribers_all_notified(self):
        bus = AppEventBus()
        seen = []
        bus.recording_toggled.connect(lambda on: seen.append(("a", on)))
        bus.recording_toggled.connect(lambda on: seen.append(("b", on)))

        bus.recording_toggled.emit(True)

        assert seen == [("a", True), ("b", True)]

    def test_emitting_with_no_subscribers_is_safe(self):
        bus = AppEventBus()
        bus.snapshot_requested.emit()  # must not raise

    def test_intent_and_feedback_signals_are_distinct(self):
        # A command request must not loop back into the result handler.
        bus = AppEventBus()
        results = []
        bus.camera_command_result.connect(
            lambda role, cmd, res: results.append((role, cmd, res))
        )

        bus.camera_command_requested.emit("rgb", "set_property", {})

        assert results == []
