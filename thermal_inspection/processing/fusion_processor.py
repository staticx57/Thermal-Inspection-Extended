"""
Thermal-RGB Fusion Processor
Combines thermal and RGB imagery for enhanced object detection
Optimized for Jetson Orin with GPU acceleration
"""
import cv2
import numpy as np
import logging
from typing import Tuple, Optional
import json
import os
import importlib.util

logger = logging.getLogger(__name__)

# Optional: torch, used only for the GPU-accelerated laplacian_pyramid path
# (see _laplacian_pyramid_gpu). Not imported eagerly - probing for real
# costs seconds and every other fusion mode runs fine without it. Same
# deferral pattern as parallax_compensator.py's DEPTH_ESTIMATION_AVAILABLE.
_TORCH_SPEC_AVAILABLE = importlib.util.find_spec("torch") is not None
# Latches True once torch/CUDA has been proven unusable in this process, so
# every GPU resolver below probes at most once instead of once per frame.
#
# _TORCH_SPEC_AVAILABLE only proves torch is INSTALLED (find_spec inspects the
# filesystem); it does not prove `import torch` succeeds. When the package is
# present but its native libraries fail to load - exactly this machine's
# broken c10.dll - the import raises, and Python does NOT cache a failed
# import (the partially-initialized module is removed from sys.modules), so
# every retry re-runs the full DLL load from scratch. Without this latch,
# _resolve_feature_weighted_gpu/_resolve_laplacian_gpu re-attempted that
# failing load on EVERY frame: measured 3.3s and 3.4s per frame respectively
# with PyQt6 resident (i.e. the real app), against ~3ms and ~6ms for those
# modes' actual CPU work - a ~1000x per-frame overhead with nothing to do
# with fusion itself. Process-wide (not per-instance) because whether torch
# imports is a property of the process, not of a FusionProcessor. CUDA
# availability cannot change within a process, so caching a negative is safe.
_TORCH_GPU_UNAVAILABLE = False

# feature_weighted's blend weight used to be a raw ratio
# thermal_strength/(thermal_strength+rgb_strength) - well-defined
# mathematically, but numerically ill-conditioned (same class of problem
# as catastrophic cancellation) whenever the two are close to equal: a
# tiny perturbation in either one flips the ratio between near-0 and
# near-1. That's invisible with a single implementation (CPU-only, always
# computed the same way), but comparing it against a GPU implementation
# doing the identical math in a different instruction/reduction order -
# neither one "wrong", see _feature_weighted_gpu's docstring - exposed it
# as a real problem: ~5% of pixels diverged visibly (mean 3.7/255, some
# 100+/255) on a realistic test scene. A sigmoid of the strength
# *difference* has a bounded derivative everywhere (max slope at
# difference=0 is 0.25*K), so the same tiny CPU/GPU perturbation can only
# ever move the weight a little, not flip it - verified this reduces
# worst-case CPU/GPU divergence on that same scene to 0 pixels beyond a
# 20/255 threshold (mean <1/255) at K=2.0, tried against 4/8/16 which
# were each progressively less stable. This changes the CPU-only path's
# blend character too (a softer transition than the old ratio, not just
# a GPU-matching patch) - by design, since the instability isn't GPU-
# specific, just GPU-visible.
_FEATURE_WEIGHTED_SIGMOID_K = 2.0

# thermal_contours' minimum contour area (px^2) to bother drawing - below
# this a contour is an invisible speck at the mode's fixed 2px line width
# anyway. See _thermal_contours' own comment for why this exists.
_THERMAL_CONTOURS_MIN_AREA = 20

# _detect_edges_multiscale's morphology kernels - fixed size,
# never depend on frame content or any instance setting, so recreating
# them with cv2.getStructuringElement() on every single call (as this
# function used to) was pure per-frame waste. Built once at import time.
_EDGE_KERNEL_MEDIUM = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
_EDGE_KERNEL_LARGE = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
_EDGE_KERNEL_CONNECT = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2, 2))

# relief_fusion's emboss kernel, one per apparent light-source corner - a
# well-established technique (an emboss/"directional difference" filter's
# apparent light direction is set entirely by which corner its negative
# weights sit in - see e.g. Wikipedia's Image embossing article). The
# original kernel (top_left, the only one this mode ever had) is a fixed
# point here; the other 3 are exact 90-degree rotations of it via
# np.rot90, not independently hand-tuned, so top_left's behavior is
# unchanged bit-for-bit and the other 3 are guaranteed consistent with it
# rather than ad hoc.
_RELIEF_KERNEL_TOP_LEFT = np.array([
    [-2, -1, 0],
    [-1, 1, 1],
    [0, 1, 2]
], dtype=np.float32)
_RELIEF_LIGHT_DIRECTIONS = {
    'top_left': _RELIEF_KERNEL_TOP_LEFT,
    'top_right': np.rot90(_RELIEF_KERNEL_TOP_LEFT, k=-1).copy(),
    'bottom_right': np.rot90(_RELIEF_KERNEL_TOP_LEFT, k=-2).copy(),
    'bottom_left': np.rot90(_RELIEF_KERNEL_TOP_LEFT, k=-3).copy(),
}


