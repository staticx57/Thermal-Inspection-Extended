#!/usr/bin/env python3
"""
Thermal + RGB Fusion Inspection Tool
Transformed from ThermalFusionDrivingAssist

Features:
- Thermal-RGB fusion (7 fusion modes - PARAMOUNT!)
- Smart ROI management (automatic and manual)
- Comprehensive thermal analysis
- Multi-palette support (global + per-ROI)
- Motion detection
- Edge detection
- Real-time and recorded media support

Cross-platform: Windows, Linux, Jetson (with VPI acceleration)
"""

import sys
import time
import logging
import argparse
import threading
import platform
from queue import Queue
from pathlib import Path
import cv2
import os
import numpy as np
import faulthandler
from typing import Optional, Dict, List, Tuple
from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed

# Enable faulthandler for debugging
faulthandler.enable()

# Camera modules
from flir_camera import FLIRBosonCamera
from flirpy_thermal_backend import FlirpyThermalBackend
from camera_factory import create_rgb_camera, autodetect_camera_types
from camera_detector import CameraDetector
from camera_initializer import CameraInitializer
from placeholder_frames import create_thermal_placeholder, create_rgb_placeholder

# Processing modules (NEW - Inspection focused)
from thermal_processor import ThermalProcessor
from thermal_analyzer import (
    ThermalAnalyzer,
    ThresholdMode,
    ThresholdVisualization,
    ThresholdDetectionResult
)
from roi_manager import ROIManager, ROISource
from roi_radiometric_analyzer import ROIRadiometricAnalyzer
from palette_manager import PaletteManager, PaletteType
from media_recorder import VideoRecorder, VideoPlayer, SnapshotManager

# Core modules (PRESERVED - Fusion is paramount!)
from fusion_processor import FusionProcessor

# Parallax compensation (optional, disabled by default)
try:
    from parallax_compensator import ParallaxCompensator, CameraGeometry
    PARALLAX_AVAILABLE = True
except ImportError:
    PARALLAX_AVAILABLE = False
    logger = logging.getLogger(__name__)
    logger.info("Parallax compensation not available")

# Measurement points (radiometric temperature measurement)
try:
    from measurement_points import MeasurementPointManager
    MEASUREMENT_POINTS_AVAILABLE = True
except ImportError:
    MEASUREMENT_POINTS_AVAILABLE = False
    logger = logging.getLogger(__name__)
    logger.info("Measurement points not available")

# Radiometric calibration
try:
    from radiometric_calibration import RadiometricCalibrator
    RADIOMETRIC_CALIBRATION_AVAILABLE = True
except ImportError:
    RADIOMETRIC_CALIBRATION_AVAILABLE = False
    logger = logging.getLogger(__name__)
    logger.info("Radiometric calibration not available")

# 8-bit pseudo-radiometric temperature estimation (works on ALL Bosons)
try:
    from thermal_estimator import ThermalTemperatureEstimator
    THERMAL_ESTIMATION_AVAILABLE = True
    logger = logging.getLogger(__name__)
    logger.info("8-bit temperature estimation module available")
except ImportError as e:
    THERMAL_ESTIMATION_AVAILABLE = False
    logger = logging.getLogger(__name__)
    logger.warning(f"Thermal temperature estimator not available: {e}")

# Performance monitoring
from performance_monitor import PerformanceMonitor

# View mode
from view_mode import ViewMode


