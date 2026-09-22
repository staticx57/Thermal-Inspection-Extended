from thermal_inspection.gui.widgets.measurement_point import MeasurementPoint


def test_measurement_point_defaults_distance_to_none():
    point = MeasurementPoint(x=10, y=20, label="Test")
    assert point.distance_m is None


def test_measurement_point_accepts_distance():
    point = MeasurementPoint(x=10, y=20, label="Test", distance_m=1.42)
    assert point.distance_m == 1.42
