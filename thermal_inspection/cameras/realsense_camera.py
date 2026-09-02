"""
RGB + Depth Camera Interface - Intel RealSense (D400/L500 series)

Uses pyrealsense2 to stream aligned color + depth from any connected
RealSense device generically (no per-model hardcoding): color/depth stream
profiles are requested without an explicit resolution, letting librealsense
pick the device's own default/first-supported profile, so this works
across the D415/D435/D435i/D455/D457 and L515 product lines without
special-casing any one of them.

T265 (pose/tracking, no depth or color stream in this sense) and other
non-depth RealSense models are detected but reported unsupported - there
is no depth-for-parallax or 3D Fusion use case for a camera with no depth
stream, and this app has no SLAM/navigation feature that would use pose
data.

Requires: pip install pyrealsense2 (not installed by default - optional
dependency, see requirements.txt).
"""
import logging
import time
from typing import Optional, Tuple, Dict, Any

import numpy as np

logger = logging.getLogger(__name__)

try:
    import pyrealsense2 as rs
    REALSENSE_AVAILABLE = True
except ImportError:
    REALSENSE_AVAILABLE = False
    logger.debug("pyrealsense2 not available. Intel RealSense support disabled.")
    logger.debug("Install with: pip install pyrealsense2")

# Warmup budget for a freshly opened device - RealSense's auto-exposure
# needs a handful of frames before color/depth settle, same reasoning as
# RGBCameraUVC's WARMUP_TIMEOUT_S.
WARMUP_FRAMES = 10


