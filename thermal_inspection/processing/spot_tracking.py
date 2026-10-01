"""
Pure helpers for spot meters: snap a click to the hottest nearby pixel, rate of change, and delta unit conversion.
No Qt, no camera - testable with a synthetic frame.
"""
from __future__ import annotations

from typing import List, Optional, Sequence, Tuple

import numpy as np

from thermal_inspection.utils.temperature_units import from_celsius, to_celsius, unit_code

RATE_WINDOW_S = 30.0        # how far back the rate of change looks
RATE_MIN_SPAN_S = 3.0       # needs at least this much history, or a rate would just be noise
RATE_TYPES = ("rising_fast", "falling_fast")


def snap_to_hottest(frame: np.ndarray, x: int, y: int, radius: int = 6) -> Tuple[int, int]:
    """Move (x, y) to the hottest pixel within `radius` pixels (a square window clipped to the frame), so a spot meter
    lands on the actual peak instead of next to it. Works on any 2-D thermal frame (Y16 counts, temperatures, 8-bit);
    a 3-channel frame is treated by brightness. Ties keep the pixel closest to the click. A click outside the frame or
    an all-equal window returns the click unchanged."""
    if frame is None or frame.size == 0:
        return x, y
    f = frame
    if f.ndim == 3:
        f = f.mean(axis=2)
    h, w = f.shape[:2]
    if not (0 <= x < w and 0 <= y < h):
        return x, y
    x0, x1 = max(0, x - radius), min(w, x + radius + 1)
    y0, y1 = max(0, y - radius), min(h, y + radius + 1)
    win = f[y0:y1, x0:x1].astype(np.float64)
    top = win.max()
    if top == win.min():
        return x, y
    ys, xs = np.where(win == top)
    d = (xs + x0 - x) ** 2 + (ys + y0 - y) ** 2
    k = int(np.argmin(d))
    return int(xs[k] + x0), int(ys[k] + y0)


def rate_per_minute(history: Sequence[Tuple[float, float]], window_s: float = RATE_WINDOW_S,
                    min_span_s: float = RATE_MIN_SPAN_S) -> Optional[float]:
    """Least-squares slope (value units per minute) of the readings in the last `window_s` seconds, or None when
    there isn't enough history yet. A fit rather than last-minus-first so one noisy sample doesn't make an alert fire."""
    if len(history) < 3:
        return None
    t_end = history[-1][0]
    pts = [(t, v) for t, v in history if t_end - t <= window_s]
    if len(pts) < 3 or pts[-1][0] - pts[0][0] < min_span_s:
        return None
    t = np.array([p[0] for p in pts], dtype=np.float64)
    v = np.array([p[1] for p in pts], dtype=np.float64)
    t = t - t.mean()
    denom = float((t * t).sum())
    if denom <= 0:
        return None
    return float((t * (v - v.mean())).sum() / denom) * 60.0


def convert_delta(delta: float, from_unit: Optional[str], to_unit: Optional[str]) -> Optional[float]:
    """A temperature DIFFERENCE between two display units (scale only, no offset): +10 degC is +18 degF.
    None when either unit isn't a real temperature unit (raw AGC counts)."""
    a, b = unit_code(from_unit), unit_code(to_unit)
    if a is None or b is None:
        return None
    if a == b:
        return delta
    return from_celsius(to_celsius(delta, a), b) - from_celsius(to_celsius(0.0, a), b)
