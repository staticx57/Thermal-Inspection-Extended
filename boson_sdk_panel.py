"""
Boson SDK Panel for GUI
Add this to inspection_gui_qt.py before CameraManagerDialog class
"""

class BosonSDKPanel(QGroupBox):
    """Panel for Boson SDK connection controls"""
    
    # Signals
    connect_clicked = pyqtSignal(str)  # COM port
    disconnect_clicked = pyqtSignal()
    ffc_clicked = pyqtSignal()
    scan_ports_clicked = pyqtSignal()
    
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
        else:
            self.status_label.setText("Disconnected")
            self.status_label.setStyleSheet("color: #ff6b6b; font-weight: bold;")
            self.connect_btn.setEnabled(True)
            self.disconnect_btn.setEnabled(False)
            self.ffc_btn.setEnabled(False)
            self.port_combo.setEnabled(True)
            self.scan_btn.setEnabled(True)
            
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
