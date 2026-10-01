import pytest
from PyQt6.QtWidgets import QApplication


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def test_panel_constructs(qapp):
    from thermal_inspection.gui.panels.mapping_fusion_panel import MappingFusionPanel
    panel = MappingFusionPanel()
    assert panel is not None


def test_start_button_emits_signal(qapp):
    from thermal_inspection.gui.panels.mapping_fusion_panel import MappingFusionPanel
    panel = MappingFusionPanel()
    received = []
    panel.start_scan_requested.connect(lambda: received.append(True))
    panel._start_button.click()
    assert received == [True]


def test_finish_button_emits_signal(qapp):
    from thermal_inspection.gui.panels.mapping_fusion_panel import MappingFusionPanel
    panel = MappingFusionPanel()
    # I11: Finish is only enabled while actually scanning - QPushButton's
    # own click() is a no-op (doesn't emit clicked()) when disabled, and
    # the panel starts out idle (Finish disabled), so put it in the
    # "scanning" state first, the same way real usage would via
    # set_status() after Start Mapping succeeds.
    panel.set_status("scanning", "n/a", 0)
    received = []
    panel.finish_scan_requested.connect(lambda: received.append(True))
    panel._finish_button.click()
    assert received == [True]


def test_reset_button_emits_signal(qapp):
    from thermal_inspection.gui.panels.mapping_fusion_panel import MappingFusionPanel
    panel = MappingFusionPanel()
    # I11: Reset is only enabled once there's something to reset - the
    # panel starts out idle/empty (Reset disabled), so give it a non-idle
    # state first.
    panel.set_status("mapped", "good", 100)
    received = []
    panel.reset_requested.connect(lambda: received.append(True))
    panel._reset_button.click()
    assert received == [True]


def test_start_button_disabled_while_scanning(qapp):
    from thermal_inspection.gui.panels.mapping_fusion_panel import MappingFusionPanel
    panel = MappingFusionPanel()
    assert panel._start_button.isEnabled()  # idle: Start allowed
    panel.set_status("scanning", "n/a", 0)
    assert not panel._start_button.isEnabled()
    assert panel._finish_button.isEnabled()


def test_finish_button_disabled_when_idle_or_mapped(qapp):
    from thermal_inspection.gui.panels.mapping_fusion_panel import MappingFusionPanel
    panel = MappingFusionPanel()
    assert not panel._finish_button.isEnabled()  # idle
    panel.set_status("mapped", "good", 100)
    assert not panel._finish_button.isEnabled()  # mapped, not scanning


def test_reset_button_disabled_when_idle_with_no_points(qapp):
    from thermal_inspection.gui.panels.mapping_fusion_panel import MappingFusionPanel
    panel = MappingFusionPanel()
    assert not panel._reset_button.isEnabled()
    panel.set_status("scanning", "n/a", 0)
    assert panel._reset_button.isEnabled()  # something to reset (an active scan)


def test_texture_source_combo_emits_signal(qapp):
    from thermal_inspection.gui.panels.mapping_fusion_panel import MappingFusionPanel
    panel = MappingFusionPanel()
    received = []
    panel.texture_source_changed.connect(received.append)
    panel._texture_source_combo.setCurrentIndex(1)
    assert len(received) == 1
    assert received[0] in ("thermal", "rgb", "blend")


def test_set_status_updates_label_text(qapp):
    from thermal_inspection.gui.panels.mapping_fusion_panel import MappingFusionPanel
    panel = MappingFusionPanel()
    panel.set_status("mapped", "good", 12345)
    assert "mapped" in panel._status_label.text().lower()
    assert "12345" in panel._status_label.text() or "12,345" in panel._status_label.text()
    assert "good" in panel._status_label.text().lower()


def test_save_button_emits_signal(qapp):
    from thermal_inspection.gui.panels.mapping_fusion_panel import MappingFusionPanel
    panel = MappingFusionPanel()
    received = []
    panel.save_requested.connect(lambda: received.append(True))
    panel._save_button.click()
    assert received == [True]


def test_load_button_emits_signal(qapp):
    from thermal_inspection.gui.panels.mapping_fusion_panel import MappingFusionPanel
    panel = MappingFusionPanel()
    received = []
    panel.load_requested.connect(lambda: received.append(True))
    panel._load_button.click()
    assert received == [True]


def test_set_status_shows_lost_message(qapp):
    from thermal_inspection.gui.panels.mapping_fusion_panel import MappingFusionPanel
    panel = MappingFusionPanel()
    panel.set_status("mapped", "lost", 500)
    assert "mapped area" in panel._status_label.text().lower() or "reset world" in panel._status_label.text().lower()


def test_view_mode_combo_emits_key(qapp):
    from thermal_inspection.gui.panels.mapping_fusion_panel import MappingFusionPanel
    panel = MappingFusionPanel()
    got = []
    panel.view_mode_changed.connect(got.append)
    panel._view_mode_combo.setCurrentIndex(panel._view_mode_combo.findData("peak"))
    assert got == ["peak"]


def test_thermal_summary_shows_and_hides(qapp):
    from thermal_inspection.gui.panels.mapping_fusion_panel import MappingFusionPanel
    panel = MappingFusionPanel()
    panel.set_status("mapped", "good", 100)
    panel.set_thermal_summary("Live: 20.0 to 80.0 C")
    assert not panel._thermal_label.isHidden() and "80.0" in panel._thermal_label.text()
    panel.set_status("idle", "n/a", 0)             # leaving the mapped state clears stale temperatures
    assert panel._thermal_label.isHidden()


def test_export_button_only_when_mapped(qapp):
    from thermal_inspection.gui.panels.mapping_fusion_panel import MappingFusionPanel
    panel = MappingFusionPanel()
    assert not panel._export_button.isEnabled()
    panel.set_status("mapped", "good", 10)
    assert panel._export_button.isEnabled()
    got = []
    panel.export_thermal_requested.connect(lambda: got.append(1))
    panel._export_button.click()
    assert got == [1]


def test_panel_no_longer_embeds_a_point_cloud(qapp):
    """The 3D world is drawn full-size in the main view (WorldViewer); the settings tab holds controls only."""
    from thermal_inspection.gui.panels.mapping_fusion_panel import MappingFusionPanel
    panel = MappingFusionPanel()
    assert not hasattr(panel, "point_cloud_view") and not hasattr(panel, "update_point_cloud")


def test_hotspot_list_fills_and_emits_selection(qapp):
    from thermal_inspection.gui.panels.mapping_fusion_panel import MappingFusionPanel
    from thermal_inspection.processing.world_thermal import Marker
    panel = MappingFusionPanel()
    panel.set_status("mapped", "good", 100)
    panel.set_hotspots([Marker("H1", (0.1, 0.2, 2.0), 80.0, "hot", 5),
                        Marker("C1", (1.0, 0.0, 2.0), -12.0, "cool", 9)], "F")
    texts = [panel._hotspot_list.item(i).text() for i in range(panel._hotspot_list.count())]
    assert "H1" in texts[0] and "176.0" in texts[0]              # absolute temperature in the app's unit (F)
    assert "C1" in texts[1] and "-21.6" in texts[1]              # a difference: scaled by 1.8, no +32 offset
    got = []
    panel.hotspot_selected.connect(got.append)
    panel._hotspot_list.setCurrentRow(1)
    assert got == [1]
    panel.set_status("idle", "n/a", 0)                           # leaving the mapped state empties the list
    assert panel._hotspot_list.count() == 0

