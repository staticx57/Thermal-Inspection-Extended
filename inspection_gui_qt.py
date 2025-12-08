#!/usr/bin/env python3
"""
Qt-based GUI for Thermal Inspection Fusion Tool
Professional interface for circuit board and residential house inspection
Optimized for Jetson Orin and x86-64 platforms
"""
import sys
import numpy as np
from typing import List, Optional, Dict, Tuple
import logging
from pathlib import Path

try:
    from PyQt6.QtWidgets import (QMainWindow, QWidget, QLabel, QPushButton, QDialog,
                                  QVBoxLayout, QHBoxLayout, QGridLayout, QApplication,
                                  QSizePolicy, QFileDialog, QListWidget, QListWidgetItem,
                                  QComboBox, QSpinBox, QDoubleSpinBox, QCheckBox,
                                  QGroupBox, QScrollArea, QTabWidget, QFrame, QMessageBox,
                                  QSlider, QProgressBar, QMenu, QRadioButton)
    from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QThread, QSize
    from PyQt6.QtGui import QImage, QPixmap, QFont, QPainter, QPen, QColor, QPalette
    PYQT_AVAILABLE = True
except ImportError:
    PYQT_AVAILABLE = False
    print("WARNING: PyQt5 not available. Install with: pip3 install PyQt5")

import cv2
from view_mode import ViewMode
from palette_manager import PaletteType
from roi_manager import ROI, ROIType
from thermal_analyzer import ThermalStatistics, HotSpot, ColdSpot, ThermalAnomaly, TemperatureTrend
from firefly_control_panel import FireflyControlPanel
from radiometric_panel import RadiometricPanel
from parallax_panel import ParallaxPanel
from fusion_panel import FusionPanel

logger = logging.getLogger(__name__)


from dataclasses import dataclass

@dataclass
class MeasurementPoint:
    """Spot measurement point."""
    x: int
    y: int
    label: str
    color: tuple = (255, 255, 0)  # RGB
    temperature: Optional[float] = None
    unit: str = "°C"


# ============================================================================
# Qt Styling (QSS - CSS-like)
# ============================================================================

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

QListWidget {
    background-color: #fdf6e3;
    color: #657b83;
    border: 1px solid #93a1a1;
    border-radius: 3px;
}

QCheckBox {
    color: #657b83;
}

