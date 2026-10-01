"""
Application themes for the Thermal Inspection GUI.

Themes are defined as Qt stylesheet (QSS) strings.
Available themes: Dark Mode, Light Mode, Solarized, Colorful, Win XP Luna, Silver, Olive,
Classic IBM, Classic HP
"""

DARK_THEME = """
QMainWindow {
    background-color: #23262b;
}

QWidget {
    background-color: #23262b;
}

QPushButton {
    background-color: #2d3137;
    color: #c8cdd4;
    border: 2px solid #3f454d;
    border-radius: 8px;
    padding: 6px 16px;
    font-size: 13px;
    font-weight: bold;
    min-width: 120px;
    min-height: 18px;
}

QPushButton:hover {
    background-color: #373c43;
    border: 2px solid #4f9fd8;
}

QPushButton:pressed {
    background-color: #1f2226;
}

QPushButton:checked {
    background-color: #4f9fd8;
    color: #eef2f6;
    border: 2px solid #74bde8;
}

QPushButton:disabled {
    background-color: #23262b;
    color: #6c737c;
    border: 2px solid #2d3137;
}

QLabel {
    color: #c8cdd4;
}

QLabel#info_panel {
    background-color: rgba(22, 24, 28, 200);
    color: #86d192;
    border: 1px solid #3f454d;
    border-radius: 5px;
    padding: 10px;
    font-size: 12px;
    font-family: monospace;
}

QGroupBox {
    background-color: #2d3137;
    border: 2px solid #3f454d;
    border-radius: 5px;
    margin-top: 10px;
    padding: 10px;
    color: #c8cdd4;
    font-weight: bold;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 5px;
}

QListWidget {
    background-color: #23262b;
    color: #c8cdd4;
    border: 1px solid #3f454d;
    border-radius: 3px;
}

QListWidget::item:selected {
    background-color: #4f9fd8;
    color: #eef2f6;
}

QComboBox {
    background-color: #2d3137;
    color: #c8cdd4;
    border: 1px solid #3f454d;
    border-radius: 3px;
    padding: 5px;
}

QComboBox:hover {
    border: 1px solid #4f9fd8;
}

QComboBox::drop-down {
    border: none;
}

QComboBox QAbstractItemView {
    background-color: #2d3137;
    color: #c8cdd4;
    selection-background-color: #4f9fd8;
    selection-color: #eef2f6;
}

QSpinBox, QDoubleSpinBox {
    background-color: #2d3137;
    color: #c8cdd4;
    border: 1px solid #3f454d;
    border-radius: 3px;
    padding: 3px;
}

QSpinBox:hover, QDoubleSpinBox:hover {
    border: 1px solid #4f9fd8;
}

QCheckBox {
    color: #c8cdd4;
}

QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border: 2px solid #3f454d;
    border-radius: 3px;
    background-color: #2d3137;
}

QCheckBox::indicator:checked {
    background-color: #4f9fd8;
}

QTabWidget::pane {
    border: 1px solid #3f454d;
    background-color: #2d3137;
}

QTabBar::tab {
    background-color: #23262b;
    color: #c8cdd4;
    border: 1px solid #3f454d;
    padding: 8px 16px;
    margin-right: 2px;
}

QTabBar::tab:selected {
    background-color: #4f9fd8;
    color: #eef2f6;
}

QTabBar::tab:hover {
    background-color: #373c43;
}

/* Once a stylesheet targets QTabBar::tab, Qt stops automatically
   reserving layout space for the tab bar's scroll buttons (shown when
   there are more tabs than fit) - without this, they render on top of
   the last tab's label instead of after it. */
QTabBar::scroller {
    width: 24px;
}

QTabBar QToolButton {
    background-color: #23262b;
    border: 1px solid #3f454d;
}
"""

