"""
Intel RealSense Control Panel.

Minimal info/status panel for RealSense depth+color cameras - unlike UVC/
Firefly there are no generic exposure/resolution controls exposed here
(RealSense's own auto-exposure/depth-processing options are sensor-level
and device-specific); this panel exists to show connection status and
make clear that depth data from this device is what feeds parallax
correction and the 3D Fusion view.
"""
from __future__ import annotations

import logging
from typing import Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QGridLayout, QGroupBox, QLabel, QScrollArea, QFrame
)
from PyQt6.QtGui import QFont

logger = logging.getLogger(__name__)


class RealSenseControlPanel(QWidget):
    """Info/status panel for an active Intel RealSense camera."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.event_bus = None
        self._build_ui()

    def set_event_bus(self, event_bus):
        self.event_bus = event_bus

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(10)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(12)

        info_grp = QGroupBox("RealSense Device")
        info_layout = QGridLayout(info_grp)
        info_layout.setContentsMargins(10, 10, 10, 10)
        info_layout.setSpacing(6)

        self.lbl_device_name = QLabel("Device: Not Connected")
        f = QFont(); f.setBold(True)
        self.lbl_device_name.setFont(f)
        info_layout.addWidget(self.lbl_device_name, 0, 0, 1, 2)

        self.lbl_res = QLabel("Resolution: —")
        info_layout.addWidget(self.lbl_res, 1, 0, 1, 2)

        layout.addWidget(info_grp)

        note = QLabel(
            "This device's real depth stream feeds parallax correction "
            "(set depth method to \"RealSense\" in the Parallax tab) and "
            "the 3D Fusion tab. No hardware controls are exposed here - "
            "RealSense auto-exposure and depth processing run on the "
            "device's own factory defaults."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color: #888888; font-size: 9pt; padding-top: 4px;")
        layout.addWidget(note)

        layout.addStretch()
        scroll.setWidget(container)
        root.addWidget(scroll)

    def update_camera_info(self, info: dict):
        """Update display when the camera connects."""
        name = info.get("model", "Intel RealSense")
        res = info.get("resolution", (0, 0))

        self.lbl_device_name.setText(f"Device: {name}")
        if res and res[0] and res[1]:
            self.lbl_res.setText(f"Resolution: {res[0]} × {res[1]}")
        else:
            self.lbl_res.setText("Resolution: (negotiating...)")
