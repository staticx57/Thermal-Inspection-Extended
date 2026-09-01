"""
Threaded Camera Capture for Thermal Inspection
Provides non-blocking camera frame capture using background threads
"""
import threading
import time
import logging
from typing import Optional, Tuple
import cv2
import numpy as np

logger = logging.getLogger(__name__)


class ThreadedCameraCapture:
    """
    Non-blocking camera capture using background thread.
    Continuously captures frames in background and provides latest frame on demand.
    """

    def __init__(self, camera, name: str = "Camera"):
        """
        Initialize threaded camera capture.

        Args:
            camera: Camera object with read() method
            name: Camera name for logging
        """
        self.camera = camera
        self.name = name
        self.latest_frame = None       # 8-bit BGR — always display-safe
        self.latest_raw_frame = None   # raw read (uint16 when radiometric)
        self.latest_timestamp = 0
        self.frame_lock = threading.Lock()
        self.running = False
        self.thread = None
        self.fps = 0.0
        self.frame_count = 0
        self.error_count = 0
        self.consecutive_errors = 0

    def start(self):
        """Start background capture thread."""
        if self.running:
            logger.warning(f"{self.name}: Already running")
            return

        if self.camera is None:
            logger.warning(f"{self.name}: No camera object provided - capture thread will not start")
            return

        self.running = True
        self.thread = threading.Thread(target=self._capture_loop, daemon=True, name=f"{self.name}Thread")
        self.thread.start()
        logger.info(f"{self.name}: Background capture thread started")

    def _capture_loop(self):
        """Background thread: continuously capture frames.

        Prefers ``read_thermal()`` when the camera supports it so that
        16-bit radiometric data is *not* degraded to 8-bit during capture.
        The raw frame (possibly uint16) is stored in ``latest_raw_frame``;
        ``latest_frame`` always holds an 8-bit/BGR display-safe copy.
        """
        last_time = time.time()
        frame_times = []

        while self.running:
            try:
                # Prefer read_thermal() to preserve 16-bit data
                if hasattr(self.camera, 'read_thermal'):
                    ret, frame = self.camera.read_thermal()
                else:
                    ret, frame = self.camera.read()

                if ret and frame is not None:
                    # Build a display-safe 8-bit BGR copy when the raw
                    # frame is 16-bit (radiometric T-Linear data).
                    if frame.dtype == np.uint16:
                        # Normalise to 8-bit for display; keep raw for analysis
                        display = cv2.normalize(
                            frame, None, 0, 255, cv2.NORM_MINMAX, dtype=cv2.CV_8U
                        )
                        if len(display.shape) == 2:
                            display = cv2.cvtColor(display, cv2.COLOR_GRAY2BGR)
                    else:
                        display = frame

                    # No .copy() here. This was tried once before and
                    # reverted out of caution (a live detail-loss report
                    # arrived around the same time, and the assumption
                    # hadn't been checked against every backend yet) - the
                    # actual cause of that report was unrelated (a Tau2
                    # colorization bug, since fixed). Every read()/
                    # read_thermal() implementation in this codebase has
                    # since been individually checked:
                    #   - RGBCameraUVC, OpenCVThermalBackend, Tau2Camera,
                    #     flir_camera.py, gige_camera.py, and flirpy's own
                    #     Boson.grab() are all thin wrappers around
                    #     cv2.VideoCapture.read(), which hands back a fresh
                    #     buffer every call.
                    #   - pyusb_thermal_backend.py builds its frame via
                    #     np.frombuffer() on a freshly-read USB transfer
                    #     each call, not a pooled/reused buffer.
                    #   - rgb_camera_firefly.py (PySpin/Spinnaker) was the
                    #     one real exception: GetNDArray() returns a VIEW
                    #     into Spinnaker's own buffer, and the immediately-
                    #     following Release() call returns that buffer to
                    #     Spinnaker's pool for reuse by the very next
                    #     GetNextImage() - fixed at the source (see that
                    #     file) by copying before releasing, so its
                    #     contract now matches every other backend's.
                    # With that guarantee actually verified, two full
                    # ~25MB memcpys held under frame_lock (frame and
                    # display were literally the same object for a non-
                    # uint16 RGB camera, so this copied identical data
                    # twice) is what measured as the dominant cause of
                    # jitter at 4K: the main thread's get_frame() could
                    # block for tens of ms whenever its poll landed
                    # mid-copy. A reference assignment is O(1) instead of
                    # O(resolution), so the lock is now held for
                    # microseconds regardless of frame size.
                    with self.frame_lock:
                        self.latest_raw_frame = frame   # 16-bit or 8-bit original
                        self.latest_frame = display     # always 8-bit BGR
                        self.latest_timestamp = time.time()
                        self.frame_count += 1

                    self.consecutive_errors = 0

                    # Calculate FPS
                    current_time = time.time()
                    frame_times.append(current_time - last_time)
                    if len(frame_times) > 30:
                        frame_times.pop(0)
                    avg_time = sum(frame_times) / len(frame_times)
                    self.fps = 1.0 / avg_time if avg_time > 0 else 0
                    last_time = current_time
                else:
                    self.error_count += 1
                    self.consecutive_errors += 1
                    if self.error_count % 10 == 0:
                        logger.warning(
                            f"{self.name}: Frame capture failed "
                            f"({self.error_count} errors)"
                        )
                    # Escalating backoff (1ms -> 250ms cap) instead of a
                    # flat 1ms retry forever. A camera that's genuinely gone
                    # (unplugged, grabbed exclusively by another process)
                    # was retrying at ~1000Hz indefinitely, pegging a full
                    # CPU core and directly competing with the Qt main
                    # thread's frame-processing loop for CPU time - this is
                    # what a "buttery smooth Windows Camera app, jumpy here"
                    # comparison was partly seeing. Still recovers fast
                    # (1-2ms) from a single transient dropped frame.
                    backoff = min(0.001 * (2 ** min(self.consecutive_errors, 8)), 0.25)
                    time.sleep(backoff)

            except Exception as e:
                logger.error(f"{self.name}: Capture error: {e}")
                time.sleep(0.01)

    def get_frame(self) -> Tuple[bool, Optional[np.ndarray], float]:
        """
        Get latest display-safe (8-bit BGR) frame (non-blocking).

        Returns:
            (success, frame, timestamp) tuple

        No copy here: the capture loop above already does `display.copy()`
        before publishing to self.latest_frame, so what's published is
        never mutated in place afterward - only ever replaced wholesale on
        the next captured frame. A second defensive copy on every read was
        pure redundant memcpy that scaled with resolution: at 4K (~25MB/
        frame) and a ~100Hz main-loop poll rate, that's ~2.5GB/s of memcpy
        for a copy nothing needed, measured as the dominant cause of FPS
        dropping with RGB resolution independent of fusion mode.
        """
        with self.frame_lock:
            if self.latest_frame is not None:
                return True, self.latest_frame, self.latest_timestamp
            else:
                return False, None, 0

    def get_raw_frame(self) -> Tuple[bool, Optional[np.ndarray], float]:
        """
        Get latest raw frame, which may be uint16 for radiometric cameras
        (non-blocking). See get_frame() - same no-copy reasoning applies.

        Returns:
            (success, raw_frame, timestamp) tuple
        """
        with self.frame_lock:
            if self.latest_raw_frame is not None:
                return True, self.latest_raw_frame, self.latest_timestamp
            else:
                return False, None, 0

    def stop(self):
        """Stop background capture thread."""
        if not self.running:
            return

        logger.info(f"{self.name}: Stopping background thread...")
        self.running = False

        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2.0)

        logger.info(f"{self.name}: Stopped (captured {self.frame_count} frames, {self.error_count} errors)")

    def get_stats(self) -> dict:
        """Get capture statistics."""
        return {
            'fps': self.fps,
            'frame_count': self.frame_count,
            'error_count': self.error_count,
            'running': self.running
        }


