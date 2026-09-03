"""
Thermal Inspection Application Coordinator.

This is the slim coordinator that composes all controllers and provides
a clean interface for the main entry point. Extracted from the monolithic
ThermalInspectionFusion class in inspection_main.py.
"""

import sys
import logging
import threading
import time
from typing import Optional
from dataclasses import dataclass

import cv2
import numpy as np
from PyQt6.QtCore import QTimer, Qt

from .core import (
    FusionController, FusionState, ViewMode,
    ROIController, RadiometricController, RadiometricState,
)
from .core.camera_state import CameraState
from .core.threshold_manager import ThresholdManager
from .core.isotherm_manager import IsothermManager
from .core.event_bus import AppEventBus
from .cameras.plugin import get_host

logger = logging.getLogger(__name__)


@dataclass
class AppConfig:
    """Application configuration."""
    # Camera settings
    thermal_device: Optional[int] = None
    rgb_device: Optional[int] = None
    disable_rgb: bool = False
    width: int = 640
    height: int = 512
    enable_boson_sdk: bool = True
    boson_com_port: str = 'COM7'

    # Fusion settings
    fusion_mode: str = 'thermal_overlay'
    fusion_alpha: float = 0.5

    # Processing settings
    device: str = 'cuda'
    palette: str = 'ironbow'
    radiometric: bool = False

    # GUI settings
    gui_type: str = 'qt'
    headless: bool = False

    # Automated testing: self-drive through every fusion mode instead of
    # requiring manual UI clicking, then exit. None disables it.
    auto_cycle_fusion_modes: Optional[float] = None

    @classmethod
    def from_args(cls, args) -> 'AppConfig':
        """Create config from argparse namespace."""
        return cls(
            thermal_device=getattr(args, 'thermal_device', None),
            rgb_device=getattr(args, 'rgb_device', None),
            disable_rgb=getattr(args, 'disable_rgb', False),
            width=getattr(args, 'width', 640),
            height=getattr(args, 'height', 512),
            enable_boson_sdk=getattr(args, 'enable_boson_sdk', True),
            boson_com_port=getattr(args, 'boson_com_port', 'COM7'),
            fusion_mode=getattr(args, 'fusion_mode', 'thermal_overlay'),
            fusion_alpha=getattr(args, 'fusion_alpha', 0.5),
            device=getattr(args, 'device', 'cuda'),
            palette=getattr(args, 'palette', 'ironbow'),
            radiometric=getattr(args, 'radiometric', False),
            gui_type=getattr(args, 'gui', 'qt'),
            headless=getattr(args, 'headless', False),
            auto_cycle_fusion_modes=getattr(args, 'auto_cycle_fusion_modes', None),
        )


