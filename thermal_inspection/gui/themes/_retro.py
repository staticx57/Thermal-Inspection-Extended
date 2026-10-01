"""
Stylesheet templates for the retro themes.

``build_xp_theme`` builds the Windows XP family (Luna / Silver / Olive): soft rounded
controls, light gradients, blue-button arrows and scrollbars, driven by a palette dict so
every theme of the family gets the same (complete) widget coverage. (The IBM / HP hardware
themes live in _instrument.py and reuse this module's arrow images and renderer.)

The template covers every control the app uses - including the ones the earlier
per-theme stylesheets skipped (headers, tables/trees, menus, tooltips,
progress bars, disabled states, combo popups, spin-box/combo/scrollbar
arrows) - and draw arrows with border triangles so no image files are needed.

Templates use @TOKEN@ placeholders rather than str.format, because QSS is
full of literal braces.
"""

_INFO_PANEL = """
QLabel#info_panel {
    background-color: rgba(0, 15, 40, 200);
    color: #6BD4FF;
    border: 1px solid @ACCENT@;
    border-radius: 2px;
    padding: 10px;
    font-size: 12px;
    font-family: 'Consolas', 'Courier New', monospace;
}
"""

# Arrow glyphs are tiny generated PNGs (see _arrow_image) - Qt renders the
# border-triangle trick as a solid rectangle. Shared by both families.
_ARROWS = """
QComboBox::down-arrow, QSpinBox::down-arrow, QDoubleSpinBox::down-arrow { image: url(@IMG_DOWN@); width: 9px; height: 5px; }
QComboBox::down-arrow:disabled, QSpinBox::down-arrow:disabled, QDoubleSpinBox::down-arrow:disabled { image: url(@IMG_DOWN_DIS@); }
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow { image: url(@IMG_UP@); width: 9px; height: 5px; }
QSpinBox::up-arrow:disabled, QDoubleSpinBox::up-arrow:disabled { image: url(@IMG_UP_DIS@); }
QScrollBar::up-arrow:vertical { image: url(@IMG_UP@); width: 9px; height: 5px; }
QScrollBar::down-arrow:vertical { image: url(@IMG_DOWN@); width: 9px; height: 5px; }
QScrollBar::left-arrow:horizontal { image: url(@IMG_LEFT@); width: 5px; height: 9px; }
QScrollBar::right-arrow:horizontal { image: url(@IMG_RIGHT@); width: 5px; height: 9px; }
"""

