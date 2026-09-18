"""
Intel RealSense Control Panel.

Shows connection diagnostics (serial, firmware, USB type, product line,
depth scale, computed FOV - all read from the actual connected device, not
guessed) and exposes whatever depth-sensor options the device reports
supporting (e.g. IR emitter, laser power) via generic camera commands.
"""
from __future__ import annotations

import logging
from typing import Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QGridLayout, QGroupBox, QLabel, QScrollArea, QFrame,
    QSlider, QCheckBox, QComboBox
)
from PyQt6.QtGui import QFont
from PyQt6.QtCore import Qt, pyqtSignal

logger = logging.getLogger(__name__)


class RealSenseControlPanel(QWidget):
    """Info/status + depth-sensor option panel for an active Intel RealSense camera."""

    command_requested = pyqtSignal(str, dict)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._block_signals = False
        self._option_widgets: dict = {}  # option_name -> (widget, kind)
        self._color_option_widgets: dict = {}  # option_name -> (widget, kind)
        self._build_ui()

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
        self.info_layout = QGridLayout(info_grp)
        self.info_layout.setContentsMargins(10, 10, 10, 10)
        self.info_layout.setSpacing(6)

        self.lbl_device_name = QLabel("Device: Not Connected")
        f = QFont(); f.setBold(True)
        self.lbl_device_name.setFont(f)
        self.info_layout.addWidget(self.lbl_device_name, 0, 0, 1, 2)

        self.lbl_res = QLabel("Resolution: —")
        self.info_layout.addWidget(self.lbl_res, 1, 0, 1, 2)

        # Populated only when the connected device actually reports them
        # (device.supports(field) checked in RGBCameraRealSense.get_info) -
        # a field that never appears here means this device/firmware
        # doesn't expose it, not that something failed to load.
        self.lbl_serial = QLabel("Serial: —")
        self.info_layout.addWidget(self.lbl_serial, 2, 0, 1, 2)
        self.lbl_firmware = QLabel("Firmware: —")
        self.info_layout.addWidget(self.lbl_firmware, 3, 0, 1, 2)
        self.lbl_usb = QLabel("USB: —")
        self.info_layout.addWidget(self.lbl_usb, 4, 0)
        self.lbl_product_line = QLabel("Line: —")
        self.info_layout.addWidget(self.lbl_product_line, 4, 1)
        self.lbl_depth_scale = QLabel("Depth scale: —")
        self.info_layout.addWidget(self.lbl_depth_scale, 5, 0, 1, 2)
        self.lbl_fov = QLabel("FOV: —")
        self.info_layout.addWidget(self.lbl_fov, 6, 0, 1, 2)

        layout.addWidget(info_grp)

        # Built dynamically in update_depth_sensor_options()/
        # update_color_sensor_options() from whatever the connected device
        # actually reports supporting via get_supported_options() - never a
        # hardcoded list, so no control here can offer a setting the
        # attached device doesn't really have.
        self.options_grp = QGroupBox("Depth Sensor Options")
        self.options_layout = QGridLayout(self.options_grp)
        self.options_layout.setContentsMargins(10, 10, 10, 10)
        self.options_layout.setSpacing(6)
        self._options_empty_label = QLabel("No options reported yet - connect a device.")
        self._options_empty_label.setStyleSheet("color: #888888; font-size: 9pt;")
        self.options_layout.addWidget(self._options_empty_label, 0, 0, 1, 3)
        layout.addWidget(self.options_grp)

        self.color_options_grp = QGroupBox("Color Sensor Options")
        self.color_options_layout = QGridLayout(self.color_options_grp)
        self.color_options_layout.setContentsMargins(10, 10, 10, 10)
        self.color_options_layout.setSpacing(6)
        self._color_options_empty_label = QLabel("No options reported yet - connect a device.")
        self._color_options_empty_label.setStyleSheet("color: #888888; font-size: 9pt;")
        self.color_options_layout.addWidget(self._color_options_empty_label, 0, 0, 1, 3)
        layout.addWidget(self.color_options_grp)

        # Depth post-processing: all off by default (matches the device's
        # own out-of-the-box state) - spatial/temporal smoothing and
        # hole-filling trade a small amount of edge sharpness/latency for
        # less noisy depth, which parallax correction and 3D Fusion both
        # consume directly.
        filter_grp = QGroupBox("Depth Post-Processing")
        filter_layout = QVBoxLayout(filter_grp)
        self.spatial_filter_chk = QCheckBox("Spatial Filter (edge-preserving smoothing)")
        self.spatial_filter_chk.toggled.connect(lambda c: self._on_depth_filter_toggled("spatial", c))
        filter_layout.addWidget(self.spatial_filter_chk)
        self.temporal_filter_chk = QCheckBox("Temporal Filter (reduces frame-to-frame flicker)")
        self.temporal_filter_chk.toggled.connect(lambda c: self._on_depth_filter_toggled("temporal", c))
        filter_layout.addWidget(self.temporal_filter_chk)
        self.hole_filling_filter_chk = QCheckBox("Hole Filling (fills invalid/occluded depth pixels)")
        self.hole_filling_filter_chk.toggled.connect(lambda c: self._on_depth_filter_toggled("hole_filling", c))
        filter_layout.addWidget(self.hole_filling_filter_chk)
        layout.addWidget(filter_grp)

        note = QLabel(
            "Real depth from this device feeds parallax correction "
            "(set depth method to \"RealSense\" in the Parallax tab) and "
            "the 3D Fusion tab. Auto-exposure and other sensor-level "
            "options not listed above run on the device's own defaults."
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

        if 'serial_number' in info:
            self.lbl_serial.setText(f"Serial: {info['serial_number']}")
        if 'firmware_version' in info:
            self.lbl_firmware.setText(f"Firmware: {info['firmware_version']}")
        if 'usb_type' in info:
            self.lbl_usb.setText(f"USB: {info['usb_type']}")
        if 'product_line' in info:
            self.lbl_product_line.setText(f"Line: {info['product_line']}")
        if 'depth_scale_m' in info:
            self.lbl_depth_scale.setText(f"Depth scale: {info['depth_scale_m'] * 1000:.3f} mm/unit")
        if 'horizontal_fov_deg' in info:
            v_fov = info.get('vertical_fov_deg')
            fov_text = f"FOV: {info['horizontal_fov_deg']:.1f}° H"
            if v_fov:
                fov_text += f" × {v_fov:.1f}° V"
            self.lbl_fov.setText(fov_text)

    def update_depth_sensor_options(self, options: dict):
        """(Re)build the Depth Sensor Options section - see _populate_option_grid()."""
        self._populate_option_grid(
            self.options_layout, self._option_widgets, options,
            self._options_empty_label, "set_depth_sensor_option"
        )

    def update_color_sensor_options(self, options: dict):
        """(Re)build the Color Sensor Options section - see _populate_option_grid()."""
        self._populate_option_grid(
            self.color_options_layout, self._color_option_widgets, options,
            self._color_options_empty_label, "set_color_sensor_option"
        )

    def _populate_option_grid(self, grid_layout: QGridLayout, widgets_dict: dict,
                               options: dict, empty_label: QLabel, command: str):
        """
        (Re)build one options section from the device's actually-supported
        options - each entry is {'value','min','max','step','default'} plus
        an optional 'enum_names' ({int: display name}) for options like
        visual_preset that are really a small named set, not a continuum.
        Bool-like ranges (0-1, step 1) get a checkbox; an entry with
        enum_names gets a named dropdown; everything else gets a slider.
        """
        if not options:
            return

        # Clear any previous controls (e.g. a different device reconnected
        # with a different option set) before rebuilding.
        while grid_layout.count():
            item = grid_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        widgets_dict.clear()
        empty_label.setParent(None)

        self._block_signals = True
        try:
            for row, (name, spec) in enumerate(sorted(options.items())):
                label_text = name.replace('_', ' ').title()
                is_bool_like = (spec['min'] == 0 and spec['max'] == 1 and spec['step'] == 1)
                enum_names = spec.get('enum_names')

                if enum_names:
                    grid_layout.addWidget(QLabel(f"{label_text}:"), row, 0)
                    combo = QComboBox()
                    current_index = 0
                    for i, (enum_val, enum_label) in enumerate(sorted(enum_names.items())):
                        combo.addItem(enum_label, enum_val)
                        if enum_val == int(spec['value']):
                            current_index = i
                    combo.setCurrentIndex(current_index)
                    combo.currentIndexChanged.connect(
                        lambda idx, n=name, c=combo, cmd=command: self._on_option_changed(n, float(c.itemData(idx)), cmd)
                    )
                    grid_layout.addWidget(combo, row, 1, 1, 2)
                    widgets_dict[name] = (combo, 'enum')
                elif is_bool_like:
                    chk = QCheckBox(label_text)
                    chk.setChecked(bool(spec['value']))
                    chk.toggled.connect(
                        lambda checked, n=name, cmd=command: self._on_option_changed(n, 1.0 if checked else 0.0, cmd)
                    )
                    grid_layout.addWidget(chk, row, 0, 1, 3)
                    widgets_dict[name] = (chk, 'bool')
                else:
                    grid_layout.addWidget(QLabel(f"{label_text}:"), row, 0)
                    slider = QSlider(Qt.Orientation.Horizontal)
                    step = spec['step'] if spec['step'] > 0 else 1
                    slider.setRange(int(spec['min'] / step), int(spec['max'] / step))
                    slider.setValue(int(round(spec['value'] / step)))
                    val_label = QLabel(str(spec['value']))
                    val_label.setFixedWidth(48)
                    slider.valueChanged.connect(
                        lambda idx, n=name, s=step, lbl=val_label, cmd=command: self._on_slider_changed(n, s, idx, lbl, cmd)
                    )
                    grid_layout.addWidget(slider, row, 1)
                    grid_layout.addWidget(val_label, row, 2)
                    widgets_dict[name] = (slider, 'range')
        finally:
            self._block_signals = False

    def _on_slider_changed(self, name: str, step: float, index: int, label: QLabel, command: str):
        value = index * step
        label.setText(str(value))
        if not self._block_signals:
            self._on_option_changed(name, value, command)

    def _on_option_changed(self, option_name: str, value: float, command: str):
        if self._block_signals:
            return
        # Found during a general audit: this panel had no
        # command_requested signal at all, only a self.event_bus/
        # set_event_bus() path that nothing ever called - every
        # depth-sensor option change here silently did nothing, with no
        # error or log. command_requested is the same signal every other
        # camera-control panel uses; main_window.py's _wire_plugin_panel()
        # already generically connects it (hasattr(panel,
        # 'command_requested')) for whichever role this plugin actually
        # has, so no wiring change was needed there.
        self.command_requested.emit(
            command, {"option": option_name, "value": value}
        )

    def update_depth_filter_state(self, filters: dict):
        """Sync the post-processing checkboxes to the backend's current state."""
        self._block_signals = True
        try:
            if 'spatial' in filters:
                self.spatial_filter_chk.setChecked(bool(filters['spatial']))
            if 'temporal' in filters:
                self.temporal_filter_chk.setChecked(bool(filters['temporal']))
            if 'hole_filling' in filters:
                self.hole_filling_filter_chk.setChecked(bool(filters['hole_filling']))
        finally:
            self._block_signals = False

    def _on_depth_filter_toggled(self, filter_name: str, checked: bool):
        if self._block_signals:
            return
        self.command_requested.emit(
            "set_depth_filter_enabled", {"filter": filter_name, "enabled": checked}
        )
