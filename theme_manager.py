#!/usr/bin/env python3
"""
Theme Manager for Settings Editor
Provides professional colorized themes with Qt stylesheet generation
Independent from main application theming
"""

import json
import logging
from pathlib import Path
from typing import Dict, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ThemeColors:
    """Color palette for a theme"""
    # Base colors
    background: str
    background_alt: str  # Alternate background (tabs, panels)
    foreground: str
    foreground_dim: str
    
    # Accent colors
    primary: str
    primary_hover: str
    secondary: str
    
    # UI elements
    border: str
    border_focus: str
    selection_bg: str
    selection_fg: str
    
    # Status colors
    success: str
    warning: str
    error: str
    info: str
    
    # Widget specific
    button_bg: str
    button_hover: str
    input_bg: str
    input_border: str


class ThemeManager:
    """Manages themes for the settings editor"""
    
    # Professional theme definitions
    THEMES: Dict[str, ThemeColors] = {
        "Dark Modern": ThemeColors(
            background="#1e1e1e",
            background_alt="#252526",
            foreground="#d4d4d4",
            foreground_dim="#858585",
            primary="#0e639c",
            primary_hover="#1177bb",
            secondary="#007acc",
            border="#3e3e42",
            border_focus="#007acc",
            selection_bg="#264f78",
            selection_fg="#ffffff",
            success="#4caf50",
            warning="#ff9800",
            error="#f44336",
            info="#2196f3",
            button_bg="#0e639c",
            button_hover="#1177bb",
            input_bg="#2d2d30",
            input_border="#3e3e42"
        ),
        
        "Light Professional": ThemeColors(
            background="#ffffff",
            background_alt="#f3f3f3",
            foreground="#1e1e1e",
            foreground_dim="#6e6e6e",
            primary="#0078d4",
            primary_hover="#106ebe",
            secondary="#005a9e",
            border="#d0d0d0",
            border_focus="#0078d4",
            selection_bg="#cce8ff",
            selection_fg="#000000",
            success="#107c10",
            warning="#ffa500",
            error="#d13438",
            info="#0078d4",
            button_bg="#0078d4",
            button_hover="#106ebe",
            input_bg="#ffffff",
            input_border="#d0d0d0"
        ),
        
        "Nord Arctic": ThemeColors(
            background="#2e3440",
            background_alt="#3b4252",
            foreground="#eceff4",
            foreground_dim="#d8dee9",
            primary="#88c0d0",
            primary_hover="#8fbcbb",
            secondary="#81a1c1",
            border="#4c566a",
            border_focus="#88c0d0",
            selection_bg="#434c5e",
            selection_fg="#eceff4",
            success="#a3be8c",
            warning="#ebcb8b",
            error="#bf616a",
            info="#5e81ac",
            button_bg="#5e81ac",
            button_hover="#81a1c1",
            input_bg="#3b4252",
            input_border="#4c566a"
        ),
        
        "Solarized Dark": ThemeColors(
            background="#002b36",
            background_alt="#073642",
            foreground="#839496",
            foreground_dim="#586e75",
            primary="#268bd2",
            primary_hover="#2aa198",
            secondary="#859900",
            border="#073642",
            border_focus="#268bd2",
            selection_bg="#073642",
            selection_fg="#93a1a1",
            success="#859900",
            warning="#b58900",
            error="#dc322f",
            info="#268bd2",
            button_bg="#268bd2",
            button_hover="#2aa198",
            input_bg="#073642",
            input_border="#586e75"
        ),
        
        "Dracula": ThemeColors(
            background="#282a36",
            background_alt="#21222c",
            foreground="#f8f8f2",
            foreground_dim="#6272a4",
            primary="#bd93f9",
            primary_hover="#ff79c6",
            secondary="#8be9fd",
            border="#44475a",
            border_focus="#bd93f9",
            selection_bg="#44475a",
            selection_fg="#f8f8f2",
            success="#50fa7b",
            warning="#f1fa8c",
            error="#ff5555",
            info="#8be9fd",
            button_bg="#bd93f9",
            button_hover="#ff79c6",
            input_bg="#21222c",
            input_border="#44475a"
        ),
        
        "Monokai": ThemeColors(
            background="#272822",
            background_alt="#1e1f1c",
            foreground="#f8f8f2",
            foreground_dim="#75715e",
            primary="#f92672",
            primary_hover="#fd971f",
            secondary="#e6db74",
            border="#3e3d32",
            border_focus="#f92672",
            selection_bg="#49483e",
            selection_fg="#f8f8f2",
            success="#a6e22e",
            warning="#fd971f",
            error="#f92672",
            info="#66d9ef",
            button_bg="#f92672",
            button_hover="#fd971f",
            input_bg="#1e1f1c",
            input_border="#3e3d32"
        ),
        
        "Gruvbox Dark": ThemeColors(
            background="#282828",
            background_alt="#1d2021",
            foreground="#ebdbb2",
            foreground_dim="#a89984",
            primary="#fe8019",
            primary_hover="#fabd2f",
            secondary="#b8bb26",
            border="#504945",
            border_focus="#fe8019",
            selection_bg="#3c3836",
            selection_fg="#ebdbb2",
            success="#b8bb26",
            warning="#fabd2f",
            error="#fb4934",
            info="#83a598",
            button_bg="#fe8019",
            button_hover="#fabd2f",
            input_bg="#1d2021",
            input_border="#504945"
        ),
        
        "Material Design": ThemeColors(
            background="#263238",
            background_alt="#1e272e",
            foreground="#eeffff",
            foreground_dim="#b0bec5",
            primary="#009688",
            primary_hover="#00bcd4",
            secondary="#80cbc4",
            border="#37474f",
            border_focus="#00bcd4",
            selection_bg="#314549",
            selection_fg="#eeffff",
            success="#4caf50",
            warning="#ff9800",
            error="#f44336",
            info="#2196f3",
            button_bg="#009688",
            button_hover="#00bcd4",
            input_bg="#1e272e",
            input_border="#37474f"
        ),
        
        "One Dark": ThemeColors(
            background="#282c34",
            background_alt="#21252b",
            foreground="#abb2bf",
            foreground_dim="#5c6370",
            primary="#61afef",
            primary_hover="#56b6c2",
            secondary="#c678dd",
            border="#3e4451",
            border_focus="#61afef",
            selection_bg="#3e4451",
            selection_fg="#abb2bf",
            success="#98c379",
            warning="#e5c07b",
            error="#e06c75",
            info="#61afef",
            button_bg="#61afef",
            button_hover="#56b6c2",
            input_bg="#21252b",
            input_border="#3e4451"
        )
    }
    
    def __init__(self, config_file: str = "settings_editor_theme.json"):
        """
        Initialize theme manager
        
        Args:
            config_file: Path to theme configuration file
        """
        self.config_file = Path(config_file)
        self.current_theme = "Dark Modern"  # Default
        self._load_theme_preference()
    
    def _load_theme_preference(self):
        """Load saved theme preference from config"""
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r') as f:
                    data = json.load(f)
                    theme = data.get('theme', 'Dark Modern')
                    if theme in self.THEMES:
                        self.current_theme = theme
                        logger.info(f"Loaded theme preference: {theme}")
        except Exception as e:
            logger.warning(f"Could not load theme preference: {e}")
    
    def save_theme_preference(self):
        """Save current theme preference to config"""
        try:
            data = {'theme': self.current_theme}
            with open(self.config_file, 'w') as f:
                json.dump(data, f, indent=2)
            logger.debug(f"Saved theme preference: {self.current_theme}")
        except Exception as e:
            logger.error(f"Could not save theme preference: {e}")
    
    def set_theme(self, theme_name: str) -> bool:
        """
        Set current theme
        
        Args:
            theme_name: Name of theme to set
            
        Returns:
            True if theme was set successfully
        """
        if theme_name in self.THEMES:
            self.current_theme = theme_name
            self.save_theme_preference()
            logger.info(f"Theme changed to: {theme_name}")
            return True
        else:
            logger.warning(f"Unknown theme: {theme_name}")
            return False
    
    def get_theme_names(self) -> list:
        """Get list of available theme names"""
        return list(self.THEMES.keys())
    
    def get_current_theme_name(self) -> str:
        """Get name of current theme"""
        return self.current_theme
    
    def get_colors(self) -> ThemeColors:
        """Get color palette for current theme"""
        return self.THEMES[self.current_theme]
    
    def generate_stylesheet(self) -> str:
        """
        Generate Qt stylesheet for current theme
        
        Returns:
            Complete Qt stylesheet string
        """
        colors = self.get_colors()
        
        stylesheet = f"""
/* Main Window and Base Widgets */
QMainWindow, QWidget {{
    background-color: {colors.background};
    color: {colors.foreground};
    font-family: "Segoe UI", Arial, sans-serif;
    font-size: 10pt;
}}

/* Tab Widget */
QTabWidget::pane {{
    border: 1px solid {colors.border};
    background-color: {colors.background};
    border-radius: 4px;
}}

QTabBar::tab {{
    background-color: {colors.background_alt};
    color: {colors.foreground_dim};
    padding: 8px 16px;
    margin: 2px;
    border: 1px solid {colors.border};
    border-bottom: none;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
}}

QTabBar::tab:selected {{
    background-color: {colors.background};
    color: {colors.foreground};
    border-bottom: 2px solid {colors.primary};
    font-weight: bold;
}}

QTabBar::tab:hover {{
    background-color: {colors.background};
    color: {colors.foreground};
}}

/* Scroll Areas */
QScrollArea {{
    border: none;
    background-color: {colors.background};
}}

/* Group Boxes */
QGroupBox {{
    border: 1px solid {colors.border};
    border-radius: 4px;
    margin-top: 12px;
    padding-top: 12px;
    font-weight: bold;
    color: {colors.foreground};
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 4px 8px;
    color: {colors.primary};
}}

/* Labels */
QLabel {{
    color: {colors.foreground};
    background-color: transparent;
}}

/* Line Edits */
QLineEdit {{
    background-color: {colors.input_bg};
    color: {colors.foreground};
    border: 1px solid {colors.input_border};
    border-radius: 3px;
    padding: 5px;
    selection-background-color: {colors.selection_bg};
    selection-color: {colors.selection_fg};
}}

QLineEdit:focus {{
    border: 1px solid {colors.border_focus};
}}

/* Spin Boxes */
QSpinBox, QDoubleSpinBox {{
    background-color: {colors.input_bg};
    color: {colors.foreground};
    border: 1px solid {colors.input_border};
    border-radius: 3px;
    padding: 4px;
    selection-background-color: {colors.selection_bg};
}}

QSpinBox:focus, QDoubleSpinBox:focus {{
    border: 1px solid {colors.border_focus};
}}

QSpinBox::up-button, QDoubleSpinBox::up-button {{
    background-color: {colors.background_alt};
    border-left: 1px solid {colors.border};
    border-radius: 0px;
}}

QSpinBox::down-button, QDoubleSpinBox::down-button {{
    background-color: {colors.background_alt};
    border-left: 1px solid {colors.border};
    border-radius: 0px;
}}

/* Combo Boxes */
QComboBox {{
    background-color: {colors.input_bg};
    color: {colors.foreground};
    border: 1px solid {colors.input_border};
    border-radius: 3px;
    padding: 5px;
    selection-background-color: {colors.selection_bg};
}}

QComboBox:focus {{
    border: 1px solid {colors.border_focus};
}}

QComboBox::drop-down {{
    border-left: 1px solid {colors.border};
    background-color: {colors.background_alt};
}}

QComboBox QAbstractItemView {{
    background-color: {colors.background_alt};
    color: {colors.foreground};
    selection-background-color: {colors.selection_bg};
    selection-color: {colors.selection_fg};
    border: 1px solid {colors.border};
}}

/* Check Boxes */
QCheckBox {{
    color: {colors.foreground};
    spacing: 8px;
}}

QCheckBox::indicator {{
    width: 18px;
    height: 18px;
    border: 1px solid {colors.input_border};
    border-radius: 3px;
    background-color: {colors.input_bg};
}}

QCheckBox::indicator:checked {{
    background-color: {colors.primary};
    border-color: {colors.primary};
}}

QCheckBox::indicator:hover {{
    border-color: {colors.primary_hover};
}}

/* Sliders */
QSlider::groove:horizontal {{
    height: 6px;
    background: {colors.background_alt};
    border: 1px solid {colors.border};
    border-radius: 3px;
}}

QSlider::handle:horizontal {{
    background: {colors.primary};
    border: 1px solid {colors.primary_hover};
    width: 16px;
    margin: -6px 0;
    border-radius: 8px;
}}

QSlider::handle:horizontal:hover {{
    background: {colors.primary_hover};
}}

/* Push Buttons */
QPushButton {{
    background-color: {colors.button_bg};
    color: white;
    border: none;
    border-radius: 4px;
    padding: 8px 16px;
    font-weight: bold;
}}

QPushButton:hover {{
    background-color: {colors.button_hover};
}}

QPushButton:pressed {{
    background-color: {colors.primary};
}}

QPushButton:disabled {{
    background-color: {colors.background_alt};
    color: {colors.foreground_dim};
}}

/* Status Bar */
QStatusBar {{
    background-color: {colors.background_alt};
    color: {colors.foreground};
    border-top: 1px solid {colors.border};
}}

/* Scroll Bars */
QScrollBar:vertical {{
    background: {colors.background_alt};
    width: 12px;
    border: none;
}}

QScrollBar::handle:vertical {{
    background: {colors.border};
    min-height: 20px;
    border-radius: 6px;
}}

QScrollBar::handle:vertical:hover {{
    background: {colors.primary};
}}

QScrollBar:horizontal {{
    background: {colors.background_alt};
    height: 12px;
    border: none;
}}

QScrollBar::handle:horizontal {{
    background: {colors.border};
    min-width: 20px;
    border-radius: 6px;
}}

QScrollBar::handle:horizontal:hover {{
    background: {colors.primary};
}}

/* Tool Tips */
QToolTip {{
    background-color: {colors.background_alt};
    color: {colors.foreground};
    border: 1px solid {colors.border};
    padding: 4px;
    border-radius: 3px;
}}

/* Message Boxes */
QMessageBox {{
    background-color: {colors.background};
}}

QMessageBox QLabel {{
    color: {colors.foreground};
}}

QMessageBox QPushButton {{
    min-width: 80px;
}}
"""
        return stylesheet


# Global theme manager instance
_theme_manager: Optional[ThemeManager] = None


def get_theme_manager() -> ThemeManager:
    """Get global theme manager instance (singleton)"""
    global _theme_manager
    if _theme_manager is None:
        _theme_manager = ThemeManager()
    return _theme_manager
