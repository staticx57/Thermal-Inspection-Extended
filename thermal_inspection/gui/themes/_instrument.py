"""
"Classic IBM" and "Classic HP" themes - inspired by 1960s-80s hardware rather than a desktop OS.

Shared design language (instrument / console front panels):
  * matte panel body with thin dark "seams" instead of 3-D window bevels
  * buttons are KEYCAPS: slightly rounded, with a thick dark bottom edge for key travel; pressing
    shrinks that edge and shifts the legend down; a checked (latched) key lights up like a lamp
  * section headings are engraved LABEL PLATES (solid coloured tab with light lettering)
  * checkboxes/radios are INDICATOR LAMPS - dim when off, bright when on
  * progress bars are LED bargraphs, and the info readout is a phosphor / LED display

IBM  - System/360 console & PC 5150 era: warm gray-beige panels, cream keycaps, IBM-blue label
       plates, amber lamps, 3270 green-phosphor readout.
HP   - 1970s-80s instruments & calculators: sage-putty body, charcoal keycaps with orange lit keys,
       red LED readout, green-bar printer-paper rows in lists.

Outer button metrics match every other theme (see themes/__init__.py) so controls keep the same size.
"""

from ._retro import _ARROWS, _render

_INSTRUMENT = """
QMainWindow, QDialog, QWidget { background-color: @BG@; color: @TEXT@; font-family: @FONT@; font-size: 9pt; }
QWidget:disabled { color: @TEXT_DIM@; }
QToolTip { background-color: @PLATE@; color: @PLATE_TEXT@; border: 1px solid @KEY_EDGE@; padding: 3px 6px; }

/* ---- keycaps ---- */
QPushButton, QToolButton {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 @KEY_TOP@, stop:1 @KEY_BOT@);
    color: @KEY_TEXT@;
    border: 1px solid @KEY_EDGE@; border-bottom: 3px solid @KEY_SHADOW@;
    border-radius: 3px;
}
/* 1px side border + 3px bottom: padding keeps the OUTER size equal to the other themes'
   buttons (2px border + 6px/16px padding) so controls don't change size with the theme. */
QPushButton { padding: 6px 17px; min-width: 120px; min-height: 18px; font-size: 9.75pt; font-weight: bold; }
QToolButton { padding: 2px 5px; }
QPushButton:hover, QToolButton:hover {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 @KEY_HOVER_TOP@, stop:1 @KEY_HOVER_BOT@);
}
QPushButton:pressed {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 @KEY_PRESS_TOP@, stop:1 @KEY_PRESS_BOT@);
    border-bottom: 1px solid @KEY_SHADOW@; padding-top: 8px;
}
QToolButton:pressed {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 @KEY_PRESS_TOP@, stop:1 @KEY_PRESS_BOT@);
}
QPushButton:checked {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 @LIT_TOP@, stop:1 @LIT_BOT@);
    color: @LIT_TEXT@; border: 1px solid @LIT_EDGE@; border-bottom: 1px solid @LIT_EDGE@; padding-top: 8px;
}
QToolButton:checked {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 @LIT_TOP@, stop:1 @LIT_BOT@);
    color: @LIT_TEXT@; border: 1px solid @LIT_EDGE@;
}
QPushButton:focus { border-color: @PLATE_ACCENT@; }
QPushButton:disabled, QToolButton:disabled {
    background: @BG@; color: @TEXT_DIM@; border: 1px solid @KEY_DISABLED@; border-bottom: 3px solid @KEY_DISABLED@;
}

/* ---- label plates ---- */
QGroupBox { border: 1px solid @SEAM@; border-radius: 2px; margin-top: 14px; padding-top: 10px; background-color: transparent; }
QGroupBox::title {
    subcontrol-origin: margin; subcontrol-position: top left; left: 8px; padding: 2px 10px;
    background-color: @PLATE@; color: @PLATE_TEXT@; font-weight: bold; border-radius: 2px;
}
QLabel { background-color: transparent; }

/* ---- indicator lamps ---- */
QCheckBox, QRadioButton { spacing: 7px; background-color: transparent; }
QCheckBox::indicator { width: 12px; height: 12px; border: 1px solid @KEY_EDGE@; border-bottom: 2px solid @KEY_SHADOW@; border-radius: 2px; background-color: @LAMP_OFF@; }
QCheckBox::indicator:checked { background-color: @LAMP@; border-color: @LIT_EDGE@; }
QRadioButton::indicator { width: 12px; height: 12px; border: 2px solid @KEY_EDGE@; border-radius: 8px; background-color: @LAMP_OFF@; }
QRadioButton::indicator:checked {
    border-color: @LIT_EDGE@;
    background: qradialgradient(cx:0.5, cy:0.45, radius:0.6, fx:0.4, fy:0.35, stop:0 #FFFFFF, stop:0.25 @LAMP@, stop:1 @LAMP@);
}
QCheckBox::indicator:disabled, QRadioButton::indicator:disabled { background-color: @BG@; border-color: @KEY_DISABLED@; }

/* ---- tabs ---- */
QTabWidget::pane { border: 1px solid @SEAM@; border-top: 3px solid @PLATE@; background-color: @BG@; top: -1px; }
QTabBar::tab {
    background: @TAB@; color: @TEXT@; border: 1px solid @SEAM@; border-bottom: none; border-top: 3px solid @TAB_BAR@;
    border-radius: 0px; padding: 4px 12px; margin-right: 2px; margin-top: 2px;
}
QTabBar::tab:hover { background: @BG_LIGHT@; }
QTabBar::tab:selected {
    background: @PLATE@; color: @PLATE_TEXT@; border-top: 3px solid @PLATE_ACCENT@;
    margin-top: 0px; padding-bottom: 6px; font-weight: bold;
}
QTabBar::scroller { width: 20px; }
QTabBar QToolButton { padding: 0px; min-height: 0px; }

/* ---- data entry ---- */
QLineEdit, QTextEdit, QPlainTextEdit {
    background-color: @FIELD@; color: @FIELD_TEXT@; border: 1px solid @FIELD_EDGE@; border-top: 2px solid @FIELD_EDGE@;
    padding: 2px 4px; font-family: @MONO@; selection-background-color: @SELECT@; selection-color: @SELECT_TEXT@;
}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus { border-color: @PLATE_ACCENT@; }
QLineEdit:disabled, QTextEdit:disabled { background-color: @BG@; color: @TEXT_DIM@; }
QSpinBox, QDoubleSpinBox, QComboBox {
    background-color: @FIELD@; color: @FIELD_TEXT@; border: 1px solid @FIELD_EDGE@; border-top: 2px solid @FIELD_EDGE@;
    padding: 2px 4px; min-height: 16px; font-family: @MONO@;
    selection-background-color: @SELECT@; selection-color: @SELECT_TEXT@;
}
QSpinBox:disabled, QDoubleSpinBox:disabled, QComboBox:disabled { background-color: @BG@; color: @TEXT_DIM@; }
QSpinBox { padding-right: 18px; }
QDoubleSpinBox { padding-right: 18px; }
QSpinBox::up-button, QSpinBox::down-button, QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {
    width: 15px; border: 1px solid @KEY_EDGE@; border-bottom: 2px solid @KEY_SHADOW@; border-radius: 2px;
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 @KEY_TOP@, stop:1 @KEY_BOT@);
}
QSpinBox::up-button, QDoubleSpinBox::up-button { subcontrol-origin: border; subcontrol-position: top right; }
QSpinBox::down-button, QDoubleSpinBox::down-button { subcontrol-origin: border; subcontrol-position: bottom right; }
QSpinBox::up-button:pressed, QSpinBox::down-button:pressed, QDoubleSpinBox::up-button:pressed, QDoubleSpinBox::down-button:pressed {
    background: @KEY_PRESS_BOT@; border-bottom: 1px solid @KEY_SHADOW@;
}
QComboBox { padding-right: 22px; }
QComboBox::drop-down {
    subcontrol-origin: padding; subcontrol-position: top right; width: 17px;
    border: 1px solid @KEY_EDGE@; border-bottom: 2px solid @KEY_SHADOW@; border-radius: 2px;
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 @KEY_TOP@, stop:1 @KEY_BOT@);
}
QComboBox QAbstractItemView {
    background-color: @FIELD@; color: @FIELD_TEXT@; border: 1px solid @KEY_EDGE@;
    selection-background-color: @SELECT@; selection-color: @SELECT_TEXT@; outline: none;
}

/* ---- faders and LED bargraph ---- */
QSlider::groove:horizontal { border: 1px solid @KEY_SHADOW@; height: 5px; background: @SLOT@; border-radius: 1px; }
QSlider::sub-page:horizontal { background: @LED@; border-radius: 1px; }
QSlider::handle:horizontal {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 @KEY_TOP@, stop:1 @KEY_BOT@);
    border: 1px solid @KEY_EDGE@; border-bottom: 3px solid @KEY_SHADOW@; width: 10px; margin: -8px 0; border-radius: 2px;
}
QSlider::groove:vertical { border: 1px solid @KEY_SHADOW@; width: 5px; background: @SLOT@; border-radius: 1px; }
QSlider::handle:vertical {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 @KEY_TOP@, stop:1 @KEY_BOT@);
    border: 1px solid @KEY_EDGE@; border-right: 3px solid @KEY_SHADOW@; height: 10px; margin: 0 -8px; border-radius: 2px;
}
QProgressBar { border: 1px solid @KEY_EDGE@; background: @FIELD@; text-align: center; color: @FIELD_TEXT@; min-height: 14px; border-radius: 1px; }
QProgressBar::chunk { background-color: @LED@; margin: 1px; width: 7px; }

/* ---- lists, tables, trees (paper) ---- */
QListWidget, QListView, QTreeWidget, QTreeView, QTableWidget, QTableView {
    background-color: @FIELD@; alternate-background-color: @ALT@; color: @FIELD_TEXT@;
    border: 1px solid @FIELD_EDGE@; gridline-color: @GRID@;
    selection-background-color: @SELECT@; selection-color: @SELECT_TEXT@; outline: none;
}
QListWidget::item:selected, QTreeView::item:selected, QTableView::item:selected { background-color: @SELECT@; color: @SELECT_TEXT@; }
QHeaderView::section {
    background-color: @PLATE@; color: @PLATE_TEXT@; border: none; border-right: 1px solid @KEY_EDGE@;
    padding: 3px 6px; font-weight: bold;
}
QTableCornerButton::section { background: @PLATE@; border: none; }

/* ---- menus ---- */
QMenuBar { background-color: @MENU_BG@; color: @MENU_TEXT@; }
QMenuBar::item { background: transparent; padding: 3px 9px; }
QMenuBar::item:selected { background-color: @PLATE_ACCENT@; color: @LIT_TEXT@; }
QMenu { background-color: @MENU_BG@; color: @MENU_TEXT@; border: 1px solid @KEY_EDGE@; padding: 2px; }
QMenu::item { padding: 3px 24px 3px 22px; }
QMenu::item:selected { background-color: @PLATE_ACCENT@; color: @LIT_TEXT@; }
QMenu::item:disabled { color: @TEXT_DIM@; background: transparent; }
QMenu::separator { height: 1px; background: @SEAM@; margin: 3px 2px; }
QStatusBar { background-color: @MENU_BG@; color: @MENU_TEXT@; }
QSplitter::handle { background-color: @SEAM@; }
QScrollArea { border: none; }

/* ---- scrollbars ---- */
QScrollBar:vertical { background: @SCROLL_TRACK@; width: 17px; margin: 17px 0 17px 0; border: none; }
QScrollBar:horizontal { background: @SCROLL_TRACK@; height: 17px; margin: 0 17px 0 17px; border: none; }
QScrollBar::handle:vertical {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 @KEY_TOP@, stop:1 @KEY_BOT@);
    border: 1px solid @KEY_EDGE@; border-right: 2px solid @KEY_SHADOW@; border-radius: 2px; min-height: 24px;
}
QScrollBar::handle:horizontal {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 @KEY_TOP@, stop:1 @KEY_BOT@);
    border: 1px solid @KEY_EDGE@; border-bottom: 2px solid @KEY_SHADOW@; border-radius: 2px; min-width: 24px;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical, QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 @KEY_TOP@, stop:1 @KEY_BOT@);
    border: 1px solid @KEY_EDGE@; border-radius: 2px; subcontrol-origin: margin;
}
QScrollBar::add-line:vertical { height: 17px; subcontrol-position: bottom; }
QScrollBar::sub-line:vertical { height: 17px; subcontrol-position: top; }
QScrollBar::add-line:horizontal { width: 17px; subcontrol-position: right; }
QScrollBar::sub-line:horizontal { width: 17px; subcontrol-position: left; }
QScrollBar::add-page, QScrollBar::sub-page { background: none; }
""" + _ARROWS + """
/* ---- phosphor / LED readout ---- */
QLabel#info_panel {
    background-color: @INFO_BG@; color: @INFO_TEXT@; border: 2px solid @INFO_EDGE@; border-radius: 3px;
    padding: 10px; font-size: 9pt; font-family: @MONO@;
}
"""