# ---------------------------------------------------------------------------
# Windows XP family
# ---------------------------------------------------------------------------
_XP = """
QMainWindow, QDialog, QWidget { background-color: @BG@; color: @TEXT@; font-family: @FONT@; font-size: 9pt; }
QWidget:disabled { color: @DISABLED@; }
QToolTip { background-color: #FFFFE1; color: #000000; border: 1px solid #000000; padding: 2px; }

QPushButton, QToolButton {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 @FACE_TOP@, stop:1 @FACE_BOT@);
    color: @TEXT@; border: 1px solid @BORDER@; border-radius: 3px;
}
/* Same outer size as the Dark/Light/Solarized/Colorful buttons (2px border + 6px/16px
   padding, 13px bold, 120px min width) so the controls don't change size with the theme.
   This family has a 1px border, so the padding is 1px larger to compensate. */
QPushButton { padding: 7px 17px; min-width: 120px; min-height: 18px; font-size: 13px; font-weight: bold; }
QToolButton { padding: 3px 6px; }
QPushButton:hover, QToolButton:hover {
    border: 1px solid @BORDER@;
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 @HOVER_TOP@, stop:1 @HOVER_BOT@);
}
QPushButton:focus { border: 1px solid @HOVER@; }
QPushButton:pressed, QToolButton:pressed {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 @PRESS_TOP@, stop:1 @PRESS_BOT@);
}
QPushButton:checked, QToolButton:checked {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 @CHECKED_TOP@, stop:1 @CHECKED_BOT@);
    border: 1px solid @ACCENT@;
}
QPushButton:disabled, QToolButton:disabled {
    background: @BG@; color: @DISABLED@; border: 1px solid @DISABLED_BORDER@;
}

QGroupBox {
    border: 1px solid @GROUP_BORDER@; border-radius: 4px; margin-top: 10px; padding-top: 8px;
    background-color: transparent;
}
QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top left; left: 10px; padding: 0 4px; color: @TITLE@; font-weight: bold; }
QLabel { background-color: transparent; }
QCheckBox, QRadioButton { spacing: 6px; background-color: transparent; }
QCheckBox::indicator, QRadioButton::indicator { width: 13px; height: 13px; border: 1px solid @IND_BORDER@; background-color: #FFFFFF; }
QCheckBox::indicator:hover, QRadioButton::indicator:hover { border-color: @HOVER@; }
QCheckBox::indicator:checked { background-color: @CHECK@; }
QRadioButton::indicator { border-radius: 7px; }
QRadioButton::indicator:checked {
    background: qradialgradient(cx:0.5, cy:0.5, radius:0.5, fx:0.5, fy:0.5,
        stop:0 @CHECK@, stop:0.45 @CHECK@, stop:0.55 #FFFFFF, stop:1 #FFFFFF);
}
QCheckBox::indicator:disabled, QRadioButton::indicator:disabled { border-color: @DISABLED@; background-color: @BG@; }

QTabWidget::pane { border: 1px solid @PANE_BORDER@; background-color: @BG@; top: -1px; }
QTabBar::tab {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 @TAB_TOP@, stop:1 @TAB_BOT@);
    color: @TEXT@; border: 1px solid @PANE_BORDER@; border-bottom: none;
    border-top-left-radius: 3px; border-top-right-radius: 3px;
    padding: 4px 12px; margin-right: 1px; margin-top: 2px;
}
QTabBar::tab:hover { border-top: 2px solid @TAB_ACCENT@; }
QTabBar::tab:selected {
    background: @BG@; border-top: 3px solid @TAB_ACCENT@; margin-top: 0px; padding-bottom: 6px; font-weight: bold;
}
QTabBar::scroller { width: 20px; }
QTabBar QToolButton { padding: 0px; min-height: 0px; border-radius: 2px; }

QLineEdit, QTextEdit, QPlainTextEdit {
    background-color: #FFFFFF; color: #000000; border: 1px solid @FIELD_BORDER@; padding: 2px 3px;
    selection-background-color: @ACCENT@; selection-color: #FFFFFF;
}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus { border: 1px solid @TITLE@; }
QLineEdit:disabled, QTextEdit:disabled { background-color: @BG@; color: @DISABLED@; }
QSpinBox, QDoubleSpinBox, QComboBox {
    background-color: #FFFFFF; color: #000000; border: 1px solid @FIELD_BORDER@; padding: 2px 3px;
    selection-background-color: @ACCENT@; selection-color: #FFFFFF; min-height: 16px;
}
QSpinBox:disabled, QDoubleSpinBox:disabled, QComboBox:disabled { background-color: @BG@; color: @DISABLED@; }
QSpinBox { padding-right: 18px; }
QDoubleSpinBox { padding-right: 18px; }
QSpinBox::up-button, QSpinBox::down-button, QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {
    width: 15px; border: 1px solid @FIELD_BORDER@; border-radius: 2px;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 @ARROW_TOP@, stop:1 @ARROW_BOT@);
}
QSpinBox::up-button, QDoubleSpinBox::up-button { subcontrol-origin: border; subcontrol-position: top right; }
QSpinBox::down-button, QDoubleSpinBox::down-button { subcontrol-origin: border; subcontrol-position: bottom right; }
QSpinBox::up-button:hover, QSpinBox::down-button:hover, QDoubleSpinBox::up-button:hover, QDoubleSpinBox::down-button:hover { border-color: @HOVER@; }
QComboBox { padding-right: 20px; }
QComboBox::drop-down {
    subcontrol-origin: padding; subcontrol-position: top right; width: 17px;
    border: 1px solid @FIELD_BORDER@; border-radius: 2px;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 @ARROW_TOP@, stop:1 @ARROW_BOT@);
}
QComboBox::drop-down:hover { border-color: @HOVER@; }
QComboBox QAbstractItemView {
    background-color: #FFFFFF; color: #000000; border: 1px solid @FIELD_BORDER@;
    selection-background-color: @ACCENT@; selection-color: #FFFFFF; outline: none;
}

QSlider::groove:horizontal { border: 1px solid @FIELD_BORDER@; height: 4px; background: #FFFFFF; border-radius: 2px; }
QSlider::sub-page:horizontal { background: @ARROW_BOT@; border: 1px solid @FIELD_BORDER@; border-radius: 2px; }
QSlider::handle:horizontal {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 @FACE_TOP@, stop:1 @ARROW_BOT@);
    border: 1px solid @BORDER@; width: 10px; margin: -6px 0; border-radius: 3px;
}
QSlider::handle:horizontal:hover { border-color: @HOVER@; }
QSlider::groove:vertical { border: 1px solid @FIELD_BORDER@; width: 4px; background: #FFFFFF; border-radius: 2px; }
QSlider::handle:vertical {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 @FACE_TOP@, stop:1 @ARROW_BOT@);
    border: 1px solid @BORDER@; height: 10px; margin: 0 -6px; border-radius: 3px;
}

QProgressBar { border: 1px solid #686868; border-radius: 3px; background: #FFFFFF; text-align: center; color: #000000; min-height: 14px; }
QProgressBar::chunk { background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 @CHUNK_TOP@, stop:1 @CHUNK_BOT@); border-radius: 2px; margin: 1px; }

QListWidget, QListView, QTreeWidget, QTreeView, QTableWidget, QTableView {
    background-color: #FFFFFF; alternate-background-color: @ALT@; color: #000000;
    border: 1px solid @FIELD_BORDER@; gridline-color: @GRID@;
    selection-background-color: @ACCENT@; selection-color: #FFFFFF; outline: none;
}
QListWidget::item:selected, QTreeView::item:selected, QTableView::item:selected { background-color: @ACCENT@; color: #FFFFFF; }
QListWidget::item:hover, QTreeView::item:hover { background-color: @HOVER_ROW@; color: #000000; }
QHeaderView::section {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 @FACE_TOP@, stop:1 @FACE_BOT@);
    color: @TEXT@; border: none; border-right: 1px solid @GRID@; border-bottom: 1px solid @GROUP_BORDER@;
    padding: 3px 6px;
}
QTableCornerButton::section { background: @FACE_BOT@; border: none; }

QMenuBar { background-color: @BG@; color: @TEXT@; }
QMenuBar::item { background: transparent; padding: 3px 8px; }
QMenuBar::item:selected { background-color: @ACCENT@; color: #FFFFFF; }
QMenu { background-color: #FFFFFF; color: #000000; border: 1px solid @PANE_BORDER@; padding: 2px; }
QMenu::item { padding: 3px 24px 3px 22px; }
QMenu::item:selected { background-color: @ACCENT@; color: #FFFFFF; }
QMenu::item:disabled { color: @DISABLED@; background: transparent; }
QMenu::separator { height: 1px; background: @GROUP_BORDER@; margin: 3px 2px; }
QStatusBar { background-color: @BG@; color: @TEXT@; }
QSplitter::handle { background-color: @BG@; }
QSplitter::handle:hover { background-color: @ARROW_BOT@; }
QScrollArea { border: none; }

QScrollBar:vertical { background: @SCROLL_TRACK@; width: 17px; margin: 17px 0 17px 0; border: none; }
QScrollBar:horizontal { background: @SCROLL_TRACK@; height: 17px; margin: 0 17px 0 17px; border: none; }
QScrollBar::handle:vertical {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 @ARROW_TOP@, stop:1 @ARROW_BOT@);
    border: 1px solid @FIELD_BORDER@; border-radius: 3px; min-height: 24px;
}
QScrollBar::handle:horizontal {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 @ARROW_TOP@, stop:1 @ARROW_BOT@);
    border: 1px solid @FIELD_BORDER@; border-radius: 3px; min-width: 24px;
}
QScrollBar::handle:vertical:hover, QScrollBar::handle:horizontal:hover { border-color: @HOVER@; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical, QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 @ARROW_TOP@, stop:1 @ARROW_BOT@);
    border: 1px solid @FIELD_BORDER@; border-radius: 3px; subcontrol-origin: margin;
}
QScrollBar::add-line:vertical { height: 17px; subcontrol-position: bottom; }
QScrollBar::sub-line:vertical { height: 17px; subcontrol-position: top; }
QScrollBar::add-line:horizontal { width: 17px; subcontrol-position: right; }
QScrollBar::sub-line:horizontal { width: 17px; subcontrol-position: left; }
QScrollBar::add-page, QScrollBar::sub-page { background: none; }
""" + _ARROWS + _INFO_PANEL

