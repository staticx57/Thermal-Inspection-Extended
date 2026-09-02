from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QGroupBox, QCheckBox, QSlider, QScrollArea, QFrame
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer

from thermal_inspection.sdk.lepton_sdk_wrapper import LeptonSDK, MockLeptonTransport

class LeptonControlPanel(QWidget):
    """
    Control panel for FLIR Lepton cameras.
    Exposes FFC, Radiometry, and AGC controls.
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
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setSpacing(10)
        layout.setContentsMargins(10, 10, 10, 10)

        # === Connection Status ===
        conn_group = QGroupBox("Connection")
        conn_layout = QVBoxLayout(conn_group)

        status_layout = QHBoxLayout()
        self.status_label = QLabel("Status: Disconnected")
        self.status_label.setStyleSheet("color: red; font-weight: bold;")
        status_layout.addWidget(self.status_label)

        self.connect_btn = QPushButton("Connect (Mock)")
        self.connect_btn.clicked.connect(self._toggle_connection)
        status_layout.addWidget(self.connect_btn)

        conn_layout.addLayout(status_layout)

        # Info Labels
        self.serial_label = QLabel("Serial: N/A")
        conn_layout.addWidget(self.serial_label)
        self.uptime_label = QLabel("Uptime: N/A")
        conn_layout.addWidget(self.uptime_label)

        layout.addWidget(conn_group)

        # === Controls ===
        ctrl_group = QGroupBox("Camera Controls")
        ctrl_layout = QVBoxLayout(ctrl_group)

        # FFC
        self.ffc_btn = QPushButton("Perform FFC (Calibration)")
        self.ffc_btn.clicked.connect(self._on_ffc_clicked)
        self.ffc_btn.setEnabled(False)
        ctrl_layout.addWidget(self.ffc_btn)

        self.ffc_status_label = QLabel("FFC Status: Unknown")
        ctrl_layout.addWidget(self.ffc_status_label)

        layout.addWidget(ctrl_group)

        # === Radiometry ===
        rad_group = QGroupBox("Radiometry")
        rad_layout = QVBoxLayout(rad_group)

        self.rad_check = QCheckBox("Enable Radiometry (T-Linear)")
        self.rad_check.toggled.connect(self._on_rad_toggled)
        self.rad_check.setEnabled(False)
        rad_layout.addWidget(self.rad_check)

        # Emissivity
        emiss_layout = QHBoxLayout()
        emiss_layout.addWidget(QLabel("Emissivity:"))
        self.emiss_slider = QSlider(Qt.Orientation.Horizontal)
        self.emiss_slider.setRange(1, 100)
        self.emiss_slider.setValue(95)
        self.emiss_slider.setEnabled(False)
        self.emiss_slider.valueChanged.connect(self._on_emissivity_changed)
        emiss_layout.addWidget(self.emiss_slider)

        self.emiss_value = QLabel("0.95")
        emiss_layout.addWidget(self.emiss_value)
        rad_layout.addLayout(emiss_layout)

        # Readings
        self.fpa_temp_label = QLabel("FPA Temp: --")
        rad_layout.addWidget(self.fpa_temp_label)

        self.spot_temp_label = QLabel("Spotmeter: --")
        rad_layout.addWidget(self.spot_temp_label)

        layout.addWidget(rad_group)
        layout.addStretch()

        scroll.setWidget(content)
        outer_layout.addWidget(scroll)

    def _toggle_connection(self):
        if not self.connected:
            # Connect
            # In a real app, we'd pass a real transport here
            self.sdk = LeptonSDK(MockLeptonTransport())
            self.connected = True
            self.status_label.setText("Status: Connected (Mock)")
            self.status_label.setStyleSheet("color: green; font-weight: bold;")
            self.connect_btn.setText("Disconnect")

            # Enable controls
            self.ffc_btn.setEnabled(True)
            self.rad_check.setEnabled(True)
            self.emiss_slider.setEnabled(True)

            # Get Info
            sn = self.sdk.get_serial_number()
            self.serial_label.setText(f"Serial: {sn if sn else 'Unknown'}")

            # Start polling
            self.timer.start()
            self.connect_requested.emit()

        else:
            # Disconnect
            self.timer.stop()
            self.sdk = None
            self.connected = False
            self.status_label.setText("Status: Disconnected")
            self.status_label.setStyleSheet("color: red; font-weight: bold;")
            self.connect_btn.setText("Connect (Mock)")

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
            self.uptime_label.setText(f"Uptime: {seconds:.1f}s")

        # FPA Temp
        fpa = self.sdk.get_fpa_temperature_celsius()
        if fpa is not None:
            self.fpa_temp_label.setText(f"FPA Temp: {fpa:.1f}°C")

        # Spotmeter (if enabled)
        if self.rad_check.isChecked():
            spot = self.sdk.get_spotmeter_value()
            if spot is not None:
                self.spot_temp_label.setText(f"Spotmeter: {spot:.1f}°C")

    def _on_ffc_clicked(self):
        if self.sdk:
            self.sdk.run_ffc()
            self.ffc_status_label.setText("FFC Status: Running...")
            # Check status after a delay
            QTimer.singleShot(1000, self._check_ffc_status)
            self.ffc_requested.emit()

    def _check_ffc_status(self):
        if self.sdk:
            status = self.sdk.get_ffc_status()
            self.ffc_status_label.setText(f"FFC Status: {status}")

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