def build_instrument_theme(palette: dict) -> str:
    """Stylesheet for a 1960s-80s hardware-inspired theme from a palette dict."""
    return _render(_INSTRUMENT, palette)


_MONO = "'Consolas', 'Lucida Console', 'Courier New', monospace"
_SANS = "'Arial', 'Helvetica', 'Segoe UI', sans-serif"

# IBM System/360 console & PC 5150 era
IBM = {
    "BG": "#CDCBC0", "BG_LIGHT": "#DAD8CD", "SEAM": "#8F8C80", "TEXT": "#1E1E1C", "TEXT_DIM": "#8A877C",
    "FONT": _SANS, "MONO": _MONO,
    "KEY_TOP": "#ECEADF", "KEY_BOT": "#D6D3C4", "KEY_EDGE": "#5C5A52", "KEY_SHADOW": "#44423B",
    "KEY_TEXT": "#1E1E1C", "KEY_HOVER_TOP": "#F7F5EB", "KEY_HOVER_BOT": "#E3E0D1",
    "KEY_PRESS_TOP": "#C8C5B6", "KEY_PRESS_BOT": "#D3D0C1", "KEY_DISABLED": "#B2AFA3",
    "LIT_TOP": "#FFD25E", "LIT_BOT": "#F2A900", "LIT_EDGE": "#8A5A00", "LIT_TEXT": "#1E1E1C",
    "PLATE": "#1B4F9C", "PLATE_TEXT": "#F4F1E6", "PLATE_ACCENT": "#E8A000",
    "TAB": "#B9B7AB", "TAB_BAR": "#8F8C80",
    "FIELD": "#F5F2E4", "FIELD_TEXT": "#1E1E1C", "FIELD_EDGE": "#5C5A52",
    "SELECT": "#1B4F9C", "SELECT_TEXT": "#F4F1E6",
    "LAMP": "#F2A900", "LAMP_OFF": "#8C887C", "LED": "#E8A000", "SLOT": "#3A3933",
    "INFO_BG": "#0C120D", "INFO_TEXT": "#4BE070", "INFO_EDGE": "#2E5A38",
    "GLYPH": "#1E1E1C", "DISABLED": "#8A877C",
    "ALT": "#EAE7D8", "GRID": "#C9C5B4", "SCROLL_TRACK": "#B7B4A7",
    "MENU_BG": "#16407F", "MENU_TEXT": "#F4F1E6",
}

