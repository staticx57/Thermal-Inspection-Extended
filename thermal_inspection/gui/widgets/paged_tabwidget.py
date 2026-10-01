"""
Tab widget with large scroll arrows on BOTH ends of the tab row.

Qt's own tab scroller puts two tiny arrows side by side at the right end, which is hard to hit. This keeps
Qt's native scrolling - a continuous row where the next tab is left partly visible at the edge, so you can see
what comes next - but:
  * the native arrows are collapsed to zero width, and
  * large "<" / ">" buttons sit at the left and right ends of the row (as corner widgets) and drive the native
    scroller (hold to keep scrolling),
  * both buttons mirror the native scroller: they appear only when the tabs don't all fit, and each is disabled
    at its end of the row.

It is an ordinary QTabWidget otherwise (same API, same theming). Selecting a tab that is scrolled out of view
scrolls it in (native behaviour).
"""

from PyQt6.QtCore import Qt, QEvent, QObject, QTimer
from PyQt6.QtWidgets import QTabWidget, QToolButton

BUTTON_W = 34
BUTTON_H = 30

# Collapse Qt's own (tiny) scroll arrows: the tab bar then uses the full width for tabs
_BAR_QSS = (
    "QTabBar::scroller { width: 0px; }"
    "QTabBar QToolButton { min-width: 0px; max-width: 0px; width: 0px; border: none; padding: 0px; margin: 0px; }"
)


class PagedTabWidget(QTabWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        bar = self.tabBar()
        bar.setUsesScrollButtons(True)                         # native scrolling, partial tabs at the edges
        bar.setElideMode(Qt.TextElideMode.ElideNone)
        bar.setExpanding(False)
        bar.setStyleSheet(_BAR_QSS)

        self._left = self._make_button("‹", "Scroll tabs left")
        self._right = self._make_button("›", "Scroll tabs right")
        self.setCornerWidget(self._left, Qt.Corner.TopLeftCorner)
        self.setCornerWidget(self._right, Qt.Corner.TopRightCorner)
        self._left.hide()
        self._right.hide()

        self._native_left = None
        self._native_right = None
        self._find_native_buttons()

        self._left.clicked.connect(lambda: self._scroll(self._native_left))
        self._right.clicked.connect(lambda: self._scroll(self._native_right))

    # ---- buttons ----------------------------------------------------------------------------------

    @staticmethod
    def _make_button(glyph: str, tip: str) -> QToolButton:
        button = QToolButton()
        button.setText(glyph)
        button.setToolTip(tip)
        button.setFixedSize(BUTTON_W, BUTTON_H)
        button.setAutoRepeat(True)              # hold to keep scrolling
        button.setAutoRepeatDelay(350)
        button.setAutoRepeatInterval(140)
        button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        button.setStyleSheet("QToolButton { font-size: 20px; font-weight: bold; padding: 0px 0px 3px 0px; }")
        return button

    # ---- native scroller plumbing -----------------------------------------------------------------

    def _find_native_buttons(self) -> None:
        """Qt creates the tab bar's two scroll buttons left-then-right; keep them and watch their state."""
        natives = self.tabBar().findChildren(QToolButton)
        if len(natives) < 2:
            return
        self._native_left, self._native_right = natives[0], natives[1]
        for native in (self._native_left, self._native_right):
            native.setMaximumWidth(0)           # belt and braces alongside the QSS: never takes space
            native.installEventFilter(self)
        self._sync_buttons()

    def _scroll(self, native) -> None:
        if native is not None and native.isEnabled():
            native.click()

    def _sync_buttons(self) -> None:
        nl, nr = self._native_left, self._native_right
        if nl is None or nr is None:
            return
        scrolling = nl.isVisibleTo(self.tabBar()) or nr.isVisibleTo(self.tabBar())
        self._left.setVisible(scrolling)
        self._right.setVisible(scrolling)
        self._left.setEnabled(nl.isEnabled())
        self._right.setEnabled(nr.isEnabled())

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        if obj in (self._native_left, self._native_right) and event.type() in (
                QEvent.Type.Show, QEvent.Type.Hide, QEvent.Type.EnabledChange):
            QTimer.singleShot(0, self._sync_buttons)
        return super().eventFilter(obj, event)

    # ---- keep in sync when tabs/size change ---------------------------------------------------------

    def tabInserted(self, index: int) -> None:
        super().tabInserted(index)
        QTimer.singleShot(0, self._sync_buttons)

    def tabRemoved(self, index: int) -> None:
        super().tabRemoved(index)
        QTimer.singleShot(0, self._sync_buttons)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        QTimer.singleShot(0, self._sync_buttons)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if self._native_left is None:
            self._find_native_buttons()
        QTimer.singleShot(0, self._sync_buttons)
