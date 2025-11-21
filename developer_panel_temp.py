#!/usr/bin/env python3
"""
Developer Panel for Thermal Fusion Driving Assist
Real-time performance metrics, diagnostics, and debugging overlays
"""
import logging
from collections import deque
from typing import Optional, Dict
import time

try:
    from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                                  QFrame, QScrollArea, QGridLayout, QPushButton,
                                  QListWidget, QListWidgetItem)
    from PyQt5.QtCore import Qt, QTimer, pyqtSignal
    from PyQt5.QtGui import QFont, QPalette, QColor
    PYQT_AVAILABLE = True
except ImportError:
    PYQT_AVAILABLE = False

logger = logging.getLogger(__name__)


# ============================================================================
# Developer Panel Styling
# ============================================================================

DEVELOPER_PANEL_STYLE = """
QFrame#DeveloperPanel {
    background-color: #0d0d0d;
    border-left: 2px solid #00aaff;
}

QLabel#SectionHeader {
    color: #00aaff;
    font-size: 12px;
    font-weight: bold;
    padding: 5px 0px;
    border-bottom: 1px solid #404040;
}

QLabel#MetricLabel {
    color: #b0b0b0;
    font-size: 10px;
    padding: 2px 5px;
}

QLabel#MetricValue {
    color: #ffffff;
    font-size: 11px;
    font-weight: bold;
    padding: 2px 5px;
}

QLabel#StatusGood {
    color: #00ff00;
    font-size: 10px;
    font-weight: bold;
}

QLabel#StatusWarning {
    color: #ffaa00;
    font-size: 10px;
    font-weight: bold;
}

QLabel#StatusError {
    color: #ff0000;
    font-size: 10px;
    font-weight: bold;
}

QPushButton#DevButton {
    background-color: #1a1a1a;
    color: #00aaff;
    border: 1px solid #404040;
    border-radius: 4px;
    padding: 4px 8px;
    font-size: 10px;
    min-width: 80px;
}

QPushButton#DevButton:hover {
    background-color: #2a2a2a;
    border: 1px solid #00aaff;
}
"""


class FPSGraph(QWidget):
    """Mini FPS graph widget"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.fps_history = deque(maxlen=60)  # Last 60 FPS samples
        self.setMinimumHeight(60)
        self.setMaximumHeight(60)

    def update_fps(self, fps: float):
        """Update FPS history"""
        self.fps_history.append(fps)
        self.update()  # Trigger repaint


class CollapsibleSection(QFrame):
    """
    Collapsible section widget with clickable header
    Can be expanded or collapsed to show/hide content
    """
    def __init__(self, title: str, expanded: bool = True, parent=None):
        super().__init__(parent)
        self.setStyleSheet("QFrame { background-color: #1a1a1a; border: 1px solid #303030; border-radius: 4px; }")

        self.is_expanded = expanded

        # Main layout
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(4)

        # Header (clickable)
        self.header = QPushButton()
        self.header.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #00aaff;
                font-size: 12px;
                font-weight: bold;
                text-align: left;
                border: none;
                padding: 5px 0px;
                border-bottom: 1px solid #404040;
            }
            QPushButton:hover {
                color: #00ddff;
            }
        """)
        self.header.setCursor(Qt.PointingHandCursor)
        self.header.clicked.connect(self.toggle)
        self._update_header_text(title)
        main_layout.addWidget(self.header)

        # Content container
        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout()
        self.content_layout.setContentsMargins(0, 4, 0, 0)
        self.content_layout.setSpacing(4)
        self.content_widget.setLayout(self.content_layout)
        main_layout.addWidget(self.content_widget)

        # Set initial state
        self.content_widget.setVisible(expanded)

        self.setLayout(main_layout)
        self.title = title

    def _update_header_text(self, title: str):
        """Update header with expand/collapse icon"""
        icon = "▼" if self.is_expanded else "▶"
        self.header.setText(f"{icon} {title}")

    def toggle(self):
        """Toggle expanded/collapsed state"""
        self.is_expanded = not self.is_expanded
        self.content_widget.setVisible(self.is_expanded)
        self._update_header_text(self.title)

    def add_widget(self, widget: QWidget):
        """Add widget to content area"""
        self.content_layout.addWidget(widget)

    def layout(self):
        """Return content layout for adding widgets"""
        return self.content_layout


