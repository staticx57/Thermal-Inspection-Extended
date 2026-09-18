"""
Regression test for a GUI panel leak found during a general
best-practices audit (2026-09-03): InspectionAppWindow._on_bus_panel_ready()
swaps in the freshly-activated camera control panel on every
connect/reconnect by calling QTabWidget.removeTab() on the old one and
insertTab()'ing the new one in its place. removeTab() does NOT destroy
the removed widget (Qt: "the page widget itself is not deleted") - the
old panel stayed alive as an orphaned QObject, still wired to the event
bus via its own _wire_plugin_panel() connections, for the rest of the
process. Every reconnect/hot-plug cycle of the same camera added
another one, none ever freed.

Exercises _on_bus_panel_ready directly against a minimal stand-in
object (not a full InspectionAppWindow, which this test suite has never
instantiated - InspectionAppWindow's constructor builds the entire GUI) rather
than mocking Qt's deferred deleteLater() timing.
"""
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from PyQt6.QtWidgets import QTabWidget, QWidget

from thermal_inspection.gui.main_window import InspectionAppWindow


def _fake_main_window(plugin_id="flir_boson"):
    """A duck-typed stand-in carrying only what _on_bus_panel_ready reads/writes.

    thermal_cameras_tabs/rgb_cameras_tabs nest one level under cameras_tabs
    (2026-09-09 Cameras-tab regroup) - _on_bus_panel_ready routes a panel
    into one of these via _container_for_plugin_id's real (unmocked)
    lookup against the real plugin registry, so a fake plugin_id here must
    be one the registry actually knows, and the test must add its panel
    to the SAME container that lookup will resolve to (flir_boson ->
    thermal_cameras_tabs).
    """
    fake = SimpleNamespace()
    fake.cameras_tabs = QTabWidget()
    fake.thermal_cameras_tabs = QTabWidget()
    fake.rgb_cameras_tabs = QTabWidget()
    fake.camera_panels = {}
    fake._wire_plugin_panel = MagicMock()
    fake._container_for_plugin_id = InspectionAppWindow._container_for_plugin_id.__get__(fake)
    fake._select_camera_panel_tab = InspectionAppWindow._select_camera_panel_tab.__get__(fake)

    active_camera = SimpleNamespace(plugin=SimpleNamespace(plugin_id=plugin_id))
    plugin_host = SimpleNamespace(get_active_camera=lambda role: active_camera)
    fake.app = SimpleNamespace(plugin_host=plugin_host)
    return fake


@pytest.mark.unit
class TestPanelReadySwap:

    def test_old_panel_scheduled_for_deletion_on_reconnect(self, qapp):
        fake = _fake_main_window()
        old_panel = QWidget()
        fake.thermal_cameras_tabs.addTab(old_panel, "FLIR Boson")
        fake.camera_panels["flir_boson"] = old_panel

        new_panel = QWidget()
        old_panel.deleteLater = MagicMock(wraps=old_panel.deleteLater)

        InspectionAppWindow._on_bus_panel_ready(fake, "thermal", new_panel)

        old_panel.deleteLater.assert_called_once()
        assert fake.camera_panels["flir_boson"] is new_panel

    def test_tab_count_does_not_grow_across_repeated_reconnects(self, qapp):
        fake = _fake_main_window()
        panel = QWidget()
        fake.thermal_cameras_tabs.addTab(panel, "FLIR Boson")
        fake.camera_panels["flir_boson"] = panel

        for _ in range(5):
            new_panel = QWidget()
            InspectionAppWindow._on_bus_panel_ready(fake, "thermal", new_panel)
            panel = new_panel

        assert fake.thermal_cameras_tabs.count() == 1
