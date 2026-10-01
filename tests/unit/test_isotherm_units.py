"""The Isotherm panel must show every threshold/preset/band in the selected unit, never a hardcoded degrees C."""

import pytest

from thermal_inspection.gui.panels.isotherm_panel import IsothermPanel


@pytest.fixture
def panel(qapp):
    return IsothermPanel()


@pytest.mark.unit
class TestIsothermUnits:
    def test_preset_buttons_start_in_celsius(self, panel):
        assert "50°C" in panel.hotspot_btn.text()
        assert "10°C" in panel.coldspot_btn.text()
        assert "20°C" in panel.normal_btn.text() and "30°C" in panel.normal_btn.text()

    def test_preset_buttons_follow_the_unit(self, panel):
        panel.set_temperature_unit(1)                     # Fahrenheit
        assert "122°F" in panel.hotspot_btn.text() and "°C" not in panel.hotspot_btn.text()
        assert "50°F" in panel.coldspot_btn.text()
        assert "68°F" in panel.normal_btn.text() and "86°F" in panel.normal_btn.text()
        panel.set_temperature_unit(2)                     # Kelvin
        assert "323K" in panel.hotspot_btn.text() and "°" not in panel.hotspot_btn.text()
        panel.set_temperature_unit(3)                     # Y16 (Kelvin x 100)
        assert "32315 Y16" in panel.hotspot_btn.text()
        assert "°C" not in panel.hotspot_btn.text() + panel.coldspot_btn.text() + panel.normal_btn.text()
        panel.set_temperature_unit(0)
        assert "50°C" in panel.hotspot_btn.text()

    def test_band_list_shows_bands_in_the_selected_unit(self, panel):
        panel._load_multiband_preset("comfort_zones")     # Celsius definitions: 18 C .. 24 C
        texts = lambda: [panel.band_list.item(i).text() for i in range(panel.band_list.count())]
        assert any("18.0°C" in t and "24.0°C" in t for t in texts())
        panel.set_temperature_unit(1)
        assert any("64.4°F" in t and "75.2°F" in t for t in texts())
        assert not any("°C" in t for t in texts())
        panel.set_temperature_unit(3)
        assert any("29115 Y16" in t for t in texts())     # (18 + 273.15) * 100 = 29115
        panel.set_temperature_unit(0)
        assert any("18.0°C" in t for t in texts())

    def test_bands_stay_stored_in_celsius_whatever_is_displayed(self, panel):
        panel.set_temperature_unit(1)
        panel._load_multiband_preset("electronics")
        bands = panel.band_manager.get_all_bands()
        assert [round(b.low_temp, 1) for b in bands][:2] == [-40.0, 50.0]   # still Celsius for the manager

    def test_format_temperature_helper(self, panel):
        assert panel.format_temperature(25.0) == "25.0°C"
        panel.set_temperature_unit(1)
        assert panel.format_temperature(25.0) == "77.0°F"
        panel.set_temperature_unit(2)
        assert panel.format_temperature(25.0) == "298.1K" or panel.format_temperature(25.0) == "298.2K"
        panel.set_temperature_unit(3)
        assert panel.format_temperature(25.0) == "29815 Y16"
