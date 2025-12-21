"""
Settings panel for application configuration.
"""

import logging

from PyQt6.QtWidgets import (
    QGroupBox, QVBoxLayout, QHBoxLayout, QLabel,
    QComboBox, QCheckBox, QPushButton, QMessageBox
)
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QFont

# Import themes from new location
from thermal_inspection.gui.themes import THEMES

logger = logging.getLogger(__name__)


class SettingsPanel(QGroupBox):
    """Panel for application configuration settings."""

    # Signals
    device_changed = pyqtSignal(str)
    backend_changed = pyqtSignal(str)
    theme_changed = pyqtSignal(str)
    palette_changed = pyqtSignal(str)
    baseline_lock_toggled = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__("Configuration", parent)
        self._init_ui()

    def _init_ui(self):
        """Initialize widget UI components."""
        layout = QVBoxLayout()
        layout.setSpacing(12)

        # Processing Settings
        proc_group = QGroupBox("Processing")
        proc_layout = QVBoxLayout(proc_group)
        proc_layout.setSpacing(10)
        proc_layout.setContentsMargins(8, 8, 8, 8)

        # Device Selection
        device_layout = QHBoxLayout()
        device_layout.addWidget(QLabel("Device:"))
        self.device_combo = QComboBox()
        self.device_combo.setMinimumHeight(28)
        self.device_combo.addItems(["CPU", "CUDA"])
        self.device_combo.currentTextChanged.connect(self.device_changed.emit)
        device_layout.addWidget(self.device_combo)
        proc_layout.addLayout(device_layout)

        # Baseline Lock
        self.baseline_check = QCheckBox("Lock Baseline Temp")
        self.baseline_check.toggled.connect(self.baseline_lock_toggled.emit)
        proc_layout.addWidget(self.baseline_check)

        layout.addWidget(proc_group)

        # System Settings
        sys_group = QGroupBox("System Configuration")
        sys_layout = QVBoxLayout(sys_group)
        sys_layout.setSpacing(10)
        sys_layout.setContentsMargins(8, 8, 8, 8)

        # Theme Selection
        theme_layout = QHBoxLayout()
        theme_layout.addWidget(QLabel("Theme:"))
        self.theme_combo = QComboBox()
        self.theme_combo.setMinimumHeight(28)
        self.theme_combo.addItems(list(THEMES.keys()))
        self.theme_combo.currentTextChanged.connect(self.theme_changed.emit)
        theme_layout.addWidget(self.theme_combo)
        sys_layout.addLayout(theme_layout)

        # Backend Selection
        backend_layout = QHBoxLayout()
        backend_layout.addWidget(QLabel("Backend:"))
        self.backend_combo = QComboBox()
        self.backend_combo.setMinimumHeight(28)
        self.backend_combo.addItems(["OpenCV (8-bit)", "Flirpy (16-bit Radiometric)"])
        self.backend_combo.setToolTip("Select thermal camera backend. Flirpy required for temperature measurement.")
        self.backend_combo.currentTextChanged.connect(self._on_backend_selection_changed)
        backend_layout.addWidget(self.backend_combo)
        sys_layout.addLayout(backend_layout)

        # COM Port
        com_layout = QHBoxLayout()
        com_layout.addWidget(QLabel("SDK COM Port:"))
        self.com_port_edit = QComboBox()
        self.com_port_edit.setEditable(True)
        self.com_port_edit.setMinimumHeight(28)
        # Use centralized config for COM port options
        try:
            from thermal_inspection.utils.config import get_config
            config = get_config()
            com_ports = config.get('sdk_com_port_options', ["COM3", "COM4", "COM5", "/dev/ttyACM0"])
        except ImportError:
            com_ports = ["COM3", "COM4", "COM5", "/dev/ttyACM0"]
        self.com_port_edit.addItems(com_ports)
        com_layout.addWidget(self.com_port_edit)
        sys_layout.addLayout(com_layout)

        # Paths
        paths_layout = QHBoxLayout()
        self.paths_btn = QPushButton("Storage Paths")
        paths_layout.addWidget(self.paths_btn)
        sys_layout.addLayout(paths_layout)

        layout.addWidget(sys_group)

        layout.addStretch()
        self.setLayout(layout)

    def _on_backend_selection_changed(self, backend_text: str):
        """Validate backend selection before emitting signal."""
        if "Flirpy" in backend_text:
            parent_window = self.window()

            if hasattr(parent_window, 'app') and parent_window.app:
                app = parent_window.app

                has_flir_thermal = False

                if hasattr(app, 'thermal_camera') and app.thermal_camera:
                    if hasattr(app.thermal_camera, '__class__'):
                        class_name = app.thermal_camera.__class__.__name__
                        if 'Flirpy' in class_name or 'Boson' in class_name or 'Lepton' in class_name:
                            has_flir_thermal = True

                    if hasattr(app.thermal_camera, 'is_sdk_connected') and hasattr(app.thermal_camera, 'do_ffc'):
                        has_flir_thermal = True

                    if hasattr(app, 'is_flir_boson') and app.is_flir_boson:
                        has_flir_thermal = True

                if not has_flir_thermal:
                    msg = QMessageBox(parent_window)
                    msg.setIcon(QMessageBox.Icon.Warning)
                    msg.setWindowTitle("Incompatible Backend")
                    msg.setText("Flirpy backend requires a FLIR Boson or Lepton thermal camera.")
                    msg.setInformativeText(
                        "No FLIR Boson/Lepton thermal camera detected.\n\n"
                        "Do you want to proceed anyway?"
                    )
                    msg.setStandardButtons(
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                    )
                    msg.setDefaultButton(QMessageBox.StandardButton.No)

                    result = msg.exec()

                    if result == QMessageBox.StandardButton.No:
                        self.backend_combo.blockSignals(True)
                        self.backend_combo.setCurrentText("OpenCV (8-bit)")
                        self.backend_combo.blockSignals(False)
                        return

        self.backend_changed.emit(backend_text)
