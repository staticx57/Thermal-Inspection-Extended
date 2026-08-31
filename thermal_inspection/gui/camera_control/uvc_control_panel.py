"""
UVC Webcam Control Panel.

Provides standard camera adjustments (resolution, exposure, brightness,
contrast, saturation, focus, sharpness) for USB webcams and built-in cameras.
"""
from __future__ import annotations

import logging
from typing import Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox,
    QLabel, QPushButton, QComboBox, QSlider, QCheckBox, QScrollArea, QFrame
)
from PyQt6.QtGui import QFont

logger = logging.getLogger(__name__)


class UVCControlPanel(QWidget):
    """
    Dedicated control panel for Generic USB / UVC Webcams.
    """
    command_requested = pyqtSignal(str, dict)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.event_bus = None
        self._block_signals = False
        self._build_ui()

    def set_event_bus(self, event_bus):
        """Attach event bus to broadcast commands."""
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

        # 1. Device Info Card
        info_grp = QGroupBox("Webcam Info")
        info_layout = QGridLayout(info_grp)
        info_layout.setContentsMargins(10, 10, 10, 10)
        info_layout.setSpacing(6)

        self.lbl_device_name = QLabel("Device: Not Connected")
        f = QFont(); f.setBold(True)
        self.lbl_device_name.setFont(f)
        info_layout.addWidget(self.lbl_device_name, 0, 0, 1, 2)

        self.lbl_res = QLabel("Resolution: —")
        self.lbl_fps = QLabel("FPS: —")
        info_layout.addWidget(self.lbl_res, 1, 0)
        info_layout.addWidget(self.lbl_fps, 1, 1)

        layout.addWidget(info_grp)

        # 2. Resolution & Stream Settings
        res_grp = QGroupBox("Stream Resolution")
        res_layout = QHBoxLayout(res_grp)
        res_layout.setContentsMargins(10, 10, 10, 10)

        res_layout.addWidget(QLabel("Preset:"))
        self.res_combo = QComboBox()
        self.res_combo.addItem("640 × 480 (VGA)", (640, 480))
        self.res_combo.addItem("1280 × 720 (720p HD)", (1280, 720))
        self.res_combo.addItem("1920 × 1080 (1080p Full HD)", (1920, 1080))
        self.res_combo.addItem("2560 × 1440 (2K QHD)", (2560, 1440))
        self.res_combo.addItem("3840 × 2160 (4K UHD)", (3840, 2160))
        self.res_combo.currentIndexChanged.connect(self._on_resolution_changed)
        res_layout.addWidget(self.res_combo, 1)

        layout.addWidget(res_grp)

        # 3. Image Controls (Brightness, Contrast, Saturation, Sharpness)
        img_grp = QGroupBox("Image Adjustments")
        img_layout = QGridLayout(img_grp)
        img_layout.setContentsMargins(10, 10, 10, 10)
        img_layout.setSpacing(8)

        # Brightness
        img_layout.addWidget(QLabel("Brightness:"), 0, 0)
        self.slider_brightness, self.lbl_brightness_val = self._make_slider(0, 255, 128, lambda v: self._emit_prop("brightness", v))
        img_layout.addWidget(self.slider_brightness, 0, 1)
        img_layout.addWidget(self.lbl_brightness_val, 0, 2)

        # Contrast
        img_layout.addWidget(QLabel("Contrast:"), 1, 0)
        self.slider_contrast, self.lbl_contrast_val = self._make_slider(0, 255, 128, lambda v: self._emit_prop("contrast", v))
        img_layout.addWidget(self.slider_contrast, 1, 1)
        img_layout.addWidget(self.lbl_contrast_val, 1, 2)

        # Saturation
        img_layout.addWidget(QLabel("Saturation:"), 2, 0)
        self.slider_saturation, self.lbl_saturation_val = self._make_slider(0, 255, 128, lambda v: self._emit_prop("saturation", v))
        img_layout.addWidget(self.slider_saturation, 2, 1)
        img_layout.addWidget(self.lbl_saturation_val, 2, 2)

        # Sharpness
        img_layout.addWidget(QLabel("Sharpness:"), 3, 0)
        self.slider_sharpness, self.lbl_sharpness_val = self._make_slider(0, 255, 128, lambda v: self._emit_prop("sharpness", v))
        img_layout.addWidget(self.slider_sharpness, 3, 1)
        img_layout.addWidget(self.lbl_sharpness_val, 3, 2)

        layout.addWidget(img_grp)

        # 4. Exposure & Focus
        exp_grp = QGroupBox("Exposure & Focus")
        exp_layout = QGridLayout(exp_grp)
        exp_layout.setContentsMargins(10, 10, 10, 10)
        exp_layout.setSpacing(8)

        self.chk_auto_exposure = QCheckBox("Auto Exposure")
        self.chk_auto_exposure.setChecked(True)
        self.chk_auto_exposure.toggled.connect(self._on_auto_exposure_toggled)
        exp_layout.addWidget(self.chk_auto_exposure, 0, 0, 1, 3)

        exp_layout.addWidget(QLabel("Exposure:"), 1, 0)
        self.slider_exposure, self.lbl_exposure_val = self._make_slider(-13, 0, -6, lambda v: self._emit_prop("exposure", v))
        self.slider_exposure.setEnabled(False)
        exp_layout.addWidget(self.slider_exposure, 1, 1)
        exp_layout.addWidget(self.lbl_exposure_val, 1, 2)

        self.chk_auto_focus = QCheckBox("Auto Focus")
        self.chk_auto_focus.setChecked(True)
        self.chk_auto_focus.toggled.connect(self._on_auto_focus_toggled)
        exp_layout.addWidget(self.chk_auto_focus, 2, 0, 1, 3)

        exp_layout.addWidget(QLabel("Focus:"), 3, 0)
        self.slider_focus, self.lbl_focus_val = self._make_slider(0, 255, 0, lambda v: self._emit_prop("focus", v))
        self.slider_focus.setEnabled(False)
        exp_layout.addWidget(self.slider_focus, 3, 1)
        exp_layout.addWidget(self.lbl_focus_val, 3, 2)

        layout.addWidget(exp_grp)

        # 5. Reset button
        btn_reset = QPushButton("Reset to Defaults")
        btn_reset.clicked.connect(self._on_reset_defaults)
        layout.addWidget(btn_reset)

        layout.addStretch()
        scroll.setWidget(container)
        root.addWidget(scroll)

    def _make_slider(self, min_val: int, max_val: int, def_val: int, on_change) -> tuple[QSlider, QLabel]:
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(min_val, max_val)
        slider.setValue(def_val)

        lbl = QLabel(str(def_val))
        lbl.setFixedWidth(36)
        lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        def handler(val):
            lbl.setText(str(val))
            if not self._block_signals:
                on_change(val)

        slider.valueChanged.connect(handler)
        return slider, lbl

    def _on_resolution_changed(self, idx: int):
        res = self.res_combo.itemData(idx)
        if res and not self._block_signals:
            self._emit_command("set_resolution", {"width": res[0], "height": res[1]})

    def _on_auto_exposure_toggled(self, checked: bool):
        self.slider_exposure.setEnabled(not checked)
        self._emit_command("set_auto_exposure", {"enabled": checked})

    def _on_auto_focus_toggled(self, checked: bool):
        self.slider_focus.setEnabled(not checked)
        self._emit_command("set_auto_focus", {"enabled": checked})

    def _on_reset_defaults(self):
        self._block_signals = True
        try:
            self.slider_brightness.setValue(128)
            self.slider_contrast.setValue(128)
            self.slider_saturation.setValue(128)
            self.slider_sharpness.setValue(128)
            self.chk_auto_exposure.setChecked(True)
            self.chk_auto_focus.setChecked(True)
        finally:
            self._block_signals = False
        self._emit_command("reset_defaults", {})

    def _emit_prop(self, prop_name: str, value: int):
        self._emit_command("set_property", {"property": prop_name, "value": value})

    def _emit_command(self, command: str, params: dict):
        self.command_requested.emit(command, params)
        if self.event_bus:
            self.event_bus.camera_command_requested.emit("rgb", command, params)

    def update_camera_info(self, info: dict):
        """Update display when camera connects."""
        name = info.get("name", info.get("model", "USB Webcam"))
        res = info.get("resolution", (640, 480))
        fps = info.get("fps", 30)

        self.lbl_device_name.setText(f"Device: {name}")
        self.lbl_res.setText(f"Resolution: {res[0]} × {res[1]}")
        self.lbl_fps.setText(f"FPS: {fps}")

        # Sync combo if matching preset found
        self._block_signals = True
        try:
            for i in range(self.res_combo.count()):
                if self.res_combo.itemData(i) == tuple(res):
                    self.res_combo.setCurrentIndex(i)
                    break
        finally:
            self._block_signals = False
