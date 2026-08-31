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
