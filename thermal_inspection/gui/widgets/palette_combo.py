"""
Palette picker with an inline swatch preview beside each palette name.

Each row (in the dropdown and in the closed combo box) shows the palette's name
and a strip of colour swatches sampled evenly along its lookup table, so palettes
can be told apart at a glance without applying them. The swatch count adapts to
the space available, from 4 (tight) to 8 (roomy).
"""

from typing import Dict, List

from PyQt6.QtCore import Qt, QSize, pyqtSignal
from PyQt6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap
from PyQt6.QtWidgets import (
    QComboBox, QStyle, QStyledItemDelegate, QStyleOptionComboBox, QStylePainter,
)

from thermal_inspection.processing.palette_manager import (
    PALETTE_CATEGORIES, PaletteManager, PaletteType, palette_display_name,
)

SWATCH_W = 14
SWATCH_H = 12
SWATCH_GAP = 1
MIN_SWATCHES = 4
MAX_SWATCHES = 8
_PAD = 10  # breathing room between the name and the strip

_VALUES = {p.value for p in PaletteType}
_manager = None
_luts: Dict[str, object] = {}


def _lut(value: str):
    """(256, 3) BGR lookup table for a palette value, built once and cached."""
    global _manager
    lut = _luts.get(value)
    if lut is None:
        if _manager is None:
            _manager = PaletteManager()
        lut = _manager.get_palette_lut(PaletteType(value))
        _luts[value] = lut
    return lut


def swatch_count(free_width: int) -> int:
    """
    How many swatches fit in free_width pixels: 4..8, or 0 if there isn't room for
    even 4 - the palette name always takes priority over its preview, so a cramped
    row shows the full name alone rather than a truncated one.
    """
    fit = (free_width + SWATCH_GAP) // (SWATCH_W + SWATCH_GAP)
    return 0 if fit < MIN_SWATCHES else min(MAX_SWATCHES, fit)


def strip_width(count: int) -> int:
    return count * (SWATCH_W + SWATCH_GAP) - SWATCH_GAP


def swatch_colors(palette_value: str, count: int) -> List[QColor]:
    """`count` colours sampled at the centres of equal slices of the palette (cold -> hot)."""
    lut = _lut(palette_value)
    colors = []
    for i in range(count):
        idx = int((i + 0.5) / count * 255)
        b, g, r = (int(v) for v in lut[idx])
        colors.append(QColor(r, g, b))
    return colors


def draw_swatches(painter: QPainter, x: int, y: int, colors: List[QColor], border: QColor,
                  w: int = SWATCH_W, h: int = SWATCH_H, gap: int = SWATCH_GAP) -> None:
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
    painter.setPen(QPen(border, 1))
    for i, color in enumerate(colors):
        painter.setBrush(color)
        painter.drawRect(x + i * (w + gap), y, w - 1, h - 1)
    painter.restore()


def _border_for(is_dark_background: bool) -> QColor:
    return QColor(255, 255, 255, 90) if is_dark_background else QColor(0, 0, 0, 110)


def palette_swatch_icon(palette_value: str, count: int = 6, w: int = 9, h: int = 12) -> QIcon:
    """Small swatch-strip icon for menu entries."""
    pixmap = QPixmap(count * (w + 1) - 1, h)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    draw_swatches(painter, 0, 0, swatch_colors(palette_value, count), QColor(0, 0, 0, 110), w=w, h=h, gap=1)
    painter.end()
    return QIcon(pixmap)


class PaletteItemDelegate(QStyledItemDelegate):
    """Draws the normal item (so themes still apply), then the swatch strip on the right."""

    def paint(self, painter, option, index):
        super().paint(painter, option, index)
        value = index.data(Qt.ItemDataRole.UserRole)
        if value not in _VALUES or not (option.state & QStyle.StateFlag.State_Enabled):
            return  # category header or blank
        text_w = option.fontMetrics.horizontalAdvance(index.data(Qt.ItemDataRole.DisplayRole) or "")
        n = swatch_count(option.rect.width() - text_w - _PAD * 2)
        if n == 0:
            return
        x = option.rect.right() - strip_width(n) - _PAD // 2
        y = option.rect.top() + (option.rect.height() - SWATCH_H) // 2
        dark = option.palette.window().color().lightness() < 128
        draw_swatches(painter, x, y, swatch_colors(value, n), _border_for(dark))

    def sizeHint(self, option, index):
        size = super().sizeHint(option, index)
        return QSize(size.width(), max(size.height(), SWATCH_H + 8))


