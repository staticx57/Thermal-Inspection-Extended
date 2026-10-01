"""
Contract tests for data-shape boundaries between core controllers and GUI panels.

These exist because two real bugs shipped from exactly this class of mismatch:
1. ROIController._get_roi_data() returns {'count', 'rois'} (a structural-change
   summary), but was wired directly to a panel method expecting
   {roi_id: stats_dict} - crashed with "'int' object has no attribute 'get'"
   on the 'count' key the first time an ROI was auto-detected.
2. Even after fixing #1's wiring, the actual per-ROI stats dict used
   'min_temp'/'max_temp'/'mean_temp' keys while the panel display code read
   'temp_min'/'temp_max'/'temp_avg' - no crash, just silently showed nothing.

Each test here pins down one such shape or translation contract so a future
change on either side of the boundary fails loudly in CI instead of silently
in the field.
"""
import pytest
from unittest.mock import MagicMock

from thermal_inspection.core.roi_controller import ROIController
from thermal_inspection.processing.roi_manager import ROIManager
from thermal_inspection.gui.panels.roi_temperature_panel import ROITemperaturePanel
from thermal_inspection.gui.panels.isotherm_panel import IsothermPanel
from thermal_inspection.core.radiometric_controller import RadiometricState
from thermal_inspection.app import ThermalInspectionApp


class TestROIControllerDataShape:
    """Pin down what ROIController._get_roi_data() actually returns."""

    @pytest.mark.unit
    def test_get_roi_data_shape(self):
        controller = ROIController()
        manager = ROIManager()
        manager.create_rectangle_roi(x=10, y=10, w=50, h=50, label="Test")
        controller.set_roi_manager(manager)

        data = controller._get_roi_data()

        assert set(data.keys()) == {'count', 'rois', 'all_rois'}
        assert data['count'] == 1
        assert len(data['rois']) == 1
        assert len(data['all_rois']) == 1       # all_rois also lists hidden ROIs; rois is only the visible ones

    @pytest.mark.unit
    def test_on_rois_changed_receives_structural_shape_not_stats(self):
        """clear_all/delete_roi/auto_detect all notify via the same
        {'count', 'rois'} structural shape - never a per-ROI stats dict."""
        controller = ROIController()
        manager = ROIManager()
        manager.create_rectangle_roi(x=10, y=10, w=50, h=50, label="Test")
        controller.set_roi_manager(manager)

        received = []
        controller.on_rois_changed = lambda data: received.append(data)

        controller.clear_all()

        assert len(received) == 1
        assert set(received[0].keys()) == {'count', 'rois', 'all_rois'}
        assert received[0]['count'] == 0


class TestAppRoiCallbackRouting:
    """ThermalInspectionApp._on_rois_changed must route the structural
    {'count', 'rois'} shape to update_rois(), never to update_roi_data()
    (which expects a per-ROI stats dict) - the original source of the
    ROI Manager panel crash."""

    @pytest.mark.unit
    def test_on_rois_changed_calls_update_rois_not_update_roi_data(self):
        app = ThermalInspectionApp(qt_app=None)
        app.gui = MagicMock()

        app._on_rois_changed({'count': 2, 'rois': ['a', 'b']})

        app.gui.update_rois.assert_called_once_with(['a', 'b'], None)
        app.gui.roi_temp_panel.update_roi_data.assert_not_called()


