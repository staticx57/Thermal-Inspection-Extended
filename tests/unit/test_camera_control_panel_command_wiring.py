"""
Regression tests for camera-control panel command wiring, found during a
general best-practices audit (2026-09-03):

- RealSenseControlPanel had no command_requested signal at all - only a
  self.event_bus/set_event_bus() path that nothing in the codebase ever
  called (grepped: zero call sites). Every depth-sensor option change in
  this panel's UI silently did nothing, with no error or log. Added the
  same command_requested signal every other camera-control panel uses -
  main_window.py's _wire_plugin_panel() already generically connects it
  (hasattr(panel, 'command_requested')), so no wiring change was needed
  there.
- UVCControlPanel and GigEControlPanel each ALSO had that same dead
  self.event_bus/set_event_bus() path in addition to their (correctly
  wired) command_requested signal - not a live bug today since nothing
  calls set_event_bus(), but the day something did, every command from
  these panels would have fired twice (GigE's dead branch even fired
  for both "thermal" and "rgb" roles unconditionally). Removed the dead
  path entirely from all three panels.
"""
import pytest

from thermal_inspection.gui.camera_control.gige_control_panel import GigEControlPanel
from thermal_inspection.gui.camera_control.realsense_control_panel import RealSenseControlPanel
from thermal_inspection.gui.camera_control.uvc_control_panel import UVCControlPanel


@pytest.mark.unit
class TestRealSenseControlPanelCommandWiring:

    def test_option_change_emits_command_requested(self, qapp):
        panel = RealSenseControlPanel()
        received = []
        panel.command_requested.connect(lambda cmd, params: received.append((cmd, params)))

        panel._on_option_changed("laser_power", 150.0)

        assert received == [
            ("set_depth_sensor_option", {"option": "laser_power", "value": 150.0})
        ]

    def test_no_leftover_event_bus_attribute(self, qapp):
        panel = RealSenseControlPanel()
        assert not hasattr(panel, "event_bus")
        assert not hasattr(panel, "set_event_bus")


@pytest.mark.unit
class TestNoDeadEventBusPath:
    """The dead self.event_bus/set_event_bus() dual-dispatch path is gone
    from all three panels - command_requested is the only path left."""

    def test_uvc_panel_has_no_event_bus_attribute(self, qapp):
        panel = UVCControlPanel()
        assert not hasattr(panel, "event_bus")
        assert not hasattr(panel, "set_event_bus")

    def test_gige_panel_has_no_event_bus_attribute(self, qapp):
        panel = GigEControlPanel()
        assert not hasattr(panel, "event_bus")
        assert not hasattr(panel, "set_event_bus")
