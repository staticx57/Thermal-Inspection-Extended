#!/usr/bin/env python3
"""
VideoProcessorWorker - QThread for async vision processing (Phase 3)
Separates vision processing from GUI thread for optimal performance
"""
import time
import logging
import numpy as np
import cv2
from PyQt5.QtCore import QThread, pyqtSignal
from view_mode import ViewMode
from config import get_config
from placeholder_frames import create_thermal_placeholder, create_rgb_placeholder

logger = logging.getLogger(__name__)


class VideoProcessorWorker(QThread):
    """
    Background thread for vision processing (thermal, RGB, fusion, detection)
    Emits signals to update GUI in main thread (thread-safe)
    """
    # Signals for thread-safe communication
    frame_ready = pyqtSignal(np.ndarray)  # Processed frame ready for display
    metrics_update = pyqtSignal(dict)  # FPS and detection metrics

    def __init__(self, app):
        """
        Args:
            app: Reference to ThermalRoadMonitorFusion instance
        """
        super().__init__()
        self.app = app
        self.running = False

        # Load object importance settings for thermal colorization
        config = get_config()
        self.object_importance = {}
        for obj_type in ['person', 'bicycle', 'motorcycle', 'dog', 'cat', 'car', 'truck', 'bus',
                         'traffic light', 'stop sign', 'bird', 'motion', 'horse', 'cow', 'sheep',
                         'elephant', 'bear', 'zebra', 'giraffe']:
            self.object_importance[obj_type] = config.get(f'object_importance.{obj_type}', 'medium')

    def run(self):
        """Main vision processing loop (runs in background thread)"""
        logger.info("VideoProcessorWorker thread started")
        self.running = True

        # Log platform-specific frame rate target
        is_jetson = hasattr(self.app, 'platform_info') and self.app.platform_info.get('is_jetson', False)
        target_fps = 20 if is_jetson else 30
        platform_name = "Jetson Orin" if is_jetson else "x86-64"
        logger.info(f"Platform: {platform_name}, Target FPS: {target_fps} (adaptive throttling)")

        while self.running:
            loop_start = time.time()

            # 0. Poll for thermal camera if not connected (hot-plug support)
            if not self.app.thermal_connected:
                current_time = time.time()
                if current_time - self.app.last_thermal_scan_time > self.app.thermal_scan_interval:
                    self.app.last_thermal_scan_time = current_time
                    logger.info("Scanning for thermal camera...")
                    if self.app._try_connect_thermal():
                        logger.info("[OK] Thermal camera connected! Initializing detector...")
                        self.app._initialize_detector_after_thermal_connect()
                    else:
                        logger.debug("Thermal camera not found, will retry in 3s...")

            # 1. Capture thermal frame (with disconnect detection)
            thermal_frame = None
            try:
                if self.app.thermal_camera and self.app.thermal_connected:
                    ret_thermal, thermal_frame = self.app.thermal_camera.read(flush_buffer=self.app.buffer_flush_enabled)
                    if not ret_thermal or thermal_frame is None:
                        logger.warning("Thermal camera read failed - camera may have disconnected")
                        self.app.thermal_connected = False
                        if self.app.thermal_camera:
                            self.app.thermal_camera.release()
                        self.app.thermal_camera = None
                        thermal_frame = None
            except Exception as e:
                logger.warning(f"Thermal camera error: {e}")
                logger.warning("Thermal camera disconnected - will attempt reconnection")
                self.app.thermal_connected = False
                if self.app.thermal_camera:
                    self.app.thermal_camera.release()
                self.app.thermal_camera = None
                thermal_frame = None

            # Create placeholder frame if no thermal camera
            if thermal_frame is None:
                res = (self.app.args.width, self.app.args.height) if hasattr(self.app, 'args') else (640, 512)
                # Generate "Feed Unavailable" placeholder frame
                placeholder_rgb = create_thermal_placeholder(width=res[0], height=res[1])
                # Convert to grayscale 16-bit to match thermal camera output
                placeholder_gray = cv2.cvtColor(placeholder_rgb, cv2.COLOR_BGR2GRAY)
                thermal_frame = (placeholder_gray.astype(np.uint16) * 256)  # Scale to 16-bit range

            # 2. Capture RGB frame (if available) - with hot-plug support
            rgb_frame = None
            if self.app.rgb_available and self.app.rgb_camera:
                try:
                    ret_rgb, rgb_frame = self.app.rgb_camera.read(flush_buffer=self.app.buffer_flush_enabled)
                    if not ret_rgb:
                        rgb_frame = None
                        logger.warning("RGB camera read failed - will attempt reconnection")
                        self.app.rgb_available = False
                        if self.app.rgb_camera:
                            self.app.rgb_camera.release()
                        self.app.rgb_camera = None
                except Exception as e:
                    logger.debug(f"RGB camera read error: {e}")
                    rgb_frame = None
                    self.app.rgb_available = False
                    if self.app.rgb_camera:
                        self.app.rgb_camera.release()
                    self.app.rgb_camera = None
            elif not self.app.rgb_available and not getattr(self.app.args, 'disable_rgb', False):
                # Auto-retry RGB camera with intelligent retry interval
                from config import get_config
                config = get_config()

                auto_retry_enabled = config.get('auto_retry_sensors', True)
                fusion_mode_active = self.app.view_mode in [ViewMode.FUSION, ViewMode.SIDE_BY_SIDE, ViewMode.PICTURE_IN_PICTURE]

                if auto_retry_enabled and fusion_mode_active:
                    retry_interval = config.get('rgb_retry_interval', 100)
                else:
                    retry_interval = 300

                if self.app.frame_count % retry_interval == 0:
                    logger.info("Attempting to reconnect RGB camera...")
                    try:
                        from camera_factory import create_rgb_camera
                        self.app.rgb_camera = create_rgb_camera(
                            resolution=(640, 480),
                            fps=30,
                            camera_type="auto",
                            thermal_device_id=self.app.args.camera_id  # Skip thermal camera
                        )
                        if self.app.rgb_camera.open():
                            self.app.rgb_available = True
                            logger.info(f"[OK] RGB camera reconnected: {self.app.rgb_camera.camera_type}")
                        else:
                            self.app.rgb_camera = None
                    except Exception as e:
                        logger.debug(f"RGB reconnection failed: {e}")
                        self.app.rgb_camera = None

            # 3. Apply thermal color palette
            if self.app.detector:
                try:
                    thermal_colored = self.app.detector.apply_thermal_palette(thermal_frame)
                except Exception as e:
                    logger.error(f"Error applying palette: {e}")
                    thermal_colored = thermal_frame
            else:
                if len(thermal_frame.shape) == 2:
                    thermal_colored = cv2.cvtColor(
                        cv2.normalize(thermal_frame, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8),
                        cv2.COLOR_GRAY2BGR
                    )
                else:
                    thermal_colored = thermal_frame

            # 4. Create fused frame (if RGB available)
            fusion_frame = None
            if self.app.rgb_available and rgb_frame is not None and self.app.fusion_processor:
                try:
                    fusion_frame = self.app.fusion_processor.fuse_frames(thermal_colored, rgb_frame)
                except Exception as e:
                    logger.debug(f"Fusion error: {e}")
                    fusion_frame = None

            # 5. Select frame for detection based on view mode
            if self.app.view_mode == ViewMode.RGB_ONLY and rgb_frame is not None:
                detection_frame = rgb_frame
            elif self.app.view_mode == ViewMode.FUSION and fusion_frame is not None:
                detection_frame = fusion_frame
            else:
                detection_frame = thermal_colored

            # 6. Send frame to async detection
            if not self.app.detection_queue.full():
                try:
                    self.app.detection_queue.put_nowait(detection_frame.copy())
                except:
                    pass

            # 7. Get latest detections
            with self.app.detection_lock:
                detections = self.app.latest_detections.copy()
                alerts = self.app.latest_alerts.copy()

            # 8. Update metrics
            if self.app.frame_count % 5 == 0:
                self.app.perf_monitor.update()

            metrics = self.app.perf_monitor.get_metrics()

            # Calculate smoothed FPS
            loop_time = time.time() - loop_start
            clamped_time = min(loop_time, self.app.min_frame_time)
            self.app.frame_times.append(clamped_time)

            if len(self.app.frame_times) > 0:
                avg_frame_time = sum(self.app.frame_times) / len(self.app.frame_times)
                self.app.smoothed_fps = 1.0 / avg_frame_time if avg_frame_time > 0 else 60.0
                self.app.smoothed_fps = min(self.app.smoothed_fps, 60.0)

            metrics['fps'] = self.app.smoothed_fps

            # 9. Select display frame based on view mode
            if self.app.view_mode == ViewMode.RGB_ONLY:
                if rgb_frame is not None:
                    display_frame = rgb_frame
                else:
                    # Show RGB placeholder when RGB camera unavailable
                    display_frame = create_rgb_placeholder(width=640, height=480)
            elif self.app.view_mode == ViewMode.FUSION:
                if fusion_frame is not None:
                    display_frame = fusion_frame
                elif rgb_frame is None:
                    # Show thermal with message that RGB is unavailable for fusion
                    display_frame = thermal_colored.copy()
                    cv2.putText(display_frame, "RGB Feed Unavailable - Fusion Disabled",
                               (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2, cv2.LINE_AA)
                else:
                    display_frame = thermal_colored
            elif self.app.view_mode == ViewMode.SIDE_BY_SIDE:
                thermal_h, thermal_w = thermal_colored.shape[:2]

                if rgb_frame is not None:
                    # Resize RGB to match thermal height if needed
                    rgb_h, rgb_w = rgb_frame.shape[:2]

                    if rgb_h != thermal_h:
                        # Maintain aspect ratio: resize to match height
                        new_w = int(rgb_w * thermal_h / rgb_h)
                        rgb_resized = cv2.resize(rgb_frame, (new_w, thermal_h))
                    else:
                        rgb_resized = rgb_frame
                else:
                    # Create RGB placeholder matching thermal height
                    rgb_placeholder = create_rgb_placeholder(width=thermal_w, height=thermal_h)
                    rgb_resized = rgb_placeholder

                display_frame = np.hstack([thermal_colored, rgb_resized])
            elif self.app.view_mode == ViewMode.PICTURE_IN_PICTURE:
                display_frame = thermal_colored.copy()
                pip_size = (thermal_colored.shape[1] // 4, thermal_colored.shape[0] // 4)

                if rgb_frame is not None:
                    rgb_small = cv2.resize(rgb_frame, pip_size)
                else:
                    # Show small RGB placeholder in PIP corner
                    rgb_small = cv2.resize(create_rgb_placeholder(width=640, height=480), pip_size)

                display_frame[10:10+rgb_small.shape[0], 10:10+rgb_small.shape[1]] = rgb_small
            else:
                display_frame = thermal_colored

            # Draw detections if enabled
            if self.app.show_detections and len(detections) > 0:
                h, w = display_frame.shape[:2]

                for det in detections:
                    try:
                        x1, y1, x2, y2 = map(int, det.bbox)
                        # Clamp coordinates to frame bounds to prevent crashes
                        x1 = max(0, min(x1, w - 1))
                        y1 = max(0, min(y1, h - 1))
                        x2 = max(0, min(x2, w - 1))
                        y2 = max(0, min(y2, h - 1))

                        # Only draw if box is valid (has area)
                        if x2 > x1 and y2 > y1:
                            # Determine color based on thermal colorization mode
                            if getattr(self.app, 'thermal_colorize_mode', False):
                                # Color-code by object importance level (configurable)
                                importance = self.object_importance.get(det.class_name, 'medium')

                                if importance == 'critical':
                                    box_color = (0, 0, 255)  # Red (BGR) - Critical
                                elif importance == 'high':
                                    box_color = (0, 255, 255)  # Yellow (BGR) - High
                                else:  # medium, low, info, ignore
                                    box_color = (255, 255, 0)  # Cyan (BGR) - Info

                                # Intensity-based colored overlay
                                # Extract bounding box region
                                roi = display_frame[y1:y2, x1:x2].copy()

                                # Convert to grayscale to get intensity
                                if len(roi.shape) == 3:
                                    gray_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
                                else:
                                    gray_roi = roi

                                # Normalize intensity to 0-1 range
                                intensity = gray_roi.astype(float) / 255.0

                                # Create colored overlay for the ROI
                                colored_roi = np.zeros_like(roi)
                                colored_roi[:, :] = box_color

                                # Apply intensity-based alpha blending
                                # Higher intensity (brighter/hotter) = more color
                                # Lower intensity (darker/cooler) = less color
                                for c in range(3):  # For each color channel
                                    roi_float = roi[:, :, c].astype(float)
                                    colored_float = colored_roi[:, :, c].astype(float)
                                    # Blend with intensity as alpha (0.4 max to avoid oversaturation)
                                    blended = roi_float * (1 - intensity * 0.4) + colored_float * (intensity * 0.4)
                                    roi[:, :, c] = np.clip(blended, 0, 255).astype(np.uint8)

                                # Put the blended ROI back into the display frame
                                display_frame[y1:y2, x1:x2] = roi
                            else:
                                # Default green
                                box_color = (0, 255, 0)

                            cv2.rectangle(display_frame, (x1, y1), (x2, y2), box_color, 2)
                            label = f"{det.class_name}: {det.confidence:.2f}"
                            # Ensure label position is within frame
                            label_y = max(10, y1 - 10)
                            cv2.putText(display_frame, label, (x1, label_y),
                                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, box_color, 2)
                    except Exception as e:
                        logger.error(f"Error drawing detection box: {e}")

            # 10. Emit signals to GUI (thread-safe)
            self.frame_ready.emit(display_frame)

            # Collect comprehensive metrics for developer panel
            comprehensive_metrics = {
                # Performance
                'fps': self.app.smoothed_fps,
                'frame_count': self.app.frame_count,

                # System resources (from PerformanceMonitor)
                'cpu_usage': metrics.get('cpu_usage', 0.0),
                'gpu_usage': metrics.get('gpu_usage', 0.0),
                'memory_usage': metrics.get('memory_usage', 0.0),
                'memory_used_mb': metrics.get('memory_used_mb', 0),
                'memory_total_mb': metrics.get('memory_total_mb', 0),
                'temperature': metrics.get('temperature', 0.0),
                'power_watts': metrics.get('power_watts', 0.0),

                # Camera status
                'thermal_connected': self.app.thermal_connected,
                'rgb_connected': self.app.rgb_available,
                'thermal_resolution': f"{self.app.args.width}x{self.app.args.height}" if hasattr(self.app, 'args') else 'N/A',
                'rgb_resolution': '640x480' if self.app.rgb_available else 'N/A',

                # Detection
                'detections': len(detections),
                'yolo_enabled': self.app.yolo_enabled if hasattr(self.app, 'yolo_enabled') else False,
                'inference_time_ms': metrics.get('inference_time_ms', 0.0),
                'frame_skip': self.app.frame_skip_value if hasattr(self.app, 'frame_skip_value') else 1,
                'device': self.app.device if hasattr(self.app, 'device') else 'CPU',

                # View mode
                'view_mode': str(self.app.view_mode) if hasattr(self.app, 'view_mode') else 'thermal',
                'fusion_mode': self.app.fusion_mode if hasattr(self.app, 'fusion_mode') else 'overlay',
                'fusion_alpha': self.app.fusion_alpha if hasattr(self.app, 'fusion_alpha') else 0.5,

                # Threading
                'gui_type': self.app.gui_type if hasattr(self.app, 'gui_type') else 'Qt',
                'worker_running': self.running,
                'detection_thread_alive': self.app.detection_thread.is_alive() if hasattr(self.app, 'detection_thread') and self.app.detection_thread else False,

                # ADAS Alerts (for alert overlay)
                'alerts': alerts,
                'detections_list': detections,

                # RGB frame for auto day/night ambient light detection
                'rgb_frame': rgb_frame if rgb_frame is not None and self.app.rgb_available else None,
            }

            self.metrics_update.emit(comprehensive_metrics)

            self.app.frame_count += 1

            # Frame rate limiting: Adaptive based on platform
            # Jetson: 20 FPS (thermal/power constrained, YOLO inference time)
            # x86: 30 FPS (more headroom, faster inference)
            # Prevents CPU spinning and Qt event queue flooding
            loop_time = time.time() - loop_start

            # Determine target FPS based on platform
            is_jetson = hasattr(self.app, 'platform_info') and self.app.platform_info.get('is_jetson', False)
            target_fps = 20 if is_jetson else 30
            target_frame_time = 1.0 / target_fps

            sleep_time = target_frame_time - loop_time
            throttle_active = sleep_time > 0
            if throttle_active:
                time.sleep(sleep_time)

            # Print stats with performance debug info
            if self.app.frame_count % 100 == 0:
                actual_loop_time = loop_time + (sleep_time if throttle_active else 0)
                throttle_status = "[OK]" if throttle_active else "[X] OVERRUN"
                logger.info(
                    f"Frame {self.app.frame_count} | "
                    f"FPS: {self.app.smoothed_fps:.1f}/{target_fps} | "
                    f"Loop: {loop_time*1000:.1f}ms | "
                    f"Throttle: {throttle_status} | "
                    f"Detections: {len(detections)} | "
                    f"View: {self.app.view_mode}"
                )

    def stop(self):
        """Stop the worker thread gracefully"""
        logger.info("Stopping VideoProcessorWorker...")
        self.running = False
        self.wait()  # Wait for thread to finish
        logger.info("VideoProcessorWorker stopped")
