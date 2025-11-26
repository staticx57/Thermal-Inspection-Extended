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
from palette_manager import PaletteManager, PaletteType
from media_recorder import VideoRecorder, VideoPlayer, SnapshotManager

# Core modules (PRESERVED - Fusion is paramount!)
from fusion_processor import FusionProcessor

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
        self.palette_manager: Optional[PaletteManager] = None

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

        # Inspection mode settings
        self.inspection_mode = getattr(args, 'mode', 'realtime')  # realtime or playback
        self.recording_enabled = False
        self.frame_frozen = False
        self.video_writer = None

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

        # Use robust initializer with thermal-first priority
        thermal_cam, rgb_cam = CameraInitializer.init_cameras_prioritized(thermal_first=True)

        # Handle thermal camera
        thermal_success = False
        if thermal_cam:
            self.thermal_camera = thermal_cam
            self.thermal_connected = True
            self.is_flir_boson = True  # Assuming Boson if thermal detected
            thermal_success = True

            # Log SDK status if enabled
            if hasattr(thermal_cam, 'is_sdk_connected') and thermal_cam.is_sdk_connected():
                logger.info("=" * 60)
                logger.info("[OK] Boson SDK connected - serial control enabled")
                info = thermal_cam.get_camera_info()
                if info:
                    logger.info(f"  Camera SN: {info.serial_number}")
                logger.info("=" * 60)

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
            enable_sdk = getattr(self.args, 'enable_boson_sdk', False)
            com_port = getattr(self.args, 'boson_com_port', 'COM6')

            self.thermal_camera = FLIRBosonCamera(
                device_id=getattr(self.args, 'thermal_device', 0),
                resolution=(getattr(self.args, 'width', 640), getattr(self.args, 'height', 512)),
                enable_sdk=enable_sdk,
                com_port=com_port
            )

            if self.thermal_camera.open():
                actual_res = self.thermal_camera.get_actual_resolution()
                logger.info(f"[OK] Thermal camera connected: {actual_res[0]}x{actual_res[1]}")

                # Set FLIR Boson flag
                self.is_flir_boson = True

                # NEW: Log SDK status (Phase 7)
                if self.thermal_camera.is_sdk_connected():
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
                elif enable_sdk:
                    logger.warning("SDK was requested but connection failed - continuing in video-only mode")

                self.thermal_connected = True
                
                # Auto-detect radiometric mode
                is_radiometric = self._detect_radiometric_mode()
                if is_radiometric:
                    self.args.radiometric = True
                    logger.info("Auto-enabled radiometric mode")
                
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

    def _detect_radiometric_mode(self) -> bool:
        """
        Detect if camera is providing radiometric data (T-Linear).
        Heuristic: T-Linear values are typically > 20000 (Kelvin * 100).
        Raw values are typically < 16384 (14-bit).
        """
        if not self.thermal_camera:
            return False
            
        logger.info("Detecting camera mode...")
        
        # Grab a few frames to settle
        for _ in range(5):
            self.thermal_camera.read_thermal()
            
        success, frame = self.thermal_camera.read_thermal()
        if not success or frame is None:
            logger.warning("Could not grab frame for mode detection")
            return False
            
        # Check median value
        median_val = np.median(frame)
        logger.info(f"Median pixel value: {median_val:.1f}")
        
        # T-Linear check: 0°C = 273.15K = 27315
        # Allow range 20000 (200K/-73°C) to 60000 (600K/327°C)
        if 20000 < median_val < 65000:
            logger.info("[DETECTED] Radiometric Mode (T-Linear)")
            return True
        else:
            logger.info("[DETECTED] Non-Radiometric Mode (Raw/AGC)")
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

            # 4. Initialize fusion processor (PARAMOUNT!)
            if self.rgb_available:
                calibration_file = getattr(self.args, 'calibration_file', None)
                self.fusion_processor = FusionProcessor(
                    fusion_mode=self.fusion_mode,
                    alpha=self.fusion_alpha,
                    calibration_file=calibration_file
                )
                logger.info(f"[OK] Fusion processor initialized (mode: {self.fusion_mode})")
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

                    # Update camera panel statuses
                    self.update_firefly_gui()
                    self.update_boson_gui()
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
            result['thermal_colorized'] = thermal_colorized

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
            t_prof['after_auto_roi'] = time.time()

            # 4. Thermal analysis for each ROI
            t_prof['before_roi_analysis'] = time.time()
            rois = self.roi_manager.get_all_rois(active_only=True)

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

                        # Update trend tracking
                        self.thermal_analyzer.update_trend(roi.roi_id, stats.mean_temp)

            t_prof['after_roi_analysis'] = time.time()

            # 5. Global thermal analysis (whole frame)
            t_prof['before_thermal_analysis'] = time.time()

            # OPTIMIZATION: Parallel detection tasks (Phase 1)
            if self.enable_parallel_processing and self.detection_executor:
                # Submit all detection tasks in parallel
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
                    self.latest_threshold_result = threshold_result
                else:
                    result['manual_threshold_result'] = None
                    self.latest_threshold_result = None

            t_prof['after_thermal_analysis'] = time.time()

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

            # 5c. Apply manual threshold visualization if enabled
            if self.manual_threshold_enabled and self.latest_threshold_result is not None:
                thermal_colorized = self.thermal_analyzer.apply_threshold_visualization(
                    thermal_frame,
                    thermal_colorized,
                    self.latest_threshold_result,
                    viz_mode=self.manual_threshold_viz_mode
                )
                result['thermal_colorized'] = thermal_colorized

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
                # 0. Check if reconfiguring (pause loop if so)
                if self.reconfiguring:
                    time.sleep(0.1)
                    if self.gui_type == 'qt' and self.qt_app:
                        self.qt_app.processEvents()
                    continue

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
                if not self.thermal_connected:
                    current_time = time.time()
                    if current_time - self.last_thermal_scan_time > self.thermal_scan_interval:
                        self.last_thermal_scan_time = current_time
                        if self._try_connect_thermal():
                            logger.info("[OK] Thermal camera connected!")

                # 2. Capture thermal frame
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

                    t_markers['after_thermal_read'] = time.time()

                    # RGB capture
                    if self.rgb_camera and self.rgb_available:
                        try:
                            ret_rgb, rgb_frame = self.rgb_camera.read()
                            if not ret_rgb:
                                rgb_frame = None
                        except Exception as e:
                            logger.debug(f"RGB camera error: {e}")
                            rgb_frame = None

                    t_markers['after_placeholder'] = time.time()
                    t_markers['after_rgb_read'] = time.time()

                # Create placeholder if no thermal
                if thermal_frame is None:
                    res = (self.args.width, self.args.height)
                    placeholder_rgb = create_thermal_placeholder(width=res[0], height=res[1])
                    placeholder_gray = cv2.cvtColor(placeholder_rgb, cv2.COLOR_BGR2GRAY)
                    thermal_frame = (placeholder_gray.astype(np.uint16) * 256)

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
                        if display_frame is not None:
                            rois = result.get('rois', [])
                            snapshot_path = self.snapshot_manager.capture_snapshot(
                                frame=display_frame,
                                rois=rois,
                                thermal_stats=thermal_stats,
                                hot_spots=self.latest_hot_spots,
                                cold_spots=self.latest_cold_spots,
                                anomalies=self.latest_anomalies
                            )
                            if snapshot_path:
                                logger.info(f"Snapshot saved: {snapshot_path}")
                    elif key == ord('f'):
                        # Trigger FFC (Flat Field Correction) - NEW: Phase 7
                        if self.thermal_camera and self.thermal_camera.is_sdk_connected():
                            logger.info("Triggering FFC (watch camera shutter)...")
                            if self.thermal_camera.trigger_ffc():
                                logger.info("[OK] FFC completed successfully")
                            else:
                                logger.error("[ERROR] FFC failed")
                        else:
                            logger.warning("FFC requires Boson SDK connection (use --enable-boson-sdk)")
                    elif key == ord('t'):
                        # Show FPA temperature - NEW: Phase 7
                        if self.thermal_camera and self.thermal_camera.is_sdk_connected():
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
                        trend=None
                    )

                    # Update ROIs
                    self.gui.update_rois(result.get('rois', []))

                    # Update Boson panel (every 60 frames to reduce overhead)
                    if self.frame_count % 60 == 0:
                        self.update_boson_gui()

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

    def set_palette(self, palette_name: str):
        """Set specific palette by name."""
        if self.palette_manager:
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

    def set_msx_strength(self, strength: float):
        """Set MSX detail overlay strength."""
        if self.fusion_processor:
            self.fusion_processor.msx_strength = strength
            logger.info(f"MSX strength set to: {strength:.2f}")

    def set_msx_quality(self, quality: float):
        """Set MSX quality/detail level."""
        if self.fusion_processor:
            self.fusion_processor.msx_quality = quality
            logger.info(f"MSX quality set to: {quality:.2f}")

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
                stats = self.thermal_analyzer.compute_statistics(self.last_thermal_frame)
                hot_threshold = stats.percentile_95
                cold_threshold = stats.percentile_5
                hot_rois = self.roi_manager.auto_detect_roi_by_temperature(
                    self.last_thermal_frame, hot_threshold, is_hot_region=True
                )
                cold_rois = self.roi_manager.auto_detect_roi_by_temperature(
                    self.last_thermal_frame, cold_threshold, is_hot_region=False
                )
                logger.info(f"Auto-detected {len(hot_rois)} hot regions and {len(cold_rois)} cold regions")
    
    def clear_rois(self):
        """Clear all ROIs."""
        if self.roi_manager:
            self.roi_manager.clear_all_rois()
            logger.info("All ROIs cleared")
    
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
        if self.thermal_camera and self.thermal_camera.is_sdk_connected():
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
        if self.thermal_camera and self.thermal_camera.is_sdk_connected():
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
        if self.thermal_camera and self.thermal_camera.is_sdk_connected():
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

    def set_boson_color_lut(self, lut_name: str):
        """Set Boson color LUT (palette)."""
        if self.thermal_camera and self.thermal_camera.is_sdk_connected():
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
        if self.thermal_camera and self.thermal_camera.is_sdk_connected():
            if hasattr(self.thermal_camera, 'set_agc_max_gain'):
                return self.thermal_camera.set_agc_max_gain(gain)
        return False

    def set_agc_gamma(self, gamma: float) -> bool:
        """Set AGC gamma correction (ACE - Automatic Contrast Enhancement)."""
        if self.thermal_camera and self.thermal_camera.is_sdk_connected():
            if hasattr(self.thermal_camera, 'set_agc_gamma'):
                return self.thermal_camera.set_agc_gamma(gamma)
        return False

    def set_agc_linearity(self, percent: float) -> bool:
        """Set AGC linearity (histogram vs. linear mapping)."""
        if self.thermal_camera and self.thermal_camera.is_sdk_connected():
            if hasattr(self.thermal_camera, 'set_agc_linearity'):
                return self.thermal_camera.set_agc_linearity(percent)
        return False

    def set_agc_dde(self, dde: float) -> bool:
        """Set AGC DDE (Digital Detail Enhancement)."""
        if self.thermal_camera and self.thermal_camera.is_sdk_connected():
            if hasattr(self.thermal_camera, 'set_detail_enhancement'):
                return self.thermal_camera.set_detail_enhancement(dde)
        return False

    def reset_agc_settings(self) -> bool:
        """Reset AGC settings to defaults."""
        if self.thermal_camera and self.thermal_camera.is_sdk_connected():
            # Reset to defaults: max_gain=2.0, gamma=1.0, linearity=50%, dde=1.3
            success = True
            success &= self.set_agc_max_gain(2.0)
            success &= self.set_agc_gamma(1.0)
            success &= self.set_agc_linearity(50.0)
            success &= self.set_agc_dde(1.3)
            if success:
                logger.info("AGC settings reset to defaults")
            return success
        return False

    def connect_boson_sdk(self, com_port: str) -> bool:
        """
        Connect to Boson SDK.

        Args:
            com_port: COM port (e.g., 'COM6')

        Returns:
            True if successful
        """
        if not self.thermal_camera or not self.is_flir_boson:
            logger.warning("No thermal camera connected or not a Boson")
            return False

        if self.thermal_camera.connect_sdk(com_port if com_port else None):
            logger.info(f"Boson SDK connected on {com_port}")
            return True
        else:
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
                from threaded_camera_capture import ThreadedCameraCapture
                self.threaded_capture = ThreadedCameraCapture(self.thermal_camera, self.rgb_camera)
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

        if not self.thermal_camera.is_sdk_connected():
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
                          self.thermal_camera.is_sdk_connected())
            
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
    parser.add_argument('--boson-com-port', type=str, default='COM6',
                       help='Boson COM port for SDK control (default: COM6)')

    # Processing settings
    parser.add_argument('--device', choices=['cuda', 'cpu'], default='cuda',
                       help='Processing device (default: cuda)')
    parser.add_argument('--palette', type=str, default='ironbow',
                      help='Thermal palette name (default: ironbow)')
    parser.add_argument('--radiometric', action='store_true',
                      help='Enable radiometric temperature measurement (default: False)')
    
    # GUI options settings (PARAMOUNT!)
    parser.add_argument('--fusion-mode', type=str, default='thermal_overlay',
                       choices=['alpha_blend', 'edge_enhanced', 'thermal_overlay',
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
