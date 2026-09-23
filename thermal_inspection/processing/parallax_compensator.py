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
from typing import List, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# The closest a depth reading can be treated as real (meters) - guards
# against near-zero/invalid depth producing an extreme or divide-by-zero
# disparity. Also the canonical source for fusion_3d_panel.MIN_VALID_DEPTH_M
# (that module imports it from here rather than redefining it) - the two
# copies previously only stayed in sync by coincidence.
MIN_VALID_DEPTH_M = 0.05

# Optional: Depth estimation model (DepthAnything V2, MiDaS, etc.)
# NOTE: We don't import torch/transformers here to avoid DLL loading errors
# They will be imported lazily when actually needed
DEPTH_ESTIMATION_AVAILABLE = False
TRANSFORMERS_AVAILABLE = False
# Latches True once the remap GPU path is proven unusable, so _resolve_remap_gpu
# probes at most once per process rather than once per frame. A failed `import
# torch` is never cached by Python (the partially-initialized module is dropped
# from sys.modules), so an un-latched retry re-runs the whole native-library
# load every call - measured in seconds on a machine with broken torch DLLs.
_REMAP_GPU_UNAVAILABLE = False

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
    # Thermal defaults match the actual owned hardware: Boson 320 (320x256)
    # with a 4.5mm lens - confirmed against Teledyne FLIR's own product
    # listing (320x256, 4.5mm, rated 50 deg HFOV) and pixel pitch (FLIR's
    # official Boson datasheet: 12um for both the 320 and 640 array
    # formats). The previous defaults (9.0mm focal length, 640x512, and a
    # 10.88mm sensor width derived from an incorrect 17um pixel pitch
    # assumption) matched neither this camera nor FLIR's real pixel pitch
    # for any Boson variant - thermal_half_fov/focal_px math in this module
    # (e.g. apply_correction, get_depth_intrinsics-adjacent calcs) reads
    # these fields directly, so a wrong default silently skewed real
    # parallax-correction/3D-fusion geometry, not just a label.
    #
    # RGB defaults are still unverified against the actual paired RGB
    # camera (Firefly and a RealSense D455 are both in use - see debt
    # ledger) and only feed the 'simplified' geometric-heuristic depth
    # path, not the 'realsense' depth method (which reads real intrinsics
    # from the device instead of this dataclass).
    baseline_mm: float = 50.0  # Default: 50mm baseline (5cm separation)
    thermal_focal_length_mm: float = 4.5  # Owned hardware: Boson 320, 4.5mm lens
    rgb_focal_length_mm: float = 6.0  # Firefly typical - unverified against actual RGB camera
    thermal_sensor_width_mm: float = 3.84  # Boson 320 (12um x 320px, FLIR datasheet)
    rgb_sensor_width_mm: float = 6.784  # IMX290 (2.9μm × 2336px) - unverified against actual RGB camera
    thermal_resolution: Tuple[int, int] = (320, 256)
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
            device: 'cpu', 'cuda', 'directml' (Intel/AMD - see
                utils/gpu_device.py), or 'auto' (re-run auto-detection
                next access)
        """
        device = device.lower()
        if device not in ('cpu', 'cuda', 'directml', 'auto'):
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

        # Live-reported: "parallax correction for realsense... visually
        # looks like two rgb images superimposed" - the other 3 depth
        # methods (simplified/depthanything/midas) never behave that way.
        # Root cause, confirmed by direct reproduction: real depth sensors
        # report 0 = "no valid reading" (occlusion, out-of-range, a
        # reflective surface), most visibly as a thin ring of invalid
        # pixels right at an object's own edge - the well-known "flying
        # pixels" artifact real depth sensors produce that synthetic/
        # model-estimated depth never does. compute_disparity/
        # compute_disparity_rgb treat any invalid pixel as "far away"
        # (5m, negligible disparity) rather than crash on the divide - a
        # safe fallback for the rare/scattered invalid pixel, but at a
        # real object's edge ring, EVERY pixel in that thin strip gets
        # this "far away" treatment while the real object one pixel
        # further in correctly gets a large disparity. The result: the
        # object's body shifts correctly, but its own edge ring stays
        # almost exactly where it started - visually splitting the
        # object into a correctly-shifted body plus a thin "ghost" strip
        # left behind at the old position, which reads as "two images
        # superimposed" wherever this happens (every real object edge in
        # the scene). Reproduced directly with a synthetic depth map
        # matching this exact real-sensor edge-hole shape before fixing.
        # Filling those holes from their real neighboring depth instead of
        # fabricating a "far away" value removes the ghost strip - a no-op
        # when there are no invalid pixels (the common case once the
        # RealSense SDK's own hole-filling filter is also enabled).
        #
        # This fill was originally cv2.inpaint(..., INPAINT_NS), which was
        # correct but far too expensive for a per-frame path: measured
        # 47.5ms of a 53ms depth stage at 640x512 with 6% invalid pixels,
        # and ~120ms/frame live on a real D455 (whose dropout count is
        # higher) - the dominant cost in the whole render loop and the
        # source of the 70-130ms spikes that showed up as loop jitter.
        # Navier-Stokes inpainting solves a PDE to synthesize plausible
        # *texture* across a hole; a depth map needs no such thing, only a
        # real neighbouring measurement.
        #
        # distanceTransformWithLabels gives exactly that in one pass: each
        # invalid pixel takes the value of its nearest VALID pixel
        # (DIST_LABEL_PIXEL numbers the zero-pixels - here the valid ones -
        # in raster order, so the label is an index into the valid set).
        # Unbiased between the near and far side of an edge ring, unlike a
        # dilate/erode fill which would systematically pull holes toward
        # the background or the foreground. Measured ~11ms vs inpaint's
        # ~47ms on the same frame, and verified against the inpainted
        # result: same hole coverage, max deviation 2.4mm.
        invalid = depth_m <= MIN_VALID_DEPTH_M
        if invalid.any() and not invalid.all():
            _, labels = cv2.distanceTransformWithLabels(
                invalid.astype(np.uint8), cv2.DIST_L2, 5,
                labelType=cv2.DIST_LABEL_PIXEL,
            )
            valid_values = depth_m[~invalid]
            depth_m = depth_m.copy()
            depth_m[invalid] = valid_values[labels[invalid] - 1]

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

        # Cap on the working width used for correction_target=="rgb"'s
        # remap (None disables the cap entirely - full native resolution).
        # Warping at full native RGB resolution is the whole point of
        # correction_target=="rgb" (preserving detail thermal can't
        # spare), but that cost scales with RGB's resolution, and GPU
        # remap wasn't a win here either (see _remap_thermal's docstring -
        # the same per-call launch-overhead problem that made it lose for
        # thermal's small frames is about interleaving with other CPU work
        # each frame, not raw pixel count, so it likely still applies at
        # RGB's larger size). Confirmed live: even a "modest" 720p RGB
        # source was more than this machine's CPU could comfortably remap
        # every frame - defaulting to "no cap" would hit the same wall
        # immediately for most real hardware, so this defaults to a real
        # cap (640px) rather than best-case. This is a real, explicit
        # quality-for-speed tradeoff (the whole corrected frame gets
        # resized down and back up, not just a cropped edge, unlike the
        # crop-vs-stretch fix) - a dial for hardware that can't afford
        # full-resolution warping every frame, not a hidden regression.
        self.rgb_target_max_width: Optional[int] = 640

        # Static crop-in zoom factor correcting a genuine FOV mismatch
        # between the thermal and RGB sensors (from their focal lengths and
        # sensor widths - a fixed optical property, not something that
        # varies frame to frame like parallax disparity does). Unlike the
        # per-frame shift/crop below, applying a resize here is correct:
        # it's compensating a real difference in what each camera actually
        # sees, not introducing an artifact. Computed via
        # compute_fov_crop_factor()/compute_auto_alignment(), 1.0 = no crop.
        self.fov_zoom_factor = 1.0

        # Fixed border-blank extent (top, bottom, left, right px), set once
        # by compute_auto_crop() (a GUI-triggered, on-demand action - see
        # its own docstring) rather than recomputed from the live
        # displacement map on every frame the way _remap_thermal's
        # fallback does. None means "no fixed crop yet" - _remap_thermal
        # falls back to its original per-frame computation in that case,
        # so behavior is unchanged until a user actually runs Auto-Crop.
        self.crop_rect: Optional[Tuple[int, int, int, int]] = None

        # Cache
        self.last_depth_map = None
        self.last_displacement_map = None
        self._last_flow_map_compute_time = 0.0
        # Depth-estimate+disparity-compute recompute throttle - see
        # _apply_correction_thermal_target/_apply_correction_rgb_target. A
        # physical camera pair's depth-based misalignment changes slowly
        # (tied to what's actually in front of the cameras, not per-frame
        # noise), so recomputing it at the full render rate was pure waste -
        # confirmed live: apply_correction() alone measured ~11ms/frame when
        # depth-based correction was genuinely engaged (simplified method),
        # stacking with 3D/2D Fusion's own per-frame cost to push several
        # mode/setting combinations into the low 20s fps. _remap_thermal
        # still runs on the CURRENT frame's live pixel data every single
        # call - only the depth-estimate+disparity step is throttled, so
        # this can't freeze the displayed video the way caching the whole
        # corrected frame would have.
        self.correction_recompute_interval_s = 1.0 / 15.0
        # _remap_thermal's coordinate grid only depends on (h, w), which is
        # constant frame-to-frame - cache it instead of rebuilding via
        # np.meshgrid() every single call. Profiled live: ~1.8ms/frame of
        # the ~15.5ms "simple geometric transform" total was this alone.
        self._coord_grid_shape = None
        self._coord_grid_xy = None
        # Everything _remap_thermal derives from a flow map alone (the
        # absolute remap coordinates and the live crop extents) is
        # identical for every frame that reuses that same flow map object.
        # Between throttled recomputes that's every frame, and for a
        # manual-shift-only setup it's all of them. Keyed on the flow map
        # object itself (held by reference, so its id can't be recycled).
        # Flow maps are never mutated in place: every recompute builds a
        # new array.
        self._remap_cache_flow = None
        self._remap_cache_maps = None    # (map_x, map_y) float32
        self._remap_cache_crops = None   # (top, bottom, left, right) live crop
        # Manual-shift-only flow map, reused while (h, w, dx, dy) is unchanged
        # instead of reallocating and filling an (H, W, 2) array every frame.
        self._manual_flow_key = None
        self._manual_flow_map = None

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
        # A flow map cached from before a disable/re-enable cycle could be
        # arbitrarily stale (the scene, camera position, or settings may
        # have changed while correction was off) - force a fresh compute
        # rather than reuse it. A fixed crop_rect (see compute_auto_crop)
        # is invalidated the same way, for the same reason.
        self.last_displacement_map = None
        self.crop_rect = None

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
        self.crop_rect = None

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

        fov_zoom_factor is handled differently - compute_fov_crop_factor()
        returns exactly reciprocal values for the two targets (tan(thermal)/
        tan(rgb) vs tan(rgb)/tan(thermal), the same optical ratio measured
        from the other camera's side), so unlike manual_shift this CAN be
        auto-corrected rather than just warned about: a zoom factor left
        unadjusted after a switch applied the wrong-direction crop/shrink
        to whichever frame is now being warped - confirmed live ("switching
        parallax correction mode to rgb the frame is cut in half", i.e. a
        stale shrink-and-pad factor meant for the old target's convention
        applied to the new one).
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
            if abs(self.fov_zoom_factor - 1.0) > 1e-3:
                old_factor = self.fov_zoom_factor
                self.fov_zoom_factor = 1.0 / self.fov_zoom_factor
                logger.info(
                    f"Parallax FOV crop-zoom factor auto-inverted for the new target: "
                    f"{old_factor:.4f} -> {self.fov_zoom_factor:.4f}"
                )
            # A cached flow map is in the OLD target's pixel space/resolution
            # entirely - the exact same class of bug as the earlier "frame
            # cut in half on target switch" issue if reused here. A fixed
            # crop_rect is in the same OLD pixel space too.
            self.last_displacement_map = None
            self.crop_rect = None
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
        self.last_displacement_map = None
        # A fixed crop_rect was sized for the OLD shift - re-run Auto-Crop
        # after this (compute_auto_crop's own docstring covers why).
        self.crop_rect = None

    def get_manual_shift(self) -> Tuple[int, int]:
        """Get the current manual alignment shift (dx, dy) in pixels."""
        return (self.manual_shift_x, self.manual_shift_y)

    def has_manual_shift(self) -> bool:
        """Whether a non-zero manual shift or FOV crop-zoom is set."""
        return (self.manual_shift_x != 0 or self.manual_shift_y != 0
                or abs(self.fov_zoom_factor - 1.0) > 1e-3)

    def set_rgb_target_max_width(self, width: Optional[int]):
        """
        Cap correction_target=="rgb"'s working resolution to at most this
        width (proportional height), or None/0 to remove the cap and warp
        at RGB's full native resolution. See this setting's __init__
        comment for the quality-vs-speed tradeoff.
        """
        self.rgb_target_max_width = int(width) if width else None
        logger.info(
            f"Parallax RGB-target max width set to "
            f"{'unlimited (full native resolution)' if self.rgb_target_max_width is None else f'{self.rgb_target_max_width}px'}"
        )
        # Changes the working resolution _apply_correction_rgb_target
        # computes the flow map at - the shape-mismatch check in
        # _flow_map_needs_recompute would catch this too, but being
        # explicit costs nothing and matches set_baseline/set_manual_shift.
        self.last_displacement_map = None
        self.crop_rect = None

    def get_rgb_target_max_width(self) -> Optional[int]:
        """Get the current correction_target=="rgb" working-resolution cap (None = unlimited)."""
        return self.rgb_target_max_width

    def set_fov_zoom_factor(self, factor: float):
        """
        Set the static crop/scale factor applied on top of any shift, e.g.
        to correct a real FOV mismatch between the two sensors. 1.0 = none;
        >1.0 crops in (narrows effective FOV, magnifying the center);
        <1.0 shrinks the frame's content and pads the border with black
        (widens effective angular scale to match a wider-FOV other camera -
        see _apply_fov_zoom for why this can't just "zoom out" for real).
        """
        self.fov_zoom_factor = max(0.1, float(factor))
        logger.info(f"Parallax FOV crop-zoom factor set to {self.fov_zoom_factor:.4f}")

    def get_fov_zoom_factor(self) -> float:
        """Get the current static FOV crop-zoom factor."""
        return self.fov_zoom_factor

    def compute_fov_crop_factor(self) -> float:
        """
        Compute the crop/scale factor needed to make correction_target's
        own horizontal FOV match the other camera's, from each camera's
        focal length and sensor width (self.geometry). This is a fixed
        optical property - it doesn't depend on distance to the subject,
        only on the two cameras' own optics.

        Returns >1.0 when the target camera's FOV is wider than the other
        camera's (crop in - see _apply_fov_zoom), <1.0 when it's narrower
        (shrink and pad - the target camera physically can't see as wide
        an angle as the other one, so there's no real pixel data to fill
        the difference with; padding at least matches angular scale so
        real features the target CAN see still line up), or 1.0 when they
        already match.
        """
        thermal_half_fov = math.atan2(self.geometry.thermal_sensor_width_mm / 2.0,
                                     self.geometry.thermal_focal_length_mm)
        rgb_half_fov = math.atan2(self.geometry.rgb_sensor_width_mm / 2.0,
                                 self.geometry.rgb_focal_length_mm)

        if self.correction_target == "rgb":
            target_half_fov, fixed_half_fov = rgb_half_fov, thermal_half_fov
        else:
            target_half_fov, fixed_half_fov = thermal_half_fov, rgb_half_fov

        # The ratio of the tangents of the half-FOV angles is exactly the
        # fraction of the target sensor's angular width the fixed camera's
        # FOV subtends - >1 (crop in) when target is wider, <1 (shrink +
        # pad) when target is narrower, computed the same way either
        # direction rather than only ever handling the "wider" case.
        return math.tan(target_half_fov) / math.tan(fixed_half_fov)

    def compute_geometric_shift_px(self, working_distance_m: float) -> int:
        """
        Compute the horizontal pixel disparity expected at a given subject
        distance, in whichever frame's pixel space correction_target
        points to - the same formula as compute_disparity()/
        compute_disparity_rgb(), applied to a single scalar distance
        instead of a per-pixel depth map.
        """
        working_distance_m = max(MIN_VALID_DEPTH_M, float(working_distance_m))
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

    # Candidate FOV crop-zoom factors tried when searching for the scale
    # that best registers the two cameras' real images (see
    # _estimate_shift_and_scale_from_images) - a coarse pass across a wide
    # range most real thermal/RGB lens pairings fall within, refined by a
    # finer pass centered on the coarse winner. Deliberately NOT derived
    # from compute_fov_crop_factor()/lens geometry at all: the whole point
    # is to find scale from what the cameras actually see, since entered
    # focal-length/sensor-width specs don't capture real manufacturing
    # tolerance, actual (vs. datasheet-nominal) mounting distance, or lens
    # distortion - see the "real world variances between cameras" note
    # that prompted this.
    _FOV_SCALE_COARSE_CANDIDATES = np.linspace(0.15, 3.0, 58)
    _FOV_SCALE_FINE_HALF_RANGE = 0.05
    _FOV_SCALE_FINE_STEPS = 11

    @staticmethod
    def _edge_magnitude(frame: np.ndarray) -> np.ndarray:
        """Sobel gradient-magnitude map - the shared structure a thermal
        and RGB frame of the same scene actually agree on (see
        _estimate_shift_and_scale_from_images)."""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if frame.ndim == 3 else frame
        gray = cv2.GaussianBlur(gray, (5, 5), 0)
        gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
        gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
        return cv2.magnitude(gx, gy)

    @staticmethod
    def _scale_edge_map(edges: np.ndarray, factor: float) -> np.ndarray:
        """Apply the same crop-in-and-resize (factor>=1) / shrink-and-pad
        (factor<1) transform _apply_fov_zoom performs on a real frame at
        render time, to an edge map instead - so a scale found here by
        phase-correlation confidence produces, at render time, exactly the
        alignment observed during the search that picked it."""
        h, w = edges.shape[:2]
        if abs(factor - 1.0) < 1e-3:
            return edges
        if factor >= 1.0:
            crop_w = max(1, min(w, int(round(w / factor))))
            crop_h = max(1, min(h, int(round(h / factor))))
            x0, y0 = (w - crop_w) // 2, (h - crop_h) // 2
            cropped = edges[y0:y0 + crop_h, x0:x0 + crop_w]
            return cv2.resize(cropped, (w, h), interpolation=cv2.INTER_LINEAR)
        new_w = max(1, min(w, int(round(w * factor))))
        new_h = max(1, min(h, int(round(h * factor))))
        shrunk = cv2.resize(edges, (new_w, new_h), interpolation=cv2.INTER_AREA)
        canvas = np.zeros_like(edges)
        x0, y0 = (w - new_w) // 2, (h - new_h) // 2
        canvas[y0:y0 + new_h, x0:x0 + new_w] = shrunk
        return canvas

    def _best_shift_for_scale(self, moving_edges: np.ndarray, fixed_edges: np.ndarray,
                              window: np.ndarray, scale: float) -> Tuple[float, float, float]:
        """One phaseCorrelate at a given candidate scale. Returns (dx, dy, confidence)."""
        scaled = self._scale_edge_map(moving_edges, scale)
        (dx, dy), confidence = cv2.phaseCorrelate(scaled, fixed_edges, window)
        return dx, dy, confidence

    def _estimate_shift_and_scale_from_images(self, thermal_frame: np.ndarray,
                                              rgb_frame: np.ndarray) -> Optional[Tuple[int, int, float]]:
        """
        Measure the actual current misalignment - horizontal shift,
        vertical shift, AND FOV crop-zoom scale - directly from what the
        two cameras see, via cv2.phaseCorrelate. Used by
        compute_auto_alignment() in preference to the geometry-only
        formula (compute_geometric_shift_px + compute_fov_crop_factor)
        whenever both frames are available: a lens datasheet's nominal
        focal length/sensor width doesn't capture real per-unit
        manufacturing tolerance or actual (vs. assumed) mounting geometry,
        so a scale found from what the cameras actually see is the more
        trustworthy number, not a secondary refinement of it.

        Registers each frame's own Sobel gradient-MAGNITUDE map, not raw
        grayscale intensity: a thermal and RGB image's raw brightness at
        "the same" real-world point are unrelated across modalities
        (thermal reflects temperature, RGB reflects lighting/color/
        material), so phase correlation on raw intensity has no shared
        signal to lock onto. A real object boundary, though, produces a
        local gradient in BOTH modalities - that shared edge structure is
        what phase correlation can actually find a meaningful peak on.

        Scale is found by a coarse-then-fine search: correction_target's
        own edge map is scaled by each candidate factor with the SAME
        crop/resize transform _apply_fov_zoom applies to a real frame,
        then phase-correlated against the other (fixed) camera's edge
        map. The candidate with the highest correlation confidence wins,
        and its own (dx, dy) is returned alongside it - a single
        self-consistent (shift, scale) pair from one measurement, not
        shift from one method and scale from another that may disagree.

        Returns None (caller falls back to the geometry-based estimate)
        when the winning candidate's confidence is too low to trust (e.g.
        a flat/textureless scene), or on any processing error - never
        raises, matching every other "refinement" path in this class.
        """
        result = self._search_shift_and_scale(thermal_frame, rgb_frame)
        if result is None:
            return None
        raw_dx, raw_dy, scale, conf = result

        if conf < self._MIN_PHASE_CORRELATION_CONFIDENCE:
            logger.info(
                f"Auto-alignment: image-based shift/scale estimate too low-confidence "
                f"({conf:.2f} < {self._MIN_PHASE_CORRELATION_CONFIDENCE}) to trust"
            )
            return None

        shift_x = int(round(raw_dx))
        shift_y = int(round(raw_dy))
        logger.info(
            f"Auto-alignment: image-based registration found shift "
            f"({shift_x}, {shift_y})px, FOV crop-zoom={scale:.4f}, confidence={conf:.2f}"
        )
        return shift_x, shift_y, float(scale)

    def _search_shift_and_scale(self, thermal_frame: np.ndarray,
                                rgb_frame: np.ndarray) -> Optional[Tuple[float, float, float, float]]:
        """
        Core single-sample coarse-then-fine phase-correlation search
        across candidate FOV scales - shared by both
        _estimate_shift_and_scale_from_images (single-sample, gated on
        THIS sample's own confidence) and
        _estimate_shift_and_scale_from_samples (multi-sample consensus,
        gated on cross-sample AGREEMENT instead - see that method's own
        docstring for why: a single real frame's confidence score was
        found NOT to reliably separate a correct registration from an
        incorrect one on real hardware).

        Returns (dx, dy, scale, confidence) - dx/dy already sign-
        corrected for correction_target's own convention (not yet
        rounded to int - callers that average across samples need the
        float precision) - or None on a degenerate boundary-artifact
        result (see below) or any processing error, never raising.
        """
        try:
            thermal_h, thermal_w = thermal_frame.shape[:2]
            rgb_for_reg = rgb_frame
            if rgb_frame.shape[:2] != (thermal_h, thermal_w):
                rgb_for_reg = cv2.resize(rgb_frame, (thermal_w, thermal_h),
                                        interpolation=cv2.INTER_LINEAR)

            thermal_edges = self._edge_magnitude(thermal_frame)
            rgb_edges = self._edge_magnitude(rgb_for_reg)

            # correction_target is whichever frame actually gets shifted +
            # zoomed at render time (_apply_manual_shift_only/
            # _apply_fov_zoom) - that's the "moving" edge map scale search
            # scales; the other camera is the fixed reference it's
            # registered against.
            if self.correction_target == "rgb":
                moving_edges, fixed_edges, sign = rgb_edges, thermal_edges, self._rgb_target_sign
            else:
                moving_edges, fixed_edges, sign = thermal_edges, rgb_edges, 1.0

            # A Hanning window is the standard pre-multiply for
            # cv2.phaseCorrelate - without it, the abrupt frame boundary
            # itself acts like a strong edge and dominates the frequency
            # spectrum, drowning out the real shift signal.
            window = cv2.createHanningWindow((thermal_w, thermal_h), cv2.CV_32F)

            coarse_lo = float(self._FOV_SCALE_COARSE_CANDIDATES[0])
            coarse_hi = float(self._FOV_SCALE_COARSE_CANDIDATES[-1])
            coarse_step = float(self._FOV_SCALE_COARSE_CANDIDATES[1] - self._FOV_SCALE_COARSE_CANDIDATES[0])

            best_scale, best_dx, best_dy, best_conf = 1.0, 0.0, 0.0, -1.0
            for scale in self._FOV_SCALE_COARSE_CANDIDATES:
                dx, dy, conf = self._best_shift_for_scale(moving_edges, fixed_edges, window, scale)
                if conf > best_conf:
                    best_scale, best_dx, best_dy, best_conf = scale, dx, dy, conf

            # A winner sitting right at the edge of the searched range is
            # NOT a genuine correlation peak - it's the classic phase-
            # correlate degenerate case: at an extreme shrink-and-pad
            # factor, most of the "moving" edge map is literal black
            # padding, which can spuriously report a sharp-looking
            # correlation peak against almost anything. A real optical
            # FOV-scale match shows as an interior peak, not a value that
            # keeps "improving" all the way to the search boundary -
            # confirmed live: on a real thermal/RGB frame pair, confidence
            # was noise-level (<0.09) at every physically-plausible
            # interior scale and only exceeded threshold at the boundary.
            if best_scale <= coarse_lo + coarse_step or best_scale >= coarse_hi - coarse_step:
                logger.info(
                    f"Auto-alignment: image-based scale search's best candidate "
                    f"({best_scale:.2f}) sits at the edge of the searched range "
                    f"[{coarse_lo:.2f}, {coarse_hi:.2f}] - treating as a degenerate "
                    f"boundary artifact, not a genuine match"
                )
                return None

            fine_candidates = np.linspace(
                max(0.1, best_scale - self._FOV_SCALE_FINE_HALF_RANGE),
                best_scale + self._FOV_SCALE_FINE_HALF_RANGE,
                self._FOV_SCALE_FINE_STEPS,
            )
            for scale in fine_candidates:
                dx, dy, conf = self._best_shift_for_scale(moving_edges, fixed_edges, window, scale)
                if conf > best_conf:
                    best_scale, best_dx, best_dy, best_conf = scale, dx, dy, conf

            # Sign verified directly against manual_shift_x's own
            # convention for correction_target=="thermal" (not assumed
            # from cv2.phaseCorrelate's docs alone): a synthetic
            # thermal/rgb pair with a KNOWN injected shift, round-tripped
            # through _apply_correction_thermal_target and checked by
            # actual edge-map agreement before/after, confirmed +dx (not
            # -dx, which was tried first and measured WORSE alignment,
            # not better) is what actually brings them into agreement
            # when passed as manual_shift_x here. See
            # TestImageBasedAutoAlign in tests/unit/test_parallax_fixes.py.
            # The "rgb" target case reuses self._rgb_target_sign, the same
            # flip already applied to the geometry-based estimate in
            # compute_geometric_shift_px for the same target switch - not
            # independently re-verified against a live image pair, since
            # no hardware with correction_target=="rgb" was available to
            # confirm against.
            return sign * best_dx, sign * best_dy, float(best_scale), float(best_conf)
        except Exception as e:
            logger.warning(f"Auto-alignment: image-based shift/scale estimation failed ({e})")
            return None

    # Multi-sample consensus: how close (in px) two samples' dx/dy must
    # land to count as "agreeing" - loose enough to tolerate normal
    # per-sample measurement noise, tight enough that a wildly different
    # (wrong) sample doesn't get counted as agreeing with a correct one.
    _SAMPLE_AGREEMENT_PX_TOLERANCE = 15.0
    # A consensus is only trusted if at least this fraction of samples
    # agree with the median - found necessary via direct testing against
    # real hardware: a single real frame's phaseCorrelate confidence
    # does NOT reliably separate a correct registration from an
    # incorrect one (both landed in the same ~0.08-0.10 range on real
    # sensor data), so cross-sample agreement is the trust signal here,
    # not any individual sample's own confidence score.
    _SAMPLE_AGREEMENT_MIN_FRACTION = 0.5
    _MIN_CONSENSUS_SAMPLES = 3

    def _estimate_shift_and_scale_from_samples(
        self, frame_pairs: List[Tuple[np.ndarray, np.ndarray]]
    ) -> Optional[Tuple[int, int, float]]:
        """
        Multi-sample consensus version of _estimate_shift_and_scale_from_images -
        takes several independently-captured thermal/RGB frame pairs
        (e.g. a handful of frames a fraction of a second apart) instead
        of trusting any single frame's phase-correlation result.

        Found necessary via direct testing against real hardware (not a
        theoretical concern): repeated real thermal/RGB frame pairs of
        the SAME real misalignment measured phaseCorrelate confidence in
        the same ~0.08-0.10 range for both a consistent, clearly-correct
        result (4 of 5 independent samples agreeing closely on a large
        real vertical mounting offset the geometry-only fallback cannot
        see at all) AND one wild outlier sample - confidence alone could
        not tell them apart. Averaging (median) across several samples
        and requiring a MAJORITY of them to agree with that median is
        robust to a minority of bad samples in a way a single frame's
        own confidence score is not.

        Returns None if fewer than _MIN_CONSENSUS_SAMPLES samples
        produced a usable (non-degenerate) result, or if fewer than
        _SAMPLE_AGREEMENT_MIN_FRACTION of them agree with the median -
        "no confident consensus" rather than trusting a possibly-wrong
        lone result.
        """
        raw_results = []
        for thermal_frame, rgb_frame in frame_pairs:
            result = self._search_shift_and_scale(thermal_frame, rgb_frame)
            if result is not None:
                raw_results.append(result)

        if len(raw_results) < self._MIN_CONSENSUS_SAMPLES:
            logger.info(
                f"Auto-alignment: only {len(raw_results)}/{len(frame_pairs)} image samples "
                f"produced a usable result - not enough for a consensus"
            )
            return None

        dxs = np.array([r[0] for r in raw_results])
        dys = np.array([r[1] for r in raw_results])
        scales = np.array([r[2] for r in raw_results])

        median_dx = float(np.median(dxs))
        median_dy = float(np.median(dys))
        median_scale = float(np.median(scales))

        # Agreement check: a sample "agrees" with the consensus if its
        # own shift is within a small tolerance of the median - the SAME
        # real misalignment measured twice should land close to the
        # same pixel offset; a wildly different sample is measuring
        # noise, not signal.
        agree = ((np.abs(dxs - median_dx) <= self._SAMPLE_AGREEMENT_PX_TOLERANCE) &
                (np.abs(dys - median_dy) <= self._SAMPLE_AGREEMENT_PX_TOLERANCE))
        agreement_fraction = float(np.mean(agree))

        if agreement_fraction < self._SAMPLE_AGREEMENT_MIN_FRACTION:
            logger.info(
                f"Auto-alignment: only {agreement_fraction:.0%} of {len(raw_results)} image "
                f"samples agreed with each other - no confident consensus, declining"
            )
            return None

        shift_x = int(round(median_dx))
        shift_y = int(round(median_dy))
        logger.info(
            f"Auto-alignment: image-based registration (multi-sample consensus, "
            f"{len(raw_results)} samples, {agreement_fraction:.0%} agreement) found "
            f"shift ({shift_x}, {shift_y})px, FOV crop-zoom={median_scale:.4f}"
        )
        return shift_x, shift_y, float(median_scale)

    # cv2.phaseCorrelate's own confidence/response value (0-1, roughly "how
    # sharp and unambiguous the correlation peak was") below which an
    # image-based shift estimate is rejected rather than trusted - a
    # low-confidence result on a flat/textureless scene (nothing for the
    # two edge maps to actually agree on) is worse than falling back to
    # the geometry-only estimate, not better.
    _MIN_PHASE_CORRELATION_CONFIDENCE = 0.15

    def compute_auto_alignment(self, working_distance_m: float = 2.0,
                              rgb_frame: Optional[np.ndarray] = None,
                              thermal_frame: Optional[np.ndarray] = None,
                              thermal_frame_samples: Optional[List[np.ndarray]] = None,
                              rgb_frame_samples: Optional[List[np.ndarray]] = None) -> Tuple[int, float]:
        """
        One-time alignment calculation, meant to be triggered on demand
        (e.g. a GUI button), not run every frame. The result is stored as
        a static manual shift + FOV crop-zoom factor, which then costs
        nothing further per frame (see _apply_manual_shift_only) - unlike
        leaving depth-based correction continuously enabled.

        Shift AND FOV crop-zoom scale both come from one of two sources,
        in priority order:
          1. Image-based registration (thermal_frame AND rgb_frame both
             given): measures the actual current shift and scale directly
             from what the two cameras really see (via
             _estimate_shift_and_scale_from_images), rather than trusting
             entered lens focal-length/sensor-width specs and an assumed
             baseline/working-distance formula. This is the preferred,
             default path - real cameras vary from their datasheet
             nominal values (manufacturing tolerance, actual mounting
             geometry, lens distortion), so a scale measured from the
             live images is more trustworthy than one computed from
             specs, not merely a refinement of it. Confirmed by direct
             testing to recover a known injected shift (see tests), not
             assumed correct from cv2.phaseCorrelate's docs alone. Falls
             through to geometry-based below if the match confidence is
             too low to trust (e.g. a flat scene with no shared edge
             structure to register against).
          2. Geometry-based (rgb_frame only, or image registration didn't
             produce a confident result): the original formula from
             baseline_mm + working_distance_m for shift, and
             compute_fov_crop_factor() (entered lens specs) for scale -
             a fallback for when no live frame pair is available to
             measure from at all, not the normal path.

        Args:
            working_distance_m: Assumed subject distance in meters, used
                for the geometry-based shift unless refined by depth
                estimation below, or superseded entirely by image-based
                registration.
            rgb_frame: If given (with thermal_frame also given), used for
                image-based registration. If given alone, runs the
                currently-selected depth estimation method once to
                measure/estimate the actual scene distance for the
                geometry-based formula instead. Ignored (pure geometric
                calculation) if None.
            thermal_frame: If given together with rgb_frame, enables
                image-based registration (source 1 above).
            thermal_frame_samples/rgb_frame_samples: If both given (equal
                length, >= _MIN_CONSENSUS_SAMPLES), used INSTEAD of the
                single thermal_frame/rgb_frame pair for image-based
                registration - several independently-captured frame
                pairs combined via _estimate_shift_and_scale_from_samples's
                cross-sample agreement check, more robust than trusting
                any one frame's own phaseCorrelate confidence (found
                necessary via direct testing against real hardware - see
                that method's docstring).

        Returns:
            (dx_px, fov_zoom_factor) - the values that were applied.
        """
        resolved_distance_m = working_distance_m

        has_multi_samples = (thermal_frame_samples and rgb_frame_samples
                            and len(thermal_frame_samples) == len(rgb_frame_samples)
                            and len(thermal_frame_samples) >= self._MIN_CONSENSUS_SAMPLES)
        has_single_pair = thermal_frame is not None and rgb_frame is not None

        if has_multi_samples or has_single_pair:
            if has_multi_samples:
                image_result = self._estimate_shift_and_scale_from_samples(
                    list(zip(thermal_frame_samples, rgb_frame_samples))
                )
            else:
                image_result = self._estimate_shift_and_scale_from_images(thermal_frame, rgb_frame)

            if image_result is not None:
                image_dx, image_dy, zoom = image_result
                self.manual_shift_x = image_dx
                self.manual_shift_y = image_dy
                self.fov_zoom_factor = zoom
                self.last_displacement_map = None
                self.crop_rect = None
                logger.info(
                    f"Auto-alignment computed from image content: shift="
                    f"({image_dx}, {image_dy})px, FOV crop-zoom={zoom:.4f}"
                )
                return image_dx, zoom
            logger.info("Auto-alignment: image-based registration inconclusive, "
                       "falling back to geometry-based calculation")

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
        # Sets manual_shift_x/fov_zoom_factor directly rather than through
        # set_manual_shift()/set_fov_zoom_factor(), so their own cache
        # invalidation doesn't run automatically here - a stale crop_rect
        # sized for the PRE-auto-align shift would blank the wrong border
        # region once this new shift takes effect.
        self.last_displacement_map = None
        self.crop_rect = None

        logger.info(
            f"Auto-alignment computed: shift=({dx}, {self.manual_shift_y})px "
            f"at {resolved_distance_m:.2f}m, FOV crop-zoom={zoom:.4f}"
        )
        return dx, zoom

    def compute_auto_crop(self) -> Optional[Tuple[int, int, int, int]]:
        """
        One-time computation of a FIXED border-blank extent from whatever
        correction is currently in effect, meant to be triggered on demand
        (e.g. a GUI "Auto-Crop" button) - not run every frame. Once set,
        _remap_thermal uses the stored rect directly instead of re-deriving
        it from the live displacement map on every call (see crop_rect's
        own __init__ comment and _remap_thermal's use of it) - a genuine
        simplification of that per-frame cost, not an addition to it.

        Reads self.last_displacement_map - whatever apply_correction() most
        recently computed, either the constant manual-shift-only map or a
        real depth-based per-pixel one - rather than requiring a fresh
        frame to be passed in, since apply_correction() already keeps this
        cache current for exactly this kind of on-demand query.

        For a manual-shift-only setup (no depth-based correction), the
        flow map is a uniform constant across the whole frame, so the
        computed crop is fully deterministic and exact - not an
        approximation of a moving target. With depth-based correction
        active, this is necessarily a snapshot of the CURRENT scene's
        depth distribution; if the scene's depth range changes
        substantially afterward (a much closer or farther subject moves
        into frame), the fixed crop may under- or over-cover the border
        until Auto-Crop is run again - the same one-time/on-demand
        tradeoff compute_auto_alignment() already accepts for shift/zoom.

        Returns:
            The computed (top, bottom, left, right) rect, or None if no
            correction has run yet (last_displacement_map is still empty)
            - nothing to crop in that case.
        """
        flow_map = self.last_displacement_map
        if flow_map is None:
            logger.warning("Auto-Crop: no correction has run yet, nothing to crop")
            return None

        h, w = flow_map.shape[:2]
        shift_x = flow_map[:, :, 0]
        shift_y = flow_map[:, :, 1]

        # Identical bound to _remap_thermal's own live computation - see
        # its comment for why a real depth source can legitimately demand
        # a crop this large, and why it's still capped rather than left
        # unbounded.
        max_crop_w = int(w * self._MAX_CROP_FRACTION)
        max_crop_h = int(h * self._MAX_CROP_FRACTION)
        left_crop = max(0, min(max_crop_w, int(np.ceil(shift_x.max()))))
        right_crop = max(0, min(max_crop_w, int(np.ceil(-shift_x.min()))))
        top_crop = max(0, min(max_crop_h, int(np.ceil(shift_y.max()))))
        bottom_crop = max(0, min(max_crop_h, int(np.ceil(-shift_y.min()))))

        self.crop_rect = (top_crop, bottom_crop, left_crop, right_crop)
        logger.info(f"Auto-Crop computed: (top={top_crop}, bottom={bottom_crop}, "
                   f"left={left_crop}, right={right_crop})px")
        return self.crop_rect

    def set_crop_rect(self, top: int, bottom: int, left: int, right: int):
        """Set a fixed border-blank extent directly (e.g. restoring a persisted value)."""
        self.crop_rect = (int(top), int(bottom), int(left), int(right))

    def get_crop_rect(self) -> Optional[Tuple[int, int, int, int]]:
        """Current fixed crop rect, or None if Auto-Crop has never run (or was reset)."""
        return self.crop_rect

    def clear_crop_rect(self):
        """Reset to _remap_thermal's original per-frame live computation."""
        self.crop_rect = None
        logger.info("Auto-Crop reset - border blanking will be recomputed live each frame again")

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
        # Real depth sources (e.g. RealSense) commonly use 0 = "no valid
        # reading" (occlusion, reflective surface, out of range) -
        # dividing by that produces inf, which crashes deep inside the
        # crop-blanking logic (int(ceil(inf)) raises OverflowError),
        # caught by apply_correction()'s broad exception handler and
        # discarding the ENTIRE correction for that frame - manual shift
        # and FOV crop-zoom included, not just the depth-based component.
        # "simplified"'s synthetic depth is always > 0 so it never hits
        # this; any real (variable) depth source can. Treat invalid/
        # non-positive depth as "far away" (~5m, the far end of the
        # realistic working range) - negligible disparity there rather
        # than a runaway/undefined shift.
        safe_depth = np.where(depth_map > MIN_VALID_DEPTH_M, depth_map, 5.0)

        thermal_focal_px = (self.geometry.thermal_focal_length_mm /
                           self.geometry.thermal_sensor_width_mm *
                           self.geometry.thermal_resolution[0])

        disparity_px = (self.geometry.baseline_mm * thermal_focal_px) / (safe_depth * 1000.0)

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
        # See compute_disparity()'s identical guard - real depth sources'
        # 0="no valid reading" pixels would otherwise divide to inf and
        # crash the crop-blanking logic, discarding the entire correction.
        safe_depth = np.where(depth_map > MIN_VALID_DEPTH_M, depth_map, 5.0)

        rgb_focal_px = (self.geometry.rgb_focal_length_mm /
                       self.geometry.rgb_sensor_width_mm *
                       rgb_width_px)

        disparity_px = (self.geometry.baseline_mm * rgb_focal_px) / (safe_depth * 1000.0)

        return disparity_px.astype(np.float32)

    def _flow_map_needs_recompute(self, expected_shape: Tuple[int, int]) -> bool:
        """
        Whether the cached self.last_displacement_map is stale and the
        depth-estimate+disparity-compute step must run again this call -
        either there's no cache yet, its shape doesn't match what this
        call needs (a correction-target switch changes the working
        resolution entirely - this is the same shape-mismatch class of
        bug as the earlier "frame cut in half on target switch" issue, so
        this check is a deliberate safety net, not just an optimization),
        or the recompute throttle interval has elapsed.
        """
        return (
            self.last_displacement_map is None
            or self.last_displacement_map.shape[:2] != expected_shape
            or (time.perf_counter() - self._last_flow_map_compute_time) >= self.correction_recompute_interval_s
        )

    def invalidate_correction_cache(self):
        """
        Force the next apply_correction() call to recompute depth+disparity
        immediately rather than reuse a cached flow map - call this after
        any change that could make the cached flow map wrong (swapping the
        depth estimator, e.g. app.py's set_parallax_depth_method(), which
        replaces self.depth_estimator directly rather than through a method
        on this class).
        """
        self.last_displacement_map = None
        self.crop_rect = None

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
            _t_corr_start = time.perf_counter()

            # show_depth_map always recomputes fresh - someone actively
            # inspecting depth-estimation quality wants current
            # information, not a throttled/stale sample.
            if self.show_depth_map or self._flow_map_needs_recompute((thermal_h, thermal_w)):
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
                depth_resized = cv2.resize(depth_map, (thermal_w, thermal_h),
                                          interpolation=cv2.INTER_LINEAR)

                disparity_map = self.compute_disparity(depth_resized)

                flow_map = np.zeros((thermal_h, thermal_w, 2), dtype=np.float32)
                flow_map[:, :, 0] = disparity_map + self.manual_shift_x
                flow_map[:, :, 1] = self.manual_shift_y

                self.last_displacement_map = flow_map
                self._last_flow_map_compute_time = time.perf_counter()

                # Return depth-map colourised overlay when requested (debug/QA mode)
                if self.show_depth_map:
                    depth_colourised = self._colourise_depth_debug(depth_resized, thermal_w, thermal_h)
                    self.last_correction_time_ms = (time.perf_counter() - _t_corr_start) * 1000.0
                    return depth_colourised, rgb_frame
            else:
                flow_map = self.last_displacement_map

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

        Runs the remap at RGB's own native resolution by default (not
        downscaled to thermal's), so the abundant RGB pixels genuinely
        absorb the crop/warp loss instead of it costing anything at
        thermal's (much smaller) scale - the tradeoff is that this remap
        step itself costs more CPU per frame than warping the smaller
        thermal frame did, proportional to RGB's resolution. See
        rgb_target_max_width for the dial that caps this when full native
        resolution is more than the hardware can sustain.
        """
        if not self.enabled:
            return thermal_frame, self._apply_manual_shift_only_rgb(rgb_frame)

        if rgb_frame is None:
            return thermal_frame, rgb_frame

        try:
            thermal_h, thermal_w = thermal_frame.shape[:2]
            rgb_h, rgb_w = rgb_frame.shape[:2]
            work_w, work_h = self._resolve_rgb_work_size(rgb_w, rgb_h)
            capped = (work_w, work_h) != (rgb_w, rgb_h)
            _t_corr_start = time.perf_counter()

            # show_depth_map always recomputes fresh - see
            # _apply_correction_thermal_target's identical reasoning.
            if self.show_depth_map or self._flow_map_needs_recompute((work_h, work_w)):
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

                # Resize the depth map up to the WORKING resolution (RGB's own
                # native size, or rgb_target_max_width's cap) - the
                # disparity/flow map, and the remap it drives, need to be at
                # the same resolution as the frame actually being warped.
                depth_resized = cv2.resize(depth_map, (work_w, work_h),
                                          interpolation=cv2.INTER_LINEAR)

                # compute_disparity_rgb still uses rgb_w (the REAL native
                # width) for the focal-length-in-pixels conversion - that's a
                # property of the actual sensor, not whatever resolution we're
                # processing at - then scale the result down to the working
                # resolution's own pixel grid below, same reasoning as
                # _apply_manual_shift_only_rgb's scale factor.
                disparity_map = self.compute_disparity_rgb(depth_resized, rgb_w)
                scale = work_w / rgb_w

                # Opposite sign convention from the thermal-target path - see
                # set_correction_target()'s docstring and _rgb_target_sign's
                # definition in __init__: aligning RGB to thermal's (now
                # unmoved) raw position is the inverse of aligning thermal to
                # RGB's raw position, derived from the same physical baseline
                # geometry. Manual shift is in RGB's own native pixel space
                # here, not thermal's - a value tuned for
                # correction_target=="thermal" is not meaningful after
                # switching (see set_correction_target).
                sign = self._rgb_target_sign
                # disparity_map and manual_shift_x are both in native-pixel
                # units (see above / rgb_target_max_width) - scale their SUM
                # down to the working resolution's own pixel grid together.
                flow_map = np.zeros((work_h, work_w, 2), dtype=np.float32)
                flow_map[:, :, 0] = sign * scale * (disparity_map + self.manual_shift_x)
                flow_map[:, :, 1] = sign * scale * self.manual_shift_y

                self.last_displacement_map = flow_map
                self._last_flow_map_compute_time = time.perf_counter()

                if self.show_depth_map:
                    depth_colourised = self._colourise_depth_debug(depth_resized, work_w, work_h)
                    if capped:
                        depth_colourised = cv2.resize(depth_colourised, (rgb_w, rgb_h))
                    self.last_correction_time_ms = (time.perf_counter() - _t_corr_start) * 1000.0
                    return thermal_frame, depth_colourised
            else:
                flow_map = self.last_displacement_map

            work_frame = (cv2.resize(rgb_frame, (work_w, work_h), interpolation=cv2.INTER_LINEAR)
                        if capped else rgb_frame)
            corrected_rgb = self._remap_thermal(work_frame, flow_map)
            if capped:
                corrected_rgb = cv2.resize(corrected_rgb, (rgb_w, rgb_h), interpolation=cv2.INTER_LINEAR)
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
        flow_map = self._get_manual_flow_map(h, w, self.manual_shift_x, self.manual_shift_y)
        self.last_displacement_map = flow_map

        corrected = self._remap_thermal(thermal_frame, flow_map)
        if self.show_displacement:
            corrected = self._draw_displacement_vectors(corrected, flow_map)
        return corrected

    def _get_manual_flow_map(self, h: int, w: int, shift_x: float, shift_y: float) -> np.ndarray:
        """Constant (H, W, 2) flow map for a manual-shift-only correction,
        cached while its shape and shift values are unchanged (see
        _manual_flow_key's __init__ comment)."""
        key = (h, w, shift_x, shift_y)
        if self._manual_flow_key != key:
            flow_map = np.zeros((h, w, 2), dtype=np.float32)
            flow_map[:, :, 0] = shift_x
            flow_map[:, :, 1] = shift_y
            self._manual_flow_map = flow_map
            self._manual_flow_key = key
        return self._manual_flow_map

    def _resolve_rgb_work_size(self, rgb_w: int, rgb_h: int) -> Tuple[int, int]:
        """
        Resolve the working resolution correction_target=="rgb" actually
        processes at, applying rgb_target_max_width if it's set and
        smaller than the frame's real size. Returns (rgb_w, rgb_h)
        unchanged when no cap applies.
        """
        cap = self.rgb_target_max_width
        if cap and rgb_w > cap:
            work_w = cap
            work_h = max(1, int(round(rgb_h * cap / rgb_w)))
            return work_w, work_h
        return rgb_w, rgb_h

    def _apply_manual_shift_only_rgb(self, rgb_frame: Optional[np.ndarray]) -> Optional[np.ndarray]:
        """RGB-target equivalent of _apply_manual_shift_only - see _apply_correction_rgb_target."""
        if rgb_frame is None or not self.has_manual_shift():
            return rgb_frame

        h, w = rgb_frame.shape[:2]
        work_w, work_h = self._resolve_rgb_work_size(w, h)
        capped = (work_w, work_h) != (w, h)
        work_frame = (cv2.resize(rgb_frame, (work_w, work_h), interpolation=cv2.INTER_LINEAR)
                    if capped else rgb_frame)

        # manual_shift_x/y are in RGB's real native pixel space - scale
        # down to the working resolution's own pixel grid so the shift
        # represents the same physical/angular offset there (see
        # rgb_target_max_width's __init__ comment).
        scale = work_w / w
        sign = self._rgb_target_sign
        flow_map = self._get_manual_flow_map(
            work_h, work_w, sign * self.manual_shift_x * scale, sign * self.manual_shift_y * scale
        )
        self.last_displacement_map = flow_map

        corrected = self._remap_thermal(work_frame, flow_map)
        if capped:
            corrected = cv2.resize(corrected, (w, h), interpolation=cv2.INTER_LINEAR)
        if self.show_displacement:
            corrected = self._draw_displacement_vectors(corrected, flow_map)
        return corrected

    # Grid spacing (pixels) for the displacement-vector overlay - dense
    # enough to see spatial variation, sparse enough not to turn the whole
    # frame into a solid mass of arrows.
    _DISPLACEMENT_GRID_STEP = 32

    # Maximum fraction of width/height _remap_thermal will ever blank away
    # per side - see its use for why this exists (an extreme real-depth
    # disparity could otherwise blank the entire frame to black).
    _MAX_CROP_FRACTION = 0.35

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
        Lazily resolve whether a torch GPU (CUDA, or DirectML on
        Intel/AMD - see utils/gpu_device.py) is usable for the remap
        step. Never raises - returns False (CPU fallback) on any failure.
        """
        global _REMAP_GPU_UNAVAILABLE
        if self._remap_gpu_ready:
            return True
        # DEPTH_ESTIMATION_AVAILABLE reflects a real module-level `import
        # torch`, so unlike fusion_processor/fusion_3d_panel's find_spec-based
        # guards this one already latches False when torch can't load at all.
        # The negative latch below still matters for the other failure mode:
        # torch imports fine but CUDA is absent or device setup raises, which
        # would otherwise re-probe on every frame the remap runs.
        if not DEPTH_ESTIMATION_AVAILABLE or _REMAP_GPU_UNAVAILABLE:
            return False
        try:
            import torch
            from thermal_inspection.utils.gpu_device import resolve_torch_gpu_device
            device, device_name = resolve_torch_gpu_device("auto", "Parallax remap")
            if device is None:
                _REMAP_GPU_UNAVAILABLE = True
                return False
            self._remap_gpu_device = device
            self._remap_gpu_ready = True
            logger.info(f"Parallax remap: GPU acceleration active ({device_name})")
            return True
        except Exception as e:
            _REMAP_GPU_UNAVAILABLE = True
            logger.warning(
                f"Parallax remap: failed to initialize GPU path, falling back "
                f"to CPU (will not retry this process): {e}"
            )
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

        img_t = torch.from_numpy(thermal_frame).to(device).float().permute(2, 0, 1).unsqueeze(0)
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

        # Absolute coordinates depend only on the flow map, so they're
        # reused for as long as the same flow map object is (see
        # _remap_cache_flow's __init__ comment). Saves two full-frame
        # float32 subtractions per call: ~0.8ms at 640x512, ~2.5ms at 1280x800.
        if self._remap_cache_flow is not flow_map or self._remap_cache_maps is None:
            self._remap_cache_maps = (x_coords - flow_map[:, :, 0], y_coords - flow_map[:, :, 1])
            self._remap_cache_flow = flow_map
            self._remap_cache_crops = None
        map_x, map_y = self._remap_cache_maps

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
        # A fixed crop from a prior compute_auto_crop() call (see its own
        # docstring) skips the live reduction below entirely - 4 cheap
        # slice-assignments from plain ints instead of 4 numpy min/max
        # reductions over the full flow_map, every frame this correction
        # path runs. This is a genuine simplification of the existing
        # per-frame cost, not a new one: the crop rect was already being
        # recomputed from scratch every call before Auto-Crop existed.
        if self.crop_rect is not None:
            # Re-clamped against the CURRENT frame size, not just trusted
            # as-is - a stored crop_rect could in principle predate a
            # camera resolution change (a different camera reconnected,
            # or a mode switch), and this same _MAX_CROP_FRACTION bound
            # already protects the live path below from ever blanking an
            # entire frame.
            max_crop_w = int(w * self._MAX_CROP_FRACTION)
            max_crop_h = int(h * self._MAX_CROP_FRACTION)
            top_crop = max(0, min(max_crop_h, self.crop_rect[0]))
            bottom_crop = max(0, min(max_crop_h, self.crop_rect[1]))
            left_crop = max(0, min(max_crop_w, self.crop_rect[2]))
            right_crop = max(0, min(max_crop_w, self.crop_rect[3]))
        else:
            shift_x = flow_map[:, :, 0]
            shift_y = flow_map[:, :, 1]

            # map_x = x - shift_x goes out of [0, w) on the LEFT wherever
            # shift_x is large positive (small x - large shift < 0), and out on
            # the RIGHT wherever shift_x is large negative (x near w-1 + |shift|
            # exceeds w-1) - blank only the actual max magnitude present on each
            # side, not a blanket worst case, so a small shift doesn't blank
            # more field of view than it has to.
            #
            # Capped at _MAX_CROP_FRACTION per side (not just min(w, ...)/
            # min(h, ...)) - a real depth source (e.g. RealSense) can
            # legitimately report a very close object, producing a disparity
            # far larger than the frame is wide. Capping only at the frame's
            # own dimension still let left_crop (or any side) reach the full
            # width/height, and corrected[:, :w] = 0 blanks the ENTIRE frame
            # to black - confirmed live: "turning on Intel RealSense parallax
            # compensation turns the RGB feed black" (synthetic depth methods
            # never report distances close enough to trigger this). Some
            # residual smeared border can remain visible in this extreme case
            # instead - a real but far lesser problem than an all-black frame.
            #
            # The four reductions depend only on flow_map, so they're
            # cached alongside the remap coordinates (_remap_thermal_cpu
            # just ran and set _remap_cache_flow to this same flow_map).
            if self._remap_cache_flow is flow_map and self._remap_cache_crops is not None:
                top_crop, bottom_crop, left_crop, right_crop = self._remap_cache_crops
            else:
                max_crop_w = int(w * self._MAX_CROP_FRACTION)
                max_crop_h = int(h * self._MAX_CROP_FRACTION)
                left_crop = max(0, min(max_crop_w, int(np.ceil(shift_x.max()))))
                right_crop = max(0, min(max_crop_w, int(np.ceil(-shift_x.min()))))
                top_crop = max(0, min(max_crop_h, int(np.ceil(shift_y.max()))))
                bottom_crop = max(0, min(max_crop_h, int(np.ceil(-shift_y.min()))))
                if self._remap_cache_flow is flow_map:
                    self._remap_cache_crops = (top_crop, bottom_crop, left_crop, right_crop)

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
        Crop/scale by self.fov_zoom_factor to correct a real FOV mismatch
        between the thermal and RGB sensors (see compute_fov_crop_factor).
        Unlike the per-frame shift/crop above, a resize here is correct
        rather than a "stretch" artifact - it's a static, one-time
        correction for a genuine optical difference between the two
        cameras, not per-frame jitter, and is only ever applied when the
        user has explicitly computed/set a zoom factor.

        factor > 1.0: crop in - the target camera's FOV is wider than the
        other camera's, so the extra angular coverage really is there to
        crop away; magnifying the remaining center crop back to full size
        narrows the effective FOV to match.

        factor < 1.0: shrink and pad - the target camera's FOV is
        NARROWER than the other camera's. There's no real pixel data to
        widen it with (the sensor genuinely didn't capture that extra
        angle), so this can't crop-and-zoom like the >1.0 case; instead it
        shrinks the frame's actual content and centers it on a black
        canvas of the original size. This matches angular scale (pixels
        per degree) between the two frames - real features the target
        camera CAN see still land in the correct relative position - at
        the cost of the target's own frame only filling the center
        portion of itself, bordered by black.
        """
        h, w = frame.shape[:2]
        factor = self.fov_zoom_factor

        if factor >= 1.0:
            crop_w = max(1, min(w, int(round(w / factor))))
            crop_h = max(1, min(h, int(round(h / factor))))
            x0 = (w - crop_w) // 2
            y0 = (h - crop_h) // 2
            cropped = frame[y0:y0 + crop_h, x0:x0 + crop_w]
            return cv2.resize(cropped, (w, h), interpolation=cv2.INTER_LINEAR)

        new_w = max(1, min(w, int(round(w * factor))))
        new_h = max(1, min(h, int(round(h * factor))))
        shrunk = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_AREA)
        canvas = np.zeros_like(frame)
        x0 = (w - new_w) // 2
        y0 = (h - new_h) // 2
        canvas[y0:y0 + new_h, x0:x0 + new_w] = shrunk
        return canvas

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
