"""
Display formatting for the 3D world viewer: distances in metric AND imperial together, temperatures in the app's
selected unit. Pure functions, no Qt - shared by the mapper's text and the viewer's cards.

Internal values are always metres and degrees Celsius.
"""
from __future__ import annotations

from typing import Optional

from thermal_inspection.utils.temperature_units import from_celsius, unit_code

_M_PER_IN = 0.0254


def format_distance(metres: Optional[float]) -> str:
    """'1.25 m (4 ft 1 in)' / '38 cm (15.0 in)' / '4.2 mm (0.17 in)': metric and imperial side by side."""
    if metres is None:
        return "-"
    m = abs(float(metres))
    sign = "-" if metres < 0 else ""
    inches = m / _M_PER_IN
    if m >= 1.0:
        metric = f"{m:.2f} m"
    elif m >= 0.01:
        metric = f"{m * 100:.0f} cm" if m >= 0.1 else f"{m * 100:.1f} cm"
    else:
        metric = f"{m * 1000:.1f} mm"
    if inches >= 12.0:
        feet = int(inches // 12)
        rem = inches - feet * 12
        if round(rem, 0) >= 12:                 # 5 ft 11.6 in must read 6 ft 0 in, not 5 ft 12 in
            feet, rem = feet + 1, 0.0
        imperial = f"{feet} ft {rem:.0f} in"
    elif inches >= 1.0:
        imperial = f"{inches:.1f} in"
    else:
        imperial = f"{inches:.2f} in"
    return f"{sign}{metric} ({imperial})"


def display_unit(symbol_or_code: Optional[str]) -> str:
    """'C' / 'F' / 'K' for whatever the app's unit setting says. Raw counts (Y16/AGC) aren't a temperature scale a
    3D world can use, so they fall back to Celsius."""
    code = unit_code(symbol_or_code) if symbol_or_code and len(symbol_or_code) > 1 else (symbol_or_code or "C")
    return code if code in ("C", "F", "K") else "C"


def unit_symbol(code: str) -> str:
    return {"C": "°C", "F": "°F", "K": "K"}.get(code, "°C")


def format_temp(celsius: Optional[float], code: str = "C", decimals: int = 1) -> str:
    """Absolute temperature in the chosen unit, e.g. '80.0 °C' / '176.0 °F'; '-' when unknown."""
    if celsius is None or celsius != celsius:       # None or NaN
        return "-"
    code = display_unit(code)
    return f"{from_celsius(float(celsius), code):.{decimals}f} {unit_symbol(code)}"


def format_delta(delta_celsius: Optional[float], code: str = "C", decimals: int = 1) -> str:
    """Temperature DIFFERENCE with sign. A difference converts by scale only (no +32 / +273.15 offset):
    +10 degC change is +18 degF and +10 K."""
    if delta_celsius is None or delta_celsius != delta_celsius:
        return "-"
    code = display_unit(code)
    scale = 1.8 if code == "F" else 1.0
    unit = {"C": "°C", "F": "°F", "K": "K"}[code]
    return f"{float(delta_celsius) * scale:+.{decimals}f} {unit}"


def convert_delta(delta_celsius: float, code: str = "C") -> float:
    """Numeric temperature difference in the chosen unit (for legends)."""
    return float(delta_celsius) * (1.8 if display_unit(code) == "F" else 1.0)


def convert_temp(celsius: float, code: str = "C") -> float:
    return from_celsius(float(celsius), display_unit(code))
