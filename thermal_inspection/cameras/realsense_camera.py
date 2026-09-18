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

# rs.rs400_visual_preset's real int values (confirmed live against a
# connected D455: custom=0, default=1, hand=2, high_accuracy=3,
# high_density=4, medium_density=5, remove_ir_pattern=6) - a device's own
# visual_preset option range may not reach every value here (this D455
# reports max=5, so remove_ir_pattern is a valid preset name on other
# firmware/models but not selectable on this one); get_depth_sensor_options()
# attaches this map only to the visual_preset entry so a control panel can
# render it as a named dropdown instead of a bare numeric slider.
_VISUAL_PRESET_NAMES = {
    0: 'Custom',
    1: 'Default',
    2: 'Hand',
    3: 'High Accuracy',
    4: 'High Density',
    5: 'Medium Density',
    6: 'Remove IR Pattern',
}

# rs.l500_visual_preset's real int values (queried directly from
# pyrealsense2 - rs.l500_visual_preset.custom/default/no_ambient_light/
# low_ambient_light/max_range/short_range/automatic - confirmed 0-6
# respectively). The L515 (an L500-line solid-state LiDAR, not a D400-
# family stereo camera) exposes an option ALSO named 'visual_preset', but
# with these completely different int-to-meaning mappings - the previous
# code attached _VISUAL_PRESET_NAMES (the D400 map) to ANY device's
# visual_preset unconditionally, which would have mislabeled e.g. an
# L515's preset value 3 ("Low Ambient Light") as "High Accuracy" in the
# control panel dropdown. See get_depth_sensor_options()'s product_line
# check for how this map is selected instead.
_L500_VISUAL_PRESET_NAMES = {
    0: 'Custom',
    1: 'Default',
    2: 'No Ambient Light',
    3: 'Low Ambient Light',
    4: 'Max Range',
    5: 'Short Range',
    6: 'Automatic',
}


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
        self._color_sensor: Optional["rs.sensor"] = None  # cached on open() for option get/set
        self._device: Optional["rs.device"] = None  # cached on open() for get_info() diagnostics

        # Depth post-processing (spatial/temporal/hole-filling) - all off by
        # default, matching every other opt-in enhancement in this codebase.
        # Decimation is deliberately not offered: it changes the depth
        # frame's resolution, which would need to happen before align() to
        # avoid a resolution mismatch, and that reordering is a bigger,
        # riskier change than this pass's scope - see get_depth_frame()'s
        # "aligned to color" contract, which decimation would break.
        self._spatial_filter: Optional["rs.spatial_filter"] = None
        self._temporal_filter: Optional["rs.temporal_filter"] = None
        self._hole_filling_filter: Optional["rs.hole_filling_filter"] = None
        self._depth_filters_enabled: Dict[str, bool] = {
            'spatial': False, 'temporal': False, 'hole_filling': False
        }

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

            # Not every RealSense model exposes a distinct color sensor
            # object under this name (D4xx/D455 do; some do not) - absence
            # here just means get_color_sensor_options() reports nothing,
            # same "never guessed" contract as the depth-sensor options.
            for sensor in device.query_sensors():
                try:
                    if sensor.get_info(rs.camera_info.name) == "RGB Camera":
                        self._color_sensor = sensor
                        break
                except Exception:
                    continue

            self.align = rs.align(rs.stream.color)
            self.pointcloud = rs.pointcloud()
            self._spatial_filter = rs.spatial_filter()
            self._temporal_filter = rs.temporal_filter()
            self._hole_filling_filter = rs.hole_filling_filter()

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
            # pipeline.start() above may have already succeeded before a
            # later step (get_device()/first_depth_sensor()/etc.) failed -
            # release() stops it properly; just clearing the reference
            # (the old behavior) orphaned a running RealSense stream with
            # nothing left to stop it.
            self.release()
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

            # Optional denoising, applied after alignment so get_depth_frame()'s
            # "aligned to color" contract is unaffected either way - these
            # filters smooth depth values in place, they don't touch geometry.
            if self._depth_filters_enabled['spatial'] and self._spatial_filter is not None:
                depth_frame = self._spatial_filter.process(depth_frame)
            if self._depth_filters_enabled['temporal'] and self._temporal_filter is not None:
                depth_frame = self._temporal_filter.process(depth_frame)
            if self._depth_filters_enabled['hole_filling'] and self._hole_filling_filter is not None:
                depth_frame = self._hole_filling_filter.process(depth_frame)

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
        self._color_sensor = None
        self._spatial_filter = None
        self._temporal_filter = None
        self._hole_filling_filter = None
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

        # D400-family and L500-family devices both expose an option named
        # 'visual_preset', but with entirely different int-to-meaning
        # mappings (rs.rs400_visual_preset vs rs.l500_visual_preset - see
        # _L500_VISUAL_PRESET_NAMES's own comment). Deciding by
        # product_line (already read the same way in get_info()) rather
        # than assuming D400 unconditionally is what makes this correct
        # for an L515.
        is_l500 = False
        if self._device is not None:
            try:
                is_l500 = self._device.get_info(rs.camera_info.product_line).upper().startswith('L5')
            except Exception:
                pass
        preset_names = _L500_VISUAL_PRESET_NAMES if is_l500 else _VISUAL_PRESET_NAMES

        options: Dict[str, Dict[str, float]] = {}
        try:
            for opt in self._depth_sensor.get_supported_options():
                try:
                    if not self._depth_sensor.supports(opt):
                        continue
                    rng = self._depth_sensor.get_option_range(opt)
                    entry = {
                        'value': self._depth_sensor.get_option(opt),
                        'min': rng.min,
                        'max': rng.max,
                        'step': rng.step,
                        'default': rng.default,
                    }
                    if opt.name == 'visual_preset':
                        entry['enum_names'] = preset_names
                    options[opt.name] = entry
                except Exception as e:
                    logger.debug(f"RealSense: could not query option {opt}: {e}")
        except Exception as e:
            logger.debug(f"RealSense: could not enumerate depth sensor options: {e}")

        return options

    def get_color_sensor_options(self) -> Dict[str, Dict[str, float]]:
        """
        Same generic, device-reported pattern as get_depth_sensor_options()
        but for the color sensor (e.g. 'brightness', 'contrast', 'gamma',
        'white_balance', 'enable_auto_white_balance') - empty if this
        device/firmware doesn't expose a distinct color sensor object.
        """
        if self._color_sensor is None:
            return {}

        options: Dict[str, Dict[str, float]] = {}
        try:
            for opt in self._color_sensor.get_supported_options():
                try:
                    if not self._color_sensor.supports(opt):
                        continue
                    rng = self._color_sensor.get_option_range(opt)
                    options[opt.name] = {
                        'value': self._color_sensor.get_option(opt),
                        'min': rng.min,
                        'max': rng.max,
                        'step': rng.step,
                        'default': rng.default,
                    }
                except Exception as e:
                    logger.debug(f"RealSense: could not query color option {opt}: {e}")
        except Exception as e:
            logger.debug(f"RealSense: could not enumerate color sensor options: {e}")

        return options

    def set_color_sensor_option(self, option_name: str, value: float) -> bool:
        """Set a color-sensor option by name - same contract as set_depth_sensor_option()."""
        if self._color_sensor is None:
            return False
        opt = getattr(rs.option, option_name, None)
        if opt is None:
            logger.warning(f"RealSense: unknown color sensor option '{option_name}'")
            return False
        try:
            if not self._color_sensor.supports(opt):
                logger.warning(f"RealSense: device does not support color option '{option_name}'")
                return False
            self._color_sensor.set_option(opt, value)
            logger.info(f"RealSense color sensor option '{option_name}' set to {value}")
            return True
        except Exception as e:
            logger.error(f"RealSense: failed to set color option '{option_name}' to {value}: {e}")
            return False

    def get_depth_filter_state(self) -> Dict[str, bool]:
        """Current on/off state of the opt-in depth post-processing filters."""
        return dict(self._depth_filters_enabled)

    def set_depth_filter_enabled(self, filter_name: str, enabled: bool) -> bool:
        """
        Toggle one depth post-processing filter ('spatial', 'temporal', or
        'hole_filling'). All default off; read()'s filter chain checks this
        dict every frame, so toggling takes effect on the next frame with
        no reconnect needed.
        """
        if filter_name not in self._depth_filters_enabled:
            logger.warning(f"RealSense: unknown depth filter '{filter_name}'")
            return False
        self._depth_filters_enabled[filter_name] = bool(enabled)
        return True

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