class FusionProcessor:
    """
    Multi-modal fusion processor for thermal and RGB cameras
    Supports multiple fusion strategies optimized for driving assistance
    """

    # Single source of truth for which fusion modes exist - process()'s
    # if/elif chain implements exactly these. cli.py's --fusion-mode
    # choices and fusion_panel.py's GUI dropdown both import this list
    # rather than keeping their own copy, after three independent
    # hardcoded copies (this class's old get_available_modes()/
    # set_fusion_mode() list, cli.py, fusion_panel.py) drifted out of
    # sync with each other and with process() itself - two modes
    # (detail_inject, relief_fusion) were fully implemented but
    # unreachable via get_available_modes()/set_fusion_mode(), and three
    # more (thermal_contours, enhanced_edge_highlight, laplacian_pyramid)
    # were unreachable via the CLI and GUI dropdown.
    # 'enhanced_edge_highlight' was removed 2026-09-07, merged into
    # 'edge_enhanced' as its opt-in multi-scale detail_balance setting -
    # see detail_balance's own __init__ docstring for why. Kept as a
    # historical note here in case an old saved config/CLI arg still
    # references the name: set_fusion_mode()/argparse's own choices=
    # validation both reject it cleanly (a logged warning, not a crash).
    AVAILABLE_FUSION_MODES = [
        'alpha_blend', 'detail_inject', 'relief_fusion', 'edge_enhanced',
        'thermal_overlay', 'side_by_side', 'picture_in_picture',
        'max_intensity', 'feature_weighted', 'thermal_contours',
        'laplacian_pyramid', 'pca_fusion', 'guided_filter_fusion',
    ]

    # Human-readable labels for AVAILABLE_FUSION_MODES, for GUI display -
    # fusion_panel.py's dropdown used to show these raw snake_case mode
    # strings directly to the user instead of a proper name.
    FUSION_MODE_LABELS = {
        'alpha_blend': 'Alpha Blend',
        'detail_inject': 'Detail Injection',
        'relief_fusion': 'Relief Fusion',
        'edge_enhanced': 'Edge Enhanced',
        'thermal_overlay': 'Thermal Overlay',
        'side_by_side': 'Side by Side',
        'picture_in_picture': 'Picture in Picture',
        'max_intensity': 'Max Intensity',
        'feature_weighted': 'Feature Weighted',
        'thermal_contours': 'Thermal Contours',
        'laplacian_pyramid': 'Laplacian Pyramid',
        'pca_fusion': 'PCA Fusion',
        'guided_filter_fusion': 'Guided Filter Fusion',
    }

    def __init__(self, fusion_mode: str = 'alpha_blend', alpha: float = 0.5,
                 calibration_file: Optional[str] = None, fusion_priority: str = 'thermal'):
        """
        Initialize fusion processor

        Args:
            fusion_mode: Fusion strategy
                - 'alpha_blend': Simple weighted average of thermal + RGB
                - 'detail_inject': Detail Injection - overlays grayscale high-frequency detail from RGB
                - 'relief_fusion': Relief Fusion - embossing filter (3D bas-relief effect)
                - 'edge_enhanced': RGB base with thermal edges overlaid (prominent colored edges)
                - 'thermal_overlay': Thermal hotspots overlaid on RGB
                - 'side_by_side': Concatenate thermal and RGB horizontally
                - 'picture_in_picture': Thermal in corner of RGB (or vice versa)
                - 'max_intensity': Take maximum intensity from both sources
                - 'feature_weighted': Adaptive blending based on edge strength
            alpha: Blend ratio for alpha_blend mode (0.0 = all RGB, 1.0 = all thermal)
            calibration_file: Path to camera calibration file (JSON with homography matrix)
            fusion_priority: Which camera gets priority ('thermal' or 'rgb')
                - 'thermal': Thermal is base, RGB overlaid (default)
                - 'rgb': RGB is base, thermal overlaid
        """
        self.fusion_mode = fusion_mode
        self.alpha = alpha
        self.fusion_priority = fusion_priority
        self.calibration_matrix = None
        self.calibration_file = calibration_file
        # Distance (metres) the loaded homography was calibrated at, when the file records it (see
        # cameras/camera_calibration.py). A homography measured on a plane at that distance already contains the
        # baseline parallax for that distance; see set_parallax_composition().
        self.calibration_distance_m = None
        self.calibration_info = {}
        self._parallax_composition = None   # (correction_target, shift_px) or None
        # "color" (default) or "grayscale" - see set_fusion_color_mode() and
        # align_rgb_to_thermal()'s apply_color_mode parameter for why this
        # conversion happens where it does rather than in the caller.
        self.fusion_color_mode = "color"

        # Load edge colors and intensity from config
        from thermal_inspection.utils.config import get_config
        config = get_config()
        # Thermal priority: RGB edges on thermal base (cyan by default)
        self.thermal_priority_edge_color = tuple(config.get('fusion.edge_enhanced.thermal_priority_edge_color', [255, 255, 0]))
        # RGB priority: Thermal edges on RGB base (red by default)
        self.rgb_priority_edge_color = tuple(config.get('fusion.edge_enhanced.rgb_priority_edge_color', [0, 0, 255]))
        # Fusion intensity: controls overlay strength (0.0 = minimal, 1.0 = maximum)
        self.fusion_intensity = float(config.get('fusion.intensity', 0.5))

        # Hardware acceleration status - detection only. No fusion mode
        # below actually dispatches to cv2.cuda.GpuMat; every blend runs on
        # CPU (OpenCV SIMD/IPP) regardless of this flag's value. Making this
        # real means writing cv2.cuda.GpuMat variants of the fusion
        # algorithms (upload/compute/download per frame) - a separate,
        # substantial feature, not a wiring fix - and profiling whether
        # that's even a net win at these frame sizes given the transfer
        # overhead. cv2.cuda is also NVIDIA-only regardless; there's no
        # equivalent OpenCV GPU path for AMD without a much larger
        # OpenCL/UMat rewrite.
        self.has_cuda = hasattr(cv2, 'cuda') and hasattr(cv2.cuda, 'getCudaEnabledDeviceCount') and cv2.cuda.getCudaEnabledDeviceCount() > 0
        if self.has_cuda:
            logger.info("FusionProcessor: CUDA GPU detected (not used - all fusion modes run on CPU)")
        else:
            logger.info("FusionProcessor: Running in CPU vectorized mode (OpenCV SIMD / IPP)")


        # Edge detection parameters (NEW)
        self.edge_threshold_low = 50   # Canny low threshold (more edges = lower value)
        self.edge_threshold_high = 150  # Canny high threshold (more edges = lower value)
        self.edge_blur_kernel = 0      # Gaussian blur kernel size for edge sharpness (0 = sharp edges, >0 = softer edges)

        # edge_enhanced's line thickness (0.0-1.0), independent of
        # fusion_intensity - previously dilation_size was derived directly
        # from fusion_intensity, coupling "how visible" and "how thick" into
        # one slider with no way to have thin-but-bold or thick-but-subtle
        # edges. 0.5 default reproduces the old formula's behavior at the
        # UI's default fusion_intensity (0.7) almost exactly (dilation_size 3
        # either way), so existing configs don't visibly jump on upgrade.
        self.edge_line_size = 0.5

        # thermal_contours' contour-line coloring: None falls back to the
        # previous hardcoded rainbow (contour_colors in _thermal_contours),
        # matching old behavior when nothing has set this yet. Set via
        # set_palette_lut() to a (256,3) BGR array (PaletteManager.
        # get_current_palette_lut()'s exact contract) to have contour colors
        # sample the same active palette the thermal image itself is
        # colorized with, instead of an unrelated fixed rainbow.
        self.palette_lut = None

        # thermal_contours' own line thickness (0.0-1.0) - deliberately a
        # separate value from edge_line_size (used by edge_enhanced): a
        # drawn isotherm polyline and a dilated
        # Canny edge are visually/semantically different things, and
        # coupling them would mean adjusting one mode's line size silently
        # changes an unrelated mode's contours too.
        self.contour_line_size = 0.5

        # thermal_contours' number of threshold levels (3-12, default 8 -
        # unchanged from the original hardcoded value). More levels = finer
        # temperature gradation but cost scales roughly linearly (each
        # level is its own threshold+findContours+drawContours pass), and
        # past ~12 closely-spaced isotherm colors become hard to
        # distinguish anyway - clamped rather than left unbounded.
        self.contour_level_count = 8

        # thermal_contours' isotherm value labels - off by default. Only
        # ever draws a real number when the frame is confirmed radiometric
        # (is_radiometric passed into process()); silently does nothing on
        # a non-radiometric feed rather than showing a fabricated
        # temperature, matching this codebase's radiometric-accuracy
        # conventions elsewhere (IsothermManager, radiometric_converter).
        self.contour_labels_enabled = False

        # thermal_contours' isotherm label unit - previously hardcoded to
        # 'C' regardless of the app-wide temperature unit setting (Settings/
        # Radiometric panel's Celsius/Fahrenheit/Kelvin choice, which every
        # other on-screen temperature - spot meters, ROI stats, the
        # histogram - already respects). Kept as a plain 'C'/'F'/'K' string
        # rather than importing RadiometricController's TemperatureUnit
        # enum, so this module stays decoupled from that GUI-adjacent
        # class; app.py's own set_temperature_unit() translates the enum
        # to this string when pushing a change through.
        self.contour_temp_unit = 'C'

        # thermal_contours' optional translucent per-level fill - off by
        # default (pure line-drawing, unchanged from this mode's original
        # behavior). Each level's own cumulative "gray >= threshold" mask
        # gets its own contour color blended in at low alpha, before that
        # level's line is drawn on top - since higher levels' masks nest
        # inside lower levels' masks, the accumulated blend naturally reads
        # as a graduated heat tint (more saturated toward the hottest
        # region) rather than one flat wash, without needing separate
        # exclusive-band math.
        self.contour_fill_enabled = False

        # edge_enhanced: opt-in enhancements, each off by default so the
        # existing fast/known-good path is unchanged unless deliberately
        # enabled.
        #
        # sobel_alpha_enabled: modulates edge opacity by normalized Sobel
        # gradient magnitude within Canny's edge pixels (strong edges more
        # opaque, faint edges more transparent) instead of one flat alpha
        # for every edge pixel. Adds a real Sobel+magnitude cost per call.
        self.sobel_alpha_enabled = False

        # adaptive_canny_enabled: per-frame median-based Canny thresholds
        # (the standard 0.33x/1.33x-median technique) instead of the fixed
        # edge_threshold_low/high, so detection density stays consistent
        # as scene brightness/temperature range shifts. The median itself
        # is throttled (recomputed every adaptive_canny_interval frames,
        # not every frame) since computing it over a full frame every call
        # would add real, avoidable cost for a value that rarely needs to
        # change faster than that.
        self.adaptive_canny_enabled = False
        self.adaptive_canny_interval = 15
        self._adaptive_canny_frame_counter = 0
        self._adaptive_canny_cached_thresholds = None  # (low, high), refreshed every Nth call

        # edge_color_mode: 'fixed' (default, uses edge_color as one flat
        # color) or 'palette' (samples the active palette at each edge
        # pixel's own thermal value). Off by default: against a full-color
        # RGB or colorized-thermal base, an edge colored to match its own
        # surrounding temperature can blend into the very background it's
        # supposed to stand out against. That risk mostly disappears when
        # RGB Mode is set to Grayscale (fusion_color_mode='grayscale') -
        # a colorized (chromatic) edge reads as different from a
        # desaturated base regardless of whether its hue happens to match
        # the local brightness, so palette mode is genuinely well-suited
        # to that pairing specifically, not just a style choice either way.
        self.edge_color_mode = 'fixed'

        # edge_direction: 'all' (default, unchanged Canny/Sobel-magnitude
        # behavior), 'horizontal', or 'vertical' - restricts detection to
        # one gradient axis, useful for isolating linear structure (pipe
        # runs, conduit, studs) from ambient texture noise. 'all' is a
        # strict no-op vs. today's behavior.
        self.edge_direction = 'all'

        # Edge Enhanced's optional multi-scale cross-scale consensus
        # strictness (0.0-1.0). History: this was originally a separate
        # top-level mode ("Enhanced Edge Highlight") whose own multi-scale
        # step first blended 3 scales additively - a real scene's genuine
        # edges show up at every scale almost by definition, so that
        # union-like combine produced output nearly indistinguishable from
        # Edge Enhanced's plain single-scale Canny (confirmed directly by
        # the user testing the live app, twice, across two different
        # attempts at differentiating them: "I can meaningfully produce an
        # image that appears so visually similar that they are not
        # different enough," and later "they are still the same mode...
        # they do the same thing even if the algorithm is slightly
        # different"). A first fix redefined the combine as a genuine
        # cross-scale CONSENSUS filter instead (an edge only survives if
        # the fine scale detects it AND at least round(balance*2) of the 2
        # coarser scales - medium, large - corroborate it there too, see
        # _detect_edges_multiscale) - a real, measurable difference on
        # synthetic test scenes, but still not perceptually distinct
        # enough on real camera footage per the second report above. The
        # honest conclusion: "single-scale vs. multi-scale consensus" is a
        # parameter of ONE edge-detection strategy, not two fusion
        # concepts that deserve separate top-level modes - merged into
        # Edge Enhanced as this optional setting instead of continuing to
        # tweak two mostly-identical modes. Default 0.0 (single-scale
        # only, i.e. off) so Edge Enhanced's own long-standing default
        # behavior is unchanged; turning this up opts into the consensus
        # filter's denoising behavior.
        self.detail_balance = 0.0

        # Detail Injection / Relief Fusion parameters
        self.detail_strength = 0.7     # Detail overlay strength (0.0 = subtle, 1.0 = strong)
        self.detail_quality = 0.5      # Detail quality/level (0.0 = less detail, 1.0 = maximum detail)

        # relief_fusion's apparent light-source corner - see
        # _RELIEF_LIGHT_DIRECTIONS' module-level comment. 'top_left' is
        # this mode's original, only-ever-had behavior, kept as the default.
        self.relief_light_direction = 'top_left'

        # thermal_overlay's hot/bright-mask percentile threshold. Was a
        # hardcoded 70 with no way to tune what counts as "hot" for a
        # given scene, on this app's own DEFAULT fusion mode.
        self.overlay_hot_percentile = 70.0

        # picture_in_picture's inset size/corner - previously hardcoded at
        # the function signature's own defaults (0.25, 'top-right') with
        # no way to change either from the GUI at all.
        self.pip_size = 0.25
        self.pip_position = 'top-right'

        # guided_filter_fusion's internal processing resolution scale
        # (1.0 = full res). Its saliency+guided-filter weight map is
        # inherently smooth/low-frequency, so it tolerates downsampling
        # well - measured at full res on a 640x512 frame: ~69ms/frame
        # mean, up to 109ms (would cap this mode under 15fps); the
        # default 0.5 cuts the guided-filter core's own cost by roughly
        # 5x (13.1ms/call at 512x640 down to 2.6ms at 256x320, measured
        # directly) for a weight map that's upsampled back with
        # INTER_LINEAR before the final full-resolution color blend.
        self.guided_filter_scale = 0.5

        # laplacian_pyramid perf/quality controls. This mode's cost is
        # dominated entirely by its full-resolution base level (measured:
        # ~35ms/frame at 640x512, ~28 FPS ceiling - reducing pyramid depth
        # barely moves this, since each deeper level is 4x fewer pixels
        # than the last and therefore nearly free already). Two independent
        # levers, in preference order:
        #   1. GPU (torch/CUDA), when available - keeps the algorithm at
        #      full resolution, no quality loss (measured ~14ms/frame,
        #      ~73 FPS on an RTX 4000 Ada; output within ~2/255 mean of the
        #      CPU path - difference is kernel shape, not resolution loss).
        #   2. CPU fallback at reduced internal resolution
        #      (laplacian_cpu_scale) when no CUDA GPU is available or GPU
        #      use is disabled - a real, visible softening trade (measured
        #      mean diff ~41/255 vs full-res CPU at scale=0.5) users should
        #      be able to see and adjust, not one silently baked in.
        self.laplacian_use_gpu = True      # only takes effect if a CUDA GPU is actually available
        self.laplacian_cpu_scale = 0.5     # 0.25-1.0; internal resolution scale for the CPU fallback path
        self._laplacian_device_requested = "auto"
        self._laplacian_torch_device = None   # resolved lazily - see _resolve_laplacian_gpu()
        self._laplacian_gpu_ready = False     # whether torch/CUDA were actually confirmed usable
        self._laplacian_sobel_kernels = None  # (sobel_x, sobel_y) torch tensors, cached per resolved device

        # feature_weighted GPU path - same lazy-detect/cached-kernel/
        # fallback-on-failure pattern as laplacian_pyramid above. No CPU-
        # side quality/speed scale knob here (unlike laplacian_cpu_scale):
        # the CPU path is already the full-quality baseline min-spec
        # hardware (down to 8th-gen U-series, integrated graphics only,
        # no CUDA) runs unmodified - GPU is a pure bonus path on top of
        # it, never a requirement.
        self.feature_weighted_use_gpu = True
        self._fw_device_requested = "auto"
        self._fw_torch_device = None
        self._fw_gpu_ready = False
        self._fw_sobel_kernel = None  # (1,1,3,3) torch tensor - Sobel(dx=1,dy=1,ksize=3)'s exact kernel

        # Load calibration if available
        if calibration_file and os.path.exists(calibration_file):
            self.load_calibration(calibration_file)
        else:
            logger.warning("No calibration file provided - using identity transform")

    def load_calibration(self, calibration_file: str) -> bool:
        """
        Load camera calibration from file

        Args:
            calibration_file: Path to JSON file with homography matrix

        Returns:
            True if successful
        """
        try:
            with open(calibration_file) as f:
                calib_data = json.load(f)

            # Load homography matrix (3x3)
            if 'homography' in calib_data:
                self.calibration_matrix = np.array(calib_data['homography'], dtype=np.float32)
                dist = calib_data.get('working_distance_m')
                self.calibration_distance_m = float(dist) if isinstance(dist, (int, float)) and dist > 0 else None
                self.calibration_info = {k: v for k, v in calib_data.items() if k != 'homography'}
                self._parallax_composition = None
                logger.info(f"Loaded calibration from {calibration_file}"
                            + (f" (calibrated at {self.calibration_distance_m:g} m)"
                               if self.calibration_distance_m else " (no calibration distance recorded)"))
                return True
            else:
                logger.error("Calibration file missing 'homography' key")
                return False

        except Exception as e:
            logger.error(f"Failed to load calibration: {e}")
            return False

    def save_calibration(self, calibration_file: str) -> bool:
        """
        Save camera calibration to file

        Args:
            calibration_file: Path to output JSON file

        Returns:
            True if successful
        """
        try:
            if self.calibration_matrix is None:
                logger.error("No calibration matrix to save")
                return False

            calib_data = dict(self.calibration_info)
            calib_data['homography'] = self.calibration_matrix.tolist()
            if self.calibration_distance_m:
                calib_data['working_distance_m'] = self.calibration_distance_m

            with open(calibration_file, 'w') as f:
                json.dump(calib_data, f, indent=2)

            logger.info(f"Saved calibration to {calibration_file}")
            return True

        except Exception as e:
            logger.error(f"Failed to save calibration: {e}")
            return False

    def set_mode(self, fusion_mode: str):
        """
        Set fusion mode dynamically. Alias for set_fusion_mode() - this is
        the method FusionController actually calls (the GUI's live path),
        while set_fusion_mode() is used by the --auto-cycle-fusion-modes
        testing path and the test suite. These used to be two independently
        maintained implementations with two different mode lists; this one's
        own `valid_modes` was missing thermal_contours, enhanced_edge_highlight,
        and laplacian_pyramid entirely (and had a stale 'anomaly_priority'
        entry that isn't a real mode at all) - selecting any of those three
        from the GUI silently no-opped here, leaving whatever mode was
        already active running, which is exactly why they all looked
        identical. Delegating to set_fusion_mode() means there's only one
        mode list (AVAILABLE_FUSION_MODES) for both call paths to drift
        out of sync with, ever again.

        Args:
            fusion_mode: New fusion mode to use
        """
        self.set_fusion_mode(fusion_mode)

    def set_priority(self, priority: str):
        """
        Set fusion priority dynamically

        Args:
            priority: Which camera gets priority ('thermal' or 'rgb')
        """
        if priority in ['thermal', 'rgb']:
            self.fusion_priority = priority
            logger.info(f"Fusion priority changed to: {priority}")
        else:
            logger.warning(f"Invalid priority '{priority}', must be 'thermal' or 'rgb'")

    def set_intensity(self, intensity: float):
        """
        Set fusion intensity dynamically
        Controls overlay strength for edge_enhanced, thermal_overlay, and feature_weighted modes

        Args:
            intensity: Overlay strength (0.0 = minimal, 1.0 = maximum)
        """
        if 0.0 <= intensity <= 1.0:
            self.fusion_intensity = intensity
            logger.info(f"Fusion intensity set to: {intensity:.2f}")
        else:
            logger.warning(f"Invalid intensity value {intensity}, must be between 0.0 and 1.0")

    def set_device(self, device: str):
        """
        Force the compute device ('cpu', 'cuda', 'directml' - Intel/AMD,
        see utils/gpu_device.py - or 'auto') used for the
        laplacian_pyramid GPU path. feature_weighted has its own separate
        GPU path/state (see set_feature_weighted_gpu_enabled) so a mode
        switch here can't silently affect the other; every remaining
        fusion mode has no GPU code path to switch (see has_cuda's
        comment in __init__).
        """
        device = device.lower()
        if device not in ('cpu', 'cuda', 'directml', 'auto'):
            logger.warning(f"Unknown fusion device '{device}', ignoring")
            return
        self._laplacian_device_requested = device
        self._laplacian_torch_device = None  # re-resolve on next use
        self._laplacian_gpu_ready = False
        self._laplacian_sobel_kernels = None
        logger.info(f"laplacian_pyramid compute device set to: {device}")

    def set_laplacian_gpu_enabled(self, enabled: bool):
        """Enable/disable the GPU (torch/CUDA) path for laplacian_pyramid. No effect if no CUDA GPU is available."""
        self.laplacian_use_gpu = bool(enabled)
        logger.info(f"laplacian_pyramid GPU acceleration: {'ON' if enabled else 'OFF'}")

    def set_feature_weighted_gpu_enabled(self, enabled: bool):
        """Enable/disable the GPU (torch/CUDA) path for feature_weighted. No effect if no CUDA GPU is available."""
        self.feature_weighted_use_gpu = bool(enabled)
        logger.info(f"feature_weighted GPU acceleration: {'ON' if enabled else 'OFF'}")

    def set_laplacian_cpu_scale(self, scale: float):
        """
        Set the internal processing resolution scale used by
        laplacian_pyramid's CPU fallback path (no effect when the GPU path
        is active). 1.0 = full resolution (~28 FPS ceiling on typical
        hardware); lower values trade a real, visible loss of edge/detail
        precision for speed (0.5 measured ~4x faster).
        """
        scale = float(scale)
        if not (0.25 <= scale <= 1.0):
            logger.warning(f"Invalid laplacian_pyramid CPU scale {scale}, must be between 0.25 and 1.0")
            return
        self.laplacian_cpu_scale = scale
        logger.info(f"laplacian_pyramid CPU fallback scale set to: {scale:.2f}")

    def set_edge_color(self, color: Tuple[int, int, int], priority: str = None):
        """
        Set edge color for edge-enhanced fusion mode

        Args:
            color: BGR color tuple (0-255 for each channel)
            priority: Which priority mode this color applies to ('thermal' or 'rgb')
                     If None, applies to current priority
        """
        if priority is None:
            priority = self.fusion_priority

        if priority == 'thermal':
            self.thermal_priority_edge_color = tuple(color)
            logger.info(f"Thermal priority edge color set to: {color}")
        elif priority == 'rgb':
            self.rgb_priority_edge_color = tuple(color)
            logger.info(f"RGB priority edge color set to: {color}")
        else:
            logger.warning(f"Invalid priority '{priority}', must be 'thermal' or 'rgb'")

    def set_edge_strength(self, threshold_low: int, threshold_high: int = None):
        """
        Set edge detection strength (Canny thresholds)
        Lower values = more edges detected, Higher values = fewer edges

        Args:
            threshold_low: Lower threshold for Canny edge detection (10-100 typical)
            threshold_high: Upper threshold (if None, automatically set to 3x low threshold)
        """
        threshold_low = max(1, min(200, threshold_low))  # Clamp to reasonable range
        if threshold_high is None:
            threshold_high = threshold_low * 3
        else:
            threshold_high = max(threshold_low, min(300, threshold_high))

        self.edge_threshold_low = threshold_low
        self.edge_threshold_high = threshold_high
        logger.info(f"Edge thresholds set to: low={threshold_low}, high={threshold_high}")

    def set_edge_blur(self, kernel_size: int):
        """
        Set edge fuzziness (Gaussian blur applied to edge mask after detection)
        Controls edge sharpness without affecting which edges are detected.

        Lower values = sharp, crisp edges (more detail visible)
        Higher values = soft, blurred edges (smoother appearance)

        Args:
            kernel_size: Gaussian blur kernel size (0 = no blur/sharp, 1-15 typical for soft)
                        Will be converted to odd number for cv2.GaussianBlur
        """
        if kernel_size < 0:
            kernel_size = 0
        elif kernel_size > 0 and kernel_size % 2 == 0:
            kernel_size += 1  # Ensure odd number

        self.edge_blur_kernel = min(15, kernel_size)
        logger.info(f"Edge blur kernel size set to: {self.edge_blur_kernel}")

    def set_edge_line_size(self, line_size: float) -> None:
        """
        Set edge_enhanced's line thickness (0.0-1.0), independent
        of fusion_intensity (which controls edge visibility/alpha). Was
        previously derived from fusion_intensity directly, coupling
        thickness to opacity with no way to set them separately.
        """
        self.edge_line_size = max(0.0, min(1.0, line_size))
        logger.info(f"Edge line size set to: {self.edge_line_size}")

    def set_palette_lut(self, lut: Optional[np.ndarray]) -> None:
        """
        Set the (256,3) BGR palette LUT thermal_contours samples its
        contour-line colors from, so contour colors track whichever palette
        the thermal image itself is colorized with (White Hot, Ironbow,
        etc.) instead of an unrelated fixed rainbow. Pass None to restore
        the fixed-rainbow fallback.
        """
        if lut is not None and (lut.ndim != 2 or lut.shape[0] < 256 or lut.shape[1] != 3):
            logger.warning(f"Ignoring invalid palette LUT shape: {None if lut is None else lut.shape}")
            return
        self.palette_lut = lut

    def set_contour_line_size(self, line_size: float) -> None:
        """Set thermal_contours' line thickness (0.0-1.0), independent of edge_line_size."""
        self.contour_line_size = max(0.0, min(1.0, line_size))

    def set_contour_level_count(self, count: int) -> None:
        """Set thermal_contours' number of threshold levels, clamped 3-12."""
        self.contour_level_count = max(3, min(12, int(count)))

    def set_contour_labels_enabled(self, enabled: bool) -> None:
        """Enable thermal_contours' isotherm value labels - only ever draws
        a number when process() is given a temperature_map_c (either a
        true 16-bit-radiometric conversion or the existing 8-bit AGC
        estimation path, see ThermalTemperatureEstimator); a no-op
        otherwise regardless of this setting. Estimated labels are marked
        with a leading '~' to disclose the lower (documented +/-5-10C)
        accuracy rather than presenting them as exact."""
        self.contour_labels_enabled = bool(enabled)

    def set_contour_temp_unit(self, unit: str) -> None:
        """Set thermal_contours' isotherm label unit: 'C', 'F', 'K', or 'RAW' (Y16, Kelvin x 100) (case-insensitive)."""
        normalized = (unit or '').strip().upper()
        # Accept the app's own longer forms too ('celsius'/'fahrenheit'/
        # 'kelvin') as well as the single-letter codes, since app.py's
        # set_temperature_unit() is itself called with either depending
        # on the caller (RadiometricController accepts both).
        aliases = {'CELSIUS': 'C', 'FAHRENHEIT': 'F', 'KELVIN': 'K', 'Y16': 'RAW'}
        normalized = aliases.get(normalized, normalized)
        if normalized not in ('C', 'F', 'K', 'RAW'):
            logger.warning(f"Invalid contour_temp_unit '{unit}', must be 'C', 'F', 'K', or 'RAW'")
            return
        self.contour_temp_unit = normalized

    def set_contour_fill_enabled(self, enabled: bool) -> None:
        """Enable thermal_contours' translucent per-level fill, highlighting each isotherm's own region."""
        self.contour_fill_enabled = bool(enabled)

    def set_sobel_alpha_enabled(self, enabled: bool) -> None:
        """Enable Sobel-magnitude-modulated edge opacity for edge_enhanced
        (opt-in, adds real per-frame cost)."""
        self.sobel_alpha_enabled = bool(enabled)

    def set_adaptive_canny_enabled(self, enabled: bool) -> None:
        """Enable per-frame median-based Canny thresholds (throttled - see
        adaptive_canny_interval), overriding edge_threshold_low/high."""
        self.adaptive_canny_enabled = bool(enabled)
        self._adaptive_canny_cached_thresholds = None  # force recompute on next call

    def set_edge_color_mode(self, mode: str) -> None:
        """Set edge coloring mode: 'fixed' (default) or 'palette'. Palette
        mode risks edges blending into their surroundings - see
        edge_color_mode's own docstring in __init__."""
        if mode not in ('fixed', 'palette'):
            logger.warning(f"Invalid edge_color_mode '{mode}', must be 'fixed' or 'palette'")
            return
        self.edge_color_mode = mode

    def set_edge_direction(self, direction: str) -> None:
        """Set edge detection direction: 'all' (default), 'horizontal', or 'vertical'."""
        if direction not in ('all', 'horizontal', 'vertical'):
            logger.warning(f"Invalid edge_direction '{direction}', must be 'all', 'horizontal', or 'vertical'")
            return
        self.edge_direction = direction

    def set_detail_balance(self, balance: float) -> None:
        """Set edge_enhanced's optional multi-scale consensus strictness (0.0-1.0, default 0.0/off) - see its docstring in __init__."""
        self.detail_balance = max(0.0, min(1.0, balance))

    def set_relief_light_direction(self, direction: str) -> None:
        """Set relief_fusion's apparent light-source corner - see _RELIEF_LIGHT_DIRECTIONS."""
        if direction not in _RELIEF_LIGHT_DIRECTIONS:
            logger.warning(f"Invalid relief_light_direction '{direction}', must be one of {list(_RELIEF_LIGHT_DIRECTIONS)}")
            return
        self.relief_light_direction = direction

    def set_overlay_hot_percentile(self, percentile: float) -> None:
        """Set thermal_overlay's hot/bright-mask percentile threshold (1-99, default 70)."""
        self.overlay_hot_percentile = max(1.0, min(99.0, percentile))

    def set_pip_size(self, size: float) -> None:
        """Set picture_in_picture's inset size as a fraction of the main frame (0.1-0.9, default 0.25)."""
        self.pip_size = max(0.1, min(0.9, size))

    def set_pip_position(self, position: str) -> None:
        """Set picture_in_picture's inset corner: 'top-left', 'top-right', 'bottom-left', or 'bottom-right'."""
        valid = ('top-left', 'top-right', 'bottom-left', 'bottom-right')
        if position not in valid:
            logger.warning(f"Invalid pip_position '{position}', must be one of {valid}")
            return
        self.pip_position = position

    def set_guided_filter_scale(self, scale: float) -> None:
        """Set guided_filter_fusion's internal processing resolution scale (0.25-1.0, default 0.5)."""
        self.guided_filter_scale = max(0.25, min(1.0, scale))

    def _get_canny_thresholds(self, gray: np.ndarray) -> Tuple[float, float]:
        """
        (low, high) Canny thresholds - either the fixed edge_threshold_low/
        high (default), or adaptive_canny_enabled's per-frame median-based
        pair (the standard 0.33x/1.33x-median technique), throttled to
        recompute only every adaptive_canny_interval calls rather than
        every frame. A full-frame np.median is real, avoidable cost
        (potentially more than Canny itself on a 1280x800+ RGB source) for
        a value that doesn't need to track scene brightness at full frame
        rate - between recomputes the previous frame's thresholds are
        reused, same throttling idea as ThreadedAnalyzer elsewhere.
        """
        if not self.adaptive_canny_enabled:
            return self.edge_threshold_low, self.edge_threshold_high

        self._adaptive_canny_frame_counter += 1
        if (self._adaptive_canny_cached_thresholds is None
                or self._adaptive_canny_frame_counter % self.adaptive_canny_interval == 0):
            median = float(np.median(gray))
            low = max(0.0, 0.67 * median)
            high = min(255.0, 1.33 * median)
            self._adaptive_canny_cached_thresholds = (low, high)

        return self._adaptive_canny_cached_thresholds

    def _detect_edges(self, gray: np.ndarray, threshold_low: float, threshold_high: float) -> np.ndarray:
        """
        Binary edge mask (uint8, 0/255). edge_direction == 'all' is plain
        Canny - unchanged from this codebase's original behavior. Canny
        has no direction parameter, so 'horizontal'/'vertical' instead
        threshold a single-axis Sobel gradient magnitude (the standard way
        to restrict edge detection to one axis - useful for isolating
        linear structure like pipe/conduit runs from ambient texture).

        threshold_low/high are calibrated for Canny's own internal
        gradient scale; the directional path normalizes Sobel's raw
        magnitude to the current frame's own min-max range and maps
        Canny's conventional 0-300ish threshold scale onto that
        normalized range, so the same slider still means "more/fewer
        edges" in both modes - not a claim that a given number produces
        an identical edge density in both, since the two aren't computing
        edges the same way.
        """
        if self.edge_direction == 'all':
            return cv2.Canny(gray, threshold_low, threshold_high)

        dx, dy = (0, 1) if self.edge_direction == 'horizontal' else (1, 0)
        sobel = cv2.Sobel(gray, cv2.CV_32F, dx, dy, ksize=3)
        np.abs(sobel, out=sobel)
        sobel_norm = cv2.normalize(sobel, None, 0, 255, cv2.NORM_MINMAX)
        low_u8 = int(np.clip(threshold_low / 300.0, 0.0, 1.0) * 255)
        _, edges = cv2.threshold(sobel_norm, low_u8, 255, cv2.THRESH_BINARY)
        return edges.astype(np.uint8)

    def _sobel_alpha_within_mask(self, gray: np.ndarray, edge_mask: np.ndarray) -> np.ndarray:
        """
        Per-pixel opacity (float32, 0.0-1.0) for sobel_alpha_enabled -
        Sobel gradient magnitude normalized against a high percentile of
        its own values WITHIN the already-detected edge pixels (not the
        whole frame, which would let one strong edge elsewhere dim every
        other edge's relative strength), so a strong edge renders more
        opaque than a faint one instead of every edge pixel getting the
        same flat alpha. Returns an all-zero array (matching "no edges" ->
        "no visible overlay") if edge_mask has no set pixels, avoiding a
        division by zero.

        Live-reported: "the line opacity is too low." Root cause,
        confirmed by direct measurement: this used to normalize against
        the single STRONGEST in-mask pixel (magnitude[mask_bool].max()),
        which sounds equivalent to "within the mask" but isn't robust to
        it - on a realistic scene the one strongest detected edge commonly
        exceeds the rest by several times over (measured 276.5 vs a median
        of 28.5 on a representative test scene), so dividing every pixel
        by that single extreme value crushed essentially every OTHER edge
        toward zero: median opacity 0.103, 88.8% of edge pixels below 0.2,
        confirmed directly before touching this.

        A first attempt used the 90th percentile as the reference, but was
        reported the same day as losing detail - confirmed why by direct
        measurement: p90 pushed 19.4% of edge pixels to full saturation
        and a mean opacity of 0.518, compressing most of the frame's real
        strong/weak edge distinction into a similar high opacity rather
        than preserving it. The 95th percentile keeps the exact same
        documented intent (a stronger edge renders more opaque than a
        fainter one, and no longer letting one pixel set the scale for
        the whole frame) while saturating far fewer edges (9.1%, mean
        0.418 on the same scene) - a real, substantial improvement over
        the original single-max normalization without flattening the
        contrast between genuinely strong and weak edges the way p90 did.
        """
        sobel_x = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
        sobel_y = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
        magnitude = cv2.magnitude(sobel_x, sobel_y)

        mask_bool = edge_mask > 0
        if not np.any(mask_bool):
            return np.zeros_like(magnitude)

        reference = float(np.percentile(magnitude[mask_bool], 95))
        if reference <= 0:
            return mask_bool.astype(np.float32)

        alpha = magnitude / reference
        np.clip(alpha, 0.0, 1.0, out=alpha)
        alpha *= mask_bool  # zero outside the actual edge mask
        return alpha

    @staticmethod
    def _crop_to_aspect_ratio(frame: np.ndarray, target_w: int, target_h: int) -> np.ndarray:
        """
        Center-crop frame to target_w/target_h's aspect ratio, then resize
        to that exact size - a uniform scale with no distortion, unlike a
        plain resize straight to (target_w, target_h) which stretches
        non-uniformly whenever the source and target aspect ratios differ
        (e.g. a RealSense's 16:10ish color stream against a 4:3 thermal
        sensor) - visibly "squishing" one frame into the other's shape and
        throwing off which real-world point lines up with which in the
        fused result, not just a cosmetic distortion.
        """
        src_h, src_w = frame.shape[:2]
        if src_w == 0 or src_h == 0:
            return cv2.resize(frame, (target_w, target_h), interpolation=cv2.INTER_LINEAR)

        target_ratio = target_w / target_h
        src_ratio = src_w / src_h

        if abs(src_ratio - target_ratio) < 1e-3:
            cropped = frame
        elif src_ratio > target_ratio:
            # Source is relatively wider than target - crop its width,
            # keep full height.
            new_w = max(1, int(round(src_h * target_ratio)))
            x0 = (src_w - new_w) // 2
            cropped = frame[:, x0:x0 + new_w]
        else:
            # Source is relatively taller than target - crop its height,
            # keep full width.
            new_h = max(1, int(round(src_w / target_ratio)))
            y0 = (src_h - new_h) // 2
            cropped = frame[y0:y0 + new_h, :]

        return cv2.resize(cropped, (target_w, target_h), interpolation=cv2.INTER_LINEAR)

    def set_parallax_composition(self, correction_target: Optional[str], shift_px: float = 0.0):
        """Tell the processor that depth-based parallax correction is ALSO active, and how much baseline shift it
        applies at the distance the homography was calibrated at (ParallaxCompensator.geometric_shift_px_at). Pass
        None when parallax correction is off. Without this, the shift is applied twice: parallax absorbs the
        distance-dependent baseline shift and the homography still contains its value at the calibration distance,
        leaving a constant error equal to that shift at every depth (measured in tests/unit/test_alignment_composition.py)."""
        self._parallax_composition = None if correction_target is None else (correction_target, float(shift_px))

    def effective_calibration_matrix(self) -> Optional[np.ndarray]:
        """The calibration homography actually applied to the RGB frame: the loaded one, minus the baseline shift
        parallax correction already supplies (see set_parallax_composition). For correction_target 'thermal' the
        parallax step moves the THERMAL frame, so the shift is removed in the output (thermal) space; for 'rgb' it
        moves the RGB frame before this warp, so it is removed in the input (RGB) space."""
        H = self.calibration_matrix
        if H is None or self._parallax_composition is None:
            return H
        target, shift = self._parallax_composition
        if shift == 0.0:
            return H
        T = np.eye(3, dtype=np.float64)
        T[0, 2] = shift if target == "thermal" else -shift
        H64 = np.asarray(H, dtype=np.float64)
        return ((T @ H64) if target == "thermal" else (H64 @ T)).astype(np.float32)

    def align_rgb_to_thermal(self, rgb: np.ndarray, thermal_shape: Tuple[int, int],
                             apply_color_mode: bool = False) -> np.ndarray:
        """
        Align RGB frame to thermal frame coordinate system

        Args:
            rgb: RGB frame (any size)
            thermal_shape: Target thermal resolution (height, width)
            apply_color_mode: Also apply fusion_color_mode's grayscale
                conversion, AFTER alignment (see _apply_fusion_color_mode).
                Defaults to False - align_rgb_to_thermal is also called by
                Picture-in-Picture, which has never respected
                fusion_color_mode and shouldn't start silently just
                because this method gained the capability; only the
                fusion-blend call sites (process(), and
                apply_3d_visualization_fused's tensor path) opt in.

        Returns:
            Aligned RGB frame matching thermal dimensions
        """
        target_h, target_w = thermal_shape

        try:
            effective_matrix = self.effective_calibration_matrix()
            if effective_matrix is not None:
                # Use calibration matrix for precise alignment - a real
                # calibration derived from actual correspondence points
                # already accounts for the true geometric relationship
                # between the two cameras (aspect ratio included), so this
                # path is left as a plain warp to the target canvas size.
                rgb_aligned = cv2.warpPerspective(
                    rgb, effective_matrix,
                    (target_w, target_h),
                    flags=cv2.INTER_LINEAR
                )
            else:
                # No calibration - crop to aspect ratio first so the
                # fallback resize is a uniform scale, not a distorting
                # stretch (see _crop_to_aspect_ratio).
                rgb_aligned = self._crop_to_aspect_ratio(rgb, target_w, target_h)

        except Exception as e:
            logger.error(f"Error aligning RGB frame: {e}")
            rgb_aligned = self._crop_to_aspect_ratio(rgb, target_w, target_h)

        if apply_color_mode:
            rgb_aligned = self._apply_fusion_color_mode(rgb_aligned)
        return rgb_aligned

    def _apply_fusion_color_mode(self, rgb_aligned: np.ndarray) -> np.ndarray:
        """
        Apply fusion_color_mode's "grayscale" option to an already-aligned
        (thermal-resolution) RGB frame.

        Every one of this method's 3 call sites (process(), and
        apply_3d_visualization_fused's tensor-fused path in
        fusion_3d_panel.py) used to have app.py convert to grayscale
        BEFORE calling in, at the RGB camera's own native resolution (e.g.
        RealSense's 1280x800) - work immediately thrown away by the very
        next step downscaling to thermal's resolution (e.g. 640x512).
        Doing the conversion here instead, after alignment, measured
        1.46ms -> 0.66ms at those resolutions: grayscale conversion cost
        scales with pixel count, so converting fewer pixels once they're
        already the size that matters is strictly cheaper, not just
        differently ordered.
        """
        if self.fusion_color_mode == "grayscale":
            gray = cv2.cvtColor(rgb_aligned, cv2.COLOR_BGR2GRAY)
            return cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
        return rgb_aligned

    def set_fusion_color_mode(self, mode: str):
        """'color' (default) or 'grayscale' - see _apply_fusion_color_mode."""
        self.fusion_color_mode = mode

    def render_alignment_overlay(self, thermal: np.ndarray, rgb: np.ndarray) -> np.ndarray:
        """
        Visual alignment aid for the Parallax panel's "Show Alignment
        Overlay" - thermal edges in cyan, RGB edges in magenta, composited
        on a black background so misalignment reads as visible color-
        fringed double-edges at a glance instead of requiring a side-by-
        side comparison. Where the two genuinely agree, cyan (B+G) and
        magenta (B+R) additively combine to white - "aligned" has an
        immediate, unambiguous visual signature, not just "look similar".

        Goes through the SAME align_rgb_to_thermal() every fusion mode
        already uses, so the overlay reflects whatever alignment is
        actually in effect (manual shift/zoom via ParallaxCompensator
        upstream, plus a calibration_matrix here if one is ever set) - not
        a separate, potentially-inconsistent computation of it.

        Not a fusion mode of its own (not in AVAILABLE_FUSION_MODES) -
        this is a calibration/debug visualization triggered from the
        Parallax panel, not an inspection view a user would leave on.
        """
        if thermal is None or rgb is None:
            return thermal if thermal is not None else rgb
        if len(thermal.shape) == 2:
            thermal = cv2.cvtColor(thermal, cv2.COLOR_GRAY2BGR)
        if len(rgb.shape) == 2:
            rgb = cv2.cvtColor(rgb, cv2.COLOR_GRAY2BGR)

        thermal_h, thermal_w = thermal.shape[:2]
        rgb_aligned = self.align_rgb_to_thermal(rgb, (thermal_h, thermal_w))

        thermal_gray = cv2.cvtColor(thermal, cv2.COLOR_BGR2GRAY)
        rgb_gray = cv2.cvtColor(rgb_aligned, cv2.COLOR_BGR2GRAY)
        thermal_edges = cv2.Canny(thermal_gray, 50, 150)
        rgb_edges = cv2.Canny(rgb_gray, 50, 150)

        overlay = np.zeros((thermal_h, thermal_w, 3), dtype=np.uint8)
        overlay[:, :, 0] = np.maximum(thermal_edges, rgb_edges)  # B: cyan + magenta both set it
        overlay[:, :, 1] = thermal_edges                          # G: cyan only
        overlay[:, :, 2] = rgb_edges                              # R: magenta only
        return overlay

    def process(self, thermal: np.ndarray, rgb: np.ndarray,
                temperature_map_c: Optional[np.ndarray] = None,
                temp_map_is_estimated: bool = False) -> np.ndarray:
        """
        Fuse thermal and RGB frames using selected strategy

        Args:
            thermal: Thermal frame (colorized, BGR format)
            rgb: RGB frame (BGR format)
            temperature_map_c: Optional float32 Celsius map, same
                resolution as `thermal`, used only by thermal_contours'
                isotherm labels (see contour_labels_enabled). Caller
                decides the source - a true 16-bit radiometric conversion
                or ThermalTemperatureEstimator's 8-bit AGC estimate are
                both valid; FusionProcessor doesn't need to know which.
                None (default) means labels silently do nothing.
            temp_map_is_estimated: Whether temperature_map_c came from the
                8-bit estimation path rather than true radiometric data -
                labels are prefixed '~' when True, to disclose the lower
                accuracy rather than presenting an estimate as exact.

        Returns:
            Fused frame (BGR format)
        """
        # Validate inputs
        if thermal is None or rgb is None:
            logger.error("Invalid input frames for fusion")
            return thermal if thermal is not None else rgb

        # Ensure both frames are BGR
        if len(thermal.shape) == 2:
            thermal = cv2.cvtColor(thermal, cv2.COLOR_GRAY2BGR)
        if len(rgb.shape) == 2:
            rgb = cv2.cvtColor(rgb, cv2.COLOR_GRAY2BGR)

        # Align RGB to thermal dimensions, then apply fusion_color_mode -
        # see align_rgb_to_thermal's apply_color_mode parameter for why
        # this order (not the reverse) matters.
        thermal_h, thermal_w = thermal.shape[:2]
        rgb_aligned = self.align_rgb_to_thermal(
            rgb, (thermal_h, thermal_w), apply_color_mode=True
        )

        # Apply fusion strategy
        if self.fusion_mode == 'alpha_blend':
            return self._alpha_blend(thermal, rgb_aligned)
        elif self.fusion_mode == 'detail_inject':
            return self._detail_inject(thermal, rgb_aligned)
        elif self.fusion_mode == 'relief_fusion':
            return self._relief_fusion(thermal, rgb_aligned)
        elif self.fusion_mode == 'edge_enhanced':
            return self._edge_enhanced(thermal, rgb_aligned)
        elif self.fusion_mode == 'thermal_overlay':
            return self._thermal_overlay(thermal, rgb_aligned)
        elif self.fusion_mode == 'side_by_side':
            return self._side_by_side(thermal, rgb_aligned)
        elif self.fusion_mode == 'picture_in_picture':
            return self._picture_in_picture(thermal, rgb_aligned, pip_size=self.pip_size, position=self.pip_position)
        elif self.fusion_mode == 'max_intensity':
            return self._max_intensity(thermal, rgb_aligned)
        elif self.fusion_mode == 'feature_weighted':
            return self._feature_weighted(thermal, rgb_aligned)
        elif self.fusion_mode == 'thermal_contours':
            return self._thermal_contours(thermal, rgb_aligned, temperature_map_c, temp_map_is_estimated)
        elif self.fusion_mode == 'laplacian_pyramid':
            return self._laplacian_pyramid(thermal, rgb_aligned)
        elif self.fusion_mode == 'pca_fusion':
            return self._pca_fusion(thermal, rgb_aligned)
        elif self.fusion_mode == 'guided_filter_fusion':
            return self._guided_filter_fusion(thermal, rgb_aligned)
        else:
            logger.warning(f"Unknown fusion mode: {self.fusion_mode}, using alpha_blend")
            return self._alpha_blend(thermal, rgb_aligned)

    def _alpha_blend(self, thermal: np.ndarray, rgb: np.ndarray) -> np.ndarray:
        """
        Simple weighted average fusion with priority control

        Args:
            thermal: Thermal frame (BGR)
            rgb: RGB frame (BGR, aligned)

        Returns:
            Blended frame
        """
        try:
            if self.fusion_priority == 'thermal':
                # Thermal-weighted: alpha controls thermal contribution
                return cv2.addWeighted(thermal, self.alpha, rgb, 1.0 - self.alpha, 0)
            else:
                # RGB-weighted: alpha controls RGB contribution
                return cv2.addWeighted(rgb, self.alpha, thermal, 1.0 - self.alpha, 0)
        except Exception as e:
            logger.error(f"Alpha blend error: {e}")
            return thermal

    def _detail_inject(self, thermal: np.ndarray, rgb: np.ndarray) -> np.ndarray:
        """
        Detail Injection fusion - FLIR MSX-style (Multi-Spectral Dynamic Imaging)
        Overlays grayscale high-frequency spatial detail from RGB onto thermal
        Adds visible structure (edges, text, outlines) as grayscale information

        Key insight: MSX extracts sharp GRAYSCALE detail (not binary edges, not embossing)
        from the visible camera and overlays it on thermal to add spatial context
        while preserving thermal radiometric data.

        Args:
            thermal: Thermal frame (BGR, colorized)
            rgb: RGB frame (BGR, aligned)

        Returns:
            Detail-injected thermal frame (thermal + grayscale RGB detail)
        """
        try:
            # Convert RGB to grayscale to extract spatial detail
            rgb_gray = cv2.cvtColor(rgb, cv2.COLOR_BGR2GRAY)

            # Extract high-frequency detail (edges, texture, structure) from RGB
            # Use high-pass filter to isolate sharp features
            # Quality controls blur kernel size (higher quality = larger kernel = more detail isolation)
            kernel_size = int(3 + self.detail_quality * 8)  # Range: 3 to 11
            if kernel_size % 2 == 0:  # Ensure odd kernel size
                kernel_size += 1
            blurred = cv2.GaussianBlur(rgb_gray, (kernel_size, kernel_size), 0)

            # Subtract to get high-frequency detail (edges/structure)
            detail = cv2.subtract(rgb_gray, blurred)

            # Enhance the detail contrast based on quality setting
            # Higher quality = more aggressive contrast enhancement
            contrast_alpha = 2.0 + self.detail_quality * 4.0  # Range: 2.0 to 6.0
            detail = cv2.convertScaleAbs(detail, alpha=contrast_alpha, beta=0)

            # Normalize to full range for better visibility
            if detail.max() > 0:
                detail = cv2.normalize(detail, None, 0, 255, cv2.NORM_MINMAX)

            # Convert detail to BGR for overlay
            detail_bgr = cv2.cvtColor(detail, cv2.COLOR_GRAY2BGR)

            # Overlay grayscale detail onto thermal with strength-controlled blending
            # Higher strength = more visible RGB structure
            blend_strength = self.fusion_intensity * self.detail_strength
            result = cv2.addWeighted(
                thermal, 1.0 - blend_strength * 0.3,  # Slightly reduce thermal
                detail_bgr, blend_strength * 0.7,      # Strength-controlled detail overlay
                0
            )

            return result

        except Exception as e:
            logger.error(f"Detail Injection fusion error: {e}")
            return thermal

    def _relief_fusion(self, thermal: np.ndarray, rgb: np.ndarray) -> np.ndarray:
        """
        Relief Fusion - Embossing filter for 3D bas-relief effect
        Creates 3D bas-relief appearance with highlights/shadows from RGB structure

        Uses convolution with emboss kernel to create raised/recessed appearance
        based on edges and gradients in the visible light image.

        Args:
            thermal: Thermal frame (BGR, colorized)
            rgb: RGB frame (BGR, aligned)

        Returns:
            Relief-fused thermal frame (thermal + embossed RGB structure)
        """
        try:
            # Convert RGB to grayscale for embossing
            rgb_gray = cv2.cvtColor(rgb, cv2.COLOR_BGR2GRAY)

            # Apply emboss filter using convolution kernel. Quality
            # controls emboss kernel strength; relief_light_direction picks
            # which corner the apparent light source sits in (see
            # _RELIEF_LIGHT_DIRECTIONS' own module-level comment) -
            # defaults to 'top_left', this mode's original and only
            # behavior before that became a real option.
            kernel_strength = 1.0 + self.detail_quality * 2.0  # Range: 1.0 to 3.0
            base_kernel = _RELIEF_LIGHT_DIRECTIONS.get(self.relief_light_direction, _RELIEF_KERNEL_TOP_LEFT)
            emboss_kernel = base_kernel * kernel_strength

            # Apply emboss convolution at float depth, not ddepth=-1 (same
            # depth as the uint8 input) - this kernel's negative weights
            # push real edge responses well outside 0-255 (this exact
            # kernel at strength 1.0 against a clean 0->200 step edge
            # measured raw responses up to 800, verified live), and
            # ddepth=-1 saturates/clips DURING the convolution itself,
            # before the +128 recentering below ever sees the value. That
            # silently destroyed the negative (shadow) side of the effect:
            # a response that should end up well below 128 after
            # recentering was already clamped to 0 by filter2D first, so
            # 0 + 128 = 128 (flat neutral gray) instead of a real shadow.
            # Computing at CV_32F and only clipping once, after the +128
            # offset, preserves the actual (possibly large) signed
            # response so highlights and shadows both render correctly.
            embossed = cv2.filter2D(rgb_gray, cv2.CV_32F, emboss_kernel)

            # Add gray offset to center around 128 - creates the
            # highlight/shadow effect for 3D appearance
            embossed += 128.0  # Center at mid-gray
            np.clip(embossed, 0, 255, out=embossed)
            embossed = embossed.astype(np.uint8)

            # Convert embossed grayscale to BGR for blending
            embossed_bgr = cv2.cvtColor(embossed, cv2.COLOR_GRAY2BGR)

            # Blend embossed details onto thermal
            # Use fusion_intensity and detail_strength to control how strong the embossing appears
            blend_strength = self.fusion_intensity * self.detail_strength
            result = cv2.addWeighted(
                thermal, 1.0 - blend_strength * 0.5,  # Thermal base
                embossed_bgr, blend_strength * 0.5,     # Strength-controlled embossed structure
                0
            )

            return result

        except Exception as e:
            logger.error(f"Relief Fusion error: {e}")
            return thermal

    def _edge_enhanced(self, thermal: np.ndarray, rgb: np.ndarray) -> np.ndarray:
        """
        Edge-enhanced fusion with priority control
        Extracts edges from one source and overlays on the other
        Uses configurable edge colors, strength, fuzziness, and line size.
        Opt-in extras (all default off - see their own attribute
        docstrings in __init__): adaptive_canny_enabled, edge_direction,
        sobel_alpha_enabled, edge_color_mode='palette'.

        detail_balance > 0 opts into multi-scale cross-scale consensus
        filtering instead of the default single-scale Canny/Sobel pass -
        see _detect_edges_multiscale and detail_balance's own __init__
        docstring for why this lives here as a parameter of one mode
        rather than as a separate "Enhanced Edge Highlight" mode (merged
        2026-09-07, after two rounds of trying to make that separate mode
        read as genuinely distinct from this one on real camera footage).

        Args:
            thermal: Thermal frame (BGR)
            rgb: RGB frame (BGR, aligned)

        Returns:
            Edge-enhanced frame
        """
        try:
            if self.fusion_priority == 'rgb':
                # RGB base + thermal edges
                base = rgb
                edge_source_gray = cv2.cvtColor(thermal, cv2.COLOR_BGR2GRAY)
                edge_color = self.rgb_priority_edge_color
            else:
                # Thermal base + RGB edges (inverted priority)
                base = thermal
                edge_source_gray = cv2.cvtColor(rgb, cv2.COLOR_BGR2GRAY)
                edge_color = self.thermal_priority_edge_color

            # Extract edges (Canny, or directional Sobel if edge_direction
            # != 'all') at either fixed or adaptive thresholds. Multi-scale
            # consensus filtering (detail_balance > 0) replaces the single
            # Canny/Sobel pass with 3-scale cross-scale corroboration - see
            # _detect_edges_multiscale's own docstring.
            threshold_low, threshold_high = self._get_canny_thresholds(edge_source_gray)
            if self.detail_balance > 0:
                edges = self._detect_edges_multiscale(edge_source_gray, threshold_low, threshold_high)
            else:
                edges = self._detect_edges(edge_source_gray, threshold_low, threshold_high)

            # Line thickness - previously this mode had no thickness
            # control at all, Canny's inherently thin (~1px) lines were
            # the only option. Dilate before the blur/alpha steps below so
            # a thickened line still gets the same soft-edge blur
            # treatment as a thin one, not a separately-blurred thick
            # outline. Applies uniformly whether edges came from the
            # single-scale or multi-scale (detail_balance > 0) path above.
            dilation_size = 1 + int(round(self.edge_line_size * 4))
            if dilation_size > 1:
                edges = cv2.dilate(edges, self._get_dilation_kernel(dilation_size), iterations=1)

            # Apply Gaussian blur to edges if configured (for softer edge appearance)
            # This creates smooth gradients around edges instead of sharp lines
            if self.edge_blur_kernel > 0:
                edges_before_blur = edges
                edges = cv2.GaussianBlur(edges,
                                        (self.edge_blur_kernel, self.edge_blur_kernel),
                                        0)
                # Live-reported: "the line opacity is too low with the
                # current settings." Root cause, confirmed by direct
                # measurement: GaussianBlur conserves the mask's total
                # energy, not its peak - blurring a THIN line (a small
                # edge_line_size, dilated only a little above) with a wide
                # kernel spreads that energy out, measurably capping the
                # achievable peak well below 255 regardless of Strength or
                # Sensitivity. At this app's own reported settings
                # (dilation=2px, a mid-range Fuzziness kernel of 9) the
                # peak was capped at 43.5% BEFORE any further scaling -
                # confirmed directly, not assumed.
                #
                # First attempt (linear peak rescale, edges *= 255/peak)
                # fixed the ceiling but was reported the same day as
                # making lines look thicker - confirmed why by direct
                # measurement: rescaling every pixel by the same factor
                # also brightens the whole low-amplitude tail of the
                # falloff, so pixels that used to be too dim to notice
                # (say 20/255) now cross into clearly-visible territory -
                # the visible width at every threshold measurably grew
                # (e.g. >20/255: 6px -> 8px on a 2px-thick test line).
                # Restoring the peak by taking the max with the PRE-blur
                # mask instead only lifts the pixels that were already
                # part of the solid line before blurring (where the
                # pre-blur mask is 255 and blur alone under-reports it) -
                # every other pixel in the soft halo keeps its original
                # blurred value untouched, so the falloff's own width is
                # bit-for-bit unchanged (confirmed: identical visible
                # width at every threshold, before and after). This
                # decouples "how soft the falloff looks" (still gets
                # wider with a larger Fuzziness kernel, unchanged) from
                # "what opacity a confident edge can reach" (now full
                # scale), the same way edge_line_size was decoupled from
                # fusion_intensity earlier this session.
                np.maximum(edges, edges_before_blur, out=edges)

            # Normalize edges to 0.0-1.0 for alpha blending. sobel_alpha_
            # enabled replaces the flat per-pixel value every edge pixel
            # would otherwise get with one scaled by that pixel's own
            # Sobel gradient magnitude - a strong edge renders more
            # opaque than a faint one, instead of every edge pixel (from
            # a hard Canny/directional threshold) getting the identical
            # opacity regardless of how strong it actually is.
            if self.sobel_alpha_enabled:
                edges_normalized = self._sobel_alpha_within_mask(edge_source_gray, edges)
            else:
                edges_normalized = edges.astype(np.float32) / 255.0
            edges_normalized *= self.fusion_intensity

            # Lerp (base + alpha*(color-base)) evaluated ONLY at pixels whose
            # alpha is nonzero. Everywhere else the float math reduces to
            # base + 0*(color-base) == base exactly, so those pixels are just
            # copied from base. Edge masks (even dilated and blurred) cover a
            # small fraction of the frame, and this blend used to run over
            # the whole (H,W,3) frame in float32 at ~6.6ms on 640x512 (the
            # largest cost in this mode). The per-pixel float32 operations
            # are the same ones, in the same order, as the old full-frame
            # version, so the output is bit-identical to it (verified).
            result = base.copy()
            alpha_flat = edges_normalized.reshape(-1)
            nz = np.flatnonzero(alpha_flat)
            if nz.size:
                result_px = result.reshape(-1, 3)
                a = alpha_flat[nz][:, np.newaxis]
                base_f = result_px[nz].astype(np.float32)
                if self.edge_color_mode == 'palette' and self.palette_lut is not None:
                    # Per-pixel palette color at each edge pixel's own gray value.
                    color = self.palette_lut[edge_source_gray.reshape(-1)[nz]].astype(np.float32)
                else:
                    color = np.asarray(edge_color, dtype=np.float32)[np.newaxis, :]
                diff = np.subtract(color, base_f)   # color - base
                diff *= a                            # alpha * (color - base)
                base_f += diff                       # base + alpha * (color - base)
                result_px[nz] = np.clip(base_f, 0, 255).astype(np.uint8)

            return result

        except Exception as e:
            logger.error(f"Edge enhanced error: {e}")
            return self._alpha_blend(thermal, rgb)

    def _get_dilation_kernel(self, size: int) -> np.ndarray:
        """
        Cached square dilation kernel for edge_line_size, used by
        _edge_enhanced (single- and multi-scale paths alike). Only 5 distinct sizes
        (1-5px) are ever requested (edge_line_size is clamped 0.0-1.0), so
        the cache never grows past a handful of tiny (<=5x5) arrays -
        cheaper than calling cv2.getStructuringElement() fresh every frame.
        """
        cache = getattr(self, '_dilation_kernel_cache', None)
        if cache is None:
            cache = {}
            self._dilation_kernel_cache = cache
        kernel = cache.get(size)
        if kernel is None:
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (size, size))
            cache[size] = kernel
        return kernel

    def _thermal_overlay(self, thermal: np.ndarray, rgb: np.ndarray) -> np.ndarray:
        """
        Overlay hotspots on base with priority control
        Priority determines which is base and which is overlay. What counts
        as "hot"/"bright" enough to overlay is overlay_hot_percentile
        (default 70th percentile of the overlay source's own frame) -
        previously a hardcoded 70 with no way to tune it per scene.

        Args:
            thermal: Thermal frame (BGR)
            rgb: RGB frame (BGR, aligned)

        Returns:
            Overlaid frame
        """
        try:
            # This is the DEFAULT fusion mode (fusion_priority defaults to
            # 'thermal', and this is what nearly every live session this
            # whole project has run in FUSION view) - profiled at
            # mean=20.4ms/call with wild variance (6.8-40ms!) even after an
            # earlier fix already moved it off boolean-mask fancy indexing
            # and onto np.repeat+np.where. That variance is allocator churn:
            # np.repeat allocates a full (H,W,3) bool array, np.where then
            # allocates the full result array, every single call. cv2.copyTo
            # with a single-channel uint8 mask does the same "blended where
            # mask, else base" select as one optimized in-place C op - no
            # repeat, no second full-array allocation for the select itself
            # (just the one unavoidable copy to seed the base case). Verified
            # bit-identical against the previous implementation; measured
            # mean=9.3ms (less than half), max=17.2ms (well under half).
            if self.fusion_priority == 'rgb':
                # RGB base + thermal hotspots overlay (use intensity)
                thermal_gray = cv2.cvtColor(thermal, cv2.COLOR_BGR2GRAY)
                threshold = np.percentile(thermal_gray, self.overlay_hot_percentile)
                hot_mask = (thermal_gray > threshold).astype(np.uint8) * 255

                blended = cv2.addWeighted(thermal, self.fusion_intensity, rgb, 1.0 - self.fusion_intensity, 0)
                result = rgb.copy()
                cv2.copyTo(blended, hot_mask, result)
            else:
                # Thermal base + RGB highlights overlay (use intensity)
                rgb_gray = cv2.cvtColor(rgb, cv2.COLOR_BGR2GRAY)
                threshold = np.percentile(rgb_gray, self.overlay_hot_percentile)
                bright_mask = (rgb_gray > threshold).astype(np.uint8) * 255

                blended = cv2.addWeighted(rgb, self.fusion_intensity, thermal, 1.0 - self.fusion_intensity, 0)
                result = thermal.copy()
                cv2.copyTo(blended, bright_mask, result)

            return result

        except Exception as e:
            logger.error(f"Thermal overlay error: {e}")
            return self._alpha_blend(thermal, rgb)

    def _side_by_side(self, thermal: np.ndarray, rgb: np.ndarray) -> np.ndarray:
        """
        Concatenate thermal and RGB horizontally with priority control
        Priority determines left/right order

        Args:
            thermal: Thermal frame (BGR)
            rgb: RGB frame (BGR, aligned)

        Returns:
            Concatenated frame
        """
        try:
            # Ensure same height
            h = thermal.shape[0]
            if rgb.shape[0] != h:
                rgb = cv2.resize(rgb, (rgb.shape[1], h))

            # Concatenate horizontally (priority determines order)
            if self.fusion_priority == 'thermal':
                return np.hstack([thermal, rgb])  # Thermal on left
            else:
                return np.hstack([rgb, thermal])  # RGB on left

        except Exception as e:
            logger.error(f"Side-by-side error: {e}")
            return thermal

    def _picture_in_picture(self, thermal: np.ndarray, rgb: np.ndarray,
                            pip_size: float = 0.25, position: str = 'top-right') -> np.ndarray:
        """
        Picture-in-picture with priority control
        Priority determines which is main and which is inset

        Args:
            thermal: Thermal frame (BGR)
            rgb: RGB frame (BGR, aligned)
            pip_size: Size of inset as fraction of main frame (0.0-1.0)
            position: 'top-right', 'top-left', 'bottom-right', 'bottom-left'

        Returns:
            Picture-in-picture frame
        """
        try:
            # Priority determines main vs inset
            if self.fusion_priority == 'thermal':
                main = thermal.copy()
                inset = rgb
            else:
                main = rgb.copy()
                inset = thermal

            # If the inset has more pixels than its slot on the main frame (e.g. a 640x480
            # RGB inset on a 320x256 thermal canvas), composing at main's native size throws
            # that detail away - the inset is shrunk to ~80x64 - and the display then enlarges
            # the whole result again, so it looks tiny and soft. Upscale main once, up front
            # (capped at 1280 wide to bound per-frame cost) so the inset keeps its detail.
            # Anything recording this frame conforms to its writer's size (MediaRecorder._conform).
            main_h, main_w = main.shape[:2]
            slot_w = main_w * pip_size
            if slot_w > 0:
                scale = max(1.0, min(inset.shape[1] / slot_w, 1280.0 / main_w))
                if scale > 1.05:
                    main = cv2.resize(main, (int(main_w * scale), int(main_h * scale)),
                                      interpolation=cv2.INTER_CUBIC)

            # Calculate allocated inset dimensions
            main_h, main_w = main.shape[:2]
            allocated_w = int(main_w * pip_size)
            allocated_h = int(main_h * pip_size)

            # CRITICAL FIX: Maintain aspect ratio when resizing inset
            # This matches the pip_thermal_rect calculation in inspection_gui_qt.py
            inset_h, inset_w = inset.shape[:2]
            inset_aspect = inset_w / inset_h
            allocated_aspect = allocated_w / allocated_h

            logger.debug(f"[FUSION PIP] Inset: {inset_w}x{inset_h} (aspect {inset_aspect:.3f}), Allocated: {allocated_w}x{allocated_h} (aspect {allocated_aspect:.3f})")

            if inset_aspect > allocated_aspect:
                # Inset is wider, fit to width
                actual_w = allocated_w
                actual_h = int(allocated_w / inset_aspect)
                offset_x = 0
                offset_y = (allocated_h - actual_h) // 2
            else:
                # Inset is taller, fit to height
                actual_h = allocated_h
                actual_w = int(allocated_h * inset_aspect)
                offset_x = (allocated_w - actual_w) // 2
                offset_y = 0

            logger.debug(f"[FUSION PIP] Actual size: {actual_w}x{actual_h}, Offset: ({offset_x}, {offset_y})")

            # Resize inset maintaining aspect ratio
            inset_resized = cv2.resize(inset, (actual_w, actual_h), interpolation=cv2.INTER_AREA)

            # Determine position for allocated space
            margin = 10
            if position == 'top-right':
                x, y = main_w - allocated_w - margin, margin
            elif position == 'top-left':
                x, y = margin, margin
            elif position == 'bottom-right':
                x, y = main_w - allocated_w - margin, main_h - allocated_h - margin
            else:  # bottom-left
                x, y = margin, main_h - allocated_h - margin

            # Add border to inset
            inset_with_border = cv2.copyMakeBorder(
                inset_resized, 2, 2, 2, 2,
                cv2.BORDER_CONSTANT, value=[255, 255, 255]
            )

            # Overlay inset on main at aspect-ratio-corrected position.
            # Clamped rather than sliced unconditionally: if rounding in
            # the aspect-ratio math above ever placed the inset (plus its
            # 2px border) past main's own edge, a numpy slice silently
            # truncates the DESTINATION but not the (still full-size)
            # SOURCE array, which raises "could not broadcast input array"
            # - previously caught by this function's own blanket except
            # and silently downgraded to _side_by_side, with no
            # indication PIP itself had a geometry problem. Clamping the
            # placement keeps PIP actually rendering instead of silently
            # swapping modes.
            ih, iw = inset_with_border.shape[:2]
            if ih > main_h or iw > main_w:
                # pip_size close enough to 1.0 that even the aspect-fit
                # inset plus its border doesn't fit at all - crop the
                # border image itself rather than attempting a paste that
                # can't succeed at any offset.
                inset_with_border = inset_with_border[:main_h, :main_w]
                ih, iw = inset_with_border.shape[:2]
            paste_y = max(0, min(y + offset_y, main_h - ih))
            paste_x = max(0, min(x + offset_x, main_w - iw))
            main[paste_y:paste_y+ih, paste_x:paste_x+iw] = inset_with_border

            return main

        except Exception as e:
            logger.error(f"Picture-in-picture error: {e}")
            return self._side_by_side(thermal, rgb)

    def _max_intensity(self, thermal: np.ndarray, rgb: np.ndarray) -> np.ndarray:
        """
        Take maximum intensity from thermal and RGB at each pixel
        Preserves brightest features from both sources

        Args:
            thermal: Thermal frame (BGR)
            rgb: RGB frame (BGR, aligned)

        Returns:
            Max intensity frame
        """
        try:
            return cv2.max(thermal, rgb)
        except Exception as e:
            logger.error(f"Max intensity error: {e}")
            return self._alpha_blend(thermal, rgb)

    def _feature_weighted(self, thermal: np.ndarray, rgb: np.ndarray) -> np.ndarray:
        """
        Adaptive fusion based on edge strength with priority bias -
        dispatches to the GPU (torch/CUDA) path when available and
        enabled, else the CPU path. See _feature_weighted_gpu/_cpu for
        details. Same dispatch/fallback pattern as _laplacian_pyramid.
        """
        if self._resolve_feature_weighted_gpu():
            try:
                return self._feature_weighted_gpu(thermal, rgb)
            except Exception as e:
                logger.error(f"feature_weighted GPU path failed, falling back to CPU: {e}")
                self._fw_gpu_ready = False  # don't retry a broken GPU path every frame

        return self._feature_weighted_cpu(thermal, rgb)

    def _resolve_feature_weighted_gpu(self) -> bool:
        """
        Determine whether a torch GPU path (CUDA, or DirectML on
        Intel/AMD - see utils/gpu_device.py) for feature_weighted should
        be used right now, resolving the device and preparing the cached
        Sobel(dx=1,dy=1,ksize=3) kernel on first use. Returns False
        (falls back to CPU) if torch isn't installed, no GPU matching
        the requested device is available, GPU use is disabled
        (set_feature_weighted_gpu_enabled(False)), or preparing the
        device fails for any reason - never raises. Mirrors
        _resolve_laplacian_gpu exactly.
        """
        global _TORCH_GPU_UNAVAILABLE
        if (not self.feature_weighted_use_gpu or not _TORCH_SPEC_AVAILABLE
                or _TORCH_GPU_UNAVAILABLE):
            return False

        if self._fw_gpu_ready and self._fw_torch_device is not None:
            return True

        if self._fw_device_requested == "cpu":
            return False

        try:
            import torch
            from thermal_inspection.utils.gpu_device import resolve_torch_gpu_device

            device, device_name = resolve_torch_gpu_device(self._fw_device_requested, "feature_weighted")
            if device is None:
                _TORCH_GPU_UNAVAILABLE = True
                return False

            self._fw_torch_device = device
            # Sobel(dx=1, dy=1, ksize=3)'s exact separable kernel - verified
            # bit-identical to cv2.getDerivKernels(1, 1, 3): kx=ky=[-1,0,1],
            # full 2D kernel = outer(ky, kx). This is a genuinely different
            # (and less common) operator than the usual gradient-magnitude
            # Sobel_x/Sobel_y pair - both derivative orders are 1, not one
            # derivative order paired with the orthogonal smoothing kernel.
            self._fw_sobel_kernel = torch.tensor(
                [[1., 0., -1.], [0., 0., 0.], [-1., 0., 1.]], device=device
            ).view(1, 1, 3, 3)
            self._fw_gpu_ready = True
            logger.info(f"feature_weighted: GPU acceleration active ({device_name})")
            return True
        except Exception as e:
            _TORCH_GPU_UNAVAILABLE = True
            logger.warning(
                f"feature_weighted: failed to initialize GPU path, falling back "
                f"to CPU (will not retry this process): {e}"
            )
            self._fw_gpu_ready = False
            self._fw_torch_device = None
            return False

    def _feature_weighted_gpu(self, thermal: np.ndarray, rgb: np.ndarray) -> np.ndarray:
        """
        GPU (torch/CUDA) implementation of _feature_weighted_cpu's exact
        algorithm - see its docstring. cv2's BGR2GRAY luma weights and
        F.pad(mode='reflect')'s border handling both match their CPU
        equivalents exactly, but conv2d vs cv2.Sobel's internal
        accumulation order differs at the floating-point rounding level
        (same class of difference as laplacian_pyramid's GPU path) -
        harmless on its own, but the original ratio-based weight formula
        amplified it into large visible differences at pixels where
        thermal/RGB edge strength were nearly equal (~5% of pixels, mean
        3.7/255, some 100+/255 on a realistic test scene). The sigmoid
        formula (_FEATURE_WEIGHTED_SIGMOID_K) fixes that at the source -
        verified 0 pixels beyond a 20/255 difference, mean <1/255, on the
        same scene.
        """
        import torch

        device = self._fw_torch_device

        def to_tensor(img):
            t = torch.from_numpy(img).to(device).float()
            return t.permute(2, 0, 1).unsqueeze(0)  # (1, 3, H, W), BGR

        thermal_t = to_tensor(thermal)
        rgb_t = to_tensor(rgb)
        result_t = self._feature_weighted_gpu_tensor(thermal_t, rgb_t)
        return result_t.squeeze(0).permute(1, 2, 0).contiguous().to(torch.uint8).cpu().numpy()

    def _feature_weighted_gpu_tensor(self, thermal_t, rgb_t):
        """
        All-tensor core of _feature_weighted_gpu - takes and returns
        (1,3,H,W) float32 GPU tensors (BGR, 0-255 range), no upload/
        download. Exists so a caller chaining straight into another
        GPU stage (see app.py's THREE_D dispatch, which used to call
        this via the CPU-facing wrapper, download to numpy, then
        immediately re-upload that same array into apply_3d_visualization)
        can stay GPU-resident instead of paying two full round trips for
        one logical operation - measured transfer cost (upload+download)
        as ~11x the actual compute cost on this hardware at 1280x800, so
        that second round trip was pure waste, not algorithmic work.
        """
        import torch
        import torch.nn.functional as F

        kernel = self._fw_sobel_kernel

        def to_gray(t):
            # Standard BGR2GRAY luma weights, matches cv2.cvtColor's convention.
            return 0.114 * t[:, 0:1] + 0.587 * t[:, 1:2] + 0.299 * t[:, 2:3]

        def sobel_dxdy(gray):
            padded = F.pad(gray, (1, 1, 1, 1), mode='reflect')
            return F.conv2d(padded, kernel)

        thermal_strength = sobel_dxdy(to_gray(thermal_t)).abs()
        rgb_strength = sobel_dxdy(to_gray(rgb_t)).abs()

        thermal_strength = thermal_strength / (thermal_strength.max() + 1e-6)
        rgb_strength = rgb_strength / (rgb_strength.max() + 1e-6)

        bias_multiplier = 1.0 + self.fusion_intensity
        if self.fusion_priority == 'thermal':
            thermal_strength = thermal_strength * bias_multiplier
        else:
            rgb_strength = rgb_strength * bias_multiplier

        # Sigmoid of the strength difference, not a raw ratio - see
        # _FEATURE_WEIGHTED_SIGMOID_K's module-level comment for why.
        thermal_weight = torch.sigmoid(
            _FEATURE_WEIGHTED_SIGMOID_K * (thermal_strength - rgb_strength)
        )  # (1, 1, H, W)

        diff = thermal_t - rgb_t                     # (1, 3, H, W)
        result = rgb_t + thermal_weight * diff        # broadcast (1,1,H,W) against (1,3,H,W)
        return torch.clamp(result, 0, 255)

    def _feature_weighted_cpu(self, thermal: np.ndarray, rgb: np.ndarray) -> np.ndarray:
        """
        Adaptive fusion based on edge strength with priority bias
        Priority adds bias toward thermal or RGB features

        Args:
            thermal: Thermal frame (BGR)
            rgb: RGB frame (BGR, aligned)

        Returns:
            Adaptively blended frame
        """
        try:
            # Convert to grayscale
            thermal_gray = cv2.cvtColor(thermal, cv2.COLOR_BGR2GRAY)
            rgb_gray = cv2.cvtColor(rgb, cv2.COLOR_BGR2GRAY)

            # Calculate edge strength at full resolution. (A downscale-then-
            # upsample shortcut was tried here for speed, but blurring the
            # per-pixel edge-strength weight map measurably softened this
            # mode's actual thermal/RGB detail - reverted; this weight map
            # directly controls how much of each source's fine detail shows
            # through, so it isn't a "just visualization" value that can be
            # freely blurred.)
            # CV_32F, not CV_64F - this is a visualization blend weight, not
            # a precision-sensitive calculation, and float64 doubled the
            # memory traffic through every step below (abs, normalize,
            # weight, blend) for no benefit. Measured at ~40-50ms/frame on a
            # 640x512 frame with CV_64F - by far the most expensive fusion
            # mode.
            thermal_strength = cv2.Sobel(thermal_gray, cv2.CV_32F, 1, 1, ksize=3)
            rgb_strength = cv2.Sobel(rgb_gray, cv2.CV_32F, 1, 1, ksize=3)
            np.abs(thermal_strength, out=thermal_strength)
            np.abs(rgb_strength, out=rgb_strength)

            # Normalize to [0, 1] (in-place - these buffers aren't needed
            # in their pre-normalized form again)
            thermal_strength /= (thermal_strength.max() + 1e-6)
            rgb_strength /= (rgb_strength.max() + 1e-6)

            # Apply priority bias (boost preferred source using intensity)
            # intensity controls bias strength: 0.0 = no bias, 1.0 = double strength
            bias_multiplier = 1.0 + self.fusion_intensity
            if self.fusion_priority == 'thermal':
                thermal_strength *= bias_multiplier
            else:
                rgb_strength *= bias_multiplier

            # Compute adaptive weight via a sigmoid of the strength
            # difference, not a raw ratio - see _FEATURE_WEIGHTED_SIGMOID_K's
            # module-level comment for why. Reuses thermal_strength as the
            # buffer throughout (diff -> scaled -> sigmoid), no new (H,W)
            # array needed.
            thermal_strength -= rgb_strength                    # now holds (ts - rs)
            thermal_strength *= _FEATURE_WEIGHTED_SIGMOID_K      # now holds K*(ts - rs)
            np.negative(thermal_strength, out=thermal_strength)  # now holds -K*(ts - rs)
            np.exp(thermal_strength, out=thermal_strength)       # now holds exp(-K*(ts - rs))
            thermal_strength += 1.0                              # now holds 1 + exp(-K*(ts - rs))
            np.reciprocal(thermal_strength, out=thermal_strength)  # now holds sigmoid(K*(ts - rs)) = thermal_weight

            # On this hardware these blends are memory-bandwidth-bound, not
            # compute-bound (confirmed via isolated benchmark: a bare
            # 1M-element float32 add costs ~1.3ms even with nothing else
            # running), so the lever is cutting full-frame temporaries, not
            # swapping numpy for cv2 - measured no faster at this size, both
            # bandwidth-bound. A (H,W,1) weight broadcasting against (H,W,3)
            # is its own separate slow path (stride-0 axis + mixed uint8/
            # float32 multiply misses numpy's SIMD ufunc loop) - repeating
            # to a real (H,W,3) array avoids that specific slow path, but
            # still pays for allocating and filling a whole extra (H,W,3)
            # array that's only ever used once. Multiplying each of diff's
            # 3 channels by the plain (H,W) weight directly - 3 contiguous
            # 2D*2D multiplies, no (H,W,1) broadcast and no (H,W,3) repeat -
            # is neither slow path: measured ~36% faster overall (14.7ms ->
            # 9.4ms mean) and bit-identical, since it's the same arithmetic
            # either way.
            # uint8->float32 casts happen inside the subtract/add loops
            # (dtype=) instead of via two separate full-frame astype()
            # copies - exact casts, and float add is commutative, so this
            # is bit-identical to astype-then-subtract/add (verified).
            diff = np.subtract(thermal, rgb, dtype=np.float32)   # thermal - rgb
            diff[:, :, 0] *= thermal_strength
            diff[:, :, 1] *= thermal_strength
            diff[:, :, 2] *= thermal_strength       # diff now holds weight * (thermal - rgb)
            np.add(diff, rgb, out=diff, dtype=np.float32)  # rgb + weight * (thermal - rgb)
            np.clip(diff, 0, 255, out=diff)
            result = diff.astype(np.uint8)

            return result

        except Exception as e:
            logger.error(f"Feature weighted error: {e}")
            return self._alpha_blend(thermal, rgb)

    def _thermal_contours(self, thermal: np.ndarray, rgb: np.ndarray,
                           temperature_map_c: Optional[np.ndarray] = None,
                           temp_map_is_estimated: bool = False) -> np.ndarray:
        """
        Thermal Contours on RGB - Phase 3 Feature 12
        Overlays thermal contour lines on RGB image to show temperature boundaries.

        Args:
            thermal: Thermal frame (BGR, colorized)
            rgb: RGB frame (BGR, aligned)
            temperature_map_c: See process()'s own docstring - optional
                float32 Celsius map for contour_labels_enabled.
            temp_map_is_estimated: See process()'s own docstring.

        Returns:
            RGB frame with thermal contour overlay
        """
        try:
            # Start with RGB as base
            result = rgb.copy()

            # Bounding boxes of labels already placed this frame (x1, y1,
            # x2, y2), oldest (coolest level) first - _place_contour_label
            # nudges a new label away from any of these instead of letting
            # labels stack on top of each other.
            placed_label_boxes = []

            # Convert thermal to grayscale for contour detection
            thermal_gray = cv2.cvtColor(thermal, cv2.COLOR_BGR2GRAY)

            # A thermal sensor's per-pixel read noise, thresholded directly
            # at 8 levels, produces a "salt and pepper" binary pattern with
            # an enormous number of tiny disconnected contours -
            # cv2.findContours' cost scales with contour count and boundary
            # complexity, not just pixel count. Measured live: pure noise
            # cost ~950ms for findContours alone (216k contours found) at
            # 512x640 - effectively freezing the app if this mode were
            # selected on a noisy scene. A light blur removes single-pixel
            # noise before thresholding while preserving genuine
            # temperature-boundary edges (this mode's actual purpose per
            # its own docstring) - measured: realistic thermal-like data
            # (smooth gradient + moderate sensor noise) drops to ~17ms,
            # matching every other fusion mode.
            thermal_gray = cv2.GaussianBlur(thermal_gray, (5, 5), 0)

            # Label each contour with its real temperature, sampled
            # empirically from temperature_map_c at pixels near this
            # level's own gray value - not derived from an assumed
            # gray-to-temperature formula, which would silently break if
            # the colorization curve isn't linear. Only ever runs when the
            # caller actually provided a map; a shape mismatch (would
            # otherwise misalign labels to the wrong pixels) disables
            # labels for this call rather than guessing.
            can_label = (
                self.contour_labels_enabled
                and temperature_map_c is not None
                and temperature_map_c.shape[:2] == thermal_gray.shape[:2]
            )

            line_thickness = 1 + int(round(self.contour_line_size * 3))
            num_levels = self.contour_level_count
            if self.palette_lut is not None:
                # Sample the active palette at each level's own gray value,
                # not a fixed 0-7 index spacing - a level near t_max should
                # get the palette's hot-end color regardless of where in
                # 0-255 that level actually falls, matching how the
                # colorized thermal image underneath is itself colored.
                contour_colors = None  # computed per-level below
            else:
                # No palette set (set_palette_lut() never called, or
                # explicitly reset to None) - previous fixed rainbow,
                # unrelated to any actual palette. Kept as the fallback so
                # behavior is unchanged for any caller that never wires
                # set_palette_lut() up.
                contour_colors = [
                    (0, 0, 255),      # Red (hottest)
                    (0, 128, 255),    # Orange
                    (0, 255, 255),    # Yellow
                    (0, 255, 128),    # Yellow-green
                    (0, 255, 0),      # Green
                    (128, 255, 0),    # Cyan-green
                    (255, 255, 0),    # Cyan
                    (255, 0, 0)       # Blue (coolest)
                ]

            # Find min and max values (as Python ints, not numpy uint8
            # scalars - (t_max - t_min) * (i + 1) below can exceed 255 and
            # silently overflow/wrap if left in uint8 arithmetic)
            t_min = int(thermal_gray.min())
            t_max = int(thermal_gray.max())

            if t_max - t_min < 10:
                # Not enough temperature variation
                return result

            # Draw contours for each level
            for i in range(num_levels):
                threshold_val = t_min + (t_max - t_min) * (i + 1) / (num_levels + 1)
                _, thresh = cv2.threshold(thermal_gray, threshold_val, 255, cv2.THRESH_BINARY)

                # Find contours
                contours, _ = cv2.findContours(thresh, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)

                # Remaining single-pixel-scale noise specks the blur above
                # didn't fully remove draw as invisible-at-2px-linewidth
                # dots anyway - skipping them cuts drawContours' cost
                # further on a noisy frame with no visual difference.
                contours = [c for c in contours if cv2.contourArea(c) >= _THERMAL_CONTOURS_MIN_AREA]

                # Draw contours
                if contour_colors is not None:
                    color = contour_colors[i % len(contour_colors)]
                else:
                    # threshold_val is already this level's gray value (0-255)
                    # in the same space the palette LUT is indexed by.
                    b, g, r = self.palette_lut[int(round(threshold_val)) & 255]
                    color = (int(b), int(g), int(r))

                # Optional translucent fill, highlighting this isotherm's
                # own region - drawn BEFORE the line so the line stays
                # crisp on top. `thresh` (gray >= threshold_val) nests
                # inside every cooler level's own mask, so blending each
                # level's color in over the one before it naturally
                # accumulates into a graduated heat tint rather than one
                # flat wash - same cv2.copyTo masked-blend idiom already
                # used by _thermal_overlay.
                #
                # Live-reported as slow: the first version ran this at
                # FULL FRAME size on every one of up to 12 levels -
                # np.full((H,W,3)) allocated and filled a whole fresh
                # frame-sized array, then cv2.addWeighted blended another
                # full frame, even though most levels (everything above
                # the coolest one or two) only actually cover a small
                # fraction of the frame. Measured directly: ~23ms/frame
                # added at 640x512/8 levels (6.1ms fill-off -> 29.2ms
                # fill-on), enough on its own to cap this mode under
                # 35fps. Cropping to this level's own contours' bounding
                # box confines both the allocation and the blend to the
                # area that can actually change - a no-op for the
                # near-full-frame coolest level, a real win for every
                # smaller one above it (measured on the same 8-level
                # scene's real bounding boxes, 100% down to 2.5% of the
                # frame by the hottest level: ~9.8ms full-frame vs.
                # ~6.9ms cropped for the 8 blends alone). A manual numpy
                # float32 blend (astype/multiply/add/clip/astype) was
                # tried first and measured SLOWER than keeping
                # cv2.addWeighted despite operating on fewer pixels
                # (~16.4ms) - numpy's per-op overhead across 5 separate
                # passes outweighs cv2's single fused call even at this
                # smaller size, so cv2.addWeighted stays, just now scoped
                # to the cropped ROI instead of the full frame. Skips
                # entirely when this level found no contours (nothing to
                # fill) rather than running an expensive blend against an
                # all-zero mask that cv2.copyTo would've discarded anyway.
                if self.contour_fill_enabled and contours:
                    bx, by, bw, bh = cv2.boundingRect(np.vstack(contours))
                    roi = result[by:by + bh, bx:bx + bw]
                    mask_roi = thresh[by:by + bh, bx:bx + bw]
                    # Same solid-color layer np.full((bh, bw, 3), color)
                    # builds, filled by broadcasting one precomputed BGR
                    # row - np.full's per-element tuple fill measured ~0.45ms
                    # per level (~3.5ms/frame at 8 levels), ~2.5x slower.
                    color_layer_roi = np.empty((bh, bw * 3), dtype=np.uint8)
                    color_layer_roi[:] = np.tile(np.asarray(color, dtype=np.uint8), bw)
                    color_layer_roi = color_layer_roi.reshape(bh, bw, 3)
                    blended_roi = cv2.addWeighted(roi, 0.85, color_layer_roi, 0.15, 0)
                    cv2.copyTo(blended_roi, mask_roi, roi)

                cv2.drawContours(result, contours, -1, color, line_thickness)

                if can_label and contours:
                    # Empirically sample the real temperature at pixels
                    # near this level's gray value from the CURRENT
                    # frame's own data, rather than assuming any fixed
                    # gray-to-temperature formula - correct regardless of
                    # whatever AGC/tone-mapping curve actually produced
                    # thermal_gray, since it measures the real
                    # correspondence directly instead of assuming one.
                    # |gray - level| <= 2 on integer gray values, as a single
                    # cv2.inRange pass rather than an int16 cast + subtract +
                    # abs + compare over the full frame for every level.
                    level = int(round(threshold_val))
                    near_level = cv2.inRange(thermal_gray, max(0, level - 2), min(255, level + 2)) != 0
                    if np.any(near_level):
                        real_c = float(np.median(temperature_map_c[near_level]))
                        label = self._format_contour_label(real_c, temp_map_is_estimated)
                        largest = max(contours, key=cv2.contourArea)
                        self._place_contour_label(result, label, largest, color, placed_label_boxes)

            # Optionally add semi-transparent thermal overlay
            if self.fusion_intensity > 0.3:
                # Add subtle thermal color overlay
                alpha = (self.fusion_intensity - 0.3) * 0.5  # Max 0.35 alpha
                result = cv2.addWeighted(result, 1.0 - alpha, thermal, alpha, 0)

            return result

        except Exception as e:
            logger.error(f"Thermal contours error: {e}")
            return rgb

    def _format_contour_label(self, temp_c: float, is_estimated: bool) -> str:
        """
        Format an isotherm label in contour_temp_unit ('C'/'F'/'K') -
        previously hardcoded to Celsius regardless of the app-wide
        temperature unit setting every other on-screen temperature
        (spot meters, ROI stats, the histogram) already respects. '~'
        prefix discloses the 8-bit-estimation path's lower accuracy
        rather than presenting an estimate as exact - unchanged from
        before, just now unit-aware too.
        """
        unit = self.contour_temp_unit
        if unit == 'F':
            value = temp_c * 9.0 / 5.0 + 32.0
        elif unit == 'K':
            value = temp_c + 273.15
        elif unit == 'RAW':
            value = (temp_c + 273.15) * 100.0
            unit = 'Y16'
        else:
            value = temp_c
            unit = 'C'
        prefix = '~' if is_estimated else ''
        return f"{prefix}{value:.0f}{unit}"

    @staticmethod
    def _boxes_overlap(a: Tuple[int, int, int, int], b: Tuple[int, int, int, int]) -> bool:
        ax1, ay1, ax2, ay2 = a
        bx1, by1, bx2, by2 = b
        return ax1 < bx2 and ax2 > bx1 and ay1 < by2 and ay2 > by1

    def _place_contour_label(self, result: np.ndarray, label: str, contour: np.ndarray,
                             color: Tuple[int, int, int], placed_boxes: list) -> None:
        """
        Anchor a level's label at the TOPMOST point of its own contour
        boundary, not the filled centroid cv2.moments gives - found live:
        for a single hot blob, every threshold level's contour is
        roughly concentric, so a centroid anchor puts nearly every
        level's label at almost the same point near the blob's peak, all
        stacked on top of each other and unreadable. The topmost
        boundary point differs meaningfully per level (each ring is a
        genuinely different size), giving real separation for free
        without tracking anything across levels.

        Beyond that: nudges a label vertically away from any
        already-placed label this frame if the natural position would
        still overlap one (placed_boxes accumulates across the calling
        loop's levels, coolest to hottest), clamps the final box inside
        the frame so text never renders partially off-canvas, and draws
        a dark outline pass before the real color so the label stays
        legible regardless of whatever's underneath it.
        """
        h, w = result.shape[:2]
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.5
        thickness = 1
        (text_w, text_h), baseline = cv2.getTextSize(label, font, font_scale, thickness)

        pts = contour.reshape(-1, 2)
        topmost_idx = int(np.argmin(pts[:, 1]))
        top_x, top_y = pts[topmost_idx]

        anchor_x = int(top_x) - text_w // 2
        anchor_y = int(top_y) - 6  # small margin above the boundary line itself

        step = text_h + 4
        box = (anchor_x, anchor_y - text_h, anchor_x + text_w, anchor_y + baseline)
        for _ in range(8):
            if not any(self._boxes_overlap(box, existing) for existing in placed_boxes):
                break
            anchor_y -= step
            box = (anchor_x, anchor_y - text_h, anchor_x + text_w, anchor_y + baseline)

        # Clamp so the text box never renders partially off-frame.
        x1, y1, x2, y2 = box
        dx = -x1 if x1 < 0 else (w - x2 if x2 > w else 0)
        dy = -y1 if y1 < 0 else (h - y2 if y2 > h else 0)
        anchor_x += dx
        anchor_y += dy
        box = (x1 + dx, y1 + dy, x2 + dx, y2 + dy)
        placed_boxes.append(box)

        cv2.putText(result, label, (anchor_x, anchor_y), font, font_scale, (0, 0, 0), thickness + 2, cv2.LINE_AA)
        cv2.putText(result, label, (anchor_x, anchor_y), font, font_scale, color, thickness, cv2.LINE_AA)

    def _detect_edges_multiscale(self, gray: np.ndarray, threshold_low: float, threshold_high: float) -> np.ndarray:
        """
        Multi-scale edge detection used as a cross-scale CONSENSUS FILTER,
        not just another detail layer: an edge only survives if the fine
        scale detects it AND enough of the 2 coarser scales corroborate it
        there too (see detail_balance's own __init__ docstring). This is
        deliberately the opposite of a single Canny pass - it suppresses
        fine-grained sensor/texture noise that only ever shows up at one
        scale, leaving just the structurally-significant boundaries.

        Formerly the whole of a separate "Enhanced Edge Highlight" mode;
        merged into _edge_enhanced as an opt-in detection strategy
        (2026-09-07) - see detail_balance's own docstring for why. Returns
        the same 0/255 single-channel mask shape as _detect_edges, so the
        caller's dilation/blur/alpha/color/blend steps are identical
        either way.

        Args:
            gray: Grayscale edge-detection source
            threshold_low: Canny low threshold (fine scale only - medium/
                large scale thresholds are derived from this, see below)
            threshold_high: Canny high threshold (fine scale)

        Returns:
            uint8 0/255 consensus-filtered edge mask
        """
        # Scale 1: Fine details, at the caller's own thresholds -
        # edge_direction (restrict to one gradient axis) only applies
        # here, via _detect_edges - the medium/large scales below already
        # use morphologyEx(GRADIENT) rather than Canny, so "restrict to
        # one axis" doesn't apply the same way there.
        edges_fine = self._detect_edges(gray, threshold_low, threshold_high)

        # Scales 2/3 (medium/large "broader structure" passes): this
        # used to run morphologyEx(GRADIENT) with a bigger kernel at
        # FULL resolution for each scale - correct in effect, but doing
        # 2 extra full-res morphology+Canny passes measured as a real
        # cost outlier (~20ms/frame vs ~1-11ms for every other fusion
        # mode - confirmed live during a stacked-settings sweep). An
        # image pyramid - analyze coarser scales on a DOWNSAMPLED image,
        # then scale the result back up - is the textbook way multi-scale
        # edge detection is actually done (Canny/Marr-Hildreth pyramids),
        # not just a speed hack: scale 2 does 1/4 the pixels, scale 3
        # does 1/16, cutting the dominant per-scale cost by roughly that
        # same factor before the (comparatively cheap) resize back up.
        # INTER_NEAREST, not INTER_LINEAR - edges_medium_small/
        # edges_large_small are BINARY (0/255) Canny output, and linearly
        # interpolating a binary image while upscaling necessarily
        # creates a blurred halo of faint intermediate values around
        # every detected pixel (verified live: this alone turned 328 real
        # fine-scale edge pixels into an 8758-pixel combined mask, most of
        # it well below 30/255 - pure interpolation artifact, not
        # anything actually detected at any scale). cv2.bitwise_and's
        # mask treats any nonzero value as "in", so that whole halo was
        # being drawn as if it were a real edge - independent of
        # edge_line_size/dilation entirely, this was why lines looked
        # thick even at the dilation kernel's minimum (1px, a no-op).
        # NEAREST preserves the blocky-but-clean 0/255 semantics
        # multi-scale detection actually calls for (a coarse-scale edge
        # legitimately covering a blocky region at full res is correct,
        # not a bug - only the anti-aliased halo was ever the problem).
        h, w = gray.shape[:2]
        medium_small = cv2.pyrDown(gray)
        gray_medium = cv2.morphologyEx(medium_small, cv2.MORPH_GRADIENT, _EDGE_KERNEL_MEDIUM)
        edges_medium_small = cv2.Canny(gray_medium, threshold_low * 0.7, threshold_high * 0.7)
        edges_medium = cv2.resize(edges_medium_small, (w, h), interpolation=cv2.INTER_NEAREST)

        large_small = cv2.pyrDown(medium_small)
        gray_large = cv2.morphologyEx(large_small, cv2.MORPH_GRADIENT, _EDGE_KERNEL_LARGE)
        edges_large_small = cv2.Canny(gray_large, threshold_low * 0.5, threshold_high * 0.5)
        edges_large = cv2.resize(edges_large_small, (w, h), interpolation=cv2.INTER_NEAREST)

        # Cross-scale consensus filter, not a blend: an edge only
        # survives here if the FINE scale detected it (the coarse scales
        # alone are too blocky/imprecise to place a line on their own -
        # see the INTER_NEAREST comment above) AND enough of the 2
        # coarser scales also detected something at that same location.
        # detail_balance sets how many coarse scales must agree: 0
        # requires none (fine scale alone is enough - most permissive,
        # equivalent to the single-scale path), 1 requires at least one
        # of medium/large to corroborate (real denoising - most
        # fine-scale sensor/texture noise isn't also picked up by a
        # heavily downsampled+blurred coarse pass), 2 requires both
        # (strictest - only edges visible at every scale survive). Three
        # tiers, not a continuous formula, because "how many of 2 scales
        # agree" is itself a 3-value quantity (0, 1, or 2) - a smooth
        # formula here would just be rounding to these same 3 outcomes
        # anyway.
        required_agreement = int(round(self.detail_balance * 2))
        fine_mask = edges_fine > 0
        agreement = (edges_medium > 0).astype(np.uint8) + (edges_large > 0).astype(np.uint8)
        edges = (fine_mask & (agreement >= required_agreement)).astype(np.uint8) * 255

        # Close small gaps left by the consensus filter dropping isolated
        # fine-scale pixels along an otherwise-corroborated line, so real
        # structural edges stay continuous rather than dashed.
        edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, _EDGE_KERNEL_CONNECT)
        return edges

    def _laplacian_pyramid(
        self, thermal: np.ndarray, rgb: np.ndarray, levels: int = 4
    ) -> np.ndarray:
        """
        Multi-scale Laplacian Pyramid blending - dispatches to the GPU
        (torch/CUDA) path when available and enabled, else the CPU path
        (optionally at reduced internal resolution - see
        laplacian_cpu_scale). See _laplacian_pyramid_gpu/_cpu for details.
        """
        if self._resolve_laplacian_gpu():
            try:
                return self._laplacian_pyramid_gpu(thermal, rgb, levels)
            except Exception as e:
                logger.error(f"laplacian_pyramid GPU path failed, falling back to CPU: {e}")
                self._laplacian_gpu_ready = False  # don't retry a broken GPU path every frame

        try:
            scale = self.laplacian_cpu_scale
            if scale >= 0.999:
                return self._laplacian_pyramid_cpu(thermal, rgb, levels)

            orig_h, orig_w = thermal.shape[:2]
            small_w = max(1, int(round(orig_w * scale)))
            small_h = max(1, int(round(orig_h * scale)))
            thermal_small = cv2.resize(thermal, (small_w, small_h), interpolation=cv2.INTER_AREA)
            rgb_small = cv2.resize(rgb, (small_w, small_h), interpolation=cv2.INTER_AREA)
            result_small = self._laplacian_pyramid_cpu(thermal_small, rgb_small, levels)
            return cv2.resize(result_small, (orig_w, orig_h), interpolation=cv2.INTER_LINEAR)
        except Exception as e:
            # Every other fusion mode degrades gracefully on its own (see
            # _max_intensity/_feature_weighted's own try/except) instead of
            # letting a bad frame propagate up to _process_frame_loop's
            # blanket handler, which drops the ENTIRE tick (every overlay,
            # stat, and recording write for that frame) rather than just
            # this one mode's output. pyrDown/pyrUp are robust at any
            # normal camera resolution (verified: Lepton 160x120 through
            # RealSense's higher resolutions all survive 4 levels), but a
            # degenerate frame from a camera glitch (hotplug drop, USB
            # stall producing a truncated/zero-sized buffer - both
            # observed on this hardware before) shouldn't take the whole
            # frame down with it when the other 11 modes wouldn't.
            logger.error(f"laplacian_pyramid CPU path failed: {e}")
            return self._alpha_blend(thermal, rgb)

    def _resolve_laplacian_gpu(self) -> bool:
        """
        Determine whether a torch GPU path (CUDA, or DirectML on
        Intel/AMD - see utils/gpu_device.py) for laplacian_pyramid
        should be used right now, resolving the device and preparing
        cached kernels on first use. Returns False (falls back to CPU) if
        torch isn't installed, no GPU matching the requested device is
        available, GPU use is disabled (set_laplacian_gpu_enabled(False)),
        or preparing the device fails for any reason - never raises.
        """
        global _TORCH_GPU_UNAVAILABLE
        if (not self.laplacian_use_gpu or not _TORCH_SPEC_AVAILABLE
                or _TORCH_GPU_UNAVAILABLE):
            return False

        if self._laplacian_gpu_ready and self._laplacian_torch_device is not None:
            return True

        if self._laplacian_device_requested == "cpu":
            return False

        try:
            import torch
            from thermal_inspection.utils.gpu_device import resolve_torch_gpu_device

            device, device_name = resolve_torch_gpu_device(self._laplacian_device_requested, "laplacian_pyramid")
            if device is None:
                _TORCH_GPU_UNAVAILABLE = True
                return False

            self._laplacian_torch_device = device
            sobel_x = torch.tensor(
                [[-1., 0., 1.], [-2., 0., 2.], [-1., 0., 1.]], device=device
            ).view(1, 1, 3, 3)
            sobel_y = torch.tensor(
                [[-1., -2., -1.], [0., 0., 0.], [1., 2., 1.]], device=device
            ).view(1, 1, 3, 3)
            self._laplacian_sobel_kernels = (sobel_x, sobel_y)
            self._laplacian_gpu_ready = True
            logger.info(f"laplacian_pyramid: GPU acceleration active ({device_name})")
            return True
        except Exception as e:
            _TORCH_GPU_UNAVAILABLE = True
            logger.warning(
                f"laplacian_pyramid: failed to initialize GPU path, falling back "
                f"to CPU (will not retry this process): {e}"
            )
            self._laplacian_gpu_ready = False
            self._laplacian_torch_device = None
            return False

    def _laplacian_pyramid_gpu(
        self, thermal: np.ndarray, rgb: np.ndarray, levels: int = 4
    ) -> np.ndarray:
        """
        GPU-resident (torch/CUDA) implementation of the same edge-weighted
        multi-scale blend as _laplacian_pyramid_cpu, kept at full
        resolution - unlike cv2.UMat (measured slower here: per-call
        OpenCL dispatch/transfer overhead dominates at this frame size), a
        torch pipeline uploads once and keeps every intermediate tensor on
        the GPU across all pyramid levels, downloading only the final
        result. Measured ~14ms/frame (~73 FPS) on an RTX 4000 Ada at
        640x512 vs ~35ms/frame (~28 FPS) for the CPU path at the same
        resolution - full quality, no downscaling needed.

        Not bit-identical to the CPU path (different pyrDown/pyrUp/blur
        kernel shapes - measured mean diff ~2/255) but the same algorithm
        and blend semantics (same edge-weighted baseline-floor formula).
        """
        import torch
        import torch.nn.functional as F

        device = self._laplacian_torch_device
        sobel_x, sobel_y = self._laplacian_sobel_kernels

        def to_tensor(img):
            t = torch.from_numpy(img).to(device).float()
            return t.permute(2, 0, 1).unsqueeze(0)

        def pyr_down(t):
            return F.avg_pool2d(t, kernel_size=2, stride=2)

        def pyr_up(t, size):
            return F.interpolate(t, size=size, mode='bilinear', align_corners=False)

        def gaussian_blur5(t):
            k = torch.tensor([1., 4., 6., 4., 1.], device=device) / 16.0
            c = t.shape[1]
            kx = k.view(1, 1, 1, 5).expand(c, 1, 1, 5)
            ky = k.view(1, 1, 5, 1).expand(c, 1, 5, 1)
            t = F.conv2d(t, kx, padding=(0, 2), groups=c)
            t = F.conv2d(t, ky, padding=(2, 0), groups=c)
            return t

        th = to_tensor(thermal)
        rg = to_tensor(rgb)
        # BGR -> luma matching cv2.cvtColor(..., COLOR_BGR2GRAY)'s weights,
        # not a plain channel average - keeps edge-weighting behaviour
        # consistent with the CPU path instead of over/under-weighting
        # whichever channel a given thermal colour palette happens to favour.
        gray_th = th[:, 2:3] * 0.299 + th[:, 1:2] * 0.587 + th[:, 0:1] * 0.114

        gp_th = [th]
        gp_rg = [rg]
        gp_w = [gray_th]
        for _ in range(levels):
            gp_th.append(pyr_down(gp_th[-1]))
            gp_rg.append(pyr_down(gp_rg[-1]))
            gp_w.append(pyr_down(gp_w[-1]))

        lp_th = []
        lp_rg = []
        for i in range(levels):
            size = gp_th[i].shape[2:]
            lp_th.append(gp_th[i] - pyr_up(gp_th[i + 1], size))
            lp_rg.append(gp_rg[i] - pyr_up(gp_rg[i + 1], size))
        lp_th.append(gp_th[levels])
        lp_rg.append(gp_rg[levels])

        BASELINE_ALPHA = 0.5  # matches _laplacian_pyramid_cpu's floor - see its comment
        blended = []
        for i in range(levels + 1):
            gx = F.conv2d(gp_w[i], sobel_x, padding=1)
            gy = F.conv2d(gp_w[i], sobel_y, padding=1)
            mag = torch.sqrt(gx * gx + gy * gy)
            max_e = mag.amax()
            # torch.where instead of an `if max_e > 0` Python branch - the
            # latter forces a host<->device sync (five times per frame) just
            # to read one scalar off the GPU, which would quietly eat back
            # a meaningful slice of the speedup this path exists for.
            alpha = torch.where(max_e > 0, mag / torch.clamp(max_e, min=1e-12), torch.zeros_like(mag))
            alpha = gaussian_blur5(alpha)
            alpha = torch.clamp(alpha, 0.0, 1.0)
            alpha = BASELINE_ALPHA + (1.0 - BASELINE_ALPHA) * alpha
            alpha = alpha * self.fusion_intensity
            blended.append(lp_rg[i] + alpha * (lp_th[i] - lp_rg[i]))

        result = blended[levels]
        for i in range(levels - 1, -1, -1):
            size = blended[i].shape[2:]
            result = pyr_up(result, size) + blended[i]

        result = torch.clamp(result, 0, 255)
        return result.squeeze(0).permute(1, 2, 0).contiguous().to(torch.uint8).cpu().numpy()

    def _laplacian_pyramid_cpu(
        self, thermal: np.ndarray, rgb: np.ndarray, levels: int = 4
    ) -> np.ndarray:
        """
        Multi-scale Laplacian Pyramid blending (CPU/OpenCV path).

        Blends thermal and RGB at each frequency scale independently, guided
        by the local edge energy of the thermal frame.  This eliminates the
        halo/ghosting artefacts produced by per-pixel gradient weighting
        (feature_weighted mode) while preserving sharp RGB texture detail.

        Uses only standard OpenCV (pyrDown / pyrUp) — no contrib required.

        Args:
            thermal: Colourised thermal frame (BGR)
            rgb:     Aligned RGB frame (BGR)
            levels:  Number of pyramid levels (4 is a good default for 640×512)

        Returns:
            Blended BGR frame
        """
        thermal_f = thermal.astype(np.float32)
        rgb_f = rgb.astype(np.float32)

        # Build Gaussian pyramids
        gp_thermal = [thermal_f]
        gp_rgb = [rgb_f]
        for _ in range(levels):
            gp_thermal.append(cv2.pyrDown(gp_thermal[-1]))
            gp_rgb.append(cv2.pyrDown(gp_rgb[-1]))

        # Build Laplacian pyramids. gp_thermal[i]/gp_rgb[i] for i < levels
        # are never read again after this loop computes their Laplacian
        # level, so subtract in place into them instead of allocating a
        # fresh lp_thermal[i]/lp_rgb[i] array - line-level profiling found
        # this step (all 4 levels) costing ~9ms on its own, second only to
        # the blend loop below, on a 640x512 frame.
        lp_thermal = []
        lp_rgb = []
        for i in range(levels):
            h, w = gp_thermal[i].shape[:2]
            up_t = cv2.pyrUp(gp_thermal[i + 1], dstsize=(w, h))
            up_r = cv2.pyrUp(gp_rgb[i + 1], dstsize=(w, h))
            gp_thermal[i] -= up_t
            gp_rgb[i] -= up_r
            lp_thermal.append(gp_thermal[i])
            lp_rgb.append(gp_rgb[i])
        lp_thermal.append(gp_thermal[levels])
        lp_rgb.append(gp_rgb[levels])

        # Build per-level weight maps from thermal edge energy
        # (higher local gradient → more thermal; smooth areas → more RGB).
        # Sobel/magnitude recomputed at each level (not computed once and
        # pyrDown'd) - measured that shortcut as only a ~2ms saving anyway
        # (not the dominant cost - see the blend loop and Laplacian
        # construction above for that), and it visibly changes this mode's
        # output: Sobel and downsampling don't commute, so an edge map
        # computed once at full res and then downsampled is measurably
        # different from recomputing Sobel at each already-downsampled
        # level (verified: max per-channel diff of 19/255 on a synthetic
        # test). Not worth trading this mode's actual visual output for a
        # secondary saving.
        gray_thermal = cv2.cvtColor(thermal, cv2.COLOR_BGR2GRAY).astype(np.float32)
        gp_weight = [gray_thermal]
        for _ in range(levels):
            gp_weight.append(cv2.pyrDown(gp_weight[-1]))

        # Blend loop measured as the single largest cost in this fusion mode
        # (~12ms of the pre-optimization ~34ms total on a 640x512 frame).
        # Every step below writes in place (out=/dst=/-=/+=) into a buffer
        # that's used exactly once per level and never read again, instead
        # of allocating a fresh array at each of these 5 steps - including
        # lp_thermal[i]/lp_rgb[i] themselves, which end this loop holding
        # the blended result rather than a separate `diff`/`blended` array.
        blended_pyramid = []
        for i in range(levels + 1):
            # Normalise edge energy to [0, 1] as blend weight for thermal.
            w_map = gp_weight[i]
            sobel_x = cv2.Sobel(w_map, cv2.CV_32F, 1, 0, ksize=3)
            sobel_y = cv2.Sobel(w_map, cv2.CV_32F, 0, 1, ksize=3)
            alpha_map = cv2.magnitude(sobel_x, sobel_y)
            max_e = alpha_map.max()
            if max_e > 0:
                alpha_map /= max_e
            else:
                alpha_map[:] = 0.0
            cv2.GaussianBlur(alpha_map, (5, 5), 0, dst=alpha_map)   # smooth weight map
            np.clip(alpha_map, 0.0, 1.0, out=alpha_map)
            # Per-level max-normalisation only pulls the single sharpest-edge
            # pixel in each level up near 1.0 - everywhere else (most of the
            # frame, away from that one strongest edge) gets a weight close
            # to 0 regardless of fusion_intensity, so thermal barely shows
            # through even at intensity=1.0. A floor guarantees every pixel
            # gets at least BASELINE_ALPHA of thermal blended in at full
            # intensity, while edge pixels still get proportionally more
            # (preserves the edge-adaptive halo-avoidance this mode exists
            # for), which is what actually lets fusion_intensity control the
            # overall blend strength the way alpha_blend's flat alpha does.
            BASELINE_ALPHA = 0.5
            alpha_map *= (1.0 - BASELINE_ALPHA)
            alpha_map += BASELINE_ALPHA
            # Apply overall fusion intensity
            alpha_map *= self.fusion_intensity
            # Broadcast (H, W) -> (H, W, 3) implicitly in the multiply below
            # instead of physically materialising a 3-channel copy via
            # np.repeat - profiled at ~3.5ms/frame (~11% of this mode's
            # total cost at 640x512) for a value numpy's own broadcasting
            # produces identically, just without the extra full-frame
            # allocation and copy.
            alpha_3 = alpha_map[:, :, np.newaxis]

            # Lerp form (rgb + alpha*(thermal-rgb)), fully in place:
            # lp_thermal[i] -= lp_rgb[i]   -> (thermal - rgb)
            # lp_thermal[i] *= alpha_3      -> alpha * (thermal - rgb)
            # lp_rgb[i] += lp_thermal[i]    -> rgb + alpha * (thermal - rgb)
            lp_thermal[i] -= lp_rgb[i]
            lp_thermal[i] *= alpha_3
            lp_rgb[i] += lp_thermal[i]
            blended_pyramid.append(lp_rgb[i])

        # Reconstruct from blended pyramid
        result = blended_pyramid[levels]
        for i in range(levels - 1, -1, -1):
            h, w = blended_pyramid[i].shape[:2]
            result = cv2.add(cv2.pyrUp(result, dstsize=(w, h)), blended_pyramid[i])

        return np.clip(result, 0, 255).astype(np.uint8)

    def _pca_fusion(self, thermal: np.ndarray, rgb: np.ndarray) -> np.ndarray:
        """
        PCA-based fusion - a classical spatial-domain technique from the
        infrared-visible fusion literature (see the 2026-09-06
        fusion-technique search): treats each pixel's (thermal, rgb)
        grayscale intensity pair as a 2D observation, finds the direction
        of maximum variance across the whole frame via a 2x2 eigen-
        decomposition, and uses that eigenvector's (normalized, always
        non-negative) components as blend weights. Unlike a fixed 50/50
        alpha blend, the weights adapt per-frame to whichever source
        actually carries more discriminating information in the current
        scene - concretely, a frame where thermal is nearly flat (a
        thermally uniform scene) leans the blend toward RGB automatically,
        without needing feature_weighted's per-pixel edge-strength
        machinery to get there.

        Priority/fusion_intensity lerp toward a single-source prior - see
        the bias code's own comment for why a multiplier (feature_weighted's
        original convention) doesn't work here: PCA's own weight is very
        often already saturated near 0 or 1, leaving a multiplier nothing
        to boost. Note this means Strength's effect is naturally small
        whenever Priority already agrees with PCA's own computed
        preference (both ends of the lerp are close together) - that's
        correct, not a bug; it's most visible when Priority is set to
        override what PCA's own data-driven weighting would pick.

        Args:
            thermal: Thermal frame (BGR, colorized)
            rgb: RGB frame (BGR, aligned)

        Returns:
            PCA-weighted blend of thermal and rgb
        """
        try:
            # 2x2 sample covariance (ddof=1, same as np.cov) between the two
            # sources' grayscale intensities. The gray values are integers
            # 0-255, so every sum and dot product below is an integer
            # < 2^53 and exact in float64. The covariance is then formed
            # with exact Python-int arithmetic and rounded once, instead of
            # np.cov's vstack + float64 copy + mean-subtraction passes
            # (~5ms at 640x512 -> ~1ms). It's the same statistic, at least
            # as precise: output was identical to the np.cov version on
            # every test frame, but it isn't bit-identical by construction
            # because the float64 rounding path differs.
            thermal_gray = cv2.cvtColor(thermal, cv2.COLOR_BGR2GRAY).reshape(-1).astype(np.float64)
            rgb_gray = cv2.cvtColor(rgb, cv2.COLOR_BGR2GRAY).reshape(-1).astype(np.float64)
            n = thermal_gray.size
            s_t = int(thermal_gray.sum())
            s_r = int(rgb_gray.sum())
            s_tt = int(thermal_gray @ thermal_gray)
            s_rr = int(rgb_gray @ rgb_gray)
            s_tr = int(thermal_gray @ rgb_gray)
            denom = n * (n - 1)
            cov_tr = (n * s_tr - s_t * s_r) / denom
            cov = np.array([
                [(n * s_tt - s_t * s_t) / denom, cov_tr],
                [cov_tr, (n * s_rr - s_r * s_r) / denom],
            ])
            eigenvalues, eigenvectors = np.linalg.eigh(cov)  # ascending order
            principal = eigenvectors[:, -1]  # eigenvector for the largest eigenvalue

            # The principal eigenvector's sign is arbitrary (eigh doesn't
            # guarantee non-negative components) - only its DIRECTION
            # carries meaning, and a blend weight must be non-negative, so
            # take absolute values before normalizing to sum to 1.
            weights = np.abs(principal)
            weight_sum = weights.sum()
            if weight_sum < 1e-6:
                # Degenerate case (near-zero variance in both sources, or
                # a singular covariance matrix) - no real principal
                # direction to speak of, fall back to an even split
                # rather than dividing by ~zero.
                w_thermal, w_rgb = 0.5, 0.5
            else:
                w_thermal, w_rgb = float(weights[0] / weight_sum), float(weights[1] / weight_sum)

            # Priority/fusion_intensity bias applied as a blend against a
            # uniform priority prior, NOT a multiplier on the PCA weight
            # above - live-reported as having "very minimal effect," and
            # confirmed directly: PCA's own weight is very often already
            # saturated close to 0 or 1 (thermal and visible imagery
            # rarely have comparable variance scales), so a multiplier has
            # essentially nothing left to boost - on a realistic test
            # scene (moderate-variance thermal hot spot vs. moderately
            # textured RGB), the result was BIT-IDENTICAL to pure thermal
            # at every intensity from 0.0 to 1.0, because PCA alone
            # already assigned thermal ~100% of the weight. Same fix
            # (and same root cause) as guided_filter_fusion's own bias:
            # a blend against a uniform prior has a real, uniform effect
            # regardless of how lopsided the underlying weight already
            # is - fusion_intensity=0 is pure PCA weighting, 1 is pure
            # single-source, with a real gradient between them.
            prior_thermal = 1.0 if self.fusion_priority == 'thermal' else 0.0
            w_thermal = (1.0 - self.fusion_intensity) * w_thermal + self.fusion_intensity * prior_thermal
            w_rgb = 1.0 - w_thermal

            return cv2.addWeighted(thermal, w_thermal, rgb, w_rgb, 0)

        except Exception as e:
            logger.error(f"PCA fusion error: {e}")
            return self._alpha_blend(thermal, rgb)

    def _guided_filter_fusion(self, thermal: np.ndarray, rgb: np.ndarray) -> np.ndarray:
        """
        Guided-filter + saliency fusion - a real-time-friendly classical
        (non-deep-learning) technique from the infrared-visible fusion
        literature (see the 2026-09-06 fusion-technique search; based on
        Li, Kang & Hu, "Image Fusion With Guided Filtering," IEEE TIP
        2013 - a single-scale simplification of their two-scale scheme,
        not a full reimplementation). A saliency map (local-average
        absolute Laplacian response - how much locally-interesting detail
        each source has) is computed per source, turned into a per-pixel
        "which source matters more here" weight map, then refined with a
        guided filter (guided by each source's own grayscale image, via
        cv2.boxFilter - this codebase has no opencv-contrib dependency,
        so cv2.ximgproc.guidedFilter isn't available, but the guided
        filter algorithm itself is a handful of box filters and is simple
        to implement directly). The refinement is what avoids halo/
        ghosting artifacts a naive per-pixel weighted blend produces at
        strong edges: it snaps the blend weight's own boundaries to real
        image edges instead of the saliency map's own blocky ones - the
        same class of problem feature_weighted's sigmoid formula and
        laplacian_pyramid's edge-weighted baseline each solve a different
        way.

        Args:
            thermal: Thermal frame (BGR, colorized)
            rgb: RGB frame (BGR, aligned)

        Returns:
            Guided-filter-fused frame
        """
        try:
            thermal_gray_full = cv2.cvtColor(thermal, cv2.COLOR_BGR2GRAY).astype(np.float32)
            rgb_gray_full = cv2.cvtColor(rgb, cv2.COLOR_BGR2GRAY).astype(np.float32)

            # The saliency+guided-filter math below runs at
            # guided_filter_scale (default 0.5, i.e. 1/4 the pixels), not
            # full resolution - measured at full res on a 640x512 frame:
            # ~69ms/frame mean (up to 109ms), which would cap this mode
            # under 15fps; box-filter cost scales with pixel count
            # (verified: 13.1ms/call at 512x640 -> 2.6ms at 256x320 -> 0.7ms
            # at 128x160 for the same guided-filter core), and the weight
            # map this produces is inherently smooth/low-frequency by
            # construction (it's built from box-filtered - already-
            # blurred - saliency, then box-filtered again to refine), so
            # it tolerates downsampling well - unlike a binary edge mask,
            # this is exactly the continuous, low-frequency data
            # INTER_LINEAR up/downsampling is the right tool for. Same
            # design precedent as laplacian_pyramid's own
            # laplacian_cpu_scale.
            scale = self.guided_filter_scale
            if scale < 0.999:
                small_w = max(1, int(round(thermal_gray_full.shape[1] * scale)))
                small_h = max(1, int(round(thermal_gray_full.shape[0] * scale)))
                thermal_gray = cv2.resize(thermal_gray_full, (small_w, small_h), interpolation=cv2.INTER_AREA)
                rgb_gray = cv2.resize(rgb_gray_full, (small_w, small_h), interpolation=cv2.INTER_AREA)
            else:
                thermal_gray = thermal_gray_full
                rgb_gray = rgb_gray_full

            def saliency(gray: np.ndarray) -> np.ndarray:
                lap = cv2.Laplacian(gray, cv2.CV_32F, ksize=3)
                np.abs(lap, out=lap)
                return cv2.boxFilter(lap, cv2.CV_32F, (7, 7))

            sal_thermal = saliency(thermal_gray)
            sal_rgb = saliency(rgb_gray)

            denom = sal_thermal + sal_rgb + 1e-6
            p_thermal = sal_thermal / denom

            # Priority/fusion_intensity bias applied as a blend against a
            # flat priority prior, NOT a multiplier on the raw saliency
            # values above - saliency is zero almost everywhere except
            # thin edge boundaries (flat/filled regions of a real hot
            # blob have no local gradient at all), so multiplying an
            # already-near-zero value by a bias factor left Priority/
            # Strength producing almost no visible change over most of a
            # typical frame (verified directly on a symmetric two-circle
            # test scene at fusion_intensity=1.0, the maximum bias setting:
            # thermal-priority and rgb-priority differed from pure thermal
            # by 87.8 vs 88.0 mean/255 - barely distinguishable despite
            # being the two opposite extremes of the Priority control). A
            # blend against a uniform prior has a real, uniform effect
            # everywhere, including flat regions where saliency alone has
            # nothing to say - fusion_intensity=0 is pure saliency-driven weighting
            # (the technique's own natural behavior), fusion_intensity=1
            # is pure priority (single source), with a real gradient
            # between the two (confirmed on the same symmetric test scene
            # at fusion_intensity=1.0: thermal-priority now reproduces
            # pure thermal exactly (0.0 mean diff), rgb-priority differs
            # by 17.1/255 - versus <0.2/255 difference between the two
            # before this fix, at the same maximum bias setting).
            prior_thermal = 1.0 if self.fusion_priority == 'thermal' else 0.0
            p_thermal = (1.0 - self.fusion_intensity) * p_thermal + self.fusion_intensity * prior_thermal
            p_rgb = 1.0 - p_thermal

            # Guided-filter radius scaled down with the resolution so it
            # covers the same proportional neighborhood either way -
            # keeping it fixed at 15 while the image shrinks would refine
            # over an effectively larger fraction of the frame than intended.
            radius = max(3, int(round(15 * scale)))
            eps = (0.05 * 255) ** 2

            def guided_refine(guide: np.ndarray, src: np.ndarray) -> np.ndarray:
                mean_i = cv2.boxFilter(guide, cv2.CV_32F, (radius, radius))
                mean_p = cv2.boxFilter(src, cv2.CV_32F, (radius, radius))
                corr_i = cv2.boxFilter(guide * guide, cv2.CV_32F, (radius, radius))
                corr_ip = cv2.boxFilter(guide * src, cv2.CV_32F, (radius, radius))
                var_i = corr_i - mean_i * mean_i
                cov_ip = corr_ip - mean_i * mean_p
                a = cov_ip / (var_i + eps)
                b = mean_p - a * mean_i
                mean_a = cv2.boxFilter(a, cv2.CV_32F, (radius, radius))
                mean_b = cv2.boxFilter(b, cv2.CV_32F, (radius, radius))
                return mean_a * guide + mean_b

            w_thermal = guided_refine(thermal_gray, p_thermal)
            w_rgb = guided_refine(rgb_gray, p_rgb)

            weight_sum = w_thermal + w_rgb
            np.clip(weight_sum, 1e-6, None, out=weight_sum)
            w_thermal /= weight_sum
            w_rgb /= weight_sum

            if scale < 0.999:
                # LINEAR, not NEAREST: this is a continuous, low-frequency
                # weight map (see the scale comment above), not a binary
                # mask - the earlier enhanced_edge_highlight bug this
                # session was the opposite situation (a binary Canny mask
                # wrongly upscaled with LINEAR, creating a blur halo
                # bitwise_and's mask treated as "edge"); here there's no
                # such hard-cutoff mask to corrupt.
                full_size = (thermal_gray_full.shape[1], thermal_gray_full.shape[0])
                w_thermal = cv2.resize(w_thermal, full_size, interpolation=cv2.INTER_LINEAR)
                w_rgb = cv2.resize(w_rgb, full_size, interpolation=cv2.INTER_LINEAR)

            # Same float32 products and sum as materializing 3-channel
            # weight maps (cv2.merge) and float copies of both frames, but
            # the uint8->float32 cast happens inside the multiply and the
            # (H,W,1) weight broadcasts. Two fewer full-frame (H,W,3)
            # float32 temporaries, bit-identical output (verified).
            result = np.multiply(thermal, w_thermal[:, :, np.newaxis], dtype=np.float32)
            result += np.multiply(rgb, w_rgb[:, :, np.newaxis], dtype=np.float32)
            np.clip(result, 0, 255, out=result)
            return result.astype(np.uint8)

        except Exception as e:
            logger.error(f"Guided filter fusion error: {e}")
            return self._alpha_blend(thermal, rgb)

    def set_fusion_mode(self, mode: str):
        """Change fusion mode"""
        if mode in self.AVAILABLE_FUSION_MODES:
            self.fusion_mode = mode
            logger.info(f"Fusion mode changed to: {mode}")
        else:
            logger.warning(f"Invalid fusion mode: {mode}")

    def set_alpha(self, alpha: float):
        """
        Set alpha blend ratio

        Args:
            alpha: Blend ratio (0.0 = all RGB, 1.0 = all thermal)
        """
        self.alpha = np.clip(alpha, 0.0, 1.0)
        logger.info(f"Alpha blend ratio set to: {self.alpha:.2f}")

    def get_available_modes(self) -> list:
        """Get list of available fusion modes"""
        return list(self.AVAILABLE_FUSION_MODES)


