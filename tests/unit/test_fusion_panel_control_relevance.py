"""
Regression tests for the 2026-09-06 fusion-panel maturity fixes:

1. The General Fusion Settings group shows 4 controls (Alpha, Priority,
   Strength, Fuzziness) for every mode, but each is only wired to a
   subset of the 12 fusion modes - turning one that doesn't apply
   silently did nothing, with no indication why. They're now
   enabled/disabled per-mode instead.
2. "Balanced" was removed from the Priority combo - FusionProcessor.set_priority()
   only ever accepted 'thermal'/'rgb', and main_window.py silently mapped
   'balanced' to 'thermal', so it was never a real third choice.
3. The Strength/Fuzziness sliders' GUI-displayed defaults (70/30) didn't
   match FusionProcessor's own actual initial engine values
   (fusion_intensity=0.5, edge_blur_kernel=0) - a fresh app launch ran at
   different settings than the panel displayed until the sliders were
   touched. Now matched.
"""
import pytest

from thermal_inspection.gui.panels.fusion_panel import FusionPanel


@pytest.mark.unit
class TestConstructionTimeStateIsCorrect:
    """
    QComboBox.addItem() fires currentIndexChanged synchronously for the
    first item added to an empty combo, so _on_fusion_mode_changed ran
    once during the mode-combo population loop inside _init_ui() - at
    which point none of the widgets _update_fusion_settings references
    existed yet (they're constructed later in the same method). The
    resulting AttributeError doesn't propagate normally (PyQt slot
    exceptions go through sys.excepthook), so the panel silently kept its
    raw construction-time widget defaults - confirmed live: a fresh app
    launch on Alpha Blend showed Edge Enhanced's settings widget under the
    placeholder title "Advanced Mode Settings", and Strength/Fuzziness
    weren't dimmed despite Alpha Blend not using either.
    """
    def test_initial_mode_title_is_correct_not_the_construction_placeholder(self, qapp):
        panel = FusionPanel()
        assert panel.fusion_mode_combo.currentData() == 'alpha_blend'
        assert panel.fusion_settings_group.title() == "Advanced Settings (None)"

    def test_initial_mode_widgets_are_actually_hidden(self, qapp):
        panel = FusionPanel()
        # edge_settings_widget defaults to visible at construction (it's
        # never explicitly hidden until _update_fusion_settings runs) -
        # alpha_blend has no mode-specific widget, so it should end up hidden.
        assert panel.edge_settings_widget.isHidden()

    def test_initial_mode_dead_controls_are_dimmed(self, qapp):
        panel = FusionPanel()
        # alpha_blend doesn't use Strength or Fuzziness.
        assert not panel.fusion_strength_slider.isEnabled()
        assert panel.fusion_strength_slider.graphicsEffect() is not None
        assert not panel.fusion_fuzziness_slider.isEnabled()
        assert panel.fusion_fuzziness_slider.graphicsEffect() is not None
        # ...but does use Alpha and Priority.
        assert panel.alpha_slider.isEnabled()
        assert panel.alpha_slider.graphicsEffect() is None
        assert panel.priority_combo.isEnabled()