def _png(width: int, height: int, pixels) -> bytes:
    """Minimal RGBA PNG encoder (pixels: rows of (r, g, b, a) tuples) - no Qt needed."""
    import struct
    import zlib

    def chunk(tag: bytes, data: bytes) -> bytes:
        body = tag + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

    raw = b"".join(b"\x00" + b"".join(bytes(px) for px in row) for row in pixels)
    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw))
            + chunk(b"IEND", b""))


def _arrow_image(direction: str, color_hex: str) -> str:
    """Path (forward slashes, QSS-safe) of a small triangle PNG, generated on first use."""
    import os
    import tempfile

    cache = os.path.join(tempfile.gettempdir(), "thermal_inspection_theme_arrows")
    path = os.path.join(cache, f"{direction}_{color_hex.lstrip('#').lower()}.png")
    if not os.path.exists(path):
        try:
            os.makedirs(cache, exist_ok=True)
            r, g, b = (int(color_hex.lstrip('#')[i:i + 2], 16) for i in (0, 2, 4))
            solid, clear = (r, g, b, 255), (0, 0, 0, 0)
            if direction in ("down", "up"):
                w, h = 9, 5
                rows = []
                for y in range(h):
                    fill = (w - 2 * y) if direction == "down" else (w - 2 * (h - 1 - y))
                    lo = (w - fill) // 2
                    rows.append([solid if lo <= x < lo + fill else clear for x in range(w)])
            else:
                w, h = 5, 9
                # Base on one side (full height), tip on the other: a left arrow has
                # its base on the right and narrows to a point on the left.
                rows = []
                for y in range(h):
                    span = min(y, h - 1 - y) + 1      # 1..5..1 pixels wide
                    if direction == "left":
                        rows.append([solid if x >= w - span else clear for x in range(w)])
                    else:
                        rows.append([solid if x < span else clear for x in range(w)])
            with open(path, "wb") as f:
                f.write(_png(w, h, rows))
        except OSError:
            pass  # arrows just won't draw; the rest of the theme is unaffected
    return path.replace("\\", "/")


