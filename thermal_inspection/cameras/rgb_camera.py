"""
RGB Camera Interface - Cross-platform (Windows/Linux/macOS)
Supports USB webcams and CSI cameras (Jetson only)
Designed to match FLIR camera interface for easy integration
"""
import cv2
import numpy as np
import logging
from typing import Tuple, Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RGBCamera:
    """
    RGB camera capture with Jetson optimization
    Supports USB and CSI cameras
    """

    def __init__(self, device_id: int = 0, resolution: Tuple[int, int] = (640, 480),
                 fps: int = 30, use_gstreamer: bool = False):
        """
        Initialize RGB camera

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
        self.camera_type = "USB/CSI (Legacy)"  # For compatibility with main.py

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
        Open camera connection with timeout and backend fallback.

        Returns:
            True if successful
        """
        import platform
        import time
        system = platform.system()

        try:
            if self.use_gstreamer:
                # Use GStreamer for CSI cameras on Jetson (Linux only)
                if system != "Linux":
                    logger.warning("GStreamer CSI mode only supported on Linux/Jetson")
                    logger.warning("Falling back to USB camera mode")
                    self.use_gstreamer = False
                else:
                    pipeline = self._create_gstreamer_pipeline()
                    logger.info("Opening CSI camera with GStreamer pipeline")
                    logger.debug(f"Pipeline: {pipeline}")
                    self.cap = cv2.VideoCapture(pipeline, cv2.CAP_GSTREAMER)

            if not self.use_gstreamer:
                # Try multiple backends with timeout
                backends = []
                if system == "Linux":
                    backends = [(cv2.CAP_V4L2, "V4L2"), (cv2.CAP_ANY, "Any")]
                elif system == "Windows":
                    # Try MSMF first, fall back to DirectShow (CAP_DSHOW).
                    backends = [(cv2.CAP_MSMF, "MSMF"), (cv2.CAP_DSHOW, "DirectShow")]
                else:
                    backends = [(cv2.CAP_ANY, "Any")]

                for backend, name in backends:
                    try:
                        logger.info(f"Trying backend: {name}")

                        # Create capture with backend
                        self.cap = cv2.VideoCapture(self.device_id, backend)

                        # Try to open and test read
                        if self.cap.isOpened():
                            ret, frame = self.cap.read()
                            if ret and frame is not None:
                                logger.info(f"[OK] RGB camera opened successfully with {name}")

                                # Set properties
                                self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
                                self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
                                self.cap.set(cv2.CAP_PROP_FPS, self.fps)
                                self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                                self.cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.75)  # Auto mode (was 0.25 manual)
                                self.cap.set(cv2.CAP_PROP_AUTOFOCUS, 0)

                                # Get actual resolution
                                actual_width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                                actual_height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                                actual_fps = self.cap.get(cv2.CAP_PROP_FPS)

                                logger.info(f"Resolution: {actual_width}x{actual_height} @ {actual_fps} FPS")

                                # Warm up camera
                                time.sleep(0.3)
                                warmup_success = False
                                for attempt in range(10):
                                    ret, _ = self.cap.read()
                                    if ret:
                                        warmup_success = True
                                        break
                                    time.sleep(0.1)

                                if not warmup_success:
                                    logger.warning("Camera warmup struggled but continuing anyway")

                                time.sleep(0.5)
                                self.is_open = True
                                return True
                            else:
                                logger.warning(f"Camera opened but failed to read frame with {name}")
                                self.cap.release()
                                self.cap = None
                        else:
                            logger.debug(f"Failed to open with {name}")
                            if self.cap:
                                self.cap.release()
                                self.cap = None

                    except Exception as e:
                        logger.debug(f"Backend {name} failed: {e}")
                        if self.cap:
                            self.cap.release()
                            self.cap = None
                        continue

                logger.error(f"Failed to open RGB camera {self.device_id} with all backends")
                return False

        except Exception as e:
            logger.error(f"Failed to open RGB camera: {e}")
            return False

    def read(self, flush_buffer: bool = False) -> Tuple[bool, Optional[np.ndarray]]:
        """
        Read frame from camera

        Args:
            flush_buffer: If True, flush buffer by reading multiple frames (reduces latency)

        Returns:
            (success, frame) tuple
        """
        if not self.is_open or self.cap is None:
            return False, None

        try:
            # Flush buffer if requested (grab latest frame)
            if flush_buffer:
                for _ in range(2):
                    self.cap.grab()

            ret, frame = self.cap.read()

            if not ret or frame is None:
                logger.warning("Failed to read RGB frame")
                return False, None

            return True, frame

        except Exception as e:
            logger.error(f"Error reading RGB camera: {e}")
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
        """Release camera resources"""
        if self.cap is not None:
            self.cap.release()
            self.cap = None
        self.is_open = False
        logger.info("RGB camera released")

        # Small delay to ensure resource cleanup
        import time
        time.sleep(0.1)

    def __del__(self):
        """Cleanup on deletion"""
        self.release()


def detect_rgb_cameras() -> list:
    """
    Detect available RGB cameras on the system

    Returns:
        List of available camera IDs
    """
    available_cameras = []

    # Test USB cameras (0-9)
    for camera_id in range(10):
        cap = cv2.VideoCapture(camera_id)
        if cap.isOpened():
            ret, _ = cap.read()
            if ret:
                width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                logger.info(f"Found USB camera {camera_id}: {width}x{height}")
                available_cameras.append({
                    'id': camera_id,
                    'type': 'USB',
                    'resolution': (width, height)
                })
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
    """Test RGB camera capture"""
    print("="*60)
    print("RGB Camera Test")
    print("="*60)

    # Detect cameras
    print("\nDetecting cameras...")
    cameras = detect_rgb_cameras()

    if not cameras:
        print("No RGB cameras found!")
        exit(1)

    print(f"\nFound {len(cameras)} camera(s):")
    for cam in cameras:
        print(f"  {cam['type']} Camera {cam['id']}: {cam['resolution'][0]}x{cam['resolution'][1]}")

    # Test first camera
    print(f"\nTesting camera {cameras[0]['id']}...")
    use_gstreamer = (cameras[0]['type'] == 'CSI')

    rgb_cam = RGBCamera(
        device_id=cameras[0]['id'],
        resolution=(640, 480),
        fps=30,
        use_gstreamer=use_gstreamer
    )

    if not rgb_cam.open():
        print("Failed to open camera!")
        exit(1)

    print("Camera opened successfully. Press 'q' to quit.")

    frame_count = 0
    import time
    start_time = time.time()

    try:
        while True:
            ret, frame = rgb_cam.read()

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
            cv2.imshow("RGB Camera Test", frame)

            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                break

    except KeyboardInterrupt:
        print("\nInterrupted by user")
    finally:
        rgb_cam.release()
        cv2.destroyAllWindows()

    print("\nTest complete!")
