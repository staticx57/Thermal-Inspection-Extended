"""
Boson Camera Control Panel for GUI
Control panel for FLIR Boson SDK connection and camera control
"""
from PyQt6.QtWidgets import (
    QGroupBox, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QRadioButton, QComboBox,
    QCheckBox, QButtonGroup, QWidget, QFrame
)
from PyQt6.QtCore import pyqtSignal, Qt
import logging

logger = logging.getLogger(__name__)


class BosonControlPanel(QGroupBox):
    """Control panel for Boson camera SDK and controls"""
    
    # Signals (COM port connection handled in SettingsPanel)
    ffc_triggered = pyqtSignal()
    gain_mode_changed = pyqtSignal(str)  # 'high', 'low', 'auto'
    ffc_mode_changed = pyqtSignal(str)  # 'manual', 'auto', 'external'
    
    def __init__(self, parent=None):
        super().__init__("🎥 Boson Camera Control", parent)
        self._init_ui()
    
    def _init_ui(self):
        layout = QVBoxLayout()
        
        # === SDK Connection Status (Read-Only) ===
        self._create_connection_status(layout)
        
        # === Camera Information ===
        self._create_camera_info_section(layout)
        
        # === Camera Controls ===
        self._create_controls_section(layout)
        
        self.setLayout(layout)
    
    def _create_connection_status(self, parent_layout):
        """Create read-only SDK connection status display"""
        status_group = QGroupBox("SDK CONNECTION STATUS")
        layout = QVBoxLayout()
        layout.setSpacing(8)
        
        # Connection status label (read-only - COM port selector is in Settings tab)
        self.connection_status_label = QLabel("● Disconnected")
        self.connection_status_label.setStyleSheet("color: #ff4444; font-weight: bold;")
        layout.addWidget(self.connection_status_label)
        
        self.connection_hint = QLabel("COM port configured in Settings tab")
        self.connection_hint.setStyleSheet("font-size: 10px; color: #888;")
        self.connection_hint.setWordWrap(True)
        layout.addWidget(self.connection_hint)
        
        status_group.setLayout(layout)
        parent_layout.addWidget(status_group)
    
    def _create_camera_info_section(self, parent_layout):
        """Create camera information display"""
        info_group = QGroupBox("CAMERA INFORMATION")
        info_group.setMaximumWidth(400)
        layout = QVBoxLayout()
        
        self.info_labels = {}
        
        info_fields = [
            ('serial', 'Serial Number:'),
            ('part_number', 'Part Number:'),
            ('software', 'Software Version:'),
            ('lens', 'Lens Number:'),
            ('table', 'Table Number:')
        ]
        
        for key, label_text in info_fields:
            row = QHBoxLayout()
            label = QLabel(label_text)
            label.setFixedWidth(120)
            label.setStyleSheet("font-weight: bold;")
            
            value_label = QLabel("N/A")
            value_label.setStyleSheet("color: #666;")
            self.info_labels[key] = value_label
            
            row.addWidget(label)
            row.addWidget(value_label)
            row.addStretch()
            layout.addLayout(row)
        
        info_group.setLayout(layout)
        parent_layout.addWidget(info_group)
    
    def _create_controls_section(self, parent_layout):
        """Create camera control widgets"""
        controls_group = QGroupBox("CAMERA CONTROLS")
        layout = QVBoxLayout()
        layout.setSpacing(12)
        
        # FFC (Flat Field Correction)
        ffc_layout = QHBoxLayout()
        self.ffc_button = QPushButton("🔧 Perform FFC")
        self.ffc_button.setMinimumHeight(35)
        self.ffc_button.setToolTip("Trigger Flat Field Correction (camera shutter)")
        self.ffc_button.clicked.connect(self.ffc_triggered.emit)
        ffc_layout.addWidget(self.ffc_button)
        ffc_layout.addStretch()
        layout.addLayout(ffc_layout)
        
        # Gain Mode
        gain_layout = QVBoxLayout()
        gain_label = QLabel("Gain Mode:")
        gain_label.setStyleSheet("font-weight: bold;")
        gain_layout.addWidget(gain_label)
        
        self.gain_button_group = QButtonGroup()
        gain_radio_layout = QHBoxLayout()
        
        self.gain_high = QRadioButton("High")
        self.gain_low = QRadioButton("Low")
        self.gain_auto = QRadioButton("Auto")
        self.gain_auto.setChecked(True)
        
        self.gain_button_group.addButton(self.gain_high)
        self.gain_button_group.addButton(self.gain_low)
        self.gain_button_group.addButton(self.gain_auto)
        
        self.gain_high.toggled.connect(lambda: self._on_gain_mode_changed('high'))
        self.gain_low.toggled.connect(lambda: self._on_gain_mode_changed('low'))
        self.gain_auto.toggled.connect(lambda: self._on_gain_mode_changed('auto'))
        
        gain_radio_layout.addWidget(self.gain_high)
        gain_radio_layout.addWidget(self.gain_low)
        gain_radio_layout.addWidget(self.gain_auto)
        gain_radio_layout.addStretch()
        
        gain_layout.addLayout(gain_radio_layout)
        layout.addLayout(gain_layout)
        
        # FFC Mode
        ffc_mode_layout = QVBoxLayout()
        ffc_mode_label = QLabel("FFC Mode:")
        ffc_mode_label.setStyleSheet("font-weight: bold;")
        ffc_mode_layout.addWidget(ffc_mode_label)
        
        self.ffc_mode_button_group = QButtonGroup()
        ffc_mode_radio_layout = QHBoxLayout()
        
        self.ffc_manual = QRadioButton("Manual")
        self.ffc_auto = QRadioButton("Auto")
        self.ffc_external = QRadioButton("External")
        self.ffc_auto.setChecked(True)
        
        self.ffc_mode_button_group.addButton(self.ffc_manual)
        self.ffc_mode_button_group.addButton(self.ffc_auto)
        self.ffc_mode_button_group.addButton(self.ffc_external)
        
        self.ffc_manual.toggled.connect(lambda: self._on_ffc_mode_changed('manual'))
        self.ffc_auto.toggled.connect(lambda: self._on_ffc_mode_changed('auto'))
        self.ffc_external.toggled.connect(lambda: self._on_ffc_mode_changed('external'))
        
        ffc_mode_radio_layout.addWidget(self.ffc_manual)
        ffc_mode_radio_layout.addWidget(self.ffc_auto)
        ffc_mode_radio_layout.addWidget(self.ffc_external)
        ffc_mode_radio_layout.addStretch()
        
        ffc_mode_layout.addLayout(ffc_mode_radio_layout)
        layout.addLayout(ffc_mode_layout)
        
        controls_group.setLayout(layout)
        parent_layout.addWidget(controls_group)
    
    
    def _on_gain_mode_changed(self, mode):
        """Handle gain mode change"""
        self.gain_mode_changed.emit(mode)
    
    def _on_ffc_mode_changed(self, mode):
        """Handle FFC mode change"""
        self.ffc_mode_changed.emit(mode)
    
    def update_connection_status(self, connected: bool, port: str = None):
        """
        Update SDK connection status display.
        
        Args:
            connected (bool): True if connected, False otherwise
            port (str): Current COM port if connected
        """
        if connected:
            self.connection_status_label.setText("● Connected")
            self.connection_status_label.setStyleSheet("color: #4caf50; font-weight: bold;")
            self.connection_hint.setText(f"Connected to Boson on {port}" if port else "Connected via SDK")
            self.connection_hint.setStyleSheet("font-size: 10px; color: #4caf50;")
        else:
            self.connection_status_label.setText("● Disconnected")
            self.connection_status_label.setStyleSheet("color: #ff4444; font-weight: bold;")
            self.connection_hint.setText("COM port configured in Settings tab")
            self.connection_hint.setStyleSheet("font-size: 10px; color: #888;")
    
    def update_camera_info(self, info: dict):
        """
        Update camera information display.
        
        Args:
            info (dict): Camera information dictionary with keys:
                - serial: Serial number
                - part_number: Part number
                - software: Software version
                - lens: Lens number
                - table: Table number
        """
        for key, label in self.info_labels.items():
            if key in info and info[key]:
                label.setText(str(info[key]))
                label.setStyleSheet("color: #4caf50; font-weight: bold;")
            else:
                label.setText("N/A")
                label.setStyleSheet("color: #666;")
