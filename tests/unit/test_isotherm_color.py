"""Isotherm highlight colour: every choice in the panel must actually reach the overlay (it used to stay red)."""

import numpy as np
import pytest

from thermal_inspection.core.isotherm_manager import ISOTHERM_COLORS, IsothermManager


def _overlay_pixel(manager, celsius=40.0):
    """Paint an all-hot frame and return the BGR value of the highlighted pixels."""
    frame = np.zeros((4, 4, 3), np.uint8)
    y16 = np.full((4, 4), int((celsius + 273.15) * 100), np.uint16)
    manager.set_enabled(True)
    manager.set_low_threshold(10.0)
    manager.set_high_threshold(60.0)
    out = manager.apply_overlay(frame, y16)
    return tuple(int(v) for v in out[0, 0])


@pytest.mark.unit
class TestIsothermColor:
    @pytest.mark.parametrize("name", list(ISOTHERM_COLORS))
    def test_each_colour_is_applied(self, name):
        m = IsothermManager()
        m.set_color(name)
        assert _overlay_pixel(m) == ISOTHERM_COLORS[name]

    @pytest.mark.parametrize("label", ["Red", "Yellow", "Green", "Blue", "Magenta", "Cyan", "White"])
    def test_panel_display_names_are_accepted(self, label):
        """The panel emits the combo text, capitalised - the exact strings that used to be rejected."""
        m = IsothermManager()
        m.set_color(label)
        assert _overlay_pixel(m) == ISOTHERM_COLORS[label.lower()]

    def test_colour_changes_take_effect_after_the_default(self):
        m = IsothermManager()
        assert _overlay_pixel(m) == ISOTHERM_COLORS["red"]          # default
        m.set_color("Green")
        assert _overlay_pixel(m) == ISOTHERM_COLORS["green"]

    def test_unknown_colour_is_still_rejected(self):
        m = IsothermManager()
        m.set_color("Yellow")
        m.set_color("Chartreuse")
        assert _overlay_pixel(m) == ISOTHERM_COLORS["yellow"]

    def test_every_panel_combo_entry_reaches_the_manager(self, qapp):
        from thermal_inspection.gui.panels.isotherm_panel import IsothermPanel
        panel = IsothermPanel()
        m = IsothermManager()
        panel.color_changed.connect(m.set_color)
        seen = set()
        for i in range(panel.color_combo.count()):
            panel.color_combo.setCurrentIndex(i)
            seen.add(_overlay_pixel(m))
        assert len(seen) == panel.color_combo.count(), "each colour choice must give a different overlay colour"
