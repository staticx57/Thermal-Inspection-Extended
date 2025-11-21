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
        self.frame_count = 0
        self.device = getattr(args, 'device', 'cuda')

        # Inspection mode settings
        self.inspection_mode = getattr(args, 'mode', 'realtime')  # realtime or playback
        self.recording_enabled = False
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

        # ROI auto-detection settings
        self.auto_roi_enabled = getattr(args, 'auto_roi', False)
        self.auto_roi_methods = {
            'temperature': True,
            'gradient': True,
            'motion': True,
            'edge': True
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

                # NEW: Log SDK status (Phase 7)
                if self.thermal_camera.is_sdk_connected():
                    logger.info("=" * 60)
                    logger.info("✓ Boson SDK connected - serial control enabled")
                    info = self.thermal_camera.get_camera_info()
                    if info:
                        logger.info(f"  Camera SN: {info.serial_number}")
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
                return True
            else:
                logger.debug("Thermal camera not found")
                self.thermal_camera = None
                return False

        except Exception as e:
            logger.debug(f"Thermal camera connection failed: {e}")
            self.thermal_camera = None
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
                'anomaly_sensitivity': 0.7
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
                # TODO: Create inspection_gui_qt.py
                logger.info("Qt GUI selected (inspection_gui_qt.py - TO BE IMPLEMENTED)")
                # Temporarily use placeholder
                self.gui_type = 'qt'
                self.gui = None  # Will be implemented in next phase
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
            if self.auto_roi_enabled:
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

            # 6. Fusion (if RGB available) - PARAMOUNT!
            if rgb_frame is not None and self.fusion_processor:
                fused = self.fusion_processor.fuse(
                    thermal_colorized, rgb_frame, mode=self.fusion_mode
                )
                result['fused_frame'] = fused
            else:
                result['fused_frame'] = thermal_colorized

            # 7. Draw ROIs on display frame
            display_frame = result['fused_frame'].copy()
            display_frame = self.roi_manager.draw_rois(display_frame, active_only=True)

            result['display_frame'] = display_frame
            result['rois'] = self.roi_manager.get_all_rois(active_only=True)

            # Store latest results for GUI
            self.latest_motion_detections = result['motion_detections']
            self.latest_edge_clusters = result['edge_clusters']
            self.latest_hot_spots = result['hot_spots']
            self.latest_cold_spots = result['cold_spots']
            self.latest_anomalies = result['anomalies']

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

                # 1. Poll for thermal camera if not connected (hot-plug support)
                if not self.thermal_connected:
                    current_time = time.time()
                    if current_time - self.last_thermal_scan_time > self.thermal_scan_interval:
                        self.last_thermal_scan_time = current_time
                        if self._try_connect_thermal():
                            logger.info("[OK] Thermal camera connected!")

                # 2. Capture thermal frame
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
                except Exception as e:
                    logger.warning(f"Thermal camera error: {e}")
                    self.thermal_connected = False
                    if self.thermal_camera:
                        self.thermal_camera.release()
                    self.thermal_camera = None

                # Create placeholder if no thermal
                if thermal_frame is None:
                    res = (self.args.width, self.args.height)
                    placeholder_rgb = create_thermal_placeholder(width=res[0], height=res[1])
                    placeholder_gray = cv2.cvtColor(placeholder_rgb, cv2.COLOR_BGR2GRAY)
                    thermal_frame = (placeholder_gray.astype(np.uint16) * 256)

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

                # 4. Process frames through inspection pipeline
                result = self.process_frame(thermal_frame, rgb_frame)

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

                # 6. Update performance metrics
                loop_time = time.time() - loop_start
                self.frame_times.append(loop_time)
                if len(self.frame_times) > 0:
                    avg_time = sum(self.frame_times) / len(self.frame_times)
                    self.smoothed_fps = 1.0 / avg_time if avg_time > 0 else 0

                self.frame_count += 1

                # Log periodically
                if self.frame_count % 100 == 0:
                    logger.info(f"Frame {self.frame_count}: {self.smoothed_fps:.1f} FPS, "
                               f"{len(result['rois'])} ROIs, "
                               f"{len(result['motion_detections'])} motion, "
                               f"{len(result['hot_spots'])} hot spots")

        except KeyboardInterrupt:
            logger.info("Interrupted by user")
        except Exception as e:
            logger.error(f"Main loop error: {e}", exc_info=True)
        finally:
            self.cleanup()

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
                       help='Default thermal palette (default: ironbow)')

    # Fusion settings (PARAMOUNT!)
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
            from PyQt5.QtWidgets import QApplication
            qt_app = QApplication(sys.argv)
            logger.info("Qt GUI enabled")
        except ImportError:
            logger.warning("PyQt5 not available, falling back to OpenCV GUI")
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