LIGHT_THEME = """
QMainWindow {
    background-color: #eaedf0;
}

QWidget {
    background-color: #eaedf0;
}

QPushButton {
    background-color: #f4f6f8;
    color: #323840;
    border: 2px solid #b7bdc5;
    border-radius: 8px;
    padding: 6px 16px;
    font-size: 13px;
    font-weight: bold;
    min-width: 120px;
    min-height: 18px;
}

QPushButton:hover {
    background-color: #e3e7eb;
    border: 2px solid #3b82c4;
}

QPushButton:pressed {
    background-color: #d8dce1;
}

QPushButton:checked {
    background-color: #3b82c4;
    color: #f4f6f8;
    border: 2px solid #5a9bd5;
}

QPushButton:disabled {
    background-color: #eaedf0;
    color: #939aa3;
    border: 2px solid #c5cad1;
}

QLabel {
    color: #323840;
}

QLabel#info_panel {
    background-color: rgba(244, 246, 248, 210);
    color: #2f6a3c;
    border: 1px solid #b7bdc5;
    border-radius: 5px;
    padding: 10px;
    font-size: 12px;
    font-family: monospace;
}

QGroupBox {
    background-color: #f4f6f8;
    border: 2px solid #b7bdc5;
    border-radius: 5px;
    margin-top: 10px;
    padding: 10px;
    color: #323840;
    font-weight: bold;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 5px;
}

QListWidget {
    background-color: #f4f6f8;
    color: #323840;
    border: 1px solid #b7bdc5;
    border-radius: 3px;
}

QListWidget::item:selected {
    background-color: #3b82c4;
    color: #f4f6f8;
}

QComboBox {
    background-color: #f4f6f8;
    color: #323840;
    border: 1px solid #b7bdc5;
    border-radius: 3px;
    padding: 5px;
}

QComboBox:hover {
    border: 1px solid #3b82c4;
}

QComboBox::drop-down {
    border: none;
}

QComboBox QAbstractItemView {
    background-color: #f4f6f8;
    color: #323840;
    selection-background-color: #3b82c4;
    selection-color: #f4f6f8;
}

QSpinBox, QDoubleSpinBox {
    background-color: #f4f6f8;
    color: #323840;
    border: 1px solid #b7bdc5;
    border-radius: 3px;
    padding: 3px;
}

QSpinBox:hover, QDoubleSpinBox:hover {
    border: 1px solid #3b82c4;
}

QCheckBox {
    color: #323840;
}

QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border: 2px solid #b7bdc5;
    border-radius: 3px;
    background-color: #f4f6f8;
}

QCheckBox::indicator:checked {
    background-color: #3b82c4;
}

QTabWidget::pane {
    border: 1px solid #b7bdc5;
    background-color: #f4f6f8;
}

QTabBar::tab {
    background-color: #eaedf0;
    color: #323840;
    border: 1px solid #b7bdc5;
    padding: 8px 16px;
    margin-right: 2px;
}

QTabBar::tab:selected {
    background-color: #3b82c4;
    color: #f4f6f8;
}

QTabBar::scroller {
    width: 24px;
}

QTabBar QToolButton {
    background-color: #eaedf0;
    border: 1px solid #b7bdc5;
}

QTabBar::tab:hover {
    background-color: #d8dce1;
}
"""

