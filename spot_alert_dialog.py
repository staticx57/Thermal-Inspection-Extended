
class SpotMeterAlertDialog(QDialog):
    """Dialog to configure spot meter alert."""
    
    def __init__(self, current_alert: Optional[SpotMeterAlert], unit: str = "°C", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configure Alert")
        self.setModal(True)
        self.result_alert = None
        
        layout = QVBoxLayout(self)
        
        # Threshold
        thresh_layout = QHBoxLayout()
        thresh_layout.addWidget(QLabel(f"Threshold ({unit}):"))
        self.thresh_spin = QDoubleSpinBox()
        self.thresh_spin.setRange(-100.0, 1000.0)
        self.thresh_spin.setDecimals(1)
        if current_alert:
            self.thresh_spin.setValue(current_alert.threshold)
        else:
            self.thresh_spin.setValue(30.0)
        thresh_layout.addWidget(self.thresh_spin)
        layout.addLayout(thresh_layout)
        
        # Type (Above/Below)
        type_group = QGroupBox("Condition")
        type_layout = QVBoxLayout(type_group)
        self.above_radio = QRadioButton("Alert when ABOVE threshold")
        self.below_radio = QRadioButton("Alert when BELOW threshold")
        
        if current_alert and current_alert.type == 'below':
            self.below_radio.setChecked(True)
        else:
            self.above_radio.setChecked(True)
            
        type_layout.addWidget(self.above_radio)
        type_layout.addWidget(self.below_radio)
        layout.addWidget(type_group)
        
        # Enabled
        self.enabled_cb = QCheckBox("Enable Alert")
        self.enabled_cb.setChecked(current_alert.enabled if current_alert else True)
        layout.addWidget(self.enabled_cb)
        
        # Buttons
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self._on_accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)
        
    def _on_accept(self):
        alert_type = 'above' if self.above_radio.isChecked() else 'below'
        self.result_alert = SpotMeterAlert(
            threshold=self.thresh_spin.value(),
            type=alert_type,
            enabled=self.enabled_cb.isChecked()
        )
        self.accept()
