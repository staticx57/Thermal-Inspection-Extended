"""
Boson SDK Panel for GUI
Add this to inspection_gui_qt.py before CameraManagerDialog class
"""
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QGroupBox, QComboBox, QFrame, QSlider, QButtonGroup)
from PyQt6.QtCore import pyqtSignal, Qt

class BosonSDKPanel(QGroupBox):
    """Panel for Boson SDK connection controls"""
    
    # Signals
    connect_clicked = pyqtSignal(str)  # COM port
    disconnect_clicked = pyqtSignal()
    ffc_clicked = pyqtSignal()
    scan_ports_clicked = pyqtSignal()
    shutter_position_changed = pyqtSignal(str)  # OPEN/CLOSED/AUTO
    agc_plateau_changed = pyqtSignal(float)  # 0.0-1.0
    agc_dampening_changed = pyqtSignal(float)  # 0.0-1.0
    
    def __init__(self, parent=None):
        super().__init__("Boson SDK Control", parent)
        self._init_ui()
        
    def _init_ui(self):
        layout = QVBoxLayout()
        
        # Connection Status
        status_layout = QHBoxLayout()
        status_layout.addWidget(QLabel("Status:"))
        self.status_label = QLabel("Disconnected")
        self.status_label.setStyleSheet("color: #ff6b6b; font-weight: bold;")
        status_layout.addWidget(self.status_label)
        status_layout.addStretch()
        layout.addLayout(status_layout)
        
        # COM Port Selection
        port_layout = QHBoxLayout()
        port_layout.addWidget(QLabel("COM Port:"))
        self.port_combo = QComboBox()
        self.port_combo.setEditable(True)
        self.port_combo.addItems(["COM1", "COM2", "COM3", "COM4", "COM5", "COM6"])
        self.port_combo.setCurrentText("COM6")
        self.port_combo.setMinimumWidth(100)
        port_layout.addWidget(self.port_combo)
        
        self.scan_btn = QPushButton("🔍")
        self.scan_btn.setToolTip("Scan for available COM ports")
        self.scan_btn.setMaximumWidth(40)
        self.scan_btn.clicked.connect(self._on_scan_ports)
        port_layout.addWidget(self.scan_btn)
        layout.addLayout(port_layout)
        
        # Connect/Disconnect Buttons
        btn_layout = QHBoxLayout()
        self.connect_btn = QPushButton("🔌 Connect")
        self.connect_btn.clicked.connect(self._on_connect)
        btn_layout.addWidget(self.connect_btn)
        
        self.disconnect_btn = QPushButton("🔌 Disconnect")
        self.disconnect_btn.clicked.connect(self._on_disconnect)
        self.disconnect_btn.setEnabled(False)
        btn_layout.addWidget(self.disconnect_btn)
        layout.addLayout(btn_layout)
        
        # FFC Button
        self.ffc_btn = QPushButton("📷 Trigger FFC")
        self.ffc_btn.setToolTip("Flat Field Correction (shutter calibration)")
        self.ffc_btn.clicked.connect(self._on_ffc)
        self.ffc_btn.setEnabled(False)
        layout.addWidget(self.ffc_btn)

        # Separator
        separator1 = QFrame()
        separator1.setFrameShape(QFrame.Shape.HLine)
        separator1.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(separator1)

        # Shutter Control Section
        shutter_label = QLabel("Shutter Control:")
        shutter_label.setStyleSheet("font-weight: bold; margin-top: 5px;")
        layout.addWidget(shutter_label)

        shutter_layout = QHBoxLayout()
        self.shutter_auto_btn = QPushButton("Auto")
        self.shutter_auto_btn.setCheckable(True)
        self.shutter_auto_btn.setChecked(True)
        self.shutter_auto_btn.setToolTip("Automatic shutter control")
        self.shutter_auto_btn.clicked.connect(lambda: self._on_shutter_position("AUTO"))
        shutter_layout.addWidget(self.shutter_auto_btn)

        self.shutter_open_btn = QPushButton("Open")
        self.shutter_open_btn.setCheckable(True)
        self.shutter_open_btn.setToolTip("Force shutter open")
        self.shutter_open_btn.clicked.connect(lambda: self._on_shutter_position("OPEN"))
        shutter_layout.addWidget(self.shutter_open_btn)

        self.shutter_closed_btn = QPushButton("Closed")
        # Disable shutter controls until connected
        self.shutter_auto_btn.setEnabled(False)
        self.shutter_open_btn.setEnabled(False)
        self.shutter_closed_btn.setEnabled(False)

        # Separator
        separator2 = QFrame()
        separator2.setFrameShape(QFrame.Shape.HLine)
        separator2.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(separator2)

        # Advanced AGC Section
        agc_label = QLabel("Advanced AGC:")
        agc_label.setStyleSheet("font-weight: bold; margin-top: 5px;")
        layout.addWidget(agc_label)

        # AGC Plateau Control
        plateau_layout = QHBoxLayout()
        plateau_layout.addWidget(QLabel("Plateau:"))
        self.plateau_slider = QSlider(Qt.Orientation.Horizontal)
        self.plateau_slider.setMinimum(0)
        self.plateau_slider.setMaximum(100)
        self.plateau_slider.setValue(50)
        self.plateau_slider.setToolTip("Histogram plateau equalization (0-100%)")
        self.plateau_slider.valueChanged.connect(self._on_plateau_changed)
        self.plateau_slider.setEnabled(False)
        plateau_layout.addWidget(self.plateau_slider)
        self.plateau_value_label = QLabel("50%")
        self.plateau_value_label.setMinimumWidth(40)
        plateau_layout.addWidget(self.plateau_value_label)
        layout.addLayout(plateau_layout)

        # AGC Dampening Control
        dampening_layout = QHBoxLayout()
        dampening_layout.addWidget(QLabel("Dampening:"))
        self.dampening_slider = QSlider(Qt.Orientation.Horizontal)
        self.dampening_slider.setMinimum(0)
        self.dampening_slider.setMaximum(100)
        self.dampening_slider.setValue(50)
        self.dampening_slider.setToolTip("Temporal smoothing factor (0-100%)")
        self.dampening_slider.valueChanged.connect(self._on_dampening_changed)
        self.dampening_slider.setEnabled(False)
        dampening_layout.addWidget(self.dampening_slider)
        self.dampening_value_label = QLabel("50%")
        self.dampening_value_label.setMinimumWidth(40)
        dampening_layout.addWidget(self.dampening_value_label)
        layout.addLayout(dampening_layout)

        # Status Message
        self.message_label = QLabel("")
        self.message_label.setWordWrap(True)
        self.message_label.setStyleSheet("font-size: 9pt; color: #666;")
        layout.addWidget(self.message_label)

        self.setLayout(layout)
        
    def _on_connect(self):
        """Emit connect signal with selected COM port"""
        port = self.port_combo.currentText()
        self.connect_clicked.emit(port)
        
    def _on_disconnect(self):
        """Emit disconnect signal"""
        self.disconnect_clicked.emit()
        
    def _on_ffc(self):
        """Emit FFC trigger signal"""
        self.ffc_clicked.emit()
        
    def _on_scan_ports(self):
        """Emit scan ports signal"""
        self.scan_ports_clicked.emit()

    def _on_shutter_position(self, position: str):
        """Handle shutter position change"""
        self.shutter_position_changed.emit(position)

    def _on_plateau_changed(self, value: int):
        """Handle AGC plateau slider change"""
        percentage = value / 100.0
        self.plateau_value_label.setText(f"{value}%")
        self.agc_plateau_changed.emit(percentage)

    def _on_dampening_changed(self, value: int):
        """Handle AGC dampening slider change"""
        percentage = value / 100.0
        self.dampening_value_label.setText(f"{value}%")
        self.agc_dampening_changed.emit(percentage)
        
    def set_connected(self, connected: bool):
        """Update UI for connection state"""
        if connected:
            self.status_label.setText("Connected")
            self.status_label.setStyleSheet("color: #51cf66; font-weight: bold;")
            self.connect_btn.setEnabled(False)
            self.disconnect_btn.setEnabled(True)
            self.ffc_btn.setEnabled(True)
            self.port_combo.setEnabled(False)
            self.scan_btn.setEnabled(False)
            # Enable shutter controls
            self.shutter_auto_btn.setEnabled(True)
            self.shutter_open_btn.setEnabled(True)
            self.shutter_closed_btn.setEnabled(True)
            # Enable AGC controls
            self.plateau_slider.setEnabled(True)
            self.dampening_slider.setEnabled(True)
        else:
            self.status_label.setText("Disconnected")
            self.status_label.setStyleSheet("color: #ff6b6b; font-weight: bold;")
            self.connect_btn.setEnabled(True)
            self.disconnect_btn.setEnabled(False)
            self.ffc_btn.setEnabled(False)
            self.port_combo.setEnabled(True)
            self.scan_btn.setEnabled(True)
            # Disable shutter controls
            self.shutter_auto_btn.setEnabled(False)
            self.shutter_open_btn.setEnabled(False)
            self.shutter_closed_btn.setEnabled(False)
            # Disable AGC controls
            self.plateau_slider.setEnabled(False)
            self.dampening_slider.setEnabled(False)
            
    def set_status(self, message: str, is_error: bool = False):
        """Set status message"""
        self.message_label.setText(message)
        if is_error:
            self.message_label.setStyleSheet("font-size: 9pt; color: #ff6b6b;")
        else:
            self.message_label.setStyleSheet("font-size: 9pt; color: #51cf66;")
            
    def update_ports(self, ports: list):
        """Update COM port dropdown"""
        current = self.port_combo.currentText()
        self.port_combo.clear()
        self.port_combo.addItems(ports)
        if current in ports:
            self.port_combo.setCurrentText(current)

    def set_shutter_position(self, position: str):
        """
        Update shutter position button state.

        Args:
            position: "AUTO", "OPEN", or "CLOSED"
        """
        if position == "AUTO":
            self.shutter_auto_btn.setChecked(True)
        elif position == "OPEN":
            self.shutter_open_btn.setChecked(True)
        elif position == "CLOSED":
            self.shutter_closed_btn.setChecked(True)

    def set_agc_plateau(self, value: float):
        """
        Update AGC plateau slider.

        Args:
            value: Plateau value 0.0-1.0
        """
        slider_value = int(value * 100)
        self.plateau_slider.blockSignals(True)
        self.plateau_slider.setValue(slider_value)
        self.plateau_value_label.setText(f"{slider_value}%")
        self.plateau_slider.blockSignals(False)

    def set_agc_dampening(self, value: float):
        """
        Update AGC dampening slider.

        Args:
            value: Dampening value 0.0-1.0
        """
        slider_value = int(value * 100)
        self.dampening_slider.blockSignals(True)
        self.dampening_slider.setValue(slider_value)
        self.dampening_value_label.setText(f"{slider_value}%")
        self.dampening_slider.blockSignals(False)
