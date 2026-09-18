from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QGroupBox, QCheckBox, QSlider, QTabWidget
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer

from thermal_inspection.sdk.lepton_sdk_wrapper import LeptonSDK, MockLeptonTransport
from thermal_inspection.gui.themes import set_button_state

class LeptonControlPanel(QWidget):
    """
    Control panel for FLIR Lepton cameras.
    Exposes FFC and Radiometry controls.

    Tab layout AND widget conventions mirror BosonControlPanel's/
    Tau2ControlPanel's exactly wherever Lepton has the same kind of control
    (status row + own-row Connect/Disconnect buttons, same widths/heights,
    same status-caption style) - Boson is the style reference for every
    control shared across the three thermal cameras. Genuine capability
    gaps (no COM port - Lepton is I2C/CCI-over-TWI, not serial; no gain/
    shutter concept; no onboard atmospheric registers) get an honestly
    labeled placeholder instead of a faked control.

    The Image Enhancement and Environment tabs are placeholders here:
    Lepton's SDK wrapper (sdk/lepton_sdk_wrapper.py) already implements
    AGC enable/policy calls, but wiring them into this panel is new SDK
    integration work that's tracked on the debt ledger rather than done in
    this pass - this reorganization only changes layout, not what this
    panel talks to.

    PENDING HARDWARE: this panel only ever talks to MockLeptonTransport -
    LeptonTransport (sdk/lepton_sdk_wrapper.py) is an ABC with no real
    (I2C/SPI) implementation yet, no Lepton hardware to test against. UI
    and command dispatch are complete but unverified; not a bug, just
    untested until a real transport exists and a Lepton is connected.
    """

    # Signals
    connect_requested = pyqtSignal()
    disconnect_requested = pyqtSignal()
    ffc_requested = pyqtSignal()
    radiometry_toggled = pyqtSignal(bool)
    emissivity_changed = pyqtSignal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.sdk = None
        self.connected = False
        self._init_ui()

        # Polling timer for status updates (temp, spotmeter)
        self.timer = QTimer()
        self.timer.timeout.connect(self._update_status)
        self.timer.setInterval(1000)  # 1Hz

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

        # "Connection", not "Serial Connection" - Lepton talks CCI-over-TWI
        # (I2C), genuinely not a serial link, unlike Boson/Tau2.
        conn_group = QGroupBox("Connection")
        conn_layout = QVBoxLayout(conn_group)

        status_row = QHBoxLayout()
        self.status_label = QLabel("● Disconnected")
        self.status_label.setStyleSheet("color: #ff4444; font-weight: bold;")
        self.status_label.setMaximumWidth(200)
        status_row.addWidget(self.status_label)
        status_row.addStretch()
        conn_layout.addLayout(status_row)

        btn_row = QHBoxLayout()
        self.connect_btn = QPushButton("Connect (Mock)")
        self.connect_btn.setMinimumHeight(35)
        self.connect_btn.setMaximumWidth(150)
        set_button_state(self.connect_btn, "accent", "primary")
        self.connect_btn.clicked.connect(self._on_connect_clicked)
        btn_row.addWidget(self.connect_btn)

        self.disconnect_btn = QPushButton("Disconnect")
        self.disconnect_btn.setMinimumHeight(35)
        self.disconnect_btn.setMaximumWidth(150)
        self.disconnect_btn.setEnabled(False)
        self.disconnect_btn.clicked.connect(self._on_disconnect_clicked)
        btn_row.addWidget(self.disconnect_btn)
        btn_row.addStretch()
        conn_layout.addLayout(btn_row)

        self.connection_hint = QLabel(
            "No real hardware yet - Connect (Mock) simulates the SDK "
            "against MockLeptonTransport"
        )
        self.connection_hint.setStyleSheet("font-size: 10px; color: #888888;")
        self.connection_hint.setWordWrap(True)
        self.connection_hint.setMaximumWidth(350)
        conn_layout.addWidget(self.connection_hint)

        layout.addWidget(conn_group)

        info_group = QGroupBox("Camera Information")
        info_layout = QVBoxLayout(info_group)

        serial_row = QHBoxLayout()
        serial_label = QLabel("Serial Number:")
        serial_label.setFixedWidth(120)
        serial_label.setStyleSheet("font-weight: bold;")
        self.serial_label = QLabel("N/A")
        self.serial_label.setStyleSheet("color: #888888;")
        self.serial_label.setWordWrap(True)
        self.serial_label.setMaximumWidth(200)
        serial_row.addWidget(serial_label)
        serial_row.addWidget(self.serial_label)
        serial_row.addStretch()
        info_layout.addLayout(serial_row)

        uptime_row = QHBoxLayout()
        uptime_label = QLabel("Uptime:")
        uptime_label.setFixedWidth(120)
        uptime_label.setStyleSheet("font-weight: bold;")
        self.uptime_label = QLabel("N/A")
        self.uptime_label.setStyleSheet("color: #888888;")
        uptime_row.addWidget(uptime_label)
        uptime_row.addWidget(self.uptime_label)
        uptime_row.addStretch()
        info_layout.addLayout(uptime_row)

        layout.addWidget(info_group)
        layout.addStretch()
        self.tabs.addTab(tab, "Connection")

    def _create_controls_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(8)

        ctrl_group = QGroupBox("Flat Field Correction (FFC)")
        ctrl_layout = QVBoxLayout(ctrl_group)

        self.ffc_btn = QPushButton("Trigger FFC")
        self.ffc_btn.setMinimumHeight(40)
        self.ffc_btn.clicked.connect(self._on_ffc_clicked)
        self.ffc_btn.setEnabled(False)
        ctrl_layout.addWidget(self.ffc_btn)

        self.ffc_status_label = QLabel("Status: Unknown")
        self.ffc_status_label.setStyleSheet("font-size: 10px; color: #888888;")
        ctrl_layout.addWidget(self.ffc_status_label)

        layout.addWidget(ctrl_group)

        note = QLabel(
            "Lepton has no gain-mode or shutter-position concept in its "
            "IDD - it's a fixed-gain, purely-digital-AGC core with no "
            "external shutter, unlike Boson/Tau 2."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color: #888888; font-size: 9pt; padding-bottom: 4px;")
        layout.addWidget(note)

        layout.addStretch()
        self.tabs.addTab(tab, "Controls")

    def _create_image_enhancement_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        grp = QGroupBox("AGC Settings")
        g_layout = QVBoxLayout(grp)
        note = QLabel(
            "Lepton's SDK wrapper already implements AGC enable/policy "
            "(Linear/HEQ) calls, but this panel doesn't wire them up yet - "
            "tracked on the debt ledger as new SDK integration work, not "
            "part of this layout pass."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color: #888888; font-size: 9pt; padding-bottom: 4px;")
        g_layout.addWidget(note)
        layout.addWidget(grp)
        layout.addStretch()
        self.tabs.addTab(tab, "Image Enhancement")

    def _create_radiometric_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        rad_group = QGroupBox("Radiometry")
        rad_layout = QVBoxLayout(rad_group)

        self.rad_check = QCheckBox("Enable Radiometry (T-Linear)")
        self.rad_check.toggled.connect(self._on_rad_toggled)
        self.rad_check.setEnabled(False)
        rad_layout.addWidget(self.rad_check)

        layout.addWidget(rad_group)
        layout.addStretch()
        self.tabs.addTab(tab, "Radiometric")

    def _create_environment_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        grp = QGroupBox("Environmental Compensation")
        g_layout = QVBoxLayout(grp)

        # Emissivity lives here (matches Boson's Environmental Compensation
        # placement), not on the Radiometric tab - Radiometric is about
        # whether/how temperature output is enabled, Environment is about
        # the scene parameters that make that output accurate.
        emiss_row = QHBoxLayout()
        emiss_row.addWidget(QLabel("Emissivity:"))
        self.emiss_slider = QSlider(Qt.Orientation.Horizontal)
        self.emiss_slider.setRange(1, 100)
        self.emiss_slider.setValue(95)
        self.emiss_slider.setEnabled(False)
        self.emiss_slider.valueChanged.connect(self._on_emissivity_changed)
        emiss_row.addWidget(self.emiss_slider)
        self.emiss_value = QLabel("0.95")
        self.emiss_value.setFixedWidth(38)
        emiss_row.addWidget(self.emiss_value)
        g_layout.addLayout(emiss_row)

        note = QLabel(
            "Lepton's IDD has no atmospheric-temperature/transmission "
            "registers exposed by this SDK wrapper (unlike Boson) - "
            "Emissivity applies live on every change, not via a batch "
            "Apply step, since that's how the SDK wrapper's set_emissivity() "
            "already works."
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

        diag_group = QGroupBox("Sensor Telemetry")
        d_layout = QVBoxLayout(diag_group)

        fpa_row = QHBoxLayout()
        fpa_row.addWidget(QLabel("FPA Temp:"))
        self.fpa_temp_label = QLabel("--")
        self.fpa_temp_label.setStyleSheet("font-weight: bold;")
        fpa_row.addWidget(self.fpa_temp_label)
        fpa_row.addStretch()
        d_layout.addLayout(fpa_row)

        spot_row = QHBoxLayout()
        spot_row.addWidget(QLabel("Spotmeter:"))
        self.spot_temp_label = QLabel("--")
        self.spot_temp_label.setStyleSheet("font-weight: bold;")
        spot_row.addWidget(self.spot_temp_label)
        spot_row.addStretch()
        d_layout.addLayout(spot_row)

        layout.addWidget(diag_group)

        auto_refresh_note = QLabel("Auto-refreshes every 1s while connected - no manual refresh needed.")
        auto_refresh_note.setStyleSheet("font-size: 10px; color: #888888;")
        layout.addWidget(auto_refresh_note)

        layout.addStretch()
        self.tabs.addTab(tab, "Diagnostics")

    def _on_connect_clicked(self):
        # In a real app, we'd pass a real transport here
        self.sdk = LeptonSDK(MockLeptonTransport())
        self.connected = True
        self.status_label.setText("● Connected (Mock)")
        self.status_label.setStyleSheet("color: #4CAF50; font-weight: bold;")
        self.connect_btn.setEnabled(False)
        self.disconnect_btn.setEnabled(True)

        # Enable controls
        self.ffc_btn.setEnabled(True)
        self.rad_check.setEnabled(True)
        self.emiss_slider.setEnabled(True)

        # Get Info
        sn = self.sdk.get_serial_number()
        self.serial_label.setText(str(sn) if sn else "Unknown")

        # Start polling
        self.timer.start()
        self.connect_requested.emit()

    def _on_disconnect_clicked(self):
        self.timer.stop()
        self.sdk = None
        self.connected = False
        self.status_label.setText("● Disconnected")
        self.status_label.setStyleSheet("color: #ff4444; font-weight: bold;")
        self.connect_btn.setEnabled(True)
        self.disconnect_btn.setEnabled(False)

        # Disable controls
        self.ffc_btn.setEnabled(False)
        self.rad_check.setEnabled(False)
        self.emiss_slider.setEnabled(False)

        self.disconnect_requested.emit()

    def _update_status(self):
        if not self.sdk:
            return

        # Uptime
        uptime = self.sdk.get_uptime()
        if uptime:
            seconds = uptime / 1000.0
            self.uptime_label.setText(f"{seconds:.1f}s")

        # FPA Temp
        fpa = self.sdk.get_fpa_temperature_celsius()
        if fpa is not None:
            self.fpa_temp_label.setText(f"{fpa:.1f} °C")

        # Spotmeter (if enabled)
        if self.rad_check.isChecked():
            spot = self.sdk.get_spotmeter_value()
            if spot is not None:
                self.spot_temp_label.setText(f"{spot:.1f} °C")

    def _on_ffc_clicked(self):
        if self.sdk:
            self.sdk.run_ffc()
            self.ffc_status_label.setText("Status: Running...")
            # Check status after a delay
            QTimer.singleShot(1000, self._check_ffc_status)
            self.ffc_requested.emit()

    def _check_ffc_status(self):
        if self.sdk:
            status = self.sdk.get_ffc_status()
            self.ffc_status_label.setText(f"Status: {status}")

    def _on_rad_toggled(self, checked):
        if self.sdk:
            self.sdk.set_rad_enable(checked)
            self.sdk.set_tlinear_enable(checked)
            self.radiometry_toggled.emit(checked)

    def _on_emissivity_changed(self, value):
        emiss = value / 100.0
        self.emiss_value.setText(f"{emiss:.2f}")
        if self.sdk:
            self.sdk.set_emissivity(emiss)
            self.emissivity_changed.emit(emiss)