SOLARIZED_THEME = """
QMainWindow {
    background-color: #fdf6e3;
}

QWidget {
    background-color: #fdf6e3;
}

QPushButton {
    background-color: #eee8d5;
    color: #657b83;
    border: 2px solid #93a1a1;
    border-radius: 8px;
    padding: 6px 16px;
    font-size: 13px;
    font-weight: bold;
    min-width: 120px;
    min-height: 18px;
}

QPushButton:hover {
    background-color: #e8e2cf;
    border: 2px solid #268bd2;
}

QPushButton:pressed {
    background-color: #dfd9c6;
}

QPushButton:checked {
    background-color: #268bd2;
    color: #fdf6e3;
    border: 2px solid #2aa198;
}

QPushButton:disabled {
    background-color: #fdf6e3;
    color: #93a1a1;
    border: 2px solid #eee8d5;
}

QLabel {
    color: #657b83;
}

QGroupBox {
    background-color: #eee8d5;
    border: 2px solid #93a1a1;
    border-radius: 5px;
    margin-top: 10px;
    padding: 10px;
    color: #586e75;
    font-weight: bold;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 5px;
}

QListWidget {
    background-color: #fdf6e3;
    color: #657b83;
    border: 1px solid #93a1a1;
    border-radius: 3px;
}

QListWidget::item:selected {
    background-color: #268bd2;
    color: #fdf6e3;
}

QCheckBox {
    color: #657b83;
}

QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border: 2px solid #93a1a1;
    border-radius: 3px;
    background-color: #eee8d5;
}

QCheckBox::indicator:checked {
    background-color: #268bd2;
}

QComboBox {
    background-color: #eee8d5;
    color: #657b83;
    border: 1px solid #93a1a1;
}

QComboBox:hover {
    border: 1px solid #268bd2;
}

QComboBox QAbstractItemView {
    background-color: #eee8d5;
    color: #657b83;
    selection-background-color: #268bd2;
    selection-color: #fdf6e3;
}

QSpinBox, QDoubleSpinBox {
    background-color: #eee8d5;
    color: #657b83;
    border: 1px solid #93a1a1;
    border-radius: 3px;
    padding: 3px;
}

QSpinBox:hover, QDoubleSpinBox:hover {
    border: 1px solid #268bd2;
}

QTabWidget::pane {
    border: 1px solid #93a1a1;
    background-color: #eee8d5;
}

QTabBar::tab {
    background-color: #fdf6e3;
    color: #657b83;
    border: 1px solid #93a1a1;
    padding: 8px 16px;
    margin-right: 2px;
}

QTabBar::tab:selected {
    background-color: #268bd2;
    color: #fdf6e3;
}

QTabBar::scroller {
    width: 24px;
}

QTabBar QToolButton {
    background-color: #fdf6e3;
    border: 1px solid #93a1a1;
}

QTabBar::tab:hover {
    background-color: #e8e2cf;
}

QLabel#info_panel {
    background-color: rgba(238, 232, 213, 200);
    color: #2aa198;
    border: 1px solid #93a1a1;
    border-radius: 5px;
    padding: 10px;
    font-size: 12px;
    font-family: monospace;
}
"""

