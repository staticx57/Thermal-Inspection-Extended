"""
Application themes for the Thermal Inspection GUI.

Themes are defined as Qt stylesheet (QSS) strings.
Available themes: Dark Mode, Light Mode, Solarized, Colorful, Win XP Luna, Silver, Olive
"""

DARK_THEME = """
QMainWindow {
    background-color: #1a1a1a;
}

QWidget {
    background-color: #1a1a1a;
}

QPushButton {
    background-color: #2d2d2d;
    color: #e0e0e0;
    border: 2px solid #404040;
    border-radius: 8px;
    padding: 10px 20px;
    font-size: 14px;
    font-weight: bold;
    min-width: 120px;
}

QPushButton:hover {
    background-color: #3d3d3d;
    border: 2px solid #00aaff;
}

QPushButton:pressed {
    background-color: #1d1d1d;
}

QPushButton:checked {
    background-color: #00aaff;
    color: #ffffff;
    border: 2px solid #00ddff;
}

QPushButton:disabled {
    background-color: #1a1a1a;
    color: #666666;
    border: 2px solid #2d2d2d;
}

QLabel {
    color: #e0e0e0;
}

QLabel#info_panel {
    background-color: rgba(0, 0, 0, 180);
    color: #00ff00;
    border: 1px solid #404040;
    border-radius: 5px;
    padding: 10px;
    font-size: 12px;
    font-family: monospace;
}

QGroupBox {
    background-color: #2d2d2d;
    border: 2px solid #404040;
    border-radius: 5px;
    margin-top: 10px;
    padding: 10px;
    color: #e0e0e0;
    font-weight: bold;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 5px;
}

QListWidget {
    background-color: #1a1a1a;
    color: #e0e0e0;
    border: 1px solid #404040;
    border-radius: 3px;
}

QListWidget::item:selected {
    background-color: #00aaff;
    color: #ffffff;
}

QComboBox {
    background-color: #2d2d2d;
    color: #e0e0e0;
    border: 1px solid #404040;
    border-radius: 3px;
    padding: 5px;
}

QComboBox:hover {
    border: 1px solid #00aaff;
}

QComboBox::drop-down {
    border: none;
}

QComboBox QAbstractItemView {
    background-color: #2d2d2d;
    color: #e0e0e0;
    selection-background-color: #00aaff;
    selection-color: #ffffff;
}

QSpinBox, QDoubleSpinBox {
    background-color: #2d2d2d;
    color: #e0e0e0;
    border: 1px solid #404040;
    border-radius: 3px;
    padding: 3px;
}

QSpinBox:hover, QDoubleSpinBox:hover {
    border: 1px solid #00aaff;
}

QCheckBox {
    color: #e0e0e0;
}

QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border: 2px solid #404040;
    border-radius: 3px;
    background-color: #2d2d2d;
}

QCheckBox::indicator:checked {
    background-color: #00aaff;
}

QTabWidget::pane {
    border: 1px solid #404040;
    background-color: #2d2d2d;
}

QTabBar::tab {
    background-color: #1a1a1a;
    color: #e0e0e0;
    border: 1px solid #404040;
    padding: 8px 16px;
    margin-right: 2px;
}

QTabBar::tab:selected {
    background-color: #00aaff;
    color: #ffffff;
}

QTabBar::tab:hover {
    background-color: #3d3d3d;
}
"""