# HP 1970s-80s instruments & calculators
HP = {
    "BG": "#D3D0C0", "BG_LIGHT": "#DFDCCD", "SEAM": "#8B8772", "TEXT": "#26241F", "TEXT_DIM": "#8E8A78",
    "FONT": _SANS, "MONO": _MONO,
    "KEY_TOP": "#5A574F", "KEY_BOT": "#3F3C36", "KEY_EDGE": "#1F1D19", "KEY_SHADOW": "#15130F",
    "KEY_TEXT": "#F1EDDC", "KEY_HOVER_TOP": "#6B675D", "KEY_HOVER_BOT": "#4D4A42",
    "KEY_PRESS_TOP": "#36332E", "KEY_PRESS_BOT": "#45423B", "KEY_DISABLED": "#AAA692",
    "LIT_TOP": "#F59A3C", "LIT_BOT": "#E0731A", "LIT_EDGE": "#8A4208", "LIT_TEXT": "#1A1712",
    "PLATE": "#3F3C36", "PLATE_TEXT": "#EFEAD6", "PLATE_ACCENT": "#E0731A",
    "TAB": "#BEBAA6", "TAB_BAR": "#8B8772",
    "FIELD": "#F3F1E4", "FIELD_TEXT": "#26241F", "FIELD_EDGE": "#6E6A57",
    "SELECT": "#E0731A", "SELECT_TEXT": "#1A1712",
    "LAMP": "#E23B24", "LAMP_OFF": "#8E8A78", "LED": "#E23B24", "SLOT": "#2A2823",
    "INFO_BG": "#140806", "INFO_TEXT": "#FF4A30", "INFO_EDGE": "#5A2016",
    "GLYPH": "#F1EDDC", "DISABLED": "#8E8A78",
    "ALT": "#E3EDD8", "GRID": "#CDD8C2", "SCROLL_TRACK": "#BFBBA8",
    "MENU_BG": "#3F3C36", "MENU_TEXT": "#EFEAD6",
}
