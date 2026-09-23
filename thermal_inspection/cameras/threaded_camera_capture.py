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
                    # A 16-bit (radiometric) frame's 8-bit display version
                    # is built lazily in get_frame(), not here: the app
                    # reads only the raw frame (it colorizes 16-bit data
                    # itself), so normalizing + GRAY2BGR-ing every captured
                    # frame on this thread was full-frame work nothing read.
                    display = None if frame.dtype == np.uint16 else frame

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
                        self.latest_frame = display     # 8-bit BGR, or None until get_frame() builds it
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

        No copy here: published frames are never mutated in place, only
        replaced wholesale by the next capture (see _capture_loop). A
        defensive copy on every read was pure redundant memcpy that scaled
        with resolution: at 4K (~25MB/frame) and a ~100Hz main-loop poll
        rate, that's ~2.5GB/s of memcpy nothing needed, measured as the
        dominant cause of FPS dropping with RGB resolution independent of
        fusion mode.

        For a 16-bit frame the 8-bit display version is built here on first
        request and cached against that frame (see _capture_loop for why).
        """
        with self.frame_lock:
            raw = self.latest_raw_frame
            if raw is None:
                return False, None, 0
            display = self.latest_frame
            timestamp = self.latest_timestamp
        if display is None:
            display = cv2.normalize(raw, None, 0, 255, cv2.NORM_MINMAX, dtype=cv2.CV_8U)
            if display.ndim == 2:
                display = cv2.cvtColor(display, cv2.COLOR_GRAY2BGR)
            with self.frame_lock:
                if self.latest_raw_frame is raw:  # still the current frame - cache it
                    self.latest_frame = display
        return True, display, timestamp

    def get_raw_and_count(self) -> Tuple[Optional[np.ndarray], int]:
        """Latest raw frame and the capture counter it was published with,
        read atomically - frame_count only changes when a new frame is
        published, so callers can tell a new frame from a re-poll of the
        same one without comparing arrays."""
        with self.frame_lock:
            return self.latest_raw_frame, self.frame_count

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

    def stop(self, timeout: float = 2.0) -> bool:
        """
        Stop the background capture thread.

        Returns True once the thread has exited (or never ran), False if it
        is still blocked inside a camera read() after `timeout`. Callers
        about to RELEASE the camera must know the difference: releasing a
        capture handle while another thread is mid-read() is a cross-thread
        driver call that native capture libraries can crash on.

        Safe to call again after a False return - it just waits longer.
        """
        was_running = self.running
        if was_running:
            logger.info(f"{self.name}: Stopping background thread...")
            self.running = False

        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=timeout)

        exited = not (self.thread and self.thread.is_alive())
        if exited:
            if was_running:
                logger.info(f"{self.name}: Stopped (captured {self.frame_count} frames, {self.error_count} errors)")
        else:
            logger.warning(
                f"{self.name}: capture thread still blocked in read() after {timeout}s - "
                "camera release may race it"
            )
        return exited

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

    def get_raw_frames(self) -> Tuple[Optional[np.ndarray], Optional[np.ndarray], Tuple[int, int]]:
        """
        (thermal_raw, rgb_frame, (thermal_count, rgb_count)) - the frames
        the render loop actually uses, without building get_frames()'s
        8-bit thermal display copy (which it discards), plus each camera's
        capture counter so the loop can skip re-processing a frame it has
        already rendered.
        """
        thermal_raw, thermal_count = self.thermal_capture.get_raw_and_count()
        rgb_frame, rgb_count = (self.rgb_capture.get_raw_and_count()
                                if self.rgb_capture else (None, 0))
        return thermal_raw, rgb_frame, (thermal_count, rgb_count)

    def stop(self, timeout: float = 2.0) -> bool:
        """Stop both camera capture threads. True if both threads exited
        (see ThreadedCameraCapture.stop)."""
        exited = self.thermal_capture.stop(timeout)
        if self.rgb_capture:
            exited = self.rgb_capture.stop(timeout) and exited
        logger.info("Dual camera threaded capture stopped")
        return exited

    def get_stats(self) -> dict:
        """Get capture statistics for both cameras."""
        stats = {
            'thermal': self.thermal_capture.get_stats()
        }
        if self.rgb_capture:
            stats['rgb'] = self.rgb_capture.get_stats()
        return stats
