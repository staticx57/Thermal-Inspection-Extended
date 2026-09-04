"""
Main inspection application window.
Integrates all GUI components for the Thermal Inspection Fusion Tool.
"""

import sys
import logging
from typing import List, Optional, Dict, Tuple

import numpy as np

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QLabel, QVBoxLayout, QHBoxLayout,
    QTabWidget, QScrollArea, QFrame, QFileDialog, QMessageBox,
    QApplication
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor

# Import themes
from thermal_inspection.gui.themes import (
    DARK_THEME, LIGHT_THEME, THEMES, STATE_COLORS_QSS
)

# Import widgets
from thermal_inspection.gui.widgets import (
    MeasurementPoint, VideoWidget, ControlPanel, InfoPanel
)

# Import panels
from thermal_inspection.gui.panels import (
    ThermalAnalysisPanel, CombinedAnomalyWidget, SettingsPanel
)

# Import camera control
from thermal_inspection.gui.camera_control import (
    CameraManagerDialog
)

# Import external modules from package
from thermal_inspection.processing.roi_manager import ROI, ROIType
from thermal_inspection.processing.thermal_analyzer import ThermalStatistics, HotSpot, ColdSpot, ThermalAnomaly, TemperatureTrend
from thermal_inspection.gui.panels.spot_meter_panel import SpotMeterPresets

logger = logging.getLogger(__name__)


