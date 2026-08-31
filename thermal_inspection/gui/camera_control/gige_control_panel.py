"""
GigE Vision Camera Control Panel.

Provides network scanning, IP configuration (ForceIP), and standard
GenICam camera parameter adjustments over Ethernet.
"""
from __future__ import annotations

import logging
from typing import Optional, List
import threading

from PyQt6.QtCore import pyqtSignal, QTimer
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox,
    QLabel, QPushButton, QComboBox, QLineEdit, QDoubleSpinBox,
    QCheckBox, QScrollArea, QFrame, QMessageBox
)
from PyQt6.QtGui import QFont

from thermal_inspection.sdk.gige.gvcp import discover_gige_cameras, force_gige_ip, GigEDeviceInfo

logger = logging.getLogger(__name__)


class GigEControlPanel(QWidget):
    """
    Dedicated control panel for GigE Vision cameras.
    """
    command_requested = pyqtSignal(str, dict)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.event_bus = None
        self._discovered_cameras: List[GigEDeviceInfo] = []
        self._block_signals = False
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

        # 1. Network Discovery & Device Selector
        disc_grp = QGroupBox("GigE Vision Network Discovery")
        disc_layout = QVBoxLayout(disc_grp)
        disc_layout.setContentsMargins(10, 10, 10, 10)
        disc_layout.setSpacing(8)

        h_top = QHBoxLayout()
        self.btn_scan = QPushButton("🔍 Scan Network (GVCP Port 3956)")
        self.btn_scan.clicked.connect(self._on_scan_network)
        h_top.addWidget(self.btn_scan)
        disc_layout.addLayout(h_top)

        h_sel = QHBoxLayout()
        h_sel.addWidget(QLabel("Camera:"))
        self.cam_combo = QComboBox()
        self.cam_combo.addItem("No GigE cameras detected", None)
        self.cam_combo.currentIndexChanged.connect(self._on_camera_selected)
        h_sel.addWidget(self.cam_combo, 1)
        disc_layout.addLayout(h_sel)

        layout.addWidget(disc_grp)

        # 2. Camera Network Details Card
        info_grp = QGroupBox("Device Details")
        info_layout = QGridLayout(info_grp)
        info_layout.setContentsMargins(10, 10, 10, 10)
        info_layout.setSpacing(6)

        self.lbl_model = QLabel("Model: —")
        f = QFont(); f.setBold(True)
        self.lbl_model.setFont(f)
        info_layout.addWidget(self.lbl_model, 0, 0, 1, 2)

        self.lbl_serial = QLabel("Serial: —")
        self.lbl_mac = QLabel("MAC: —")
        info_layout.addWidget(self.lbl_serial, 1, 0)
        info_layout.addWidget(self.lbl_mac, 1, 1)

        self.lbl_curr_ip = QLabel("Current IP: —")
        self.lbl_curr_subnet = QLabel("Subnet: —")
        info_layout.addWidget(self.lbl_curr_ip, 2, 0)
        info_layout.addWidget(self.lbl_curr_subnet, 2, 1)

        layout.addWidget(info_grp)

        # 3. ForceIP / Network Reconfiguration
        ip_grp = QGroupBox("ForceIP Configuration (Subnet Rescue)")
        ip_layout = QGridLayout(ip_grp)
        ip_layout.setContentsMargins(10, 10, 10, 10)
        ip_layout.setSpacing(8)

        ip_layout.addWidget(QLabel("New IP:"), 0, 0)
        self.txt_ip = QLineEdit("192.168.1.100")
        ip_layout.addWidget(self.txt_ip, 0, 1)

        ip_layout.addWidget(QLabel("Subnet:"), 1, 0)
        self.txt_subnet = QLineEdit("255.255.255.0")
        ip_layout.addWidget(self.txt_subnet, 1, 1)

        ip_layout.addWidget(QLabel("Gateway:"), 2, 0)
        self.txt_gateway = QLineEdit("192.168.1.1")
        ip_layout.addWidget(self.txt_gateway, 2, 1)

        self.btn_force_ip = QPushButton("Apply ForceIP")
        self.btn_force_ip.clicked.connect(self._on_apply_force_ip)
        ip_layout.addWidget(self.btn_force_ip, 3, 0, 1, 2)

        layout.addWidget(ip_grp)

        # 4. GenICam Controls (Exposure, Gain, Trigger, Packet Size)
        gen_grp = QGroupBox("GenICam Parameters")
        gen_layout = QGridLayout(gen_grp)
        gen_layout.setContentsMargins(10, 10, 10, 10)
        gen_layout.setSpacing(8)

        # Exposure Time
        gen_layout.addWidget(QLabel("Exposure (µs):"), 0, 0)
        self.spin_exposure = QDoubleSpinBox()
        self.spin_exposure.setRange(10.0, 1000000.0)
        self.spin_exposure.setValue(10000.0)
        self.spin_exposure.setSingleStep(1000.0)
        self.spin_exposure.valueChanged.connect(lambda v: self._emit_command("set_exposure_time", {"time_us": v}))
        gen_layout.addWidget(self.spin_exposure, 0, 1)

        # Gain
        gen_layout.addWidget(QLabel("Gain (dB):"), 1, 0)
        self.spin_gain = QDoubleSpinBox()
        self.spin_gain.setRange(0.0, 48.0)
        self.spin_gain.setValue(0.0)
        self.spin_gain.setSingleStep(1.0)
        self.spin_gain.valueChanged.connect(lambda v: self._emit_command("set_gain", {"gain_db": v}))
        gen_layout.addWidget(self.spin_gain, 1, 1)

        # Packet Size (MTU)
        gen_layout.addWidget(QLabel("Packet Size (MTU):"), 2, 0)
        self.combo_mtu = QComboBox()
        self.combo_mtu.addItem("1500 (Standard Ethernet)", 1500)
        self.combo_mtu.addItem("9000 (Jumbo Frames)", 9000)
        self.combo_mtu.currentIndexChanged.connect(self._on_mtu_changed)
        gen_layout.addWidget(self.combo_mtu, 2, 1)

        # Trigger
        self.chk_trigger = QCheckBox("Enable Software Trigger")
        self.chk_trigger.toggled.connect(lambda c: self._emit_command("set_trigger_mode", {"enabled": c}))
        gen_layout.addWidget(self.chk_trigger, 3, 0)

        self.btn_fire_trigger = QPushButton("⚡ Fire Software Trigger")
        self.btn_fire_trigger.clicked.connect(lambda: self._emit_command("trigger_software", {}))
        gen_layout.addWidget(self.btn_fire_trigger, 3, 1)

        layout.addWidget(gen_grp)

        layout.addStretch()
        scroll.setWidget(container)
        root.addWidget(scroll)

    def _on_scan_network(self):
        self.btn_scan.setEnabled(False)
        self.btn_scan.setText("Scanning Network...")

        def scan_worker():
            cams = discover_gige_cameras()
            QTimer.singleShot(0, lambda: self._update_camera_list(cams))

        threading.Thread(target=scan_worker, daemon=True, name="GigEScanWorker").start()

    def _update_camera_list(self, cameras: List[GigEDeviceInfo]):
        self._discovered_cameras = cameras
        self.cam_combo.clear()

        if not cameras:
            self.cam_combo.addItem("No GigE cameras detected", None)
            self.lbl_model.setText("Model: None")
            self.lbl_serial.setText("Serial: —")
            self.lbl_mac.setText("MAC: —")
            self.lbl_curr_ip.setText("Current IP: —")
            self.lbl_curr_subnet.setText("Subnet: —")
        else:
            for cam in cameras:
                tag = " [Thermal]" if cam.is_thermal else ""
                self.cam_combo.addItem(f"{cam.display_name}{tag}", cam)

        self.btn_scan.setEnabled(True)
        self.btn_scan.setText("🔍 Scan Network (GVCP Port 3956)")

    def _on_camera_selected(self, idx: int):
        cam: Optional[GigEDeviceInfo] = self.cam_combo.itemData(idx)
        if cam:
            self.lbl_model.setText(f"Model: {cam.manufacturer} {cam.model}")
            self.lbl_serial.setText(f"Serial: {cam.serial_number}")
            self.lbl_mac.setText(f"MAC: {cam.mac_address}")
            self.lbl_curr_ip.setText(f"Current IP: {cam.ip_address}")
            self.lbl_curr_subnet.setText(f"Subnet: {cam.subnet_mask}")

            self.txt_ip.setText(cam.ip_address)
            self.txt_subnet.setText(cam.subnet_mask)
            self.txt_gateway.setText(cam.gateway)

    def _on_apply_force_ip(self):
        idx = self.cam_combo.currentIndex()
        cam: Optional[GigEDeviceInfo] = self.cam_combo.itemData(idx)
        if not cam:
            return

        new_ip = self.txt_ip.text().strip()
        subnet = self.txt_subnet.text().strip()
        gw = self.txt_gateway.text().strip()

        ok = force_gige_ip(cam.mac_address, new_ip, subnet, gw)
        if ok:
            QMessageBox.information(self, "ForceIP Successful", f"Camera {cam.model} reconfigured to {new_ip}!")
            self._on_scan_network()
        else:
            QMessageBox.warning(self, "ForceIP Failed", f"Could not set IP for camera {cam.mac_address}. Check physical network connection.")

    def _on_mtu_changed(self, idx: int):
        mtu = self.combo_mtu.itemData(idx)
        if mtu and not self._block_signals:
            self._emit_command("set_packet_size", {"packet_size": mtu})

    def _emit_command(self, command: str, params: dict):
        self.command_requested.emit(command, params)
        if self.event_bus:
            # Route to either thermal or rgb role based on active camera
            self.event_bus.camera_command_requested.emit("thermal", command, params)
            self.event_bus.camera_command_requested.emit("rgb", command, params)

    def update_camera_info(self, info: dict):
        """Update fields from active camera SDK."""
        if "ip_address" in info:
            self.lbl_curr_ip.setText(f"Current IP: {info['ip_address']}")
        if "model" in info:
            self.lbl_model.setText(f"Model: {info['model']}")
        if "serial" in info:
            self.lbl_serial.setText(f"Serial: {info['serial']}")