def setup_logging():
    """Configure logging with console and file output."""
    from logging.handlers import RotatingFileHandler

    detailed_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
    )
    simple_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(simple_formatter)
    
    # Fix Unicode encoding issues on Windows
    try:
        console_handler.stream.reconfigure(encoding='utf-8', errors='replace')
    except AttributeError:
        # Python < 3.7 fallback
        import codecs
        console_handler.stream = codecs.getwriter('utf-8')(console_handler.stream.buffer, errors='replace')
    
    root_logger.addHandler(console_handler)

    # File handler
    try:
        file_handler = RotatingFileHandler(
            'thermal_inspection_debug.log',
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(detailed_formatter)
        root_logger.addHandler(file_handler)
        logging.info("[OK] Debug logging: thermal_inspection_debug.log")
    except Exception as e:
        logging.warning(f"Could not create debug log: {e}")

    return logging.getLogger(__name__)


logger = setup_logging()


def create_thermal_backend(backend_type: str, device_id: int, resolution: Tuple[int, int],
                           enable_sdk: bool = False, com_port: Optional[str] = None):
    """
    Factory function to create thermal camera backend.

    Args:
        backend_type: 'opencv' for FLIRBosonCamera, 'flirpy' for FlirpyThermalBackend
        device_id: Video device ID
        resolution: Camera resolution (width, height)
        enable_sdk: Enable Boson SDK for serial control
        com_port: COM port for SDK control

    Returns:
        Thermal camera backend instance
    """
    if backend_type == 'flirpy':
        logger.info(f"Creating flirpy thermal backend (16-bit Y16 + SDK via {com_port or 'COM7'})")
        backend = FlirpyThermalBackend(
            com_port=com_port or 'COM7',
            auto_configure=True  # Auto-configure T-Linear mode
        )
        # Flirpy backend handles SDK control internally via dual-path architecture
        # SDK control is handled separately via BosonSDK wrapper
        return backend
    else:  # Default to 'opencv' (FLIRBosonCamera)
        logger.info(f"Creating OpenCV thermal backend (device_id={device_id}, resolution={resolution}, sdk={enable_sdk})")
        return FLIRBosonCamera(
            device_id=device_id,
            resolution=resolution,
            enable_sdk=enable_sdk,
            com_port=com_port
        )


def detect_platform():
    """Detect platform (Jetson ARM or x86-64 workstation)."""
    machine = platform.machine()
    is_jetson = os.path.exists('/etc/nv_tegra_release') or 'tegra' in platform.platform().lower()

    platform_info = {
        'machine': machine,
        'is_jetson': is_jetson,
        'is_arm': machine in ['aarch64', 'arm64', 'armv7l'],
        'is_x86': machine in ['x86_64', 'AMD64', 'i386', 'i686'],
        'system': platform.system(),
        'platform': platform.platform()
    }

    logger.info(f"Platform: {platform_info}")
    return platform_info


class ThermalInspectionFusion:
    """
    Main inspection application with thermal-RGB fusion.

    Transformed from ThermalRoadMonitorFusion (ADAS) to inspection tool.
    """

    def __init__(self, args, qt_app=None):
        """
        Initialize inspection application.

        Args:
            args: Command-line arguments
            qt_app: QApplication instance (if using Qt GUI)
        """
        self.args = args
        self.qt_app = qt_app
        self.platform_info = detect_platform()

        # Auto-detect cameras if not explicitly specified
        should_autodetect = getattr(args, 'auto_detect_cameras', True)
        thermal_specified = getattr(args, 'thermal_device', None) is not None
        rgb_specified = getattr(args, 'rgb_device', None) is not None

        # Skip legacy auto-detection if using robust init (it will handle detection)
        use_robust_init = getattr(args, 'use_robust_camera_init', True)

        if should_autodetect and (not thermal_specified or not rgb_specified) and not use_robust_init:
            try:
                logger.info("=" * 60)
                logger.info("AUTO-DETECTING CAMERAS (LEGACY)")
                logger.info("=" * 60)

                t_id, r_id = autodetect_camera_types()
                
                # Assign thermal camera
                if not thermal_specified:
                    if t_id is not None:
                        logger.info(f"[OK] Auto-detected Thermal Camera at index {t_id}")
                        self.args.thermal_device = t_id
                    else:
                        logger.warning("[WARN] No thermal camera detected, defaulting to index 1")
                        self.args.thermal_device = 1  # Changed from 0 to 1 (640x512 thermal)
                else:
                    logger.info(f"Using specified Thermal Camera at index {self.args.thermal_device}")
                
                # Assign RGB camera
                if not rgb_specified:
                    if r_id is not None:
                        logger.info(f"[OK] Auto-detected RGB Camera at index {r_id}")
                        self.args.rgb_device = r_id
                    else:
                        logger.warning("[WARN] No RGB camera detected, defaulting to index 0")
                        self.args.rgb_device = 0  # Changed from 2 to 0 (640x480 RGB)
                else:
                    logger.info(f"Using specified RGB Camera at index {self.args.rgb_device}")
                    
                logger.info("=" * 60)
                
            except Exception as e:
                logger.error(f"Camera auto-detection failed: {e}")
                import traceback
                traceback.print_exc()
                # Fallback to defaults
                if not thermal_specified:
                    self.args.thermal_device = 0
                if not rgb_specified:
                    self.args.rgb_device = 1

        # Cameras
        self.thermal_camera: Optional[FLIRBosonCamera] = None
        self.rgb_camera = None
        self.rgb_available = False
        self.thermal_connected = False

        # Threaded camera capture (for performance)
        self.use_threaded_capture = getattr(args, 'threaded_capture', True)
        self.threaded_capture = None

        # NEW: Inspection processors
        self.thermal_processor: Optional[ThermalProcessor] = None
        self.thermal_analyzer: Optional[ThermalAnalyzer] = None
        self.roi_manager: Optional[ROIManager] = None
        self.roi_radiometric_analyzer: Optional[ROIRadiometricAnalyzer] = None
        self.palette_manager: Optional[PaletteManager] = None

        # 8-Bit Temperature Estimator (works on ALL Bosons with SDK)
        self.temp_estimator: Optional[ThermalTemperatureEstimator] = None
        self.temp_estimation_enabled: bool = False
        self.active_temp_mode: str = "none"  # "8bit", "16bit", or "none"
        self.latest_temp_data: Optional[Dict] = None  # Stores latest temperature statistics

        # PRESERVED: Fusion processor (PARAMOUNT!)
        self.fusion_processor: Optional[FusionProcessor] = None

        # GUI
        self.gui = None
        self.gui_type = None

        # Performance monitoring
        self.perf_monitor = None

        # Runtime state
        self.running = False
        self.last_frame_time = time.time()
        self.frame_count = 0
        self.fps = 0.0
        self.device = getattr(args, 'device', 'cuda')
        self.temperature_unit = 'C' # Default to Celsius
        
        # Performance settings
        self.target_fps_rgb = 30
        self.target_fps_thermal = 60
        self.target_fps_fusion = 30
        self.frame_skip_counter = 0

        # Auto-ROI optimization - don't run every frame
        self.auto_roi_frame_counter = 0
        self.auto_roi_update_interval = 10  # Update auto-ROIs every 10 frames
        
        # Camera specific flags
        self.is_flir_boson = False
        self.reconfiguring = False  # Flag to pause main loop during camera reconfiguration

        # Persisted device IDs for stable switching
        self.effective_thermal_device_id = None
        self.effective_rgb_device_id = None
        self.rgb_camera_source = 'uvc'

        # Inspection mode settings
        self.inspection_mode = getattr(args, 'mode', 'realtime')  # realtime or playback
        self.recording_enabled = False
        self.frame_frozen = False
        self.video_writer = None
        
        # Logging state (Enhancement #12)
        self.last_spot_log_time = 0
        self.spot_log_interval = 10.0  # Log every 10 seconds

        # Media recorder (NEW - Phase 6)
        self.video_recorder: Optional[VideoRecorder] = None
        self.video_player: Optional[VideoPlayer] = None
        self.snapshot_manager: Optional[SnapshotManager] = None

        # Fusion settings (PRESERVED!)
        self.fusion_mode = getattr(args, 'fusion_mode', 'thermal_overlay')
        self.fusion_alpha = getattr(args, 'fusion_alpha', 0.5)
        self.fusion_priority = 'thermal'  # Default fusion priority
        self.rgb_fusion_color_mode = 'color'  # Default RGB mode: color or grayscale
        self.available_fusion_modes = [
            'alpha_blend', 'edge_enhanced', 'thermal_overlay',
            'side_by_side', 'picture_in_picture', 'max_intensity',
            'feature_weighted'
        ]
        self.current_fusion_mode_index = 0
        if self.fusion_mode in self.available_fusion_modes:
            self.current_fusion_mode_index = self.available_fusion_modes.index(self.fusion_mode)

        # View mode
        self.view_mode = ViewMode.THERMAL_ONLY

        # FPS smoothing
        self.frame_times = deque(maxlen=60)
        self.smoothed_fps = 60.0

        # Camera connection state (hot-plug support)
        self.last_thermal_scan_time = 0
        self.thermal_scan_interval = 3.0  # Scan every 3 seconds
        self.last_rgb_scan_time = 0
        self.rgb_scan_interval = 5.0

        # Processing state
        self.latest_motion_detections = []
        self.latest_edge_clusters = []
        self.latest_hot_spots = []
        self.latest_cold_spots = []
        self.latest_anomalies = []
        self.latest_stats = None
        self.latest_display_frame = None
        self.latest_rois = []
        self.last_thermal_frame = None  # For Auto-ROI detection

        # ROI auto-detection settings
        self.auto_roi_enabled = getattr(args, 'auto_roi', False)
        self.auto_roi_methods = {
            'temperature': True,
            'gradient': True,
            'motion': True,
            'edge': True
        }

        # Anomaly type filtering (for anomaly priority feature)
        self.enabled_anomaly_types = {
            "motion": True,
            "edges": True,
            "hot_spots": True,
            "cold_spots": True,
            "thermal_anomalies": True,
            "enhanced_fusion": False  # Off by default (performance)
        }

        # Manual threshold detection state
        self.manual_threshold_enabled = False
        self.manual_threshold_mode = ThresholdMode.ABOVE
        self.manual_threshold_min = 50.0  # Default: 50% (percentage mode)
        self.manual_threshold_max = 75.0  # Default: 75% (percentage mode)
        self.manual_threshold_use_raw = False  # Default: percentage mode (not raw)
        self.manual_threshold_viz_mode = ThresholdVisualization.GRAYSCALE_NON_ANOMALY
        self.latest_threshold_result: Optional[ThresholdDetectionResult] = None

        # Parallel processing configuration (Phase 1 optimization)
        self.enable_parallel_processing = getattr(args, 'enable_parallel', True)
        self.max_detection_workers = getattr(args, 'max_workers', 5)

        # ThreadPoolExecutor for parallel detection tasks
        if self.enable_parallel_processing:
            self.detection_executor = ThreadPoolExecutor(
                max_workers=self.max_detection_workers,
                thread_name_prefix="detection"
            )
            self.roi_executor = ThreadPoolExecutor(
                max_workers=4,
                thread_name_prefix="roi_analysis"
            )
            logger.info(f"Parallel processing enabled: {self.max_detection_workers} detection workers, 4 ROI workers")
        else:
            self.detection_executor = None
            self.roi_executor = None
            logger.info("Parallel processing disabled (sequential mode)")

    def _init_cameras_robust(self) -> Tuple[bool, bool]:
        """
        Initialize cameras using robust detection with timeout protection

        Uses the enhanced CameraInitializer which:
        - Auto-detects Firefly (Spinnaker) vs UVC cameras
        - Uses maximum resolution for RGB
        - Has timeout protection to prevent hanging
        - Handles thermal first (priority for inspection)

        Returns:
            (thermal_success, rgb_success) tuple
        """
        logger.info("="*70)
        logger.info("INITIALIZING CAMERAS (ROBUST MODE)")
        logger.info("="*70)

        # Get SDK parameters from args - DEFAULT TO TRUE for auto-connect (Bug #17)
        enable_sdk = getattr(self.args, 'enable_boson_sdk', True)
        com_port = getattr(self.args, 'boson_com_port', 'COM7')

        # Use robust initializer with thermal-first priority
        thermal_cam, rgb_cam = CameraInitializer.init_cameras_prioritized(
            thermal_first=True,
            enable_sdk=enable_sdk,
            com_port=com_port
        )

        # Handle thermal camera
        thermal_success = False
        if thermal_cam:
            self.thermal_camera = thermal_cam
            self.thermal_connected = True
            self.is_flir_boson = True  # Assuming Boson if thermal detected
            thermal_success = True

            # Persist device ID for backend switching (Critical for stability)
            if hasattr(thermal_cam, 'device_id'):
                self.effective_thermal_device_id = thermal_cam.device_id
            elif hasattr(thermal_cam, 'device'):
                self.effective_thermal_device_id = thermal_cam.device
            else:
                self.effective_thermal_device_id = getattr(self.args, 'thermal_device', 2)
            logger.info(f"Persisted thermal device ID: {self.effective_thermal_device_id}")

            # Log SDK status if enabled
            if hasattr(thermal_cam, 'is_sdk_connected') and thermal_cam.is_sdk_connected:
                logger.info("=" * 60)
                logger.info("[OK] Boson SDK connected - serial control enabled")
                info = thermal_cam.get_camera_info()
                if info:
                    logger.info(f"  Camera SN: {info.serial_number}")
                logger.info("=" * 60)

                # Initialize 8-bit temperature estimator when SDK connects
                self._init_8bit_estimation()
            
            # Auto-Scan for SDK if enabled but failed to connect (Robustness)
            elif enable_sdk and (not hasattr(thermal_cam, 'is_sdk_connected') or not thermal_cam.is_sdk_connected):
                logger.warning(f"SDK failed to connect on default port {com_port}, attempting auto-scan...")
                try:
                    available_ports = self.scan_boson_com_ports()
                    for port in available_ports:
                        if port == com_port: continue # Skip already failed port
                        
                        logger.info(f"Trying SDK connection on {port}...")
                        if thermal_cam.connect_sdk(port):
                            logger.info(f"[OK] Found Boson SDK on {port}!")
                            # Update args so it persists for future switches
                            self.args.boson_com_port = port
                            
                            # Log info
                            info = thermal_cam.get_camera_info()
                            if info:
                                logger.info(f"  Camera SN: {info.serial_number}")
                                
                            # Initialize estimator
                            self._init_8bit_estimation()
                            break
                        else:
                            logger.debug(f"Failed on {port}")
                except Exception as e:
                    logger.error(f"Error during SDK auto-scan: {e}")

            # Auto-enable radiometric if available
            if hasattr(thermal_cam, 'enable_radiometric_mode'):
                try:
                    if thermal_cam.enable_radiometric_mode():
                        logger.info("Auto-enabled radiometric mode")
                except:
                    pass
        else:
            logger.warning("Thermal camera initialization failed - using placeholder")

        # Handle RGB camera
        rgb_success = False
        if rgb_cam and not getattr(self.args, 'disable_rgb', False):
            self.rgb_camera = rgb_cam
            self.rgb_available = True
            rgb_success = True

            # Persist RGB info for backend switching
            if hasattr(rgb_cam, 'device_id'):
                self.effective_rgb_device_id = rgb_cam.device_id
            elif hasattr(rgb_cam, 'device'):
                self.effective_rgb_device_id = rgb_cam.device
            
            self.rgb_camera_source = getattr(rgb_cam, 'camera_source', 'uvc')
            logger.info(f"Persisted RGB device ID: {self.effective_rgb_device_id}, Source: {self.rgb_camera_source}")
        else:
            if not getattr(self.args, 'disable_rgb', False):
                logger.warning("RGB camera initialization failed - thermal-only mode")

        logger.info("="*70)
        return (thermal_success, rgb_success)

    def _try_connect_thermal(self) -> bool:
        """
        Try to connect to thermal camera.

        Returns:
            True if successful, False otherwise
        """
        try:
            if self.thermal_camera:
                self.thermal_camera.release()

            logger.info("Scanning for FLIR Boson thermal camera...")

            # NEW: Phase 7 - Enable SDK for serial control
            # CHANGED: Default to True so T-Linear mode can be enabled automatically
            enable_sdk = getattr(self.args, 'enable_boson_sdk', True)  # Changed from False to True
            com_port = getattr(self.args, 'boson_com_port', 'COM7')

            # Determine device ID
            device_id = getattr(self.args, 'thermal_device', None)
            backend_type = getattr(self.args, 'thermal_backend', 'opencv')
            logger.info(f"DEBUG: Initial device_id from args: {device_id}, backend: {backend_type}")
            
            # For flirpy backend, skip camera detection (flirpy auto-detects Boson)
            if backend_type == 'flirpy':
                device_id = 0  # Not used by flirpy, just a placeholder
                logger.info("Flirpy backend - skipping camera detection (auto-detect)")
            elif device_id is None:
                # Auto-detect if not specified (only for opencv backend)
                logger.info("DEBUG: Auto-detecting thermal camera...")
                from camera_detector import CameraDetector
                thermal_info = CameraDetector.find_thermal_camera()
                if thermal_info:
                    device_id = thermal_info.device_id
                    logger.info(f"Auto-detected thermal camera at index {device_id}")
                else:
                    # No thermal camera found - don't blindly grab index 0 (might be RGB)
                    logger.warning("[WARN] No thermal camera detected - will use placeholder")
                    self.thermal_camera = None
                    self.thermal_connected = False
                    return False
            
            logger.info(f"DEBUG: Final device_id: {device_id}")

            # Get backend type from command-line args
            backend_type = getattr(self.args, 'thermal_backend', 'opencv')
            
            # Use factory to create appropriate backend
            self.thermal_camera = create_thermal_backend(
                backend_type=backend_type,
                device_id=device_id,
                resolution=(getattr(self.args, 'width', 640), getattr(self.args, 'height', 512)),
                enable_sdk=enable_sdk,
                com_port=com_port
            )

            if self.thermal_camera.open():
                actual_res = self.thermal_camera.get_actual_resolution()
                logger.info(f"[OK] Thermal camera connected: {actual_res[0]}x{actual_res[1]}")

                # Propagate resolution to GUI overlay for coordinate mapping
                if self.gui and hasattr(self.gui, 'video_widget') and hasattr(self.gui.video_widget, 'overlay'):
                   if hasattr(self.gui.video_widget.overlay, 'set_thermal_resolution'):
                       self.gui.video_widget.overlay.set_thermal_resolution(actual_res[0], actual_res[1])

                # Set FLIR Boson flag
                self.is_flir_boson = True

                # NEW: Log SDK status (Phase 7)
                if self.thermal_camera.is_sdk_connected:
                    logger.info("=" * 60)
                    logger.info("[OK] Boson SDK connected - serial control enabled")
                    info = self.thermal_camera.get_camera_info()
                    if info:
                        logger.info(f"  Camera SN: {info.serial_number}")
                        logger.info(f"  Camera PN: {info.camera_part_number}")
                        logger.info(f"  Sensor PN: {info.sensor_part_number}")
                        logger.info(f"  Software: {info.software_version}")
                        temp = self.thermal_camera.get_fpa_temperature()
                        if temp:
                            logger.info(f"  FPA Temp: {temp[1]:.1f}°C")
                        logger.info(f"  Gain Mode: {info.gain_mode.name if info.gain_mode else 'Unknown'}")
                    logger.info("  Press 'f' to trigger FFC (Flat Field Correction)")
                    logger.info("=" * 60)
                    
                    # Auto-initialize 8-bit temperature estimator (works on ALL Bosons)
                    self._init_8bit_estimation()
                elif enable_sdk:
                    logger.warning("SDK was requested but connection failed - continuing in video-only mode")

                self.thermal_connected = True
                
                # Auto-detect radiometric mode
                is_radiometric = self._detect_radiometric_mode()
                if is_radiometric:
                    self.args.radiometric = True
                    logger.info("Auto-enabled radiometric mode")
                
                # Initialize radiometric panel if GUI exists
                if self.gui and hasattr(self.gui, 'radiometric_panel'):
                    sdk_connected = self.thermal_camera.is_sdk_connected
                    mode_desc = "16-bit Radiometric" if is_radiometric else "8-bit AGC"
                    self.gui.radiometric_panel.set_radiometric_status(
                        capable=is_radiometric,
                        enabled=self.args.radiometric,
                        mode=mode_desc
                    )

                    # Update panel availability (isotherm, environmental)
                    if hasattr(self.gui, 'update_radiometric_panel_availability'):
                        self.gui.update_radiometric_panel_availability(self.args.radiometric)

                    # Enable hardware spotmeter checkbox if SDK is connected
                    if sdk_connected and hasattr(self.gui.radiometric_panel, 'hw_spotmeter_checkbox'):
                        self.gui.radiometric_panel.hw_spotmeter_checkbox.setEnabled(True)
                    
                    # Enable 8-bit estimation controls (always enable if GUI present, regardless of SDK)
                    if hasattr(self.gui.radiometric_panel, 'set_8bit_estimation_available'):
                        self.gui.radiometric_panel.set_8bit_estimation_available(
                            available=True,
                            auto_enabled=self.temp_estimation_enabled
                        )
                    
                    # Update status banner
                    if hasattr(self.gui.radiometric_panel, 'update_active_mode_status'):
                        mode_info = self.get_active_temperature_mode()
                        self.gui.radiometric_panel.update_active_mode_status(
                            mode_info['mode'],
                            mode_info['accuracy'],
                            mode_info['description']
                        )
                    
                    # Update backend status (Fix Bug #17)
                    if hasattr(self.gui.radiometric_panel, 'update_backend_status'):
                        backend_type = getattr(self.args, 'thermal_backend', 'opencv')
                        
                        backend_info = {
                            'backend': backend_type,
                            'bit_depth': '16' if is_radiometric else '8',
                            'radiometric': is_radiometric,
                            'resolution': actual_res,
                            'current_mode': backend_type
                        }
                        self.gui.radiometric_panel.update_backend_status(backend_info)
                        logger.info(f"✓ Initial backend status updated: {backend_type} (Radiometric: {is_radiometric})")
                    
                    logger.info(f"[OK] Radiometric panel initialized (capable={is_radiometric}, sdk={sdk_connected}, 8bit={self.temp_estimation_enabled})")
                
                # Update ThermalAnalyzer radiometric state
                if self.thermal_analyzer:
                    self.thermal_analyzer.set_radiometric_mode(is_radiometric)
                    logger.info(f"Updated ThermalAnalyzer radiometric state to: {is_radiometric}")
                
                # Initialize ROI radiometric analyzer
                self._init_roi_radiometric_analyzer()

                return True
            else:
                logger.debug("Thermal camera not found")
                self.thermal_camera = None
                self.is_flir_boson = False
                return False

        except Exception as e:
            logger.debug(f"Thermal camera connection failed: {e}")
            self.thermal_camera = None
            self.is_flir_boson = False
            return False

    def _init_roi_radiometric_analyzer(self):
        """Initialize the ROI radiometric analyzer if possible."""
        if (self.thermal_camera and 
            hasattr(self.thermal_camera, 'radiometric_converter') and 
            self.thermal_camera.radiometric_converter and 
            not self.roi_radiometric_analyzer):
            try:
                self.roi_radiometric_analyzer = ROIRadiometricAnalyzer(
                    self.thermal_camera.radiometric_converter
                )
                logger.info("[OK] ROI radiometric analyzer initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize ROI radiometric analyzer: {e}")

    def _detect_radiometric_mode(self) -> bool:
        """
        Detect if camera is providing radiometric data (T-Linear).
        Heuristic: T-Linear values are typically > 20000 (Kelvin * 100).
        Raw values are typically < 16384 (14-bit).
        """
        if not self.thermal_camera:
            return False
            
        logger.info("Detecting camera mode...")
        
        # Use appropriate read method depending on backend
        if hasattr(self.thermal_camera, 'read_thermal'):
            # FLIRBosonCamera - use read_thermal()
            # Grab a few frames to settle
            for _ in range(5):
                self.thermal_camera.read_thermal()
                
            success, frame = self.thermal_camera.read_thermal()
        else:
            # FlirpyThermalBackend - use read()
            # Grab a few frames to settle
            for _ in range(5):
                self.thermal_camera.read()
                
            success, frame = self.thermal_camera.read()
            
        if not success or frame is None:
            logger.warning("Could not grab frame for mode detection")
            return False
            
        # Check median value
        median_val = np.median(frame)
        logger.info(f"Median pixel value: {median_val:.1f}")

        # T-Linear check: values are Kelvin × 100
        # 8-bit AGC: 0-255
        # 14-bit raw: 0-16383
        # T-Linear: 15000 (150K/-123°C) to 65000 (650K/377°C)
        # Typical room temp scene: ~29000-30000 (17-27°C)
        # Cold reference areas: ~19000-22000 (-80°C to -50°C)
        #
        # Key insight: 8-bit values max at 255, so anything > 256 must be 16-bit
        # Values > 10000 are almost certainly T-Linear Y16 radiometric data
        if median_val > 10000:
            logger.info(f"[DETECTED] Radiometric Mode (T-Linear) - median {median_val:.0f} > 10000")
            return True
        else:
            logger.info(f"[DETECTED] Non-Radiometric Mode (Raw/AGC) - median {median_val:.0f} <= 10000")
            return False

    def _try_connect_rgb(self) -> bool:
        """
        Try to connect to RGB camera.

        Returns:
            True if successful, False otherwise
        """
        if self.args.disable_rgb:
            return False

        try:
            if self.rgb_camera:
                self.rgb_camera.release()

            logger.info("Scanning for RGB camera...")

            thermal_id = None
            if self.thermal_connected and self.thermal_camera:
                thermal_id = self.thermal_camera.device_id

            # CRITICAL FIX: Use args.rgb_device, NOT camera_index=0
            # The auto-detection should have set this correctly
            rgb_device_id = getattr(self.args, 'rgb_device', 0)  # Fallback to device 0
            
            logger.info(f"Attempting to open RGB camera on device {rgb_device_id}")

            self.rgb_camera = create_rgb_camera(
                resolution=(640, 480),
                fps=30,
                camera_type="auto",
                camera_index=rgb_device_id,  # Use the detected/assigned ID
                thermal_device_id=thermal_id
            )

            if self.rgb_camera.open():
                rgb_res = self.rgb_camera.get_actual_resolution()
                logger.info(f"[OK] RGB camera connected: {rgb_res[0]}x{rgb_res[1]}")
                self.rgb_available = True
                return True
            else:
                self.rgb_camera = None
                return False

        except Exception as e:
            logger.debug(f"RGB camera connection failed: {e}")
            self.rgb_camera = None
            return False

    def _setup_gui(self):
        """Initialize the Qt GUI."""
        if self.args.headless:
            self.gui_type = 'headless'
            return

        # Check explicit OpenCV request or fallback from main
        if self.args.use_opencv_gui:
            self.gui_type = 'opencv'
            return

        try:
            # Import here to avoid circular dependencies
            from inspection_gui_qt import InspectionAppWindow
            
            # Create window
            self.gui = InspectionAppWindow(self)
            self.gui_type = 'qt'
            logger.info("Qt GUI initialized successfully")
            
        except ImportError as e:
            logger.warning(f"Failed to import Qt GUI: {e}")
            logger.warning("Falling back to OpenCV GUI")
            self.gui_type = 'opencv'
        except Exception as e:
            logger.error(f"Failed to initialize Qt GUI: {e}", exc_info=True)
            self.gui_type = 'opencv'

    def initialize(self) -> bool:
        """
        Initialize all inspection components.

        Returns:
            True if successful, False otherwise
        """
        logger.info("=" * 80)
        logger.info("Initializing Thermal Inspection Fusion Tool")
        logger.info("=" * 80)
        logger.info(f"Platform: {'Jetson' if self.platform_info['is_jetson'] else 'x86-64'} "
                   f"({self.platform_info['machine']})")
        logger.info(f"Mode: {self.inspection_mode}")
        logger.info(f"Device: {self.device}")

        # 0. Initialize GUI (Restored)
        self._setup_gui()

        try:
            # 1. Connect cameras using robust auto-detection
            # Uses enhanced detection with timeout protection
            use_robust_init = getattr(self.args, 'use_robust_camera_init', True)

            if use_robust_init:
                # NEW: Robust initialization with auto-detection
                thermal_connected, rgb_connected = self._init_cameras_robust()
            else:
                # LEGACY: Manual device ID initialization
                thermal_connected = self._try_connect_thermal()

                if not thermal_connected:
                    logger.warning("=" * 60)
                    logger.warning("NO THERMAL CAMERA DETECTED")
                    logger.warning("System will wait for thermal camera connection...")
                    logger.warning("=" * 60)

                # 3. Connect RGB camera (optional)
                if not self.args.disable_rgb:
                    self._try_connect_rgb()

            # 2. Determine resolution
            if self.thermal_connected and self.thermal_camera:
                actual_res = self.thermal_camera.get_actual_resolution()
            else:
                actual_res = (self.args.width, self.args.height)
                logger.info(f"Using default resolution: {actual_res[0]}x{actual_res[1]}")

            # 3. Initialize Radiometric GUI (Fix Bug #17)
            # Must run after camera connection, regardless of init method (Robust/Legacy)
            if self.thermal_connected and self.thermal_camera:
                # Detect radiometric mode (if not already done)
                is_radiometric = self._detect_radiometric_mode()
                if is_radiometric:
                    self.args.radiometric = True
                
                if self.gui and hasattr(self.gui, 'radiometric_panel'):
                    sdk_connected = getattr(self.thermal_camera, 'is_sdk_connected', False)
                    mode_desc = "16-bit Radiometric" if is_radiometric else "8-bit AGC"

                    # Basic status
                    self.gui.radiometric_panel.set_radiometric_status(
                        capable=is_radiometric,
                        enabled=self.args.radiometric,
                        mode=mode_desc
                    )

                    # Update panel availability (isotherm, environmental)
                    if hasattr(self.gui, 'update_radiometric_panel_availability'):
                        self.gui.update_radiometric_panel_availability(self.args.radiometric)

                    # Hardware spotmeter
                    if sdk_connected and hasattr(self.gui.radiometric_panel, 'hw_spotmeter_checkbox'):
                        self.gui.radiometric_panel.hw_spotmeter_checkbox.setEnabled(True)
                    
                    # 8-bit estimation controls
                    if hasattr(self.gui.radiometric_panel, 'set_8bit_estimation_available'):
                        self.gui.radiometric_panel.set_8bit_estimation_available(
                            available=True,
                            auto_enabled=self.temp_estimation_enabled
                        )
                    
                    # Active mode status banner
                    if hasattr(self.gui.radiometric_panel, 'update_active_mode_status'):
                        mode_info = self.get_active_temperature_mode()
                        self.gui.radiometric_panel.update_active_mode_status(
                            mode_info['mode'],
                            mode_info['accuracy'],
                            mode_info['description']
                        )
                    
                    # Backend status (Critical Fix)
                    if hasattr(self.gui.radiometric_panel, 'update_backend_status'):
                        backend_type = getattr(self.args, 'thermal_backend', 'opencv')
                        backend_info = {
                            'backend': backend_type,
                            'bit_depth': '16' if is_radiometric else '8',
                            'radiometric': is_radiometric,
                            'resolution': actual_res,
                            'current_mode': backend_type
                        }
                        self.gui.radiometric_panel.update_backend_status(backend_info)
                        logger.info(f"✓ Initial backend status updated: {backend_type} (Radiometric: {is_radiometric})")

            # 4. Initialize fusion processor (PARAMOUNT!)
            if self.rgb_available:
                calibration_file = getattr(self.args, 'calibration_file', None)
                self.fusion_processor = FusionProcessor(
                    fusion_mode=self.fusion_mode,
                    alpha=self.fusion_alpha,
                    calibration_file=calibration_file
                )
                logger.info(f"[OK] Fusion processor initialized (mode: {self.fusion_mode})")

                # 4b. Initialize parallax compensator (OPTIONAL, disabled by default)
                self.parallax_compensator = None
                if PARALLAX_AVAILABLE:
                    geometry = CameraGeometry(
                        baseline_mm=50.0,  # Default 5cm
                        thermal_resolution=(640, 512),
                        rgb_resolution=(1920, 1200)
                    )
                    self.parallax_compensator = ParallaxCompensator(
                        camera_geometry=geometry,
                        depth_method="simplified"
                    )
                    self.parallax_compensator.enable(False)  # DISABLED BY DEFAULT
                    logger.info("[OK] Parallax compensator initialized (DISABLED by default)")
                else:
                    logger.info("[ ] Parallax compensation not available")

                # 4c. Initialize measurement points manager
                self.measurement_points = None
                if MEASUREMENT_POINTS_AVAILABLE:
                    self.measurement_points = MeasurementPointManager()
                    logger.info("[OK] Measurement points manager initialized")
                else:
                    logger.info("[ ] Measurement points not available")

                # 4d. Initialize radiometric calibrator
                self.radiometric_calibrator = None
                self.calibration_enabled = False
                self.calibration_add_point_mode = False
                self.calibration_reference_temp = 25.0
                if RADIOMETRIC_CALIBRATION_AVAILABLE:
                    self.radiometric_calibrator = RadiometricCalibrator()
                    logger.info("[OK] Radiometric calibrator initialized")
                else:
                    logger.info("[ ] Radiometric calibration not available")

                logger.info("     7 fusion algorithms available!")
                self.view_mode = ViewMode.FUSION
            else:
                logger.info("Fusion processor deferred (no RGB camera)")
                self.view_mode = ViewMode.THERMAL_ONLY

            # 5. Initialize NEW inspection modules
            logger.info("-" * 60)
            logger.info("Initializing inspection modules...")

            # Thermal processor (replaces VPIDetector)
            processor_config = {
                'device': self.device,
                'thermal_palette': getattr(self.args, 'palette', 'ironbow'),
                'motion_detection_enabled': True,
                'edge_detection_enabled': True,
                'min_edge_cluster_area': 50  # Lowered from 500 for better edge detection
            }
            self.thermal_processor = ThermalProcessor(processor_config)
            if not self.thermal_processor.initialize():
                logger.error("Failed to initialize thermal processor")
                return False
            logger.info("[OK] Thermal processor initialized")

            # Thermal analyzer
            analyzer_config = {
                'temperature_unit': 'C',
                'hot_spot_threshold': 0.85,
                'cold_spot_threshold': 0.15,
                'anomaly_sensitivity': 0.7,
                'radiometric': getattr(self.args, 'radiometric', False)
            }
            self.thermal_analyzer = ThermalAnalyzer(analyzer_config)
            logger.info("[OK] Thermal analyzer initialized")

            # ROI manager
            roi_config = {
                'auto_temp_threshold_hot': 0.85,
                'auto_temp_threshold_cold': 0.15,
                'auto_roi_min_area': 500,
                'auto_roi_max_count': 20
            }
            self.roi_manager = ROIManager(roi_config)
            logger.info("[OK] ROI manager initialized")
            
            # ROI Radiometric Analyzer (NEW - Phase 11)
            # Only initialize if thermal analyzer is available for radiometric conversion
            self.roi_radiometric_analyzer = None
            if self.thermal_analyzer:
                # Note: thermal_analyzer has radiometric converter internally
                # We'll initialize roi_radiometric_analyzer later when converter is available
                logger.info("[ ] ROI radiometric analyzer will be initialized with thermal camera")
            else:
                logger.info("[ ] ROI radiometric analyzer deferred (no thermal analyzer)")

            # Palette manager
            palette_config = {
                'default_palette': getattr(self.args, 'palette', 'ironbow'),
                'auto_contrast': True
            }
            self.palette_manager = PaletteManager(palette_config)
            logger.info("[OK] Palette manager initialized")
            logger.info(f"     {len(self.palette_manager.get_available_palettes())} palettes available")

            # Media recorder and snapshot manager (NEW - Phase 6)
            recording_config = {
                'output_path': 'recordings/',
                'filename_pattern': 'inspection_%Y%m%d_%H%M%S',
                'video_codec': 'mp4v',
                'fps': 30,
                'save_thermal': False,
                'save_rgb': False,
                'save_fusion': True,
                'save_roi_metadata': True
            }
            self.video_recorder = VideoRecorder(recording_config)
            logger.info("[OK] Video recorder initialized")

            snapshot_config = {
                'output_path': 'snapshots/',
                'filename_pattern': 'snapshot_%Y%m%d_%H%M%S',
                'format': 'png',
                'quality': 95,
                'save_metadata': True
            }
            self.snapshot_manager = SnapshotManager(snapshot_config)
            logger.info("[OK] Snapshot manager initialized")

            # Initialize video player if in playback mode
            if self.inspection_mode == 'playback':
                playback_file = getattr(self.args, 'playback_file', None)
                if playback_file:
                    self.video_player = VideoPlayer(playback_file)
                    logger.info(f"[OK] Video player initialized: {playback_file}")
                else:
                    logger.error("Playback mode requires --playback-file argument")
                    return False

            logger.info("-" * 60)

            # 5.5 Initialize threaded camera capture (if enabled)
            if self.use_threaded_capture and (self.thermal_connected or self.rgb_available):
                from threaded_camera_capture import DualThreadedCameraCapture
                self.threaded_capture = DualThreadedCameraCapture(
                    self.thermal_camera if self.thermal_connected else None,
                    self.rgb_camera if self.rgb_available else None
                )
                logger.info("[OK] Threaded camera capture initialized")

            # 6. Initialize performance monitor
            self.perf_monitor = PerformanceMonitor()

            # 7. Initialize GUI
            use_opencv = getattr(self.args, 'use_opencv_gui', False)
            use_qt = not use_opencv and self.qt_app is not None

            if use_qt:
                try:
                    from inspection_gui_qt import InspectionAppWindow
                    logger.info("Qt GUI selected")
                    self.gui_type = 'qt'
                    self.gui = InspectionAppWindow(self)
                    logger.info("Qt GUI created successfully")

                    # Connect all GUI signals
                    self._connect_signals()

                    # Update camera panel statuses
                    self.update_firefly_gui()
                    self.update_boson_gui()
                    self.update_radiometric_gui()
                except ImportError as e:
                    logger.error(f"Failed to import Qt GUI: {e}")
                    self.gui_type = 'opencv'
                    self.gui = None
                except Exception as e:
                    logger.error(f"Failed to create Qt GUI: {e}", exc_info=True)
                    self.gui_type = 'opencv'
                    self.gui = None
            elif use_opencv:
                # TODO: Create simple OpenCV GUI for inspection
                logger.info("OpenCV GUI selected (simple inspection view)")
                self.gui_type = 'opencv'
                self.gui = None
            else:
                logger.info("Headless mode (no GUI)")
                self.gui_type = None

            logger.info("=" * 80)
            logger.info("Initialization complete!")
            logger.info("=" * 80)

            return True

        except Exception as e:
            logger.error(f"Initialization failed: {e}", exc_info=True)
            return False

    def _connect_signals(self):
        """Connect all GUI signals to their handlers."""
        if not self.gui:
            return

        try:
            # 1. Control Panel (Bottom)
            if hasattr(self.gui, 'control_panel'):
                cp = self.gui.control_panel
                # Media controls
                if hasattr(cp, 'record_toggled'): cp.record_toggled.connect(self.toggle_recording)
                if hasattr(cp, 'snapshot_clicked'): cp.snapshot_clicked.connect(self.capture_snapshot)
                if hasattr(cp, 'freeze_frame_toggled'): cp.freeze_frame_toggled.connect(self.toggle_freeze)
                
                # View controls
                if hasattr(cp, 'view_mode_clicked'): cp.view_mode_clicked.connect(self.cycle_view_mode)
                # if hasattr(cp, 'day_night_clicked'): cp.day_night_clicked.connect(self.toggle_theme) # REMOVED: Handled by GUI internally
                
                # ROI controls
                if hasattr(cp, 'auto_roi_clicked'): cp.auto_roi_clicked.connect(self.auto_roi_detect)
                if hasattr(cp, 'draw_roi_clicked'): cp.draw_roi_clicked.connect(self.draw_roi)
                if hasattr(cp, 'clear_rois_clicked'): cp.clear_rois_clicked.connect(self.clear_rois)

            # 2. Thermal Analysis Panel (General)
            if hasattr(self.gui, 'analysis_panel'):
                ap = self.gui.analysis_panel
                if hasattr(ap, 'palette_changed'): ap.palette_changed.connect(self.set_palette)
                if hasattr(ap, 'baseline_toggled'): ap.baseline_toggled.connect(self.lock_baseline)
                # Note: overlay_info_toggled is handled by GUI internally or needs handler?
                # Let's add handler if we want to toggle overlay rendering in main loop
                if hasattr(ap, 'overlay_info_toggled'): ap.overlay_info_toggled.connect(self.toggle_overlay_info)
                # CONNECTED: ROI palette change signal
                if hasattr(ap, 'roi_palette_changed'): ap.roi_palette_changed.connect(self.set_roi_palette)

            # 3. Radiometric Panel
            if hasattr(self.gui, 'radiometric_panel'):
                rp = self.gui.radiometric_panel
                # TODO: Add handlers for radiometric panel signals
                # if hasattr(rp, 'spotmeter_mode_changed'): rp.spotmeter_mode_changed.connect(self._on_spotmeter_mode_changed)
                pass

            # 4. Firefly Control Panel
            if hasattr(self.gui, 'firefly_panel'):
                fp = self.gui.firefly_panel
                if hasattr(fp, 'exposure_mode_changed'): fp.exposure_mode_changed.connect(self.set_firefly_exposure_mode)
                if hasattr(fp, 'exposure_time_changed'): fp.exposure_time_changed.connect(self.set_firefly_exposure_time)
                if hasattr(fp, 'gain_mode_changed'): fp.gain_mode_changed.connect(self.set_firefly_gain_mode)
                if hasattr(fp, 'gain_changed'): fp.gain_changed.connect(self.set_firefly_gain)
                if hasattr(fp, 'wb_mode_changed'): fp.wb_mode_changed.connect(self.set_firefly_wb_mode)
                
                # Use lambdas for specific channel/parameter mapping
                if hasattr(fp, 'wb_red_changed'): fp.wb_red_changed.connect(lambda v: self.set_firefly_wb_ratio('Red', v))
                if hasattr(fp, 'wb_blue_changed'): fp.wb_blue_changed.connect(lambda v: self.set_firefly_wb_ratio('Blue', v))
                
                if hasattr(fp, 'trigger_mode_changed'): fp.trigger_mode_changed.connect(self.set_firefly_trigger_mode)
                if hasattr(fp, 'software_trigger_clicked'): fp.software_trigger_clicked.connect(self.fire_software_trigger)
                
                if hasattr(fp, 'gamma_changed'): fp.gamma_changed.connect(self.set_firefly_gamma)
                if hasattr(fp, 'sharpness_enabled_changed'): fp.sharpness_enabled_changed.connect(lambda e: self.set_firefly_sharpness(e))
                if hasattr(fp, 'sharpness_changed'): fp.sharpness_changed.connect(lambda v: self.set_firefly_sharpness(True, v))

            # 5. Boson Control Panel
            if hasattr(self.gui, 'boson_panel'):
                bp = self.gui.boson_panel
                if hasattr(bp, 'connect_clicked'): bp.connect_clicked.connect(self.connect_boson_sdk)
                if hasattr(bp, 'ffc_clicked'): bp.ffc_clicked.connect(self.trigger_ffc)
                if hasattr(bp, 'gain_mode_changed'): bp.gain_mode_changed.connect(self.set_boson_gain_mode)
                if hasattr(bp, 'ffc_mode_changed'): bp.ffc_mode_changed.connect(self.set_boson_ffc_mode)

            # 6. Radiometric Panel
            if hasattr(self.gui, 'radiometric_panel'):
                rp = self.gui.radiometric_panel
                # Hardware spotmeter signals
                if hasattr(rp, 'spotmeter_enabled_changed'): rp.spotmeter_enabled_changed.connect(self._on_spotmeter_enabled)
                if hasattr(rp, 'spotmeter_mode_changed'): rp.spotmeter_mode_changed.connect(self._on_spotmeter_mode_changed)
                # Sensor temperature refresh signal
                if hasattr(rp, 'sensor_temps_requested'): rp.sensor_temps_requested.connect(self._update_sensor_temperatures)

            logger.info("[OK] GUI signals connected")

        except Exception as e:
            logger.error(f"Failed to connect GUI signals: {e}", exc_info=True)

    def toggle_theme(self):
        """Toggle between light and dark theme."""
        if self.gui:
            current = self.gui.current_theme
            new_theme = "light" if current == "dark" else "dark"
            self.gui._apply_theme(new_theme)
            logger.info(f"Theme switched to {new_theme}")

    def toggle_overlay_info(self, enabled: bool):
        """Toggle overlay information display."""
        self.show_overlay_info = enabled
        logger.info(f"Overlay info: {'ON' if enabled else 'OFF'}")

    def set_palette(self, palette_name: str):
        """Set global palette."""
        try:
            from palette_manager import PaletteType
            # Clean up name if it comes from combo box styling
            clean_name = palette_name.strip().lstrip("─ ")
            if clean_name and not clean_name.startswith("───"):
                pt = PaletteType(clean_name)
                self.palette_manager.set_global_palette(pt)
                logger.info(f"Global palette changed to: {clean_name}")
        except Exception as e:
            logger.error(f"Failed to set palette {palette_name}: {e}")

    def set_roi_palette(self, roi_id: str, palette_name: str):
        """
        Set palette for a specific ROI.
        Connected to ThermalAnalysisPanel.roi_palette_changed signal.
        """
        try:
            logger.info(f"Applying palette '{palette_name}' to ROI {roi_id}")
            
            # 1. Update ROI in ROI Manager (Primary method for apply_composite_palette)
            roi = self.roi_manager.get_roi(roi_id)
            if roi:
                roi.custom_palette = palette_name
                logger.debug(f"ROI {roi_id} custom_palette updated to {palette_name}")
            else:
                logger.warning(f"ROI {roi_id} not found in manager!")
                
            # 2. Update PaletteManager config (Legacy/Backup)
            from palette_manager import PaletteType
            pt = PaletteType(palette_name)
            self.palette_manager.set_roi_palette(roi_id, pt)
            
        except Exception as e:
            logger.error(f"Failed to set ROI palette: {e}")

    def _apply_isotherm_overlay(self, thermal_frame: np.ndarray, colorized_frame: np.ndarray) -> np.ndarray:
        """Apply isotherm temperature highlighting overlay.
        
        Args:
            thermal_frame: Grayscale thermal frame (raw values or temperature)
            colorized_frame: Colorized thermal frame to overlay on
            
        Returns:
            Frame with isotherm regions highlighted
        """
        try:
            mode = getattr(self, 'isotherm_mode', 'above')
            low = getattr(self, 'isotherm_low_threshold', 10)
            high = getattr(self, 'isotherm_high_threshold', 50)
            color = getattr(self, 'isotherm_color_bgr', (0, 0, 255))  # Default red
            
            # Prepare frame for thresholding (convert to Celsius if 16-bit)
            proc_frame = thermal_frame
            if thermal_frame.dtype == np.uint16:
                # Convert Kelvin (centi-Kelvin) to Celsius
                # Standard T-Linear: (K*100 - 27315) / 100
                proc_frame = (thermal_frame.astype(float) - 27315.0) / 100.0
            
            # Create mask based on mode
            if mode == 'above':
                mask = proc_frame > high
            elif mode == 'below':
                mask = proc_frame < low
            elif mode == 'between':
                mask = (proc_frame >= low) & (proc_frame <= high)
            elif mode == 'outside':
                mask = (proc_frame < low) | (proc_frame > high)
            else:
                mask = proc_frame > high

            # Debug logging for isotherm
            if hasattr(self, '_isotherm_debug_counter'):
                self._isotherm_debug_counter += 1
            else:
                self._isotherm_debug_counter = 0

            if self._isotherm_debug_counter % 30 == 0:  # Log every 30 frames
                min_temp = proc_frame.min()
                max_temp = proc_frame.max()
                mean_temp = proc_frame.mean()
                matched_pixels = mask.sum()
                logger.debug(f"Isotherm: mode={mode}, low={low:.1f}, high={high:.1f}, "
                           f"temp_range=[{min_temp:.1f}, {max_temp:.1f}], mean={mean_temp:.1f}, "
                           f"matched={matched_pixels} pixels")

            # Apply color overlay where mask is True
            result = colorized_frame.copy()
            if mask.any():
                # Create colored overlay
                overlay = np.zeros_like(colorized_frame)
                overlay[mask] = color
                
                # Blend with original (50% opacity)
                alpha = 0.5
                result = cv2.addWeighted(colorized_frame, 1 - alpha, overlay, alpha, 0)
                # Restore non-masked areas
                result[~mask] = colorized_frame[~mask]
            
            return result
            
        except Exception as e:
            logger.debug(f"Isotherm overlay error: {e}")
            return colorized_frame


    def process_frame(self, thermal_frame: np.ndarray, rgb_frame: Optional[np.ndarray] = None) -> Dict:
        """
        Process thermal and RGB frames through inspection pipeline.

        Args:
            thermal_frame: Thermal image (grayscale, 8-bit or 16-bit)
            rgb_frame: Optional RGB image (BGR format)

        Returns:
            Dictionary with all processing results
        """
        t_prof = {}  # Timing profile for this function
        t_prof['start'] = time.time()

        result = {
            'thermal_colorized': None,
            'rgb_frame': rgb_frame,
            'fused_frame': None,
            'display_frame': None,
            'motion_detections': [],
            'edge_clusters': [],
            'hot_spots': [],
            'cold_spots': [],
            'anomalies': [],
            'rois': [],
            'thermal_stats': None,
            'timing_profile': t_prof  # Include timing in result
        }

        if thermal_frame is None:
            return result

        try:
            # 1. Process thermal frame (motion + edge detection)
            t_prof['before_thermal_processor'] = time.time()
            processor_result = self.thermal_processor.process_frame(thermal_frame)
            t_prof['after_thermal_processor'] = time.time()
            result['motion_detections'] = processor_result['motion_detections']
            result['edge_clusters'] = processor_result['edge_clusters']

            # 2. Apply palette (global + ROI overrides)
            t_prof['before_palette'] = time.time()
            thermal_colorized = self.palette_manager.apply_composite_palette(
                thermal_frame, self.roi_manager
            )
            t_prof['after_palette'] = time.time()

            # 2b. Apply temperature overlay if radiometric is enabled
            if self.thermal_camera and self.thermal_camera.is_radiometric_enabled():
                if self.gui and hasattr(self.gui, 'radiometric_panel'):
                    if self.gui.radiometric_panel.is_temp_overlay_enabled():
                        # Get temperature frame from radiometric converter
                        temp_frame = self._get_temperature_frame()
                        if temp_frame is not None:
                            colormap = self.gui.radiometric_panel.get_colormap()
                            opacity = self.gui.radiometric_panel.get_overlay_opacity()
                            thermal_colorized = self.thermal_processor.apply_temperature_overlay(
                                thermal_colorized, temp_frame, colormap, opacity
                            )

            result['thermal_colorized'] = thermal_colorized

            # 2c. Apply Isotherm Highlighting (if enabled)
            if getattr(self, 'isotherm_enabled', False):
                thermal_colorized = self._apply_isotherm_overlay(thermal_frame, thermal_colorized)
                result['thermal_colorized'] = thermal_colorized

            # 2c. Update 8-bit temperature estimation (if enabled)
            t_prof['before_temp_estimation'] = time.time()
            if self.temp_estimation_enabled and self.temp_estimator:
                # Convert to 8-bit grayscale if needed
                if thermal_colorized.ndim == 3:
                    thermal_gray = cv2.cvtColor(thermal_colorized, cv2.COLOR_BGR2GRAY)
                else:
                    thermal_gray = thermal_frame if thermal_frame.dtype == np.uint8 else (thermal_frame / 256).astype(np.uint8)
                
                self._update_temperature_estimation(thermal_gray)
            t_prof['after_temp_estimation'] = time.time()

            # 3. Automatic ROI detection (if enabled)
            # OPTIMIZATION: Only run auto-ROI detection every N frames to reduce overhead
            t_prof['before_auto_roi'] = time.time()
            if self.auto_roi_enabled:
                self.auto_roi_frame_counter += 1
                if self.auto_roi_frame_counter >= self.auto_roi_update_interval:
                    self.auto_roi_frame_counter = 0

                    # Clear previous auto-detected ROIs
                    self.roi_manager.delete_rois_by_source(ROISource.AUTO_TEMPERATURE)
                    self.roi_manager.delete_rois_by_source(ROISource.AUTO_GRADIENT)
                    self.roi_manager.delete_rois_by_source(ROISource.AUTO_MOTION)
                    self.roi_manager.delete_rois_by_source(ROISource.AUTO_EDGE)

                    # Detect new ROIs
                    if self.auto_roi_methods.get('temperature', True):
                        temp_rois = self.roi_manager.detect_temperature_rois(thermal_frame)

                    if self.auto_roi_methods.get('gradient', True):
                        grad_rois = self.roi_manager.detect_gradient_rois(thermal_frame)

                    if self.auto_roi_methods.get('motion', True) and result['motion_detections']:
                        motion_dicts = [
                            {'bbox': (d.bbox[0], d.bbox[1], d.bbox[2]-d.bbox[0], d.bbox[3]-d.bbox[1])}
                            for d in result['motion_detections']
                        ]
                        motion_rois = self.roi_manager.detect_motion_rois(motion_dicts)

                    if self.auto_roi_methods.get('edge', True):
                        edge_rois = self.roi_manager.detect_edge_rois(thermal_frame)

                    # NMS Cleanup (Refinement)
                    # Remove overlapping ROIs based on priority (Manual > Temp > Gradient > Motion > Edge)
                    self.roi_manager.cleanup_overlapping_rois()
            t_prof['after_auto_roi'] = time.time()

            # 4. Thermal analysis for each ROI
            t_prof['before_roi_analysis'] = time.time()
            
            # Calculate global statistics first (for GUI display)
            if self.thermal_analyzer:
                # Use temperature map if 8-bit estimation is active
                analysis_frame = thermal_frame
                if self.temp_estimation_enabled and self.temp_estimator:
                    if self.thermal_camera and self.thermal_camera.is_sdk_connected:
                        fpa_temp_result = self.thermal_camera.get_fpa_temperature()
                        if fpa_temp_result:
                            fpa_temp_c = fpa_temp_result[1]
                            # Convert AGC frame to temperature map
                            analysis_frame = self.temp_estimator.estimate_temperature_map(
                                thermal_frame, fpa_temp_c
                            )
                            # Hot/cold spots will now show temperatures in °C

                result['thermal_stats'] = self.thermal_analyzer.analyze_frame(analysis_frame)

            rois = self.roi_manager.get_all_rois(active_only=True)
            result['rois'] = rois

            # OPTIMIZATION: Parallel ROI analysis (Phase 1)
            if self.enable_parallel_processing and self.roi_executor and len(rois) > 0:
                def analyze_single_roi(roi):
                    """Analyze a single ROI (thread-safe)."""
                    mask = roi.get_mask(thermal_frame.shape)
                    stats = self.thermal_analyzer.analyze_frame(thermal_frame, mask)
                    return roi, stats

                # Process all ROIs in parallel
                roi_futures = {self.roi_executor.submit(analyze_single_roi, roi): roi for roi in rois}

                for future in as_completed(roi_futures):
                    roi, stats = future.result()
                    # Store stats in ROI metadata
                    if stats:
                        roi.metadata['thermal_stats'] = {
                            'min_temp': stats.min_temp,
                            'max_temp': stats.max_temp,
                            'mean_temp': stats.mean_temp,
                            'std_temp': stats.std_temp
                        }
                        # Update trend tracking
                        self.thermal_analyzer.update_trend(roi.roi_id, stats.mean_temp)

            else:
                # FALLBACK: Sequential ROI analysis
                for roi in rois:
                    mask = roi.get_mask(thermal_frame.shape)
                    stats = self.thermal_analyzer.analyze_frame(thermal_frame, mask)

                    # Store stats in ROI metadata
                    if stats:
                        roi.metadata['thermal_stats'] = {
                            'min_temp': stats.min_temp,
                            'max_temp': stats.max_temp,
                            'mean_temp': stats.mean_temp,
                            'std_temp': stats.std_temp
                        }


            t_prof['after_roi_analysis'] = time.time() # Corrected missing timestamp
            t_prof['before_thermal_analysis'] = time.time()

            # 5. Global thermal analysis (Parallel vs Sequential)
            if self.enable_parallel_processing and self.detection_executor:
                future_stats = self.detection_executor.submit(
                    self.thermal_analyzer.analyze_frame, thermal_frame
                )
                future_hot = self.detection_executor.submit(
                    self.thermal_analyzer.detect_hot_spots, thermal_frame
                )
                future_cold = self.detection_executor.submit(
                    self.thermal_analyzer.detect_cold_spots, thermal_frame
                )
                future_anomaly = self.detection_executor.submit(
                    self.thermal_analyzer.detect_anomalies, thermal_frame, 'global'
                )

                future_threshold = None
                if self.manual_threshold_enabled:
                    future_threshold = self.detection_executor.submit(
                        self.thermal_analyzer.detect_threshold_anomalies,
                        thermal_frame,
                        threshold_mode=self.manual_threshold_mode,
                        min_threshold=self.manual_threshold_min,
                        max_threshold=self.manual_threshold_max,
                        use_raw_values=self.manual_threshold_use_raw
                    )

                # Collect results (blocks until all complete)
                result['thermal_stats'] = future_stats.result()
                result['hot_spots'] = future_hot.result()
                result['cold_spots'] = future_cold.result()
                result['anomalies'] = future_anomaly.result()

                if future_threshold:
                    result['manual_threshold_result'] = future_threshold.result()
                    self.latest_threshold_result = result['manual_threshold_result']
                else:
                    result['manual_threshold_result'] = None
                    self.latest_threshold_result = None

            else:
                # FALLBACK: Sequential execution (for debugging or single-threaded mode)
                global_stats = self.thermal_analyzer.analyze_frame(thermal_frame)
                result['thermal_stats'] = global_stats

                result['hot_spots'] = self.thermal_analyzer.detect_hot_spots(thermal_frame)
                result['cold_spots'] = self.thermal_analyzer.detect_cold_spots(thermal_frame)
                result['anomalies'] = self.thermal_analyzer.detect_anomalies(thermal_frame, 'global')

                if self.manual_threshold_enabled:
                    threshold_result = self.thermal_analyzer.detect_threshold_anomalies(
                        thermal_frame,
                        threshold_mode=self.manual_threshold_mode,
                        min_threshold=self.manual_threshold_min,
                        max_threshold=self.manual_threshold_max,
                        use_raw_values=self.manual_threshold_use_raw
                    )
                    result['manual_threshold_result'] = threshold_result
            
            # 5a. Per-ROI Radiometric Temperature Analysis (NEW - Phase 11)
            # Analyze temperature for each ROI if radiometric is enabled
            roi_temp_stats = {}
            
            # DEBUG: Diagnose why ROI analysis might be skipped
            if len(result['rois']) > 0:
                has_analyzer = self.roi_radiometric_analyzer is not None
                has_camera = self.thermal_camera is not None
                is_radiometric = False
                if has_camera:
                    is_radiometric = self.thermal_camera.is_radiometric_enabled()
                
                # Only log if something is missing to avoid spam
                if not (has_analyzer and has_camera and is_radiometric):
                    logger.debug(f"Skipping ROI analysis: Analyzer={has_analyzer}, Camera={has_camera}, Radiometric={is_radiometric}")

            if (self.roi_radiometric_analyzer and 
                self.thermal_camera and 
                self.thermal_camera.is_radiometric_enabled()):
                
                # Get the raw 16-bit frame for radiometric conversion
                raw_frame_16bit = None
                if hasattr(self.thermal_camera, 'get_last_raw_frame'):
                    raw_frame_16bit = self.thermal_camera.get_last_raw_frame()
                    # DEBUG: Check raw frame
                    if len(result['rois']) > 0:
                        logger.debug(f"Raw frame: {type(raw_frame_16bit)}")
                        if hasattr(raw_frame_16bit, 'dtype'):
                            logger.debug(f"Raw frame dtype: {raw_frame_16bit.dtype}, shape: {raw_frame_16bit.shape}")
                
                # If we have 16-bit data, analyze all active ROIs
                if raw_frame_16bit is not None and raw_frame_16bit.dtype == np.uint16:
                    try:
                        # Analyze all ROIs
                        roi_temp_stats = self.roi_radiometric_analyzer.analyze_all_rois(
                            result['rois'],
                            raw_frame_16bit
                        )
                        
                        # Update each ROI with temperature data
                        for roi in result['rois']:
                            stats = roi_temp_stats.get(roi.roi_id)
                            if stats:
                                roi.temp_min = stats.get('temp_min')
                                roi.temp_max = stats.get('temp_max')
                                roi.temp_avg = stats.get('temp_avg')
                                roi.temp_std = stats.get('temp_std')
                        
                        logger.debug(f"ROI Stats Generated: {len(roi_temp_stats)} ROIs")
                    except Exception as e:
                        logger.debug(f"ROI radiometric analysis failed: {e}")
            
            # FALLBACK: If no 16-bit stats, use standard analysis stats
            # This ensures the Per-ROI panel works even in 8-bit mode or if SDK is missing
            if not roi_temp_stats and result['rois']:
                for roi in result['rois']:
                    if 'thermal_stats' in roi.metadata:
                        stats = roi.metadata['thermal_stats']
                        roi_temp_stats[roi.roi_id] = {
                            'roi_name': roi.label or f"ROI-{roi.roi_id}",
                            'temp_min': stats['min_temp'],
                            'temp_max': stats['max_temp'],
                            'temp_avg': stats['mean_temp'],
                            'temp_std': stats['std_temp'],
                            'pixel_count': 0, # Unknown without mask count
                            'emissivity': roi.emissivity,
                            'min_location': (0,0), # Not stored in simple stats
                            'max_location': (0,0)
                        }

            result['roi_temp_stats'] = roi_temp_stats

            # 5b. Apply anomaly priority colorization if enabled (AFTER all detections)
            t_prof['before_anomaly_priority'] = time.time()
            if self.thermal_processor.anomaly_priority_enabled:
                # Combine enabled anomaly types for gradient fade visualization
                all_anomalies = []

                # Add motion detections (if enabled)
                if self.enabled_anomaly_types.get("motion", True):
                    for motion in result['motion_detections']:
                        all_anomalies.append(motion)  # MotionDetection has .bbox attribute

                # Add edge clusters (if enabled)
                if self.enabled_anomaly_types.get("edges", True):
                    for edge in result['edge_clusters']:
                        all_anomalies.append(edge)  # EdgeCluster has .bbox attribute

                # Add hot spots (if enabled)
                if self.enabled_anomaly_types.get("hot_spots", True):
                    for hot_spot in result['hot_spots']:
                        all_anomalies.append(hot_spot)  # ThermalHotspot has .bbox attribute

                # Add cold spots (if enabled)
                if self.enabled_anomaly_types.get("cold_spots", True):
                    for cold_spot in result['cold_spots']:
                        all_anomalies.append(cold_spot)  # ThermalColdspot has .bbox attribute

                # Add statistical thermal anomalies (if enabled)
                if self.enabled_anomaly_types.get("thermal_anomalies", True):
                    for thermal_anomaly in result['anomalies']:
                        all_anomalies.append(thermal_anomaly)  # ThermalAnomaly has .bbox attribute

                # Add enhanced fusion (thermal + edge combined) if enabled
                # This adds both thermal anomalies and edges together when enabled
                if self.enabled_anomaly_types.get("enhanced_fusion", False):
                    # Add edges if not already added
                    if not self.enabled_anomaly_types.get("edges", False):
                        for edge in result['edge_clusters']:
                            all_anomalies.append(edge)
                    # Add thermal anomalies if not already added
                    if not self.enabled_anomaly_types.get("thermal_anomalies", False):
                        for thermal_anomaly in result['anomalies']:
                            all_anomalies.append(thermal_anomaly)

                # Apply gradient fade colorization with ALL anomalies
                # This updates thermal_colorized which is then used in fusion
                thermal_colorized = self.thermal_processor.apply_anomaly_priority_colorization(
                    thermal_frame, all_anomalies, thermal_colorized
                )
                # Update result with anomaly-priority-applied colorization
                result['thermal_colorized'] = thermal_colorized
            t_prof['after_anomaly_priority'] = time.time()
            t_prof['after_thermal_analysis'] = time.time()  # Mark end of thermal analysis section

            # 5c. Apply manual threshold visualization if enabled
            if self.manual_threshold_enabled and self.latest_threshold_result is not None:
                thermal_colorized = self.thermal_analyzer.apply_threshold_visualization(
                    thermal_frame,
                    thermal_colorized,
                    self.latest_threshold_result,
                    viz_mode=self.manual_threshold_viz_mode
                )
                result['thermal_colorized'] = thermal_colorized

            # 5d. Update Spot Meters (Enhancement #1)
            # Update temperatures for all user-defined spot meters
            if self.gui and hasattr(self.gui, 'get_spot_meter_coords'):
                coords = self.gui.get_spot_meter_coords()
                if coords:
                    spot_values = []
                    temp_map_for_spots = None
                    unit = "°C"
                    
                    # Strategy 1: Use 16-bit radiometric data (Best Accuracy)
                    if self.thermal_camera and self.thermal_camera.is_radiometric_enabled():
                         if hasattr(self.thermal_camera, 'get_last_raw_frame'):
                             raw = self.thermal_camera.get_last_raw_frame()
                             if raw is not None and raw.dtype == np.uint16:
                                 # Convert Kelvinx100 to Celsius: (K*100 - 27315) / 100.0
                                 temp_map_for_spots = (raw.astype(float) - 27315.0) / 100.0
                    
                    # Strategy 2: Use 8-bit estimation (Fallback)
                    if temp_map_for_spots is None and self.temp_estimation_enabled and self.temp_estimator:
                         if self.thermal_camera and self.thermal_camera.is_sdk_connected:
                             fpa = self.thermal_camera.get_fpa_temperature()
                             if fpa:
                                 # Re-calculate map for spot metering
                                 temp_map_for_spots = self.temp_estimator.estimate_temperature_map(thermal_frame, fpa[1])
                    
                    # Strategy 3: Use raw 8-bit values (Basic Fallback)
                    # When neither radiometric nor estimation is available, show raw values
                    if temp_map_for_spots is None and thermal_frame is not None:
                        temp_map_for_spots = thermal_frame.astype(float)
                        unit = " (raw)"  # Indicate these are uncalibrated raw values

                    # Extract temperatures
                    if temp_map_for_spots is not None:
                        h, w = temp_map_for_spots.shape
                        for x, y, label in coords:
                            # Check bounds and valid data
                            if 0 <= x < w and 0 <= y < h:
                                val = temp_map_for_spots[y, x]
                                if not np.isnan(val):
                                    spot_values.append({'label': label, 'temperature': float(val), 'unit': unit})
                        
                        # Send updates to GUI
                        self.gui.update_spot_meter_values(spot_values)

            # 6. Create fused frame if RGB available
            t_prof['before_fusion'] = time.time()
            if rgb_frame is not None and self.fusion_processor:
                try:
                    # Apply RGB color mode (convert to grayscale if requested)
                    rgb_for_fusion = rgb_frame
                    if self.rgb_fusion_color_mode == 'grayscale':
                        rgb_gray = cv2.cvtColor(rgb_frame, cv2.COLOR_BGR2GRAY)
                        rgb_for_fusion = cv2.cvtColor(rgb_gray, cv2.COLOR_GRAY2BGR)  # Convert back to 3-channel for fusion

                    fused_frame = self.fusion_processor.fuse_frames(thermal_colorized, rgb_for_fusion)
                    result['fused_frame'] = fused_frame
                except Exception as e:
                    logger.debug(f"Fusion processing error: {e}")
                    result['fused_frame'] = None
            t_prof['after_fusion'] = time.time()

            # 7. Select display frame based on view mode
            t_prof['before_display_select'] = time.time()
            if self.view_mode == ViewMode.THERMAL_ONLY:
                # Show only thermal colorized
                display_frame = thermal_colorized.copy()
            elif self.view_mode == ViewMode.RGB_ONLY:
                # Show only RGB
                if rgb_frame is not None:
                    display_frame = rgb_frame.copy()
                else:
                    # Fallback to thermal if no RGB
                    display_frame = thermal_colorized.copy()
            elif self.view_mode == ViewMode.FUSION:
                # Show fusion overlay
                if result.get('fused_frame') is not None:
                    display_frame = result['fused_frame'].copy()
                else:
                    # Fallback to thermal if no fusion available
                    display_frame = thermal_colorized.copy()
            elif self.view_mode == ViewMode.SIDE_BY_SIDE:
                # Show thermal and RGB side-by-side
                if rgb_frame is not None:
                    # Resize both to same height
                    h = min(thermal_colorized.shape[0], rgb_frame.shape[0])
                    thermal_resized = cv2.resize(thermal_colorized, (int(thermal_colorized.shape[1] * h / thermal_colorized.shape[0]), h))
                    rgb_resized = cv2.resize(rgb_frame, (int(rgb_frame.shape[1] * h / rgb_frame.shape[0]), h))
                    display_frame = np.hstack([thermal_resized, rgb_resized])
                else:
                    display_frame = thermal_colorized.copy()
            elif self.view_mode == ViewMode.PICTURE_IN_PICTURE:
                # Show RGB with thermal PiP in corner
                if rgb_frame is not None:
                    display_frame = rgb_frame.copy()
                    # Create small thermal PiP (20% of width)
                    pip_width = rgb_frame.shape[1] // 5
                    pip_height = int(pip_width * thermal_colorized.shape[0] / thermal_colorized.shape[1])
                    thermal_pip = cv2.resize(thermal_colorized, (pip_width, pip_height))
                    # Place in top-right corner with 10px margin
                    y_offset = 10
                    x_offset = rgb_frame.shape[1] - pip_width - 10
                    display_frame[y_offset:y_offset+pip_height, x_offset:x_offset+pip_width] = thermal_pip
                else:
                    display_frame = thermal_colorized.copy()
            else:
                # Default: fusion
                display_frame = result['fused_frame'].copy()

            t_prof['after_display_select'] = time.time()

            # 8. Draw ROIs on display frame
            t_prof['before_draw_rois'] = time.time()
            display_frame = self.roi_manager.draw_rois(display_frame, active_only=True)
            t_prof['after_draw_rois'] = time.time()

            result['display_frame'] = display_frame
            result['rois'] = self.roi_manager.get_all_rois(active_only=True)

            # Store latest results for GUI
            self.latest_motion_detections = result['motion_detections']
            self.latest_edge_clusters = result['edge_clusters']
            self.latest_hot_spots = result['hot_spots']
            self.latest_cold_spots = result['cold_spots']
            self.latest_anomalies = result['anomalies']
            self.latest_stats = result['thermal_stats']
            self.latest_display_frame = result['display_frame']
            self.latest_rois = result['rois']

            t_prof['end'] = time.time()

        except Exception as e:
            logger.error(f"Frame processing error: {e}", exc_info=True)
            t_prof['end'] = time.time()

        return result

    def _perform_deferred_initialization(self):
        """
        Perform initialization tasks that require the GUI loop to be running.
        This fixes issues where status updates are lost if sent before app.exec().
        """
        if self.gui_type != 'qt' or not self.gui:
            return

        try:
            logger.info("Executing deferred GUI initialization...")

            # 1. Update Backend Status (Fix Bug #17)
            if hasattr(self.gui, 'radiometric_panel') and hasattr(self.gui.radiometric_panel, 'update_backend_status'):
                # Re-detect properties to be sure
                is_radiometric = self._detect_radiometric_mode()
                backend_type = getattr(self.args, 'thermal_backend', 'opencv')
                
                if self.thermal_connected and self.thermal_camera:
                    actual_res = self.thermal_camera.get_actual_resolution()
                    # Ensure we have a valid mode string for the banner
                    if is_radiometric:
                        mode_str = "T-Linear Radiometric (16-bit)"
                    else:
                        mode_str = "UVC Colorized (8-bit)"
                else:
                    actual_res = (self.args.width, self.args.height)
                    mode_str = "Initializing..."

                backend_info = {
                    'backend': backend_type,
                    'bit_depth': '16' if is_radiometric else '8',
                    'radiometric': is_radiometric,
                    'resolution': actual_res,
                    'current_mode': mode_str  # Use human-readable mode string
                }
                self.gui.radiometric_panel.update_backend_status(backend_info)
                logger.info(f"Deferred backend status update: {backend_info}")

            # 2. Update Camera Info & Connection Status
            if hasattr(self.gui, 'boson_panel'):
                # Update Connection Status
                if hasattr(self.gui.boson_panel, 'update_connection_status'):
                    is_sdk = self.thermal_camera and getattr(self.thermal_camera, 'is_sdk_connected', False)
                    port = getattr(self.args, 'com_port', None)
                    self.gui.boson_panel.update_connection_status(is_sdk)
                    logger.info(f"Deferred connection status: connected={is_sdk}, port={port}")

                # Update Camera Info
                if self.thermal_camera and hasattr(self.thermal_camera, 'get_camera_info'):
                    cam_info = self.thermal_camera.get_camera_info()
                    logger.info(f"Deferred Camera Info: {cam_info}")
                    if cam_info and hasattr(self.gui.boson_panel, 'update_camera_info'):
                        self.gui.boson_panel.update_camera_info(cam_info)
                        logger.info("Deferred camera info update sent to boson_panel")
            
            # 3. Force 8-bit toggle update
            if hasattr(self.gui, 'radiometric_panel'):
                self.gui.radiometric_panel.set_8bit_estimation_available(
                    available=True,
                    auto_enabled=self.temp_estimation_enabled
                )

            # 4. Propagate thermal resolution to GUI overlay for coordinate mapping (Bug Fix)
            if self.thermal_connected and self.thermal_camera:
                try:
                    actual_res = self.thermal_camera.get_actual_resolution()
                    if hasattr(self.gui, 'video_widget') and hasattr(self.gui.video_widget, 'overlay'):
                        if hasattr(self.gui.video_widget.overlay, 'set_thermal_resolution'):
                            self.gui.video_widget.overlay.set_thermal_resolution(actual_res[0], actual_res[1])
                            logger.info(f"[DEFERRED] Thermal resolution propagated to overlay: {actual_res[0]}x{actual_res[1]}")
                except Exception as res_e:
                    logger.warning(f"Failed to propagate thermal resolution: {res_e}")

        except Exception as e:
            logger.error(f"Error during deferred GUI initialization: {e}", exc_info=True)


    def run(self):
        """Main inspection application loop."""
        logger.info("Starting inspection loop...")
        self.running = True

        # Start threaded camera capture (if enabled)
        if self.threaded_capture:
            self.threaded_capture.start()
            logger.info("Threaded camera capture started")

        # Show Qt GUI if available
        if self.gui_type == 'qt' and self.gui:
            self.gui.show()
            logger.info("Qt GUI window shown")

        try:
            while self.running:
                if self.reconfiguring:
                    time.sleep(0.1)
                    if self.gui_type == 'qt' and self.qt_app:
                        self.qt_app.processEvents()
                    continue

                # Deferred GUI initialization (one-shot)
                if not getattr(self, '_deferred_init_done', False):
                    self._perform_deferred_initialization()
                    self._deferred_init_done = True
                    # Initialize last_deferred_update time
                    self._last_deferred_update = time.time()

                loop_start = time.time()
                t_markers = {'start': loop_start}  # Timing markers for profiling

                # Calculate FPS
                current_time = time.time()
                if (current_time - self.last_frame_time) > 0:
                    self.fps = 1.0 / (current_time - self.last_frame_time)
                self.last_frame_time = current_time

                # REMOVED: Frame skipping logic - it was creating a feedback loop
                # The issue was that skipping frames causes fps to measure incorrectly
                # Instead, we'll optimize the processing pipeline itself

                # 1. Poll for thermal camera if not connected (hot-plug support)
                # Wait for thermal camera (hot-plug support)
                if not self.thermal_connected:
                    current_time = time.time()
                    if current_time - self.last_thermal_scan_time > self.thermal_scan_interval:
                        self.last_thermal_scan_time = current_time
                        logger.info("Thermal camera not connected. Scanning...")
                        self._try_connect_thermal()

                        # Initialize ROI radiometric analyzer when thermal camera is connected
                        # (only if it has a radiometric converter)
                        if self.thermal_connected: # Check if connection was successful
                            logger.info("[OK] Thermal camera connected!")
                            if (self.thermal_camera and
                                hasattr(self.thermal_camera, 'radiometric_converter') and
                                self.thermal_camera.radiometric_converter and
                                not self.roi_radiometric_analyzer):
                                try:
                                    self.roi_radiometric_analyzer = ROIRadiometricAnalyzer(
                                        self.thermal_camera.radiometric_converter
                                    )
                                    logger.info("[OK] ROI radiometric analyzer initialized")
                                except Exception as e:
                                    logger.warning(f"Failed to initialize ROI radiometric analyzer: {e}")
                        continue

                # 2. Check for freeze state
                if self.frame_frozen:
                    # If frozen, just process GUI events and continue
                    # We skip capture and processing to maintain the static image
                    if self.gui_type == 'qt' and self.qt_app:
                        self.qt_app.processEvents()
                    
                    # Sleep briefly to prevent CPU spinning
                    time.sleep(0.03)
                    continue

                # 3. Capture thermal frame
                t_markers['before_thermal_read'] = time.time()
                thermal_frame = None
                rgb_frame = None

                # Use threaded capture if available (MUCH faster!)
                if self.threaded_capture:
                    thermal_frame, rgb_frame = self.threaded_capture.get_frames()
                    t_markers['after_thermal_read'] = time.time()
                    t_markers['after_placeholder'] = time.time()
                    t_markers['after_rgb_read'] = time.time()
                else:
                    # Fallback to blocking capture
                    try:
                        if self.thermal_camera and self.thermal_connected:
                            ret_thermal, thermal_frame = self.thermal_camera.read()
                            if not ret_thermal or thermal_frame is None:
                                logger.warning("Thermal camera disconnected")
                                self.thermal_connected = False
                                if self.thermal_camera:
                                    self.thermal_camera.release()
                                self.thermal_camera = None
                                self.is_flir_boson = False # Reset flag
                    except Exception as e:
                        logger.warning(f"Thermal camera error: {e}")
                        self.thermal_connected = False
                        if self.thermal_camera:
                            self.thermal_camera.release()
                        self.thermal_camera = None
                        self.is_flir_boson = False # Reset flag

                    t_markers['after_rgb_read'] = time.time()

                # Create placeholder if no thermal
                if thermal_frame is None:
                    res = (self.args.width, self.args.height)
                    placeholder_rgb = create_thermal_placeholder(width=res[0], height=res[1])
                    placeholder_gray = cv2.cvtColor(placeholder_rgb, cv2.COLOR_BGR2GRAY)
                    thermal_frame = (placeholder_gray.astype(np.uint16) * 256)

                # Store thermal frame for Auto-ROI detection
                self.last_thermal_frame = thermal_frame
                
                # Fix for top-line corruption (hardware/driver artifact):
                # Mask top 8 rows to prevent false cold/hot spot detections
                if thermal_frame is not None and thermal_frame.shape[0] > 8:
                    # Option 1: Set to 0 (might be cold spot if 0 is cold)
                    # Option 2: Clone row 8 (better for visualization)
                    # Option 3: Mask with invalid value if handled?
                    # We'll use row 8 replication to be visually unobtrusive
                    thermal_frame[:8, :] = thermal_frame[8, :]
                
                # 4. Process frames through inspection pipeline
                result = self.process_frame(thermal_frame, rgb_frame)
                t_markers['after_process_frame'] = time.time()

                # 4.5. Handle recording (NEW - Phase 6)
                display_frame = result.get('display_frame')
                if self.recording_enabled and display_frame is not None:
                    # Start recording if not already started
                    if not self.video_recorder.is_recording():
                        # Extract height and width from frame shape (ignore channels)
                        frame_shape = (display_frame.shape[0], display_frame.shape[1])
                        if self.video_recorder.start_recording(frame_shape, fps=30):
                            logger.info("Recording started")

                    # Write frame
                    rois = result.get('rois', [])
                    thermal_stats = {
                        'min_temp': result.get('min_temp'),
                        'max_temp': result.get('max_temp'),
                        'mean_temp': result.get('mean_temp'),
                    }
                    self.video_recorder.write_frame(
                        fusion_frame=display_frame,
                        thermal_frame=thermal_frame,
                        rgb_frame=rgb_frame,
                        rois=rois,
                        thermal_stats=thermal_stats
                    )
                elif not self.recording_enabled and self.video_recorder.is_recording():
                    # Stop recording
                    self.video_recorder.stop_recording()
                    logger.info("Recording stopped")

                # 5. Display (temporary simple display until GUI is ready)
                t_markers['before_gui_update'] = time.time()
                display_frame = result.get('display_frame')
                if display_frame is not None and self.gui_type == 'opencv':
                    # Simple OpenCV display
                    cv2.imshow('Thermal Inspection', display_frame)
                    key = cv2.waitKey(1) & 0xFF
                    if key == ord('q'):
                        break
                    elif key == ord('r'):
                        # Toggle recording
                        self.recording_enabled = not self.recording_enabled
                        logger.info(f"Recording: {'ON' if self.recording_enabled else 'OFF'}")
                    elif key == ord('s'):
                        # Capture snapshot (NEW - Phase 6)
                        self.capture_snapshot()
                    elif key == ord('f'):
                        # Trigger FFC (Flat Field Correction) - NEW: Phase 7
                        if self.thermal_camera and self.thermal_camera.is_sdk_connected:
                            logger.info("Triggering FFC (watch camera shutter)...")
                            if self.thermal_camera.trigger_ffc():
                                logger.info("[OK] FFC completed successfully")
                            else:
                                logger.error("[ERROR] FFC failed")
                        else:
                            logger.warning("FFC requires Boson SDK connection (use --enable-boson-sdk)")
                    elif key == ord('t'):
                        # Show FPA temperature - NEW: Phase 7
                        if self.thermal_camera and self.thermal_camera.is_sdk_connected:
                            temp = self.thermal_camera.get_fpa_temperature()
                            if temp:
                                logger.info(f"FPA Temperature: {temp[0]:.1f}K ({temp[1]:.1f}°C)")
                            else:
                                logger.warning("Could not read FPA temperature")
                        else:
                            logger.warning("Temperature reading requires Boson SDK connection")
                # Update Qt GUI
                elif self.gui_type == 'qt' and self.gui:
                    if display_frame is not None:
                        self.gui.update_frame(display_frame)

                    # Update metrics
                    self.gui.update_metrics(
                        fps=self.smoothed_fps,
                        roi_count=len(result.get('rois', [])),
                        thermal_connected=self.thermal_connected,
                        rgb_connected=self.rgb_available
                    )

                    # Update thermal analysis
                    self.gui.update_thermal_analysis(
                        stats=result.get('thermal_stats'),
                        hot_spots=result.get('hot_spots', []),
                        cold_spots=result.get('cold_spots', []),
                        anomalies=result.get('anomalies', []),
                        motion_detections=result.get('motion_detections', []),
                        edge_clusters=result.get('edge_clusters', []),
                        trend=result.get('trend')
                    )

                    # Update Per-ROI panel (NEW - Fix for Bug #7)
                    if hasattr(self.gui, 'roi_temp_panel'):
                        self.gui.roi_temp_panel.update_roi_data(result.get('roi_temp_stats', {}))

                    # Update radiometric panel with live temperature data
                    if hasattr(self.gui, 'radiometric_panel') and self.args.radiometric:
                        thermal_stats = result.get('thermal_stats')
                        thermal_frame_16bit = result.get('thermal_16bit')
                        
                        # Update frame statistics (min/max/mean)
                        if thermal_stats:
                            self.gui.radiometric_panel.set_frame_statistics(
                                min_temp=thermal_stats.min_temp,
                                max_temp=thermal_stats.max_temp,
                                mean_temp=thermal_stats.mean_temp,
                                unit=thermal_stats.unit
                            )
                        
                        # Update center temperature (frame center pixel)
                        if thermal_frame_16bit is not None:
                            h, w = thermal_frame_16bit.shape
                            center_y, center_x = h // 2, w // 2
                            center_pixel = thermal_frame_16bit[center_y, center_x]
                            
                            # Convert to temperature if radiometric converter available
                            if self.thermal_camera and hasattr(self.thermal_camera, 'radiometric_converter'):
                                conv = self.thermal_camera.radiometric_converter
                                if conv:
                                    # Update center
                                    center_temp_c = conv.pixel_to_celsius(center_pixel)
                                    self.gui.radiometric_panel.set_center_temperature(center_temp_c)

                                    # Update Spot Meters
                                    if hasattr(self.gui, 'measurement_points') and self.gui.measurement_points:
                                        spot_updates = []
                                        for p in self.gui.measurement_points:
                                            # Boundary check
                                            if 0 <= p.x < w and 0 <= p.y < h:
                                                raw_val = thermal_frame_16bit[p.y, p.x]
                                                t_c = conv.pixel_to_celsius(raw_val)
                                                spot_updates.append({
                                                    'label': p.label,
                                                    'temperature': t_c,
                                                    'unit': 'C'
                                                })
                                        
                                        if spot_updates:
                                            self.gui.update_spot_meter_values(spot_updates)

                        # Update cursor temperature if cursor position is available
                        # (This would be set by mouse move events in the GUI)
                        # For now, we'll use center as a placeholder

                    # Update ROIs
                    self.gui.update_rois(result.get('rois', []))

                    # Update Spot Meters (Enhancement #1)
                    if hasattr(self.gui, 'get_spot_meter_coords'):
                        # 1. Get current spot meters from GUI
                        spots = self.gui.get_spot_meter_coords() # List of (x, y, label)
                        
                        if spots:
                            spot_updates = []
                            h, w = thermal_frame.shape[:2]
                            
                            # Determine source frame and converter
                            # Prefer 16-bit frame if available for accuracy
                            t_frame_source = result.get('thermal_16bit')
                            is_16bit = False
                            
                            if t_frame_source is not None:
                                is_16bit = True
                            else:
                                t_frame_source = thermal_frame # Fallback
                                # Robust check: logic might have passed 16-bit frame as main 'thermal'
                                if t_frame_source is not None:
                                     if t_frame_source.dtype == np.uint16 or np.max(t_frame_source) > 255:
                                         is_16bit = True
                                
                            use_radiometric = False
                            converter = None
                            
                            # Only use radiometric converter if we have 16-bit data AND a converter
                            if is_16bit and self.thermal_camera and hasattr(self.thermal_camera, 'radiometric_converter') and self.thermal_camera.radiometric_converter:
                                use_radiometric = True
                                converter = self.thermal_camera.radiometric_converter
                            
                            for x, y, label in spots:
                                # Boundary check
                                if 0 <= x < w and 0 <= y < h:
                                    raw_val = t_frame_source[y, x]
                                    
                                    temp = 0.0
                                    unit = ''

                                    # Delegate calculation to ThermalAnalyzer for consistency
                                    if self.thermal_analyzer:
                                        # Determine if we should force estimation (e.g., if args.radiometric is true but no converter)
                                        # Note: calculate_spot_temperature handles the logic internally
                                        temp, unit = self.thermal_analyzer.calculate_spot_temperature(
                                            raw_val=raw_val,
                                            converter=converter,
                                            force_estimation=(self.args.radiometric and not is_16bit)
                                        )
                                    else:
                                        # Fallback if analyzer not ready (should rarely happen)
                                        temp = float(raw_val)
                                        unit = ' (raw)'

                                    # Debug logging once per second
                                    if self.frame_count % 60 == 0:
                                         logger.info(f"Spot {label}: raw={raw_val}, temp={temp:.1f}{unit}, target={self.temperature_unit}")

                                    spot_updates.append({
                                        'label': label,
                                        'temperature': temp,
                                        'unit': unit
                                    })
                                    
                            # 2. Send updates back to GUI
                            if spot_updates:
                                self.gui.update_spot_meter_values(spot_updates)

                    # Update Boson panel (every 60 frames to reduce overhead)
                    if self.frame_count % 60 == 0:
                        self.update_boson_gui()

                    # Update Radiometric panel (every 30 frames for live temperature)
                    if self.frame_count % 30 == 0:
                        self.update_radiometric_gui()

                    t_markers['before_processEvents'] = time.time()
                    self.qt_app.processEvents()
                    t_markers['after_processEvents'] = time.time()

                t_markers['after_gui_update'] = time.time()
                loop_time = time.time() - loop_start
                self.frame_times.append(loop_time)
                if len(self.frame_times) > 0:
                    avg_time = sum(self.frame_times) / len(self.frame_times)
                    self.smoothed_fps = 1.0 / avg_time if avg_time > 0 else 0

                self.frame_count += 1

                # Periodic Spot Meter Logging (Enhancement #12)
                # Log independent of frame rate (every 10 seconds default)
                current_time = time.time()
                if hasattr(self, 'spot_log_interval') and (current_time - self.last_spot_log_time >= self.spot_log_interval):
                    self.last_spot_log_time = current_time
                    if hasattr(self.gui, 'spot_meter_panel') and hasattr(self, 'spot_meter_logger'):
                        # Use logger from spot_meter_exporter.py if integrated, or just log to file manually here
                        # For now, we'll use the SpotMeterLogger class if we instantiated it, or just use info log
                        # Note: We need to instantiate SpotMeterLogger in __init__ if we want to use it
                        pass
                    
                    # Simple logging for now as per requirements
                    if hasattr(self.gui, 'get_spot_meter_coords'):
                        spots = self.gui.get_spot_meter_coords()
                        if spots:
                            logger.info(f"Spot Meter Log: {len(spots)} spots active")

                # Log periodically with detailed timing breakdown
                if self.frame_count % 100 == 0:
                    # Calculate main loop timing deltas
                    thermal_read_ms = (t_markers.get('after_thermal_read', 0) - t_markers.get('before_thermal_read', 0)) * 1000
                    placeholder_ms = (t_markers.get('after_placeholder', 0) - t_markers.get('after_thermal_read', 0)) * 1000
                    rgb_read_ms = (t_markers.get('after_rgb_read', 0) - t_markers.get('after_placeholder', 0)) * 1000
                    process_frame_ms = (t_markers.get('after_process_frame', 0) - t_markers.get('after_rgb_read', 0)) * 1000
                    gui_update_ms = (t_markers.get('after_gui_update', 0) - t_markers.get('before_gui_update', 0)) * 1000
                    process_events_ms = (t_markers.get('after_processEvents', 0) - t_markers.get('before_processEvents', 0)) * 1000

                    logger.info(f"Frame {self.frame_count}: {self.smoothed_fps:.1f} FPS ({avg_time*1000:.1f}ms/frame)")
                    logger.info(f"  Main loop: thermal_read={thermal_read_ms:.1f}ms, placeholder={placeholder_ms:.1f}ms, "
                               f"rgb_read={rgb_read_ms:.1f}ms, process_frame={process_frame_ms:.1f}ms, "
                               f"gui_update={gui_update_ms:.1f}ms, processEvents={process_events_ms:.1f}ms")

                    # Calculate process_frame internal timing (from result's timing_profile)
                    t_prof = result.get('timing_profile', {})
                    if t_prof:
                        thermal_proc_ms = (t_prof.get('after_thermal_processor', 0) - t_prof.get('before_thermal_processor', 0)) * 1000
                        palette_ms = (t_prof.get('after_palette', 0) - t_prof.get('before_palette', 0)) * 1000
                        auto_roi_ms = (t_prof.get('after_auto_roi', 0) - t_prof.get('before_auto_roi', 0)) * 1000
                        roi_analysis_ms = (t_prof.get('after_roi_analysis', 0) - t_prof.get('before_roi_analysis', 0)) * 1000
                        thermal_analysis_ms = (t_prof.get('after_thermal_analysis', 0) - t_prof.get('before_thermal_analysis', 0)) * 1000
                        anomaly_priority_ms = (t_prof.get('after_anomaly_priority', 0) - t_prof.get('before_anomaly_priority', 0)) * 1000
                        fusion_ms = (t_prof.get('after_fusion', 0) - t_prof.get('before_fusion', 0)) * 1000
                        display_select_ms = (t_prof.get('after_display_select', 0) - t_prof.get('before_display_select', 0)) * 1000
                        draw_rois_ms = (t_prof.get('after_draw_rois', 0) - t_prof.get('before_draw_rois', 0)) * 1000

                        logger.info(f"  process_frame breakdown: thermal_proc={thermal_proc_ms:.1f}ms, palette={palette_ms:.1f}ms, "
                                   f"auto_roi={auto_roi_ms:.1f}ms, roi_analysis={roi_analysis_ms:.1f}ms, "
                                   f"thermal_analysis={thermal_analysis_ms:.1f}ms, anomaly_priority={anomaly_priority_ms:.1f}ms, "
                                   f"fusion={fusion_ms:.1f}ms, display_select={display_select_ms:.1f}ms, draw_rois={draw_rois_ms:.1f}ms")

                    logger.info(f"  Detections: {len(result['rois'])} ROIs, {len(result['motion_detections'])} motion, "
                               f"{len(result['edge_clusters'])} edges, {len(result['hot_spots'])} hot spots")

        except KeyboardInterrupt:
            logger.info("Interrupted by user")
        except Exception as e:
            logger.error(f"Main loop error: {e}", exc_info=True)
        finally:
            self.cleanup()
    # ========================================================================
    # GUI Control Methods
    # ========================================================================

    def capture_snapshot(self):
        """Capture snapshot with full metadata (including spot meters)."""
        if not hasattr(self, 'latest_display_frame') or self.latest_display_frame is None:
            logger.warning("Cannot capture snapshot: no frame available")
            return

        try:
            # 1. Get spot meters from GUI (Enhancement #12)
            spot_meters = None
            if self.gui and hasattr(self.gui, 'get_spot_meter_coords'):
                # We need the full spot data objects or a dict list that SnapshotManager expects
                # SnapshotManager (modified) expects a list of dicts or objects
                # GUI returns list of (x, y, label) tuples from get_spot_meter_coords... 
                # actually check get_spot_meter_coords implementation in inspection_gui_qt
                # Better: use spot_meter_panel.get_all_spots() if available
                if hasattr(self.gui, 'analysis_panel') and hasattr(self.gui.analysis_panel, 'spot_meter_panel'):
                    spot_meters = self.gui.analysis_panel.spot_meter_panel.get_all_spots()
            
            # 2. Capture
            snapshot_path = self.snapshot_manager.capture_snapshot(
                frame=self.latest_display_frame,
                rois=getattr(self, 'latest_rois', []),
                thermal_stats=getattr(self, 'latest_stats', None),
                hot_spots=getattr(self, 'latest_hot_spots', []),
                cold_spots=getattr(self, 'latest_cold_spots', []),
                anomalies=getattr(self, 'latest_anomalies', []),
                spot_meters=spot_meters
            )
            
            if snapshot_path:
                logger.info(f"Snapshot saved: {snapshot_path}")
                # Optional: Show flash or status in GUI
                
        except Exception as e:
            logger.error(f"Snapshot capture failed: {e}")

    def set_palette(self, palette_name: str):
        """Set specific palette by name."""
        if not palette_name or not self.palette_manager:
            return
            
        # Strip whitespace (combo box adds indentation)
        palette_name = palette_name.strip()
        
        # Skip category headers (they contain "───")
        if "───" in palette_name:
            return
            
        try:
            self.palette_manager.set_global_palette(PaletteType(palette_name))
            if self.gui and hasattr(self.gui, 'control_panel') and hasattr(self.gui.control_panel, 'update_palette_button'):
                self.gui.control_panel.update_palette_button(palette_name)
            logger.info(f"Switched to palette: {palette_name}")
        except (ValueError, KeyError) as e:
            logger.error(f"Failed to set palette '{palette_name}': {e}")

    def cycle_palette(self):
        """Cycle to next palette."""
        if self.palette_manager:
            palettes = self.palette_manager.get_available_palettes()
            current = self.palette_manager.global_palette.palette_type.value
            try:
                idx = palettes.index(current)
                next_palette = palettes[(idx + 1) % len(palettes)]
                self.palette_manager.set_global_palette(PaletteType(next_palette))
                if self.gui and hasattr(self.gui, 'control_panel'):
                    self.gui.control_panel.update_palette_button(next_palette)
                logger.info(f"Switched to palette: {next_palette}")
            except (ValueError, IndexError):
                # Fallback to first palette
                if palettes:
                    self.palette_manager.set_global_palette(PaletteType(palettes[0]))
                    if self.gui and hasattr(self.gui, 'control_panel'):
                        self.gui.control_panel.update_palette_button(palettes[0])

    def set_device(self, device: str):
        """Set processing device."""
        self.device = device.lower()
        logger.info(f"Device set to: {self.device}")

    def set_fusion_mode(self, mode: str):
        """Set fusion mode."""
        self.fusion_mode = mode.lower()
        if self.fusion_processor:
            self.fusion_processor.set_mode(self.fusion_mode)
        
        # Update overlay widget view mode for proper detection coordinate handling (Bug #20 fix)
        # Update overlay widget view mode for proper detection coordinate handling (Bug #20 fix)
        if self.gui and hasattr(self.gui, 'video_widget') and hasattr(self.gui.video_widget, 'overlay'):
            self.gui.video_widget.overlay.set_view_mode(
                self.fusion_mode,
                fusion_priority=getattr(self, 'fusion_priority', 'rgb'),
                pip_size=0.25
            )
        
        logger.info(f"Fusion mode set to: {self.fusion_mode}")

    def set_fusion_alpha(self, alpha: float):
        """Set fusion alpha blending factor."""
        self.fusion_alpha = max(0.0, min(1.0, alpha))
        if self.fusion_processor:
            self.fusion_processor.set_alpha(self.fusion_alpha)
        # logger.info(f"Fusion alpha set to: {self.fusion_alpha}")

    def set_fusion_priority(self, priority: str):
        """Set fusion priority."""
        self.fusion_priority = priority.lower()
        if self.fusion_processor:
            self.fusion_processor.set_priority(self.fusion_priority)
        
        # Update overlay widget for PIP coordinate handling (Bug #20 fix)
        # Update overlay widget for PIP coordinate handling (Bug #20 fix)
        if self.gui and hasattr(self.gui, 'video_widget') and hasattr(self.gui.video_widget, 'overlay'):
            self.gui.video_widget.overlay.set_view_mode(
                getattr(self, 'fusion_mode', 'thermal'),
                fusion_priority=self.fusion_priority,
                pip_size=0.25
            )
        
        logger.info(f"Fusion priority set to: {self.fusion_priority}")

    def set_fusion_strength(self, strength: float):
        """Set fusion strength (intensity)."""
        if self.fusion_processor:
            self.fusion_processor.set_intensity(strength)
            logger.info(f"Fusion strength set to: {strength:.2f}")

    def set_fusion_fuzziness(self, fuzziness: float):
        """Set fusion fuzziness (edge blur for blending)."""
        if self.fusion_processor:
            # Convert 0.0-1.0 to kernel size (0-15)
            kernel_size = int(fuzziness * 15)
            # Ensure odd number for Gaussian blur
            if kernel_size > 0 and kernel_size % 2 == 0:
                kernel_size += 1
            self.fusion_processor.set_edge_blur(kernel_size)
            logger.info(f"Fusion fuzziness set to: {fuzziness:.2f} (kernel={kernel_size})")

    def set_fusion_color_mode(self, mode: str):
        """Set RGB fusion color mode (color vs grayscale)."""
        # Store the mode for use during RGB processing
        self.rgb_fusion_color_mode = mode.lower()
        logger.info(f"Fusion RGB color mode set to: {self.rgb_fusion_color_mode}")

    def set_edge_strength(self, strength: float):
        """Set edge detection strength (how many edges to detect)."""
        if self.fusion_processor:
            # Convert 0.0-1.0 to Canny threshold range
            # Higher strength = more edges = LOWER thresholds (detect more)
            # Lower strength = fewer edges = HIGHER thresholds (detect less)
            # Formula: strength 0.0 → threshold 100, strength 1.0 → threshold 10
            threshold_low = int(100 - (strength * 90))  # Range: 100→10
            self.fusion_processor.set_edge_strength(threshold_low)
            logger.info(f"Edge strength set to: {strength:.2f} (threshold={threshold_low})")

    def set_edge_fuzziness(self, fuzziness: float):
        """Set edge fuzziness (edge sharpness/softness).

        Lower fuzziness = sharper edges (more detail shows through)
        Higher fuzziness = softer edges (less sharp, more blended)
        """
        if self.fusion_processor:
            # Convert 0.0-1.0 to kernel size (0-15)
            # Lower fuzziness = smaller kernel = sharper edges
            # Higher fuzziness = larger kernel = softer edges
            kernel_size = int(fuzziness * 15)
            # Ensure odd number for Gaussian blur
            if kernel_size > 0 and kernel_size % 2 == 0:
                kernel_size += 1
            self.fusion_processor.set_edge_blur(kernel_size)
            logger.info(f"Edge fuzziness set to: {fuzziness:.2f} (kernel={kernel_size}, sharpness={'sharp' if fuzziness < 0.3 else 'medium' if fuzziness < 0.7 else 'soft'})")

    def set_edge_color(self, color: str):
        """Set edge overlay color."""
        if self.fusion_processor:
            # Map color names to BGR tuples
            color_map = {
                'white': (255, 255, 255),
                'cyan': (255, 255, 0),
                'green': (0, 255, 0),
                'yellow': (0, 255, 255),
                'red': (0, 0, 255),
                'magenta': (255, 0, 255)
            }
            bgr_color = color_map.get(color.lower(), (255, 255, 0))  # Default to cyan
            self.fusion_processor.set_edge_color(bgr_color)
            logger.info(f"Edge color set to: {color} (BGR={bgr_color})")

    def set_detail_strength(self, strength: float):
        """Set Detail Injection/Relief Fusion strength."""
        if self.fusion_processor:
            self.fusion_processor.detail_strength = strength
            logger.info(f"Detail strength set to: {strength:.2f}")

    def set_detail_quality(self, quality: float):
        """Set Detail Injection/Relief Fusion quality/detail level."""
        if self.fusion_processor:
            self.fusion_processor.detail_quality = quality
            logger.info(f"Detail quality set to: {quality:.2f}")

    def set_view_mode(self, mode: str):
        """Set view mode."""
        mode_map = {
            "thermal only": ViewMode.THERMAL_ONLY,
            "rgb only": ViewMode.RGB_ONLY,
            "fusion": ViewMode.FUSION,
            "side-by-side": ViewMode.SIDE_BY_SIDE,
            "picture-in-picture": ViewMode.PICTURE_IN_PICTURE
        }
        view_mode = mode_map.get(mode.lower())
        if view_mode:
            self.view_mode = view_mode
            logger.info(f"View mode set to: {self.view_mode}")
        else:
            logger.warning(f"Invalid view mode: {mode}")

    def cycle_view_mode(self):
        """Cycle view mode."""
        modes = [ViewMode.THERMAL_ONLY, ViewMode.RGB_ONLY, ViewMode.FUSION, ViewMode.SIDE_BY_SIDE, ViewMode.PICTURE_IN_PICTURE]
        try:
            idx = modes.index(self.view_mode)
            self.view_mode = modes[(idx + 1) % len(modes)]
            if self.gui and hasattr(self.gui, 'control_panel'):
                self.gui.control_panel.update_view_button(self.view_mode)
            logger.info(f"Switched to view mode: {self.view_mode}")
        except ValueError:
            pass

    def toggle_recording(self, enabled: bool):
        """Toggle recording."""
        self.recording_enabled = enabled
        # Note: Actual recording start happens in the main loop when first frame arrives
        # This just sets the flag
        logger.info(f"Recording: {'ENABLED' if enabled else 'OFF'}")

    def capture_snapshot(self):
        """Capture snapshot."""
        if self.snapshot_manager:
            # We need the latest frame. It's not stored globally, so we might need to grab it from last processing result
            # For now, we'll rely on the main loop to handle 's' key, but for GUI button we need a way.
            # Let's store the latest display frame in self
            if hasattr(self, 'latest_display_frame') and self.latest_display_frame is not None:
                path = self.snapshot_manager.capture_snapshot(
                    self.latest_display_frame,
                    self.latest_rois,
                    self.latest_stats,
                    self.latest_hot_spots,
                    self.latest_cold_spots,
                    self.latest_anomalies
                )
                logger.info(f"Snapshot saved: {path}")
            else:
                logger.warning("No frame available for snapshot")

    def toggle_freeze(self, enabled: bool):
        """Toggle frame freeze."""
        self.frame_frozen = enabled
        logger.info(f"Frame freeze: {'ON' if enabled else 'OFF'}")

    def toggle_motion(self, enabled: bool):
        """Toggle motion detection."""
        if self.thermal_processor:
            self.thermal_processor.set_motion_enabled(enabled)
            logger.info(f"Motion detection: {enabled}")

    def toggle_edge(self, enabled: bool):
        """Toggle edge detection."""
        if self.thermal_processor:
            self.thermal_processor.set_edge_enabled(enabled)
            logger.info(f"Edge detection: {enabled}")

    def toggle_anomaly_priority(self, enabled: bool):
        """Toggle anomaly priority mode."""
        if self.thermal_processor:
            self.thermal_processor.set_anomaly_priority_enabled(enabled)
            logger.info(f"Anomaly priority: {enabled}")

    def set_enabled_anomaly_types(self, types_dict: dict):
        """Set which anomaly types are enabled for anomaly priority visualization."""
        self.enabled_anomaly_types = types_dict.copy()
        logger.info(f"Enabled anomaly types: {self.enabled_anomaly_types}")

    def set_manual_threshold_enabled(self, enabled: bool):
        """Enable/disable manual threshold detection."""
        self.manual_threshold_enabled = enabled
        logger.info(f"Manual threshold enabled: {enabled}")

    def set_temperature_unit(self, unit: str):
        """
        Set temperature unit for display and analysis.
        
        Args:
            unit: 'C', 'F', 'K', or 'RAW'
        """
        logger.info(f"Setting temperature unit to: {unit}")
        self.temperature_unit = unit
        
        # Update ThermalAnalyzer
        if self.thermal_analyzer:
            # ThermalAnalyzer expects 'C', 'F', 'K'
            # If 'RAW' is selected, we tell analyzer to use 'C' (base unit) 
            # and let the UI handle the raw display
            analyzer_unit = 'C' if unit == 'RAW' else unit
            self.thermal_analyzer.set_temperature_unit(analyzer_unit)
            
        # Update ROI Manager if it has unit awareness
        # (ROIManager currently handles units internally or relies on analyzer)
        
        # Update GUI components if needed
        # (InspectionOverlayWidget is updated directly by ThermalAnalysisPanel)

    def set_manual_threshold_mode(self, mode: str):
        """Set manual threshold mode."""
        mode_map = {
            "above": ThresholdMode.ABOVE,
            "below": ThresholdMode.BELOW,
            "between": ThresholdMode.BETWEEN,
            "outside": ThresholdMode.OUTSIDE
        }
        self.manual_threshold_mode = mode_map.get(mode, ThresholdMode.ABOVE)
        logger.info(f"Manual threshold mode: {mode} -> {self.manual_threshold_mode}")

    def set_manual_min_threshold(self, value: float):
        """Set manual minimum threshold."""
        self.manual_threshold_min = value
        logger.info(f"Manual min threshold: {value}")

    def set_manual_max_threshold(self, value: float):
        """Set manual maximum threshold."""
        self.manual_threshold_max = value
        logger.info(f"Manual max threshold: {value}")

    def set_manual_use_raw_values(self, use_raw: bool):
        """Set whether manual threshold uses raw values or temperature."""
        self.manual_threshold_use_raw = use_raw
        logger.info(f"Manual threshold use raw: {use_raw}")

    def set_manual_viz_mode(self, mode: str):
        """Set manual threshold visualization mode."""
        mode_map = {
            "grayscale_non_anomaly": ThresholdVisualization.GRAYSCALE_NON_ANOMALY,
            "color_non_anomaly": ThresholdVisualization.COLOR_NON_ANOMALY,
            "binary_mask": ThresholdVisualization.BINARY_MASK,
            "gradient_overlay": ThresholdVisualization.GRADIENT_OVERLAY
        }
        self.manual_threshold_viz_mode = mode_map.get(mode, ThresholdVisualization.GRAYSCALE_NON_ANOMALY)
        logger.info(f"Manual threshold viz mode: {mode} -> {self.manual_threshold_viz_mode}")

    # === ENVIRONMENTAL COMPENSATION METHODS ===

    def set_emissivity(self, value: float):
        """Set target emissivity for temperature compensation.
        
        Args:
            value: Emissivity value (0.0-1.0), typically 0.95 for most objects
        """
        self.emissivity = max(0.01, min(1.0, value))
        # Apply to thermal camera if SDK connected
        if self.thermal_camera and hasattr(self.thermal_camera, 'set_emissivity'):
            self.thermal_camera.set_emissivity(self.emissivity)
        logger.info(f"Emissivity set to: {self.emissivity:.2f}")

    def set_atmospheric_temperature(self, temp_celsius: float):
        """Set atmospheric/ambient temperature for compensation.
        
        Args:
            temp_celsius: Ambient temperature in Celsius
        """
        self.atmospheric_temp = temp_celsius
        # Apply to thermal camera if SDK connected
        if self.thermal_camera and hasattr(self.thermal_camera, 'set_atmospheric_temperature'):
            self.thermal_camera.set_atmospheric_temperature(self.atmospheric_temp)
        logger.info(f"Atmospheric temperature set to: {self.atmospheric_temp:.1f}°C")

    def set_atmospheric_transmission(self, transmission: float):
        """Set atmospheric transmission coefficient.
        
        Args:
            transmission: Transmission (0.0-1.0), 1.0=clear, 0.9=typical 1-2m, 0.8=humid/far
        """
        self.atmospheric_transmission = max(0.0, min(1.0, transmission))
        # Apply to thermal camera if SDK connected  
        if self.thermal_camera and hasattr(self.thermal_camera, 'set_atmospheric_transmission'):
            self.thermal_camera.set_atmospheric_transmission(self.atmospheric_transmission)
        logger.info(f"Atmospheric transmission set to: {self.atmospheric_transmission:.2f}")

    # === RADIOMETRIC CONTROL METHODS ===

    def set_temperature_unit(self, unit: str):
        """Set temperature display unit (C, F, K).
        
        Args:
            unit: 'C' for Celsius, 'F' for Fahrenheit, 'K' for Kelvin
        """
        self.temperature_unit = unit.upper()
        # Update thermal analyzer
        if hasattr(self, 'thermal_analyzer') and self.thermal_analyzer:
            self.thermal_analyzer.set_temperature_unit(unit)
        logger.info(f"Temperature unit set to: {self.temperature_unit}")

    def set_max_hot_spots(self, count: int):
        """Set maximum number of hot spots to detect and display.
        
        Args:
            count: Maximum hot spots (0=unlimited, typical 1-10)
        """
        self.max_hot_spots = count
        logger.info(f"Max hot spots set to: {count}")

    def set_max_cold_spots(self, count: int):
        """Set maximum number of cold spots to detect and display.
        
        Args:
            count: Maximum cold spots (0=unlimited, typical 1-10)
        """
        self.max_cold_spots = count
        logger.info(f"Max cold spots set to: {count}")

    def set_temp_estimation_enabled(self, enabled: bool):
        """Enable/disable 8-bit temperature estimation mode.
        
        Args:
            enabled: True to enable 8-bit estimation
        """
        self.temp_estimation_enabled = enabled
        logger.info(f"8-bit temperature estimation: {'ON' if enabled else 'OFF'}")

    def set_temperature_range(self, min_c: float, max_c: float):
        """Set expected temperature range for 8-bit estimation.
        
        Args:
            min_c: Minimum expected temperature (Celsius)
            max_c: Maximum expected temperature (Celsius)
        """
        self.temp_range_min = min_c
        self.temp_range_max = max_c
        if hasattr(self, 'temp_estimator') and self.temp_estimator:
            self.temp_estimator.set_range(min_c, max_c)
        logger.info(f"Temperature range: {min_c:.1f}°C to {max_c:.1f}°C")

    def calibrate_single_point(self):
        """Request single-point temperature calibration."""
        if hasattr(self, 'temp_estimator') and self.temp_estimator:
            # Single point calibration uses current spot meter if available
            logger.info("Single-point calibration: Click on known temperature reference")
            # Flag will be checked in main loop
            self._calibration_mode = 'single_point'
        else:
            logger.warning("Temperature estimator not available for calibration")

    def calibrate_two_point(self):
        """Request two-point temperature calibration."""
        if hasattr(self, 'temp_estimator') and self.temp_estimator:
            logger.info("Two-point calibration: Click on two known temperature references")
            self._calibration_mode = 'two_point'
        else:
            logger.warning("Temperature estimator not available for calibration")

    # === ISOTHERM CONTROL METHODS ===

    def set_isotherm_enabled(self, enabled: bool):
        """Enable/disable isotherm temperature highlighting.
        
        Args:
            enabled: True to enable isotherm overlay
        """
        self.isotherm_enabled = enabled
        logger.info(f"Isotherm highlighting: {'ON' if enabled else 'OFF'}")

    def set_isotherm_mode(self, mode: str):
        """Set isotherm detection mode.
        
        Args:
            mode: 'above', 'below', 'between', or 'outside'
        """
        self.isotherm_mode = mode
        logger.info(f"Isotherm mode: {mode}")

    def set_isotherm_low_threshold(self, value: float):
        """Set isotherm low temperature threshold.
        
        Args:
            value: Temperature threshold in current unit
        """
        self.isotherm_low_threshold = value
        logger.info(f"Isotherm low threshold: {value:.1f}")

    def set_isotherm_high_threshold(self, value: float):
        """Set isotherm high temperature threshold.
        
        Args:
            value: Temperature threshold in current unit
        """
        self.isotherm_high_threshold = value
        logger.info(f"Isotherm high threshold: {value:.1f}")

    def set_isotherm_color(self, color: str):
        """Set isotherm highlight color.
        
        Args:
            color: Color name (Red, Yellow, Green, Blue, Magenta, Cyan, White)
        """
        # Map color names to BGR tuples for OpenCV
        color_map = {
            'red': (0, 0, 255),
            'yellow': (0, 255, 255),
            'green': (0, 255, 0),
            'blue': (255, 0, 0),
            'magenta': (255, 0, 255),
            'cyan': (255, 255, 0),
            'white': (255, 255, 255)
        }
        self.isotherm_color_name = color
        self.isotherm_color_bgr = color_map.get(color.lower(), (0, 0, 255))
        logger.info(f"Isotherm color: {color}")

    def cycle_fusion_mode(self):
        """Cycle fusion mode."""
        self.current_fusion_mode_index = (self.current_fusion_mode_index + 1) % len(self.available_fusion_modes)
        self.fusion_mode = self.available_fusion_modes[self.current_fusion_mode_index]

        # Actually apply the new fusion mode to the processor
        if self.fusion_processor:
            self.fusion_processor.set_mode(self.fusion_mode)

        # Update GUI button
        if self.gui and hasattr(self.gui, 'control_panel'):
            self.gui.control_panel.update_fusion_mode_button(self.fusion_mode)
        logger.info(f"Fusion mode: {self.fusion_mode}")

    def cycle_fusion_alpha(self):
        """Cycle fusion alpha."""
        self.fusion_alpha += 0.1
        if self.fusion_alpha > 1.0:
            self.fusion_alpha = 0.0

        # Actually apply the new alpha to the processor
        if self.fusion_processor:
            self.fusion_processor.set_alpha(self.fusion_alpha)

        # Update GUI button
        if self.gui and hasattr(self.gui, 'control_panel'):
            self.gui.control_panel.update_fusion_alpha_button(self.fusion_alpha)
        logger.info(f"Fusion alpha: {self.fusion_alpha:.1f}")

    def cycle_fusion_priority(self):
        """Cycle fusion priority (thermal vs RGB base)."""
        if self.fusion_processor:
            # Toggle between 'thermal' and 'rgb' priority
            current_priority = self.fusion_processor.fusion_priority
            new_priority = 'rgb' if current_priority == 'thermal' else 'thermal'

            # Actually apply the new priority using set_priority method
            self.fusion_processor.set_priority(new_priority)

            # Update GUI button
            if self.gui and hasattr(self.gui, 'control_panel'):
                self.gui.control_panel.update_fusion_priority_button(new_priority)
            logger.info(f"Fusion priority: {new_priority}")

    def draw_roi(self):
        """Enable ROI drawing mode in GUI."""
        if self.gui:
            # GUI will handle drawing mode
            logger.info("Draw ROI mode activated")
    
    def auto_roi_detect(self):
        """Automatically detect ROIs based on temperature gradients."""
        if self.roi_manager and self.last_thermal_frame is not None:
            from roi_manager import ROISource
            if self.thermal_analyzer:
                # Detect ROIs based on temperature (hot and cold regions)
                temp_rois = self.roi_manager.detect_temperature_rois(
                    self.last_thermal_frame, detect_hot=True, detect_cold=True
                )
                # Detect ROIs based on thermal gradients
                gradient_rois = self.roi_manager.detect_gradient_rois(self.last_thermal_frame)
                logger.info(f"Auto-detected {len(temp_rois)} temperature ROIs and {len(gradient_rois)} gradient ROIs")
                
                # NMS Cleanup (Refinement)
                # Remove overlapping ROIs based on priority (Manual > Temp > Gradient > Motion > Edge)
                self.roi_manager.cleanup_overlapping_rois()
    
    def clear_rois(self):
        """Clear all ROIs."""
        if self.roi_manager:
            self.roi_manager.clear_all_rois()
            
            # Also clear radiometric analyzer history
            if self.roi_radiometric_analyzer:
                self.roi_radiometric_analyzer.clear_history()
            
            # Update GUI panel immediately
            if hasattr(self.gui, 'roi_temp_panel'):
                self.gui.roi_temp_panel.update_roi_data({})
                
            if hasattr(self.gui, 'roi_temp_panel'):
                self.gui.roi_temp_panel.update_roi_data({})
                
            logger.info("All ROIs cleared")

    def delete_roi(self, roi_id: str):
        """Delete a specific ROI and update related systems."""
        if self.roi_manager:
            self.roi_manager.delete_roi(roi_id)
            
            # Clear history for this ROI
            if self.roi_radiometric_analyzer:
                self.roi_radiometric_analyzer.clear_history(roi_id)
                
            # Clear any associated palette config
            if self.palette_manager:
                self.palette_manager.clear_roi_palette(roi_id)
            
            logger.info(f"ROI {roi_id} deleted")
    
    def save_rois(self, filename: str):
        """Save ROIs to JSON file."""
        if self.roi_manager:
            success = self.roi_manager.save_rois(filename)
            logger.info(f"ROIs {'saved to' if success else 'failed to save to'} {filename}")
            return success
        return False
    
    def load_rois(self, filename: str):
        """Load ROIs from JSON file."""
        if self.roi_manager:
            success = self.roi_manager.load_rois(filename)
            logger.info(f"ROIs {'loaded from' if success else 'failed to load from'} {filename}")
            return success
        return False
    
    def cycle_device(self):
        """Cycle processing device (CPU/CUDA)."""
        if self.thermal_processor:
            current_device = self.thermal_processor.device
            new_device = 'cpu' if current_device == 'cuda' else 'cuda'
            self.thermal_processor.switch_device(new_device)
            logger.info(f"Switched device: {current_device} -> {new_device}")
    def lock_baseline(self, enabled: bool):
        """Lock/unlock baseline temperature."""
        if self.thermal_analyzer:
            if enabled:
                # Lock current mean temp as baseline
                if self.latest_stats:
                    self.thermal_analyzer.set_baseline(self.latest_stats.mean_temp)
                    logger.info(f"Baseline locked at {self.latest_stats.mean_temp:.1f}")
            else:
                self.thermal_analyzer.set_baseline(None)
                logger.info("Baseline unlocked")

    # ========================================================================
    # Boson SDK Control Methods
    # ========================================================================

    def trigger_ffc(self):
        """Trigger FFC (Flat Field Correction)."""
        if self.thermal_camera and self.thermal_camera.is_sdk_connected:
            logger.info("Triggering FFC...")
            if self.thermal_camera.trigger_ffc():
                logger.info("[OK] FFC completed successfully")
                if self.gui and hasattr(self.gui, 'boson_panel'):
                    self.gui.boson_panel.set_status("FFC completed successfully", is_error=False)
                return True
            else:
                logger.error("[ERROR] FFC failed")
                if self.gui and hasattr(self.gui, 'boson_panel'):
                    self.gui.boson_panel.set_status("FFC failed", is_error=True)
                return False
        else:
            logger.warning("FFC requires Boson SDK connection")
        return False

    def connect_boson_sdk(self, com_port: str) -> bool:
        """
        Connect to Boson SDK on specified COM port.
        
        Args:
            com_port: COM port string (e.g., "COM6")
            
        Returns:
            True if successful
        """
        try:
            if not self.thermal_camera:
                logger.warning("No thermal camera available for SDK connection")
                return False
                
            logger.info(f"Connecting to Boson SDK on {com_port}...")
            success = self.thermal_camera.connect_sdk(com_port)
            
            if success:
                logger.info("[OK] Boson SDK connected")

                # Initialize 8-bit temperature estimator now that SDK is connected
                self._init_8bit_estimation()

                return True
            else:
                logger.error("[ERROR] Boson SDK connection failed")
                return False
                
        except Exception as e:
            logger.error(f"SDK connection error: {e}")
            import traceback
            traceback.print_exc()
            return False

    def scan_boson_com_ports(self) -> list:
        """
        Scan for available COM ports.
        
        Returns:
            List of available COM port names
        """
        try:
            import serial.tools.list_ports
            
            ports = []
            for port in serial.tools.list_ports.comports():
                ports.append(port.device)
                logger.debug(f"Found COM port: {port.device} - {port.description}")
                
            logger.info(f"Scanned {len(ports)} COM ports")
            return ports
            
        except ImportError:
            logger.error("pyserial not installed - cannot scan COM ports")
            return []
        except Exception as e:
            logger.error(f"Error scanning COM ports: {e}")
            return []

    def set_boson_gain_mode(self, mode: str):
        """Set Boson gain mode (high/low/auto)."""
        if self.thermal_camera and self.thermal_camera.is_sdk_connected:
            # Map string to enum value
            mode_map = {
                'high': 0,
                'low': 1,
                'auto': 2
            }
            if mode.lower() in mode_map:
                if self.thermal_camera.set_gain_mode(mode_map[mode.lower()]):
                    logger.info(f"Gain mode set to {mode}")
                    return True
                else:
                    logger.error(f"Failed to set gain mode to {mode}")
                    return False
        return False

    def set_boson_ffc_mode(self, mode: str):
        """Set Boson FFC mode (manual/auto/external)."""
        if self.thermal_camera and self.thermal_camera.is_sdk_connected:
            # Map string to enum value
            mode_map = {
                'manual': 0,
                'auto': 1,
                'external': 2
            }
            if mode.lower() in mode_map:
                if self.thermal_camera.set_ffc_mode(mode_map[mode.lower()]):
                    logger.info(f"FFC mode set to {mode}")
                    return True
                else:
                    logger.error(f"Failed to set FFC mode to {mode}")
                    return False
        return False

    # ========================================================================
    # Firefly Camera Control Methods
    # ========================================================================

    def set_firefly_exposure_mode(self, mode: str):
        """Set Firefly exposure mode (Off/Once/Continuous)."""
        if self.rgb_camera and hasattr(self.rgb_camera, 'set_exposure_mode'):
            if self.rgb_camera.set_exposure_mode(mode):
                logger.info(f"Firefly exposure mode set to: {mode}")

    def set_firefly_exposure_time(self, time_us: float):
        """Set Firefly exposure time in microseconds."""
        if self.rgb_camera and hasattr(self.rgb_camera, 'set_exposure_time'):
            if self.rgb_camera.set_exposure_time(time_us):
                # logger.info(f"Firefly exposure time set to: {time_us}us")
                pass

    def set_firefly_gain_mode(self, mode: str):
        """Set Firefly gain mode (Off/Once/Continuous)."""
        if self.rgb_camera and hasattr(self.rgb_camera, 'set_gain_mode'):
            if self.rgb_camera.set_gain_mode(mode):
                logger.info(f"Firefly gain mode set to: {mode}")

    def set_firefly_gain(self, gain_db: float):
        """Set Firefly gain in dB."""
        if self.rgb_camera and hasattr(self.rgb_camera, 'set_gain'):
            if self.rgb_camera.set_gain(gain_db):
                # logger.info(f"Firefly gain set to: {gain_db}dB")
                pass

    def set_firefly_wb_mode(self, mode: str):
        """Set Firefly white balance mode (Off/Once/Continuous)."""
        if self.rgb_camera and hasattr(self.rgb_camera, 'set_white_balance_mode'):
            if self.rgb_camera.set_white_balance_mode(mode):
                logger.info(f"Firefly WB mode set to: {mode}")

    def set_firefly_wb_ratio(self, channel: str, value: float):
        """Set Firefly white balance ratio (Red/Blue)."""
        if self.rgb_camera and hasattr(self.rgb_camera, 'set_white_balance_ratio'):
            if self.rgb_camera.set_white_balance_ratio(channel, value):
                # logger.info(f"Firefly WB {channel} ratio set to: {value}")
                pass

    def set_firefly_trigger_mode(self, enabled: bool, source: str = 'Software'):
        """Set Firefly trigger mode."""
        if self.rgb_camera and hasattr(self.rgb_camera, 'set_trigger_mode'):
            if self.rgb_camera.set_trigger_mode(enabled, source):
                logger.info(f"Firefly trigger mode: {'ON' if enabled else 'OFF'} ({source})")

    def fire_software_trigger(self):
        """Fire software trigger."""
        if self.rgb_camera and hasattr(self.rgb_camera, 'execute_software_trigger'):
            self.rgb_camera.execute_software_trigger()
            logger.info("Software trigger fired")

    def set_firefly_gamma(self, gamma: float):
        if self.rgb_camera and hasattr(self.rgb_camera, 'set_gamma'):
            self.rgb_camera.set_gamma(gamma)
            logger.info(f"Firefly gamma set to: {gamma}")

    def set_firefly_sharpness(self, enabled: bool, value: int = 1000):
        """Set Firefly sharpness."""
        if self.rgb_camera and hasattr(self.rgb_camera, 'set_sharpness'):
            if self.rgb_camera.set_sharpness(enabled, value):
                # logger.info(f"Firefly sharpness: {'ON' if enabled else 'OFF'} (value={value})")
                pass

    # ========================================================================
    # Radiometric Panel Handlers
    # ========================================================================

    def _on_spotmeter_enabled(self, enabled: bool):
        """Handle hardware spotmeter enable/disable."""
        if self.thermal_camera and hasattr(self.thermal_camera, 'spotmeter_enable'):
            if self.thermal_camera.spotmeter_enable(enabled):
                self.use_hw_spotmeter = enabled
                logger.info(f"Hardware spotmeter: {'ON' if enabled else 'OFF'}")
            else:
                logger.warning("Failed to enable hardware spotmeter - using software")
                self.use_hw_spotmeter = False
        else:
            logger.debug("Hardware spotmeter not available on this camera")
            self.use_hw_spotmeter = False

    def _on_spotmeter_mode_changed(self, mode: str):
        """Handle spotmeter statistics mode change."""
        if self.thermal_camera and hasattr(self.thermal_camera, 'spotmeter_set_statistics_mode'):
            if self.thermal_camera.spotmeter_set_statistics_mode(mode):
                logger.info(f"Spotmeter mode: {mode}")
            else:
                logger.warning(f"Failed to set spotmeter mode to {mode}")
        else:
            logger.debug("Spotmeter mode control not available on this camera")

    def _update_sensor_temperatures(self):
        """Read and update all sensor temperatures."""
        if not self.thermal_camera:
            return
            
        try:
            # Initialize temperatures
            fpa_temp = 0.0
            lens_temp = 0.0
            shutter_temp = 0.0
            board_temp = 0.0
            
            # Helper to extract temperature from result (handles float or tuple)
            def extract_temp(result):
                if result is None:
                    return 0.0
                if isinstance(result, (int, float)):
                    return float(result)
                if isinstance(result, (list, tuple)) and len(result) > 1:
                    return float(result[1])
                return 0.0
            
            # FPA temperature
            if hasattr(self.thermal_camera, 'get_fpa_temperature'):
                result = self.thermal_camera.get_fpa_temperature()
                fpa_temp = extract_temp(result)
            
            # Lens temperature
            if hasattr(self.thermal_camera, 'get_lens_temperature'):
                result = self.thermal_camera.get_lens_temperature()
                lens_temp = extract_temp(result)
            
            # Shutter temperature
            if hasattr(self.thermal_camera, 'get_shutter_temperature'):
                result = self.thermal_camera.get_shutter_temperature()
                shutter_temp = extract_temp(result)
            
            # Board temperature
            if hasattr(self.thermal_camera, 'get_board_temperature'):
                result = self.thermal_camera.get_board_temperature()
                board_temp = extract_temp(result)
            
            # Update GUI
            if self.gui and hasattr(self.gui, 'radiometric_panel'):
                self.gui.radiometric_panel.update_sensor_temperatures(
                    fpa_temp, lens_temp, shutter_temp, board_temp
                )
                
        except Exception as e:
            logger.debug(f"Failed to read sensor temperatures: {e}")

    def read_sensor_temperatures(self):
        """Public method to read and update sensor temperatures (called from GUI)."""
        self._update_sensor_temperatures()

    def set_boson_color_lut(self, lut_name: str):
        """Set Boson color LUT (palette)."""
        if self.thermal_camera and self.thermal_camera.is_sdk_connected:
            # Map string to enum value
            lut_map = {
                'white_hot': 0,
                'black_hot': 1,
                'rainbow': 2,
                'rainbow_hc': 3,
                'ironbow': 4,
                'lava': 5,
                'arctic': 6,
                'globow': 7,
                'graded_fire': 8,
                'gradedfire': 8,
                'hottest': 9
            }
            if lut_name.lower() in lut_map:
                if self.thermal_camera.set_color_lut(lut_map[lut_name.lower()]):
                    logger.info(f"Color LUT set to {lut_name}")
                    return True
                else:
                    logger.error(f"Failed to set color LUT to {lut_name}")
                    return False
        return False

    # ========================================================================
    # AGC (Automatic Gain Control) Methods - Universal (ALL Boson cameras)
    # ========================================================================

    def set_agc_max_gain(self, gain: float) -> bool:
        """Set AGC maximum gain (contrast limit)."""
        if self.thermal_camera and self.thermal_camera.is_sdk_connected:
            if hasattr(self.thermal_camera, 'set_agc_max_gain'):
                return self.thermal_camera.set_agc_max_gain(gain)
        return False

    def set_agc_gamma(self, gamma: float) -> bool:
        """Set AGC gamma correction (ACE - Automatic Contrast Enhancement)."""
        if self.thermal_camera and self.thermal_camera.is_sdk_connected:
            if hasattr(self.thermal_camera, 'set_agc_gamma'):
                return self.thermal_camera.set_agc_gamma(gamma)
        return False

    def set_agc_linearity(self, percent: float) -> bool:
        """Set AGC linearity (histogram vs. linear mapping)."""
        if self.thermal_camera and self.thermal_camera.is_sdk_connected:
            if hasattr(self.thermal_camera, 'set_agc_linearity'):
                return self.thermal_camera.set_agc_linearity(percent)
        return False

    def set_agc_dde(self, dde: float) -> bool:
        """Set AGC DDE (Digital Detail Enhancement)."""
        if self.thermal_camera and self.thermal_camera.is_sdk_connected:
            if hasattr(self.thermal_camera, 'set_detail_enhancement'):
                return self.thermal_camera.set_detail_enhancement(dde)
        return False

    def reset_agc_settings(self) -> bool:
        """Reset AGC settings to defaults."""
        if self.thermal_camera and self.thermal_camera.is_sdk_connected:
            # Reset to defaults: max_gain=2.0, gamma=1.0, linearity=50%, dde=1.3, plateau=0.5, dampening=0.5
            success = True
            success &= self.set_agc_max_gain(2.0)
            success &= self.set_agc_gamma(1.0)
            success &= self.set_agc_linearity(50.0)
            success &= self.set_agc_dde(1.3)
            success &= self.set_agc_plateau(0.5)
            success &= self.set_agc_dampening(0.5)
            if success:
                logger.info("AGC settings reset to defaults")
            return success
        return False

    def set_agc_plateau(self, value: float) -> bool:
        """
        Set AGC plateau (histogram equalization).

        Args:
            value: Plateau value 0.0-1.0

        Returns:
            True if successful
        """
        if self.thermal_camera and self.thermal_camera.is_sdk_connected:
            if hasattr(self.thermal_camera.sdk, 'set_agc_plateau'):
                return self.thermal_camera.sdk.set_agc_plateau(value)
        return False

    def set_agc_dampening(self, value: float) -> bool:
        """
        Set AGC dampening (temporal smoothing).

        Args:
            value: Dampening value 0.0-1.0

        Returns:
            True if successful
        """
        if self.thermal_camera and self.thermal_camera.is_sdk_connected:
            if hasattr(self.thermal_camera.sdk, 'set_agc_dampening'):
                return self.thermal_camera.sdk.set_agc_dampening(value)
        return False

    def set_shutter_position(self, position: str) -> bool:
        """
        Set shutter position.

        Args:
            position: "AUTO", "OPEN", or "CLOSED"

        Returns:
            True if successful
        """
        if self.thermal_camera and self.thermal_camera.is_sdk_connected:
            if hasattr(self.thermal_camera.sdk, 'set_shutter_position'):
                return self.thermal_camera.sdk.set_shutter_position(position)
        return False

    def _restart_thermal_camera_for_mode_change(self):
        """
        Restart the thermal camera to apply video format changes.

        On Windows, DirectShow caches the video format. After switching
        T-Linear mode via SDK, we need to close and reopen the camera
        to get the new Y16 format.
        """
        if not self.thermal_camera:
            return

        try:
            # Get current device ID
            device_id = getattr(self.thermal_camera, 'device_id', 1)
            sdk = getattr(self.thermal_camera, 'sdk', None)
            sdk_connected = self.thermal_camera.is_sdk_connected if hasattr(self.thermal_camera, 'is_sdk_connected') else False

            logger.info(f"Restarting thermal camera (device {device_id}) for format change...")

            # Stop threaded capture if running
            if hasattr(self, 'threaded_capture') and self.threaded_capture:
                self.threaded_capture.stop()
                import time
                time.sleep(0.5)  # Give camera time to release

            # Close current camera
            if hasattr(self.thermal_camera, 'close'):
                self.thermal_camera.close()
            elif hasattr(self.thermal_camera, 'release'):
                self.thermal_camera.release()

            import time
            time.sleep(1.0)  # Wait for Windows to release the device

            # Reopen camera with same device ID
            from flir_camera import FLIRBosonCamera
            self.thermal_camera = FLIRBosonCamera(device_id)

            # Reconnect SDK if it was connected
            if sdk_connected and sdk:
                self.thermal_camera.sdk = sdk
                self.thermal_camera.sdk_connected = True
                logger.info("SDK connection preserved")

            # Re-detect radiometric mode
            is_radiometric = self._detect_radiometric_mode()
            logger.info(f"Camera restarted. Radiometric mode detected: {is_radiometric}")

            # Restart threaded capture
            if hasattr(self, 'threaded_capture') and self.threaded_capture:
                from threaded_camera_capture import ThreadedCameraCapture
                self.threaded_capture = ThreadedCameraCapture(
                    thermal_camera=self.thermal_camera,
                    rgb_camera=getattr(self, 'rgb_camera', None)
                )
                self.threaded_capture.start()
                logger.info("Threaded capture restarted")

        except Exception as e:
            logger.error(f"Error restarting thermal camera: {e}", exc_info=True)

    def set_radiometric_mode(self, enable_radiometric: bool) -> bool:
        """
        Switch between T-Linear radiometric mode (16-bit) and UVC colorized mode (8-bit).

        Args:
            enable_radiometric: True for T-Linear mode, False for UVC mode

        Returns:
            True if successful, False otherwise

        Note:
            - T-Linear mode: 16-bit absolute temperature data for precise measurements
            - UVC mode: 8-bit AGC-processed colorized output for visual display
            - In radiometric mode, colorization is still applied via palette manager
        """
        if not self.thermal_camera:
            logger.error("No thermal camera available")
            return False

        if not self.thermal_camera.is_sdk_connected:
            logger.error("SDK not connected - cannot change camera mode")
            return False

        try:
            if enable_radiometric:
                # Enable T-Linear mode via SDK
                logger.info("Enabling T-Linear radiometric mode...")
                success = self.thermal_camera.enable_tlinear_mode()

                if success:
                    logger.info("[OK] T-Linear mode enabled via SDK")
                    logger.info("  -> Camera will output 16-bit absolute temperature data")
                    logger.info("  -> Restarting camera capture to apply format change...")

                    # Enable radiometric processing in the camera object
                    if hasattr(self.thermal_camera, 'enable_radiometric'):
                        self.thermal_camera.enable_radiometric(True)

                    # CRITICAL: Restart camera to get Y16 format
                    # Windows DirectShow needs camera reopened to switch formats
                    self._restart_thermal_camera_for_mode_change()

                    # Update thermal analyzer to radiometric mode
                    if self.thermal_analyzer:
                        self.thermal_analyzer.set_radiometric_mode(True)
                        logger.info("ThermalAnalyzer set to radiometric mode")

                    return True
                else:
                    logger.error("[ERROR] Failed to enable T-Linear mode")
                    return False
            else:
                # Disable T-Linear mode (revert to standard UVC)
                logger.info("Switching to UVC post-colorized mode...")

                # Disable radiometric processing
                if hasattr(self.thermal_camera, 'enable_radiometric'):
                    self.thermal_camera.enable_radiometric(False)

                # Disable T-Linear via SDK
                if hasattr(self.thermal_camera, 'disable_tlinear_mode'):
                    self.thermal_camera.disable_tlinear_mode()

                # Restart camera to apply format change
                logger.info("Restarting camera capture...")
                self._restart_thermal_camera_for_mode_change()

                # Update thermal analyzer to non-radiometric mode
                if self.thermal_analyzer:
                    self.thermal_analyzer.set_radiometric_mode(False)
                    logger.info("ThermalAnalyzer set to non-radiometric mode")

                logger.info("[OK] Switched to AGC mode")
                return True

        except Exception as e:
            logger.error(f"Error changing radiometric mode: {e}")
            return False

    def swap_cameras(self) -> bool:
        """
        Swap RGB and Thermal camera sources.
        Useful if UVC cameras are assigned incorrectly.
        """
        logger.info("Swapping camera sources...")
        
        # Get current IDs
        current_thermal = getattr(self.args, 'thermal_device', 0)
        current_rgb = getattr(self.args, 'rgb_device', None)
        
        if current_rgb is None:
            # If RGB was auto-detected, we need to guess.
            # Usually if thermal is 0, RGB is 1.
            current_rgb = 1 if current_thermal == 0 else 0
            
        # Swap
        new_thermal = current_rgb
        new_rgb = current_thermal
        
        # Run in separate thread to avoid blocking GUI
        threading.Thread(target=self.reassign_cameras, args=(new_thermal, new_rgb), daemon=True).start()
        return True

    def reassign_cameras(self, thermal_id: int, rgb_id: int) -> bool:
        """
        Reassign camera device IDs.
        
        Args:
            thermal_id: New thermal camera device ID
            rgb_id: New RGB camera device ID
            
        Returns:
            True if successful
        """
        if self.reconfiguring:
            logger.warning("Already reconfiguring cameras...")
            return False

        self.reconfiguring = True
        logger.info(f"Reassigning cameras: Thermal={thermal_id}, RGB={rgb_id}")
        
        try:
            # 1. Stop capture
            if self.threaded_capture:
                logger.info("Stopping capture threads...")
                self.threaded_capture.stop()
                self.threaded_capture = None
            
            # 2. Update args FIRST (before releasing cameras)
            logger.info(f"Updating device IDs: Thermal={thermal_id}, RGB={rgb_id}")
            self.args.thermal_device = thermal_id
            self.args.rgb_device = rgb_id
                
            # 3. Release current cameras
            if self.thermal_camera:
                logger.info("Releasing thermal camera...")
                self.thermal_camera.release()
                self.thermal_camera = None
                self.thermal_connected = False
                self.is_flir_boson = False
                
            if self.rgb_camera:
                logger.info("Releasing RGB camera...")
                self.rgb_camera.release()
                self.rgb_camera = None
                self.rgb_available = False
                
            # Force OpenCV to release resources
            cv2.waitKey(1)
            cv2.destroyAllWindows()
            cv2.waitKey(1)
            
            # Wait for OS to release resources (increased to 2s for stability)
            logger.info("Waiting for OS to release camera resources...")
            time.sleep(2.0)
            
            # 4. Re-connect with NEW device IDs
            logger.info(f"Reconnecting thermal camera on device {thermal_id}...")
            self.thermal_connected = self._try_connect_thermal()
            
            logger.info(f"Reconnecting RGB camera on device {rgb_id}...")
            self.rgb_available = self._try_connect_rgb()
            
            # 5. Restart threaded capture
            if self.thermal_connected or self.rgb_available:
                logger.info("Restarting capture threads...")
                from threaded_camera_capture import DualThreadedCameraCapture
                self.threaded_capture = DualThreadedCameraCapture(self.thermal_camera, self.rgb_camera)
                self.threaded_capture.start()
                logger.info("[OK] Camera reassignment complete")
            else:
                logger.error("[ERROR] No cameras connected after reassignment")
                
        except Exception as e:
            logger.error(f"Error reassigning cameras: {e}")
            import traceback
            traceback.print_exc()
            
        finally:
            self.reconfiguring = False
            
        return True

    def disconnect_boson_sdk(self):
        """Disconnect from Boson SDK."""
        if not self.thermal_camera:
            return

        if not self.thermal_camera.is_sdk_connected:
            logger.info("SDK not connected")
            return

        try:
            logger.info("Disconnecting Boson SDK...")
            self.thermal_camera.disconnect_sdk()
            logger.info("[OK] Boson SDK disconnected")

            # Update GUI status if available
            if self.gui and hasattr(self.gui, 'boson_panel'):
                self.gui.boson_panel.update_connection_status(False)

        except Exception as e:
            logger.error(f"[ERROR] SDK disconnection error: {e}")

    def scan_boson_com_ports(self) -> list:
        """
        Scan for available COM ports that might be Boson cameras.

        Returns:
            List of COM port names
        """
        try:
            from boson_serial import BosonSerialInterface
            ports = BosonSerialInterface.find_boson_com_ports()
            logger.info(f"Found {len(ports)} potential Boson COM ports")
            return ports
        except ImportError:
            logger.warning("boson_serial module not available")
            return []
        except Exception as e:
            logger.error(f"Error scanning COM ports: {e}")
            return []

    def update_boson_gui(self):
        """Update Boson SDK panel GUI state."""
        if not self.gui or not hasattr(self.gui, 'boson_panel'):
            return
            
        try:
            is_connected = (self.thermal_camera and 
                          self.thermal_camera.is_sdk_connected)
            
            # Update connection status
            self.gui.boson_panel.update_connection_status(is_connected)
            
            # Update camera info if connected
            if is_connected and hasattr(self.thermal_camera, 'get_camera_info'):
                info = self.thermal_camera.get_camera_info()
                if info:
                    self.gui.boson_panel.set_status(f"SN: {info.serial_number}")
            
            # Update FPA temperature if connected
            if is_connected and hasattr(self.thermal_camera, 'get_fpa_temperature'):
                temp = self.thermal_camera.get_fpa_temperature()
                if temp:
                    self.gui.boson_panel.update_fpa_temperature(temp[0], temp[1])
                    
        except Exception as e:
            logger.debug(f"Error updating Boson GUI: {e}")

    def update_firefly_gui(self):
        """Update Firefly camera panel GUI state."""
        if not self.gui or not hasattr(self.gui, 'firefly_panel'):
            return

        try:
            is_connected = (self.rgb_camera and
                          self.rgb_available and
                          hasattr(self.rgb_camera, 'is_open') and
                          self.rgb_camera.is_open)

            if is_connected:
                # Get camera info for display
                info = {}
                if hasattr(self.rgb_camera, 'get_camera_info'):
                    camera_info = self.rgb_camera.get_camera_info()
                    if camera_info:
                        info = camera_info
                else:
                    # Build info dict from camera properties
                    info['model'] = getattr(self.rgb_camera, 'camera_model', 'Firefly')
                    info['serial'] = getattr(self.rgb_camera, 'serial_number', 'Unknown')
                    info['width'] = getattr(self.rgb_camera, 'width', 0)
                    info['height'] = getattr(self.rgb_camera, 'height', 0)
                    info['fps'] = getattr(self.rgb_camera, 'fps', 0)
                    info['pixel_format'] = getattr(self.rgb_camera, 'pixel_format', 'BGR8')

                self.gui.firefly_panel.set_camera_connected(True, info)
            else:
                self.gui.firefly_panel.set_camera_connected(False)

        except Exception as e:
            logger.debug(f"Error updating Firefly GUI: {e}")

    def cleanup(self):
        """Clean up resources."""
        logger.info("Cleaning up...")
        self.running = False

        # Stop threaded capture first
        if self.threaded_capture:
            self.threaded_capture.stop()

        # Stop recording if active (NEW - Phase 6)
        if self.video_recorder and self.video_recorder.is_recording():
            self.video_recorder.stop_recording()
            logger.info("Recording stopped (cleanup)")

        # Release video recorder
        if self.video_recorder:
            self.video_recorder.cleanup()

        # Release video player
        if self.video_player:
            self.video_player.cleanup()

        # Shutdown thread pool executors (Phase 1 optimization)
        if hasattr(self, 'detection_executor') and self.detection_executor:
            logger.info("Shutting down detection executor...")
            self.detection_executor.shutdown(wait=True, cancel_futures=True)
            logger.info("Detection executor shutdown complete")

        if hasattr(self, 'roi_executor') and self.roi_executor:
            logger.info("Shutting down ROI executor...")
            self.roi_executor.shutdown(wait=True, cancel_futures=True)
            logger.info("ROI executor shutdown complete")

        if self.thermal_camera:
            self.thermal_camera.release()
        if self.rgb_camera:
            self.rgb_camera.release()
        if self.thermal_processor:
            self.thermal_processor.release()

        cv2.destroyAllWindows()
        logger.info("Cleanup complete")
    
    # ==========================================================================
    # Firefly Camera Control Methods
    # ==========================================================================
    
    def set_firefly_exposure_mode(self, mode: str) -> bool:
        """Set Firefly camera exposure mode."""
        from rgb_camera_firefly import RGBCameraFirefly
        if isinstance(self.rgb_camera, RGBCameraFirefly):
            return self.rgb_camera.set_exposure_mode(mode)
        logger.warning("RGB camera is not a Firefly camera")
        return False
    
    def set_firefly_exposure_time(self, time_us: float) -> bool:
        """Set Firefly camera exposure time in microseconds."""
        from rgb_camera_firefly import RGBCameraFirefly
        if isinstance(self.rgb_camera, RGBCameraFirefly):
            return self.rgb_camera.set_exposure_time(time_us)
        return False
    
    def set_firefly_gain_mode(self, mode: str) -> bool:
        """Set Firefly camera gain mode."""
        from rgb_camera_firefly import RGBCameraFirefly
        if isinstance(self.rgb_camera, RGBCameraFirefly):
            return self.rgb_camera.set_gain_mode(mode)
        logger.warning("RGB camera is not a Firefly camera")
        return False
    
    def set_firefly_gain(self, gain_db: float) -> bool:
        """Set Firefly camera gain in dB."""
        from rgb_camera_firefly import RGBCameraFirefly
        if isinstance(self.rgb_camera, RGBCameraFirefly):
            return self.rgb_camera.set_gain(gain_db)
        return False
    
    def set_firefly_white_balance_mode(self, mode: str) -> bool:
        """Set Firefly camera white balance mode."""
        from rgb_camera_firefly import RGBCameraFirefly
        if isinstance(self.rgb_camera, RGBCameraFirefly):
            return self.rgb_camera.set_white_balance_mode(mode)
        logger.warning("RGB camera is not a Firefly camera")
        return False
    
    def calibrate_firefly_white_balance(self) -> bool:
        """Calibrate Firefly camera white balance (one-shot)."""
        from rgb_camera_firefly import RGBCameraFirefly
        if isinstance(self.rgb_camera, RGBCameraFirefly):
            return self.rgb_camera.calibrate_white_balance()
        logger.warning("RGB camera is not a Firefly camera")
        return False
    
    def set_firefly_white_balance_ratio(self, color: str, ratio: float) -> bool:
        """Set Firefly camera white balance ratio for red or blue channel."""
        from rgb_camera_firefly import RGBCameraFirefly
        if isinstance(self.rgb_camera, RGBCameraFirefly):
            return self.rgb_camera.set_white_balance_ratio(color, ratio)
        return False
    
    def set_firefly_trigger_mode(self, enabled: bool, source: str = 'Software') -> bool:
        """Set Firefly camera trigger mode."""
        from rgb_camera_firefly import RGBCameraFirefly
        if isinstance(self.rgb_camera, RGBCameraFirefly):
            return self.rgb_camera.set_trigger_mode(enabled, source)
        logger.warning("RGB camera is not a Firefly camera")
        return False
    
    def fire_firefly_software_trigger(self) -> bool:
        """Fire Firefly camera software trigger."""
        from rgb_camera_firefly import RGBCameraFirefly
        if isinstance(self.rgb_camera, RGBCameraFirefly):
            return self.rgb_camera.execute_software_trigger()
        logger.warning("RGB camera is not a Firefly camera")
        return False
    
    def set_firefly_gamma(self, gamma: float) -> bool:
        """Set Firefly camera gamma correction."""
        from rgb_camera_firefly import RGBCameraFirefly
        if isinstance(self.rgb_camera, RGBCameraFirefly):
            return self.rgb_camera.set_gamma(gamma)
        return False
    
    def set_firefly_sharpness(self, enabled: bool, value: float = 1.0) -> bool:
        """Set Firefly camera sharpness."""
        from rgb_camera_firefly import RGBCameraFirefly
        if isinstance(self.rgb_camera, RGBCameraFirefly):
            return self.rgb_camera.set_sharpness(enabled, value)
        return False

    # ========================================================================
    # Radiometric Control (Phase 9)
    # ========================================================================

    def enable_radiometric(self, enable: bool) -> bool:
        """
        Enable/disable radiometric temperature conversion.

        Args:
            enable: True to enable, False to disable

        Returns:
            True if successful
        """
        if not self.thermal_camera:
            logger.warning("No thermal camera available for radiometric control")
            return False

        try:
            self.thermal_camera.enable_radiometric(enable)

            # Update GUI status
            if self.gui and hasattr(self.gui, 'radiometric_panel'):
                capable = self.thermal_camera.is_radiometric_capable()
                enabled = self.thermal_camera.is_radiometric_enabled()
                mode = "16-bit Radiometric" if capable else "8-bit UVC"
                self.gui.radiometric_panel.set_radiometric_status(capable, enabled, mode)

                # Update panel availability (isotherm, environmental)
                if hasattr(self.gui, 'update_radiometric_panel_availability'):
                    self.gui.update_radiometric_panel_availability(enabled)

                # Clear readings if disabled
                if not enabled:
                    self.gui.radiometric_panel.clear_temperature_readings()

            return True
        except Exception as e:
            logger.error(f"Error enabling radiometric: {e}")
            return False

    def set_radiometric_temperature_range(self, min_celsius: float, max_celsius: float) -> bool:
        """
        Set expected temperature range for radiometric conversion.

        Args:
            min_celsius: Minimum expected temperature
            max_celsius: Maximum expected temperature

        Returns:
            True if successful
        """
        if not self.thermal_camera:
            logger.warning("No thermal camera available")
            return False

        try:
            return self.thermal_camera.set_temperature_range(min_celsius, max_celsius)
        except Exception as e:
            logger.error(f"Error setting temperature range: {e}")
            return False

    def update_radiometric_gui(self):
        """Update radiometric GUI panel with current status and temperature readings."""
        if not self.gui or not hasattr(self.gui, 'radiometric_panel'):
            return

        if not self.thermal_camera:
            return

        try:
            # Update status
            capable = self.thermal_camera.is_radiometric_capable()
            enabled = self.thermal_camera.is_radiometric_enabled()
            mode = "16-bit Radiometric" if capable else "8-bit UVC"
            self.gui.radiometric_panel.set_radiometric_status(capable, enabled, mode)

            # Update panel availability (isotherm, environmental)
            if hasattr(self.gui, 'update_radiometric_panel_availability'):
                self.gui.update_radiometric_panel_availability(enabled)

            # Update temperature readings if enabled
            if enabled and capable:
                # Get frame statistics
                stats = self.thermal_camera.get_frame_temperature_stats()
                if stats:
                    self.gui.radiometric_panel.set_frame_statistics(
                        stats['min_temp'],
                        stats['max_temp'],
                        stats['mean_temp']
                    )

                # Get center temperature
                if hasattr(self.thermal_camera, 'last_frame_16bit') and self.thermal_camera.last_frame_16bit is not None:
                    h, w = self.thermal_camera.last_frame_16bit.shape
                    center_temp = self.thermal_camera.get_spot_temperature(w // 2, h // 2)
                    if center_temp is not None:
                        self.gui.radiometric_panel.set_center_temperature(center_temp)

                # Update measurement points
                if self.measurement_points:
                    temp_frame = self._get_temperature_frame()
                    if temp_frame is not None:
                        # Get unit symbol from thermal_analyzer (same as hot/cold spots)
                        unit_symbol = "°C"  # Default
                        if self.thermal_analyzer:
                            unit_symbol = self.thermal_analyzer._get_unit_symbol()

                        self.measurement_points.update_temperatures(temp_frame, unit_symbol)
                        points = self.measurement_points.get_all_points()
                        self.gui.radiometric_panel.update_measurement_points(points)

        except Exception as e:
            logger.debug(f"Error updating radiometric GUI: {e}")

    def load_radiometric_lut(self, filepath: str) -> bool:
        """
        Load TLinear lookup table from CSV file.

        Args:
            filepath: Path to LUT CSV file

        Returns:
            True if loaded successfully
        """
        if not self.thermal_camera:
            logger.warning("No thermal camera available for LUT loading")
            return False

        if not hasattr(self.thermal_camera, 'radiometric_converter'):
            logger.warning("Thermal camera does not have radiometric converter")
            return False

        try:
            converter = self.thermal_camera.radiometric_converter
            if not converter:
                logger.error("Radiometric converter not initialized")
                return False

            # Load LUT file
            success = converter.load_lut_from_file(filepath)

            if success and self.gui and hasattr(self.gui, 'radiometric_panel'):
                # Update GUI with LUT status
                info = converter.get_info()
                if info['lut_loaded']:
                    lut_keys = sorted(converter.lut.keys())
                    lut_vals = [converter.lut[k] for k in lut_keys]
                    pixel_range = (min(lut_keys), max(lut_keys))
                    temp_range = (min(lut_vals), max(lut_vals))

                    self.gui.radiometric_panel.set_lut_status(
                        loaded=True,
                        entry_count=info['lut_size'],
                        pixel_range=pixel_range,
                        temp_range=temp_range
                    )

            return success

        except Exception as e:
            logger.error(f"Error loading radiometric LUT: {e}")
            return False

    def set_radiometric_method(self, method: str) -> bool:
        """
        Set radiometric conversion method (linear or lut).

        Args:
            method: "linear" or "lut"

        Returns:
            True if successful
        """
        if not self.thermal_camera:
            logger.warning("No thermal camera available")
            return False

        if not hasattr(self.thermal_camera, 'radiometric_converter'):
            logger.warning("Thermal camera does not have radiometric converter")
            return False

        try:
            converter = self.thermal_camera.radiometric_converter
            if not converter:
                logger.error("Radiometric converter not initialized")
                return False

            converter.method = method
            logger.info(f"Radiometric conversion method set to: {method}")
            return True

        except Exception as e:
            logger.error(f"Error setting radiometric method: {e}")
            return False

        # Radiometric state
        self.use_hw_spotmeter = False  # Track if hardware spotmeter is enabled

    # ========================================================================
    # Parallax Compensation Control (Phase 11)
    # ========================================================================

    def enable_parallax_compensation(self, enable: bool) -> bool:
        """
        Enable or disable parallax compensation.

        Args:
            enable: True to enable, False to disable

        Returns:
            True if successful
        """
        if not self.parallax_compensator:
            logger.warning("Parallax compensator not available")
            return False

        try:
            self.parallax_compensator.enable(enable)
            logger.info(f"Parallax compensation: {'ENABLED' if enable else 'DISABLED'}")
            return True
        except Exception as e:
            logger.error(f"Error toggling parallax compensation: {e}")
            return False

    def set_parallax_baseline(self, baseline_mm: float) -> bool:
        """
        Set camera baseline distance for parallax compensation.

        Args:
            baseline_mm: Distance between camera centers in millimeters

        Returns:
            True if successful
        """
        if not self.parallax_compensator:
            logger.warning("Parallax compensator not available")
            return False

        try:
            self.parallax_compensator.set_baseline(baseline_mm)
            logger.info(f"Parallax baseline set to {baseline_mm}mm")
            return True
        except Exception as e:
            logger.error(f"Error setting parallax baseline: {e}")
            return False

    def set_parallax_depth_method(self, method: str) -> bool:
        """
        Set depth estimation method for parallax compensation.

        Args:
            method: "simplified", "midas", or "depthanything"

        Returns:
            True if successful
        """
        if not self.parallax_compensator:
            logger.warning("Parallax compensator not available")
            return False

        try:
            # Create new depth estimator with selected method
            from parallax_compensator import DepthEstimator
            self.parallax_compensator.depth_estimator = DepthEstimator(method=method)
            logger.info(f"Parallax depth method set to: {method}")

            # Update GUI status if available
            if self.gui and hasattr(self.gui, 'parallax_panel'):
                if method in ["midas", "depthanything"]:
                    self.gui.parallax_panel.set_method_status(
                        f"{method} model loading...", is_error=False
                    )
                else:
                    self.gui.parallax_panel.set_method_status("Ready", is_error=False)

            return True
        except Exception as e:
            logger.error(f"Error setting parallax depth method: {e}")
            if self.gui and hasattr(self.gui, 'parallax_panel'):
                self.gui.parallax_panel.set_method_status(f"Error: {e}", is_error=True)
            return False

    # ========================================================================
    # Temperature Frame Access (Helper)
    # ========================================================================

    def _get_temperature_frame(self) -> Optional[np.ndarray]:
        """
        Get temperature frame in the user's selected units from thermal camera.

        Uses the same conversion logic as hot/cold spots for consistency.

        Returns:
            Temperature frame (H, W) float32 in user-selected units, or None if not available
        """
        if not self.thermal_camera:
            return None

        # Strategy 1: 16-bit radiometric mode (best accuracy)
        if self.thermal_camera.is_radiometric_enabled():
            if not hasattr(self.thermal_camera, 'radiometric_converter'):
                return None

            converter = self.thermal_camera.radiometric_converter
            if not converter:
                return None

            # Get last 16-bit frame
            if not hasattr(self.thermal_camera, 'last_frame_16bit'):
                return None

            frame_16bit = self.thermal_camera.last_frame_16bit
            if frame_16bit is None:
                return None

            try:
                # Convert to Celsius first (same as hot/cold spots)
                if self.thermal_analyzer and self.thermal_analyzer.is_radiometric:
                    # Use thermal_analyzer's Y16 conversion for consistency (vectorized)
                    # Y16 format: value = Kelvin × 100, so temp_c = (value / 100.0) - 273.15
                    temp_frame_c = (frame_16bit.astype(np.float32) / 100.0) - 273.15

                    # Convert to user's selected unit
                    from thermal_analyzer import TemperatureUnit
                    if self.thermal_analyzer.temp_unit == TemperatureUnit.FAHRENHEIT:
                        temp_frame = (temp_frame_c * 9.0/5.0) + 32.0
                    elif self.thermal_analyzer.temp_unit == TemperatureUnit.KELVIN:
                        temp_frame = temp_frame_c + 273.15
                    else:  # CELSIUS
                        temp_frame = temp_frame_c
                else:
                    # Fallback to converter
                    temp_frame = converter.pixel_to_celsius(frame_16bit)

                # Apply calibration if enabled
                if (self.calibration_enabled and
                    RADIOMETRIC_CALIBRATION_AVAILABLE and
                    self.radiometric_calibrator and
                    self.radiometric_calibrator.is_calibrated):
                    temp_frame = self.radiometric_calibrator.apply_calibration_to_frame(temp_frame)

                return temp_frame
            except Exception as e:
                logger.debug(f"Error getting temperature frame: {e}")
                return None

        # Strategy 2: 8-bit estimation mode (if enabled)
        elif self.temp_estimation_enabled and self.temp_estimator:
            if not hasattr(self, 'last_thermal_frame') or self.last_thermal_frame is None:
                return None

            if not self.thermal_camera.is_sdk_connected:
                return None

            fpa = self.thermal_camera.get_fpa_temperature()
            if not fpa:
                return None

            try:
                # Get thermal frame (8-bit)
                thermal_frame = self.last_thermal_frame
                if thermal_frame.ndim == 3:
                    thermal_frame = cv2.cvtColor(thermal_frame, cv2.COLOR_BGR2GRAY)

                # Estimate temperature map (returns Celsius)
                temp_frame_c = self.temp_estimator.estimate_temperature_map(thermal_frame, fpa[1])

                # Convert to user's selected unit (same as hot/cold spots)
                if self.thermal_analyzer:
                    from thermal_analyzer import TemperatureUnit
                    if self.thermal_analyzer.temp_unit == TemperatureUnit.FAHRENHEIT:
                        temp_frame = (temp_frame_c * 9.0/5.0) + 32.0
                    elif self.thermal_analyzer.temp_unit == TemperatureUnit.KELVIN:
                        temp_frame = temp_frame_c + 273.15
                    else:  # CELSIUS
                        temp_frame = temp_frame_c
                else:
                    temp_frame = temp_frame_c

                return temp_frame
            except Exception as e:
                logger.debug(f"Error estimating temperature frame: {e}")
                return None

        # Strategy 3: No radiometric or estimation available
        return None

    # ========================================================================
    # Radiometric Calibration Control
    # ========================================================================

    def set_calibration_add_point_mode(self, enabled: bool, reference_temp: float):
        """
        Enable/disable calibration point adding mode.

        Args:
            enabled: True to enable mode
            reference_temp: Reference temperature for the point
        """
        if not RADIOMETRIC_CALIBRATION_AVAILABLE or not self.radiometric_calibrator:
            logger.warning("Radiometric calibration not available")
            return

        self.calibration_add_point_mode = enabled
        self.calibration_reference_temp = reference_temp

        if self.gui and hasattr(self.gui, 'video_widget'):
            self.gui.video_widget.set_add_point_mode(enabled)

        logger.info(f"Calibration add point mode: {'ENABLED' if enabled else 'DISABLED'}")

    def _on_add_calibration_point(self, x: int, y: int):
        """
        Handle adding a calibration point from video widget click.

        Args:
            x: Frame X coordinate
            y: Frame Y coordinate
        """
        if not RADIOMETRIC_CALIBRATION_AVAILABLE or not self.radiometric_calibrator:
            return

        if not hasattr(self, 'calibration_add_point_mode') or not self.calibration_add_point_mode:
            return

        try:
            # Get measured temperature at this location
            temp_frame = self._get_temperature_frame()
            if temp_frame is None:
                logger.warning("No temperature frame available for calibration")
                return

            h, w = temp_frame.shape
            if not (0 <= x < w and 0 <= y < h):
                logger.warning(f"Calibration point coordinates out of bounds: ({x}, {y})")
                return

            measured_temp = float(temp_frame[y, x])
            reference_temp = self.calibration_reference_temp

            # Add calibration point
            point = self.radiometric_calibrator.add_calibration_point(
                reference_temp, measured_temp, x, y
            )

            logger.info(f"Added calibration point: {reference_temp:.1f}°C (ref) vs {measured_temp:.1f}°C (meas)")

            # Update GUI
            self.update_calibration_gui()

            # Disable add mode
            if self.gui and hasattr(self.gui, 'calibration_panel'):
                self.gui.calibration_panel.disable_add_point_mode()

        except Exception as e:
            logger.error(f"Error adding calibration point: {e}")

    def compute_calibration(self, method: str, degree: int = 2) -> bool:
        """
        Compute radiometric calibration.

        Args:
            method: "linear" or "polynomial"
            degree: Polynomial degree (for polynomial method)

        Returns:
            True if successful
        """
        if not RADIOMETRIC_CALIBRATION_AVAILABLE or not self.radiometric_calibrator:
            return False

        return self.radiometric_calibrator.compute_calibration(method, degree)

    def set_calibration_enabled(self, enabled: bool):
        """
        Enable/disable calibration correction.

        Args:
            enabled: True to enable calibration correction
        """
        if not RADIOMETRIC_CALIBRATION_AVAILABLE or not self.radiometric_calibrator:
            return

        self.calibration_enabled = enabled
        logger.info(f"Calibration correction: {'ENABLED' if enabled else 'DISABLED'}")

    def clear_calibration(self):
        """Clear all calibration points."""
        if not RADIOMETRIC_CALIBRATION_AVAILABLE or not self.radiometric_calibrator:
            return

        self.radiometric_calibrator.clear_calibration_points()
        logger.info("Calibration cleared")

    # ========================================================================
    # 8-Bit Temperature Estimation (Works on ALL Bosons)
    # ========================================================================

    def _init_8bit_estimation(self):
        """
        Initialize 8-bit pseudo-radiometric temperature estimator.
        AUTO-CALLED when SDK connects (works on all Bosons).
        """
        logger.info(f"_init_8bit_estimation() called. THERMAL_ESTIMATION_AVAILABLE={THERMAL_ESTIMATION_AVAILABLE}")

        if not THERMAL_ESTIMATION_AVAILABLE:
            logger.warning("8-bit temperature estimator not available - module import failed")
            return

        try:
            # Initialize estimator with default scene range
            self.temp_estimator = ThermalTemperatureEstimator(
                scene_min_c=10.0,
                scene_max_c=110.0,
                use_adaptive_range=True
            )

            # Do NOT auto-enable - requires user calibration first
            # User must explicitly enable via GUI checkbox after calibrating
            self.temp_estimation_enabled = False
            self.active_temp_mode = "agc"  # Start in AGC mode (raw values)
            self.last_agc_stats = {'min': 0, 'max': 255, 'center': 128}

            # Keep thermal analyzer in non-radiometric mode until 8-bit estimation is enabled
            # (it will be set to radiometric when user enables 8-bit estimation)

            logger.info("=" * 60)
            logger.info("[OK] 8-Bit Temperature Estimation AVAILABLE (not enabled)")
            logger.info("  Requires calibration before use")
            logger.info("  Enable via Analysis > Radiometric > 8-Bit Estimation checkbox")
            logger.info("=" * 60)
            
        except Exception as e:
            logger.error(f"Failed to initialize 8-bit temperature estimator: {e}")

    def _update_temperature_estimation(self, thermal_frame: np.ndarray):
        """
        Update temperature estimation from thermal frame.
        
        Args:
            thermal_frame: 8-bit thermal image (grayscale)
        """
        if not self.temp_estimation_enabled or not self.temp_estimator:
            return

        if not self.thermal_camera or not self.thermal_camera.is_sdk_connected:
            return

        try:
            # Get FPA temperature from SDK
            fpa_temp_result = self.thermal_camera.get_fpa_temperature()
            if not fpa_temp_result:
                return
            
            fpa_temp_c = fpa_temp_result[1]  # Celsius value
            
            # Store AGC statistics for calibration
            h, w = thermal_frame.shape
            center_y, center_x = h // 2, w // 2
            self.last_agc_stats = {
                'min': int(np.min(thermal_frame)),
                'max': int(np.max(thermal_frame)),
                'center': int(thermal_frame[center_y, center_x])
            }
            
            # Get temperature statistics
            stats = self.temp_estimator.get_statistics(thermal_frame, fpa_temp_c)
            
            if stats:
                self.latest_temp_data = stats
                
                # Update GUI if available
                if self.gui and hasattr(self.gui, 'radiometric_panel'):
                    panel = self.gui.radiometric_panel
                    
                    # Update live temperature readings
                    panel.set_frame_statistics(
                        stats['min_temp_c'],
                        stats['max_temp_c'],
                        stats['mean_temp_c']
                    )
                    
                    # Update center temperature
                    center_temp = self.temp_estimator.get_pixel_temperature(
                        thermal_frame, center_x, center_y, fpa_temp_c
                    )
                    if center_temp is not None:
                        panel.set_center_temperature(center_temp)
        
        except Exception as e:
            logger.debug(f"Error updating temperature estimation: {e}")

    def set_temperature_range(self, min_c: float, max_c: float) -> bool:
        """
        Set expected temperature range for 8-bit estimation.
        
        Args:
            min_c: Minimum expected temperature (Celsius)
            max_c: Maximum expected temperature (Celsius)
            
        Returns:
            True if successful
        """
        if not self.temp_estimator:
            return False

        try:
            self.temp_estimator.scene_min_c = min_c
            self.temp_estimator.scene_max_c = max_c
            logger.info(f"Temperature range set: {min_c:.1f}°C to {max_c:.1f}°C")
            return True
        except Exception as e:
            logger.error(f"Error setting temperature range: {e}")
            return False

    def switch_thermal_backend(self, backend_type: str) -> bool:
        """
        Switch thermal camera backend at runtime.

        Args:
            backend_type: 'opencv' for FLIRBosonCamera, 'flirpy' for FlirpyThermalBackend

        Returns:
            True if successful, False otherwise
        """
        logger.info(f"=== Switching thermal backend to: {backend_type} ===")
        
        # 0. Prevent redundant switches (Fix for Bug #16)
        # Note: We check against current internal state or args
        current_backend = getattr(self.args, 'thermal_backend', None)
        if current_backend == backend_type and self.thermal_connected:
            logger.info(f"Backend {backend_type} already active and connected. Ignoring switch request.")
            return True
        
        # Check if already reconfiguring
        if self.reconfiguring:
            logger.warning("Backend switch already in progress...")
            return False
        
        # Set reconfiguring flag to pause main loop
        self.reconfiguring = True
        logger.info("Main loop paused for backend switching")
        
        try:
            # 1. Stop threaded capture if running
            if self.threaded_capture:
                logger.info("Stopping threaded capture...")
                self.threaded_capture.stop()
                self.threaded_capture = None

            # 2. Save COM port and device ID from current camera before releasing
            current_com_port = None
            thermal_device_id = None
            old_resolution = None

            if self.thermal_camera:
                # Capture resolution for coordinate scaling (Fix for spot meter location mismatch)
                if hasattr(self.thermal_camera, 'get_main_image_size'):
                     old_resolution = self.thermal_camera.get_main_image_size()  # (w, h)
                elif hasattr(self.thermal_camera, 'get_resolution'):
                     old_resolution = self.thermal_camera.get_resolution()
                elif hasattr(self.thermal_camera, 'resolution'):
                     old_resolution = self.thermal_camera.resolution
                
                # If still None, try to use args or known default
                if old_resolution is None or old_resolution == (0, 0):
                     old_resolution = (getattr(self.args, 'width', 640), getattr(self.args, 'height', 512))
                
                logger.info(f"Captured old resolution for scaling: {old_resolution}")

                # Save device ID for reuse (avoids camera detection which probes ALL cameras)
                if hasattr(self.thermal_camera, 'device_id'):
                    thermal_device_id = self.thermal_camera.device_id
                elif hasattr(self.thermal_camera, 'device'):
                    thermal_device_id = self.thermal_camera.device
                logger.info(f"Preserving thermal device ID: {thermal_device_id}")
                
                # Only preserve COM port if SDK was successfully connected
                if hasattr(self.thermal_camera, 'com_port'):
                    if hasattr(self.thermal_camera, 'is_sdk_connected') and self.thermal_camera.is_sdk_connected:
                        current_com_port = self.thermal_camera.com_port
                        logger.info(f"Preserving COM port from current camera: {current_com_port}")
                    else:
                        logger.info(f"SDK not connected on current camera, will not preserve COM port")

            # 3. Release current thermal camera
            if self.thermal_camera:
                logger.info(f"Releasing current thermal camera...")
                self.thermal_camera.release()
                self.thermal_camera = None

            # 3.5. Save RGB camera info and release (NO camera detection - it probes all devices!)
            rgb_device_id = None
            rgb_camera_source = 'opencv'  # Default
            if self.rgb_camera:
                # Save device ID for reinitialization later
                if hasattr(self.rgb_camera, 'device_id'):
                    rgb_device_id = self.rgb_camera.device_id
                elif hasattr(self.rgb_camera, 'device'):
                    rgb_device_id = self.rgb_camera.device
                if hasattr(self.rgb_camera, 'camera_source'):
                    rgb_camera_source = self.rgb_camera.camera_source
                logger.info(f"Releasing RGB camera (device {rgb_device_id})...")
                self.rgb_camera.release()
                self.rgb_camera = None

            # 4. Get SDK parameters - prioritize: current camera COM port > args > default
            enable_sdk = getattr(self.args, 'enable_boson_sdk', True)
            com_port = current_com_port or getattr(self.args, 'boson_com_port', None) or 'COM7'
            logger.info(f"Using COM port: {com_port} for new backend")

            # 5. Use saved device ID (stable)
            device_id = getattr(self, 'effective_thermal_device_id', None)
            if device_id is None:
                # Fallback to args or default
                device_id = getattr(self.args, 'thermal_device', 2)
                logger.warning(f"No saved thermal device ID, using args/default: {device_id}")
            else:
                logger.info(f"Using persisted thermal device ID: {device_id}")

            # 6. Create new backend using factory
            self.thermal_camera = create_thermal_backend(
                backend_type=backend_type,
                device_id=device_id,
                resolution=(getattr(self.args, 'width', 640), getattr(self.args, 'height', 512)),
                enable_sdk=enable_sdk,
                com_port=com_port
            )

            # 7. Open the new camera
            if not self.thermal_camera.open():
                logger.error(f"Failed to open {backend_type} backend")
                self.thermal_connected = False
                return False

            # 7. Update connection state
            self.thermal_connected = True
            # Get resolution - use appropriate method for each backend
            if hasattr(self.thermal_camera, 'get_actual_resolution'):
                actual_res = self.thermal_camera.get_actual_resolution()
            else:
                actual_res = self.thermal_camera.get_resolution()
            logger.info(f"[OK] Thermal camera connected: {actual_res[0]}x{actual_res[1]} ({backend_type} backend)")

            # Propagate resolution to GUI overlay for coordinate mapping
            if self.gui and hasattr(self.gui, 'video_widget') and hasattr(self.gui.video_widget, 'overlay'):
                if hasattr(self.gui.video_widget.overlay, 'set_thermal_resolution'):
                    self.gui.video_widget.overlay.set_thermal_resolution(actual_res[0], actual_res[1])

            # 8. Set radiometric mode based on backend type
            # flirpy backend = 16-bit T-Linear radiometric mode
            # opencv backend = 8-bit AGC non-radiometric mode
            is_radiometric = (backend_type == 'flirpy')
            
            if is_radiometric:
                logger.info(f"[OK] Radiometric mode enabled (flirpy 16-bit T-Linear backend)")
                self.args.radiometric = True
                
                # CRITICAL: Enforce T-Linear mode (Mode 2) for flirpy
                # flirpy assumes T-Linear data (Kelvin * 100). If camera is in Raw mode (Mode 0/1),
                # readings will be wrong (e.g. -65C).
                try:
                    from boson_sdk_wrapper import BosonSDK
                    # Use resolved COM port
                    sdk = BosonSDK(com_port=com_port) 
                    if sdk.open():
                        logger.info("Connected to SDK to verify T-Linear mode")
                        current_mode = sdk.get_usb_video_ir16_mode()
                        logger.info(f"Current USB IR16 Mode: {current_mode}")
                        
                        if current_mode != 2:
                            logger.warning(f"Camera is in mode {current_mode}, enforcing T-Linear (Mode 2)...")
                            if sdk.set_usb_video_ir16_mode(2):
                                logger.info("Successfully set T-Linear mode")
                                logger.info("Restarting backend to apply format change...")
                                sdk.close()
                                
                                # Restart backend to get new format
                                if self.thermal_camera:
                                    self.thermal_camera.release()
                                import time
                                time.sleep(1.0) # Wait for device release
                                self.thermal_camera = create_thermal_backend(backend_type)
                                if not self.thermal_camera.open():
                                    logger.error("Failed to reopen camera after mode switch")
                                    return False
                            else:
                                logger.error("Failed to set T-Linear mode")
                        else:
                            logger.info("Camera already in T-Linear mode")
                        
                        if sdk.connected:
                            sdk.close()
                    else:
                        logger.warning("Could not connect to SDK to verify T-Linear mode")
                except Exception as e:
                    logger.error(f"Error enforcing T-Linear mode: {e}")
            else:
                self.args.radiometric = False
                logger.info(f"[OK] Non-radiometric mode (opencv 8-bit AGC backend)")

            # 8.5. Reset thermal analyzer and processor due to resolution change
            if hasattr(self, 'thermal_analyzer') and self.thermal_analyzer:
                logger.info("Resetting thermal analyzer background model...")
                self.thermal_analyzer.reset_background_model()
                # CRITICAL FIX: Update analyzer's radiometric state
                self.thermal_analyzer.set_radiometric_mode(is_radiometric)
                logger.info(f"Updated ThermalAnalyzer radiometric state to: {is_radiometric}")

            if hasattr(self, 'thermal_processor') and self.thermal_processor:
                logger.info("Resetting thermal processor motion detection...")
                self.thermal_processor.reset_motion_detection()

            # 9. Initialize 8-bit estimation if SDK available
            if hasattr(self.thermal_camera, 'is_sdk_connected') and self.thermal_camera.is_sdk_connected:
                self._init_8bit_estimation()

            # 10. Update GUI radiometric panel if available
            if self.gui and hasattr(self.gui, 'radiometric_panel'):
                sdk_connected = self.thermal_camera.is_sdk_connected if hasattr(self.thermal_camera, 'is_sdk_connected') else False
                mode_desc = "16-bit Radiometric" if is_radiometric else "8-bit AGC"
                self.gui.radiometric_panel.set_radiometric_status(
                    capable=is_radiometric,
                    enabled=self.args.radiometric,
                    mode=mode_desc
                )
                logger.info(f"✓ GUI radiometric panel updated for {backend_type} backend")

                # Update panel availability (isotherm, environmental)
                if hasattr(self.gui, 'update_radiometric_panel_availability'):
                    self.gui.update_radiometric_panel_availability(self.args.radiometric)

                # Update active mode status banner
                if hasattr(self.gui.radiometric_panel, 'update_active_mode_status'):
                    mode_info = self.get_active_temperature_mode()
                    self.gui.radiometric_panel.update_active_mode_status(
                        mode_info['mode'],
                        mode_info['accuracy'],
                        mode_info['description']
                    )
                    logger.info(f"✓ Active mode status updated: {mode_info['description']}")
                
                # Update backend status to clear "Switching to..." message
                if hasattr(self.gui.radiometric_panel, 'update_backend_status'):
                    backend_info = {
                        'backend': backend_type,
                        'bit_depth': '16' if is_radiometric else '8',
                        'radiometric': is_radiometric,
                        'resolution': actual_res,
                        'current_mode': backend_type
                    }
                    self.gui.radiometric_panel.update_backend_status(backend_info)
                    logger.info(f"✓ Backend status updated: {backend_type}")

            # 11. Reinitialize RGB camera (was released for detection) and restart threaded capture
            if self.use_threaded_capture:
                # Reinitialize RGB camera using saved device ID (don't probe cameras - that breaks flirpy)
                rgb_id = getattr(self, 'effective_rgb_device_id', 0)
                # Ensure we have a valid ID (not None)
                if rgb_id is None: 
                    rgb_id = getattr(self.args, 'rgb_device', 0)

                rgb_source = getattr(self, 'rgb_camera_source', 'uvc')

                if self.rgb_camera is None and rgb_id is not None:
                    logger.info(f"Reinitializing RGB camera ({rgb_source}) at device {rgb_id}...")
                    try:
                        from camera_factory import create_rgb_camera
                        
                        # Reuse saved device ID - DON'T call detect_all_cameras() as it probes thermal
                        self.rgb_camera = create_rgb_camera(
                            camera_type=rgb_source,  # Use correctly saved source (e.g. firefly)
                            camera_index=rgb_id,
                            resolution=(0, 0),  # Auto-negotiate best resolution
                            use_max_resolution=True
                        )
                        
                        if self.rgb_camera.open():
                            logger.info(f"[OK] RGB camera reinitialized at device {rgb_device_id}")
                        else:
                            logger.warning("Failed to open RGB camera after switch")
                            self.rgb_camera = None
                    except Exception as e:
                        logger.error(f"Error reinitializing RGB camera: {e}")
                        self.rgb_camera = None
                
                from threaded_camera_capture import DualThreadedCameraCapture
                self.threaded_capture = DualThreadedCameraCapture(self.thermal_camera, self.rgb_camera)
                self.threaded_capture.start()
                logger.info("Threaded capture restarted")

            # 12. Update backend type in args
            self.args.thermal_backend = backend_type

            # 13. Rebuild measurement_points from SpotMeterPanel (the persistent source of truth)
            # This fixes "ghost spot meters" bug where spots disappear after backend switch
            if self.gui:
                if hasattr(self.gui, 'analysis_panel') and hasattr(self.gui.analysis_panel, 'spot_meter_panel'):
                    panel = self.gui.analysis_panel.spot_meter_panel
                    panel_spots = panel.get_all_spots()
                    logger.info(f"Backend switch: Found {len(panel_spots)} spots in SpotMeterPanel")
                    
                    # COORDINATE SCALING (Fix for resolution mismatch)
                    scale_x = 1.0
                    scale_y = 1.0
                    new_resolution = (0, 0)
                    
                    # Get new resolution
                    if hasattr(self.thermal_camera, 'get_main_image_size'):
                            new_resolution = self.thermal_camera.get_main_image_size()
                    elif hasattr(self.thermal_camera, 'get_resolution'):
                            new_resolution = self.thermal_camera.get_resolution()
                    elif hasattr(self.thermal_camera, 'resolution'):
                            new_resolution = self.thermal_camera.resolution
                    
                    if new_resolution != (0, 0) and old_resolution is not None and old_resolution != (0, 0):
                        if new_resolution != old_resolution:
                            scale_x = new_resolution[0] / old_resolution[0]
                            scale_y = new_resolution[1] / old_resolution[1]
                            logger.info(f"Scaling coordinates: {old_resolution} -> {new_resolution} (sx={scale_x:.2f}, sy={scale_y:.2f})")
                    
                    if panel_spots:
                        from inspection_gui_qt import MeasurementPoint

                        # Rebuild measurement_points list from panel data
                        self.gui.measurement_points = []
                        for spot_data in panel_spots:
                            # Apply scaling to maintain relative position
                            if scale_x != 1.0 or scale_y != 1.0:
                                # Update underlying data in panel
                                # Use rounding (+0.5) to minimize incremental drift
                                new_x = int(spot_data.x * scale_x + 0.5)
                                new_y = int(spot_data.y * scale_y + 0.5)
                                # Clamp to new resolution
                                new_x = max(0, min(new_x, new_resolution[0]-1))
                                new_y = max(0, min(new_y, new_resolution[1]-1))
                                
                                logger.debug(f"  Scaling spot {spot_data.label}: ({spot_data.x},{spot_data.y}) -> ({new_x},{new_y})")
                                spot_data.x = new_x
                                spot_data.y = new_y
                                
                            point = MeasurementPoint(
                                x=spot_data.x,
                                y=spot_data.y,
                                label=spot_data.label,
                                color=spot_data.color,
                                temperature=spot_data.temperature,
                                unit=spot_data.unit
                            )
                            self.gui.measurement_points.append(point)
                            logger.debug(f"  Rebuilt spot: {spot_data.label} at ({spot_data.x},{spot_data.y}) T={spot_data.temperature}")
                            
                        # Force panel list update to show new coordinates
                        if scale_x != 1.0 or scale_y != 1.0:
                            # Refresh all items to display new coords
                            for spot_id in panel.spots.keys():
                                panel._refresh_list_item(spot_id)

                        # Update the overlay with rebuilt list
                        if hasattr(self.gui, 'video_widget'):
                            # Call update_measurement_points which internally updates the overlay
                            self.gui.video_widget.update_measurement_points(self.gui.measurement_points)
                            
                            # SCALE ROIs
                            if hasattr(self.gui.video_widget, 'overlay') and hasattr(self.gui.video_widget.overlay, 'rois'):
                                overlay = self.gui.video_widget.overlay
                                if overlay.rois and (scale_x != 1.0 or scale_y != 1.0):
                                    logger.info(f"Scaling {len(overlay.rois)} ROIs...")
                                    for roi in overlay.rois:
                                        new_points = []
                                        for x, y in roi.points:
                                            # Use rounding (+0.5)
                                            nx = int(x * scale_x + 0.5)
                                            ny = int(y * scale_y + 0.5)
                                            nx = max(0, min(nx, new_resolution[0]-1))
                                            ny = max(0, min(ny, new_resolution[1]-1))
                                            new_points.append((nx, ny))
                                        roi.points = new_points
                                        roi.last_updated = time.time()
                                    logger.info("ROIs scaled successfully")

                            # CRITICAL FIX: Sync overlay view mode after backend switch
                            # The overlay needs to know the current view mode or it won't render thermal overlays
                            if hasattr(self.gui.video_widget, 'overlay') and self.gui.video_widget.overlay is not None:
                                try:
                                    # Get current view mode from fusion processor
                                    current_mode = getattr(self.args, 'view_mode', 'thermal')
                                    fusion_priority = getattr(self.args, 'fusion_priority', 'thermal')
                                    self.gui.video_widget.overlay.set_view_mode(current_mode, fusion_priority)
                                except Exception as e:
                                    logger.error(f"ERROR syncing overlay view_mode: {e}")
                            
                            # Also force a full repaint of both video widget and overlay
                            self.gui.video_widget.update()  # Repaint VideoWidget
                            if hasattr(self.gui.video_widget, 'overlay'):
                                self.gui.video_widget.overlay.update()  # Repaint overlay

                        logger.info(f"Rebuilt {len(self.gui.measurement_points)} spot meters from SpotMeterPanel")
                    else:
                        logger.info("No spots to rebuild (panel is empty)")

            logger.info(f"=== Successfully switched to {backend_type} backend ===")
            return True

        except Exception as e:
            logger.error(f"Error switching thermal backend: {e}", exc_info=True)
            self.thermal_connected = False
            return False
        
        finally:
            # Always clear reconfiguring flag to resume main loop
            self.reconfiguring = False
            logger.info("Main loop resumed")

    def calibrate_8bit_single_point(self, known_temp_c: float, agc_value: Optional[int] = None) -> bool:
        """
        Perform single-point calibration for 8-bit estimation.
        
        Args:
            known_temp_c: Known temperature at reference point
            agc_value: Optional AGC pixel value (0-255). If None, uses last center pixel.
            
        Returns:
            True if successful
        """
        if not self.temp_estimator or not self.thermal_camera:
            return False

        try:
            # Use last center AGC if not provided
            if agc_value is None:
                agc_value = self.last_agc_stats.get('center', 128)
                logger.info(f"Using center AGC value: {agc_value}")

            fpa_temp_result = self.thermal_camera.get_fpa_temperature()
            if not fpa_temp_result:
                logger.warning("Cannot calibrate: FPA temperature not available")
                return False
            
            fpa_temp_c = fpa_temp_result[1]
            self.temp_estimator.calibrate_single_point(agc_value, known_temp_c, fpa_temp_c)
            logger.info(f"Single-point calibration: {known_temp_c:.1f}°C (AGC: {agc_value})")
            return True
        except Exception as e:
            logger.error(f"Error in single-point calibration: {e}")
            return False

    def calibrate_8bit_two_point(self, temp_low_c: float, temp_high_c: float,
                                  agc_low: Optional[int] = None, agc_high: Optional[int] = None) -> bool:
        """
        Perform two-point calibration for 8-bit estimation.
        
        Args:
            temp_low_c: Temperature at cold reference
            temp_high_c: Temperature at hot reference
            agc_low: Optional AGC value at cold reference. If None, uses scene min.
            agc_high: Optional AGC value at hot reference. If None, uses scene max.
            
        Returns:
            True if successful
        """
        if not self.temp_estimator or not self.thermal_camera:
            return False

        try:
            # Use scene min/max if not provided
            if agc_low is None:
                agc_low = self.last_agc_stats.get('min', 0)
            if agc_high is None:
                agc_high = self.last_agc_stats.get('max', 255)
                
            logger.info(f"Using AGC range: {agc_low} (low) to {agc_high} (high)")

            fpa_temp_result = self.thermal_camera.get_fpa_temperature()
            if not fpa_temp_result:
                logger.warning("Cannot calibrate: FPA temperature not available")
                return False
            
            fpa_temp_c = fpa_temp_result[1]
            self.temp_estimator.calibrate_two_point(
                agc_low, temp_low_c, agc_high, temp_high_c, fpa_temp_c
            )
            logger.info(f"Two-point calibration: {temp_low_c:.1f}°C to {temp_high_c:.1f}°C")
            return True
        except Exception as e:
            logger.error(f"Error in two-point calibration: {e}")
            return False

    def set_8bit_estimation_enabled(self, enabled: bool):
        """
        Enable or disable 8-bit temperature estimation.

        Args:
            enabled: True to enable, False to disable
        """
        if not self.temp_estimator:
            logger.warning("8-bit temperature estimator not initialized")
            return

        self.temp_estimation_enabled = enabled

        # Update thermal analyzer's radiometric flag
        # When 8-bit estimation is active, hot/cold spots should show temperatures
        if self.thermal_analyzer:
            self.thermal_analyzer.is_radiometric = enabled
            logger.debug(f"Thermal analyzer radiometric mode: {enabled}")

        # Update active mode
        if enabled:
            self.active_temp_mode = "8bit"
        else:
            # Check if 16-bit is available
            if self.thermal_camera and self.thermal_camera.is_radiometric_enabled():
                self.active_temp_mode = "16bit"
            else:
                self.active_temp_mode = "none"
        
        logger.info(f"8-bit temperature estimation: {'ENABLED' if enabled else 'DISABLED'}")
        logger.info(f"Active temperature mode: {self.active_temp_mode}")

    def get_active_temperature_mode(self) -> Dict[str, any]:
        """
        Get current active temperature mode information.
        
        Returns:
            Dictionary with mode info: {'mode': str, 'accuracy': str, 'enabled': bool}
        """
        mode_info = {
            'mode': self.active_temp_mode,
            'accuracy': 'N/A',
            'enabled': False,
            'description': 'No temperature measurement'
        }

        if self.active_temp_mode == "16bit":
            mode_info['accuracy'] = '±2°C'
            mode_info['enabled'] = True
            mode_info['description'] = '16-Bit Radiometric (True Temperature)'
        elif self.active_temp_mode == "8bit":
            mode_info['accuracy'] = '±5-10°C'
            mode_info['enabled'] = True
            mode_info['description'] = '8-Bit Pseudo-Radiometric (Estimation)'

        return mode_info

    def export_calibration(self, filepath: str) -> bool:
        """Export calibration to file."""
        if not RADIOMETRIC_CALIBRATION_AVAILABLE or not self.radiometric_calibrator:
            return False

        return self.radiometric_calibrator.export_calibration(filepath)

    def import_calibration(self, filepath: str) -> bool:
        """Import calibration from file."""
        if not RADIOMETRIC_CALIBRATION_AVAILABLE or not self.radiometric_calibrator:
            return False

        return self.radiometric_calibrator.import_calibration(filepath)

    def remove_calibration_point(self, index: int) -> bool:
        """Remove calibration point at index."""
        if not RADIOMETRIC_CALIBRATION_AVAILABLE or not self.radiometric_calibrator:
            return False

        return self.radiometric_calibrator.remove_calibration_point(index)

    def update_calibration_gui(self):
        """Update calibration GUI panel."""
        if not self.gui or not hasattr(self.gui, 'calibration_panel'):
            return

        if not RADIOMETRIC_CALIBRATION_AVAILABLE or not self.radiometric_calibrator:
            return

        try:
            # Update calibration points table
            points = self.radiometric_calibrator.calibration_points
            self.gui.calibration_panel.update_calibration_points(points)

            # Update calibration status
            stats = self.radiometric_calibrator.get_calibration_stats()
            is_calibrated = self.radiometric_calibrator.is_calibrated
            self.gui.calibration_panel.set_calibration_status(is_calibrated, stats)

        except Exception as e:
            logger.debug(f"Error updating calibration GUI: {e}")

    # ========================================================================
    # Measurement Points Control (Radiometric Feature)
    # ========================================================================

    def _on_add_point_mode_toggled(self, checked: bool):
        """Handle add point mode toggle from radiometric panel."""
        if self.gui and hasattr(self.gui, 'video_widget'):
            self.gui.video_widget.set_add_point_mode(checked)
            logger.info(f"Add measurement point mode: {'ENABLED' if checked else 'DISABLED'}")

    def _on_add_measurement_point(self, x: int, y: int):
        """
        Handle adding a measurement point from video widget click.

        Args:
            x: Frame X coordinate
            y: Frame Y coordinate
        """
        if not MEASUREMENT_POINTS_AVAILABLE or not self.measurement_points:
            logger.warning("Measurement points not available")
            return

        try:
            # Add point to manager
            point = self.measurement_points.add_point(x, y)
            logger.info(f"Added measurement point '{point.label}' at ({x}, {y})")

            # Update temperature immediately if available
            temp_frame = self._get_temperature_frame()
            if temp_frame is not None:
                # Get unit symbol from thermal_analyzer (same as hot/cold spots)
                unit_symbol = "°C"  # Default
                if self.thermal_analyzer:
                    unit_symbol = self.thermal_analyzer._get_unit_symbol()

                self.measurement_points.update_temperatures(temp_frame, unit_symbol)

            # Update GUI
            if self.gui and hasattr(self.gui, 'video_widget'):
                points = self.measurement_points.get_all_points()
                self.gui.video_widget.update_measurement_points(points)

            # Update radiometric panel
            self.update_radiometric_gui()

            # Enable buttons
            if self.gui and hasattr(self.gui, 'radiometric_panel'):
                self.gui.radiometric_panel.clear_points_btn.setEnabled(True)

        except Exception as e:
            logger.error(f"Error adding measurement point: {e}")

    def _on_clear_measurement_points(self):
        """Handle clearing all measurement points."""
        if not MEASUREMENT_POINTS_AVAILABLE or not self.measurement_points:
            return

        try:
            self.measurement_points.clear_all_points()
            logger.info("Cleared all measurement points")

            # Update GUI
            if self.gui and hasattr(self.gui, 'video_widget'):
                self.gui.video_widget.update_measurement_points([])

            # Update radiometric panel
            self.update_radiometric_gui()

            # Disable clear button
            if self.gui and hasattr(self.gui, 'radiometric_panel'):
                self.gui.radiometric_panel.clear_points_btn.setEnabled(False)
                # Turn off add mode
                self.gui.radiometric_panel.add_point_btn.setChecked(False)

        except Exception as e:
            logger.error(f"Error clearing measurement points: {e}")

    def _on_export_points_csv(self):
        """Export measurement points to CSV file."""
        if not MEASUREMENT_POINTS_AVAILABLE or not self.measurement_points:
            return

        try:
            from PyQt6.QtWidgets import QFileDialog
            import csv
            from datetime import datetime

            # Get save file path
            default_name = f"measurement_points_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            file_path, _ = QFileDialog.getSaveFileName(
                self.gui,
                "Export Measurement Points to CSV",
                default_name,
                "CSV Files (*.csv);;All Files (*.*)"
            )

            if not file_path:
                return

            # Export data
            data = self.measurement_points.export_data()

            with open(file_path, 'w', newline='') as csvfile:
                fieldnames = ['id', 'label', 'x', 'y', 'temperature_c', 'color_rgb']
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()

                for point_data in data:
                    # Convert color tuple to string for CSV
                    point_data_copy = point_data.copy()
                    point_data_copy['color_rgb'] = str(point_data['color_rgb'])
                    writer.writerow(point_data_copy)

            logger.info(f"Exported {len(data)} measurement points to CSV: {file_path}")

            # Show success message
            if self.gui:
                from PyQt6.QtWidgets import QMessageBox
                QMessageBox.information(
                    self.gui,
                    "Export Successful",
                    f"Exported {len(data)} measurement points to:\n{file_path}"
                )

        except Exception as e:
            logger.error(f"Error exporting measurement points to CSV: {e}")
            if self.gui:
                from PyQt6.QtWidgets import QMessageBox
                QMessageBox.critical(
                    self.gui,
                    "Export Failed",
                    f"Error exporting CSV:\n{str(e)}"
                )

    def _on_export_points_json(self):
        """Export measurement points to JSON file."""
        if not MEASUREMENT_POINTS_AVAILABLE or not self.measurement_points:
            return

        try:
            from PyQt6.QtWidgets import QFileDialog
            import json
            from datetime import datetime

            # Get save file path
            default_name = f"measurement_points_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            file_path, _ = QFileDialog.getSaveFileName(
                self.gui,
                "Export Measurement Points to JSON",
                default_name,
                "JSON Files (*.json);;All Files (*.*)"
            )

            if not file_path:
                return

            # Export data
            data = self.measurement_points.export_data()

            # Create full export with metadata
            export_obj = {
                'export_timestamp': datetime.now().isoformat(),
                'point_count': len(data),
                'measurement_points': data
            }

            with open(file_path, 'w') as jsonfile:
                json.dump(export_obj, jsonfile, indent=2)

            logger.info(f"Exported {len(data)} measurement points to JSON: {file_path}")

            # Show success message
            if self.gui:
                from PyQt6.QtWidgets import QMessageBox
                QMessageBox.information(
                    self.gui,
                    "Export Successful",
                    f"Exported {len(data)} measurement points to:\n{file_path}"
                )

        except Exception as e:
            logger.error(f"Error exporting measurement points to JSON: {e}")
            if self.gui:
                from PyQt6.QtWidgets import QMessageBox
                QMessageBox.critical(
                    self.gui,
                    "Export Failed",
                    f"Error exporting JSON:\n{str(e)}"
                )
    
    def _on_temperature_unit_changed(self, unit: str):
        """
        Handle temperature unit change (C/F/K/RAW).

        Args:
            unit: 'C' for Celsius, 'F' for Fahrenheit, 'K' for Kelvin, or 'RAW' for Y16 values
        """
        logger.info(f"[TEMP_UNIT] _on_temperature_unit_changed called with unit: {unit}")

        # Update thermal_analyzer (handles HotSpots/ColdSpots)
        if self.thermal_analyzer:
            self.thermal_analyzer.set_temperature_unit(unit)
            logger.info(f"[TEMP_UNIT] Updated thermal_analyzer to unit: {unit}")

        # Update radiometric converter on camera
        if self.thermal_camera and hasattr(self.thermal_camera, 'radiometric_converter'):
            converter = self.thermal_camera.radiometric_converter
            if converter:
                converter.set_temperature_unit(unit)
                logger.info(f"[TEMP_UNIT] Updated radiometric_converter to unit: {unit}")

                # Update ROI radiometric analyzer if it exists
                if self.roi_radiometric_analyzer:
                    # The ROI analyzer uses the same converter, so it's already updated
                    pass

                # Update GUI displays if radiometric is enabled
                if self.gui and hasattr(self.gui, 'radiometric_panel'):
                    self.update_radiometric_gui()

    def set_temperature_unit(self, unit: str):
        """
        Public API to set temperature unit for all displays.

        Args:
            unit: 'C' for Celsius, 'F' for Fahrenheit, or 'K' for Kelvin
        """
        self._on_temperature_unit_changed(unit)

    def set_max_hot_spots(self, count: int):
        """
        Set maximum number of hot spots to display.

        Args:
            count: Maximum number of hot spots (1-20)
        """
        try:
            if self.thermal_analyzer:
                self.thermal_analyzer.max_hot_spots = count
                logger.info(f"Max hot spots set to: {count}")
            else:
                logger.warning("Cannot set max hot spots: thermal analyzer not initialized")
        except Exception as e:
            logger.error(f"Error setting max hot spots: {e}")

    def set_max_cold_spots(self, count: int):
        """
        Set maximum number of cold spots to display.

        Args:
            count: Maximum number of cold spots (1-20)
        """
        try:
            if self.thermal_analyzer:
                self.thermal_analyzer.max_cold_spots = count
                logger.info(f"Max cold spots set to: {count}")
            else:
                logger.warning("Cannot set max cold spots: thermal analyzer not initialized")
        except Exception as e:
            logger.error(f"Error setting max cold spots: {e}")

    # ========================================================================
    # Environmental Compensation Methods (Phase 11)
    # ========================================================================

    def set_emissivity(self, emissivity: float):
        """
        Set target emissivity for temperature measurement.
        
        Args:
            emissivity: Emissivity value (0.01-1.0)
        """
        if self.thermal_camera and hasattr(self.thermal_camera, 'set_emissivity'):
            self.thermal_camera.set_emissivity(emissivity)
            logger.info(f"[OK] Emissivity set to {emissivity:.2f}")
        else:
            logger.warning("Thermal camera does not support emissivity setting")

    def set_atmospheric_temperature(self, temp_celsius: float):
        """
        Set atmospheric temperature for compensation.
        
        Args:
            temp_celsius: Atmospheric temperature in °C
        """
        if self.thermal_camera and hasattr(self.thermal_camera, 'set_atmospheric_temperature'):
            self.thermal_camera.set_atmospheric_temperature(temp_celsius)
            logger.info(f"✓ Atmospheric temperature set to {temp_celsius:.1f}°C")
        else:
            logger.warning("Thermal camera does not support atmospheric temperature setting")

    def set_atmospheric_transmission(self, transmission: float):
        """
        Set atmospheric transmission coefficient.
        
        Args:
            transmission: Transmission value (0.7-1.0)
        """
        if self.thermal_camera and hasattr(self.thermal_camera, 'set_atmospheric_transmission'):
            self.thermal_camera.set_atmospheric_transmission(transmission)
            logger.info(f"✓ Atmospheric transmission set to {transmission:.2f}")
        else:
            logger.warning("Thermal camera does not support atmospheric transmission setting")