class PaletteComboBox(QComboBox):
    """
    QComboBox listing every palette by category, with inline swatch previews.

    Rows show a friendly name ("White Hot"); the internal palette ID ("white_hot")
    is the item's data - read it with currentValue() / paletteValueChanged, not
    currentText().
    """

    paletteValueChanged = pyqtSignal(str)  # internal palette ID of the newly selected palette

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setItemDelegate(PaletteItemDelegate(self))
        self.populate()
        self.currentIndexChanged.connect(self._emit_value)

    def _emit_value(self, index: int) -> None:
        value = self.itemData(index, Qt.ItemDataRole.UserRole)
        if value in _VALUES:
            self.paletteValueChanged.emit(value)

    def currentValue(self) -> str:
        """Internal ID of the selected palette ('' if a category header/nothing is selected)."""
        value = self.currentData(Qt.ItemDataRole.UserRole)
        return value if value in _VALUES else ""

    def findValue(self, value: str) -> int:
        """Index of the palette with this internal ID (case-insensitive), or -1."""
        wanted = (value or "").strip().lower().replace(" ", "_")
        for i in range(self.count()):
            if self.itemData(i, Qt.ItemDataRole.UserRole) == wanted:
                return i
        return -1

    def setCurrentValue(self, value: str) -> bool:
        index = self.findValue(value)
        if index >= 0:
            self.setCurrentIndex(index)
        return index >= 0

    def populate(self) -> None:
        """Fill with category headers (disabled) and indented palette names."""
        from PyQt6.QtGui import QFont
        self.clear()
        for category, palettes in PALETTE_CATEGORIES:
            self.addItem(f"─── {category} ───")
            header = self.model().item(self.count() - 1)
            font = QFont()
            font.setBold(True)
            header.setFont(font)
            header.setEnabled(False)
            for palette in palettes:
                self.addItem(f"  {palette_display_name(palette)}", palette.value)

    # --- sizing: leave room for the swatch strip ---------------------------

    def _longest_name_width(self) -> int:
        fm = self.fontMetrics()
        return max((fm.horizontalAdvance(self.itemText(i)) for i in range(self.count())), default=0)

    def _popup_width(self) -> int:
        return self._longest_name_width() + strip_width(MAX_SWATCHES) + _PAD * 3

    def sizeHint(self) -> QSize:
        base = super().sizeHint()
        return QSize(max(base.width(), self._popup_width() + 24), base.height())

    def showPopup(self) -> None:
        self.view().setMinimumWidth(max(self.width(), self._popup_width()))
        super().showPopup()

    # --- closed state: name + swatches --------------------------------------

    def paintEvent(self, event) -> None:
        value = self.currentValue()
        text = self.currentText().strip()
        painter = QStylePainter(self)
        opt = QStyleOptionComboBox()
        self.initStyleOption(opt)
        if value not in _VALUES:
            painter.drawComplexControl(QStyle.ComplexControl.CC_ComboBox, opt)
            painter.drawControl(QStyle.ControlElement.CE_ComboBoxLabel, opt)
            return

        edit = self.style().subControlRect(
            QStyle.ComplexControl.CC_ComboBox, opt, QStyle.SubControl.SC_ComboBoxEditField, self)
        fm = self.fontMetrics()
        n = swatch_count(edit.width() - fm.horizontalAdvance(text) - _PAD)
        opt.currentText = text
        painter.drawComplexControl(QStyle.ComplexControl.CC_ComboBox, opt)
        painter.drawControl(QStyle.ControlElement.CE_ComboBoxLabel, opt)
        if n == 0:
            return  # no room for a preview next to the full name

        strip_w = strip_width(n)
        x = edit.right() - strip_w - 2
        y = edit.top() + (edit.height() - SWATCH_H) // 2
        dark = self.palette().window().color().lightness() < 128
        draw_swatches(painter, x, y, swatch_colors(value, n), _border_for(dark))
