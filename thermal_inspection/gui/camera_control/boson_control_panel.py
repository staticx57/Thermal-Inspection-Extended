"""
FLIR Boson camera control panel widget.

Provides comprehensive SDK controls for FLIR Boson thermal cameras including:
- SDK connection management
- FFC (Flat Field Correction) controls
- Gain mode selection
- AGC (Automatic Gain Control) settings
- Color LUT selection
- Radiometric mode display
- Diagnostics
"""

import logging

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox,
    QLabel, QPushButton, QComboBox, QSlider, QCheckBox,
    QScrollArea, QFrame, QTabWidget, QButtonGroup
)
from PyQt6.QtCore import Qt, pyqtSignal

from thermal_inspection.gui.themes import set_button_state

logger = logging.getLogger(__name__)


class BosonControlPanel(QWidget):
    """FLIR Boson camera control panel widget."""

    # Signals
    sdk_connect_requested = pyqtSignal(str)  # Emits COM port
    sdk_disconnect_requested = pyqtSignal()
    sdk_scan_ports_requested = pyqtSignal()
    ffc_triggered = pyqtSignal()
    gain_mode_changed = pyqtSignal(str)  # 'high', 'low', 'auto'
    ffc_mode_changed = pyqtSignal(str)  # 'manual', 'auto', 'external'
    color_lut_changed = pyqtSignal(str)  # LUT name
    # AGC signals (Universal - ALL Boson cameras)
    agc_max_gain_changed = pyqtSignal(float)  # Max gain (1.0-4.0)
    agc_gamma_changed = pyqtSignal(float)  # Gamma (0.5-2.0)
    agc_linearity_changed = pyqtSignal(float)  # Linearity (0-100%)
    agc_dde_changed = pyqtSignal(float)  # DDE ratio (0.0-3.0)
    agc_reset_requested = pyqtSignal()  # Reset to defaults
    # Advanced controls
    shutter_position_changed = pyqtSignal(str)  # OPEN/CLOSED/AUTO
    agc_plateau_changed = pyqtSignal(float)  # 0.0-1.0
    agc_dampening_changed = pyqtSignal(float)  # 0.0-1.0
    # Radiometric mode control
    radiometric_mode_changed = pyqtSignal(bool)  # True=Radiometric, False=Colorized
    # Environmental compensation
    environmental_settings_changed = pyqtSignal(dict)  # {'emissivity': float, 'atm_temp': float, 'atm_transmission': float}

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()
        self._connect_signals()

    def _init_ui(self):
        """Initialize widget UI components with tabbed submenus."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        self.boson_tabs = QTabWidget()
        main_layout.addWidget(self.boson_tabs)

        # CONNECTION TAB
        self._create_connection_tab()

        # SIMPLE CONTROLS TAB
        self._create_simple_controls_tab()

        # ADVANCED CONTROLS TAB
        self._create_advanced_controls_tab()

        # RADIOMETRIC TAB
        self._create_radiometric_tab()

        # ENVIRONMENT TAB
        self._create_environment_tab()

        # DIAGNOSTICS TAB
        self._create_diagnostics_tab()

    def _create_connection_tab(self):
        """Create the connection tab."""
        connection_tab = QWidget()
        connection_scroll = QScrollArea()
        connection_scroll.setWidgetResizable(True)
        connection_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        connection_scroll.setFrameShape(QFrame.Shape.NoFrame)

        connection_content = QWidget()
        connection_layout = QVBoxLayout(connection_content)
        connection_layout.setSpacing(8)
        connection_layout.setContentsMargins(6, 6, 6, 6)

        self._create_connection_status(connection_layout)
        self._create_camera_info(connection_layout)

        connection_layout.addStretch()
        connection_scroll.setWidget(connection_content)
        connection_tab_layout = QVBoxLayout(connection_tab)
        connection_tab_layout.setContentsMargins(0, 0, 0, 0)
        connection_tab_layout.addWidget(connection_scroll)

        self.boson_tabs.addTab(connection_tab, "Connection")

    def _create_simple_controls_tab(self):
        """Create simple controls tab."""
        simple_tab = QWidget()
        simple_scroll = QScrollArea()
        simple_scroll.setWidgetResizable(True)
        simple_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        simple_scroll.setFrameShape(QFrame.Shape.NoFrame)

        simple_content = QWidget()
        simple_layout = QVBoxLayout(simple_content)
        simple_layout.setSpacing(8)
        simple_layout.setContentsMargins(6, 6, 6, 6)

        self._create_ffc_controls(simple_layout)
        self._create_gain_controls(simple_layout)
        self._create_color_lut_controls(simple_layout)

        simple_layout.addStretch()
        simple_scroll.setWidget(simple_content)
        simple_tab_layout = QVBoxLayout(simple_tab)
        simple_tab_layout.setContentsMargins(0, 0, 0, 0)
        simple_tab_layout.addWidget(simple_scroll)

        self.boson_tabs.addTab(simple_tab, "Controls")

    def _create_advanced_controls_tab(self):
        """Create advanced controls tab."""
        advanced_tab = QWidget()
        advanced_scroll = QScrollArea()
        advanced_scroll.setWidgetResizable(True)
        advanced_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        advanced_scroll.setFrameShape(QFrame.Shape.NoFrame)

        advanced_content = QWidget()
        advanced_layout = QVBoxLayout(advanced_content)
        advanced_layout.setSpacing(8)
        advanced_layout.setContentsMargins(6, 6, 6, 6)

        self._create_agc_controls(advanced_layout)
        self._create_temperature_display(advanced_layout)

        advanced_layout.addStretch()
        advanced_scroll.setWidget(advanced_content)
        advanced_tab_layout = QVBoxLayout(advanced_tab)
        advanced_tab_layout.setContentsMargins(0, 0, 0, 0)
        advanced_tab_layout.addWidget(advanced_scroll)

        self.boson_tabs.addTab(advanced_tab, "Image Enhancement")

    def _create_environment_tab(self):
        """Create environmental compensation tab."""
        env_tab = QWidget()
        env_scroll = QScrollArea()
        env_scroll.setWidgetResizable(True)
        env_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        env_scroll.setFrameShape(QFrame.Shape.NoFrame)

        env_content = QWidget()
        env_layout = QVBoxLayout(env_content)
        env_layout.setSpacing(8)
        env_layout.setContentsMargins(6, 6, 6, 6)

        env_group = QGroupBox("Environmental Compensation")
        env_group_layout = QGridLayout(env_group)
        env_group_layout.setSpacing(6)

        # Info label
        info_label = QLabel(
            "Adjust environmental parameters to improve radiometric accuracy."
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: #888888; font-size: 9pt; padding-bottom: 4px;")
        env_group_layout.addWidget(info_label, 0, 0, 1, 3)

        # Emissivity (0.01 – 1.00, stored ×100 as int)
        env_group_layout.addWidget(QLabel("Emissivity:"), 1, 0)
        self.emissivity_slider = QSlider(Qt.Orientation.Horizontal)
        self.emissivity_slider.setRange(1, 100)
        self.emissivity_slider.setValue(95)  # default 0.95
        self.emissivity_slider.setToolTip("Object emissivity (0.01 – 1.00)")
        env_group_layout.addWidget(self.emissivity_slider, 1, 1)
        self.emissivity_value = QLabel("0.95")
        self.emissivity_value.setFixedWidth(38)
        env_group_layout.addWidget(self.emissivity_value, 1, 2)

        # Atmospheric Temperature (°C, -40 – 60)
        env_group_layout.addWidget(QLabel("Atm. Temp (°C):"), 2, 0)
        self.atm_temp_slider = QSlider(Qt.Orientation.Horizontal)
        self.atm_temp_slider.setRange(-40, 60)
        self.atm_temp_slider.setValue(25)  # default 25 °C
        self.atm_temp_slider.setToolTip("Atmospheric temperature (°C)")
        env_group_layout.addWidget(self.atm_temp_slider, 2, 1)
        self.atm_temp_value = QLabel("25°C")
        self.atm_temp_value.setFixedWidth(38)
        env_group_layout.addWidget(self.atm_temp_value, 2, 2)

        # Atmospheric Transmission (0.50 – 1.00, stored ×100 as int)
        env_group_layout.addWidget(QLabel("Atm. Transmission:"), 3, 0)
        self.atm_trans_slider = QSlider(Qt.Orientation.Horizontal)
        self.atm_trans_slider.setRange(50, 100)
        self.atm_trans_slider.setValue(100)  # default 1.00
        self.atm_trans_slider.setToolTip("Atmospheric transmission (0.50 – 1.00)")
        env_group_layout.addWidget(self.atm_trans_slider, 3, 1)
        self.atm_trans_value = QLabel("1.00")
        self.atm_trans_value.setFixedWidth(38)
        env_group_layout.addWidget(self.atm_trans_value, 3, 2)

        # Apply button - set_button_state (not setStyleSheet) to avoid
        # discarding the active theme's border-radius/padding/border, same
        # reasoning as connect_button above.
        self.env_apply_button = QPushButton("Apply to Camera")
        set_button_state(self.env_apply_button, "accent", "primary")
        env_group_layout.addWidget(self.env_apply_button, 4, 0, 1, 3)

        env_layout.addWidget(env_group)
        env_layout.addStretch()

        env_scroll.setWidget(env_content)
        env_tab_layout = QVBoxLayout(env_tab)
        env_tab_layout.setContentsMargins(0, 0, 0, 0)
        env_tab_layout.addWidget(env_scroll)

        self.boson_tabs.addTab(env_tab, "Environment")

    def _create_radiometric_tab(self):
        """Create radiometric status tab."""
        radiometric_tab = QWidget()
        radiometric_scroll = QScrollArea()
        radiometric_scroll.setWidgetResizable(True)
        radiometric_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        radiometric_scroll.setFrameShape(QFrame.Shape.NoFrame)

        radiometric_content = QWidget()
        radiometric_layout = QVBoxLayout(radiometric_content)
        radiometric_layout.setSpacing(8)
        radiometric_layout.setContentsMargins(6, 6, 6, 6)

        # Unified control notice
        unified_notice = QGroupBox("Unified Radiometric Control")
        unified_layout = QVBoxLayout(unified_notice)
        notice_text = QLabel(
            "<b>Radiometric settings are controlled from:</b><br>"
            "→ <b>Analysis Tab > Radiometric Panel</b><br><br>"
            "This tab shows the current camera mode status."
        )
        notice_text.setWordWrap(True)
        notice_text.setStyleSheet("color: #aaf; font-size: 10px; padding: 8px;")
        unified_layout.addWidget(notice_text)
        radiometric_layout.addWidget(unified_notice)

        # Camera Mode Status
        status_group = QGroupBox("Current Camera Output Mode (Read-Only)")
        status_layout = QVBoxLayout(status_group)

        self.radiometric_mode_status = QLabel("Current Mode: UVC Post-Colorized (8-bit)")
        self.radiometric_mode_status.setStyleSheet(
            "font-weight: bold; padding: 8px; background-color: #2a2a2a; "
            "border-radius: 3px; font-size: 11px;"
        )
        self.radiometric_mode_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        status_layout.addWidget(self.radiometric_mode_status)

        mode_explain = QLabel(
            "• <b>T-Linear Radiometric (16-bit)</b>: Precise temperature measurement<br>"
            "• <b>Colorized (8-bit)</b>: Visual thermal imaging with AGC"
        )
        mode_explain.setWordWrap(True)
        mode_explain.setStyleSheet("color: gray; font-size: 9px; padding: 8px;")
        status_layout.addWidget(mode_explain)

        radiometric_layout.addWidget(status_group)
        radiometric_layout.addStretch()
        radiometric_scroll.setWidget(radiometric_content)
        radiometric_tab_layout = QVBoxLayout(radiometric_tab)
        radiometric_tab_layout.setContentsMargins(0, 0, 0, 0)
        radiometric_tab_layout.addWidget(radiometric_scroll)

        self.boson_tabs.addTab(radiometric_tab, "Radiometric")

    def _create_diagnostics_tab(self):
        """Create diagnostics tab."""
        diagnostics_tab = QWidget()
        diagnostics_scroll = QScrollArea()
        diagnostics_scroll.setWidgetResizable(True)
        diagnostics_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        diagnostics_scroll.setFrameShape(QFrame.Shape.NoFrame)

        diagnostics_content = QWidget()
        diagnostics_layout = QVBoxLayout(diagnostics_content)
        diagnostics_layout.setSpacing(8)
        diagnostics_layout.setContentsMargins(6, 6, 6, 6)

        # System Status
        system_group = QGroupBox("System Status")
        system_layout = QVBoxLayout(system_group)

        frame_layout = QHBoxLayout()
        frame_layout.addWidget(QLabel("Frame Count:"))
        self.diag_frame_count_label = QLabel("--")
        self.diag_frame_count_label.setStyleSheet("font-weight: bold;")
        frame_layout.addWidget(self.diag_frame_count_label)
        frame_layout.addStretch()
        system_layout.addLayout(frame_layout)

        board_temp_layout = QHBoxLayout()
        board_temp_layout.addWidget(QLabel("Board Temp:"))
        self.diag_board_temp_label = QLabel("--")
        self.diag_board_temp_label.setStyleSheet("font-weight: bold;")
        board_temp_layout.addWidget(self.diag_board_temp_label)
        board_temp_layout.addStretch()
        system_layout.addLayout(board_temp_layout)

        fpa_temp_layout = QHBoxLayout()
        fpa_temp_layout.addWidget(QLabel("FPA Temp:"))
        self.diag_fpa_temp_label = QLabel("--")
        self.diag_fpa_temp_label.setStyleSheet("font-weight: bold;")
        fpa_temp_layout.addWidget(self.diag_fpa_temp_label)
        fpa_temp_layout.addStretch()
        system_layout.addLayout(fpa_temp_layout)

        diagnostics_layout.addWidget(system_group)

        # FFC Status
        ffc_status_group = QGroupBox("FFC Status")
        ffc_status_layout = QVBoxLayout(ffc_status_group)

        last_ffc_frame_layout = QHBoxLayout()
        last_ffc_frame_layout.addWidget(QLabel("Last FFC Frame:"))
        self.diag_last_ffc_frame_label = QLabel("--")
        self.diag_last_ffc_frame_label.setStyleSheet("font-weight: bold;")
        last_ffc_frame_layout.addWidget(self.diag_last_ffc_frame_label)
        last_ffc_frame_layout.addStretch()
        ffc_status_layout.addLayout(last_ffc_frame_layout)

        frames_since_layout = QHBoxLayout()
        frames_since_layout.addWidget(QLabel("Frames Since FFC:"))
        self.diag_frames_since_ffc_label = QLabel("--")
        self.diag_frames_since_ffc_label.setStyleSheet("font-weight: bold;")
        frames_since_layout.addWidget(self.diag_frames_since_ffc_label)
        frames_since_layout.addStretch()
        ffc_status_layout.addLayout(frames_since_layout)

        last_ffc_temp_layout = QHBoxLayout()
        last_ffc_temp_layout.addWidget(QLabel("Last FFC Temp:"))
        self.diag_last_ffc_temp_label = QLabel("--")
        self.diag_last_ffc_temp_label.setStyleSheet("font-weight: bold;")
        last_ffc_temp_layout.addWidget(self.diag_last_ffc_temp_label)
        last_ffc_temp_layout.addStretch()
        ffc_status_layout.addLayout(last_ffc_temp_layout)

        ffc_threshold_layout = QHBoxLayout()
        ffc_threshold_layout.addWidget(QLabel("Auto FFC Threshold:"))
        self.diag_ffc_threshold_label = QLabel("--")
        self.diag_ffc_threshold_label.setStyleSheet("font-weight: bold;")
        ffc_threshold_layout.addWidget(self.diag_ffc_threshold_label)
        ffc_threshold_layout.addStretch()
        ffc_status_layout.addLayout(ffc_threshold_layout)

        diagnostics_layout.addWidget(ffc_status_group)

        refresh_btn = QPushButton("Refresh Diagnostics")
        refresh_btn.clicked.connect(self._on_refresh_diagnostics)
        diagnostics_layout.addWidget(refresh_btn)

        diagnostics_layout.addStretch()
        diagnostics_scroll.setWidget(diagnostics_content)
        diagnostics_tab_layout = QVBoxLayout(diagnostics_tab)
        diagnostics_tab_layout.setContentsMargins(0, 0, 0, 0)
        diagnostics_tab_layout.addWidget(diagnostics_scroll)

        self.boson_tabs.addTab(diagnostics_tab, "Diagnostics")

    def _create_connection_status(self, layout):
        """Create SDK connection status display and controls."""
        status_group = QGroupBox("Serial Connection")
        status_layout = QVBoxLayout(status_group)

        status_label_layout = QHBoxLayout()
        self.connection_status_label = QLabel("● Disconnected")
        self.connection_status_label.setStyleSheet("color: #ff4444; font-weight: bold;")
        self.connection_status_label.setMaximumWidth(200)
        status_label_layout.addWidget(self.connection_status_label)
        status_label_layout.addStretch()
        status_layout.addLayout(status_label_layout)

        port_layout = QHBoxLayout()
        port_label = QLabel("COM Port:")
        port_label.setFixedWidth(80)
        port_layout.addWidget(port_label)

        self.com_port_combo = QComboBox()
        self.com_port_combo.setEditable(True)
        self.com_port_combo.setPlaceholderText("COM Port")
        self.com_port_combo.setToolTip("Select COM port or enter manually")
        self.com_port_combo.setMaximumWidth(150)
        port_layout.addWidget(self.com_port_combo)

        self.scan_ports_button = QPushButton("Scan")
        self.scan_ports_button.setFixedWidth(50)
        self.scan_ports_button.setToolTip("Scan for available COM ports")
        port_layout.addWidget(self.scan_ports_button)
        port_layout.addStretch()
        status_layout.addLayout(port_layout)

        button_layout = QHBoxLayout()
        self.connect_button = QPushButton("Connect")
        self.connect_button.setMinimumHeight(35)
        self.connect_button.setMaximumWidth(150)
        # setProperty (not setStyleSheet) - see STATE_COLORS_QSS's docstring:
        # a full setStyleSheet() override here discarded the active theme's
        # border-radius/padding/border, flattening this one button while
        # every other button on the panel kept its themed shape.
        set_button_state(self.connect_button, "accent", "primary")
        self.connect_button.setToolTip("Connect to Boson camera via SDK")
        button_layout.addWidget(self.connect_button)

        self.disconnect_button = QPushButton("Disconnect")
        self.disconnect_button.setMinimumHeight(35)
        self.disconnect_button.setMaximumWidth(150)
        self.disconnect_button.setEnabled(False)
        self.disconnect_button.setToolTip("Disconnect from SDK")
        button_layout.addWidget(self.disconnect_button)
        button_layout.addStretch()
        status_layout.addLayout(button_layout)

        self.connection_hint = QLabel("Connect via COM port or use --enable-boson-sdk flag")
        self.connection_hint.setStyleSheet("font-size: 10px; color: #888888;")
        self.connection_hint.setWordWrap(True)
        self.connection_hint.setMaximumWidth(350)
        status_layout.addWidget(self.connection_hint)

        layout.addWidget(status_group)

    def _create_camera_info(self, layout):
        """Create camera info display."""
        info_group = QGroupBox("Camera Information")
        info_layout = QVBoxLayout(info_group)

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
            value = QLabel("N/A")
            value.setStyleSheet("color: #888888;")
            value.setWordWrap(True)
            value.setMaximumWidth(200)

            row.addWidget(label)
            row.addWidget(value)
            row.addStretch()

            self.info_labels[key] = value
            info_layout.addLayout(row)

        layout.addWidget(info_group)

    def _create_ffc_controls(self, layout):
        """Create FFC control buttons."""
        ffc_group = QGroupBox("Flat Field Correction (FFC)")
        ffc_layout = QVBoxLayout(ffc_group)

        self.ffc_button = QPushButton("Trigger FFC")
        self.ffc_button.setMinimumHeight(40)
        self.ffc_button.setToolTip("Manually trigger Flat Field Correction")
        ffc_layout.addWidget(self.ffc_button)

        ffc_mode_layout = QHBoxLayout()
        ffc_label = QLabel("FFC Mode:")
        ffc_label.setFixedWidth(80)
        ffc_mode_layout.addWidget(ffc_label)

        self.ffc_mode_combo = QComboBox()
        self.ffc_mode_combo.addItems(['Manual', 'Auto', 'External'])
        self.ffc_mode_combo.setToolTip("FFC mode: Manual, Auto, or External trigger")
        self.ffc_mode_combo.setMinimumHeight(28)
        self.ffc_mode_combo.setMaximumWidth(150)
        ffc_mode_layout.addWidget(self.ffc_mode_combo)
        ffc_mode_layout.addStretch()
        ffc_layout.addLayout(ffc_mode_layout)

        self.ffc_status_label = QLabel("Status: Ready")
        self.ffc_status_label.setStyleSheet("font-size: 10px; color: #888888;")
        ffc_layout.addWidget(self.ffc_status_label)

        layout.addWidget(ffc_group)
        self._create_shutter_controls(layout)

    def _create_shutter_controls(self, layout):
        """Create shutter position control buttons."""
        shutter_group = QGroupBox("Shutter Control")
        shutter_layout = QVBoxLayout(shutter_group)

        button_layout = QHBoxLayout()

        self.shutter_auto_btn = QPushButton("Auto")
        self.shutter_auto_btn.setCheckable(True)
        self.shutter_auto_btn.setChecked(True)
        self.shutter_auto_btn.setToolTip("Automatic shutter control (recommended)")
        self.shutter_auto_btn.setMinimumHeight(32)
        button_layout.addWidget(self.shutter_auto_btn)

        self.shutter_open_btn = QPushButton("Open")
        self.shutter_open_btn.setCheckable(True)
        self.shutter_open_btn.setToolTip("Force shutter open (imaging mode)")
        self.shutter_open_btn.setMinimumHeight(32)
        button_layout.addWidget(self.shutter_open_btn)

        self.shutter_closed_btn = QPushButton("Closed")
        self.shutter_closed_btn.setCheckable(True)
        self.shutter_closed_btn.setToolTip("Force shutter closed (calibration)")
        self.shutter_closed_btn.setMinimumHeight(32)
        button_layout.addWidget(self.shutter_closed_btn)

        shutter_layout.addLayout(button_layout)

        self.shutter_btn_group = QButtonGroup()
        self.shutter_btn_group.addButton(self.shutter_auto_btn)
        self.shutter_btn_group.addButton(self.shutter_open_btn)
        self.shutter_btn_group.addButton(self.shutter_closed_btn)
        self.shutter_btn_group.setExclusive(True)

        self.shutter_status_label = QLabel("Position: Auto")
        self.shutter_status_label.setStyleSheet("font-size: 10px; color: #888888;")
        shutter_layout.addWidget(self.shutter_status_label)

        layout.addWidget(shutter_group)

    def _create_gain_controls(self, layout):
        """Create gain mode controls."""
        gain_group = QGroupBox("Gain Mode")
        gain_layout = QVBoxLayout(gain_group)

        combo_layout = QHBoxLayout()
        self.gain_mode_combo = QComboBox()
        self.gain_mode_combo.addItems(['High', 'Low', 'Auto'])
        self.gain_mode_combo.setToolTip("Sensor gain mode")
        self.gain_mode_combo.setMinimumHeight(28)
        self.gain_mode_combo.setMaximumWidth(150)
        combo_layout.addWidget(self.gain_mode_combo)
        combo_layout.addStretch()
        gain_layout.addLayout(combo_layout)

        self.current_gain_label = QLabel("Current: Auto")
        self.current_gain_label.setStyleSheet("font-size: 10px; color: #888888;")
        gain_layout.addWidget(self.current_gain_label)

        layout.addWidget(gain_group)

    def _create_color_lut_controls(self, layout):
        """Create color LUT controls."""
        lut_group = QGroupBox("Color Lookup Table (LUT)")
        lut_layout = QVBoxLayout(lut_group)

        combo_layout = QHBoxLayout()
        self.color_lut_combo = QComboBox()
        self.color_lut_combo.addItems([
            'White Hot', 'Black Hot', 'Rainbow', 'Rainbow HC',
            'Ironbow', 'Lava', 'Arctic', 'Globow',
            'Graded Fire', 'Hottest'
        ])
        self.color_lut_combo.setToolTip("Hardware color palette (applies on-camera)")
        self.color_lut_combo.setMinimumHeight(28)
        self.color_lut_combo.setMaximumWidth(180)
        combo_layout.addWidget(self.color_lut_combo)
        combo_layout.addStretch()
        lut_layout.addLayout(combo_layout)

        hint = QLabel("Note: Hardware LUT applies before software processing")
        hint.setStyleSheet("font-size: 9px; color: #888888;")
        hint.setWordWrap(True)
        lut_layout.addWidget(hint)

        layout.addWidget(lut_group)

    def _create_agc_controls(self, layout):
        """Create AGC (Automatic Gain Control) controls."""
        agc_group = QGroupBox("AGC Settings")
        agc_layout = QVBoxLayout(agc_group)

        info_label = QLabel("Works on ALL Boson cameras (radiometric and non-radiometric)")
        info_label.setStyleSheet("font-size: 9px; color: #4CAF50; font-weight: bold;")
        info_label.setWordWrap(True)
        agc_layout.addWidget(info_label)

        # Max Gain slider
        max_gain_layout = QVBoxLayout()
        max_gain_header = QHBoxLayout()
        max_gain_header.addWidget(QLabel("Max Gain (Contrast):"))
        self.agc_max_gain_value = QLabel("2.0x")
        self.agc_max_gain_value.setStyleSheet("font-weight: bold; color: #00aaff;")
        max_gain_header.addWidget(self.agc_max_gain_value)
        max_gain_header.addStretch()
        max_gain_layout.addLayout(max_gain_header)

        self.agc_max_gain_slider = QSlider(Qt.Orientation.Horizontal)
        self.agc_max_gain_slider.setRange(10, 40)
        self.agc_max_gain_slider.setValue(20)
        self.agc_max_gain_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.agc_max_gain_slider.setTickInterval(5)
        self.agc_max_gain_slider.setToolTip("Limit maximum contrast enhancement (1.0-4.0x)")
        max_gain_layout.addWidget(self.agc_max_gain_slider)
        agc_layout.addLayout(max_gain_layout)

        # Gamma slider
        gamma_layout = QVBoxLayout()
        gamma_header = QHBoxLayout()
        gamma_header.addWidget(QLabel("Gamma (ACE):"))
        self.agc_gamma_value = QLabel("1.0")
        self.agc_gamma_value.setStyleSheet("font-weight: bold; color: #00aaff;")
        gamma_header.addWidget(self.agc_gamma_value)
        gamma_header.addStretch()
        gamma_layout.addLayout(gamma_header)

        self.agc_gamma_slider = QSlider(Qt.Orientation.Horizontal)
        self.agc_gamma_slider.setRange(5, 20)
        self.agc_gamma_slider.setValue(10)
        self.agc_gamma_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.agc_gamma_slider.setTickInterval(5)
        self.agc_gamma_slider.setToolTip("Gamma correction")
        gamma_layout.addWidget(self.agc_gamma_slider)
        agc_layout.addLayout(gamma_layout)

        # Linearity slider
        linearity_layout = QVBoxLayout()
        linearity_header = QHBoxLayout()
        linearity_header.addWidget(QLabel("Linearity:"))
        self.agc_linearity_value = QLabel("50%")
        self.agc_linearity_value.setStyleSheet("font-weight: bold; color: #00aaff;")
        linearity_header.addWidget(self.agc_linearity_value)
        linearity_header.addStretch()
        linearity_layout.addLayout(linearity_header)

        self.agc_linearity_slider = QSlider(Qt.Orientation.Horizontal)
        self.agc_linearity_slider.setRange(0, 100)
        self.agc_linearity_slider.setValue(50)
        self.agc_linearity_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.agc_linearity_slider.setTickInterval(20)
        self.agc_linearity_slider.setToolTip("Histogram vs. linear")
        linearity_layout.addWidget(self.agc_linearity_slider)
        agc_layout.addLayout(linearity_layout)

        # DDE slider
        dde_layout = QVBoxLayout()
        dde_header = QHBoxLayout()
        dde_header.addWidget(QLabel("Detail (DDE):"))
        self.agc_dde_value = QLabel("1.3")
        self.agc_dde_value.setStyleSheet("font-weight: bold; color: #00aaff;")
        dde_header.addWidget(self.agc_dde_value)
        dde_header.addStretch()
        dde_layout.addLayout(dde_header)

        self.agc_dde_slider = QSlider(Qt.Orientation.Horizontal)
        self.agc_dde_slider.setRange(0, 30)
        self.agc_dde_slider.setValue(13)
        self.agc_dde_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.agc_dde_slider.setTickInterval(5)
        self.agc_dde_slider.setToolTip("Detail enhancement")
        dde_layout.addWidget(self.agc_dde_slider)
        agc_layout.addLayout(dde_layout)

        # Separator
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        agc_layout.addWidget(separator)

        # Plateau slider
        plateau_layout = QVBoxLayout()
        plateau_header = QHBoxLayout()
        plateau_header.addWidget(QLabel("Plateau:"))
        self.agc_plateau_value = QLabel("50%")
        self.agc_plateau_value.setStyleSheet("font-weight: bold; color: #00aaff;")
        plateau_header.addWidget(self.agc_plateau_value)
        plateau_header.addStretch()
        plateau_layout.addLayout(plateau_header)

        self.agc_plateau_slider = QSlider(Qt.Orientation.Horizontal)
        self.agc_plateau_slider.setRange(0, 100)
        self.agc_plateau_slider.setValue(50)
        self.agc_plateau_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.agc_plateau_slider.setTickInterval(20)
        self.agc_plateau_slider.setToolTip("Histogram plateau equalization")
        plateau_layout.addWidget(self.agc_plateau_slider)
        agc_layout.addLayout(plateau_layout)

        # Dampening slider
        dampening_layout = QVBoxLayout()
        dampening_header = QHBoxLayout()
        dampening_header.addWidget(QLabel("Dampening:"))
        self.agc_dampening_value = QLabel("50%")
        self.agc_dampening_value.setStyleSheet("font-weight: bold; color: #00aaff;")
        dampening_header.addWidget(self.agc_dampening_value)
        dampening_header.addStretch()
        dampening_layout.addLayout(dampening_header)

        self.agc_dampening_slider = QSlider(Qt.Orientation.Horizontal)
        self.agc_dampening_slider.setRange(0, 100)
        self.agc_dampening_slider.setValue(50)
        self.agc_dampening_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.agc_dampening_slider.setTickInterval(20)
        self.agc_dampening_slider.setToolTip("Temporal smoothing factor")
        dampening_layout.addWidget(self.agc_dampening_slider)
        agc_layout.addLayout(dampening_layout)

        # Reset button
        self.agc_reset_button = QPushButton("Reset to Defaults")
        self.agc_reset_button.setMinimumHeight(30)
        self.agc_reset_button.setToolTip("Reset all AGC settings to defaults")
        agc_layout.addWidget(self.agc_reset_button)

        layout.addWidget(agc_group)

    def _create_temperature_display(self, layout):
        """Create FPA temperature display."""
        temp_group = QGroupBox("FPA Temperature")
        temp_layout = QVBoxLayout(temp_group)

        self.fpa_temp_label = QLabel("N/A")
        self.fpa_temp_label.setStyleSheet("font-size: 24px; font-weight: bold; color: #00aaff;")
        self.fpa_temp_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        temp_layout.addWidget(self.fpa_temp_label)

        self.fpa_temp_unit = QLabel("Focal Plane Array Temperature")
        self.fpa_temp_unit.setStyleSheet("font-size: 10px; color: #888888;")
        self.fpa_temp_unit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        temp_layout.addWidget(self.fpa_temp_unit)

        refresh_layout = QHBoxLayout()
        self.temp_auto_refresh = QCheckBox("Auto-refresh (1s)")
        self.temp_auto_refresh.setChecked(True)
        self.temp_auto_refresh.setToolTip("Automatically read temperature every second")
        refresh_layout.addWidget(self.temp_auto_refresh)
        refresh_layout.addStretch()
        temp_layout.addLayout(refresh_layout)

        layout.addWidget(temp_group)

    def _connect_signals(self):
        """Connect internal signals."""
        self.connect_button.clicked.connect(self._on_connect_clicked)
        self.disconnect_button.clicked.connect(lambda: self.sdk_disconnect_requested.emit())
        self.scan_ports_button.clicked.connect(self._on_scan_ports_clicked)

        self.ffc_button.clicked.connect(lambda: self.ffc_triggered.emit())
        self.gain_mode_combo.currentTextChanged.connect(
            lambda text: self.gain_mode_changed.emit(text.lower())
        )
        self.ffc_mode_combo.currentTextChanged.connect(
            lambda text: self.ffc_mode_changed.emit(text.lower())
        )
        self.color_lut_combo.currentTextChanged.connect(
            lambda text: self.color_lut_changed.emit(text.lower().replace(' ', '_'))
        )

        self.agc_max_gain_slider.valueChanged.connect(self._on_agc_max_gain_changed)
        self.agc_gamma_slider.valueChanged.connect(self._on_agc_gamma_changed)
        self.agc_linearity_slider.valueChanged.connect(self._on_agc_linearity_changed)
        self.agc_dde_slider.valueChanged.connect(self._on_agc_dde_changed)
        self.agc_plateau_slider.valueChanged.connect(self._on_agc_plateau_changed)
        self.agc_dampening_slider.valueChanged.connect(self._on_agc_dampening_changed)
        self.agc_reset_button.clicked.connect(self._on_agc_reset_clicked)

        self.shutter_auto_btn.clicked.connect(lambda: self._on_shutter_position_changed("AUTO"))
        self.shutter_open_btn.clicked.connect(lambda: self._on_shutter_position_changed("OPEN"))
        self.shutter_closed_btn.clicked.connect(lambda: self._on_shutter_position_changed("CLOSED"))

        # Environmental compensation
        self.emissivity_slider.valueChanged.connect(
            lambda v: self.emissivity_value.setText(f"{v / 100:.2f}")
        )
        self.atm_temp_slider.valueChanged.connect(
            lambda v: self.atm_temp_value.setText(f"{v}°C")
        )
        self.atm_trans_slider.valueChanged.connect(
            lambda v: self.atm_trans_value.setText(f"{v / 100:.2f}")
        )
        self.env_apply_button.clicked.connect(self._on_env_apply_clicked)

    def _on_connect_clicked(self):
        """Handle connect button click."""
        com_port = self.com_port_combo.currentText().strip()
        self.sdk_connect_requested.emit(com_port if com_port else "")

    def _on_env_apply_clicked(self):
        """Emit environmental settings to the app for SDK application."""
        settings = {
            'emissivity': self.emissivity_slider.value() / 100.0,
            'atm_temp': float(self.atm_temp_slider.value()),
            'atm_transmission': self.atm_trans_slider.value() / 100.0,
        }
        self.environmental_settings_changed.emit(settings)
        logger.info(f"Environmental settings applied: {settings}")

    def _on_scan_ports_clicked(self):
        """Handle scan ports button click."""
        self.sdk_scan_ports_requested.emit()

    def _on_agc_max_gain_changed(self, value: int):
        """Handle max gain slider change."""
        gain = value / 10.0
        self.agc_max_gain_value.setText(f"{gain:.1f}x")
        self.agc_max_gain_changed.emit(gain)

    def _on_agc_gamma_changed(self, value: int):
        """Handle gamma slider change."""
        gamma = value / 10.0
        self.agc_gamma_value.setText(f"{gamma:.1f}")
        self.agc_gamma_changed.emit(gamma)

    def _on_agc_linearity_changed(self, value: int):
        """Handle linearity slider change."""
        self.agc_linearity_value.setText(f"{value}%")
        self.agc_linearity_changed.emit(float(value))

    def _on_agc_dde_changed(self, value: int):
        """Handle DDE slider change."""
        dde = value / 10.0
        self.agc_dde_value.setText(f"{dde:.1f}")
        self.agc_dde_changed.emit(dde)

    def _on_agc_plateau_changed(self, value: int):
        """Handle AGC plateau slider change."""
        self.agc_plateau_value.setText(f"{value}%")
        self.agc_plateau_changed.emit(value / 100.0)

    def _on_agc_dampening_changed(self, value: int):
        """Handle AGC dampening slider change."""
        self.agc_dampening_value.setText(f"{value}%")
        self.agc_dampening_changed.emit(value / 100.0)

    def _on_agc_reset_clicked(self):
        """Reset AGC controls to defaults."""
        self.agc_max_gain_slider.setValue(20)
        self.agc_gamma_slider.setValue(10)
        self.agc_linearity_slider.setValue(50)
        self.agc_dde_slider.setValue(13)
        self.agc_plateau_slider.setValue(50)
        self.agc_dampening_slider.setValue(50)
        self.agc_reset_requested.emit()

    def _on_shutter_position_changed(self, position: str):
        """Handle shutter position button change."""
        self.shutter_status_label.setText(f"Position: {position.capitalize()}")
        self.shutter_position_changed.emit(position)

    def _on_refresh_diagnostics(self):
        """Refresh diagnostics data from the Boson SDK."""
        try:
            # Access the thermal camera via the app reference
            app = None
            parent = self.parent()
            while parent is not None:
                if hasattr(parent, 'app'):
                    app = parent.app
                    break
                parent = parent.parent()

            if app is None or not hasattr(app, 'thermal_camera'):
                logger.debug("Cannot refresh diagnostics: no app reference")
                return

            cam = app.thermal_camera
            if cam is None:
                return

            # Try SDK wrapper's get_system_status()
            if hasattr(cam, 'get_system_status'):
                status = cam.get_system_status()
                if status:
                    self.update_diagnostics(status)
                    logger.info("Diagnostics refreshed from SDK")
        except Exception as e:
            logger.error(f"Error refreshing diagnostics: {e}")

    def update_connection_status(self, connected: bool, port: str = None):
        """Update SDK connection status and button states."""
        if connected:
            self.connection_status_label.setText("● Connected")
            self.connection_status_label.setStyleSheet("color: #4CAF50; font-weight: bold;")
            self.connection_hint.setText("SDK features available")
            self.connect_button.setEnabled(False)
            self.disconnect_button.setEnabled(True)
            self.com_port_combo.setEnabled(False)
            self.scan_ports_button.setEnabled(False)
            self.ffc_button.setEnabled(True)
            self.gain_mode_combo.setEnabled(True)
            self.ffc_mode_combo.setEnabled(True)
            self.color_lut_combo.setEnabled(True)
            self.agc_max_gain_slider.setEnabled(True)
            self.agc_gamma_slider.setEnabled(True)
            self.agc_linearity_slider.setEnabled(True)
            self.agc_dde_slider.setEnabled(True)
            self.agc_plateau_slider.setEnabled(True)
            self.agc_dampening_slider.setEnabled(True)
            self.agc_reset_button.setEnabled(True)
            self.shutter_auto_btn.setEnabled(True)
            self.shutter_open_btn.setEnabled(True)
            self.shutter_closed_btn.setEnabled(True)
        else:
            self.connection_status_label.setText("● Disconnected")
            self.connection_status_label.setStyleSheet("color: #ff4444; font-weight: bold;")
            self.connection_hint.setText("Connect via COM port or use --enable-boson-sdk flag")
            self.connect_button.setEnabled(True)
            self.disconnect_button.setEnabled(False)
            self.com_port_combo.setEnabled(True)
            self.scan_ports_button.setEnabled(True)
            self.ffc_button.setEnabled(False)
            self.gain_mode_combo.setEnabled(False)
            self.ffc_mode_combo.setEnabled(False)
            self.color_lut_combo.setEnabled(False)
            self.agc_max_gain_slider.setEnabled(False)
            self.agc_gamma_slider.setEnabled(False)
            self.agc_linearity_slider.setEnabled(False)
            self.agc_dde_slider.setEnabled(False)
            self.agc_plateau_slider.setEnabled(False)
            self.agc_dampening_slider.setEnabled(False)
            self.agc_reset_button.setEnabled(False)
            self.shutter_auto_btn.setEnabled(False)
            self.shutter_open_btn.setEnabled(False)
            self.shutter_closed_btn.setEnabled(False)

    def update_com_ports(self, ports: list):
        """Update COM port dropdown with available ports."""
        current = self.com_port_combo.currentText()
        self.com_port_combo.clear()
        self.com_port_combo.addItems(ports)
        if current in ports:
            self.com_port_combo.setCurrentText(current)

    def update_camera_info(self, info: dict):
        """Update camera information display.

        `info` is the dict returned by CameraSDK.execute("get_camera_info")
        (see plugins/boson/plugin.py), not the raw BosonInfo SDK object.
        """
        if not info:
            return

        if info.get('serial'):
            self.info_labels['serial'].setText(str(info['serial']))
            self.info_labels['serial'].setStyleSheet("color: #e0e0e0;")

        if info.get('part_number'):
            self.info_labels['part_number'].setText(str(info['part_number']))
            self.info_labels['part_number'].setStyleSheet("color: #e0e0e0;")

        if info.get('firmware'):
            self.info_labels['software'].setText(str(info['firmware']))
            self.info_labels['software'].setStyleSheet("color: #e0e0e0;")

        if info.get('lens_number') is not None:
            self.info_labels['lens'].setText(str(info['lens_number']))
            self.info_labels['lens'].setStyleSheet("color: #e0e0e0;")

        if info.get('table_number') is not None:
            self.info_labels['table'].setText(str(info['table_number']))
            self.info_labels['table'].setStyleSheet("color: #e0e0e0;")

        if info.get('gain_mode'):
            self.current_gain_label.setText(f"Current: {info['gain_mode']}")
            self.current_gain_label.setStyleSheet("font-size: 10px; color: #00aaff;")

    def update_fpa_temperature(self, temp_kelvin: float, temp_celsius: float):
        """Update FPA temperature display."""
        self.fpa_temp_label.setText(f"{temp_celsius:.1f}°C")
        self.fpa_temp_unit.setText(f"({temp_kelvin:.1f}K)")

    def set_ffc_status(self, message: str, is_error: bool = False):
        """Update FFC status message."""
        color = "#ff4444" if is_error else "#4CAF50"
        self.ffc_status_label.setText(f"Status: {message}")
        self.ffc_status_label.setStyleSheet(f"font-size: 10px; color: {color};")

    def set_status(self, message: str, is_error: bool = False):
        """Update connection hint/status message."""
        color = "#ff4444" if is_error else "#4CAF50"
        self.connection_hint.setText(message)
        self.connection_hint.setStyleSheet(f"font-size: 10px; color: {color};")

    def update_ports(self, ports: list):
        """Update COM port dropdown with scanned ports."""
        current = self.com_port_combo.currentText()
        self.com_port_combo.clear()
        if ports:
            self.com_port_combo.addItems(ports)
            if current in ports:
                self.com_port_combo.setCurrentText(current)
        else:
            self.com_port_combo.setPlaceholderText("No ports found")

    def update_diagnostics(self, diagnostics: dict):
        """Update diagnostics panel with camera status data."""
        if 'frame_count' in diagnostics and diagnostics['frame_count'] is not None:
            self.diag_frame_count_label.setText(f"{diagnostics['frame_count']:,}")
        else:
            self.diag_frame_count_label.setText("--")

        if 'board_temp_c' in diagnostics and diagnostics['board_temp_c'] is not None:
            self.diag_board_temp_label.setText(f"{diagnostics['board_temp_c']:.1f}°C")
        else:
            self.diag_board_temp_label.setText("--")

        if 'fpa_temp_c' in diagnostics and diagnostics['fpa_temp_c'] is not None:
            self.diag_fpa_temp_label.setText(f"{diagnostics['fpa_temp_c']:.1f}°C")
        else:
            self.diag_fpa_temp_label.setText("--")

        if 'last_ffc_frame' in diagnostics and diagnostics['last_ffc_frame'] is not None:
            self.diag_last_ffc_frame_label.setText(f"{diagnostics['last_ffc_frame']:,}")
        else:
            self.diag_last_ffc_frame_label.setText("--")

        if 'frames_since_ffc' in diagnostics and diagnostics['frames_since_ffc'] is not None:
            self.diag_frames_since_ffc_label.setText(f"{diagnostics['frames_since_ffc']:,}")
        else:
            self.diag_frames_since_ffc_label.setText("--")

        if 'last_ffc_temp_c' in diagnostics and diagnostics['last_ffc_temp_c'] is not None:
            self.diag_last_ffc_temp_label.setText(f"{diagnostics['last_ffc_temp_c']:.1f}°C")
        else:
            self.diag_last_ffc_temp_label.setText("--")

        if 'ffc_temp_delta_c' in diagnostics and diagnostics['ffc_temp_delta_c'] is not None:
            self.diag_ffc_threshold_label.setText(f"{diagnostics['ffc_temp_delta_c']:.1f}°C")
        else:
            self.diag_ffc_threshold_label.setText("--")

    def update_radiometric_mode_status(self, is_radiometric: bool, success: bool = True):
        """Update the radiometric mode status display."""
        if success:
            if is_radiometric:
                self.radiometric_mode_status.setText("Current Mode: T-Linear Radiometric (16-bit)")
                self.radiometric_mode_status.setStyleSheet(
                    "font-weight: bold; padding: 8px; background-color: #004400; "
                    "border-radius: 3px; color: #4CAF50;"
                )
            else:
                self.radiometric_mode_status.setText("Current Mode: UVC Post-Colorized (8-bit)")
                self.radiometric_mode_status.setStyleSheet(
                    "font-weight: bold; padding: 8px; background-color: #004400; "
                    "border-radius: 3px; color: #4CAF50;"
                )
        else:
            self.radiometric_mode_status.setText("Mode change failed")
            self.radiometric_mode_status.setStyleSheet(
                "font-weight: bold; padding: 8px; background-color: #440000; "
                "border-radius: 3px; color: #ff4444;"
            )
