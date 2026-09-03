"""
AppEventBus — Central typed signal broker for GUI ↔ backend communication.

The bus does NOT contain business logic. It defines ``pyqtSignal``
declarations that the GUI emits (intents) and the backend connects
to (reactions). Feedback signals flow in the reverse direction.

Usage in ``app.py``::

    self.event_bus = AppEventBus()
    self.event_bus.camera_command_requested.connect(self.plugin_host.execute_command_async)

Usage in ``main_window.py``::

    self.event_bus.camera_command_requested.emit("thermal", "ffc", {})
"""

import logging
from PyQt6.QtCore import QObject, pyqtSignal

logger = logging.getLogger(__name__)


class AppEventBus(QObject):
    """Central event bus for decoupling GUI ↔ backend communication.

    Signal naming convention:
      - ``<noun>_<verb_past>``  for intent signals   (GUI → backend)
      - ``<noun>_<noun>``      for feedback signals  (backend → GUI)
    """

    # =====================================================================
    # Generic Hardware-Agnostic Camera Signals
    # =====================================================================
    camera_command_requested = pyqtSignal(str, str, dict)   # (role: 'thermal'|'rgb', command_name: str, params: dict)
    camera_reassign_requested = pyqtSignal(int, int)        # (thermal_id, rgb_id)
    device_changed = pyqtSignal(str)                        # device_name

    # Camera Feedback Signals
    camera_command_result = pyqtSignal(str, str, dict)      # (role, command_name, result_dict)
    camera_connected = pyqtSignal(str, dict)                # (role, capabilities_dict)
    camera_disconnected = pyqtSignal(str)                   # (role)
    sdk_connected = pyqtSignal(str, dict)                   # (role, info_dict)
    sdk_disconnected = pyqtSignal(str)                      # (role)
    panel_ready = pyqtSignal(str, object)                   # (role, QWidget)
    ports_scan_result = pyqtSignal(list)                    # list of COM ports

    # =====================================================================
    # Recording & Snapshots
    # =====================================================================
    recording_toggled = pyqtSignal(bool)                    # enabled
    snapshot_requested = pyqtSignal()
    freeze_toggled = pyqtSignal(bool)                       # enabled
    recording_state_changed = pyqtSignal(bool)              # is_recording

    # =====================================================================
    # Manual Threshold (8-bit simple)
    # =====================================================================
    threshold_enabled_changed = pyqtSignal(bool)
    threshold_mode_changed = pyqtSignal(str)
    threshold_min_changed = pyqtSignal(float)
    threshold_max_changed = pyqtSignal(float)
    threshold_use_raw_changed = pyqtSignal(bool)
    threshold_viz_changed = pyqtSignal(str)
    threshold_stats_updated = pyqtSignal(float, int, int)   # pct, count, total

    # =====================================================================
    # Isotherm (16-bit temperature-aware)
    # =====================================================================
    isotherm_enabled_changed = pyqtSignal(bool)
    isotherm_mode_changed = pyqtSignal(str)
    isotherm_low_threshold_changed = pyqtSignal(float)
    isotherm_high_threshold_changed = pyqtSignal(float)
    isotherm_color_changed = pyqtSignal(str)
    isotherm_band_manager_set = pyqtSignal(object)          # band_manager instance
    isotherm_multiband_changed = pyqtSignal(bool)

    # =====================================================================
    # Calibration
    # =====================================================================
    calibration_add_point_mode_changed = pyqtSignal(bool, float)  # enabled, ref_temp
    calibration_point_add_requested = pyqtSignal(int, int)        # x, y pixel coords - actually add a point here
    calibration_compute_requested = pyqtSignal(str, int)          # method, degree
    calibration_clear_requested = pyqtSignal()
    calibration_export_requested = pyqtSignal(str)                # filepath
    calibration_import_requested = pyqtSignal(str)                # filepath
    calibration_enabled_changed = pyqtSignal(bool)
    calibration_point_removed = pyqtSignal(int)                   # index

    # Calibration Feedback
    calibration_compute_result = pyqtSignal(bool)                 # success
    calibration_export_result = pyqtSignal(bool, str)             # success, path
    calibration_import_result = pyqtSignal(bool, str)             # success, path
    calibration_point_remove_result = pyqtSignal(bool)            # success
    calibration_gui_update_requested = pyqtSignal()               # ask GUI to refresh

    # =====================================================================
    # View / Fusion
    # =====================================================================
    view_mode_cycled = pyqtSignal()
    palette_cycled = pyqtSignal()
    palette_set = pyqtSignal(str)
    fusion_mode_changed = pyqtSignal(str)
    fusion_alpha_changed = pyqtSignal(float)
    fusion_priority_changed = pyqtSignal(str)
    fusion_strength_changed = pyqtSignal(float)
    fusion_fuzziness_changed = pyqtSignal(float)
    fusion_color_mode_changed = pyqtSignal(str)
    edge_strength_changed = pyqtSignal(float)
    edge_fuzziness_changed = pyqtSignal(float)
    edge_color_changed = pyqtSignal(str)
    detail_strength_changed = pyqtSignal(float)
    detail_quality_changed = pyqtSignal(str)
    laplacian_gpu_changed = pyqtSignal(bool)
    laplacian_cpu_scale_changed = pyqtSignal(float)
    fusion_3d_strength_changed = pyqtSignal(float)
    fusion_3d_mode_changed = pyqtSignal(str)
    fusion_3d_data_source_changed = pyqtSignal(str)
    fusion_3d_fog_range_changed = pyqtSignal(float, float)   # near_m, far_m
    fusion_3d_contour_interval_changed = pyqtSignal(float)   # interval_m

    # =====================================================================
    # ROI
    # =====================================================================
    auto_roi_requested = pyqtSignal()
    clear_rois_requested = pyqtSignal()
    roi_deleted = pyqtSignal(str)                           # roi_id
    roi_palette_changed = pyqtSignal(str, str)              # roi_id, palette_name
    roi_palette_cleared = pyqtSignal(str)                   # roi_id

    # =====================================================================
    # Analysis / Anomaly
    # =====================================================================
    anomaly_priority_toggled = pyqtSignal(bool)
    anomaly_types_changed = pyqtSignal(dict)
    anomaly_fade_strength_changed = pyqtSignal(float)
    anomaly_fade_distance_changed = pyqtSignal(float)
    anomaly_motion_threshold_changed = pyqtSignal(float)
    anomaly_edge_thresholds_changed = pyqtSignal(float, float)  # low, high
    hot_spot_percentile_changed = pyqtSignal(float)
    cold_spot_percentile_changed = pyqtSignal(float)
    min_anomaly_size_changed = pyqtSignal(float)

    # =====================================================================
    # Environmental / Radiometric
    # =====================================================================
    emissivity_changed = pyqtSignal(float)
    atmospheric_temperature_changed = pyqtSignal(float)
    atmospheric_transmission_changed = pyqtSignal(float)
    temperature_unit_changed = pyqtSignal(str)
    radiometric_enabled_changed = pyqtSignal(bool)
    temperature_range_changed = pyqtSignal(float, float)        # low, high
    radiometric_range_apply_requested = pyqtSignal(float, float)# low, high
    radiometric_method_changed = pyqtSignal(str)                 # "t-linear" or "lut"

    # =====================================================================
    # Parallax
    # =====================================================================
    parallax_toggled = pyqtSignal(bool)
    parallax_baseline_changed = pyqtSignal(float)
    parallax_method_changed = pyqtSignal(str)
    depth_map_display_toggled = pyqtSignal(bool)
    displacement_display_toggled = pyqtSignal(bool)
    parallax_shift_changed = pyqtSignal(int, int)
    parallax_auto_alignment_requested = pyqtSignal(float, bool)  # working_distance_m, refine_with_depth
    parallax_auto_alignment_result = pyqtSignal(int, int, float)  # dx, dy, fov_zoom_factor

    # =====================================================================
    # Analyzer / Processor Settings
    # =====================================================================
    max_hot_spots_changed = pyqtSignal(int)
    max_cold_spots_changed = pyqtSignal(int)
    spotmeter_enabled_changed = pyqtSignal(bool)
    spotmeter_mode_changed = pyqtSignal(str)
    estimation_8bit_enabled_changed = pyqtSignal(bool)
    estimation_range_changed = pyqtSignal(float, float)         # low, high
    calibrate_single_point_requested = pyqtSignal(float)        # reference_temp
    calibrate_two_point_requested = pyqtSignal(float, float)    # t1, t2
    sensor_temps_requested = pyqtSignal()
    sensor_temps_result = pyqtSignal(float, float)               # fpa_temp, housing_temp

    # =====================================================================
    # Gradient Overlay
    # =====================================================================
    gradient_enabled_changed = pyqtSignal(bool)
    gradient_mode_changed = pyqtSignal(str)                     # magnitude|horizontal|vertical|both
    gradient_threshold_changed = pyqtSignal(float)              # °C/px
    gradient_colormap_changed = pyqtSignal(str)                 # hot|cool|jet|viridis|gray

    # =====================================================================
    # Line Profile Tool
    # =====================================================================
    line_profile_mode_toggled = pyqtSignal(bool)                # enable/disable draw mode
    line_profile_deleted = pyqtSignal(str)                      # line_id

    # =====================================================================
    # Spot Selection
    # =====================================================================
    spot_selected = pyqtSignal(str)                             # spot_id selected in panel

    # =====================================================================
    # Settings / Baseline
    # =====================================================================
    baseline_lock_toggled = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        logger.info("AppEventBus initialized with generic camera architecture")