COLORFUL_THEME = """
QMainWindow {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                                      stop:0 #1a3a52, stop:1 #0f1e2e);
}

QWidget {
    background-color: #0f1e2e;
}

QPushButton {
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                       stop:0 #2c5f7e, stop:1 #1c4a6e);
    color: #d4e8ff;
    border: 2px solid #4a7c9e;
    border-radius: 8px;
    padding: 6px 16px;
    font-size: 13px;
    font-weight: bold;
    min-width: 120px;
    min-height: 18px;
}

QPushButton:hover {
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                       stop:0 #3c8fae, stop:1 #2c7f9e);
    border: 2px solid #6bcf9d;
}

QPushButton:pressed {
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                       stop:0 #1c4a6e, stop:1 #0c3a5e);
}

QPushButton:checked {
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                       stop:0 #6bcf9d, stop:1 #44a569);
    color: #ffffff;
    border: 2px solid #57cafe;
}

QPushButton:disabled {
    background-color: #1a3a52;
    color: #4a7c9e;
    border: 2px solid #1c4a6e;
}

QLabel {
    color: #d4e8ff;
}

QGroupBox {
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                       stop:0 #1c4a6e, stop:1 #0c3a5e);
    border: 2px solid #4a7c9e;
    border-radius: 5px;
    margin-top: 10px;
    padding: 10px;
    color: #d4e8ff;
    font-weight: bold;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 5px;
}

QListWidget {
    background-color: #0f1e2e;
    color: #d4e8ff;
    border: 1px solid #4a7c9e;
    border-radius: 3px;
}

QListWidget::item:selected {
    background-color: #6bcf9d;
    color: #ffffff;
}

QComboBox {
    background-color: #1c4a6e;
    color: #d4e8ff;
    border: 1px solid #4a7c9e;
    border-radius: 3px;
    padding: 5px;
}

QComboBox:hover {
    border: 1px solid #6bcf9d;
}

QComboBox::drop-down {
    border: none;
}

QComboBox QAbstractItemView {
    background-color: #1c4a6e;
    color: #d4e8ff;
    selection-background-color: #6bcf9d;
    selection-color: #ffffff;
}

QSpinBox, QDoubleSpinBox {
    background-color: #1c4a6e;
    color: #d4e8ff;
    border: 1px solid #4a7c9e;
    border-radius: 3px;
    padding: 3px;
}

QSpinBox:hover, QDoubleSpinBox:hover {
    border: 1px solid #6bcf9d;
}

QCheckBox {
    color: #d4e8ff;
}

QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border: 2px solid #4a7c9e;
    border-radius: 3px;
    background-color: #1c4a6e;
}

QCheckBox::indicator:checked {
    background-color: #6bcf9d;
}

QTabWidget::pane {
    border: 1px solid #4a7c9e;
    background-color: #1c4a6e;
}

QTabBar::tab {
    background-color: #0f1e2e;
    color: #d4e8ff;
    border: 1px solid #4a7c9e;
    padding: 8px 16px;
    margin-right: 2px;
}

QTabBar::tab:selected {
    background-color: #6bcf9d;
    color: #ffffff;
}

QTabBar::scroller {
    width: 24px;
}

QTabBar QToolButton {
    background-color: #0f1e2e;
    border: 1px solid #4a7c9e;
}

QTabBar::tab:hover {
    background-color: #1c4a6e;
}

QLabel#info_panel {
    background-color: rgba(12, 58, 94, 200);
    color: #57cafe;
    border: 1px solid #4a7c9e;
    border-radius: 5px;
    padding: 10px;
    font-size: 12px;
    font-family: monospace;
}
"""

# Retro themes are generated from shared templates (see _retro.py) so every
# one gets the same, complete widget coverage - one palette per theme.
from ._retro import build_xp_theme, LUNA, SILVER, OLIVE
from ._instrument import build_instrument_theme, IBM, HP


# The four standard themes share two fixes the retro themes already have: label/checkbox rows
# must not paint the window colour over their group box (visible as darker strips), and
# spin/combo/scrollbar buttons need arrow glyphs.
from ._retro import _ARROWS, _render


def _field_look(qss: str):
    """(background, text, border) of the theme's own spin-box rule, so text fields can match it."""
    import re
    m = re.search(r"\nQSpinBox, QDoubleSpinBox \{([^}]*)\}", qss)
    body = m.group(1) if m else ""

    def pick(prop):
        found = re.search(r"(?<![-\w])" + prop + r":\s*([^;]+);", body)
        return found.group(1).strip() if found else None

    border = pick("border") or ""
    border_color = border.split()[-1] if border else None
    return pick("background-color"), pick("color"), border_color


