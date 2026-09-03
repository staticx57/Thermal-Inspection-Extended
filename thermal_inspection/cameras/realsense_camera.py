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

import cv2
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
        self._depth_sensor: Optional["rs.sensor"] = None  # cached on open() for option get/set
        self._device: Optional["rs.device"] = None  # cached on open() for get_info() diagnostics

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
            self._depth_sensor = depth_sensor
            self._device = device

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

    def get_depth_frame(self, resize_to: Optional[Tuple[int, int]] = None) -> Optional[np.ndarray]:
        """
        Real metric depth map (meters, float32, H x W) aligned to the color
        frame from the most recent read(). None if no frame has been read
        yet or the last frame had no valid depth data.

        Args:
            resize_to: Optional (width, height) to resize down to. When the
                caller only needs a smaller working resolution (e.g. the
                parallax compensator resizes this down to thermal's
                resolution immediately afterward anyway), pass it here so
                the resize happens on the small raw uint16 array BEFORE
                the float32 conversion+scale multiply, not after - doing
                the conversion at full native depth-sensor resolution
                (e.g. 1280x800) only to immediately discard most of it in
                a downstream resize was costing real time per frame for no
                benefit, the same class of waste fixed earlier for the
                MiDaS/DepthAnything/simplified depth paths.
        """
        if self._last_depth_frame is None:
            return None
        try:
            raw = np.asanyarray(self._last_depth_frame.get_data())  # uint16, raw device units
            if resize_to is not None and resize_to != (raw.shape[1], raw.shape[0]):
                raw = cv2.resize(raw, resize_to, interpolation=cv2.INTER_NEAREST)
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
        """
        Pinhole intrinsics (fx, fy, cx, cy, width, height) matching the
        depth data get_depth_frame() actually returns - i.e. the ALIGNED
        depth frame's intrinsics (the color stream's resolution/grid), not
        the depth sensor's native resolution.

        The depth and color sensors have different native resolutions on
        most RealSense models (e.g. 848x480 depth vs 1280x800 color on a
        D455) - querying the pipeline's raw depth stream profile here
        instead of the last aligned frame's own intrinsics returned the
        native depth resolution while get_depth_frame() returns data at
        the color resolution, a real width/height mismatch confirmed on
        real D455 hardware.
        """
        if self._last_depth_frame is None:
            return None
        try:
            intr = self._last_depth_frame.profile.as_video_stream_profile().get_intrinsics()
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
        self._depth_sensor = None
        self._device = None

    def is_opened(self) -> bool:
        return self.is_open

    def get_info(self) -> Dict[str, Any]:
        info: Dict[str, Any] = {
            'backend': 'realsense',
            'type': 'rgb',
            'bit_depth': 8,
            'radiometric': False,
            'resolution': (self.width, self.height),
            'features': ['depth', 'point_cloud'],
            'model': self.model or self.camera_type,
            'depth_scale_m': self.depth_scale,
        }

        # Real hardware-reported diagnostics (device.get_info() calls a
        # librealsense property table baked into firmware) - only added
        # when actually available, never guessed, so a field's absence
        # means "this device/firmware doesn't report it", not "unknown".
        if self._device is not None:
            for key, camera_info_field in (
                ('serial_number', rs.camera_info.serial_number),
                ('firmware_version', rs.camera_info.firmware_version),
                ('usb_type', rs.camera_info.usb_type_descriptor),
                ('product_line', rs.camera_info.product_line),
                ('physical_port', rs.camera_info.physical_port),
            ):
                try:
                    if self._device.supports(camera_info_field):
                        info[key] = self._device.get_info(camera_info_field)
                except Exception:
                    pass

        intr = self.get_depth_intrinsics()
        if intr is not None and intr.get('fx') and intr.get('width'):
            import math
            info['horizontal_fov_deg'] = math.degrees(2 * math.atan2(intr['width'] / 2.0, intr['fx']))
            if intr.get('fy') and intr.get('height'):
                info['vertical_fov_deg'] = math.degrees(2 * math.atan2(intr['height'] / 2.0, intr['fy']))

        return info

    def get_depth_sensor_options(self) -> Dict[str, Dict[str, float]]:
        """
        Query which depth-sensor options the connected device actually
        supports right now, with each one's current/min/max/default value -
        built dynamically from the live device rather than a hardcoded
        list, so a control panel built from this never offers a setting
        the attached device doesn't really have.

        Returns:
            {option_name: {'value', 'min', 'max', 'step', 'default'}},
            e.g. {'emitter_enabled': {...}, 'laser_power': {...}}. Empty if
            no device is open or nothing could be queried.
        """
        if self._depth_sensor is None:
            return {}

        options: Dict[str, Dict[str, float]] = {}
        try:
            for opt in self._depth_sensor.get_supported_options():
                try:
                    if not self._depth_sensor.supports(opt):
                        continue
                    rng = self._depth_sensor.get_option_range(opt)
                    options[opt.name] = {
                        'value': self._depth_sensor.get_option(opt),
                        'min': rng.min,
                        'max': rng.max,
                        'step': rng.step,
                        'default': rng.default,
                    }
                except Exception as e:
                    logger.debug(f"RealSense: could not query option {opt}: {e}")
        except Exception as e:
            logger.debug(f"RealSense: could not enumerate depth sensor options: {e}")

        return options

    def set_depth_sensor_option(self, option_name: str, value: float) -> bool:
        """
        Set a depth-sensor option by name (one of the keys returned by
        get_depth_sensor_options(), e.g. 'emitter_enabled', 'laser_power').
        Returns False (no-op) if no device is open, the name doesn't match
        a real rs.option, or the device doesn't currently support it.
        """
        if self._depth_sensor is None:
            return False
        # rs.option is a pybind11-wrapped enum, not a Python enum.Enum - it
        # doesn't support the `EnumClass[name]` subscript lookup, only
        # getattr-style attribute access.
        opt = getattr(rs.option, option_name, None)
        if opt is None:
            logger.warning(f"RealSense: unknown depth sensor option '{option_name}'")
            return False
        try:
            if not self._depth_sensor.supports(opt):
                logger.warning(f"RealSense: device does not support option '{option_name}'")
                return False
            self._depth_sensor.set_option(opt, value)
            logger.info(f"RealSense depth sensor option '{option_name}' set to {value}")
            return True
        except Exception as e:
            logger.error(f"RealSense: failed to set option '{option_name}' to {value}: {e}")
            return False

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
