"""
Parallax Compensation Module for Thermal-RGB Fusion

Corrects parallax offset between thermal and RGB cameras using depth estimation.
The thermal and RGB cameras are mounted side-by-side with a baseline distance,
causing parallax that varies with object distance.

This module uses depth estimation to estimate per-pixel depth and compute adaptive
pixel displacement to align the thermal and RGB views.

Architecture:
- DepthEstimator: Estimates depth from RGB image (supports DepthAnything V2, simplified)
- ParallaxCompensator: Computes alignment displacement based on depth
- Optional: Can be disabled for performance or when cameras are co-located

NEW in v3.3.0:
- DepthAnything V2 ML depth estimation integration (state-of-the-art accuracy)
- Model size selection (small/base/large) for performance/quality tradeoffs
- Auto device detection (CUDA/CPU)
- Lazy model loading
"""

import math
import numpy as np
import cv2
import logging
import time
from typing import Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Optional: Depth estimation model (DepthAnything V2, MiDaS, etc.)
# NOTE: We don't import torch/transformers here to avoid DLL loading errors
# They will be imported lazily when actually needed
DEPTH_ESTIMATION_AVAILABLE = False
TRANSFORMERS_AVAILABLE = False

# Check if torch/transformers are importable (without actually importing them
# at module level - both are optional, and probing for real costs seconds).
#
# TRANSFORMERS_AVAILABLE used to only ever get set True as a side effect of
# load_model() actually running its own `from transformers import pipeline`
# - but the constructor below gates depth_method="depthanything" on this
# flag BEFORE load_model() has ever been called, so on every first
# construction it was always False regardless of whether transformers was
# actually installed. DepthAnything was never reachable through this class
# at all, even with correct dependencies - confirmed live: a real GPU
# inference test returned 0MB GPU memory used and a silent fallback to
# "simplified", with transformers 4.57.3 actually installed.
try:
    import importlib.util
    torch_spec = importlib.util.find_spec("torch")
    if torch_spec is not None:
        # torch package exists, but we won't import it yet (lazy import)
        DEPTH_ESTIMATION_AVAILABLE = True
        logger.info("PyTorch package detected (will load lazily if needed)")
    else:
        logger.info("PyTorch not installed - ML depth estimation disabled")
        logger.info("Parallax correction will use simplified geometric mode")

    transformers_spec = importlib.util.find_spec("transformers")
    TRANSFORMERS_AVAILABLE = transformers_spec is not None
    if TRANSFORMERS_AVAILABLE:
        logger.info("transformers package detected (will load lazily if needed)")
except Exception as e:
    logger.info(f"Could not detect PyTorch/transformers: {e}")
    logger.info("Parallax correction will use simplified geometric mode")



@dataclass
class CameraGeometry:
    """
    Geometric parameters for parallax compensation.

    Attributes:
        baseline_mm: Distance between thermal and RGB camera centers (millimeters)
        thermal_focal_length_mm: Thermal camera focal length (mm)
        rgb_focal_length_mm: RGB camera focal length (mm)
        thermal_sensor_width_mm: Thermal sensor width (mm)
        rgb_sensor_width_mm: RGB sensor width (mm)
        thermal_resolution: (width, height) in pixels
        rgb_resolution: (width, height) in pixels
    """
    baseline_mm: float = 50.0  # Default: 50mm baseline (5cm separation)
    thermal_focal_length_mm: float = 9.0  # Boson 640 typical
    rgb_focal_length_mm: float = 6.0  # Firefly typical
    thermal_sensor_width_mm: float = 10.88  # Boson 640 (17μm × 640px)
    rgb_sensor_width_mm: float = 6.784  # IMX290 (2.9μm × 2336px)
    thermal_resolution: Tuple[int, int] = (640, 512)
    rgb_resolution: Tuple[int, int] = (1920, 1200)


