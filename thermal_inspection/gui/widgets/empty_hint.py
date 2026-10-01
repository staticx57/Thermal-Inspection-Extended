"""
List / table widgets that draw a short hint in the empty viewport ("No spot meters yet - click Add Spot Meter, then the
video"), so an empty panel says what puts something in it instead of looking broken. The hint disappears as soon as there
is a row, so it never competes with real hardware data.
"""
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QPainter
from PyQt6.QtWidgets import QListWidget, QTableWidget


def _paint_hint(widget, text: str):
    if not text:
        return
    painter = QPainter(widget.viewport())
    colour = QColor(widget.palette().color(widget.foregroundRole()))
    colour.setAlpha(120)                                   # a hint, not content: works on light and dark themes
    painter.setPen(colour)
    rect = widget.viewport().rect().adjusted(12, 8, -12, -8)
    painter.drawText(rect, int(Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap), text)
    painter.end()


class HintListWidget(QListWidget):
    def __init__(self, hint: str = "", parent=None):
        super().__init__(parent)
        self.empty_hint = hint

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.count() == 0:
            _paint_hint(self, self.empty_hint)


class HintTableWidget(QTableWidget):
    def __init__(self, *args, hint: str = "", **kwargs):
        super().__init__(*args, **kwargs)
        self.empty_hint = hint

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.rowCount() == 0:
            _paint_hint(self, self.empty_hint)