LIGHT_THEME = """
QMainWindow {
    background-color: #f5f5f5;
}

QWidget {
    background-color: #f5f5f5;
}

QPushButton {
    background-color: #ffffff;
    color: #202020;
    border: 2px solid #c0c0c0;
    border-radius: 8px;
    padding: 10px 20px;
    font-size: 14px;
    font-weight: bold;
    min-width: 120px;
}

QPushButton:hover {
    background-color: #f0f0f0;
    border: 2px solid #0080ff;
}

QPushButton:pressed {
    background-color: #e0e0e0;
}

QPushButton:checked {
    background-color: #0080ff;
    color: #ffffff;
    border: 2px solid #0099ff;
}

QPushButton:disabled {
    background-color: #f5f5f5;
    color: #a0a0a0;
    border: 2px solid #d0d0d0;
}

QLabel {
    color: #202020;
}

QLabel#info_panel {
    background-color: rgba(255, 255, 255, 200);
    color: #006600;
    border: 1px solid #c0c0c0;
    border-radius: 5px;
    padding: 10px;
    font-size: 12px;
    font-family: monospace;
}

QGroupBox {
    background-color: #ffffff;
    border: 2px solid #c0c0c0;
    border-radius: 5px;
    margin-top: 10px;
    padding: 10px;
    color: #202020;
    font-weight: bold;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 5px;
}

QListWidget {
    background-color: #ffffff;
    color: #202020;
    border: 1px solid #c0c0c0;
    border-radius: 3px;
}

QListWidget::item:selected {
    background-color: #0080ff;
    color: #ffffff;
}

QComboBox {
    background-color: #ffffff;
    color: #202020;
    border: 1px solid #c0c0c0;
    border-radius: 3px;
    padding: 5px;
}

QComboBox:hover {
    border: 1px solid #0080ff;
}

QComboBox::drop-down {
    border: none;
}

QComboBox QAbstractItemView {
    background-color: #ffffff;
    color: #202020;
    selection-background-color: #0080ff;
    selection-color: #ffffff;
}

QSpinBox, QDoubleSpinBox {
    background-color: #ffffff;
    color: #202020;
    border: 1px solid #c0c0c0;
    border-radius: 3px;
    padding: 3px;
}

QSpinBox:hover, QDoubleSpinBox:hover {
    border: 1px solid #0080ff;
}

QCheckBox {
    color: #202020;
}

QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border: 2px solid #c0c0c0;
    border-radius: 3px;
    background-color: #ffffff;
}

QCheckBox::indicator:checked {
    background-color: #0080ff;
}

QTabWidget::pane {
    border: 1px solid #c0c0c0;
    background-color: #ffffff;
}

QTabBar::tab {
    background-color: #f5f5f5;
    color: #202020;
    border: 1px solid #c0c0c0;
    padding: 8px 16px;
    margin-right: 2px;
}

QTabBar::tab:selected {
    background-color: #0080ff;
    color: #ffffff;
}

QTabBar::tab:hover {
    background-color: #e0e0e0;
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
    padding: 10px 20px;
    font-size: 14px;
    font-weight: bold;
    min-width: 120px;
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
    padding: 10px 20px;
    font-size: 14px;
    font-weight: bold;
    min-width: 120px;
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

LUNA_THEME = """
QMainWindow, QWidget { background-color: #ECE9D8; color: #000000; font-family: 'Tahoma', 'Segoe UI'; font-size: 9pt; }
QPushButton {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #FFFFFF, stop:1 #E0E0E0);
    color: #000000; border: 2px solid #003C74;
    border-radius: 4px; padding: 7px; font-weight: bold;
    min-height: 20px;
}
QPushButton:hover {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #FFF7E0, stop:1 #FFE0A0);
    border-color: #E68B2C; border-width: 2px;
}
QPushButton:pressed {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #C0C0C0, stop:1 #D0D0D0);
    border-color: #003C74;
}
QPushButton:checked {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #A0C0FF, stop:1 #6090FF);
    color: #FFFFFF; border-color: #0054E3;
}
QGroupBox {
    border: 2px solid #0054E3; border-radius: 5px; margin-top: 20px;
    padding-top: 5px;
    background-color: #FAFAF8; color: #000000; font-weight: bold;
}
QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top left; left: 10px; padding: 0 3px; color: #0054E3; font-size: 11pt; }
QLabel { color: #000000; background-color: transparent; }
QCheckBox { spacing: 5px; color: #000000; font-weight: bold; }
QCheckBox::indicator { width: 13px; height: 13px; border: 1px solid #003C74; background-color: #FFFFFF; }
QCheckBox::indicator:checked { background-color: #0054E3; }
QRadioButton { spacing: 5px; color: #000000; font-weight: bold; }
QRadioButton::indicator { width: 13px; height: 13px; border: 2px solid #003C74; border-radius: 7px; background-color: #FFFFFF; }
QRadioButton::indicator:checked { background-color: #0054E3; }
QTabWidget::pane { border: 2px solid #003C74; background-color: #ECE9D8; }
QTabBar::tab {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #F0EFE8, stop:1 #D8D6C8);
    color: #000000; border: 1px solid #7F9DB9;
    padding: 8px 14px; margin-right: 2px; font-weight: bold;
}
QTabBar::tab:selected {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #FFFFFF, stop:1 #F0F0F0);
    border-bottom-color: #FFFFFF; border-width: 2px; border-bottom-width: 0px;
}
QListWidget { background-color: #FFFFFF; color: #000000; border: 2px solid #7F9DB9; }
QLineEdit, QTextEdit { background-color: #FFFFFF; color: #000000; border: 1px solid #7F9DB9; padding: 3px; selection-background-color: #316AC5; selection-color: #FFFFFF; }
QSpinBox, QDoubleSpinBox, QComboBox { background-color: #FFFFFF; color: #000000; border: 1px solid #7F9DB9; padding: 3px; }
QComboBox::drop-down { border-left: 1px solid #7F9DB9; background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #F0EFE8, stop:1 #D8D6C8); }
QSlider::groove:horizontal { border: 1px solid #7F9DB9; height: 6px; background: #E0E0E0; }
QSlider::handle:horizontal { background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #FFFFFF, stop:1 #D0D0D0);
    border: 2px solid #003C74; width: 14px; margin: -5px 0; border-radius: 7px; }
QScrollBar:vertical { border: 1px solid #7F9DB9; background: #ECE9D8; width: 16px; }
QScrollBar::handle:vertical { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #FFFFFF, stop:1 #D8D6C8); min-height: 20px; border: 1px solid #7F9DB9; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
QScrollBar:horizontal { border: 1px solid #7F9DB9; background: #ECE9D8; height: 16px; }
QScrollBar::handle:horizontal { background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #FFFFFF, stop:1 #D8D6C8); min-width: 20px; border: 1px solid #7F9DB9; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0px; }
"""

SILVER_THEME = """
QMainWindow, QWidget { background-color: #E0DFE3; color: #000000; font-family: 'Tahoma', 'Segoe UI'; font-size: 9pt; }
QPushButton {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #FAFAFA, stop:1 #D8D8D8);
    color: #000000; border: 2px solid #606060;
    border-radius: 4px; padding: 7px; font-weight: bold;
    min-height: 20px;
}
QPushButton:hover {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #FFFFFF, stop:1 #E8E8E8);
    border-color: #909090; border-width: 2px;
}
QPushButton:pressed {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #B0B0B0, stop:1 #C8C8C8);
    border-color: #505050;
}
QPushButton:checked {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #A0A0B0, stop:1 #707080);
    color: #FFFFFF; border-color: #404050;
}
QGroupBox {
    border: 2px solid #707070; border-radius: 5px; margin-top: 20px;
    padding-top: 5px;
    background-color: #F0EFF3; color: #000000; font-weight: bold;
}
QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top left; left: 10px; padding: 0 3px; color: #404040; font-size: 11pt; }
QLabel { color: #000000; background-color: transparent; }
QCheckBox { spacing: 5px; color: #000000; font-weight: bold; }
QCheckBox::indicator { width: 13px; height: 13px; border: 1px solid #606060; background-color: #FFFFFF; }
QCheckBox::indicator:checked { background-color: #707070; }
QRadioButton { spacing: 5px; color: #000000; font-weight: bold; }
QRadioButton::indicator { width: 13px; height: 13px; border: 2px solid #606060; border-radius: 7px; background-color: #FFFFFF; }
QRadioButton::indicator:checked { background-color: #707070; }
QTabWidget::pane { border: 2px solid #707070; background-color: #E0DFE3; }
QTabBar::tab {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #ECECF0, stop:1 #C8C8D0);
    color: #000000; border: 1px solid #707070;
    padding: 8px 14px; margin-right: 2px; font-weight: bold;
}
QTabBar::tab:selected {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #FFFFFF, stop:1 #F0F0F0);
    border-bottom-color: #FFFFFF; border-width: 2px; border-bottom-width: 0px;
}
QListWidget { background-color: #FFFFFF; color: #000000; border: 2px solid #707070; }
QLineEdit, QTextEdit { background-color: #FFFFFF; color: #000000; border: 1px solid #707070; padding: 3px; selection-background-color: #6B6B83; selection-color: #FFFFFF; }
QSpinBox, QDoubleSpinBox, QComboBox { background-color: #FFFFFF; color: #000000; border: 1px solid #707070; padding: 3px; }
QComboBox::drop-down { border-left: 1px solid #707070; background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #ECECF0, stop:1 #C8C8D0); }
QSlider::groove:horizontal { border: 1px solid #707070; height: 6px; background: #D0D0D0; }
QSlider::handle:horizontal { background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #F0F0F0, stop:1 #C0C0C0);
    border: 2px solid #606060; width: 14px; margin: -5px 0; border-radius: 7px; }
QScrollBar:vertical { border: 1px solid #707070; background: #E0DFE3; width: 16px; }
QScrollBar::handle:vertical { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #FAFAFA, stop:1 #C8C8D0); min-height: 20px; border: 1px solid #707070; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
QScrollBar:horizontal { border: 1px solid #707070; background: #E0DFE3; height: 16px; }
QScrollBar::handle:horizontal { background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #FAFAFA, stop:1 #C8C8D0); min-width: 20px; border: 1px solid #707070; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0px; }
"""

OLIVE_THEME = """
QMainWindow, QWidget { background-color: #F6F7F2; color: #000000; font-family: 'Tahoma', 'Segoe UI'; font-size: 9pt; }
QPushButton {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #F8F8DC, stop:1 #E0E0B8);
    color: #000000; border: 2px solid #607450;
    border-radius: 4px; padding: 7px; font-weight: bold;
    min-height: 20px;
}
QPushButton:hover {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #FFFFEA, stop:1 #F0F0C8);
    border-color: #E68B2C; border-width: 2px;
}
QPushButton:pressed {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #C8C8A0, stop:1 #D8D8B0);
    border-color: #506840;
}
QPushButton:checked {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #A0BF90, stop:1 #708060);
    color: #FFFFFF; border-color: #506840;
}
QGroupBox {
    border: 2px solid #A5BFA0; border-radius: 5px; margin-top: 20px;
    padding-top: 5px;
    background-color: #FCFCF7; color: #000000; font-weight: bold;
}
QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top left; left: 10px; padding: 0 3px; color: #607450; font-size: 11pt; }
QLabel { color: #000000; background-color: transparent; }
QCheckBox { spacing: 5px; color: #000000; font-weight: bold; }
QCheckBox::indicator { width: 13px; height: 13px; border: 1px solid #607450; background-color: #FFFFFF; }
QCheckBox::indicator:checked { background-color: #A5BFA0; }
QRadioButton { spacing: 5px; color: #000000; font-weight: bold; }
QRadioButton::indicator { width: 13px; height: 13px; border: 2px solid #607450; border-radius: 7px; background-color: #FFFFFF; }
QRadioButton::indicator:checked { background-color: #A5BFA0; }
QTabWidget::pane { border: 2px solid #A5BFA0; background-color: #F6F7F2; }
QTabBar::tab {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #F0F2EC, stop:1 #D8DAD0);
    color: #000000; border: 1px solid #A5BFA0;
    padding: 8px 14px; margin-right: 2px; font-weight: bold;
}
QTabBar::tab:selected {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #FFFFFF, stop:1 #F8F8F0);
    border-bottom-color: #FFFFFF; border-width: 2px; border-bottom-width: 0px;
}
QListWidget { background-color: #FFFFFF; color: #000000; border: 2px solid #A5BFA0; }
QLineEdit, QTextEdit { background-color: #FFFFFF; color: #000000; border: 1px solid #A5BFA0; padding: 3px; selection-background-color: #739E6D; selection-color: #FFFFFF; }
QSpinBox, QDoubleSpinBox, QComboBox { background-color: #FFFFFF; color: #000000; border: 1px solid #A5BFA0; padding: 3px; }
QComboBox::drop-down { border-left: 1px solid #A5BFA0; background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #F0F2EC, stop:1 #D8DAD0); }
QSlider::groove:horizontal { border: 1px solid #A5BFA0; height: 6px; background: #E8E8D8; }
QSlider::handle:horizontal { background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #F8F8DC, stop:1 #D8D8B8);
    border: 2px solid #607450; width: 14px; margin: -5px 0; border-radius: 7px; }
QScrollBar:vertical { border: 1px solid #A5BFA0; background: #F6F7F2; width: 16px; }
QScrollBar::handle:vertical { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #F8F8DC, stop:1 #D8DAD0); min-height: 20px; border: 1px solid #A5BFA0; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
QScrollBar:horizontal { border: 1px solid #A5BFA0; background: #F6F7F2; height: 16px; }
QScrollBar::handle:horizontal { background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #F8F8DC, stop:1 #D8DAD0); min-width: 20px; border: 1px solid #A5BFA0; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0px; }
"""

# Theme name to stylesheet mapping
THEMES = {
    "Dark Mode": DARK_THEME,
    "Light Mode": LIGHT_THEME,
    "Solarized": SOLARIZED_THEME,
    "Colorful": COLORFUL_THEME,
    "Win XP Luna": LUNA_THEME,
    "Silver": SILVER_THEME,
    "Olive": OLIVE_THEME
}

__all__ = [
    'DARK_THEME',
    'LIGHT_THEME',
    'SOLARIZED_THEME',
    'COLORFUL_THEME',
    'LUNA_THEME',
    'SILVER_THEME',
    'OLIVE_THEME',
    'THEMES'
]