class ThermalInspectionApp:
    """
    Main application coordinator for Thermal Inspection.

    This class composes all controllers and provides a unified interface
    for the application lifecycle.

    Usage:
        app = ThermalInspectionApp(config)
        if app.initialize():
            app.run()
        app.cleanup()
    """

    def __init__(self, config: Optional[AppConfig] = None, qt_app=None):
        """
        Initialize the application.

        Args:
            config: Application configuration
            qt_app: Optional QApplication instance for Qt GUI
        """
        self.config = config or AppConfig()
        self.qt_app = qt_app

        # Media recording manager (initialized in _init_processing)
        self.media_manager = None

        # Managers (encapsulated state with validation and signals)
        self.threshold_manager = ThresholdManager()
        self.isotherm_manager = IsothermManager()

        # Calibration state (delegated)
        from .core.calibration_manager import CalibrationManager
        self.calibration_manager = CalibrationManager()

        # Fusion color mode ("color" or "grayscale")
        self._fusion_color_mode = "color"

        # Central event bus for GUI ↔ backend communication
        self.event_bus = AppEventBus()

        # Hardware-agnostic camera plugin host
        self.plugin_host = get_host()

        # Initialize controllers (uses event_bus in _wire_callbacks)
        self._init_controllers()

        # GUI reference (set during initialization)
        self.gui = None

        # Processing components (set during initialization)
        self.fusion_processor = None
        self.thermal_processor = None
        self.thermal_analyzer = None
        self.roi_manager = None
        self.palette_manager = None
        self.gradient_processor = None

        # State flags
        self.initialized = False
        self.running = False
        self.frame_frozen = False
        self.enabled_anomaly_types = {}
        self.view_mode = ViewMode.THERMAL_ONLY # Initial default
        self.args = config # Legacy compatibility for GUI

        # Automated fusion-mode sweep (see AppConfig.auto_cycle_fusion_modes) -
        # self-drives through every mode instead of requiring manual UI
        # clicking, for performance testing. None/-1 idx = not yet started.
        self._auto_cycle_modes = None
        self._auto_cycle_idx = -1
        self._auto_cycle_deadline = 0.0

        # Throttle for handing frames to ThreadedAnalyzer - see its
        # submission call site in _process_frame_loop for why.
        self._last_analysis_submit_time = 0.0
        self._analysis_submit_interval_s = 1.0 / 30.0

        # Throttle for 3D Fusion point-cloud updates - GL upload + the
        # per-point thermal-color sampling isn't free, and the view only
        # needs to feel live, not match the main video loop's framerate.
        self._last_3d_fusion_update_time = 0.0
        self._3d_fusion_update_interval_s = 1.0 / 15.0
        # Dedup state so hardware/alignment status is only pushed to the
        # GUI when it actually changes, not every frame.
        self._last_3d_hw_available_reported = None  # holds the backend object once reported available
        self._last_3d_aligned_reported = False
        self._3d_relief_strength = 0.5
        self._3d_mode = "relief"  # "relief", "fog", or "contours" - see fusion_3d_panel.THREE_D_MODES
        self._3d_data_source = "auto"  # "auto", "rgb_only", or "fusion" - which base image THREE_D shades
        self._3d_fog_near_m = 0.3
        self._3d_fog_far_m = 4.0
        self._3d_contour_interval_m = 0.5

        # Throttle for pushing parallax perf metrics to the GUI - a display
        # metric, not something that needs updating every single frame.
        self._last_parallax_perf_update_time = 0.0
        self._parallax_perf_update_interval_s = 0.5
        # Same, for the Anomaly panel's Performance section.
        self._last_anomaly_perf_update_time = 0.0
        self._anomaly_perf_update_interval_s = 0.5
        # Cache for the main viewport's THREE_D display frame - see its
        # branch in the display_frame selection for why this is throttled
        # instead of recomputed every frame.
        self._last_3d_display_frame = None
        self._last_3d_display_time = 0.0

        # Throttle for per-ROI temperature stats (ROI Manager panel).
        # compute_statistics() does a percentile pass per ROI - profiled
        # elsewhere as the single largest cost in the whole analysis
        # pipeline for one region, so doing it for every active ROI (up to
        # auto_roi_max_count) belongs at a human-perceptible cadence, not
        # every render tick.
        self._last_roi_stats_time = 0.0
        self._roi_stats_interval_s = 1.0

        # New: Processing loop state
        self.timer = QTimer()
        # Qt's default CoarseTimer can coalesce/drift by several ms on
        # Windows (~15.6ms system tick) - a big fraction of an 8ms nominal
        # interval, which reads as uneven frame pacing ("jumpy") even when
        # the averaged fps looks fine over a 30-frame window. PreciseTimer
        # asks for real millisecond accuracy instead.
        self.timer.setTimerType(Qt.TimerType.PreciseTimer)
        self.timer.timeout.connect(self._process_frame_loop)
        self.frame_count = 0
        self.last_fps_time = time.time()
        self.frame_times = []
        self.smoothed_fps = 0.0
        self._health_check_counter = 0

        # thermal_analyzer.analyze() (stats/hot/cold/anomaly detection, plus
        # the 8-bit estimator when enabled) costs 10-40ms/frame on a
        # 640x512 frame. Running it inline on this thread capped video
        # rendering at that same rate regardless of CPU power, since a
        # single synchronous call blocks everything else in this loop
        # until it returns - more cores don't parallelize one sequential
        # call. See processing/threaded_analyzer.py: it now runs on its
        # own thread, and this loop just reads whatever its latest
        # completed result is, non-blocking, so video rendering is no
        # longer gated by analysis cost at all.
        self._last_analysis_results = None

        # Placeholders
        self.thermal_placeholder = None
        self.rgb_placeholder = None

        # Actual thermal capture resolution, tracked from live frames so the
        # GUI's overlay coordinate transform matches whatever camera is
        # connected (Boson, Tau2, Lepton — each with a different native
        # resolution and aspect ratio) instead of a hardcoded default.
        self._last_thermal_resolution = (640, 512)
        self._gui_thermal_resolution_synced = None

        # While True, _restart_threaded_capture() no-ops. autodiscover()
        # activates thermal and RGB in sequence, each activation firing a
        # camera_connected signal that would otherwise independently tear
        # down and rebuild the capture threads — once for thermal alone
        # (before RGB exists), again once RGB joins. Stopping a
        # ThreadedCameraCapture thread mid-warmup can outlast its 2s join
        # timeout, and stop() proceeds regardless of whether the thread
        # actually exited, so a fast-enough second rebuild can end up with
        # two threads briefly reading the same cv2.VideoCapture handle —
        # exactly the kind of transient instability observed as an RGB
        # camera failing its first several reads right after a dual-camera
        # startup. Set during autodiscover() so only one clean rebuild
        # happens, after both roles have settled.
        self._suppress_capture_restart = False

    def _init_controllers(self):
        """Initialize all controllers."""
        self.camera_state = CameraState()
        self.threaded_capture = None
        self._loop_idle_event = threading.Event()
        self.loop_pause_event = threading.Event()

        # Hot-plug watchdog (started in initialize())
        self._camera_monitor = None

        # Fusion controller
        self.fusion_controller = FusionController(
            initial_mode=self.config.fusion_mode,
            initial_alpha=self.config.fusion_alpha,
        )

        # ROI controller
        self.roi_controller = ROIController()

        # Radiometric controller
        self.radiometric_controller = RadiometricController()

        # Wire up controller callbacks
        self._wire_callbacks()

    def _wire_callbacks(self):
        """Wire up callbacks between controllers."""

        # Fusion state changes
        self.fusion_controller.on_state_change = self._on_fusion_state_change
        self.fusion_controller.on_mode_change = self._on_fusion_mode_change

        # ROI changes
        self.roi_controller.on_rois_changed = self._on_rois_changed

        # Radiometric changes
        self.radiometric_controller.on_state_change = self._on_radiometric_state_change

        bus = self.event_bus

        # --- Generic Camera Plugin Host Wiring ---
        bus.camera_command_requested.connect(self.plugin_host.execute_command_async)
        self.plugin_host.camera_command_result.connect(bus.camera_command_result)

        self.plugin_host.camera_connected.connect(self._on_camera_connected)
        self.plugin_host.camera_disconnected.connect(self._on_camera_disconnected)
        self.plugin_host.camera_connected.connect(bus.camera_connected)
        self.plugin_host.camera_disconnected.connect(bus.camera_disconnected)

        self.plugin_host.sdk_connected.connect(bus.sdk_connected)
        self.plugin_host.sdk_disconnected.connect(bus.sdk_disconnected)
        self.plugin_host.panel_ready.connect(bus.panel_ready)

        # --- Threshold ---
        bus.threshold_enabled_changed.connect(self.threshold_manager.set_enabled)
        bus.threshold_mode_changed.connect(self.threshold_manager.set_mode)
        bus.threshold_min_changed.connect(self.threshold_manager.set_min)
        bus.threshold_max_changed.connect(self.threshold_manager.set_max)
        bus.threshold_use_raw_changed.connect(self.threshold_manager.set_use_raw)
        bus.threshold_viz_changed.connect(self.threshold_manager.set_viz_mode)

        # --- Isotherm ---
        bus.isotherm_enabled_changed.connect(self.isotherm_manager.set_enabled)
        bus.isotherm_mode_changed.connect(self.isotherm_manager.set_mode)
        bus.isotherm_low_threshold_changed.connect(self.isotherm_manager.set_low_threshold)
        bus.isotherm_high_threshold_changed.connect(self.isotherm_manager.set_high_threshold)
        bus.isotherm_color_changed.connect(self.isotherm_manager.set_color)
        bus.isotherm_band_manager_set.connect(self.isotherm_manager.set_band_manager)
        bus.isotherm_multiband_changed.connect(self.isotherm_manager.set_multiband_mode)

        # --- Recording / Snapshots ---
        bus.recording_toggled.connect(self._bus_toggle_recording)
        bus.snapshot_requested.connect(self._bus_capture_snapshot)
        bus.freeze_toggled.connect(self.toggle_freeze)

        # --- Calibration ---
        bus.calibration_enabled_changed.connect(self.calibration_manager.set_calibration_enabled)
        bus.calibration_clear_requested.connect(self._bus_clear_calibration)
        bus.calibration_compute_requested.connect(self._bus_compute_calibration)
        bus.calibration_export_requested.connect(self._bus_export_calibration)
        bus.calibration_import_requested.connect(self._bus_import_calibration)
        bus.calibration_add_point_mode_changed.connect(
            self.calibration_manager.set_calibration_add_point_mode
        )
        bus.calibration_point_add_requested.connect(self.add_calibration_point)
        bus.calibration_point_removed.connect(self._bus_remove_calibration_point)

        # --- View / Fusion ---
        bus.view_mode_cycled.connect(self.cycle_view_mode)
        bus.palette_cycled.connect(self.cycle_palette)
        bus.palette_set.connect(self.set_palette)
        bus.fusion_mode_changed.connect(self.set_fusion_mode)
        bus.fusion_alpha_changed.connect(self.set_fusion_alpha)
        bus.fusion_priority_changed.connect(self.set_fusion_priority)
        bus.fusion_strength_changed.connect(self.set_fusion_strength)
        bus.fusion_fuzziness_changed.connect(self.set_fusion_fuzziness)
        bus.fusion_color_mode_changed.connect(self.set_fusion_color_mode)
        bus.edge_strength_changed.connect(self.set_edge_strength)
        bus.edge_fuzziness_changed.connect(self.set_edge_fuzziness)
        bus.edge_color_changed.connect(self.set_edge_color)
        bus.detail_strength_changed.connect(self.set_detail_strength)
        bus.detail_quality_changed.connect(self.set_detail_quality)
        bus.laplacian_gpu_changed.connect(self.set_laplacian_gpu)
        bus.laplacian_cpu_scale_changed.connect(self.set_laplacian_cpu_scale)
        bus.fusion_3d_strength_changed.connect(self.set_3d_relief_strength)
        bus.fusion_3d_mode_changed.connect(self.set_3d_mode)
        bus.fusion_3d_data_source_changed.connect(self.set_3d_data_source)
        bus.fusion_3d_fog_range_changed.connect(self.set_3d_fog_range)
        bus.fusion_3d_contour_interval_changed.connect(self.set_3d_contour_interval)

        # --- ROI ---
        bus.auto_roi_requested.connect(self.auto_roi_detect)
        bus.clear_rois_requested.connect(self.clear_rois)
        bus.roi_deleted.connect(
            lambda roi_id: self.delete_roi(roi_id) if hasattr(self, 'delete_roi')
            else (self.roi_manager.delete_roi(roi_id) if hasattr(self, 'roi_manager') else None)
        )
        bus.roi_palette_changed.connect(
            lambda roi_id, palette: self.set_roi_palette(roi_id, palette)
            if hasattr(self, 'set_roi_palette') else None
        )
        bus.roi_palette_cleared.connect(
            lambda roi_id: self._bus_clear_roi_palette(roi_id)
        )

        # --- Anomaly processor settings ---
        bus.anomaly_priority_toggled.connect(self.toggle_anomaly_priority)
        bus.anomaly_types_changed.connect(self.set_enabled_anomaly_types)
        bus.anomaly_fade_strength_changed.connect(self._bus_set_fade_strength)
        bus.anomaly_fade_distance_changed.connect(self._bus_set_fade_distance)
        bus.anomaly_motion_threshold_changed.connect(self._bus_set_motion_threshold)
        bus.anomaly_edge_thresholds_changed.connect(self._bus_set_edge_thresholds)
        bus.hot_spot_percentile_changed.connect(self._bus_set_hot_spot_percentile)
        bus.cold_spot_percentile_changed.connect(self._bus_set_cold_spot_percentile)
        bus.min_anomaly_size_changed.connect(self._bus_set_min_anomaly_size)
        bus.max_hot_spots_changed.connect(self._bus_set_max_hot_spots)
        bus.max_cold_spots_changed.connect(self._bus_set_max_cold_spots)

        # --- Analyzer / Spotmeter / Estimation ---
        bus.spotmeter_enabled_changed.connect(self._bus_set_spotmeter_enabled)
        bus.spotmeter_mode_changed.connect(self._bus_set_spotmeter_mode)
        bus.estimation_8bit_enabled_changed.connect(self._bus_set_estimation_enabled)
        bus.estimation_range_changed.connect(self._bus_set_estimation_range)
        bus.calibrate_single_point_requested.connect(self._bus_calibrate_single_point)
        bus.calibrate_two_point_requested.connect(self._bus_calibrate_two_point)
        bus.sensor_temps_requested.connect(self._bus_get_sensor_temps)

        # --- Radiometric ---
        bus.emissivity_changed.connect(self.set_emissivity)
        bus.atmospheric_temperature_changed.connect(self.set_atmospheric_temperature)
        bus.atmospheric_transmission_changed.connect(self.set_atmospheric_transmission)
        bus.temperature_unit_changed.connect(self.set_temperature_unit)
        bus.radiometric_enabled_changed.connect(self.enable_radiometric)
        bus.temperature_range_changed.connect(
            lambda low, high: self.radiometric_controller.set_temperature_range(low, high)
        )
        bus.radiometric_range_apply_requested.connect(
            lambda low, high: self.radiometric_controller.set_temperature_range(low, high)
        )
        bus.radiometric_method_changed.connect(self._bus_set_radiometric_method)

        # --- Camera management ---
        bus.device_changed.connect(
            lambda name: self.set_device(name) if hasattr(self, 'set_device') else None
        )

        # --- Parallax ---
        bus.parallax_toggled.connect(
            lambda en: self.enable_parallax_compensation(en) if hasattr(self, 'enable_parallax_compensation') else None
        )
        bus.parallax_baseline_changed.connect(
            lambda v: self.set_parallax_baseline(v) if hasattr(self, 'set_parallax_baseline') else None
        )
        bus.parallax_method_changed.connect(
            lambda m: self.set_parallax_depth_method(m) if hasattr(self, 'set_parallax_depth_method') else None
        )
        bus.depth_map_display_toggled.connect(self._bus_depth_map_display_toggled)
        bus.displacement_display_toggled.connect(self._bus_displacement_display_toggled)
        bus.parallax_shift_changed.connect(
            lambda dx, dy: self.set_parallax_shift(dx, dy) if hasattr(self, 'set_parallax_shift') else None
        )
        bus.parallax_auto_alignment_requested.connect(self._bus_parallax_auto_alignment_requested)
        bus.parallax_geometry_optics_changed.connect(
            lambda optics: self.set_parallax_camera_optics(optics) if hasattr(self, 'set_parallax_camera_optics') else None
        )
        bus.parallax_zoom_changed.connect(
            lambda z: self.set_parallax_zoom(z) if hasattr(self, 'set_parallax_zoom') else None
        )
        bus.parallax_correction_target_changed.connect(
            lambda t: self.set_parallax_correction_target(t) if hasattr(self, 'set_parallax_correction_target') else None
        )
        bus.parallax_rgb_target_max_width_changed.connect(
            lambda w: self.set_parallax_rgb_target_max_width(w) if hasattr(self, 'set_parallax_rgb_target_max_width') else None
        )

        # --- Gradient Overlay ---
        bus.gradient_enabled_changed.connect(
            lambda v: self.gradient_processor.update_settings(enabled=v)
            if self.gradient_processor else None
        )
        bus.gradient_mode_changed.connect(
            lambda v: self.gradient_processor.update_settings(mode=v)
            if self.gradient_processor else None
        )
        bus.gradient_threshold_changed.connect(
            lambda v: self.gradient_processor.update_settings(threshold=v)
            if self.gradient_processor else None
        )
        bus.gradient_colormap_changed.connect(
            lambda v: self.gradient_processor.update_settings(colormap=v)
            if self.gradient_processor else None
        )

        # --- Baseline ---
        bus.baseline_lock_toggled.connect(self.lock_baseline)

    def _on_camera_connected(self, role: str, capabilities: dict):
        logger.info(f"PluginHost camera connected: {role} (caps: {capabilities})")
        if role == 'thermal':
            self.camera_state.thermal_connected = True
            is_rad = capabilities.get('radiometric', False)
            self.camera_state.is_radiometric = is_rad
            self.radiometric_controller.state.capable = is_rad
            self.radiometric_controller.state.enabled = is_rad
            self.radiometric_controller.state.mode = "16-bit Radiometric" if is_rad else "8-bit AGC"
            if self.thermal_analyzer:
                self.thermal_analyzer.set_radiometric_mode(is_rad)
            # Setting the dataclass fields above doesn't itself notify
            # listeners (only the controller's own setter methods do) - the
            # radiometric panel's "Active Mode" banner was stuck on its
            # construction-time "Checking..." placeholder forever because
            # nothing ever pushed a first real state to it. Reuse the same
            # state-change handler camera connect uses everywhere else.
            self._on_radiometric_state_change(self.radiometric_controller.state)

            active = self.plugin_host.get_active_camera('thermal')
            if active:
                self.camera_state.is_flir_boson = (active.plugin.plugin_id == 'flir_boson')
                self.camera_state.is_lepton = (active.plugin.plugin_id == 'flir_lepton')
                self.camera_state.is_firefly = (active.plugin.plugin_id == 'flir_firefly')
                self.camera_state.thermal_device_id = active.match.device_index

                if self.radiometric_controller and hasattr(active, 'backend'):
                    self.radiometric_controller.set_thermal_camera(active.backend)

            self._restart_threaded_capture()

        elif role == 'rgb':
            self.camera_state.rgb_available = True
            active = self.plugin_host.get_active_camera('rgb')
            if active:
                self.camera_state.rgb_device_id = active.match.device_index

                # Wire real hardware depth into parallax correction (depth
                # method "realsense") whenever a RealSense camera becomes
                # the active RGB source - it's the only backend with a
                # get_depth_frame() to offer. Cleared on disconnect below,
                # regardless of which RGB camera disconnects (harmless if
                # it wasn't the one providing it).
                if active.plugin.plugin_id == 'intel_realsense':
                    backend = active.backend
                    if self.parallax_compensator and hasattr(backend, 'get_depth_frame'):
                        self.parallax_compensator.set_hardware_depth_source(backend.get_depth_frame)
                        logger.info("RealSense camera active - wired as hardware depth source for parallax correction")
                    if hasattr(backend, 'get_point_cloud'):
                        self._gui_invoke("set_fusion_3d_hardware_available", True)

            self._restart_threaded_capture()

        self._gui_invoke("update_camera_status", self.camera_state)

    def _on_camera_disconnected(self, role: str):
        logger.info(f"PluginHost camera disconnected: {role}")
        if role == 'thermal':
            self.camera_state.thermal_connected = False
            self.camera_state.is_flir_boson = False
            self.camera_state.is_lepton = False
            self.camera_state.is_firefly = False
            self.camera_state.is_radiometric = False
            self.camera_state.thermal_device_id = None
            self.radiometric_controller.state.capable = False
            self.radiometric_controller.state.enabled = False
            self.radiometric_controller.state.mode = '8-bit AGC'
            self.radiometric_controller.state.estimation_enabled = False
            if self.thermal_analyzer:
                self.thermal_analyzer.set_radiometric_mode(False)
            self._on_radiometric_state_change(self.radiometric_controller.state)
            self._restart_threaded_capture()
        elif role == 'rgb':
            self.camera_state.rgb_available = False
            self.camera_state.rgb_device_id = None
            if self.parallax_compensator:
                self.parallax_compensator.set_hardware_depth_source(None)
            self._gui_invoke("set_fusion_3d_hardware_available", False)
            self._restart_threaded_capture()

        self._gui_invoke("show_camera_lost_notification", role)
        self._gui_invoke("update_camera_status", self.camera_state)

    # ------------------------------------------------------------------
    # Camera hot-plug watchdog
    # ------------------------------------------------------------------
    def _start_camera_monitor(self):
        """Start the background camera monitor for hot-plug detection."""
        from thermal_inspection.cameras.camera_monitor import CameraMonitor
        self._camera_monitor = CameraMonitor(
            scan_interval=2.5,
            callback=self._on_monitor_event,
        )
        # Mark currently active devices so the monitor skips re-probing them
        state = self.camera_state
        if state.thermal_device_id is not None:
            self._camera_monitor.mark_device_active(state.thermal_device_id)
        if state.rgb_device_id is not None:
            self._camera_monitor.mark_device_active(state.rgb_device_id)
        self._camera_monitor.start()
        logger.info("Camera hot-plug monitor started")

    def _on_monitor_event(self, event):
        """
        Handle camera connect/disconnect events from CameraMonitor (background thread).

        Type-handling logic:
        - CONNECTED: determine likely role from CameraInfo.camera_type, auto-assign
          if a slot is vacant, otherwise ask the user via the GUI.
        - DISCONNECTED: update controller state, notify GUI.

        All GUI calls are routed through _gui_invoke so they execute on the
        Qt main thread (QueuedConnection).
        """
        from thermal_inspection.cameras.camera_monitor import CameraEventType
        from thermal_inspection.cameras.camera_detector import CameraType

        if event.event_type == CameraEventType.CONNECTED:
            dev_id = event.device_id
            cam    = event.camera_info          # CameraInfo or None

            name   = cam.name       if cam else f"Device {dev_id}"
            res    = (f"{cam.resolution[0]}x{cam.resolution[1]}"
                      if cam else "unknown")
            ctype  = cam.camera_type if cam else CameraType.RGB   # default RGB

            logger.info(
                f"Hot-plug CONNECTED: device {dev_id}  name='{name}'  "
                f"res={res}  type={ctype.value}"
            )

            state = self.camera_state

            # ── Auto-assign if a slot is vacant ──────────────────────────
            if ctype == CameraType.THERMAL and not state.thermal_connected:
                logger.info(
                    f"Hot-plug: auto-assigning device {dev_id} as THERMAL "
                    "(thermal slot vacant, camera looks thermal)"
                )
                import threading
                threading.Thread(
                    target=self._hotplug_assign, args=(dev_id, 'thermal'),
                    daemon=True, name=f"HotPlugAssign-{dev_id}"
                ).start()

            elif ctype == CameraType.RGB and not state.rgb_available:
                logger.info(
                    f"Hot-plug: auto-assigning device {dev_id} as RGB "
                    "(RGB slot vacant)"
                )
                import threading
                threading.Thread(
                    target=self._hotplug_assign, args=(dev_id, 'rgb'),
                    daemon=True, name=f"HotPlugAssign-{dev_id}"
                ).start()

            else:
                # Both slots occupied or type is ambiguous — let the user decide
                suggested_role = ctype.value.lower() if ctype != CameraType.UNKNOWN else 'rgb'
                self._gui_invoke(
                    "show_camera_connected_notification",
                    dev_id, name, res, suggested_role
                )

        elif event.event_type == CameraEventType.DISCONNECTED:
            dev_id = event.device_id
            logger.info(f"Hot-plug DISCONNECTED: device {dev_id}")

            state = self.camera_state
            role  = None
            if dev_id == state.thermal_device_id:
                role = 'thermal'
            elif dev_id == state.rgb_device_id:
                role = 'rgb'

            if role:
                self.plugin_host.deactivate_camera(role)

            # Remove from monitor's active set so it can re-detect it later
            if self._camera_monitor:
                self._camera_monitor.mark_device_inactive(dev_id)

            if role:
                self._gui_invoke("show_camera_lost_notification", role)

    def _hotplug_assign(self, device_id: int, role: str):
        """
        Worker executed in a daemon thread when a new camera is auto-assigned.
        Opens the device and slots it in; notifies the GUI on completion.
        """
        ok = self.assign_camera_to_slot(device_id, role)
        state = self.camera_state

        if ok and self._camera_monitor:
            self._camera_monitor.mark_device_active(device_id)

        logger.info(
            f"Hot-plug assign device {device_id} -> '{role}': "
            f"{'OK' if ok else 'FAILED'}"
        )
        self._gui_invoke(
            "show_hotplug_result",
            device_id, role, ok
        )

    def _gui_invoke(self, method_name: str, *args):
        """
        Thread-safe GUI method call.  Uses QTimer.singleShot to marshal the
        call onto the Qt main thread — works with any Python callable stored
        on the GUI object, without needing Q_ARG wrappers.
        """
        if self.gui is None:
            return
        gui_ref = self.gui      # capture reference for lambda closure
        if not hasattr(gui_ref, method_name):
            return
        try:
            from PyQt6.QtCore import QTimer
            method = getattr(gui_ref, method_name)
            QTimer.singleShot(0, lambda: method(*args))
        except Exception as exc:
            logger.debug(f"_gui_invoke {method_name} failed: {exc}")

    def assign_camera_to_slot(self, device_id: int, role: str) -> bool:
        logger.info(f"Assigning device {device_id} to slot '{role}'")
        self._loop_idle_event.clear()
        self.loop_pause_event.set()
        if not self._loop_idle_event.wait(timeout=0.5):
            logger.warning("Frame loop did not ack pause within 500 ms")

        self._stop_threaded_capture()
        try:
            # registry.discover() returns raw CameraPluginMatch candidates
            # (has device_index). autodiscover() returns already-activated
            # ActiveCamera objects (no device_index) and would also activate
            # its own best-guess cameras as a side effect of this lookup.
            matches = self.plugin_host.registry.discover()
            match = next((m for m in matches if m.device_index == device_id), None)

            if match:
                ok = self.plugin_host.activate_camera(role, match)
            else:
                logger.warning(f"Could not discover device_id {device_id} to assign")
                ok = False

            if ok and self._camera_monitor:
                self._camera_monitor.mark_device_active(device_id)
            return ok
        finally:
            self._restart_threaded_capture()
            self.loop_pause_event.clear()
            self._loop_idle_event.clear()
            self._gui_invoke("update_camera_status", self.camera_state)

    def reconnect_camera(self, role: str) -> bool:
        logger.info(f"reconnect_camera: role='{role}'")
        dev_id = self.camera_state.thermal_device_id if role == 'thermal' else self.camera_state.rgb_device_id
        if dev_id is None:
            return False
        return self.assign_camera_to_slot(dev_id, role)

    def _on_camera_lost(self, role: str):
        """Called by CameraController when a camera disconnects mid-stream."""
        logger.warning(f"Camera lost: {role}")
        self._gui_invoke("show_camera_lost_notification", role)
        self._gui_invoke("update_camera_status", self.camera_state)

    def _on_camera_reconnected(self, role: str):
        """Called by CameraController when a camera reconnects."""
        logger.info(f"Camera reconnected: {role}")
        self._gui_invoke("update_camera_status", self.camera_state)

    # (duplicate reconnect_camera removed — see definition above at line 390)


    def _on_fusion_state_change(self, state: FusionState):
        """Handle fusion state changes."""
        logger.debug(f"Fusion state changed: mode={state.mode}, alpha={state.alpha}")

    def _on_fusion_mode_change(self, mode: str):
        """Handle fusion mode change."""
        if self.gui and hasattr(self.gui, 'control_panel') and hasattr(self.gui.control_panel, 'update_fusion_mode_button'):
            self.gui.control_panel.update_fusion_mode_button(mode)

    def _on_rois_changed(self, roi_data: dict):
        """Handle structural ROI changes (added/removed/cleared).

        `roi_data` is `{'count': N, 'rois': [...]}` from
        `ROIController._get_roi_data()` - a list, not the roi_id -> stats
        mapping `update_roi_data()` expects (that comes from the periodic
        temperature-stats push in `_process_frame_loop` instead).
        """
        if self.gui and hasattr(self.gui, 'update_rois'):
            self.gui.update_rois(roi_data.get('rois', []))

    def _on_radiometric_state_change(self, state: RadiometricState):
        """Handle radiometric state changes."""
        if self.gui and hasattr(self.gui, 'radiometric_panel'):
            self.gui.radiometric_panel.set_radiometric_status(
                state.capable, state.enabled, state.mode
            )

            active = self.radiometric_controller.get_active_mode()
            # get_active_mode()'s vocabulary ('radiometric'/'estimated'/'agc',
            # accuracy as 'high'/'medium'/'relative') and the banner's
            # ('16bit'/'8bit'/'none', accuracy as a literal +/-X C string)
            # were never reconciled - translate between them here.
            mode_map = {'radiometric': '16bit', 'estimated': '8bit', 'agc': 'none'}
            accuracy_map = {'radiometric': '±2°C', 'estimated': '±5-10°C', 'agc': 'N/A'}
            self.gui.radiometric_panel.update_active_mode_status(
                mode_map.get(active['mode'], 'none'),
                accuracy_map.get(active['mode'], 'N/A'),
                active['description']
            )

    def initialize(self) -> bool:
        """
        Initialize all application components.

        The GUI opens immediately; camera detection runs in a background
        thread so the window appears without delay.

        Returns:
            True if non-camera initialisation succeeded
        """
        logger.info("=" * 80)
        logger.info("Thermal Inspection Fusion Tool")
        logger.info("=" * 80)

        try:
            # 1. Processing components (fast, no I/O)
            self._init_processing()

            # 2. Wire controllers
            self._connect_controllers()

            # 3. Init placeholders so the frame loop can show something immediately
            self._init_placeholders()

            # 4. Open the GUI right away — don't wait for cameras
            if not self.config.headless:
                self._init_gui()

            self.initialized = True
            logger.info("Core init complete — deferring camera detection to background")
            return True

        except Exception as e:
            logger.error(f"Initialization failed: {e}", exc_info=True)
            return False

    def _init_processing(self):
        """Initialize processing components."""
        # Import processing modules from new package structure
        try:
            from .processing import FusionProcessor, ThermalProcessor, ThermalAnalyzer
            from .processing import ROIManager, PaletteManager

            # Create processors
            self.fusion_processor = FusionProcessor()
            self.fusion_controller.set_fusion_processor(self.fusion_processor)

            self.thermal_processor = ThermalProcessor({'device': self.config.device})
            self.thermal_analyzer = ThermalAnalyzer()

            from .utils.thermal_estimator import ThermalTemperatureEstimator
            self.thermal_estimator = ThermalTemperatureEstimator()
            self._last_fpa_temp_c: Optional[float] = None
            # hot/cold-spot detection and frame stats live in thermal_analyzer,
            # which needs the estimator directly to convert AGC values itself.
            self.thermal_analyzer.thermal_estimator = self.thermal_estimator

            from .processing.threaded_analyzer import ThreadedAnalyzer
            self.threaded_analyzer = ThreadedAnalyzer(self.thermal_analyzer)
            self.threaded_analyzer.start()

            self.roi_manager = ROIManager()
            self.palette_manager = PaletteManager({'default_palette': self.config.palette})

            from .processing.gradient_processor import GradientProcessor
            self.gradient_processor = GradientProcessor()

            logger.info("Processing components initialized")

        except ImportError as e:
            logger.warning(f"Some processing components not available: {e}")

        # Radiometric calibrator initialization is now handled by CalibrationManager

        # Parallax compensator
        try:
            from .processing.parallax_compensator import ParallaxCompensator
            self.parallax_compensator = ParallaxCompensator()
            logger.info("ParallaxCompensator initialized")
        except ImportError as e:
            logger.warning(f"ParallaxCompensator not available: {e}")
            self.parallax_compensator = None

        # Media recorder
        try:
            from .core.media_manager import MediaManager
            self.media_manager = MediaManager()
            logger.info("MediaManager initialized")
        except Exception as e:
            logger.warning(f"Media manager not available: {e}")
            self.media_manager = None

    def _connect_controllers(self):
        """Connect controllers to processing components."""
        # ROI controller
        if self.roi_manager:
            self.roi_controller.set_roi_manager(self.roi_manager)
        if self.palette_manager:
            self.roi_controller.set_palette_manager(self.palette_manager)
        if self.thermal_analyzer:
            self.roi_controller.set_thermal_analyzer(self.thermal_analyzer)

        # Radiometric controller
        if self.thermal_camera:
            self.radiometric_controller.set_thermal_camera(
                self.thermal_camera
            )
        if self.thermal_analyzer:
            self.radiometric_controller.set_thermal_analyzer(self.thermal_analyzer)

    def _init_gui(self):
        """Initialize GUI components."""
        if self.config.gui_type == 'qt' and self.qt_app:
            try:
                from .gui import InspectionAppWindow
                self.gui = InspectionAppWindow(self)
                self.gui.show()
                logger.info("Qt GUI initialized")
            except ImportError as e:
                logger.warning(f"Qt GUI not available: {e}")

    def run(self):
        """Run the main application loop."""
        if not self.initialized:
            logger.error("Application not initialized")
            return

        self.running = True
        logger.info("Starting main loop")

        # Start frame loop immediately in placeholder mode.
        # threaded_capture.get_frames() returns the latest cached frame
        # non-blocking, so this interval isn't "the" frame rate — it's just
        # how often we poll for one. 33ms hardcoded a ~30fps ceiling on every
        # camera combination, including the 60fps thermal path; poll fast
        # enough that actual throughput is bounded by real per-frame work,
        # not this timer.
        self.timer.start(8)

        # Kick off camera detection in background after Qt is running
        if self.qt_app:
            from PyQt6.QtCore import QTimer as _QT
            _QT.singleShot(150, self._init_cameras_async)
        else:
            # Headless: run detection synchronously then start loop
            self._init_cameras_sync()

        try:
            if self.qt_app:
                sys.exit(self.qt_app.exec())
            else:
                self._run_headless_loop()

        except KeyboardInterrupt:
            logger.info("Interrupted by user")
        finally:
            self.cleanup()

    def _init_cameras_async(self):
        """
        Trigger camera detection. Called 150 ms after the Qt event loop
        starts so the window has time to paint before we touch any hardware.
        Runs on the main thread so the COM apartment stays alive!
        """
        self._gui_invoke("show_camera_startup_overlay", True)
        # Call it directly on the main thread
        self._init_cameras_sync()

    def _stop_threaded_capture(self):
        if getattr(self, 'threaded_capture', None):
            self.threaded_capture.stop()
            self.threaded_capture = None

    def _restart_threaded_capture(self):
        if self._suppress_capture_restart:
            logger.debug("Threaded capture restart suppressed (mid-autodiscover)")
            return
        self._stop_threaded_capture()
        try:
            from thermal_inspection.cameras.threaded_camera_capture import DualThreadedCameraCapture
            thermal_active = self.plugin_host.get_active_camera('thermal')
            rgb_active = self.plugin_host.get_active_camera('rgb')

            t_backend = thermal_active.backend if thermal_active else None
            r_backend = rgb_active.backend if rgb_active else None

            if t_backend or r_backend:
                self.threaded_capture = DualThreadedCameraCapture(
                    thermal_camera=t_backend,
                    rgb_camera=r_backend if not self.config.disable_rgb else None
                )
                self.threaded_capture.start()
        except Exception as e:
            logger.warning(f"Could not start threaded capture: {e}")
            self.threaded_capture = None

    def _init_cameras_sync(self):
        """
        Synchronous camera initialisation — safe to call from any thread.
        Uses CameraPluginHost to detect and activate cameras.
        """
        logger.info("Background camera detection starting via PluginHost...")
        self._suppress_capture_restart = True
        try:
            self.plugin_host.autodiscover()
        finally:
            self._suppress_capture_restart = False
        # One clean rebuild with both roles already settled, instead of the
        # per-camera rebuilds autodiscover()'s own connect signals would
        # have triggered.
        self._restart_threaded_capture()

        thermal_ok = self.plugin_host.is_connected('thermal')
        rgb_ok = self.plugin_host.is_connected('rgb')

        if not thermal_ok and not rgb_ok:
            logger.warning("No cameras detected — running in placeholder mode")

        # Auto-switch view mode: if no thermal but RGB is available, show RGB feed
        if not thermal_ok and rgb_ok and self.view_mode == ViewMode.THERMAL_ONLY:
            logger.info("No thermal camera found but RGB is available — auto-switching view mode to RGB_ONLY")
            self.view_mode = ViewMode.RGB_ONLY
            self._gui_invoke("_sync_view_mode_button", self.view_mode)

        self._gui_invoke("show_camera_startup_overlay", False)
        self._start_camera_monitor()
        logger.info(f"Camera init done: thermal={thermal_ok} rgb={rgb_ok}")
        self._gui_invoke("update_camera_status", self.camera_state)

    def _run_headless_loop(self):
        """Run headless processing loop."""
        import time

        while self.running:
            # Process frames
            # This would be expanded with actual processing logic
            time.sleep(0.1)

    def cleanup(self):
        """Clean up resources."""
        logger.info("Cleaning up...")
        self.running = False
        self.timer.stop()
        if getattr(self, 'threaded_analyzer', None):
            self.threaded_analyzer.stop()

        # Stop any active recording cleanly before camera release
        if self.media_manager:
            self.media_manager.cleanup()

        # Release cameras. release_all() deactivates each role in turn, and
        # each deactivation fires a camera_disconnected signal that would
        # otherwise rebuild the capture threads on its own — with whichever
        # camera hasn't been deactivated yet — moments before that one gets
        # torn down too. That orphaned thread reads from a closing/closed
        # cv2.VideoCapture and fails hard (this is exactly what produced the
        # RGB "10 consecutive read failures" burst diagnosed during this
        # session). Capture was already stopped cleanly just above, and
        # there is nothing to rebuild for at shutdown, so suppress it.
        if self._camera_monitor is not None:
            self._camera_monitor.stop()
        self._stop_threaded_capture()
        self._suppress_capture_restart = True
        try:
            self.plugin_host.release_all()
        finally:
            self._suppress_capture_restart = False

        logger.info("Cleanup complete")

    @property
    def thermal_camera(self):
        """Get thermal camera instance."""
        active = self.plugin_host.get_active_camera('thermal')
        return active.backend if active else None

    @property
    def rgb_camera(self):
        """Get RGB camera instance."""
        active = self.plugin_host.get_active_camera('rgb')
        return active.backend if active else None

    # Public API methods that delegate to controllers

    def set_fusion_mode(self, mode: str):
        """Set fusion mode."""
        self.fusion_controller.set_mode(mode)

    def set_fusion_alpha(self, alpha: float):
        """Set fusion alpha."""
        self.fusion_controller.set_alpha(alpha)

    def cycle_fusion_mode(self):
        """Cycle to next fusion mode."""
        return self.fusion_controller.cycle_mode()

    def swap_cameras(self):
        """Swap camera assignments."""
        current_thermal = self.camera_state.thermal_device_id or 0
        current_rgb = self.camera_state.rgb_device_id
        if current_rgb is None:
            current_rgb = 1 if current_thermal == 0 else 0
        threading.Thread(
            target=self.reassign_cameras,
            args=(current_rgb, current_thermal),
            daemon=True
        ).start()
        return True

    def auto_roi_detect(self):
        """Auto-detect ROIs based on thermal temperature gradients."""
        frame = getattr(self, '_last_thermal_frame', None)
        if frame is None:
            logger.warning("Cannot auto-detect ROIs: no thermal frame available")
            return
        if not self.roi_controller:
            logger.warning("Cannot auto-detect ROIs: ROI controller not initialized")
            return
        temp_count, grad_count = self.roi_controller.auto_detect(frame)
        logger.info(f"Auto-detected {temp_count} temperature + {grad_count} gradient ROIs")

    def clear_rois(self):
        """Clear all ROIs."""
        self.roi_controller.clear_all()

    def set_temperature_unit(self, unit: str):
        """Set temperature display unit."""
        self.radiometric_controller.set_temperature_unit(unit)

    def enable_radiometric(self, enable: bool) -> bool:
        """
        Enable/disable radiometric mode.

        The active thermal plugin owns the actual switching mechanism (SDK
        calls, backend swap, whatever a given camera needs) - this only
        asks for it and reflects the real outcome. It used to go through
        radiometric_controller.enable_radiometric(), which called
        self.thermal_camera.enable_radiometric() on the backend object;
        that backend no longer owns an SDK connection at all (disabled to
        fix a port conflict with the plugin's own connection - see
        BosonPlugin.create_backend), so that path was silently a no-op.
        """
        result = self.plugin_host.execute_command('thermal', 'set_radiometric_mode', {'enabled': enable})
        success = result.get('success', False)
        actual_enabled = enable if success else self.radiometric_controller.state.enabled

        self.radiometric_controller.state.enabled = actual_enabled
        self.camera_state.is_radiometric = actual_enabled and self.radiometric_controller.state.capable
        if self.thermal_analyzer:
            self.thermal_analyzer.set_radiometric_mode(self.camera_state.is_radiometric)
        self._on_radiometric_state_change(self.radiometric_controller.state)

        if self.gui:
            for panel in getattr(self.gui, 'camera_panels', {}).values():
                if hasattr(panel, 'update_radiometric_mode_status'):
                    panel.update_radiometric_mode_status(actual_enabled, success)

        if not success:
            logger.warning(f"set_radiometric_mode({enable}) failed: {result.get('error')}")
        return success

    def reassign_cameras(self, thermal_id: int, rgb_id: int):
        """Reassign camera device IDs."""
        if self.camera_state.reconfiguring:
            return False
        self.camera_state.reconfiguring = True
        self.loop_pause_event.set()
        try:
            self.config.thermal_device = thermal_id
            self.config.rgb_device = rgb_id
            time.sleep(0.1)

            self._stop_threaded_capture()
            # See cleanup()'s comment: deactivating thermal and rgb one at a
            # time each fires a disconnect signal that would otherwise
            # rebuild capture with whichever role is still active, right
            # before that one is torn down too.
            self._suppress_capture_restart = True
            try:
                self.plugin_host.deactivate_camera('thermal')
                self.plugin_host.deactivate_camera('rgb')
            finally:
                self._suppress_capture_restart = False

            time.sleep(1.0)
            self._init_cameras_sync()
            return True
        finally:
            self.camera_state.reconfiguring = False
            self.loop_pause_event.clear()
            self._gui_invoke("update_camera_status", self.camera_state)

    def detect_cameras(self) -> list:
        """
        Run a fresh camera detection scan and return all CameraInfo objects.
        Does NOT open or reinitialise any camera — detection only.
        """
        from thermal_inspection.cameras.camera_detector import CameraDetector
        from thermal_inspection.cameras.device_scanner import invalidate_cache

        # An explicit rescan must re-probe hardware, not replay the cache.
        invalidate_cache()

        skip_ids = []
        state = self.camera_state
        if state.thermal_device_id is not None:
            skip_ids.append(state.thermal_device_id)
        if state.rgb_device_id is not None:
            skip_ids.append(state.rgb_device_id)

        return CameraDetector.detect_all_cameras(
            skip_device_ids=skip_ids,
            register_cameras=True
        )

    def set_camera_role(self, device_id: int, role: str):
        """
        Manually override the role of a detected camera in the registry.

        Args:
            device_id: OpenCV device index of the camera.
            role: 'thermal', 'rgb', or 'unassigned'
        """
        from thermal_inspection.cameras.camera_registry import get_camera_registry, CameraRole
        registry = get_camera_registry()
        try:
            camera_role = CameraRole(role)
        except ValueError:
            import logging
            logging.getLogger(__name__).warning(f"Unknown camera role '{role}' – ignoring")
            return
        registry.set_camera_role(device_id, camera_role, manual=True)

    def apply_camera_roles(self, thermal_id, rgb_id):
        """
        Apply role reassignment then reinitialise cameras.

        Safe to call from any thread — the GUI dialog runs this in a
        QThread worker so the UI stays responsive during the 2 s OS
        settle wait inside reassign_cameras.

        Either argument may be None (thermal-only or RGB-only mode).
        Updates the config cache so the next startup uses the new IDs.

        Returns:
            True if at least one camera opened successfully.
        """
        from thermal_inspection.utils.config import get_config
        cfg = get_config()
        cfg.set('thermal_device_id', thermal_id, save=True)
        cfg.set('rgb_device_id',     rgb_id,     save=True)

        state = self.camera_state
        t_id = thermal_id if thermal_id is not None else state.thermal_device_id
        r_id = rgb_id     if rgb_id     is not None else state.rgb_device_id

        return self.reassign_cameras(
            t_id if t_id is not None else 0,
            r_id if r_id is not None else 1,
        )

    def trigger_ffc(self):
        """Trigger Flat Field Correction (FFC)."""
        return self.plugin_host.execute_command("thermal", "ffc")

    def _init_placeholders(self):
        """Pre-allocate placeholder frames for fallback mode."""
        w, h = self.config.width, self.config.height

        # Thermal placeholder (ironbow-ish gradient with text)
        self.thermal_placeholder = np.zeros((h, w, 3), dtype=np.uint8)
        cv2.putText(self.thermal_placeholder, "NO THERMAL SIGNAL", (w//4, h//2),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)

        # RGB placeholder (dark gray with text)
        self.rgb_placeholder = np.full((h, w, 3), 40, dtype=np.uint8)
        cv2.putText(self.rgb_placeholder, "NO RGB SIGNAL", (w//3, h//2),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (200, 200, 200), 2)

    def _auto_cycle_fusion_modes_tick(self):
        """
        Self-drive through every fusion mode when --auto-cycle-fusion-modes
        is set, instead of requiring someone to click through the UI. Each
        tick just checks a deadline - cheap enough to call unconditionally
        from the render loop, and it's a no-op (single None check) when the
        flag isn't set.

        Written for automated performance testing (e.g. sweeping fusion_ms/
        fps/jitter across every mode without a human present at the
        keyboard) - not something normal runs should enable.
        """
        interval = self.config.auto_cycle_fusion_modes
        if interval is None:
            return

        if self.fusion_processor is None:
            return  # cameras/processing not initialized yet

        # Re-asserted every tick, not just once at start: something else in
        # GUI/config initialization was observed overriding view_mode back
        # to a persisted setting (e.g. Picture-in-Picture) shortly after
        # this set it to Fusion once, which silently made the whole sweep
        # exercise _picture_in_picture() instead of fusion_processor.process()
        # for every mode after the first - fusion_mode was cycling correctly
        # the whole time, but the render loop was never actually taking the
        # Fusion-view code path that reads it. This is a testing/automation
        # feature owning view_mode outright for its duration is the
        # pragmatic fix, rather than chasing down every place that might
        # touch it.
        self.view_mode = ViewMode.FUSION

        now = time.time()

        if self._auto_cycle_modes is None:
            # First tick: capture the mode list.
            self._auto_cycle_modes = self.fusion_processor.get_available_modes()
            self._auto_cycle_idx = 0
            self._auto_cycle_deadline = now + interval
            mode = self._auto_cycle_modes[0]
            self.fusion_processor.set_fusion_mode(mode)
            logger.info(f"[AUTO_CYCLE] mode 1/{len(self._auto_cycle_modes)}: {mode}")
            print(f"[AUTO_CYCLE] mode=1/{len(self._auto_cycle_modes)} name={mode}", flush=True)
            return

        if now < self._auto_cycle_deadline:
            return

        self._auto_cycle_idx += 1
        if self._auto_cycle_idx >= len(self._auto_cycle_modes):
            print("[AUTO_CYCLE_DONE]", flush=True)
            logger.info("[AUTO_CYCLE] Sweep complete - exiting")
            if self.qt_app:
                self.qt_app.quit()
            else:
                self.running = False
            return

        mode = self._auto_cycle_modes[self._auto_cycle_idx]
        self.fusion_processor.set_fusion_mode(mode)
        self._auto_cycle_deadline = now + interval
        logger.info(f"[AUTO_CYCLE] mode {self._auto_cycle_idx + 1}/{len(self._auto_cycle_modes)}: {mode}")
        print(f"[AUTO_CYCLE] mode={self._auto_cycle_idx + 1}/{len(self._auto_cycle_modes)} name={mode}", flush=True)

    def _process_frame_loop(self):
        """Main processing loop triggered by timer."""
        if not self.running:
            return

        if self.loop_pause_event.is_set():
            self._loop_idle_event.set()
            return

        self._auto_cycle_fusion_modes_tick()

        # Note: Health checks are now driven by SDK heartbeat and hotplug monitor
        self._health_check_counter += 1
        if self._health_check_counter >= 30:
            self._health_check_counter = 0

            # FPA temp anchors the 8-bit estimator's AGC->celsius mapping.
            # It changes slowly, so once per ~30 ticks (not every frame) is
            # plenty and keeps this serial round-trip off the hot path.
            if self.radiometric_controller.state.estimation_enabled:
                try:
                    result = self.plugin_host.execute_command('thermal', 'get_fpa_temp')
                    if result.get('success') and result.get('celsius') is not None:
                        self._last_fpa_temp_c = float(result['celsius'])
                        if self.thermal_analyzer:
                            self.thermal_analyzer.last_fpa_temp_c = self._last_fpa_temp_c
                except Exception as e:
                    logger.debug(f"FPA temp poll for estimation failed: {e}")

        loop_start = time.time()
        self.frame_count += 1
        _prof_stage_t = loop_start

        try:
            # 1. Capture frames
            thermal_frame = None
            rgb_frame = None

            if self.threaded_capture:
                # threaded_capture returns (display_frame, raw_frame, rgb_frame)
                _, thermal_raw, rgb_f = self.threaded_capture.get_frames()
                # Prefer raw (which preserves 16-bit) if available
                if thermal_raw is not None:
                    thermal_frame = thermal_raw
                if rgb_f is not None:
                    rgb_frame = rgb_f
            else:
                # Synchronous fallback
                success, t_f = self.plugin_host.read_thermal()
                if success and t_f is not None:
                    thermal_frame = t_f

                # Assume read_rgb exists or we just rely on threaded capture
                # For safety, let's look at the active RGB backend directly:
                rgb_active = self.plugin_host.get_active_camera('rgb')
                if rgb_active and rgb_active.backend:
                    success, r_f = rgb_active.backend.read()
                    if success and r_f is not None:
                        rgb_frame = r_f

            # Save latest thermal frame for calibration point lookup and spot metering
            self._last_thermal_frame = thermal_frame
            # Save latest real (non-placeholder) RGB frame for on-demand
            # parallax auto-alignment, which runs off the GUI thread in
            # response to a button click rather than every frame.
            if rgb_frame is not None and rgb_frame is not self.rgb_placeholder:
                self._last_rgb_frame = rgb_frame

            # Every ROI, hot/cold spot, and spot-meter coordinate downstream is
            # expressed in this frame's native pixel space, so the GUI's overlay
            # transform must track it exactly — not the 640x512 default it was
            # built with, which silently misaligns every reading on any camera
            # that isn't a full-res Boson (Tau2, Lepton, or a Boson in its
            # lower-resolution mode). Track only real captures, not the
            # placeholder, so a reconnect doesn't clobber the last known size.
            if thermal_frame is not None:
                h, w = thermal_frame.shape[:2]
                if (w, h) != self._last_thermal_resolution:
                    self._last_thermal_resolution = (w, h)

            # Handle fallback
            if thermal_frame is None:
                thermal_frame = self.thermal_placeholder


            if rgb_frame is None and not self.config.disable_rgb:
                rgb_frame = self.rgb_placeholder

            _prof_t_capture = time.time()

            # 1b. Parallax correction — shift thermal to match RGB perspective
            # Must run after frame capture but before colorization/fusion so all
            # downstream processing sees the spatially-corrected thermal data.
            #
            # Gated on has_correction() rather than is_enabled(): a manual
            # alignment shift (fixed mounting offset) should apply even when
            # depth-based correction is off, since it doesn't need RGB or
            # depth estimation at all - just a constant translation.
            if (self.parallax_compensator
                    and self.parallax_compensator.has_correction()
                    and thermal_frame is not None
                    and thermal_frame is not self.thermal_placeholder):
                try:
                    safe_rgb = (rgb_frame if rgb_frame is not None
                                and rgb_frame is not self.rgb_placeholder else None)
                    corrected_thermal, corrected_rgb = self.parallax_compensator.apply_correction(
                        thermal_frame, safe_rgb
                    )
                    thermal_frame = corrected_thermal
                    # Only overwrite rgb_frame when a real corrected frame
                    # came back - safe_rgb was None (no real RGB available)
                    # returns None here too, and reassigning that would
                    # clobber a legitimate placeholder frame downstream.
                    if corrected_rgb is not None:
                        rgb_frame = corrected_rgb
                    # Parallax panel's "Performance" section - built with a
                    # working update method but nothing ever called it.
                    # Throttled: this is a display metric, not something
                    # that needs GUI updates every single frame.
                    _now_px_perf = time.time()
                    if _now_px_perf - self._last_parallax_perf_update_time >= self._parallax_perf_update_interval_s:
                        self._last_parallax_perf_update_time = _now_px_perf
                        self._gui_invoke(
                            "_update_parallax_performance",
                            self.parallax_compensator.last_depth_time_ms,
                            self.parallax_compensator.last_correction_time_ms,
                        )
                except Exception as _px_err:
                    logger.debug(f"Parallax correction failed: {_px_err}")

            # 2. Process thermal & Colorization
            # Use the snapshotted reference — safe even if reassign fires mid-tick
            thermal_16bit = None
            if thermal_frame is not None and thermal_frame.dtype == np.uint16:
                # The threaded capture already preserves 16-bit radiometric data;
                # use it directly for analysis/isotherm without any extra call.
                thermal_16bit = thermal_frame

            # Base colorized frame
            already_colorized = (
                thermal_frame is not self.thermal_placeholder
                and thermal_frame.dtype == np.uint8
                and thermal_frame.ndim == 3
                and thermal_frame.shape[2] == 3
                and not np.array_equal(thermal_frame[:, :, 0], thermal_frame[:, :, 1])
            )
            if thermal_frame is self.thermal_placeholder:
                colorized_thermal = thermal_frame
            elif already_colorized:
                # A genuinely false-colored frame straight from the camera's
                # own onboard processing (e.g. a Tau2 breakout board with no
                # CCI line - it can't be commanded into a raw/grayscale
                # output mode, so this IS the display-ready image, the same
                # feed Windows' own Camera app shows). Re-running this
                # through apply_composite_palette() would collapse it to
                # grayscale (throwing away 2 of 3 real color channels) and
                # recolor what's left with an unrelated palette. A camera
                # whose channels are actually equal (grayscale replicated
                # into BGR by the UVC layer, e.g. a non-radiometric Boson)
                # still takes the normal palette path below.
                colorized_thermal = thermal_frame
            elif self.palette_manager:
                colorized_thermal = self.palette_manager.apply_composite_palette(thermal_frame, self.roi_controller.roi_manager)
            else:
                colorized_thermal = cv2.cvtColor(thermal_frame, cv2.COLOR_GRAY2BGR) if len(thermal_frame.shape) == 2 else thermal_frame

            # 3D Fusion setup - detects RealSense hardware and whether
            # thermal is properly aligned to it, used both by the main
            # viewport's THREE_D mode (further below, in the display_frame
            # selection) and by the settings tab's point-cloud preview.
            #
            # _thermal_aligned_realsense requires the depth METHOD be
            # specifically "realsense" ONLY when depth-based (per-pixel)
            # correction is actually driving the shift: the thermal camera
            # has no depth information of its own, so a per-pixel shift's
            # alignment is only as trustworthy as whatever depth data it
            # was computed from - if that were "simplified"/MiDaS/
            # DepthAnything (an estimate) while relief-shading uses
            # RealSense's real depth, the two would be geometrically
            # inconsistent with each other even though "some" alignment is
            # nominally on.
            #
            # A manual-shift-only correction (parallax_compensator.enabled
            # is False, just a configured dx/dy/zoom) doesn't derive its
            # offset from ANY depth estimate at all - it's a constant
            # translation, entirely independent of whichever depth_method
            # string happens to be selected in the dropdown - so it's
            # equally valid regardless of that setting. Previously this
            # required method=="realsense" even in that case, forcing
            # users who only wanted a simple manual offset/crop (no
            # per-pixel depth-based correction at all) to also select
            # "realsense" just to unlock 3D Fusion - which then risked
            # depth estimation failing (e.g. no RealSense hardware
            # actually providing frames) and silently dropping the manual
            # correction too (see apply_correction()'s depth-estimation-
            # failed fallback).
            _rs_backend = None
            active_rgb = self.plugin_host.get_active_camera('rgb') if self.plugin_host else None
            if active_rgb and hasattr(active_rgb.backend, 'get_point_cloud'):
                _rs_backend = active_rgb.backend

            _thermal_aligned_realsense = bool(
                self.parallax_compensator
                and self.parallax_compensator.has_correction()
                and (
                    not self.parallax_compensator.enabled
                    or self.parallax_compensator.depth_estimator.method == "realsense"
                )
                # correction_target=="rgb" warps the RGB frame to align
                # with thermal - but RealSense's depth is natively
                # hardware-aligned to its OWN raw, unwarped color stream.
                # Warping that RGB frame breaks the depth-color
                # correspondence 3D Fusion's relief shading and point-
                # cloud coloring both depend on (get_depth_frame() is
                # always fetched raw/unwarped) - confirmed live ("3d
                # fusion also ignores the crop factor and shift... a
                # display that is mismatched in the two cameras POVs").
                # Only "thermal" target keeps this consistent: RealSense's
                # own RGB+depth stay untouched, and thermal is warped to
                # match them instead.
                and self.parallax_compensator.get_correction_target() == "thermal"
            )
            if _rs_backend is not None and _rs_backend is not self._last_3d_hw_available_reported:
                self._gui_invoke("set_fusion_3d_hardware_available", True)
                self._last_3d_hw_available_reported = _rs_backend
            elif _rs_backend is None and self._last_3d_hw_available_reported is not None:
                self._gui_invoke("set_fusion_3d_hardware_available", False)
                self._last_3d_hw_available_reported = None
            if _thermal_aligned_realsense != self._last_3d_aligned_reported:
                self._gui_invoke("set_fusion_3d_thermal_aligned", _thermal_aligned_realsense)
                self._last_3d_aligned_reported = _thermal_aligned_realsense

            # Point-cloud preview (3D Fusion settings tab) - independent of
            # the main viewport's view mode, so it's checkable any time;
            # gated on its own component-mode needs instead (its "RGB Only"
            # mode needs no thermal alignment at all - see
            # Fusion3DPointCloudView.needs_thermal_alignment).
            _3d_panel = getattr(self.gui, 'fusion_3d_panel', None) if self.gui else None
            _preview = getattr(_3d_panel, 'point_cloud_view', None) if _3d_panel else None
            _preview_ready = bool(
                _preview is not None and _preview.isVisible()
                and (_thermal_aligned_realsense or not _preview.needs_thermal_alignment())
            )
            if (_rs_backend and _preview_ready
                    and rgb_frame is not None and rgb_frame is not self.rgb_placeholder):
                _now_3d = time.time()
                if _now_3d - self._last_3d_fusion_update_time >= self._3d_fusion_update_interval_s:
                    self._last_3d_fusion_update_time = _now_3d
                    try:
                        cloud = _rs_backend.get_point_cloud()
                        if cloud is not None:
                            vertices, uv = cloud
                            self._gui_invoke(
                                "update_fusion_3d_view", vertices, uv,
                                rgb_frame.copy(), colorized_thermal.copy()
                            )
                    except Exception as _rs3d_err:
                        logger.debug(f"3D Fusion point-cloud update failed: {_rs3d_err}")

            # Detections (Motion/Edges)
            proc_results = {}
            if self.thermal_processor and thermal_frame is not self.thermal_placeholder:
                proc_results = self.thermal_processor.process_frame(thermal_frame)

            # Anomaly Priority is applied after analysis below (line ~903)

            # 3. Analyze (Radiometric stats)
            analysis_results = {
                'stats': None, 'hot_spots': [], 'cold_spots': [],
                'anomalies': [], 'motion_detections': [],
                'edge_clusters': [], 'trend': None
            }

            if self.thermal_analyzer and thermal_frame is not self.thermal_placeholder:
                # Throttled to ~30Hz, not submitted every render tick.
                # ThreadedAnalyzer has no pacing of its own - it processes
                # whatever's submitted as fast as analyze() allows (10-40ms/
                # frame) with no idle time in between, so at the render
                # loop's now much higher fps (300+ after the palette
                # optimization) it was submitting a new frame again well
                # before the previous analysis finished, keeping the
                # analyzer thread continuously busy on a CPU core with no
                # gaps. That's a genuine, sustained contender for the same
                # shared memory bandwidth the main thread's fusion
                # processing needs (this hardware's fusion blends were
                # already established as memory-bandwidth-bound, not
                # compute-bound, earlier this session) - a background
                # thread saturating a core is exactly the kind of
                # concurrent load that would show up as the fusion_dispatch
                # jitter reported live (12-20ms swing on the same mode,
                # same resolution). Hot/cold-spot overlays don't need
                # updates faster than a human can perceive anyway.
                _now = time.time()
                if _now - self._last_analysis_submit_time >= self._analysis_submit_interval_s:
                    self._last_analysis_submit_time = _now
                    source_for_analysis = thermal_16bit if thermal_16bit is not None else thermal_frame
                    self.threaded_analyzer.submit_frame(source_for_analysis)
                latest = self.threaded_analyzer.get_latest_results()
                if latest is not None:
                    self._last_analysis_results = latest
                if self._last_analysis_results is not None:
                    analysis_results = self._last_analysis_results

            # Enrich analysis with proc_results (motion, edges)
            analysis_results['motion_detections'] = proc_results.get('motion_detections', [])
            analysis_results['edge_clusters'] = proc_results.get('edge_clusters', [])

            # Anomaly panel's "Performance" section - built with a working
            # update method but nothing ever called it, same as parallax's
            # equivalent was before this session. Throttled: a display
            # metric, not something that needs updating every single frame.
            if self.thermal_analyzer:
                _now_anom_perf = time.time()
                if _now_anom_perf - self._last_anomaly_perf_update_time >= self._anomaly_perf_update_interval_s:
                    self._last_anomaly_perf_update_time = _now_anom_perf
                    self._gui_invoke(
                        "_update_anomaly_performance",
                        self.threaded_analyzer.last_analysis_time_ms,
                        self._analysis_submit_interval_s * 1000.0,
                    )

            # 3a. Per-ROI temperature stats for the ROI Manager panel - throttled
            # per _roi_stats_interval_s (see its definition for why).
            if (self.gui and hasattr(self.gui, 'update_roi_stats')
                    and self.roi_controller and self.roi_controller.rois
                    and self.thermal_analyzer and thermal_frame is not self.thermal_placeholder):
                _now_roi = time.time()
                if _now_roi - self._last_roi_stats_time >= self._roi_stats_interval_s:
                    self._last_roi_stats_time = _now_roi
                    stats_source = thermal_16bit if thermal_16bit is not None else thermal_frame
                    roi_stats = {}
                    for roi in self.roi_controller.rois.values():
                        if not roi.active:
                            continue
                        try:
                            mask = roi.get_mask(stats_source.shape[:2])
                            roi_stat = self.thermal_analyzer.compute_statistics(stats_source, roi_mask=mask)
                        except Exception as e:
                            logger.debug(f"ROI stats failed for {roi.roi_id}: {e}")
                            continue
                        if roi_stat is None:
                            continue
                        roi_stats[roi.roi_id] = {
                            'roi_name': roi.label or roi.roi_id,
                            'temp_avg': roi_stat.mean_temp,
                            'temp_min': roi_stat.min_temp,
                            'temp_max': roi_stat.max_temp,
                            'temp_std': roi_stat.std_temp,
                            'pixel_count': roi_stat.pixel_count,
                            'unit': roi_stat.unit,
                            'emissivity': 'global',
                        }
                    self.gui.update_roi_stats(roi_stats)

            # Apply anomaly priority if enabled
            if self.thermal_processor and self.thermal_processor.anomaly_priority_enabled:
                colorized_thermal = self.thermal_processor.apply_anomaly_priority_colorization(
                    thermal_frame, self._collect_priority_anomalies(analysis_results), colorized_thermal
                )

            # 3b. Apply isotherm overlay via IsothermManager
            if thermal_16bit is not None:
                colorized_thermal = self.isotherm_manager.apply_overlay(colorized_thermal, thermal_16bit)

            # 3c. Apply manual threshold overlay via ThresholdManager
            ts = self.threshold_manager.get_state()
            if (
                ts.enabled
                and self.thermal_analyzer is not None
                and thermal_frame is not self.thermal_placeholder
            ):
                try:
                    from thermal_inspection.processing.thermal_analyzer import (
                        ThresholdMode, ThresholdVisualization
                    )
                    t_mode = ThresholdMode(ts.mode)
                    v_mode = ThresholdVisualization(ts.viz_mode)
                    source = thermal_16bit if thermal_16bit is not None else thermal_frame
                    detection = self.thermal_analyzer.detect_threshold_anomalies(
                        source,
                        threshold_mode=t_mode,
                        min_threshold=ts.min_val,
                        max_threshold=ts.max_val,
                        use_raw_values=ts.use_raw,
                    )
                    colorized_thermal = self.thermal_analyzer.apply_threshold_visualization(
                        source, colorized_thermal, detection, v_mode
                    )
                    # Proactive feedback via event bus
                    self.event_bus.threshold_stats_updated.emit(
                        detection.anomaly_percentage,
                        detection.anomaly_count,
                        detection.total_pixels,
                    )
                except Exception as _thresh_err:
                    logger.debug(f"Manual threshold overlay error: {_thresh_err}")

            _prof_t_preprocess = time.time()

            display_frame = colorized_thermal  # Default

            if self.view_mode == ViewMode.THERMAL_ONLY:
                display_frame = colorized_thermal
            elif self.view_mode == ViewMode.RGB_ONLY:
                if rgb_frame is not None:
                    display_frame = rgb_frame
                else:
                    display_frame = self.rgb_placeholder if self.rgb_placeholder is not None else colorized_thermal
            elif self.view_mode == ViewMode.FUSION:
                if self.fusion_processor and rgb_frame is not None:
                    # Apply fusion color mode (grayscale RGB if requested)
                    fusion_rgb = rgb_frame
                    if self._fusion_color_mode == "grayscale" and rgb_frame is not None:
                        gray = cv2.cvtColor(rgb_frame, cv2.COLOR_BGR2GRAY)
                        fusion_rgb = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
                    _fus_t0 = time.perf_counter()
                    display_frame = self.fusion_processor.process(colorized_thermal, fusion_rgb)
                    _fus_ms = (time.perf_counter() - _fus_t0) * 1000
                    if self.frame_count % 30 == 0:
                        print(f"[PROFILE_FUSION2] mode={self.fusion_processor.fusion_mode} "
                              f"thermal_shape={colorized_thermal.shape} rgb_in_shape={fusion_rgb.shape} "
                              f"fusion_ms={_fus_ms:.2f}", flush=True)
                else:
                    display_frame = colorized_thermal
            elif self.view_mode == ViewMode.SIDE_BY_SIDE:
                if rgb_frame is not None:
                    # Create side-by-side view
                    h1, w1 = colorized_thermal.shape[:2]
                    h2, w2 = rgb_frame.shape[:2]
                    # Resize RGB to match thermal height
                    if h1 != h2:
                        rgb_resized = cv2.resize(rgb_frame, (int(w2 * h1 / h2), h1))
                    else:
                        rgb_resized = rgb_frame
                    # Order must match InspectionOverlayWidget._transform_thermal_coords'
                    # side_by_side branch, which places thermal at x=0 when
                    # fusion_priority=='thermal' and at x=(fw-tw) otherwise - it has
                    # no way to know the actual concat order, only to assume it
                    # matches this setting. This used to always put thermal first
                    # regardless of priority, so with priority set to 'rgb' every
                    # overlay marker (ROIs, hot/cold spots, spot meters) mapped to
                    # the wrong side of the frame - spread out over what looked like
                    # the whole fused frame's width once the offset was that far off.
                    priority = getattr(self.fusion_processor, 'fusion_priority', 'thermal')
                    if priority == 'thermal':
                        display_frame = cv2.hconcat([colorized_thermal, rgb_resized])
                    else:
                        display_frame = cv2.hconcat([rgb_resized, colorized_thermal])
                else:
                    display_frame = colorized_thermal
            elif self.view_mode == ViewMode.THREE_D:
                # Real depth (RealSense) shades a 2D image with a relief/
                # bump-map effect - see apply_depth_relief. With thermal
                # aligned to RealSense (has_correction() AND depth_method
                # == "realsense" - see _thermal_aligned_realsense above),
                # the base image is the full RGB+thermal 2D Fusion blend.
                # Without that (including thermal camera off entirely),
                # this still shows a useful depth-enhanced RGB view -
                # RealSense's own RGB+depth are natively hardware-aligned
                # by its SDK and need no thermal alignment at all.
                if _rs_backend is not None:
                    # apply_depth_relief costs ~20ms at thermal resolution
                    # and ~90ms at RealSense's native 1280x800 (the RGB-only
                    # fallback path) even after in-place optimization -
                    # recomputing it every single frame (as opposed to the
                    # point-cloud preview above, which is already
                    # throttled) directly capped the whole video loop's
                    # framerate to near-single-digit FPS. Reuse the last
                    # computed frame between throttled recomputes instead -
                    # a real-depth relief effect doesn't need to update
                    # faster than a human can perceive it changing anyway.
                    _now_3d_disp = time.time()
                    if (self._last_3d_display_frame is None
                            or _now_3d_disp - self._last_3d_display_time >= self._3d_fusion_update_interval_s):
                        self._last_3d_display_time = _now_3d_disp
                        try:
                            from thermal_inspection.gui.panels.fusion_3d_panel import apply_3d_visualization

                            # _3d_data_source lets the user force RGB Only or
                            # RGB+Thermal explicitly instead of always
                            # auto-deciding - but "fusion" without real
                            # alignment still falls back to RGB Only rather
                            # than honoring a request that would blend
                            # spatially-unrelated thermal/RGB pixels.
                            want_fusion = (
                                self._3d_data_source == "fusion"
                                or (self._3d_data_source == "auto" and _thermal_aligned_realsense)
                            )
                            if (want_fusion and _thermal_aligned_realsense
                                    and self.fusion_processor and rgb_frame is not None):
                                fusion_rgb = rgb_frame
                                if self._fusion_color_mode == "grayscale":
                                    gray = cv2.cvtColor(rgb_frame, cv2.COLOR_BGR2GRAY)
                                    fusion_rgb = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
                                base_2d = self.fusion_processor.process(colorized_thermal, fusion_rgb)
                            elif rgb_frame is not None and rgb_frame is not self.rgb_placeholder:
                                base_2d = rgb_frame
                            else:
                                base_2d = colorized_thermal

                            depth_map = _rs_backend.get_depth_frame()
                            if depth_map is not None:
                                bh, bw = base_2d.shape[:2]
                                if depth_map.shape[:2] != (bh, bw):
                                    depth_map = cv2.resize(depth_map, (bw, bh), interpolation=cv2.INTER_NEAREST)
                                # apply_3d_visualization runs full-resolution
                                # on GPU when available (~5ms/frame at
                                # 1280x800 on an RTX 4000 Ada), or falls back
                                # to a resolution-capped CPU path otherwise.
                                # near_m/far_m/interval_m are harmlessly
                                # unused by whichever mode isn't "fog"/
                                # "contours" - each function only reads the
                                # kwargs it defines.
                                self._last_3d_display_frame = apply_3d_visualization(
                                    self._3d_mode, base_2d, depth_map, strength=self._3d_relief_strength,
                                    near_m=self._3d_fog_near_m, far_m=self._3d_fog_far_m,
                                    interval_m=self._3d_contour_interval_m,
                                )
                            else:
                                self._last_3d_display_frame = base_2d
                        except Exception as _3d_disp_err:
                            logger.debug(f"3D Fusion display frame failed: {_3d_disp_err}")
                            self._last_3d_display_frame = colorized_thermal
                    display_frame = self._last_3d_display_frame
                else:
                    self._last_3d_display_frame = None
                    display_frame = colorized_thermal
            elif self.view_mode == ViewMode.PICTURE_IN_PICTURE:
                if self.fusion_processor and rgb_frame is not None:
                    # Fix Bug #25: use fusion_processor for proper alignment before PIP
                    rgb_aligned = self.fusion_processor.align_rgb_to_thermal(
                        rgb_frame, colorized_thermal.shape[:2]
                    )
                    display_frame = self.fusion_processor._picture_in_picture(
                        colorized_thermal, rgb_aligned
                    )
                else:
                    display_frame = colorized_thermal

            _prof_t_fusion = time.time()

            # 5. Push to GUI
            if self.gui:
                if self._last_thermal_resolution != self._gui_thermal_resolution_synced:
                    self.gui.update_thermal_resolution(*self._last_thermal_resolution)
                    self._gui_thermal_resolution_synced = self._last_thermal_resolution

                # frame_frozen was set by toggle_freeze() but never read
                # anywhere - the Freeze button updated its own label/icon
                # and nothing else, the video kept updating live
                # regardless. Skip only the visible video push here -
                # analysis/recording/metrics continue normally on the
                # freshly computed frame, so unfreezing resumes cleanly
                # with no backlog, and a snapshot/recording taken while
                # frozen isn't itself frozen in time for no reason.
                if not self.frame_frozen:
                    self.gui.update_frame(display_frame)

                _prof_t_guiframe = time.time()

                # Update metrics
                state = self.camera_state
                self.gui.update_metrics(
                    fps=self.smoothed_fps,
                    roi_count=len(self.roi_controller.rois) if self.roi_controller else 0,
                    thermal_connected=state.thermal_connected,
                    rgb_connected=state.rgb_available
                )

                # Get palette LUT for histogram coloring
                palette_lut = None
                if self.palette_manager:
                    palette_lut = self.palette_manager.get_current_palette_lut()

                # Update analysis
                self.gui.update_thermal_analysis(
                    stats=analysis_results.get('stats'),
                    hot_spots=analysis_results.get('hot_spots', []),
                    cold_spots=analysis_results.get('cold_spots', []),
                    anomalies=analysis_results.get('anomalies', []),
                    motion_detections=analysis_results.get('motion_detections', []),
                    edge_clusters=analysis_results.get('edge_clusters', []),
                    trend=analysis_results.get('trend'),
                    temp_array=analysis_results.get('temp_array'),
                    palette_lut=palette_lut,
                    is_radiometric=analysis_results.get('is_radiometric', False)
                )

                # Update ROIs
                if self.roi_controller:
                    self.gui.update_rois(self.roi_controller.rois)

                # Update spot meters (measurement points) in the GUI
                if hasattr(self.gui, 'measurement_points') and self.gui.measurement_points:
                    spot_values = []
                    for point in self.gui.measurement_points:
                        temp = None
                        unit = "°C"
                        cam = self.thermal_camera
                        if cam and hasattr(cam, 'get_spot_temperature'):
                            temp = cam.get_spot_temperature(point.x, point.y)

                        # Fallback: true radiometric conversion isn't available. If the
                        # user has opted into 8-bit estimation, use the FPA-referenced
                        # estimator; otherwise fall back further to the analyzer's raw
                        # AGC display (no estimate, honest "(AGC)" label).
                        if temp is None and self._last_thermal_frame is not None:
                            h, w = self._last_thermal_frame.shape[:2]
                            if 0 <= point.x < w and 0 <= point.y < h:
                                if (self.radiometric_controller.state.estimation_enabled
                                        and hasattr(self, 'thermal_estimator')):
                                    fpa = self._last_fpa_temp_c if self._last_fpa_temp_c is not None else 25.0
                                    temp_c = self.thermal_estimator.get_pixel_temperature(
                                        self._last_thermal_frame, point.x, point.y, fpa
                                    )
                                    # get_pixel_temperature always returns Celsius -
                                    # respect whatever unit the user picked instead
                                    # of hardcoding °C regardless of that choice.
                                    temp = self.radiometric_controller.convert_temperature(temp_c) if temp_c is not None else None
                                    unit = f"{self.radiometric_controller.get_unit_symbol()} (est)"
                                elif self.thermal_analyzer:
                                    raw_pixel = float(self._last_thermal_frame[point.y, point.x])
                                    temp, unit = self.thermal_analyzer.calculate_spot_temperature(raw_pixel)

                        if temp is not None:
                            # Use radiometric unit symbol if available
                            if self.radiometric_controller and cam and hasattr(cam, 'is_radiometric_capable') and cam.is_radiometric_capable():
                                unit = self.radiometric_controller.get_unit_symbol()
                            spot_values.append({
                                'label': point.label,
                                'temperature': temp,
                                'unit': unit
                            })
                    self.gui.update_spot_meter_values(spot_values)


            # Cache display frame for snapshot access (always update outside GUI block)
            self._last_display_frame = display_frame

            # Non-blocking enqueue for background video recording
            if self.media_manager and self.media_manager.recording_enabled:
                rois_snap = list(self.roi_controller.rois.values()) if self.roi_controller and hasattr(self.roi_controller, 'rois') else []
                stats_snap = analysis_results.get('stats')
                self.media_manager.enqueue_frame(
                    display_frame,
                    thermal_frame,
                    rgb_frame,
                    rois_snap,
                    stats_snap
                )


        except Exception as e:
            logger.error(f"Error in processing loop: {e}", exc_info=True)

        # Performance tracking
        loop_time = time.time() - loop_start
        self.frame_times.append(loop_time)
        if len(self.frame_times) > 30:
            self.frame_times.pop(0)
            avg_time = sum(self.frame_times) / len(self.frame_times)
            self.smoothed_fps = 1.0 / avg_time if avg_time > 0 else 0

        if self.frame_count % 30 == 0:
            logger.debug(f"Loop running: {self.smoothed_fps:.1f} FPS")
            rgb_shape = getattr(locals().get('rgb_frame'), 'shape', None)
            fmode = getattr(self.fusion_processor, 'fusion_mode', None) if self.fusion_processor else None
            loop_max_ms = max(self.frame_times) * 1000
            loop_min_ms = min(self.frame_times) * 1000
            rgb_cap_fps = None
            rgb_cap_err = None
            if getattr(self, 'threaded_capture', None) and self.threaded_capture.rgb_capture:
                rgb_cap_fps = self.threaded_capture.rgb_capture.fps
                rgb_cap_err = self.threaded_capture.rgb_capture.error_count
            _lv = locals()
            _stage_capture_ms = (_lv.get('_prof_t_capture', loop_start) - loop_start) * 1000
            _stage_preprocess_ms = (_lv.get('_prof_t_preprocess', loop_start) - _lv.get('_prof_t_capture', loop_start)) * 1000
            _stage_fusion_ms = (_lv.get('_prof_t_fusion', loop_start) - _lv.get('_prof_t_preprocess', loop_start)) * 1000
            _stage_guiframe_ms = (_lv.get('_prof_t_guiframe', loop_start) - _lv.get('_prof_t_fusion', loop_start)) * 1000
            _stage_rest_ms = loop_time * 1000 - (_stage_capture_ms + _stage_preprocess_ms + _stage_fusion_ms + _stage_guiframe_ms)
            print(f"[PROFILE_STAGES] capture={_stage_capture_ms:.1f} preprocess={_stage_preprocess_ms:.1f} "
                  f"fusion_dispatch={_stage_fusion_ms:.1f} gui_update_frame={_stage_guiframe_ms:.1f} "
                  f"rest={_stage_rest_ms:.1f} total={loop_time*1000:.1f}", flush=True)
            print(f"[PROFILE_COMBO] fps={self.smoothed_fps:.1f} jitter_ms={loop_max_ms - loop_min_ms:.1f} "
                  f"loop_max={loop_max_ms:.1f} loop_min={loop_min_ms:.1f} view={self.view_mode} "
                  f"fusion_mode={fmode} rgb_shape={rgb_shape} rgb_cap_fps={rgb_cap_fps} rgb_cap_err={rgb_cap_err}", flush=True)

    def toggle_freeze(self, enabled: bool):
        """Toggle frame freeze."""
        self.frame_frozen = enabled
        logger.info(f"Frame freeze: {'ON' if enabled else 'OFF'}")

    @property
    def recording_enabled(self) -> bool:
        return self.media_manager.recording_enabled if self.media_manager else False

    def toggle_recording(self, enabled: bool):
        """Start or stop video recording."""
        if self.media_manager:
            frame_shape = (self.config.height or 512, self.config.width or 640, 3)
            fps = max(1, int(self.smoothed_fps)) if self.smoothed_fps > 1 else 30
            self.media_manager.toggle_recording(enabled, fps=fps, frame_shape=frame_shape)

    def cycle_palette(self):
        """Cycle to next palette."""
        if self.palette_manager:
            palettes = self.palette_manager.get_available_palettes()
            current = self.palette_manager.global_palette.palette_type.value
            try:
                idx = palettes.index(current)
                next_palette = palettes[(idx + 1) % len(palettes)]
                self.palette_manager.set_global_palette(next_palette)
                logger.info(f"Switched to palette: {next_palette}")
            except (ValueError, IndexError):
                if palettes:
                    self.palette_manager.set_global_palette(palettes[0])

    def cycle_view_mode(self):
        """
        Cycle view mode.

        THREE_D is always in the cycle, not conditionally added only when a
        RealSense camera is connected - RealSense availability should make
        3D usable, not force the mode switch or hide it from manual
        toggling. Without hardware depth it just shows Fusion3DViewWidget's
        "no hardware depth sensor" placeholder, the same way RGB_ONLY shows
        a placeholder with no RGB camera connected.
        """
        modes = [ViewMode.THERMAL_ONLY, ViewMode.RGB_ONLY, ViewMode.FUSION,
                 ViewMode.SIDE_BY_SIDE, ViewMode.PICTURE_IN_PICTURE, ViewMode.THREE_D]
        try:
            idx = modes.index(self.view_mode)
            self.view_mode = modes[(idx + 1) % len(modes)]

            # Convert ViewMode enum to string format expected by set_view_mode
            mode_name_map = {
                ViewMode.THERMAL_ONLY: "thermal only",
                ViewMode.RGB_ONLY: "rgb only",
                ViewMode.FUSION: "fusion",
                ViewMode.SIDE_BY_SIDE: "side-by-side",
                ViewMode.PICTURE_IN_PICTURE: "picture-in-picture",
                ViewMode.THREE_D: "3d",
            }
            mode_str = mode_name_map.get(self.view_mode, "thermal only")
            self.fusion_controller.set_view_mode(mode_str)
            logger.info(f"Switched view mode to: {self.view_mode}")
        except ValueError:
            self.view_mode = modes[0]


    def capture_snapshot(self):
        """
        Capture a snapshot of the current display frame and save it to disk.
        """
        if not self.media_manager:
            logger.warning("capture_snapshot: no MediaManager available")
            return

        frame = getattr(self, '_last_display_frame', None)
        if frame is None:
            logger.warning("capture_snapshot: no display frame available yet")
            return

        rois = list(self.roi_controller.get_all_rois()) if self.roi_controller else []
        stats = None

        self.media_manager.capture_snapshot(
            frame,
            rois=rois,
            stats=stats,
            gui_invoke_fn=self._gui_invoke
        )

    def toggle_anomaly_priority(self, enabled: bool):
        """Toggle anomaly priority mode."""
        if self.thermal_processor and hasattr(self.thermal_processor, 'set_anomaly_priority_enabled'):
            self.thermal_processor.set_anomaly_priority_enabled(enabled)

    def set_enabled_anomaly_types(self, types_dict: dict):
        """Set enabled anomaly types."""
        self.enabled_anomaly_types = types_dict.copy()

    # Anomaly-panel type checkbox key -> analysis_results key holding that
    # category's detections. All five share the same `bbox` (x1,y1,x2,y2)
    # field - HotSpot/ColdSpot/ThermalAnomaly's docstrings say so
    # explicitly ("for anomaly priority compatibility") - but nothing ever
    # actually combined them: apply_anomaly_priority_colorization() only
    # ever received analysis_results['anomalies'] (ThermalAnomaly alone),
    # so toggling Motion/Edges/Hot Spots/Cold Spots off (or on) had zero
    # effect on the anomaly-priority fade regardless of checkbox state.
    # "enhanced_fusion" is deliberately not in this map -
    # detect_enhanced_fusion_anomalies() exists but is never called
    # anywhere in the pipeline; that checkbox has no detection behind it
    # yet, a separate gap from this dead-merge bug.
    _ANOMALY_TYPE_RESULT_KEYS = {
        'hot_spots': 'hot_spots',
        'cold_spots': 'cold_spots',
        'thermal_anomalies': 'anomalies',
        'motion': 'motion_detections',
        'edges': 'edge_clusters',
    }

    def _collect_priority_anomalies(self, analysis_results: dict) -> list:
        """
        Merge every enabled anomaly-type category's detections into one
        list for apply_anomaly_priority_colorization() - each entry only
        needs the shared `bbox` field that method reads. A type absent
        from self.enabled_anomaly_types (e.g. before the user has ever
        touched a checkbox) defaults to enabled, matching the panel's own
        all-checked-by-default initial state.
        """
        combined = []
        for type_key, results_key in self._ANOMALY_TYPE_RESULT_KEYS.items():
            if self.enabled_anomaly_types.get(type_key, True):
                combined.extend(analysis_results.get(results_key) or [])
        return combined

    def delete_roi(self, roi_id: str):
        """Delete specific ROI."""
        self.roi_controller.delete_roi(roi_id)

    # Advanced Fusion/Edge settings placeholders
    # (MainWindow calls these, so we need them to avoid AttributeErrors)
    def set_fusion_priority(self, priority: str):
        """Set fusion priority (thermal or rgb)."""
        if self.fusion_processor:
            self.fusion_processor.set_priority(priority)
            logger.info(f"Fusion priority set to: {priority}")
    def set_fusion_strength(self, strength: float):
        """Set fusion strength/intensity."""
        if self.fusion_processor:
            self.fusion_processor.set_intensity(strength)

    def set_fusion_fuzziness(self, fuzziness: float):
        """Set fusion edge blur/fuzziness."""
        if self.fusion_processor:
            # Convert float 0.0-1.0 to kernel size (0-15)
            kernel_size = int(fuzziness * 15)
            self.fusion_processor.set_edge_blur(kernel_size)

    def set_fusion_color_mode(self, mode: str):
        """Set fusion color mode ('color' or 'grayscale')."""
        self._fusion_color_mode = mode
        logger.info(f"Fusion color mode set to: {mode}")

    def set_edge_strength(self, strength: float):
        """Set Canny edge detection thresholds based on strength."""
        if self.fusion_processor:
            # strength 0.0-1.0 -> low threshold 200-10
            # Higher strength = detect more edges = lower threshold
            low_thresh = int(200 - (strength * 190))
            self.fusion_processor.set_edge_strength(low_thresh)

    def set_edge_fuzziness(self, fuzziness: float):
        """Set edge blur/fuzziness."""
        if self.fusion_processor:
            kernel_size = int(fuzziness * 15)
            self.fusion_processor.set_edge_blur(kernel_size)

    def set_edge_color(self, color_name: str):
        """Set edge color."""
        # Simple color map
        colors = {
            'red': (0, 0, 255),
            'green': (0, 255, 0),
            'blue': (255, 0, 0),
            'cyan': (255, 255, 0),
            'magenta': (255, 0, 255),
            'yellow': (0, 255, 255),
            'white': (255, 255, 255),
            'black': (0, 0, 0)
        }
        if self.fusion_processor and color_name in colors:
            self.fusion_processor.set_edge_color(colors[color_name])

    def set_detail_strength(self, strength: float):
        """Set detail injection strength."""
        if self.fusion_processor:
             # direct property set - FusionProcessor doesn't have a setter for this yet?
             # Checking FusionProcessor, it has parameters but maybe not a setter method for just strength
             # It acts via FusionProcessor.detail_strength attribute
             self.fusion_processor.detail_strength = strength

    def set_detail_quality(self, quality: str):
        """Set detail quality (low/med/high)."""
        if self.fusion_processor:
            q_map = {'low': 0.0, 'medium': 0.5, 'high': 1.0}
            val = q_map.get(quality, 0.5)
            self.fusion_processor.detail_quality = val

    def set_laplacian_gpu(self, enabled: bool):
        """Enable/disable GPU (CUDA) acceleration for the laplacian_pyramid fusion mode."""
        if self.fusion_processor:
            self.fusion_processor.set_laplacian_gpu_enabled(enabled)

    def set_laplacian_cpu_scale(self, scale: float):
        """Set laplacian_pyramid's CPU-fallback internal resolution scale (no effect when GPU is active)."""
        if self.fusion_processor:
            self.fusion_processor.set_laplacian_cpu_scale(scale)

    def set_3d_relief_strength(self, strength: float):
        """Set how strongly real RealSense depth shades ViewMode.THREE_D's output (0-1)."""
        self._3d_relief_strength = max(0.0, min(1.0, strength))

    def set_3d_mode(self, mode: str):
        """Set which depth visualization ViewMode.THREE_D uses - see fusion_3d_panel.THREE_D_MODES."""
        from thermal_inspection.gui.panels.fusion_3d_panel import THREE_D_MODES
        if mode not in THREE_D_MODES:
            logger.warning(f"Unknown 3D Fusion mode '{mode}', ignoring")
            return
        self._3d_mode = mode
        self._last_3d_display_frame = None  # force an immediate recompute in the new mode

    def set_3d_data_source(self, source: str):
        """Set which base image ViewMode.THREE_D shades - "auto", "rgb_only", or "fusion"."""
        if source not in ("auto", "rgb_only", "fusion"):
            logger.warning(f"Unknown 3D Fusion data source '{source}', ignoring")
            return
        self._3d_data_source = source
        self._last_3d_display_frame = None  # force an immediate recompute with the new source

    def set_3d_fog_range(self, near_m: float, far_m: float):
        """Set the near/far distance range (meters) for the "fog" 3D Fusion mode."""
        self._3d_fog_near_m = near_m
        self._3d_fog_far_m = far_m
        self._last_3d_display_frame = None

    def set_3d_contour_interval(self, interval_m: float):
        """Set the line spacing (meters) for the "contours" 3D Fusion mode."""
        self._3d_contour_interval_m = interval_m
        self._last_3d_display_frame = None

    def set_emissivity(self, val: float):
        """Set emissivity value."""
        if self.thermal_analyzer:
            self.thermal_analyzer.set_emissivity(val)

    def set_atmospheric_temperature(self, val: float):
        """Set atmospheric temperature."""
        if self.thermal_analyzer:
            self.thermal_analyzer.set_atmospheric_temperature(val)

    def set_atmospheric_transmission(self, val: float):
        """Set atmospheric transmission."""
        if self.thermal_analyzer:
            self.thermal_analyzer.set_atmospheric_transmission(val)

    # --- Threshold backward-compat delegations (prefer event bus) ---
    def set_manual_threshold_enabled(self, enabled: bool):
        self.threshold_manager.set_enabled(enabled)

    def set_manual_threshold_mode(self, mode: str):
        self.threshold_manager.set_mode(mode)

    def set_manual_min_threshold(self, val: float):
        self.threshold_manager.set_min(val)

    def set_manual_max_threshold(self, val: float):
        self.threshold_manager.set_max(val)

    def set_manual_use_raw_values(self, enabled: bool):
        self.threshold_manager.set_use_raw(enabled)

    def set_manual_viz_mode(self, mode: str):
        self.threshold_manager.set_viz_mode(mode)

    # === PALETTE METHODS ===
    def set_palette(self, palette_name: str):
        """Set global palette.

        Args:
            palette_name: Name of the palette to use (e.g., 'ironbow', 'rainbow', etc.)
        """
        if self.palette_manager:
            from thermal_inspection.processing.palette_manager import PaletteType
            # Convert string to PaletteType enum
            try:
                # Normalize name (lowercase, replace spaces with underscores).
                # strip() first: palette combo boxes indent items for visual
                # grouping under category headers (f"  {palette.value}"),
                # and that display-only padding must not become part of the
                # value — replace(' ', '_') alone turns it into leading
                # underscores that never match a real PaletteType.
                clean_name = palette_name.strip().lower().replace(' ', '_').replace('-', '_')
                palette_type = PaletteType(clean_name)
                self.palette_manager.set_global_palette(palette_type)
                logger.info(f"Global palette set to: {palette_name.strip()}")
            except ValueError:
                logger.warning(f"Unknown palette: {palette_name!r}")

    def set_roi_palette(self, roi_id: str, palette_name: str):
        """Set palette for a specific ROI.

        Args:
            roi_id: ID of the ROI
            palette_name: Name of the palette to use
        """
        if self.palette_manager:
            from thermal_inspection.processing.palette_manager import PaletteType
            try:
                clean_name = palette_name.strip().lower().replace(' ', '_').replace('-', '_')
                palette_type = PaletteType(clean_name)
                self.palette_manager.set_roi_palette(roi_id, palette_type)
                # Also update ROI object if ROI controller exists
                if self.roi_controller:
                    roi = self.roi_controller.get_roi(roi_id)
                    if roi:
                        roi.custom_palette = palette_name.strip()
                logger.info(f"ROI {roi_id} palette set to: {palette_name.strip()}")
            except ValueError:
                logger.warning(f"Unknown palette for ROI: {palette_name!r}")

    # =========================================================================
    # Calibration Properties (Backward Compatibility)
    # =========================================================================

    @property
    def calibration_enabled(self) -> bool:
        return self.calibration_manager.calibration_enabled

    @calibration_enabled.setter
    def calibration_enabled(self, value: bool):
        self.calibration_manager.calibration_enabled = value

    @property
    def calibration_add_point_mode(self) -> bool:
        return self.calibration_manager.calibration_add_point_mode

    @calibration_add_point_mode.setter
    def calibration_add_point_mode(self, value: bool):
        self.calibration_manager.calibration_add_point_mode = value

    @property
    def calibration_reference_temp(self) -> float:
        return self.calibration_manager.calibration_reference_temp

    @calibration_reference_temp.setter
    def calibration_reference_temp(self, value: float):
        self.calibration_manager.calibration_reference_temp = value

    @property
    def radiometric_calibrator(self):
        return self.calibration_manager.radiometric_calibrator

    @radiometric_calibrator.setter
    def radiometric_calibrator(self, value):
        self.calibration_manager.radiometric_calibrator = value

    # =========================================================================
    # Calibration Methods
    # =========================================================================

    def clear_calibration(self):
        """Clear all radiometric calibration points."""
        self.calibration_manager.clear_calibration()

    def compute_calibration(self, method: str = 'linear', degree: int = 2) -> bool:
        """Compute calibration from current points."""
        return self.calibration_manager.compute_calibration(method, degree)

    def import_calibration(self, filepath: str) -> bool:
        """Import calibration from JSON file."""
        return self.calibration_manager.import_calibration(filepath)

    def export_calibration(self, filepath: str) -> bool:
        """Export current calibration to JSON file."""
        return self.calibration_manager.export_calibration(filepath)

    def set_calibration_enabled(self, enabled: bool):
        """Enable or disable application of the radiometric calibration."""
        self.calibration_manager.set_calibration_enabled(enabled)

    def set_calibration_add_point_mode(self, enabled: bool, reference_temp: float = 25.0):
        """Enter or exit calibration point-add mode."""
        self.calibration_manager.set_calibration_add_point_mode(enabled, reference_temp)

    def remove_calibration_point(self, index: int) -> bool:
        """Remove a calibration point by index."""
        return self.calibration_manager.remove_calibration_point(index)

    def _on_add_calibration_point(self, x: int, y: int):
        """Add a calibration point at the given pixel coordinates."""
        last_frame = getattr(self, '_last_thermal_frame', None)
        self.calibration_manager.add_calibration_point(
            x, y, self.thermal_camera, self.thermal_analyzer, last_frame
        )
        self.update_calibration_gui()

    # Public alias so GUI code doesn't need to call the private method
    add_calibration_point = _on_add_calibration_point

    def _get_temperature_frame(self):
        """Return the latest per-pixel temperature frame from the thermal camera."""
        cam = self.thermal_camera
        if cam and hasattr(cam, 'get_temperature_frame'):
            return cam.get_temperature_frame()
        return None

    def update_calibration_gui(self):
        """Push the current calibration statistics to the GUI calibration panel."""
        if not self.gui or not hasattr(self.gui, 'calibration_panel'):
            return
        panel = self.gui.calibration_panel
        calibrator = self.calibration_manager.radiometric_calibrator
        points = calibrator.calibration_points if calibrator else []
        stats = self.calibration_manager.get_calibration_stats()
        panel.update_calibration_points(points)
        panel.set_calibration_status(bool(stats.get('is_calibrated')), stats)
        # Manager auto-exits add-point mode after one click ("only one point
        # per activation") - resync the checkable button so it doesn't keep
        # showing "Active" once the backend has already turned the mode off.
        if not self.calibration_manager.calibration_add_point_mode:
            panel.disable_add_point_mode()
        logger.debug(f"Calibration GUI updated: {stats.get('point_count', 0)} points")

    # --- Isotherm backward-compat delegations (prefer event bus) ---
    def set_isotherm_enabled(self, enabled: bool):
        self.isotherm_manager.set_enabled(enabled)

    def set_isotherm_mode(self, mode: str):
        self.isotherm_manager.set_mode(mode)

    def set_isotherm_low_threshold(self, val: float):
        self.isotherm_manager.set_low_threshold(val)

    def set_isotherm_high_threshold(self, val: float):
        self.isotherm_manager.set_high_threshold(val)

    def set_isotherm_color(self, color: str):
        self.isotherm_manager.set_color(color)

    def set_isotherm_band_manager(self, band_manager):
        self.isotherm_manager.set_band_manager(band_manager)

    def set_isotherm_multiband_mode(self, enabled: bool):
        self.isotherm_manager.set_multiband_mode(enabled)

    # =========================================================================
    # Event Bus Feedback Handlers (proactive signal-based responses)
    # =========================================================================

    def _bus_toggle_recording(self, enabled: bool):
        """Handle recording toggle via event bus with feedback."""
        self.toggle_recording(enabled)
        self.event_bus.recording_state_changed.emit(
            self.media_manager.recording_enabled if self.media_manager else False
        )

    def _bus_capture_snapshot(self):
        """Handle snapshot request via event bus."""
        self.capture_snapshot()

    def _bus_compute_calibration(self, method: str, degree: int):
        """Handle calibration compute with feedback signal."""
        success = self.calibration_manager.compute_calibration(method, degree)
        self.event_bus.calibration_compute_result.emit(success)
        if success:
            self.event_bus.calibration_gui_update_requested.emit()

    def _bus_clear_calibration(self):
        """Handle calibration clear with GUI update."""
        self.calibration_manager.clear_calibration()
        self.event_bus.calibration_gui_update_requested.emit()

    def _bus_export_calibration(self, filepath: str):
        """Handle calibration export with feedback signal."""
        success = self.calibration_manager.export_calibration(filepath)
        self.event_bus.calibration_export_result.emit(success, filepath)

    def _bus_import_calibration(self, filepath: str):
        """Handle calibration import with feedback signal."""
        success = self.calibration_manager.import_calibration(filepath)
        self.event_bus.calibration_import_result.emit(success, filepath)
        if success:
            self.event_bus.calibration_gui_update_requested.emit()

    def _bus_remove_calibration_point(self, index: int):
        """Handle calibration point removal with feedback signal."""
        success = self.calibration_manager.remove_calibration_point(index)
        self.event_bus.calibration_point_remove_result.emit(success)
        if success:
            self.event_bus.calibration_gui_update_requested.emit()

    # --- Anomaly Processor helpers ---

    def _bus_set_fade_strength(self, value: float):
        if hasattr(self, 'thermal_processor'):
            self.thermal_processor.anomaly_fade_strength = value

    def _bus_set_fade_distance(self, value: float):
        if hasattr(self, 'thermal_processor'):
            self.thermal_processor.anomaly_max_distance = int(value)

    def _bus_set_motion_threshold(self, value: float):
        if hasattr(self, 'thermal_processor'):
            self.thermal_processor.motion_threshold = int(value)

    def _bus_set_edge_thresholds(self, low: float, high: float):
        if hasattr(self, 'thermal_processor'):
            self.thermal_processor.edge_threshold_low = int(low)
            self.thermal_processor.edge_threshold_high = int(high)

    def _bus_set_hot_spot_percentile(self, value: float):
        if hasattr(self, 'thermal_analyzer'):
            self.thermal_analyzer.hot_spot_percentile = value

    def _bus_set_cold_spot_percentile(self, value: float):
        if hasattr(self, 'thermal_analyzer'):
            self.thermal_analyzer.cold_spot_percentile = value

    def _bus_set_min_anomaly_size(self, value: float):
        if hasattr(self, 'thermal_analyzer'):
            self.thermal_analyzer.min_anomaly_size = int(value)

    def _bus_set_max_hot_spots(self, count: int):
        if hasattr(self, 'thermal_analyzer'):
            self.thermal_analyzer.max_hot_spots = count

    def _bus_set_max_cold_spots(self, count: int):
        if hasattr(self, 'thermal_analyzer'):
            self.thermal_analyzer.max_cold_spots = count

    # --- Spotmeter / Estimation helpers ---

    def _bus_set_spotmeter_enabled(self, enabled: bool):
        if hasattr(self, 'thermal_analyzer'):
            self.thermal_analyzer.spotmeter_enabled = enabled

    def _bus_set_spotmeter_mode(self, mode: str):
        if hasattr(self, 'thermal_analyzer'):
            self.thermal_analyzer.spotmeter_mode = mode

    def _bus_set_estimation_enabled(self, enabled: bool):
        self.radiometric_controller.set_estimation_enabled(enabled)
        if self.thermal_analyzer:
            self.thermal_analyzer.estimation_enabled = enabled

    def _bus_set_estimation_range(self, low: float, high: float):
        if hasattr(self, 'thermal_estimator'):
            self.thermal_estimator.scene_min_c = low
            self.thermal_estimator.scene_max_c = high
            logger.info(f"Estimation scene range set to {low:.1f}C - {high:.1f}C")

    def _bus_calibrate_single_point(self, temp: float):
        """Single-point calibration: sample the current center pixel as the reference."""
        if not hasattr(self, 'thermal_estimator') or self._last_thermal_frame is None:
            return
        frame = self._last_thermal_frame
        h, w = frame.shape[:2]
        agc_value = int(frame[h // 2, w // 2])
        fpa = self._last_fpa_temp_c if self._last_fpa_temp_c is not None else 25.0
        self.thermal_estimator.calibrate_single_point(agc_value, temp, fpa)
        if self.gui and hasattr(self.gui, 'radiometric_panel'):
            self.gui.radiometric_panel.set_calibration_offset(self.thermal_estimator.calibration_offset)
        logger.info(f"Single-point calibration: AGC={agc_value} at center -> {temp}C")

    def _bus_calibrate_two_point(self, t1: float, t2: float):
        """
        Two-point calibration: read the coldest/hottest values already in
        the current frame (5th/95th percentile, avoiding single-pixel noise)
        as the two AGC references, paired with the two known temperatures.
        Assumes both reference objects (e.g. ice water and boiling water)
        are visible in the same frame at calibration time.
        """
        if not hasattr(self, 'thermal_estimator') or self._last_thermal_frame is None:
            return
        frame = self._last_thermal_frame
        agc_low = float(np.percentile(frame, 5))
        agc_high = float(np.percentile(frame, 95))
        fpa = self._last_fpa_temp_c if self._last_fpa_temp_c is not None else 25.0
        self.thermal_estimator.calibrate_two_point(agc_low, t1, agc_high, t2, fpa)
        if self.gui and hasattr(self.gui, 'radiometric_panel'):
            self.gui.radiometric_panel.set_calibration_offset(self.thermal_estimator.calibration_offset)
        logger.info(f"Two-point calibration: AGC {agc_low:.0f}->{t1}C, {agc_high:.0f}->{t2}C")

    def _bus_get_sensor_temps(self):
        """Fetch FPA/housing temps and emit result signal."""
        fpa = housing = 0.0
        try:
            cam = getattr(self, 'thermal_camera', None)
            if cam:
                if hasattr(cam, 'get_fpa_temperature'):
                    fpa = cam.get_fpa_temperature() or 0.0
                if hasattr(cam, 'get_housing_temperature'):
                    housing = cam.get_housing_temperature() or 0.0
        except Exception as e:
            logger.error(f"Error reading sensor temps: {e}")
        self.event_bus.sensor_temps_result.emit(float(fpa), float(housing))

    # --- Radiometric / backend ---

    def _bus_set_radiometric_method(self, mode: str):
        """Set radiometric conversion method."""
        if hasattr(self, 'radiometric_controller') and hasattr(self.radiometric_controller, 'set_conversion_method'):
            self.radiometric_controller.set_conversion_method(mode)
            logger.info(f"Radiometric method set to: {mode}")
        else:
            logger.debug(f"radiometric_controller.set_conversion_method not available — mode={mode}")

    # --- ROI palette clear helper ---

    def _bus_clear_roi_palette(self, roi_id: str):
        """Clear ROI-specific palette."""
        if hasattr(self, 'palette_manager') and hasattr(self.palette_manager, 'clear_roi_palette'):
            self.palette_manager.clear_roi_palette(roi_id)
        elif hasattr(self, 'roi_manager'):
            roi = self.roi_manager.get_roi(roi_id) if hasattr(self.roi_manager, 'get_roi') else None
            if roi and hasattr(roi, 'clear_palette'):
                roi.clear_palette()

    # =========================================================================
    # Camera & Boson SDK Methods
    # =========================================================================

    def set_device(self, device_name: str):
        """
        Set the compute device ('cpu' or 'cuda') for GPU-capable processing:
        thermal_processor's VPI backend (Jetson, or Linux with VPI
        installed - VPI has no Windows build at all), parallax_compensator's
        depth-estimation model (CUDA via PyTorch, works on any platform
        with a CUDA-enabled torch install), and fusion_processor's
        laplacian_pyramid mode (also CUDA via PyTorch - see
        FusionProcessor._laplacian_pyramid_gpu; every other fusion mode
        still has no GPU-accelerated code path, see has_cuda's comment in
        FusionProcessor.__init__).

        Settings panel combo emits "CPU"/"CUDA" (uppercase); normalize
        once here rather than relying on every downstream consumer to
        handle case, since thermal_processor.set_device()'s own validation
        is case-sensitive.
        """
        device = device_name.strip().lower()
        if device not in ('cpu', 'cuda'):
            logger.warning(f"Invalid device '{device_name}' (expected 'cpu' or 'cuda')")
            return

        logger.info(f"Compute device set to: {device}")
        self.config.device = device

        if self.thermal_processor:
            self.thermal_processor.set_device(device)

        if self.parallax_compensator:
            self.parallax_compensator.set_device(device)

        if self.fusion_processor:
            self.fusion_processor.set_device(device)

    def execute_camera_command(self, role: str, command: str, params: Optional[dict] = None) -> dict:
        """Execute a generic camera command via the CameraPluginHost."""
        return self.plugin_host.execute_command(role, command, params)

    # =========================================================================
    # Parallax Compensation Methods
    # =========================================================================

    def enable_parallax_compensation(self, enabled: bool):
        """Enable or disable parallax compensation."""
        if self.parallax_compensator:
            self.parallax_compensator.enable(enabled)
            logger.info(f"Parallax compensation: {'ON' if enabled else 'OFF'}")
        else:
            logger.warning("ParallaxCompensator not available")

    def set_parallax_baseline(self, baseline_mm: float):
        """Set the camera-pair baseline distance in millimetres."""
        if self.parallax_compensator:
            self.parallax_compensator.set_baseline(baseline_mm)
        else:
            logger.warning("ParallaxCompensator not available")

    def set_parallax_shift(self, dx: int, dy: int):
        """Set a constant manual alignment shift (pixels) for a fixed mounting offset."""
        if self.parallax_compensator:
            self.parallax_compensator.set_manual_shift(dx, dy)
        else:
            logger.warning("ParallaxCompensator not available")

    def set_parallax_camera_optics(self, optics: dict):
        """
        Set per-camera lens focal length/sensor width (mm) - real specs
        from the attached lens' datasheet, since neither the thermal nor
        RGB camera SDKs used here report this themselves (Boson ships
        several fixed lens options with no SDK-queryable FOV; RGB lenses
        are often swappable third-party glass). Drives both the geometric
        auto-alignment shift and the FOV crop-zoom factor.
        """
        if not self.parallax_compensator:
            logger.warning("ParallaxCompensator not available")
            return
        geometry = self.parallax_compensator.geometry
        geometry.thermal_focal_length_mm = optics.get('thermal_focal_length_mm', geometry.thermal_focal_length_mm)
        geometry.thermal_sensor_width_mm = optics.get('thermal_sensor_width_mm', geometry.thermal_sensor_width_mm)
        geometry.rgb_focal_length_mm = optics.get('rgb_focal_length_mm', geometry.rgb_focal_length_mm)
        geometry.rgb_sensor_width_mm = optics.get('rgb_sensor_width_mm', geometry.rgb_sensor_width_mm)
        logger.info(f"Parallax camera optics updated: {optics}")

    def set_parallax_zoom(self, zoom_factor: float):
        """Set the manual crop-in zoom factor (1.0 = none) directly, independent of auto-alignment."""
        if self.parallax_compensator:
            self.parallax_compensator.set_fov_zoom_factor(zoom_factor)
        else:
            logger.warning("ParallaxCompensator not available")

    def set_parallax_correction_target(self, target: str):
        """Set which frame ("thermal" or "rgb") apply_correction() warps/crops."""
        if self.parallax_compensator:
            self.parallax_compensator.set_correction_target(target)
        else:
            logger.warning("ParallaxCompensator not available")

    def set_parallax_rgb_target_max_width(self, width):
        """Cap correction_target=="rgb"'s working resolution (None/0 = uncapped, full native)."""
        if self.parallax_compensator:
            self.parallax_compensator.set_rgb_target_max_width(width)
        else:
            logger.warning("ParallaxCompensator not available")

    def set_parallax_depth_method(self, method: str):
        """Set the depth estimation method ('simplified', 'realsense', 'depthanything', 'midas').

        Reconstructs the DepthEstimator so model_loaded / pipeline state is
        always consistent with the requested method.
        """
        if self.parallax_compensator:
            from .processing.parallax_compensator import DepthEstimator
            old_estimator = self.parallax_compensator.depth_estimator
            old_device = old_estimator._device_requested
            new_estimator = DepthEstimator(method=method, device=old_device)
            # A fresh DepthEstimator has no hardware depth source wired in -
            # carry over the active one (if any), or "realsense" would
            # silently produce nothing until the RealSense camera happened
            # to reconnect and re-wire it.
            new_estimator._hardware_depth_source = old_estimator._hardware_depth_source
            self.parallax_compensator.depth_estimator = new_estimator
            logger.info(f"Parallax depth method set to: {method}")
        else:
            logger.warning("ParallaxCompensator not available")

    def _bus_depth_map_display_toggled(self, show: bool):
        """Handle event bus signal to toggle depth map display on parallax compensator."""
        if self.parallax_compensator:
            if hasattr(self.parallax_compensator, 'set_depth_display'):
                self.parallax_compensator.set_depth_display(show)
            else:
                self.parallax_compensator.show_depth_map = show
            logger.info(f"Parallax depth map display set to: {show}")
        else:
            logger.warning("ParallaxCompensator not available for depth map display toggle")

    def _bus_displacement_display_toggled(self, show: bool):
        """Handle event bus signal to toggle displacement-vector overlay on parallax compensator."""
        if self.parallax_compensator and hasattr(self.parallax_compensator, 'set_displacement_display'):
            self.parallax_compensator.set_displacement_display(show)
        else:
            logger.warning("ParallaxCompensator not available for displacement overlay toggle")

    def _bus_parallax_auto_alignment_requested(self, working_distance_m: float, refine_with_depth: bool):
        """
        Handle a one-time auto-alignment request from the Parallax panel:
        compute a static shift + FOV crop-zoom from camera geometry (and
        optionally one depth-estimation call), then report the result back
        so the panel can display it. Runs once on request, not per frame -
        the computed values become a plain manual shift afterward, costing
        nothing further until recalculated.
        """
        if not self.parallax_compensator:
            logger.warning("ParallaxCompensator not available for auto-alignment")
            return
        rgb_frame = getattr(self, '_last_rgb_frame', None) if refine_with_depth else None
        dx, zoom = self.parallax_compensator.compute_auto_alignment(working_distance_m, rgb_frame)
        dy = self.parallax_compensator.manual_shift_y
        if self.event_bus:
            self.event_bus.parallax_auto_alignment_result.emit(dx, dy, zoom)

    # =========================================================================
    # Baseline & Misc Methods
    # =========================================================================

    def lock_baseline(self, enabled: bool):
        """Lock or unlock the thermal analysis baseline temperature.

        When locking, the current frame's mean temperature is stored and passed
        to ThermalAnalyzer as the reference baseline.
        """
        if not self.thermal_analyzer:
            return
        if enabled:
            # Capture mean temperature of the current frame as the baseline
            baseline_val = None
            if self.thermal_analyzer and hasattr(self.thermal_analyzer, 'last_stats'):
                last = self.thermal_analyzer.last_stats
                if last and hasattr(last, 'mean'):
                    baseline_val = last.mean
            if baseline_val is None:
                baseline_val = 0.0
            self.thermal_analyzer.set_baseline(baseline_val)
            logger.info(f"Baseline locked at {baseline_val:.2f}")
        else:
            self.thermal_analyzer.set_baseline(None)
            logger.info("Baseline unlocked")
