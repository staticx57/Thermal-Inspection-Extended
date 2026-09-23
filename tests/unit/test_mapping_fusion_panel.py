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


def test_point_cloud_view_not_stuck_on_no_hardware_placeholder(qapp):
    """C2: the viewport must not be permanently hidden behind the 'no
    hardware depth sensor' placeholder - this panel shows the WORLD point
    cloud (from WorldMapper), not a live RealSense preview, so that gate
    doesn't apply here."""
    from thermal_inspection.gui.panels.mapping_fusion_panel import MappingFusionPanel
    from thermal_inspection.gui.panels.fusion_3d_panel import GL_AVAILABLE
    panel = MappingFusionPanel()
    if not GL_AVAILABLE:
        pytest.skip("PyOpenGL not installed - placeholder-visibility check needs the real GL view")
    # isHidden() (not isVisible()) - the panel is never shown/realized in
    # this headless test, so isVisible() would read False regardless of
    # the internal show()/hide() calls this test actually cares about.
    assert panel.point_cloud_view._no_source_label.isHidden()


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


def test_update_point_cloud_delegates_to_view(qapp):
    import numpy as np
    from thermal_inspection.gui.panels.mapping_fusion_panel import MappingFusionPanel
    panel = MappingFusionPanel()
    vertices = np.zeros((10, 3), dtype=np.float32)
    colors = np.ones((10, 4), dtype=np.float32)
    # Should not raise - actual rendering is Fusion3DPointCloudView's own
    # already-tested responsibility.
    panel.update_point_cloud(vertices, colors)


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
