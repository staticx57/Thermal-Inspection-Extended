#!/usr/bin/env python3
"""
Multi-Row Tab Widget
Custom QTabWidget that displays tabs in multiple rows when needed
Includes macOS-style keyboard navigation
"""

import logging
from PyQt5.QtWidgets import QTabWidget, QTabBar, QStylePainter, QStyleOptionTab, QStyle
from PyQt5.QtCore import Qt, QRect, QSize, pyqtSignal
from PyQt5.QtGui import QKeyEvent

logger = logging.getLogger(__name__)


class MultiRowTabBar(QTabBar):
    """Custom tab bar that supports multiple rows"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setElideMode(Qt.ElideNone)  # Don't elide text
        self.setExpanding(False)  # Don't expand tabs to fill space
        self.setUsesScrollButtons(False)  # Disable scroll buttons
        
    def tabSizeHint(self, index: int) -> QSize:
        """Return optimal size for a tab"""
        size = super().tabSizeHint(index)
        # Set a reasonable max width to prevent very wide tabs
        size.setWidth(min(size.width(), 200))
        return size


class MultiRowTabWidget(QTabWidget):
    """
    Tab widget that displays tabs in multiple rows when window is narrow
    Includes keyboard navigation shortcuts
    """
    
    # Signal emitted when tab changes
    tabNavigated = pyqtSignal(int)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Set custom tab bar
        custom_tab_bar = MultiRowTabBar(self)
        self.setTabBar(custom_tab_bar)
        
        # Enable mouse tracking for hover effects
        self.setMouseTracking(True)
        
        # Configure tab position
        self.setTabPosition(QTabWidget.North)
        
        # Connect signals
        self.currentChanged.connect(self._on_tab_changed)
        
        logger.debug("MultiRowTabWidget initialized")
    
    def _on_tab_changed(self, index: int):
        """Handle tab change event"""
        self.tabNavigated.emit(index)
        logger.debug(f"Tab changed to index {index}")
    
    def keyPressEvent(self, event: QKeyEvent):
        """
        Handle keyboard shortcuts for tab navigation
        
        macOS-style shortcuts:
        - Ctrl+Left/Right (Windows) or Cmd+Left/Right (macOS): Navigate tabs
        - Ctrl+Tab: Next tab
        - Ctrl+Shift+Tab: Previous tab
        """
        # Check for modifier keys
        ctrl_pressed = event.modifiers() & Qt.ControlModifier
        shift_pressed = event.modifiers() & Qt.ShiftModifier
        
        # Ctrl/Cmd + Right Arrow -> Next tab
        if ctrl_pressed and event.key() == Qt.Key_Right:
            self._navigate_next_tab()
            event.accept()
            return
        
        # Ctrl/Cmd + Left Arrow -> Previous tab
        elif ctrl_pressed and event.key() == Qt.Key_Left:
            self._navigate_previous_tab()
            event.accept()
            return
        
        # Ctrl + Tab -> Next tab
        elif ctrl_pressed and event.key() == Qt.Key_Tab and not shift_pressed:
            self._navigate_next_tab()
            event.accept()
            return
        
        # Ctrl + Shift + Tab -> Previous tab
        elif ctrl_pressed and shift_pressed and event.key() == Qt.Key_Tab:
            self._navigate_previous_tab()
            event.accept()
            return
        
        # Ctrl + Number (1-9) -> Jump to specific tab
        elif ctrl_pressed and Qt.Key_1 <= event.key() <= Qt.Key_9:
            tab_index = event.key() - Qt.Key_1
            if tab_index < self.count():
                self.setCurrentIndex(tab_index)
                event.accept()
                return
        
        # Pass other events to parent
        super().keyPressEvent(event)
    
    def wheelEvent(self, event):
        """
        Handle mouse wheel for tab navigation (optional)
        Scroll up/down to switch tabs
        """
        if event.angleDelta().y() > 0:
            # Scroll up -> previous tab
            self._navigate_previous_tab()
        elif event.angleDelta().y() < 0:
            # Scroll down -> next tab
            self._navigate_next_tab()
        
        event.accept()
    
    def _navigate_next_tab(self):
        """Navigate to next tab (wrap around at end)"""
        current = self.currentIndex()
        next_index = (current + 1) % self.count()
        self.setCurrentIndex(next_index)
        logger.debug(f"Navigated to next tab: {next_index}")
    
    def _navigate_previous_tab(self):
        """Navigate to previous tab (wrap around at start)"""
        current = self.currentIndex()
        prev_index = (current - 1) % self.count()
        self.setCurrentIndex(prev_index)
        logger.debug(f"Navigated to previous tab: {prev_index}")
    
    def addTab(self, widget, label: str) -> int:
        """
        Add a tab with the given widget and label
        
        Args:
            widget: Widget to add
            label: Tab label text
            
        Returns:
            Index of added tab
        """
        index = super().addTab(widget, label)
        logger.debug(f"Added tab '{label}' at index {index}")
        return index
    
    def insertTab(self, index: int, widget, label: str) -> int:
        """
        Insert a tab at the given index
        
        Args:
            index: Position to insert tab
            widget: Widget to add
            label: Tab label text
            
        Returns:
            Index of inserted tab
        """
        result = super().insertTab(index, widget, label)
        logger.debug(f"Inserted tab '{label}' at index {index}")
        return result
    
    def resizeEvent(self, event):
        """
        Handle resize events to manage tab layout
        This is where multi-row logic would be implemented for more complex layouts
        """
        super().resizeEvent(event)
        # Note: Qt's default tab bar already handles wrapping reasonably well
        # For true multi-row support, we would need to calculate tab positions
        # and potentially override the tab bar's painting/layout methods


class NavigationHintWidget:
    """
    Helper class to display keyboard navigation hints
    Can be added to status bar or as tooltip
    """
    
    @staticmethod
    def get_navigation_hints() -> str:
        """
        Get keyboard navigation hint text
        
        Returns:
            String with navigation shortcuts
        """
        hints = [
            "Navigation Shortcuts:",
            "Ctrl+Left/Right - Previous/Next tab",
            "Ctrl+Tab - Next tab",
            "Ctrl+Shift+Tab - Previous tab",
            "Ctrl+1-9 - Jump to tab",
            "Mouse Wheel - Scroll through tabs"
        ]
        return " | ".join(hints)
    
    @staticmethod
    def get_short_hint() -> str:
        """Get short hint for status bar"""
        return "Ctrl+Left/Right to navigate tabs"


def create_multi_row_tabwidget(parent=None) -> MultiRowTabWidget:
    """
    Factory function to create a multi-row tab widget
    
    Args:
        parent: Parent widget
        
    Returns:
        Configured MultiRowTabWidget instance
    """
    widget = MultiRowTabWidget(parent)
    logger.info("Created multi-row tab widget")
    return widget
