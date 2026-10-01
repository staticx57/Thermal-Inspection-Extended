"""
Colorbar (temperature scale) for the video overlay.

Shows the current palette as a gradient with tick labels on round numbers (10, 20, 30 ... not 23.7, 41.2 ...). The unit
appears once as a header instead of on every label. With no real temperatures (a non-radiometric camera: the frame is
only 8-bit counts) the bar shows relative 'cold' / 'hot' ends rather than inventing numbers.

The gradient is rendered once per palette change into a QImage and drawn with a single call; the widget sizes itself from
the font and the available video height, so it stays readable on high-DPI displays and is not clipped by long labels.
"""
import logging
import math
from typing import List, Optional

import numpy as np
from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QFont, QFontMetrics, QImage, QPainter, QPen, QTransform
from PyQt6.QtWidgets import QWidget

logger = logging.getLogger(__name__)

MIN_BAR_LENGTH = 140
MAX_BAR_LENGTH = 420
RELATIVE_UNITS = ("AGC", "RAW", "(RAW)", "COUNTS", "")


def nice_ticks(lo: float, hi: float, max_ticks: int = 6) -> List[float]:
    """Round tick values inside [lo, hi]: steps of 1, 2, 5 (x10^n), as many as fit within max_ticks. Always at least the
    two ends when the range is degenerate."""
    if not (math.isfinite(lo) and math.isfinite(hi)):
        return []
    if hi < lo:
        lo, hi = hi, lo
    span = hi - lo
    if span <= 1e-12:
        return [lo]
    raw = span / max(1, max_ticks - 1)
    mag = 10 ** math.floor(math.log10(raw))
    step = mag
    for mult in (1, 2, 5, 10):
        step = mult * mag
        if span / step <= max_ticks - 1 + 1e-9:
            break
    first = math.ceil(lo / step - 1e-9) * step
    ticks, v = [], first
    while v <= hi + step * 1e-9:
        ticks.append(round(v, 10))
        v += step
    return ticks


def tick_step(ticks: List[float]) -> float:
    return abs(ticks[1] - ticks[0]) if len(ticks) > 1 else 1.0


def format_tick(value: float, step: float) -> str:
    """Decimals are the fewest that show the step exactly (step 5 -> none, 0.5 or 2.5 -> one, 0.25 -> two)."""
    decimals = 0
    for d in range(0, 4):
        decimals = d
        if abs(round(step, d) - step) < 1e-9:
            break
    text = f"{value:.{decimals}f}"
    return "0" if text.lstrip("-").strip("0.") == "" else text


def is_relative_unit(unit: Optional[str]) -> bool:
    return (unit or "").strip().upper() in RELATIVE_UNITS or "AGC" in (unit or "").upper()


