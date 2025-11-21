#!/usr/bin/env python3
"""
FLIR Boson Thermal + RGB Fusion Road Monitor
Cross-platform: Jetson Orin (ARM + CUDA) and x86-64 workstations
Features: Thermal-RGB fusion, multi-view display, smart proximity alerts
"""
import sys
import time
import logging
import argparse
import threading
import platform
from queue import Queue
import cv2
import os
import numpy as np
import faulthandler

# Enable faulthandler to catch segfaults and C++ crashes
faulthandler.enable()

from flir_camera import FLIRBosonCamera
from camera_factory import create_rgb_camera, detect_all_rgb_cameras
from camera_detector import CameraDetector
from camera_registry import get_camera_registry, CameraRole
from placeholder_frames import (create_thermal_placeholder, create_rgb_placeholder,
                                 create_feed_unavailable_frame, CameraStatus)
from vpi_detector import VPIDetector
from fusion_processor import FusionProcessor
# from road_analyzer import RoadAnalyzer  # Commented out - file removed during transformation
from view_mode import ViewMode
from performance_monitor import PerformanceMonitor

# Qt VideoProcessorWorker (Phase 3 multithreading)
try:
    from video_worker import VideoProcessorWorker
    HAS_VIDEO_WORKER = True
except ImportError:
    HAS_VIDEO_WORKER = False
    VideoProcessorWorker = None

# GUI will be imported conditionally based on --use-qt-gui argument


def setup_logging():
    """
    Configure logging with both console and file output
    File: thermal_fusion_debug.log (rotating, keeps last 5 files, 10MB each)
    """
    from logging.handlers import RotatingFileHandler

    # Create formatters
    detailed_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
    )
    simple_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    # Console handler (simple format)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(simple_formatter)
    root_logger.addHandler(console_handler)

    # File handler (detailed format with line numbers)
    # Rotating: 10MB per file, keep last 5 files
    try:
        file_handler = RotatingFileHandler(
            'thermal_fusion_debug.log',
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5
        )
        file_handler.setLevel(logging.DEBUG)  # Capture everything to file
        file_handler.setFormatter(detailed_formatter)
        root_logger.addHandler(file_handler)
        logging.info("[OK] Debug logging enabled: thermal_fusion_debug.log (10MB x5 files)")
    except Exception as e:
        logging.warning(f"Could not create debug log file: {e}")

    return logging.getLogger(__name__)


# Initialize logging
logger = setup_logging()


def detect_platform():
    """
    Detect platform (Jetson ARM or x86-64 workstation)

    Returns:
        dict with platform info
    """
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

    logger.info(f"Platform detection: {platform_info}")
    return platform_info