@pytest.mark.unit
class TestEdgeModeMerge:
    """
    Enhanced Edge Highlight was merged into Edge Enhanced (2026-09-07)
    after two rounds of trying to differentiate them still left them
    reading as the same mode on real camera footage ("they are still the
    same mode... they do the same thing even if the algorithm is
    slightly different"). detail_balance (the former mode's whole reason
    to exist) is now just one more optional setting inside Edge Enhanced's
    own settings group, alongside its pre-existing Sensitivity/Line Size.
    """
    def test_enhanced_edge_highlight_is_gone_from_available_modes(self):
        from thermal_inspection.processing.fusion_processor import FusionProcessor
        assert 'enhanced_edge_highlight' not in FusionProcessor.AVAILABLE_FUSION_MODES
        assert 'enhanced_edge_highlight' not in FusionProcessor.FUSION_MODE_LABELS

    def test_no_separate_enhanced_edge_widgets_remain(self, qapp):
        panel = FusionPanel()
        assert not hasattr(panel, 'enhanced_edge_settings_widget')
        assert not hasattr(panel, 'enhanced_edge_sensitivity_slider')
        assert not hasattr(panel, 'enhanced_edge_line_size_slider')

    def test_edge_enhanced_keeps_its_own_sensitivity_control(self, qapp):
        panel = FusionPanel()
        assert panel.edge_strength_slider.value() == 50

    def test_detail_balance_now_lives_in_edge_enhanced_settings(self, qapp):
        panel = FusionPanel()
        panel._update_fusion_settings("edge_enhanced")
        assert not panel.edge_settings_widget.isHidden()
        assert not panel.detail_balance_slider.isHidden()
        assert panel.detail_balance_slider.value() == 0  # matches the new off-by-default engine default

    def test_edge_enhanced_no_longer_has_a_duplicate_fuzziness_slider(self, qapp):
        # Removed 2026-09-07: it and General Fusion Settings' own
        # "Fuzziness" both set the same edge_blur_kernel, as two
        # independent, unsynced widgets once General Fuzziness was
        # correctly gated to enable/disable per-mode.
        panel = FusionPanel()
        assert not hasattr(panel, 'edge_fuzziness_slider')


@pytest.mark.unit
class TestGeneralControlDefaultsMatchEngine:
    def test_alpha_default_matches_fusionprocessor(self, qapp):
        panel = FusionPanel()
        assert panel.alpha_slider.value() == 50  # FusionProcessor.__init__(alpha=0.5)

    def test_strength_default_matches_fusionprocessor(self, qapp):
        panel = FusionPanel()
        # FusionProcessor.fusion_intensity defaults to 0.5 (config.get with
        # no matching config key ever set) - the GUI previously showed 70.
        assert panel.fusion_strength_slider.value() == 50
        assert panel.fusion_strength_value.text() == "50"

    def test_fuzziness_default_matches_fusionprocessor(self, qapp):
        panel = FusionPanel()
        # FusionProcessor.edge_blur_kernel defaults to 0 (sharp edges) -
        # the GUI previously showed 30 (-> kernel_size=4).
        assert panel.fusion_fuzziness_slider.value() == 0
        assert panel.fusion_fuzziness_value.text() == "0"


@pytest.mark.unit
class TestBalancedPriorityRemoved:
    def test_priority_combo_has_only_two_real_options(self, qapp):
        panel = FusionPanel()
        items = [panel.priority_combo.itemText(i) for i in range(panel.priority_combo.count())]
        assert items == ["Thermal", "RGB"]


@pytest.mark.unit
class TestGeneralControlsEnabledByMode:
    """
    Each row: (mode, alpha_enabled, priority_enabled, strength_enabled, fuzziness_enabled).
    Chosen to cover: a mode using all 4 (edge_enhanced), the one mode using
    Alpha (alpha_blend), a mode using none of Alpha/Priority/Strength/Fuzziness
    except Strength (thermal_contours), and a mode using none at all (side_by_side).
    """
    @pytest.mark.parametrize("mode,alpha,priority,strength,fuzz", [
        ("alpha_blend", True, True, False, False),
        ("detail_inject", False, False, True, False),
        ("relief_fusion", False, False, True, False),
        ("edge_enhanced", False, True, True, True),
        ("thermal_overlay", False, True, True, False),
        ("side_by_side", False, True, False, False),
        ("picture_in_picture", False, True, False, False),
        ("max_intensity", False, False, False, False),
        ("feature_weighted", False, True, True, False),
        ("thermal_contours", False, False, True, False),
        ("laplacian_pyramid", False, False, True, False),
        ("pca_fusion", False, True, True, False),
        ("guided_filter_fusion", False, True, True, False),
    ])
    def test_control_enabled_state_matches_mode(self, qapp, mode, alpha, priority, strength, fuzz):
        panel = FusionPanel()
        panel._update_fusion_settings(mode)
        assert panel.alpha_slider.isEnabled() == alpha, f"alpha for {mode}"
        assert panel.priority_combo.isEnabled() == priority, f"priority for {mode}"
        assert panel.fusion_strength_slider.isEnabled() == strength, f"strength for {mode}"
        assert panel.fusion_fuzziness_slider.isEnabled() == fuzz, f"fuzziness for {mode}"