def _render(template: str, palette: dict) -> str:
    import re
    values = dict(palette)
    glyph = palette["GLYPH"]
    dis = palette.get("DISABLED", "#808080")
    values.update(
        IMG_DOWN=_arrow_image("down", glyph), IMG_UP=_arrow_image("up", glyph),
        IMG_LEFT=_arrow_image("left", glyph), IMG_RIGHT=_arrow_image("right", glyph),
        IMG_DOWN_DIS=_arrow_image("down", dis), IMG_UP_DIS=_arrow_image("up", dis),
    )
    out = template
    for key, value in values.items():
        out = out.replace(f"@{key}@", value)
    left = sorted(set(re.findall(r"@[A-Z_]+@", out)))
    if left:
        raise KeyError(f"theme palette is missing: {left}")
    return out


def build_xp_theme(palette: dict) -> str:
    """Windows XP-style stylesheet (Luna/Silver/Olive) from a palette dict."""
    return _render(_XP, palette)


# ---------------------------------------------------------------------------
# Palettes
# ---------------------------------------------------------------------------
_XP_COMMON = {
    "TEXT": "#000000",
    "FONT": "'Tahoma', 'Segoe UI', sans-serif",
    "DISABLED": "#ACA899",
    "DISABLED_BORDER": "#C9C7BA",
    "CHECK": "#21A121",
    "CHUNK_TOP": "#7CD36C",
    "CHUNK_BOT": "#2FA524",
    "ALT": "#F5F4EC",
}

