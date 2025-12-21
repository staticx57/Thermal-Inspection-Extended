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
    QInputDialog, QApplication
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor

# Import themes
from thermal_inspection.gui.themes import (
    DARK_THEME, LIGHT_THEME, SOLARIZED_THEME, COLORFUL_THEME, THEMES
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
    BosonControlPanel, BosonSDKPanel, CameraManagerDialog
)

# Import external modules from package
from thermal_inspection.processing.roi_manager import ROI, ROIType
from thermal_inspection.processing.thermal_analyzer import ThermalStatistics, HotSpot, ColdSpot, ThermalAnomaly, TemperatureTrend
from thermal_inspection.gui.panels.spot_meter_panel import SpotMeterPanel, SpotMeterPresets

logger = logging.getLogger(__name__)


class InspectionAppWindow(QMainWindow):
    """
    Main inspection application window.
    Replaces DriverAppWindow with inspection-focused UI.
    """

    def __init__(self, app_instance=None):
        super().__init__()
        self.app = app_instance

        # Window setup
        self.setWindowTitle("Thermal Inspection Fusion Tool v2.0")
        self.setMinimumSize(1280, 720)

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

            # Video widget
            self.video_widget = VideoWidget()
            self.video_widget.overlay.spot_meter_clicked.connect(self._on_spot_meter_clicked)
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
            self.roi_temp_panel = ROITemperaturePanel()
            self.analysis_tabs.addTab(self.roi_temp_panel, "ROI Manager")
            logger.info("  [OK] ROI Manager panel added")

            # Connect ROI Manager signals
            if hasattr(self, 'video_widget') and hasattr(self.video_widget, 'overlay'):
                self.roi_temp_panel.roi_selected.connect(self.video_widget.overlay.set_selected_roi)
                logger.info("  [OK] Connected ROI Manager.roi_selected to overlay")

            # Connect ROI deletion and palette signals to app
            if hasattr(self, 'app') and self.app:
                self.roi_temp_panel.roi_deleted.connect(lambda roi_id: self.app.roi_manager.delete_roi(roi_id) if hasattr(self.app, 'roi_manager') else None)
                self.roi_temp_panel.roi_palette_changed.connect(lambda roi_id, palette: self.app.set_roi_palette(roi_id, palette) if hasattr(self.app, 'set_roi_palette') else None)
                logger.info("  [OK] Connected ROI Manager.roi_deleted and roi_palette_changed")
                
            # Connect export and clear history signals
            self.roi_temp_panel.export_data_requested.connect(self._on_roi_export_data)
            self.roi_temp_panel.clear_history_requested.connect(self._on_roi_clear_history)
            logger.info("  [OK] Connected ROI Manager.export_data and clear_history")

            from thermal_inspection.gui.panels.environmental_compensation_panel import EnvironmentalCompensationPanel
            self.env_comp_panel = EnvironmentalCompensationPanel()
            self.analysis_tabs.addTab(self.env_comp_panel, "Environmental")
            logger.info("  [OK] Environmental compensation panel added")

            from thermal_inspection.gui.panels.isotherm_panel import IsothermPanel
            self.isotherm_panel = IsothermPanel()
            self.analysis_tabs.addTab(self.isotherm_panel, "Isotherm")
            logger.info("  [OK] Isotherm panel added")

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

            self.boson_panel = BosonControlPanel()
            self.cameras_tabs.addTab(self.boson_panel, "Boson")
            logger.info("  [OK] Boson panel added")

            from thermal_inspection.gui.camera_control.firefly_control_panel import FireflyControlPanel
            self.firefly_panel = FireflyControlPanel()
            self.cameras_tabs.addTab(self.firefly_panel, "Firefly")
            logger.info("  [OK] Firefly panel added")

            from thermal_inspection.gui.camera_control.lepton_control_panel import LeptonControlPanel
            self.lepton_panel = LeptonControlPanel()
            self.cameras_tabs.addTab(self.lepton_panel, "Lepton")
            logger.info("  [OK] Lepton panel added")
            
            # Connect Lepton panel signals
            self.lepton_panel.connect_requested.connect(self._on_lepton_connect)
            self.lepton_panel.disconnect_requested.connect(self._on_lepton_disconnect)
            self.lepton_panel.ffc_requested.connect(self._on_lepton_ffc)
            self.lepton_panel.radiometry_toggled.connect(self._on_lepton_radiometry_toggled)
            self.lepton_panel.emissivity_changed.connect(self._on_lepton_emissivity_changed)
            logger.info("  [OK] Lepton panel signals connected")

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

            # Tab 4: Fusion
            logger.info("Creating Fusion tab...")
            from thermal_inspection.gui.panels.fusion_panel import FusionPanel
            self.fusion_panel = FusionPanel()
            self.right_panel_tabs.addTab(self.fusion_panel, "Fusion")
            logger.info("[OK] Fusion tab added to right panel")

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
        self._safe_connect("settings_panel", "backend_changed", self._on_radiometric_backend_changed, "(settings)")
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

        # === BOSON SDK PANEL ===
        self._safe_connect("boson_panel", "sdk_connect_requested", self._on_boson_connect, "(boson)")
        self._safe_connect("boson_panel", "sdk_disconnect_requested", self._on_boson_disconnect, "(boson)")
        self._safe_connect("boson_panel", "ffc_triggered", self._on_boson_ffc, "(boson)")
        self._safe_connect("boson_panel", "sdk_scan_ports_requested", self._on_boson_scan_ports, "(boson)")
        self._safe_connect("boson_panel", "gain_mode_changed", self._on_boson_gain_mode, "(boson)")
        self._safe_connect("boson_panel", "ffc_mode_changed", self._on_boson_ffc_mode, "(boson)")
        self._safe_connect("boson_panel", "color_lut_changed", self._on_boson_color_lut, "(boson)")
        self._safe_connect("boson_panel", "agc_max_gain_changed", self._on_agc_max_gain_changed, "(boson AGC)")
        self._safe_connect("boson_panel", "agc_gamma_changed", self._on_agc_gamma_changed, "(boson AGC)")
        self._safe_connect("boson_panel", "agc_linearity_changed", self._on_agc_linearity_changed, "(boson AGC)")
        self._safe_connect("boson_panel", "agc_dde_changed", self._on_agc_dde_changed, "(boson AGC)")
        self._safe_connect("boson_panel", "agc_plateau_changed", self._on_agc_plateau_changed, "(boson AGC)")
        self._safe_connect("boson_panel", "agc_dampening_changed", self._on_agc_dampening_changed, "(boson AGC)")
        self._safe_connect("boson_panel", "agc_reset_requested", self._on_agc_reset, "(boson AGC)")
        self._safe_connect("boson_panel", "shutter_position_changed", self._on_shutter_position_changed, "(boson shutter)")
        self._safe_connect("boson_panel", "radiometric_mode_changed", self._on_radiometric_mode_changed, "(boson radiometric)")

        # === FIREFLY CAMERA PANEL ===
        self._safe_connect("firefly_panel", "exposure_mode_changed", self._on_firefly_exposure_mode, "(firefly)")
        self._safe_connect("firefly_panel", "exposure_time_changed", self._on_firefly_exposure_time, "(firefly)")
        self._safe_connect("firefly_panel", "gain_mode_changed", self._on_firefly_gain_mode, "(firefly)")
        self._safe_connect("firefly_panel", "gain_changed", self._on_firefly_gain, "(firefly)")
        self._safe_connect("firefly_panel", "white_balance_mode_changed", self._on_firefly_white_balance_mode, "(firefly)")
        self._safe_connect("firefly_panel", "white_balance_calibrate", self._on_firefly_white_balance_calibrate, "(firefly)")
        self._safe_connect("firefly_panel", "white_balance_ratio_changed", self._on_firefly_white_balance_ratio, "(firefly)")
        self._safe_connect("firefly_panel", "trigger_mode_changed", self._on_firefly_trigger_mode, "(firefly)")
        self._safe_connect("firefly_panel", "trigger_fire", self._on_firefly_trigger_fire, "(firefly)")
        self._safe_connect("firefly_panel", "gamma_changed", self._on_firefly_gamma, "(firefly)")
        self._safe_connect("firefly_panel", "sharpness_changed", self._on_firefly_sharpness, "(firefly)")

        # === CALIBRATION PANEL ===
        self._safe_connect("calibration_panel", "add_calibration_point_clicked", self._on_calibration_add_point_mode, "(calibration)")
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

        # === RADIOMETRIC PANEL 8-Bit ===
        self._safe_connect("radiometric_panel", "estimation_8bit_enabled_changed", self._on_8bit_estimation_toggled, "(radiometric 8-bit)")
        self._safe_connect("radiometric_panel", "temperature_range_changed", self._on_temperature_range_changed, "(radiometric 8-bit)")
        self._safe_connect("radiometric_panel", "calibrate_single_point_requested", self._on_calibrate_single_point, "(radiometric 8-bit)")
        self._safe_connect("radiometric_panel", "calibrate_two_point_requested", self._on_calibrate_two_point, "(radiometric 8-bit)")

        # === RADIOMETRIC PANEL Unit & Detection Settings ===
        self._safe_connect("radiometric_panel", "temperature_unit_changed", self._on_radiometric_temp_unit_changed, "(radiometric unit)")
        self._safe_connect("radiometric_panel", "max_hot_spots_changed", self._on_radiometric_max_hot_spots_changed, "(radiometric spots)")
        self._safe_connect("radiometric_panel", "max_cold_spots_changed", self._on_radiometric_max_cold_spots_changed, "(radiometric spots)")
        self._safe_connect("radiometric_panel", "backend_changed", self._on_radiometric_backend_changed, "(radiometric backend)")

        # === GENERAL ANALYSIS PANEL Detection Toggles ===
        self._safe_connect("analysis_panel.show_hot_spots_checkbox", "toggled", self._on_show_hot_spots_toggled, "(detection toggle)")
        self._safe_connect("analysis_panel.show_cold_spots_checkbox", "toggled", self._on_show_cold_spots_toggled, "(detection toggle)")
        self._safe_connect("analysis_panel.show_anomalies_checkbox", "toggled", self._on_show_anomalies_toggled, "(detection toggle)")

        # === ROI MANAGEMENT ===
        self._safe_connect("analysis_panel", "roi_selected", self._on_roi_selected, "(analysis)")
        self._safe_connect("analysis_panel", "roi_deleted", self._on_roi_delete, "(analysis)")

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

        # === INITIALIZE BOSON PANEL IF SDK ALREADY CONNECTED ===
        try:
            if self.app and hasattr(self.app, 'thermal_camera'):
                thermal_cam = self.app.thermal_camera
                if hasattr(thermal_cam, 'sdk_connected') and thermal_cam.sdk_connected:
                    logger.info("[BOSON INIT] SDK already connected, updating panel...")
                    self.boson_panel.update_connection_status(True)
                    if hasattr(thermal_cam, 'get_camera_info'):
                        info = thermal_cam.get_camera_info()
                        if info:
                            self.boson_panel.set_status(f"SN: {info.serial_number}")
                            self.boson_panel.update_camera_info(info)
                            logger.info(f"[BOSON INIT] Panel updated with camera info (SN: {info.serial_number})")
                else:
                    logger.info("[BOSON INIT] SDK not connected yet")
            else:
                logger.info("[BOSON INIT] App or thermal_camera not available yet")
        except Exception as e:
            logger.error(f"[BOSON INIT] Error initializing Boson panel: {e}", exc_info=True)

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

        if actual_theme in THEMES:
            self.setStyleSheet(THEMES[actual_theme])
        elif actual_theme == "light":
            self.setStyleSheet(THEMES.get("Light Mode", LIGHT_THEME))
        elif actual_theme == "dark":
            self.setStyleSheet(THEMES.get("Dark Mode", DARK_THEME))
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
    # Stub Handler Methods (to be connected to app)
    # ========================================================================

    def _on_radiometric_backend_changed(self, backend_text: str):
        if "Flirpy" in backend_text:
            backend_id = "flirpy"
        else:
            backend_id = "opencv"
        logger.info(f"Radiometric backend switch requested: {backend_text} -> {backend_id}")
        if self.app:
            self.app.switch_thermal_backend(backend_id)

    def _on_radiometric_max_cold_spots_changed(self, count: int):
        if self.app and hasattr(self.app, 'thermal_analyzer'):
            self.app.thermal_analyzer.max_cold_spots = count
            logger.info(f"Max cold spots set to: {count}")

    def _on_radiometric_max_hot_spots_changed(self, count: int):
        if self.app and hasattr(self.app, 'thermal_analyzer'):
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
        if self.app:
            self.app.enable_radiometric(enabled)

    def _on_radiometric_range_apply(self):
        """Apply manual radiometric range."""
        if not self.app or not hasattr(self, 'radiometric_panel'):
            return

        try:
            low = self.radiometric_panel.range_low_spin.value()
            high = self.radiometric_panel.range_high_spin.value()
            logger.info(f"Applying radiometric range: {low} - {high}")
            
            # Update controller
            self.app.radiometric_controller.set_temperature_range(low, high)
            
            # Also ensure manual mode is active if that's the intent
            # (The controller usually handles mode switching if needed)
        except Exception as e:
            logger.error(f"Error applying radiometric range: {e}")

    def _on_load_lut(self):
        """Load custom Look-Up Table (LUT)."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Load LUT File", "", "LUT Files (*.csv *.png *.jpg);;All Files (*)"
        )
        if file_path:
            logger.info(f"Loading LUT from: {file_path}")
            if self.app and hasattr(self.app, 'palette_manager'):
                # Assuming palette manager has a load_lut method
                # If not, this is a placeholder for that future capability
                # self.app.palette_manager.load_custom_lut(file_path)
                logger.info("LUT loading logic would go here (pending PaletteManager update)")

    def _on_radiometric_method_changed(self):
        """Handle radiometric conversion method change (Linear vs LUT)."""
        if not self.app or not hasattr(self, 'radiometric_panel'):
            return
            
        is_lut = self.radiometric_panel.method_lut_radio.isChecked()
        mode = "lut" if is_lut else "t-linear"
        logger.info(f"Radiometric method changed to: {mode}")
        
        # Update controller
        # self.app.radiometric_controller.set_conversion_method(mode)

    def _on_spotmeter_enabled_changed(self, enabled: bool):
        """Handle spotmeter enable toggle."""
        if self.app and hasattr(self.app, 'thermal_analyzer'):
            self.app.thermal_analyzer.spotmeter_enabled = enabled
            logger.info(f"Spotmeter analysis enabled: {enabled}")

    def _on_spotmeter_mode_changed(self, mode: str):
        """Handle spotmeter mode change (center, max, min)."""
        if self.app and hasattr(self.app, 'thermal_analyzer'):
            self.app.thermal_analyzer.spotmeter_mode = mode
            logger.info(f"Spotmeter mode set to: {mode}")

    def _on_sensor_temps_requested(self):
        """Handle request for FPA/Housing temperatures."""
        if not self.app or not self.app.thermal_camera:
            return
            
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
        if self.app and hasattr(self.app, 'thermal_analyzer'):
            self.app.thermal_analyzer.estimator_enabled = enabled
            logger.info(f"8-bit estimator enabled: {enabled}")

    def _on_temperature_range_changed(self, low: float, high: float):
        """Handle temperature range change for estimation."""
        if self.app and hasattr(self.app, 'thermal_analyzer'):
            self.app.thermal_analyzer.set_estimation_range(low, high)

    def _on_calibrate_single_point(self, temp: float):
        """Handle single point calibration."""
        if self.app and hasattr(self.app, 'thermal_analyzer'):
            self.app.thermal_analyzer.calibrate_single_point(temp)
            logger.info(f"Single point calibration triggered at {temp}")

    def _on_calibrate_two_point(self, t1: float, t2: float):
        """Handle two point calibration."""
        if self.app and hasattr(self.app, 'thermal_analyzer'):
            self.app.thermal_analyzer.calibrate_two_point(t1, t2)
            logger.info(f"Two point calibration triggered: {t1}, {t2}")

    def _on_radiometric_temp_unit_changed(self, unit: str):
        logger.info(f"[MAIN_WINDOW] _on_radiometric_temp_unit_changed called with unit: {unit}")
        if hasattr(self, 'video_widget') and hasattr(self.video_widget, 'overlay'):
            self.video_widget.overlay.set_temperature_unit(unit)
        if self.app:
            self.app.set_temperature_unit(unit)
        if hasattr(self, 'isotherm_panel'):
            unit_index_map = {'C': 0, 'F': 1, 'K': 2, 'RAW': 3}
            unit_index = unit_index_map.get(unit, 0)
            self.isotherm_panel.set_temperature_unit(unit_index)

    # === FUSION HANDLERS ===
    def _on_fusion_mode_changed(self, mode: str):
        if self.app:
            self.app.set_fusion_mode(mode)
        logger.info(f"Fusion mode changed to: {mode}")

    def _on_fusion_alpha_changed(self, val: float):
        if self.app:
            self.app.set_fusion_alpha(val)

    def _on_fusion_priority_changed(self, val: str):
        # Normalize to lowercase for backend compatibility
        priority = val.lower()
        if priority == 'balanced':
            priority = 'thermal'  # Default to thermal for 'balanced'
        
        if self.app:
            self.app.set_fusion_priority(priority)
            # Sync overlay with new priority
            if hasattr(self, 'video_widget') and hasattr(self.video_widget, 'overlay'):
                current_mode = self.video_widget.overlay.current_view_mode
                self.video_widget.overlay.set_view_mode(current_mode, priority)
        logger.info(f"Fusion priority changed to: {priority}")

    def _on_fusion_strength_changed(self, val: float):
        if self.app and hasattr(self.app, 'set_fusion_strength'):
            self.app.set_fusion_strength(val)
        logger.info(f"Fusion strength changed to: {val:.2f}")

    def _on_fusion_fuzziness_changed(self, val: float):
        if self.app and hasattr(self.app, 'set_fusion_fuzziness'):
            self.app.set_fusion_fuzziness(val)

    def _on_fusion_color_mode_changed(self, val: str):
        if self.app and hasattr(self.app, 'set_fusion_color_mode'):
            self.app.set_fusion_color_mode(val)

    def _on_edge_strength_changed(self, val: float):
        if self.app and hasattr(self.app, 'set_edge_strength'):
            self.app.set_edge_strength(val)

    def _on_edge_fuzziness_changed(self, val: float):
        if self.app and hasattr(self.app, 'set_edge_fuzziness'):
            self.app.set_edge_fuzziness(val)

    def _on_edge_color_changed(self, val: str):
        if self.app and hasattr(self.app, 'set_edge_color'):
            self.app.set_edge_color(val)

    def _on_detail_strength_changed(self, val: float):
        if self.app and hasattr(self.app, 'set_detail_strength'):
            self.app.set_detail_strength(val)

    def _on_detail_quality_changed(self, val: str):
        if self.app and hasattr(self.app, 'set_detail_quality'):
            self.app.set_detail_quality(val)

    # === ANALYSIS HANDLERS ===
    def _on_global_palette_changed(self, palette_name: str):
        try:
            logger.info(f"Attempting to change palette to: '{palette_name}'")
            if self.app:
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
        if self.app and hasattr(self.app, 'set_emissivity'):
            self.app.set_emissivity(val)
        logger.info(f"Emissivity changed to: {val:.2f}")

    def _on_atmospheric_temp_changed(self, val: float):
        if self.app and hasattr(self.app, 'set_atmospheric_temperature'):
            self.app.set_atmospheric_temperature(val)

    def _on_atmospheric_transmission_changed(self, val: float):
        if self.app and hasattr(self.app, 'set_atmospheric_transmission'):
            self.app.set_atmospheric_transmission(val)

    # === ISOTHERM HANDLERS ===
    def _on_isotherm_enabled_changed(self, enabled: bool):
        if self.app:
            if hasattr(self.app, 'set_isotherm_enabled'):
                self.app.set_isotherm_enabled(enabled)
            else:
                self.app.isotherm_enabled = enabled

    def _on_isotherm_mode_changed(self, mode: str):
        if self.app:
            if hasattr(self.app, 'set_isotherm_mode'):
                self.app.set_isotherm_mode(mode)
            else:
                self.app.isotherm_mode = mode

    def _on_isotherm_low_threshold_changed(self, val: float):
        if self.app:
            if hasattr(self.app, 'set_isotherm_low_threshold'):
                self.app.set_isotherm_low_threshold(val)
            else:
                self.app.isotherm_low_threshold = val

    def _on_isotherm_high_threshold_changed(self, val: float):
        if self.app:
            if hasattr(self.app, 'set_isotherm_high_threshold'):
                self.app.set_isotherm_high_threshold(val)
            else:
                self.app.isotherm_high_threshold = val

    def _on_isotherm_color_changed(self, val: str):
        if self.app:
            if hasattr(self.app, 'set_isotherm_color'):
                self.app.set_isotherm_color(val)
            else:
                self.app.isotherm_color = val

    def _on_isotherm_bands_changed(self, band_manager):
        if self.app:
            if hasattr(self.app, 'set_isotherm_band_manager'):
                self.app.set_isotherm_band_manager(band_manager)
            if hasattr(self.app, 'set_isotherm_multiband_mode'):
                is_multiband = self.isotherm_panel.is_multiband_mode()
                self.app.set_isotherm_multiband_mode(is_multiband)

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
        pass

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
        if self.app and hasattr(self.app, 'lock_baseline'):
            self.app.lock_baseline(enabled)
        logger.info(f"Baseline lock: {'ON' if enabled else 'OFF'}")

    # === CONTROL PANEL HANDLERS ===
    def _on_palette_cycle(self):
        if self.app:
            self.app.cycle_palette()
        logger.info("Palette cycle")

    def _on_view_mode_cycle(self):
        if self.app:
            self.app.cycle_view_mode()
            # Sync overlay with new view mode
            self._sync_overlay_view_mode()
        logger.info("View mode cycle")

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
        
        # Update overlay
        self.video_widget.overlay.set_view_mode(mode_str, fusion_priority)
        logger.debug(f"Overlay synced: mode={mode_str}, priority={fusion_priority}")

    def _on_record_toggle(self, enabled: bool):
        self.recording = enabled
        self.control_panel.update_record_button(enabled)
        if self.app:
            self.app.toggle_recording(enabled)
        logger.info(f"Recording: {'ON' if enabled else 'OFF'}")

    def _on_snapshot(self):
        if self.app:
            self.app.capture_snapshot()
        logger.info("Snapshot captured")

    def _on_freeze_toggle(self, enabled: bool):
        self.frozen = enabled
        self.control_panel.update_freeze_button(enabled)
        if self.app:
            self.app.toggle_freeze(enabled)
        logger.info(f"Frame freeze: {'ON' if enabled else 'OFF'}")

    def _on_auto_roi(self):
        if self.app and hasattr(self.app, 'auto_roi_detect'):
            self.app.auto_roi_detect()
            logger.info("Auto ROI detection triggered")

    def _on_draw_roi(self):
        if self.video_widget and hasattr(self.video_widget, 'overlay'):
            self.video_widget.overlay.enable_drawing_mode(ROIType.RECTANGLE)
            logger.info("Draw ROI mode activated (rectangle)")
            self.control_panel.draw_roi_btn.setChecked(True)

    def _on_clear_rois(self):
        if self.app:
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
        if self.app:
            self.app.set_device(device_name)
        logger.info(f"Device changed to: {device_name}")

    def _on_roi_delete(self, roi_id: str):
        if self.app:
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
            self.video_widget.overlay.clear_spots()
        if hasattr(self.analysis_panel, 'spot_meter_panel'):
            self.analysis_panel.spot_meter_panel.clear_all_spots()

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
        if self.app:
            self.app.toggle_anomaly_priority(enabled)
        logger.info(f"Anomaly priority: {'ON' if enabled else 'OFF'}")

    def _on_anomaly_types_changed(self, types_dict: dict):
        if self.app:
            self.app.set_enabled_anomaly_types(types_dict)
        logger.info(f"Anomaly types changed: {types_dict}")

    def _on_fade_strength_changed(self, value: float):
        if self.app and hasattr(self.app, 'thermal_processor'):
            self.app.thermal_processor.anomaly_fade_strength = value

    def _on_fade_distance_changed(self, value: int):
        if self.app and hasattr(self.app, 'thermal_processor'):
            self.app.thermal_processor.anomaly_max_distance = value

    def _on_motion_threshold_changed(self, value: int):
        if self.app and hasattr(self.app, 'thermal_processor'):
            self.app.thermal_processor.motion_threshold = value

    def _on_edge_thresholds_changed(self, low: int, high: int):
        if self.app and hasattr(self.app, 'thermal_processor'):
            self.app.thermal_processor.edge_threshold_low = low
            self.app.thermal_processor.edge_threshold_high = high

    def _on_hot_spot_percentile_changed(self, value: int):
        if self.app and hasattr(self.app, 'thermal_analyzer'):
            self.app.thermal_analyzer.hot_spot_percentile = value

    def _on_cold_spot_percentile_changed(self, value: int):
        if self.app and hasattr(self.app, 'thermal_analyzer'):
            self.app.thermal_analyzer.cold_spot_percentile = value

    def _on_min_anomaly_size_changed(self, value: int):
        if self.app and hasattr(self.app, 'thermal_analyzer'):
            self.app.thermal_analyzer.min_anomaly_size = value

    def _on_manual_threshold_enabled(self, enabled: bool):
        if self.app:
            self.app.set_manual_threshold_enabled(enabled)

    def _on_manual_threshold_mode_changed(self, mode: str):
        if self.app:
            self.app.set_manual_threshold_mode(mode)

    def _on_manual_min_threshold_changed(self, value: float):
        if self.app:
            self.app.set_manual_min_threshold(value)

    def _on_manual_max_threshold_changed(self, value: float):
        if self.app:
            self.app.set_manual_max_threshold(value)

    def _on_manual_use_raw_changed(self, use_raw: bool):
        if self.app:
            self.app.set_manual_use_raw_values(use_raw)

    def _on_manual_viz_mode_changed(self, mode: str):
        if self.app:
            self.app.set_manual_viz_mode(mode)

    # === BOSON HANDLERS ===
    def _on_boson_connect(self, com_port: str):
        if self.app and hasattr(self.app, 'connect_boson_sdk'):
            success = self.app.connect_boson_sdk(com_port)
            if success:
                self.boson_panel.update_connection_status(True)
                logger.info(f"Boson SDK connected on {com_port}")
                if hasattr(self.app.thermal_camera, 'get_camera_info'):
                    info = self.app.thermal_camera.get_camera_info()
                    if info:
                        self.boson_panel.set_status(f"SN: {info.serial_number}")
                        self.boson_panel.update_camera_info(info)
            else:
                self.boson_panel.set_status("Connection failed", is_error=True)

    def _on_boson_disconnect(self):
        if self.app and hasattr(self.app, 'disconnect_boson_sdk'):
            self.app.disconnect_boson_sdk()
            self.boson_panel.update_connection_status(False)
            self.boson_panel.set_status("Disconnected")

    def _on_boson_scan_ports(self):
        if self.app and hasattr(self.app, 'scan_boson_com_ports'):
            ports = self.app.scan_boson_com_ports()
            if ports:
                self.boson_panel.update_ports(ports)
                self.boson_panel.set_status(f"Found {len(ports)} COM ports")

    def _on_boson_ffc(self):
        if self.app and hasattr(self.app, 'trigger_ffc'):
            success = self.app.trigger_ffc()
            if success:
                self.boson_panel.set_status("FFC completed successfully")

    def _on_boson_gain_mode(self, mode: str):
        if self.app and hasattr(self.app, 'set_boson_gain_mode'):
            self.app.set_boson_gain_mode(mode)

    def _on_boson_ffc_mode(self, mode: str):
        if self.app and hasattr(self.app, 'set_boson_ffc_mode'):
            self.app.set_boson_ffc_mode(mode)

    def _on_boson_color_lut(self, lut_name: str):
        if self.app and hasattr(self.app, 'set_boson_color_lut'):
            self.app.set_boson_color_lut(lut_name)

    def _on_agc_max_gain_changed(self, gain: float):
        if self.app and hasattr(self.app, 'set_agc_max_gain'):
            self.app.set_agc_max_gain(gain)

    def _on_agc_gamma_changed(self, gamma: float):
        if self.app and hasattr(self.app, 'set_agc_gamma'):
            self.app.set_agc_gamma(gamma)

    def _on_agc_linearity_changed(self, percent: float):
        if self.app and hasattr(self.app, 'set_agc_linearity'):
            self.app.set_agc_linearity(percent)

    def _on_agc_dde_changed(self, dde: float):
        if self.app and hasattr(self.app, 'set_agc_dde'):
            self.app.set_agc_dde(dde)

    def _on_agc_reset(self):
        if self.app and hasattr(self.app, 'reset_agc_settings'):
            self.app.reset_agc_settings()

    def _on_agc_plateau_changed(self, value: float):
        if self.app and hasattr(self.app, 'set_agc_plateau'):
            self.app.set_agc_plateau(value)

    def _on_agc_dampening_changed(self, value: float):
        if self.app and hasattr(self.app, 'set_agc_dampening'):
            self.app.set_agc_dampening(value)

    def _on_shutter_position_changed(self, position: str):
        if self.app and hasattr(self.app, 'set_shutter_position'):
            self.app.set_shutter_position(position)

    def _on_radiometric_mode_changed(self, enable_radiometric: bool):
        if self.app and hasattr(self.app, 'set_radiometric_mode'):
            success = self.app.set_radiometric_mode(enable_radiometric)
            self.boson_panel.update_radiometric_mode_status(enable_radiometric, success)

    # === LEPTON HANDLERS ===
    def _on_lepton_connect(self):
        """Handle Lepton connect request."""
        logger.info("Lepton connect requested")
        if self.app and hasattr(self.app, 'connect_lepton'):
            success = self.app.connect_lepton()
            if hasattr(self, 'lepton_panel'):
                self.lepton_panel.update_connection_status(success)

    def _on_lepton_disconnect(self):
        """Handle Lepton disconnect request."""
        logger.info("Lepton disconnect requested")
        if self.app and hasattr(self.app, 'disconnect_lepton'):
            self.app.disconnect_lepton()
            if hasattr(self, 'lepton_panel'):
                self.lepton_panel.update_connection_status(False)

    def _on_lepton_ffc(self):
        """Handle Lepton FFC request."""
        logger.info("Lepton FFC requested")
        if self.app and hasattr(self.app, 'trigger_lepton_ffc'):
            self.app.trigger_lepton_ffc()

    def _on_lepton_radiometry_toggled(self, enabled: bool):
        """Handle Lepton radiometry toggle."""
        logger.info(f"Lepton radiometry: {enabled}")
        if self.app and hasattr(self.app, 'set_lepton_radiometry'):
            self.app.set_lepton_radiometry(enabled)

    def _on_lepton_emissivity_changed(self, value: float):
        """Handle Lepton emissivity change."""
        logger.info(f"Lepton emissivity: {value}")
        if self.app:
            self.app.set_emissivity(value)

    # === FIREFLY HANDLERS ===
    def _on_firefly_exposure_mode(self, mode: str):
        if self.app:
            self.app.set_firefly_exposure_mode(mode)

    def _on_firefly_exposure_time(self, time_us: float):
        if self.app:
            self.app.set_firefly_exposure_time(time_us)

    def _on_firefly_gain_mode(self, mode: str):
        if self.app:
            self.app.set_firefly_gain_mode(mode)

    def _on_firefly_gain(self, gain_db: float):
        if self.app:
            self.app.set_firefly_gain(gain_db)

    def _on_firefly_white_balance_mode(self, mode: str):
        if self.app:
            self.app.set_firefly_white_balance_mode(mode)

    def _on_firefly_white_balance_calibrate(self):
        if self.app:
            self.app.calibrate_firefly_white_balance()

    def _on_firefly_white_balance_ratio(self, color: str, ratio: float):
        if self.app:
            self.app.set_firefly_white_balance_ratio(color, ratio)

    def _on_firefly_trigger_mode(self, enabled: bool, source: str):
        if self.app:
            self.app.set_firefly_trigger_mode(enabled, source)

    def _on_firefly_trigger_fire(self):
        if self.app:
            self.app.fire_firefly_software_trigger()

    def _on_firefly_gamma(self, gamma: float):
        if self.app:
            self.app.set_firefly_gamma(gamma)

    def _on_firefly_sharpness(self, enabled: bool, value: float):
        if self.app:
            self.app.set_firefly_sharpness(enabled, value)

    # === CALIBRATION HANDLERS ===
    def _on_calibration_add_point_mode(self, reference_temp: float):
        if self.app and hasattr(self.app, 'set_calibration_add_point_mode'):
            self.app.set_calibration_add_point_mode(True, reference_temp)

    def _on_compute_calibration(self, method: str, degree: int):
        if self.app and hasattr(self.app, 'compute_calibration'):
            if self.app.compute_calibration(method, degree):
                logger.info(f"Calibration computed using {method} method")
                if hasattr(self.app, 'update_calibration_gui'):
                    self.app.update_calibration_gui()
            else:
                QMessageBox.warning(self, "Calibration Error",
                                   "Failed to compute calibration. Need at least 2 points for linear, more for polynomial.")

    def _on_apply_calibration_toggled(self, enabled: bool):
        if self.app and hasattr(self.app, 'set_calibration_enabled'):
            self.app.set_calibration_enabled(enabled)

    def _on_clear_calibration(self):
        if self.app and hasattr(self.app, 'clear_calibration'):
            self.app.clear_calibration()
            if hasattr(self.app, 'update_calibration_gui'):
                self.app.update_calibration_gui()

    def _on_export_calibration(self):
        if not self.app or not hasattr(self.app, 'export_calibration'):
            return

        from datetime import datetime
        default_name = f"calibration_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export Calibration", default_name, "JSON Files (*.json);;All Files (*.*)"
        )

        if file_path:
            if self.app.export_calibration(file_path):
                QMessageBox.information(self, "Export Successful", f"Calibration exported to:\n{file_path}")
            else:
                QMessageBox.critical(self, "Export Failed", "Failed to export calibration")

    def _on_import_calibration(self):
        if not self.app or not hasattr(self.app, 'import_calibration'):
            return

        file_path, _ = QFileDialog.getOpenFileName(
            self, "Import Calibration", "", "JSON Files (*.json);;All Files (*.*)"
        )

        if file_path:
            if self.app.import_calibration(file_path):
                QMessageBox.information(self, "Import Successful", f"Calibration imported from:\n{file_path}")
                if hasattr(self.app, 'update_calibration_gui'):
                    self.app.update_calibration_gui()
            else:
                QMessageBox.critical(self, "Import Failed", "Failed to import calibration")

    def _on_remove_calibration_point(self, index: int):
        if self.app and hasattr(self.app, 'remove_calibration_point'):
            if self.app.remove_calibration_point(index):
                if hasattr(self.app, 'update_calibration_gui'):
                    self.app.update_calibration_gui()

    # === PARALLAX HANDLERS ===
    def _on_parallax_toggled(self, enabled: bool):
        if self.app and hasattr(self.app, 'enable_parallax_compensation'):
            self.app.enable_parallax_compensation(enabled)

    def _on_parallax_baseline_changed(self, baseline_mm: float):
        if self.app and hasattr(self.app, 'set_parallax_baseline'):
            self.app.set_parallax_baseline(baseline_mm)

    def _on_parallax_method_changed(self, method: str):
        if self.app and hasattr(self.app, 'set_parallax_depth_method'):
            self.app.set_parallax_depth_method(method)

    def _on_parallax_geometry_apply(self):
        baseline = self.parallax_panel.get_baseline()
        if self.app and hasattr(self.app, 'set_parallax_baseline'):
            self.app.set_parallax_baseline(baseline)

    # ========================================================================
    # Public Update Methods (called from app)
    # ========================================================================

    def update_frame(self, frame: np.ndarray):
        """Update video display."""
        self.video_widget.update_frame(frame)

    def update_metrics(self, fps: float, roi_count: int, thermal_connected: bool, rgb_connected: bool):
        """Update info panel metrics."""
        self.info_panel.update_info(fps, roi_count, thermal_connected, rgb_connected, self.recording)

    def update_rois(self, rois: List[ROI]):
        """Update ROI visualization and list."""
        self.video_widget.update_rois(rois)
        self.analysis_panel.update_rois(rois)
        if hasattr(self, 'roi_temp_panel'):
            self.roi_temp_panel.update_rois(rois)

    def update_thermal_analysis(self, stats: Optional[ThermalStatistics],
                                hot_spots: List[HotSpot],
                                cold_spots: List[ColdSpot],
                                anomalies: List[ThermalAnomaly],
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
            "edges": len(edge_clusters) if edge_clusters else 0
        }
        self.anomaly_widget.update_counts(counts)

    def update_radiometric_panel_availability(self, is_radiometric: bool):
        """Enable/disable panels that require radiometric mode."""
        if hasattr(self, 'isotherm_panel'):
            self.isotherm_panel.setEnabled(is_radiometric)
        if hasattr(self, 'env_comp_panel'):
            self.env_comp_panel.setEnabled(is_radiometric)


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
