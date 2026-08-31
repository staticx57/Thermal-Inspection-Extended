"""
Colorbar Widget for Thermal Inspection Tool
Phase 1 - Feature 2: Temperature Scale Display

Displays a colorbar/legend showing the current palette with temperature labels.
"""

from PyQt6.QtWidgets import QWidget
from PyQt6.QtGui import QPainter, QColor, QPen, QFont
from PyQt6.QtCore import Qt
import logging

logger = logging.getLogger(__name__)


class ColorbarWidget(QWidget):
    """
    Widget that displays a colorbar/legend with temperature scale.
    Shows the current thermal palette gradient with temperature labels.
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        # Palette data (256x3 BGR array)
        self.palette_lut = None

        # Temperature range
        self.temp_min = 0.0
        self.temp_max = 100.0
        self.unit = "°C"

        # Display settings
        self.position = "right"  # "right", "left", "top", "bottom"
        self.enabled = True
        self.bar_width = 30
        self.bar_height = 256
        self.tick_count = 5  # Number of temperature labels

        # Margins
        self.margin_left = 10
        self.margin_right = 60  # Extra space for temperature text
        self.margin_top = 10
        self.margin_bottom = 10

        # Styling
        self.background_alpha = 160  # Semi-transparent background
        self.text_color = QColor(255, 255, 255)
        self.font = QFont("Arial", 9)

        # Set widget properties
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setStyleSheet("background: transparent;")

        # Calculate size
        self._update_size()

    def _update_size(self):
        """Update widget size based on position and settings."""
        if self.position in ["right", "left"]:
            width = self.margin_left + self.bar_width + self.margin_right
            height = self.margin_top + self.bar_height + self.margin_bottom
        else:  # top or bottom
            width = self.margin_left + self.bar_height + self.margin_right
            height = self.margin_top + self.bar_width + self.margin_bottom

        self.setFixedSize(width, height)

    def set_palette_lut(self, palette_lut):
        """
        Set the palette lookup table.

        Args:
            palette_lut: numpy array of shape (256, 3) with BGR values
        """
        if palette_lut is not None and palette_lut.shape == (256, 3):
            self.palette_lut = palette_lut.copy()
            self.update()
        else:
            logger.warning(f"Invalid palette LUT shape: {palette_lut.shape if palette_lut is not None else None}")

    def set_temperature_range(self, temp_min: float, temp_max: float, unit: str = "°C"):
        """
        Set the temperature range for the colorbar.

        Args:
            temp_min: Minimum temperature
            temp_max: Maximum temperature
            unit: Temperature unit string
        """
        self.temp_min = temp_min
        self.temp_max = temp_max
        self.unit = unit
        self.update()

    def set_enabled(self, enabled: bool):
        """Enable or disable colorbar display."""
        self.enabled = enabled
        self.setVisible(enabled)

    def set_position(self, position: str):
        """
        Set colorbar position.

        Args:
            position: One of "right", "left", "top", "bottom"
        """
        if position in ["right", "left", "top", "bottom"]:
            self.position = position
            self._update_size()
            self.update()

    def paintEvent(self, event):
        """Draw the colorbar with temperature labels."""
        if not self.enabled or self.palette_lut is None:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setFont(self.font)

        # Draw semi-transparent background
        painter.setBrush(QColor(0, 0, 0, self.background_alpha))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRect(self.rect())

        if self.position in ["right", "left"]:
            self._draw_vertical_colorbar(painter)
        else:
            self._draw_horizontal_colorbar(painter)

    def _draw_vertical_colorbar(self, painter):
        """Draw vertical colorbar (for right/left positions)."""
        # Calculate bar rectangle
        bar_x = self.margin_left
        bar_y = self.margin_top
        bar_w = self.bar_width
        bar_h = self.bar_height

        # Draw gradient bar (256 horizontal lines, one per palette entry)
        for i in range(256):
            # Palette index (invert so hot is at top)
            palette_idx = 255 - i

            # Get color from palette LUT (BGR format)
            if palette_idx < len(self.palette_lut):
                b, g, r = self.palette_lut[palette_idx]
                color = QColor(int(r), int(g), int(b))
            else:
                color = QColor(128, 128, 128)  # Gray fallback

            # Calculate y position
            y = bar_y + int((i / 256.0) * bar_h)

            # Draw 1-pixel high line
            painter.setPen(QPen(color, 1))
            painter.drawLine(bar_x, y, bar_x + bar_w, y)

        # Draw border around bar
        painter.setPen(QPen(QColor(255, 255, 255, 180), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(bar_x, bar_y, bar_w, bar_h)

        # Draw temperature ticks and labels
        painter.setPen(QPen(self.text_color, 1))

        for i in range(self.tick_count):
            # Calculate fraction (0.0 to 1.0)
            frac = i / (self.tick_count - 1)

            # Calculate temperature (hot at top, cold at bottom)
            temp = self.temp_max - frac * (self.temp_max - self.temp_min)

            # Calculate y position
            y = bar_y + int(frac * bar_h)

            # Draw tick mark
            tick_x1 = bar_x + bar_w
            tick_x2 = tick_x1 + 5
            painter.drawLine(tick_x1, y, tick_x2, y)

            # Draw temperature label
            if abs(temp) >= 100:
                temp_text = f"{temp:.0f}{self.unit}"
            elif abs(temp) >= 10:
                temp_text = f"{temp:.1f}{self.unit}"
            else:
                temp_text = f"{temp:.1f}{self.unit}"

            text_x = tick_x2 + 3
            text_y = y + 4  # Slight offset to center text
            painter.drawText(text_x, text_y, temp_text)

    def _draw_horizontal_colorbar(self, painter):
        """Draw horizontal colorbar (for top/bottom positions)."""
        # Calculate bar rectangle
        bar_x = self.margin_left
        bar_y = self.margin_top
        bar_w = self.bar_height  # Swap width/height for horizontal
        bar_h = self.bar_width

        # Draw gradient bar (256 vertical lines, one per palette entry)
        for i in range(256):
            # Palette index (cold on left, hot on right)
            palette_idx = i

            # Get color from palette LUT (BGR format)
            if palette_idx < len(self.palette_lut):
                b, g, r = self.palette_lut[palette_idx]
                color = QColor(int(r), int(g), int(b))
            else:
                color = QColor(128, 128, 128)  # Gray fallback

            # Calculate x position
            x = bar_x + int((i / 256.0) * bar_w)

            # Draw 1-pixel wide line
            painter.setPen(QPen(color, 1))
            painter.drawLine(x, bar_y, x, bar_y + bar_h)

        # Draw border around bar
        painter.setPen(QPen(QColor(255, 255, 255, 180), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(bar_x, bar_y, bar_w, bar_h)

        # Draw temperature ticks and labels
        painter.setPen(QPen(self.text_color, 1))

        for i in range(self.tick_count):
            # Calculate fraction (0.0 to 1.0)
            frac = i / (self.tick_count - 1)

            # Calculate temperature (cold on left, hot on right)
            temp = self.temp_min + frac * (self.temp_max - self.temp_min)

            # Calculate x position
            x = bar_x + int(frac * bar_w)

            # Draw tick mark
            tick_y1 = bar_y + bar_h
            tick_y2 = tick_y1 + 5
            painter.drawLine(x, tick_y1, x, tick_y2)

            # Draw temperature label (rotated or horizontal)
            if abs(temp) >= 100:
                temp_text = f"{temp:.0f}{self.unit}"
            elif abs(temp) >= 10:
                temp_text = f"{temp:.1f}{self.unit}"
            else:
                temp_text = f"{temp:.1f}{self.unit}"

            # Center text horizontally
            font_metrics = painter.fontMetrics()
            text_width = font_metrics.horizontalAdvance(temp_text)
            text_x = x - text_width // 2
            text_y = tick_y2 + font_metrics.height()
            painter.drawText(text_x, text_y, temp_text)
