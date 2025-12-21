"""
Info panel widget for displaying inspection status overlay.
"""

from PyQt6.QtWidgets import QLabel
from PyQt6.QtCore import Qt


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