def _with_common_fixes(qss: str, glyph: str, disabled: str, ring: str, accent: str) -> str:
    fixes = "\nQLabel, QCheckBox, QRadioButton { background-color: transparent; }\n"
    # Radio labels had no text colour of their own (unlike checkboxes), so on dark themes they fell back
    # to the default near-black text and all but vanished
    fixes += "QRadioButton { color: " + glyph + "; }\n"
    # Text fields had no rule at all in these themes: default text colour on the theme's own background
    bg, fg, edge = _field_look(qss)
    if bg and fg:
        fixes += (
            "QLineEdit, QTextEdit, QPlainTextEdit { background-color: " + bg + "; color: " + fg + "; "
            "border: 1px solid " + (edge or ring) + "; border-radius: 3px; padding: 3px; "
            "selection-background-color: " + accent + "; selection-color: #ffffff; }\n"
            "QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus { border: 1px solid " + accent + "; }\n"
            "QLineEdit:disabled, QTextEdit:disabled, QPlainTextEdit:disabled { color: " + disabled + "; }\n"
        )
    # A visible radio ring (unchecked radios had no outline at all) with an accent dot when checked
    fixes += (
        "QRadioButton::indicator { width: 12px; height: 12px; border: 2px solid " + ring + "; "
        "border-radius: 8px; background: transparent; }\n"
        "QRadioButton::indicator:checked { background: qradialgradient(cx:0.5, cy:0.5, radius:0.5, "
        "fx:0.5, fy:0.5, stop:0 " + accent + ", stop:0.5 " + accent + ", stop:0.6 rgba(0,0,0,0), "
        "stop:1 rgba(0,0,0,0)); }\n"
    )
    return qss + fixes + _render(_ARROWS, {"GLYPH": glyph, "DISABLED": disabled})


# OLED Black: the Dark theme's structure on true black (pixels off) with very dark panel
# separation and dimmed text/accents - no pure-white text, no bright saturated accent.
_OLED_COLORS = {
    "#23262b": "#000000", "#2d3137": "#0b0b0c", "#3f454d": "#26282b", "#373c43": "#141517",
    "#1f2226": "#050505", "#c8cdd4": "#b4b9c0", "#eef2f6": "#e6eaee", "#4f9fd8": "#3f86bf",
    "#74bde8": "#5aa3d4", "#6c737c": "#5a5f66", "#86d192": "#6fbf7c",
    "rgba(22, 24, 28, 200)": "rgba(0, 0, 0, 230)",
}


def _recolor(qss: str, mapping: dict) -> str:
    import re
    pattern = re.compile("|".join(re.escape(k) for k in sorted(mapping, key=len, reverse=True)), re.I)
    return pattern.sub(lambda m: mapping[m.group(0).lower()], qss)


OLED_THEME = _with_common_fixes(_recolor(DARK_THEME, _OLED_COLORS), "#b4b9c0", "#5a5f66", "#6a6f77", "#3f86bf")
DARK_THEME = _with_common_fixes(DARK_THEME, "#c8cdd4", "#6c737c", "#7d848e", "#4f9fd8")
LIGHT_THEME = _with_common_fixes(LIGHT_THEME, "#323840", "#939aa3", "#8a919b", "#3b82c4")
SOLARIZED_THEME = _with_common_fixes(SOLARIZED_THEME, "#657b83", "#93a1a1", "#93a1a1", "#268bd2")
COLORFUL_THEME = _with_common_fixes(COLORFUL_THEME, "#d4e8ff", "#6c8aa8", "#6f9cc0", "#5aa9e6")

LUNA_THEME = build_xp_theme(LUNA)
SILVER_THEME = build_xp_theme(SILVER)
OLIVE_THEME = build_xp_theme(OLIVE)
IBM_THEME = build_instrument_theme(IBM)
HP_THEME = build_instrument_theme(HP)

# Theme name to stylesheet mapping
THEMES = {
    "Dark Mode": DARK_THEME,
    "OLED Black": OLED_THEME,
    "Light Mode": LIGHT_THEME,
    "Solarized": SOLARIZED_THEME,
    "Colorful": COLORFUL_THEME,
    "Win XP Luna": LUNA_THEME,
    "Silver": SILVER_THEME,
    "Olive": OLIVE_THEME,
    "Classic IBM": IBM_THEME,
    "Classic HP": HP_THEME
}

