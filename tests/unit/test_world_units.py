import pytest

from thermal_inspection.processing import world_units as wu


@pytest.mark.parametrize("m,expected", [
    (1.25, "1.25 m (4 ft 1 in)"),
    (0.38, "38 cm (1 ft 3 in)"),
    (0.20, "20 cm (7.9 in)"),
    (0.0042, "4.2 mm (0.17 in)"),
    (3.0, "3.00 m (9 ft 10 in)"),
    (1.8288, "1.83 m (6 ft 0 in)"),          # 5 ft 11.6 in rounds up to 6 ft 0 in, never "5 ft 12 in"
    (0.0, "0.0 mm (0.00 in)"),
])
def test_distance_shows_metric_and_imperial(m, expected):
    assert wu.format_distance(m) == expected


def test_distance_unknown_and_negative():
    assert wu.format_distance(None) == "-"
    assert wu.format_distance(-0.5).startswith("-50 cm")


def test_absolute_temperature_follows_unit():
    assert wu.format_temp(80.0, "C") == "80.0 °C"
    assert wu.format_temp(80.0, "F") == "176.0 °F"
    assert wu.format_temp(0.0, "K") == "273.1 K" or wu.format_temp(0.0, "K") == "273.2 K"
    assert wu.format_temp(float("nan")) == "-" and wu.format_temp(None) == "-"


def test_temperature_difference_has_no_offset():
    assert wu.format_delta(10.0, "C") == "+10.0 °C"
    assert wu.format_delta(10.0, "F") == "+18.0 °F"       # not +50: a difference converts by scale only
    assert wu.format_delta(-10.0, "K") == "-10.0 K"
    assert wu.convert_delta(5.0, "F") == pytest.approx(9.0)


def test_unit_symbols_and_raw_fallback():
    assert wu.display_unit("°F") == "F" and wu.display_unit("K") == "K" and wu.display_unit("C") == "C"
    assert wu.display_unit("Y16") == "C" and wu.display_unit("AGC") == "C" and wu.display_unit(None) == "C"
