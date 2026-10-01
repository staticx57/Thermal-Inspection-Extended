"""Gradient panel: sensitivity is wired, and the threshold follows the selected unit (no hardcoded degrees C)."""

import pytest

from thermal_inspection.gui.panels.gradient_overlay_panel import GradientOverlayPanel


@pytest.fixture
def panel(qapp):
    return GradientOverlayPanel()


@pytest.mark.unit
class TestGradientPanel:
    def test_sensitivity_slider_emits(self, panel):
        seen = []
        panel.gradient_sensitivity_changed.connect(seen.append)
        panel.sensitivity_slider.setValue(80)
        assert seen == [80]

    def test_default_is_celsius_per_pixel(self, panel):
        assert panel.threshold_spin.suffix().strip() == "°C/px"
        assert panel.threshold_base() == pytest.approx(0.2)

    def test_threshold_follows_the_unit_and_keeps_the_same_physical_value(self, panel):
        panel.set_temperature_unit("F")
        assert panel.threshold_spin.suffix().strip() == "°F/px"
        assert panel.threshold_spin.value() == pytest.approx(0.36)    # 0.2 C/px = 0.36 F/px (a difference: no offset)
        assert panel.threshold_base() == pytest.approx(0.2)
        panel.set_temperature_unit("RAW")
        assert panel.threshold_spin.suffix().strip() == "Y16/px"
        assert panel.threshold_spin.value() == pytest.approx(20)      # 0.2 C = 20 counts
        panel.set_temperature_unit("K")
        assert panel.threshold_spin.suffix().strip() == "K/px" and panel.threshold_spin.value() == pytest.approx(0.2)
        panel.set_temperature_unit("C")
        assert panel.threshold_spin.value() == pytest.approx(0.2)

    def test_changing_unit_does_not_emit_a_threshold_change(self, panel):
        seen = []
        panel.gradient_threshold_changed.connect(seen.append)
        panel.set_temperature_unit("F")
        assert seen == []

    def test_user_edits_are_emitted_in_processor_units(self, panel):
        seen = []
        panel.gradient_threshold_changed.connect(seen.append)
        panel.set_temperature_unit("F")
        panel.threshold_spin.setValue(0.9)                            # 0.9 F/px = 0.5 C/px
        assert seen[-1] == pytest.approx(0.5)

    def test_presets_apply_in_the_displayed_unit(self, panel):
        panel.set_temperature_unit("F")
        seen = []
        panel.gradient_threshold_changed.connect(seen.append)
        panel._apply_preset(0.5, 50, "magnitude")                     # preset defined as 0.5 C/px
        assert panel.threshold_spin.value() == pytest.approx(0.9)
        assert seen[-1] == pytest.approx(0.5)
        assert panel.get_settings()["threshold"] == pytest.approx(0.5)

    def test_non_radiometric_source_shows_counts_per_pixel(self, panel):
        panel.set_radiometric(False)
        assert panel.threshold_spin.suffix().strip() == "counts/px"
        assert panel.threshold_base() == pytest.approx(6.0)           # default rescaled for counts (0.2 x 30)
        panel.set_temperature_unit("F")                               # no temperature: unit doesn't apply
        assert panel.threshold_spin.suffix().strip() == "counts/px"
        assert panel.threshold_base() == pytest.approx(6.0)
        panel.set_radiometric(True)
        assert panel.threshold_spin.suffix().strip() == "°F/px"
        assert panel.threshold_base() == pytest.approx(0.2)           # back to the degree default

    def test_switching_source_kind_tells_the_processor_the_new_threshold(self, panel):
        seen = []
        panel.gradient_threshold_changed.connect(seen.append)
        panel.set_radiometric(False)
        assert seen[-1] == pytest.approx(6.0)
        panel.set_radiometric(True)
        assert seen[-1] == pytest.approx(0.2)

    def test_presets_in_counts_on_a_non_radiometric_camera(self, panel):
        panel.set_radiometric(False)
        panel._apply_preset(0.5, 50, "magnitude")
        assert panel.threshold_base() == pytest.approx(15.0)          # 0.5 x 30
