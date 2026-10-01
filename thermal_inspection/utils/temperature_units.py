"""
Conversions between the temperature units the app can display.

Units are identified by the symbol strings the GUI shows: '°C', '°F', 'K',
'Y16' (radiometric raw, Kelvin x 100) and 'AGC' (8-bit counts from a
non-radiometric camera - not a temperature, so never convertible). Symbols
may carry extra text such as ' (est)' or a leading space.
"""

from typing import Optional


def unit_code(symbol: Optional[str]) -> Optional[str]:
    """'C' / 'F' / 'K' / 'Y16' for a display symbol, or None for AGC/raw/unknown."""
    if not symbol:
        return None
    s = symbol.upper()
    if 'AGC' in s or '(RAW)' in s:
        return None
    if 'Y16' in s:
        return 'Y16'
    if '°F' in s or s.strip().startswith('F'):
        return 'F'
    if '°C' in s or s.strip().startswith('C'):
        return 'C'
    if s.strip().startswith('K'):
        return 'K'
    return None


def to_celsius(value: float, code: str) -> float:
    if code == 'F':
        return (value - 32.0) * 5.0 / 9.0
    if code == 'K':
        return value - 273.15
    if code == 'Y16':
        return value / 100.0 - 273.15
    return value


def from_celsius(value_c: float, code: str) -> float:
    if code == 'F':
        return value_c * 9.0 / 5.0 + 32.0
    if code == 'K':
        return value_c + 273.15
    if code == 'Y16':
        return (value_c + 273.15) * 100.0
    return value_c


def convert(value: float, from_symbol: Optional[str], to_symbol: Optional[str]) -> Optional[float]:
    """Convert between display symbols; None if either side isn't a real temperature unit."""
    src, dst = unit_code(from_symbol), unit_code(to_symbol)
    if src is None or dst is None:
        return None
    if src == dst:
        return value
    return from_celsius(to_celsius(value, src), dst)