if __name__ == "__main__":
    """Test fusion processor with synthetic data"""
    print("="*60)
    print("Fusion Processor Test")
    print("="*60)

    # Create synthetic thermal and RGB frames
    thermal = np.random.randint(0, 255, (512, 640, 3), dtype=np.uint8)
    thermal = cv2.applyColorMap(cv2.cvtColor(thermal, cv2.COLOR_BGR2GRAY), cv2.COLORMAP_HOT)

    rgb = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)

    # Draw some test patterns
    cv2.circle(thermal, (320, 256), 50, (0, 0, 255), -1)  # Hot spot
    cv2.rectangle(rgb, (200, 200), (400, 400), (0, 255, 0), 3)  # Green box

    # Test all fusion modes
    processor = FusionProcessor()

    modes = processor.get_available_modes()
    print(f"\nTesting {len(modes)} fusion modes...")

    for mode in modes:
        print(f"\nMode: {mode}")
        processor.set_fusion_mode(mode)
        fused = processor.fuse_frames(thermal, rgb)

        if fused is not None:
            cv2.imshow(f"Fusion Mode: {mode}", fused)
            print(f"  Output shape: {fused.shape}")
            key = cv2.waitKey(0)
            if key == ord('q'):
                break

    cv2.destroyAllWindows()
    print("\nTest complete!")