class DepthEstimator:
    """
    Estimates depth map from RGB image using deep learning model.

    Supports:
    - DepthAnything V2 (state-of-the-art, recommended)
    - MiDaS / Intel DPT (well-established, moderate accuracy)
    - Simplified geometric estimation (fallback, fast, not real depth -
      a fixed top-far/bottom-near gradient, ignores image content entirely)
    """

    def __init__(self, method: str = "simplified", device: str = "auto", model_size: str = "small"):
        """
        Initialize depth estimator.

        Args:
            method: "simplified", "depthanything", or "midas"
            device: "auto", "cpu", "cuda", or "cuda:0" (auto detects best device)
            model_size: "small", "base", "large" (for DepthAnything V2)
        """
        self.method = method
        self.model_size = model_size
        self.model = None
        self.pipeline = None
        self.enabled = False
        self.model_loaded = False

        # Real hardware depth source (e.g. RealSenseCamera.get_depth_frame),
        # wired by app.py when a depth-capable camera becomes the active RGB
        # source - see set_hardware_depth_source(). Unlike simplified/midas/
        # depthanything (which all derive an *estimate* from the RGB image
        # itself), this method reads real measured depth and ignores the
        # rgb_image argument entirely.
        self._hardware_depth_source = None

        # "simplified" is the one method whose output depends only on
        # (h, w) - it never reads rgb_image's actual pixel content (see
        # _estimate_depth_simplified) - so its result is identical every
        # frame for a fixed resolution. Cache it instead of rebuilding via
        # GaussianBlur+tile+linspace every single call.
        self._simplified_depth_shape = None
        self._simplified_depth_cache = None

        # Device selection is deferred: probing CUDA means importing torch,
        # which costs seconds (and on a broken install fails slowly) even
        # though the default 'simplified' method never touches it. The real
        # value is resolved by the `device` property when a model loads.
        self._device_requested = device
        self._device_resolved: Optional[str] = None if device == "auto" else device

        if method == "simplified":
            self.enabled = True
            logger.info("Using simplified depth estimation (geometric heuristics)")
        elif method == "realsense":
            # Enabled immediately - there's no model to lazy-load; whether
            # this actually produces depth depends on whether a RealSense
            # camera is the active RGB source (see estimate_depth()).
            self.enabled = True
            logger.info("Using Intel RealSense hardware depth (real measured depth, no estimation)")
        elif method == "depthanything":
            if DEPTH_ESTIMATION_AVAILABLE and TRANSFORMERS_AVAILABLE:
                # Device is intentionally not logged here — reading it would
                # import torch and undo the deferral. load_model() logs it.
                logger.info(f"DepthAnything V2 ({model_size}) will be loaded on first use")
                self.enabled = False  # Will be enabled when model loads
            else:
                logger.warning("DepthAnything V2 requested but dependencies not available")
                logger.warning("Falling back to simplified method")
                logger.warning("Install with: pip install torch transformers")
                self.method = "simplified"
                self.enabled = True
        elif method == "midas":
            if DEPTH_ESTIMATION_AVAILABLE and TRANSFORMERS_AVAILABLE:
                # Device is intentionally not logged here — reading it would
                # import torch and undo the deferral. load_model() logs it.
                logger.info(f"MiDaS ({model_size}) will be loaded on first use")
                self.enabled = False  # Will be enabled when model loads
            else:
                logger.warning("MiDaS requested but dependencies not available")
                logger.warning("Falling back to simplified method")
                logger.warning("Install with: pip install torch transformers")
                self.method = "simplified"
                self.enabled = True

    @property
    def device(self) -> str:
        """
        Compute device for depth estimation, resolved on first access.

        Importing torch to probe for CUDA is slow, so an "auto" request stays
        unresolved until something actually needs the answer.
        """
        if self._device_resolved is not None:
            return self._device_resolved

        resolved = "cpu"
        if DEPTH_ESTIMATION_AVAILABLE:
            try:
                import torch

                if torch.cuda.is_available():
                    resolved = "cuda"
                    logger.info("Auto-detected CUDA GPU for depth estimation")
                else:
                    # AMD/Intel GPUs on Windows have no CUDA path - DirectML
                    # (the `torch-directml` package) is the realistic
                    # acceleration route there, but HF's pipeline(device=...)
                    # below only understands a CUDA device index or -1/CPU,
                    # not a DirectML device object; using one would mean
                    # loading the model manually and moving it with .to(),
                    # not just passing a device string. Not implemented -
                    # no AMD/DirectML hardware available here to verify the
                    # pipeline actually produces correct output that way, so
                    # this only detects and logs rather than silently doing
                    # nothing or pretending to use it untested.
                    try:
                        import torch_directml
                        if torch_directml.is_available():
                            logger.info(
                                "DirectML-capable device detected (torch_directml) "
                                "but not wired for depth estimation yet - falling "
                                "back to CPU. See DepthEstimator's set_device()."
                            )
                    except ImportError:
                        pass
                    logger.info("Using CPU for depth estimation (no GPU detected)")
            except Exception as e:
                logger.warning(f"Could not load PyTorch for device detection: {e}")

        self._device_resolved = resolved
        return resolved

    def set_hardware_depth_source(self, source_fn):
        """
        Wire a real hardware depth source for method="realsense".

        Args:
            source_fn: Callable[[Optional[Tuple[int, int]]], Optional[np.ndarray]]
                returning the latest depth map in meters (float32, aligned
                to the RGB frame), or None to clear the source (e.g. when
                the RealSense camera is deactivated). Takes an optional
                (width, height) to resize to - passed through so the
                resize can happen on the source's own cheaper raw data
                before an expensive per-pixel conversion, not after (see
                RGBCameraRealSense.get_depth_frame).
        """
        self._hardware_depth_source = source_fn

    def set_device(self, device: str):
        """
        Force the compute device for depth estimation instead of leaving it
        on auto-detection.

        Args:
            device: 'cpu', 'cuda', or 'auto' (re-run auto-detection next access)
        """
        device = device.lower()
        if device not in ('cpu', 'cuda', 'auto'):
            logger.warning(f"Unknown depth-estimation device '{device}', ignoring")
            return

        self._device_requested = device
        self._device_resolved = None if device == 'auto' else device

        # A model already loaded on a different device needs to reload -
        # cheap for 'simplified' (no model at all), unavoidable for
        # depthanything since HF's pipeline() bakes the device in at load
        # time rather than letting it be changed after the fact.
        if self.model_loaded and self.method != 'simplified':
            self.model_loaded = False
            self.pipeline = None
            logger.info(f"Depth estimation device changed to '{device}' - model will reload on next use")

        logger.info(f"Depth estimation device set to: {device}")

    def load_model(self) -> bool:
        """
        Load depth estimation model (DepthAnything V2 or MiDaS).

        Model is loaded lazily on first inference call.

        Returns:
            True if model loaded successfully
        """
        global TRANSFORMERS_AVAILABLE

        if self.method == "simplified":
            self.model_loaded = True
            self.enabled = True
            return True

        if not DEPTH_ESTIMATION_AVAILABLE:
            logger.error("Cannot load model - PyTorch not available")
            logger.error("Install with: pip install torch")
            return False

        if self.model_loaded:
            logger.info("Depth model already loaded")
            return True

        try:
            if self.method == "depthanything":
                try:
                    from transformers import pipeline
                    TRANSFORMERS_AVAILABLE = True
                except ImportError:
                    logger.error("Cannot load DepthAnything V2 - transformers not available")
                    logger.error("Install with: pip install transformers")
                    return False
                except Exception as e:
                    logger.error(f"Cannot load transformers: {e}")
                    return False

                model_map = {
                    "small": "depth-anything/Depth-Anything-V2-Small-hf",
                    "base": "depth-anything/Depth-Anything-V2-Base-hf",
                    "large": "depth-anything/Depth-Anything-V2-Large-hf"
                }

                model_id = model_map.get(self.model_size, model_map["small"])
                logger.info(f"Loading DepthAnything V2: {model_id}")
                logger.info(f"Device: {self.device}")
                logger.info("First-time download: ~100-350MB (cached for future use)...")

                device_id = 0 if self.device == "cuda" else -1

                self.pipeline = pipeline(
                    task="depth-estimation",
                    model=model_id,
                    device=device_id
                )

                logger.info(f"✓ DepthAnything V2 ({self.model_size}) loaded successfully")
                self.model_loaded = True
                self.enabled = True
                return True

            elif self.method == "midas":
                try:
                    from transformers import pipeline
                    TRANSFORMERS_AVAILABLE = True
                except ImportError:
                    logger.error("Cannot load MiDaS - transformers not available")
                    logger.error("Install with: pip install transformers")
                    return False
                except Exception as e:
                    logger.error(f"Cannot load transformers: {e}")
                    return False

                # Intel's DPT (Dense Prediction Transformer) models, the
                # HuggingFace-hosted MiDaS family - same depth-estimation
                # pipeline API as DepthAnything above, different weights.
                # Verified these three exist and declare pipeline_tag
                # "depth-estimation" before wiring them in.
                model_map = {
                    "small": "Intel/dpt-swinv2-tiny-256",
                    "base": "Intel/dpt-hybrid-midas",
                    "large": "Intel/dpt-large",
                }
                model_id = model_map.get(self.model_size, model_map["base"])
                logger.info(f"Loading MiDaS: {model_id}")
                logger.info(f"Device: {self.device}")
                logger.info("First-time download: ~100-1300MB depending on size (cached for future use)...")

                device_id = 0 if self.device == "cuda" else -1

                self.pipeline = pipeline(
                    task="depth-estimation",
                    model=model_id,
                    device=device_id
                )

                logger.info(f"✓ MiDaS ({model_id}) loaded successfully")
                self.model_loaded = True
                self.enabled = True
                return True

            return False
        except Exception as e:
            logger.error(f"Error loading depth model: {e}")
            import traceback
            traceback.print_exc()
            return False

    def estimate_depth(self, rgb_image: np.ndarray) -> Optional[np.ndarray]:
        """
        Estimate depth map from RGB image.

        Args:
            rgb_image: RGB image (H, W, 3) uint8

        Returns:
            Depth map (H, W) float32, values in meters, or None if failed
            Closer objects have smaller values (typical range: 0.5m-5.0m)
        """
        # No `if not self.enabled: return None` gate here - for
        # depthanything/midas, self.enabled only becomes True *after*
        # load_model() succeeds (see __init__), and load_model() is only
        # ever called from the method-specific handlers below. Gating on
        # it here meant those handlers could never run at all through the
        # normal call path - confirmed live: every call short-circuited
        # with "Depth estimator not enabled" before ever attempting to
        # load or infer, so depthanything/midas never did anything.
        # ParallaxCompensator.apply_correction() already checks its own
        # separate `enabled` flag (whether depth-based correction is
        # turned on at all) before ever calling this method - that's the
        # real gate; each handler below manages its own lazy-load.
        if rgb_image is None or rgb_image.size == 0:
            return None

        try:
            if self.method == "simplified":
                return self._estimate_depth_simplified(rgb_image)
            elif self.method == "realsense":
                return self._estimate_depth_realsense(rgb_image)
            elif self.method == "depthanything":
                return self._estimate_depth_depthanything(rgb_image)
            elif self.method == "midas":
                return self._estimate_depth_midas(rgb_image)

            return None
        except Exception as e:
            logger.error(f"Error estimating depth: {e}")
            return None

    def _estimate_depth_realsense(self, rgb_image: np.ndarray) -> Optional[np.ndarray]:
        """
        Real measured depth from an active RealSense camera - not an
        estimate. Ignores rgb_image's pixel content entirely (unlike every
        other method here); only its shape is used, to resize the hardware
        depth map to match if the two aren't already the same resolution.

        Returns None (falls through to "no correction this frame" in
        apply_correction()) if no RealSense camera is wired as the active
        RGB source - this method never falls back to an estimate, since
        presenting an estimate as if it were the real thing is exactly what
        this method exists to avoid.
        """
        if self._hardware_depth_source is None:
            logger.warning(
                "Depth method is 'realsense' but no RealSense camera is active - "
                "connect one, or switch to 'simplified'/'midas'/'depthanything'"
            )
            return None

        h, w = rgb_image.shape[:2]
        # Request the source pre-resized to (w, h) - lets it resize its own
        # cheap raw data BEFORE an expensive per-pixel conversion (see
        # RGBCameraRealSense.get_depth_frame) rather than after, same class
        # of fix as the 4K-RGB depth-estimation cost already fixed for the
        # simplified/midas/depthanything methods. Still checked/resized
        # here too as a cheap no-op safety net in case the source ignores
        # resize_to or wasn't updated to support it.
        depth_m = self._hardware_depth_source((w, h))
        if depth_m is None:
            return None

        if depth_m.shape[:2] != (h, w):
            depth_m = cv2.resize(depth_m, (w, h), interpolation=cv2.INTER_NEAREST)

        return depth_m

    def _estimate_depth_simplified(self, rgb_image: np.ndarray) -> np.ndarray:
        """
        Simplified depth estimation using geometric heuristics.

        Assumes:
        - Typical inspection distance: 1-3 meters
        - Top of frame = farther (ceiling/background)
        - Bottom of frame = closer (equipment/floor)
        - Center focus distance = ~2 meters

        Args:
            rgb_image: RGB image (H, W, 3)

        Returns:
            Depth map (H, W) in meters
        """
        h, w = rgb_image.shape[:2]

        # This heuristic never reads rgb_image's actual pixel content, only
        # its shape - the result is identical every frame for a fixed
        # resolution, so cache it instead of rebuilding via
        # GaussianBlur+tile+linspace every single call. Return a copy so a
        # caller mutating its result in place can't corrupt the cache.
        if self._simplified_depth_shape == (h, w) and self._simplified_depth_cache is not None:
            return self._simplified_depth_cache.copy()

        y_coords = np.linspace(3.0, 1.0, h, dtype=np.float32)
        depth_map = np.tile(y_coords[:, np.newaxis], (1, w))
        depth_map = cv2.GaussianBlur(depth_map, (5, 5), 1.0)

        self._simplified_depth_shape = (h, w)
        self._simplified_depth_cache = depth_map
        return depth_map.copy()

    def _estimate_depth_midas(self, rgb_image: np.ndarray) -> Optional[np.ndarray]:
        """
        Estimate depth using MiDaS (Intel DPT) via HuggingFace Transformers.

        Args:
            rgb_image: RGB image (H, W, 3)

        Returns:
            Depth map (H, W) in meters, normalized to 0.5m-5.0m range
        """
        return self._estimate_depth_hf_pipeline(rgb_image, model_label="MiDaS")

    def _estimate_depth_depthanything(self, rgb_image: np.ndarray) -> Optional[np.ndarray]:
        """
        Estimate depth using DepthAnything V2 model via HuggingFace Transformers.

        Args:
            rgb_image: RGB image (H, W, 3) uint8

        Returns:
            Depth map (H, W) in meters, normalized to 0.5m-5.0m range
        """
        return self._estimate_depth_hf_pipeline(rgb_image, model_label="DepthAnything V2")

    def _estimate_depth_hf_pipeline(self, rgb_image: np.ndarray, model_label: str) -> Optional[np.ndarray]:
        """
        Shared inference path for any HuggingFace depth-estimation pipeline
        (DepthAnything and MiDaS both use it - same pipeline API, different
        weights, identical output post-processing).

        Args:
            rgb_image: RGB image (H, W, 3) uint8
            model_label: Human-readable name for log messages only

        Returns:
            Depth map (H, W) in meters, normalized to 0.5m-5.0m range
        """
        if self.pipeline is None:
            if not self.load_model():
                logger.error(f"Failed to load {model_label} model")
                return None

        try:
            from PIL import Image

            if rgb_image.shape[2] == 3:
                rgb_for_model = cv2.cvtColor(rgb_image, cv2.COLOR_BGR2RGB)
            else:
                rgb_for_model = rgb_image

            pil_image = Image.fromarray(rgb_for_model)
            result = self.pipeline(pil_image)
            depth_pil = result["depth"]
            depth_array = np.array(depth_pil).astype(np.float32)

            h, w = rgb_image.shape[:2]
            if depth_array.shape != (h, w):
                depth_array = cv2.resize(depth_array, (w, h), interpolation=cv2.INTER_LINEAR)

            depth_min = depth_array.min()
            depth_max = depth_array.max()

            if depth_max > depth_min:
                depth_normalized = (depth_array - depth_min) / (depth_max - depth_min)
                depth_inverted = 1.0 - depth_normalized
                depth_meters = 0.5 + depth_inverted * 4.5
            else:
                depth_meters = np.full_like(depth_array, 2.0)

            return depth_meters

        except Exception as e:
            logger.error(f"{model_label} inference failed: {e}")
            import traceback
            traceback.print_exc()
            return None


