"""
RGB Camera Interface - Generic UVC Webcam
Supports any USB Video Class (UVC) compliant webcam
Works out-of-the-box with OpenCV, no special drivers required

Compatible with:
- Logitech C920, C922, C930e
- Microsoft LifeCam
- Generic USB webcams
- Jetson CSI cameras (via GStreamer)
"""
import os
os.environ["OPENCV_VIDEOIO_PRIORITY_OBSENSOR"] = "0"
os.environ["OPENCV_LOG_LEVEL"] = "ERROR"

import cv2
import numpy as np
import logging
import time
from typing import Tuple, Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Warmup budget for a freshly opened camera. Webcams deliver readable but
# black frames while auto-exposure ramps (~0.8s is typical), so readiness is
# judged by frame content rather than by a successful read.
WARMUP_TIMEOUT_S = 2.0
WARMUP_MIN_MEAN = 1.0   # mean pixel value above which a frame counts as lit


class RGBCameraUVC:
    """
    Generic UVC webcam interface
    Compatible with any USB Video Class webcam
    """

    def __init__(self, device_id: int = 0, resolution: Tuple[int, int] = (640, 480),
                 fps: int = 30, use_gstreamer: bool = False):
        """
        Initialize UVC webcam

        Args:
            device_id: Camera device ID (0 for default USB, 0-1 for CSI)
            resolution: Desired resolution (width, height)
            fps: Target frame rate
            use_gstreamer: Use GStreamer pipeline for CSI cameras (Jetson optimization)
        """
        self.device_id = device_id
        self.width, self.height = resolution
        self.fps = fps
        self.use_gstreamer = use_gstreamer
        self.cap = None
        self.is_open = False
        self.camera_type = "UVC Webcam"
        self._consecutive_failures = 0
        self._MAX_CONSECUTIVE_FAILURES = 10  # ~0.3 s at 30 fps
        self._last_reopen_attempt = 0.0
        self._reopen_interval_s = 2.0  # don't hammer a truly-unplugged camera

    def _create_gstreamer_pipeline(self) -> str:
        """
        Create GStreamer pipeline for Jetson CSI cameras
        Optimized for low latency and GPU acceleration

        Returns:
            GStreamer pipeline string
        """
        # CSI camera pipeline for Jetson (IMX219, IMX477, etc.)
        pipeline = (
            f"nvarguscamerasrc sensor-id={self.device_id} ! "
            f"video/x-raw(memory:NVMM), width={self.width}, height={self.height}, "
            f"format=NV12, framerate={self.fps}/1 ! "
            f"nvvidconv flip-method=0 ! "
            f"video/x-raw, width={self.width}, height={self.height}, format=BGRx ! "
            f"videoconvert ! "
            f"video/x-raw, format=BGR ! "
            f"appsink drop=1"
        )
        return pipeline

    def open(self) -> bool:
        """
        Open camera connection

        Returns:
            True if successful
        """
        try:
            if self.use_gstreamer:
                # Use GStreamer for CSI cameras on Jetson
                pipeline = self._create_gstreamer_pipeline()
                logger.info("Opening CSI camera with GStreamer pipeline")
                logger.debug(f"Pipeline: {pipeline}")
                self.cap = cv2.VideoCapture(pipeline, cv2.CAP_GSTREAMER)
                self.camera_type = "CSI Camera (GStreamer)"
            else:
                # Use V4L2 for USB cameras (Linux) or default backend (Windows)
                logger.info(f"Opening UVC webcam {self.device_id}")

                # Retry mechanism to handle "Resource detected but busy" scenarios
                # This often happens if the camera was recently scanned by CameraDetector
                max_retries = 2
                for attempt in range(max_retries):
                    try:
                        import platform
                        if platform.system() == 'Windows':
                            # Windows: Try DSHOW first (standard for webcams), fall back to MSMF/default
                            self.cap = cv2.VideoCapture(self.device_id, cv2.CAP_DSHOW)
                            if not self.cap.isOpened():
                                self.cap.release()
                                self.cap = cv2.VideoCapture(self.device_id, cv2.CAP_MSMF)
                            if not self.cap.isOpened():
                                self.cap.release()
                                self.cap = cv2.VideoCapture(self.device_id)
                        else:
                            # Linux: Try V4L2 first, fall back to default
                            self.cap = cv2.VideoCapture(self.device_id, cv2.CAP_V4L2)
                            if not self.cap.isOpened():
                                self.cap = cv2.VideoCapture(self.device_id)
                    except Exception as exc:
                        logger.warning(f"Camera open exception on attempt {attempt+1}: {exc}")
                        self.cap = None

                    if self.cap and self.cap.isOpened():
                        break

                    logger.warning(f"Attempt {attempt+1}/{max_retries}: Failed to open camera {self.device_id} - retrying...")
                    time.sleep(0.5)  # Wait for resource release

            self.camera_type = "UVC Webcam"

            if not self.cap.isOpened():
                logger.error(f"Failed to open camera {self.device_id} after {max_retries} attempts")
                return False

            # Configure camera properties (for USB cameras)
            if not self.use_gstreamer:
                # If resolution is 0x0, use maximum available resolution by trying high-res standards
                if self.width == 0 or self.height == 0:
                    logger.info("Resolution not specified - attempting to negotiate maximum resolution...")

                    # Try setting common high resolutions in descending order
                    resolutions_to_try = [
                        (3840, 2160),  # 4K
                        (2560, 1440),  # 2K
                        (1920, 1080),  # 1080p
                        (1280, 720),   # 720p
                        (640, 480)     # VGA (Fallback)
                    ]

                    for w, h in resolutions_to_try:
                        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, w)
                        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, h)
                        actual_w = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                        actual_h = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

                        # If we got what we asked for (or better), break
                        # Note: DSHOW defaults to 640x480 if request fails
                        if actual_w >= w and actual_h >= h:
                            # Verify with a frame read to ensure graph is stable
                            time.sleep(0.2)  # Allow graph to rebuild
                            if self.cap.grab():
                                logger.info(f"Negotiated resolution: {actual_w}x{actual_h}")
                                break
                            else:
                                logger.warning(f"Resolution {w}x{h} accepted but frame grab failed")

                        time.sleep(0.1)  # Don't hammer the DSHOW backend

                    # Final update of stored resolution
                    self.width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                    self.height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                    logger.info(f"Using resolution: {self.width}x{self.height}")
                else:
                    # Set requested resolution.
                    #
                    # Every accepted set() makes DirectShow tear down and
                    # rebuild the capture graph, which costs ~1.5s per call.
                    # The camera is very often already at the requested
                    # geometry (detection reports its current mode), so skip
                    # the write when it would not change anything.
                    current_w = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                    current_h = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                    if (current_w, current_h) != (self.width, self.height):
                        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
                        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
                    else:
                        logger.debug(
                            f"Camera already at {self.width}x{self.height} — skipping resolution set"
                        )

                current_fps = int(self.cap.get(cv2.CAP_PROP_FPS))
                if current_fps != int(self.fps):
                    self.cap.set(cv2.CAP_PROP_FPS, self.fps)
                else:
                    logger.debug(f"Camera already at {current_fps} FPS — skipping FPS set")

                self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # Minimize latency

                # Enable auto exposure and auto white balance
                self.cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 1)
                try:
                    self.cap.set(cv2.CAP_PROP_AUTOFOCUS, 1)
                except Exception as e:
                    logger.debug(f"Autofocus not supported by this camera: {e}")

            # Verify actual resolution
            actual_width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            actual_height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            actual_fps = int(self.cap.get(cv2.CAP_PROP_FPS))

            # Update stored resolution to actual
            self.width = actual_width
            self.height = actual_height

            logger.info(f"{self.camera_type} opened successfully")
            logger.info(f"Resolution: {actual_width}x{actual_height} @ {actual_fps} FPS")

            # Warm up the camera.
            #
            # A readable frame is NOT sufficient: webcams deliver frames while
            # auto-exposure is still ramping, and those first frames come back
            # black. So poll until a frame carries actual image content, which
            # is the real readiness signal — a camera that is ready quickly
            # costs only the time it needs, and a slow one still gets the full
            # budget. A genuinely dark scene falls through to the timeout,
            # which is why this warns rather than fails.
            warmup_success = False
            warmup_deadline = time.time() + WARMUP_TIMEOUT_S
            while time.time() < warmup_deadline:
                ret, frame = self.cap.read()
                if ret and frame is not None and float(np.mean(frame)) > WARMUP_MIN_MEAN:
                    warmup_success = True
                    break
                time.sleep(0.05)

            if not warmup_success:
                logger.warning(
                    "Camera warmup did not produce a lit frame within "
                    f"{WARMUP_TIMEOUT_S:.1f}s — continuing (scene may be dark)"
                )

            self.is_open = True
            return True

        except Exception as e:
            logger.error(f"Failed to open UVC camera: {e}")
            # self.cap may already be a genuinely opened VideoCapture if a
            # later step (resolution negotiation, warmup) is what threw -
            # release() closes it; leaving it open here leaked the handle.
            self.release()
            return False

    def is_opened(self) -> bool:
        """Check if camera is open and ready."""
        return bool(self.is_open and self.cap is not None and self.cap.isOpened())

    def read(self, flush_buffer: bool = False) -> Tuple[bool, Optional[np.ndarray]]:
        """
        Read frame from camera.

        Returns:
            (success, frame) tuple. Returns (False, None) on any error.
            After MAX_CONSECUTIVE_FAILURES consecutive failures the camera is
            marked as disconnected (is_open=False) so callers can detect
            a hot-unplug.
        """
        if not self.is_open or self.cap is None:
            # Self-heal: previously, once marked disconnected, read() just
            # returned (False, None) forever - nothing anywhere ever called
            # open() again, so a brief driver/USB hiccup permanently froze
            # the feed on whatever frame was last cached for the rest of
            # the session, even though the physical camera was fine and
            # still streaming to everything else on the system. Retry the
            # open on a cooldown instead of giving up outright.
            now = time.time()
            if now - self._last_reopen_attempt < self._reopen_interval_s:
                return False, None
            self._last_reopen_attempt = now
            if not self.open():
                return False, None

        try:
            if flush_buffer:
                for _ in range(2):
                    self.cap.grab()

            ret, frame = self.cap.read()

            if not ret or frame is None:
                self._consecutive_failures += 1
                if self._consecutive_failures >= self._MAX_CONSECUTIVE_FAILURES:
                    logger.warning(
                        f"UVC camera {self.device_id}: {self._consecutive_failures} consecutive "
                        f"read failures — marking as disconnected"
                    )
                    self.is_open = False
                else:
                    logger.debug(
                        f"UVC camera {self.device_id}: read failure "
                        f"({self._consecutive_failures}/{self._MAX_CONSECUTIVE_FAILURES})"
                    )
                return False, None

            # Successful read — reset failure counter
            self._consecutive_failures = 0
            return True, frame

        except Exception as e:
            self._consecutive_failures += 1
            logger.error(f"Error reading UVC camera {self.device_id}: {e}")
            if self._consecutive_failures >= self._MAX_CONSECUTIVE_FAILURES:
                self.is_open = False
            return False, None

    def get_actual_resolution(self) -> Tuple[int, int]:
        """
        Get actual camera resolution

        Returns:
            (width, height) tuple
        """
        if not self.is_open or self.cap is None:
            return (0, 0)

        width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        return (width, height)

    def set_property(self, prop: int, value: float) -> bool:
        """
        Set camera property

        Args:
            prop: OpenCV property ID (e.g., cv2.CAP_PROP_BRIGHTNESS)
            value: Property value

        Returns:
            True if successful
        """
        if not self.is_open or self.cap is None:
            return False

        try:
            return self.cap.set(prop, value)
        except Exception as e:
            logger.error(f"Failed to set property {prop}={value}: {e}")
            return False



    def get_property(self, prop: int) -> float:
        """
        Get camera property

        Args:
            prop: OpenCV property ID

        Returns:
            Property value
        """
        if not self.is_open or self.cap is None:
            return 0.0

        try:
            return self.cap.get(prop)
        except Exception as e:
            logger.error(f"Failed to get property {prop}: {e}")
            return 0.0

    def release(self):
        """Release camera resources."""
        if self.cap is not None:
            try:
                self.cap.release()
            except Exception as e:
                logger.debug(f"Error releasing UVC capture: {e}")
            self.cap = None
        self.is_open = False
        self._consecutive_failures = 0
        logger.info("UVC camera released")

    def __del__(self):
        """Cleanup on deletion"""
        self.release()