LUNA = dict(_XP_COMMON, **{
    "BG": "#ECE9D8", "FACE_TOP": "#FFFFFF", "FACE_BOT": "#ECEBE5",
    "HOVER_TOP": "#FFF3D6", "HOVER_BOT": "#FFD98A", "HOVER": "#E68B2C", "HOVER_ROW": "#E3EDFB",
    "PRESS_TOP": "#CECBBB", "PRESS_BOT": "#E1DED0",
    "CHECKED_TOP": "#B9CDF0", "CHECKED_BOT": "#DCE7FB",
    "BORDER": "#003C74", "ACCENT": "#316AC5", "TITLE": "#0046D5",
    "GROUP_BORDER": "#D0D0BF", "PANE_BORDER": "#919B9C", "FIELD_BORDER": "#7F9DB9",
    "IND_BORDER": "#1C5180", "TAB_TOP": "#F6F5EE", "TAB_BOT": "#E2DFCF", "TAB_ACCENT": "#FFC83C",
    "ARROW_TOP": "#C1D3FB", "ARROW_BOT": "#8DABE8", "GLYPH": "#4D6185",
    "SCROLL_TRACK": "#F3F1E7", "GRID": "#E0DED0",
})

SILVER = dict(_XP_COMMON, **{
    "BG": "#E0DFE3", "FACE_TOP": "#FFFFFF", "FACE_BOT": "#E3E3E8",
    "HOVER_TOP": "#FFF3D6", "HOVER_BOT": "#FFD98A", "HOVER": "#E68B2C", "HOVER_ROW": "#E8E8F0",
    "PRESS_TOP": "#C8C8D0", "PRESS_BOT": "#DADAE0",
    "CHECKED_TOP": "#C4C4D6", "CHECKED_BOT": "#E6E6F0",
    "BORDER": "#6B6B83", "ACCENT": "#6B6B83", "TITLE": "#4A4A66",
    "GROUP_BORDER": "#B8B8C4", "PANE_BORDER": "#9898A8", "FIELD_BORDER": "#A0A0B0",
    "IND_BORDER": "#505064", "TAB_TOP": "#F0EFF3", "TAB_BOT": "#D8D8DE", "TAB_ACCENT": "#E68B2C",
    "ARROW_TOP": "#F0F0F5", "ARROW_BOT": "#B8B8C8", "GLYPH": "#404050",
    "SCROLL_TRACK": "#ECECF0", "GRID": "#D0D0D8", "ALT": "#F3F3F7",
    "DISABLED": "#A0A0B0", "DISABLED_BORDER": "#C0C0CC",
})

OLIVE = dict(_XP_COMMON, **{
    "BG": "#E8E8D8", "FACE_TOP": "#FFFFFF", "FACE_BOT": "#E6E6D2",
    "HOVER_TOP": "#FFF3D6", "HOVER_BOT": "#FFD98A", "HOVER": "#E68B2C", "HOVER_ROW": "#F0F2E0",
    "PRESS_TOP": "#C8C8A0", "PRESS_BOT": "#D8D8B8",
    "CHECKED_TOP": "#C3D4A8", "CHECKED_BOT": "#E0EBCE",
    "BORDER": "#506840", "ACCENT": "#506840", "TITLE": "#3F6B2F",
    "GROUP_BORDER": "#C8C8A0", "PANE_BORDER": "#9CA882", "FIELD_BORDER": "#A5BFA0",
    "IND_BORDER": "#506840", "TAB_TOP": "#F0F0DC", "TAB_BOT": "#DCDCBC", "TAB_ACCENT": "#E68B2C",
    "ARROW_TOP": "#D8E4C0", "ARROW_BOT": "#A0BF90", "GLYPH": "#3A4F2C",
    "SCROLL_TRACK": "#F0F0E0", "GRID": "#DCDCC4", "ALT": "#F6F7EC",
    "DISABLED": "#A8A890", "DISABLED_BORDER": "#C8C8B0",
})
