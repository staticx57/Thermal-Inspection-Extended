"""
Unit tests verifying that all thermal controls, generic connectors,
and dynamic hot-plugging handlers are properly wired.
"""
from thermal_inspection.cameras.plugin import get_registry, CameraRole, CameraPluginMatch
from thermal_inspection.gui.camera_control.boson_control_panel import BosonControlPanel
from thermal_inspection.gui.camera_control.tau2_control_panel import Tau2ControlPanel
from thermal_inspection.gui.camera_control.gige_control_panel import GigEControlPanel
from thermal_inspection.gui.camera_control.uvc_control_panel import UVCControlPanel

# `qapp` fixture is provided by tests/conftest.py (session-scoped, shared
# across all test modules — see the comment there for why that matters).


class TestThermalPluginRegistration:
    def test_all_plugins_registered(self, qapp):
        registry = get_registry()
        plugins = {p.plugin_id: p for p in registry.get_all_plugins()}

        expected_plugins = ["flir_boson", "flir_tau2", "flir_lepton", "flir_firefly", "generic_uvc", "gige_vision"]
        for pid in expected_plugins:
            assert pid in plugins, f"Expected plugin '{pid}' is not registered in CameraPluginRegistry!"

    def test_thermal_plugin_capabilities(self, qapp):
        registry = get_registry()

        # Boson
        boson = registry.get_plugin("flir_boson")
        assert boson.camera_role == CameraRole.THERMAL
        match = CameraPluginMatch(plugin_id="flir_boson", device_index=0)
        caps = boson.get_capabilities(match)
        assert caps.radiometric is True
        assert caps.has_ffc is True
        assert caps.has_gain_mode is True

        # Tau 2
        tau2 = registry.get_plugin("flir_tau2")
        assert tau2.camera_role == CameraRole.THERMAL
        caps_tau = tau2.get_capabilities(match)
        assert caps_tau.radiometric is True
        assert caps_tau.bit_depth == 16
        assert caps_tau.has_tlinear is True

        # Lepton
        lepton = registry.get_plugin("flir_lepton")
        assert lepton.camera_role == CameraRole.THERMAL


class TestThermalPanelSignalsAndWiring:
    def test_all_control_panels_instantiate_and_have_signals(self, qapp):
        boson_panel = BosonControlPanel()
        assert hasattr(boson_panel, "ffc_triggered")
        assert hasattr(boson_panel, "gain_mode_changed")
        assert hasattr(boson_panel, "color_lut_changed")
        assert hasattr(boson_panel, "shutter_position_changed")
        assert hasattr(boson_panel, "radiometric_mode_changed")

        tau2_panel = Tau2ControlPanel()
        assert hasattr(tau2_panel, "connect_requested")
        assert hasattr(tau2_panel, "ffc_triggered")
        assert hasattr(tau2_panel, "gain_mode_changed")
        assert hasattr(tau2_panel, "tlinear_toggled")
        assert hasattr(tau2_panel, "color_lut_changed")

        gige_panel = GigEControlPanel()
        assert hasattr(gige_panel, "command_requested")

        uvc_panel = UVCControlPanel()
        assert hasattr(uvc_panel, "command_requested")

    def test_wire_plugin_panel_connections(self, qapp):
        from thermal_inspection.gui.main_window import InspectionAppWindow
        from thermal_inspection.app import ThermalInspectionApp, AppConfig

        app = ThermalInspectionApp(AppConfig(headless=True), qapp)
        win = InspectionAppWindow(app)

        # Verify that all panels were created and stored in win.camera_panels
        assert "flir_boson" in win.camera_panels
        assert "flir_tau2" in win.camera_panels
        assert "flir_lepton" in win.camera_panels
        assert "flir_firefly" in win.camera_panels
        assert "generic_uvc" in win.camera_panels
        assert "gige_vision" in win.camera_panels

        # Test hotplug auto-focus
        win._on_bus_camera_connected("thermal", {"model": "FLIR Tau 2 640", "plugin_id": "flir_tau2"})
        assert win.cameras_tabs.currentWidget() == win.tau2_panel

        win._on_bus_camera_connected("rgb", {"model": "Logitech BRIO", "plugin_id": "generic_uvc"})
        assert win.cameras_tabs.currentWidget() == win.uvc_panel

        win._on_bus_camera_connected("thermal", {"model": "FLIR Boson 640", "plugin_id": "flir_boson"})
        assert win.cameras_tabs.currentWidget() == win.boson_panel

    def test_update_thermal_resolution_reaches_the_overlay(self, qapp):
        """
        The overlay's coordinate transform depends on thermal_resolution
        tracking the real connected camera (see
        test_overlay_coordinate_transform.py for why). This confirms the
        wiring from the main window's public update method down to the
        overlay actually works, since nothing else exercises it — app.py
        calls win.update_thermal_resolution(), not the overlay directly.
        """
        from thermal_inspection.gui.main_window import InspectionAppWindow
        from thermal_inspection.app import ThermalInspectionApp, AppConfig

        app = ThermalInspectionApp(AppConfig(headless=True), qapp)
        win = InspectionAppWindow(app)

        win.update_thermal_resolution(336, 256)
        assert win.video_widget.overlay.thermal_resolution == (336, 256)

        win.update_thermal_resolution(160, 120)
        assert win.video_widget.overlay.thermal_resolution == (160, 120)

    def test_update_thermal_resolution_ignores_invalid_values(self, qapp):
        from thermal_inspection.gui.main_window import InspectionAppWindow
        from thermal_inspection.app import ThermalInspectionApp, AppConfig

        app = ThermalInspectionApp(AppConfig(headless=True), qapp)
        win = InspectionAppWindow(app)

        win.update_thermal_resolution(640, 512)
        win.update_thermal_resolution(0, 0)
        win.update_thermal_resolution(-1, 200)

        # An invalid update must not clobber the last good resolution.
        assert win.video_widget.overlay.thermal_resolution == (640, 512)
