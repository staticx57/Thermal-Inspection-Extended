"""
FLIR Tau 2 Camera Control Panel Widget.

Provides full GUI controls for FLIR / Teledyne Tau 2 thermal cameras:
- Serial connection setup (COM port & baud rate selection)
- Flat Field Correction (FFC / NUC) trigger & mode
- Sensor gain mode (High / Low / Auto / Manual)
- Color LUT / Palette selection
- AGC algorithm type (Plateau / Linear / Auto Dynamic / Once Bright / Info-Based)
- Advanced Radiometry T-Linear configuration
- FPA & Housing temperature readout

Tab layout AND widget conventions mirror BosonControlPanel's exactly (same
group-box titles/order, same widget types/dimensions, same status-caption
style) - Boson is the style reference for every control the two cameras
share, so a control that exists on both looks and behaves identically;
only where Tau2's CCI protocol genuinely lacks a capability (shutter
"Auto" position, onboard atmospheric compensation) does this panel diverge,
and it says so rather than faking parity. See LeptonControlPanel for the
same convention applied to a camera with fewer onboard capabilities still.

PENDING HARDWARE: everything below the Connection tab (FFC, gain, LUT,
T-Linear, shutter, AGC type) requires a live CCI/serial link. The currently-
owned breakout board has no CCI wired to USB yet (see project memory), so
these controls are UI-complete but unverified against real hardware - not a
bug, just untested until that connection exists. Tau2Serial (sdk/tau2_serial.py)
already implements the CCI command layer these signals dispatch to.
"""
from __future__ import annotations

import logging
from typing import Dict, Any

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox,
    QLabel, QPushButton, QComboBox, QCheckBox, QTabWidget, QRadioButton,
    QButtonGroup
)