@pytest.mark.unit
class TestDeadControlsAreVisuallyDimmed:
    """
    setEnabled(False) alone isn't enough: none of this app's 9 themes
    define a QSlider/QComboBox :disabled style (only QPushButton does),
    so a disabled slider rendered with this app's QSS looks pixel-
    identical to an enabled one - confirmed live. A QGraphicsOpacityEffect
    dims at the paint-compositing level, which no QSS rule can override.
    """
    def test_disabled_control_gets_an_opacity_effect(self, qapp):
        panel = FusionPanel()
        panel._update_fusion_settings("alpha_blend")  # Strength/Fuzziness both dead here
        assert panel.fusion_strength_slider.graphicsEffect() is not None
        assert panel.fusion_fuzziness_slider.graphicsEffect() is not None
        assert panel.fusion_strength_slider.graphicsEffect().opacity() < 1.0

    def test_enabled_control_has_no_opacity_effect(self, qapp):
        panel = FusionPanel()
        panel._update_fusion_settings("alpha_blend")  # Alpha/Priority both live here
        assert panel.alpha_slider.graphicsEffect() is None
        assert panel.priority_combo.graphicsEffect() is None

    def test_dimming_updates_when_mode_changes(self, qapp):
        panel = FusionPanel()
        panel._update_fusion_settings("alpha_blend")  # Strength dead
        assert panel.fusion_strength_slider.graphicsEffect() is not None
        panel._update_fusion_settings("edge_enhanced")  # Strength live
        assert panel.fusion_strength_slider.graphicsEffect() is None


@pytest.mark.unit
class TestNewModeSettingsWidgets:
    def test_thermal_overlay_shows_its_own_settings(self, qapp):
        # isHidden() (the widget's own show/hide flag), not isVisible()
        # (which also depends on the whole ancestor chain being on-screen
        # - false here since the panel itself is never shown in this test).
        panel = FusionPanel()
        panel._update_fusion_settings("thermal_overlay")
        assert not panel.overlay_settings_widget.isHidden()
        assert panel.pip_settings_widget.isHidden()
        assert panel.detail_settings_widget.isHidden()

    def test_picture_in_picture_shows_its_own_settings(self, qapp):
        panel = FusionPanel()
        panel._update_fusion_settings("picture_in_picture")
        assert not panel.pip_settings_widget.isHidden()
        assert panel.overlay_settings_widget.isHidden()

    def test_relief_light_direction_row_only_visible_for_relief_fusion(self, qapp):
        panel = FusionPanel()
        panel._update_fusion_settings("relief_fusion")
        assert not panel.detail_settings_widget.isHidden()
        assert not panel.relief_light_direction_row.isHidden()

        panel._update_fusion_settings("detail_inject")
        assert not panel.detail_settings_widget.isHidden()
        assert panel.relief_light_direction_row.isHidden()

    def test_detail_settings_title_reflects_actual_mode(self, qapp):
        panel = FusionPanel()
        panel._update_fusion_settings("relief_fusion")
        assert panel.fusion_settings_group.title() == "Relief Fusion Settings"
        panel._update_fusion_settings("detail_inject")
        assert panel.fusion_settings_group.title() == "Detail Injection Settings"

    def test_contour_fill_checkbox_present_and_wired(self, qapp):
        panel = FusionPanel()
        panel._update_fusion_settings("thermal_contours")
        assert not panel.contour_settings_widget.isHidden()
        assert not panel.contour_fill_checkbox.isChecked()  # off by default

        received = []
        panel.contour_fill_changed.connect(received.append)
        panel.contour_fill_checkbox.setChecked(True)
        assert received == [True]