def parse_arguments():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description='Thermal + RGB Fusion Inspection Tool'
    )

    # Camera settings
    parser.add_argument('--thermal-device', type=int, default=None,
                       help='Thermal camera device ID (default: auto-detect)')
    parser.add_argument('--rgb-device', type=int, default=None,
                       help='RGB camera device ID (default: auto-detect)')
    parser.add_argument('--auto-detect-cameras', action='store_true', default=True,
                       help='Auto-detect camera types (default: True)')
    parser.add_argument('--width', type=int, default=640,
                       help='Thermal camera width (default: 640)')
    parser.add_argument('--height', type=int, default=512,
                       help='Thermal camera height (default: 512)')
    parser.add_argument('--disable-rgb', action='store_true',
                       help='Disable RGB camera')

    # Boson SDK settings (NEW - Phase 7)
    parser.add_argument('--enable-boson-sdk', action='store_true',
                       help='Enable FLIR Boson SDK for serial control (FFC, gain, temperature)')
    parser.add_argument('--boson-com-port', type=str, default='COM7',
                       help='Boson COM port for SDK control (default: COM7)')

    # Thermal backend selection
    parser.add_argument('--thermal-backend', type=str, choices=['opencv', 'flirpy'], default='opencv',
                       help='Thermal camera backend: opencv (8-bit AGC) or flirpy (16-bit Y16 radiometric) (default: opencv)')

    # Processing settings
    parser.add_argument('--device', choices=['cuda', 'cpu'], default='cuda',
                       help='Processing device (default: cuda)')
    parser.add_argument('--palette', type=str, default='ironbow',
                      help='Thermal palette name (default: ironbow)')
    parser.add_argument('--radiometric', action='store_true',
                      help='Enable radiometric temperature measurement (default: False)')
    
    # GUI options settings (PARAMOUNT!)
    parser.add_argument('--fusion-mode', type=str, default='thermal_overlay',
                       choices=['alpha_blend', 'detail_inject', 'relief_fusion',
                               'edge_enhanced', 'thermal_overlay',
                               'side_by_side', 'picture_in_picture', 'max_intensity',
                               'feature_weighted'],
                       help='Fusion mode (default: thermal_overlay)')
    parser.add_argument('--fusion-alpha', type=float, default=0.5,
                       help='Fusion alpha for alpha_blend mode (default: 0.5)')
    parser.add_argument('--calibration-file', type=str,
                       help='Camera calibration file for alignment')

    # Inspection settings
    parser.add_argument('--mode', choices=['realtime', 'playback'], default='realtime',
                       help='Inspection mode (default: realtime)')
    parser.add_argument('--playback-file', type=str,
                       help='Video file to play back (required for playback mode)')
    parser.add_argument('--auto-roi', action='store_true',
                       help='Enable automatic ROI detection')

    # GUI settings
    parser.add_argument('--gui', type=str, choices=['qt', 'opencv', 'headless'], default='qt',
                       help='GUI type (default: qt)')
    parser.add_argument('--use-opencv-gui', action='store_true',
                       help='Use simple OpenCV GUI instead of Qt')
    parser.add_argument('--headless', action='store_true',
                       help='Run without GUI')

    # Performance optimization settings (Phase 1)
    parser.add_argument('--enable_parallel', type=lambda x: x.lower() == 'true', default=True,
                       help='Enable parallel processing (default: True)')
    parser.add_argument('--max_workers', type=int, default=5,
                       help='Maximum number of worker threads for parallel detection (default: 5)')

    return parser.parse_args()


def main():
    """Main entry point."""
    args = parse_arguments()

    logger.info("=" * 80)
    logger.info("Thermal Inspection Fusion Tool")
    logger.info("Transformed from ThermalFusionDrivingAssist")
    logger.info("=" * 80)

    # Initialize Qt app if not using OpenCV GUI
    qt_app = None
    if not args.use_opencv_gui and not args.headless:
        try:
            from PyQt6.QtWidgets import QApplication
            qt_app = QApplication(sys.argv)
            logger.info("Qt GUI enabled")
        except ImportError:
            logger.warning("PyQt6 not available, falling back to OpenCV GUI")
            args.use_opencv_gui = True

    # Create and run application
    app = ThermalInspectionFusion(args, qt_app)

    if not app.initialize():
        logger.error("Initialization failed")
        return 1

    app.run()

    return 0


if __name__ == '__main__':
    sys.exit(main())
