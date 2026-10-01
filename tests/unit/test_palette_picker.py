"""
Tests for the expanded palette set and the swatch-preview palette picker.
"""

from collections import Counter

import numpy as np
import pytest

from thermal_inspection.processing.palette_manager import (
    PALETTE_CATEGORIES, PaletteManager, PaletteType,
)

ADDED = [
    "green_hot", "red_hot", "copper", "afmhot", "gnuplot2", "ylorrd",
    "nipy_spectral", "ylgnbu", "cmrmap", "seismic", "rdylbu", "brbg",
]


@pytest.mark.unit
class TestPaletteSet:
    def test_added_palettes_exist(self):
        values = {p.value for p in PaletteType}
        assert set(ADDED) <= values

    def test_every_palette_has_a_valid_lut(self):
        manager = PaletteManager()
        for palette in PaletteType:
            lut = manager.get_palette_lut(palette)
            assert lut.shape == (256, 3), palette
            assert lut.dtype == np.uint8, palette

    def test_every_palette_is_listed_in_exactly_one_category(self):
        listed = Counter(p for _, palettes in PALETTE_CATEGORIES for p in palettes)
        assert set(listed) == set(PaletteType)
        assert all(count == 1 for count in listed.values())

    def test_get_palette_lut_matches_current_lut_for_active_palette(self):
        manager = PaletteManager()
        manager.set_global_palette(PaletteType.SEISMIC)
        assert np.array_equal(manager.get_current_palette_lut(),
                              manager.get_palette_lut(PaletteType.SEISMIC))

    def test_added_palettes_apply_to_a_frame(self):
        manager = PaletteManager()
        gradient = np.tile(np.linspace(0, 255, 64, dtype=np.uint8), (8, 1))
        for value in ADDED:
            manager.set_global_palette(PaletteType(value))
            out = manager.apply_palette(gradient, manager.get_global_palette())
            assert out.shape == (8, 64, 3), value


@pytest.mark.unit
class TestSwatchPreview:
    def test_swatch_count_is_4_to_8_or_none_when_cramped(self):
        from thermal_inspection.gui.widgets.palette_combo import swatch_count, strip_width
        assert swatch_count(0) == 0                # no room: show the name alone
        assert swatch_count(strip_width(4) - 1) == 0
        assert swatch_count(strip_width(4)) == 4
        assert swatch_count(10_000) == 8
        counts = [swatch_count(w) for w in range(0, 400, 5)]
        assert counts == sorted(counts)            # more room never means fewer swatches
        assert set(counts) <= {0, 4, 5, 6, 7, 8}

    def test_name_is_never_truncated_for_the_sake_of_swatches(self, qapp):
        """A narrow combo drops the swatches instead of eliding the palette name."""
        from thermal_inspection.gui.widgets.palette_combo import PaletteComboBox, swatch_count
        combo = PaletteComboBox()
        combo.setCurrentValue("nipy_spectral")
        name_w = combo.fontMetrics().horizontalAdvance("Full Spectrum")
        assert swatch_count(name_w + 10 + 20 - name_w - 10) == 0   # e.g. ~20px spare: no strip

    def test_swatch_colors_run_cold_to_hot(self):
        from thermal_inspection.gui.widgets.palette_combo import swatch_colors
        colors = swatch_colors("white_hot", 8)
        assert len(colors) == 8
        lightness = [c.lightness() for c in colors]
        assert lightness == sorted(lightness) and lightness[0] < lightness[-1]
        # black_hot is the same ramp reversed
        inv = [c.lightness() for c in swatch_colors("black_hot", 8)]
        assert inv == sorted(inv, reverse=True)

    def test_every_palette_has_a_friendly_unique_name(self):
        from thermal_inspection.processing.palette_manager import PALETTE_DISPLAY_NAMES
        assert set(PALETTE_DISPLAY_NAMES) == set(PaletteType)
        names = list(PALETTE_DISPLAY_NAMES.values())
        assert len(set(names)) == len(names)
        # friendly, not the internal id (no snake_case / lowercase-run-together ids)
        assert all("_" not in n and n[0].isupper() for n in names)

    def test_combo_shows_friendly_names_and_keeps_ids_as_data(self, qapp):
        from thermal_inspection.gui.widgets.palette_combo import PaletteComboBox
        from thermal_inspection.processing.palette_manager import palette_display_name
        combo = PaletteComboBox()
        data = [combo.itemData(i) for i in range(combo.count()) if combo.itemData(i)]
        assert set(data) == {p.value for p in PaletteType}
        texts = [combo.itemText(i).strip() for i in range(combo.count())]
        assert palette_display_name(PaletteType.WHITE_HOT) in texts       # "White Hot"
        assert "white_hot" not in texts and "rainbow_rev" not in texts    # no raw ids shown
        headers = [i for i in range(combo.count()) if combo.itemText(i).startswith("───")]
        assert len(headers) == len(PALETTE_CATEGORIES)
        assert all(not combo.model().item(i).isEnabled() for i in headers)

    def test_selection_emits_internal_id_not_display_text(self, qapp):
        """The app maps the emitted string straight to PaletteType - it must be the id."""
        from thermal_inspection.gui.widgets.palette_combo import PaletteComboBox
        combo = PaletteComboBox()
        seen = []
        combo.paletteValueChanged.connect(seen.append)
        for value in ("ironbow", "rainbow_rev", "nipy_spectral"):
            assert combo.setCurrentValue(value)
            assert combo.currentValue() == value
        assert seen[-3:] == ["ironbow", "rainbow_rev", "nipy_spectral"]
        assert all(PaletteType(v) for v in seen)
        assert combo.findValue("Rainbow Rev") == combo.findValue("rainbow_rev") >= 0   # legacy/loose ids
        assert combo.findValue("does_not_exist") == -1

    def test_combo_paints_without_error(self, qapp):
        from thermal_inspection.gui.widgets.palette_combo import PaletteComboBox
        combo = PaletteComboBox()
        combo.resize(300, 30)
        combo.setCurrentValue("viridis")
        assert not combo.grab().isNull()
        combo.resize(120, 30)                      # cramped: must still paint (4 swatches)
        assert not combo.grab().isNull()