class TestROITemperaturePanelStatsDisplay:
    """Pin down the exact stats-dict key names the panel reads, and that
    the displayed unit suffix reflects the actual data instead of being
    hardcoded to degC regardless of unit or estimation mode."""

    @pytest.mark.gui
    @pytest.mark.unit
    def test_update_roi_data_displays_correct_values_and_unit(self, qapp):
        panel = ROITemperaturePanel()

        # the panel lists ROIs from update_rois(); feed it the matching ROI object
        from thermal_inspection.processing.roi_manager import ROIManager
        mgr = ROIManager()
        roi = mgr.create_rectangle_roi(x=0, y=0, w=10, h=10, label='Test ROI')
        panel.tracker.records.clear()
        panel.update_rois([roi])
        panel.update_roi_data({roi.roi_id: {
            'roi_name': 'Test ROI', 'temp_avg': 42.5, 'temp_min': 30.0, 'temp_max': 55.0, 'temp_std': 5.0,
            'pixel_count': 1000, 'unit': '°F (est)', 'emissivity': 'global'}})

        from thermal_inspection.gui.panels import roi_temperature_panel as rp
        row = [panel.table.item(0, c).text() for c in range(panel.table.columnCount())]
        assert 'Test ROI' in row[rp.COL_NAME]
        assert row[rp.COL_AVG] == '~42.5 °F'        # estimated readings carry a '~' and keep the app's unit
        assert row[rp.COL_MIN] == '~30.0 °F' and row[rp.COL_MAX] == '~55.0 °F'

    @pytest.mark.gui
    @pytest.mark.unit
    def test_update_roi_data_empty_dict_clears_display(self, qapp):
        panel = ROITemperaturePanel()
        panel.update_roi_data({
            'roi_1': {
                'roi_name': 'x', 'temp_avg': 1, 'temp_min': 1, 'temp_max': 1,
                'temp_std': 0, 'pixel_count': 1, 'unit': '°C',
            }
        })

        panel.update_roi_data({})

        assert panel.stats_label.text() == "No ROI data available"
        assert panel.table.rowCount() == 0


class TestIsothermPanelSignalWiring:
    """Pin down mode-combo text -> emitted mode-string mapping, and the
    enable checkbox -> bool signal."""

    @pytest.mark.gui
    @pytest.mark.unit
    @pytest.mark.parametrize("combo_text,expected_mode", [
        ("Above High (> High)", "above"),
        ("Below Low (< Low)", "below"),
        ("Between Range (Low ≤ T ≤ High)", "between"),
        ("Outside Range (< Low OR > High)", "outside"),
    ])
    def test_mode_combo_emits_correct_mode_string(self, qapp, combo_text, expected_mode):
        panel = IsothermPanel()
        # QComboBox only emits currentTextChanged on an actual change, so
        # start from whichever *other* item guarantees setCurrentText(combo_text)
        # below is a real change, regardless of which case is parametrized.
        target_index = panel.mode_combo.findText(combo_text)
        other_index = (target_index + 1) % panel.mode_combo.count()
        panel.mode_combo.setCurrentIndex(other_index)

        received = []
        panel.mode_changed.connect(lambda m: received.append(m))

        panel.mode_combo.setCurrentText(combo_text)

        assert received == [expected_mode]

    @pytest.mark.gui
    @pytest.mark.unit
    def test_enable_checkbox_emits_bool(self, qapp):
        panel = IsothermPanel()

        received = []
        panel.enabled_changed.connect(lambda v: received.append(v))

        panel.enable_check.setChecked(True)

        assert received == [True]


class TestRadiometricModeTranslation:
    """Pin down ThermalInspectionApp's translation between
    RadiometricController.get_active_mode()'s vocabulary
    ('radiometric'/'estimated'/'agc') and the banner's
    ('16bit'/'8bit'/'none') - two independent vocabularies reconciled by
    hand in app.py's _on_radiometric_state_change, per its own comment."""

    @pytest.mark.unit
    @pytest.mark.parametrize("controller_mode,expected_banner_mode,expected_accuracy", [
        ('radiometric', '16bit', 'verify against a reference'),
        ('estimated', '8bit', 'approximate, ±5-10°C'),
        ('agc', 'none', 'N/A'),
    ])
    def test_active_mode_translation(self, controller_mode, expected_banner_mode, expected_accuracy):
        app = ThermalInspectionApp(qt_app=None)
        app.gui = MagicMock()
        app.radiometric_controller = MagicMock()
        app.radiometric_controller.get_active_mode.return_value = {
            'mode': controller_mode,
            'accuracy': 'n/a',
            'description': f'test description for {controller_mode}',
        }

        state = RadiometricState(enabled=True, capable=True, mode='16-bit T-Linear')
        app._on_radiometric_state_change(state)

        app.gui.radiometric_panel.update_active_mode_status.assert_called_once_with(
            expected_banner_mode, expected_accuracy, f'test description for {controller_mode}'
        )
        app.gui.radiometric_panel.set_radiometric_status.assert_called_once_with(
            state.capable, state.enabled, state.mode
        )