class DualThreadedCameraCapture:
    """
    Dual-camera threaded capture for thermal + RGB cameras.
    Captures both cameras in parallel using separate threads.
    """

    def __init__(self, thermal_camera, rgb_camera=None):
        """
        Initialize dual camera capture.

        Args:
            thermal_camera: Thermal camera object
            rgb_camera: RGB camera object (optional)
        """
        self.thermal_capture = ThreadedCameraCapture(thermal_camera, "Thermal")
        self.rgb_capture = ThreadedCameraCapture(rgb_camera, "RGB") if rgb_camera else None

    def start(self):
        """Start both camera capture threads."""
        self.thermal_capture.start()
        if self.rgb_capture:
            self.rgb_capture.start()
        logger.info("Dual camera threaded capture started")

    def get_frames(self) -> Tuple[Optional[np.ndarray], Optional[np.ndarray], Optional[np.ndarray]]:
        """
        Get latest frames from both cameras (non-blocking).

        Returns:
            (thermal_display, thermal_raw, rgb_frame) tuple.
            ``thermal_display`` is always 8-bit BGR (display-safe).
            ``thermal_raw``    may be uint16 for radiometric cameras.
        """
        # Get thermal display + raw frames
        ret_thermal, thermal_frame, _ = self.thermal_capture.get_frame()
        thermal_frame = thermal_frame if ret_thermal else None

        ret_raw, thermal_raw, _ = self.thermal_capture.get_raw_frame()
        thermal_raw = thermal_raw if ret_raw else None

        # Get RGB frame
        rgb_frame = None
        if self.rgb_capture:
            ret_rgb, rgb_frame, _ = self.rgb_capture.get_frame()
            rgb_frame = rgb_frame if ret_rgb else None

        return thermal_frame, thermal_raw, rgb_frame

    def stop(self):
        """Stop both camera capture threads."""
        self.thermal_capture.stop()
        if self.rgb_capture:
            self.rgb_capture.stop()
        logger.info("Dual camera threaded capture stopped")

    def get_stats(self) -> dict:
        """Get capture statistics for both cameras."""
        stats = {
            'thermal': self.thermal_capture.get_stats()
        }
        if self.rgb_capture:
            stats['rgb'] = self.rgb_capture.get_stats()
        return stats