class RGBCameraRealSense:
    """
    Intel RealSense camera interface providing aligned color + depth.

    Implements the same duck-typed interface as RGBCameraUVC/RGBCameraFirefly
    (open/read/release/is_opened/get_info) plus RealSense-specific extras
    (get_depth_frame, get_point_cloud, get_depth_intrinsics) that only this
    backend exposes - callers that want real hardware depth (parallax's
    "realsense" depth method, the 3D Fusion panel) check for these via
    hasattr()/isinstance() rather than every RGBBackend needing them.
    """

    def __init__(self, serial_number: str = "", fps: int = 30):
        """
        Args:
            serial_number: Specific device serial to open (empty = first
                detected RealSense device)
            fps: Requested stream framerate (device clamps to what its
                negotiated profile actually supports)
        """
        self.serial_number = serial_number
        self.fps = fps
        self.width = 0
        self.height = 0
        self.camera_type = "Intel RealSense"
        self.model = ""

        self.pipeline: Optional["rs.pipeline"] = None
        self.align: Optional["rs.align"] = None
        self.pointcloud: Optional["rs.pointcloud"] = None
        self.depth_scale: float = 0.001  # overwritten from the device on open()
        self.is_open = False

        self._last_depth_frame = None  # rs.depth_frame, kept for point-cloud calc
        self._last_color_image = None

    def is_available(self) -> bool:
        """Whether pyrealsense2 is importable on this system."""
        return REALSENSE_AVAILABLE

    def open(self) -> bool:
        if not REALSENSE_AVAILABLE:
            logger.error("pyrealsense2 not available. Cannot open RealSense camera.")
            return False

        try:
            self.pipeline = rs.pipeline()
            config = rs.config()
            if self.serial_number:
                config.enable_device(self.serial_number)

            # No explicit width/height - let the device pick its own
            # default profile for whichever model is connected (D415,
            # D435, D435i, D455, D457, L515 all support this generically).
            config.enable_stream(rs.stream.color, rs.format.bgr8, self.fps)
            config.enable_stream(rs.stream.depth, rs.format.z16, self.fps)

            profile = self.pipeline.start(config)

            device = profile.get_device()
            self.model = device.get_info(rs.camera_info.name)
            depth_sensor = device.first_depth_sensor()
            self.depth_scale = depth_sensor.get_depth_scale()

            self.align = rs.align(rs.stream.color)
            self.pointcloud = rs.pointcloud()

            # Warm up - discard frames while auto-exposure settles, same
            # pattern as RGBCameraFirefly's warm-up loop.
            for _ in range(WARMUP_FRAMES):
                try:
                    self.pipeline.wait_for_frames(timeout_ms=2000)
                except Exception as e:
                    logger.debug(f"RealSense warm-up frame failed: {e}")

            color_stream = profile.get_stream(rs.stream.color).as_video_stream_profile()
            self.width = color_stream.width()
            self.height = color_stream.height()

            self.is_open = True
            logger.info(f"RealSense camera opened: {self.model} ({self.width}x{self.height} @ {self.fps}fps requested)")
            return True

        except Exception as e:
            logger.error(f"Failed to open RealSense camera: {e}")
            self.pipeline = None
            return False

    def read(self) -> Tuple[bool, Optional[np.ndarray]]:
        """Read the next aligned color frame (RGBBackend.read() contract)."""
        if not self.is_open or self.pipeline is None:
            return False, None

        try:
            frames = self.pipeline.wait_for_frames(timeout_ms=2000)
            aligned = self.align.process(frames)

            color_frame = aligned.get_color_frame()
            depth_frame = aligned.get_depth_frame()
            if not color_frame or not depth_frame:
                return False, None

            # get_data() returns a view into RealSense's own frame buffer,
            # which the SDK reuses on the next wait_for_frames() call - copy
            # before handing it to callers, same reasoning as
            # RGBCameraFirefly.read()'s GetNDArray() copy.
            color_image = np.asanyarray(color_frame.get_data()).copy()
            self._last_color_image = color_image
            self._last_depth_frame = depth_frame

            return True, color_image

        except Exception as e:
            logger.error(f"Error reading RealSense frame: {e}")
            return False, None

    def get_depth_frame(self) -> Optional[np.ndarray]:
        """
        Real metric depth map (meters, float32, H x W) aligned to the color
        frame from the most recent read(). None if no frame has been read
        yet or the last frame had no valid depth data.
        """
        if self._last_depth_frame is None:
            return None
        try:
            raw = np.asanyarray(self._last_depth_frame.get_data())  # uint16, raw device units
            return raw.astype(np.float32) * self.depth_scale
        except Exception as e:
            logger.error(f"Error reading RealSense depth frame: {e}")
            return None

    def get_point_cloud(self) -> Optional[Tuple[np.ndarray, np.ndarray]]:
        """
        Real 3D point cloud from the most recent read(), in the color
        camera's coordinate frame (meters).

        Returns:
            (vertices, uv) where vertices is (N, 3) float32 XYZ and uv is
            (N, 2) float32 texture coordinates into the color image
            (each in [0, 1]), or None if no frame is available.
        """
        if self._last_depth_frame is None or self.pointcloud is None:
            return None
        try:
            points = self.pointcloud.calculate(self._last_depth_frame)
            vtx = np.asanyarray(points.get_vertices()).view(np.float32).reshape(-1, 3)
            tex = np.asanyarray(points.get_texture_coordinates()).view(np.float32).reshape(-1, 2)
            return vtx, tex
        except Exception as e:
            logger.error(f"Error calculating RealSense point cloud: {e}")
            return None

    def get_depth_intrinsics(self) -> Optional[Dict[str, float]]:
        """Depth camera pinhole intrinsics (fx, fy, cx, cy, width, height), or None."""
        if not self.is_open or self.pipeline is None:
            return None
        try:
            profile = self.pipeline.get_active_profile()
            depth_profile = profile.get_stream(rs.stream.depth).as_video_stream_profile()
            intr = depth_profile.get_intrinsics()
            return {
                'fx': intr.fx, 'fy': intr.fy,
                'cx': intr.ppx, 'cy': intr.ppy,
                'width': intr.width, 'height': intr.height,
            }
        except Exception as e:
            logger.debug(f"Could not read RealSense depth intrinsics: {e}")
            return None

    def release(self):
        if self.pipeline is not None:
            try:
                self.pipeline.stop()
                logger.info("RealSense camera released")
            except Exception as e:
                logger.debug(f"Error releasing RealSense pipeline: {e}")
            finally:
                self.pipeline = None
        self.is_open = False
        self._last_depth_frame = None
        self._last_color_image = None

    def is_opened(self) -> bool:
        return self.is_open

    def get_info(self) -> Dict[str, Any]:
        return {
            'backend': 'realsense',
            'type': 'rgb',
            'bit_depth': 8,
            'radiometric': False,
            'resolution': (self.width, self.height),
            'features': ['depth', 'point_cloud'],
            'model': self.model or self.camera_type,
        }

    def get_resolution(self) -> Optional[Tuple[int, int]]:
        if self.width and self.height:
            return (self.width, self.height)
        return None

    def supports_color(self) -> bool:
        return True

    def get_exposure(self) -> Optional[float]:
        # RealSense exposure is a sensor-level option (rs.option.exposure),
        # not exposed generically here - the control panel talks to the
        # sensor directly via the SDK object when needed.
        return None

    def set_exposure(self, exposure_ms: float) -> bool:
        return False

    def __del__(self):
        self.release()


def detect_realsense_cameras() -> list:
    """
    Detect all connected RealSense devices without opening a stream.

    Returns:
        List of dicts with keys: serial, model, product_line, supported
        (bool - whether this app can use it, i.e. has a depth+color stream)
    """
    if not REALSENSE_AVAILABLE:
        return []

    devices_found = []
    try:
        ctx = rs.context()
        for device in ctx.query_devices():
            serial = device.get_info(rs.camera_info.serial_number)
            name = device.get_info(rs.camera_info.name)
            try:
                product_line = device.get_info(rs.camera_info.product_line)
            except Exception:
                product_line = "unknown"

            # T2xx (T265 tracking cameras) have no depth/color stream in
            # this sense - fisheye + pose only. Nothing in this app (no
            # SLAM/navigation feature) would use that data, so report them
            # as detected-but-unsupported rather than silently hiding them
            # or crashing trying to enable streams they don't have.
            supported = not product_line.upper().startswith("T2")

            devices_found.append({
                'serial': serial,
                'model': name,
                'product_line': product_line,
                'supported': supported,
            })
            logger.info(f"Found RealSense device: {name} (S/N: {serial}, line: {product_line}, supported: {supported})")

    except Exception as e:
        logger.error(f"Error detecting RealSense devices: {e}")

    return devices_found
