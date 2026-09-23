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
    received = []
    panel.finish_scan_requested.connect(lambda: received.append(True))
    panel._finish_button.click()
    assert received == [True]


def test_reset_button_emits_signal(qapp):
    from thermal_inspection.gui.panels.mapping_fusion_panel import MappingFusionPanel
    panel = MappingFusionPanel()
    received = []
    panel.reset_requested.connect(lambda: received.append(True))
    panel._reset_button.click()
    assert received == [True]


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