def detect_uvc_cameras() -> list:
    """
    Detect all available UVC webcams

    Returns:
        List of dictionaries with camera info
    """
    available_cameras = []
    import platform
    is_windows = (platform.system() == 'Windows')

    # Try pygrabber on Windows for non-intrusive device names
    device_names = []
    if is_windows:
        try:
            from pygrabber.dshow_graph import FilterGraph
            device_names = FilterGraph().get_input_devices()
        except Exception as e:
            logger.debug(f"pygrabber device name lookup failed: {e}")

    max_devs = max(len(device_names), 6) if device_names else 6

    # Test USB cameras
    for camera_id in range(max_devs):
        cap = None
        try:
            if is_windows:
                cap = cv2.VideoCapture(camera_id, cv2.CAP_DSHOW)
                if not cap.isOpened():
                    cap.release()
                    cap = cv2.VideoCapture(camera_id, cv2.CAP_MSMF)
                if not cap.isOpened():
                    cap.release()
                    cap = cv2.VideoCapture(camera_id)
            else:
                cap = cv2.VideoCapture(camera_id, cv2.CAP_V4L2)
                if not cap.isOpened():
                    cap.release()
                    cap = cv2.VideoCapture(camera_id)

            if cap and cap.isOpened():
                ret, _ = cap.read()
                if ret:
                    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                    name = device_names[camera_id] if camera_id < len(device_names) else f"UVC Camera {camera_id}"
                    logger.info(f"Found UVC camera {camera_id} ({name}): {width}x{height}")
                    available_cameras.append({
                        'id': camera_id,
                        'name': name,
                        'type': 'UVC',
                        'resolution': (width, height)
                    })
        except Exception as exc:
            logger.debug(f"Error probing device {camera_id}: {exc}")
        finally:
            if cap:
                cap.release()

    # Test CSI cameras (Jetson-specific)
    try:
        for sensor_id in range(2):
            pipeline = (
                f"nvarguscamerasrc sensor-id={sensor_id} ! "
                f"video/x-raw(memory:NVMM), width=640, height=480, format=NV12, framerate=30/1 ! "
                f"nvvidconv ! video/x-raw, format=BGRx ! videoconvert ! video/x-raw, format=BGR ! appsink"
            )
            cap = cv2.VideoCapture(pipeline, cv2.CAP_GSTREAMER)
            if cap.isOpened():
                ret, _ = cap.read()
                if ret:
                    logger.info(f"Found CSI camera (sensor-id={sensor_id})")
                    available_cameras.append({
                        'id': sensor_id,
                        'type': 'CSI',
                        'resolution': (1920, 1080)  # Typical CSI resolution
                    })
                cap.release()
    except Exception as e:
        logger.debug(f"CSI camera detection skipped: {e}")

    return available_cameras


