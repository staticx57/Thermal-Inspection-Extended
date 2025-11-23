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
from typing import Optional, Dict, List
from collections import deque

# Enable faulthandler for debugging
faulthandler.enable()

# Camera modules
from flir_camera import FLIRBosonCamera
from camera_factory import create_rgb_camera
from placeholder_frames import create_thermal_placeholder, create_rgb_placeholder

# Processing modules (NEW - Inspection focused)
from thermal_processor import ThermalProcessor
from thermal_analyzer import ThermalAnalyzer
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

        # Cameras
        self.thermal_camera: Optional[FLIRBosonCamera] = None
        self.rgb_camera = None
        self.rgb_available = False
        self.thermal_connected = False

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
            "thermal_anomalies": True
        }

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
                    logger.info("✓ Boson SDK connected - serial control enabled")
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

            self.rgb_camera = create_rgb_camera(
                resolution=(640, 480),
                fps=30,
                camera_type="auto",
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
            # 1. Connect thermal camera (optional at startup - hot-plug support)
            thermal_connected = self._try_connect_thermal()

            if not thermal_connected:
                logger.warning("=" * 60)
                logger.warning("NO THERMAL CAMERA DETECTED")
                logger.warning("System will wait for thermal camera connection...")
                logger.warning("=" * 60)

            # 2. Determine resolution
            if self.thermal_connected and self.thermal_camera:
                actual_res = self.thermal_camera.get_actual_resolution()
            else:
                actual_res = (self.args.width, self.args.height)
                logger.info(f"Using default resolution: {actual_res[0]}x{actual_res[1]}")

            # 3. Connect RGB camera (optional)
            if not self.args.disable_rgb:
                self._try_connect_rgb()

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
                'edge_detection_enabled': True
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
            'thermal_stats': None
        }

        if thermal_frame is None:
            return result

        try:
            # 1. Process thermal frame (motion + edge detection)
            processor_result = self.thermal_processor.process_frame(thermal_frame)
            result['motion_detections'] = processor_result['motion_detections']
            result['edge_clusters'] = processor_result['edge_clusters']

            # 2. Apply palette (global + ROI overrides)
            thermal_colorized = self.palette_manager.apply_composite_palette(
                thermal_frame, self.roi_manager
            )
            result['thermal_colorized'] = thermal_colorized

            # 3. Automatic ROI detection (if enabled)
            # OPTIMIZATION: Only run auto-ROI detection every N frames to reduce overhead
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

            # 4. Thermal analysis for each ROI
            for roi in self.roi_manager.get_all_rois(active_only=True):
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

            # 5. Global thermal analysis (whole frame)
            global_stats = self.thermal_analyzer.analyze_frame(thermal_frame)
            result['thermal_stats'] = global_stats

            # Hot/cold spot detection
            result['hot_spots'] = self.thermal_analyzer.detect_hot_spots(thermal_frame)
            result['cold_spots'] = self.thermal_analyzer.detect_cold_spots(thermal_frame)

            # Anomaly detection
            result['anomalies'] = self.thermal_analyzer.detect_anomalies(thermal_frame, 'global')

            # 5b. Apply anomaly priority colorization if enabled (AFTER all detections)
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

                # Apply gradient fade colorization with ALL anomalies
                # This updates thermal_colorized which is then used in fusion
                thermal_colorized = self.thermal_processor.apply_anomaly_priority_colorization(
                    thermal_frame, all_anomalies, thermal_colorized
                )
                # Update result with anomaly-priority-applied colorization
                result['thermal_colorized'] = thermal_colorized

            # 6. Create fused frame if RGB available
            if rgb_frame is not None and self.fusion_processor:
                try:
                    fused_frame = self.fusion_processor.fuse_frames(thermal_colorized, rgb_frame)
                    result['fused_frame'] = fused_frame
                except Exception as e:
                    logger.debug(f"Fusion processing error: {e}")
                    result['fused_frame'] = None

            # 7. Select display frame based on view mode
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

            # 8. Draw ROIs on display frame
            display_frame = self.roi_manager.draw_rois(display_frame, active_only=True)

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

        except Exception as e:
            logger.error(f"Frame processing error: {e}", exc_info=True)

        return result

    def run(self):
        """Main inspection application loop."""
        logger.info("Starting inspection loop...")
        self.running = True

        # Show Qt GUI if available
        if self.gui_type == 'qt' and self.gui:
            self.gui.show()
            logger.info("Qt GUI window shown")

        try:
            while self.running:
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

                # Create placeholder if no thermal
                if thermal_frame is None:
                    res = (self.args.width, self.args.height)
                    placeholder_rgb = create_thermal_placeholder(width=res[0], height=res[1])
                    placeholder_gray = cv2.cvtColor(placeholder_rgb, cv2.COLOR_BGR2GRAY)
                    thermal_frame = (placeholder_gray.astype(np.uint16) * 256)

                t_markers['after_placeholder'] = time.time()

                # 3. Capture RGB frame
                rgb_frame = None
                if self.rgb_camera and self.rgb_available:
                    try:
                        ret_rgb, rgb_frame = self.rgb_camera.read()
                        if not ret_rgb:
                            rgb_frame = None
                    except Exception as e:
                        logger.debug(f"RGB camera error: {e}")
                        rgb_frame = None

                t_markers['after_rgb_read'] = time.time()

                # 4. Process frames through inspection pipeline
                result = self.process_frame(thermal_frame, rgb_frame)
                t_markers['after_process_frame'] = time.time()

                # 4.5. Handle recording (NEW - Phase 6)
                display_frame = result.get('display_frame')
                if self.recording_enabled and display_frame is not None:
                    # Start recording if not already started
                    if not self.video_recorder.is_recording():
                        frame_shape = display_frame.shape
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
                                logger.info("✓ FFC completed successfully")
                            else:
                                logger.error("✗ FFC failed")
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
                t_markers['before_gui_update'] = time.time()
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
                    # Calculate timing deltas
                    thermal_read_ms = (t_markers.get('after_thermal_read', 0) - t_markers.get('before_thermal_read', 0)) * 1000
                    placeholder_ms = (t_markers.get('after_placeholder', 0) - t_markers.get('after_thermal_read', 0)) * 1000
                    rgb_read_ms = (t_markers.get('after_rgb_read', 0) - t_markers.get('after_placeholder', 0)) * 1000
                    process_frame_ms = (t_markers.get('after_process_frame', 0) - t_markers.get('after_rgb_read', 0)) * 1000
                    gui_update_ms = (t_markers.get('after_gui_update', 0) - t_markers.get('before_gui_update', 0)) * 1000
                    process_events_ms = (t_markers.get('after_processEvents', 0) - t_markers.get('before_processEvents', 0)) * 1000

                    logger.info(f"Frame {self.frame_count}: {self.smoothed_fps:.1f} FPS ({avg_time*1000:.1f}ms/frame)")
                    logger.info(f"  Timing breakdown: thermal_read={thermal_read_ms:.1f}ms, placeholder={placeholder_ms:.1f}ms, "
                               f"rgb_read={rgb_read_ms:.1f}ms, process_frame={process_frame_ms:.1f}ms, "
                               f"gui_update={gui_update_ms:.1f}ms, processEvents={process_events_ms:.1f}ms")
                    logger.info(f"  Detections: {len(result['rois'])} ROIs, {len(result['motion_detections'])} motion, "
                               f"{len(result['hot_spots'])} hot spots")

        except KeyboardInterrupt:
            logger.info("Interrupted by user")
        except Exception as e:
            logger.error(f"Main loop error: {e}", exc_info=True)
        finally:
            self.cleanup()
    # ========================================================================
    # GUI Control Methods
    # ========================================================================

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
        if self.recording_enabled:
            if self.video_recorder:
                filename = self.video_recorder.start_recording((self.args.width, self.args.height))
                logger.info(f"Started recording: {filename}")
        else:
            if self.video_recorder:
                self.video_recorder.stop_recording()
                logger.info("Stopped recording")

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
                logger.info("✓ FFC completed successfully")
                if self.gui and hasattr(self.gui, 'boson_panel'):
                    self.gui.boson_panel.set_ffc_status("FFC completed successfully", is_error=False)
                return True
            else:
                logger.error("✗ FFC failed")
                if self.gui and hasattr(self.gui, 'boson_panel'):
                    self.gui.boson_panel.set_ffc_status("FFC failed", is_error=True)
                return False
        else:
            logger.warning("FFC requires Boson SDK connection")
            return False

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

    def update_boson_gui(self):
        """Update Boson control panel with current camera info."""
        if not self.gui or not hasattr(self.gui, 'boson_panel'):
            return

        # Update connection status
        is_connected = self.thermal_camera and self.thermal_camera.is_sdk_connected()
        self.gui.boson_panel.update_connection_status(is_connected)

        if is_connected:
            # Update camera info
            info = self.thermal_camera.get_camera_info()
            if info:
                self.gui.boson_panel.update_camera_info(info)

            # Update FPA temperature
            temp = self.thermal_camera.get_fpa_temperature()
            if temp:
                self.gui.boson_panel.update_fpa_temperature(temp[0], temp[1])


    def cleanup(self):
        """Clean up resources."""
        logger.info("Cleaning up...")
        self.running = False

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

        if self.thermal_camera:
            self.thermal_camera.release()
        if self.rgb_camera:
            self.rgb_camera.release()
        if self.thermal_processor:
            self.thermal_processor.release()

        cv2.destroyAllWindows()
        logger.info("Cleanup complete")


def parse_arguments():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description='Thermal + RGB Fusion Inspection Tool'
    )

    # Camera settings
    parser.add_argument('--thermal-device', type=int, default=0,
                       help='Thermal camera device ID (default: 0)')
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
    parser.add_argument('--use-opencv-gui', action='store_true',
                       help='Use simple OpenCV GUI instead of Qt')
    parser.add_argument('--headless', action='store_true',
                       help='Run without GUI')

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