class ColorbarWidget(QWidget):
    """Temperature scale for the current palette; transparent to the mouse so it never blocks drawing ROIs."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.palette_lut = None
        self._gradient: Optional[QImage] = None          # 1 x 256 strip, index 0 = coldest
        self.temp_min = 0.0
        self.temp_max = 100.0
        self.unit = "°C"
        self.position = "right"                          # "right", "left", "top", "bottom"
        self.enabled = True                              # the user's show/hide choice
        self._view_allowed = True                        # false in views where a thermal scale means nothing
        self.bar_thickness = 22
        self.bar_length = 220
        self.background_alpha = 170
        self.text_color = QColor(255, 255, 255)
        self.font = QFont()
        self.font.setPointSize(9)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setStyleSheet("background: transparent;")
        self._update_size()

    # ------------------------------------------------------------------ configuration

    def set_palette_lut(self, palette_lut):
        """palette_lut: (256, 3) BGR uint8 array (index 0 = coldest)."""
        if palette_lut is None or getattr(palette_lut, "shape", None) != (256, 3):
            logger.warning(f"Invalid palette LUT shape: {getattr(palette_lut, 'shape', None)}")
            return
        arr = np.ascontiguousarray(palette_lut, dtype=np.uint8)
        if self.palette_lut is not None and np.array_equal(arr, self.palette_lut):
            return                                       # unchanged: don't rebuild or repaint
        self.palette_lut = arr.copy()
        rgb = np.ascontiguousarray(arr[:, ::-1])         # BGR -> RGB
        self._gradient = QImage(rgb.data, 256, 1, 256 * 3, QImage.Format.Format_RGB888).copy()
        self.update()

    def set_temperature_range(self, temp_min: float, temp_max: float, unit: str = "°C"):
        if (temp_min, temp_max, unit) == (self.temp_min, self.temp_max, self.unit):
            return
        self.temp_min, self.temp_max, self.unit = float(temp_min), float(temp_max), unit
        self._update_size()
        self.update()

    def set_enabled(self, enabled: bool):
        """The user's show/hide choice (the overlay can still hide it in views where it makes no sense)."""
        self.enabled = bool(enabled)
        self._sync_visibility()

    def set_view_allowed(self, allowed: bool):
        self._view_allowed = bool(allowed)
        self._sync_visibility()

    def _sync_visibility(self):
        self.setVisible(self.enabled and self._view_allowed)

    def set_position(self, position: str):
        if position in ("right", "left", "top", "bottom"):
            self.position = position
            self._update_size()
            self.update()

    def set_available_size(self, width: int, height: int):
        """Scale the bar to the video area: about a third of its height (or width when horizontal)."""
        span = height if self.position in ("right", "left") else width
        length = int(max(MIN_BAR_LENGTH, min(MAX_BAR_LENGTH, span * 0.35)))
        if length != self.bar_length:
            self.bar_length = length
            self._update_size()
            self.update()

    # ------------------------------------------------------------------ layout

    @property
    def relative(self) -> bool:
        return is_relative_unit(self.unit)

    def _ticks(self) -> List[float]:
        if self.relative:
            return []
        return nice_ticks(self.temp_min, self.temp_max, 6 if self.bar_length >= 200 else 5)

    def _labels(self):
        """[(fraction along the bar from cold (0) to hot (1), text)]"""
        if self.relative:
            return [(1.0, "hot"), (0.0, "cold")]
        lo, hi = self.temp_min, self.temp_max
        ticks = self._ticks()
        if not ticks or hi - lo <= 1e-12:
            return [(0.5, format_tick(lo, 1.0))]
        step = tick_step(ticks)
        return [((v - lo) / (hi - lo), format_tick(v, step)) for v in ticks]

    def _header(self) -> str:
        if self.relative:
            return ""
        est = "(est)" in (self.unit or "")
        clean = (self.unit or "").replace("(est)", "").strip()
        return ("~" if est else "") + clean

    def _update_size(self):
        fm = QFontMetrics(self.font)
        labels = [t for _, t in self._labels()]
        text_w = max([fm.horizontalAdvance(t) for t in labels] + [fm.horizontalAdvance(self._header())] + [0])
        pad = 8
        header_h = fm.height() if self._header() else 0
        if self.position in ("right", "left"):
            w = pad + self.bar_thickness + 6 + 5 + text_w + pad
            h = pad + header_h + self.bar_length + pad + fm.height() // 2
        else:
            w = pad + self.bar_length + pad + text_w // 2
            h = pad + header_h + self.bar_thickness + 6 + fm.height() + pad
        self.setFixedSize(max(w, 40), max(h, 40))

    # ------------------------------------------------------------------ painting

    def paintEvent(self, event):
        if not (self.enabled and self._view_allowed) or self._gradient is None:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        p.setFont(self.font)
        p.setBrush(QColor(0, 0, 0, self.background_alpha))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(QRectF(self.rect()), 6, 6)

        fm = p.fontMetrics()
        pad = 8
        header = self._header()
        top = pad + (fm.height() if header else 0)
        vertical = self.position in ("right", "left")
        if header:
            p.setPen(QPen(self.text_color))
            p.drawText(QPointF(pad, pad + fm.ascent()), header)

        if vertical:
            bar = QRectF(pad, top + fm.height() / 4, self.bar_thickness, self.bar_length)
            # the gradient strip is 256 wide, coldest first: rotate it so hot is at the top
            img = self._gradient.transformed(QTransform().rotate(-90))
            p.drawImage(bar, img)
        else:
            bar = QRectF(pad, top, self.bar_length, self.bar_thickness)
            p.drawImage(bar, self._gradient)
        p.setPen(QPen(QColor(255, 255, 255, 190), 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRect(bar)

        p.setPen(QPen(self.text_color, 1))
        for frac, text in self._labels():
            if vertical:
                y = bar.bottom() - frac * bar.height()
                x1 = bar.right()
                p.drawLine(QPointF(x1, y), QPointF(x1 + 5, y))
                p.drawText(QPointF(x1 + 8, y + fm.ascent() / 2 - 1), text)
            else:
                x = bar.left() + frac * bar.width()
                y1 = bar.bottom()
                p.drawLine(QPointF(x, y1), QPointF(x, y1 + 5))
                p.drawText(QPointF(x - fm.horizontalAdvance(text) / 2, y1 + 6 + fm.ascent()), text)
        p.end()
