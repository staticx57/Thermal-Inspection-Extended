"""Grid overlay panel: resolution-aware division presets and the cell-count readout."""
from unittest.mock import MagicMock

import pytest
from PyQt6.QtWidgets import QApplication

from thermal_inspection.gui.main_window import InspectionAppWindow as MainWindow
from thermal_inspection.gui.panels.grid_overlay_panel import GridOverlayPanel


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def panel(qapp):
    return GridOverlayPanel()


def test_no_resolution_yet_means_no_readout_and_a_sane_fallback(panel):
    assert panel.cells_label.text() == ""
    panel.division_buttons[4].click()
    assert panel.get_spacing() == (50, 50)


@pytest.mark.parametrize("res,n,expected", [
    ((640, 512), 4, (160, 128)),
    ((320, 256), 4, (80, 64)),                  # the Boson that "Custom (64x51)" was wrong for
    ((320, 256), 10, (32, 26)),
    ((160, 120), 3, (53, 40)),
    ((160, 120), 10, (16, 12)),
])
def test_division_presets_follow_the_sensor(panel, res, n, expected):
    panel.set_thermal_resolution(*res)
    seen = []
    panel.grid_spacing_changed.connect(lambda x, y: seen.append((x, y)))
    panel.division_buttons[n].click()
    assert panel.get_spacing() == expected and seen[-1] == expected


def test_cell_count_readout_tracks_the_spacing(panel):
    panel.set_thermal_resolution(320, 256)
    assert panel.cells_label.text() == "Thermal image 320×256 px  →  7 × 6 cells"      # 50 px grid
    panel.division_buttons[4].click()
    assert panel.cells_label.text() == "Thermal image 320×256 px  →  4 × 4 cells"
    panel.x_spacing_spin.setValue(100)
    assert "4 × " in panel.cells_label.text() or "→  4" in panel.cells_label.text()


def test_spacing_range_grows_for_big_sensors(panel):
    assert panel.x_spacing_spin.maximum() == 500
    panel.set_thermal_resolution(1280, 1024)
    assert panel.x_spacing_spin.maximum() == 1280


def test_the_boson_specific_preset_is_gone(panel):
    from PyQt6.QtWidgets import QPushButton
    texts = [b.text() for b in panel.findChildren(QPushButton)]
    assert not any("64x51" in t for t in texts)
    assert {"3 × 3", "4 × 4", "10 × 10"} <= set(texts)


def test_nonsense_resolution_is_ignored(panel):
    panel.set_thermal_resolution(0, 100)
    assert panel.thermal_resolution is None


def test_main_window_passes_the_resolution_on():
    w = MagicMock()
    w.video_widget.overlay = MagicMock()
    MainWindow.update_thermal_resolution(w, 320, 256)
    w.video_widget.overlay.set_thermal_resolution.assert_called_once_with(320, 256)
    w.analysis_panel.grid_overlay_panel.set_thermal_resolution.assert_called_once_with(320, 256)
