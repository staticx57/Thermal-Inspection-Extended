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
from thermal_inspection.gui.themes import THEMES

logger = logging.getLogger(__name__)


class SettingsPanel(QGroupBox):
    """Panel for application configuration settings."""

    # Signals
    device_changed = pyqtSignal(str)
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
