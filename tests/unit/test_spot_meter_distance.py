import pytest
from PyQt6.QtWidgets import QApplication
from thermal_inspection.gui.panels.spot_meter_panel import SpotMeterPanel, SpotMeterData, SpotMeterListItem


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def test_apply_temperature_stores_distance(qapp):
    panel = SpotMeterPanel()
    panel.add_spot("s1", 10, 20, label="Spot 1")
    panel._apply_temperature("s1", 42.0, "°C", distance_m=1.75)
    assert panel.spots["s1"].distance_m == 1.75


def test_apply_temperature_without_distance_defaults_none(qapp):
    panel = SpotMeterPanel()
    panel.add_spot("s1", 10, 20, label="Spot 1")
    panel._apply_temperature("s1", 42.0, "°C")
    assert panel.spots["s1"].distance_m is None


def test_list_item_display_includes_distance(qapp):
    data = SpotMeterData(id="s1", label="Spot 1", x=10, y=20, temperature=42.0, distance_m=1.75)
    item = SpotMeterListItem(data)
    assert "1.75m" in item.text()


def test_list_item_display_omits_distance_when_none(qapp):
    data = SpotMeterData(id="s1", label="Spot 1", x=10, y=20, temperature=42.0, distance_m=None)
    item = SpotMeterListItem(data)
    # Check that there's no stray "Xm)" from a distance suffix
    text = item.text()
    # Remove the coordinates part to avoid false positives
    text_without_coords = text.replace("(10, 20)", "")
    assert "m)" not in text_without_coords
