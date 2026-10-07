"""Deleting a spot meter must remove it from the overlay as well as from the list (only Clear All used to)."""
from unittest.mock import MagicMock

from thermal_inspection.gui.main_window import InspectionAppWindow
from thermal_inspection.gui.panels.spot_meter_panel import SpotMeterPanel
from thermal_inspection.gui.widgets.measurement_point import MeasurementPoint


class _Win:
    pass


def _setup(qapp):
    w = _Win()
    w.measurement_points = []
    w.video_widget = MagicMock()
    w.analysis_panel = MagicMock()
    panel = SpotMeterPanel()
    w.analysis_panel.spot_meter_panel = panel
    panel.spot_deleted.connect(lambda sid: InspectionAppWindow._on_spot_deleted(w, sid))
    for i, (x, y) in enumerate([(10, 10), (20, 20), (30, 30)], 1):
        w.measurement_points.append(MeasurementPoint(x=x, y=y, label=f"SP{i}"))
        panel.add_spot(f"spot_{i}_{x}_{y}", x, y, f"SP{i}")
    return w, panel


def test_panel_can_look_up_a_spot_by_id(qapp):
    _, panel = _setup(qapp)
    assert panel.get_spot("spot_2_20_20").label == "SP2"
    assert panel.get_spot("nope") is None


def test_deleting_one_spot_removes_it_from_the_overlay(qapp):
    w, panel = _setup(qapp)
    panel.spot_list.item(1).setSelected(True)
    panel._on_delete_clicked()
    assert [p.label for p in w.measurement_points] == ["SP1", "SP3"]
    shown = w.video_widget.update_measurement_points.call_args[0][0]
    assert [p.label for p in shown] == ["SP1", "SP3"]                  # what the overlay actually draws
    assert panel.get_spot("spot_2_20_20") is None


def test_deleting_several_selected_spots(qapp):
    w, panel = _setup(qapp)
    panel.spot_list.item(0).setSelected(True)
    panel.spot_list.item(2).setSelected(True)
    panel._on_delete_clicked()
    assert [p.label for p in w.measurement_points] == ["SP2"]


def test_selecting_a_spot_from_the_video_works(qapp):
    _, panel = _setup(qapp)
    panel.select_spot("spot_3_30_30")
    assert panel.spot_list.currentItem().data(0x100) == "spot_3_30_30"      # Qt.UserRole


def test_the_main_loop_gets_coordinates_of_visible_spots(qapp):
    _, panel = _setup(qapp)
    assert panel.get_coords_for_main_loop() == [(10, 10, "SP1"), (20, 20, "SP2"), (30, 30, "SP3")]