class InspectionAppWindow(QMainWindow):
    """
    Main inspection application window.
    Replaces DriverAppWindow with inspection-focused UI.
    """

    def __init__(self, app_instance=None):
        super().__init__()
        self.app = app_instance
        # Central event bus for decoupled GUI ↔ backend communication
        self.event_bus = getattr(app_instance, 'event_bus', None)

        # Window setup
        self.setWindowTitle("Thermal Inspection Fusion Tool v3.6.0")
        self.setMinimumSize(1280, 720)
        self.resize(1280, 720)

        # Center on the screen where the cursor currently is
        from PyQt6.QtGui import QGuiApplication
        def center_window():
            screen = QGuiApplication.screenAt(QGuiApplication.primaryScreen().geometry().center())
            try:
                screen = QGuiApplication.screenAt(QGuiApplication.queryKeyboardModifiers()) # fallback
                import PyQt6.QtGui as qtgui
                screen = qtgui.QCursor.pos()
                screen = QGuiApplication.screenAt(qtgui.QCursor.pos())
            except Exception:
                screen = QGuiApplication.primaryScreen()

            if screen:
                screen_geometry = screen.geometry()
                x = screen_geometry.x() + (screen_geometry.width() - self.width()) // 2
                y = screen_geometry.y() + (screen_geometry.height() - self.height()) // 2
                self.move(x, y)

        QTimer.singleShot(0, center_window)

        # Add status bar
        self.statusBar().showMessage("Developer Mode: ON (Press Ctrl+D to toggle panels)", 8000)

        # State
        self.current_theme = "dark"
        self.developer_mode = True
        self.recording = False
        self.frozen = False

        # Connection tracking for defensive pattern
        self._connected_signals = set()

        # Measurement points for spot metering
        self.measurement_points: List[MeasurementPoint] = []

        # Build UI
        self._build_ui()

        # Apply initial theme
        self._apply_theme(self.current_theme)

        # Force layout update after startup to ensure panels are visible
        QTimer.singleShot(500, self._force_layout_update)

    def _force_layout_update(self):
        """Force layout update and visibility check."""
        self.right_panel_tabs.setVisible(True)
        self.control_panel.setVisible(True)

        # Log geometry and visibility
        logger.info(f"Window geometry: {self.geometry()}")
        logger.info(f"Right panel visible: {self.right_panel_tabs.isVisible()}")
        logger.info(f"Right panel geometry: {self.right_panel_tabs.geometry()}")
        logger.info(f"Right panel size hint: {self.right_panel_tabs.sizeHint()}")
        logger.info(f"Control panel visible: {self.control_panel.isVisible()}")
        logger.info(f"Control panel geometry: {self.control_panel.geometry()}")

        # Check if tabs have content
        logger.info(f"Tab count: {self.right_panel_tabs.count()}")
        for i in range(self.right_panel_tabs.count()):
            # Safe logging avoiding unicode errors on Windows consoles
            try:
                text = self.right_panel_tabs.tabText(i)
                safe_text = text.encode('ascii', 'replace').decode('ascii')
                logger.debug(f"Tab {i}: {safe_text}")
            except Exception:
                pass

        # Trigger a slight resize to force layout recalculation
        self.resize(self.width() + 1, self.height())
        self.resize(self.width() - 1, self.height())
        logger.info("Forced layout update and visibility check")

    def _build_ui(self):
        """Build the main UI layout."""
        logger.info("=" * 60)
        logger.info("Building UI layout...")
        logger.info("=" * 60)

        try:
            # Central widget
            central = QWidget()
            central.setObjectName("central_widget")
            self.setCentralWidget(central)
            logger.info("[OK] Central widget created")

            # Main layout container
            main_layout = QHBoxLayout(central)
            main_layout.setContentsMargins(0, 0, 0, 0)
            main_layout.setSpacing(0)
            logger.info("[OK] Main layout created")

            # Left side: Video + Controls
            left_widget = QWidget()
            left_widget.setObjectName("left_widget")
            left_layout = QVBoxLayout(left_widget)
            left_layout.setContentsMargins(0, 0, 0, 0)
            left_layout.setSpacing(0)

            # Video widget - ViewMode.THREE_D also displays through this
            # same widget: its output is app.py's normal 2D Fusion blend
            # with a real-depth relief-shading effect applied
            # (apply_depth_relief), not a separate GL viewport. See
            # thermal_inspection/gui/panels/fusion_3d_panel.py.
            self.video_widget = VideoWidget()
            # NOTE: don't also connect video_widget.overlay.spot_meter_clicked
            # here - _safe_connect("video_widget.overlay", "spot_meter_clicked", ...)
            # below already does, and this duplicate connection meant every
            # overlay click fired _on_spot_meter_clicked (and, when active,
            # the broken calibration add-point routing) twice.
            left_layout.addWidget(self.video_widget, stretch=1)
            logger.info("[OK] Video widget created")

            # Control panel
            self.control_panel = ControlPanel()
            self.control_panel.setMinimumHeight(120)
            self.control_panel.setMaximumHeight(150)
            left_layout.addWidget(self.control_panel, stretch=0)
            logger.info("[OK] Control panel created")

            main_layout.addWidget(left_widget, stretch=5)
            logger.info("[OK] Left widget added to main layout")

            # RIGHT PANEL TABS
            self.right_panel_tabs = QTabWidget()
            self.right_panel_tabs.setObjectName("right_panel")
            self.right_panel_tabs.setFixedWidth(630)
            self.right_panel_tabs.setVisible(True)
            logger.info("[OK] Right panel tabs widget created (width=630, visible=True)")

            # === OPTIMIZED TAB STRUCTURE ===

            # Analysis tab with subtabs
            logger.info("Creating Analysis tab...")
            self.analysis_tabs = QTabWidget()

            # Create ThermalAnalysisPanel and transfer ALL its tabs
            self.analysis_panel = ThermalAnalysisPanel()

            # Transfer tabs from ThermalAnalysisPanel
            while self.analysis_panel.analysis_tabs.count() > 0:
                widget = self.analysis_panel.analysis_tabs.widget(0)
                title = self.analysis_panel.analysis_tabs.tabText(0)
                self.analysis_tabs.addTab(widget, title)
                logger.info(f"  [OK] Transferred tab '{title}' from ThermalAnalysisPanel")

            # Create Radiometric tab
            from thermal_inspection.gui.panels.radiometric_panel import RadiometricPanel
            radiometric_tab = QWidget()
            radiometric_scroll = QScrollArea()
            radiometric_scroll.setWidgetResizable(True)
            radiometric_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            radiometric_scroll.setFrameShape(QFrame.Shape.NoFrame)

            radiometric_content = QWidget()
            radiometric_layout = QVBoxLayout(radiometric_content)
            radiometric_layout.setSpacing(8)
            radiometric_layout.setContentsMargins(6, 6, 6, 6)

            self.radiometric_panel = RadiometricPanel()
            radiometric_layout.addWidget(self.radiometric_panel)
            radiometric_layout.addStretch()

            radiometric_scroll.setWidget(radiometric_content)
            radiometric_tab_layout = QVBoxLayout(radiometric_tab)
            radiometric_tab_layout.setContentsMargins(0, 0, 0, 0)
            radiometric_tab_layout.addWidget(radiometric_scroll)

            self.analysis_tabs.addTab(radiometric_tab, "Radiometric")
            logger.info("  [OK] Radiometric panel added at top level")

            from thermal_inspection.gui.panels.roi_temperature_panel import ROITemperaturePanel
            roi_temp_tab = QWidget()
            roi_temp_scroll = QScrollArea()
            roi_temp_scroll.setWidgetResizable(True)
            roi_temp_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            roi_temp_scroll.setFrameShape(QFrame.Shape.NoFrame)

            self.roi_temp_panel = ROITemperaturePanel()
            roi_temp_scroll.setWidget(self.roi_temp_panel)

            roi_temp_tab_layout = QVBoxLayout(roi_temp_tab)
            roi_temp_tab_layout.setContentsMargins(0, 0, 0, 0)
            roi_temp_tab_layout.addWidget(roi_temp_scroll)

            self.analysis_tabs.addTab(roi_temp_tab, "ROI Manager")
            logger.info("  [OK] ROI Manager panel added")

            # Connect ROI Manager signals
            if hasattr(self, 'video_widget') and hasattr(self.video_widget, 'overlay'):
                self.roi_temp_panel.roi_selected.connect(self.video_widget.overlay.set_selected_roi)
                logger.info("  [OK] Connected ROI Manager.roi_selected to overlay")

            # Connect ROI deletion and palette signals — prefer event bus, fallback to app
            if self.event_bus:
                self.roi_temp_panel.roi_deleted.connect(
                    lambda roi_id: self.event_bus.roi_deleted.emit(roi_id)
                )
                self.roi_temp_panel.roi_palette_changed.connect(
                    lambda roi_id, palette: self.event_bus.roi_palette_changed.emit(roi_id, palette)
                )
            elif hasattr(self, 'app') and self.app:
                self.roi_temp_panel.roi_deleted.connect(
                    lambda roi_id: self.app.roi_manager.delete_roi(roi_id)
                    if hasattr(self.app, 'roi_manager') else None
                )
                self.roi_temp_panel.roi_palette_changed.connect(
                    lambda roi_id, palette: self.app.set_roi_palette(roi_id, palette)
                    if hasattr(self.app, 'set_roi_palette') else None
                )
            logger.info("  [OK] Connected ROI Manager.roi_deleted and roi_palette_changed")

            # Connect export and clear history signals
            self.roi_temp_panel.export_data_requested.connect(self._on_roi_export_data)
            self.roi_temp_panel.clear_history_requested.connect(self._on_roi_clear_history)
            logger.info("  [OK] Connected ROI Manager.export_data and clear_history")

            from thermal_inspection.gui.panels.environmental_compensation_panel import EnvironmentalCompensationPanel
            env_comp_tab = QWidget()
            env_comp_scroll = QScrollArea()
            env_comp_scroll.setWidgetResizable(True)
            env_comp_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            env_comp_scroll.setFrameShape(QFrame.Shape.NoFrame)

            self.env_comp_panel = EnvironmentalCompensationPanel()
            env_comp_scroll.setWidget(self.env_comp_panel)

            env_comp_tab_layout = QVBoxLayout(env_comp_tab)
            env_comp_tab_layout.setContentsMargins(0, 0, 0, 0)
            env_comp_tab_layout.addWidget(env_comp_scroll)

            self.analysis_tabs.addTab(env_comp_tab, "Environmental")
            logger.info("  [OK] Environmental compensation panel added")

            from thermal_inspection.gui.panels.isotherm_panel import IsothermPanel
            isotherm_tab = QWidget()
            isotherm_scroll = QScrollArea()
            isotherm_scroll.setWidgetResizable(True)
            isotherm_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            isotherm_scroll.setFrameShape(QFrame.Shape.NoFrame)

            self.isotherm_panel = IsothermPanel()
            isotherm_scroll.setWidget(self.isotherm_panel)

            isotherm_tab_layout = QVBoxLayout(isotherm_tab)
            isotherm_tab_layout.setContentsMargins(0, 0, 0, 0)
            isotherm_tab_layout.addWidget(isotherm_scroll)

            self.analysis_tabs.addTab(isotherm_tab, "Isotherm")
            logger.info("  [OK] Isotherm panel added")

            from thermal_inspection.gui.panels.gradient_overlay_panel import GradientOverlayPanel
            gradient_tab = QWidget()
            gradient_scroll = QScrollArea()
            gradient_scroll.setWidgetResizable(True)
            gradient_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            gradient_scroll.setFrameShape(QFrame.Shape.NoFrame)

            self.gradient_panel = GradientOverlayPanel()
            gradient_scroll.setWidget(self.gradient_panel)

            gradient_tab_layout = QVBoxLayout(gradient_tab)
            gradient_tab_layout.setContentsMargins(0, 0, 0, 0)
            gradient_tab_layout.addWidget(gradient_scroll)

            self.analysis_tabs.addTab(gradient_tab, "Gradient")
            logger.info("  [OK] Gradient overlay panel added")

            from thermal_inspection.gui.panels.line_profile_panel import LineProfilePanel
            line_profile_tab = QWidget()
            line_profile_scroll = QScrollArea()
            line_profile_scroll.setWidgetResizable(True)
            line_profile_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            line_profile_scroll.setFrameShape(QFrame.Shape.NoFrame)

            self.line_profile_panel = LineProfilePanel()
            line_profile_scroll.setWidget(self.line_profile_panel)

            line_profile_tab_layout = QVBoxLayout(line_profile_tab)
            line_profile_tab_layout.setContentsMargins(0, 0, 0, 0)
            line_profile_tab_layout.addWidget(line_profile_scroll)

            self.analysis_tabs.addTab(line_profile_tab, "Line Profile")
            logger.info("  [OK] Line profile panel added")

            self.right_panel_tabs.addTab(self.analysis_tabs, "Analysis")
            logger.info("[OK] Analysis tab added to right panel")

            # Tab 2: Detection & Anomaly
            logger.info("Creating Detection tab...")
            self.combined_anomaly_widget = CombinedAnomalyWidget()
            self.right_panel_tabs.addTab(self.combined_anomaly_widget, "Detection")
            self.anomaly_widget = self.combined_anomaly_widget.automatic_widget
            self.manual_threshold_widget = self.combined_anomaly_widget.manual_widget
            logger.info("[OK] Detection tab added to right panel")

            # Tab 3: Cameras
            logger.info("Creating Cameras tab...")
            self.cameras_tabs = QTabWidget()
            self.camera_panels = {}

            # Populate registered camera plugins
            from thermal_inspection.cameras.plugin import get_registry
            for plugin in get_registry().get_all_plugins():
                try:
                    panel = plugin.create_control_panel()
                    if panel:
                        self.camera_panels[plugin.plugin_id] = panel
                        self.cameras_tabs.addTab(panel, plugin.display_name)
                        self._wire_plugin_panel(plugin, panel)
                        logger.info(f"  [OK] {plugin.display_name} panel added")
                except Exception as e:
                    logger.warning(f"Failed to create panel for {plugin.plugin_id}: {e}")

            # Keep convenient attributes for backwards compatibility
            self.boson_panel = self.camera_panels.get("flir_boson")
            self.tau2_panel = self.camera_panels.get("flir_tau2")
            self.lepton_panel = self.camera_panels.get("flir_lepton")
            self.firefly_panel = self.camera_panels.get("flir_firefly")
            self.uvc_panel = self.camera_panels.get("generic_uvc")
            self.gige_panel = self.camera_panels.get("gige_vision")

            from thermal_inspection.gui.panels.calibration_panel import CalibrationPanel
            self.calibration_panel = CalibrationPanel()
            self.cameras_tabs.addTab(self.calibration_panel, "Calibration")
            logger.info("  [OK] Calibration panel added")

            from thermal_inspection.gui.panels.parallax_panel import ParallaxPanel
            self.parallax_panel = ParallaxPanel()
            self.cameras_tabs.addTab(self.parallax_panel, "Parallax")
            logger.info("  [OK] Parallax panel added")

            self.right_panel_tabs.addTab(self.cameras_tabs, "Cameras")
            logger.info("[OK] Cameras tab added to right panel")

            # Tab 4: 2D Fusion
            logger.info("Creating 2D Fusion tab...")
            from thermal_inspection.gui.panels.fusion_panel import FusionPanel
            self.fusion_panel = FusionPanel()
            self.right_panel_tabs.addTab(self.fusion_panel, "2D Fusion")
            logger.info("[OK] 2D Fusion tab added to right panel")

            # Tab 4b: 3D Fusion settings - controls the main viewport's
            # THREE_D mode (a real-depth relief-shading effect applied to
            # the 2D Fusion image, shown through video_widget like every
            # other mode - not a separate viewport), plus a point-cloud
            # preview for verifying the underlying RealSense data.
            logger.info("Creating 3D Fusion settings tab...")
            from thermal_inspection.gui.panels.fusion_3d_panel import Fusion3DSettingsPanel
            self.fusion_3d_panel = Fusion3DSettingsPanel()
            self.right_panel_tabs.addTab(self.fusion_3d_panel, "3D Fusion")
            logger.info("[OK] 3D Fusion settings tab added to right panel")

            # Tab 5: Settings
            logger.info("Creating Settings tab...")
            self.settings_panel = SettingsPanel()
            self.right_panel_tabs.addTab(self.settings_panel, "Settings")
            logger.info("[OK] Settings tab added to right panel")

            # ADD RIGHT PANEL TO MAIN LAYOUT
            main_layout.addWidget(self.right_panel_tabs, stretch=0)

            # CRITICAL FIX: Set visibility AFTER adding to layout
            self.right_panel_tabs.setVisible(True)
            self.right_panel_tabs.show()

            logger.info("[OK] RIGHT PANEL TABS ADDED TO MAIN LAYOUT [OK]")
            logger.info(f"    Right panel tab count: {self.right_panel_tabs.count()}")
            logger.info(f"    Right panel visible: {self.right_panel_tabs.isVisible()}")
            logger.info(f"    Right panel width: {self.right_panel_tabs.width()}")

            # Signals from analysis panel
            self.analysis_panel.show_hot_spots_toggled.connect(self._on_show_hot_spots_toggled)
            self.analysis_panel.show_cold_spots_toggled.connect(self._on_show_cold_spots_toggled)
            self.analysis_panel.show_anomalies_toggled.connect(self._on_show_anomalies_toggled)

            # Info panel (overlay on video widget)
            self.info_panel = InfoPanel(self.video_widget)
            self.info_panel.move(10, 10)
            logger.info("[OK] Info panel created")

            # Connect signals
            self._connect_signals()

            logger.info("=" * 60)
            logger.info("[OK] UI LAYOUT BUILD COMPLETE [OK]")
            logger.info("=" * 60)

        except Exception as e:
            logger.error(f"ERROR during UI build: {e}", exc_info=True)
            raise

    def _safe_connect(self, source_path: str, signal_name: str, handler, context: str = ""):
        """
        Safely connect a signal to a handler with defensive checks.
        """
        try:
            handler_name = handler.__name__ if hasattr(handler, '__name__') else str(handler)

            if not callable(handler):
                logger.error(f"Handler not callable: {handler_name} for {source_path}.{signal_name} {context}")
                return False

            if hasattr(handler, '__self__') and handler.__self__ is self:
                if not hasattr(self, handler_name):
                    logger.error(f"MISSING HANDLER METHOD: {handler_name} for {source_path}.{signal_name} {context}")
                    return False

            parts = source_path.split('.')
            obj = self

            for part in parts:
                if not hasattr(obj, part):
                    logger.warning(f"Signal connection skipped: {source_path}.{signal_name} - '{part}' not found {context}")
                    return False
                obj = getattr(obj, part)

            if not hasattr(obj, signal_name):
                logger.warning(f"Signal connection skipped: {source_path}.{signal_name} - signal not found {context}")
                return False

            connection_key = f"{source_path}.{signal_name} -> {handler_name}"

            if connection_key in self._connected_signals:
                logger.warning(f"DUPLICATE CONNECTION SKIPPED: {connection_key} {context}")
                return False

            signal = getattr(obj, signal_name)
            signal.connect(handler)

            self._connected_signals.add(connection_key)
            logger.debug(f"Connected: {connection_key} {context}")
            return True

        except Exception as e:
            handler_name = handler.__name__ if hasattr(handler, '__name__') else str(handler)
            logger.error(f"Connection failed: {source_path}.{signal_name} -> {handler_name}: {e} {context}")
            import traceback
            logger.debug(traceback.format_exc())
            return False

    def _connect_signals(self):
        """Connect control panel signals to handlers using defensive pattern."""
        logger.info("Connecting signals with defensive checks...")

        # === CRITICAL CONTROLS ===
        self._safe_connect("control_panel", "view_mode_clicked", self._on_view_mode_cycle, "(critical control)")
        self._safe_connect("control_panel", "day_night_clicked", self._on_theme_cycle, "(critical control)")
        self._safe_connect("control_panel", "record_toggled", self._on_record_toggle, "(critical control)")
        self._safe_connect("control_panel", "snapshot_clicked", self._on_snapshot, "(critical control)")
        self._safe_connect("control_panel", "freeze_frame_toggled", self._on_freeze_toggle, "(critical control)")
        self._safe_connect("control_panel", "auto_roi_clicked", self._on_auto_roi, "(critical control)")
        self._safe_connect("control_panel", "draw_roi_clicked", self._on_draw_roi, "(critical control)")
        self._safe_connect("control_panel", "clear_rois_clicked", self._on_clear_rois, "(critical control)")
        self._safe_connect("control_panel", "camera_clicked", self._on_camera_clicked, "(critical control)")

        # === SETTINGS PANEL ===
        self._safe_connect("settings_panel", "device_changed", self._on_device_changed, "(settings)")
        self._safe_connect("settings_panel", "theme_changed", self._on_theme_changed, "(settings)")
        self._safe_connect("settings_panel", "baseline_lock_toggled", self._on_baseline_toggle, "(settings)")
        self._safe_connect("settings_panel", "palette_changed", self._on_global_palette_changed, "(settings)")

        # === FUSION PANEL ===
        self._safe_connect("fusion_panel", "fusion_mode_changed", self._on_fusion_mode_changed, "(fusion)")
        self._safe_connect("fusion_panel", "fusion_alpha_changed", self._on_fusion_alpha_changed, "(fusion)")
        self._safe_connect("fusion_panel", "fusion_priority_changed", self._on_fusion_priority_changed, "(fusion)")
        self._safe_connect("fusion_panel", "fusion_strength_changed", self._on_fusion_strength_changed, "(fusion)")
        self._safe_connect("fusion_panel", "fusion_fuzziness_changed", self._on_fusion_fuzziness_changed, "(fusion)")
        self._safe_connect("fusion_panel", "fusion_color_mode_changed", self._on_fusion_color_mode_changed, "(fusion)")
        self._safe_connect("fusion_panel", "edge_strength_changed", self._on_edge_strength_changed, "(fusion)")
        self._safe_connect("fusion_panel", "edge_fuzziness_changed", self._on_edge_fuzziness_changed, "(fusion)")
        self._safe_connect("fusion_panel", "edge_color_changed", self._on_edge_color_changed, "(fusion)")
        self._safe_connect("fusion_panel", "detail_strength_changed", self._on_detail_strength_changed, "(fusion)")
        self._safe_connect("fusion_panel", "detail_quality_changed", self._on_detail_quality_changed, "(fusion)")
        self._safe_connect("fusion_panel", "laplacian_gpu_changed", self._on_laplacian_gpu_changed, "(fusion)")
        self._safe_connect("fusion_panel", "laplacian_cpu_scale_changed", self._on_laplacian_cpu_scale_changed, "(fusion)")
        self._safe_connect("fusion_3d_panel", "strength_changed", self._on_3d_relief_strength_changed, "(3d fusion)")
        self._safe_connect("fusion_3d_panel", "mode_changed", self._on_3d_mode_changed, "(3d fusion)")
        self._safe_connect("fusion_3d_panel", "data_source_changed", self._on_3d_data_source_changed, "(3d fusion)")
        self._safe_connect("fusion_3d_panel", "fog_range_changed", self._on_3d_fog_range_changed, "(3d fusion)")
        self._safe_connect("fusion_3d_panel", "contour_interval_changed", self._on_3d_contour_interval_changed, "(3d fusion)")
        self._safe_connect("fusion_3d_panel", "gradient_style_changed", self._on_3d_gradient_style_changed, "(3d fusion)")
        self._safe_connect("fusion_3d_panel", "fog_fade_metric_changed", self._on_3d_fog_fade_metric_changed, "(3d fusion)")

        # === ANALYSIS PANEL ===
        self._safe_connect("analysis_panel", "palette_changed", self._on_global_palette_changed, "(analysis)")
        self._safe_connect("analysis_panel", "baseline_toggled", self._on_baseline_toggle, "(analysis)")
        self._safe_connect("analysis_panel", "overlay_info_toggled", self._on_overlay_info_toggle, "(analysis)")
        self._safe_connect("analysis_panel", "spot_meter_toggled", self._on_spot_meter_toggled, "(analysis)")
        if hasattr(self.analysis_panel, 'clear_spots_clicked'):
             self._safe_connect("analysis_panel", "clear_spots_clicked", self._on_clear_spots_clicked, "(analysis)")

        # === SPOT METER PANEL ===
        if hasattr(self.analysis_panel, 'spot_meter_panel'):
            spot_panel = self.analysis_panel.spot_meter_panel
            spot_panel.spot_deleted.connect(self._on_spot_deleted)
            spot_panel.spot_renamed.connect(self._on_spot_renamed)
            spot_panel.highlight_spot.connect(self._on_highlight_spot)
            spot_panel.preset_requested.connect(self._on_spot_preset_requested)
            spot_panel.alert_triggered.connect(self._on_spot_alert_triggered)

            # Additional spot meter connections
            if hasattr(spot_panel, 'spot_visibility_changed'):
                spot_panel.spot_visibility_changed.connect(self._on_spot_visibility_changed)
            if hasattr(spot_panel, 'spot_locked_changed'):
                spot_panel.spot_locked_changed.connect(self._on_spot_locked_changed)
            if hasattr(spot_panel, 'clear_all_requested'):
                spot_panel.clear_all_requested.connect(self._on_clear_all_spots)
            if hasattr(spot_panel, 'export_requested'):
                spot_panel.export_requested.connect(self._on_spot_export_requested)

            if hasattr(spot_panel, 'spot_selected'):
                spot_panel.spot_selected.connect(self._on_spot_selected)

            if hasattr(spot_panel, 'cursor_readout_cb') and hasattr(self, 'video_widget'):
                spot_panel.cursor_readout_cb.toggled.connect(self._on_cursor_readout_toggled)
                logger.info("  [OK] Connected cursor readout checkbox")

            if hasattr(spot_panel, 'comparison_changed') and hasattr(self, 'video_widget'):
                spot_panel.comparison_changed.connect(self._on_comparison_changed)
                logger.info("  [OK] Connected spot comparison signal")

            logger.info("Connected SpotMeterPanel signals")

        # === GRID OVERLAY PANEL ===
        if hasattr(self.analysis_panel, 'grid_overlay_panel'):
            grid_panel = self.analysis_panel.grid_overlay_panel
            grid_panel.grid_enabled.connect(self._on_grid_enabled)
            grid_panel.grid_spacing_changed.connect(self._on_grid_spacing_changed)
            grid_panel.grid_color_changed.connect(self._on_grid_color_changed)
            logger.info("Connected GridOverlayPanel signals")

        # === ANOMALY WIDGET ===
        self._safe_connect("anomaly_widget", "anomaly_priority_toggled", self._on_anomaly_priority_toggle, "(anomaly)")
        self._safe_connect("anomaly_widget", "anomaly_types_changed", self._on_anomaly_types_changed, "(anomaly)")
        self._safe_connect("anomaly_widget", "fade_strength_changed", self._on_fade_strength_changed, "(anomaly)")
        self._safe_connect("anomaly_widget", "fade_distance_changed", self._on_fade_distance_changed, "(anomaly)")
        self._safe_connect("anomaly_widget", "motion_threshold_changed", self._on_motion_threshold_changed, "(anomaly)")
        self._safe_connect("anomaly_widget", "edge_thresholds_changed", self._on_edge_thresholds_changed, "(anomaly)")
        self._safe_connect("anomaly_widget", "hot_spot_percentile_changed", self._on_hot_spot_percentile_changed, "(anomaly)")
        self._safe_connect("anomaly_widget", "cold_spot_percentile_changed", self._on_cold_spot_percentile_changed, "(anomaly)")
        self._safe_connect("anomaly_widget", "min_anomaly_size_changed", self._on_min_anomaly_size_changed, "(anomaly)")

        # === MANUAL THRESHOLD WIDGET ===
        self._safe_connect("manual_threshold_widget", "enabled_changed", self._on_manual_threshold_enabled, "(manual threshold)")
        self._safe_connect("manual_threshold_widget", "threshold_mode_changed", self._on_manual_threshold_mode_changed, "(manual threshold)")
        self._safe_connect("manual_threshold_widget", "min_threshold_changed", self._on_manual_min_threshold_changed, "(manual threshold)")
        self._safe_connect("manual_threshold_widget", "max_threshold_changed", self._on_manual_max_threshold_changed, "(manual threshold)")
        self._safe_connect("manual_threshold_widget", "use_raw_values_changed", self._on_manual_use_raw_changed, "(manual threshold)")
        self._safe_connect("manual_threshold_widget", "visualization_mode_changed", self._on_manual_viz_mode_changed, "(manual threshold)")

        # (Camera panel signals are dynamically wired via _wire_plugin_panel during initialization)

        # === CALIBRATION PANEL ===
        self._safe_connect("calibration_panel", "add_point_mode_changed", self._on_calibration_add_point_mode, "(calibration)")
        self._safe_connect("calibration_panel", "compute_calibration_clicked", self._on_compute_calibration, "(calibration)")
        self._safe_connect("calibration_panel", "apply_calibration_toggled", self._on_apply_calibration_toggled, "(calibration)")
        self._safe_connect("calibration_panel", "clear_calibration_clicked", self._on_clear_calibration, "(calibration)")
        self._safe_connect("calibration_panel", "export_calibration_clicked", self._on_export_calibration, "(calibration)")
        self._safe_connect("calibration_panel", "import_calibration_clicked", self._on_import_calibration, "(calibration)")
        self._safe_connect("calibration_panel", "remove_point_clicked", self._on_remove_calibration_point, "(calibration)")

        # === RADIOMETRIC PANEL ===
        self._safe_connect("radiometric_panel.enable_checkbox", "stateChanged", self._on_radiometric_enable_changed, "(radiometric)")
        self._safe_connect("radiometric_panel.apply_range_btn", "clicked", self._on_radiometric_range_apply, "(radiometric)")
        self._safe_connect("radiometric_panel.load_lut_btn", "clicked", self._on_load_lut, "(radiometric)")
        self._safe_connect("radiometric_panel.method_linear_radio", "toggled", self._on_radiometric_method_changed, "(radiometric)")
        self._safe_connect("radiometric_panel.method_lut_radio", "toggled", self._on_radiometric_method_changed, "(radiometric)")

        self._safe_connect("radiometric_panel", "spotmeter_enabled_changed", self._on_spotmeter_enabled_changed, "(radiometric spotmeter)")
        self._safe_connect("radiometric_panel", "spotmeter_mode_changed", self._on_spotmeter_mode_changed, "(radiometric spotmeter)")
        self._safe_connect("radiometric_panel", "sensor_temps_requested", self._on_sensor_temps_requested, "(radiometric spotmeter)")

        # === PARALLAX PANEL ===
        self._safe_connect("parallax_panel", "parallax_toggled", self._on_parallax_toggled, "(parallax)")
        self._safe_connect("parallax_panel", "baseline_changed", self._on_parallax_baseline_changed, "(parallax)")
        self._safe_connect("parallax_panel", "depth_method_changed", self._on_parallax_method_changed, "(parallax)")
        self._safe_connect("parallax_panel.apply_geometry_btn", "clicked", self._on_parallax_geometry_apply, "(parallax)")
        self._safe_connect("parallax_panel", "show_depth_map_toggled", self._on_show_depth_map_toggled, "(parallax depth)")
        self._safe_connect("parallax_panel", "show_displacement_toggled", self._on_show_displacement_toggled, "(parallax displacement)")
        self._safe_connect("parallax_panel", "shift_changed", self._on_parallax_shift_changed, "(parallax shift)")
        self._safe_connect("parallax_panel", "auto_alignment_requested", self._on_parallax_auto_alignment_requested, "(parallax auto-align)")
        self._safe_connect("parallax_panel", "zoom_changed", self._on_parallax_zoom_changed, "(parallax zoom)")
        self._safe_connect("parallax_panel", "correction_target_changed", self._on_parallax_correction_target_changed, "(parallax target)")
        self._safe_connect("parallax_panel", "rgb_target_max_width_changed", self._on_parallax_rgb_target_max_width_changed, "(parallax rgb cap)")

        # === GRADIENT OVERLAY PANEL ===
        self._safe_connect("gradient_panel", "gradient_enabled", self._on_gradient_enabled, "(gradient)")
        self._safe_connect("gradient_panel", "gradient_mode_changed", self._on_gradient_mode_changed, "(gradient)")
        self._safe_connect("gradient_panel", "gradient_threshold_changed", self._on_gradient_threshold_changed, "(gradient)")
        self._safe_connect("gradient_panel", "gradient_color_map_changed", self._on_gradient_colormap_changed, "(gradient)")

        # === LINE PROFILE PANEL ===
        self._safe_connect("line_profile_panel", "line_mode_toggled", self._on_line_profile_mode_toggled, "(line profile)")
        self._safe_connect("line_profile_panel", "line_deleted", self._on_line_profile_deleted, "(line profile)")
        self._safe_connect("line_profile_panel", "clear_all_requested", self._on_line_profile_clear_all, "(line profile)")
        self._safe_connect("line_profile_panel", "export_requested", self._on_line_profile_export, "(line profile)")

        # === RADIOMETRIC PANEL 8-Bit ===
        self._safe_connect("radiometric_panel", "estimation_8bit_enabled_changed", self._on_8bit_estimation_toggled, "(radiometric 8-bit)")
        self._safe_connect("radiometric_panel", "temperature_range_changed", self._on_temperature_range_changed, "(radiometric 8-bit)")
        self._safe_connect("radiometric_panel", "calibrate_single_point_requested", self._on_calibrate_single_point, "(radiometric 8-bit)")
        self._safe_connect("radiometric_panel", "calibrate_two_point_requested", self._on_calibrate_two_point, "(radiometric 8-bit)")

        # === RADIOMETRIC PANEL Unit & Detection Settings ===
        self._safe_connect("radiometric_panel", "temperature_unit_changed", self._on_radiometric_temp_unit_changed, "(radiometric unit)")
        self._safe_connect("radiometric_panel", "max_hot_spots_changed", self._on_radiometric_max_hot_spots_changed, "(radiometric spots)")
        self._safe_connect("radiometric_panel", "max_cold_spots_changed", self._on_radiometric_max_cold_spots_changed, "(radiometric spots)")

        # === GENERAL ANALYSIS PANEL Detection Toggles ===
        self._safe_connect("analysis_panel.show_hot_spots_checkbox", "toggled", self._on_show_hot_spots_toggled, "(detection toggle)")
        self._safe_connect("analysis_panel.show_cold_spots_checkbox", "toggled", self._on_show_cold_spots_toggled, "(detection toggle)")
        self._safe_connect("analysis_panel.show_anomalies_checkbox", "toggled", self._on_show_anomalies_toggled, "(detection toggle)")

        # === ROI MANAGEMENT ===
        # roi_selected and roi_deleted live on roi_temp_panel, not analysis_panel.
        # roi_temp_panel signals are wired during panel construction above.
        # Keep this comment so _safe_connect failures are not re-introduced.

        # === ENVIRONMENTAL COMPENSATION PANEL ===
        self._safe_connect("env_comp_panel", "emissivity_changed", self._on_emissivity_changed, "(environmental)")
        self._safe_connect("env_comp_panel", "atmospheric_temp_changed", self._on_atmospheric_temp_changed, "(environmental)")
        self._safe_connect("env_comp_panel", "atmospheric_transmission_changed", self._on_atmospheric_transmission_changed, "(environmental)")

        # === ISOTHERM PANEL ===
        self._safe_connect("isotherm_panel", "enabled_changed", self._on_isotherm_enabled_changed, "(isotherm)")
        self._safe_connect("isotherm_panel", "mode_changed", self._on_isotherm_mode_changed, "(isotherm)")
        self._safe_connect("isotherm_panel", "low_threshold_changed", self._on_isotherm_low_threshold_changed, "(isotherm)")
        self._safe_connect("isotherm_panel", "high_threshold_changed", self._on_isotherm_high_threshold_changed, "(isotherm)")
        self._safe_connect("isotherm_panel", "color_changed", self._on_isotherm_color_changed, "(isotherm)")
        self._safe_connect("isotherm_panel", "bands_changed", self._on_isotherm_bands_changed, "(isotherm multiband)")

        # === ROI OVERLAY ===
        self._safe_connect("video_widget.overlay", "roi_created", self._on_roi_created, "(roi overlay)")
        self._safe_connect("video_widget.overlay", "roi_selected", self._on_roi_selected, "(roi overlay)")

        # === VIDEO WIDGET ===
        self._safe_connect("video_widget", "cursor_moved", self._on_cursor_moved, "(video)")

        # === SPOT METER SIGNALS ===
        self._safe_connect("radiometric_panel", "spot_meter_toggled", self._on_spot_meter_toggled, "(spot meter)")
        self._safe_connect("radiometric_panel", "clear_spot_meters_requested", self._on_clear_spots_clicked, "(spot meter)")
        self._safe_connect("video_widget.overlay", "spot_meter_clicked", self._on_spot_meter_clicked, "(spot meter)")

        # === MODE SYNC SIGNALS ===
        self._safe_connect("video_widget.overlay", "spot_meter_mode_changed", self._on_overlay_spot_meter_mode_changed, "(mode sync)")
        self._safe_connect("video_widget.overlay", "drawing_mode_changed", self._on_overlay_drawing_mode_changed, "(mode sync)")

        logger.info("[OK] Signal connections complete (defensive mode)")

        # Connect proactive feedback signals from event bus
        self._connect_feedback_signals()

        logger.info("Generic signal wiring completed.")

    # ========================================================================
    # Feedback Signal Connections (backend → GUI, proactive)
    # ========================================================================

    def _connect_feedback_signals(self):
        """Connect backend feedback signals to GUI update handlers."""
        if not self.event_bus:
            logger.debug("No event_bus available — skipping feedback connections")
            return

        bus = self.event_bus

        # --- Generic Camera Feedback Signals ---
        bus.camera_command_result.connect(self._on_bus_camera_command_result)
        bus.camera_connected.connect(self._on_bus_camera_connected)
        bus.camera_disconnected.connect(self._on_bus_camera_disconnected)
        bus.sdk_connected.connect(self._on_bus_sdk_connected)
        bus.sdk_disconnected.connect(self._on_bus_sdk_disconnected)
        bus.panel_ready.connect(self._on_bus_panel_ready)
        bus.ports_scan_result.connect(self._on_bus_ports_scan_result)

        # --- Calibration ---
        bus.calibration_compute_result.connect(self._on_bus_calibration_compute_result)
        bus.calibration_export_result.connect(self._on_bus_calibration_export_result)
        bus.calibration_import_result.connect(self._on_bus_calibration_import_result)
        bus.calibration_gui_update_requested.connect(self._on_bus_calibration_gui_update)
        bus.parallax_auto_alignment_result.connect(self._on_bus_parallax_auto_alignment_result)

        # --- Manual Threshold Anomaly Detection ---
        bus.threshold_stats_updated.connect(self._on_bus_threshold_stats_updated)

        # --- Recording ---
        bus.recording_state_changed.connect(self._on_bus_recording_state_changed)

        # --- Sensor Temps ---
        bus.sensor_temps_result.connect(self._on_bus_sensor_temps_result)

        logger.info("[OK] Feedback signal connections established")

    def _emit_camera_command(self, role: str, command: str, params: dict):
        """Emit camera_command_requested on the event bus."""
        if self.event_bus:
            self.event_bus.camera_command_requested.emit(role, command, params)
        elif self.app and hasattr(self.app, 'execute_camera_command'):
            self.app.execute_camera_command(role, command, params)

    def _parse_connect_args(self, args: tuple) -> dict:
        """Helper to parse variable argument tuples for connect requests."""
        if not args:
            return {}
        if len(args) == 1:
            return {'com_port': str(args[0])}
        elif len(args) >= 2:
            return {'com_port': str(args[0]), 'baud_rate': int(args[1])}
        return {}

    def _wire_plugin_panel(self, plugin, panel):
        """Wire signals from a plugin control panel into the generic event bus."""
        role = plugin.camera_role.value if hasattr(plugin.camera_role, 'value') else str(plugin.camera_role)

        if hasattr(panel, 'connect_requested'):
            panel.connect_requested.connect(
                lambda *args: self._emit_camera_command(role, 'connect', self._parse_connect_args(args))
            )
        if hasattr(panel, 'sdk_connect_requested'):
            panel.sdk_connect_requested.connect(
                lambda *args: self._emit_camera_command(role, 'connect', self._parse_connect_args(args))
            )
        if hasattr(panel, 'disconnect_requested'):
            panel.disconnect_requested.connect(
                lambda: self._emit_camera_command(role, 'disconnect', {})
            )
        if hasattr(panel, 'sdk_disconnect_requested'):
            panel.sdk_disconnect_requested.connect(
                lambda: self._emit_camera_command(role, 'disconnect', {})
            )
        if hasattr(panel, 'scan_ports_requested'):
            panel.scan_ports_requested.connect(
                lambda: self._emit_camera_command(role, 'scan_ports', {})
            )
        if hasattr(panel, 'sdk_scan_ports_requested'):
            panel.sdk_scan_ports_requested.connect(
                lambda: self._emit_camera_command(role, 'scan_ports', {})
            )

        if hasattr(panel, 'ffc_triggered'):
            panel.ffc_triggered.connect(
                lambda: self._emit_camera_command(role, 'ffc', {})
            )
        if hasattr(panel, 'ffc_requested'):
            panel.ffc_requested.connect(
                lambda: self._emit_camera_command(role, 'ffc', {})
            )

        if hasattr(panel, 'gain_mode_changed'):
            panel.gain_mode_changed.connect(
                lambda mode: self._emit_camera_command(role, 'set_gain_mode', {'mode': str(mode)})
            )
        if hasattr(panel, 'ffc_mode_changed'):
            panel.ffc_mode_changed.connect(
                lambda mode: self._emit_camera_command(role, 'set_ffc_mode', {'mode': str(mode)})
            )
        if hasattr(panel, 'color_lut_changed'):
            panel.color_lut_changed.connect(
                lambda lut: self._emit_camera_command(role, 'set_palette', {'palette': str(lut)})
            )
        if hasattr(panel, 'shutter_position_changed'):
            panel.shutter_position_changed.connect(
                lambda pos: self._emit_camera_command(role, 'set_shutter_position', {'position': str(pos)})
            )
        if hasattr(panel, 'tlinear_toggled'):
            panel.tlinear_toggled.connect(
                lambda en, res='high': self._emit_camera_command(role, 'set_tlinear', {'enabled': en, 'resolution': res})
            )
        if hasattr(panel, 'radiometric_mode_changed'):
            panel.radiometric_mode_changed.connect(
                lambda en: self._emit_camera_command(role, 'set_radiometric_mode', {'enabled': en})
            )
        if hasattr(panel, 'radiometry_toggled'):
            panel.radiometry_toggled.connect(
                lambda en: self._emit_camera_command(role, 'set_radiometric', {'enabled': en})
            )
        if hasattr(panel, 'fpa_temp_requested'):
            panel.fpa_temp_requested.connect(
                lambda: self._emit_camera_command(role, 'get_fpa_temp', {})
            )
        if hasattr(panel, 'environmental_settings_changed'):
            panel.environmental_settings_changed.connect(
                lambda settings: self._emit_camera_command(role, 'set_environmental', settings)
            )

        for sig, param in [
            ('agc_max_gain_changed', 'max_gain'),
            ('agc_gamma_changed', 'gamma'),
            ('agc_linearity_changed', 'linearity'),
            ('agc_dde_changed', 'dde'),
            ('agc_plateau_changed', 'plateau'),
            ('agc_dampening_changed', 'dampening'),
        ]:
            if hasattr(panel, sig):
                getattr(panel, sig).connect(
                    (lambda p: lambda val: self._emit_camera_command(role, 'set_agc', {p: val}))(param)
                )

        if hasattr(panel, 'exposure_mode_changed'):
            panel.exposure_mode_changed.connect(
                lambda mode: self._emit_camera_command(role, 'set_exposure_mode', {'mode': str(mode)})
            )
        if hasattr(panel, 'exposure_time_changed'):
            panel.exposure_time_changed.connect(
                lambda time_us: self._emit_camera_command(role, 'set_exposure_time', {'time_us': float(time_us)})
            )
        if hasattr(panel, 'gain_changed'):
            panel.gain_changed.connect(
                lambda gain_db: self._emit_camera_command(role, 'set_gain', {'gain_db': float(gain_db)})
            )
        if hasattr(panel, 'white_balance_mode_changed'):
            panel.white_balance_mode_changed.connect(
                lambda mode: self._emit_camera_command(role, 'set_white_balance_mode', {'mode': str(mode)})
            )
        if hasattr(panel, 'white_balance_calibrate'):
            panel.white_balance_calibrate.connect(
                lambda: self._emit_camera_command(role, 'calibrate_white_balance', {})
            )
        if hasattr(panel, 'white_balance_ratio_changed'):
            panel.white_balance_ratio_changed.connect(
                lambda color, ratio: self._emit_camera_command(role, 'set_white_balance_ratio', {'color': str(color), 'ratio': float(ratio)})
            )
        if hasattr(panel, 'trigger_mode_changed'):
            panel.trigger_mode_changed.connect(
                lambda en, src='Software': self._emit_camera_command(role, 'set_trigger_mode', {'enabled': bool(en), 'source': str(src)})
            )
        if hasattr(panel, 'trigger_fire'):
            panel.trigger_fire.connect(
                lambda: self._emit_camera_command(role, 'trigger_fire', {})
            )
        if hasattr(panel, 'gamma_changed'):
            panel.gamma_changed.connect(
                lambda gamma: self._emit_camera_command(role, 'set_gamma', {'gamma': float(gamma)})
            )
        # Generic direct command emission from new panels
        if hasattr(panel, 'command_requested'):
            panel.command_requested.connect(
                lambda cmd, params: self._emit_camera_command(role, cmd, params)
            )
        if hasattr(panel, 'agc_reset_requested'):
            panel.agc_reset_requested.connect(
                lambda: self._emit_camera_command(role, 'reset_agc', {})
            )
        if hasattr(panel, 'housing_temp_requested'):
            panel.housing_temp_requested.connect(
                lambda: self._emit_camera_command(role, 'get_housing_temp', {})
            )
        if hasattr(panel, 'palette_changed'):
            panel.palette_changed.connect(
                lambda pal: self._emit_camera_command(role, 'set_palette', {'palette': str(pal)})
            )
        if hasattr(panel, 'do_ffc_requested'):
            panel.do_ffc_requested.connect(
                lambda: self._emit_camera_command(role, 'ffc', {})
            )

    # --- Generic Camera feedback handlers ---

    def _on_bus_camera_command_result(self, role: str, command: str, result: dict):
        """React to generic camera command execution result."""
        success = result.get('success', False)

        # camera_panels is keyed by plugin_id, not role - resolve to the one
        # panel that actually issued this command. Iterating every panel
        # unfiltered fed every camera's command results (including another
        # camera's FPA-temp tuple/shape) into every OTHER camera's panel,
        # e.g. a connected Boson's result reaching Tau2ControlPanel and
        # crashing it on a value it never expected.
        target_panel = None
        if self.app and hasattr(self.app, 'plugin_host'):
            active = self.app.plugin_host.get_active_camera(role)
            if active:
                target_panel = getattr(self, 'camera_panels', {}).get(active.plugin.plugin_id)
        panels = [target_panel] if target_panel else []

        for panel in panels:
            if command == 'ffc' and hasattr(panel, 'set_status'):
                if success:
                    panel.set_status("FFC completed successfully")
                    if hasattr(self, 'statusBar'):
                        self.statusBar().showMessage("FFC complete", 3000)
                else:
                    panel.set_status("FFC failed", is_error=True)
            elif command == 'scan_ports' and result.get('ports'):
                if hasattr(panel, 'update_ports'):
                    panel.update_ports(result['ports'])
                elif hasattr(panel, 'update_ports_list'):
                    panel.update_ports_list(result['ports'])
            elif command in ('get_fpa_temp', 'get_housing_temp', 'get_camera_info') and hasattr(panel, 'update_camera_info'):
                panel.update_camera_info(result)

    def _on_bus_sdk_connected(self, role: str, info: dict):
        """React to camera SDK connection."""
        # Same role -> plugin_id -> panel resolution as
        # _on_bus_camera_command_result - broadcasting to every panel showed
        # "Connected" on cameras that were never touched.
        target_panel = None
        if self.app and hasattr(self.app, 'plugin_host'):
            active = self.app.plugin_host.get_active_camera(role)
            if active:
                target_panel = getattr(self, 'camera_panels', {}).get(active.plugin.plugin_id)

        if target_panel:
            if hasattr(target_panel, 'update_connection_status'):
                target_panel.update_connection_status(True)
            if info and hasattr(target_panel, 'update_camera_info'):
                try:
                    target_panel.update_camera_info(info)
                except Exception:
                    pass

        # 8-bit estimation is a stand-in for cameras that can't produce true
        # calibrated temperature; only offer it once we can tell (SDK
        # connected) and only for non-radiometric hardware. A radiometric
        # camera should use its real conversion, not an AGC guess.
        if role == 'thermal' and hasattr(self, 'radiometric_panel'):
            # Default True (assume radiometric) when a plugin doesn't report
            # this key at all — Tau2/Lepton already do real conversion via
            # their own path, and offering an AGC-guess toggle on top of a
            # camera that already produces calibrated temperatures would be
            # actively misleading, not just redundant.
            is_rad = bool((info or {}).get('radiometric_capable', True))
            self.radiometric_panel.set_8bit_estimation_available(not is_rad)
            self.update_radiometric_panel_availability(is_rad)

    def _on_bus_sdk_disconnected(self, role: str):
        """React to camera SDK disconnection."""
        target_panel = None
        if self.app and hasattr(self.app, 'plugin_host'):
            active = self.app.plugin_host.get_active_camera(role)
            if active:
                target_panel = getattr(self, 'camera_panels', {}).get(active.plugin.plugin_id)
        if target_panel and hasattr(target_panel, 'update_connection_status'):
            target_panel.update_connection_status(False)

        if role == 'thermal' and hasattr(self, 'radiometric_panel'):
            self.radiometric_panel.set_8bit_estimation_available(False)
            self.update_radiometric_panel_availability(False)

    def _on_bus_camera_connected(self, role: str, capabilities: dict):
        """React to camera hardware hotplug connection and focus active panel."""
        model = capabilities.get('model', '').lower()
        plugin_id = capabilities.get('plugin_id', '').lower()
        logger.info(f"Camera connected for role '{role}': {capabilities.get('model', 'Unknown')}")

        target_panel = None
        for pid, p in getattr(self, 'camera_panels', {}).items():
            if pid == plugin_id or pid in model:
                target_panel = p
                break
            if role == 'thermal':
                if 'boson' in model and 'boson' in pid:
                    target_panel = p; break
                elif 'tau' in model and 'tau' in pid:
                    target_panel = p; break
                elif 'lepton' in model and 'lepton' in pid:
                    target_panel = p; break
                elif 'gige' in model and 'gige' in pid:
                    target_panel = p; break
            elif role == 'rgb':
                if 'firefly' in model and 'firefly' in pid:
                    target_panel = p; break
                elif ('brio' in model or 'uvc' in model or 'webcam' in model or 'camera' in model) and 'uvc' in pid:
                    target_panel = p; break

        if target_panel and hasattr(self, 'cameras_tabs'):
            self.cameras_tabs.setCurrentWidget(target_panel)

        cam_name = capabilities.get('model') or f"{role.capitalize()} Camera"
        msg = f"📷 {cam_name} connected and active"
        if hasattr(self, 'statusBar'):
            self.statusBar().showMessage(msg, 5000)
        self._show_hotplug_banner(msg, warning=False)

    def _on_bus_camera_disconnected(self, role: str):
        """React to camera hardware disconnection."""
        logger.info(f"Camera disconnected for role '{role}'")
        msg = f"⚠  {role.capitalize()} camera disconnected — using placeholder."
        if hasattr(self, 'statusBar'):
            self.statusBar().showMessage(msg, 5000)
        self._show_hotplug_banner(msg, warning=True)

    def _on_bus_panel_ready(self, role: str, panel):
        """Swap in the just-activated (SDK-wired) panel for whichever plugin
        claimed this role, replacing its startup-time placeholder tab in
        place instead of stacking a second, generically-titled tab.

        activate_camera() calls plugin.create_control_panel() fresh on every
        activation - a different object than the one the startup loop in
        _init_ui already put in cameras_tabs/camera_panels for every
        registered plugin. Previously this handler just added the new panel
        under a new "Thermal"/"Rgb" tab and left camera_panels[plugin_id]
        pointing at the old, never-connected one - so the plugin's own
        named tab (e.g. "FLIR Boson") looked identical to and permanently
        disconnected from the real, working one, and status routing that
        reads camera_panels (_on_bus_camera_command_result,
        _on_bus_sdk_connected, port-scan broadcast) updated the dead panel
        instead of the one on screen. The new panel's buttons were never
        wired to dispatch commands either, since _wire_plugin_panel() was
        only ever called on the startup panel.
        """
        if not hasattr(self, 'cameras_tabs') or not panel:
            return

        for i in range(self.cameras_tabs.count()):
            if self.cameras_tabs.widget(i) == panel:
                self.cameras_tabs.setCurrentWidget(panel)
                return

        active = None
        if self.app and hasattr(self.app, 'plugin_host'):
            active = self.app.plugin_host.get_active_camera(role)
        plugin_id = active.plugin.plugin_id if active else None

        old_panel = getattr(self, 'camera_panels', {}).get(plugin_id) if plugin_id else None
        replaced = False
        if old_panel is not None:
            for i in range(self.cameras_tabs.count()):
                if self.cameras_tabs.widget(i) == old_panel:
                    title = self.cameras_tabs.tabText(i)
                    self.cameras_tabs.removeTab(i)
                    # QTabWidget.removeTab() does NOT destroy the removed
                    # widget - it's left as a live, still-parented,
                    # still-wired-to-_wire_plugin_panel's connections
                    # orphan. Every reconnect/hot-plug of the same camera
                    # would otherwise add another one, none ever freed for
                    # the life of the process.
                    old_panel.deleteLater()
                    self.cameras_tabs.insertTab(i, panel, title)
                    replaced = True
                    break

        if not replaced:
            self.cameras_tabs.addTab(panel, f"{role.capitalize()}")

        if plugin_id:
            self.camera_panels[plugin_id] = panel
            self._wire_plugin_panel(active.plugin, panel)
            # Keep the convenience per-plugin attributes (used by
            # show_camera_connected_notification's auto-focus) pointing at
            # the live panel too, not the just-removed startup one.
            convenience_attr = {
                'flir_boson': 'boson_panel', 'flir_tau2': 'tau2_panel',
                'flir_lepton': 'lepton_panel', 'flir_firefly': 'firefly_panel',
                'generic_uvc': 'uvc_panel', 'gige_vision': 'gige_panel',
            }.get(plugin_id)
            if convenience_attr:
                setattr(self, convenience_attr, panel)

        self.cameras_tabs.setCurrentWidget(panel)

    def _on_bus_ports_scan_result(self, ports: list):
        """Update port list from scan result."""
        for panel in getattr(self, 'camera_panels', {}).values():
            if hasattr(panel, 'update_ports'):
                panel.update_ports(ports)
            elif hasattr(panel, 'update_ports_list'):
                panel.update_ports_list(ports)

    # --- Calibration feedback handlers ---

    def _on_bus_calibration_compute_result(self, success: bool):
        """React to calibration compute result."""
        if success:
            logger.info("Calibration computed successfully")
        else:
            QMessageBox.warning(
                self, "Calibration Error",
                "Failed to compute calibration.\n"
                "Need at least 2 points for linear, more for polynomial."
            )

    def _on_bus_calibration_export_result(self, success: bool, path: str):
        """React to calibration export result."""
        if success:
            QMessageBox.information(self, "Export Successful",
                                    f"Calibration exported to:\n{path}")
        else:
            QMessageBox.critical(self, "Export Failed",
                                 "Failed to export calibration")

    def _on_bus_calibration_import_result(self, success: bool, path: str):
        """React to calibration import result."""
        if success:
            QMessageBox.information(self, "Import Successful",
                                    f"Calibration imported from:\n{path}")
        else:
            QMessageBox.critical(self, "Import Failed",
                                 "Failed to import calibration")

    def _on_bus_calibration_gui_update(self):
        """Refresh calibration GUI after backend state change."""
        if self.app and hasattr(self.app, 'update_calibration_gui'):
            self.app.update_calibration_gui()

    def _on_bus_threshold_stats_updated(self, anomaly_percentage: float, anomaly_count: int, total_pixels: int):
        """Push manual-threshold detection stats to the panel's Detection Statistics display."""
        if hasattr(self, 'manual_threshold_widget'):
            self.manual_threshold_widget.update_statistics(anomaly_percentage, anomaly_count, total_pixels)

    # --- Recording feedback handlers ---

    def _on_bus_recording_state_changed(self, is_recording: bool):
        """Sync recording UI to actual backend state."""
        self.recording = is_recording
        if hasattr(self, 'control_panel'):
            self.control_panel.update_record_button(is_recording)

    def _on_bus_sensor_temps_result(self, fpa: float, housing: float):
        """Display sensor temperature results in status bar."""
        parts = []
        if fpa:
            parts.append(f"FPA: {fpa:.1f} K")
        if housing:
            parts.append(f"Housing: {housing:.1f} K")
        msg = "  |  ".join(parts) if parts else "Sensor temps: N/A"
        if hasattr(self, 'statusBar'):
            self.statusBar().showMessage(msg, 5000)
        logger.info(f"Sensor temps — {msg}")

    # ========================================================================
    # Keyboard Shortcuts
    # ========================================================================

    def keyPressEvent(self, event):
        """Handle keyboard shortcuts."""
        key = event.key()
        modifiers = event.modifiers()

        if key == Qt.Key.Key_D and modifiers == Qt.KeyboardModifier.ControlModifier:
            self._toggle_developer_mode()
        elif key in (Qt.Key.Key_Q, Qt.Key.Key_Escape):
            self.close()
        elif key == Qt.Key.Key_V:
            self._on_view_mode_cycle()
        elif key == Qt.Key.Key_C:
            self._on_palette_cycle()
        elif key == Qt.Key.Key_T:
            self._on_theme_cycle()
        elif key == Qt.Key.Key_R:
            self.control_panel.record_btn.setChecked(not self.recording)
        elif key == Qt.Key.Key_S:
            self._on_snapshot()
        elif key == Qt.Key.Key_Space:
            self.control_panel.freeze_btn.setChecked(not self.frozen)
        elif key == Qt.Key.Key_A:
            self._on_auto_roi()
        else:
            super().keyPressEvent(event)

    def _toggle_developer_mode(self):
        """Toggle developer mode (show/hide advanced controls and analysis panel)."""
        self.developer_mode = not self.developer_mode
        self.control_panel.show_developer_controls(self.developer_mode)
        self.right_panel_tabs.setVisible(self.developer_mode)

        if self.developer_mode:
            self.resize(self.width() + 350, self.height())
        else:
            self.resize(self.width() - 350, self.height())

        mode_text = "ON" if self.developer_mode else "OFF"
        logger.warning(f"********** DEVELOPER MODE: {mode_text} **********")
        if hasattr(self, 'statusBar'):
            self.statusBar().showMessage(f"Developer Mode: {mode_text} (Press Ctrl+D to toggle)", 5000)

    # ========================================================================
    # Theme Methods
    # ========================================================================

    def _on_theme_changed(self, theme: str):
        """Handle theme change from settings."""
        self._apply_theme(theme)

    def _apply_theme(self, theme: str):
        """Apply color theme."""
        self.current_theme = theme

        actual_theme = theme
        if theme == "auto":
            import datetime
            hour = datetime.datetime.now().hour
            actual_theme = "Light Mode" if 7 <= hour < 19 else "Dark Mode"

        # STATE_COLORS_QSS is appended after every theme (not baked into
        # each one) so recording/frozen/primary-action buttons keep a fixed,
        # recognizable color while inheriting that theme's own QPushButton
        # border-radius/padding/border via the cascade - see its docstring.
        if actual_theme in THEMES:
            self.setStyleSheet(THEMES[actual_theme] + STATE_COLORS_QSS)
        elif actual_theme == "light":
            self.setStyleSheet(THEMES.get("Light Mode", LIGHT_THEME) + STATE_COLORS_QSS)
        elif actual_theme == "dark":
            self.setStyleSheet(THEMES.get("Dark Mode", DARK_THEME) + STATE_COLORS_QSS)
        else:
            logger.warning(f"Unknown theme: {actual_theme}")

        if hasattr(self, 'control_panel'):
            if theme == "auto":
                self.control_panel.update_theme_button(f"auto ({actual_theme})")
            else:
                self.control_panel.update_theme_button(theme)

    def _on_theme_cycle(self):
        """Cycle through themes."""
        themes = list(THEMES.keys()) + ["auto"]

        current = self.current_theme
        if current not in themes:
            if current == "light": current = "Light Mode"
            elif current == "dark": current = "Dark Mode"
            elif current == "colorful": current = "Colorful"
            elif current == "solarized": current = "Solarized"

        current_idx = themes.index(current) if current in themes else 0
        next_theme = themes[(current_idx + 1) % len(themes)]
        self._apply_theme(next_theme)
        logger.info(f"Theme: {next_theme}")

    # ========================================================================
    # Signal Handler Methods
    # ========================================================================

    def _on_radiometric_max_cold_spots_changed(self, count: int):
        if self.event_bus:
            self.event_bus.max_cold_spots_changed.emit(count)
        elif self.app and hasattr(self.app, 'thermal_analyzer'):
            self.app.thermal_analyzer.max_cold_spots = count
        logger.info(f"Max cold spots set to: {count}")

    def _on_radiometric_max_hot_spots_changed(self, count: int):
        if self.event_bus:
            self.event_bus.max_hot_spots_changed.emit(count)
        elif self.app and hasattr(self.app, 'thermal_analyzer'):
            self.app.thermal_analyzer.max_hot_spots = count
        logger.info(f"Max hot spots set to: {count}")

    def _on_show_hot_spots_toggled(self, enabled: bool):
        if hasattr(self, 'video_widget') and hasattr(self.video_widget, 'overlay'):
            self.video_widget.overlay.show_hot_spots = enabled
            self.video_widget.overlay.update()
            logger.info(f"Show hot spots: {enabled}")

    def _on_show_cold_spots_toggled(self, enabled: bool):
        if hasattr(self, 'video_widget') and hasattr(self.video_widget, 'overlay'):
            self.video_widget.overlay.show_cold_spots = enabled
            self.video_widget.overlay.update()
            logger.info(f"Show cold spots: {enabled}")

    def _on_show_anomalies_toggled(self, enabled: bool):
        if hasattr(self, 'video_widget') and hasattr(self.video_widget, 'overlay'):
            self.video_widget.overlay.show_anomalies = enabled
            self.video_widget.overlay.update()
            logger.info(f"Show anomalies: {enabled}")

    def _on_radiometric_enable_changed(self, enabled: bool):
        """Handle radiometric enable toggle."""
        logger.info(f"Radiometric enable toggled: {enabled}")
        if self.event_bus:
            self.event_bus.radiometric_enabled_changed.emit(enabled)
        elif self.app:
            self.app.enable_radiometric(enabled)

    def _on_radiometric_range_apply(self):
        """Apply manual radiometric range."""
        if not hasattr(self, 'radiometric_panel'):
            return
        try:
            low = self.radiometric_panel.range_low_spin.value()
            high = self.radiometric_panel.range_high_spin.value()
            logger.info(f"Applying radiometric range: {low} - {high}")
            if self.event_bus:
                self.event_bus.radiometric_range_apply_requested.emit(low, high)
            elif self.app and hasattr(self.app, 'radiometric_controller'):
                self.app.radiometric_controller.set_temperature_range(low, high)
        except Exception as e:
            logger.error(f"Error applying radiometric range: {e}")

    def _on_load_lut(self):
        """Load custom Look-Up Table (LUT) and apply to palette manager."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Load LUT File", "", "LUT Files (*.csv *.png *.jpg);;All Files (*)"
        )
        if not file_path:
            return
        logger.info(f"Loading LUT from: {file_path}")
        if self.event_bus:
            # Palette manager wiring is pending — log until PaletteManager.load_custom_lut() is implemented
            logger.info("[LUT] Event bus path not yet wired — PaletteManager.load_custom_lut() pending implementation")
        elif self.app and hasattr(self.app, 'palette_manager'):
            pm = self.app.palette_manager
            if hasattr(pm, 'load_custom_lut'):
                success = pm.load_custom_lut(file_path)
                if success:
                    QMessageBox.information(self, "LUT Loaded", f"Custom LUT loaded from:\n{file_path}")
                else:
                    QMessageBox.warning(self, "LUT Load Failed", f"Could not load LUT from:\n{file_path}")
            else:
                logger.info("[LUT] PaletteManager.load_custom_lut() not yet implemented")

    def _on_radiometric_method_changed(self):
        """Handle radiometric conversion method change (Linear vs LUT)."""
        if not hasattr(self, 'radiometric_panel'):
            return
        is_lut = self.radiometric_panel.method_lut_radio.isChecked()
        mode = "lut" if is_lut else "t-linear"
        logger.info(f"Radiometric method changed to: {mode}")
        if self.event_bus:
            self.event_bus.radiometric_method_changed.emit(mode)
        elif self.app and hasattr(self.app, 'radiometric_controller'):
            if hasattr(self.app.radiometric_controller, 'set_conversion_method'):
                self.app.radiometric_controller.set_conversion_method(mode)

    def _on_spotmeter_enabled_changed(self, enabled: bool):
        """Handle spotmeter enable toggle."""
        if self.event_bus:
            self.event_bus.spotmeter_enabled_changed.emit(enabled)
        elif self.app and hasattr(self.app, 'thermal_analyzer'):
            self.app.thermal_analyzer.spotmeter_enabled = enabled
        logger.info(f"Spotmeter analysis enabled: {enabled}")

    def _on_spotmeter_mode_changed(self, mode: str):
        """Handle spotmeter mode change (center, max, min)."""
        if self.event_bus:
            self.event_bus.spotmeter_mode_changed.emit(mode)
        elif self.app and hasattr(self.app, 'thermal_analyzer'):
            self.app.thermal_analyzer.spotmeter_mode = mode
        logger.info(f"Spotmeter mode set to: {mode}")

    def _on_sensor_temps_requested(self):
        """Request FPA/Housing temperatures via event bus."""
        if self.event_bus:
            self.event_bus.sensor_temps_requested.emit()
        elif self.app and self.app.thermal_camera:
            try:
                if hasattr(self.app.thermal_camera, 'get_fpa_temperature'):
                    fpa = self.app.thermal_camera.get_fpa_temperature()
                    msg = f"FPA Temp: {fpa:.2f} K" if fpa else "FPA Temp: N/A"
                    logger.info(msg)
                    self.statusBar().showMessage(msg, 5000)
            except Exception as e:
                logger.error(f"Error getting sensor temps: {e}")

    def _on_8bit_estimation_toggled(self, enabled: bool):
        """Handle 8-bit estimation toggle."""
        if self.event_bus:
            self.event_bus.estimation_8bit_enabled_changed.emit(enabled)
        logger.info(f"8-bit estimator enabled: {enabled}")

    def _on_temperature_range_changed(self, low: float, high: float):
        """Handle temperature range change for estimation."""
        if self.event_bus:
            self.event_bus.estimation_range_changed.emit(low, high)

    def _on_calibrate_single_point(self):
        """
        Handle single point calibration.

        radiometric_panel.calibrate_single_point_requested fires with no
        arguments (it's just a button click) — the reference temperature
        has no other input field in the UI, so it's collected here.
        """
        from PyQt6.QtWidgets import QInputDialog
        temp, ok = QInputDialog.getDouble(
            self, "Single-Point Calibration",
            "Known reference temperature (°C) at the center of frame\n"
            "(point the camera at the reference object first):",
            20.0, -40.0, 550.0, 1
        )
        if not ok:
            return
        if self.event_bus:
            self.event_bus.calibrate_single_point_requested.emit(temp)
        logger.info(f"Single point calibration triggered at {temp}")

    def _on_calibrate_two_point(self):
        """
        Handle two point calibration.

        Same no-argument signal as above. Both reference temperatures are
        collected here; app.py samples the coldest/hottest points already
        in the current frame, so both references need to be visible in the
        same shot (e.g. ice water and boiling water side by side).
        """
        from PyQt6.QtWidgets import QInputDialog
        t1, ok1 = QInputDialog.getDouble(
            self, "Two-Point Calibration",
            "Cold reference temperature (°C):", 0.0, -40.0, 550.0, 1
        )
        if not ok1:
            return
        t2, ok2 = QInputDialog.getDouble(
            self, "Two-Point Calibration",
            "Hot reference temperature (°C):", 100.0, -40.0, 550.0, 1
        )
        if not ok2:
            return
        if self.event_bus:
            self.event_bus.calibrate_two_point_requested.emit(t1, t2)
        logger.info(f"Two point calibration triggered: {t1}, {t2}")

    def _on_radiometric_temp_unit_changed(self, unit: str):
        logger.info(f"[MAIN_WINDOW] _on_radiometric_temp_unit_changed called with unit: {unit}")
        if hasattr(self, 'video_widget') and hasattr(self.video_widget, 'overlay'):
            self.video_widget.overlay.set_temperature_unit(unit)
        if self.event_bus:
            self.event_bus.temperature_unit_changed.emit(unit)
        elif self.app:
            self.app.set_temperature_unit(unit)
        if hasattr(self, 'isotherm_panel'):
            unit_index_map = {'C': 0, 'F': 1, 'K': 2, 'RAW': 3}
            unit_index = unit_index_map.get(unit, 0)
            self.isotherm_panel.set_temperature_unit(unit_index)

    # === FUSION HANDLERS ===
    def _on_fusion_mode_changed(self, mode: str):
        if self.event_bus:
            self.event_bus.fusion_mode_changed.emit(mode)
        elif self.app:
            self.app.set_fusion_mode(mode)
        # The overlay's coordinate transform needs to know when the Fusion
        # Mode dropdown itself picks a layout-changing algorithm (e.g.
        # 'side_by_side') - this used to only resync on the top-level View
        # Mode button, so choosing that layout from here left the overlay
        # thinking it was still in generic single-frame 'fusion' mode.
        self._sync_overlay_view_mode()
        logger.info(f"Fusion mode changed to: {mode}")

    def _on_fusion_alpha_changed(self, val: float):
        if self.event_bus:
            self.event_bus.fusion_alpha_changed.emit(val)
        elif self.app:
            self.app.set_fusion_alpha(val)

    def _on_fusion_priority_changed(self, val: str):
        priority = val.lower()
        if priority == 'balanced':
            priority = 'thermal'

        if self.event_bus:
            self.event_bus.fusion_priority_changed.emit(priority)
        elif self.app:
            self.app.set_fusion_priority(priority)
        # Sync overlay with new priority
        if hasattr(self, 'video_widget') and hasattr(self.video_widget, 'overlay'):
            current_mode = self.video_widget.overlay.current_view_mode
            self.video_widget.overlay.set_view_mode(current_mode, priority)
        logger.info(f"Fusion priority changed to: {priority}")

    def _on_fusion_strength_changed(self, val: float):
        if self.event_bus:
            self.event_bus.fusion_strength_changed.emit(val)
        elif self.app and hasattr(self.app, 'set_fusion_strength'):
            self.app.set_fusion_strength(val)
        logger.info(f"Fusion strength changed to: {val:.2f}")

    def _on_fusion_fuzziness_changed(self, val: float):
        if self.event_bus:
            self.event_bus.fusion_fuzziness_changed.emit(val)
        elif self.app and hasattr(self.app, 'set_fusion_fuzziness'):
            self.app.set_fusion_fuzziness(val)

    def _on_fusion_color_mode_changed(self, val: str):
        if self.event_bus:
            self.event_bus.fusion_color_mode_changed.emit(val)
        elif self.app and hasattr(self.app, 'set_fusion_color_mode'):
            self.app.set_fusion_color_mode(val)

    def _on_edge_strength_changed(self, val: float):
        if self.event_bus:
            self.event_bus.edge_strength_changed.emit(val)
        elif self.app and hasattr(self.app, 'set_edge_strength'):
            self.app.set_edge_strength(val)

    def _on_edge_fuzziness_changed(self, val: float):
        if self.event_bus:
            self.event_bus.edge_fuzziness_changed.emit(val)
        elif self.app and hasattr(self.app, 'set_edge_fuzziness'):
            self.app.set_edge_fuzziness(val)

    def _on_edge_color_changed(self, val: str):
        if self.event_bus:
            self.event_bus.edge_color_changed.emit(val)
        elif self.app and hasattr(self.app, 'set_edge_color'):
            self.app.set_edge_color(val)

    def _on_detail_strength_changed(self, val: float):
        if self.event_bus:
            self.event_bus.detail_strength_changed.emit(val)
        elif self.app and hasattr(self.app, 'set_detail_strength'):
            self.app.set_detail_strength(val)

    def _on_detail_quality_changed(self, val: str):
        if self.event_bus:
            self.event_bus.detail_quality_changed.emit(val)
        elif self.app and hasattr(self.app, 'set_detail_quality'):
            self.app.set_detail_quality(val)

    def _on_laplacian_gpu_changed(self, val: bool):
        if self.event_bus:
            self.event_bus.laplacian_gpu_changed.emit(val)
        elif self.app and hasattr(self.app, 'set_laplacian_gpu'):
            self.app.set_laplacian_gpu(val)

    def _on_laplacian_cpu_scale_changed(self, val: float):
        if self.event_bus:
            self.event_bus.laplacian_cpu_scale_changed.emit(val)
        elif self.app and hasattr(self.app, 'set_laplacian_cpu_scale'):
            self.app.set_laplacian_cpu_scale(val)

    def _on_3d_relief_strength_changed(self, val: float):
        if self.event_bus:
            self.event_bus.fusion_3d_strength_changed.emit(val)
        elif self.app and hasattr(self.app, 'set_3d_relief_strength'):
            self.app.set_3d_relief_strength(val)

    def _on_3d_mode_changed(self, mode: str):
        if self.event_bus:
            self.event_bus.fusion_3d_mode_changed.emit(mode)
        elif self.app and hasattr(self.app, 'set_3d_mode'):
            self.app.set_3d_mode(mode)

    def _on_3d_data_source_changed(self, source: str):
        if self.event_bus:
            self.event_bus.fusion_3d_data_source_changed.emit(source)
        elif self.app and hasattr(self.app, 'set_3d_data_source'):
            self.app.set_3d_data_source(source)

    def _on_3d_fog_range_changed(self, near_m: float, far_m: float):
        if self.event_bus:
            self.event_bus.fusion_3d_fog_range_changed.emit(near_m, far_m)
        elif self.app and hasattr(self.app, 'set_3d_fog_range'):
            self.app.set_3d_fog_range(near_m, far_m)

    def _on_3d_contour_interval_changed(self, interval_m: float):
        if self.event_bus:
            self.event_bus.fusion_3d_contour_interval_changed.emit(interval_m)
        elif self.app and hasattr(self.app, 'set_3d_contour_interval'):
            self.app.set_3d_contour_interval(interval_m)

    def _on_3d_gradient_style_changed(self, style: str):
        if self.event_bus:
            self.event_bus.fusion_3d_gradient_style_changed.emit(style)
        elif self.app and hasattr(self.app, 'set_3d_gradient_style'):
            self.app.set_3d_gradient_style(style)

    def _on_3d_fog_fade_metric_changed(self, metric: str):
        if self.event_bus:
            self.event_bus.fusion_3d_fog_fade_metric_changed.emit(metric)
        elif self.app and hasattr(self.app, 'set_3d_fog_fade_metric'):
            self.app.set_3d_fog_fade_metric(metric)

    # === ANALYSIS HANDLERS ===
    def _on_global_palette_changed(self, palette_name: str):
        try:
            logger.info(f"Attempting to change palette to: '{palette_name}'")
            if self.event_bus:
                self.event_bus.palette_set.emit(palette_name)
            elif self.app:
                self.app.set_palette(palette_name)
            logger.info(f"Global palette changed successfully: {palette_name}")
        except Exception as e:
            logger.error(f"CRASH in _on_global_palette_changed with palette '{palette_name}': {e}", exc_info=True)
            QMessageBox.critical(self, "Palette Error", f"Failed to change palette to '{palette_name}':\n{e}")

    def _on_roi_palette_changed(self, roi_id: str, palette_name: str):
        if self.app and hasattr(self.app, 'set_roi_palette'):
            self.app.set_roi_palette(roi_id, palette_name)
            logger.info(f"ROI {roi_id} palette set to {palette_name}")

    def _on_roi_palette_cleared(self, roi_id: str):
        if self.app and hasattr(self.app, 'palette_manager'):
            self.app.palette_manager.clear_roi_palette(roi_id)
            if hasattr(self.app, 'roi_manager'):
                roi = self.app.roi_manager.get_roi(roi_id)
                if roi:
                    roi.custom_palette = None
            logger.info(f"ROI {roi_id} palette cleared")

    def _on_overlay_info_toggle(self, enabled: bool):
        if hasattr(self.video_widget, 'overlay'):
            self.video_widget.overlay.set_show_detection_info(enabled)

    # === ENVIRONMENTAL COMP HANDLERS ===
    def _on_emissivity_changed(self, val: float):
        if self.event_bus:
            self.event_bus.emissivity_changed.emit(val)
        elif self.app and hasattr(self.app, 'set_emissivity'):
            self.app.set_emissivity(val)
        logger.info(f"Emissivity changed to: {val:.2f}")

    def _on_atmospheric_temp_changed(self, val: float):
        if self.event_bus:
            self.event_bus.atmospheric_temperature_changed.emit(val)
        elif self.app and hasattr(self.app, 'set_atmospheric_temperature'):
            self.app.set_atmospheric_temperature(val)

    def _on_atmospheric_transmission_changed(self, val: float):
        if self.event_bus:
            self.event_bus.atmospheric_transmission_changed.emit(val)
        elif self.app and hasattr(self.app, 'set_atmospheric_transmission'):
            self.app.set_atmospheric_transmission(val)

    # === ISOTHERM HANDLERS ===
    def _on_isotherm_enabled_changed(self, enabled: bool):
        if self.event_bus:
            self.event_bus.isotherm_enabled_changed.emit(enabled)
        elif self.app:
            self.app.set_isotherm_enabled(enabled)

    def _on_isotherm_mode_changed(self, mode: str):
        if self.event_bus:
            self.event_bus.isotherm_mode_changed.emit(mode)
        elif self.app:
            self.app.set_isotherm_mode(mode)

    def _on_isotherm_low_threshold_changed(self, val: float):
        if self.event_bus:
            self.event_bus.isotherm_low_threshold_changed.emit(val)
        elif self.app:
            self.app.set_isotherm_low_threshold(val)

    def _on_isotherm_high_threshold_changed(self, val: float):
        if self.event_bus:
            self.event_bus.isotherm_high_threshold_changed.emit(val)
        elif self.app:
            self.app.set_isotherm_high_threshold(val)

    def _on_isotherm_color_changed(self, val: str):
        if self.event_bus:
            self.event_bus.isotherm_color_changed.emit(val)
        elif self.app:
            self.app.set_isotherm_color(val)

    def _on_isotherm_bands_changed(self, band_manager):
        if self.event_bus:
            self.event_bus.isotherm_band_manager_set.emit(band_manager)
            if hasattr(self, 'isotherm_panel'):
                is_multiband = self.isotherm_panel.is_multiband_mode()
                self.event_bus.isotherm_multiband_changed.emit(is_multiband)
        elif self.app:
            if hasattr(self.app, 'set_isotherm_band_manager'):
                self.app.set_isotherm_band_manager(band_manager)
            if hasattr(self.app, 'set_isotherm_multiband_mode') and hasattr(self, 'isotherm_panel'):
                self.app.set_isotherm_multiband_mode(self.isotherm_panel.is_multiband_mode())

    # === ROI & VIDEO HANDLERS ===
    def _on_roi_created(self, roi):
        try:
            if self.app and hasattr(self.app, 'roi_manager'):
                self.app.roi_manager.add_roi(roi)
                logger.info(f"ROI created: {roi.label} ({roi.roi_type})")
            if hasattr(self.video_widget, 'overlay'):
                self.video_widget.overlay.disable_drawing_mode()
            if hasattr(self, 'control_panel') and hasattr(self.control_panel, 'draw_roi_btn'):
                self.control_panel.draw_roi_btn.setChecked(False)
        except Exception as e:
            logger.error(f"Error in _on_roi_created: {e}", exc_info=True)

    def _on_roi_selected(self, roi_id):
        logger.info(f"ROI selected: {roi_id}")
        if hasattr(self, 'video_widget') and hasattr(self.video_widget, 'overlay'):
            self.video_widget.overlay.set_selected_roi(roi_id)
        if hasattr(self, 'analysis_panel'):
            self.analysis_panel.select_roi(roi_id)

    def _on_cursor_moved(self, pos):
        """Display temperature at cursor position in the status bar."""
        if not self.app:
            return
        frame = getattr(self.app, '_last_thermal_frame', None)
        if frame is None:
            return
        try:
            x, y = pos.x(), pos.y()
            h, w = frame.shape[:2]
            if 0 <= y < h and 0 <= x < w:
                raw_val = float(frame[y, x])
                # Try radiometric conversion for calibrated temperature
                analyzer = getattr(self.app, 'thermal_analyzer', None)
                if analyzer and hasattr(analyzer, 'calculate_spot_temperature'):
                    temp, unit = analyzer.calculate_spot_temperature(raw_val)
                    if temp is not None:
                        self.statusBar().showMessage(f"Cursor: ({x}, {y})  {temp:.1f}{unit}")
                        return
                self.statusBar().showMessage(f"Cursor: ({x}, {y})  Raw: {raw_val:.0f}")
        except Exception:
            pass  # Don't let cursor tracking errors affect the UI

    def _on_roi_export_data(self):
        """Export ROI temperature data to file."""
        logger.info("ROI export data requested")
        # Open file dialog and export data
        from PyQt6.QtWidgets import QFileDialog
        filepath, _ = QFileDialog.getSaveFileName(
            self, "Export ROI Data", "", "CSV Files (*.csv);;JSON Files (*.json)"
        )
        if filepath:
            if hasattr(self, 'roi_temp_panel'):
                self.roi_temp_panel.export_data(filepath)
                logger.info(f"ROI data exported to: {filepath}")

    def _on_roi_clear_history(self, roi_id: str):
        """Clear temperature history for a specific ROI."""
        logger.info(f"Clear history requested for ROI: {roi_id}")
        if hasattr(self, 'roi_temp_panel'):
            self.roi_temp_panel.clear_roi_history(roi_id)

    # === MODE SYNC HANDLERS ===
    def _on_overlay_spot_meter_mode_changed(self, enabled: bool):
        if hasattr(self, 'analysis_panel') and hasattr(self.analysis_panel, 'spot_meter_btn'):
            self.analysis_panel.spot_meter_btn.blockSignals(True)
            self.analysis_panel.spot_meter_btn.setChecked(enabled)
            self.analysis_panel.spot_meter_btn.blockSignals(False)

    def _on_overlay_drawing_mode_changed(self, enabled: bool):
        if hasattr(self, 'control_panel') and hasattr(self.control_panel, 'draw_roi_btn'):
            self.control_panel.draw_roi_btn.blockSignals(True)
            self.control_panel.draw_roi_btn.setChecked(enabled)
            self.control_panel.draw_roi_btn.blockSignals(False)

    # === BASELINE HANDLER ===
    def _on_baseline_toggle(self, enabled: bool):
        if self.event_bus:
            self.event_bus.baseline_lock_toggled.emit(enabled)
        elif self.app and hasattr(self.app, 'lock_baseline'):
            self.app.lock_baseline(enabled)
        logger.info(f"Baseline lock: {'ON' if enabled else 'OFF'}")

    # === CONTROL PANEL HANDLERS ===
    def _on_palette_cycle(self):
        if self.event_bus:
            self.event_bus.palette_cycled.emit()
        elif self.app:
            self.app.cycle_palette()
        logger.info("Palette cycle")

    def _on_view_mode_cycle(self):
        if self.event_bus:
            self.event_bus.view_mode_cycled.emit()
        elif self.app:
            self.app.cycle_view_mode()
        # cycle_view_mode() above runs synchronously (updates self.app.view_mode
        # directly, no async signal round-trip), so the new mode is already
        # readable here - sync the button label and viewport immediately
        # rather than only on the app's own auto-fallback switches.
        self._sync_view_mode_button()
        logger.info("View mode cycle")

    def _sync_view_mode_button(self, view_mode=None):
        """
        Update the View Mode button label to reflect the current mode.
        Called when the app auto-switches view mode (e.g. no thermal camera
        found) and after a manual view-mode cycle click.
        """
        try:
            from thermal_inspection.core import ViewMode
            if view_mode is None and self.app:
                view_mode = getattr(self.app, 'view_mode', None)
            if view_mode is None:
                return
            label_map = {
                ViewMode.THERMAL_ONLY: "Thermal",
                ViewMode.RGB_ONLY: "RGB",
                ViewMode.FUSION: "Fusion",
                ViewMode.SIDE_BY_SIDE: "Side by Side",
                ViewMode.PICTURE_IN_PICTURE: "PiP",
                ViewMode.THREE_D: "3D",
            }
            label = label_map.get(view_mode, str(view_mode))
            # NOTE: the button is named view_mode_btn, not view_btn - a
            # prior mismatched attribute name here meant this method never
            # actually updated the button text at all, on any view mode
            # change, manual or automatic.
            if hasattr(self, 'control_panel') and hasattr(self.control_panel, 'view_mode_btn'):
                self.control_panel.view_mode_btn.setText(f"\U0001F441 {label}")

            self._sync_overlay_view_mode()
            logger.info(f"View mode button synced to: {label}")
        except Exception as e:
            logger.debug(f"_sync_view_mode_button failed: {e}")

    def _sync_overlay_view_mode(self):
        """Sync overlay widget's view mode with current app state."""
        if not self.app or not hasattr(self, 'video_widget'):
            return
        if not hasattr(self.video_widget, 'overlay'):
            return

        # Get current view mode from app
        view_mode = getattr(self.app, 'view_mode', None)
        if view_mode is None:
            return

        # Map ViewMode enum to overlay mode string
        from thermal_inspection.core import ViewMode
        mode_map = {
            ViewMode.THERMAL_ONLY: 'thermal',
            ViewMode.RGB_ONLY: 'rgb',
            ViewMode.FUSION: 'fusion',
            ViewMode.SIDE_BY_SIDE: 'side_by_side',
            ViewMode.PICTURE_IN_PICTURE: 'picture_in_picture',
        }
        mode_str = mode_map.get(view_mode, 'thermal')

        # Get fusion priority from fusion processor
        fusion_priority = 'thermal'  # Default
        if hasattr(self.app, 'fusion_processor') and self.app.fusion_processor:
            fusion_priority = getattr(self.app.fusion_processor, 'fusion_priority', 'thermal')

        # ViewMode.FUSION collapses every FusionProcessor.fusion_mode choice
        # to the single generic string 'fusion', but the overlay's
        # coordinate transform has dedicated layout-aware handling only for
        # specific mode strings like 'side_by_side' - selecting that
        # algorithm from the Fusion Mode dropdown (as opposed to the
        # top-level View Mode button) never reached that branch, so
        # coordinates meant to stay within the thermal half were instead
        # scaled across the entire combined frame's width. Surface the
        # actual algorithm the overlay needs to know about.
        if view_mode == ViewMode.FUSION and self.app.fusion_processor:
            inner_mode = getattr(self.app.fusion_processor, 'fusion_mode', None)
            if inner_mode == 'side_by_side':
                mode_str = 'side_by_side'

        # Update overlay
        self.video_widget.overlay.set_view_mode(mode_str, fusion_priority)
        logger.debug(f"Overlay synced: mode={mode_str}, priority={fusion_priority}")

    def _on_record_toggle(self, enabled: bool):
        self.recording = enabled
        self.control_panel.update_record_button(enabled)
        if self.event_bus:
            self.event_bus.recording_toggled.emit(enabled)
        elif self.app:
            self.app.toggle_recording(enabled)
        logger.info(f"Recording: {'ON' if enabled else 'OFF'}")

    def _on_snapshot(self):
        if self.event_bus:
            self.event_bus.snapshot_requested.emit()
        elif self.app:
            self.app.capture_snapshot()
        logger.info("Snapshot captured")

    def _on_freeze_toggle(self, enabled: bool):
        self.frozen = enabled
        self.control_panel.update_freeze_button(enabled)
        if self.event_bus:
            self.event_bus.freeze_toggled.emit(enabled)
        elif self.app:
            self.app.toggle_freeze(enabled)
        logger.info(f"Frame freeze: {'ON' if enabled else 'OFF'}")

    def _on_auto_roi(self):
        if self.event_bus:
            self.event_bus.auto_roi_requested.emit()
        elif self.app and hasattr(self.app, 'auto_roi_detect'):
            self.app.auto_roi_detect()
        logger.info("Auto ROI detection triggered")

    def _on_draw_roi(self):
        if self.video_widget and hasattr(self.video_widget, 'overlay'):
            self.video_widget.overlay.enable_drawing_mode(ROIType.RECTANGLE)
            logger.info("Draw ROI mode activated (rectangle)")
            self.control_panel.draw_roi_btn.setChecked(True)

    def _on_clear_rois(self):
        if self.event_bus:
            self.event_bus.clear_rois_requested.emit()
        elif self.app:
            self.app.clear_rois()
        logger.info("ROIs cleared")

    def _on_camera_clicked(self):
        if not self.app:
            return
        try:
            dialog = CameraManagerDialog(self.app, self)
            dialog.exec()
        except Exception as e:
            logger.error(f"Camera manager dialog error: {e}", exc_info=True)
            QMessageBox.critical(self, "Error", f"Failed to open camera manager: {e}")

    def _on_device_changed(self, device_name: str):
        if self.event_bus:
            self.event_bus.device_changed.emit(device_name)
        elif self.app and hasattr(self.app, 'set_device'):
            self.app.set_device(device_name)
        logger.info(f"Device changed to: {device_name}")

    def _on_roi_delete(self, roi_id: str):
        if self.event_bus:
            self.event_bus.roi_deleted.emit(roi_id)
        elif self.app:
            if hasattr(self.app, 'delete_roi'):
                self.app.delete_roi(roi_id)
            elif hasattr(self.app, 'roi_manager'):
                self.app.roi_manager.delete_roi(roi_id)
        logger.info(f"ROI {roi_id} deleted")

    # === SPOT METER HANDLERS ===
    def _on_spot_meter_toggled(self, checked: bool):
        if hasattr(self, 'video_widget'):
            self.video_widget.set_add_point_mode(checked)
            msg = "Spot meter mode: ON (Click on video to measure)" if checked else "Spot meter mode: OFF"
            self.statusBar().showMessage(msg, 3000)
            logger.info(msg)

    def _on_clear_spots_clicked(self):
        logger.info("Main Window: _on_clear_spots_clicked called")
        self.measurement_points.clear()
        if hasattr(self, 'video_widget'):
            self.video_widget.update_measurement_points(self.measurement_points)
        if hasattr(self, 'analysis_panel') and hasattr(self.analysis_panel, 'spot_meter_panel'):
            self.analysis_panel.spot_meter_panel.clear()
        logger.info("Cleared all spot meters from both overlay and panel")

    def _on_cursor_readout_toggled(self, checked: bool):
        logger.info(f"Cursor temperature readout toggled: {checked}")
        if hasattr(self, 'video_widget') and hasattr(self.video_widget, 'overlay'):
            self.video_widget.overlay.set_cursor_enabled(checked)
            msg = "Cursor readout: ON (Move mouse over thermal)" if checked else "Cursor readout: OFF"
            self.statusBar().showMessage(msg, 3000)

    def _on_comparison_changed(self, spot1_id: str, spot2_id: str, delta: float):
        if hasattr(self, 'video_widget') and hasattr(self.video_widget, 'overlay'):
            self.video_widget.overlay.set_comparison(spot1_id, spot2_id, delta)

    def _on_grid_enabled(self, enabled: bool):
        logger.info(f"Grid overlay enabled: {enabled}")
        if hasattr(self, 'video_widget') and hasattr(self.video_widget, 'overlay'):
            self.video_widget.overlay.set_grid_enabled(enabled)
            msg = "Grid overlay: ON" if enabled else "Grid overlay: OFF"
            self.statusBar().showMessage(msg, 3000)

    def _on_grid_spacing_changed(self, x: int, y: int):
        if hasattr(self, 'video_widget') and hasattr(self.video_widget, 'overlay'):
            self.video_widget.overlay.set_grid_spacing(x, y)

    def _on_grid_color_changed(self, color: QColor):
        if hasattr(self, 'video_widget') and hasattr(self.video_widget, 'overlay'):
            self.video_widget.overlay.set_grid_color(color)

    def _on_spot_deleted(self, spot_id: str):
        logger.info(f"Main Window: _on_spot_deleted for {spot_id}")
        if hasattr(self, 'analysis_panel') and hasattr(self.analysis_panel, 'spot_meter_panel'):
            spot_data = self.analysis_panel.spot_meter_panel.get_spot(spot_id)
            if spot_data:
                self.measurement_points = [
                    p for p in self.measurement_points
                    if p.label != spot_data.label
                ]
                if hasattr(self, 'video_widget'):
                    self.video_widget.update_measurement_points(self.measurement_points)

    def _on_spot_renamed(self, spot_id: str, new_name: str):
        logger.info(f"Main Window: _on_spot_renamed {spot_id} -> {new_name}")
        if hasattr(self, 'analysis_panel') and hasattr(self.analysis_panel, 'spot_meter_panel'):
            spot_data = self.analysis_panel.spot_meter_panel.get_spot(spot_id)
            if spot_data:
                for point in self.measurement_points:
                    if point.x == spot_data.x and point.y == spot_data.y:
                        point.label = new_name
                        break
                if hasattr(self, 'video_widget'):
                    self.video_widget.update_measurement_points(self.measurement_points)

    def _on_highlight_spot(self, spot_id: str):
        logger.debug(f"Highlight spot: {spot_id}")

    def get_spot_meter_coords(self) -> List[Tuple[int, int, str]]:
        return [(p.x, p.y, p.label) for p in self.measurement_points]

    def _on_spot_meter_clicked(self, x: int, y: int):
        logger.info(f"Main Window: _on_spot_meter_clicked at ({x}, {y})")

        # Route to calibration point-add handler if that mode is active
        if getattr(self.app, 'calibration_add_point_mode', False) or \
                (self.app and getattr(self.app, 'calibration_manager', None) and
                 getattr(self.app.calibration_manager, 'add_point_mode', False)):
            logger.info(f"Routing click to calibration point-add at ({x}, {y})")
            # NOTE: this used to re-emit calibration_add_point_mode_changed
            # (enabled=True, ref_temp=0) here instead of actually requesting
            # a point be added at (x, y) - that signal only ever toggles the
            # add-point-mode flag (already True) and carries no coordinates
            # at all, so every click while "Add Point" mode was on silently
            # did nothing. calibration_point_add_requested actually carries
            # the clicked position through to add_calibration_point().
            if self.event_bus:
                self.event_bus.calibration_point_add_requested.emit(x, y)
            elif self.app and hasattr(self.app, 'add_calibration_point'):
                self.app.add_calibration_point(x, y)
            elif self.app and hasattr(self.app, '_on_add_calibration_point'):
                self.app._on_add_calibration_point(x, y)
            return

        for existing in self.measurement_points:
            if existing.x == x and existing.y == y:
                logger.debug(f"Spot at ({x}, {y}) already exists, skipping duplicate")
                return

        idx = len(self.measurement_points) + 1
        label = f"SP{idx}"
        spot_id = f"spot_{idx}_{x}_{y}"

        point = MeasurementPoint(x=x, y=y, label=label)
        self.measurement_points.append(point)

        if hasattr(self, 'analysis_panel') and hasattr(self.analysis_panel, 'spot_meter_panel'):
            self.analysis_panel.spot_meter_panel.add_spot(spot_id, x, y, label)

        if hasattr(self, 'video_widget'):
            self.video_widget.update_measurement_points(self.measurement_points)

        logger.info(f"Added spot meter {label} at ({x}, {y}). Total spots: {len(self.measurement_points)}")

    def update_spot_meter_values(self, values: List[Dict]):
        updated = False
        val_map = {v['label']: v for v in values}

        for point in self.measurement_points:
            if point.label in val_map:
                data = val_map[point.label]
                point.temperature = data['temperature']
                point.unit = data['unit']
                updated = True

        if updated:
            if hasattr(self, 'video_widget'):
                self.video_widget.update_measurement_points(self.measurement_points)
            if hasattr(self, 'analysis_panel') and hasattr(self.analysis_panel, 'spot_meter_panel'):
                self.analysis_panel.spot_meter_panel.update_spot_temperatures(values)

    def _on_spot_preset_requested(self, preset_name: str):
        if not hasattr(self.analysis_panel, 'spot_meter_panel'):
            return

        w, h = 640, 512

        if hasattr(self, 'video_widget') and hasattr(self.video_widget, 'overlay'):
            if self.video_widget.overlay.thermal_resolution:
                w, h = self.video_widget.overlay.thermal_resolution
            elif hasattr(self.video_widget, '_frame_width') and self.video_widget._frame_width > 0:
                w = self.video_widget._frame_width
                h = self.video_widget._frame_height

        coords = SpotMeterPresets.generate(preset_name, w, h)

        self.analysis_panel.spot_meter_panel.clear()
        self.measurement_points.clear()

        import time
        for i, (x, y) in enumerate(coords):
            spot_id = f"spot_{int(time.time()*1000)}_{i}"
            label = f"SP{i+1}"

            self.analysis_panel.spot_meter_panel.add_spot(spot_id, x, y, label)

            point = MeasurementPoint(x=x, y=y, label=label)
            self.measurement_points.append(point)

        if hasattr(self, 'video_widget'):
            self.video_widget.update_measurement_points(self.measurement_points)

        logger.info(f"Applied preset: {preset_name} ({len(coords)} spots)")

    def _on_spot_alert_triggered(self, spot_id: str, type_: str, val: float):
        if hasattr(self.analysis_panel, 'spot_meter_panel'):
            spot = self.analysis_panel.spot_meter_panel.get_spot(spot_id)
            label = spot.label if spot else spot_id
            msg = f"ALERT: {label} is {type_} threshold ({val:.1f})"
            if hasattr(self, 'statusBar'):
                self.statusBar().showMessage(msg, 3000)

    def _on_spot_visibility_changed(self, spot_id: str, visible: bool):
        """Handle spot visibility toggle."""
        logger.info(f"Spot {spot_id} visibility: {visible}")
        # Update overlay if available
        if hasattr(self, 'video_widget') and hasattr(self.video_widget, 'overlay'):
            self.video_widget.overlay.set_spot_visibility(spot_id, visible)

    def _on_spot_locked_changed(self, spot_id: str, locked: bool):
        """Handle spot locked toggle."""
        logger.info(f"Spot {spot_id} locked: {locked}")
        # Locked spots cannot be moved/deleted
        if hasattr(self, 'video_widget') and hasattr(self.video_widget, 'overlay'):
            self.video_widget.overlay.set_spot_locked(spot_id, locked)

    def _on_clear_all_spots(self):
        """Clear all spot meters."""
        logger.info("Clear all spots requested")
        self.measurement_points.clear()
        if hasattr(self, 'video_widget') and hasattr(self.video_widget, 'overlay'):
            # overlay.clear_spots() never existed - the overlay's own spot
            # list is only ever set via update_measurement_points().
            self.video_widget.overlay.update_measurement_points([])
            self.video_widget.overlay.update()
        if hasattr(self.analysis_panel, 'spot_meter_panel'):
            self.analysis_panel.spot_meter_panel.clear()

    def _on_spot_export_requested(self, format_type: str):
        """Export spot temperature data."""
        logger.info(f"Spot export requested: {format_type}")
        from PyQt6.QtWidgets import QFileDialog
        ext_map = {'csv': 'CSV Files (*.csv)', 'json': 'JSON Files (*.json)'}
        filter_str = ext_map.get(format_type, 'All Files (*.*)')
        filepath, _ = QFileDialog.getSaveFileName(self, "Export Spots", "", filter_str)
        if filepath:
            if hasattr(self.analysis_panel, 'spot_meter_panel'):
                self.analysis_panel.spot_meter_panel.export_spots(filepath, format_type)
                logger.info(f"Spots exported to: {filepath}")

    # === ANOMALY HANDLERS ===
    def _on_anomaly_priority_toggle(self, enabled: bool):
        if self.event_bus:
            self.event_bus.anomaly_priority_toggled.emit(enabled)
        elif self.app:
            self.app.toggle_anomaly_priority(enabled)
        logger.info(f"Anomaly priority: {'ON' if enabled else 'OFF'}")

    def _on_anomaly_types_changed(self, types_dict: dict):
        if self.event_bus:
            self.event_bus.anomaly_types_changed.emit(types_dict)
        elif self.app:
            self.app.set_enabled_anomaly_types(types_dict)
        logger.info(f"Anomaly types changed: {types_dict}")

    def _on_fade_strength_changed(self, value: float):
        if self.event_bus:
            self.event_bus.anomaly_fade_strength_changed.emit(value)
        elif self.app and hasattr(self.app, 'thermal_processor'):
            self.app.thermal_processor.anomaly_fade_strength = value

    def _on_fade_distance_changed(self, value: int):
        if self.event_bus:
            self.event_bus.anomaly_fade_distance_changed.emit(float(value))
        elif self.app and hasattr(self.app, 'thermal_processor'):
            self.app.thermal_processor.anomaly_max_distance = value

    def _on_motion_threshold_changed(self, value: int):
        if self.event_bus:
            self.event_bus.anomaly_motion_threshold_changed.emit(float(value))
        elif self.app and hasattr(self.app, 'thermal_processor'):
            self.app.thermal_processor.motion_threshold = value

    def _on_edge_thresholds_changed(self, low: int, high: int):
        if self.event_bus:
            self.event_bus.anomaly_edge_thresholds_changed.emit(float(low), float(high))
        elif self.app and hasattr(self.app, 'thermal_processor'):
            self.app.thermal_processor.edge_threshold_low = low
            self.app.thermal_processor.edge_threshold_high = high

    def _on_hot_spot_percentile_changed(self, value: int):
        if self.event_bus:
            self.event_bus.hot_spot_percentile_changed.emit(float(value))
        elif self.app and hasattr(self.app, 'thermal_analyzer'):
            self.app.thermal_analyzer.hot_spot_percentile = value

    def _on_cold_spot_percentile_changed(self, value: int):
        if self.event_bus:
            self.event_bus.cold_spot_percentile_changed.emit(float(value))
        elif self.app and hasattr(self.app, 'thermal_analyzer'):
            self.app.thermal_analyzer.cold_spot_percentile = value

    def _on_min_anomaly_size_changed(self, value: int):
        if self.event_bus:
            self.event_bus.min_anomaly_size_changed.emit(float(value))
        elif self.app and hasattr(self.app, 'thermal_analyzer'):
            self.app.thermal_analyzer.min_anomaly_size = value

    def _on_manual_threshold_enabled(self, enabled: bool):
        if self.event_bus:
            self.event_bus.threshold_enabled_changed.emit(enabled)
        elif self.app:
            self.app.set_manual_threshold_enabled(enabled)

    def _on_manual_threshold_mode_changed(self, mode: str):
        if self.event_bus:
            self.event_bus.threshold_mode_changed.emit(mode)
        elif self.app:
            self.app.set_manual_threshold_mode(mode)

    def _on_manual_min_threshold_changed(self, value: float):
        if self.event_bus:
            self.event_bus.threshold_min_changed.emit(value)
        elif self.app:
            self.app.set_manual_min_threshold(value)

    def _on_manual_max_threshold_changed(self, value: float):
        if self.event_bus:
            self.event_bus.threshold_max_changed.emit(value)
        elif self.app:
            self.app.set_manual_max_threshold(value)

    def _on_manual_use_raw_changed(self, use_raw: bool):
        if self.event_bus:
            self.event_bus.threshold_use_raw_changed.emit(use_raw)
        elif self.app:
            self.app.set_manual_use_raw_values(use_raw)

    def _on_manual_viz_mode_changed(self, mode: str):
        if self.event_bus:
            self.event_bus.threshold_viz_changed.emit(mode)
        elif self.app:
            self.app.set_manual_viz_mode(mode)

    # (Camera-specific control events are handled by _wire_plugin_panel and generic command dispatch)

    # === CALIBRATION HANDLERS ===
    def _on_calibration_add_point_mode(self, enabled: bool, reference_temp: float):
        # Tell the video overlay to route clicks here regardless of Spot
        # Meter mode - the overlay's click-to-frame-coordinate mapping only
        # ever ran when spot_meter_mode was on, so without this a click
        # while only "Add Point" was checked emitted no signal at all.
        if hasattr(self, 'video_widget') and hasattr(self.video_widget, 'overlay'):
            self.video_widget.overlay.set_calibration_add_point_mode(enabled)

        if self.event_bus:
            self.event_bus.calibration_add_point_mode_changed.emit(enabled, reference_temp)
        elif self.app and hasattr(self.app, 'set_calibration_add_point_mode'):
            self.app.set_calibration_add_point_mode(enabled, reference_temp)

    def _on_compute_calibration(self, method: str, degree: int):
        if self.event_bus:
            self.event_bus.calibration_compute_requested.emit(method, degree)
        elif self.app and hasattr(self.app, 'compute_calibration'):
            if self.app.compute_calibration(method, degree):
                logger.info(f"Calibration computed using {method} method")
                self.event_bus.calibration_gui_update_requested.emit() if self.event_bus else (
                    self.app.update_calibration_gui() if hasattr(self.app, 'update_calibration_gui') else None
                )
            else:
                QMessageBox.warning(self, "Calibration Error",
                                   "Failed to compute calibration. Need at least 2 points for linear, more for polynomial.")

    def _on_apply_calibration_toggled(self, enabled: bool):
        if self.event_bus:
            self.event_bus.calibration_enabled_changed.emit(enabled)
        elif self.app and hasattr(self.app, 'set_calibration_enabled'):
            self.app.set_calibration_enabled(enabled)

    def _on_clear_calibration(self):
        if self.event_bus:
            self.event_bus.calibration_clear_requested.emit()
        elif self.app and hasattr(self.app, 'clear_calibration'):
            self.app.clear_calibration()
            self.event_bus.calibration_gui_update_requested.emit() if self.event_bus else (
                self.app.update_calibration_gui() if hasattr(self.app, 'update_calibration_gui') else None
            )

    def _on_export_calibration(self):
        from datetime import datetime
        default_name = f"calibration_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export Calibration", default_name, "JSON Files (*.json);;All Files (*.*)"
        )
        if file_path:
            if self.event_bus:
                self.event_bus.calibration_export_requested.emit(file_path)
            elif self.app and hasattr(self.app, 'export_calibration'):
                if self.app.export_calibration(file_path):
                    QMessageBox.information(self, "Export Successful", f"Calibration exported to:\n{file_path}")
                else:
                    QMessageBox.critical(self, "Export Failed", "Failed to export calibration")

    def _on_import_calibration(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Import Calibration", "", "JSON Files (*.json);;All Files (*.*)"
        )
        if file_path:
            if self.event_bus:
                self.event_bus.calibration_import_requested.emit(file_path)
            elif self.app and hasattr(self.app, 'import_calibration'):
                if self.app.import_calibration(file_path):
                    QMessageBox.information(self, "Import Successful", f"Calibration imported from:\n{file_path}")
                    if hasattr(self.app, 'update_calibration_gui'):
                        self.app.update_calibration_gui()
                else:
                    QMessageBox.critical(self, "Import Failed", "Failed to import calibration")

    def _on_remove_calibration_point(self, index: int):
        if self.event_bus:
            self.event_bus.calibration_point_removed.emit(index)
        elif self.app and hasattr(self.app, 'remove_calibration_point'):
            if self.app.remove_calibration_point(index):
                self.event_bus.calibration_gui_update_requested.emit() if self.event_bus else (
                    self.app.update_calibration_gui() if hasattr(self.app, 'update_calibration_gui') else None
                )

    # === PARALLAX HANDLERS ===
    def _on_parallax_toggled(self, enabled: bool):
        if self.event_bus:
            self.event_bus.parallax_toggled.emit(enabled)
        elif self.app and hasattr(self.app, 'enable_parallax_compensation'):
            self.app.enable_parallax_compensation(enabled)

    def _on_parallax_baseline_changed(self, baseline_mm: float):
        if self.event_bus:
            self.event_bus.parallax_baseline_changed.emit(baseline_mm)
        elif self.app and hasattr(self.app, 'set_parallax_baseline'):
            self.app.set_parallax_baseline(baseline_mm)

    def _on_parallax_method_changed(self, method: str):
        if self.event_bus:
            self.event_bus.parallax_method_changed.emit(method)
        elif self.app and hasattr(self.app, 'set_parallax_depth_method'):
            self.app.set_parallax_depth_method(method)

    def _on_parallax_geometry_apply(self):
        baseline = self.parallax_panel.get_baseline()
        optics = self.parallax_panel.get_camera_optics()
        if self.event_bus:
            self.event_bus.parallax_baseline_changed.emit(baseline)
            self.event_bus.parallax_geometry_optics_changed.emit(optics)
        elif self.app and hasattr(self.app, 'set_parallax_baseline'):
            self.app.set_parallax_baseline(baseline)
            if hasattr(self.app, 'set_parallax_camera_optics'):
                self.app.set_parallax_camera_optics(optics)

    def _on_parallax_zoom_changed(self, zoom_factor: float):
        """Handle manual zoom/crop-factor spinbox change."""
        if self.event_bus:
            self.event_bus.parallax_zoom_changed.emit(zoom_factor)
        elif self.app and hasattr(self.app, 'set_parallax_zoom'):
            self.app.set_parallax_zoom(zoom_factor)

    def _on_parallax_correction_target_changed(self, target: str):
        """Handle Correction Target combo change."""
        if self.event_bus:
            self.event_bus.parallax_correction_target_changed.emit(target)
        elif self.app and hasattr(self.app, 'set_parallax_correction_target'):
            self.app.set_parallax_correction_target(target)

    def _on_parallax_rgb_target_max_width_changed(self, width):
        """Handle RGB Working Width spinbox / No-cap checkbox change."""
        if self.event_bus:
            self.event_bus.parallax_rgb_target_max_width_changed.emit(width)
        elif self.app and hasattr(self.app, 'set_parallax_rgb_target_max_width'):
            self.app.set_parallax_rgb_target_max_width(width)

    def _on_show_depth_map_toggled(self, show: bool):
        """Show/hide depth map overlay on the video stream."""
        logger.info(f"Depth map overlay: {'ON' if show else 'OFF'}")
        if self.event_bus:
            self.event_bus.depth_map_display_toggled.emit(show)
        elif self.app and hasattr(self.app, 'parallax_compensator'):
            pc = self.app.parallax_compensator
            if hasattr(pc, 'set_depth_display'):
                pc.set_depth_display(show)

    def _on_show_displacement_toggled(self, show: bool):
        """Show/hide the sparse displacement-vector arrow overlay on the video stream."""
        logger.info(f"Displacement-vector overlay: {'ON' if show else 'OFF'}")
        if self.event_bus:
            self.event_bus.displacement_display_toggled.emit(show)
        elif self.app and hasattr(self.app, 'parallax_compensator'):
            pc = self.app.parallax_compensator
            if hasattr(pc, 'set_displacement_display'):
                pc.set_displacement_display(show)

    def _on_parallax_shift_changed(self, dx: int, dy: int):
        """Handle manual alignment shift change (fixed mounting-offset correction)."""
        if self.event_bus:
            self.event_bus.parallax_shift_changed.emit(dx, dy)
        elif self.app and hasattr(self.app, 'set_parallax_shift'):
            self.app.set_parallax_shift(dx, dy)

    def _on_parallax_auto_alignment_requested(self, working_distance_m: float, refine_with_depth: bool):
        """Request a one-time auto-alignment calculation from camera geometry."""
        if self.event_bus:
            self.event_bus.parallax_auto_alignment_requested.emit(working_distance_m, refine_with_depth)

    def _on_bus_parallax_auto_alignment_result(self, dx: int, dy: int, fov_zoom_factor: float):
        """Reflect a completed auto-alignment calculation in the panel."""
        if hasattr(self, 'parallax_panel'):
            self.parallax_panel.set_auto_alignment_result(dx, dy, fov_zoom_factor)

    # ========================================================================
    # Gradient Overlay Handlers
    # ========================================================================

    def _on_gradient_enabled(self, enabled: bool):
        logger.info(f"Gradient overlay: {'ON' if enabled else 'OFF'}")
        if self.event_bus:
            self.event_bus.gradient_enabled_changed.emit(enabled)
        self._apply_gradient_setting(enabled=enabled)

    def _on_gradient_mode_changed(self, mode: str):
        logger.debug(f"Gradient mode: {mode}")
        if self.event_bus:
            self.event_bus.gradient_mode_changed.emit(mode)
        self._apply_gradient_setting(mode=mode)

    def _on_gradient_threshold_changed(self, value: float):
        logger.debug(f"Gradient threshold: {value}")
        if self.event_bus:
            self.event_bus.gradient_threshold_changed.emit(value)
        self._apply_gradient_setting(threshold=value)

    def _on_gradient_colormap_changed(self, colormap: str):
        logger.debug(f"Gradient colormap: {colormap}")
        if self.event_bus:
            self.event_bus.gradient_colormap_changed.emit(colormap)
        self._apply_gradient_setting(colormap=colormap)

    def _apply_gradient_setting(self, **kwargs):
        """Forward gradient settings to the app's GradientProcessor if available."""
        if self.app and hasattr(self.app, 'gradient_processor'):
            self.app.gradient_processor.update_settings(**kwargs)

    # ========================================================================
    # Line Profile Handlers
    # ========================================================================

    def _on_line_profile_mode_toggled(self, enabled: bool):
        """Enable/disable interactive line-drawing mode on the video canvas."""
        logger.info(f"Line profile draw mode: {'ON' if enabled else 'OFF'}")
        if self.event_bus:
            self.event_bus.line_profile_mode_toggled.emit(enabled)
        if hasattr(self, 'video_widget') and hasattr(self.video_widget, 'set_line_profile_mode'):
            self.video_widget.set_line_profile_mode(enabled)

    def _on_line_profile_deleted(self, line_id: str):
        """Remove the line overlay from the video canvas."""
        logger.info(f"Line profile deleted: {line_id}")
        if self.event_bus:
            self.event_bus.line_profile_deleted.emit(line_id)
        if hasattr(self, 'video_widget') and hasattr(self.video_widget, 'remove_line_profile'):
            self.video_widget.remove_line_profile(line_id)

    def _on_line_profile_clear_all(self):
        """Clear all line overlays from the video canvas."""
        logger.info("Line profiles: clear all")
        if hasattr(self, 'video_widget') and hasattr(self.video_widget, 'clear_line_profiles'):
            self.video_widget.clear_line_profiles()
        if hasattr(self, 'line_profile_panel'):
            self.line_profile_panel.clear_all_lines()

    def _on_line_profile_export(self, line_id: str):
        """Export a single line profile to CSV via file dialog."""
        logger.info(f"Line profile export requested: {line_id}")
        from PyQt6.QtWidgets import QFileDialog
        filepath, _ = QFileDialog.getSaveFileName(
            self, "Export Line Profile", f"line_profile_{line_id}.csv",
            "CSV Files (*.csv);;All Files (*.*)"
        )
        if filepath and hasattr(self, 'line_profile_panel'):
            self.line_profile_panel.export_line(line_id, filepath)

    # ========================================================================
    # Spot Selection Handler
    # ========================================================================

    def _on_spot_selected(self, spot_id: str):
        """Highlight the selected spot on the video overlay."""
        logger.debug(f"Spot selected: {spot_id}")
        if self.event_bus:
            self.event_bus.spot_selected.emit(spot_id)
        # Focus/flash the overlay marker for this spot
        if hasattr(self, 'video_widget') and hasattr(self.video_widget, 'overlay'):
            overlay = self.video_widget.overlay
            if hasattr(overlay, 'set_selected_spot'):
                overlay.set_selected_spot(spot_id)
        # Also update the highlight via the existing highlight_spot handler
        self._on_highlight_spot(spot_id)

    # ========================================================================
    # Public Update Methods (called from app)
    # ========================================================================

    def update_frame(self, frame: np.ndarray):
        """Update video display."""
        self.video_widget.update_frame(frame)

    def update_thermal_resolution(self, width: int, height: int):
        """
        Sync the overlay's thermal-sensor resolution with the actual camera.

        ROI, hot/cold spot, and spot-meter coordinates are all expressed in
        thermal sensor pixel space, so every overlay transform (including PIP
        and side-by-side sub-region placement) depends on this matching the
        real camera — not the 640x512 the overlay is built with — or markers
        drift on any camera with a different native resolution or aspect
        ratio (Tau2, Lepton, a Boson in its 320x256 mode, etc.).
        """
        if width <= 0 or height <= 0:
            return
        if hasattr(self, 'video_widget') and hasattr(self.video_widget, 'overlay'):
            self.video_widget.overlay.set_thermal_resolution(width, height)

    def update_metrics(self, fps: float, roi_count: int, thermal_connected: bool, rgb_connected: bool):
        """Update info panel metrics."""
        self.info_panel.update_info(fps, roi_count, thermal_connected, rgb_connected, self.recording)

    def update_rois(self, rois: List[ROI]):
        """Update ROI visualization and list."""
        self.video_widget.update_rois(rois)
        self.analysis_panel.update_rois(rois)
        if hasattr(self, 'roi_temp_panel'):
            self.roi_temp_panel.update_rois(rois)

    def set_fusion_3d_hardware_available(self, available: bool):
        """Record whether a RealSense camera is active, for the 3D Fusion settings tab's status/preview."""
        self._fusion_3d_hw_available = available
        self._sync_fusion_3d_status()

    def set_fusion_3d_thermal_aligned(self, aligned: bool):
        """Record whether thermal is aligned to RealSense, for the 3D Fusion settings tab's status/preview."""
        self._fusion_3d_aligned = aligned
        self._sync_fusion_3d_status()

    def _sync_fusion_3d_status(self):
        if hasattr(self, 'fusion_3d_panel'):
            self.fusion_3d_panel.set_status(
                getattr(self, '_fusion_3d_hw_available', False),
                getattr(self, '_fusion_3d_aligned', False),
            )

    def update_fusion_3d_view(self, vertices, uv, rgb_frame, thermal_colorized):
        """Push a new point cloud to the 3D Fusion settings tab's preview."""
        if hasattr(self, 'fusion_3d_panel'):
            self.fusion_3d_panel.point_cloud_view.update_from_realsense(vertices, uv, rgb_frame, thermal_colorized)

    def update_roi_stats(self, roi_stats: dict):
        """Push per-ROI temperature statistics (roi_id -> stats dict) to the ROI Manager panel."""
        if hasattr(self, 'roi_temp_panel'):
            self.roi_temp_panel.update_roi_data(roi_stats)

    def _update_parallax_performance(self, depth_time_ms: float, correction_time_ms: float):
        """Push parallax correction timing to the Parallax panel's Performance section."""
        if hasattr(self, 'parallax_panel'):
            self.parallax_panel.set_performance_metrics(depth_time_ms, correction_time_ms)

    def _update_anomaly_performance(self, analysis_time_ms: float, submit_interval_ms: float):
        """
        Push the background analyzer's real timing to the Anomaly panel's
        Performance section (built but never populated before this).
        "Overhead" here means the analyzer's own processing time as a
        percentage of its throttled submission interval - over 100% means
        it can't keep up with the rate frames are being submitted at, not
        that it's competing with the render thread (it runs on its own
        background thread specifically so it doesn't block that).
        """
        if not hasattr(self, 'anomaly_widget'):
            return
        fps = 1000.0 / analysis_time_ms if analysis_time_ms > 0 else 0.0
        overhead_pct = (analysis_time_ms / submit_interval_ms) * 100.0 if submit_interval_ms > 0 else 0.0
        self.anomaly_widget.update_performance(fps, analysis_time_ms, overhead_pct)

    def update_thermal_analysis(self, stats: Optional[ThermalStatistics],
                                hot_spots: List[HotSpot],
                                cold_spots: List[ColdSpot],
                                anomalies: List[ThermalAnomaly],
                                enhanced_fusion_anomalies: List = None,
                                motion_detections: List = None,
                                edge_clusters: List = None,
                                trend: Optional[TemperatureTrend] = None,
                                temp_array = None,
                                palette_lut = None,
                                is_radiometric: bool = False):
        """Update thermal analysis displays."""
        self.video_widget.update_thermal_detections(hot_spots, cold_spots, anomalies)
        self.analysis_panel.update_statistics(stats)
        self.analysis_panel.update_hot_spots(hot_spots)
        self.analysis_panel.update_cold_spots(cold_spots)
        self.analysis_panel.update_anomalies(anomalies)
        self.analysis_panel.update_trend(trend)

        # Update histogram temperature unit based on mode
        if hasattr(self.analysis_panel, 'set_histogram_temperature_unit'):
            unit = 'C' if is_radiometric else 'RAW'
            self.analysis_panel.set_histogram_temperature_unit(unit)

        # Update histogram palette LUT if available
        if palette_lut is not None and hasattr(self.analysis_panel, 'set_histogram_palette_lut'):
            self.analysis_panel.set_histogram_palette_lut(palette_lut)

        # Update histogram if temp_array is available
        if temp_array is not None and hasattr(self.analysis_panel, 'update_histogram'):
            self.analysis_panel.update_histogram(temp_array)

        counts = {
            "hot_spots": len(hot_spots),
            "cold_spots": len(cold_spots),
            "thermal_anomalies": len(anomalies),
            "motion": len(motion_detections) if motion_detections else 0,
            "edges": len(edge_clusters) if edge_clusters else 0,
            "enhanced_fusion": len(enhanced_fusion_anomalies) if enhanced_fusion_anomalies else 0,
        }
        self.anomaly_widget.update_counts(counts)

    def update_radiometric_panel_availability(self, is_radiometric: bool):
        """Enable/disable panels that require radiometric mode."""
        if hasattr(self, 'isotherm_panel'):
            self.isotherm_panel.setEnabled(is_radiometric)
        if hasattr(self, 'env_comp_panel'):
            self.env_comp_panel.setEnabled(is_radiometric)
        if hasattr(self, 'manual_threshold_widget'):
            self.manual_threshold_widget.set_raw_mode_available(is_radiometric)

    # ========================================================================
    # Camera Status / Hot-Plug Notifications
    # ========================================================================

    def update_camera_status(self, state):
        """
        Reflect the current CameraState in the status bar.

        Args:
            state: CameraState dataclass from camera_controller.
        """
        parts = []
        if getattr(state, 'thermal_connected', False):
            dev = getattr(state, 'thermal_device_id', '?')
            label = 'FLIR Boson' if getattr(state, 'is_flir_boson', False) else 'Thermal'
            parts.append(f"🌡 {label} [dev {dev}]")
        else:
            parts.append("🌡 Thermal: disconnected")

        if getattr(state, 'rgb_available', False):
            dev = getattr(state, 'rgb_device_id', '?')
            parts.append(f"📷 RGB [dev {dev}]")
        else:
            parts.append("📷 RGB: disconnected")

        msg = "  |  ".join(parts)
        self.statusBar().showMessage(msg, 0)   # 0 = persist until next message

        # If no thermal but RGB available, hint that view mode was auto-switched
        if (not getattr(state, 'thermal_connected', False)
                and getattr(state, 'rgb_available', False)):
            self.statusBar().showMessage(
                msg + "  |  ℹ View auto-set to RGB — press V to cycle modes", 0
            )

        # Ensure all camera control tabs remain accessible
        if hasattr(self, 'cameras_tabs'):
            for i in range(self.cameras_tabs.count()):
                self.cameras_tabs.setTabVisible(i, True)

            # Auto-focus the active camera tab if connected
            if getattr(state, 'is_flir_boson', False) and getattr(self, 'boson_panel', None):
                self.cameras_tabs.setCurrentWidget(self.boson_panel)
            elif getattr(state, 'is_lepton', False) and getattr(self, 'lepton_panel', None):
                self.cameras_tabs.setCurrentWidget(self.lepton_panel)
            elif getattr(state, 'is_tau2', False) and getattr(self, 'tau2_panel', None):
                self.cameras_tabs.setCurrentWidget(self.tau2_panel)


    def show_camera_lost_notification(self, role: str):
        """
        Show a transient warning when a camera is physically disconnected.

        Args:
            role: 'thermal' or 'rgb'
        """
        label = "Thermal" if role == 'thermal' else "RGB"
        msg = f"⚠  {label} camera disconnected — using placeholder.  Open Camera Manager to reconnect."
        self.statusBar().showMessage(msg, 0)
        self._show_hotplug_banner(msg, warning=True)

    def show_camera_connected_notification(self, device_id: int, name: str,
                                           resolution: str, suggested_role: str):
        """
        Show a banner when a new camera is detected and both slots are full
        (or the type is ambiguous), prompting the user to assign it manually.

        Args:
            device_id:      OpenCV device index of the new camera.
            name:           Human-readable camera name.
            resolution:     Resolution string e.g. '1920x1080'.
            suggested_role: 'thermal' or 'rgb' (best-guess from detector).
        """
        msg = (
            f"🔌 New camera detected: {name} ({resolution}) "
            f"[dev {device_id}]  — Open Camera Manager to assign it."
        )
        self.statusBar().showMessage(msg, 12000)
        self._show_hotplug_banner(msg, warning=False)

    def show_hotplug_result(self, device_id: int, role: str, success: bool):
        """
        Called after an auto-assign attempt completes.

        Args:
            device_id: OpenCV device index.
            role:      'thermal' or 'rgb'
            success:   Whether the open/assign succeeded.
        """
        label = "Thermal" if role == 'thermal' else "RGB"
        if success:
            msg = f"✅ Auto-connected device {device_id} as {label} camera."
        else:
            msg = (
                f"⚠  Could not auto-connect device {device_id} as {label}. "
                "Open Camera Manager to assign manually."
            )
        self.statusBar().showMessage(msg, 8000)
        self._show_hotplug_banner(msg, warning=not success)

    def _show_hotplug_banner(self, message: str, warning: bool = False):
        """
        Display a transient coloured banner at the bottom of the video area.
        Auto-dismisses after 6 seconds.
        """
        from PyQt6.QtCore import Qt, QTimer

        if not hasattr(self, '_hotplug_banner') or self._hotplug_banner is None:
            self._hotplug_banner = QLabel(self)
            self._hotplug_banner.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._hotplug_banner.setWordWrap(True)
            self._hotplug_banner.setAttribute(
                Qt.WidgetAttribute.WA_TransparentForMouseEvents, False
            )

        banner = self._hotplug_banner
        bg = "#7c2d12" if warning else "#14532d"    # dark-red / dark-green
        banner.setStyleSheet(
            f"background:{bg}; color:#f5f5f5; font-size:13px; "
            "padding:8px 16px; border-radius:6px;"
        )
        banner.setText(message)

        # Position at bottom-centre of the window
        w = min(self.width() - 40, 900)
        h = 52
        banner.setGeometry(
            (self.width() - w) // 2,
            self.height() - h - 36,
            w, h
        )
        banner.raise_()
        banner.show()

        # Auto-hide after 6 s
        if hasattr(self, '_hotplug_banner_timer'):
            self._hotplug_banner_timer.stop()
        self._hotplug_banner_timer = QTimer(self)
        self._hotplug_banner_timer.setSingleShot(True)
        self._hotplug_banner_timer.timeout.connect(banner.hide)
        self._hotplug_banner_timer.start(6000)

    def show_camera_startup_overlay(self, visible: bool):
        """
        Show/hide a translucent 'Detecting cameras…' overlay over the
        video widget while background camera initialisation runs.

        Args:
            visible: True to show, False to dismiss.
        """
        from PyQt6.QtCore import Qt, QTimer as _QT

        if not hasattr(self, '_startup_overlay') or self._startup_overlay is None:
            overlay = QLabel(self)
            overlay.setAlignment(Qt.AlignmentFlag.AlignCenter)
            overlay.setStyleSheet(
                "background: rgba(10,12,20,200);"
                "color: #e2e8f0;"
                "font-size: 15px;"
                "font-weight: 600;"
                "border-radius: 12px;"
                "padding: 20px 32px;"
            )
            overlay.setText("🔍  Detecting cameras…")
            overlay.hide()
            self._startup_overlay = overlay
            self._startup_dot_count = 0

            self._startup_anim = _QT(self)
            self._startup_anim.setInterval(420)
            def _tick():
                self._startup_dot_count = (self._startup_dot_count + 1) % 4
                dots = "." * self._startup_dot_count
                self._startup_overlay.setText(f"🔍  Detecting cameras{dots}")
            self._startup_anim.timeout.connect(_tick)

        overlay = self._startup_overlay
        if visible:
            w, h = 340, 70
            overlay.setGeometry(
                (self.width() - w) // 2,
                (self.height() - h) // 2,
                w, h
            )
            overlay.raise_()
            overlay.show()
            self._startup_anim.start()
        else:
            self._startup_anim.stop()
            overlay.hide()


# ============================================================================
# Standalone Test
# ============================================================================

def main():
    """Standalone test of inspection GUI."""
    app = QApplication(sys.argv)
    window = InspectionAppWindow()
    window.show()

    # Test with dummy data
    dummy_frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
    window.update_frame(dummy_frame)
    window.update_metrics(fps=30.0, roi_count=3, thermal_connected=True, rgb_connected=True)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