class ParallaxCompensator:
    """
    Computes and applies parallax correction to align thermal and RGB cameras.

    Uses depth map to calculate per-pixel displacement based on camera geometry.
    """

    def __init__(self, camera_geometry: Optional[CameraGeometry] = None,
                 depth_method: str = "simplified"):
        """
        Initialize parallax compensator.

        Args:
            camera_geometry: Camera geometric parameters
            depth_method: Depth estimation method ("simplified", "depthanything", "midas")
        """
        self.geometry = camera_geometry or CameraGeometry()
        self.depth_estimator = DepthEstimator(method=depth_method)
        self.enabled = False  # CRITICAL: Disabled by default
        self.show_depth_map = False  # Whether to return depth-map overlay instead of corrected thermal
        self.show_displacement = False  # Whether to overlay a sparse displacement-vector grid (debug)

        # Manual alignment shift (pixels) - a constant, distance-independent
        # translation on top of (or instead of, when depth-based correction
        # is disabled) the depth-based correction. Depth-based correction
        # only ever handles the X-axis baseline disparity that varies with
        # distance; a fixed mechanical mounting offset between the two
        # cameras doesn't vary with distance and isn't something depth
        # estimation corrects for at all - this is for that.
        self.manual_shift_x = 0
        self.manual_shift_y = 0

        # Which frame actually gets warped/cropped to align with the
        # other - "thermal" (default, this module's original behavior) or
        # "rgb". "rgb" is generally the better choice when the RGB sensor
        # has substantially more native resolution than the thermal one
        # (true for every camera pair this app supports - Boson/Tau2/
        # Lepton are all far lower-resolution than any UVC/Firefly/GigE/
        # RealSense RGB source): the abundant RGB pixels absorb the
        # crop/warp loss while thermal stays byte-for-byte as captured.
        # This isn't just about pixel count either - thermal pixel values
        # are real radiometric measurements, not cosmetic appearance, so
        # every OTHER consumer of thermal_frame (spot meter, isotherm
        # overlay, calibration, radiometric anomaly detection) currently
        # reads a bilinear-interpolated blend of neighboring temperature
        # readings whenever correction_target=="thermal" and depth-based
        # correction is active - not the sensor's actual per-pixel
        # measurement. correction_target=="rgb" leaves thermal completely
        # untouched for all of that.
        #
        # Kept as an opt-in setting rather than switching the default,
        # since the sign/scale conversion to RGB's own resolution and
        # focal length (see _apply_correction_rgb_target) is derived from
        # the existing thermal-shift formula's convention, not yet
        # verified against real hardware the way that formula's own
        # thermal-shift direction has been over this project's testing.
        self.correction_target = "thermal"

        # Derived from the existing thermal-shift formula's convention
        # (see _apply_correction_rgb_target), NOT yet confirmed against
        # real hardware. If RGB alignment ever visibly drifts in the
        # wrong direction as depth changes (misalignment gets worse
        # instead of better with distance, or a manual shift moves things
        # the opposite way from what the sign implies it should), this is
        # the one value to flip to -1.0/+1.0.
        self._rgb_target_sign = -1.0

        # Static crop-in zoom factor correcting a genuine FOV mismatch
        # between the thermal and RGB sensors (from their focal lengths and
        # sensor widths - a fixed optical property, not something that
        # varies frame to frame like parallax disparity does). Unlike the
        # per-frame shift/crop below, applying a resize here is correct:
        # it's compensating a real difference in what each camera actually
        # sees, not introducing an artifact. Computed via
        # compute_fov_crop_factor()/compute_auto_alignment(), 1.0 = no crop.
        self.fov_zoom_factor = 1.0

        # Cache
        self.last_depth_map = None
        self.last_displacement_map = None
        # _remap_thermal's coordinate grid only depends on (h, w), which is
        # constant frame-to-frame - cache it instead of rebuilding via
        # np.meshgrid() every single call. Profiled live: ~1.8ms/frame of
        # the ~15.5ms "simple geometric transform" total was this alone.
        self._coord_grid_shape = None
        self._coord_grid_xy = None

        # Last-call timing, in milliseconds - feeds the Parallax panel's
        # "Performance" section (depth_time_label/correction_time_label),
        # previously built but never actually populated by anything.
        self.last_depth_time_ms = 0.0
        self.last_correction_time_ms = 0.0

        # GPU (torch/CUDA) remap state - see _resolve_remap_gpu(). Measured
        # ~3x faster (2.93ms vs ~9ms/frame) and more consistent than the
        # CPU cv2.remap path (GPU compute has much less exposure to OS
        # scheduling jitter than a CPU-bound per-pixel remap over a
        # 300k+ pixel frame).
        self._remap_gpu_ready = False
        self._remap_gpu_device = None
        self._remap_gpu_coord_grid_shape = None
        self._remap_gpu_coord_grid_xy = None  # cached (xs, ys) torch tensors

        logger.info("ParallaxCompensator initialized (DISABLED by default)")
        logger.info(f"  Baseline: {self.geometry.baseline_mm}mm")
        logger.info(f"  Depth method: {depth_method}")

    def enable(self, enabled: bool = True):
        """Enable or disable parallax compensation."""
        self.enabled = enabled
        logger.info(f"Parallax compensation: {'ENABLED' if enabled else 'DISABLED'}")

    def is_enabled(self) -> bool:
        """Check if parallax compensation is enabled."""
        return self.enabled

    def set_depth_display(self, show: bool):
        """Enable or disable depth-map overlay mode.

        When True, apply_correction() returns a colourised depth-map frame
        instead of the corrected thermal frame so the user can inspect depth
        estimation quality directly in the video stream.
        """
        self.show_depth_map = show
        logger.info(f"Parallax depth-map overlay: {'ON' if show else 'OFF'}")

    def set_displacement_display(self, show: bool):
        """Enable or disable displacement-vector overlay mode.

        When True, apply_correction() draws a sparse grid of arrows over
        the corrected thermal frame showing the actual per-pixel shift
        applied - lets you see at a glance whether correction is doing
        something reasonable (consistent direction/magnitude) or garbage
        (random-looking vectors) without reading raw numbers.
        """
        self.show_displacement = show
        logger.info(f"Parallax displacement-vector overlay: {'ON' if show else 'OFF'}")

    def set_baseline(self, baseline_mm: float):
        """Set camera baseline distance in millimeters."""
        self.geometry.baseline_mm = baseline_mm
        logger.info(f"Parallax baseline set to {baseline_mm}mm")
        self.last_displacement_map = None

    def set_device(self, device: str):
        """Force the compute device ('cpu', 'cuda', or 'auto') used for depth estimation."""
        self.depth_estimator.set_device(device)

    def set_hardware_depth_source(self, source_fn):
        """Wire a real hardware depth source (e.g. a RealSense camera) for depth_method="realsense"."""
        self.depth_estimator.set_hardware_depth_source(source_fn)

    def set_correction_target(self, target: str):
        """
        Choose which frame apply_correction() actually warps/crops to
        align with the other: "thermal" (default) or "rgb".

        "rgb" is generally the better choice whenever the RGB sensor has
        substantially more native resolution than the thermal one (true
        for every camera pair this app supports) - see this class's
        correction_target comment in __init__ for the full reasoning
        (spare RGB pixels absorb the crop/warp loss; thermal pixel values
        are real radiometric measurements that stay byte-for-byte exact
        instead of being bilinear-blended by the remap).

        Switching targets changes which frame's pixel space
        manual_shift_x/manual_shift_y are expressed in - a shift tuned
        for one target is not meaningful for the other (different
        resolution, different focal length in pixels). Re-tune (or
        re-run Auto-Calculate Alignment) after switching.
        """
        target = target.lower()
        if target not in ("thermal", "rgb"):
            logger.warning(f"Unknown parallax correction target '{target}', ignoring")
            return
        if target != self.correction_target:
            logger.info(
                f"Parallax correction target changed to '{target}' - manual shift "
                f"({self.manual_shift_x}, {self.manual_shift_y})px was tuned for the "
                f"other target's pixel space and likely needs re-tuning"
            )
        self.correction_target = target

    def get_correction_target(self) -> str:
        """Get which frame apply_correction() currently warps/crops ("thermal" or "rgb")."""
        return self.correction_target

    def set_manual_shift(self, dx: int, dy: int):
        """
        Set a constant manual alignment shift (pixels), independent of
        depth-based correction. Use this for a fixed mechanical mounting
        offset between the thermal and RGB cameras - something that
        doesn't vary with distance, so depth estimation can't and
        shouldn't try to correct for it.
        """
        self.manual_shift_x = int(dx)
        self.manual_shift_y = int(dy)
        logger.info(f"Manual alignment shift set to ({self.manual_shift_x}, {self.manual_shift_y}) px")

    def get_manual_shift(self) -> Tuple[int, int]:
        """Get the current manual alignment shift (dx, dy) in pixels."""
        return (self.manual_shift_x, self.manual_shift_y)

    def has_manual_shift(self) -> bool:
        """Whether a non-zero manual shift or FOV crop-zoom is set."""
        return (self.manual_shift_x != 0 or self.manual_shift_y != 0
                or abs(self.fov_zoom_factor - 1.0) > 1e-3)

    def set_fov_zoom_factor(self, factor: float):
        """
        Set the static crop-in zoom factor applied on top of any shift, e.g.
        to correct a real FOV mismatch between the two sensors. 1.0 = none.
        """
        self.fov_zoom_factor = max(1.0, float(factor))
        logger.info(f"Parallax FOV crop-zoom factor set to {self.fov_zoom_factor:.4f}")

    def get_fov_zoom_factor(self) -> float:
        """Get the current static FOV crop-zoom factor."""
        return self.fov_zoom_factor

    def compute_fov_crop_factor(self) -> float:
        """
        Compute the crop-in zoom factor needed to make the thermal camera's
        horizontal FOV match the RGB camera's, from each camera's focal
        length and sensor width (self.geometry). This is a fixed optical
        property - it doesn't depend on distance to the subject, only on
        the two cameras' own optics.

        Returns 1.0 (no crop needed) if correction_target's own FOV is
        already the same or narrower than the other camera's - this only
        ever crops whichever frame correction_target points to, so it
        can't correct the opposite case (the OTHER camera being the
        narrower one) without also touching that frame instead.
        """
        thermal_half_fov = math.atan2(self.geometry.thermal_sensor_width_mm / 2.0,
                                     self.geometry.thermal_focal_length_mm)
        rgb_half_fov = math.atan2(self.geometry.rgb_sensor_width_mm / 2.0,
                                 self.geometry.rgb_focal_length_mm)

        if self.correction_target == "rgb":
            target_half_fov, fixed_half_fov = rgb_half_fov, thermal_half_fov
        else:
            target_half_fov, fixed_half_fov = thermal_half_fov, rgb_half_fov

        if target_half_fov <= fixed_half_fov:
            return 1.0

        # Crop the target frame down to the angular width the fixed
        # camera actually covers, then that crop gets resized back up to
        # full resolution (see _apply_fov_zoom) - the ratio of the
        # tangents of the half-FOV angles is exactly the fraction of the
        # target sensor's width that subtends the fixed camera's
        # (narrower) FOV.
        return math.tan(target_half_fov) / math.tan(fixed_half_fov)

    def compute_geometric_shift_px(self, working_distance_m: float) -> int:
        """
        Compute the horizontal pixel disparity expected at a given subject
        distance, in whichever frame's pixel space correction_target
        points to - the same formula as compute_disparity()/
        compute_disparity_rgb(), applied to a single scalar distance
        instead of a per-pixel depth map.
        """
        working_distance_m = max(0.05, float(working_distance_m))
        if self.correction_target == "rgb":
            focal_px = (self.geometry.rgb_focal_length_mm /
                      self.geometry.rgb_sensor_width_mm *
                      self.geometry.rgb_resolution[0])
            sign = self._rgb_target_sign
        else:
            focal_px = (self.geometry.thermal_focal_length_mm /
                      self.geometry.thermal_sensor_width_mm *
                      self.geometry.thermal_resolution[0])
            sign = 1.0
        disparity_px = (self.geometry.baseline_mm * focal_px) / (working_distance_m * 1000.0)
        return int(round(sign * disparity_px))

    def compute_auto_alignment(self, working_distance_m: float = 2.0,
                              rgb_frame: Optional[np.ndarray] = None) -> Tuple[int, float]:
        """
        One-time alignment calculation from camera geometry, optionally
        refined by a single depth-estimation call - meant to be triggered
        on demand (e.g. a GUI button), not run every frame. The result is
        stored as a static manual shift + FOV crop-zoom factor, which then
        costs nothing further per frame (see _apply_manual_shift_only) -
        unlike leaving depth-based correction continuously enabled.

        Args:
            working_distance_m: Assumed subject distance in meters, used
                directly unless rgb_frame is provided.
            rgb_frame: If given, runs the currently-selected depth
                estimation method (whatever depth_estimator.method is set
                to - simplified/midas/depthanything/realsense) ONCE to
                measure/estimate the actual scene distance instead of
                trusting the assumed working_distance_m - this is the
                "depth estimation enhances this" refinement. Ignored if
                None (pure geometric calculation, no ML/hardware call).

        Returns:
            (dx_px, fov_zoom_factor) - the values that were applied.
        """
        resolved_distance_m = working_distance_m

        if rgb_frame is not None:
            try:
                thermal_w, thermal_h = self.geometry.thermal_resolution
                rgb_for_depth = rgb_frame
                if rgb_frame.shape[0] > thermal_h or rgb_frame.shape[1] > thermal_w:
                    rgb_for_depth = cv2.resize(rgb_frame, (thermal_w, thermal_h),
                                              interpolation=cv2.INTER_LINEAR)
                depth_map = self.depth_estimator.estimate_depth(rgb_for_depth)
                if depth_map is not None:
                    h, w = depth_map.shape[:2]
                    # Sample the central region only - the subject being
                    # aligned to is assumed to be roughly centered in frame,
                    # same assumption "simplified"'s center-distance already
                    # makes; avoids skew from background/foreground clutter
                    # at the edges.
                    cy0, cy1 = int(h * 0.4), int(h * 0.6)
                    cx0, cx1 = int(w * 0.4), int(w * 0.6)
                    center_region = depth_map[cy0:cy1, cx0:cx1]
                    valid = center_region[np.isfinite(center_region) & (center_region > 0)]
                    if valid.size > 0:
                        resolved_distance_m = float(np.median(valid))
                        logger.info(
                            f"Auto-alignment: refined working distance to "
                            f"{resolved_distance_m:.2f}m via {self.depth_estimator.method} depth estimation"
                        )
                    else:
                        logger.warning(
                            "Auto-alignment: depth estimation returned no valid center-region "
                            f"samples - falling back to assumed {working_distance_m:.2f}m"
                        )
                else:
                    logger.warning(
                        "Auto-alignment: depth estimation failed - falling back to "
                        f"assumed {working_distance_m:.2f}m"
                    )
            except Exception as e:
                logger.warning(f"Auto-alignment: depth refinement failed ({e}), using assumed distance")

        dx = self.compute_geometric_shift_px(resolved_distance_m)
        zoom = self.compute_fov_crop_factor()

        self.manual_shift_x = dx
        self.fov_zoom_factor = zoom

        logger.info(
            f"Auto-alignment computed: shift=({dx}, {self.manual_shift_y})px "
            f"at {resolved_distance_m:.2f}m, FOV crop-zoom={zoom:.4f}"
        )
        return dx, zoom

    def has_correction(self) -> bool:
        """
        Whether apply_correction() would do anything at all right now -
        either depth-based correction is enabled, or a manual shift is set
        (or both). Callers should gate on this instead of is_enabled()
        alone, so a manual-shift-only setup doesn't need depth-based
        correction turned on (and doesn't pay for depth estimation) just
        to get a fixed registration offset applied.
        """
        return self.enabled or self.has_manual_shift()

    def compute_disparity(self, depth_map: np.ndarray) -> np.ndarray:
        """
        Compute pixel disparity (in the THERMAL frame's own pixel space)
        from depth map using camera geometry.

        Formula: disparity = (baseline × focal_length) / depth

        Args:
            depth_map: Depth map in meters (H, W)

        Returns:
            Disparity map in pixels (H, W)
        """
        thermal_focal_px = (self.geometry.thermal_focal_length_mm /
                           self.geometry.thermal_sensor_width_mm *
                           self.geometry.thermal_resolution[0])

        disparity_px = (self.geometry.baseline_mm * thermal_focal_px) / (depth_map * 1000.0)

        return disparity_px.astype(np.float32)

    def compute_disparity_rgb(self, depth_map: np.ndarray, rgb_width_px: int) -> np.ndarray:
        """
        Compute pixel disparity in the RGB frame's own pixel space, using
        the RGB camera's own focal length and the RGB frame's ACTUAL live
        width (not a stored default resolution) - a camera's own angular
        resolution (pixels per radian) is what converts a physical
        baseline/depth-derived angular shift into a pixel count, and RGB's
        differs from thermal's, so the same physical disparity is a
        different number of pixels in each frame.

        Args:
            depth_map: Depth map in meters (H, W), same shape as the RGB
                frame this disparity will be applied to
            rgb_width_px: The RGB frame's actual width in pixels

        Returns:
            Disparity map in pixels (H, W), in RGB's pixel space
        """
        rgb_focal_px = (self.geometry.rgb_focal_length_mm /
                       self.geometry.rgb_sensor_width_mm *
                       rgb_width_px)

        disparity_px = (self.geometry.baseline_mm * rgb_focal_px) / (depth_map * 1000.0)

        return disparity_px.astype(np.float32)

    def apply_correction(self, thermal_frame: np.ndarray,
                        rgb_frame: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        Apply parallax correction, aligning one camera's view to the
        other's - which one actually gets warped/cropped is controlled by
        self.correction_target ("thermal", this module's original
        behavior, or "rgb" - see set_correction_target()'s docstring for
        why "rgb" is usually the better choice).

        Args:
            thermal_frame: Thermal image (H_t, W_t, C) or (H_t, W_t)
            rgb_frame: RGB image (H_r, W_r, 3), or None

        Returns:
            (thermal_out, rgb_out) - both always populated; whichever
            frame isn't the active correction_target is returned
            completely unmodified (not even copied).
        """
        if thermal_frame is None:
            return thermal_frame, rgb_frame

        if self.correction_target == "rgb":
            return self._apply_correction_rgb_target(thermal_frame, rgb_frame)
        return self._apply_correction_thermal_target(thermal_frame, rgb_frame)

    def _apply_correction_thermal_target(self, thermal_frame: np.ndarray,
                                        rgb_frame: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """correction_target=="thermal": warp/crop thermal to align with RGB. See apply_correction()."""
        if not self.enabled:
            # Depth-based correction is off, but a manual shift may still be
            # requested - apply just the constant translation. Skips depth
            # estimation entirely (no RGB frame needed, no GPU/CPU cost for
            # a plain mounting-offset correction).
            return self._apply_manual_shift_only(thermal_frame), rgb_frame

        if rgb_frame is None:
            return self._apply_manual_shift_only(thermal_frame), rgb_frame

        try:
            thermal_h, thermal_w = thermal_frame.shape[:2]

            # Depth output gets resized down to thermal resolution a few
            # lines below regardless of method, so estimating it at the
            # RGB camera's native resolution is pure waste - for
            # "simplified" specifically the result doesn't depend on pixel
            # content at all (only rgb_image.shape), so shrinking first
            # costs no accuracy either way. Confirmed live: with a 4K RGB
            # camera this stage alone was costing ~50-90ms/frame (vs
            # ~1-2ms at a normal RGB resolution) for a depth map that gets
            # immediately downsampled to 640x512 anyway.
            rgb_for_depth = rgb_frame
            if rgb_frame.shape[0] > thermal_h or rgb_frame.shape[1] > thermal_w:
                # INTER_LINEAR, not INTER_AREA: measured INTER_AREA at 7ms for
                # a 4K->640x512 downscale vs INTER_LINEAR's 0.9ms (OpenCV's
                # proper area-averaging is far more expensive than its
                # SIMD/IPP-optimized linear path at large downscale ratios).
                # The precision difference is moot here - "simplified" never
                # reads pixel content at all, and midas/depthanything resize
                # again internally to their own fixed model input size.
                rgb_for_depth = cv2.resize(rgb_frame, (thermal_w, thermal_h),
                                          interpolation=cv2.INTER_LINEAR)

            _t_depth_start = time.perf_counter()
            depth_map = self.depth_estimator.estimate_depth(rgb_for_depth)
            self.last_depth_time_ms = (time.perf_counter() - _t_depth_start) * 1000.0
            if depth_map is None:
                # Depth-based correction can't run this frame (e.g.
                # depth_method="realsense" but no RealSense hardware is
                # actually providing frames right now), but a manual
                # shift/FOV crop-zoom may still be configured - dropping
                # to a bare, completely uncorrected pass-through silently
                # discarded those too, every single frame depth failed,
                # not just the depth-based component. Fall back to
                # whatever static correction is available instead.
                logger.warning("Depth estimation failed - falling back to manual shift/crop only")
                return self._apply_manual_shift_only(thermal_frame), rgb_frame

            self.last_depth_map = depth_map

            _t_corr_start = time.perf_counter()
            depth_resized = cv2.resize(depth_map, (thermal_w, thermal_h),
                                      interpolation=cv2.INTER_LINEAR)

            disparity_map = self.compute_disparity(depth_resized)

            flow_map = np.zeros((thermal_h, thermal_w, 2), dtype=np.float32)
            flow_map[:, :, 0] = disparity_map + self.manual_shift_x
            flow_map[:, :, 1] = self.manual_shift_y

            self.last_displacement_map = flow_map

            # Return depth-map colourised overlay when requested (debug/QA mode)
            if self.show_depth_map:
                depth_colourised = self._colourise_depth_debug(depth_resized, thermal_w, thermal_h)
                self.last_correction_time_ms = (time.perf_counter() - _t_corr_start) * 1000.0
                return depth_colourised, rgb_frame

            corrected_thermal = self._remap_thermal(thermal_frame, flow_map)
            self.last_correction_time_ms = (time.perf_counter() - _t_corr_start) * 1000.0

            if self.show_displacement:
                corrected_thermal = self._draw_displacement_vectors(corrected_thermal, flow_map)

            return corrected_thermal, rgb_frame

        except Exception as e:
            logger.error(f"Error applying parallax correction: {e}")
            return thermal_frame, rgb_frame

    def _apply_correction_rgb_target(self, thermal_frame: np.ndarray,
                                    rgb_frame: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        correction_target=="rgb": warp/crop RGB to align with thermal,
        leaving thermal completely untouched. See apply_correction() and
        set_correction_target()'s docstrings for why.

        Runs the remap at RGB's own native resolution (not downscaled to
        thermal's), so the abundant RGB pixels genuinely absorb the
        crop/warp loss instead of it costing anything at thermal's
        (much smaller) scale - the tradeoff is that this remap step
        itself costs more CPU per frame than warping the smaller thermal
        frame did, proportional to RGB's resolution (e.g. a 4K RGB source
        costs substantially more here than a 640x512 one).
        """
        if not self.enabled:
            return thermal_frame, self._apply_manual_shift_only_rgb(rgb_frame)

        if rgb_frame is None:
            return thermal_frame, rgb_frame

        try:
            thermal_h, thermal_w = thermal_frame.shape[:2]
            rgb_h, rgb_w = rgb_frame.shape[:2]

            # Depth estimation still runs at thermal's (small) resolution
            # regardless of correction_target - it's an analysis step, not
            # the thing being warped, and downscaling first doesn't cost
            # accuracy for the same reasons _apply_correction_thermal_target
            # doesn't either.
            rgb_for_depth = rgb_frame
            if rgb_h > thermal_h or rgb_w > thermal_w:
                rgb_for_depth = cv2.resize(rgb_frame, (thermal_w, thermal_h),
                                          interpolation=cv2.INTER_LINEAR)

            _t_depth_start = time.perf_counter()
            depth_map = self.depth_estimator.estimate_depth(rgb_for_depth)
            self.last_depth_time_ms = (time.perf_counter() - _t_depth_start) * 1000.0
            if depth_map is None:
                # See _apply_correction_thermal_target's identical fallback
                # reasoning - don't drop a configured manual shift/FOV
                # crop-zoom just because depth-based correction couldn't
                # run this frame.
                logger.warning("Depth estimation failed - falling back to manual shift/crop only")
                return thermal_frame, self._apply_manual_shift_only_rgb(rgb_frame)

            self.last_depth_map = depth_map

            _t_corr_start = time.perf_counter()
            # Resize the depth map up to RGB's own native resolution (not
            # thermal's) - the disparity/flow map, and the remap it drives,
            # need to be at the same resolution as the frame being warped.
            depth_resized = cv2.resize(depth_map, (rgb_w, rgb_h),
                                      interpolation=cv2.INTER_LINEAR)

            disparity_map = self.compute_disparity_rgb(depth_resized, rgb_w)

            # Opposite sign convention from the thermal-target path - see
            # set_correction_target()'s docstring and _rgb_target_sign's
            # definition in __init__: aligning RGB to thermal's (now
            # unmoved) raw position is the inverse of aligning thermal to
            # RGB's raw position, derived from the same physical baseline
            # geometry. Manual shift is in RGB's own pixel space here, not
            # thermal's - a value tuned for correction_target=="thermal"
            # is not meaningful after switching (see set_correction_target).
            sign = self._rgb_target_sign
            flow_map = np.zeros((rgb_h, rgb_w, 2), dtype=np.float32)
            flow_map[:, :, 0] = sign * (disparity_map + self.manual_shift_x)
            flow_map[:, :, 1] = sign * self.manual_shift_y

            self.last_displacement_map = flow_map

            if self.show_depth_map:
                depth_colourised = self._colourise_depth_debug(depth_resized, rgb_w, rgb_h)
                self.last_correction_time_ms = (time.perf_counter() - _t_corr_start) * 1000.0
                return thermal_frame, depth_colourised

            corrected_rgb = self._remap_thermal(rgb_frame, flow_map)
            self.last_correction_time_ms = (time.perf_counter() - _t_corr_start) * 1000.0

            if self.show_displacement:
                corrected_rgb = self._draw_displacement_vectors(corrected_rgb, flow_map)

            return thermal_frame, corrected_rgb

        except Exception as e:
            logger.error(f"Error applying parallax correction (rgb target): {e}")
            return thermal_frame, rgb_frame

    def _colourise_depth_debug(self, depth_resized: np.ndarray, out_w: int, out_h: int) -> np.ndarray:
        """
        Shared "Show Depth Map" debug overlay for either correction
        target - colourises depth_resized and, for any non-hardware
        (estimated) depth method, watermarks it as such so a heuristic
        never reads as a real measurement (same reasoning as the 3D
        Fusion view).
        """
        d_norm = cv2.normalize(depth_resized, None, 0, 255, cv2.NORM_MINMAX)
        d_u8 = d_norm.astype(np.uint8)
        depth_colourised = cv2.applyColorMap(d_u8, cv2.COLORMAP_JET)
        if depth_colourised.shape[:2] != (out_h, out_w):
            depth_colourised = cv2.resize(depth_colourised, (out_w, out_h))

        if self.depth_estimator.method != "realsense":
            label = f"ESTIMATED depth ({self.depth_estimator.method}) - not measured"
            cv2.putText(depth_colourised, label, (10, 25),
                      cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2, cv2.LINE_AA)
            cv2.putText(depth_colourised, label, (10, 25),
                      cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 1, cv2.LINE_AA)

        return depth_colourised

    def _apply_manual_shift_only(self, thermal_frame: np.ndarray) -> np.ndarray:
        """Apply just the constant manual (dx, dy) shift, no depth estimation."""
        if not self.has_manual_shift():
            return thermal_frame

        h, w = thermal_frame.shape[:2]
        flow_map = np.zeros((h, w, 2), dtype=np.float32)
        flow_map[:, :, 0] = self.manual_shift_x
        flow_map[:, :, 1] = self.manual_shift_y
        self.last_displacement_map = flow_map

        corrected = self._remap_thermal(thermal_frame, flow_map)
        if self.show_displacement:
            corrected = self._draw_displacement_vectors(corrected, flow_map)
        return corrected

    def _apply_manual_shift_only_rgb(self, rgb_frame: Optional[np.ndarray]) -> Optional[np.ndarray]:
        """RGB-target equivalent of _apply_manual_shift_only - see _apply_correction_rgb_target."""
        if rgb_frame is None or not self.has_manual_shift():
            return rgb_frame

        h, w = rgb_frame.shape[:2]
        sign = self._rgb_target_sign
        flow_map = np.zeros((h, w, 2), dtype=np.float32)
        flow_map[:, :, 0] = sign * self.manual_shift_x
        flow_map[:, :, 1] = sign * self.manual_shift_y
        self.last_displacement_map = flow_map

        corrected = self._remap_thermal(rgb_frame, flow_map)
        if self.show_displacement:
            corrected = self._draw_displacement_vectors(corrected, flow_map)
        return corrected

    # Grid spacing (pixels) for the displacement-vector overlay - dense
    # enough to see spatial variation, sparse enough not to turn the whole
    # frame into a solid mass of arrows.
    _DISPLACEMENT_GRID_STEP = 32

    def _draw_displacement_vectors(self, frame: np.ndarray, flow_map: np.ndarray) -> np.ndarray:
        """
        Overlay a sparse grid of arrows showing the actual per-pixel shift
        that was just applied (flow_map's own (dx, dy) at each sampled
        point) - a way to see at a glance whether correction looks
        reasonable (consistent direction/magnitude, e.g. larger near
        objects than far ones) or clearly wrong (random-looking vectors),
        without reading raw displacement numbers.
        """
        vis = frame.copy()
        h, w = vis.shape[:2]
        step = self._DISPLACEMENT_GRID_STEP

        shift_x = flow_map[:, :, 0]
        shift_y = flow_map[:, :, 1]
        max_mag = float(np.sqrt(shift_x ** 2 + shift_y ** 2).max())

        for y in range(step // 2, h, step):
            for x in range(step // 2, w, step):
                dx = float(shift_x[y, x])
                dy = float(shift_y[y, x])
                mag = (dx ** 2 + dy ** 2) ** 0.5
                # Green (small shift) -> red (large shift), relative to
                # this frame's own max so the color scale stays meaningful
                # regardless of how far the camera is from the subject.
                t = 0.0 if max_mag < 1e-6 else min(1.0, mag / max_mag)
                color = (0, int(255 * (1.0 - t)), int(255 * t))  # BGR: green->red
                end_x = int(round(x + dx))
                end_y = int(round(y + dy))
                cv2.arrowedLine(vis, (x, y), (end_x, end_y), color, 1, tipLength=0.35)

        return vis

    def _resolve_remap_gpu(self) -> bool:
        """
        Lazily resolve whether a CUDA GPU is usable for the remap step.
        Never raises - returns False (CPU fallback) on any failure.
        """
        if self._remap_gpu_ready:
            return True
        if not DEPTH_ESTIMATION_AVAILABLE:  # torch importable - see module-level check
            return False
        try:
            import torch
            if not torch.cuda.is_available():
                return False
            self._remap_gpu_device = "cuda"
            self._remap_gpu_ready = True
            logger.info(f"Parallax remap: GPU acceleration active ({torch.cuda.get_device_name(0)})")
            return True
        except Exception as e:
            logger.warning(f"Parallax remap: failed to initialize GPU path, falling back to CPU: {e}")
            return False

    def _remap_thermal_gpu(self, thermal_frame: np.ndarray, flow_map: np.ndarray,
                          h: int, w: int) -> np.ndarray:
        """GPU (torch/CUDA) implementation of the remap step - see _remap_thermal_cpu for the CPU equivalent."""
        import torch
        import torch.nn.functional as F

        device = self._remap_gpu_device
        if self._remap_gpu_coord_grid_shape != (h, w):
            ys, xs = torch.meshgrid(
                torch.arange(h, device=device, dtype=torch.float32),
                torch.arange(w, device=device, dtype=torch.float32),
                indexing='ij'
            )
            self._remap_gpu_coord_grid_xy = (xs, ys)
            self._remap_gpu_coord_grid_shape = (h, w)
        xs, ys = self._remap_gpu_coord_grid_xy

        shift_x_t = torch.from_numpy(np.ascontiguousarray(flow_map[:, :, 0])).to(device, dtype=torch.float32)
        shift_y_t = torch.from_numpy(np.ascontiguousarray(flow_map[:, :, 1])).to(device, dtype=torch.float32)
        map_x = xs - shift_x_t
        map_y = ys - shift_y_t

        # grid_sample expects normalized [-1, 1] coordinates, not pixel
        # indices - and uses BORDER_REPLICATE-equivalent padding, matching
        # the CPU path's borderMode=cv2.BORDER_REPLICATE (the smeared
        # border strip this produces is exactly what the crop-then-rescale
        # step below discards either way).
        grid_x = (map_x / max(w - 1, 1)) * 2 - 1
        grid_y = (map_y / max(h - 1, 1)) * 2 - 1
        grid = torch.stack([grid_x, grid_y], dim=-1).unsqueeze(0)

        img_t = torch.from_numpy(thermal_frame).to(device, dtype=torch.float32).permute(2, 0, 1).unsqueeze(0)
        out = F.grid_sample(img_t, grid, mode='bilinear', padding_mode='border', align_corners=True)
        out = torch.clamp(out, 0, 255)
        return out.squeeze(0).permute(1, 2, 0).contiguous().to(torch.uint8).cpu().numpy()

    def _remap_thermal_cpu(self, thermal_frame: np.ndarray, flow_map: np.ndarray,
                          h: int, w: int) -> np.ndarray:
        """CPU (cv2.remap) implementation of the remap step."""
        # (x_coords, y_coords) depend only on (h, w), not on any per-frame
        # data - cache instead of rebuilding via np.meshgrid() (plus its
        # internal broadcast_arrays/reshape machinery) every single call.
        # Pre-cast to float32 here too, so the subtraction below doesn't
        # promote to float64 and cast back every frame.
        if self._coord_grid_shape != (h, w):
            x_coords, y_coords = np.meshgrid(np.arange(w), np.arange(h))
            self._coord_grid_xy = (x_coords.astype(np.float32), y_coords.astype(np.float32))
            self._coord_grid_shape = (h, w)
        x_coords, y_coords = self._coord_grid_xy

        map_x = x_coords - flow_map[:, :, 0]
        map_y = y_coords - flow_map[:, :, 1]

        return cv2.remap(thermal_frame, map_x, map_y,
                        interpolation=cv2.INTER_LINEAR,
                        borderMode=cv2.BORDER_REPLICATE)

    def _remap_thermal(self, thermal_frame: np.ndarray,
                      flow_map: np.ndarray) -> np.ndarray:
        """
        Remap thermal frame using displacement map (cv2.remap).

        A GPU (torch/CUDA) path exists (_remap_thermal_gpu) and measured
        ~3x faster in isolation (2.93ms vs ~9ms), but measured *slower*
        (11.24ms vs 7.18ms) as part of the real apply_correction() call
        chain, interleaved with the other CPU-bound work each frame
        (depth fetch, resize, disparity) - the per-call GPU upload/launch
        overhead isn't amortized the way a tight isolated benchmark loop
        lets it be. Unlike the 3D Fusion relief/fog/contours effects
        (dense, standalone per-pixel math with nothing else competing for
        the GPU queue in between calls), this remap step is comparatively
        light per-pixel work where that overhead isn't worth paying for.
        Not wired into the default path - kept available (see
        _resolve_remap_gpu/_remap_thermal_gpu) in case a future caller
        pattern (e.g. batching, or removing the CPU work interleaved with
        it) makes it worthwhile, but always falls through to CPU for now.
        """
        h, w = thermal_frame.shape[:2]
        corrected = self._remap_thermal_cpu(thermal_frame, flow_map, h, w)

        # BORDER_REPLICATE smears the edge row/column across whatever strip
        # shifted off-frame, rather than leaving a gap. This used to crop
        # that strip away and cv2.resize() the remainder back up to the
        # original size - which zooms/stretches the ENTIRE frame (not just
        # the edge) to fill the gap, distorting real thermal readings
        # everywhere via resize interpolation, not just at the border. A
        # real crop shouldn't stretch the valid interior at all - blank the
        # invalid strip instead and leave every other pixel exactly as
        # measured (same "no fake data" reasoning as the depth-map
        # watermark: don't manufacture pixel values, even by interpolation,
        # where there's no real aligned data).
        shift_x = flow_map[:, :, 0]
        shift_y = flow_map[:, :, 1]

        # map_x = x - shift_x goes out of [0, w) on the LEFT wherever
        # shift_x is large positive (small x - large shift < 0), and out on
        # the RIGHT wherever shift_x is large negative (x near w-1 + |shift|
        # exceeds w-1) - blank only the actual max magnitude present on each
        # side, not a blanket worst case, so a small shift doesn't blank
        # more field of view than it has to.
        left_crop = max(0, min(w, int(np.ceil(shift_x.max()))))
        right_crop = max(0, min(w, int(np.ceil(-shift_x.min()))))
        top_crop = max(0, min(h, int(np.ceil(shift_y.max()))))
        bottom_crop = max(0, min(h, int(np.ceil(-shift_y.min()))))

        if top_crop:
            corrected[:top_crop, :] = 0
        if bottom_crop:
            corrected[h - bottom_crop:, :] = 0
        if left_crop:
            corrected[:, :left_crop] = 0
        if right_crop:
            corrected[:, w - right_crop:] = 0

        if abs(self.fov_zoom_factor - 1.0) > 1e-3:
            corrected = self._apply_fov_zoom(corrected)

        return corrected

    def _apply_fov_zoom(self, frame: np.ndarray) -> np.ndarray:
        """
        Crop-and-zoom by self.fov_zoom_factor to correct a real FOV
        mismatch between the thermal and RGB sensors (see
        compute_fov_crop_factor). Unlike the per-frame shift/crop above,
        a resize here is correct rather than a "stretch" artifact - it's a
        static, one-time correction for a genuine optical difference
        between the two cameras, not per-frame jitter, and is only ever
        applied when the user has explicitly computed/set a zoom factor.
        """
        h, w = frame.shape[:2]
        crop_w = max(1, min(w, int(round(w / self.fov_zoom_factor))))
        crop_h = max(1, min(h, int(round(h / self.fov_zoom_factor))))
        x0 = (w - crop_w) // 2
        y0 = (h - crop_h) // 2
        cropped = frame[y0:y0 + crop_h, x0:x0 + crop_w]
        return cv2.resize(cropped, (w, h), interpolation=cv2.INTER_LINEAR)

    def get_depth_map(self) -> Optional[np.ndarray]:
        """Get last computed depth map for visualization."""
        return self.last_depth_map

    def get_displacement_map(self) -> Optional[np.ndarray]:
        """Get last computed displacement map for debugging."""
        return self.last_displacement_map

    def get_info(self) -> dict:
        """Get parallax compensator information."""
        return {
            'enabled': self.enabled,
            'depth_method': self.depth_estimator.method,
            'baseline_mm': self.geometry.baseline_mm,
            'thermal_resolution': self.geometry.thermal_resolution,
            'rgb_resolution': self.geometry.rgb_resolution,
            'depth_available': self.last_depth_map is not None,
            'manual_shift': (self.manual_shift_x, self.manual_shift_y),
            'fov_zoom_factor': self.fov_zoom_factor,
        }


def create_parallax_compensator(baseline_mm: float = 50.0,
                                depth_method: str = "simplified",
                                enabled: bool = False) -> ParallaxCompensator:
    """
    Create and configure parallax compensator.

    Args:
        baseline_mm: Camera baseline distance (mm)
        depth_method: "simplified", "depthanything", or "midas"
        enabled: Enable parallax correction (default: False)

    Returns:
        Configured ParallaxCompensator instance
    """
    geometry = CameraGeometry(baseline_mm=baseline_mm)
    compensator = ParallaxCompensator(camera_geometry=geometry,
                                     depth_method=depth_method)
    compensator.enable(enabled)

    return compensator


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("\n" + "="*70)
    print("PARALLAX COMPENSATOR TEST")
    print("="*70)

    compensator = create_parallax_compensator(baseline_mm=50.0, enabled=False)

    print("\nCompensator info:")
    info = compensator.get_info()
    for key, value in info.items():
        print(f"  {key}: {value}")

    print("\nTesting with dummy frames...")
    thermal_dummy = np.random.randint(0, 255, (512, 640, 3), dtype=np.uint8)
    rgb_dummy = np.random.randint(0, 255, (1200, 1920, 3), dtype=np.uint8)

    thermal_disabled, rgb_disabled = compensator.apply_correction(thermal_dummy, rgb_dummy)
    assert np.array_equal(thermal_disabled, thermal_dummy), "Disabled mode should return original thermal"
    assert np.array_equal(rgb_disabled, rgb_dummy), "Disabled mode should return original rgb"
    print("✓ Disabled mode: Returns original thermal/rgb frames")

    compensator.enable(True)
    thermal_enabled, rgb_enabled = compensator.apply_correction(thermal_dummy, rgb_dummy)
    print(f"✓ Enabled mode (target=thermal): Processed frame shape {thermal_enabled.shape}")

    compensator.set_correction_target("rgb")
    thermal_rgb_target, rgb_corrected = compensator.apply_correction(thermal_dummy, rgb_dummy)
    assert np.array_equal(thermal_rgb_target, thermal_dummy), "rgb target should leave thermal untouched"
    print(f"✓ Enabled mode (target=rgb): Processed frame shape {rgb_corrected.shape}, thermal untouched")

    if compensator.get_depth_map() is not None:
        print(f"✓ Depth map generated: {compensator.get_depth_map().shape}")

    print("\n" + "="*70)
    print("Test complete!")
    print("="*70 + "\n")