class ThermalRoadMonitorFusion:
    """Main application with thermal-RGB fusion support"""

    def __init__(self, args, qt_app=None):
        self.args = args
        self.qt_app = qt_app  # QApplication instance (if using Qt GUI)
        self.platform_info = detect_platform()

        # Cameras
        self.thermal_camera = None
        self.rgb_camera = None
        self.rgb_available = False

        # Processing
        self.detector = None
        self.fusion_processor = None
        self.analyzer = None
        self.gui = None
        self.perf_monitor = None

        # Runtime state
        self.running = False
        self.show_detections = True
        self.yolo_enabled = (getattr(args, 'detection_mode', 'edge') == 'model')
        self.frame_count = 0
        self.device = getattr(args, 'device', 'cuda')
        self.alert_override_mode = "auto"  # Alert override mode: auto/on/off
        self.thermal_colorize_mode = False  # Thermal colorization mode

        # Performance tuning
        self.buffer_flush_enabled = False
        self.frame_skip_value = 1

        # Debug features
        self.use_simulated_thermal = False  # Simulated thermal camera for testing

        # v3.0 Advanced ADAS state
        self.audio_enabled = getattr(args, 'enable_audio', True)
        self.distance_enabled = getattr(args, 'enable_distance', True)

        # GUI state (dual-mode GUI)
        self.show_info_panel = False
        self.developer_mode = False  # Start in simple mode

        # Model management
        self.available_models = ['yolov8n.pt', 'yolov8s.pt', 'yolov8m.pt']
        self.current_model = getattr(args, 'model', 'yolov8s.pt')
        self.current_model_index = 0
        if self.current_model in self.available_models:
            self.current_model_index = self.available_models.index(self.current_model)
        self.model_switching = False

        # Fusion settings
        self.fusion_mode = getattr(args, 'fusion_mode', 'alpha_blend')
        self.fusion_alpha = getattr(args, 'fusion_alpha', 0.5)
        self.available_fusion_modes = ['alpha_blend', 'edge_enhanced', 'thermal_overlay',
                                       'side_by_side', 'picture_in_picture', 'max_intensity',
                                       'feature_weighted']
        self.current_fusion_mode_index = 0
        if self.fusion_mode in self.available_fusion_modes:
            self.current_fusion_mode_index = self.available_fusion_modes.index(self.fusion_mode)

        # View mode
        self.view_mode = ViewMode.THERMAL_ONLY  # Start with thermal

        # FPS smoothing
        from collections import deque
        self.frame_times = deque(maxlen=60)
        self.smoothed_fps = 60.0
        self.min_frame_time = 1.0 / 60.0

        # Async detection
        self.detection_thread = None
        self.detection_queue = Queue(maxsize=2)
        self.result_queue = Queue(maxsize=2)
        self.detection_lock = threading.Lock()
        self.latest_detections = []
        self.latest_alerts = []

        # Thermal camera connection state
        self.thermal_connected = False
        self.last_thermal_scan_time = 0
        self.thermal_scan_interval = 3.0  # Scan every 3 seconds
        
        # RGB camera connection state (for hot-plugging)
        self.last_rgb_scan_time = 0
        self.rgb_scan_interval = 5.0  # Scan every 5 seconds
        
        # Camera registry for tracking camera roles
        self.camera_registry = get_camera_registry()

    def _generate_simulated_thermal_frame(self, resolution=(640, 512)) -> np.ndarray:
        """
        Generate a simulated thermal frame for debugging without hardware.
        Creates a synthetic thermal pattern with hot spots and gradients.

        Args:
            resolution: (width, height) tuple

        Returns:
            np.ndarray: Simulated 16-bit thermal frame
        """
        width, height = resolution
        frame = np.zeros((height, width), dtype=np.uint16)

        # Base temperature gradient (simulates ground and sky)
        y_gradient = np.linspace(28000, 26000, height, dtype=np.uint16)[:, np.newaxis]
        frame += y_gradient

        # Add animated hot spots (simulates vehicles, people, etc.)
        num_hotspots = 3 + (self.frame_count % 3)  # 3-5 hotspots
        for i in range(num_hotspots):
            # Animated position
            x = int((width * 0.2) + (width * 0.6) * ((self.frame_count * (i + 1) / 100) % 1.0))
            y = int(height * 0.3) + int(height * 0.4 * (i / num_hotspots))

            # Create Gaussian hot spot
            size = 40 + (i * 15)
            y_grid, x_grid = np.ogrid[-y:height-y, -x:width-x]
            mask = (x_grid*x_grid + y_grid*y_grid) <= (size*size)

            # Add temperature variation (30000-32000 = hot objects)
            intensity = 30000 + (i * 500) + int(500 * np.sin(self.frame_count / 10))
            frame[mask] = np.clip(frame[mask] + intensity - 26000, 26000, 32000)

        # Add noise for realism
        noise = np.random.randint(-200, 200, (height, width), dtype=np.int16)
        frame = np.clip(frame.astype(np.int32) + noise, 0, 65535).astype(np.uint16)

        return frame

    def _try_connect_thermal(self) -> bool:
        """
        Try to detect and connect thermal camera with proper camera type validation
        Uses camera registry to support manual camera assignments

        Returns:
            True if connected successfully, False otherwise
        """
        try:
            # Check camera registry for manually assigned thermal camera first
            thermal_cam_descriptor = self.camera_registry.get_thermal_camera()
            
            if thermal_cam_descriptor:
                # Manual assignment exists - try to connect to that specific camera
                logger.info(f"Using manually assigned thermal camera: device {thermal_cam_descriptor.device_id}")
                self.args.camera_id = thermal_cam_descriptor.device_id
                self.args.width = thermal_cam_descriptor.resolution[0]
                self.args.height = thermal_cam_descriptor.resolution[1]
            elif self.args.camera_id is None:
                # No manual assignment - auto-detect
                logger.info("Auto-detecting thermal cameras...")

                # Build list of device IDs to skip (already in use by RGB)
                skip_device_ids = []
                if hasattr(self, 'rgb_camera') and self.rgb_camera and hasattr(self.rgb_camera, 'device_id'):
                    skip_device_ids.append(self.rgb_camera.device_id)
                    logger.debug(f"Skipping RGB camera device {self.rgb_camera.device_id} during thermal scan")

                cameras = CameraDetector.detect_all_cameras(skip_device_ids=skip_device_ids)

                CameraDetector.print_camera_list(cameras)

                # Use new thermal camera detection with type validation
                # Check registry first for any thermal-assigned cameras
                thermal_camera = None
                for cam in cameras:
                    if cam.is_thermal():
                        thermal_camera = cam
                        logger.info(f"Detected thermal camera: {thermal_camera}")
                        break

                if thermal_camera:
                    self.args.camera_id = thermal_camera.device_id
                    self.args.width = thermal_camera.resolution[0] if thermal_camera.resolution[0] > 0 else self.args.width
                    self.args.height = thermal_camera.resolution[1] if thermal_camera.resolution[1] > 0 else self.args.height
                else:
                    logger.debug("No thermal camera detected - application will use placeholder")
                    return False

            # Try to open thermal camera
            logger.info(f"Opening thermal camera device {self.args.camera_id}...")
            self.thermal_camera = FLIRBosonCamera(
                device_id=self.args.camera_id,
                resolution=(self.args.width, self.args.height)
            )

            if self.thermal_camera.open():
                actual_res = self.thermal_camera.get_actual_resolution()

                # Validate resolution is thermal-like
                thermal_resolutions = [(640, 512), (320, 256), (512, 640), (256, 320)]
                if actual_res not in thermal_resolutions:
                    logger.warning(f"Warning: Opened camera has resolution {actual_res[0]}x{actual_res[1]} which is not typical for thermal cameras")
                    logger.warning("This may be a regular webcam. Thermal cameras typically use 640x512 or 320x256")

                logger.info(f"[OK] Thermal camera connected: {actual_res[0]}x{actual_res[1]}")
                self.thermal_connected = True
                return True
            else:
                logger.debug("Thermal camera failed to open")
                self.thermal_camera = None
                return False

        except Exception as e:
            logger.debug(f"Thermal camera connection error: {e}")
            self.thermal_camera = None
            return False

    def _try_connect_rgb(self) -> bool:
        """
        Try to detect and connect RGB camera
        Uses camera registry to support manual camera assignments

        Returns:
            True if connected successfully, False otherwise
        """
        try:
            # Check camera registry for manually assigned RGB camera first
            rgb_cam_descriptor = self.camera_registry.get_rgb_camera()
            
            if rgb_cam_descriptor:
                # Manual assignment exists - try to connect to that specific camera
                logger.info(f"Using manually assigned RGB camera: device {rgb_cam_descriptor.device_id}")
                
                # Skip thermal camera device if it exists
                thermal_id = self.thermal_camera.device_id if self.thermal_camera else None
                
                # Use camera factory to create RGB camera
                self.rgb_camera = create_rgb_camera(
                    resolution=rgb_cam_descriptor.resolution,
                    fps=30,
                    camera_type="auto",
                    camera_index=rgb_cam_descriptor.device_id,
                    thermal_device_id=thermal_id
                )
            else:
                # No manual assignment - auto-detect
                logger.info("Auto-detecting RGB cameras...")
                
                # Skip thermal camera device if it exists
                thermal_id = self.thermal_camera.device_id if self.thermal_camera else None
                
                # Use camera factory for auto-detection
                self.rgb_camera = create_rgb_camera(
                    resolution=(640, 480),
                    fps=30,
                    camera_type="auto",
                    thermal_device_id=thermal_id
                )
            
            # Try to open RGB camera
            if self.rgb_camera and self.rgb_camera.open():
                rgb_res = self.rgb_camera.get_actual_resolution()
                self.rgb_available = True
                logger.info(f"[OK] RGB camera connected: {self.rgb_camera.camera_type}")
                logger.info(f"  Resolution: {rgb_res[0]}x{rgb_res[1]}")
                return True
            else:
                logger.debug("RGB camera failed to open")
                self.rgb_camera = None
                self.rgb_available = False
                return False
                
        except Exception as e:
            logger.debug(f"RGB camera connection error: {e}")
            self.rgb_camera = None
            self.rgb_available = False
            return False

    def _initialize_detector_after_thermal_connect(self):
        """Initialize detector after thermal camera connects during runtime"""
        try:
            if not self.thermal_camera:
                return

            detection_mode = getattr(self.args, 'detection_mode', 'edge')
            model_path = getattr(self.args, 'model', None) if detection_mode == 'model' else None
            palette = getattr(self.args, 'palette', 'ironbow')

            self.detector = VPIDetector(
                confidence_threshold=self.args.confidence,
                thermal_palette=palette,
                model_path=model_path,
                detection_mode=detection_mode,
                device=self.device
            )

            if self.detector.initialize():
                self.available_palettes = self.detector.get_available_palettes()
                self.current_palette_idx = self.available_palettes.index(palette) if palette in self.available_palettes else 0
                logger.info("[OK] Detector initialized successfully")
            else:
                logger.error("Failed to initialize detector after thermal connect")
                self.detector = None

        except Exception as e:
            logger.error(f"Error initializing detector: {e}")
            self.detector = None

    def _display_waiting_screen(self):
        """Display waiting screen when no thermal camera connected"""
        import numpy as np

        # Create black screen with message
        screen = np.zeros((720, 1280, 3), dtype=np.uint8)

        # Draw message
        messages = [
            "THERMAL FUSION DRIVING ASSIST",
            "",
            "Waiting for thermal camera...",
            "",
            "Connect FLIR Boson thermal camera",
            "",
            f"Next scan in: {int(self.thermal_scan_interval - (time.time() - self.last_thermal_scan_time))}s",
            "",
            "Press Q to quit"
        ]

        y_start = 200
        for i, msg in enumerate(messages):
            y = y_start + i * 50
            color = (0, 255, 255) if i == 0 else (200, 200, 200)
            font_scale = 1.2 if i == 0 else 0.8
            thickness = 3 if i == 0 else 2

            # Center text
            text_size = cv2.getTextSize(msg, cv2.FONT_HERSHEY_SIMPLEX, font_scale, thickness)[0]
            x = (1280 - text_size[0]) // 2

            cv2.putText(screen, msg, (x, y), cv2.FONT_HERSHEY_SIMPLEX,
                       font_scale, color, thickness)

        # Display
        if self.gui:
            key = self.gui.display(screen)
            if key == ord('q') or key == 27:
                self.running = False

    def initialize(self) -> bool:
        """
        Initialize all components

        PRODUCTION MODE: Gracefully handles zero sensors at startup
        System will wait for thermal camera connection
        """
        logger.info("Initializing Thermal + RGB Fusion Road Monitor...")
        logger.info(f"Platform: {'Jetson' if self.platform_info['is_jetson'] else 'x86-64'} "
                   f"({self.platform_info['machine']})")

        try:
            # 1. Try to detect and connect thermal camera (optional at startup)
            thermal_connected = self._try_connect_thermal()

            if not thermal_connected:
                logger.warning("=" * 60)
                logger.warning("NO THERMAL CAMERA DETECTED")
                logger.warning("System will wait for thermal camera connection...")
                logger.warning("Connect thermal camera and it will auto-detect")
                logger.warning("=" * 60)
                # Don't return False - continue initialization
                # System will poll for thermal camera in main loop

            # 2. Determine actual resolution (use thermal if available, else defaults)
            if self.thermal_connected and self.thermal_camera:
                actual_res = self.thermal_camera.get_actual_resolution()
            else:
                # Use default resolution if no thermal camera
                actual_res = (self.args.width, self.args.height)
                logger.info(f"Using default resolution: {actual_res[0]}x{actual_res[1]}")

            # 3. Detect and initialize RGB camera (optional)
            # Camera factory auto-detects: FLIR Firefly (global shutter) or UVC webcam
            if not self.args.disable_rgb:
                logger.info("Detecting RGB cameras (FLIR Firefly or UVC)...")

                try:
                    # Camera factory auto-detects best available camera
                    # Priority: FLIR Firefly > UVC webcam
                    # Pass thermal device ID to avoid opening the same camera
                    thermal_id = None
                    if self.thermal_connected and self.thermal_camera:
                        thermal_id = self.thermal_camera.device_id
                        logger.info(f"Skipping thermal camera device {thermal_id} during RGB detection")
                    
                    self.rgb_camera = create_rgb_camera(
                        resolution=(640, 480),  # Standard RGB resolution
                        fps=30,
                        camera_type="auto",  # Auto-detect
                        thermal_device_id=thermal_id  # Skip thermal camera
                    )

                    if self.rgb_camera.open():
                        self.rgb_available = True
                        rgb_res = self.rgb_camera.get_actual_resolution()
                        logger.info(f"[OK] RGB camera opened: {self.rgb_camera.camera_type}")
                        logger.info(f"  Resolution: {rgb_res[0]}x{rgb_res[1]}")
                    else:
                        logger.warning("RGB camera failed to open - continuing with thermal only")
                        self.rgb_camera = None
                except RuntimeError as e:
                    logger.info(f"No RGB cameras found: {e}")
                    logger.info("Continuing with thermal only")
                    self.rgb_camera = None
            else:
                logger.info("RGB camera disabled by user")

            # 4. Initialize fusion processor (if RGB available)
            if self.rgb_available:
                calibration_file = getattr(self.args, 'calibration_file', None)
                self.fusion_processor = FusionProcessor(
                    fusion_mode=self.fusion_mode,
                    alpha=self.fusion_alpha,
                    calibration_file=calibration_file
                )
                logger.info(f"Fusion processor initialized (mode: {self.fusion_mode})")

                # Set default view to fusion if RGB available
                self.view_mode = ViewMode.FUSION
            else:
                logger.info("Fusion processor not initialized (no RGB camera)")
                self.view_mode = ViewMode.THERMAL_ONLY

            # 5. Initialize VPI detector (only if thermal connected)
            if self.thermal_connected:
                detection_mode = getattr(self.args, 'detection_mode', 'edge')
                model_path = getattr(self.args, 'model', None) if detection_mode == 'model' else None
                logger.info(f"Initializing VPI detector (mode: {detection_mode}, device: {self.device})...")
                palette = getattr(self.args, 'palette', 'ironbow')

                # Check VPI availability (may not be on x86)
                try:
                    import vpi
                    vpi_available = True
                except ImportError:
                    vpi_available = False
                    logger.warning("VPI not available on this platform - using CPU-only processing")
                    if self.device == 'cuda':
                        logger.info("Forcing device to CPU (VPI not available)")
                        self.device = 'cpu'

                self.detector = VPIDetector(
                    confidence_threshold=self.args.confidence,
                    thermal_palette=palette,
                    model_path=model_path,
                    detection_mode=detection_mode,
                    device=self.device
                )

                if not self.detector.initialize():
                    logger.error("Failed to initialize VPI detector")
                    return False

                self.available_palettes = self.detector.get_available_palettes()
                self.current_palette_idx = self.available_palettes.index(palette) if palette in self.available_palettes else 0
            else:
                logger.info("Detector initialization deferred until thermal camera connects")
                self.detector = None
                self.available_palettes = ['ironbow']  # Default
                self.current_palette_idx = 0

            # 6. Initialize road analyzer with v3.0 features
            enable_distance = getattr(self.args, 'enable_distance', True)
            enable_audio = getattr(self.args, 'enable_audio', True)
            thermal_mode = not self.rgb_available  # Use thermal mode if RGB not available

            # RoadAnalyzer commented out - file removed during transformation
            self.analyzer = None  # Placeholder for compatibility
            # self.analyzer = RoadAnalyzer(
            #     frame_width=actual_res[0],
            #     frame_height=actual_res[1],
            #     enable_distance=enable_distance,
            #     enable_audio=enable_audio,
            #     thermal_mode=thermal_mode
            # )

            # Update vehicle speed if provided (for TTC calculation)
            # vehicle_speed = getattr(self.args, 'vehicle_speed', 0.0)
            # if vehicle_speed > 0:
            #     self.analyzer.update_vehicle_speed(vehicle_speed)
            #     logger.info(f"Vehicle speed set to {vehicle_speed} km/h for TTC calculation")

            # 7. Initialize GUI (Qt is now default)
            use_opencv = getattr(self.args, 'use_opencv_gui', False)
            use_qt = not use_opencv and self.qt_app is not None

            logger.info(f"GUI Selection: use_opencv={use_opencv}, qt_app={'present' if self.qt_app else 'None'}, use_qt={use_qt}")

            if use_qt:
                # Qt GUI - Professional interface (v3.x default)
                from driver_gui_qt import DriverAppWindow
                logger.info("[OK] Using Qt GUI (professional mode)")
                self.gui = DriverAppWindow(app=self)  # Pass self reference for button callbacks
                self.gui_type = 'qt'
                # Qt GUI will be shown in run() method
                logger.info("[OK] Qt GUI window created successfully with app reference")

            else:
                # OpenCV GUI - Legacy fallback (deprecated)
                logger.warning("=" * 70)
                logger.warning("Using LEGACY OpenCV GUI (deprecated)")
                logger.warning("For best experience, use Qt GUI (default)")
                logger.warning("Qt GUI features: multithreading, developer mode, ADAS alerts")
                logger.warning("=" * 70)
                from driver_gui import DriverGUI
                scale_factor = getattr(self.args, 'scale', 2.0)
                self.gui = DriverGUI(
                    window_name="Thermal Fusion Driving Assist",
                    scale_factor=scale_factor
                )
                self.gui_type = 'opencv'

                # Calculate window size
                video_width = int(actual_res[0] * scale_factor)
                video_height = int(actual_res[1] * scale_factor)
                window_width = video_width * 2
                window_height = video_height * 2

                self.gui.create_window(
                    fullscreen=self.args.fullscreen,
                    window_width=window_width,
                    window_height=window_height
                )

                # Set up mouse callback (OpenCV only)
                cv2.setMouseCallback(self.gui.window_name, self._mouse_callback)

            # 8. Initialize performance monitor
            self.perf_monitor = PerformanceMonitor()

            logger.info("Initialization complete!")
            logger.info(f"RGB camera: {'ENABLED' if self.rgb_available else 'DISABLED'}")
            logger.info(f"View mode: {self.view_mode}")
            return True

        except Exception as e:
            logger.error(f"Initialization failed: {e}", exc_info=True)
            return False

    def _detection_worker(self):
        """Background thread for async YOLO detection"""
        logger.info("Detection worker thread started")

        while self.running:
            try:
                if self.yolo_enabled and not self.detection_queue.empty():
                    frame = self.detection_queue.get(timeout=0.1)

                    # Check if detector is available (requires thermal camera connection)
                    if self.detector:
                        self.detector.frame_skip = self.frame_skip_value

                        detections = self.detector.detect(frame, filter_road_objects=True)
                        alerts = []  # Placeholder - analyzer disabled
                        # alerts = self.analyzer.analyze(detections) if self.analyzer else []

                        with self.detection_lock:
                            self.latest_detections = detections
                            self.latest_alerts = alerts

                        self.perf_monitor.update_inference_metrics(
                            self.detector.fps,
                            self.detector.last_inference_time * 1000
                        )
                    else:
                        # No detector available - clear detections
                        with self.detection_lock:
                            self.latest_detections = []
                            self.latest_alerts = []
                elif not self.yolo_enabled:
                    with self.detection_lock:
                        self.latest_detections = []
                        self.latest_alerts = []
                    while not self.detection_queue.empty():
                        try:
                            self.detection_queue.get_nowait()
                        except:
                            break
                    time.sleep(0.05)
                else:
                    time.sleep(0.001)

            except Exception as e:
                logger.error(f"Detection worker error: {e}")
                time.sleep(0.1)

        logger.info("Detection worker thread stopped")

    def _mouse_callback(self, event, x, y, flags, param):
        """Handle mouse clicks on GUI buttons"""
        if event == cv2.EVENT_LBUTTONDOWN:
            button_id = self.gui.check_button_click(x, y)

            if button_id == 'palette_cycle':
                if self.detector:
                    self.current_palette_idx = (self.current_palette_idx + 1) % len(self.available_palettes)
                    new_palette = self.available_palettes[self.current_palette_idx]
                    self.detector.set_palette(new_palette)
                    logger.info(f"Palette changed to: {new_palette}")
                else:
                    logger.warning("Palette change requires thermal camera connection")

            elif button_id == 'yolo_toggle':
                self.yolo_enabled = not self.yolo_enabled
                logger.info(f"YOLO detection {'enabled' if self.yolo_enabled else 'disabled'}")

            elif button_id == 'detection_toggle':
                self.show_detections = not self.show_detections
                logger.info(f"Detection boxes {'enabled' if self.show_detections else 'disabled'}")

            elif button_id == 'buffer_flush_toggle':
                self.buffer_flush_enabled = not self.buffer_flush_enabled
                logger.info(f"Buffer flush {'enabled' if self.buffer_flush_enabled else 'disabled'}")

            elif button_id == 'frame_skip_cycle':
                self.frame_skip_value = (self.frame_skip_value + 1) % 4
                logger.info(f"Frame skip set to: {self.frame_skip_value}")

            elif button_id == 'device_toggle':
                if self.detector:
                    self.device = 'cpu' if self.device == 'cuda' else 'cuda'
                    self.detector.set_device(self.device)
                    logger.info(f"Device switched to: {self.device.upper()}")
                else:
                    logger.warning("Device toggle requires thermal camera connection")

            elif button_id == 'model_cycle':
                if self.detector and not self.model_switching and self.detector.detection_mode == 'model':
                    self.model_switching = True
                    self.current_model_index = (self.current_model_index + 1) % len(self.available_models)
                    new_model = self.available_models[self.current_model_index]
                    self.current_model = new_model
                    logger.info(f"Switching to model: {new_model}")
                    self.detector.load_yolo_model(new_model)
                    self.model_switching = False
                    logger.info(f"Model switched to: {new_model}")
                elif not self.detector:
                    logger.warning("Model switching requires thermal camera connection")

            elif button_id == 'view_mode_cycle':
                # Cycle through view modes
                modes = [ViewMode.THERMAL_ONLY]
                if self.rgb_available:
                    modes.extend([ViewMode.RGB_ONLY, ViewMode.FUSION,
                                 ViewMode.SIDE_BY_SIDE, ViewMode.PICTURE_IN_PICTURE])

                current_idx = modes.index(self.view_mode) if self.view_mode in modes else 0
                next_idx = (current_idx + 1) % len(modes)
                self.view_mode = modes[next_idx]
                self.gui.set_view_mode(self.view_mode)
                logger.info(f"View mode changed to: {self.view_mode}")

            elif button_id == 'fusion_mode_cycle':
                if self.fusion_processor:
                    self.current_fusion_mode_index = (self.current_fusion_mode_index + 1) % len(self.available_fusion_modes)
                    self.fusion_mode = self.available_fusion_modes[self.current_fusion_mode_index]
                    self.fusion_processor.set_fusion_mode(self.fusion_mode)
                    logger.info(f"Fusion mode changed to: {self.fusion_mode}")

            elif button_id == 'fusion_alpha_adjust':
                if self.fusion_processor:
                    # Cycle through alpha values: 0.3, 0.5, 0.7
                    alpha_values = [0.3, 0.5, 0.7]
                    current_idx = min(range(len(alpha_values)),
                                     key=lambda i: abs(alpha_values[i] - self.fusion_alpha))
                    next_idx = (current_idx + 1) % len(alpha_values)
                    self.fusion_alpha = alpha_values[next_idx]
                    self.fusion_processor.set_alpha(self.fusion_alpha)
                    logger.info(f"Fusion alpha set to: {self.fusion_alpha}")

            elif button_id == 'audio_toggle':
                # Toggle audio alerts (v3.0)
                self.audio_enabled = not self.audio_enabled
                if self.analyzer:
                    self.analyzer.set_audio_enabled(self.audio_enabled)
                logger.info(f"Audio alerts {'enabled' if self.audio_enabled else 'disabled'}")

            elif button_id == 'info_toggle':
                # Toggle info panel
                self.show_info_panel = not self.show_info_panel
                logger.info(f"Info panel {'shown' if self.show_info_panel else 'hidden'}")

            elif button_id == 'dev_mode_toggle':
                # Toggle developer mode
                self.developer_mode = self.gui.toggle_developer_mode()
                mode_name = "DEVELOPER" if self.developer_mode else "SIMPLE"
                logger.info(f"GUI mode switched to: {mode_name}")
                logger.info(f"  {'All controls available for configuration' if self.developer_mode else 'Clean interface for driving'}")

            elif button_id == 'theme_toggle':
                # Cycle theme override: AUTO → DARK → LIGHT → AUTO
                from config import get_config
                config = get_config()
                current_override = config.get('theme_override')

                if current_override is None:
                    # AUTO → DARK
                    config.set_theme_override('dark', save=True)
                    logger.info("Theme override: DARK (manual)")
                elif current_override == 'dark':
                    # DARK → LIGHT
                    config.set_theme_override('light', save=True)
                    logger.info("Theme override: LIGHT (manual)")
                elif current_override == 'light':
                    # LIGHT → AUTO
                    config.set_theme_override(None, save=True)
                    logger.info("Theme override: AUTO (time + ambient)")

            elif button_id == 'retry_sensors':
                # Manual sensor retry (v3.4.0)
                logger.info("Manual sensor retry requested...")

                # Reset thermal connection
                if not self.thermal_connected:
                    logger.info("  Retrying thermal camera...")
                    self.last_thermal_scan_time = 0  # Force immediate retry
                else:
                    logger.info("  Thermal camera already connected")

                # Reset RGB connection
                if not self.rgb_available:
                    logger.info("  Retrying RGB camera...")
                    try:
                        from camera_factory import create_rgb_camera
                        # Skip thermal camera device if connected
                        thermal_id = self.args.camera_id if self.thermal_connected and hasattr(self.args, 'camera_id') else None
                        rgb_camera = create_rgb_camera(
                            resolution=(self.args.rgb_width, self.args.rgb_height),
                            fps=self.args.rgb_fps,
                            camera_type=self.args.rgb_camera_type,
                            thermal_device_id=thermal_id
                        )
                        if rgb_camera.open():
                            if hasattr(self, 'rgb_camera') and self.rgb_camera:
                                self.rgb_camera.release()
                            self.rgb_camera = rgb_camera
                            self.rgb_available = True
                            logger.info("  [OK] RGB camera reconnected successfully!")
                        else:
                            logger.warning("  [X] RGB camera failed to open")
                    except Exception as e:
                        logger.warning(f"  [X] RGB camera retry failed: {e}")
                else:
                    logger.info("  RGB camera already connected")

    def run(self):
        """Main application loop"""
        logger.info("Starting main loop...")
        self.running = True

        # Show Qt GUI window if using Qt
        if self.gui_type == 'qt':
            self.gui.show()
            logger.info("Qt GUI window shown")

        # Start async detection worker thread
        self.detection_thread = threading.Thread(target=self._detection_worker, daemon=True)
        self.detection_thread.start()
        logger.info("Async detection thread started")

        try:
            # Phase 3: Use QThread worker for Qt GUI (proper multithreading)
            if self.gui_type == 'qt' and HAS_VIDEO_WORKER:
                logger.info("Phase 3: Starting VideoProcessorWorker thread...")

                # Create and configure worker thread
                self.video_worker = VideoProcessorWorker(self)
                self.gui.connect_worker_signals(self.video_worker)

                # Start worker thread
                self.video_worker.start()
                logger.info("VideoProcessorWorker started - entering Qt event loop")

                # Run Qt event loop (blocks until quit)
                self.qt_app.exec_()

                # Clean shutdown
                logger.info("Qt event loop exited")
                self.video_worker.stop()
                return  # Exit run() method after Qt event loop closes

            # Fallback: Use processEvents() approach (Phase 1) or OpenCV GUI
            while self.running:
                loop_start = time.time()

                # 0. Poll for thermal camera if not connected (hot-plug support)
                if not self.thermal_connected:
                    current_time = time.time()
                    if current_time - self.last_thermal_scan_time > self.thermal_scan_interval:
                        self.last_thermal_scan_time = current_time
                        logger.info("Scanning for thermal camera...")
                        if self._try_connect_thermal():
                            logger.info("[OK] Thermal camera connected! Initializing detector...")
                            # Initialize detector now that thermal is connected
                            self._initialize_detector_after_thermal_connect()
                        else:
                            logger.debug("Thermal camera not found, will retry in 3s...")

                # 1. Capture thermal frame (with disconnect detection)
                # If not connected, create placeholder frame so GUI can still render
                thermal_frame = None
                try:
                    if self.thermal_camera and self.thermal_connected:
                        ret_thermal, thermal_frame = self.thermal_camera.read(flush_buffer=self.buffer_flush_enabled)
                        if not ret_thermal or thermal_frame is None:
                            logger.warning("Thermal camera read failed - camera may have disconnected")
                            self.thermal_connected = False
                            if self.thermal_camera:
                                self.thermal_camera.release()
                            self.thermal_camera = None
                            thermal_frame = None
                except Exception as e:
                    logger.warning(f"Thermal camera error: {e}")
                    logger.warning("Thermal camera disconnected - will attempt reconnection")
                    self.thermal_connected = False
                    if self.thermal_camera:
                        self.thermal_camera.release()
                    self.thermal_camera = None
                    thermal_frame = None

                # Create placeholder or simulated frame if no thermal camera
                if thermal_frame is None:
                    # Use saved resolution or default
                    res = (self.args.width, self.args.height) if hasattr(self, 'args') else (640, 512)

                    # Use simulated thermal frame if enabled (debug mode)
                    if getattr(self, 'use_simulated_thermal', False):
                        thermal_frame = self._generate_simulated_thermal_frame(res)
                        # Log every 30 frames when using simulation
                        if self.frame_count % 30 == 0:
                            logger.debug(f"[SIM] Frame {self.frame_count}: Generated simulated thermal frame {thermal_frame.shape}")
                    else:
                        # Generate "Feed Unavailable" placeholder frame
                        # Note: Placeholder is in RGB format, will be converted to thermal format later
                        placeholder_rgb = create_thermal_placeholder(width=res[0], height=res[1])
                        # Convert to grayscale 16-bit to match thermal camera output
                        placeholder_gray = cv2.cvtColor(placeholder_rgb, cv2.COLOR_BGR2GRAY)
                        thermal_frame = (placeholder_gray.astype(np.uint16) * 256)  # Scale to 16-bit range

                        # DEBUG: Log placeholder dimensions every 30 frames to track variations
                        if self.frame_count % 30 == 0:
                            logger.debug(f"[PLACEHOLDER] Frame {self.frame_count}: Thermal feed unavailable, using placeholder")

                # 2. Capture RGB frame (if available) - with hot-plug support
                rgb_frame = None
                if self.rgb_available and self.rgb_camera:
                    try:
                        ret_rgb, rgb_frame = self.rgb_camera.read(flush_buffer=self.buffer_flush_enabled)
                        if not ret_rgb:
                            rgb_frame = None
                            # Try to reconnect on next iteration
                            logger.warning("RGB camera read failed - will attempt reconnection")
                            self.rgb_available = False
                            if self.rgb_camera:
                                self.rgb_camera.release()
                            self.rgb_camera = None
                    except Exception as e:
                        logger.debug(f"RGB camera read error: {e}")
                        rgb_frame = None
                        self.rgb_available = False
                        if self.rgb_camera:
                            self.rgb_camera.release()
                        self.rgb_camera = None
                elif not self.rgb_available and not getattr(self.args, 'disable_rgb', False):
                    # Auto-retry RGB camera with intelligent retry interval (v3.4.0)
                    from config import get_config
                    config = get_config()

                    # Check if auto-retry is enabled AND fusion mode is active
                    auto_retry_enabled = config.get('auto_retry_sensors', True)
                    fusion_mode_active = self.view_mode in [ViewMode.FUSION, ViewMode.SIDE_BY_SIDE, ViewMode.PICTURE_IN_PICTURE]

                    # Determine retry interval
                    if auto_retry_enabled and fusion_mode_active:
                        # Aggressive retry when fusion mode enabled (config default: every 100 frames)
                        retry_interval = config.get('rgb_retry_interval', 100)
                    else:
                        # Standard retry (every 300 frames = ~10s at 30fps)
                        retry_interval = 300

                    # Try to reconnect RGB camera (hot-plug support)
                    if self.frame_count % retry_interval == 0:
                        logger.info("Attempting to reconnect RGB camera...")
                        try:
                            # Camera factory auto-detects: FLIR Firefly or UVC webcam
                            self.rgb_camera = create_rgb_camera(
                                resolution=(640, 480),
                                fps=30,
                                camera_type="auto"
                            )
                            if self.rgb_camera.open():
                                self.rgb_available = True
                                logger.info(f"[OK] RGB camera reconnected: {self.rgb_camera.camera_type}")
                            else:
                                self.rgb_camera = None
                        except Exception as e:
                            logger.debug(f"RGB reconnection failed: {e}")
                            self.rgb_camera = None

                # 3. Apply thermal color palette
                if self.detector:
                    try:
                        thermal_colored = self.detector.apply_thermal_palette(thermal_frame)
                    except Exception as e:
                        logger.error(f"Error applying palette: {e}")
                        thermal_colored = thermal_frame
                else:
                    # No detector available (no thermal camera) - create grayscale placeholder
                    if len(thermal_frame.shape) == 2:
                        # Convert grayscale to BGR for consistent display
                        thermal_colored = cv2.cvtColor(
                            cv2.normalize(thermal_frame, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8),
                            cv2.COLOR_GRAY2BGR
                        )
                    else:
                        thermal_colored = thermal_frame

                # 4. Create fused frame (if RGB available)
                fusion_frame = None
                if self.rgb_available and rgb_frame is not None and self.fusion_processor:
                    try:
                        fusion_frame = self.fusion_processor.fuse_frames(thermal_colored, rgb_frame)
                    except Exception as e:
                        logger.debug(f"Fusion error: {e}")
                        fusion_frame = None

                # 5. Select frame for detection based on view mode
                if self.view_mode == ViewMode.RGB_ONLY and rgb_frame is not None:
                    detection_frame = rgb_frame
                elif self.view_mode == ViewMode.FUSION and fusion_frame is not None:
                    detection_frame = fusion_frame
                else:
                    detection_frame = thermal_colored

                # 6. Send frame to async detection
                if not self.detection_queue.full():
                    try:
                        self.detection_queue.put_nowait(detection_frame.copy())
                    except:
                        pass

                # 7. Get latest detections
                with self.detection_lock:
                    detections = self.latest_detections.copy()
                    alerts = self.latest_alerts.copy()

                # 8. Update metrics
                if self.frame_count % 5 == 0:
                    self.perf_monitor.update()

                metrics = self.perf_monitor.get_metrics()

                # Calculate smoothed FPS
                loop_time = time.time() - loop_start
                clamped_time = min(loop_time, self.min_frame_time)
                self.frame_times.append(clamped_time)

                if len(self.frame_times) > 0:
                    avg_frame_time = sum(self.frame_times) / len(self.frame_times)
                    self.smoothed_fps = 1.0 / avg_frame_time if avg_frame_time > 0 else 60.0
                    self.smoothed_fps = min(self.smoothed_fps, 60.0)

                metrics['fps'] = self.smoothed_fps

                # 9. Render and display
                try:
                    # Display frame based on GUI type
                    if self.gui_type == 'qt':
                        # Qt GUI: Select frame based on view mode and pass raw frame
                        if self.view_mode == ViewMode.RGB_ONLY and rgb_frame is not None:
                            display_frame = rgb_frame
                        elif self.view_mode == ViewMode.FUSION and fusion_frame is not None:
                            display_frame = fusion_frame
                        elif self.view_mode == ViewMode.SIDE_BY_SIDE:
                            # Create side-by-side view
                            if rgb_frame is not None and thermal_colored.shape[0] == rgb_frame.shape[0]:
                                display_frame = np.hstack([thermal_colored, rgb_frame])
                            else:
                                display_frame = thermal_colored
                        elif self.view_mode == ViewMode.PICTURE_IN_PICTURE and rgb_frame is not None:
                            # Simple PiP: RGB in corner of thermal
                            display_frame = thermal_colored.copy()
                            pip_size = (thermal_colored.shape[1] // 4, thermal_colored.shape[0] // 4)
                            rgb_small = cv2.resize(rgb_frame, pip_size)
                            display_frame[10:10+rgb_small.shape[0], 10:10+rgb_small.shape[1]] = rgb_small
                        else:
                            display_frame = thermal_colored

                        # Draw detections if enabled (before passing to Qt GUI)
                        if self.show_detections and len(detections) > 0:
                            for det in detections:
                                x1, y1, x2, y2 = map(int, det.bbox)
                                # Draw bounding box
                                cv2.rectangle(display_frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                                # Draw label
                                label = f"{det.class_name}: {det.confidence:.2f}"
                                cv2.putText(display_frame, label, (x1, y1 - 10),
                                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

                        # Update Qt GUI (handles its own rendering of controls/overlays)
                        self.gui.update_frame(display_frame)
                        self.gui.update_metrics(
                            fps=self.smoothed_fps,
                            detections=len(detections),
                            thermal_connected=self.thermal_connected,
                            rgb_connected=self.rgb_available
                        )
                        # Update view mode and control states
                        self.gui.set_view_mode(self.view_mode)
                        self.gui.control_panel.set_yolo_enabled(self.yolo_enabled)
                        self.gui.control_panel.set_audio_enabled(self.audio_enabled)
                        # Process Qt events (allows GUI to remain responsive)
                        self.qt_app.processEvents()
                        # Qt GUI doesn't return key codes in the same way, use a small delay
                        time.sleep(0.001)
                    else:
                        # OpenCV GUI: Composite everything into single frame with controls
                        current_palette = self.available_palettes[self.current_palette_idx]
                        display_frame = self.gui.render_frame_with_controls(
                            thermal_frame=thermal_colored,
                            rgb_frame=rgb_frame,
                            fusion_frame=fusion_frame,
                            detections=detections,
                            alerts=alerts,
                            metrics=metrics,
                            show_detections=self.show_detections,
                            current_palette=current_palette,
                            yolo_enabled=self.yolo_enabled,
                            buffer_flush_enabled=self.buffer_flush_enabled,
                            frame_skip_value=self.frame_skip_value,
                            device=self.device,
                            current_model=self.current_model,
                            fusion_mode=self.fusion_mode,
                            fusion_alpha=self.fusion_alpha,
                            audio_enabled=self.audio_enabled,  # v3.0
                            show_info=self.show_info_panel,  # NEW
                            thermal_available=self.thermal_connected,  # NEW
                            rgb_available=self.rgb_available,  # NEW
                            detection_count=len(detections),  # NEW
                            lidar_available=False  # NEW (will be True when LiDAR integrated)
                        )

                        # Display and handle keypress
                        key = self.gui.display(display_frame)
                        self._handle_keypress(key, display_frame)
                except Exception as e:
                    logger.error(f"GUI error: {e}", exc_info=True)

                self.frame_count += 1

                # Print stats
                if self.frame_count % 100 == 0:
                    logger.info(f"Frame {self.frame_count} | FPS: {self.smoothed_fps:.1f} | "
                              f"Detections: {len(detections)} | View: {self.view_mode}")

        except KeyboardInterrupt:
            logger.info("Interrupted by user")
        except Exception as e:
            logger.error(f"Error in main loop: {e}", exc_info=True)
        finally:
            self.shutdown()

    def _handle_keypress(self, key: int, frame):
        """Handle keyboard input"""
        if key == ord('q') or key == 27:
            self.running = False
        elif key == ord('f'):
            self.gui.toggle_fullscreen()
        elif key == ord('d'):
            self.show_detections = not self.show_detections
        elif key == ord('y') or key == ord('Y'):
            self.yolo_enabled = not self.yolo_enabled
            logger.info(f"YOLO detection {'enabled' if self.yolo_enabled else 'disabled'}")
        elif key == ord('v') or key == ord('V'):
            # Cycle view modes
            modes = [ViewMode.THERMAL_ONLY]
            if self.rgb_available:
                modes.extend([ViewMode.RGB_ONLY, ViewMode.FUSION,
                             ViewMode.SIDE_BY_SIDE, ViewMode.PICTURE_IN_PICTURE])
            current_idx = modes.index(self.view_mode) if self.view_mode in modes else 0
            next_idx = (current_idx + 1) % len(modes)
            self.view_mode = modes[next_idx]
            self.gui.set_view_mode(self.view_mode)
            logger.info(f"View mode: {self.view_mode}")
        elif key == ord('s'):
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"screenshot_{timestamp}.png"
            cv2.imwrite(filename, frame)
            logger.info(f"Screenshot saved: {filename}")
        elif key == ord('p'):
            print("\n" + "="*50)
            print(self.perf_monitor.get_summary())
            print("="*50 + "\n")
        elif key == ord('c') or key == ord('C'):
            if self.detector:
                self.current_palette_idx = (self.current_palette_idx + 1) % len(self.available_palettes)
                new_palette = self.available_palettes[self.current_palette_idx]
                self.detector.set_palette(new_palette)
                logger.info(f"Palette: {new_palette}")
            else:
                logger.warning("Palette change requires thermal camera connection")
        elif key == ord('g') or key == ord('G'):
            if self.detector:
                self.device = 'cpu' if self.device == 'cuda' else 'cuda'
                self.detector.set_device(self.device)
                logger.info(f"Device: {self.device.upper()}")
            else:
                logger.warning("Device toggle requires thermal camera connection")
        elif key == ord('a') or key == ord('A'):
            # Toggle audio alerts (v3.0)
            self.audio_enabled = not self.audio_enabled
            if self.analyzer:
                self.analyzer.set_audio_enabled(self.audio_enabled)
            logger.info(f"Audio alerts {'enabled' if self.audio_enabled else 'disabled'}")
        elif key == ord('i') or key == ord('I'):
            # Toggle info panel
            self.show_info_panel = not self.show_info_panel
            logger.info(f"Info panel {'shown' if self.show_info_panel else 'hidden'}")
        elif key == ord('h') or key == ord('H'):
            # Show help overlay (quick reference)
            self._show_help_overlay()
        elif key == ord('b') or key == ord('B'):
            # Toggle detection boxes (moved from button in simple mode)
            self.show_detections = not self.show_detections
            logger.info(f"Detection boxes {'shown' if self.show_detections else 'hidden'}")
        elif key == ord('m') or key == ord('M'):
            # Cycle models (moved from button in simple mode)
            if not self.model_switching and self.detector and self.detector.detection_mode == 'model':
                self.model_switching = True
                self.current_model_index = (self.current_model_index + 1) % len(self.available_models)
                new_model = self.available_models[self.current_model_index]
                self.current_model = new_model
                logger.info(f"Switching to model: {new_model}")
                self.detector.load_yolo_model(new_model)
                self.model_switching = False
                logger.info(f"Model switched to: {new_model}")

    def _show_help_overlay(self):
        """Show keyboard shortcuts help overlay"""
        import numpy as np

        # Create semi-transparent overlay
        help_screen = np.zeros((720, 1280, 3), dtype=np.uint8)

        # Title
        title = "KEYBOARD SHORTCUTS"
        cv2.putText(help_screen, title, (400, 80),
                   cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 255, 255), 3)

        # Shortcuts (2 columns)
        shortcuts_left = [
            ("V", "Cycle view modes"),
            ("D", "Toggle detection boxes"),
            ("Y", "Toggle YOLO"),
            ("A", "Toggle audio"),
            ("C", "Cycle thermal palette"),
            ("M", "Cycle models"),
        ]

        shortcuts_right = [
            ("I", "Toggle info panel"),
            ("B", "Toggle boxes"),
            ("S", "Screenshot"),
            ("P", "Print stats"),
            ("F", "Fullscreen"),
            ("H", "This help"),
            ("Q/ESC", "Quit"),
        ]

        # Draw left column
        y = 150
        for key, desc in shortcuts_left:
            cv2.putText(help_screen, f"{key}", (200, y),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
            cv2.putText(help_screen, f"- {desc}", (280, y),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (200, 200, 200), 1)
            y += 60

        # Draw right column
        y = 150
        for key, desc in shortcuts_right:
            cv2.putText(help_screen, f"{key}", (700, y),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
            cv2.putText(help_screen, f"- {desc}", (780, y),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (200, 200, 200), 1)
            y += 60

        # GUI modes section
        y += 40
        cv2.putText(help_screen, "GUI MODES:", (200, y),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.9, (100, 150, 255), 2)
        y += 50
        cv2.putText(help_screen, "SIMPLE MODE - Clean interface for driving (default)", (220, y),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.65, (200, 200, 200), 1)
        y += 40
        cv2.putText(help_screen, "DEV MODE - Full controls for configuration when stationary", (220, y),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.65, (200, 200, 200), 1)
        y += 50
        cv2.putText(help_screen, "Click 'DEV MODE' button or 'SIMPLE' button to toggle", (220, y),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 100), 1)

        # Footer
        cv2.putText(help_screen, "Press any key to close", (450, 650),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.8, (100, 100, 100), 1)

        # Display and wait for key
        if self.gui:
            self.gui.display(help_screen)
            cv2.waitKey(0)

    def shutdown(self):
        """Cleanup resources"""
        logger.info("Shutting down...")

        self.running = False
        if self.detection_thread and self.detection_thread.is_alive():
            logger.info("Waiting for detection thread...")
            self.detection_thread.join(timeout=2.0)

        if self.thermal_camera:
            self.thermal_camera.release()
        if self.rgb_camera:
            self.rgb_camera.release()
        if self.detector:
            self.detector.release()
        if self.analyzer:
            # Cleanup audio system (v3.0)
            self.analyzer.cleanup()
        if self.gui:
            self.gui.close()
        if self.perf_monitor:
            self.perf_monitor.release()
        logger.info("Shutdown complete")


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="FLIR Boson Thermal + RGB Fusion Road Monitor",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    # Camera options
    parser.add_argument('--camera-id', type=int, default=None,
                       help='Thermal camera device ID (auto-detect if not specified)')
    parser.add_argument('--width', type=int, default=640, help='Camera frame width')
    parser.add_argument('--height', type=int, default=512, help='Camera frame height')
    parser.add_argument('--disable-rgb', action='store_true',
                       help='Disable RGB camera (thermal only mode)')

    # Detection options
    parser.add_argument('--confidence', type=float, default=0.25,
                       help='Detection confidence threshold')
    parser.add_argument('--detection-mode', type=str, default='model',
                       choices=['edge', 'model'], help='Detection mode')
    parser.add_argument('--model', type=str, default='yolov8n.pt',
                       help='YOLO model path')
    parser.add_argument('--device', type=str, default='cuda',
                       choices=['cuda', 'cpu'], help='Processing device')

    # Display options
    parser.add_argument('--fullscreen', action='store_true', help='Start in fullscreen')
    parser.add_argument('--scale', type=float, default=2.0, help='Display scale factor')
    parser.add_argument('--palette', type=str, default='ironbow',
                       choices=['white_hot', 'black_hot', 'ironbow', 'rainbow',
                               'arctic', 'lava', 'medical', 'plasma'],
                       help='Thermal color palette')

    # Fusion options
    parser.add_argument('--fusion-mode', type=str, default='alpha_blend',
                       choices=['alpha_blend', 'edge_enhanced', 'thermal_overlay',
                               'side_by_side', 'picture_in_picture', 'max_intensity',
                               'feature_weighted'],
                       help='Fusion algorithm')
    parser.add_argument('--fusion-alpha', type=float, default=0.5,
                       help='Fusion blend ratio (0.0=RGB, 1.0=Thermal)')
    parser.add_argument('--calibration-file', type=str, default=None,
                       help='Camera calibration file (JSON)')

    # v3.0 Advanced ADAS options
    parser.add_argument('--enable-distance', action='store_true', default=True,
                       help='Enable distance estimation (default: True)')
    parser.add_argument('--disable-distance', dest='enable_distance', action='store_false',
                       help='Disable distance estimation')
    parser.add_argument('--enable-audio', action='store_true', default=True,
                       help='Enable audio alerts (default: True)')
    parser.add_argument('--disable-audio', dest='enable_audio', action='store_false',
                       help='Disable audio alerts')
    parser.add_argument('--audio-volume', type=float, default=0.7,
                       help='Audio alert volume (0.0-1.0, default: 0.7)')
    parser.add_argument('--vehicle-speed', type=float, default=0.0,
                       help='Vehicle speed in km/h for TTC calculation (default: 0)')

    # GUI options (Qt is now default)
    parser.add_argument('--use-opencv-gui', action='store_true',
                       help='Use legacy OpenCV GUI instead of Qt (not recommended)')

    return parser.parse_args()


def main():
    print("""
╔══════════════════════════════════════════════════════════════╗
║   FLIR Thermal + RGB Fusion Road Monitor v3.5              ║
║   Qt Professional GUI | Jetson Orin & x86-64               ║
╠══════════════════════════════════════════════════════════════╣
║  Keyboard Controls:                                          ║
║    Q/ESC - Quit          F - Fullscreen      D - Detections  ║
║    Y - Toggle YOLO       V - Cycle Views     S - Screenshot  ║
║    C - Cycle Palettes    G - Device Toggle   P - Stats       ║
║    A - Toggle Audio      (v3.0 Audio Alerts)                ║
║                                                               ║
║  GUI Buttons (click):                                        ║
║    Row 1: PAL, YOLO, BOX, DEV, MODEL                        ║
║    Row 2: FLUSH, AUDIO, SKIP, VIEW, FUS, α                  ║
║                                                               ║
║  View Modes: Thermal, RGB, Fusion, Side-by-Side, PIP       ║
║  Fusion Modes: Alpha Blend, Edge Enhanced, Thermal Overlay  ║
║                Side-by-Side, PIP, Max Intensity, Weighted   ║
║                                                               ║
║  v3.0 Smart Features:                                        ║
║    • Distance estimation with TTC warnings                   ║
║    • ISO 26262 compliant audio alerts (1.5-2 kHz)          ║
║    • RED PULSE alerts on sides for pedestrians/animals      ║
║    • Directional proximity warnings (left/right/center)     ║
║    • Multi-view support for optimal situational awareness   ║
╚══════════════════════════════════════════════════════════════╝
    """)

    args = parse_arguments()

    # Initialize QApplication (Qt GUI is now default)
    qt_app = None
    use_opencv = getattr(args, 'use_opencv_gui', False)

    if not use_opencv:
        try:
            from PyQt5.QtWidgets import QApplication
            qt_app = QApplication(sys.argv)
            qt_app.setApplicationName("Thermal Fusion Driving Assist")
            logger.info("QApplication initialized (Qt GUI)")
        except ImportError:
            logger.error("=" * 70)
            logger.error("PyQt5 is required but not installed!")
            logger.error("Install with: pip install PyQt5")
            logger.error("Or use legacy OpenCV GUI with: --use-opencv-gui")
            logger.error("=" * 70)
            sys.exit(1)

    app = ThermalRoadMonitorFusion(args, qt_app=qt_app)

    if not app.initialize():
        logger.error("Failed to initialize application")
        sys.exit(1)

    app.run()
    sys.exit(0)


if __name__ == "__main__":
    main()