if __name__ == "__main__":
    """Test UVC camera capture"""
    print("="*60)
    print("UVC Webcam Test")
    print("="*60)

    # Detect cameras
    print("\nDetecting UVC cameras...")
    cameras = detect_uvc_cameras()

    if not cameras:
        print("No UVC cameras found!")
        exit(1)

    print(f"\nFound {len(cameras)} camera(s):")
    for cam in cameras:
        print(f"  {cam['type']} Camera {cam['id']}: {cam['resolution'][0]}x{cam['resolution'][1]}")

    # Test first camera
    print(f"\nTesting camera {cameras[0]['id']}...")
    use_gstreamer = (cameras[0]['type'] == 'CSI')

    uvc_cam = RGBCameraUVC(
        device_id=cameras[0]['id'],
        resolution=(640, 480),
        fps=30,
        use_gstreamer=use_gstreamer
    )

    if not uvc_cam.open():
        print("Failed to open camera!")
        exit(1)

    print("Camera opened successfully. Press 'q' to quit.")

    frame_count = 0
    import time
    start_time = time.time()

    try:
        while True:
            ret, frame = uvc_cam.read()

            if not ret:
                print("Failed to read frame")
                break

            frame_count += 1

            # Calculate FPS
            if frame_count % 30 == 0:
                elapsed = time.time() - start_time
                fps = frame_count / elapsed
                print(f"FPS: {fps:.1f}")

            # Display frame
            cv2.imshow("UVC Camera Test", frame)

            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                break

    except KeyboardInterrupt:
        print("\nInterrupted by user")
    finally:
        uvc_cam.release()
        cv2.destroyAllWindows()

    print("\nTest complete!")
