"""Environmental compensation panel: emissivity round trip, unit-aware ambient temperature, settings check."""
import pytest
from PyQt6.QtWidgets import QApplication

from thermal_inspection.gui.panels.environmental_compensation_panel import EnvironmentalCompensationPanel
from thermal_inspection.utils.materials import MATERIALS


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def panel(qapp):
    return EnvironmentalCompensationPanel()


class TestEmissivity:
    def test_every_preset_round_trips_exactly(self, panel):
        """int(0.29 * 100) is 28 in floating point: presets like that used to load one step low."""
        seen = []
        panel.emissivity_changed.connect(seen.append)
        for i in range(1, panel.material_combo.count()):
            material = panel.material_combo.itemData(i)
            panel.material_combo.setCurrentIndex(i)
            assert panel.get_emissivity() == pytest.approx(material.emissivity, abs=0.0051), material.name
            assert panel.emissivity_value.text() == f"{material.emissivity:.2f}"
            assert seen[-1] == material.emissivity
        assert len(seen) == len(MATERIALS)

    @pytest.mark.parametrize("value", [0.29, 0.57, 0.58, 0.07, 0.95, 1.0, 0.01])
    def test_set_emissivity_is_not_truncated(self, panel, value):
        panel.set_emissivity(value)
        assert panel.get_emissivity() == pytest.approx(value, abs=0.0051)
        assert panel.emissivity_value.text() == f"{value:.2f}"

    @pytest.mark.parametrize("value", [0.29, 0.57, 0.93])
    def test_set_transmission_is_not_truncated(self, panel, value):
        panel.set_atmospheric_transmission(max(0.7, value))
        assert panel.get_atmospheric_transmission() == pytest.approx(max(0.7, value), abs=0.0051)

    def test_programmatic_value_updates_the_preset_box(self, panel):
        panel.material_combo.setCurrentIndex(1)
        preset = panel.material_combo.currentData()
        panel.set_emissivity(preset.emissivity)
        assert panel.material_combo.currentData() is preset                       # same value: keeps the preset
        panel.set_emissivity(0.37 if abs(preset.emissivity - 0.37) > 0.01 else 0.41)
        assert panel.material_combo.currentIndex() == 0                           # no longer matches: Custom
        assert panel.material_description.text() == "Custom emissivity value"

    def test_dragging_the_slider_switches_to_custom(self, panel):
        panel.material_combo.setCurrentIndex(1)
        panel.emissivity_slider.setValue(33)
        assert panel.material_combo.currentIndex() == 0


class TestAmbientTemperature:
    def test_signals_are_always_celsius(self, panel):
        seen = []
        panel.atmospheric_temp_changed.connect(seen.append)
        panel.set_temperature_unit("F")
        panel.ambient_temp_spinbox.setValue(77.0)                                 # entered in F
        assert seen[-1] == pytest.approx(25.0, abs=0.06)
        panel.set_temperature_unit("K")
        panel.ambient_temp_spinbox.setValue(300.0)
        assert seen[-1] == pytest.approx(26.85, abs=0.06)

    def test_unit_switch_keeps_the_physical_temperature(self, panel):
        panel.set_atmospheric_temperature(25.0)
        seen = []
        panel.atmospheric_temp_changed.connect(seen.append)
        panel.set_temperature_unit("F")
        assert panel.ambient_temp_spinbox.value() == pytest.approx(77.0) and panel.ambient_temp_spinbox.suffix() == " °F"
        assert seen == [] and panel.get_atmospheric_temperature() == pytest.approx(25.0)    # nothing re-emitted
        panel.set_temperature_unit("K")
        assert panel.ambient_temp_spinbox.value() == pytest.approx(298.15, abs=0.06)
        panel.set_temperature_unit("C")
        assert panel.ambient_temp_spinbox.value() == pytest.approx(25.0)

    def test_range_follows_the_unit(self, panel):
        panel.set_temperature_unit("F")
        assert panel.ambient_temp_spinbox.minimum() == pytest.approx(-40.0)
        assert panel.ambient_temp_spinbox.maximum() == pytest.approx(176.0)

    def test_programmatic_set_is_celsius_and_silent(self, panel):
        seen = []
        panel.atmospheric_temp_changed.connect(seen.append)
        panel.set_temperature_unit("F")
        panel.set_atmospheric_temperature(0.0)
        assert panel.ambient_temp_spinbox.value() == pytest.approx(32.0) and seen == []

    def test_unknown_unit_is_celsius(self, panel):
        panel.set_temperature_unit("Y16")
        assert panel.unit == "C"


class TestSettingsCheck:
    def test_no_invented_accuracy_numbers(self, panel):
        panel.set_emissivity(0.95)
        text = panel.accuracy_label.text() + panel.accuracy_note.text()
        assert "±" not in text                                                    # no made-up degC figures
        assert "camera's own calibration" in panel.accuracy_note.text()

    @pytest.mark.parametrize("e,t,level", [(0.95, 1.0, "good"), (0.7, 1.0, "fair"), (0.95, 0.9, "fair"),
                                           (0.3, 1.0, "poor"), (0.95, 0.8, "poor")])
    def test_levels(self, panel, e, t, level):
        panel.set_emissivity(e)
        panel.set_atmospheric_transmission(t)
        assert panel.check_settings()[0] == level

    def test_low_emissivity_advice_is_actionable(self, panel):
        panel.set_emissivity(0.1)
        _, headline, advice = panel.check_settings()
        assert "reflect" in advice and "tape" in advice and headline == "Check these settings"


class TestRadiometricGate:
    def test_disabled_with_an_explanation(self, panel):
        panel.set_radiometric(False)
        assert not panel.controls.isEnabled() and not panel.not_radiometric_note.isHidden()
        panel.set_radiometric(True)
        assert panel.controls.isEnabled() and panel.not_radiometric_note.isHidden()