from thermal_inspection.gui.themes import set_button_state

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
    agc_type_changed = pyqtSignal(str)               # 'plateau', 'linear', 'auto_dynamic', 'once_bright', 'info_based'
    tlinear_toggled = pyqtSignal(bool, str)          # (enabled, 'high'|'low')
    shutter_position_changed = pyqtSignal(str)       # 'open', 'closed'
    fpa_temp_requested = pyqtSignal()
    housing_temp_requested = pyqtSignal()

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
        self._create_image_enhancement_tab()
        self._create_radiometric_tab()
        self._create_environment_tab()
        self._create_diagnostics_tab()

    def _create_connection_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(8)

        # Connection Box - same widget dimensions/order as BosonControlPanel's
        # Serial Connection group, so the two cameras' connect flow looks
        # and behaves identically.
        grp = QGroupBox("Serial Connection")
        g_layout = QVBoxLayout(grp)

        status_row = QHBoxLayout()
        self.status_lbl = QLabel("● Disconnected")
        self.status_lbl.setStyleSheet("color: #ff4444; font-weight: bold;")
        self.status_lbl.setMaximumWidth(200)
        status_row.addWidget(self.status_lbl)
        status_row.addStretch()
        g_layout.addLayout(status_row)

        port_row = QHBoxLayout()
        port_label = QLabel("COM Port:")
        port_label.setFixedWidth(80)
        port_row.addWidget(port_label)

        self.com_combo = QComboBox()
        self.com_combo.setEditable(True)
        self.com_combo.setPlaceholderText("COM Port")
        self.com_combo.setToolTip("Select COM port or enter manually")
        self.com_combo.setMaximumWidth(150)
        # Starts empty (matches BosonControlPanel's com_port_combo) - a
        # hardcoded placeholder list here previously let a user select a
        # port that was never actually detected; only a real scan_ports_requested
        # scan (or update_ports_list()) should ever populate this.
        port_row.addWidget(self.com_combo)

        self.scan_btn = QPushButton("Scan")
        self.scan_btn.setFixedWidth(50)
        set_button_state(self.scan_btn, "compact", True)
        self.scan_btn.setToolTip("Scan for available COM ports")
        port_row.addWidget(self.scan_btn)
        port_row.addStretch()
        g_layout.addLayout(port_row)

        baud_row = QHBoxLayout()
        baud_label = QLabel("Baud Rate:")
        baud_label.setFixedWidth(80)
        baud_row.addWidget(baud_label)
        self.baud_combo = QComboBox()
        self.baud_combo.addItems(["57600", "9600", "19200", "38400", "115200", "921600"])
        self.baud_combo.setCurrentText("57600")
        self.baud_combo.setMaximumWidth(150)
        baud_row.addWidget(self.baud_combo)
        baud_row.addStretch()
        g_layout.addLayout(baud_row)

        btn_row = QHBoxLayout()
        self.connect_btn = QPushButton("Connect")
        self.connect_btn.setMinimumHeight(35)
        self.connect_btn.setMaximumWidth(150)
        set_button_state(self.connect_btn, "accent", "primary")
        self.connect_btn.setToolTip("Connect to Tau 2 camera via CCI serial")
        btn_row.addWidget(self.connect_btn)

        self.disconnect_btn = QPushButton("Disconnect")
        self.disconnect_btn.setMinimumHeight(35)
        self.disconnect_btn.setMaximumWidth(150)
        self.disconnect_btn.setEnabled(False)
        btn_row.addWidget(self.disconnect_btn)
        btn_row.addStretch()
        g_layout.addLayout(btn_row)

        self.connection_hint = QLabel(
            "Connect via COM port, or Scan if none is listed - some Tau 2 "
            "breakout boards expose no CCI line (video-only)"
        )
        self.connection_hint.setStyleSheet("font-size: 10px; color: #888888;")
        self.connection_hint.setWordWrap(True)
        self.connection_hint.setMaximumWidth(350)
        g_layout.addWidget(self.connection_hint)

        layout.addWidget(grp)

        # Status & Info Box - core fields (Serial Number, Software Version)
        # match Boson's Camera Information exactly; connection status and
        # FPA temperature live in the Serial Connection status row and the
        # Diagnostics tab respectively, not duplicated here.
        info_grp = QGroupBox("Camera Information")
        i_layout = QVBoxLayout(info_grp)

        self.info_labels: Dict[str, QLabel] = {}
        for key, label_text in [("serial", "Serial Number:"), ("software", "Software Version:")]:
            row = QHBoxLayout()
            label = QLabel(label_text)
            label.setFixedWidth(120)
            label.setStyleSheet("font-weight: bold;")
            value = QLabel("N/A")
            value.setStyleSheet("color: #888888;")
            value.setWordWrap(True)
            value.setMaximumWidth(200)
            row.addWidget(label)
            row.addWidget(value)
            row.addStretch()
            self.info_labels[key] = value
            i_layout.addLayout(row)

        layout.addWidget(info_grp)
        layout.addStretch()
        self.tabs.addTab(tab, "Connection")

    def _create_controls_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(8)

        # FFC Box - same widget dimensions/status-caption convention as
        # BosonControlPanel's Flat Field Correction group.
        ffc_grp = QGroupBox("Flat Field Correction (NUC)")
        f_layout = QVBoxLayout(ffc_grp)

        self.ffc_btn = QPushButton("Trigger FFC")
        self.ffc_btn.setMinimumHeight(40)
        self.ffc_btn.setToolTip("Manually trigger Flat Field Correction")
        f_layout.addWidget(self.ffc_btn)

        mode_row = QHBoxLayout()
        mode_label = QLabel("FFC Mode:")
        mode_label.setFixedWidth(80)
        mode_row.addWidget(mode_label)
        self.ffc_mode_combo = QComboBox()
        self.ffc_mode_combo.addItems(["Manual", "Auto", "External"])
        self.ffc_mode_combo.setMinimumHeight(28)
        self.ffc_mode_combo.setMaximumWidth(150)
        mode_row.addWidget(self.ffc_mode_combo)
        mode_row.addStretch()
        f_layout.addLayout(mode_row)

        self.ffc_status_label = QLabel("Status: Ready")
        self.ffc_status_label.setStyleSheet("font-size: 10px; color: #888888;")
        f_layout.addWidget(self.ffc_status_label)

        layout.addWidget(ffc_grp)

        # Shutter Control - same exclusive-toggle-button widget as Boson's
        # Shutter Control group. Tau 2's CCI protocol only has Open/Closed
        # (set_shutter_position takes 0=OPEN, 1=CLOSED) - no "Auto" state
        # exists to offer, unlike Boson.
        shutter_grp = QGroupBox("Shutter Control")
        shutter_layout = QVBoxLayout(shutter_grp)
        shutter_btn_row = QHBoxLayout()

        self.shutter_open_btn = QPushButton("Open")
        self.shutter_open_btn.setCheckable(True)
        self.shutter_open_btn.setChecked(True)
        self.shutter_open_btn.setToolTip("Force shutter open (imaging mode)")
        self.shutter_open_btn.setMinimumHeight(32)
        shutter_btn_row.addWidget(self.shutter_open_btn)

        self.shutter_closed_btn = QPushButton("Closed")
        self.shutter_closed_btn.setCheckable(True)
        self.shutter_closed_btn.setToolTip("Force shutter closed (calibration)")
        self.shutter_closed_btn.setMinimumHeight(32)
        shutter_btn_row.addWidget(self.shutter_closed_btn)

        shutter_layout.addLayout(shutter_btn_row)

        self.shutter_btn_group = QButtonGroup(self)
        self.shutter_btn_group.addButton(self.shutter_open_btn)
        self.shutter_btn_group.addButton(self.shutter_closed_btn)
        self.shutter_btn_group.setExclusive(True)

        self.shutter_status_label = QLabel("Position: Open")
        self.shutter_status_label.setStyleSheet("font-size: 10px; color: #888888;")
        shutter_layout.addWidget(self.shutter_status_label)

        layout.addWidget(shutter_grp)

        # Gain Box - same combo dimensions/status-caption convention as
        # Boson's Gain Mode group.
        gain_grp = QGroupBox("Gain Mode")
        gg_layout = QVBoxLayout(gain_grp)
        gain_combo_row = QHBoxLayout()
        self.gain_combo = QComboBox()
        self.gain_combo.addItems(["High", "Low", "Auto", "Manual"])
        self.gain_combo.setToolTip("Sensor gain mode")
        self.gain_combo.setMinimumHeight(28)
        self.gain_combo.setMaximumWidth(150)
        gain_combo_row.addWidget(self.gain_combo)
        gain_combo_row.addStretch()
        gg_layout.addLayout(gain_combo_row)

        self.current_gain_label = QLabel("Current: High")
        self.current_gain_label.setStyleSheet("font-size: 10px; color: #888888;")
        gg_layout.addWidget(self.current_gain_label)

        layout.addWidget(gain_grp)

        # Color LUT Box - same combo dimensions/note convention as Boson's.
        lut_grp = QGroupBox("Color Lookup Table (LUT)")
        l_layout = QVBoxLayout(lut_grp)
        lut_combo_row = QHBoxLayout()
        self.palette_combo = QComboBox()
        self.palette_combo.addItems([
            "White Hot", "Black Hot", "Fusion", "Rainbow",
            "Globow", "Ironbow", "Color1", "Color2", "IceFire"
        ])
        self.palette_combo.setCurrentText("White Hot")
        self.palette_combo.setMinimumHeight(28)
        self.palette_combo.setMaximumWidth(150)
        lut_combo_row.addWidget(self.palette_combo)
        lut_combo_row.addStretch()
        l_layout.addLayout(lut_combo_row)

        lut_note = QLabel("Note: Hardware LUT applies before software processing")
        lut_note.setStyleSheet("font-size: 9px; color: #888888;")
        lut_note.setWordWrap(True)
        l_layout.addWidget(lut_note)
        layout.addWidget(lut_grp)

        layout.addStretch()
        self.tabs.addTab(tab, "Controls")

    def _create_image_enhancement_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(8)

        agc_grp = QGroupBox("AGC Algorithm")
        a_layout = QVBoxLayout(agc_grp)
        agc_combo_row = QHBoxLayout()
        agc_label = QLabel("AGC Type:")
        agc_label.setFixedWidth(80)
        agc_combo_row.addWidget(agc_label)
        self.agc_type_combo = QComboBox()
        self.agc_type_combo.addItems([
            "Plateau", "Linear", "Auto Dynamic", "Once Bright", "Info Based"
        ])
        self.agc_type_combo.setMinimumHeight(28)
        self.agc_type_combo.setMaximumWidth(150)
        agc_combo_row.addWidget(self.agc_type_combo)
        agc_combo_row.addStretch()
        a_layout.addLayout(agc_combo_row)

        note = QLabel(
            "Tau 2's CCI protocol selects between five fixed AGC algorithms "
            "rather than the continuous gain/gamma/DDE sliders Boson exposes - "
            "this is a hardware difference, not a missing control."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color: #888888; font-size: 9pt; padding-bottom: 4px;")
        a_layout.addWidget(note)

        layout.addWidget(agc_grp)
        layout.addStretch()
        self.tabs.addTab(tab, "Image Enhancement")

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
        set_button_state(self.apply_tlinear_btn, "accent", "primary")
        r_layout.addWidget(self.apply_tlinear_btn)

        layout.addWidget(rad_grp)
        layout.addStretch()
        self.tabs.addTab(tab, "Radiometric")

    def _create_environment_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        grp = QGroupBox("Environmental Compensation")
        g_layout = QVBoxLayout(grp)
        note = QLabel(
            "Tau 2's CCI protocol has no onboard atmospheric/emissivity "
            "registers to push settings to (unlike Boson) - use the app's "
            "main Environmental Compensation panel for software-side "
            "accuracy correction, which applies to every connected camera."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color: #888888; font-size: 9pt; padding-bottom: 4px;")
        g_layout.addWidget(note)
        layout.addWidget(grp)
        layout.addStretch()
        self.tabs.addTab(tab, "Environment")

    def _create_diagnostics_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(8)

        # Same "QHBoxLayout row of label + bold value" convention and same
        # button-below-the-group(s), not-inside-them, placement as Boson's
        # System Status / FFC Status / "Refresh Diagnostics" pattern.
        diag_grp = QGroupBox("Sensor Telemetry")
        d_layout = QVBoxLayout(diag_grp)

        fpa_row = QHBoxLayout()
        fpa_row.addWidget(QLabel("FPA Detector Temp:"))
        self.diag_fpa_lbl = QLabel("--")
        self.diag_fpa_lbl.setStyleSheet("font-weight: bold;")
        fpa_row.addWidget(self.diag_fpa_lbl)
        fpa_row.addStretch()
        d_layout.addLayout(fpa_row)

        housing_row = QHBoxLayout()
        housing_row.addWidget(QLabel("Camera Housing Temp:"))
        self.diag_housing_lbl = QLabel("--")
        self.diag_housing_lbl.setStyleSheet("font-weight: bold;")
        housing_row.addWidget(self.diag_housing_lbl)
        housing_row.addStretch()
        d_layout.addLayout(housing_row)

        layout.addWidget(diag_grp)

        self.refresh_temps_btn = QPushButton("Refresh Diagnostics")
        self.refresh_temps_btn.clicked.connect(self._on_refresh_temps_clicked)
        layout.addWidget(self.refresh_temps_btn)

        layout.addStretch()
        self.tabs.addTab(tab, "Diagnostics")

    def _connect_signals(self):
        self.connect_btn.clicked.connect(self._on_connect_clicked)
        self.disconnect_btn.clicked.connect(self._on_disconnect_clicked)
        self.scan_btn.clicked.connect(self.scan_ports_requested.emit)
        self.ffc_btn.clicked.connect(self.ffc_triggered.emit)
        self.gain_combo.currentTextChanged.connect(self._on_gain_mode_changed)
        self.ffc_mode_combo.currentTextChanged.connect(lambda t: self.ffc_mode_changed.emit(t.lower()))
        self.palette_combo.currentTextChanged.connect(lambda t: self.color_lut_changed.emit(t.lower()))
        self.shutter_open_btn.toggled.connect(lambda checked: self._on_shutter_toggled("open", checked))
        self.shutter_closed_btn.toggled.connect(lambda checked: self._on_shutter_toggled("closed", checked))
        self.agc_type_combo.currentTextChanged.connect(
            lambda t: self.agc_type_changed.emit(t.lower().replace(" ", "_"))
        )
        self.apply_tlinear_btn.clicked.connect(self._on_apply_tlinear)
        self.refresh_temps_btn.clicked.connect(self._on_refresh_temps_clicked)

    def _on_connect_clicked(self):
        port = self.com_combo.currentText().strip()
        baud = int(self.baud_combo.currentText())
        self.connect_requested.emit(port, baud)

    def _on_disconnect_clicked(self):
        self.disconnect_requested.emit()

    def _on_gain_mode_changed(self, text: str):
        self.current_gain_label.setText(f"Current: {text}")
        self.gain_mode_changed.emit(text.lower())

    def _on_shutter_toggled(self, position: str, checked: bool):
        if not checked:
            return
        self.shutter_status_label.setText(f"Position: {position.capitalize()}")
        self.shutter_position_changed.emit(position)

    def _on_apply_tlinear(self):
        enabled = self.tlinear_chk.isChecked()
        res = "high" if self.res_high.isChecked() else "low"
        self.tlinear_toggled.emit(enabled, res)

    def _on_refresh_temps_clicked(self):
        self.fpa_temp_requested.emit()
        self.housing_temp_requested.emit()

    def set_status(self, message: str, is_error: bool = False):
        """Show a transient status message (e.g. FFC result) - same
        contract as BosonControlPanel.set_status()."""
        color = "#ff4444" if is_error else "#888888"
        self.ffc_status_label.setText(f"Status: {message}")
        self.ffc_status_label.setStyleSheet(f"font-size: 10px; color: {color};")

    def update_connection_status(self, connected: bool):
        if connected:
            self.status_lbl.setText("● Connected")
            self.status_lbl.setStyleSheet("color: #4CAF50; font-weight: bold;")
            self.connect_btn.setEnabled(False)
            self.disconnect_btn.setEnabled(True)
        else:
            self.status_lbl.setText("● Disconnected")
            self.status_lbl.setStyleSheet("color: #ff4444; font-weight: bold;")
            self.connect_btn.setEnabled(True)
            self.disconnect_btn.setEnabled(False)

    def update_camera_info(self, info: Dict[str, Any]):
        if not info:
            return
        sn = info.get("serial") or info.get("serial_number")
        if sn:
            self.info_labels["serial"].setText(str(sn))
        fw = info.get("firmware") or info.get("revision")
        if fw:
            self.info_labels["software"].setText(str(fw))
        fpa = info.get("celsius") or info.get("fpa_temp")
        if fpa is not None:
            self.diag_fpa_lbl.setText(f"{float(fpa):.1f} °C")

    def update_housing_temp(self, celsius: float):
        self.diag_housing_lbl.setText(f"{float(celsius):.1f} °C")

    def update_ports_list(self, ports: list):
        current = self.com_combo.currentText()
        self.com_combo.clear()
        for p in ports:
            self.com_combo.addItem(p)
        if current in ports:
            self.com_combo.setCurrentText(current)
