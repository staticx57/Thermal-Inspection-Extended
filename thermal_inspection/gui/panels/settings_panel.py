"""
Settings panel for application configuration.
"""

import logging

from PyQt6.QtWidgets import (
    QGroupBox, QVBoxLayout, QHBoxLayout, QLabel,
    QComboBox, QCheckBox, QPushButton
)
from PyQt6.QtCore import pyqtSignal

# Import themes from new location
from thermal_inspection.gui.themes import THEMES, AUTO_THEME_LABEL

logger = logging.getLogger(__name__)


class SettingsPanel(QGroupBox):
    """Panel for application configuration settings."""

    # Signals
    device_changed = pyqtSignal(str)
    theme_changed = pyqtSignal(str)
    palette_changed = pyqtSignal(str)
    baseline_lock_toggled = pyqtSignal(bool)
    com_port_changed = pyqtSignal(str)      # '' = auto-detect

    def __init__(self, parent=None):
        super().__init__("Configuration", parent)
        self._init_ui()

    @staticmethod
    def _detected_ports():
        try:
            import serial.tools.list_ports
            return [p.device for p in serial.tools.list_ports.comports()]
        except Exception:
            return []

    @staticmethod
    def _data_folder_tip() -> str:
        try:
            from thermal_inspection.utils.paths import data_dir
            return (f"Opens {data_dir()}\nconfig.json, the saved alignment calibration, recordings/ and snapshots/ "
                    "live here.")
        except Exception:
            return "Open the folder holding config.json, recordings and snapshots."

    def _emit_port(self):
        text = self.com_port_edit.currentText().strip()
        self.com_port_changed.emit("" if text in ("", self.AUTO_PORT) else text)

    def _open_data_folder(self):
        from PyQt6.QtCore import QUrl
        from PyQt6.QtGui import QDesktopServices
        from thermal_inspection.utils.paths import data_dir
        folder = data_dir()
        folder.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))

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
        self.device_combo.addItems(["CPU", "CUDA", "DirectML"])
        self.device_combo.setToolTip(
            "CUDA: NVIDIA GPU acceleration.\n"
            "DirectML: Intel/AMD GPU acceleration via the torch-directml "
            "package - requires torch-directml installed for this Python "
            "environment (it pins a specific torch version - see "
            "requirements.txt); silently falls back to CPU per-path if "
            "unavailable, same as CUDA does."
        )
        self.device_combo.currentTextChanged.connect(self.device_changed.emit)
        device_layout.addWidget(self.device_combo)
        proc_layout.addLayout(device_layout)

        # Baseline Lock
        self.baseline_check = QCheckBox("Lock Baseline Temp")
        self.baseline_check.setToolTip(
            "Freeze the current frame's average temperature as the reference that change / anomaly detection compares "
            "against. Untick to release it.")
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
        self.theme_combo.addItems([AUTO_THEME_LABEL] + list(THEMES.keys()))
        self.theme_combo.setToolTip("Auto follows your system's light/dark setting and switches live")
        self.theme_combo.currentTextChanged.connect(self.theme_changed.emit)
        theme_layout.addWidget(self.theme_combo)
        sys_layout.addLayout(theme_layout)

        # Control port override (was a dead combo: nothing was connected to it)
        com_layout = QHBoxLayout()
        com_layout.addWidget(QLabel("Control port:"))
        self.com_port_edit = QComboBox()
        self.com_port_edit.setEditable(True)
        self.com_port_edit.setMinimumHeight(28)
        self.com_port_edit.setToolTip(
            "Serial port used to control a Boson or Tau 2 (FFC, gain, radiometry). Auto-detect scans for the camera; "
            "pick a port only to force one. Applies the next time a camera connects.")
        self.AUTO_PORT = "Auto-detect"
        self.com_port_edit.addItem(self.AUTO_PORT)
        for port in self._detected_ports():
            self.com_port_edit.addItem(port)
        override = None
        try:
            from thermal_inspection.utils.config import get_config
            override = get_config().get('sdk_com_port')
        except Exception:
            pass
        if override:
            if self.com_port_edit.findText(override) < 0:
                self.com_port_edit.addItem(override)
            self.com_port_edit.setCurrentText(override)
        self.com_port_edit.activated.connect(lambda _i: self._emit_port())
        self.com_port_edit.lineEdit().editingFinished.connect(self._emit_port)
        com_layout.addWidget(self.com_port_edit)
        sys_layout.addLayout(com_layout)

        # Data folder (was a dead "Storage Paths" button)
        paths_layout = QHBoxLayout()
        self.paths_btn = QPushButton("Open Data Folder")
        self.paths_btn.setToolTip(self._data_folder_tip())
        self.paths_btn.clicked.connect(self._open_data_folder)
        paths_layout.addWidget(self.paths_btn)
        sys_layout.addLayout(paths_layout)

        layout.addWidget(sys_group)

        layout.addStretch()
        self.setLayout(layout)