class DeveloperPanel(QFrame):
    """
    Developer mode panel with comprehensive diagnostics and metrics
    Shows real-time performance, camera status, detection stats, and system info
    """
    
    # Signals
    camera_assignment_changed = pyqtSignal(int, str)  # device_id, role
    rescan_cameras_requested = pyqtSignal()
    clear_assignments_requested = pyqtSignal()
    palette_selected = pyqtSignal(str)  # palette_name

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("DeveloperPanel")
        self.setFixedWidth(300)
        # CRITICAL: Set size policy to prevent vertical expansion
        # This prevents the panel from forcing the parent window to grow
        from PyQt5.QtWidgets import QSizePolicy
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)
        self.setMaximumHeight(16777215)  # Allow shrinking but don't force expansion
        self.setStyleSheet(DEVELOPER_PANEL_STYLE)

        # State
        self.app = None  # Reference to main app
        self.start_time = time.time()

        # Build UI
        self._build_ui()

        # Update timer (10 FPS for developer panel)
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self._auto_update)
        self.update_timer.start(100)  # 10 Hz update

    def _build_ui(self):
        """Build developer panel UI with tabs and collapsible sections"""
        from PyQt5.QtWidgets import QTabWidget

        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(0)

        # Tab widget
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #303030;
                background-color: #0d0d0d;
            }
            QTabBar::tab {
                background-color: #1a1a1a;
                color: #b0b0b0;
                border: 1px solid #303030;
                padding: 6px 12px;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                background-color: #0d0d0d;
                color: #00aaff;
                border-bottom: 2px solid #00aaff;
            }
            QTabBar::tab:hover {
                background-color: #2a2a2a;
                color: #00ddff;
            }
        """)

        # ===================================================================
        # TAB 1: MONITOR (Performance, Cameras, Detection)
        # ===================================================================
        monitor_tab = self._create_monitor_tab()
        self.tabs.addTab(monitor_tab, "Monitor")

        # ===================================================================
        # TAB 2: TOOLS (Presets, Settings, Camera Management)
        # ===================================================================
        tools_tab = self._create_tools_tab()
        self.tabs.addTab(tools_tab, "Tools")

        # ===================================================================
        # TAB 3: ADVANCED (System Resources, View, Threading)
        # ===================================================================
        advanced_tab = self._create_advanced_tab()
        self.tabs.addTab(advanced_tab, "Advanced")

        main_layout.addWidget(self.tabs)
        self.setLayout(main_layout)

    def _create_monitor_tab(self):
        """Create Monitor tab with Performance, Cameras, Detection sections"""
        tab = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(8)

        # Scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { border: none; background-color: transparent; }")

        content = QWidget()
        content_layout = QVBoxLayout()
        content_layout.setSpacing(8)

        # === PERFORMANCE Section (Collapsible, collapsed by default) ===
        perf_section = CollapsibleSection("PERFORMANCE", expanded=False)
        self.fps_label = self._create_metric_row("FPS:", "0.0")
        self.frame_time_label = self._create_metric_row("Frame Time:", "0.0 ms")
        self.frame_count_label = self._create_metric_row("Frames:", "0")
        self.uptime_label = self._create_metric_row("Uptime:", "00:00:00")
        perf_section.add_widget(self.fps_label)
        perf_section.add_widget(self.frame_time_label)
        perf_section.add_widget(self.frame_count_label)
        perf_section.add_widget(self.uptime_label)
        content_layout.addWidget(perf_section)

        # === CAMERAS Section (Collapsible, collapsed by default) ===
        cam_section = CollapsibleSection("CAMERAS", expanded=False)
        self.thermal_status_label = self._create_status_row("Thermal:", "DISCONNECTED")
        self.thermal_res_label = self._create_metric_row("  Resolution:", "N/A")
        self.rgb_status_label = self._create_status_row("RGB:", "DISCONNECTED")
        self.rgb_res_label = self._create_metric_row("  Resolution:", "N/A")
        cam_section.add_widget(self.thermal_status_label)
        cam_section.add_widget(self.thermal_res_label)
        cam_section.add_widget(self.rgb_status_label)
        cam_section.add_widget(self.rgb_res_label)
        content_layout.addWidget(cam_section)

        # === DETECTION Section (Collapsible, collapsed by default) ===
        det_section = CollapsibleSection("DETECTION", expanded=False)
        self.yolo_status_label = self._create_status_row("YOLO:", "DISABLED")
        self.detection_count_label = self._create_metric_row("Detections:", "0")
        self.inference_time_label = self._create_metric_row("Inference:", "0.0 ms")
        self.frame_skip_label = self._create_metric_row("Frame Skip:", "1")
        self.device_label = self._create_metric_row("Device:", "CPU")
        det_section.add_widget(self.yolo_status_label)
        det_section.add_widget(self.detection_count_label)
        det_section.add_widget(self.inference_time_label)
        det_section.add_widget(self.frame_skip_label)
        det_section.add_widget(self.device_label)
        content_layout.addWidget(det_section)

        content_layout.addStretch()
        content.setLayout(content_layout)
        scroll.setWidget(content)
        layout.addWidget(scroll)
        tab.setLayout(layout)
        return tab

    def _create_tools_tab(self):
        """Create Tools tab with Presets, Settings, Camera Management"""
        tab = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(8)

        # Scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { border: none; background-color: transparent; }")

        content = QWidget()
        content_layout = QVBoxLayout()
        content_layout.setSpacing(8)

        # === PRESETS Section (Collapsible, collapsed by default) ===
        from preset_manager import get_preset_manager
        self.preset_manager = get_preset_manager()

        presets_section = CollapsibleSection("PRESETS", expanded=False)
        self.preset_widgets = []
        for i in range(3):
            preset_row = QWidget()
            preset_layout = QHBoxLayout()
            preset_layout.setContentsMargins(0, 0, 0, 0)
            preset_layout.setSpacing(4)

            name_label = QLabel(self.preset_manager.get_preset_name(i))
            name_label.setStyleSheet("color: #00aaff; font-size: 10px; font-weight: bold;")
            preset_layout.addWidget(name_label)
            preset_layout.addStretch()

            save_btn = QPushButton("💾")
            save_btn.setObjectName("DevButton")
            save_btn.setFixedSize(30, 22)
            save_btn.setToolTip(f"Save current settings to preset {i+1}")
            save_btn.clicked.connect(lambda checked, slot=i: self._save_preset(slot))
            preset_layout.addWidget(save_btn)

            load_btn = QPushButton("📂")
            load_btn.setObjectName("DevButton")
            load_btn.setFixedSize(30, 22)
            load_btn.setToolTip(f"Load preset {i+1}")
            load_btn.clicked.connect(lambda checked, slot=i: self._load_preset(slot))
            preset_layout.addWidget(load_btn)

            preset_row.setLayout(preset_layout)
            presets_section.add_widget(preset_row)

            self.preset_widgets.append({
                'row': preset_row,
                'name_label': name_label,
                'save_btn': save_btn,
                'load_btn': load_btn
            })

        content_layout.addWidget(presets_section)

        # === SETTINGS Section (Collapsible, collapsed by default) ===
        settings_section = CollapsibleSection("SETTINGS", expanded=False)

        self.settings_editor_btn = QPushButton("⚙️ Open Settings Editor")
        self.settings_editor_btn.setObjectName("DevButton")
        self.settings_editor_btn.setToolTip("Launch settings editor in separate window")
        self.settings_editor_btn.clicked.connect(self._launch_settings_editor)
        settings_section.add_widget(self.settings_editor_btn)

        self.settings_status_label = QLabel("Not running")
        self.settings_status_label.setStyleSheet("color: #666666; font-size: 9px; font-style: italic;")
        self.settings_status_label.setAlignment(Qt.AlignCenter)
        settings_section.add_widget(self.settings_status_label)

        content_layout.addWidget(settings_section)

        # === CAMERA MANAGEMENT Section (Collapsible, collapsed by default) ===
        cam_mgmt_section = CollapsibleSection("CAMERA MANAGEMENT", expanded=False)

        # Camera list
        self.camera_list = QListWidget()
        self.camera_list.setStyleSheet("""
            QListWidget {
                background-color: #0d0d0d;
                border: 1px solid #404040;
                color: #ffffff;
                font-size: 10px;
                padding: 4px;
            }
            QListWidget::item {
                padding: 3px;
            }
            QListWidget::item:selected {
                background-color: #2a2a2a;
                border: 1px solid #00aaff;
            }
        """)
        self.camera_list.setMaximumHeight(120)
        cam_mgmt_section.add_widget(self.camera_list)

        # Palette dropdown
        from PyQt5.QtWidgets import QComboBox
        palette_row = QWidget()
        palette_layout = QHBoxLayout()
        palette_layout.setContentsMargins(0, 0, 0, 0)
        palette_layout.setSpacing(4)

        palette_label = QLabel("Palette:")
        palette_label.setStyleSheet("color: #aaaaaa;")

        self.palette_combo = QComboBox()
        self.palette_combo.setStyleSheet("""
            QComboBox {
                background-color: #2d2d2d;
                color: #e0e0e0;
                border: 1px solid #404040;
                border-radius: 4px;
                padding: 4px;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox QAbstractItemView {
                background-color: #2d2d2d;
                color: #e0e0e0;
                selection-background-color: #00aaff;
            }
        """)

        palettes = [
            "White Hot", "Black Hot", "Ironbow", "Rainbow", "Rainbow HC",
            "Arctic", "Lava", "Medical", "Plasma", "Sepia",
            "Ocean", "Amber", "Gray", "Feather"
        ]
        self.palette_combo.addItems(palettes)
        self.palette_combo.currentTextChanged.connect(self._on_palette_changed)

        palette_layout.addWidget(palette_label)
        palette_layout.addWidget(self.palette_combo)
        palette_row.setLayout(palette_layout)
        cam_mgmt_section.add_widget(palette_row)

        # Buttons row 1
        btn_row1 = QWidget()
        btn_layout1 = QHBoxLayout()
        btn_layout1.setContentsMargins(0, 0, 0, 0)
        btn_layout1.setSpacing(4)

        self.btn_assign_thermal = QPushButton("Thermal")
        self.btn_assign_thermal.setObjectName("DevButton")
        self.btn_assign_thermal.setToolTip("Assign selected camera as thermal")
        self.btn_assign_thermal.clicked.connect(self._assign_thermal)

        self.btn_assign_rgb = QPushButton("RGB")
        self.btn_assign_rgb.setObjectName("DevButton")
        self.btn_assign_rgb.setToolTip("Assign selected camera as RGB")
        self.btn_assign_rgb.clicked.connect(self._assign_rgb)

        btn_layout1.addWidget(self.btn_assign_thermal)
        btn_layout1.addWidget(self.btn_assign_rgb)
        btn_row1.setLayout(btn_layout1)
        cam_mgmt_section.add_widget(btn_row1)

        # Buttons row 2
        btn_row2 = QWidget()
        btn_layout2 = QHBoxLayout()
        btn_layout2.setContentsMargins(0, 0, 0, 0)
        btn_layout2.setSpacing(4)

        self.btn_rescan = QPushButton("Rescan")
        self.btn_rescan.setObjectName("DevButton")
        self.btn_rescan.setToolTip("Force camera rescan")
        self.btn_rescan.clicked.connect(self._rescan_cameras)

        self.btn_clear = QPushButton("Clear All")
        self.btn_clear.setObjectName("DevButton")
        self.btn_clear.setToolTip("Clear all manual assignments")
        self.btn_clear.clicked.connect(self._clear_assignments)

        btn_layout2.addWidget(self.btn_rescan)
        btn_layout2.addWidget(self.btn_clear)
        btn_row2.setLayout(btn_layout2)
        cam_mgmt_section.add_widget(btn_row2)

        content_layout.addWidget(cam_mgmt_section)

        content_layout.addStretch()
        content.setLayout(content_layout)
        scroll.setWidget(content)
        layout.addWidget(scroll)
        tab.setLayout(layout)
        return tab

    def _create_advanced_tab(self):
        """Create Advanced tab with System Resources, View, Threading"""
        tab = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(8)

        # Scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { border: none; background-color: transparent; }")

        content = QWidget()
        content_layout = QVBoxLayout()
        content_layout.setSpacing(8)

        # === SYSTEM RESOURCES Section (Collapsible, collapsed by default) ===
        sys_section = CollapsibleSection("SYSTEM RESOURCES", expanded=False)
        self.cpu_label = self._create_metric_row("CPU:", "0%")
        self.gpu_label = self._create_metric_row("GPU:", "0%")
        self.memory_label = self._create_metric_row("Memory:", "0 MB")
        self.temp_label = self._create_metric_row("Temp:", "0°C")
        self.power_label = self._create_metric_row("Power:", "0.0 W")
        sys_section.add_widget(self.cpu_label)
        sys_section.add_widget(self.gpu_label)
        sys_section.add_widget(self.memory_label)
        sys_section.add_widget(self.temp_label)
        sys_section.add_widget(self.power_label)
        content_layout.addWidget(sys_section)

        # === VIEW Section (Collapsible, collapsed by default) ===
        view_section = CollapsibleSection("VIEW", expanded=False)
        self.view_mode_label = self._create_metric_row("Mode:", "thermal")
        self.fusion_mode_label = self._create_metric_row("Fusion:", "overlay")
        self.fusion_alpha_label = self._create_metric_row("Alpha:", "0.5")
        view_section.add_widget(self.view_mode_label)
        view_section.add_widget(self.fusion_mode_label)
        view_section.add_widget(self.fusion_alpha_label)
        content_layout.addWidget(view_section)

        # === THREADING Section (Collapsible, collapsed by default) ===
        thread_section = CollapsibleSection("THREADING", expanded=False)
        self.gui_type_label = self._create_metric_row("GUI:", "Qt")
        self.worker_status_label = self._create_status_row("Worker:", "RUNNING")
        self.detection_thread_label = self._create_status_row("Detection Thread:", "RUNNING")
        thread_section.add_widget(self.gui_type_label)
        thread_section.add_widget(self.worker_status_label)
        thread_section.add_widget(self.detection_thread_label)
        content_layout.addWidget(thread_section)

        content_layout.addStretch()
        content.setLayout(content_layout)
        scroll.setWidget(content)
        layout.addWidget(scroll)
        tab.setLayout(layout)
        return tab
    def _create_section(self, title: str) -> QFrame:
        """Create a section frame with header"""
        frame = QFrame()
        frame.setStyleSheet("QFrame { background-color: #1a1a1a; border: 1px solid #303030; border-radius: 4px; }")
        layout = QVBoxLayout()
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        header = QLabel(title)
        header.setObjectName("SectionHeader")
        layout.addWidget(header)

        frame.setLayout(layout)
        return frame

    def _create_metric_row(self, label_text: str, value_text: str) -> QWidget:
        """Create a metric row (label + value)"""
        widget = QWidget()
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)

        label = QLabel(label_text)
        label.setObjectName("MetricLabel")
        label.setMinimumWidth(100)

        value = QLabel(value_text)
        value.setObjectName("MetricValue")
        value.setAlignment(Qt.AlignRight)

        layout.addWidget(label)
        layout.addWidget(value)

        widget.setLayout(layout)
        widget._value_label = value  # Store reference for updates
        return widget

    def _create_status_row(self, label_text: str, status_text: str) -> QWidget:
        """Create a status row with color-coded status"""
        widget = QWidget()
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)

        label = QLabel(label_text)
        label.setObjectName("MetricLabel")
        label.setMinimumWidth(100)

        status = QLabel(status_text)
        status.setObjectName("StatusError")  # Default to error state
        status.setAlignment(Qt.AlignRight)

        layout.addWidget(label)
        layout.addWidget(status)

        widget.setLayout(layout)
        widget._status_label = status  # Store reference for updates
        return widget

    def set_app_reference(self, app):
        """Set reference to main application"""
        self.app = app
        logger.info("Developer panel connected to main app")

    def _auto_update(self):
        """Auto-update developer panel metrics"""
        if not self.app:
            return

        # Update uptime
        uptime_sec = int(time.time() - self.start_time)
        hours = uptime_sec // 3600
        minutes = (uptime_sec % 3600) // 60
        seconds = uptime_sec % 60
        self.uptime_label._value_label.setText(f"{hours:02d}:{minutes:02d}:{seconds:02d}")

    def update_metrics(self, metrics: Dict):
        """
        Update all metrics from main app

        Args:
            metrics: Dictionary with all performance and status metrics
        """
        # Performance
        fps = metrics.get('fps', 0.0)
        frame_time = (1000.0 / fps) if fps > 0 else 0.0
        self.fps_label._value_label.setText(f"{fps:.1f}")
        self.frame_time_label._value_label.setText(f"{frame_time:.1f} ms")
        self.frame_count_label._value_label.setText(f"{metrics.get('frame_count', 0)}")

        # System resources
        self.cpu_label._value_label.setText(f"{metrics.get('cpu_usage', 0.0):.1f}%")
        self.gpu_label._value_label.setText(f"{metrics.get('gpu_usage', 0.0):.1f}%")
        mem_used = metrics.get('memory_used_mb', 0)
        mem_total = metrics.get('memory_total_mb', 0)
        self.memory_label._value_label.setText(f"{mem_used:.0f}/{mem_total:.0f} MB")

        temp = metrics.get('temperature', 0.0)
        self.temp_label._value_label.setText(f"{temp:.1f}°C")
        # Color code temperature
        if temp > 80:
            self.temp_label._value_label.setObjectName("StatusError")
        elif temp > 70:
            self.temp_label._value_label.setObjectName("StatusWarning")
        else:
            self.temp_label._value_label.setObjectName("StatusGood")
        self.temp_label._value_label.setStyleSheet(DEVELOPER_PANEL_STYLE)

        self.power_label._value_label.setText(f"{metrics.get('power_watts', 0.0):.1f} W")

        # Camera status
        thermal_connected = metrics.get('thermal_connected', False)
        self._update_status(self.thermal_status_label, "CONNECTED" if thermal_connected else "DISCONNECTED", thermal_connected)
        if thermal_connected:
            thermal_res = metrics.get('thermal_resolution', 'N/A')
            self.thermal_res_label._value_label.setText(str(thermal_res))
        else:
            self.thermal_res_label._value_label.setText("N/A")

        rgb_connected = metrics.get('rgb_connected', False)
        self._update_status(self.rgb_status_label, "CONNECTED" if rgb_connected else "DISCONNECTED", rgb_connected)
        if rgb_connected:
            rgb_res = metrics.get('rgb_resolution', 'N/A')
            self.rgb_res_label._value_label.setText(str(rgb_res))
        else:
            self.rgb_res_label._value_label.setText("N/A")

        # Detection
        yolo_enabled = metrics.get('yolo_enabled', False)
        self._update_status(self.yolo_status_label, "ENABLED" if yolo_enabled else "DISABLED", yolo_enabled)
        self.detection_count_label._value_label.setText(f"{metrics.get('detections', 0)}")
        self.inference_time_label._value_label.setText(f"{metrics.get('inference_time_ms', 0.0):.1f} ms")
        self.frame_skip_label._value_label.setText(f"{metrics.get('frame_skip', 1)}")
        self.device_label._value_label.setText(metrics.get('device', 'CPU'))

        # View mode
        self.view_mode_label._value_label.setText(metrics.get('view_mode', 'thermal'))
        self.fusion_mode_label._value_label.setText(metrics.get('fusion_mode', 'overlay'))
        self.fusion_alpha_label._value_label.setText(f"{metrics.get('fusion_alpha', 0.5):.2f}")

        # Threading
        self.gui_type_label._value_label.setText(metrics.get('gui_type', 'Qt'))
        worker_running = metrics.get('worker_running', True)
        self._update_status(self.worker_status_label, "RUNNING" if worker_running else "STOPPED", worker_running)
        detection_thread_alive = metrics.get('detection_thread_alive', True)
        self._update_status(self.detection_thread_label, "RUNNING" if detection_thread_alive else "STOPPED", detection_thread_alive)

    def _update_status(self, widget: QWidget, text: str, is_good: bool):
        """Update status label with color coding"""
        widget._status_label.setText(text)
        if is_good:
            widget._status_label.setObjectName("StatusGood")
        else:
            widget._status_label.setObjectName("StatusError")
        widget._status_label.setStyleSheet(DEVELOPER_PANEL_STYLE)
    
    # ========================================================================
    # Camera Management Methods
    # ========================================================================
    
    def update_camera_list(self):
        """Refresh camera list from registry"""
        from camera_registry import get_camera_registry, CameraRole
        
        try:
            self.camera_list.clear()
            registry = get_camera_registry()
            cameras = registry.get_all_cameras()
            
            if not cameras:
                logger.debug("No cameras in registry yet")
                return
            
            for cam in cameras:
                status = "●" if cam.is_connected else "○"
                role_text = cam.role.value.upper()
                
                # Color based on connection
                color = "#ffffff" if cam.is_connected else "#666666"
                
                # Build display text
                text = f"{status} Dev {cam.device_id} - {cam.name} [{role_text}]"
                if cam.manual_override:
                    text += " (manual)"
                
                item = QListWidgetItem(text)
                item.setForeground(QColor(color))
                item.setData(Qt.UserRole, cam.device_id)
                self.camera_list.addItem(item)
            
            logger.debug(f"Camera list updated: {len(cameras)} cameras")
        except Exception as e:
            logger.error(f"Error updating camera list: {e}")
            # Don't crash - just log and continue
    
    def _assign_thermal(self):
        """Assign selected camera as thermal"""
        from camera_registry import get_camera_registry, CameraRole
        
        selected_items = self.camera_list.selectedItems()
        if selected_items:
            device_id = selected_items[0].data(Qt.UserRole)
            registry = get_camera_registry()
            registry.set_camera_role(device_id, CameraRole.THERMAL, manual=True)
            logger.info(f"Manually assigned camera {device_id} as THERMAL")
            self.update_camera_list()
            
            # Notify main app
            if self.app and hasattr(self.app, '_on_camera_assignment_changed'):
                self.app._on_camera_assignment_changed()
    
    def _assign_rgb(self):
        """Assign selected camera as RGB"""
        from camera_registry import get_camera_registry, CameraRole
        
        selected_items = self.camera_list.selectedItems()
        if selected_items:
            device_id = selected_items[0].data(Qt.UserRole)
            registry = get_camera_registry()
            registry.set_camera_role(device_id, CameraRole.RGB, manual=True)
            logger.info(f"Manually assigned camera {device_id} as RGB")
            self.update_camera_list()
            
            # Notify main app
            if self.app and hasattr(self.app, '_on_camera_assignment_changed'):
                self.app._on_camera_assignment_changed()
    
    def _rescan_cameras(self):
        """Force camera rescan"""
        logger.info("Forcing camera rescan...")
        
        try:
            from camera_monitor import get_camera_monitor
            monitor = get_camera_monitor()
            monitor.force_scan()
            logger.info("Camera rescan triggered")
        except Exception as e:
            logger.error(f"Failed to trigger camera rescan: {e}")
        
        # Update list after short delay
        QTimer.singleShot(500, self.update_camera_list)
    
    def _clear_assignments(self):
        """Clear all manual camera assignments"""
        from camera_registry import get_camera_registry
        
        registry = get_camera_registry()
        registry.clear_manual_assignments()
        logger.info("Cleared all manual camera assignments")
        self.update_camera_list()
        
        # Notify main app
        if self.app and hasattr(self.app, '_on_camera_assignment_changed'):
            self.app._on_camera_assignment_changed()

    def _on_palette_changed(self, text):
        """Handle palette dropdown change"""
        # Convert display name to internal name (e.g. "White Hot" -> "white_hot")
        internal_name = text.lower().replace(" ", "_")
        self.palette_selected.emit(internal_name)
        
    def update_palette_selection(self, palette_name):
        """Update dropdown selection from external change"""
        # Convert internal name to display name (e.g. "white_hot" -> "White Hot")
        display_name = palette_name.replace("_", " ").title()
        # Special case for "Rainbow Hc" -> "Rainbow HC"
        if display_name == "Rainbow Hc":
            display_name = "Rainbow HC"
            
        index = self.palette_combo.findText(display_name)
        if index >= 0:
            self.palette_combo.blockSignals(True)
            self.palette_combo.setCurrentIndex(index)
            self.palette_combo.blockSignals(False)
    
    # ========================================================================
    # Presets Methods
    # ========================================================================
    
    def _save_preset(self, slot: int):
        """Save current application state to preset slot"""
        if not self.app:
            logger.warning("Cannot save preset: no app reference")
            return
        
        # Gather current application state
        app_state = {
            'view_mode': str(self.app.view_mode.value) if hasattr(self.app, 'view_mode') else 'thermal',
            'fusion_mode': getattr(self.app, 'fusion_mode', 'alpha_blend'),
            'fusion_alpha': getattr(self.app, 'fusion_alpha', 0.5),
            'thermal_palette': getattr(self.app.detector, 'palette_name', 'ironbow') if self.app.detector else 'ironbow',
            'yolo_enabled': getattr(self.app, 'yolo_enabled', True),
            'yolo_model': getattr(self.app, 'model_name', 'yolov8n.pt'),
            'show_boxes': getattr(self.app, 'show_detections', True),
            'audio_enabled': getattr(self.app, 'audio_enabled', True),
            'frame_skip': getattr(self.app, 'frame_skip_value', 1),
            'device': getattr(self.app, 'device', 'cuda'),
        }
        
        preset_name = self.preset_manager.get_preset_name(slot)
        
        if self.preset_manager.save_preset(slot, preset_name, app_state):
            logger.info(f"Saved preset {slot+1}: {preset_name}")
            # Update UI to show saved time
            saved_time = self.preset_manager.get_saved_time(slot)
            if saved_time:
                self.preset_widgets[slot]['name_label'].setToolTip(f"Saved: {saved_time}")
        else:
            logger.error(f"Failed to save preset {slot+1}")
    
    def _load_preset(self, slot: int):
        """Load preset and apply to application"""
        if not self.app:
            logger.warning("Cannot load preset: no app reference")
            return
        
        preset = self.preset_manager.load_preset(slot)
        if not preset:
            logger.warning(f"No preset saved in slot {slot+1}")
            return
        
        # Apply preset settings to application
        try:
            # View mode
            from view_mode import ViewMode
            if preset.view_mode:
                view_mode_map = {
                    'thermal': ViewMode.THERMAL_ONLY,
                    'rgb': ViewMode.RGB_ONLY,
                    'fusion': ViewMode.FUSION,
                    'side_by_side': ViewMode.SIDE_BY_SIDE,
                    'pip': ViewMode.PICTURE_IN_PICTURE
                }
                if preset.view_mode in view_mode_map:
                    self.app.view_mode = view_mode_map[preset.view_mode]
            
            # Fusion settings
            if hasattr(self.app, 'fusion_mode'):
                self.app.fusion_mode = preset.fusion_mode
            if hasattr(self.app, 'fusion_alpha'):
                self.app.fusion_alpha = preset.fusion_alpha
            
            # YOLO settings
            if hasattr(self.app, 'yolo_enabled'):
                self.app.yolo_enabled = preset.yolo_enabled
            if hasattr(self.app, 'show_detections'):
                self.app.show_detections = preset.show_boxes
            
            # Audio
            if hasattr(self.app, 'audio_enabled'):
                self.app.audio_enabled = preset.audio_enabled
            
            # Frame skip
            if hasattr(self.app, 'frame_skip_value'):
                self.app.frame_skip_value = preset.frame_skip
            
            # Apply palette if detector exists
            if self.app.detector and hasattr(self.app.detector, 'set_palette'):
                self.app.detector.set_palette(preset.thermal_palette)
            
            logger.info(f"Loaded preset {slot+1}: {preset.name}")
        except Exception as e:
            logger.error(f"Error loading preset: {e}")
    
    # ========================================================================
    # Settings Editor Launch
    # ========================================================================
    
    def _launch_settings_editor(self):
        """Launch settings editor as separate process"""
        import subprocess
        import sys
        from pathlib import Path
        
        try:
            # Find settings_editor.py
            settings_editor_path = Path("settings_editor.py")
            if not settings_editor_path.exists():
                logger.error("settings_editor.py not found")
                self.settings_status_label.setText("Error: File not found")
                self.settings_status_label.setStyleSheet("color: #ff0000; font-size: 9px; font-style: italic;")
                return
            
            # Launch as subprocess
            process = subprocess.Popen(
                [sys.executable, str(settings_editor_path)],
                creationflags=subprocess.CREATE_NEW_CONSOLE if sys.platform == 'win32' else 0
            )
            
            logger.info(f"Launched settings editor (PID: {process.pid})")
            self.settings_status_label.setText(f"Running (PID: {process.pid})")
            self.settings_status_label.setStyleSheet("color: #00ff00; font-size: 9px; font-style: italic;")
        except Exception as e:
            logger.error(f"Failed to launch settings editor: {e}")
            self.settings_status_label.setText(f"Error: {str(e)[:20]}")
            self.settings_status_label.setStyleSheet("color: #ff0000; font-size: 9px; font-style: italic;")