QComboBox {
    background-color: #eee8d5;
    color: #657b83;
    border: 1px solid #93a1a1;
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

QComboBox QAbstractItemView {
    background-color: #eee8d5;
    color: #657b83;
    selection-background-color: #268bd2;
    selection-color: #fdf6e3;
}

QComboBox:hover {
    border: 1px solid #268bd2;
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

QListWidget::item:selected {
    background-color: #268bd2;
    color: #fdf6e3;
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

QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 5px;
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
QComboBox::down-arrow { image: none; border: 2px solid #003C74; width: 0; height: 0; border-left: 4px solid transparent; border-right: 4px solid transparent; border-top: 6px solid #003C74; margin-right: 4px; }
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
QComboBox::down-arrow { image: none; border: 2px solid #606060; width: 0; height: 0; border-left: 4px solid transparent; border-right: 4px solid transparent; border-top: 6px solid #606060; margin-right: 4px; }
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
QComboBox::down-arrow { image: none; border: 2px solid #607450; width: 0; height: 0; border-left: 4px solid transparent; border-right: 4px solid transparent; border-top: 6px solid #607450; margin-right: 4px; }
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

THEMES = {
    "Dark Mode": DARK_THEME,
    "Light Mode": LIGHT_THEME,
    "Solarized": SOLARIZED_THEME,
    "Colorful": COLORFUL_THEME,
    "Win XP Luna": LUNA_THEME,
    "Silver": SILVER_THEME,
    "Olive": OLIVE_THEME
}

# ============================================================================
# Inspection Overlay Widget
# ============================================================================

class InspectionOverlayWidget(QWidget):
    """
    Overlay widget for drawing ROIs, hot spots, cold spots, and anomalies.
    Replaces AlertOverlayWidget from ADAS system.
    """

    # Signals for ROI drawing
    from PyQt6.QtCore import pyqtSignal
    roi_created = pyqtSignal(object)  # Emits newly created ROI
    roi_selected = pyqtSignal(str)    # Emits selected ROI ID
    spot_meter_clicked = pyqtSignal(int, int) # Emits (x, y) coordinates of spot meter click

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)  # Let VideoWidget handle clicks
        self.setStyleSheet("background: transparent;")

        self.rois: List[ROI] = []
        self.hot_spots: List[HotSpot] = []
        self.cold_spots: List[ColdSpot] = []
        self.anomalies: List[ThermalAnomaly] = []
        self.selected_roi_id: Optional[str] = None
        self.show_detection_info = False  # Toggle for showing detection info (default: hidden)

        # Multi-select support
        self.selected_roi_ids: set = set()  # Set of selected ROI IDs

        # Measurement points
        self.measurement_points: List = []  # List of MeasurementPoint objects
        self.spot_meter_mode = False        # Toggle for spot metering mode

        # ROI drawing state
        self.drawing_mode = False
        self.drawing_type = ROIType.RECTANGLE  # Default
        self.draw_start_pos = None
        self.draw_current_pos = None
        self.temp_polygon_points = []

        # Coordinate transformation for scaled video
        self.frame_size = (640, 512)  # Original frame size (width, height)
        self.scale = 1.0
        self.offset_x = 0
        self.offset_y = 0

        # Temperature unit for hot/cold spot display
        self.current_temp_unit = 'C'  # Default to Celsius (C/F/K/RAW)

        # Individual toggles for each detection type
        self.show_hot_spots = True  # Show hot spots by default
        self.show_cold_spots = True  # Show cold spots by default
        self.show_anomalies = True  # Show anomalies by default

    def set_spot_meter_mode(self, enabled: bool):
        """Enable or disable spot metering mode."""
        self.spot_meter_mode = enabled
        if enabled:
            self.setCursor(Qt.CursorShape.CrossCursor)
            # Disable drawing mode if enabling spot meter
            if self.drawing_mode:
                self.disable_drawing_mode()
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)
        self.update()

    def update_rois(self, rois: List[ROI]):
        """Update ROI list for visualization."""
        self.rois = rois
        self.update()

    def update_thermal_detections(self, hot_spots: List[HotSpot], cold_spots: List[ColdSpot], anomalies: List[ThermalAnomaly]):
        """Update thermal detection results."""
        self.hot_spots = hot_spots
        self.cold_spots = cold_spots
        self.anomalies = anomalies
        self.update()

    def update_measurement_points(self, points: List):
        """Update measurement points for visualization."""
        self.measurement_points = points
        self.update()

    def set_frame_transform(self, frame_width: int, frame_height: int, pixmap_width: int, pixmap_height: int, widget_width: int, widget_height: int):
        """
        Update coordinate transformation parameters.

        Args:
            frame_width: Original frame width
            frame_height: Original frame height
            pixmap_width: Scaled pixmap width
            pixmap_height: Scaled pixmap height
            widget_width: Widget width
            widget_height: Widget height
        """
        self.frame_size = (frame_width, frame_height)
        self.scale = pixmap_width / frame_width  # Assuming uniform scaling
        # Calculate offset for centered image
        self.offset_x = (widget_width - pixmap_width) // 2
        self.offset_y = (widget_height - pixmap_height) // 2

    def frame_to_widget(self, x: float, y: float) -> tuple:
        """Convert frame coordinates to widget coordinates."""
        widget_x = int(x * self.scale + self.offset_x)
        widget_y = int(y * self.scale + self.offset_y)
        return (widget_x, widget_y)

    def widget_to_frame(self, x: float, y: float) -> tuple:
        """Convert widget coordinates to frame coordinates."""
        frame_x = int((x - self.offset_x) / self.scale)
        frame_y = int((y - self.offset_y) / self.scale)
        return (frame_x, frame_y)

    def set_selected_roi(self, roi_id: Optional[str]):
        """Highlight a specific ROI."""
        self.selected_roi_id = roi_id
        self.update()

    def _format_temperature_with_unit(self, temp_celsius: float, original_unit: str, raw_value: Optional[float] = None) -> tuple:
        """
        Convert temperature to current unit and return with unit symbol.

        Args:
            temp_celsius: Temperature in Celsius (converted value)
            original_unit: Original unit string from detection ("°C" or " (raw)")
            raw_value: Raw pixel value (Y16: kelvin×100) if available

        Returns:
            Tuple of (display_value, unit_symbol)
        """
        # If it's 8-bit AGC data (non-radiometric), always show raw values
        # 8-bit AGC values cannot be converted to absolute temperatures
        if "(raw)" in original_unit:
            if self.current_temp_unit == 'RAW':
                return (temp_celsius, " (raw)")  # Already in raw format
            else:
                # In 8-bit mode, even if user selects C/F/K, we can only show raw
                # Display with note that conversion isn't available
                return (temp_celsius, " (AGC)")
        
        # For 16-bit radiometric data:
        # If user selected RAW unit, show raw pixel value
        if self.current_temp_unit == 'RAW':
            if raw_value is not None:
                return (raw_value, " (Y16)")
            else:
                return (temp_celsius, "°C")  # Fallback
        
        # If units match, return as is
        # Note: We handle the case where original is "°C" and current is 'C' (no degree symbol in key)
        if (self.current_temp_unit == 'C' and "C" in original_unit) or \
           (self.current_temp_unit == 'F' and "F" in original_unit) or \
           (self.current_temp_unit == 'K' and "K" in original_unit):
            return (temp_celsius, original_unit)

        # Otherwise convert celsius to selected unit
        # We assume input is Celsius if units don't match, unless it's explicitly F or K
        # But ThermalAnalyzer now returns values in the selected unit, so mismatch should be rare
        # (only during switching).
        
        # If input is actually F but we want C (rare case of mismatch)
        if "F" in original_unit:
            # Convert F to C first
            temp_celsius = (temp_celsius - 32) * 5/9
        elif "K" in original_unit:
            # Convert K to C first
            temp_celsius = temp_celsius - 273.15

        if self.current_temp_unit == 'C':
            return (temp_celsius, "°C")
        elif self.current_temp_unit == 'F':
            temp_f = temp_celsius * 9/5 + 32
            return (temp_f, "°F")
        elif self.current_temp_unit == 'K':
            temp_k = temp_celsius + 273.15
            return (temp_k, "K")
        
        return (temp_celsius, "°C")

    def set_temperature_unit(self, unit: str):
        """
        Set the temperature unit for display (C/F/K/RAW).
        
        Args:
            unit: Temperature unit code ('C', 'F', 'K', or 'RAW')
        """
        self.current_temp_unit = unit
        self.update()  # Trigger repaint to update hot/cold spot labels

    def paintEvent(self, event):
        """Draw ROIs and thermal detections."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Helper to draw text with background
        def draw_label(x, y, text, color):
            font_metrics = painter.fontMetrics()
            rect = font_metrics.boundingRect(text)
            # Add padding
            rect.adjust(-2, -2, 2, 2)
            rect.moveTo(x, y - rect.height() + 2)
            
            painter.setBrush(QColor(0, 0, 0, 160))  # Semi-transparent black
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRect(rect)
            
            painter.setPen(QPen(color, 1))
            painter.drawText(x, y, text)

        # Draw ROIs
        for roi in self.rois:
            # Determine color and thickness based on selection state
            is_selected = roi.roi_id in self.selected_roi_ids or roi.roi_id == self.selected_roi_id

            if is_selected:
                color = QColor(0, 255, 255)  # Cyan for selected
                thickness = 3
            elif roi.roi_type == ROIType.RECTANGLE:
                color = QColor(0, 255, 0)  # Green for rectangle
                thickness = 2
            elif roi.roi_type == ROIType.POLYGON:
                color = QColor(255, 255, 0)  # Yellow for polygon
                thickness = 2
            elif roi.roi_type == ROIType.ELLIPSE:
                color = QColor(255, 128, 0)  # Orange for ellipse
                thickness = 2
            elif roi.roi_type == ROIType.CIRCLE:
                color = QColor(128, 0, 255)  # Purple for circle
                thickness = 2
            else:
                color = QColor(255, 255, 255)  # White fallback
                thickness = 2

            pen = QPen(color, thickness)

            # Add dashed line style for multi-selected ROIs (not the primary selected one)
            if is_selected and roi.roi_id != self.selected_roi_id:
                pen.setStyle(Qt.PenStyle.DashLine)

            painter.setPen(pen)

            # Draw based on ROI type (with coordinate transformation)
            if roi.roi_type == ROIType.RECTANGLE:
                x, y, w, h = roi.get_bbox()
                # Transform frame coordinates to widget coordinates
                wx1, wy1 = self.frame_to_widget(x, y)
                wx2, wy2 = self.frame_to_widget(x + w, y + h)
                painter.drawRect(wx1, wy1, wx2 - wx1, wy2 - wy1)
            elif roi.roi_type == ROIType.POLYGON:
                from PyQt6.QtCore import QPoint
                # Transform all polygon points
                points = [QPoint(int(self.frame_to_widget(p[0], p[1])[0]),
                                int(self.frame_to_widget(p[0], p[1])[1])) for p in roi.points]
                from PyQt6.QtGui import QPolygon
                painter.drawPolygon(QPolygon(points))
            elif roi.roi_type == ROIType.ELLIPSE:
                x, y, w, h = roi.get_bbox()
                # Transform frame coordinates to widget coordinates
                wx1, wy1 = self.frame_to_widget(x, y)
                wx2, wy2 = self.frame_to_widget(x + w, y + h)
                painter.drawEllipse(wx1, wy1, wx2 - wx1, wy2 - wy1)
            elif roi.roi_type == ROIType.CIRCLE:
                x, y, w, h = roi.get_bbox()
                # Transform to widget coordinates
                wx1, wy1 = self.frame_to_widget(x, y)
                wx2, wy2 = self.frame_to_widget(x + w, y + h)
                ww = wx2 - wx1
                wh = wy2 - wy1
                radius = int(ww / 2)
                center_x = int(wx1 + radius)
                center_y = int(wy1 + radius)
                painter.drawEllipse(center_x - radius, center_y - radius, radius * 2, radius * 2)

            # Draw label
            if roi.label:
                x, y, _, _ = roi.get_bbox()
                wx, wy = self.frame_to_widget(x, y)
                draw_label(int(wx), int(wy) - 5, roi.label, color)

        # Draw hot spots (with coordinate transformation) - only if enabled
        if self.show_hot_spots:
            for hot_spot in self.hot_spots:
                painter.setPen(QPen(QColor(255, 0, 0), 2))  # Red
                x, y = hot_spot.centroid
                wx, wy = self.frame_to_widget(x, y)
                painter.drawEllipse(int(wx) - 5, int(wy) - 5, 10, 10)
                # Convert temperature to current unit
                temp_val, unit_symbol = self._format_temperature_with_unit(
                    hot_spot.max_temp, hot_spot.unit, hot_spot.raw_value)
                draw_label(int(wx) + 10, int(wy), f"{temp_val:.1f}{unit_symbol}", QColor(255, 100, 100))

        # Draw cold spots (with coordinate transformation) - only if enabled
        if self.show_cold_spots:
            for cold_spot in self.cold_spots:
                painter.setPen(QPen(QColor(0, 128, 255), 2))  # Light blue
                x, y = cold_spot.centroid
                wx, wy = self.frame_to_widget(x, y)
                painter.drawEllipse(int(wx) - 5, int(wy) - 5, 10, 10)
                # Convert temperature to current unit
                temp_val, unit_symbol = self._format_temperature_with_unit(
                    cold_spot.min_temp, cold_spot.unit, cold_spot.raw_value)
                draw_label(int(wx) + 10, int(wy), f"{temp_val:.1f}{unit_symbol}", QColor(100, 200, 255))

        # Draw anomalies (with coordinate transformation) - only if enabled
        if self.show_anomalies:
            for anomaly in self.anomalies:
                painter.setPen(QPen(QColor(255, 255, 0), 3))  # Yellow
                x, y = anomaly.location
                wx, wy = self.frame_to_widget(x, y)
                # Draw warning triangle
                painter.drawLine(int(wx), int(wy) - 10, int(wx) - 8, int(wy) + 6)
                painter.drawLine(int(wx) - 8, int(wy) + 6, int(wx) + 8, int(wy) + 6)
                painter.drawLine(int(wx) + 8, int(wy) + 6, int(wx), int(wy) - 10)

                # Use description if available, otherwise type
                label_text = f"⚠ {anomaly.description}" if anomaly.description else f"⚠ {anomaly.anomaly_type.value}"
                draw_label(int(wx) + 15, int(wy), label_text, QColor(255, 255, 0))

        # Draw measurement points
        for point in self.measurement_points:
            # Transform frame coordinates to widget coordinates
            wx, wy = self.frame_to_widget(point.x, point.y)

            # Draw point marker (circle with cross)
            r, g, b = point.color
            point_color = QColor(r, g, b)
            painter.setPen(QPen(point_color, 2))
            painter.setBrush(QColor(r, g, b, 100))  # Semi-transparent fill

            # Draw crosshair
            cross_size = 10
            painter.drawLine(int(wx) - cross_size, int(wy), int(wx) + cross_size, int(wy))
            painter.drawLine(int(wx), int(wy) - cross_size, int(wx), int(wy) + cross_size)
            # Draw center circle
            painter.drawEllipse(int(wx) - 3, int(wy) - 3, 6, 6)

            # Draw label with temperature and unit
            if point.temperature is not None:
                unit = getattr(point, 'unit', '')
                label_text = f"{point.label}: {point.temperature:.1f}{unit}"
            else:
                label_text = f"{point.label}: --"
            draw_label(int(wx) + 12, int(wy) + 5, label_text, point_color)

        # Draw temporary ROI being created
        if self.drawing_mode and self.draw_start_pos and self.draw_current_pos:
            painter.setPen(QPen(QColor(255, 255, 0), 2, Qt.PenStyle.DashLine))  # Yellow dashed line

            if self.drawing_type == ROIType.RECTANGLE:
                x = min(self.draw_start_pos.x(), self.draw_current_pos.x())
                y = min(self.draw_start_pos.y(), self.draw_current_pos.y())
                w = abs(self.draw_current_pos.x() - self.draw_start_pos.x())
                h = abs(self.draw_current_pos.y() - self.draw_start_pos.y())
                painter.drawRect(x, y, w, h)

            elif self.drawing_type == ROIType.ELLIPSE:
                x = min(self.draw_start_pos.x(), self.draw_current_pos.x())
                y = min(self.draw_start_pos.y(), self.draw_current_pos.y())
                w = abs(self.draw_current_pos.x() - self.draw_start_pos.x())
                h = abs(self.draw_current_pos.y() - self.draw_start_pos.y())
                painter.drawEllipse(x, y, w, h)

            elif self.drawing_type == ROIType.CIRCLE:
                center_x = self.draw_start_pos.x()
                center_y = self.draw_start_pos.y()
                radius = int(((self.draw_current_pos.x() - center_x) ** 2 +
                             (self.draw_current_pos.y() - center_y) ** 2) ** 0.5)
                painter.drawEllipse(center_x - radius, center_y - radius, radius * 2, radius * 2)

            elif self.drawing_type == ROIType.POLYGON and self.temp_polygon_points:
                from PyQt6.QtCore import QPoint
                from PyQt6.QtGui import QPolygon
                # Draw lines between polygon points
                points = self.temp_polygon_points + [self.draw_current_pos]
                for i in range(len(points) - 1):
                    painter.drawLine(points[i], points[i + 1])

    def enable_drawing_mode(self, roi_type: ROIType = ROIType.RECTANGLE):
        """Enable ROI drawing mode."""
        self.drawing_mode = True
        self.drawing_type = roi_type
        self.draw_start_pos = None
        self.draw_current_pos = None
        self.temp_polygon_points = []
        self.setCursor(Qt.CursorShape.CrossCursor)
        logger.info(f"Drawing mode enabled: {roi_type}")

    def disable_drawing_mode(self):
        """Disable ROI drawing mode."""
        self.drawing_mode = False
        self.draw_start_pos = None
        self.draw_current_pos = None
        self.temp_polygon_points = []
        self.setCursor(Qt.CursorShape.ArrowCursor)
        logger.info("Drawing mode disabled")

    def set_show_detection_info(self, show: bool):
        """Toggle visibility of detection info (hot spots, cold spots, anomalies)."""
        self.show_detection_info = show
        self.update()  # Trigger repaint

    def mousePressEvent(self, event):
        """Handle mouse press for ROI drawing and selection."""
        if self.spot_meter_mode:
            # Spot metering: click to add measurement point
            click_x, click_y = self.widget_to_frame(event.pos().x(), event.pos().y())
            self.spot_meter_clicked.emit(click_x, click_y)
            event.accept() # Stop propagation to VideoWidget
            return

        if not self.drawing_mode:
            # Check if clicking on existing ROI for selection
            # Transform click to frame coordinates
            click_x, click_y = self.widget_to_frame(event.pos().x(), event.pos().y())

            # Check modifiers for multi-select
            modifiers = event.modifiers()
            ctrl_pressed = modifiers & Qt.KeyboardModifier.ControlModifier
            shift_pressed = modifiers & Qt.KeyboardModifier.ShiftModifier

            clicked_roi = None
            for roi in self.rois:
                if roi.contains_point((click_x, click_y)):
                    clicked_roi = roi
                    break

            if clicked_roi:
                if ctrl_pressed:
                    # Ctrl+Click: Toggle selection
                    if clicked_roi.roi_id in self.selected_roi_ids:
                        self.selected_roi_ids.remove(clicked_roi.roi_id)
                        logger.info(f"ROI {clicked_roi.roi_id} deselected (multi-select)")
                    else:
                        self.selected_roi_ids.add(clicked_roi.roi_id)
                        logger.info(f"ROI {clicked_roi.roi_id} added to selection (multi-select)")

                    # Set primary selection to clicked ROI
                    self.set_selected_roi(clicked_roi.roi_id)
                    logger.debug(f"[OVERLAY] Emitting roi_selected for {clicked_roi.roi_id}")
                    self.roi_selected.emit(clicked_roi.roi_id)

                elif shift_pressed:
                    # Shift+Click: Select range (from last selected to current)
                    if self.selected_roi_id:
                        # Find indices of last selected and current
                        try:
                            start_idx = next(i for i, r in enumerate(self.rois) if r.roi_id == self.selected_roi_id)
                            end_idx = next(i for i, r in enumerate(self.rois) if r.roi_id == clicked_roi.roi_id)

                            # Select all ROIs in range
                            start, end = min(start_idx, end_idx), max(start_idx, end_idx)
                            for i in range(start, end + 1):
                                self.selected_roi_ids.add(self.rois[i].roi_id)

                            logger.info(f"Selected ROI range: {end - start + 1} ROIs")
                        except StopIteration:
                            pass

                    self.set_selected_roi(clicked_roi.roi_id)
                    self.roi_selected.emit(clicked_roi.roi_id)

                else:
                    # Normal click: Single selection (clear others)
                    self.selected_roi_ids.clear()
                    self.selected_roi_ids.add(clicked_roi.roi_id)
                    self.set_selected_roi(clicked_roi.roi_id)
                    logger.debug(f"[OVERLAY] Emitting roi_selected for {clicked_roi.roi_id}")
                    self.roi_selected.emit(clicked_roi.roi_id)

                self.update()  # Redraw to show selection changes
            else:
                # Clicked on empty space - clear selection
                if not ctrl_pressed and not shift_pressed:
                    self.selected_roi_ids.clear()
                    self.set_selected_roi(None)
                    self.update()

            return

        if self.drawing_type == ROIType.POLYGON:
            # For polygon, collect multiple points
            self.temp_polygon_points.append(event.pos())
            self.update()
        else:
            # For rectangle, ellipse, circle - start drawing
            self.draw_start_pos = event.pos()
            self.draw_current_pos = event.pos()
            self.update()

    def mouseMoveEvent(self, event):
        """Handle mouse move for ROI drawing."""
        if self.drawing_mode and self.draw_start_pos:
            self.draw_current_pos = event.pos()
            self.update()

    def mouseReleaseEvent(self, event):
        """Handle mouse release to finalize ROI."""
        if not self.drawing_mode or not self.draw_start_pos:
            return

        if self.drawing_type == ROIType.POLYGON:
            # Polygon requires double-click or Enter key to finish
            return

        try:
            # Create ROI from drawn shape
            from roi_manager import ROI, ROISource
            import uuid

            if self.drawing_type == ROIType.RECTANGLE:
                x = min(self.draw_start_pos.x(), event.pos().x())
                y = min(self.draw_start_pos.y(), event.pos().y())
                w = abs(event.pos().x() - self.draw_start_pos.x())
                h = abs(event.pos().y() - self.draw_start_pos.y())

                if w > 10 and h > 10:  # Minimum size
                    # Transform widget coordinates to frame coordinates
                    fx1, fy1 = self.widget_to_frame(x, y)
                    fx2, fy2 = self.widget_to_frame(x + w, y + h)
                    # Convert bounds to points (4 corners) in frame coordinates
                    points = [(fx1, fy1), (fx2, fy1), (fx2, fy2), (fx1, fy2)]
                    roi = ROI(
                        roi_id=str(uuid.uuid4()),
                        roi_type=ROIType.RECTANGLE,
                        roi_source=ROISource.MANUAL,
                        points=points,
                        label=f"ROI-{len(self.rois) + 1}"
                    )
                    self.roi_created.emit(roi)

            elif self.drawing_type == ROIType.ELLIPSE:
                x = min(self.draw_start_pos.x(), event.pos().x())
                y = min(self.draw_start_pos.y(), event.pos().y())
                w = abs(event.pos().x() - self.draw_start_pos.x())
                h = abs(event.pos().y() - self.draw_start_pos.y())

                if w > 10 and h > 10:
                    # Transform widget coordinates to frame coordinates
                    fx1, fy1 = self.widget_to_frame(x, y)
                    fx2, fy2 = self.widget_to_frame(x + w, y + h)
                    # Convert ellipse bounds to points (4 corners of bounding box) in frame coordinates
                    points = [(fx1, fy1), (fx2, fy1), (fx2, fy2), (fx1, fy2)]
                    roi = ROI(
                        roi_id=str(uuid.uuid4()),
                        roi_type=ROIType.ELLIPSE,
                        roi_source=ROISource.MANUAL,
                        points=points,
                        label=f"ROI-{len(self.rois) + 1}"
                    )
                    self.roi_created.emit(roi)

            elif self.drawing_type == ROIType.CIRCLE:
                center_x = self.draw_start_pos.x()
                center_y = self.draw_start_pos.y()
                radius = int(((event.pos().x() - center_x) ** 2 +
                             (event.pos().y() - center_y) ** 2) ** 0.5)

                if radius > 5:
                    # Transform center to frame coordinates
                    fcx, fcy = self.widget_to_frame(center_x, center_y)
                    
                    # Calculate a point on the circumference in frame coordinates
                    # We can't just transform the radius because scaling might be different (though here it's uniform)
                    # Let's transform the current mouse position
                    fpx, fpy = self.widget_to_frame(event.pos().x(), event.pos().y())
                    
                    points = [(fcx, fcy), (fpx, fpy)]
                    roi = ROI(
                        roi_id=str(uuid.uuid4()),
                        roi_type=ROIType.CIRCLE,
                        roi_source=ROISource.MANUAL,
                        points=points,
                        label=f"ROI-{len(self.rois) + 1}"
                    )
                    self.roi_created.emit(roi)

        except Exception as e:
            logger.error(f"Error creating ROI: {e}", exc_info=True)

        # Reset drawing state
        self.draw_start_pos = None
        self.draw_current_pos = None
        self.update()

    def mouseDoubleClickEvent(self, event):
        """Handle double-click to finish polygon drawing."""
        if self.drawing_mode and self.drawing_type == ROIType.POLYGON and len(self.temp_polygon_points) >= 3:
            from roi_manager import ROI, ROISource
            import uuid

            # Convert QPoint to tuples
            points = [(p.x(), p.y()) for p in self.temp_polygon_points]

            # Calculate bounding box
            xs = [p[0] for p in points]
            ys = [p[1] for p in points]
            x, y = min(xs), min(ys)
            w, h = max(xs) - x, max(ys) - y

            roi = ROI(
                roi_id=str(uuid.uuid4()),
                roi_type=ROIType.POLYGON,
                bounds=(x, y, w, h),
                polygon_points=points,
                label=f"ROI-{len(self.rois) + 1}",
                source=ROISource.MANUAL
            )
            self.roi_created.emit(roi)

            # Reset polygon drawing
            self.temp_polygon_points = []
            self.draw_start_pos = None
            self.draw_current_pos = None
            self.update()

    def mouseDoubleClickEvent(self, event):
        """Handle double click to finalize polygon."""
        if self.drawing_mode and self.drawing_type == ROIType.POLYGON:
            if len(self.temp_polygon_points) > 2:
                try:
                    from roi_manager import ROI, ROISource
                    import uuid
                    
                    # Transform all points to frame coordinates
                    points = []
                    for p in self.temp_polygon_points:
                        fx, fy = self.widget_to_frame(p.x(), p.y())
                        points.append((fx, fy))
                        
                    roi = ROI(
                        roi_id=str(uuid.uuid4()),
                        roi_type=ROIType.POLYGON,
                        roi_source=ROISource.MANUAL,
                        points=points,
                        label=f"ROI-{len(self.rois) + 1}"
                    )
                    self.roi_created.emit(roi)
                    
                    # Reset drawing state
                    self.temp_polygon_points = []
                    self.draw_start_pos = None
                    self.draw_current_pos = None
                    self.update()
                    
                except Exception as e:
                    logger.error(f"Error creating polygon ROI: {e}", exc_info=True)

    def contextMenuEvent(self, event):
        """Show context menu for ROI operations."""
        if not self.selected_roi_id:
            return

        # Find selected ROI
        selected_roi = None
        for roi in self.rois:
            if roi.roi_id == self.selected_roi_id:
                selected_roi = roi
                break

        if not selected_roi:
            return

        menu = QMenu(self)

        # Get total number of selected ROIs
        num_selected = len(self.selected_roi_ids) if self.selected_roi_ids else 1

        # Set Palette submenu
        if num_selected > 1:
            palette_menu = menu.addMenu(f"Set Palette ({num_selected} ROIs)")
        else:
            palette_menu = menu.addMenu("Set Palette")

        # Add all available palettes
        palettes = [
            ("white_hot", "White Hot"),
            ("black_hot", "Black Hot"),
            ("ironbow", "Ironbow"),
            ("rainbow", "Rainbow"),
            ("lava", "Lava"),
            ("arctic", "Arctic"),
            ("medical", "Medical"),
            ("plasma", "Plasma"),
            ("amber", "Amber"),
            ("gray", "Gray")
        ]

        for palette_id, palette_name in palettes:
            action = palette_menu.addAction(palette_name)
            action.triggered.connect(lambda checked, p=palette_id: self._set_roi_palette(p))

        # Clear palette option
        clear_action = palette_menu.addAction("Clear Custom Palette")
        clear_action.triggered.connect(self._clear_roi_palette)

        menu.addSeparator()

        # Delete ROI option
        if num_selected > 1:
            delete_action = menu.addAction(f"Delete {num_selected} ROIs")
        else:
            delete_action = menu.addAction("Delete ROI")
        delete_action.triggered.connect(self._delete_selected_roi)

        menu.exec(event.globalPos())

    def _set_roi_palette(self, palette_name: str):
        """Set palette for all selected ROIs."""
        parent_window = self.window()
        if not hasattr(parent_window, '_on_roi_palette_changed'):
            return

        # Get all ROI IDs to update (multi-select or just primary)
        roi_ids = list(self.selected_roi_ids) if self.selected_roi_ids else [self.selected_roi_id]

        for roi_id in roi_ids:
            if roi_id:
                parent_window._on_roi_palette_changed(roi_id, palette_name)

        logger.info(f"Setting palette '{palette_name}' for {len(roi_ids)} ROI(s)")

    def _clear_roi_palette(self):
        """Clear custom palette for all selected ROIs."""
        parent_window = self.window()
        if not hasattr(parent_window, '_on_roi_palette_cleared'):
            return

        # Get all ROI IDs to update (multi-select or just primary)
        roi_ids = list(self.selected_roi_ids) if self.selected_roi_ids else [self.selected_roi_id]

        for roi_id in roi_ids:
            if roi_id:
                parent_window._on_roi_palette_cleared(roi_id)

        logger.info(f"Clearing custom palette for {len(roi_ids)} ROI(s)")

    def _delete_selected_roi(self):
        """Delete all selected ROIs."""
        parent_window = self.window()
        if not hasattr(parent_window, '_on_roi_delete'):
            return

        # Get all ROI IDs to delete (multi-select or just primary)
        roi_ids = list(self.selected_roi_ids) if self.selected_roi_ids else [self.selected_roi_id]

        for roi_id in roi_ids:
            if roi_id:
                parent_window._on_roi_delete(roi_id)

        logger.info(f"Deleting {len(roi_ids)} ROI(s)")

        # Clear multi-select after deletion
        self.selected_roi_ids.clear()
        self.selected_roi_id = None
        self.update()

class VideoWidget(QLabel):
    """
    High-performance video display widget with embedded inspection overlay.
    Reuses frame buffers to reduce memory allocations on Jetson.
    """
    # Signal for cursor position (emits x, y in frame coordinates)
    cursor_moved = pyqtSignal(int, int)
    # Signal for spot meter creation (emits x, y in frame coordinates)
    spot_meter_clicked = pyqtSignal(int, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(640, 480)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setStyleSheet("background-color: #000000; border: 2px solid #404040;")

        # Enable mouse tracking for cursor temperature readout
        self.setMouseTracking(True)

        # Frame buffer reuse (performance optimization for Jetson)
        self._last_qimage = None
        self._last_qpixmap = None
        self._frame_width = 0
        self._frame_height = 0

        # Measurement point mode
        self.add_point_mode = False

        # Embedded inspection overlay
        self.overlay = InspectionOverlayWidget(self)
        # Relay spot meter clicks from overlay to main window
        self.overlay.spot_meter_clicked.connect(self.spot_meter_clicked.emit)

    def update_frame(self, frame: np.ndarray):
        """Update displayed frame with performance optimization."""
        if frame is None or frame.size == 0:
            return

        height, width = frame.shape[:2]

        # Store frame dimensions for cursor position mapping
        self._frame_width = width
        self._frame_height = height

        # Convert BGR to RGB
        if len(frame.shape) == 3 and frame.shape[2] == 3:
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        else:
            rgb_frame = frame

        # Fix for video corruption:
        # 1. Use QImage.copy() to ensure deep copy of data
        # 2. Ensure data survives until copy is made
        # 3. Use contiguous array
        qimage = QImage(rgb_frame.data, width, height, 3 * width, QImage.Format.Format_RGB888)
        self._last_qimage = qimage.copy()

        # Scale to widget size and display
        # PERFORMANCE: Use FastTransformation instead of SmoothTransformation
        # SmoothTransformation uses bicubic interpolation (~100ms per frame)
        # FastTransformation uses nearest neighbor (~1ms per frame)
        self._last_qpixmap = QPixmap.fromImage(self._last_qimage).scaled(
            self.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.FastTransformation
        )
        self.setPixmap(self._last_qpixmap)

        # Update overlay coordinate transformation
        self.overlay.set_frame_transform(
            width, height,  # Original frame size
            self._last_qpixmap.width(), self._last_qpixmap.height(),  # Scaled pixmap size
            self.width(), self.height()  # Widget size
        )

    def update_rois(self, rois: List[ROI]):
        """Update ROIs on overlay."""
        self.overlay.update_rois(rois)

    def update_thermal_detections(self, hot_spots: List[HotSpot], cold_spots: List[ColdSpot], anomalies: List[ThermalAnomaly]):
        """Update thermal detections on overlay."""
        self.overlay.update_thermal_detections(hot_spots, cold_spots, anomalies)

    def set_add_point_mode(self, enabled: bool):
        """Enable/disable measurement point adding mode."""
        self.add_point_mode = enabled
        if enabled:
            self.setCursor(Qt.CursorShape.CrossCursor)
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)
        
        # Sync with overlay which handles mouse events
        self.overlay.set_spot_meter_mode(enabled)

    def update_measurement_points(self, points):
        """Update measurement points on overlay."""
        self.overlay.update_measurement_points(points)

    def resizeEvent(self, event):
        """Ensure overlay matches video widget size and update coordinate transformation."""
        super().resizeEvent(event)
        self.overlay.setGeometry(self.rect())

        # Update coordinate transformation if we have frame dimensions
        if self._last_qpixmap and hasattr(self.overlay, 'frame_size') and self.overlay.frame_size != (640, 512):
            # Re-scale pixmap and update transformation
            if self._last_qimage:
                frame_width, frame_height = self.overlay.frame_size
                self._last_qpixmap = QPixmap.fromImage(self._last_qimage).scaled(
                    self.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
                )
                self.setPixmap(self._last_qpixmap)

                # Update overlay coordinate transformation
                self.overlay.set_frame_transform(
                    frame_width, frame_height,
                    self._last_qpixmap.width(), self._last_qpixmap.height(),
                    self.width(), self.height()
                )

    def mouseMoveEvent(self, event):
        """Handle mouse move to emit cursor position in frame coordinates."""
        super().mouseMoveEvent(event)

        # Only emit if we have valid frame dimensions
        if self._frame_width == 0 or self._frame_height == 0:
            return

        if not self._last_qpixmap:
            return

        # Get mouse position in widget coordinates
        mouse_x = event.pos().x()
        mouse_y = event.pos().y()

        # Calculate pixmap position within widget (centered with aspect ratio)
        pixmap_width = self._last_qpixmap.width()
        pixmap_height = self._last_qpixmap.height()

        widget_width = self.width()
        widget_height = self.height()

        # Calculate pixmap offset (it's centered in the widget)
        pixmap_x = (widget_width - pixmap_width) // 2
        pixmap_y = (widget_height - pixmap_height) // 2

        # Check if mouse is within pixmap bounds
        if mouse_x < pixmap_x or mouse_x >= pixmap_x + pixmap_width:
            return
        if mouse_y < pixmap_y or mouse_y >= pixmap_y + pixmap_height:
            return

        # Convert to pixmap coordinates
        pixmap_local_x = mouse_x - pixmap_x
        pixmap_local_y = mouse_y - pixmap_y

        # Map pixmap coordinates to frame coordinates
        frame_x = int((pixmap_local_x / pixmap_width) * self._frame_width)
        frame_y = int((pixmap_local_y / pixmap_height) * self._frame_height)

        # Clamp to frame bounds
        frame_x = max(0, min(frame_x, self._frame_width - 1))
        frame_y = max(0, min(frame_y, self._frame_height - 1))

        # Emit cursor position signal
        self.cursor_moved.emit(frame_x, frame_y)

        # Trigger overlay repaint with new coordinates
        self.overlay.update()

    def mousePressEvent(self, event):
        """Handle mouse click."""
        # Process click if in add point mode
        if self.add_point_mode:
            x = event.pos().x()
            y = event.pos().y()
            
            # Convert to frame coordinates
            frame_x, frame_y = self._widget_to_frame_coords(x, y)

            if frame_x is not None and frame_y is not None:
                logger.info(f"VideoWidget request spot at ({frame_x}, {frame_y})")
                self.spot_meter_clicked.emit(frame_x, frame_y)
        
        super().mousePressEvent(event)




    def mouseMoveEvent(self, event):
        """Track mouse for cursor temperature and coordinate mapping."""
        x = event.position().x()
        y = event.position().y()
        
        # Convert to frame coordinates
        frame_x, frame_y = self._widget_to_frame_coords(x, y)
        
        if frame_x is not None and frame_y is not None:
            self.cursor_moved.emit(frame_x, frame_y)
            
        super().mouseMoveEvent(event)

    def _widget_to_frame_coords(self, wx, wy):
        """Convert widget coordinates to frame coordinates."""
        if self._last_qpixmap is None or self._frame_width == 0 or self._frame_height == 0:
            return None, None
            
        # Get pixmap dimensions (scaled image size)
        pm_width = self._last_qpixmap.width()
        pm_height = self._last_qpixmap.height()
        
        # Calculate offsets (centering)
        offset_x = (self.width() - pm_width) / 2
        offset_y = (self.height() - pm_height) / 2
        
        # Check if click is inside the image area
        if (wx < offset_x or wx > offset_x + pm_width or
            wy < offset_y or wy > offset_y + pm_height):
            return None, None
            
        # Map to frame coordinates
        rel_x = wx - offset_x
        rel_y = wy - offset_y
        
        frame_x = int(rel_x * (self._frame_width / pm_width))
        frame_y = int(rel_y * (self._frame_height / pm_height))

        # Clamp to frame bounds
        frame_x = max(0, min(frame_x, self._frame_width - 1))
        frame_y = max(0, min(frame_y, self._frame_height - 1))

        return frame_x, frame_y


# ============================================================================
# Control Panel
# ============================================================================

class ControlPanel(QWidget):
    """
    Control panel with inspection-specific buttons.
    Streamlined to 7 core functions.
    """

    # Signals
    record_toggled = pyqtSignal(bool)
    snapshot_clicked = pyqtSignal()
    freeze_frame_toggled = pyqtSignal(bool)
    camera_clicked = pyqtSignal()
    auto_roi_clicked = pyqtSignal()
    draw_roi_clicked = pyqtSignal()
    clear_rois_clicked = pyqtSignal()
    view_mode_clicked = pyqtSignal()
    day_night_clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)

        # Main layout
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(10, 10, 10, 10)
        self.main_layout.setSpacing(12)

        # Controls Layout (Grid)
        self.controls_layout = QGridLayout()
        self.controls_layout.setSpacing(10)

        # Row 0: Capture & Camera
        self.record_btn = QPushButton("⏺ Record")
        self.record_btn.setCheckable(True)
        self.record_btn.setMinimumWidth(100)
        self.record_btn.setToolTip("Toggle video recording")
        
        self.snapshot_btn = QPushButton("📷 Snapshot")
        self.snapshot_btn.setMinimumWidth(100)
        self.snapshot_btn.setToolTip("Capture snapshot")
        
        self.freeze_btn = QPushButton("⏸ Freeze")
        self.freeze_btn.setCheckable(True)
        self.freeze_btn.setMinimumWidth(100)
        self.freeze_btn.setToolTip("Freeze/Unfreeze frame")
        
        self.camera_btn = QPushButton("🎥 Cameras")
        self.camera_btn.setMinimumWidth(100)
        self.camera_btn.setToolTip("Manage camera connections")

        self.controls_layout.addWidget(self.record_btn, 0, 0)
        self.controls_layout.addWidget(self.snapshot_btn, 0, 1)
        self.controls_layout.addWidget(self.freeze_btn, 0, 2)
        self.controls_layout.addWidget(self.camera_btn, 0, 3)

        # Row 1: ROI Controls
        self.auto_roi_btn = QPushButton("🔍 Auto ROI")
        self.auto_roi_btn.setMinimumWidth(100)
        self.auto_roi_btn.setToolTip("Automatically detect ROIs")
        
        self.draw_roi_btn = QPushButton("✏ Draw ROI")
        self.draw_roi_btn.setCheckable(True)
        self.draw_roi_btn.setMinimumWidth(100)
        self.draw_roi_btn.setToolTip("Manually draw ROI")
        
        self.clear_roi_btn = QPushButton("🗑 Clear ROIs")
        self.clear_roi_btn.setMinimumWidth(100)
        self.clear_roi_btn.setToolTip("Clear all ROIs")

        self.controls_layout.addWidget(self.auto_roi_btn, 1, 0)
        self.controls_layout.addWidget(self.draw_roi_btn, 1, 1)
        self.controls_layout.addWidget(self.clear_roi_btn, 1, 2)

        # Row 2: View Controls
        self.view_mode_btn = QPushButton("👁 View Mode")
        self.view_mode_btn.setMinimumWidth(100)
        self.view_mode_btn.setToolTip("Cycle view mode (Thermal/RGB/Fusion/Side-by-Side/PiP)")

        self.theme_btn = QPushButton("🌓 Theme")
        self.theme_btn.setMinimumWidth(100)
        self.theme_btn.setToolTip("Toggle dark/light theme")

        self.controls_layout.addWidget(self.view_mode_btn, 2, 0)
        self.controls_layout.addWidget(self.theme_btn, 2, 1)

        self.main_layout.addLayout(self.controls_layout)

        # Connect signals
        self._connect_signals()

    def _connect_signals(self):
        """Connect button signals."""
        self.record_btn.toggled.connect(self.record_toggled.emit)
        self.snapshot_btn.clicked.connect(lambda: self.snapshot_clicked.emit())
        self.freeze_btn.toggled.connect(self.freeze_frame_toggled.emit)
        self.camera_btn.clicked.connect(lambda: self.camera_clicked.emit())
        self.auto_roi_btn.clicked.connect(lambda: self.auto_roi_clicked.emit())
        self.draw_roi_btn.clicked.connect(lambda: self.draw_roi_clicked.emit())
        self.clear_roi_btn.clicked.connect(lambda: self.clear_rois_clicked.emit())
        self.view_mode_btn.clicked.connect(lambda: self.view_mode_clicked.emit())
        self.theme_btn.clicked.connect(lambda: self.day_night_clicked.emit())

    def update_record_button(self, recording: bool):
        """Update record button state."""
        if recording:
            self.record_btn.setText("⏹ Stop")
            self.record_btn.setStyleSheet("background-color: #ff4444; color: white;")
        else:
            self.record_btn.setText("⏺ Record")
            self.record_btn.setStyleSheet("")
        self.record_btn.setChecked(recording)

    def update_freeze_button(self, frozen: bool):
        """Update freeze button state."""
        if frozen:
            self.freeze_btn.setText("▶ Resume")
            self.freeze_btn.setStyleSheet("background-color: #4444ff; color: white;")
        else:
            self.freeze_btn.setText("⏸ Freeze")
            self.freeze_btn.setStyleSheet("")
        self.freeze_btn.setChecked(frozen)

    def update_theme_button(self, theme: str):
        """Update theme button display - shows current theme."""
        # Theme icons and display names
        theme_info = {
            "Dark Mode": ("🌙", "Dark"),
            "Light Mode": ("☀", "Light"),
            "Solarized": ("🌅", "Solarized"),
            "Colorful": ("🎨", "Colorful"),
            "Win XP Luna": ("🖼", "XP Luna"),
            "Silver": ("💿", "XP Silver"),
            "Olive": ("🌿", "XP Olive"),
            "auto": ("🔄", "Auto")
        }

        # Handle auto mode with actual theme in parentheses
        display_theme = theme
        if "auto (" in theme:
            # Extract actual theme from "auto (dark)" or "auto (light)"
            display_theme = "auto"
            icon, name = theme_info.get("auto", ("🔄", "Auto"))
            self.theme_btn.setText(f"{icon} {theme.replace('auto ', 'Auto ')}")
            self.theme_btn.setToolTip(f"Theme: {theme} - Click to cycle")
        else:
            icon, name = theme_info.get(theme, ("🌓", "Theme"))
            self.theme_btn.setText(f"{icon} {name}")
            self.theme_btn.setToolTip(f"Theme: {name} - Click to cycle")

    def update_view_button(self, view_mode):
        """Update view mode button display."""
        from view_mode import ViewMode
        mode_names = {
            ViewMode.THERMAL_ONLY: "Thermal",
            ViewMode.RGB_ONLY: "RGB",
            ViewMode.FUSION: "Fusion",
            ViewMode.SIDE_BY_SIDE: "Side-by-Side",
            ViewMode.PICTURE_IN_PICTURE: "PiP"
        }
        mode_name = mode_names.get(view_mode, "View")
        self.view_mode_btn.setText(f"👁 {mode_name}")

    def show_developer_controls(self, show: bool):
        """Legacy method compatibility."""
        pass



# ============================================================================
# Info Panel (Minimal Status Overlay)
# ============================================================================

class InfoPanel(QLabel):
    """
    Minimal inspection status overlay (280x70px, top-right corner).
    Shows FPS, thermal status, ROI count, and recording status.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("info_panel")
        self.setFixedSize(300, 70)  # Increased width for better text display
        self.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.setWordWrap(True)

    def update_info(self, fps: float, roi_count: int, thermal_connected: bool, rgb_connected: bool, recording: bool = False):
        """Update inspection status information."""
        # Performance quality indicator
        if fps >= 25:
            quality = "● "  # Green
        elif fps >= 15:
            quality = "● "  # Yellow
        else:
            quality = "● "  # Red

        # Connection status
        thermal_status = "✓" if thermal_connected else "✗"
        rgb_status = "✓" if rgb_connected else "✗"

        # Recording indicator
        rec_indicator = " [⏺ REC]" if recording else ""

        info_text = (
            f"{quality}FPS: {fps:.1f}{rec_indicator}\n"
            f"ROIs: {roi_count}\n"
            f"Thermal:{thermal_status} RGB:{rgb_status}"
        )

        self.setText(info_text)


# ============================================================================
# Thermal Analysis Panel (Right Sidebar)
# ============================================================================

class ThermalAnalysisPanel(QWidget):
    """
    Right sidebar panel for thermal analysis display.
    Shows temperature statistics, hot/cold spots, trends, and anomalies.
    """

    # Signals
    baseline_toggled = pyqtSignal(bool)
    palette_changed = pyqtSignal(str)  # Emits palette name
    roi_selected = pyqtSignal(str)  # Emits ROI ID
    roi_palette_changed = pyqtSignal(str, str)  # Emits (ROI ID, palette name)
    roi_palette_cleared = pyqtSignal(str)  # Emits ROI ID when palette is cleared
    overlay_info_toggled = pyqtSignal(bool)
    show_hot_spots_toggled = pyqtSignal(bool)
    show_cold_spots_toggled = pyqtSignal(bool)
    show_anomalies_toggled = pyqtSignal(bool)

    # Spot Meter Signals
    spot_meter_toggled = pyqtSignal(bool)
    clear_spots_clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        # Removed fixed width - use parent tab width dynamically
        self.current_rois = []  # Store ROI list
        self.selected_roi_index = -1  # Track selected ROI

        # Main layout with tabs
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Create tab widget
        self.analysis_tabs = QTabWidget()
        main_layout.addWidget(self.analysis_tabs)

        # Helper function to create section headers
        def create_section_header(text):
            header = QLabel(text)
            font = QFont()
            font.setPointSize(11)
            font.setBold(True)
            header.setFont(font)
            return header

        # Helper function to create separators
        def create_separator():
            line = QFrame()
            line.setFrameShape(QFrame.Shape.HLine)
            line.setFrameShadow(QFrame.Shadow.Sunken)
            palette = line.palette()
            palette.setColor(QPalette.ColorRole.WindowText, palette.color(QPalette.ColorRole.Mid))
            line.setPalette(palette)
            return line

        # ===================================================================
        # GENERAL TAB
        # ===================================================================
        general_tab = QWidget()
        general_scroll = QScrollArea()
        general_scroll.setWidgetResizable(True)
        general_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        general_scroll.setFrameShape(QFrame.Shape.NoFrame)

        general_content = QWidget()
        self.general_layout = QVBoxLayout(general_content)
        self.general_layout.setSpacing(8)  # Reduced from 12
        self.general_layout.setContentsMargins(6, 6, 6, 6)  # Reduced from 8

        # === Global Palette ===
        self.general_layout.addWidget(create_section_header("🎨 Global Palette"))
        
        self.palette_combo = QComboBox()
        self.palette_combo.setMinimumHeight(32)
        self.palette_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        # Populate palette combo
        self._populate_palette_combo(self.palette_combo)
        self.palette_combo.currentTextChanged.connect(self.palette_changed.emit)
        self.general_layout.addWidget(self.palette_combo)

        self.general_layout.addWidget(create_separator())

        # === Overlay Display ===
        self.general_layout.addWidget(create_section_header("👁 Overlay Display"))

        # Individual checkboxes for each detection type
        self.show_hot_spots_checkbox = QCheckBox("Show Hot Spots")
        self.show_hot_spots_checkbox.setChecked(True)  # Enabled by default
        self.show_hot_spots_checkbox.setToolTip("Show/hide hot spot markers on video")
        self.show_hot_spots_checkbox.setMinimumHeight(28)
        self.general_layout.addWidget(self.show_hot_spots_checkbox)

        self.show_cold_spots_checkbox = QCheckBox("Show Cold Spots")
        self.show_cold_spots_checkbox.setChecked(True)  # Enabled by default
        self.show_cold_spots_checkbox.setToolTip("Show/hide cold spot markers on video")
        self.show_cold_spots_checkbox.setMinimumHeight(28)
        self.general_layout.addWidget(self.show_cold_spots_checkbox)

        self.show_anomalies_checkbox = QCheckBox("Show Anomalies")
        self.show_anomalies_checkbox.setChecked(True)  # Enabled by default
        self.show_anomalies_checkbox.setToolTip("Show/hide thermal anomaly markers on video")
        self.show_anomalies_checkbox.setMinimumHeight(28)
        self.general_layout.addWidget(self.show_anomalies_checkbox)

        self.general_layout.addWidget(create_separator())

        # === Detection Results ===
        self.general_layout.addWidget(create_section_header("🎯 Detection Results"))

        self.detection_label = QLabel("No detections")
        self.detection_label.setWordWrap(True)
        font = QFont("Consolas", 10)
        self.detection_label.setFont(font)
        self.general_layout.addWidget(self.detection_label)

        self.general_layout.addWidget(create_separator())

        # === ROI Summary ===
        self.general_layout.addWidget(create_section_header("📍 ROI Summary"))

        self.roi_summary_label = QLabel("No active ROIs")
        self.roi_summary_label.setWordWrap(True)
        font = QFont("Consolas", 10)
        self.roi_summary_label.setFont(font)
        self.general_layout.addWidget(self.roi_summary_label)

        spot_layout = QHBoxLayout()
        self.spot_meter_btn = QPushButton("✚ Spot Meter")
        self.spot_meter_btn.setCheckable(True)
        self.spot_meter_btn.setToolTip("Click on video to add temperature measurement points")
        self.spot_meter_btn.setMinimumHeight(32)
        spot_layout.addWidget(self.spot_meter_btn)

        self.clear_spots_btn = QPushButton("Clear Points")
        self.clear_spots_btn.setToolTip("Remove all spot meters")
        self.clear_spots_btn.setMinimumHeight(32)
        spot_layout.addWidget(self.clear_spots_btn)
        self.general_layout.addLayout(spot_layout)

        self.general_layout.addWidget(create_separator())

        # === Hot Spots ===
        self.general_layout.addWidget(create_section_header("🔥 Hot Spots"))

        self.hotspot_list = QListWidget()
        self.hotspot_list.setMaximumHeight(90)  # Increased to show more items
        self.hotspot_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        font = QFont()
        font.setPointSize(10)
        self.hotspot_list.setFont(font)
        self.general_layout.addWidget(self.hotspot_list)

        self.general_layout.addWidget(create_separator())

        # === Cold Spots ===
        self.general_layout.addWidget(create_section_header("❄️ Cold Spots"))

        self.coldspot_list = QListWidget()
        self.coldspot_list.setMaximumHeight(90)  # Increased to show more items
        self.coldspot_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        font = QFont()
        font.setPointSize(10)
        self.coldspot_list.setFont(font)
        self.general_layout.addWidget(self.coldspot_list)

        self.general_layout.addWidget(create_separator())

        # === Thermal Anomalies ===
        self.general_layout.addWidget(create_section_header("⚠️ Thermal Anomalies"))

        self.anomaly_list = QListWidget()
        self.anomaly_list.setMaximumHeight(90)  # Increased to show more items
        self.anomaly_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        font = QFont()
        font.setPointSize(10)
        self.anomaly_list.setFont(font)
        self.general_layout.addWidget(self.anomaly_list)

        self.general_layout.addWidget(create_separator())

        # === Regions of Interest ===
        self.general_layout.addWidget(create_section_header("📍 Regions of Interest"))

        self.roi_list = QListWidget()
        self.roi_list.setMaximumHeight(100)  # Increased to show more items
        self.roi_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        font = QFont()
        font.setPointSize(10)
        self.roi_list.setFont(font)
        self.general_layout.addWidget(self.roi_list)

        # ROI palette selector (compact horizontal layout)
        roi_palette_layout = QHBoxLayout()
        roi_palette_layout.setSpacing(8)
        roi_label = QLabel("Palette:")
        font = QFont()
        font.setPointSize(10)
        roi_label.setFont(font)
        roi_palette_layout.addWidget(roi_label)

        self.roi_palette_combo = QComboBox()
        self.roi_palette_combo.setMinimumHeight(32)
        self.roi_palette_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        # Populate with categorized palettes (same as global)
        self._populate_palette_combo(self.roi_palette_combo)
        # Connect ROI palette signal
        self.roi_palette_combo.currentTextChanged.connect(self._on_roi_palette_combo_changed)
        roi_palette_layout.addWidget(self.roi_palette_combo, 1)
        self.general_layout.addLayout(roi_palette_layout)

        self.general_layout.addWidget(create_separator())

        self.general_layout.addWidget(create_separator())

        # === Temperature Statistics ===
        self.general_layout.addWidget(create_section_header("📊 Temperature Statistics"))

        self.stats_label = QLabel("No data")
        self.stats_label.setWordWrap(True)
        self.stats_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        font = QFont("Consolas", 10)
        self.stats_label.setFont(font)
        self.stats_label.setStyleSheet("padding: 8px;")
        self.general_layout.addWidget(self.stats_label)

        # Baseline control
        self.baseline_btn = QPushButton("🔒 Lock Baseline")
        self.baseline_btn.setCheckable(True)
        self.baseline_btn.setToolTip("Lock current mean temperature as baseline for relative measurements")
        self.baseline_btn.setMinimumHeight(32)
        self.general_layout.addWidget(self.baseline_btn)

        self.general_layout.addWidget(create_separator())

        # === Temperature Trend ===
        self.general_layout.addWidget(create_section_header("📈 Temperature Trend"))

        self.trend_label = QLabel("No trend data")
        self.trend_label.setWordWrap(True)
        self.trend_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        font = QFont("Consolas", 10)
        self.trend_label.setFont(font)
        self.trend_label.setStyleSheet("padding: 8px;")
        self.general_layout.addWidget(self.trend_label)

        self.general_layout.addStretch()

        general_scroll.setWidget(general_content)
        general_tab_layout = QVBoxLayout(general_tab)
        general_tab_layout.setContentsMargins(0, 0, 0, 0)
        general_tab_layout.addWidget(general_scroll)

        self.analysis_tabs.addTab(general_tab, "General")

        # Connect signals
        self.baseline_btn.toggled.connect(self.baseline_toggled.emit)
        self.spot_meter_btn.toggled.connect(self._on_spot_meter_toggled)
        self.clear_spots_btn.clicked.connect(self._on_clear_spots_clicked)
        self.roi_list.currentRowChanged.connect(self._on_roi_selected)
        self.roi_palette_combo.currentTextChanged.connect(self._on_roi_palette_combo_changed)
        
        # Connect individual detection type checkboxes via signals
        self.show_hot_spots_checkbox.toggled.connect(self.show_hot_spots_toggled.emit)
        self.show_cold_spots_checkbox.toggled.connect(self.show_cold_spots_toggled.emit)
        self.show_anomalies_checkbox.toggled.connect(self.show_anomalies_toggled.emit)

    def _populate_palette_combo(self, combo: QComboBox):
        """Populate a combo box with categorized palettes."""
        palette_categories = [
            ("GRAYSCALE", [
                PaletteType.WHITE_HOT, PaletteType.BLACK_HOT,
                PaletteType.GRAY, PaletteType.SEPIA
            ]),
            ("IRON/FIRE", [
                PaletteType.IRONBOW, PaletteType.LAVA, PaletteType.GRADEDFIRE,
                PaletteType.HOTTEST, PaletteType.AMBER, PaletteType.INFERNO
            ]),
            ("RAINBOW", [
                PaletteType.RAINBOW, PaletteType.RAINBOW_HC, PaletteType.RAINBOW_REVERSED,
                PaletteType.SPECTRAL, PaletteType.COOL_HOT
            ]),
            ("COLD/ARCTIC", [
                PaletteType.ARCTIC, PaletteType.ICE,
                PaletteType.WINTER, PaletteType.OCEAN
            ]),
            ("SCIENTIFIC", [
                PaletteType.VIRIDIS, PaletteType.PLASMA, PaletteType.MAGMA,
                PaletteType.CIVIDIS, PaletteType.TURBO
            ]),
            ("DIVERGING", [
                PaletteType.BLUE_RED, PaletteType.COOL_WARM, PaletteType.PURPLE_ORANGE,
                PaletteType.GREEN_RED, PaletteType.BLUE_YELLOW, PaletteType.PINK_GREEN
            ]),
            ("SEQUENTIAL", [
                PaletteType.GLOBOW, PaletteType.MEDICAL, PaletteType.THERMAL,
                PaletteType.HELIX, PaletteType.CUBEHELIX, PaletteType.TWILIGHT, PaletteType.DUSK
            ]),
            ("SPECIALIZED", [
                PaletteType.FUSION, PaletteType.PRISM, PaletteType.ALARM,
                PaletteType.LAPLACIAN, PaletteType.ISOTHERM, PaletteType.VELOCITY,
                PaletteType.TERRAIN, PaletteType.DEPTH
            ])
        ]

        # Populate combo box with categorized palettes
        for category_name, palettes in palette_categories:
            # Add category header (bold, disabled)
            combo.addItem(f"─── {category_name} ───")
            idx = combo.count() - 1
            item = combo.model().item(idx)
            font = QFont()
            font.setBold(True)
            item.setFont(font)
            item.setEnabled(False)

            # Add palette items (indented)
            for palette in palettes:
                combo.addItem(f"  {palette.value}")

    def _on_global_palette_changed(self, palette_name: str):
        """Handle global palette change."""
        # Remove category header prefix and indentation if present
        clean_name = palette_name.strip().lstrip("─ ")
        if clean_name and not clean_name.startswith("───"):
            self.palette_changed.emit(clean_name)

    def _on_roi_selected(self, row: int):
        """Handle ROI selection in list."""
        if 0 <= row < len(self.current_rois):
            roi = self.current_rois[row]
            logger.debug(f"Panel internal selection: Row {row} -> ROI {roi.roi_id}")
            self.roi_selected.emit(roi.roi_id)
            self.selected_roi_index = row
            
            # Update palette combo to match ROI's current palette
            if roi.custom_palette:
                # Find index for this palette
                text = f"  {roi.custom_palette}"
                index = self.roi_palette_combo.findText(text)
                if index >= 0:
                    logger.debug(f"Syncing palette combo to {text} for ROI {roi.roi_id}")
                    self.roi_palette_combo.blockSignals(True)
                    self.roi_palette_combo.setCurrentIndex(index)
                    self.roi_palette_combo.blockSignals(False)
            else:
                # Default/Global - Reset to first item or specific "Global" item if it exists
                # For now, we'll just leave it or set to index 0 if we had a "Global" option
                pass
        else:
            logger.debug(f"Panel internal selection: Invalid row {row}")
            self.selected_roi_index = -1

    def _on_roi_palette_combo_changed(self, palette_name: str):
        """Handle ROI palette change."""
        # Remove category header prefix and indentation if present
        clean_name = palette_name.strip().lstrip("─ ")
        if clean_name and not clean_name.startswith("───"):
            if 0 <= self.selected_roi_index < len(self.current_rois):
                roi = self.current_rois[self.selected_roi_index]
                logger.info(f"Setting ROI {roi.roi_id} palette to {clean_name}")
                self.roi_palette_changed.emit(roi.roi_id, clean_name)

    def select_roi(self, roi_id: str):
        """Select ROI in list by ID."""
        logger.debug(f"Panel selecting ROI: {roi_id}")
        found = False
        for i in range(self.roi_list.count()):
            item = self.roi_list.item(i)
            item_id = item.data(Qt.ItemDataRole.UserRole)
            if item_id == roi_id:
                logger.debug(f"ROI {roi_id} found at index {i}, selecting...")
                self.roi_list.setCurrentRow(i)
                found = True
                break
        
        if not found:
            logger.warning(f"ROI {roi_id} not found in ROI list (count: {self.roi_list.count()})")



    # Handlers for detection toggles are now signals emitted directly
    # _on_show_hot_spots_toggled, _on_show_cold_spots_toggled, _on_show_anomalies_toggled
    # are removed in favor of direct signal emission to parent InspectionAppWindow

    # Direct signal emission handlers
    def _on_spot_meter_toggled(self, checked: bool):
        """Handle spot meter toggle button."""
        logger.info(f"ThermalAnalysisPanel: Spot meter toggled to {checked}, emitting signal")
        self.spot_meter_toggled.emit(checked)

    def _on_clear_spots_clicked(self):
        """Handle clear spots button click."""
        logger.info("ThermalAnalysisPanel: Clear spots clicked, emitting signal")
        self.clear_spots_clicked.emit()

    def _on_clear_spots_clicked(self):
        """Handle clear spots button click."""
        logger.info("ThermalAnalysisPanel: Clear spots clicked, emitting signal")
        self.clear_spots_clicked.emit()

    def update_detection_results(self, motion_count: int, edge_count: int, anomaly_count: int):
        """Update detection results display."""
        text = (
            f"Motion Events: {motion_count}\n"
            f"Edge Clusters: {edge_count}\n"
            f"Anomalies:     {anomaly_count}"
        )
        self.detection_label.setText(text)

    def update_rois(self, rois: List[ROI]):
        """Update ROI summary and list."""
        
        # 1. Check if update is needed (compare IDs)
        current_ids = [r.roi_id for r in self.current_rois]
        new_ids = [r.roi_id for r in rois]
        
        self.current_rois = rois
        count = len(rois)
        
        # Only rebuild list if ROIs changed
        if current_ids != new_ids:
            # Preservation of selection
            selected_id = None
            if self.selected_roi_index >= 0 and self.selected_roi_index < len(current_ids):
                selected_id = current_ids[self.selected_roi_index]
            
            logger.debug(f"Rebuilding ROI list (was {len(current_ids)}, now {len(rois)})")
            
            # Update ROI List Widget
            self.roi_list.blockSignals(True) # Block signals to prevent spurious selection changes during rebuild
            self.roi_list.clear()
            for roi in rois:
                # Add palette indicator if custom palette is set
                label = f"{roi.label} ({roi.roi_type.value})"
                if roi.custom_palette:
                    label += " 🎨" # Visual indicator
                    
                item = QListWidgetItem(label)
                item.setData(Qt.ItemDataRole.UserRole, roi.roi_id)
                self.roi_list.addItem(item)
            
            # Restore selection if possible
            if selected_id:
                for i in range(self.roi_list.count()):
                    if self.roi_list.item(i).data(Qt.ItemDataRole.UserRole) == selected_id:
                        self.roi_list.setCurrentRow(i)
                        self.selected_roi_index = i # Update index
                        break
            else:
                self.selected_roi_index = -1
                
            self.roi_list.blockSignals(False) # Unblock AFTER restoration
        
        # Still update text summaries
        if count == 0:
            self.roi_summary_label.setText("No active ROIs")
            return
            
        # Calculate some basic stats if needed
        types = {}
        for roi in rois:
            t = roi.roi_type.value
            types[t] = types.get(t, 0) + 1
            
        summary = f"Total ROIs: {count}\n"
        for t, c in types.items():
            summary += f"• {t}: {c}\n"
            
        self.roi_summary_label.setText(summary)



    def update_statistics(self, stats: Optional[ThermalStatistics]):
        """Update temperature statistics display."""
        if stats is None:
            self.stats_label.setText("No data")
            self.stats_label.setToolTip("")
            return

        unit = stats.unit
        text = (
            f"Min:  {stats.min_temp:.1f}{unit}\n"
            f"Max:  {stats.max_temp:.1f}{unit}\n"
            f"Mean: {stats.mean_temp:.1f}{unit}\n"
            f"Std:  {stats.std_temp:.1f}{unit}"
        )
        
        # Create detailed tooltip
        tooltip = (
            f"Temperature Statistics:\n"
            f"Minimum: {stats.min_temp:.2f}{unit}\n"
            f"Maximum: {stats.max_temp:.2f}{unit}\n"
            f"Mean (Average): {stats.mean_temp:.2f}{unit}\n"
            f"Standard Deviation: {stats.std_temp:.2f}{unit}"
        )
        
        if stats.relative_mean is not None:
            text += f"\n\nΔ Mean: {stats.relative_mean:+.1f}{unit}"
            tooltip += f"\nRelative to Baseline: {stats.relative_mean:+.2f}{unit}"
            
        self.stats_label.setText(text)
        self.stats_label.setToolTip(tooltip)

    def update_hot_spots(self, hot_spots: List[HotSpot]):
        """Update hot spot list."""
        self.hotspot_list.clear()
        for i, hs in enumerate(hot_spots):
            text = f"#{i}: {hs.max_temp:.1f}{hs.unit} at ({hs.centroid[0]:.0f}, {hs.centroid[1]:.0f})"
            item = QListWidgetItem(text)
            # Add tooltip with full information
            tooltip = f"Hot Spot #{i}\nTemperature: {hs.max_temp:.2f}{hs.unit}\nLocation: ({hs.centroid[0]:.1f}, {hs.centroid[1]:.1f})\nArea: {hs.area} pixels"
            item.setToolTip(tooltip)
            self.hotspot_list.addItem(item)

    def update_cold_spots(self, cold_spots: List[ColdSpot]):
        """Update cold spot list."""
        self.coldspot_list.clear()
        for i, cs in enumerate(cold_spots):
            text = f"#{i}: {cs.min_temp:.1f}{cs.unit} at ({cs.centroid[0]:.0f}, {cs.centroid[1]:.0f})"
            item = QListWidgetItem(text)
            # Add tooltip with full information
            tooltip = f"Cold Spot #{i}\nTemperature: {cs.min_temp:.2f}{cs.unit}\nLocation: ({cs.centroid[0]:.1f}, {cs.centroid[1]:.1f})\nArea: {cs.area} pixels"
            item.setToolTip(tooltip)
            self.coldspot_list.addItem(item)

    def update_anomalies(self, anomalies: List[ThermalAnomaly]):
        """Update anomaly list."""
        self.anomaly_list.clear()
        for i, anom in enumerate(anomalies, 1):
            text = f"#{i}: {anom.anomaly_type} - {anom.description}"
            item = QListWidgetItem(text)
            # Add tooltip with full information
            tooltip = f"Anomaly #{i}\nType: {anom.anomaly_type}\nDescription: {anom.description}\nSeverity: {anom.severity}\nLocation: ({anom.location[0]:.1f}, {anom.location[1]:.1f})"
            item.setToolTip(tooltip)
            self.anomaly_list.addItem(item)

    def update_trend(self, trend: Optional[TemperatureTrend]):
        """Update temperature trend display."""
        if trend is None or trend.data_points == 0:
            self.trend_label.setText("No trend data")
            self.trend_label.setToolTip("")
            return

        text = (
            f"Direction: {trend.trend_direction}\n"
            f"Rate: {trend.rate_of_change:.3f}°C/s\n"
            f"Predicted: {trend.predicted_temp:.1f}°C\n"
            f"Data points: {trend.data_points}"
        )
        
        # Create detailed tooltip
        tooltip = (
            f"Temperature Trend Analysis:\n"
            f"Trend Direction: {trend.trend_direction}\n"
            f"Rate of Change: {trend.rate_of_change:.4f}°C/second\n"
            f"Predicted Temperature: {trend.predicted_temp:.2f}°C\n"
            f"Based on {trend.data_points} data points"
        )
        
        self.trend_label.setText(text)
        self.trend_label.setToolTip(tooltip)


# ============================================================================
# Manual Threshold Widget
# ============================================================================

class ManualThresholdWidget(QWidget):
    """Manual threshold-based anomaly detection widget."""

    # Signals
    threshold_mode_changed = pyqtSignal(str)  # "above", "below", "between", "outside"
    min_threshold_changed = pyqtSignal(float)
    max_threshold_changed = pyqtSignal(float)
    visualization_mode_changed = pyqtSignal(str)
    use_raw_values_changed = pyqtSignal(bool)
    enabled_changed = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)

        # State
        self.enabled = False

        self._init_ui()
        self._connect_signals()

    def _init_ui(self):
        """Initialize widget UI components."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(10)

        # Enable/Disable toggle
        enable_group = QGroupBox("MANUAL THRESHOLD MODE")
        enable_layout = QVBoxLayout(enable_group)

        self.enable_toggle = QPushButton("Manual Mode: OFF")
        self.enable_toggle.setCheckable(True)
        self.enable_toggle.setMinimumHeight(35)
        self.enable_toggle.setToolTip("Enable manual threshold-based anomaly detection")
        enable_layout.addWidget(self.enable_toggle)

        main_layout.addWidget(enable_group)

        # Threshold configuration (initially hidden)
        self.config_widget = QWidget()
        config_layout = QVBoxLayout(self.config_widget)
        config_layout.setContentsMargins(0, 0, 0, 0)
        config_layout.setSpacing(10)

        # Value type selection
        value_type_group = QGroupBox("VALUE TYPE")
        value_type_layout = QHBoxLayout(value_type_group)

        self.percent_radio = QPushButton("Percentage")
        self.percent_radio.setCheckable(True)
        self.percent_radio.setChecked(True)
        self.percent_radio.setToolTip("Use percentage values (0-100%)")

        self.advanced_radio = QPushButton("Advanced (Raw)")
        self.advanced_radio.setCheckable(True)
        self.advanced_radio.setToolTip("Use raw 14-bit thermal values (0-16383) - Advanced users only")

        value_type_layout.addWidget(self.percent_radio)
        value_type_layout.addWidget(self.advanced_radio)
        config_layout.addWidget(value_type_group)

        # Threshold mode selection
        mode_group = QGroupBox("THRESHOLD MODE")
        mode_layout = QVBoxLayout(mode_group)

        mode_label = QLabel("Detection Mode:")
        mode_layout.addWidget(mode_label)

        self.threshold_mode_combo = QComboBox()
        self.threshold_mode_combo.addItems([
            "Above Threshold",
            "Below Threshold",
            "Between Thresholds",
            "Outside Thresholds"
        ])
        self.threshold_mode_combo.setToolTip("Select how to detect anomalies")
        mode_layout.addWidget(self.threshold_mode_combo)

        config_layout.addWidget(mode_group)

        # Threshold values
        threshold_group = QGroupBox("THRESHOLD VALUES")
        threshold_layout = QVBoxLayout(threshold_group)

        # Min threshold
        min_layout = QHBoxLayout()
        min_layout.addWidget(QLabel("Min Threshold:"))
        self.min_threshold_spin = QSpinBox()
        self.min_threshold_spin.setRange(0, 100)
        self.min_threshold_spin.setValue(50)
        self.min_threshold_spin.setSuffix("%")
        self.min_threshold_spin.setToolTip("Minimum threshold percentage")
        min_layout.addWidget(self.min_threshold_spin)
        threshold_layout.addLayout(min_layout)

        # Max threshold
        max_layout = QHBoxLayout()
        max_layout.addWidget(QLabel("Max Threshold:"))
        self.max_threshold_spin = QSpinBox()
        self.max_threshold_spin.setRange(0, 100)
        self.max_threshold_spin.setValue(75)
        self.max_threshold_spin.setSuffix("%")
        self.max_threshold_spin.setToolTip("Maximum threshold percentage (for BETWEEN/OUTSIDE modes)")
        max_layout.addWidget(self.max_threshold_spin)
        threshold_layout.addLayout(max_layout)

        self.threshold_hint = QLabel("Using percentage (0-100%)")
        self.threshold_hint.setStyleSheet("font-size: 9px; color: #888;")
        threshold_layout.addWidget(self.threshold_hint)

        config_layout.addWidget(threshold_group)

        # Visualization mode
        viz_group = QGroupBox("VISUALIZATION")
        viz_layout = QVBoxLayout(viz_group)

        viz_label = QLabel("Display Mode:")
        viz_layout.addWidget(viz_label)

        self.viz_mode_combo = QComboBox()
        self.viz_mode_combo.addItems([
            "Grayscale Non-Anomalies",
            "Highlight Anomalies",
            "Binary Mask",
            "Gradient Overlay"
        ])
        self.viz_mode_combo.setToolTip("Choose how to visualize detected anomalies")
        viz_layout.addWidget(self.viz_mode_combo)

        config_layout.addWidget(viz_group)

        # Statistics display
        stats_group = QGroupBox("DETECTION STATISTICS")
        stats_layout = QVBoxLayout(stats_group)

        self.anomaly_percentage_label = QLabel("Anomalies: 0.0%")
        self.anomaly_percentage_label.setStyleSheet("font-size: 12px; font-weight: bold;")
        stats_layout.addWidget(self.anomaly_percentage_label)

        self.anomaly_count_label = QLabel("0 / 0 pixels")
        self.anomaly_count_label.setStyleSheet("font-size: 10px; color: #888;")
        stats_layout.addWidget(self.anomaly_count_label)

        config_layout.addWidget(stats_group)

        main_layout.addWidget(self.config_widget)
        self.config_widget.setVisible(False)

        main_layout.addStretch()

    def _connect_signals(self):
        """Connect internal signals."""
        self.enable_toggle.toggled.connect(self._on_enable_toggled)
        self.percent_radio.clicked.connect(lambda: self._on_value_type_changed(False))
        self.advanced_radio.clicked.connect(lambda: self._on_value_type_changed(True))
        self.threshold_mode_combo.currentTextChanged.connect(self._on_threshold_mode_changed)
        self.min_threshold_spin.valueChanged.connect(self.min_threshold_changed.emit)
        self.max_threshold_spin.valueChanged.connect(self.max_threshold_changed.emit)
        self.viz_mode_combo.currentTextChanged.connect(self._on_viz_mode_changed)

    def _on_enable_toggled(self, checked: bool):
        """Handle enable/disable toggle."""
        self.enabled = checked
        self.enable_toggle.setText(f"Manual Mode: {'ON' if checked else 'OFF'}")
        self.config_widget.setVisible(checked)
        self.enabled_changed.emit(checked)

    def _on_value_type_changed(self, use_raw: bool):
        """Handle value type radio button change."""
        self.percent_radio.setChecked(not use_raw)
        self.advanced_radio.setChecked(use_raw)

        if use_raw:
            # Advanced mode: Raw values
            self.min_threshold_spin.setRange(0, 16383)
            self.max_threshold_spin.setRange(0, 16383)
            self.min_threshold_spin.setSuffix("")
            self.max_threshold_spin.setSuffix("")
            self.min_threshold_spin.setValue(8000)
            self.max_threshold_spin.setValue(12000)
            self.threshold_hint.setText("Using raw values (0-16383) - Advanced mode")
        else:
            # Default mode: Percentage
            self.min_threshold_spin.setRange(0, 100)
            self.max_threshold_spin.setRange(0, 100)
            self.min_threshold_spin.setSuffix("%")
            self.max_threshold_spin.setSuffix("%")
            self.min_threshold_spin.setValue(50)
            self.max_threshold_spin.setValue(75)
            self.threshold_hint.setText("Using percentage (0-100%)")

        self.use_raw_values_changed.emit(use_raw)

    def _on_threshold_mode_changed(self, text: str):
        """Handle threshold mode combo change."""
        mode_map = {
            "Above Threshold": "above",
            "Below Threshold": "below",
            "Between Thresholds": "between",
            "Outside Thresholds": "outside"
        }
        mode = mode_map.get(text, "above")

        # Enable/disable max threshold based on mode
        needs_max = mode in ["between", "outside"]
        self.max_threshold_spin.setEnabled(needs_max)

        self.threshold_mode_changed.emit(mode)

    def _on_viz_mode_changed(self, text: str):
        """Handle visualization mode combo change."""
        viz_map = {
            "Grayscale Non-Anomalies": "grayscale_non_anomaly",
            "Highlight Anomalies": "color_non_anomaly",
            "Binary Mask": "binary_mask",
            "Gradient Overlay": "gradient_overlay"
        }
        mode = viz_map.get(text, "grayscale_non_anomaly")
        self.visualization_mode_changed.emit(mode)

    def update_statistics(self, anomaly_percentage: float, anomaly_count: int, total_pixels: int):
        """Update detection statistics display."""
        self.anomaly_percentage_label.setText(f"Anomalies: {anomaly_percentage:.2f}%")
        self.anomaly_count_label.setText(f"{anomaly_count:,} / {total_pixels:,} pixels")


# ============================================================================
# Anomaly Priority Control Widget
# ============================================================================

class AnomalyWidget(QWidget):
    """Anomaly priority control panel widget."""

    # Signals
    anomaly_priority_toggled = pyqtSignal(bool)
    anomaly_types_changed = pyqtSignal(dict)
    fade_strength_changed = pyqtSignal(float)
    fade_distance_changed = pyqtSignal(int)
    motion_threshold_changed = pyqtSignal(int)
    edge_thresholds_changed = pyqtSignal(int, int)
    hot_spot_percentile_changed = pyqtSignal(int)
    cold_spot_percentile_changed = pyqtSignal(int)
    min_anomaly_size_changed = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        # Removed fixed width - use parent tab width dynamically

        # State
        self.enabled_types = {
            "motion": True,
            "edges": True,
            "hot_spots": True,
            "cold_spots": True,
            "thermal_anomalies": True,
            "enhanced_fusion": False  # Off by default
        }

        self.anomaly_counts = {
            "motion": 0,
            "edges": 0,
            "hot_spots": 0,
            "cold_spots": 0,
            "thermal_anomalies": 0,
            "enhanced_fusion": 0
        }

        self._init_ui()
        self._connect_signals()

    def _init_ui(self):
        """Initialize widget UI components."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(15)

        # Scroll area for content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget()
        self.content_layout = QVBoxLayout(content)
        self.content_layout.setSpacing(15)
        self.content_layout.setContentsMargins(5, 5, 5, 5)

        # 1. Main toggle
        self._create_main_toggle()

        # 2. Anomaly types multi-select
        self._create_type_selector()

        # 3. Gradient controls
        self._create_gradient_controls()

        # 4. Detection settings (collapsible)
        self._create_detection_settings()

        # 5. Performance display
        self._create_performance_display()

        self.content_layout.addStretch()

        scroll.setWidget(content)
        main_layout.addWidget(scroll)

    def _create_main_toggle(self):
        """Create main anomaly priority ON/OFF toggle."""
        toggle_group = QGroupBox("ANOMALY PRIORITY CONTROL")
        toggle_layout = QVBoxLayout(toggle_group)

        self.main_toggle = QPushButton("Anomaly Priority: OFF")
        self.main_toggle.setCheckable(True)
        self.main_toggle.setMinimumHeight(40)
        self.main_toggle.setToolTip("Enable/disable anomaly priority gradient fade visualization")

        toggle_layout.addWidget(self.main_toggle)
        self.content_layout.addWidget(toggle_group)

    def _create_type_selector(self):
        """Create anomaly type multi-select checkboxes."""
        type_group = QGroupBox("ANOMALY TYPES")
        type_layout = QVBoxLayout(type_group)

        info_label = QLabel("Select which detections to highlight:")
        info_label.setWordWrap(True)
        type_layout.addWidget(info_label)

        # Create checkboxes with live count labels
        self.type_checkboxes = {}
        self.type_count_labels = {}

        anomaly_type_configs = [
            ("motion", "Motion Detections", "Temporal changes between frames"),
            ("edges", "Edge Clusters", "Thermal boundary edges"),
            ("hot_spots", "Hot Spots", "95th percentile temperature"),
            ("cold_spots", "Cold Spots", "5th percentile temperature"),
            ("thermal_anomalies", "Thermal Anomalies", "Statistical outliers"),
            ("enhanced_fusion", "Enhanced Thermal+Edge Fusion", "Intelligent thermal and edge combination")
        ]

        for key, label, tooltip in anomaly_type_configs:
            row_layout = QHBoxLayout()

            checkbox = QCheckBox(label)
            checkbox.setChecked(True)
            checkbox.setToolTip(tooltip)
            self.type_checkboxes[key] = checkbox

            count_label = QLabel("(0 found)")
            count_label.setStyleSheet("font-size: 10px;")
            self.type_count_labels[key] = count_label

            row_layout.addWidget(checkbox)
            row_layout.addWidget(count_label)
            row_layout.addStretch()

            type_layout.addLayout(row_layout)

        # Total count
        self.total_count_label = QLabel("Total: 0 anomalies")
        font = QFont()
        font.setBold(True)
        self.total_count_label.setFont(font)
        type_layout.addWidget(self.total_count_label)

        self.content_layout.addWidget(type_group)

    def _create_gradient_controls(self):
        """Create gradient fade control sliders."""
        gradient_group = QGroupBox("GRADIENT FADE")
        gradient_layout = QVBoxLayout(gradient_group)

        # Fade Strength slider
        strength_label = QLabel("Fade Strength:")
        gradient_layout.addWidget(strength_label)

        strength_row = QHBoxLayout()
        self.fade_strength_slider = QSlider(Qt.Orientation.Horizontal)
        self.fade_strength_slider.setMinimum(5)  # 0.5
        self.fade_strength_slider.setMaximum(20)  # 2.0
        self.fade_strength_slider.setValue(10)  # 1.0
        self.fade_strength_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.fade_strength_slider.setTickInterval(5)
        self.fade_strength_slider.setToolTip("Controls gradient steepness (0.5 soft - 2.0 sharp)")

        self.fade_strength_value = QLabel("1.0")
        self.fade_strength_value.setMinimumWidth(35)

        strength_row.addWidget(self.fade_strength_slider)
        strength_row.addWidget(self.fade_strength_value)
        gradient_layout.addLayout(strength_row)

        strength_hint = QLabel("(0.5 soft ← → 2.0 sharp)")
        strength_hint.setStyleSheet("font-size: 9px;")
        gradient_layout.addWidget(strength_hint)

        # Fade Distance slider
        distance_label = QLabel("Fade Distance:")
        gradient_layout.addWidget(distance_label)

        distance_row = QHBoxLayout()
        self.fade_distance_slider = QSlider(Qt.Orientation.Horizontal)
        self.fade_distance_slider.setMinimum(50)
        self.fade_distance_slider.setMaximum(200)
        self.fade_distance_slider.setValue(100)
        self.fade_distance_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.fade_distance_slider.setTickInterval(50)
        self.fade_distance_slider.setToolTip("Maximum distance for gradient fade effect (pixels)")

        self.fade_distance_value = QLabel("100px")
        self.fade_distance_value.setMinimumWidth(50)

        distance_row.addWidget(self.fade_distance_slider)
        distance_row.addWidget(self.fade_distance_value)
        gradient_layout.addLayout(distance_row)

        distance_hint = QLabel("(50px ← → 200px)")
        distance_hint.setStyleSheet("font-size: 9px;")
        gradient_layout.addWidget(distance_hint)

        self.content_layout.addWidget(gradient_group)

    def _create_detection_settings(self):
        """Create collapsible detection settings section."""
        self.detection_group = QGroupBox("DETECTION SETTINGS")
        detection_layout = QVBoxLayout(self.detection_group)

        # Expand/Collapse button
        self.detection_expand_btn = QPushButton("Expand Settings")
        self.detection_expand_btn.setCheckable(True)
        self.detection_expand_btn.setMaximumHeight(28)
        detection_layout.addWidget(self.detection_expand_btn)

        # Collapsible content
        self.detection_content = QWidget()
        self.detection_content.setVisible(False)
        settings_layout = QVBoxLayout(self.detection_content)
        settings_layout.setContentsMargins(0, 0, 0, 0)

        # Motion Threshold
        motion_layout = QHBoxLayout()
        motion_layout.addWidget(QLabel("Motion Threshold:"))
        self.motion_threshold_spin = QSpinBox()
        self.motion_threshold_spin.setRange(5, 50)
        self.motion_threshold_spin.setValue(20)
        self.motion_threshold_spin.setToolTip("Sensitivity for motion detection")
        motion_layout.addWidget(self.motion_threshold_spin)
        settings_layout.addLayout(motion_layout)

        # Edge Thresholds
        edge_low_layout = QHBoxLayout()
        edge_low_layout.addWidget(QLabel("Edge Low:"))
        self.edge_low_spin = QSpinBox()
        self.edge_low_spin.setRange(10, 100)
        self.edge_low_spin.setValue(50)
        self.edge_low_spin.setToolTip("Low threshold for edge detection")
        edge_low_layout.addWidget(self.edge_low_spin)
        settings_layout.addLayout(edge_low_layout)

        edge_high_layout = QHBoxLayout()
        edge_high_layout.addWidget(QLabel("Edge High:"))
        self.edge_high_spin = QSpinBox()
        self.edge_high_spin.setRange(50, 200)
        self.edge_high_spin.setValue(150)
        self.edge_high_spin.setToolTip("High threshold for edge detection")
        edge_high_layout.addWidget(self.edge_high_spin)
        settings_layout.addLayout(edge_high_layout)

        # Hot Spot Percentile
        hot_layout = QHBoxLayout()
        hot_layout.addWidget(QLabel("Hot Spot %ile:"))
        self.hot_spot_spin = QSpinBox()
        self.hot_spot_spin.setRange(85, 99)
        self.hot_spot_spin.setValue(95)
        self.hot_spot_spin.setToolTip("Percentile threshold for hot spot detection")
        hot_layout.addWidget(self.hot_spot_spin)
        settings_layout.addLayout(hot_layout)

        # Cold Spot Percentile
        cold_layout = QHBoxLayout()
        cold_layout.addWidget(QLabel("Cold Spot %ile:"))
        self.cold_spot_spin = QSpinBox()
        self.cold_spot_spin.setRange(1, 15)
        self.cold_spot_spin.setValue(5)
        self.cold_spot_spin.setToolTip("Percentile threshold for cold spot detection")
        cold_layout.addWidget(self.cold_spot_spin)
        settings_layout.addLayout(cold_layout)

        # Min Anomaly Size
        size_layout = QHBoxLayout()
        size_layout.addWidget(QLabel("Min Size (px²):"))
        self.min_size_spin = QSpinBox()
        self.min_size_spin.setRange(100, 2000)
        self.min_size_spin.setValue(400)
        self.min_size_spin.setSingleStep(100)
        self.min_size_spin.setToolTip("Minimum anomaly area size filter")
        size_layout.addWidget(self.min_size_spin)
        settings_layout.addLayout(size_layout)

        detection_layout.addWidget(self.detection_content)
        self.content_layout.addWidget(self.detection_group)

    def _create_performance_display(self):
        """Create performance metrics display."""
        perf_group = QGroupBox("PERFORMANCE")
        perf_layout = QVBoxLayout(perf_group)

        self.fps_label = QLabel("FPS: --")
        self.processing_time_label = QLabel("Processing: --")
        self.overhead_label = QLabel("Overhead: --")

        self.overhead_bar = QProgressBar()
        self.overhead_bar.setRange(0, 100)
        self.overhead_bar.setValue(0)
        self.overhead_bar.setTextVisible(True)
        self.overhead_bar.setFormat("%p%")
        self.overhead_bar.setMaximumHeight(20)

        perf_layout.addWidget(self.fps_label)
        perf_layout.addWidget(self.processing_time_label)
        perf_layout.addWidget(self.overhead_label)
        perf_layout.addWidget(self.overhead_bar)

        self.content_layout.addWidget(perf_group)

    def _connect_signals(self):
        """Connect internal widget signals."""
        # Main toggle
        self.main_toggle.toggled.connect(self._on_main_toggle_changed)

        # Anomaly type checkboxes
        for key, checkbox in self.type_checkboxes.items():
            checkbox.stateChanged.connect(self._on_type_checkbox_changed)

        # Gradient sliders
        self.fade_strength_slider.valueChanged.connect(self._on_fade_strength_changed)
        self.fade_distance_slider.valueChanged.connect(self._on_fade_distance_changed)

        # Detection settings expand/collapse
        self.detection_expand_btn.toggled.connect(self._on_detection_expand_toggled)

        # Detection setting spinboxes
        self.motion_threshold_spin.valueChanged.connect(self.motion_threshold_changed.emit)
        self.edge_low_spin.valueChanged.connect(self._on_edge_thresholds_changed)
        self.edge_high_spin.valueChanged.connect(self._on_edge_thresholds_changed)
        self.hot_spot_spin.valueChanged.connect(self.hot_spot_percentile_changed.emit)
        self.cold_spot_spin.valueChanged.connect(self.cold_spot_percentile_changed.emit)
        self.min_size_spin.valueChanged.connect(self.min_anomaly_size_changed.emit)

    def _on_main_toggle_changed(self, checked: bool):
        """Handle main toggle state change."""
        self.main_toggle.setText(f"Anomaly Priority: {'ON' if checked else 'OFF'}")
        self.anomaly_priority_toggled.emit(checked)

    def _on_type_checkbox_changed(self):
        """Handle anomaly type checkbox changes."""
        for key, checkbox in self.type_checkboxes.items():
            self.enabled_types[key] = checkbox.isChecked()

        self.anomaly_types_changed.emit(self.enabled_types)
        self._update_total_count()

    def _on_fade_strength_changed(self, value: int):
        """Handle fade strength slider change."""
        strength = value / 10.0  # Convert 5-20 to 0.5-2.0
        self.fade_strength_value.setText(f"{strength:.1f}")
        self.fade_strength_changed.emit(strength)

    def _on_fade_distance_changed(self, value: int):
        """Handle fade distance slider change."""
        self.fade_distance_value.setText(f"{value}px")
        self.fade_distance_changed.emit(value)

    def _on_detection_expand_toggled(self, expanded: bool):
        """Handle detection settings expand/collapse."""
        self.detection_content.setVisible(expanded)
        self.detection_expand_btn.setText("Collapse Settings" if expanded else "Expand Settings")

    def _on_edge_thresholds_changed(self):
        """Handle edge threshold changes."""
        low = self.edge_low_spin.value()
        high = self.edge_high_spin.value()
        self.edge_thresholds_changed.emit(low, high)

    def update_counts(self, counts: dict):
        """Update live anomaly counts.

        Args:
            counts: Dict with keys matching enabled_types
        """
        for key, count in counts.items():
            if key in self.anomaly_counts:
                self.anomaly_counts[key] = count
                if key in self.type_count_labels:
                    self.type_count_labels[key].setText(f"({count} found)")

        self._update_total_count()

    def _update_total_count(self):
        """Update total anomaly count display."""
        total = sum(
            self.anomaly_counts[key]
            for key in self.enabled_types
            if self.enabled_types[key]
        )
        self.total_count_label.setText(f"Total: {total} anomalies")

    def update_performance(self, fps: float, processing_time: float, overhead: float = 0.0):
        """Update performance metrics.

        Args:
            fps: Current frames per second
            processing_time: Processing time in milliseconds
            overhead: Overhead percentage (0-100)
        """
        self.fps_label.setText(f"FPS: {fps:.1f}")
        self.processing_time_label.setText(f"Processing: {processing_time:.1f}ms")
        self.overhead_label.setText(f"Overhead: {overhead:.1f}%")

        self.overhead_bar.setValue(int(overhead))

        # Color code overhead bar
        if overhead < 10:
            color = "#4CAF50"  # Green
        elif overhead < 20:
            color = "#FFC107"  # Yellow
        else:
            color = "#F44336"  # Red

        self.overhead_bar.setStyleSheet(f"""
            QProgressBar::chunk {{
                background-color: {color};
            }}
        """)

    def set_anomaly_priority_enabled(self, enabled: bool):
        """Programmatically set anomaly priority state."""
        self.main_toggle.setChecked(enabled)


# ============================================================================
# Main Inspection Window
# ============================================================================

class BosonControlPanel(QWidget):
    """FLIR Boson camera control panel widget."""

    # Signals
    sdk_connect_requested = pyqtSignal(str)  # Emits COM port
    sdk_disconnect_requested = pyqtSignal()
    sdk_scan_ports_requested = pyqtSignal()
    ffc_triggered = pyqtSignal()
    gain_mode_changed = pyqtSignal(str)  # 'high', 'low', 'auto'
    ffc_mode_changed = pyqtSignal(str)  # 'manual', 'auto', 'external'
    color_lut_changed = pyqtSignal(str)  # LUT name
    # AGC signals (Universal - ALL Boson cameras)
    agc_max_gain_changed = pyqtSignal(float)  # Max gain (1.0-4.0)
    agc_gamma_changed = pyqtSignal(float)  # Gamma (0.5-2.0)
    agc_linearity_changed = pyqtSignal(float)  # Linearity (0-100%)
    agc_dde_changed = pyqtSignal(float)  # DDE ratio (0.0-3.0)
    agc_reset_requested = pyqtSignal()  # Reset to defaults
    # New advanced controls
    shutter_position_changed = pyqtSignal(str)  # OPEN/CLOSED/AUTO
    agc_plateau_changed = pyqtSignal(float)  # 0.0-1.0
    agc_dampening_changed = pyqtSignal(float)  # 0.0-1.0
    # Radiometric mode control
    radiometric_mode_changed = pyqtSignal(bool)  # True=Radiometric, False=Colorized

    def __init__(self, parent=None):
        super().__init__(parent)
        # Remove fixed width to allow flexible sizing within tab
        self._init_ui()
        self._connect_signals()

    def _init_ui(self):
        """Initialize widget UI components with tabbed submenus."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Create tab widget for organization
        self.boson_tabs = QTabWidget()
        main_layout.addWidget(self.boson_tabs)

        # ===================================================================
        # CONNECTION TAB
        # ===================================================================
        connection_tab = QWidget()
        connection_scroll = QScrollArea()
        connection_scroll.setWidgetResizable(True)
        connection_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        connection_scroll.setFrameShape(QFrame.Shape.NoFrame)

        connection_content = QWidget()
        connection_layout = QVBoxLayout(connection_content)
        connection_layout.setSpacing(8)  # Reduced from 12
        connection_layout.setContentsMargins(6, 6, 6, 6)  # Reduced from 8

        # SDK Connection Status
        self._create_connection_status(connection_layout)

        # Camera Info
        self._create_camera_info(connection_layout)

        connection_layout.addStretch()
        connection_scroll.setWidget(connection_content)
        connection_tab_layout = QVBoxLayout(connection_tab)
        connection_tab_layout.setContentsMargins(0, 0, 0, 0)
        connection_tab_layout.addWidget(connection_scroll)

        self.boson_tabs.addTab(connection_tab, "Connection")

        # ===================================================================
        # SIMPLE CONTROLS TAB
        # ===================================================================
        simple_tab = QWidget()
        simple_scroll = QScrollArea()
        simple_scroll.setWidgetResizable(True)
        simple_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        simple_scroll.setFrameShape(QFrame.Shape.NoFrame)

        simple_content = QWidget()
        simple_layout = QVBoxLayout(simple_content)
        simple_layout.setSpacing(8)  # Reduced from 12
        simple_layout.setContentsMargins(6, 6, 6, 6)  # Reduced from 8

        # FFC Controls
        self._create_ffc_controls(simple_layout)

        # Gain Controls
        self._create_gain_controls(simple_layout)

        # Color LUT Controls
        self._create_color_lut_controls(simple_layout)

        simple_layout.addStretch()
        simple_scroll.setWidget(simple_content)
        simple_tab_layout = QVBoxLayout(simple_tab)
        simple_tab_layout.setContentsMargins(0, 0, 0, 0)
        simple_tab_layout.addWidget(simple_scroll)

        self.boson_tabs.addTab(simple_tab, "Simple Controls")

        # ===================================================================
        # ADVANCED CONTROLS TAB (AGC)
        # ===================================================================
        advanced_tab = QWidget()
        advanced_scroll = QScrollArea()
        advanced_scroll.setWidgetResizable(True)
        advanced_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        advanced_scroll.setFrameShape(QFrame.Shape.NoFrame)

        advanced_content = QWidget()
        advanced_layout = QVBoxLayout(advanced_content)
        advanced_layout.setSpacing(8)  # Reduced from 12
        advanced_layout.setContentsMargins(6, 6, 6, 6)  # Reduced from 8

        # AGC Controls (Universal Feature - ALL Bosons)
        self._create_agc_controls(advanced_layout)

        # Temperature Display
        self._create_temperature_display(advanced_layout)

        advanced_layout.addStretch()
        advanced_scroll.setWidget(advanced_content)
        advanced_tab_layout = QVBoxLayout(advanced_tab)
        advanced_tab_layout.setContentsMargins(0, 0, 0, 0)
        advanced_tab_layout.addWidget(advanced_scroll)

        self.boson_tabs.addTab(advanced_tab, "Advanced Controls")

        # ===================================================================
        # RADIOMETRIC STATUS TAB (Read-Only Display)
        # ===================================================================
        radiometric_tab = QWidget()
        radiometric_scroll = QScrollArea()
        radiometric_scroll.setWidgetResizable(True)
        radiometric_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        radiometric_scroll.setFrameShape(QFrame.Shape.NoFrame)

        radiometric_content = QWidget()
        radiometric_layout = QVBoxLayout(radiometric_content)
        radiometric_layout.setSpacing(8)
        radiometric_layout.setContentsMargins(6, 6, 6, 6)

        # UNIFIED CONTROL NOTICE
        unified_notice = QGroupBox("ℹ️ UNIFIED RADIOMETRIC CONTROL")
        unified_layout = QVBoxLayout(unified_notice)
        unified_layout.setSpacing(8)

        notice_text = QLabel(
            "<b>Radiometric settings are controlled from:</b><br>"
            "→ <b>Analysis Tab > Radiometric Panel</b><br><br>"
            "When you select a backend (8-bit OpenCV, 16-bit USB, or 16-bit flirpy), "
            "the system automatically configures the camera hardware mode (T-Linear/Colorized).<br><br>"
            "<i>This tab shows the current camera mode status.</i>"
        )
        notice_text.setWordWrap(True)
        notice_text.setStyleSheet("color: #aaf; font-size: 10px; padding: 8px;")
        unified_layout.addWidget(notice_text)
        radiometric_layout.addWidget(unified_notice)

        # Camera Mode Status Display (Read-Only)
        status_group = QGroupBox("CURRENT CAMERA OUTPUT MODE (Read-Only)")
        status_layout = QVBoxLayout(status_group)

        # Status label (updated by unified control)
        self.radiometric_mode_status = QLabel("Current Mode: UVC Post-Colorized (8-bit)")
        self.radiometric_mode_status.setStyleSheet(
            "font-weight: bold; padding: 8px; background-color: #2a2a2a; "
            "border-radius: 3px; font-size: 11px;"
        )
        self.radiometric_mode_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        status_layout.addWidget(self.radiometric_mode_status)

        # Mode explanation
        mode_explain = QLabel(
            "• <b>T-Linear Radiometric (16-bit)</b>: Precise temperature measurement<br>"
            "• <b>Colorized (8-bit)</b>: Visual thermal imaging with AGC"
        )
        mode_explain.setWordWrap(True)
        mode_explain.setStyleSheet("color: gray; font-size: 9px; padding: 8px;")
        status_layout.addWidget(mode_explain)

        radiometric_layout.addWidget(status_group)

        # Future: Lepton Integration
        lepton_group = QGroupBox("🔧 FUTURE: LEPTON INTEGRATION")
        lepton_layout = QVBoxLayout(lepton_group)

        lepton_label = QLabel(
            "<b>Planned Features:</b><br>"
            "• Lepton 3.5 radiometric support via integration board<br>"
            "• Similar VPC-style module architecture as Boson<br>"
            "• Unified control for both Boson and Lepton cameras<br>"
            "• Automatic backend/mode configuration for Lepton<br><br>"
            "<i>Integration board design in progress...</i>"
        )
        lepton_label.setWordWrap(True)
        lepton_label.setStyleSheet("color: #aa8; padding: 10px; font-size: 10px;")
        lepton_layout.addWidget(lepton_label)

        radiometric_layout.addWidget(lepton_group)

        # Advanced radiometric controls placeholder
        future_group = QGroupBox("ADVANCED RADIOMETRIC CONTROLS (Coming Soon)")
        future_layout = QVBoxLayout(future_group)

        future_label = QLabel(
            "Additional radiometric features:\n"
            "• Emissivity settings\n"
            "• Atmospheric corrections\n"
            "• Temperature range calibration\n"
            "• Spotmeter configuration\n\n"
            "Note: Requires radiometric camera model (Boson 640R/320R, Lepton 3.5)"
        )
        future_label.setWordWrap(True)
        future_label.setStyleSheet("color: gray; padding: 10px;")
        future_layout.addWidget(future_label)

        radiometric_layout.addWidget(future_group)
        radiometric_layout.addStretch()
        radiometric_scroll.setWidget(radiometric_content)
        radiometric_tab_layout = QVBoxLayout(radiometric_tab)
        radiometric_tab_layout.setContentsMargins(0, 0, 0, 0)
        radiometric_tab_layout.addWidget(radiometric_scroll)

        self.boson_tabs.addTab(radiometric_tab, "Radiometric")

        # ===================================================================
        # DIAGNOSTICS TAB (Phase 10)
        # ===================================================================
        diagnostics_tab = QWidget()
        diagnostics_scroll = QScrollArea()
        diagnostics_scroll.setWidgetResizable(True)
        diagnostics_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        diagnostics_scroll.setFrameShape(QFrame.Shape.NoFrame)

        diagnostics_content = QWidget()
        diagnostics_layout = QVBoxLayout(diagnostics_content)
        diagnostics_layout.setSpacing(8)
        diagnostics_layout.setContentsMargins(6, 6, 6, 6)

        # System Status Group
        system_group = QGroupBox("SYSTEM STATUS")
        system_layout = QVBoxLayout(system_group)

        # Frame count
        frame_layout = QHBoxLayout()
        frame_layout.addWidget(QLabel("Frame Count:"))
        self.diag_frame_count_label = QLabel("--")
        self.diag_frame_count_label.setStyleSheet("font-weight: bold;")
        frame_layout.addWidget(self.diag_frame_count_label)
        frame_layout.addStretch()
        system_layout.addLayout(frame_layout)

        # Board temperature
        board_temp_layout = QHBoxLayout()
        board_temp_layout.addWidget(QLabel("Board Temp:"))
        self.diag_board_temp_label = QLabel("--")
        self.diag_board_temp_label.setStyleSheet("font-weight: bold;")
        board_temp_layout.addWidget(self.diag_board_temp_label)
        board_temp_layout.addStretch()
        system_layout.addLayout(board_temp_layout)

        # FPA temperature
        fpa_temp_layout = QHBoxLayout()
        fpa_temp_layout.addWidget(QLabel("FPA Temp:"))
        self.diag_fpa_temp_label = QLabel("--")
        self.diag_fpa_temp_label.setStyleSheet("font-weight: bold;")
        fpa_temp_layout.addWidget(self.diag_fpa_temp_label)
        fpa_temp_layout.addStretch()
        system_layout.addLayout(fpa_temp_layout)

        diagnostics_layout.addWidget(system_group)

        # FFC Status Group
        ffc_status_group = QGroupBox("FFC STATUS")
        ffc_status_layout = QVBoxLayout(ffc_status_group)

        # Last FFC frame
        last_ffc_frame_layout = QHBoxLayout()
        last_ffc_frame_layout.addWidget(QLabel("Last FFC Frame:"))
        self.diag_last_ffc_frame_label = QLabel("--")
        self.diag_last_ffc_frame_label.setStyleSheet("font-weight: bold;")
        last_ffc_frame_layout.addWidget(self.diag_last_ffc_frame_label)
        last_ffc_frame_layout.addStretch()
        ffc_status_layout.addLayout(last_ffc_frame_layout)

        # Frames since FFC
        frames_since_layout = QHBoxLayout()
        frames_since_layout.addWidget(QLabel("Frames Since FFC:"))
        self.diag_frames_since_ffc_label = QLabel("--")
        self.diag_frames_since_ffc_label.setStyleSheet("font-weight: bold;")
        frames_since_layout.addWidget(self.diag_frames_since_ffc_label)
        frames_since_layout.addStretch()
        ffc_status_layout.addLayout(frames_since_layout)

        # Last FFC temp
        last_ffc_temp_layout = QHBoxLayout()
        last_ffc_temp_layout.addWidget(QLabel("Last FFC Temp:"))
        self.diag_last_ffc_temp_label = QLabel("--")
        self.diag_last_ffc_temp_label.setStyleSheet("font-weight: bold;")
        last_ffc_temp_layout.addWidget(self.diag_last_ffc_temp_label)
        last_ffc_temp_layout.addStretch()
        ffc_status_layout.addLayout(last_ffc_temp_layout)

        # Auto FFC threshold
        ffc_threshold_layout = QHBoxLayout()
        ffc_threshold_layout.addWidget(QLabel("Auto FFC Threshold:"))
        self.diag_ffc_threshold_label = QLabel("--")
        self.diag_ffc_threshold_label.setStyleSheet("font-weight: bold;")
        ffc_threshold_layout.addWidget(self.diag_ffc_threshold_label)
        ffc_threshold_layout.addStretch()
        ffc_status_layout.addLayout(ffc_threshold_layout)

        diagnostics_layout.addWidget(ffc_status_group)

        # Refresh button
        refresh_btn = QPushButton("Refresh Diagnostics")
        refresh_btn.clicked.connect(self._on_refresh_diagnostics)
        diagnostics_layout.addWidget(refresh_btn)

        diagnostics_layout.addStretch()
        diagnostics_scroll.setWidget(diagnostics_content)
        diagnostics_tab_layout = QVBoxLayout(diagnostics_tab)
        diagnostics_tab_layout.setContentsMargins(0, 0, 0, 0)
        diagnostics_tab_layout.addWidget(diagnostics_scroll)

        self.boson_tabs.addTab(diagnostics_tab, "Diagnostics")

    def _create_connection_status(self, layout):
        """Create SDK connection status display and controls."""
        status_group = QGroupBox("SDK CONNECTION")
        status_group.setMaximumWidth(400)  # Limit group box width
        status_layout = QVBoxLayout(status_group)

        # Connection status
        status_label_layout = QHBoxLayout()
        self.connection_status_label = QLabel("● Disconnected")
        self.connection_status_label.setStyleSheet("color: #ff4444; font-weight: bold;")
        self.connection_status_label.setMaximumWidth(200)
        status_label_layout.addWidget(self.connection_status_label)
        status_label_layout.addStretch()
        status_layout.addLayout(status_label_layout)

        # COM port selection
        port_layout = QHBoxLayout()
        port_label = QLabel("COM Port:")
        port_label.setFixedWidth(80)  # Fixed label width for alignment
        port_layout.addWidget(port_label)

        self.com_port_combo = QComboBox()
        self.com_port_combo.setEditable(True)
        self.com_port_combo.setPlaceholderText("COM Port")
        self.com_port_combo.setToolTip("Select COM port or enter manually (e.g., COM6)")
        self.com_port_combo.setMaximumWidth(150)
        port_layout.addWidget(self.com_port_combo)

        self.scan_ports_button = QPushButton("🔄")
        self.scan_ports_button.setFixedWidth(35)
        self.scan_ports_button.setToolTip("Scan for available COM ports")
        port_layout.addWidget(self.scan_ports_button)

        port_layout.addStretch()  # Push elements to left, prevent expansion

        status_layout.addLayout(port_layout)

        # Connection buttons
        button_layout = QHBoxLayout()

        self.connect_button = QPushButton("Connect")
        self.connect_button.setMinimumHeight(35)
        self.connect_button.setMaximumWidth(150)  # Limit button width
        self.connect_button.setStyleSheet("background-color: #4CAF50;")
        self.connect_button.setToolTip("Connect to Boson camera via SDK")
        button_layout.addWidget(self.connect_button)

        self.disconnect_button = QPushButton("Disconnect")
        self.disconnect_button.setMinimumHeight(35)
        self.disconnect_button.setMaximumWidth(150)  # Limit button width
        self.disconnect_button.setEnabled(False)
        self.disconnect_button.setToolTip("Disconnect from SDK")
        button_layout.addWidget(self.disconnect_button)

        button_layout.addStretch()  # Push buttons to left

        status_layout.addLayout(button_layout)

        # Connection hint
        self.connection_hint = QLabel("Connect via COM port or use --enable-boson-sdk flag")
        self.connection_hint.setStyleSheet("font-size: 10px; color: #888;")
        self.connection_hint.setWordWrap(True)
        self.connection_hint.setMaximumWidth(350)  # Limit label width
        status_layout.addWidget(self.connection_hint)

        layout.addWidget(status_group)

    def _create_camera_info(self, layout):
        """Create camera info display."""
        info_group = QGroupBox("CAMERA INFORMATION")
        info_group.setMaximumWidth(400)  # Limit group box width
        info_layout = QVBoxLayout(info_group)

        self.info_labels = {}

        info_fields = [
            ('serial', 'Serial Number:'),
            ('part_number', 'Part Number:'),
            ('software', 'Software Version:'),
            ('lens', 'Lens Number:'),
            ('table', 'Table Number:')
        ]

        for key, label_text in info_fields:
            row = QHBoxLayout()
            label = QLabel(label_text)
            label.setFixedWidth(120)  # Fixed width instead of min-width
            label.setStyleSheet("font-weight: bold;")
            value = QLabel("N/A")
            value.setStyleSheet("color: #888;")
            value.setWordWrap(True)
            value.setMaximumWidth(200)  # Limit value label width

            row.addWidget(label)
            row.addWidget(value)
            row.addStretch()  # Add stretch at end to push everything left

            self.info_labels[key] = value
            info_layout.addLayout(row)

        layout.addWidget(info_group)

    def _create_ffc_controls(self, layout):
        """Create FFC control buttons."""
        ffc_group = QGroupBox("FLAT FIELD CORRECTION (FFC)")
        ffc_layout = QVBoxLayout(ffc_group)

        # Manual FFC trigger button
        self.ffc_button = QPushButton("⚡ Trigger FFC")
        self.ffc_button.setMinimumHeight(40)
        self.ffc_button.setToolTip("Manually trigger Flat Field Correction (watch camera shutter)")
        ffc_layout.addWidget(self.ffc_button)

        # FFC Mode selection
        ffc_mode_layout = QHBoxLayout()
        ffc_label = QLabel("FFC Mode:")
        ffc_label.setFixedWidth(80)  # Fixed label width for alignment
        ffc_mode_layout.addWidget(ffc_label)

        self.ffc_mode_combo = QComboBox()
        self.ffc_mode_combo.addItems(['Manual', 'Auto', 'External'])
        self.ffc_mode_combo.setToolTip("FFC mode: Manual, Auto, or External trigger")
        self.ffc_mode_combo.setMinimumHeight(28)  # Consistent combo height
        self.ffc_mode_combo.setMaximumWidth(150)  # Limit horizontal expansion
        ffc_mode_layout.addWidget(self.ffc_mode_combo)

        ffc_mode_layout.addStretch()  # Push elements to left

        ffc_layout.addLayout(ffc_mode_layout)

        # Last FFC status
        self.ffc_status_label = QLabel("Status: Ready")
        self.ffc_status_label.setStyleSheet("font-size: 10px; color: #888;")
        ffc_layout.addWidget(self.ffc_status_label)

        layout.addWidget(ffc_group)

        # Add shutter control
        self._create_shutter_controls(layout)

    def _create_shutter_controls(self, layout):
        """Create shutter position control buttons."""
        shutter_group = QGroupBox("SHUTTER CONTROL")
        shutter_layout = QVBoxLayout(shutter_group)

        # Shutter position buttons
        button_layout = QHBoxLayout()

        self.shutter_auto_btn = QPushButton("Auto")
        self.shutter_auto_btn.setCheckable(True)
        self.shutter_auto_btn.setChecked(True)
        self.shutter_auto_btn.setToolTip("Automatic shutter control (recommended)")
        self.shutter_auto_btn.setMinimumHeight(32)
        button_layout.addWidget(self.shutter_auto_btn)

        self.shutter_open_btn = QPushButton("Open")
        self.shutter_open_btn.setCheckable(True)
        self.shutter_open_btn.setToolTip("Force shutter open (imaging mode)")
        self.shutter_open_btn.setMinimumHeight(32)
        button_layout.addWidget(self.shutter_open_btn)

        self.shutter_closed_btn = QPushButton("Closed")
        self.shutter_closed_btn.setCheckable(True)
        self.shutter_closed_btn.setToolTip("Force shutter closed (calibration)")
        self.shutter_closed_btn.setMinimumHeight(32)
        button_layout.addWidget(self.shutter_closed_btn)

        shutter_layout.addLayout(button_layout)

        # Create button group for exclusive selection
        from PyQt6.QtWidgets import QButtonGroup
        self.shutter_btn_group = QButtonGroup()
        self.shutter_btn_group.addButton(self.shutter_auto_btn)
        self.shutter_btn_group.addButton(self.shutter_open_btn)
        self.shutter_btn_group.addButton(self.shutter_closed_btn)
        self.shutter_btn_group.setExclusive(True)

        # Status label
        self.shutter_status_label = QLabel("Position: Auto")
        self.shutter_status_label.setStyleSheet("font-size: 10px; color: #888;")
        shutter_layout.addWidget(self.shutter_status_label)

        layout.addWidget(shutter_group)

    def _create_gain_controls(self, layout):
        """Create gain mode controls."""
        gain_group = QGroupBox("GAIN MODE")
        gain_layout = QVBoxLayout(gain_group)

        combo_layout = QHBoxLayout()
        self.gain_mode_combo = QComboBox()
        self.gain_mode_combo.addItems(['High', 'Low', 'Auto'])
        self.gain_mode_combo.setToolTip("Sensor gain mode:\n• High: Optimal for low temps\n• Low: Optimal for high temps\n• Auto: Automatic switching")
        self.gain_mode_combo.setMinimumHeight(28)
        self.gain_mode_combo.setMaximumWidth(150)
        combo_layout.addWidget(self.gain_mode_combo)
        combo_layout.addStretch()
        gain_layout.addLayout(combo_layout)

        # Current gain display
        self.current_gain_label = QLabel("Current: Auto")
        self.current_gain_label.setStyleSheet("font-size: 10px; color: #888;")
        gain_layout.addWidget(self.current_gain_label)

        layout.addWidget(gain_group)

    def _create_color_lut_controls(self, layout):
        """Create color LUT controls."""
        lut_group = QGroupBox("COLOR LOOKUP TABLE (LUT)")
        lut_layout = QVBoxLayout(lut_group)

        combo_layout = QHBoxLayout()
        self.color_lut_combo = QComboBox()
        self.color_lut_combo.addItems([
            'White Hot', 'Black Hot', 'Rainbow', 'Rainbow HC',
            'Ironbow', 'Lava', 'Arctic', 'Globow',
            'Graded Fire', 'Hottest'
        ])
        self.color_lut_combo.setToolTip("Hardware color palette (applies on-camera)")
        self.color_lut_combo.setMinimumHeight(28)
        self.color_lut_combo.setMaximumWidth(180)
        combo_layout.addWidget(self.color_lut_combo)
        combo_layout.addStretch()
        lut_layout.addLayout(combo_layout)

        hint = QLabel("Note: Hardware LUT applies before software processing")
        hint.setStyleSheet("font-size: 9px; color: #888;")
        hint.setWordWrap(True)
        lut_layout.addWidget(hint)

        layout.addWidget(lut_group)

    def _create_agc_controls(self, layout):
        """Create AGC (Automatic Gain Control) controls - Universal feature for ALL Bosons."""
        agc_group = QGroupBox("IMAGE ENHANCEMENT (AGC)")
        agc_layout = QVBoxLayout(agc_group)

        # Info label
        info_label = QLabel("✓ Works on ALL Boson cameras (radiometric and non-radiometric)")
        info_label.setStyleSheet("font-size: 9px; color: #0a0; font-weight: bold;")
        info_label.setWordWrap(True)
        agc_layout.addWidget(info_label)

        # Max Gain slider
        max_gain_layout = QVBoxLayout()
        max_gain_header = QHBoxLayout()
        max_gain_header.addWidget(QLabel("Max Gain (Contrast):"))
        self.agc_max_gain_value = QLabel("2.0x")
        self.agc_max_gain_value.setStyleSheet("font-weight: bold; color: #00aaff;")
        max_gain_header.addWidget(self.agc_max_gain_value)
        max_gain_header.addStretch()
        max_gain_layout.addLayout(max_gain_header)

        self.agc_max_gain_slider = QSlider(Qt.Orientation.Horizontal)
        self.agc_max_gain_slider.setRange(10, 40)  # 1.0 to 4.0 (x10)
        self.agc_max_gain_slider.setValue(20)  # Default 2.0
        self.agc_max_gain_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.agc_max_gain_slider.setTickInterval(5)
        self.agc_max_gain_slider.setToolTip("Limit maximum contrast enhancement (1.0-4.0x)")
        max_gain_layout.addWidget(self.agc_max_gain_slider)

        range_label = QLabel("Less Contrast                More Contrast")
        range_label.setStyleSheet("font-size: 9px; color: #888;")
        max_gain_layout.addWidget(range_label)
        agc_layout.addLayout(max_gain_layout)

        # Gamma slider
        gamma_layout = QVBoxLayout()
        gamma_header = QHBoxLayout()
        gamma_header.addWidget(QLabel("Gamma (ACE):"))
        self.agc_gamma_value = QLabel("1.0")
        self.agc_gamma_value.setStyleSheet("font-weight: bold; color: #00aaff;")
        gamma_header.addWidget(self.agc_gamma_value)
        gamma_header.addStretch()
        gamma_layout.addLayout(gamma_header)

        self.agc_gamma_slider = QSlider(Qt.Orientation.Horizontal)
        self.agc_gamma_slider.setRange(5, 20)  # 0.5 to 2.0 (x10)
        self.agc_gamma_slider.setValue(10)  # Default 1.0
        self.agc_gamma_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.agc_gamma_slider.setTickInterval(5)
        self.agc_gamma_slider.setToolTip("Gamma correction: <1.0 = more hot contrast, >1.0 = more cold contrast")
        gamma_layout.addWidget(self.agc_gamma_slider)

        range_label = QLabel("Hot Contrast               Cold Contrast")
        range_label.setStyleSheet("font-size: 9px; color: #888;")
        gamma_layout.addWidget(range_label)
        agc_layout.addLayout(gamma_layout)

        # Linearity slider
        linearity_layout = QVBoxLayout()
        linearity_header = QHBoxLayout()
        linearity_header.addWidget(QLabel("Linearity:"))
        self.agc_linearity_value = QLabel("50%")
        self.agc_linearity_value.setStyleSheet("font-weight: bold; color: #00aaff;")
        linearity_header.addWidget(self.agc_linearity_value)
        linearity_header.addStretch()
        linearity_layout.addLayout(linearity_header)

        self.agc_linearity_slider = QSlider(Qt.Orientation.Horizontal)
        self.agc_linearity_slider.setRange(0, 100)  # 0-100%
        self.agc_linearity_slider.setValue(50)  # Default 50%
        self.agc_linearity_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.agc_linearity_slider.setTickInterval(20)
        self.agc_linearity_slider.setToolTip("Histogram vs. linear: 0% = adaptive, 100% = linear")
        linearity_layout.addWidget(self.agc_linearity_slider)

        range_label = QLabel("Adaptive (Histogram)          Linear")
        range_label.setStyleSheet("font-size: 9px; color: #888;")
        linearity_layout.addWidget(range_label)
        agc_layout.addLayout(linearity_layout)

        # DDE (Digital Detail Enhancement) slider
        dde_layout = QVBoxLayout()
        dde_header = QHBoxLayout()
        dde_header.addWidget(QLabel("Detail (DDE):"))
        self.agc_dde_value = QLabel("1.3")
        self.agc_dde_value.setStyleSheet("font-weight: bold; color: #00aaff;")
        dde_header.addWidget(self.agc_dde_value)
        dde_header.addStretch()
        dde_layout.addLayout(dde_header)

        self.agc_dde_slider = QSlider(Qt.Orientation.Horizontal)
        self.agc_dde_slider.setRange(0, 30)  # 0.0 to 3.0 (x10)
        self.agc_dde_slider.setValue(13)  # Default 1.3
        self.agc_dde_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.agc_dde_slider.setTickInterval(5)
        self.agc_dde_slider.setToolTip("Detail enhancement: higher = sharper edges")
        dde_layout.addWidget(self.agc_dde_slider)

        range_label = QLabel("Soft Edges                 Sharp Edges")
        range_label.setStyleSheet("font-size: 9px; color: #888;")
        dde_layout.addWidget(range_label)
        agc_layout.addLayout(dde_layout)

        # Separator for new advanced controls
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        agc_layout.addWidget(separator)

        # Advanced AGC label
        advanced_label = QLabel("Advanced Controls:")
        advanced_label.setStyleSheet("font-weight: bold; font-size: 10px; margin-top: 5px;")
        agc_layout.addWidget(advanced_label)

        # Plateau slider (histogram equalization)
        plateau_layout = QVBoxLayout()
        plateau_header = QHBoxLayout()
        plateau_header.addWidget(QLabel("Plateau:"))
        self.agc_plateau_value = QLabel("50%")
        self.agc_plateau_value.setStyleSheet("font-weight: bold; color: #00aaff;")
        plateau_header.addWidget(self.agc_plateau_value)
        plateau_header.addStretch()
        plateau_layout.addLayout(plateau_header)

        self.agc_plateau_slider = QSlider(Qt.Orientation.Horizontal)
        self.agc_plateau_slider.setRange(0, 100)  # 0-100%
        self.agc_plateau_slider.setValue(50)  # Default 50%
        self.agc_plateau_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.agc_plateau_slider.setTickInterval(20)
        self.agc_plateau_slider.setToolTip("Histogram plateau equalization (0-100%)")
        plateau_layout.addWidget(self.agc_plateau_slider)

        range_label = QLabel("Less Equalization         More Equalization")
        range_label.setStyleSheet("font-size: 9px; color: #888;")
        plateau_layout.addWidget(range_label)
        agc_layout.addLayout(plateau_layout)

        # Dampening slider (temporal smoothing)
        dampening_layout = QVBoxLayout()
        dampening_header = QHBoxLayout()
        dampening_header.addWidget(QLabel("Dampening:"))
        self.agc_dampening_value = QLabel("50%")
        self.agc_dampening_value.setStyleSheet("font-weight: bold; color: #00aaff;")
        dampening_header.addWidget(self.agc_dampening_value)
        dampening_header.addStretch()
        dampening_layout.addLayout(dampening_header)

        self.agc_dampening_slider = QSlider(Qt.Orientation.Horizontal)
        self.agc_dampening_slider.setRange(0, 100)  # 0-100%
        self.agc_dampening_slider.setValue(50)  # Default 50%
        self.agc_dampening_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.agc_dampening_slider.setTickInterval(20)
        self.agc_dampening_slider.setToolTip("Temporal smoothing factor (0-100%)")
        dampening_layout.addWidget(self.agc_dampening_slider)

        range_label = QLabel("Fast Response             Smooth/Slow")
        range_label.setStyleSheet("font-size: 9px; color: #888;")
        dampening_layout.addWidget(range_label)
        agc_layout.addLayout(dampening_layout)

        # Reset button
        self.agc_reset_button = QPushButton("Reset to Defaults")
        self.agc_reset_button.setMinimumHeight(30)
        self.agc_reset_button.setToolTip("Reset all AGC settings to defaults")
        agc_layout.addWidget(self.agc_reset_button)

        # Status hint
        status_hint = QLabel("AGC enhances image quality for better defect detection")
        status_hint.setStyleSheet("font-size: 9px; color: #888; font-style: italic;")
        status_hint.setWordWrap(True)
        agc_layout.addWidget(status_hint)

        layout.addWidget(agc_group)

    def _create_temperature_display(self, layout):
        """Create FPA temperature display."""
        temp_group = QGroupBox("FPA TEMPERATURE")
        temp_layout = QVBoxLayout(temp_group)

        self.fpa_temp_label = QLabel("N/A")
        self.fpa_temp_label.setStyleSheet("font-size: 24px; font-weight: bold; color: #00aaff;")
        self.fpa_temp_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        temp_layout.addWidget(self.fpa_temp_label)

        self.fpa_temp_unit = QLabel("Focal Plane Array Temperature")
        self.fpa_temp_unit.setStyleSheet("font-size: 10px; color: #888;")
        self.fpa_temp_unit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        temp_layout.addWidget(self.fpa_temp_unit)

        # Auto-refresh toggle
        refresh_layout = QHBoxLayout()
        self.temp_auto_refresh = QCheckBox("Auto-refresh (1s)")
        self.temp_auto_refresh.setChecked(True)
        self.temp_auto_refresh.setToolTip("Automatically read temperature every second")
        refresh_layout.addWidget(self.temp_auto_refresh)
        refresh_layout.addStretch()
        temp_layout.addLayout(refresh_layout)

        layout.addWidget(temp_group)

    def _connect_signals(self):
        """Connect internal signals."""
        # SDK connection controls
        self.connect_button.clicked.connect(self._on_connect_clicked)
        self.disconnect_button.clicked.connect(lambda: self.sdk_disconnect_requested.emit())
        self.scan_ports_button.clicked.connect(self._on_scan_ports_clicked)

        # Camera controls
        self.ffc_button.clicked.connect(lambda: self.ffc_triggered.emit())
        self.gain_mode_combo.currentTextChanged.connect(
            lambda text: self.gain_mode_changed.emit(text.lower())
        )
        self.ffc_mode_combo.currentTextChanged.connect(
            lambda text: self.ffc_mode_changed.emit(text.lower())
        )
        self.color_lut_combo.currentTextChanged.connect(
            lambda text: self.color_lut_changed.emit(text.lower().replace(' ', '_'))
        )

        # AGC controls
        self.agc_max_gain_slider.valueChanged.connect(self._on_agc_max_gain_changed)
        self.agc_gamma_slider.valueChanged.connect(self._on_agc_gamma_changed)
        self.agc_linearity_slider.valueChanged.connect(self._on_agc_linearity_changed)
        self.agc_dde_slider.valueChanged.connect(self._on_agc_dde_changed)
        self.agc_plateau_slider.valueChanged.connect(self._on_agc_plateau_changed)
        self.agc_dampening_slider.valueChanged.connect(self._on_agc_dampening_changed)
        self.agc_reset_button.clicked.connect(self._on_agc_reset_clicked)

        # Shutter controls
        self.shutter_auto_btn.clicked.connect(lambda: self._on_shutter_position_changed("AUTO"))
        self.shutter_open_btn.clicked.connect(lambda: self._on_shutter_position_changed("OPEN"))
        self.shutter_closed_btn.clicked.connect(lambda: self._on_shutter_position_changed("CLOSED"))

    def _on_connect_clicked(self):
        """Handle connect button click."""
        com_port = self.com_port_combo.currentText().strip()
        if com_port:
            self.sdk_connect_requested.emit(com_port)
        else:
            # Auto-detect if no port specified
            self.sdk_connect_requested.emit("")

    def _on_scan_ports_clicked(self):
        """Handle scan ports button click."""
        self.sdk_scan_ports_requested.emit()

    def _on_agc_max_gain_changed(self, value: int):
        """Handle max gain slider change."""
        gain = value / 10.0  # Convert to 1.0-4.0 range
        self.agc_max_gain_value.setText(f"{gain:.1f}x")
        self.agc_max_gain_changed.emit(gain)

    def _on_agc_gamma_changed(self, value: int):
        """Handle gamma slider change."""
        gamma = value / 10.0  # Convert to 0.5-2.0 range
        self.agc_gamma_value.setText(f"{gamma:.1f}")
        self.agc_gamma_changed.emit(gamma)

    def _on_agc_linearity_changed(self, value: int):
        """Handle linearity slider change."""
        self.agc_linearity_value.setText(f"{value}%")
        self.agc_linearity_changed.emit(float(value))

    def _on_agc_dde_changed(self, value: int):
        """Handle DDE slider change."""
        dde = value / 10.0  # Convert to 0.0-3.0 range
        self.agc_dde_value.setText(f"{dde:.1f}")
        self.agc_dde_changed.emit(dde)

    def _on_agc_reset_clicked(self):
        """Reset AGC controls to defaults."""
        self.agc_max_gain_slider.setValue(20)  # 2.0x
        self.agc_gamma_slider.setValue(10)  # 1.0
        self.agc_linearity_slider.setValue(50)  # 50%
        self.agc_dde_slider.setValue(13)  # 1.3
        self.agc_plateau_slider.setValue(50)  # 50%
        self.agc_dampening_slider.setValue(50)  # 50%
        self.agc_reset_requested.emit()

    def _on_agc_plateau_changed(self, value: int):
        """Handle AGC plateau slider change."""
        self.agc_plateau_value.setText(f"{value}%")
        self.agc_plateau_changed.emit(value / 100.0)

    def _on_agc_dampening_changed(self, value: int):
        """Handle AGC dampening slider change."""
        self.agc_dampening_value.setText(f"{value}%")
        self.agc_dampening_changed.emit(value / 100.0)

    def _on_shutter_position_changed(self, position: str):
        """Handle shutter position button change."""
        self.shutter_status_label.setText(f"Position: {position.capitalize()}")
        self.shutter_position_changed.emit(position)

    def _on_radiometric_mode_apply(self):
        """Handle radiometric mode change request."""
        enable_radiometric = self.radiometric_mode_radio.isChecked()
        self.radiometric_mode_changed.emit(enable_radiometric)

        # Update status label
        if enable_radiometric:
            self.radiometric_mode_status.setText("Switching to: T-Linear Radiometric (16-bit)...")
            self.radiometric_mode_status.setStyleSheet("font-weight: bold; padding: 4px; background-color: #444400; border-radius: 3px; color: yellow;")
        else:
            self.radiometric_mode_status.setText("Switching to: UVC Post-Colorized (8-bit)...")
            self.radiometric_mode_status.setStyleSheet("font-weight: bold; padding: 4px; background-color: #444400; border-radius: 3px; color: yellow;")

    def update_radiometric_mode_status(self, is_radiometric: bool, success: bool = True):
        """Update the radiometric mode status display."""
        if success:
            if is_radiometric:
                self.radiometric_mode_status.setText("Current Mode: T-Linear Radiometric (16-bit) ✓")
                self.radiometric_mode_status.setStyleSheet("font-weight: bold; padding: 4px; background-color: #004400; border-radius: 3px; color: #44ff44;")
                self.radiometric_mode_radio.setChecked(True)
            else:
                self.radiometric_mode_status.setText("Current Mode: UVC Post-Colorized (8-bit) ✓")
                self.radiometric_mode_status.setStyleSheet("font-weight: bold; padding: 4px; background-color: #004400; border-radius: 3px; color: #44ff44;")
                self.colorized_mode_radio.setChecked(True)
        else:
            self.radiometric_mode_status.setText("Mode change failed ✗")
            self.radiometric_mode_status.setStyleSheet("font-weight: bold; padding: 4px; background-color: #440000; border-radius: 3px; color: #ff4444;")

    def update_connection_status(self, connected: bool, port: str = None):
        """Update SDK connection status and button states."""
        if connected:
            self.connection_status_label.setText("● Connected")
            self.connection_status_label.setStyleSheet("color: #44ff44; font-weight: bold;")
            self.connection_hint.setText("SDK features available")

            # Update connection button states
            self.connect_button.setEnabled(False)
            self.disconnect_button.setEnabled(True)
            self.com_port_combo.setEnabled(False)
            self.scan_ports_button.setEnabled(False)

            # Enable controls
            self.ffc_button.setEnabled(True)
            self.gain_mode_combo.setEnabled(True)
            self.ffc_mode_combo.setEnabled(True)
            self.color_lut_combo.setEnabled(True)
            # Enable AGC controls
            self.agc_max_gain_slider.setEnabled(True)
            self.agc_gamma_slider.setEnabled(True)
            self.agc_linearity_slider.setEnabled(True)
            self.agc_dde_slider.setEnabled(True)
            self.agc_plateau_slider.setEnabled(True)
            self.agc_dampening_slider.setEnabled(True)
            self.agc_reset_button.setEnabled(True)
            # Enable shutter controls
            self.shutter_auto_btn.setEnabled(True)
            self.shutter_open_btn.setEnabled(True)
            self.shutter_closed_btn.setEnabled(True)
        else:
            self.connection_status_label.setText("● Disconnected")
            self.connection_status_label.setStyleSheet("color: #ff4444; font-weight: bold;")
            self.connection_hint.setText("Connect via COM port or use --enable-boson-sdk flag")

            # Update connection button states
            self.connect_button.setEnabled(True)
            self.disconnect_button.setEnabled(False)
            self.com_port_combo.setEnabled(True)
            self.scan_ports_button.setEnabled(True)

            # Disable controls
            self.ffc_button.setEnabled(False)
            self.gain_mode_combo.setEnabled(False)
            self.ffc_mode_combo.setEnabled(False)
            self.color_lut_combo.setEnabled(False)
            # Disable AGC controls
            self.agc_max_gain_slider.setEnabled(False)
            self.agc_gamma_slider.setEnabled(False)
            self.agc_linearity_slider.setEnabled(False)
            self.agc_dde_slider.setEnabled(False)
            self.agc_plateau_slider.setEnabled(False)
            self.agc_dampening_slider.setEnabled(False)
            self.agc_reset_button.setEnabled(False)
            # Disable shutter controls
            self.shutter_auto_btn.setEnabled(False)
            self.shutter_open_btn.setEnabled(False)
            self.shutter_closed_btn.setEnabled(False)

    def update_com_ports(self, ports: list):
        """Update COM port dropdown with available ports."""
        current = self.com_port_combo.currentText()
        self.com_port_combo.clear()
        self.com_port_combo.addItems(ports)
        # Restore previous selection if it's still available
        if current in ports:
            self.com_port_combo.setCurrentText(current)

    def update_camera_info(self, info):
        """Update camera information display."""
        if hasattr(info, 'serial_number') and info.serial_number:
            self.info_labels['serial'].setText(str(info.serial_number))
            self.info_labels['serial'].setStyleSheet("color: #e0e0e0;")

        if hasattr(info, 'camera_part_number') and info.camera_part_number:
            self.info_labels['part_number'].setText(str(info.camera_part_number))
            self.info_labels['part_number'].setStyleSheet("color: #e0e0e0;")

        if hasattr(info, 'software_version') and info.software_version:
            self.info_labels['software'].setText(str(info.software_version))
            self.info_labels['software'].setStyleSheet("color: #e0e0e0;")

        if hasattr(info, 'lens_number') and info.lens_number is not None:
            self.info_labels['lens'].setText(str(info.lens_number))
            self.info_labels['lens'].setStyleSheet("color: #e0e0e0;")

        if hasattr(info, 'table_number') and info.table_number is not None:
            self.info_labels['table'].setText(str(info.table_number))
            self.info_labels['table'].setStyleSheet("color: #e0e0e0;")

        # Update gain mode if available
        if hasattr(info, 'gain_mode') and info.gain_mode:
            self.current_gain_label.setText(f"Current: {info.gain_mode.name}")
            self.current_gain_label.setStyleSheet("font-size: 10px; color: #00aaff;")

    def update_fpa_temperature(self, temp_kelvin: float, temp_celsius: float):
        """Update FPA temperature display."""
        self.fpa_temp_label.setText(f"{temp_celsius:.1f}°C")
        self.fpa_temp_unit.setText(f"({temp_kelvin:.1f}K)")

    def set_ffc_status(self, message: str, is_error: bool = False):
        """Update FFC status message."""
        color = "#ff4444" if is_error else "#44ff44"
        self.ffc_status_label.setText(f"Status: {message}")
        self.ffc_status_label.setStyleSheet(f"font-size: 10px; color: {color};")

    def update_connection_status(self, connected: bool):
        """Update SDK connection status in UI."""
        if connected:
            self.connection_status_label.setText("● Connected")
            self.connection_status_label.setStyleSheet("color: #44ff44; font-weight: bold;")
            self.connect_button.setEnabled(False)
            self.disconnect_button.setEnabled(True)
            self.com_port_combo.setEnabled(False)
            self.scan_ports_button.setEnabled(False)
        else:
            self.connection_status_label.setText("● Disconnected")
            self.connection_status_label.setStyleSheet("color: #ff4444; font-weight: bold;")
            self.connect_button.setEnabled(True)
            self.disconnect_button.setEnabled(False)
            self.com_port_combo.setEnabled(True)
            self.scan_ports_button.setEnabled(True)

    def set_status(self, message: str, is_error: bool = False):
        """Update connection hint/status message."""
        color = "#ff4444" if is_error else "#44ff44"
        self.connection_hint.setText(message)
        self.connection_hint.setStyleSheet(f"font-size: 10px; color: {color};")

    def update_ports(self, ports: list):
        """Update COM port dropdown with scanned ports."""
        current = self.com_port_combo.currentText()
        self.com_port_combo.clear()
        if ports:
            self.com_port_combo.addItems(ports)
            if current in ports:
                self.com_port_combo.setCurrentText(current)
        else:
            self.com_port_combo.setPlaceholderText("No ports found")

    # ========================================================================
    # Diagnostics Panel Methods (Phase 10)
    # ========================================================================

    def _on_refresh_diagnostics(self):
        """Signal to refresh diagnostics data from application."""
        # This will be connected to application's refresh_boson_diagnostics method
        pass

    def update_diagnostics(self, diagnostics: dict):
        """
        Update diagnostics panel with camera status data.

        Args:
            diagnostics: Dictionary with keys:
                - frame_count: int
                - board_temp_c: float
                - fpa_temp_c: float
                - last_ffc_frame: int
                - frames_since_ffc: int
                - last_ffc_temp_c: float
                - ffc_temp_delta_c: float
        """
        # System status
        if 'frame_count' in diagnostics and diagnostics['frame_count'] is not None:
            self.diag_frame_count_label.setText(f"{diagnostics['frame_count']:,}")
        else:
            self.diag_frame_count_label.setText("--")

        if 'board_temp_c' in diagnostics and diagnostics['board_temp_c'] is not None:
            self.diag_board_temp_label.setText(f"{diagnostics['board_temp_c']:.1f}°C")
        else:
            self.diag_board_temp_label.setText("--")

        if 'fpa_temp_c' in diagnostics and diagnostics['fpa_temp_c'] is not None:
            self.diag_fpa_temp_label.setText(f"{diagnostics['fpa_temp_c']:.1f}°C")
        else:
            self.diag_fpa_temp_label.setText("--")

        # FFC status
        if 'last_ffc_frame' in diagnostics and diagnostics['last_ffc_frame'] is not None:
            self.diag_last_ffc_frame_label.setText(f"{diagnostics['last_ffc_frame']:,}")
        else:
            self.diag_last_ffc_frame_label.setText("--")

        if 'frames_since_ffc' in diagnostics and diagnostics['frames_since_ffc'] is not None:
            self.diag_frames_since_ffc_label.setText(f"{diagnostics['frames_since_ffc']:,}")
        else:
            self.diag_frames_since_ffc_label.setText("--")

        if 'last_ffc_temp_c' in diagnostics and diagnostics['last_ffc_temp_c'] is not None:
            self.diag_last_ffc_temp_label.setText(f"{diagnostics['last_ffc_temp_c']:.1f}°C")
        else:
            self.diag_last_ffc_temp_label.setText("--")

        if 'ffc_temp_delta_c' in diagnostics and diagnostics['ffc_temp_delta_c'] is not None:
            self.diag_ffc_threshold_label.setText(f"{diagnostics['ffc_temp_delta_c']:.1f}°C")
        else:
            self.diag_ffc_threshold_label.setText("--")


# ============================================================================
# Combined Anomaly Control Widget (Automatic + Manual)
# ============================================================================

class CombinedAnomalyWidget(QWidget):
    """
    Combined anomaly detection widget with automatic and manual modes.
    Uses tabs to switch between automatic (image analysis) and manual (threshold) modes.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        # Removed fixed width - use parent tab width dynamically

        self._init_ui()

    def _init_ui(self):
        """Initialize widget UI components."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Create tab widget for mode switching
        self.mode_tabs = QTabWidget()
        self.mode_tabs.setDocumentMode(False)

        # Automatic mode (existing anomaly widget)
        self.automatic_widget = AnomalyWidget()
        self.mode_tabs.addTab(self.automatic_widget, "Automatic")

        # Manual threshold mode
        self.manual_widget = ManualThresholdWidget()
        self.mode_tabs.addTab(self.manual_widget, "Manual")

        main_layout.addWidget(self.mode_tabs)

# ============================================================================
# Settings Panel
# ============================================================================

class SettingsPanel(QGroupBox):
    """Panel for application configuration settings."""

    # Signals
    device_changed = pyqtSignal(str)
    backend_changed = pyqtSignal(str)
    theme_changed = pyqtSignal(str)  # New signal
    palette_changed = pyqtSignal(str)
    baseline_lock_toggled = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__("Configuration", parent)
        self._init_ui()

    def _init_ui(self):
        """Initialize widget UI components."""
        layout = QVBoxLayout()
        layout.setSpacing(12)  # Space between group boxes to prevent overlap

        # Processing Settings
        proc_group = QGroupBox("Processing")
        proc_layout = QVBoxLayout(proc_group)
        proc_layout.setSpacing(10)  # Consistent spacing for all elements
        proc_layout.setContentsMargins(8, 8, 8, 8)  # Add padding inside group

        # Device Selection
        device_layout = QHBoxLayout()
        device_layout.addWidget(QLabel("Device:"))
        self.device_combo = QComboBox()
        self.device_combo.setMinimumHeight(28)  # Taller for full text visibility
        self.device_combo.addItems(["CPU", "CUDA"])
        self.device_combo.currentTextChanged.connect(self.device_changed.emit)
        device_layout.addWidget(self.device_combo)
        proc_layout.addLayout(device_layout)

        # Baseline Lock
        self.baseline_check = QCheckBox("Lock Baseline Temp")
        self.baseline_check.toggled.connect(self.baseline_lock_toggled.emit)
        proc_layout.addWidget(self.baseline_check)
        
        layout.addWidget(proc_group)

        # System Settings
        sys_group = QGroupBox("System Configuration")
        sys_layout = QVBoxLayout(sys_group)
        sys_layout.setSpacing(10)
        sys_layout.setContentsMargins(8, 8, 8, 8)

        # Theme Selection
        theme_layout = QHBoxLayout()
        theme_layout.addWidget(QLabel("Theme:"))
        self.theme_combo = QComboBox()
        self.theme_combo.setMinimumHeight(28)
        self.theme_combo.addItems(list(THEMES.keys()))
        self.theme_combo.currentTextChanged.connect(self.theme_changed.emit)
        theme_layout.addWidget(self.theme_combo)
        sys_layout.addLayout(theme_layout)

        # Backend Selection
        backend_layout = QHBoxLayout()
        backend_layout.addWidget(QLabel("Backend:"))
        self.backend_combo = QComboBox()
        self.backend_combo.setMinimumHeight(28)
        self.backend_combo.addItems(["OpenCV (8-bit)", "Flirpy (16-bit Radiometric)"])
        self.backend_combo.setToolTip("Select thermal camera backend. Flirpy required for temperature measurement.")
        self.backend_combo.currentTextChanged.connect(self.backend_changed.emit)
        backend_layout.addWidget(self.backend_combo)
        sys_layout.addLayout(backend_layout)

        # COM Port
        com_layout = QHBoxLayout()
        com_layout.addWidget(QLabel("SDK COM Port:"))
        self.com_port_edit = QComboBox()
        self.com_port_edit.setEditable(True)
        self.com_port_edit.setMinimumHeight(28)
        self.com_port_edit.addItems(["COM3", "COM4", "COM5", "/dev/ttyACM0"])
        # self.com_port_edit.currentTextChanged.connect(self.com_port_changed.emit) # TODO: Implement signal
        com_layout.addWidget(self.com_port_edit)
        sys_layout.addLayout(com_layout)

        # Paths
        paths_layout = QHBoxLayout()
        self.paths_btn = QPushButton("📂 Storage Paths")
        paths_layout.addWidget(self.paths_btn)
        sys_layout.addLayout(paths_layout)

        layout.addWidget(sys_group)

        layout.addStretch()
        self.setLayout(layout)

    def _populate_palette_combo(self, combo: QComboBox):
        """Populate a combo box with categorized palettes."""
        palette_categories = [
            ("GRAYSCALE", [
                PaletteType.WHITE_HOT, PaletteType.BLACK_HOT,
                PaletteType.GRAY, PaletteType.SEPIA
            ]),
            ("IRON/FIRE", [
                PaletteType.IRONBOW, PaletteType.LAVA, PaletteType.GRADEDFIRE,
                PaletteType.HOTTEST, PaletteType.AMBER, PaletteType.INFERNO
            ]),
            ("RAINBOW", [
                PaletteType.RAINBOW, PaletteType.RAINBOW_HC, PaletteType.RAINBOW_REVERSED,
                PaletteType.SPECTRAL, PaletteType.COOL_HOT
            ]),
            ("COLD/ARCTIC", [
                PaletteType.ARCTIC, PaletteType.ICE,
                PaletteType.WINTER, PaletteType.OCEAN
            ]),
            ("SCIENTIFIC", [
                PaletteType.VIRIDIS, PaletteType.PLASMA, PaletteType.MAGMA,
                PaletteType.CIVIDIS, PaletteType.TURBO
            ]),
            ("DIVERGING", [
                PaletteType.BLUE_RED, PaletteType.COOL_WARM, PaletteType.PURPLE_ORANGE,
                PaletteType.GREEN_RED, PaletteType.BLUE_YELLOW, PaletteType.PINK_GREEN
            ]),
            ("SEQUENTIAL", [
                PaletteType.GLOBOW, PaletteType.MEDICAL, PaletteType.THERMAL,
                PaletteType.HELIX, PaletteType.CUBEHELIX, PaletteType.TWILIGHT, PaletteType.DUSK
            ]),
            ("SPECIALIZED", [
                PaletteType.FUSION, PaletteType.PRISM, PaletteType.ALARM,
                PaletteType.LAPLACIAN, PaletteType.ISOTHERM, PaletteType.VELOCITY,
                PaletteType.TERRAIN, PaletteType.DEPTH
            ])
        ]

        # Populate combo box with categorized palettes
        for category_name, palettes in palette_categories:
            # Add category header (bold, disabled)
            combo.addItem(f"─── {category_name} ───")
            idx = combo.count() - 1
            item = combo.model().item(idx)
            font = QFont()
            font.setBold(True)
            item.setFont(font)
            item.setEnabled(False)

            # Add palette items (indented)
            for palette in palettes:
                combo.addItem(f"  {palette.value}")

    def _on_palette_changed(self, palette_name: str):
        """Handle palette change, cleaning category headers."""
        # Skip category headers (they start with ───)
        if palette_name.startswith("───"):
            return
        # Remove leading/trailing spaces and indentation
        clean_name = palette_name.strip()
        if clean_name:
            self.palette_changed.emit(clean_name)

# ============================================================================
# Boson SDK Panel
# ============================================================================

class BosonSDKPanel(QGroupBox):
    """Panel for Boson SDK connection controls"""
    
    # Signals
    connect_clicked = pyqtSignal(str)  # COM port
    disconnect_clicked = pyqtSignal()
    ffc_clicked = pyqtSignal()
    scan_ports_clicked = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__("Boson SDK Control", parent)
        self._init_ui()
        
    def _init_ui(self):
        layout = QVBoxLayout()
        
        # Connection Status
        status_layout = QHBoxLayout()
        status_layout.addWidget(QLabel("Status:"))
        self.status_label = QLabel("Disconnected")
        self.status_label.setStyleSheet("color: #ff6b6b; font-weight: bold;")
        status_layout.addWidget(self.status_label)
        status_layout.addStretch()
        layout.addLayout(status_layout)
        
        # COM Port Selection
        port_layout = QHBoxLayout()
        port_layout.addWidget(QLabel("COM Port:"))
        self.port_combo = QComboBox()
        self.port_combo.setEditable(True)
        self.port_combo.addItems(["COM1", "COM2", "COM3", "COM4", "COM5", "COM6"])
        self.port_combo.setCurrentText("COM6")
        self.port_combo.setMinimumWidth(100)
        port_layout.addWidget(self.port_combo)
        
        self.scan_btn = QPushButton("🔍")
        self.scan_btn.setToolTip("Scan for available COM ports")
        self.scan_btn.setMaximumWidth(40)
        self.scan_btn.clicked.connect(self._on_scan_ports)
        port_layout.addWidget(self.scan_btn)
        layout.addLayout(port_layout)
        
        # Connect/Disconnect Buttons
        btn_layout = QHBoxLayout()
        self.connect_btn = QPushButton("Connect")
        self.connect_btn.clicked.connect(self._on_connect)
        btn_layout.addWidget(self.connect_btn)
        
        self.disconnect_btn = QPushButton("Disconnect")
        self.disconnect_btn.clicked.connect(self._on_disconnect)
        self.disconnect_btn.setEnabled(False)
        btn_layout.addWidget(self.disconnect_btn)
        layout.addLayout(btn_layout)
        
        # FFC Button
        self.ffc_btn = QPushButton("Trigger FFC")
        self.ffc_btn.setToolTip("Flat Field Correction (shutter calibration)")
        self.ffc_btn.clicked.connect(self._on_ffc)
        self.ffc_btn.setEnabled(False)
        layout.addWidget(self.ffc_btn)
        
        # Status Message
        self.message_label = QLabel("")
        self.message_label.setWordWrap(True)
        self.message_label.setStyleSheet("font-size: 9pt; color: #666;")
        layout.addWidget(self.message_label)
        
        self.setLayout(layout)
        
    def _on_connect(self):
        """Emit connect signal with selected COM port"""
        port = self.port_combo.currentText()
        self.connect_clicked.emit(port)
        
    def _on_disconnect(self):
        """Emit disconnect signal"""
        self.disconnect_clicked.emit()
        
    def _on_ffc(self):
        """Emit FFC trigger signal"""
        self.ffc_clicked.emit()
        
    def _on_scan_ports(self):
        """Emit scan ports signal"""
        self.scan_ports_clicked.emit()
        
    def set_connected(self, connected: bool):
        """Update UI for connection state"""
        if connected:
            self.status_label.setText("Connected")
            self.status_label.setStyleSheet("color: #51cf66; font-weight: bold;")
            self.connect_btn.setEnabled(False)
            self.disconnect_btn.setEnabled(True)
            self.ffc_btn.setEnabled(True)
            self.port_combo.setEnabled(False)
            self.scan_btn.setEnabled(False)
        else:
            self.status_label.setText("Disconnected")
            self.status_label.setStyleSheet("color: #ff6b6b; font-weight: bold;")
            self.connect_btn.setEnabled(True)
            self.disconnect_btn.setEnabled(False)
            self.ffc_btn.setEnabled(False)
            self.port_combo.setEnabled(True)
            self.scan_btn.setEnabled(True)
            
    def set_status(self, message: str, is_error: bool = False):
        """Set status message"""
        self.message_label.setText(message)
        if is_error:
            self.message_label.setStyleSheet("font-size: 9pt; color: #ff6b6b;")
        else:
            self.message_label.setStyleSheet("font-size: 9pt; color: #51cf66;")
            
    def update_ports(self, ports: list):
        """Update COM port dropdown"""
        current = self.port_combo.currentText()
        self.port_combo.clear()
        self.port_combo.addItems(ports)
        if current in ports:
            self.port_combo.setCurrentText(current)
            
    def update_camera_info(self, serial_number: str):
        """Update camera information display"""
        self.set_status(f"SN: {serial_number}")
        
    def update_fpa_temperature(self, temp_k: float, temp_c: float):
        """Update FPA temperature display"""
        # For now, just show in status message
        # Can be enhanced later with dedicated display
        pass

# ============================================================================
# Camera Manager Dialog
# ============================================================================

class CameraManagerDialog(QDialog):
    """Dialog to manage camera assignments."""
    def __init__(self, app, parent=None):
        super().__init__(parent)
        self.app = app
        self.setWindowTitle("Camera Management")
        self.setModal(True)
        self.setMinimumWidth(400)
        self._init_ui()
        
    def _init_ui(self):
        layout = QVBoxLayout(self)

        # Camera Status Group
        status_group = QGroupBox("Current Assignment")
        status_layout = QGridLayout()

        status_layout.addWidget(QLabel("Thermal Camera:"), 0, 0)
        args_obj = getattr(self.app, 'args', None)
        thermal_dev = getattr(args_obj, 'thermal_device', 0) if args_obj is not None else 0
        if thermal_dev is None: thermal_dev = 0
        self.thermal_label = QLabel(f"Device {thermal_dev}")
        status_layout.addWidget(self.thermal_label, 0, 1)

        status_layout.addWidget(QLabel("RGB Camera:"), 1, 0)
        rgb_dev = getattr(args_obj, 'rgb_device', None) if args_obj is not None else None
        self.rgb_label = QLabel(f"Device {rgb_dev if rgb_dev is not None else 'Auto'}")
        status_layout.addWidget(self.rgb_label, 1, 1)
        
        status_group.setLayout(status_layout)
        layout.addWidget(status_group)
        
        # Actions
        btn_layout = QHBoxLayout()
        
        self.redetect_btn = QPushButton("🔍 Re-Detect Cameras")
        self.redetect_btn.clicked.connect(self._on_redetect)
        self.redetect_btn.setToolTip("Stop capture and re-detect available cameras")
        btn_layout.addWidget(self.redetect_btn)

        self.swap_btn = QPushButton("Swap Cameras")
        self.swap_btn.clicked.connect(self._on_swap)
        self.swap_btn.setToolTip("Swap Thermal and RGB camera sources")
        btn_layout.addWidget(self.swap_btn)
        
        layout.addLayout(btn_layout)
        
        # Manual Assignment Group
        manual_group = QGroupBox("Manual Assignment")
        manual_layout = QGridLayout()
        
        manual_layout.addWidget(QLabel("Thermal Device ID:"), 0, 0)
        self.thermal_spin = QSpinBox()
        self.thermal_spin.setRange(0, 10)
        args_obj = getattr(self.app, 'args', None)
        thermal_dev = getattr(args_obj, 'thermal_device', 0) if args_obj is not None else 0
        if thermal_dev is None: thermal_dev = 0
        self.thermal_spin.setValue(thermal_dev)
        manual_layout.addWidget(self.thermal_spin, 0, 1)

        manual_layout.addWidget(QLabel("RGB Device ID:"), 1, 0)
        self.rgb_spin = QSpinBox()
        self.rgb_spin.setRange(0, 10)
        val = getattr(args_obj, 'rgb_device', 0) if args_obj is not None else 0
        if val is None: val = 0
        self.rgb_spin.setValue(val)
        manual_layout.addWidget(self.rgb_spin, 1, 1)
        
        self.apply_btn = QPushButton("Apply Assignment")
        self.apply_btn.clicked.connect(self._on_apply)
        manual_layout.addWidget(self.apply_btn, 2, 0, 1, 2)
        
        manual_group.setLayout(manual_layout)
        layout.addWidget(manual_group)
        
        # Close
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)
        
    def _on_swap(self):
        if QMessageBox.question(self, "Confirm Swap", 
                              "This will stop capture, swap cameras, and restart.\nContinue?",
                              QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            
            self.app.swap_cameras()
            self._update_labels()
            QMessageBox.information(self, "Success", "Cameras swapped successfully.")
            
    def _on_redetect(self):
        """Re-detect cameras and reassign"""
        if QMessageBox.question(self, "Confirm Re-Detection", 
                              "This will stop capture, detect cameras, and restart.\nContinue?",
                              QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            
            try:
                # Import auto-detection
                from camera_factory import autodetect_camera_types
                
                # Run auto-detection
                logger.info("Re-detecting cameras...")
                t_id, r_id = autodetect_camera_types()
                
                if t_id is None and r_id is None:
                    QMessageBox.warning(self, "Detection Failed", 
                                      "No cameras detected. Please check connections.")
                    return
                
                # Use detected IDs or fallback
                thermal_id = t_id if t_id is not None else 1
                rgb_id = r_id if r_id is not None else 0
                
                logger.info(f"Re-detection results: Thermal={thermal_id}, RGB={rgb_id}")
                
                # Reassign cameras
                self.app.reassign_cameras(thermal_id, rgb_id)
                
                # Update spinboxes
                self.thermal_spin.setValue(thermal_id)
                self.rgb_spin.setValue(rgb_id)
                
                self._update_labels()
                QMessageBox.information(self, "Success", 
                                      f"Cameras re-detected and assigned:\nThermal: Device {thermal_id}\nRGB: Device {rgb_id}")
                
            except Exception as e:
                logger.error(f"Re-detection failed: {e}")
                QMessageBox.critical(self, "Error", f"Re-detection failed: {e}")
    
    def _on_apply(self):
        t_id = self.thermal_spin.value()
        r_id = self.rgb_spin.value()
        
        if t_id == r_id:
            QMessageBox.warning(self, "Invalid Assignment", "Thermal and RGB cameras cannot share the same device ID.")
            return

        if QMessageBox.question(self, "Confirm Assignment", 
                              f"Reassign cameras?\nThermal: {t_id}\nRGB: {r_id}",
                              QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            
            self.app.reassign_cameras(t_id, r_id)
            self._update_labels()
            QMessageBox.information(self, "Success", "Cameras reassigned successfully.")

    def _update_labels(self):
        args_obj = getattr(self.app, 'args', None)
        thermal_dev = getattr(args_obj, 'thermal_device', 0) if args_obj is not None else 0
        if thermal_dev is None: thermal_dev = 0
        self.thermal_label.setText(f"Device {thermal_dev}")
        rgb_dev = getattr(args_obj, 'rgb_device', None) if args_obj is not None else None
        self.rgb_label.setText(f"Device {rgb_dev if rgb_dev is not None else 'Auto'}")
        self.thermal_spin.setValue(thermal_dev)
        val = rgb_dev if rgb_dev is not None else 0
        self.rgb_spin.setValue(val)


class InspectionAppWindow(QMainWindow):
    """
    Main inspection application window.
    Replaces DriverAppWindow with inspection-focused UI.
    """

    def __init__(self, app_instance=None):
        super().__init__()
        self.app = app_instance

        # Window setup
        self.setWindowTitle("Thermal Inspection Fusion Tool v2.0")
        self.setMinimumSize(1280, 720)
        
        # Add status bar
        self.statusBar().showMessage("Developer Mode: ON (Press Ctrl+D to toggle panels)", 8000)

        # State
        self.current_theme = "dark"
        self.developer_mode = True
        self.recording = False
        self.frozen = False

        # Connection tracking for defensive pattern
        self._connected_signals = set()

        # Measurement points for spot metering
        self.measurement_points: List[MeasurementPoint] = []

        # Build UI
        self._build_ui()

        # Apply initial theme
        self._apply_theme(self.current_theme)

        # Force layout update after startup to ensure panels are visible
        QTimer.singleShot(500, self._force_layout_update)

    def _force_layout_update(self):
        """Force layout update and visibility check."""
        self.right_panel_tabs.setVisible(True)
        self.control_panel.setVisible(True)
        
        # Log geometry and visibility
        logger.info(f"Window geometry: {self.geometry()}")
        logger.info(f"Right panel visible: {self.right_panel_tabs.isVisible()}")
        logger.info(f"Right panel geometry: {self.right_panel_tabs.geometry()}")
        logger.info(f"Right panel size hint: {self.right_panel_tabs.sizeHint()}")
        logger.info(f"Control panel visible: {self.control_panel.isVisible()}")
        logger.info(f"Control panel geometry: {self.control_panel.geometry()}")
        
        # Check if tabs have content
        logger.info(f"Tab count: {self.right_panel_tabs.count()}")
        for i in range(self.right_panel_tabs.count()):
            # Safe logging avoiding unicode errors on Windows consoles
            try:
                text = self.right_panel_tabs.tabText(i)
                safe_text = text.encode('ascii', 'replace').decode('ascii')
                logger.debug(f"Tab {i}: {safe_text}")
            except Exception:
                pass
            
        # Trigger a slight resize to force layout recalculation
        self.resize(self.width() + 1, self.height())
        self.resize(self.width() - 1, self.height())
        logger.info("Forced layout update and visibility check")

    def _build_ui(self):
        """Build the main UI layout."""
        logger.info("=" * 60)
        logger.info("Building UI layout...")
        logger.info("=" * 60)
        
        try:
            # Central widget
            central = QWidget()
            central.setObjectName("central_widget")
            # Removed hardcoded style that was blocking theme switching
            self.setCentralWidget(central)
            logger.info("[OK] Central widget created")

            # Main layout container
            main_layout = QHBoxLayout(central)
            main_layout.setContentsMargins(0, 0, 0, 0)
            main_layout.setSpacing(0)
            logger.info("[OK] Main layout created")

            # Left side: Video + Controls
            left_widget = QWidget()
            left_widget.setObjectName("left_widget")
            left_layout = QVBoxLayout(left_widget)
            left_layout.setContentsMargins(0, 0, 0, 0)
            left_layout.setSpacing(0)

            # Video widget
            self.video_widget = VideoWidget()
            self.video_widget.spot_meter_clicked.connect(self._on_spot_meter_clicked)
            # Removed minimum size constraint to allow proper scaling
            left_layout.addWidget(self.video_widget, stretch=1)
            logger.info("[OK] Video widget created")

            # Control panel
            self.control_panel = ControlPanel()
            self.control_panel.setMinimumHeight(120)
            self.control_panel.setMaximumHeight(150)  # Limit control panel height
            left_layout.addWidget(self.control_panel, stretch=0)
            logger.info("[OK] Control panel created")

            main_layout.addWidget(left_widget, stretch=5)  # Increased from 3 to 5 for even more video space
            logger.info("[OK] Left widget added to main layout")

            # RIGHT PANEL TABS - THIS IS WHAT THE USER IS MISSING
            self.right_panel_tabs = QTabWidget()
            self.right_panel_tabs.setObjectName("right_panel")
            self.right_panel_tabs.setFixedWidth(630)  # Increased from 420 to 630 (50% larger)
            self.right_panel_tabs.setVisible(True)
            logger.info("[OK] Right panel tabs widget created (width=630, visible=True)")

            # === OPTIMIZED TAB STRUCTURE (5 main subtabs under Analysis) ===
            
            # Analysis tab with 5 subtabs: General, Radiometric, Per-ROI, Environmental, Isotherm
            logger.info("Creating Analysis tab...")
            self.analysis_tabs = QTabWidget()
            
            # Create General tab (just the general analysis content, no nested radiometric)
            self.analysis_panel = ThermalAnalysisPanel()
            # Only use the "General" tab, ignore the nested "Radiometric" tab
            general_content = self.analysis_panel.analysis_tabs.widget(0)
            self.analysis_tabs.addTab(general_content, "General")
            logger.info("  [OK] General analysis panel added")
            
            # Create Radiometric tab directly at top level
            from radiometric_panel import RadiometricPanel
            radiometric_tab = QWidget()
            radiometric_scroll = QScrollArea()
            radiometric_scroll.setWidgetResizable(True)
            radiometric_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            radiometric_scroll.setFrameShape(QFrame.Shape.NoFrame)
            
            radiometric_content = QWidget()
            radiometric_layout = QVBoxLayout(radiometric_content)
            radiometric_layout.setSpacing(8)
            radiometric_layout.setContentsMargins(6, 6, 6, 6)
            
            self.radiometric_panel = RadiometricPanel()
            radiometric_layout.addWidget(self.radiometric_panel)
            radiometric_layout.addStretch()
            
            radiometric_scroll.setWidget(radiometric_content)
            radiometric_tab_layout = QVBoxLayout(radiometric_tab)
            radiometric_tab_layout.setContentsMargins(0, 0, 0, 0)
            radiometric_tab_layout.addWidget(radiometric_scroll)
            
            self.analysis_tabs.addTab(radiometric_tab, "Radiometric")
            logger.info("  [OK] Radiometric panel added at top level")
            
            from roi_temperature_panel import ROITemperaturePanel
            self.roi_temp_panel = ROITemperaturePanel()
            self.analysis_tabs.addTab(self.roi_temp_panel, "Per-ROI")
            logger.info("  [OK] Per-ROI temperature panel added")
            
            from environmental_compensation_panel import EnvironmentalCompensationPanel
            self.env_comp_panel = EnvironmentalCompensationPanel()
            self.analysis_tabs.addTab(self.env_comp_panel, "Environmental")
            logger.info("  [OK] Environmental compensation panel added")
            
            from isotherm_panel import IsothermPanel
            self.isotherm_panel = IsothermPanel()
            self.analysis_tabs.addTab(self.isotherm_panel, "Isotherm")
            logger.info("  [OK] Isotherm panel added")
            
            self.right_panel_tabs.addTab(self.analysis_tabs, "📊 Analysis")
            logger.info("[OK] Analysis tab added to right panel")
            
            # Tab 2: Detection & Anomaly
            logger.info("Creating Detection tab...")
            self.combined_anomaly_widget = CombinedAnomalyWidget()
            self.right_panel_tabs.addTab(self.combined_anomaly_widget, "🔍 Detection")
            self.anomaly_widget = self.combined_anomaly_widget.automatic_widget
            self.manual_threshold_widget = self.combined_anomaly_widget.manual_widget
            logger.info("[OK] Detection tab added to right panel")
            
            # Tab 3: Cameras (Hardware & Calibration - 5 subtabs)
            logger.info("Creating Cameras tab...")
            self.cameras_tabs = QTabWidget()
            
            self.boson_panel = BosonControlPanel()
            self.cameras_tabs.addTab(self.boson_panel, "Boson")
            logger.info("  [OK] Boson panel added")
            
            self.firefly_panel = FireflyControlPanel()
            self.cameras_tabs.addTab(self.firefly_panel, "Firefly")
            logger.info("  [OK] Firefly panel added")

            from lepton_control_panel import LeptonControlPanel
            self.lepton_panel = LeptonControlPanel()
            self.cameras_tabs.addTab(self.lepton_panel, "Lepton")
            logger.info("  [OK] Lepton panel added")
            
            from calibration_panel import CalibrationPanel
            self.calibration_panel = CalibrationPanel()
            self.cameras_tabs.addTab(self.calibration_panel, "Calibration")
            logger.info("  [OK] Calibration panel added")
            
            self.parallax_panel = ParallaxPanel()
            self.cameras_tabs.addTab(self.parallax_panel, "Parallax")
            logger.info("  [OK] Parallax panel added")
            
            self.right_panel_tabs.addTab(self.cameras_tabs, "🎥 Cameras")
            logger.info("[OK] Cameras tab added to right panel")

            # Tab 4: Fusion (NEW)
            logger.info("Creating Fusion tab...")
            self.fusion_panel = FusionPanel()
            self.right_panel_tabs.addTab(self.fusion_panel, "🧬 Fusion")
            logger.info("[OK] Fusion tab added to right panel")

            
            # Tab 4: Settings
            logger.info("Creating Settings tab...")
            self.settings_panel = SettingsPanel()
            self.right_panel_tabs.addTab(self.settings_panel, "🛠️ Settings")
            logger.info("[OK] Settings tab added to right panel")

            # ADD RIGHT PANEL TO MAIN LAYOUT
            main_layout.addWidget(self.right_panel_tabs, stretch=0)
            
            # CRITICAL FIX: Set visibility AFTER adding to layout
            # Qt widgets can lose visibility when added to layouts
            self.right_panel_tabs.setVisible(True)
            self.right_panel_tabs.show()  # Force show
            
            logger.info("[OK] RIGHT PANEL TABS ADDED TO MAIN LAYOUT [OK]")
            logger.info(f"    Right panel tab count: {self.right_panel_tabs.count()}")
            logger.info(f"    Right panel visible: {self.right_panel_tabs.isVisible()}")
            logger.info(f"    Right panel width: {self.right_panel_tabs.width()}")

            # Signals from analysis panel
            self.analysis_panel.show_hot_spots_toggled.connect(self._on_show_hot_spots_toggled)
            self.analysis_panel.show_cold_spots_toggled.connect(self._on_show_cold_spots_toggled)
            self.analysis_panel.show_anomalies_toggled.connect(self._on_show_anomalies_toggled)

            # Info panel (overlay on video widget)
            self.info_panel = InfoPanel(self.video_widget)
            self.info_panel.move(10, 10)
            logger.info("[OK] Info panel created")

            # Connect signals
            self._connect_signals()
            
            logger.info("=" * 60)
            logger.info("[OK] UI LAYOUT BUILD COMPLETE [OK]")
            logger.info("=" * 60)
            
        except Exception as e:
            logger.error(f"ERROR during UI build: {e}", exc_info=True)
            raise

    def _safe_connect(self, source_path: str, signal_name: str, handler, context: str = ""):
        """
        Safely connect a signal to a handler with defensive checks.
        
        ENHANCED with handler validation and duplicate detection.

        Args:
            source_path: Dot-separated path to the panel (e.g., "radiometric_panel.enable_checkbox")
            signal_name: Name of the signal (e.g., "stateChanged")
            handler: Handler method to connect
            context: Optional context description for logging

        Returns:
            bool: True if connection succeeded, False otherwise
        """
        try:
            # Get handler name for logging
            handler_name = handler.__name__ if hasattr(handler, '__name__') else str(handler)
            
            # 1. ENHANCED: Validate handler exists and is callable
            if not callable(handler):
                logger.error(f"⚠️ Handler not callable: {handler_name} for {source_path}.{signal_name} {context}")
                return False
            
            # 2. ENHANCED: Check if handler method exists on self
            if hasattr(handler, '__self__') and handler.__self__ is self:
                if not hasattr(self, handler_name):
                    logger.error(f"⚠️ MISSING HANDLER METHOD: {handler_name} for {source_path}.{signal_name} {context}")
                    logger.error(f"   This method needs to be defined in InspectionAppWindow")
                    return False
            
            # 3. Navigate the path to find the source object
            parts = source_path.split('.')
            obj = self

            for part in parts:
                if not hasattr(obj, part):
                    logger.warning(f"Signal connection skipped: {source_path}.{signal_name} - '{part}' not found {context}")
                    return False
                obj = getattr(obj, part)

            # 4. Check if signal exists
            if not hasattr(obj, signal_name):
                logger.warning(f"Signal connection skipped: {source_path}.{signal_name} - signal not found {context}")
                return False

            # 5. ENHANCED: Check for duplicate connections
            connection_key = f"{source_path}.{signal_name} -> {handler_name}"
            
            if connection_key in self._connected_signals:
                logger.warning(f"⚠️ DUPLICATE CONNECTION SKIPPED: {connection_key} {context}")
                return False
            
            # 6. Connect the signal
            signal = getattr(obj, signal_name)
            signal.connect(handler)
            
            # 7. Track the connection
            self._connected_signals.add(connection_key)
            logger.debug(f"✓ Connected: {connection_key} {context}")
            return True

        except Exception as e:
            handler_name = handler.__name__ if hasattr(handler, '__name__') else str(handler)
            logger.error(f"⚠️ Connection failed: {source_path}.{signal_name} -> {handler_name}: {e} {context}")
            import traceback
            logger.debug(traceback.format_exc())
            return False

    def _on_radiometric_backend_changed(self, backend_text: str):
        """
        Handle backend switch requests relative to 16-bit radiometric mode.
        Maps GUI dropdown text to internal backend IDs ('flirpy' or 'opencv').
        """
        # Map GUI string to backend ID
        if "Flirpy" in backend_text:
            backend_id = "flirpy"
        else:
            backend_id = "opencv"

        logger.info(f"Radiometric backend switch requested: {backend_text} -> {backend_id}")
        
        if self.app:
            self.app.switch_thermal_backend(backend_id)
        else:
            logger.warning("Backend switch requested but no app instance available")

    def _on_radiometric_max_cold_spots_changed(self, count: int):
        """Handle change in max cold spots."""
        if self.app and hasattr(self.app, 'thermal_analyzer'):
            self.app.thermal_analyzer.max_cold_spots = count
            logger.info(f"Max cold spots set to: {count}")

    def _on_radiometric_max_hot_spots_changed(self, count: int):
        """Handle change in max hot spots."""
        if self.app and hasattr(self.app, 'thermal_analyzer'):
            self.app.thermal_analyzer.max_hot_spots = count
            logger.info(f"Max hot spots set to: {count}")
    
    def _on_show_hot_spots_toggled(self, enabled: bool):
        """Handle hot spots display toggle."""
        if self.app and hasattr(self.app, 'thermal_analyzer'):
            # Assuming thermal_analyzer has show_hot_spots
            pass
    
    def _on_show_cold_spots_toggled(self, enabled: bool):
        """Handle cold spots display toggle."""
        if self.app and hasattr(self.app, 'thermal_analyzer'):
            pass

    def _on_show_anomalies_toggled(self, enabled: bool):
        """Handle anomalies display toggle."""
        if self.app and hasattr(self.app, 'thermal_analyzer'):
            pass
    
    def _on_radiometric_enable_changed(self, enabled: bool):
        """Handle radiometric mode toggle."""
        pass

    def _on_radiometric_range_apply(self):
        """Handle manual range apply."""
        pass

    def _on_load_lut(self):
        """load color look up table"""
        pass

    def _on_radiometric_method_changed(self):
        """method changed"""
        pass
    
    def _on_spotmeter_enabled_changed(self, enabled: bool):
        """spotmeter"""
        pass

    def _on_spotmeter_mode_changed(self, mode: str):
        """mode"""
        pass

    def _on_sensor_temps_requested(self):
        """sensor temps"""
        pass

    def _on_8bit_estimation_toggled(self, enabled: bool):
        """8bit est"""
        pass

    def _on_temperature_range_changed(self, low: float, high: float):
        """temp range"""
        pass

    def _on_calibrate_single_point(self, temp: float):
        """calib single"""
        pass

    def _on_calibrate_two_point(self, t1: float, t2: float):
        """calib two"""
        pass

    def _on_radiometric_temp_unit_changed(self, unit: str):
        """unit changed"""
        pass

    # === FUSION HANDLERS ===
    def _on_fusion_mode_changed(self, mode: str):
        pass
    def _on_fusion_alpha_changed(self, val: float):
        pass
    def _on_fusion_priority_changed(self, val: str):
        pass
    def _on_fusion_strength_changed(self, val: float):
        pass
    def _on_fusion_fuzziness_changed(self, val: float):
        pass
    def _on_fusion_color_mode_changed(self, val: str):
        pass
    def _on_edge_strength_changed(self, val: float):
        pass
    def _on_edge_fuzziness_changed(self, val: float):
        pass
    def _on_edge_color_changed(self, val: str):
        pass
    def _on_detail_strength_changed(self, val: float):
        pass
    def _on_detail_quality_changed(self, val: str):
        pass

    # === ANALYSIS HANDLERS ===
    def _on_global_palette_changed(self, val: str):
        pass
    def _on_roi_palette_changed(self, id: str, val: str):
        pass
    def _on_roi_palette_cleared(self, id: str):
        pass
    def _on_overlay_info_toggle(self, enabled: bool):
        pass

    # === ENVIRONMENTAL COMP HANDLERS ===
    def _on_emissivity_changed(self, val: float):
        pass
    def _on_atmospheric_temp_changed(self, val: float):
        pass
    def _on_atmospheric_transmission_changed(self, val: float):
        pass

    # === ISOTHERM HANDLERS ===
    def _on_isotherm_enabled_changed(self, enabled: bool):
        pass
    def _on_isotherm_mode_changed(self, mode: str):
        pass
    def _on_isotherm_low_threshold_changed(self, val: float):
        pass
    def _on_isotherm_high_threshold_changed(self, val: float):
        pass
    def _on_isotherm_color_changed(self, val: str):
        pass

    # === ROI & VIDEO HANDLERS ===
    def _on_roi_created(self, roi_data):
        pass
    def _on_roi_selected(self, roi_id):
        pass
    def _on_cursor_moved(self, pos):
        pass

    # === SPOT METER HANDLERS ===
    def _on_spot_meter_toggled(self, enabled: bool):
        """Handle toggle of spot meter add mode."""
        if hasattr(self.video_widget, 'overlay'):
            self.video_widget.overlay.set_spot_meter_mode(enabled)
            # Update cursor
            if enabled:
                self.video_widget.setCursor(Qt.CursorShape.CrossCursor)
            else:
                self.video_widget.setCursor(Qt.CursorShape.ArrowCursor)
        logger.info(f"Spot meter mode: {enabled}")

    def _on_clear_spots_clicked(self):
        """Clear all spot meters."""
        self.measurement_points.clear()
        if hasattr(self.video_widget, 'overlay'):
            self.video_widget.overlay.update_measurement_points([])
        logger.info("Cleared all spot meters")

    def _on_spot_meter_clicked(self, x, y):
        """Handle click to add spot meter."""
        try:
            # Ensure coordinates are integers
            x, y = int(x), int(y)
            count = len(self.measurement_points) + 1
            
            # Create a simple measurement point
            # Note: Temperature will be updated in the main update loop (update_thermal_data)
            point = MeasurementPoint(
                x=x, 
                y=y, 
                label=f"S{count}",
                color=(255, 255, 0) # Cyan/Yellow
            )
            
            self.measurement_points.append(point)
            
            # Update overlay
            if hasattr(self.video_widget, 'overlay'):
                self.video_widget.overlay.update_measurement_points(self.measurement_points)
                
                # Turn off toggle after adding one point (optional user preference)
                # self.control_panel.spot_meter_btn.setChecked(False)
                
            logger.info(f"Added spot meter at ({x}, {y})")
            
        except Exception as e:
            logger.error(f"Error adding spot meter: {e}")
    
    # === BASELINE HANDLER ===
    def _on_baseline_toggle(self, enabled: bool):
        pass

    def _connect_signals(self):
        """Connect control panel signals to handlers using defensive pattern."""
        logger.info("Connecting signals with defensive checks...")
        
        # === CRITICAL CONTROLS (Always present) ===
        # These should always exist, but we'll still use defensive connections
        self._safe_connect("control_panel", "view_mode_clicked", self._on_view_mode_cycle, "(critical control)")
        self._safe_connect("control_panel", "day_night_clicked", self._on_theme_cycle, "(critical control)")
        self._safe_connect("control_panel", "record_toggled", self._on_record_toggle, "(critical control)")
        self._safe_connect("control_panel", "snapshot_clicked", self._on_snapshot, "(critical control)")
        self._safe_connect("control_panel", "freeze_frame_toggled", self._on_freeze_toggle, "(critical control)")
        self._safe_connect("control_panel", "auto_roi_clicked", self._on_auto_roi, "(critical control)")
        self._safe_connect("control_panel", "draw_roi_clicked", self._on_draw_roi, "(critical control)")
        self._safe_connect("control_panel", "clear_rois_clicked", self._on_clear_rois, "(critical control)")
        self._safe_connect("control_panel", "camera_clicked", self._on_camera_clicked, "(critical control)")

        # === SETTINGS PANEL ===
        self._safe_connect("settings_panel", "device_changed", self._on_device_changed, "(settings)")
        self._safe_connect("settings_panel", "backend_changed", self._on_radiometric_backend_changed, "(settings)")
        self._safe_connect("settings_panel", "theme_changed", self._on_theme_changed, "(settings)")
        self._safe_connect("settings_panel", "baseline_lock_toggled", self._on_baseline_toggle, "(settings)")
        # Fusion signals moved to FusionPanel


        # === FUSION PANEL ===
        self._safe_connect("fusion_panel", "fusion_mode_changed", self._on_fusion_mode_changed, "(fusion)")
        self._safe_connect("fusion_panel", "fusion_alpha_changed", self._on_fusion_alpha_changed, "(fusion)")
        self._safe_connect("fusion_panel", "fusion_priority_changed", self._on_fusion_priority_changed, "(fusion)")
        self._safe_connect("fusion_panel", "fusion_strength_changed", self._on_fusion_strength_changed, "(fusion)")
        self._safe_connect("fusion_panel", "fusion_fuzziness_changed", self._on_fusion_fuzziness_changed, "(fusion)")
        self._safe_connect("fusion_panel", "fusion_color_mode_changed", self._on_fusion_color_mode_changed, "(fusion)")
        self._safe_connect("fusion_panel", "edge_strength_changed", self._on_edge_strength_changed, "(fusion)")
        self._safe_connect("fusion_panel", "edge_fuzziness_changed", self._on_edge_fuzziness_changed, "(fusion)")
        self._safe_connect("fusion_panel", "edge_color_changed", self._on_edge_color_changed, "(fusion)")
        self._safe_connect("fusion_panel", "detail_strength_changed", self._on_detail_strength_changed, "(fusion)")
        self._safe_connect("fusion_panel", "detail_quality_changed", self._on_detail_quality_changed, "(fusion)")

        # === ANALYSIS PANEL ===
        self._safe_connect("analysis_panel", "palette_changed", self._on_global_palette_changed, "(analysis)")
        self._safe_connect("analysis_panel", "roi_palette_changed", self._on_roi_palette_changed, "(analysis)")
        self._safe_connect("analysis_panel", "roi_palette_cleared", self._on_roi_palette_cleared, "(analysis)")
        self._safe_connect("analysis_panel", "overlay_info_toggled", self._on_overlay_info_toggle, "(analysis)")
        self._safe_connect("analysis_panel", "spot_meter_toggled", self._on_spot_meter_toggled, "(analysis)")
        # Handled in Signal Integration
        if hasattr(self.analysis_panel, 'clear_spots_clicked'):
             self._safe_connect("analysis_panel", "clear_spots_clicked", self._on_clear_spots_clicked, "(analysis)")

        # === ANOMALY WIDGET ===
        self._safe_connect("anomaly_widget", "anomaly_priority_toggled", self._on_anomaly_priority_toggle, "(anomaly)")
        self._safe_connect("anomaly_widget", "anomaly_types_changed", self._on_anomaly_types_changed, "(anomaly)")
        self._safe_connect("anomaly_widget", "fade_strength_changed", self._on_fade_strength_changed, "(anomaly)")
        self._safe_connect("anomaly_widget", "fade_distance_changed", self._on_fade_distance_changed, "(anomaly)")
        self._safe_connect("anomaly_widget", "motion_threshold_changed", self._on_motion_threshold_changed, "(anomaly)")
        self._safe_connect("anomaly_widget", "edge_thresholds_changed", self._on_edge_thresholds_changed, "(anomaly)")
        self._safe_connect("anomaly_widget", "hot_spot_percentile_changed", self._on_hot_spot_percentile_changed, "(anomaly)")
        self._safe_connect("anomaly_widget", "cold_spot_percentile_changed", self._on_cold_spot_percentile_changed, "(anomaly)")
        self._safe_connect("anomaly_widget", "min_anomaly_size_changed", self._on_min_anomaly_size_changed, "(anomaly)")

        # === MANUAL THRESHOLD WIDGET ===
        self._safe_connect("manual_threshold_widget", "enabled_changed", self._on_manual_threshold_enabled, "(manual threshold)")
        self._safe_connect("manual_threshold_widget", "threshold_mode_changed", self._on_manual_threshold_mode_changed, "(manual threshold)")
        self._safe_connect("manual_threshold_widget", "min_threshold_changed", self._on_manual_min_threshold_changed, "(manual threshold)")
        self._safe_connect("manual_threshold_widget", "max_threshold_changed", self._on_manual_max_threshold_changed, "(manual threshold)")
        self._safe_connect("manual_threshold_widget", "use_raw_values_changed", self._on_manual_use_raw_changed, "(manual threshold)")
        self._safe_connect("manual_threshold_widget", "visualization_mode_changed", self._on_manual_viz_mode_changed, "(manual threshold)")

        # === BOSON SDK PANEL ===
        self._safe_connect("boson_panel", "sdk_connect_requested", self._on_boson_connect, "(boson)")
        self._safe_connect("boson_panel", "sdk_disconnect_requested", self._on_boson_disconnect, "(boson)")
        self._safe_connect("boson_panel", "ffc_triggered", self._on_boson_ffc, "(boson)")
        self._safe_connect("boson_panel", "sdk_scan_ports_requested", self._on_boson_scan_ports, "(boson)")
        self._safe_connect("boson_panel", "gain_mode_changed", self._on_boson_gain_mode, "(boson)")
        self._safe_connect("boson_panel", "ffc_mode_changed", self._on_boson_ffc_mode, "(boson)")
        self._safe_connect("boson_panel", "color_lut_changed", self._on_boson_color_lut, "(boson)")
        self._safe_connect("boson_panel", "agc_max_gain_changed", self._on_agc_max_gain_changed, "(boson AGC)")
        self._safe_connect("boson_panel", "agc_gamma_changed", self._on_agc_gamma_changed, "(boson AGC)")
        self._safe_connect("boson_panel", "agc_linearity_changed", self._on_agc_linearity_changed, "(boson AGC)")
        self._safe_connect("boson_panel", "agc_dde_changed", self._on_agc_dde_changed, "(boson AGC)")
        self._safe_connect("boson_panel", "agc_plateau_changed", self._on_agc_plateau_changed, "(boson AGC)")
        self._safe_connect("boson_panel", "agc_dampening_changed", self._on_agc_dampening_changed, "(boson AGC)")
        self._safe_connect("boson_panel", "agc_reset_requested", self._on_agc_reset, "(boson AGC)")
        self._safe_connect("boson_panel", "shutter_position_changed", self._on_shutter_position_changed, "(boson shutter)")
        self._safe_connect("boson_panel", "radiometric_mode_changed", self._on_radiometric_mode_changed, "(boson radiometric)")

        # === FIREFLY CAMERA PANEL ===
        self._safe_connect("firefly_panel", "exposure_mode_changed", self._on_firefly_exposure_mode, "(firefly)")
        self._safe_connect("firefly_panel", "exposure_time_changed", self._on_firefly_exposure_time, "(firefly)")
        self._safe_connect("firefly_panel", "gain_mode_changed", self._on_firefly_gain_mode, "(firefly)")
        self._safe_connect("firefly_panel", "gain_changed", self._on_firefly_gain, "(firefly)")
        self._safe_connect("firefly_panel", "white_balance_mode_changed", self._on_firefly_white_balance_mode, "(firefly)")
        self._safe_connect("firefly_panel", "white_balance_calibrate", self._on_firefly_white_balance_calibrate, "(firefly)")
        self._safe_connect("firefly_panel", "white_balance_ratio_changed", self._on_firefly_white_balance_ratio, "(firefly)")
        self._safe_connect("firefly_panel", "trigger_mode_changed", self._on_firefly_trigger_mode, "(firefly)")
        self._safe_connect("firefly_panel", "trigger_fire", self._on_firefly_trigger_fire, "(firefly)")
        self._safe_connect("firefly_panel", "gamma_changed", self._on_firefly_gamma, "(firefly)")
        self._safe_connect("firefly_panel", "sharpness_changed", self._on_firefly_sharpness, "(firefly)")

        # === CALIBRATION PANEL ===
        self._safe_connect("calibration_panel", "add_calibration_point_clicked", self._on_calibration_add_point_mode, "(calibration)")
        self._safe_connect("calibration_panel", "compute_calibration_clicked", self._on_compute_calibration, "(calibration)")
        self._safe_connect("calibration_panel", "apply_calibration_toggled", self._on_apply_calibration_toggled, "(calibration)")
        self._safe_connect("calibration_panel", "clear_calibration_clicked", self._on_clear_calibration, "(calibration)")
        self._safe_connect("calibration_panel", "export_calibration_clicked", self._on_export_calibration, "(calibration)")
        self._safe_connect("calibration_panel", "import_calibration_clicked", self._on_import_calibration, "(calibration)")
        self._safe_connect("calibration_panel", "remove_point_clicked", self._on_remove_calibration_point, "(calibration)")

        # === RADIOMETRIC PANEL (nested widget) ===
        self._safe_connect("radiometric_panel.enable_checkbox", "stateChanged", self._on_radiometric_enable_changed, "(radiometric)")
        self._safe_connect("radiometric_panel.apply_range_btn", "clicked", self._on_radiometric_range_apply, "(radiometric)")
        self._safe_connect("radiometric_panel.load_lut_btn", "clicked", self._on_load_lut, "(radiometric)")
        self._safe_connect("radiometric_panel.method_linear_radio", "toggled", self._on_radiometric_method_changed, "(radiometric)")
        self._safe_connect("radiometric_panel.method_lut_radio", "toggled", self._on_radiometric_method_changed, "(radiometric)")

        # === RADIOMETRIC PANEL (spotmeter signals - for 16-bit radiometric) ===
        self._safe_connect("radiometric_panel", "spotmeter_enabled_changed", self._on_spotmeter_enabled_changed, "(radiometric spotmeter)")
        self._safe_connect("radiometric_panel", "spotmeter_mode_changed", self._on_spotmeter_mode_changed, "(radiometric spotmeter)")
        self._safe_connect("radiometric_panel", "sensor_temps_requested", self._on_sensor_temps_requested, "(radiometric spotmeter)")

        # === PARALLAX PANEL ===
        self._safe_connect("parallax_panel", "parallax_toggled", self._on_parallax_toggled, "(parallax)")
        self._safe_connect("parallax_panel", "baseline_changed", self._on_parallax_baseline_changed, "(parallax)")
        self._safe_connect("parallax_panel", "depth_method_changed", self._on_parallax_method_changed, "(parallax)")
        self._safe_connect("parallax_panel.apply_geometry_btn", "clicked", self._on_parallax_geometry_apply, "(parallax)")

        # === RADIOMETRIC PANEL (8-Bit Estimation) ===
        self._safe_connect("radiometric_panel", "estimation_8bit_enabled_changed", self._on_8bit_estimation_toggled, "(radiometric 8-bit)")
        self._safe_connect("radiometric_panel", "temperature_range_changed", self._on_temperature_range_changed, "(radiometric 8-bit)")
        self._safe_connect("radiometric_panel", "calibrate_single_point_requested", self._on_calibrate_single_point, "(radiometric 8-bit)")
        self._safe_connect("radiometric_panel", "calibrate_two_point_requested", self._on_calibrate_two_point, "(radiometric 8-bit)")
        
        # === RADIOMETRIC PANEL (Temperature Unit & Detection Settings) ===
        self._safe_connect("radiometric_panel", "temperature_unit_changed", self._on_radiometric_temp_unit_changed, "(radiometric unit)")
        self._safe_connect("radiometric_panel", "max_hot_spots_changed", self._on_radiometric_max_hot_spots_changed, "(radiometric spots)")
        self._safe_connect("radiometric_panel", "max_cold_spots_changed", self._on_radiometric_max_cold_spots_changed, "(radiometric spots)")
        self._safe_connect("radiometric_panel", "backend_changed", self._on_radiometric_backend_changed, "(radiometric backend)")

        # === GENERAL ANALYSIS PANEL (Detection Toggles) ===
        self._safe_connect("analysis_panel.show_hot_spots_checkbox", "toggled", self._on_show_hot_spots_toggled, "(detection toggle)")
        self._safe_connect("analysis_panel.show_cold_spots_checkbox", "toggled", self._on_show_cold_spots_toggled, "(detection toggle)")
        self._safe_connect("analysis_panel.show_anomalies_checkbox", "toggled", self._on_show_anomalies_toggled, "(detection toggle)")

        # === ENVIRONMENTAL COMPENSATION PANEL ===
        self._safe_connect("env_comp_panel", "emissivity_changed", self._on_emissivity_changed, "(environmental)")
        self._safe_connect("env_comp_panel", "atmospheric_temp_changed", self._on_atmospheric_temp_changed, "(environmental)")
        self._safe_connect("env_comp_panel", "atmospheric_transmission_changed", self._on_atmospheric_transmission_changed, "(environmental)")

        # === ISOTHERM PANEL ===
        self._safe_connect("isotherm_panel", "enabled_changed", self._on_isotherm_enabled_changed, "(isotherm)")
        self._safe_connect("isotherm_panel", "mode_changed", self._on_isotherm_mode_changed, "(isotherm)")
        self._safe_connect("isotherm_panel", "low_threshold_changed", self._on_isotherm_low_threshold_changed, "(isotherm)")
        self._safe_connect("isotherm_panel", "high_threshold_changed", self._on_isotherm_high_threshold_changed, "(isotherm)")
        self._safe_connect("isotherm_panel", "color_changed", self._on_isotherm_color_changed, "(isotherm)")

        # === ROI OVERLAY (nested widget) ===
        self._safe_connect("video_widget.overlay", "roi_created", self._on_roi_created, "(roi overlay)")
        self._safe_connect("video_widget.overlay", "roi_selected", self._on_roi_selected, "(roi overlay)")

        # === VIDEO WIDGET ===
        self._safe_connect("video_widget", "cursor_moved", self._on_cursor_moved, "(video)")

        # === SPOT METER SIGNALS ===
        self._safe_connect("radiometric_panel", "spot_meter_toggled", self._on_spot_meter_toggled, "(spot meter)")
        self._safe_connect("radiometric_panel", "clear_spot_meters_requested", self._on_clear_spots_clicked, "(spot meter)")
        self._safe_connect("video_widget.overlay", "spot_meter_clicked", self._on_spot_meter_clicked, "(spot meter)")
        
        logger.info("[OK] Signal connections complete (defensive mode)")

        # === INITIALIZE BOSON PANEL IF SDK ALREADY CONNECTED ===
        # The SDK may auto-connect during startup (--enable-boson-sdk flag)
        # In that case, the camera info is retrieved but the panel is never updated
        # because the panel update code only runs when user manually clicks "Connect"
        # This code checks if SDK is already connected and updates the panel
        try:
            if self.app and hasattr(self.app, 'thermal_camera'):
                thermal_cam = self.app.thermal_camera
                # Check if SDK is connected
                if hasattr(thermal_cam, 'sdk_connected') and thermal_cam.sdk_connected:
                    logger.info("[BOSON INIT] SDK already connected, updating panel...")

                    # Update connection status
                    self.boson_panel.update_connection_status(True)

                    # Get and display camera info
                    if hasattr(thermal_cam, 'get_camera_info'):
                        info = thermal_cam.get_camera_info()
                        if info:
                            self.boson_panel.set_status(f"SN: {info.serial_number}")
                            self.boson_panel.update_camera_info(info)
                            logger.info(f"[BOSON INIT] Panel updated with camera info (SN: {info.serial_number})")
                        else:
                            logger.warning("[BOSON INIT] SDK connected but get_camera_info() returned None")
                    else:
                        logger.warning("[BOSON INIT] thermal_camera does not have get_camera_info() method")
                else:
                    logger.info("[BOSON INIT] SDK not connected yet")
            else:
                logger.info("[BOSON INIT] App or thermal_camera not available yet")
        except Exception as e:
            logger.error(f"[BOSON INIT] Error initializing Boson panel: {e}", exc_info=True)

    def keyPressEvent(self, event):
        """Handle keyboard shortcuts."""
        key = event.key()
        modifiers = event.modifiers()

        # Ctrl+D: Toggle developer mode
        if key == Qt.Key.Key_D and modifiers == Qt.KeyboardModifier.ControlModifier:
            self._toggle_developer_mode()
        # Q/Esc: Quit
        elif key in (Qt.Key.Key_Q, Qt.Key.Key_Escape):
            self.close()
        # V: Cycle view mode
        elif key == Qt.Key.Key_V:
            self._on_view_mode_cycle()
        # C: Cycle palette
        elif key == Qt.Key.Key_C:
            self._on_palette_cycle()
        # T: Cycle theme
        elif key == Qt.Key.Key_T:
            self._on_theme_cycle()
        # R: Record toggle
        elif key == Qt.Key.Key_R:
            self.control_panel.record_btn.setChecked(not self.recording)
        # S: Snapshot
        elif key == Qt.Key.Key_S:
            self._on_snapshot()
        # Space: Freeze toggle
        elif key == Qt.Key.Key_Space:
            self.control_panel.freeze_btn.setChecked(not self.frozen)
        # A: Auto ROI
        elif key == Qt.Key.Key_A:
            self._on_auto_roi()
        else:
            super().keyPressEvent(event)

    def _toggle_developer_mode(self):
        """Toggle developer mode (show/hide advanced controls and analysis panel)."""
        self.developer_mode = not self.developer_mode
        self.control_panel.show_developer_controls(self.developer_mode)
        self.right_panel_tabs.setVisible(self.developer_mode)

        # Adjust window size
        if self.developer_mode:
            self.resize(self.width() + 350, self.height())
        else:
            self.resize(self.width() - 350, self.height())

        # Show prominent message
        mode_text = "ON" if self.developer_mode else "OFF"
        logger.warning(f"********** DEVELOPER MODE: {mode_text} **********")
        if hasattr(self, 'statusBar'):
            self.statusBar().showMessage(f"Developer Mode: {mode_text} (Press Ctrl+D to toggle)", 5000)

    def _on_theme_changed(self, theme: str):
        """Handle theme change from settings."""
        self._apply_theme(theme)

    def _apply_theme(self, theme: str):
        """Apply color theme."""
        self.current_theme = theme

        # Determine actual theme to apply
        actual_theme = theme
        if theme == "auto":
            # Auto mode: Use system time or config settings
            import datetime
            hour = datetime.datetime.now().hour
            # Day mode: 7 AM - 7 PM, Night mode: 7 PM - 7 AM
            actual_theme = "Light Mode" if 7 <= hour < 19 else "Dark Mode"

        # Apply theme from dictionary
        if actual_theme in THEMES:
            self.setStyleSheet(THEMES[actual_theme])
        elif actual_theme == "light": # Legacy fallback
            self.setStyleSheet(THEMES.get("Light Mode", LIGHT_THEME))
        elif actual_theme == "dark": # Legacy fallback
            self.setStyleSheet(THEMES.get("Dark Mode", DARK_THEME))
        else:
            logger.warning(f"Unknown theme: {actual_theme}")

        # Update button to show current mode (if control panel exists)
        if hasattr(self, 'control_panel'):
            if theme == "auto":
                self.control_panel.update_theme_button(f"auto ({actual_theme})")
            else:
                self.control_panel.update_theme_button(theme)

    def _on_theme_cycle(self):
        """Cycle through themes."""
        # Use keys from THEMES dictionary plus 'auto'
        # Ensure consistent ordering
        themes = list(THEMES.keys()) + ["auto"]
        
        # Handle legacy or mismatched current theme
        current = self.current_theme
        if current not in themes:
            # Try to map legacy names
            if current == "light": current = "Light Mode"
            elif current == "dark": current = "Dark Mode"
            elif current == "colorful": current = "Colorful"
            elif current == "solarized": current = "Solarized"
            
        current_idx = themes.index(current) if current in themes else 0
        next_theme = themes[(current_idx + 1) % len(themes)]
        self._apply_theme(next_theme)
        logger.info(f"Theme: {next_theme}")

    def _on_palette_cycle(self):
        """Cycle through palettes."""
        if self.app:
            self.app.cycle_palette()
        logger.info("Palette cycle")

    def _on_view_mode_cycle(self):
        """Cycle through view modes."""
        if self.app:
            self.app.cycle_view_mode()
        logger.info("View mode cycle")

    def _on_record_toggle(self, enabled: bool):
        """Toggle recording."""
        self.recording = enabled
        self.control_panel.update_record_button(enabled)
        if self.app:
            self.app.toggle_recording(enabled)
        logger.info(f"Recording: {'ON' if enabled else 'OFF'}")

    def _on_snapshot(self):
        """Take a snapshot."""
        if self.app:
            self.app.capture_snapshot()
        logger.info("Snapshot captured")

    def _on_freeze_toggle(self, enabled: bool):
        """Toggle frame freeze."""
        self.frozen = enabled
        self.control_panel.update_freeze_button(enabled)
        if self.app:
            self.app.toggle_freeze(enabled)
        logger.info(f"Frame freeze: {'ON' if enabled else 'OFF'}")

    def _on_auto_roi(self):
        """Trigger automatic ROI detection."""
        if self.app and hasattr(self.app, 'auto_roi_detect'):
            self.app.auto_roi_detect()
            logger.info("Auto ROI detection triggered")
        else:
            logger.warning("Auto ROI detection not available")

    def _on_draw_roi(self):
        """Enter ROI drawing mode."""
        if self.video_widget and hasattr(self.video_widget, 'overlay'):
            # Enable drawing mode on the overlay (default: rectangle)
            self.video_widget.overlay.enable_drawing_mode(ROIType.RECTANGLE)
            logger.info("Draw ROI mode activated (rectangle)")
            # Update button state
            self.control_panel.draw_roi_btn.setChecked(True)
        else:
            logger.warning("Video widget overlay not available")

    def _on_clear_rois(self):
        """Clear all ROIs."""
        if self.app:
            self.app.clear_rois()
        logger.info("ROIs cleared")

    def _on_save_rois(self):
        """Save ROIs to file."""
        filename, _ = QFileDialog.getSaveFileName(
            self, "Save ROIs", "", "JSON Files (*.json)"
        )
        if filename:
            if self.app:
                self.app.save_rois(filename)
            else:
                logger.info(f"ROIs saved to {filename}")

    def _on_load_rois(self):
        """Load ROIs from file."""
        filename, _ = QFileDialog.getOpenFileName(
            self, "Load ROIs", "", "JSON Files (*.json)"
        )
        if filename:
            if self.app:
                self.app.load_rois(filename)
            else:
                logger.info(f"ROIs loaded from {filename}")

    def _on_load_lut(self):
        """Handle load LUT button click."""
        filename, _ = QFileDialog.getOpenFileName(
            self, "Load TLinear LUT", "", "CSV Files (*.csv);;All Files (*.*)"
        )
        if filename and self.app:
            success = self.app.load_radiometric_lut(filename)
            if success:
                self.statusBar().showMessage(f"Loaded LUT from {filename}", 3000)
                logger.info(f"Loaded radiometric LUT from {filename}")
            else:
                from PyQt6.QtWidgets import QMessageBox
                QMessageBox.warning(self, "LUT Load Failed", "Could not load TLinear LUT file")

    # === 8-BIT TEMPERATURE ESTIMATION HANDLERS (NEW) ===
    
    def _on_8bit_estimation_toggled(self, enabled: bool):
        """Handle 8-bit temperature estimation enable/disable."""
        if self.app and hasattr(self.app, 'set_8bit_estimation_enabled'):
            self.app.set_8bit_estimation_enabled(enabled)
            logger.info(f"8-bit temperature estimation: {'enabled' if enabled else 'disabled'}")
            
            # Update status banner
            if hasattr(self.radiometric_panel, 'update_active_mode_status'):
                mode_info = self.app.get_active_temperature_mode()
                self.radiometric_panel.update_active_mode_status(
                    mode_info['mode'],
                    mode_info['accuracy'],
                    mode_info['description']
                )
    
    def _on_temperature_range_changed(self, min_c: float, max_c: float):
        """Handle temperature range configuration change."""
        if self.app and hasattr(self.app, 'set_temperature_range'):
            success = self.app.set_temperature_range(min_c, max_c)
            if success:
                self.statusBar().showMessage(f"Temperature range set: {min_c:.1f}°C to {max_c:.1f}°C", 2000)
                logger.info(f"Temperature range updated: {min_c:.1f}°C to {max_c:.1f}°C")
            else:
                from PyQt6.QtWidgets import QMessageBox
                QMessageBox.warning(self, "Range Error", "Failed to set temperature range")
    
    def _on_calibrate_single_point(self):
        """Handle single-point calibration request."""
        from PyQt6.QtWidgets import QInputDialog, QMessageBox
        
        # Get known temperature from user
        known_temp, ok = QInputDialog.getDouble(
            self,
            "Single-Point Calibration",
            "Enter known temperature at center point (°C):",
            25.0,  # default value
            -40.0, 550.0,  # min, max
            1  # decimals
        )
        
        if ok and self.app:
            # We pass None for agc_value to let the app use the latest frame's center pixel
            if hasattr(self.app, 'calibrate_8bit_single_point'):
                success = self.app.calibrate_8bit_single_point(known_temp)
                if success:
                    # Update calibration offset display
                    if self.app.temp_estimator and hasattr(self.radiometric_panel, 'set_calibration_offset'):
                        offset = self.app.temp_estimator.calibration_offset
                        self.radiometric_panel.set_calibration_offset(offset)

                    QMessageBox.information(
                        self,
                        "Calibration Complete",
                        f"Single-point calibration set to {known_temp:.1f}°C"
                    )
                    logger.info(f"Single-point calibration: {known_temp:.1f}°C")
                else:
                    QMessageBox.warning(self, "Calibration Failed", "Could not perform calibration")
    
    def _on_calibrate_two_point(self):
        """Handle two-point calibration request."""
        if self.app:
            self.app.calibrate_two_point()

    def _on_radiometric_temp_unit_changed(self, unit: str):
        """Handle temperature unit change from top-level radiometric panel."""
        logger.info(f"[MAIN_WINDOW] _on_radiometric_temp_unit_changed called with unit: {unit}")
        if hasattr(self, 'video_widget') and hasattr(self.video_widget, 'overlay'):
            self.video_widget.overlay.set_temperature_unit(unit)
            logger.info(f"[MAIN_WINDOW] Updated overlay to unit: {unit}")
        else:
            logger.warning("[MAIN_WINDOW] video_widget or overlay not found")
        if self.app:
            self.app.set_temperature_unit(unit)
            logger.info(f"[MAIN_WINDOW] Called app.set_temperature_unit({unit})")
        else:
            logger.warning("[MAIN_WINDOW] app not found")

    def _on_radiometric_max_hot_spots_changed(self, count: int):
        """Handle max hot spots change from top-level radiometric panel."""
        if self.app:
            self.app.set_max_hot_spots(count)
            self.video_widget.overlay.update()
            logger.info(f"Max hot spots set to: {count}")

    def _on_show_hot_spots_toggled(self, enabled: bool):
        """Handle show hot spots checkbox toggle."""
        if hasattr(self, 'video_widget') and hasattr(self.video_widget, 'overlay'):
            self.video_widget.overlay.show_hot_spots = enabled
            self.video_widget.overlay.update()
            logger.info(f"Show hot spots: {enabled}")

    def _on_show_cold_spots_toggled(self, enabled: bool):
        """Handle show cold spots checkbox toggle."""
        if hasattr(self, 'video_widget') and hasattr(self.video_widget, 'overlay'):
            self.video_widget.overlay.show_cold_spots = enabled
            self.video_widget.overlay.update()
            logger.info(f"Show cold spots: {enabled}")

    def _on_show_anomalies_toggled(self, enabled: bool):
        """Handle show anomalies checkbox toggle."""
        if hasattr(self, 'video_widget') and hasattr(self.video_widget, 'overlay'):
            self.video_widget.overlay.show_anomalies = enabled
            self.video_widget.overlay.update()
            logger.info(f"Show anomalies: {enabled}")

    def _on_emissivity_changed(self, emissivity: float):
        """Handle emissivity change."""
        if self.app:
            self.app.set_emissivity(emissivity)
        logger.info(f"Emissivity changed to: {emissivity:.2f}")

    # === SPOT METER HANDLERS (Enhancement #1) ===

    def _on_spot_meter_toggled(self, checked: bool):
        """Handle spot meter toggle button."""
        if hasattr(self, 'video_widget'):
            self.video_widget.set_add_point_mode(checked)
            msg = "Spot meter mode: ON (Click on video to measure)" if checked else "Spot meter mode: OFF"
            self.statusBar().showMessage(msg, 3000)
            logger.info(msg)

    def _on_clear_spots_clicked(self):
        """Clear all spot measurement points."""
        logger.info("Main Window: _on_clear_spots_clicked called")
        self.measurement_points.clear()
        if hasattr(self, 'video_widget'):
            self.video_widget.update_measurement_points(self.measurement_points)
        logger.info("Cleared all spot meters")

    def get_spot_meter_coords(self) -> List[Tuple[int, int, str]]:
        """Get coordinates of all active spot meters."""
        return [(p.x, p.y, p.label) for p in self.measurement_points]
    
    def update_spot_meter_values(self, values: List[Dict]):
        """
        Update temperatures for spot meters.
        
        Args:
            values: List of dicts with {'label': str, 'temperature': float, 'unit': str}
        """
        updated = False
        val_map = {v['label']: v for v in values}
        
        for point in self.measurement_points:
            if point.label in val_map:
                data = val_map[point.label]
                point.temperature = data['temperature']
                point.unit = data['unit']
                updated = True
                
        if updated and hasattr(self, 'video_widget'):
            self.video_widget.update_measurement_points(self.measurement_points)

    def _on_spot_meter_clicked(self, x: int, y: int):
        """Handle click on video to add spot measurement point."""
        logger.info(f"Main Window: _on_spot_meter_clicked at ({x}, {y})")
        # Create unique label (SP1, SP2, ...)
        idx = len(self.measurement_points) + 1
        label = f"SP{idx}"
        
        # Create point
        point = MeasurementPoint(x=x, y=y, label=label)
        self.measurement_points.append(point)
        
        # Update overlay immediately (will show -- temp until next frame update)
        if hasattr(self, 'video_widget'):
            self.video_widget.update_measurement_points(self.measurement_points)
            
        logger.info(f"Added spot meter {label} at ({x}, {y})")

    def get_spot_meter_coords(self) -> List[Tuple[int, int, str]]:
        """Get coordinates of all active spot meters."""
        return [(p.x, p.y, p.label) for p in self.measurement_points]
    
    def update_spot_meter_values(self, values: List[Dict]):
        """
        Update temperatures for spot meters.
        
        Args:
            values: List of dicts with {'label': str, 'temperature': float, 'unit': str}
        """
        updated = False
        val_map = {v['label']: v for v in values}
        
        for point in self.measurement_points:
            if point.label in val_map:
                data = val_map[point.label]
                point.temperature = data['temperature']
                point.unit = data['unit']
                updated = True
                
        if updated and hasattr(self, 'video_widget'):
            self.video_widget.update_measurement_points(self.measurement_points)

    # === RADIOMETRIC SPOTMETER HANDLERS (Placeholder for 16-bit radiometric) ===
    
    def _on_spotmeter_enabled_changed(self, enabled: bool):
        """Handle hardware spotmeter enable/disable (16-bit radiometric feature)."""
        logger.info(f"Spotmeter {'enabled' if enabled else 'disabled'} (16-bit feature - not yet implemented)")
        # TODO: Implement when 16-bit radiometric is working
        pass
    
    def _on_spotmeter_mode_changed(self, mode: str):
        """Handle hardware spotmeter mode change (16-bit radiometric feature)."""
        logger.info(f"Spotmeter mode changed to: {mode} (16-bit feature - not yet implemented)")
        # TODO: Implement when 16-bit radiometric is working
        pass
    
    def _on_sensor_temps_requested(self):
        """Handle sensor temperature request (16-bit radiometric feature)."""
        logger.info("Sensor temperatures requested (16-bit feature - not yet implemented)")
        # TODO: Implement when 16-bit radiometric is working
        if self.app and hasattr(self.app, 'read_sensor_temperatures'):
            self.app.read_sensor_temperatures()

    # === PARALLAX HANDLERS ===
    def _on_view_mode_changed(self, mode_name: str):
        """Handle view mode change."""
        if self.app:
            self.app.set_view_mode(mode_name)
        logger.info(f"View mode changed to: {mode_name}")

    def _on_device_changed(self, device_name: str):
        """Handle processing device change."""
        if self.app:
            self.app.set_device(device_name)
        logger.info(f"Device changed to: {device_name}")

    def _on_fusion_mode_changed(self, mode_name: str):
        """Handle fusion mode change."""
        if self.app:
            self.app.set_fusion_mode(mode_name)
        logger.info(f"Fusion mode changed to: {mode_name}")

    def _on_fusion_alpha_changed(self, alpha: float):
        """Handle fusion alpha change."""
        if self.app:
            self.app.set_fusion_alpha(alpha)

    def _on_fusion_priority_changed(self, priority: str):
        """Handle fusion priority change."""
        if self.app:
            self.app.set_fusion_priority(priority)
        logger.info(f"Fusion priority changed to: {priority}")

    def _on_fusion_strength_changed(self, strength: float):
        """Handle fusion strength change."""
        if self.app and hasattr(self.app, 'set_fusion_strength'):
            self.app.set_fusion_strength(strength)
        logger.info(f"Fusion strength changed to: {strength:.2f}")

    def _on_fusion_fuzziness_changed(self, fuzziness: float):
        """Handle fusion fuzziness change."""
        if self.app and hasattr(self.app, 'set_fusion_fuzziness'):
            self.app.set_fusion_fuzziness(fuzziness)
        logger.info(f"Fusion fuzziness changed to: {fuzziness:.2f}")

    def _on_fusion_color_mode_changed(self, mode: str):
        """Handle RGB fusion color mode change (color vs grayscale)."""
        if self.app and hasattr(self.app, 'set_fusion_color_mode'):
            self.app.set_fusion_color_mode(mode)
        logger.info(f"Fusion color mode changed to: {mode}")

    def _on_edge_strength_changed(self, strength: float):
        """Handle edge detection strength change."""
        if self.app and hasattr(self.app, 'set_edge_strength'):
            self.app.set_edge_strength(strength)
        logger.info(f"Edge detection strength changed to: {strength:.2f}")

    def _on_edge_fuzziness_changed(self, fuzziness: float):
        """Handle edge detection fuzziness change."""
        if self.app and hasattr(self.app, 'set_edge_fuzziness'):
            self.app.set_edge_fuzziness(fuzziness)
        logger.info(f"Edge detection fuzziness changed to: {fuzziness:.2f}")

    def _on_edge_color_changed(self, color: str):
        """Handle edge overlay color change."""
        if self.app and hasattr(self.app, 'set_edge_color'):
            self.app.set_edge_color(color)
        logger.info(f"Edge color changed to: {color}")

    def _on_detail_strength_changed(self, strength: float):
        """Handle Detail Injection/Relief Fusion strength change."""
        if self.app and hasattr(self.app, 'set_detail_strength'):
            self.app.set_detail_strength(strength)
        logger.info(f"Detail strength changed to: {strength:.2f}")

    def _on_detail_quality_changed(self, quality: float):
        """Handle Detail Injection/Relief Fusion quality change."""
        if self.app and hasattr(self.app, 'set_detail_quality'):
            self.app.set_detail_quality(quality)
        logger.info(f"Detail quality changed to: {quality:.2f}")

    def _on_show_stats_toggle(self, checked: bool):
        """Toggle statistics display."""
        if hasattr(self.analysis_panel, 'stats_label'):
             self.analysis_panel.stats_label.setVisible(checked)
        logger.info(f"Show stats: {checked}")

    def _on_show_trends_toggle(self, checked: bool):
        """Toggle trends display."""
        if hasattr(self.analysis_panel, 'trend_label'):
             self.analysis_panel.trend_label.setVisible(checked)
        logger.info(f"Show trends: {checked}")

    def _on_show_detections_toggle(self, checked: bool):
        """Toggle detections display."""
        if hasattr(self.analysis_panel, 'detection_label'):
             self.analysis_panel.detection_label.setVisible(checked)
        logger.info(f"Show detections: {checked}")

    def _on_anomaly_priority_toggle(self, enabled: bool):
        """Toggle anomaly priority mode."""
        # Update button if it exists (it might not anymore if removed from control panel)
        # self.control_panel.update_anomaly_priority_button(enabled) 
        if self.app:
            self.app.toggle_anomaly_priority(enabled)
        logger.info(f"Anomaly priority: {'ON' if enabled else 'OFF'}")

    def _on_anomaly_types_changed(self, types_dict: dict):
        """Handle anomaly type selection changes."""
        if self.app:
            self.app.set_enabled_anomaly_types(types_dict)
        logger.info(f"Anomaly types changed: {types_dict}")

    def _on_fade_strength_changed(self, value: float):
        """Handle fade strength changes."""
        if self.app and hasattr(self.app, 'thermal_processor'):
            self.app.thermal_processor.anomaly_fade_strength = value
        logger.info(f"Fade strength: {value}")

    def _on_fade_distance_changed(self, value: int):
        """Handle fade distance changes."""
        if self.app and hasattr(self.app, 'thermal_processor'):
            self.app.thermal_processor.anomaly_max_distance = value
        logger.info(f"Fade distance: {value}px")

    def _on_motion_threshold_changed(self, value: int):
        """Handle motion threshold changes."""
        if self.app and hasattr(self.app, 'thermal_processor'):
            self.app.thermal_processor.motion_threshold = value
        logger.info(f"Motion threshold: {value}")

    def _on_edge_thresholds_changed(self, low: int, high: int):
        """Handle edge threshold changes."""
        if self.app and hasattr(self.app, 'thermal_processor'):
            self.app.thermal_processor.edge_threshold_low = low
            self.app.thermal_processor.edge_threshold_high = high
        logger.info(f"Edge thresholds: {low}/{high}")

    def _on_hot_spot_percentile_changed(self, value: int):
        """Handle hot spot percentile changes."""
        if self.app and hasattr(self.app, 'thermal_analyzer'):
            self.app.thermal_analyzer.hot_spot_percentile = value
        logger.info(f"Hot spot percentile: {value}")

    def _on_cold_spot_percentile_changed(self, value: int):
        """Handle cold spot percentile changes."""
        if self.app and hasattr(self.app, 'thermal_analyzer'):
            self.app.thermal_analyzer.cold_spot_percentile = value
        logger.info(f"Cold spot percentile: {value}")

    def _on_min_anomaly_size_changed(self, value: int):
        """Handle minimum anomaly size changes."""
        if self.app and hasattr(self.app, 'thermal_analyzer'):
            self.app.thermal_analyzer.min_anomaly_size = value
        logger.info(f"Min anomaly size: {value}px²")

    def _on_manual_threshold_enabled(self, enabled: bool):
        """Handle manual threshold enable/disable."""
        if self.app:
            self.app.set_manual_threshold_enabled(enabled)
        logger.info(f"Manual threshold: {'ENABLED' if enabled else 'DISABLED'}")

    def _on_manual_threshold_mode_changed(self, mode: str):
        """Handle manual threshold mode changes."""
        if self.app:
            self.app.set_manual_threshold_mode(mode)
        logger.info(f"Manual threshold mode: {mode}")

    def _on_manual_min_threshold_changed(self, value: float):
        """Handle manual minimum threshold changes."""
        if self.app:
            self.app.set_manual_min_threshold(value)
        logger.info(f"Manual min threshold: {value}")

    def _on_manual_max_threshold_changed(self, value: float):
        """Handle manual maximum threshold changes."""
        if self.app:
            self.app.set_manual_max_threshold(value)
        logger.info(f"Manual max threshold: {value}")

    def _on_manual_use_raw_changed(self, use_raw: bool):
        """Handle manual threshold raw values toggle."""
        if self.app:
            self.app.set_manual_use_raw_values(use_raw)
        logger.info(f"Manual threshold using: {'RAW values' if use_raw else 'Temperature (°C)'}")

    def _on_manual_viz_mode_changed(self, mode: str):
        """Handle manual threshold visualization mode changes."""
        if self.app:
            self.app.set_manual_viz_mode(mode)
        logger.info(f"Manual threshold viz mode: {mode}")

    def _on_fusion_mode_cycle(self):
        """Cycle fusion mode."""
        if self.app:
            self.app.cycle_fusion_mode()
        logger.info("Fusion mode cycle")

    def _on_fusion_alpha_cycle(self):
        """Cycle fusion alpha."""
        if self.app:
            self.app.cycle_fusion_alpha()
        logger.info("Fusion alpha cycle")

    def _on_fusion_priority_cycle(self):
        """Cycle fusion priority."""
        if self.app:
            self.app.cycle_fusion_priority()
        logger.info("Fusion priority cycle")

    def _on_baseline_toggle(self, enabled: bool):
        """Toggle baseline lock for relative temperature."""
        if self.app:
            # Call app's baseline toggle method
            if hasattr(self.app, 'lock_baseline'):
                self.app.lock_baseline(enabled)
        logger.info(f"Baseline lock: {'ON' if enabled else 'OFF'}")

    def _on_global_palette_changed(self, palette_name: str):
        """Handle global palette selection from analysis panel."""
        try:
            logger.info(f"Attempting to change palette to: '{palette_name}' (type: {type(palette_name)})")
            if self.app:
                self.app.set_palette(palette_name)
            logger.info(f"Global palette changed successfully: {palette_name}")
        except Exception as e:
            logger.error(f"CRASH in _on_global_palette_changed with palette '{palette_name}': {e}", exc_info=True)
            # Show error to user
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(self, "Palette Error", f"Failed to change palette to '{palette_name}':\n{e}")

    def _on_boson_connect(self, com_port: str):
        """Handle SDK connection request from Boson panel."""
        if self.app and hasattr(self.app, 'connect_boson_sdk'):
            success = self.app.connect_boson_sdk(com_port)
            if success:
                self.boson_panel.update_connection_status(True)
                logger.info(f"Boson SDK connected on {com_port}")

                # Enable 8-bit estimation controls now that SDK is connected
                # Do NOT auto-enable - user must enable after calibration
                if hasattr(self.radiometric_panel, 'set_8bit_estimation_available'):
                    self.radiometric_panel.set_8bit_estimation_available(
                        available=True,
                        auto_enabled=False  # Don't auto-check - requires calibration
                    )
                    logger.info("8-bit estimation controls available (not auto-enabled)")

                # Update status banner
                if hasattr(self.radiometric_panel, 'update_active_mode_status') and hasattr(self.app, 'get_active_temperature_mode'):
                    mode_info = self.app.get_active_temperature_mode()
                    self.radiometric_panel.update_active_mode_status(
                        mode_info['mode'],
                        mode_info['accuracy'],
                        mode_info['description']
                    )

                # Get camera info and display
                if hasattr(self.app.thermal_camera, 'get_camera_info'):
                    info = self.app.thermal_camera.get_camera_info()
                    if info:
                        self.boson_panel.set_status(f"SN: {info.serial_number}")
                        # Update all camera info fields
                        self.boson_panel.update_camera_info(info)
            else:
                self.boson_panel.set_status("Connection failed", is_error=True)
                logger.error(f"Boson SDK connection failed on {com_port}")
        else:
            self.boson_panel.set_status("App not ready", is_error=True)

    def _on_boson_disconnect(self):
        """Handle SDK disconnection request from Boson panel."""
        if self.app and hasattr(self.app, 'disconnect_boson_sdk'):
            self.app.disconnect_boson_sdk()
            self.boson_panel.update_connection_status(False)
            self.boson_panel.set_status("Disconnected")

            # Disable 8-bit estimation controls when SDK disconnects
            if hasattr(self.radiometric_panel, 'set_8bit_estimation_available'):
                self.radiometric_panel.set_8bit_estimation_available(
                    available=False,
                    auto_enabled=False
                )
                logger.info("8-bit estimation controls disabled")

            logger.info("Boson SDK disconnected")

    def _on_boson_scan_ports(self):
        """Handle COM port scan request from Boson panel."""
        if self.app and hasattr(self.app, 'scan_boson_com_ports'):
            ports = self.app.scan_boson_com_ports()
            if ports:
                self.boson_panel.update_ports(ports)
                self.boson_panel.set_status(f"Found {len(ports)} COM ports")
                logger.info(f"Found COM ports: {', '.join(ports)}")
            else:
                self.boson_panel.set_status("No COM ports found", is_error=True)
                logger.warning("No COM ports found")

    def _on_boson_ffc(self):
        """Handle FFC trigger from Boson panel."""
        if self.app and hasattr(self.app, 'trigger_ffc'):
            success = self.app.trigger_ffc()
            if success:
                self.boson_panel.set_status("FFC completed successfully")
                logger.info("FFC triggered successfully")
            else:
                self.boson_panel.set_status("FFC failed", is_error=True)
                logger.error("FFC trigger failed")

    def _on_boson_gain_mode(self, mode: str):
        """Handle gain mode change from Boson panel."""
        if self.app and hasattr(self.app, 'set_boson_gain_mode'):
            self.app.set_boson_gain_mode(mode)

    def _on_boson_ffc_mode(self, mode: str):
        """Handle FFC mode change from Boson panel."""
        if self.app and hasattr(self.app, 'set_boson_ffc_mode'):
            self.app.set_boson_ffc_mode(mode)

    def _on_boson_color_lut(self, lut_name: str):
        """Handle color LUT change from Boson panel."""
        if self.app and hasattr(self.app, 'set_boson_color_lut'):
            self.app.set_boson_color_lut(lut_name)
            logger.info(f"Boson color LUT set to: {lut_name}")

    def _on_agc_max_gain_changed(self, gain: float):
        """Handle AGC max gain change."""
        if self.app and hasattr(self.app, 'set_agc_max_gain'):
            if self.app.set_agc_max_gain(gain):
                logger.info(f"AGC max gain set to {gain:.1f}x")
            else:
                logger.warning(f"Failed to set AGC max gain to {gain:.1f}x")

    def _on_agc_gamma_changed(self, gamma: float):
        """Handle AGC gamma change."""
        if self.app and hasattr(self.app, 'set_agc_gamma'):
            if self.app.set_agc_gamma(gamma):
                logger.info(f"AGC gamma set to {gamma:.2f}")
            else:
                logger.warning(f"Failed to set AGC gamma to {gamma:.2f}")

    def _on_agc_linearity_changed(self, percent: float):
        """Handle AGC linearity change."""
        if self.app and hasattr(self.app, 'set_agc_linearity'):
            if self.app.set_agc_linearity(percent):
                logger.info(f"AGC linearity set to {percent:.0f}%")
            else:
                logger.warning(f"Failed to set AGC linearity to {percent:.0f}%")

    def _on_agc_dde_changed(self, dde: float):
        """Handle AGC DDE (Detail Enhancement) change."""
        if self.app and hasattr(self.app, 'set_agc_dde'):
            if self.app.set_agc_dde(dde):
                logger.info(f"AGC DDE set to {dde:.2f}")
            else:
                logger.warning(f"Failed to set AGC DDE to {dde:.2f}")

    def _on_agc_reset(self):
        """Reset AGC settings to defaults."""
        if self.app and hasattr(self.app, 'reset_agc_settings'):
            if self.app.reset_agc_settings():
                logger.info("AGC settings reset to defaults")
            else:
                logger.warning("Failed to reset AGC settings")

    def _on_agc_plateau_changed(self, value: float):
        """Handle AGC plateau change."""
        if self.app and hasattr(self.app, 'set_agc_plateau'):
            if self.app.set_agc_plateau(value):
                logger.info(f"AGC plateau set to {value*100:.0f}%")
            else:
                logger.warning(f"Failed to set AGC plateau to {value*100:.0f}%")

    def _on_agc_dampening_changed(self, value: float):
        """Handle AGC dampening change."""
        if self.app and hasattr(self.app, 'set_agc_dampening'):
            if self.app.set_agc_dampening(value):
                logger.info(f"AGC dampening set to {value*100:.0f}%")
            else:
                logger.warning(f"Failed to set AGC dampening to {value*100:.0f}%")

    def _on_shutter_position_changed(self, position: str):
        """Handle shutter position change."""
        if self.app and hasattr(self.app, 'set_shutter_position'):
            if self.app.set_shutter_position(position):
                logger.info(f"Shutter position set to {position}")
            else:
                logger.warning(f"Failed to set shutter position to {position}")

    def _on_radiometric_mode_changed(self, enable_radiometric: bool):
        """Handle radiometric mode change request."""
        if self.app and hasattr(self.app, 'set_radiometric_mode'):
            success = self.app.set_radiometric_mode(enable_radiometric)

            # Update UI based on result
            self.boson_panel.update_radiometric_mode_status(enable_radiometric, success)

            if success:
                mode_name = "T-Linear Radiometric (16-bit)" if enable_radiometric else "UVC Post-Colorized (8-bit)"
                logger.info(f"Camera mode changed to: {mode_name}")
            else:
                logger.error(f"Failed to change camera mode")
        else:
            logger.error("set_radiometric_mode method not available")
            self.boson_panel.update_radiometric_mode_status(enable_radiometric, False)

    def _on_calibration_add_point_mode(self, reference_temp: float):
        """Handle calibration add point mode toggle."""
        if self.app and hasattr(self.app, 'set_calibration_add_point_mode'):
            self.app.set_calibration_add_point_mode(True, reference_temp)

    def _on_compute_calibration(self, method: str, degree: int):
        """Handle compute calibration request."""
        if self.app and hasattr(self.app, 'compute_calibration'):
            if self.app.compute_calibration(method, degree):
                logger.info(f"Calibration computed using {method} method")
                # Update GUI
                if hasattr(self.app, 'update_calibration_gui'):
                    self.app.update_calibration_gui()
            else:
                logger.warning("Failed to compute calibration")
                QMessageBox.warning(self, "Calibration Error",
                                   "Failed to compute calibration. Need at least 2 points for linear, more for polynomial.")

    def _on_apply_calibration_toggled(self, enabled: bool):
        """Handle apply calibration toggle."""
        if self.app and hasattr(self.app, 'set_calibration_enabled'):
            self.app.set_calibration_enabled(enabled)
            logger.info(f"Calibration correction: {'ENABLED' if enabled else 'DISABLED'}")

    def _on_update_depth_config(self):
        """Handle depth map configuration update."""
        if self.app and hasattr(self.app, 'update_depth_config'):
            config = {
                'enable_ml': self.parallax_panel.ml_depth_enabled,
                'min_depth_m': self.parallax_panel.get_depth_range()[0],
                'max_depth_m': self.parallax_panel.get_depth_range()[1],
            }
            self.app.update_depth_config(config)
            logger.info(f"Depth configuration updated: {config}")
    
    def _on_clear_calibration(self):
        """Handle clear calibration request."""
        if self.app and hasattr(self.app, 'clear_calibration'):
            self.app.clear_calibration()
            logger.info("Calibration cleared")
            if hasattr(self.app, 'update_calibration_gui'):
                self.app.update_calibration_gui()
    
    # ========================================================================
    # Environmental Compensation Handlers (Phase 11)
    # ========================================================================
    
    def _on_emissivity_changed(self, emissivity: float):
        """Handle emissivity change."""
        if self.app and hasattr(self.app, 'set_emissivity'):
            self.app.set_emissivity(emissivity)
            logger.info(f"Emissivity set to {emissivity:.2f}")
    
    def _on_atmospheric_temp_changed(self, temp_c: float):
        """Handle atmospheric temperature change."""
        if self.app and hasattr(self.app, 'set_atmospheric_temperature'):
            self.app.set_atmospheric_temperature(temp_c)
            logger.info(f"Atmospheric temperature set to {temp_c:.1f}°C")
    
    def _on_atmospheric_transmission_changed(self, transmission: float):
        """Handle atmospheric transmission change."""
        if self.app and hasattr(self.app, 'set_atmospheric_transmission'):
            self.app.set_atmospheric_transmission(transmission)
            logger.info(f"Atmospheric transmission set to {transmission:.2f}")

    def _on_isotherm_enabled_changed(self, enabled: bool):
        """Handle isotherm highlighting enable/disable."""
        if self.app:
            if hasattr(self.app, 'set_isotherm_enabled'):
                self.app.set_isotherm_enabled(enabled)
            else:
                self.app.isotherm_enabled = enabled
            logger.info(f"Isotherm highlighting: {'enabled' if enabled else 'disabled'}")

    def _on_isotherm_mode_changed(self, mode: str):
        """Handle isotherm mode change."""
        if self.app:
            if hasattr(self.app, 'set_isotherm_mode'):
                self.app.set_isotherm_mode(mode)
            else:
                self.app.isotherm_mode = mode
            logger.info(f"Isotherm mode: {mode}")

    def _on_isotherm_low_threshold_changed(self, threshold: float):
        """Handle isotherm low threshold change."""
        if self.app:
            if hasattr(self.app, 'set_isotherm_low_threshold'):
                self.app.set_isotherm_low_threshold(threshold)
            else:
                self.app.isotherm_low_threshold = threshold

    def _on_isotherm_high_threshold_changed(self, threshold: float):
        """Handle isotherm high threshold change."""
        if self.app:
            if hasattr(self.app, 'set_isotherm_high_threshold'):
                self.app.set_isotherm_high_threshold(threshold)
            else:
                self.app.isotherm_high_threshold = threshold

    def _on_isotherm_color_changed(self, color: str):
        """Handle isotherm color change."""
        if self.app:
            # Call the setter method which converts color name to BGR
            if hasattr(self.app, 'set_isotherm_color'):
                self.app.set_isotherm_color(color)
            else:
                self.app.isotherm_color = color
            logger.info(f"Isotherm color set to: {color}")

    def update_radiometric_panel_availability(self, is_radiometric: bool):
        """Enable/disable panels that require radiometric mode.

        Args:
            is_radiometric: True if radiometric mode is active (16-bit), False otherwise (8-bit)
        """
        # Isotherm panel - only available in radiometric mode
        if hasattr(self, 'isotherm_panel'):
            self.isotherm_panel.setEnabled(is_radiometric)
            if not is_radiometric:
                logger.debug("Isotherm panel disabled (8-bit mode)")
            else:
                logger.debug("Isotherm panel enabled (16-bit mode)")

        # Environmental compensation panel - only available in radiometric mode
        if hasattr(self, 'env_comp_panel'):
            self.env_comp_panel.setEnabled(is_radiometric)
            if not is_radiometric:
                logger.debug("Environmental panel disabled (8-bit mode)")
            else:
                logger.debug("Environmental panel enabled (16-bit mode)")

    # ========================================================================
    # Radiometric Tab Placeholder Creation Methods
    # ========================================================================
    
    def _create_roi_temp_placeholder(self):
        """Create placeholder widget for Per-ROI temperature panel"""
        widget = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)
        
        header = QLabel("Per-ROI Temperature Analysis")
        header.setStyleSheet("font-size: 14pt; font-weight: bold; color: #0a0;")
        layout.addWidget(header)
        
        status = QLabel("✅ Backend Implementation Complete")
        status.setStyleSheet("color: #0a0; font-size: 11pt; font-weight: bold;")
        layout.addWidget(status)
        
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(separator)
        
        info = QLabel(
            "<b>Implemented Features:</b><br>"
            "• Independent temperature statistics per ROI (min/max/avg/std)<br>"
            "• Per-ROI emissivity override for different materials<br>"
            "• Temperature trend tracking over time<br>"
            "• CSV/JSON export with per-ROI data<br>"
            "<br>"
            "<b>Status:</b> Backend integrated into main processing loop.<br>"
            "<b>Pending:</b> GUI display and controls (coming soon)."
        )
        info.setWordWrap(True)
        info.setStyleSheet("font-size: 10pt;")
        layout.addWidget(info)
        
        layout.addStretch()
        widget.setLayout(layout)
        return widget
    
    def _create_env_comp_placeholder(self):
        """Create placeholder widget for environmental compensation panel"""
        widget = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)
        
        header = QLabel("Environmental Compensation")
        header.setStyleSheet("font-size: 14pt; font-weight: bold; color: #fa0;")
        layout.addWidget(header)
        
        status = QLabel("📋 Planned for Advanced Radiometry Phase 1")
        status.setStyleSheet("color: #fa0; font-size: 11pt; font-weight: bold;")
        layout.addWidget(status)
        
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(separator)
        
        info = QLabel(
            "<b>Planned Features:</b><br>"
            "• Emissivity control with material presets<br>"
            "• Atmospheric transmission compensation<br>"
            "• Distance and reflected temperature settings<br>"
            "• Humidity and atmospheric absorption<br>"
            "<br>"
            "<b>Impact:</b> Improves accuracy from ±2-5°C to ±0.5-1°C<br>"
            "<b>Priority:</b> HIGH (next major radiometric feature)"
        )
        info.setWordWrap(True)
        info.setStyleSheet("font-size: 10pt;")
        layout.addWidget(info)
        
        layout.addStretch()
        widget.setLayout(layout)
        return widget
    
    def _create_isotherm_placeholder(self):
        """Create placeholder widget for isotherm highlighting panel"""
        widget = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)
        
        header = QLabel("Temperature Range Highlighting (Isotherm)")
        header.setStyleSheet("font-size: 14pt; font-weight: bold; color: #08f;")
        layout.addWidget(header)
        
        status = QLabel("📋 Planned for Advanced Radiometry Phase 2")
        status.setStyleSheet("color: #08f; font-size: 11pt; font-weight: bold;")
        layout.addWidget(status)
        
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(separator)
        
        info = QLabel(
            "<b>Planned Features:</b><br>"
            "• Highlight pixels within temperature range<br>"
            "• Configurable low/high thresholds and colors<br>"
            "• Multiple modes: above, below, between<br>"
            "• Real-time visualization overlay<br>"
            "<br>"
            "<b>Use Cases:</b> Identify overheating components, thermal leaks,<br>"
            "temperature uniformity analysis<br>"
            "<b>Priority:</b> MEDIUM (after environmental compensation)"
        )
        info.setWordWrap(True)
        info.setStyleSheet("font-size: 10pt;")
        layout.addWidget(info)
        
        layout.addStretch()
        widget.setLayout(layout)
        return widget

    def _on_export_calibration(self):
        """Handle export calibration request."""
        if not self.app or not hasattr(self.app, 'export_calibration'):
            return

        from datetime import datetime
        default_name = f"calibration_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Calibration",
            default_name,
            "JSON Files (*.json);;All Files (*.*)"
        )

        if file_path:
            if self.app.export_calibration(file_path):
                logger.info(f"Calibration exported to {file_path}")
                QMessageBox.information(self, "Export Successful",
                                       f"Calibration exported to:\n{file_path}")
            else:
                logger.error("Failed to export calibration")
                QMessageBox.critical(self, "Export Failed", "Failed to export calibration")

    def _on_import_calibration(self):
        """Handle import calibration request."""
        if not self.app or not hasattr(self.app, 'import_calibration'):
            return

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Import Calibration",
            "",
            "JSON Files (*.json);;All Files (*.*)"
        )

        if file_path:
            if self.app.import_calibration(file_path):
                logger.info(f"Calibration imported from {file_path}")
                QMessageBox.information(self, "Import Successful",
                                       f"Calibration imported from:\n{file_path}")
                if hasattr(self.app, 'update_calibration_gui'):
                    self.app.update_calibration_gui()
            else:
                logger.error("Failed to import calibration")
                QMessageBox.critical(self, "Import Failed", "Failed to import calibration")

    def _on_remove_calibration_point(self, index: int):
        """Handle remove calibration point request."""
        if self.app and hasattr(self.app, 'remove_calibration_point'):
            if self.app.remove_calibration_point(index):
                logger.info(f"Removed calibration point at index {index}")
                if hasattr(self.app, 'update_calibration_gui'):
                    self.app.update_calibration_gui()

    def _on_overlay_info_toggle(self, show: bool):
        """Handle overlay detection info toggle."""
        if hasattr(self.video_widget, 'overlay'):
            self.video_widget.overlay.set_show_detection_info(show)
            logger.info(f"Overlay detection info: {'ON' if show else 'OFF'}")

    def _on_roi_created(self, roi):
        """Handle new ROI created from overlay."""
        try:
            # Add to app's ROI manager if available
            if self.app and hasattr(self.app, 'roi_manager'):
                self.app.roi_manager.add_roi(roi)
                logger.info(f"ROI created: {roi.label} ({roi.roi_type})")
            else:
                logger.warning("ROI manager not available")

            # Disable drawing mode after creating one ROI
            if hasattr(self.video_widget, 'overlay'):
                self.video_widget.overlay.disable_drawing_mode()

            # Uncheck the draw button
            if hasattr(self, 'control_panel') and hasattr(self.control_panel, 'draw_roi_btn'):
                self.control_panel.draw_roi_btn.setChecked(False)

        except Exception as e:
            logger.error(f"Error in _on_roi_created: {e}", exc_info=True)

    def _on_roi_selected(self, roi_id: str):
        """Handle ROI selection from overlay."""
        logger.info(f"ROI selected: {roi_id}")
        
        # Update analysis panel selection
        if hasattr(self, 'analysis_panel'):
            self.analysis_panel.select_roi(roi_id)

    def _on_roi_palette_changed(self, roi_id: str, palette_name: str):
        """Handle ROI palette change."""
        if self.app:
            if hasattr(self.app, 'set_roi_palette'):
                # Use unified handler that updates both ROI object and PaletteManager
                self.app.set_roi_palette(roi_id, palette_name)
                logger.info(f"ROI {roi_id} palette updated to: {palette_name}")
            elif hasattr(self.app, 'palette_manager'):
                # Fallback for legacy
                from palette_manager import PaletteType
                try:
                    palette_type = PaletteType(palette_name)
                    self.app.palette_manager.set_roi_palette(roi_id, palette_type)
                except Exception as e:
                    logger.error(f"Error setting palette: {e}")

    def _on_roi_palette_cleared(self, roi_id: str):
        """Handle ROI palette clear."""
        if self.app and hasattr(self.app, 'palette_manager'):
            self.app.palette_manager.clear_roi_palette(roi_id)
            logger.info(f"ROI {roi_id} palette cleared (using global)")

    def _on_roi_delete(self, roi_id: str):
        """Handle ROI deletion."""
        if self.app:
            if hasattr(self.app, 'delete_roi'):
                self.app.delete_roi(roi_id)
            elif hasattr(self.app, 'roi_manager'):
                self.app.roi_manager.delete_roi(roi_id)
            logger.info(f"ROI {roi_id} deleted")

    def update_frame(self, frame: np.ndarray):
        """Update video display."""
        self.video_widget.update_frame(frame)

    def update_metrics(self, fps: float, roi_count: int, thermal_connected: bool, rgb_connected: bool):
        """Update info panel metrics."""
        self.info_panel.update_info(fps, roi_count, thermal_connected, rgb_connected, self.recording)

    def update_rois(self, rois: List[ROI]):
        """Update ROI visualization and list."""
        self.video_widget.update_rois(rois)
        self.analysis_panel.update_rois(rois)

    def update_thermal_analysis(self, stats: Optional[ThermalStatistics],
                                hot_spots: List[HotSpot],
                                cold_spots: List[ColdSpot],
                                anomalies: List[ThermalAnomaly],
                                motion_detections: List = None,
                                edge_clusters: List = None,
                                trend: Optional[TemperatureTrend] = None):
        """Update thermal analysis displays."""
        self.video_widget.update_thermal_detections(hot_spots, cold_spots, anomalies)
        self.analysis_panel.update_statistics(stats)
        self.analysis_panel.update_hot_spots(hot_spots)
        self.analysis_panel.update_cold_spots(cold_spots)
        self.analysis_panel.update_anomalies(anomalies)
        self.analysis_panel.update_trend(trend)

        # Update Anomaly Widget counts
        counts = {
            "hot_spots": len(hot_spots),
            "cold_spots": len(cold_spots),
            "thermal_anomalies": len(anomalies),
            "motion": len(motion_detections) if motion_detections else 0,
            "edges": len(edge_clusters) if edge_clusters else 0
        }
        self.anomaly_widget.update_counts(counts)

    def _on_camera_clicked(self):
        """Handle camera manager button click."""
        if not self.app:
            return
        try:
            dialog = CameraManagerDialog(self.app, self)
            dialog.exec()
        except Exception as e:
            logger.error(f"Camera manager dialog error: {e}", exc_info=True)
            QMessageBox.critical(self, "Error", f"Failed to open camera manager: {e}")
    
    # ==========================================================================
    # Firefly Camera Control Handlers
    # ==========================================================================
    
    def _on_firefly_exposure_mode(self, mode: str):
        """Handle Firefly exposure mode change."""
        if self.app:
            self.app.set_firefly_exposure_mode(mode)
            logger.info(f"Firefly exposure mode: {mode}")
    
    def _on_firefly_exposure_time(self, time_us: float):
        """Handle Firefly exposure time change."""
        if self.app:
            self.app.set_firefly_exposure_time(time_us)
            logger.debug(f"Firefly exposure time: {time_us} µs")
    
    def _on_firefly_gain_mode(self, mode: str):
        """Handle Firefly gain mode change."""
        if self.app:
            self.app.set_firefly_gain_mode(mode)
            logger.info(f"Firefly gain mode: {mode}")
    
    def _on_firefly_gain(self, gain_db: float):
        """Handle Firefly gain change."""
        if self.app:
            self.app.set_firefly_gain(gain_db)
            logger.debug(f"Firefly gain: {gain_db} dB")
    
    def _on_firefly_white_balance_mode(self, mode: str):
        """Handle Firefly white balance mode change."""
        if self.app:
            self.app.set_firefly_white_balance_mode(mode)
            logger.info(f"Firefly white balance mode: {mode}")
    
    def _on_firefly_white_balance_calibrate(self):
        """Handle Firefly white balance calibration."""
        if self.app:
            self.app.calibrate_firefly_white_balance()
            logger.info("Firefly white balance calibration triggered")
    
    def _on_firefly_white_balance_ratio(self, color: str, ratio: float):
        """Handle Firefly white balance ratio change."""
        if self.app:
            self.app.set_firefly_white_balance_ratio(color, ratio)
            logger.debug(f"Firefly {color} balance ratio: {ratio}")
    
    def _on_firefly_trigger_mode(self, enabled: bool, source: str):
        """Handle Firefly trigger mode change."""
        if self.app:
            self.app.set_firefly_trigger_mode(enabled, source)
            mode_str = f"{source} trigger" if enabled else "Free-run"
            logger.info(f"Firefly trigger mode: {mode_str}")
    
    def _on_firefly_trigger_fire(self):
        """Handle Firefly software trigger."""
        if self.app:
            self.app.fire_firefly_software_trigger()
            logger.info("Firefly software trigger fired")
    
    def _on_firefly_gamma(self, gamma: float):
        """Handle Firefly gamma change."""
        if self.app:
            self.app.set_firefly_gamma(gamma)
            logger.debug(f"Firefly gamma: {gamma}")
    
    def _on_firefly_sharpness(self, enabled: bool, value: float):
        """Handle Firefly sharpness change."""
        if self.app:
            self.app.set_firefly_sharpness(enabled, value)
            logger.debug(f"Firefly sharpness: {'ON' if enabled else 'OFF'} ({value})")

    # ========================================================================
    # Radiometric Panel Handlers
    # ========================================================================

    def _on_radiometric_enable_changed(self, state: int):
        """Handle radiometric enable/disable toggle."""
        enabled = (state == Qt.CheckState.Checked.value)
        if self.app:
            self.app.enable_radiometric(enabled)
            logger.info(f"Radiometric conversion: {'ENABLED' if enabled else 'DISABLED'}")

    def _on_radiometric_range_apply(self):
        """Handle temperature range apply button."""
        min_temp, max_temp = self.radiometric_panel.get_temperature_range()
        if self.app:
            self.app.set_radiometric_temperature_range(min_temp, max_temp)
            logger.info(f"Radiometric temperature range: {min_temp}°C - {max_temp}°C")

    def _on_cursor_moved(self, x: int, y: int):
        """Handle cursor movement to display temperature at cursor position."""
        if not self.app or not hasattr(self.app, 'thermal_camera'):
            return

        if not self.app.thermal_camera:
            return

        # Get temperature at cursor position
        try:
            temp = self.app.thermal_camera.get_spot_temperature(x, y)
            if temp is not None:
                # Update radiometric panel
                self.radiometric_panel.set_cursor_temperature(temp, x, y)
        except Exception as e:
            logger.debug(f"Error getting cursor temperature: {e}")

    def _on_load_lut(self):
        """Handle Load LUT button click."""
        from PyQt6.QtWidgets import QFileDialog

        # Open file dialog
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Load TLinear LUT File",
            "",
            "CSV Files (*.csv);;All Files (*.*)"
        )

        if not file_path:
            return  # User cancelled

        # Load LUT via app
        if self.app and hasattr(self.app, 'load_radiometric_lut'):
            success = self.app.load_radiometric_lut(file_path)
            if success:
                logger.info(f"TLinear LUT loaded successfully from {file_path}")
                # Status will be updated by app calling radiometric panel methods
            else:
                logger.error(f"Failed to load TLinear LUT from {file_path}")
                from PyQt6.QtWidgets import QMessageBox
                QMessageBox.warning(self, "LUT Load Failed",
                                   f"Failed to load TLinear LUT from:\n{file_path}\n\nCheck the file format.")

    def _on_radiometric_method_changed(self):
        """Handle conversion method change (linear/LUT)."""
        method = self.radiometric_panel.get_conversion_method()
        if self.app and hasattr(self.app, 'set_radiometric_method'):
            self.app.set_radiometric_method(method)
            logger.info(f"Radiometric conversion method: {method.upper()}")

    # ========================================================================
    # Parallax Panel Handlers
    # ========================================================================

    def _on_parallax_toggled(self, enabled: bool):
        """Handle parallax enable/disable toggle."""
        if self.app and hasattr(self.app, 'enable_parallax_compensation'):
            self.app.enable_parallax_compensation(enabled)
            logger.info(f"Parallax compensation: {'ENABLED' if enabled else 'DISABLED'}")

    def _on_parallax_baseline_changed(self, baseline_mm: float):
        """Handle baseline distance change."""
        if self.app and hasattr(self.app, 'set_parallax_baseline'):
            self.app.set_parallax_baseline(baseline_mm)
            logger.info(f"Parallax baseline: {baseline_mm}mm")

    def _on_parallax_method_changed(self, method: str):
        """Handle depth estimation method change."""
        if self.app and hasattr(self.app, 'set_parallax_depth_method'):
            self.app.set_parallax_depth_method(method)
            logger.info(f"Parallax depth method: {method}")

    def _on_parallax_geometry_apply(self):
        """Handle apply geometry button click."""
        baseline = self.parallax_panel.get_baseline()
        if self.app and hasattr(self.app, 'set_parallax_baseline'):
            self.app.set_parallax_baseline(baseline)
            logger.info(f"Parallax geometry applied: baseline={baseline}mm")

# ============================================================================
# Standalone Test
# ============================================================================

def main():
    """Standalone test of inspection GUI."""
    if not PYQT_AVAILABLE:
        print("ERROR: PyQt5 is required. Install with: pip3 install PyQt5")
        sys.exit(1)

    app = QApplication(sys.argv)
    window = InspectionAppWindow()
    window.show()

    # Test with dummy data
    import time
    dummy_frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
    window.update_frame(dummy_frame)
    window.update_metrics(fps=30.0, roi_count=3, thermal_connected=True, rgb_connected=True)

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
