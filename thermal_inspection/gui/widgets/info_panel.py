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
        # The HUD sits ON the video, so it must be readable on any frame whatever the app theme is: fixed dark pill with
        # light text (the themes' green-on-translucent variants went dark-green-on-black and were hard to read).
        self.setStyleSheet("QLabel#info_panel { background-color: rgba(10, 12, 16, 205); color: #e8eef0; "
                           "border: 1px solid #5b6570; border-radius: 5px; padding: 8px 10px; "
                           "font-size: 9pt; font-family: monospace; }")
        self.setFixedSize(300, 70)  # Increased width for better text display
        self.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.setWordWrap(True)
        self.setToolTip("FPS: frames the camera is delivering.  Loop: how fast the processing loop is running "
                        "(its capacity - it can be far above the camera's rate).")

    def update_info(self, fps: float, roi_count: int, thermal_connected: bool, rgb_connected: bool, recording: bool = False,
                    loop_fps: float = None):
        """Update inspection status information. `fps` is the CAMERA frame rate (frames actually arriving); `loop_fps`,
        when given, is how fast the processing loop is running (its capacity, often far above the camera's rate), shown
        beside it. The dot says whether frames are arriving, not whether the rate is "good": a radiometric
        Boson at 9 Hz is healthy, and the old 25/15 fps thresholds painted it red."""
        if fps > 0:
            quality = '<span style="color:#6fdc8c">&#9679;</span> '      # frames arriving
        else:
            quality = '<span style="color:#8a929a">&#9679;</span> '      # nothing arriving
        self.setTextFormat(Qt.TextFormat.RichText)

        # Connection status
        thermal_status = "✓" if thermal_connected else "✗"
        rgb_status = "✓" if rgb_connected else "✗"

        # Recording indicator
        rec_indicator = " [⏺ REC]" if recording else ""

        loop_text = f"  &middot;  Loop: {loop_fps:.0f}" if loop_fps else ""
        info_text = (
            f"{quality}FPS: {fps:.1f}{loop_text}{rec_indicator}<br>"
            f"ROIs: {roi_count}<br>"
            f"Thermal:{thermal_status} RGB:{rgb_status}"
        )

        self.setText(info_text)