# Cross-theme state-color overrides for buttons whose meaning (recording,
# frozen, primary action) needs a fixed, universally-recognizable color
# regardless of the active theme's palette.
#
# These use attribute selectors (QPushButton[state="true"]) rather than a
# widget-level setStyleSheet() override, so Qt's cascade only replaces
# background-color/color and leaves each theme's own QPushButton rule
# (border-radius, padding, border-width, min-width) in place. The previous
# pattern - e.g. record_btn.setStyleSheet("background-color: #ff4444; color:
# white;") - replaced the ENTIRE stylesheet for that widget, so the button
# visually "flattened" (square corners, no border, no padding) the instant
# recording started, on every one of the 9 themes.
#
# Append this to whichever theme stylesheet is applied; use
# set_button_state() below instead of setStyleSheet() to toggle a button
# into one of these states.
STATE_COLORS_QSS = """
QPushButton[recording="true"] {
    background-color: #ff4444;
    color: #ffffff;
}

QPushButton[frozen="true"] {
    background-color: #4444ff;
    color: #ffffff;
}

/* Small fixed-width buttons (Scan, colour swatch, row remove) can't hold the standard
   padding/min-width, so they opt out: set_button_state(btn, "compact", True) */
QPushButton[compact="true"] {
    padding: 1px 4px;
    min-width: 0px;
    min-height: 0px;
    font-size: 12px;
}

QPushButton[accent="primary"] {
    background-color: #4CAF50;
    color: #ffffff;
}
"""


AUTO_THEME = "auto"
AUTO_THEME_LABEL = "Auto (Follow System)"


def system_prefers_dark():
    """
    True/False if the OS is set to dark/light mode, or None if it can't be determined.

    Uses Qt's color scheme (Qt 6.5+; live on Windows 10/11, macOS, most Linux desktops),
    then falls back to the Windows "Apps use light theme" registry value.
    """
    try:
        from PyQt6.QtCore import Qt
        from PyQt6.QtGui import QGuiApplication
        hints = QGuiApplication.styleHints()
        if hints is not None and hasattr(hints, "colorScheme"):
            scheme = hints.colorScheme()
            if scheme == Qt.ColorScheme.Dark:
                return True
            if scheme == Qt.ColorScheme.Light:
                return False
    except Exception:
        pass
    try:
        import winreg
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
        ) as key:
            return winreg.QueryValueEx(key, "AppsUseLightTheme")[0] == 0
    except Exception:
        return None


def resolve_auto_theme(now_hour=None) -> str:
    """
    Theme name for "auto": follows the OS light/dark setting. If the OS setting can't
    be read, falls back to time of day (light 07:00-19:00) as before.
    """
    dark = system_prefers_dark()
    if dark is None:
        import datetime
        hour = datetime.datetime.now().hour if now_hour is None else now_hour
        dark = not (7 <= hour < 19)
    return "Dark Mode" if dark else "Light Mode"


def set_button_state(button, property_name: str, value) -> None:
    """
    Set one of STATE_COLORS_QSS's attribute-selector properties on a button.

    ``value`` matches whatever the corresponding QSS selector compares
    against - a bool for e.g. ``[recording="true"]``, or a string for e.g.
    ``[accent="primary"]``.

    Qt only re-evaluates a stylesheet attribute selector after the widget's
    style is explicitly unpolished/repolished - a bare setProperty() call is
    silently ignored until the next full style refresh.
    """
    button.setProperty(property_name, value)
    button.style().unpolish(button)
    button.style().polish(button)

__all__ = [
    'DARK_THEME',
    'OLED_THEME',
    'LIGHT_THEME',
    'SOLARIZED_THEME',
    'COLORFUL_THEME',
    'LUNA_THEME',
    'SILVER_THEME',
    'OLIVE_THEME',
    'IBM_THEME',
    'HP_THEME',
    'THEMES',
    'STATE_COLORS_QSS',
    'set_button_state',
    'AUTO_THEME',
    'AUTO_THEME_LABEL',
    'system_prefers_dark',
    'resolve_auto_theme',
]
