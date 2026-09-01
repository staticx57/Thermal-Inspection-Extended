"""
FLIR Tau 2 Camera Control Panel Widget.

Provides full GUI controls for FLIR / Teledyne Tau 2 thermal cameras:
- Serial connection setup (COM port & baud rate selection)
- Flat Field Correction (FFC / NUC) trigger & mode
- Sensor gain mode (High / Low / Auto / Manual)
- Color LUT / Palette selection
- Advanced Radiometry T-Linear configuration
- FPA & Housing temperature readout
"""
from __future__ import annotations

import logging
from typing import Dict, Any

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox,
    QLabel, QPushButton, QComboBox, QCheckBox, QTabWidget, QRadioButton
)

logger = logging.getLogger(__name__)


class Tau2ControlPanel(QWidget):
    """FLIR Tau 2 camera control panel widget."""

    # Outgoing signals (routed to AppEventBus camera_command_requested)
    connect_requested = pyqtSignal(str, int)          # (com_port, baud_rate)
    disconnect_requested = pyqtSignal()
    scan_ports_requested = pyqtSignal()
    ffc_triggered = pyqtSignal()
    gain_mode_changed = pyqtSignal(str)              # 'high', 'low', 'auto', 'manual'
    ffc_mode_changed = pyqtSignal(str)               # 'manual', 'auto', 'external'
    color_lut_changed = pyqtSignal(str)              # LUT name
    tlinear_toggled = pyqtSignal(bool, str)          # (enabled, 'high'|'low')
    shutter_position_changed = pyqtSignal(str)       # 'open', 'closed'
    fpa_temp_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()
        self._connect_signals()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)

        self._create_connection_tab()
        self._create_controls_tab()
        self._create_radiometric_tab()
        self._create_diagnostics_tab()

    def _create_connection_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(8)

        # Connection Box
        grp = QGroupBox("Tau 2 Serial Connection")
        g_layout = QGridLayout(grp)

        g_layout.addWidget(QLabel("COM Port:"), 0, 0)
        self.com_combo = QComboBox()
        self.com_combo.setEditable(True)
        self.com_combo.addItems(["COM3", "COM4", "COM5", "COM6", "COM7", "COM8"])
        g_layout.addWidget(self.com_combo, 0, 1)

        self.scan_btn = QPushButton("Scan Ports")
        g_layout.addWidget(self.scan_btn, 0, 2)

        g_layout.addWidget(QLabel("Baud Rate:"), 1, 0)
        self.baud_combo = QComboBox()
        self.baud_combo.addItems(["57600", "9600", "19200", "38400", "115200", "921600"])
        self.baud_combo.setCurrentText("57600")
        g_layout.addWidget(self.baud_combo, 1, 1)

        btn_box = QHBoxLayout()
        self.connect_btn = QPushButton("Connect Serial")
        self.connect_btn.setStyleSheet("font-weight: bold; background-color: #4CAF50; color: white;")
        self.disconnect_btn = QPushButton("Disconnect")
        self.disconnect_btn.setEnabled(False)
        btn_box.addWidget(self.connect_btn)
        btn_box.addWidget(self.disconnect_btn)
        g_layout.addLayout(btn_box, 2, 0, 1, 3)

        layout.addWidget(grp)

        # Status & Info Box
        info_grp = QGroupBox("Camera Status & Information")
        i_layout = QGridLayout(info_grp)

        i_layout.addWidget(QLabel("Link Status:"), 0, 0)
        self.status_lbl = QLabel("Disconnected")
        self.status_lbl.setStyleSheet("color: #ff4444; font-weight: bold;")
        i_layout.addWidget(self.status_lbl, 0, 1)

        i_layout.addWidget(QLabel("Serial Number:"), 1, 0)
        self.sn_lbl = QLabel("N/A")
        i_layout.addWidget(self.sn_lbl, 1, 1)

        i_layout.addWidget(QLabel("Firmware:"), 2, 0)
        self.fw_lbl = QLabel("N/A")
        i_layout.addWidget(self.fw_lbl, 2, 1)

        i_layout.addWidget(QLabel("FPA Temperature:"), 3, 0)
        self.fpa_lbl = QLabel("N/A")
        i_layout.addWidget(self.fpa_lbl, 3, 1)

        layout.addWidget(info_grp)
        layout.addStretch()
        self.tabs.addTab(tab, "Connection")

    def _create_controls_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # FFC Box
        ffc_grp = QGroupBox("Flat Field Correction (NUC)")
        f_layout = QVBoxLayout(ffc_grp)

        self.ffc_btn = QPushButton("Trigger Manual FFC")
        self.ffc_btn.setStyleSheet("font-weight: bold; padding: 6px;")
        f_layout.addWidget(self.ffc_btn)

        h = QHBoxLayout()
        h.addWidget(QLabel("FFC Mode:"))
        self.ffc_mode_combo = QComboBox()
        self.ffc_mode_combo.addItems(["Manual", "Auto", "External"])
        h.addWidget(self.ffc_mode_combo)
        f_layout.addLayout(h)
        layout.addWidget(ffc_grp)

        # Gain Box
        gain_grp = QGroupBox("Sensor Gain & Mode")
        g_layout = QGridLayout(gain_grp)

        g_layout.addWidget(QLabel("Gain Mode:"), 0, 0)
        self.gain_combo = QComboBox()
        self.gain_combo.addItems(["High", "Low", "Auto", "Manual"])
        g_layout.addWidget(self.gain_combo, 0, 1)

        g_layout.addWidget(QLabel("Color Palette:"), 1, 0)
        self.palette_combo = QComboBox()
        self.palette_combo.addItems([
            "White Hot", "Black Hot", "Fusion", "Rainbow",
            "Globow", "Ironbow", "Color1", "Color2", "IceFire"
        ])
        self.palette_combo.setCurrentText("White Hot")
        g_layout.addWidget(self.palette_combo, 1, 1)

        g_layout.addWidget(QLabel("Shutter Position:"), 2, 0)
        self.shutter_combo = QComboBox()
        self.shutter_combo.addItems(["Open", "Closed"])
        g_layout.addWidget(self.shutter_combo, 2, 1)

        layout.addWidget(gain_grp)
        layout.addStretch()
        self.tabs.addTab(tab, "Controls")

    def _create_radiometric_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        rad_grp = QGroupBox("Advanced Radiometry (T-Linear)")
        r_layout = QVBoxLayout(rad_grp)

        self.tlinear_chk = QCheckBox("Enable T-Linear Radiometric Output")
        self.tlinear_chk.setChecked(True)
        r_layout.addWidget(self.tlinear_chk)

        res_box = QHBoxLayout()
        res_box.addWidget(QLabel("Resolution Scale:"))
        self.res_high = QRadioButton("High Res (0.04 K / count)")
        self.res_low = QRadioButton("Low Res (0.40 K / count)")
        self.res_high.setChecked(True)
        res_box.addWidget(self.res_high)
        res_box.addWidget(self.res_low)
        r_layout.addLayout(res_box)

        self.apply_tlinear_btn = QPushButton("Apply Radiometric Settings")
        r_layout.addWidget(self.apply_tlinear_btn)

        layout.addWidget(rad_grp)
        layout.addStretch()
        self.tabs.addTab(tab, "Radiometry")

    def _create_diagnostics_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        diag_grp = QGroupBox("Sensor Telemetry")
        d_layout = QGridLayout(diag_grp)

        d_layout.addWidget(QLabel("FPA Detector Temp:"), 0, 0)
        self.diag_fpa_lbl = QLabel("-- °C")
        d_layout.addWidget(self.diag_fpa_lbl, 0, 1)

        d_layout.addWidget(QLabel("Camera Housing Temp:"), 1, 0)
        self.diag_housing_lbl = QLabel("-- °C")
        d_layout.addWidget(self.diag_housing_lbl, 1, 1)

        self.refresh_temps_btn = QPushButton("Poll Temperatures")
        d_layout.addWidget(self.refresh_temps_btn, 2, 0, 1, 2)

        layout.addWidget(diag_grp)
        layout.addStretch()
        self.tabs.addTab(tab, "Diagnostics")

    def _connect_signals(self):
        self.connect_btn.clicked.connect(self._on_connect_clicked)
        self.disconnect_btn.clicked.connect(self._on_disconnect_clicked)
        self.scan_btn.clicked.connect(self.scan_ports_requested.emit)
        self.ffc_btn.clicked.connect(self.ffc_triggered.emit)
        self.gain_combo.currentTextChanged.connect(lambda t: self.gain_mode_changed.emit(t.lower()))
        self.ffc_mode_combo.currentTextChanged.connect(lambda t: self.ffc_mode_changed.emit(t.lower()))
        self.palette_combo.currentTextChanged.connect(lambda t: self.color_lut_changed.emit(t.lower()))
        self.shutter_combo.currentTextChanged.connect(lambda t: self.shutter_position_changed.emit(t.lower()))
        self.apply_tlinear_btn.clicked.connect(self._on_apply_tlinear)
        self.refresh_temps_btn.clicked.connect(self.fpa_temp_requested.emit)

    def _on_connect_clicked(self):
        port = self.com_combo.currentText().strip()
        baud = int(self.baud_combo.currentText())
        self.connect_requested.emit(port, baud)

    def _on_disconnect_clicked(self):
        self.disconnect_requested.emit()

    def _on_apply_tlinear(self):
        enabled = self.tlinear_chk.isChecked()
        res = "high" if self.res_high.isChecked() else "low"
        self.tlinear_toggled.emit(enabled, res)

    def update_connection_status(self, connected: bool):
        if connected:
            self.status_lbl.setText("Connected (Serial OK)")
            self.status_lbl.setStyleSheet("color: #4CAF50; font-weight: bold;")
            self.connect_btn.setEnabled(False)
            self.disconnect_btn.setEnabled(True)
        else:
            self.status_lbl.setText("Disconnected")
            self.status_lbl.setStyleSheet("color: #ff4444; font-weight: bold;")
            self.connect_btn.setEnabled(True)
            self.disconnect_btn.setEnabled(False)

    def update_camera_info(self, info: Dict[str, Any]):
        if not info:
            return
        sn = info.get("serial") or info.get("serial_number")
        if sn:
            self.sn_lbl.setText(str(sn))
        fw = info.get("firmware") or info.get("revision")
        if fw:
            self.fw_lbl.setText(str(fw))
        fpa = info.get("celsius") or info.get("fpa_temp")
        if fpa is not None:
            self.fpa_lbl.setText(f"{float(fpa):.1f} °C")
            self.diag_fpa_lbl.setText(f"{float(fpa):.1f} °C")

    def update_ports_list(self, ports: list):
        current = self.com_combo.currentText()
        self.com_combo.clear()
        for p in ports:
            self.com_combo.addItem(p)
        if current in ports:
            self.com_combo.setCurrentText(current)
