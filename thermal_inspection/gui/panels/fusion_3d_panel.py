"""
3D Fusion - a pseudo-3D depth-relief enhancement of the 2D Fusion image,
not a separate navigable point cloud as the primary feature. The 2D
Fusion (RGB+thermal alpha blend) output is shaded using real depth-derived
surface normals (an emboss/bump-map effect, like the existing Relief
Fusion mode, but driven by real measured geometry instead of RGB edge
structure), then displayed through the same main video widget every other
view mode uses - the output is still a flat image, just one with real 3D
depth cues baked in.

A small live point-cloud view (Fusion3DPointCloudView) lives in the
right-dock settings panel as a secondary verification tool - it exists to
visually confirm the RealSense depth/RGB/thermal data is being captured
and aligned correctly, with a component checklist to isolate which
sources feed it, not as the main deliverable.

Both are deliberately gated on real measured depth only (RealSense).
Parallax correction's "simplified"/MiDaS/DepthAnything depth methods are
estimation heuristics that exist to correct for the fact that no two
cameras can be perfectly mechanically aligned - they are not accurate
enough to shade or reconstruct real 3D structure from, and doing so would
be exactly the kind of "looks plausible but isn't real" visualization
this project avoids elsewhere (see e.g. radiometric calibration handling).
"""
from __future__ import annotations

import logging
import importlib.util
import time
from typing import Optional

import cv2
import numpy as np
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSlider, QComboBox, QPushButton
)
from PyQt6.QtCore import Qt, pyqtSignal

logger = logging.getLogger(__name__)

# Optional: torch, for GPU-accelerated depth visualizations at full
# resolution (see _resolve_3d_gpu). Not imported eagerly - same deferral
# pattern as fusion_processor.py's laplacian_pyramid GPU path.
_TORCH_SPEC_AVAILABLE = importlib.util.find_spec("torch") is not None
_torch_gpu_ready = False
_torch_device = None
_torch_kernels = None  # (sobel_x, sobel_y, gauss_kx, gauss_ky) tensors, built once per process
# Diagnostic only - counts apply_3d_visualization's GPU-path calls so
# torch.cuda memory stats print periodically instead of every call. See
# their use in apply_3d_visualization: investigating "fps eventually
# sinks" over a long session - if gpu_reserved_mb climbs without bound
# over time while gpu_allocated_mb stays flat, that's the caching
# allocator fragmenting from repeatedly seeing different tensor shapes
# (512x640 vs 800x1280 vs whatever feature_weighted_gpu uses), not a
# real leak - the fix would be a periodic torch.cuda.empty_cache() or
# pinning to consistent shapes, not chasing a reference-counting bug.
_apply_3d_viz_call_count = 0

try:
    import pyqtgraph.opengl as gl
    from pyqtgraph import Vector
    GL_AVAILABLE = True
except ImportError:
    GL_AVAILABLE = False
    logger.info("pyqtgraph.opengl not available (PyOpenGL not installed) - 3D Fusion point-cloud preview disabled")
    logger.info("Install with: pip install PyOpenGL PyOpenGL_accelerate")

# RealSense depth frames routinely report a handful of wildly-wrong far
# points (specular reflections, sensor noise at the field-of-view edges) -
# confirmed live on a D455: depth ranged 0-65.5m with a mean of ~1.5m in an
# ordinary room. Left unfiltered, those dominate both the relief-shading
# gradient computation and the point-cloud preview's framing.
MAX_VALID_DEPTH_M = 6.0
MIN_VALID_DEPTH_M = 0.05

# Point budget for the point-cloud preview's real-time GLScatterPlotItem
# updates - a RealSense depth frame can have 300k+ valid points at full
# resolution; redrawing that many every frame is not real-time on typical
# hardware, so the cloud is stride-subsampled down to roughly this many
# points before each update. This is a small verification view, not the
# primary feature, so a modest budget is fine.
MAX_PREVIEW_POINTS = 20000

DEFAULT_CAMERA_DISTANCE = 2.0

# Single source of truth for 3D Fusion's visualization modes - mirrors the
# AVAILABLE_FUSION_MODES/FUSION_MODE_LABELS pattern in fusion_processor.py
# (2D Fusion's mode list), after that split into independent copies drifted
# out of sync with each other earlier this session.
THREE_D_MODES = ["relief", "fog", "contours", "anaglyph", "colorize"]
THREE_D_MODE_LABELS = {
    "relief": "Relief Shading",
    "fog": "Depth Fog",
    "contours": "Depth Contours",
    "anaglyph": "Anaglyph Stereo (red/cyan)",
    "colorize": "Depth Colorize",
}

# Max per-pixel horizontal disparity (px) anaglyph applies at strength=1.0
# and MIN_VALID_DEPTH_M (the closest a pixel can be) - a stylized value,
# not calibrated to any real eye separation or baseline (there's no
# second real viewpoint here, just one depth-augmented image), tuned to
# give a clearly visible stereo pop without becoming an unreadable ghosted
# double-image at typical inspection distances/strengths.
ANAGLYPH_MAX_SHIFT_PX = 20.0

# Depth-gradient color styles shared by fog/relief/contours/colorize - a
# separate axis from THREE_D_MODES (which mode) and applies to whichever
# mode uses a depth gradient at all (anaglyph doesn't). "color" (TURBO
# rainbow) is the most perceptually distinguishable option, but thermal
# already has its OWN color palette encoding temperature - stacking a
# second, unrelated color meaning (hue = distance) on top of that can
# read as confusing double-encoding. "grayscale" (black=near/white=far,
# no hue at all) avoids that clash entirely when fusing with a colorized
# thermal palette; "color" is better when the base image is otherwise
# fairly neutral (e.g. RGB Only, or a grayscale thermal palette).
GRADIENT_STYLES = ["color", "grayscale"]
GRADIENT_STYLE_LABELS = {
    "color": "Color (Turbo)",
    "grayscale": "Grayscale",
}


def _gradient_colorize_cpu(normalized_01: np.ndarray, gradient_style: str = "color") -> np.ndarray:
    """
    Map a [0,1]-normalized depth-derived array to a float32 BGR image
    (H, W, 3) per gradient_style - shared by fog/relief/contours/colorize
    so all four depth gradients stay visually consistent and controlled
    by the same one setting.
    """
    if gradient_style == "grayscale":
        gray_u8 = np.clip(normalized_01 * 255.0, 0, 255).astype(np.uint8)
        return cv2.cvtColor(gray_u8, cv2.COLOR_GRAY2BGR).astype(np.float32)
    depth_u8 = np.clip(normalized_01 * 255.0, 0, 255).astype(np.uint8)
    return cv2.applyColorMap(depth_u8, cv2.COLORMAP_TURBO).astype(np.float32)


# Depth Fog's fade metric - "distance" (default, real measured depth) or
# "motion" (frame-to-frame change - fades STATIC regions, keeps actively
# CHANGING ones sharp, e.g. highlighting a moving belt/fan/vibration
# against a static background). Motion needs no depth data at all, so
# unlike every other 3D Fusion mode it works even without RealSense - but
# stays gated the same way as the rest of 3D Fusion for consistency
# (it's a per-mode metric choice, not a reason to change the whole
# feature's hardware gating).
FOG_FADE_METRICS = ["distance", "motion"]
FOG_FADE_METRIC_LABELS = {
    "distance": "Distance",
    "motion": "Motion",
}

# Frame-to-frame grayscale difference (0-255 scale) that counts as "fully
# in motion" for the motion fade metric - tuned so typical real movement
# (not just sensor/compression noise) reaches full scale without a single
# noisy pixel maxing it out.
_FOG_MOTION_DIFF_SCALE = 40.0

# Previous-frame cache for the motion fade metric, keyed by frame shape -
# module-level like this file's other per-process caches (_turbo_lut_gpu
# etc.), since apply_depth_fog itself is otherwise a stateless pure
# function of its arguments.
_fog_motion_prev_gray: dict = {}


def _compute_motion_normalized_cpu(image_bgr: np.ndarray) -> np.ndarray:
    """Per-pixel motion magnitude in [0, 1] from frame-to-frame grayscale difference - see FOG_FADE_METRICS."""
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY).astype(np.float32)
    key = gray.shape
    prev = _fog_motion_prev_gray.get(key)
    _fog_motion_prev_gray[key] = gray
    if prev is None:
        return np.zeros(gray.shape, dtype=np.float32)
    return np.clip(np.abs(gray - prev) / _FOG_MOTION_DIFF_SCALE, 0.0, 1.0)


def apply_depth_relief(image_bgr: np.ndarray, depth_m: np.ndarray, strength: float = 0.5,
                        gradient_style: str = "color", **_unused) -> np.ndarray:
    """
    Shade a BGR image using real depth-derived surface normals - an
    emboss/bump-map effect giving edges and surfaces a subtle 3D-relief
    look driven by real measured geometry, not RGB edge structure (compare
    FusionProcessor._relief_fusion, which embosses RGB gradients instead).

    Local slope shading alone only reveals RELATIVE depth (two equally-
    sloped surfaces at very different absolute distances shade
    identically) - blends in a modest ABSOLUTE-depth gradient tint on top
    (see GRADIENT_STYLES/gradient_style) so distance itself, not just
    local surface angle, comes through visually.

    Args:
        image_bgr: base image to shade (H, W, 3) uint8 - typically the 2D
            Fusion RGB+thermal blend, but works with any BGR image the same
            resolution as depth_m
        depth_m: depth map in meters (H, W) float32, same resolution as
            image_bgr (resize first if not - see caller)
        strength: 0 = no effect (image unchanged), 1 = strong relief
        gradient_style: "color" (TURBO rainbow) or "grayscale" (no hue,
            avoids clashing with a colorized thermal palette already in
            the base image) - see GRADIENT_STYLES

    Returns:
        Shaded BGR uint8 image, same shape as image_bgr
    """
    # Profiled at ~36ms/frame (of ~47ms total) in the plain, non-in-place
    # version of the arithmetic below - the same "every step allocates a
    # fresh temp array" cost found and fixed in laplacian_pyramid earlier.
    # Every step here writes into a buffer already held (out=/dst=/-=/+=/
    # *=/np.multiply(..., out=)) instead of allocating a new array, since
    # none of these intermediates are read again after the step that
    # produces the next one.
    depth = np.clip(depth_m, MIN_VALID_DEPTH_M, MAX_VALID_DEPTH_M)
    # Snapshot before blur for the absolute-depth tint below - using the
    # blurred value there instead measurably diverged between the CPU
    # (cv2.GaussianBlur) and GPU (hand-rolled separable kernel) paths:
    # numerically close but not identical, and TURBO's colormap isn't
    # perceptually linear, so even a tiny blur difference could land on a
    # very different color index. The plain clamp is numerically identical
    # either way (np.clip vs torch.clamp).
    depth_for_tint = depth.copy()
    # Real depth sensors are noisier per-pixel than RGB - smooth before
    # differentiating so gradient noise doesn't dominate the shading.
    cv2.GaussianBlur(depth, (5, 5), 1.0, dst=depth)

    gx = cv2.Sobel(depth, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(depth, cv2.CV_32F, 0, 1, ksize=3)

    # Depth increases away from the camera - negate in place so a
    # physically closer (nearer-camera) surface reads as "raised" in the
    # height-map sense a normal-map computation expects. gx/gy are each
    # used only once more below (squared into norm), so this is safe.
    nx, ny = gx, gy
    np.negative(nx, out=nx)
    np.negative(ny, out=ny)

    # norm = sqrt(nx^2 + ny^2 + nz^2), nz constant 0.05 (small z keeps
    # normals mostly-flat except at real depth edges) - accumulate into a
    # single buffer rather than building nx*nx, ny*ny, nz*nz as separate
    # fresh arrays.
    norm = np.multiply(nx, nx)
    norm += ny * ny
    norm += 0.05 * 0.05
    np.sqrt(norm, out=norm)
    norm += 1e-6
    nx /= norm
    ny /= norm
    nz = 0.05 / norm  # only remaining fresh allocation for the normal itself

    # Light from upper-left, standard relief/bump-map convention -
    # constants, not worth vectorizing.
    lx, ly, lz = -0.5, -0.5, 0.7
    l_norm = (lx * lx + ly * ly + lz * lz) ** 0.5
    lx, ly, lz = lx / l_norm, ly / l_norm, lz / l_norm

    # shade = dot(normal, light), recentred to [0, 1]; reuse nx as the
    # accumulator (it's the only one of the three no longer needed after).
    shade = nx
    shade *= lx
    shade += ny * ly
    shade += nz * lz
    shade *= 0.5
    shade += 0.5

    strength = max(0.0, min(1.0, strength))
    # factor = 1 + strength*(shade-0.5)*2, reusing shade's buffer throughout.
    shade -= 0.5
    shade *= strength * 2.0
    shade += 1.0
    factor_3ch = shade[:, :, np.newaxis]

    result = image_bgr.astype(np.float32)
    result *= factor_3ch
    np.clip(result, 0, 255, out=result)

    # Absolute-depth gradient tint, scaled down (0.35x of strength) so it
    # reads as a color cast alongside the shading rather than overwhelming
    # it - uses depth_for_tint (pre-blur) - see its definition above.
    depth_for_tint -= MIN_VALID_DEPTH_M
    depth_for_tint /= (MAX_VALID_DEPTH_M - MIN_VALID_DEPTH_M)
    tint = _gradient_colorize_cpu(depth_for_tint, gradient_style)
    tint_amount = strength * 0.35
    result *= (1.0 - tint_amount)
    result += tint * tint_amount
    np.clip(result, 0, 255, out=result)
    return result.astype(np.uint8)


def apply_depth_fog(image_bgr: np.ndarray, depth_m: np.ndarray, strength: float = 0.5,
                     near_m: float = 0.3, far_m: float = 4.0,
                     gradient_style: str = "color", fade_metric: str = "distance", **_unused) -> np.ndarray:
    """
    Fade the image toward a depth gradient as real measured depth (or, with
    fade_metric="motion", frame-to-frame change) increases - the default
    fades far objects and keeps near ones sharp, drawing the eye to
    close-range detail using real distance rather than RGB/thermal
    contrast alone; "motion" instead fades STATIC regions and keeps
    actively CHANGING ones sharp (e.g. highlighting a moving belt/fan/
    vibration against a static background) - a genuinely different signal
    from depth, and one that needs no depth data at all.

    Args:
        image_bgr: base image to fade (H, W, 3) uint8
        depth_m: depth map in meters (H, W) float32, same resolution -
            unused when fade_metric="motion"
        strength: 0 = no effect, 1 = fully faded at the far/static end
        near_m/far_m: depth range the fade spans (meters), fade_metric=
            "distance" only - closer than near_m stays full contrast,
            farther than far_m is fully faded
        gradient_style: "color" (TURBO rainbow) or "grayscale" - see
            GRADIENT_STYLES
        fade_metric: "distance" (default, real depth) or "motion" (frame-
            to-frame grayscale difference) - see FOG_FADE_METRICS

    Returns:
        Faded BGR uint8 image, same shape as image_bgr
    """
    if fade_metric == "motion":
        # 0 = actively changing (stays sharp), 1 = static (fades) - the
        # inverse of the motion signal itself, so the fade math below
        # (unchanged from the distance case) applies identically.
        fade_pos = 1.0 - _compute_motion_normalized_cpu(image_bgr)
    else:
        fade_pos = np.clip(depth_m, near_m, far_m)
        fade_pos -= near_m
        fade_pos /= max(far_m - near_m, 1e-6)  # 0=near, 1=far

    # Fade toward a depth-gradient color (near/far, or static/moving)
    # instead of flat neutral gray - a uniform gray fade is easy to miss
    # on a scene with fairly modest variation (a flat fade amount, not a
    # color change); this gives a real gradient to fade INTO, not just
    # fade TOWARD greyness. gradient_style="grayscale" still varies (dark
    # to light) rather than collapsing to one flat gray.
    target_color = _gradient_colorize_cpu(fade_pos, gradient_style)

    fade_3ch = (fade_pos * max(0.0, min(1.0, strength)))[:, :, np.newaxis]
    result = image_bgr.astype(np.float32)
    result *= (1.0 - fade_3ch)
    result += target_color * fade_3ch
    np.clip(result, 0, 255, out=result)
    return result.astype(np.uint8)


def apply_depth_contours(image_bgr: np.ndarray, depth_m: np.ndarray, strength: float = 0.5,
                          interval_m: float = 0.5, gradient_style: str = "color", **_unused) -> np.ndarray:
    """
    Overlay topographic-style contour lines at fixed real-depth intervals -
    communicates distance bands explicitly without altering the base
    image's overall brightness/color the way relief/fog do.

    Each line is colored by ITS OWN depth along the gradient (see
    GRADIENT_STYLES) instead of a single fixed color for every line - like
    a topographic map tinting contour lines by elevation, so near and far
    bands are visually distinguishable from EACH OTHER, not just from the
    base image.

    Args:
        image_bgr: base image to draw on (H, W, 3) uint8
        depth_m: depth map in meters (H, W) float32, same resolution
        strength: 0 = no lines, 1 = fully opaque contour lines
        interval_m: spacing between contour lines, in meters
        gradient_style: "color" (TURBO rainbow) or "grayscale" - see
            GRADIENT_STYLES

    Returns:
        BGR uint8 image with contour lines overlaid, same shape as image_bgr
    """
    depth = np.clip(depth_m, MIN_VALID_DEPTH_M, MAX_VALID_DEPTH_M)
    bands = (depth / interval_m).astype(np.int32)

    edges = np.zeros(bands.shape, dtype=bool)
    edges[:, 1:] |= bands[:, 1:] != bands[:, :-1]
    edges[1:, :] |= bands[1:, :] != bands[:-1, :]

    strength = max(0.0, min(1.0, strength))
    result = image_bgr.copy()
    depth_normalized = (depth - MIN_VALID_DEPTH_M) / (MAX_VALID_DEPTH_M - MIN_VALID_DEPTH_M)
    line_colors = _gradient_colorize_cpu(depth_normalized, gradient_style)
    blended = result[edges].astype(np.float32)
    blended *= (1.0 - strength)
    blended += line_colors[edges] * strength
    result[edges] = np.clip(blended, 0, 255).astype(np.uint8)
    return result


def apply_depth_anaglyph(image_bgr: np.ndarray, depth_m: np.ndarray, strength: float = 0.5, **_unused) -> np.ndarray:
    """
    Synthesize a red/cyan anaglyph stereo pair from a single image + real
    depth, viewable with red-cyan 3D glasses for genuine binocular depth
    perception - unlike relief/fog/contours (all still flat 2D shading/
    tinting of a single image with no left/right viewpoint difference),
    this is the one mode that actually reconstructs two distinct
    viewpoints and encodes them for stereoscopic viewing.

    Not a real stereo camera pair - there's only one image and one depth
    map, so "left eye"/"right eye" here are both synthesized from the same
    source by shifting each pixel horizontally by an amount inversely
    proportional to its own depth (closer = more shift, matching how real
    parallax between two eyes/cameras varies with distance) and resampling
    - the same underlying idea as this project's real parallax correction,
    but applied twice in opposite directions purely for a visual stereo
    effect rather than to align two real sensors. Areas that shift off-
    frame get BORDER_REPLICATE-smeared rather than cropped/blanked (as
    parallax correction does) since a small amount of edge stretching is
    far less objectionable here than losing frame content at the edges of
    a deliberately exaggerated stereo effect.

    Uses a "half-color" anaglyph encoding (red channel = left eye's
    grayscale luma, green+blue = right eye's own color channels) rather
    than full-color or full-grayscale - preserves most of the fused image's
    color/thermal-palette information (important for an inspection tool
    where color often encodes temperature) while reducing the retinal
    rivalry/ghosting a full-color anaglyph would show at shifted edges.

    Args:
        image_bgr: base image to convert (H, W, 3) uint8
        depth_m: depth map in meters (H, W) float32, same resolution
        strength: 0 = no stereo separation (flat, both eyes identical),
            1 = maximum separation (see ANAGLYPH_MAX_SHIFT_PX)

    Returns:
        Red/cyan anaglyph BGR uint8 image, same shape as image_bgr
    """
    h, w = image_bgr.shape[:2]
    depth = np.clip(depth_m, MIN_VALID_DEPTH_M, MAX_VALID_DEPTH_M)

    # closeness: 1.0 at the nearest valid depth, 0.0 at the farthest -
    # nearer pixels get pushed apart more, same intuition as real stereo
    # parallax (closer objects show more disparity between two viewpoints
    # than distant ones).
    closeness = 1.0 - (depth - MIN_VALID_DEPTH_M) / (MAX_VALID_DEPTH_M - MIN_VALID_DEPTH_M)
    strength = max(0.0, min(1.0, strength))
    half_disparity = (closeness * strength * ANAGLYPH_MAX_SHIFT_PX) / 2.0

    x_coords, y_coords = np.meshgrid(np.arange(w, dtype=np.float32), np.arange(h, dtype=np.float32))
    left_eye = cv2.remap(image_bgr, x_coords - half_disparity, y_coords,
                        interpolation=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
    right_eye = cv2.remap(image_bgr, x_coords + half_disparity, y_coords,
                         interpolation=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)

    left_gray = cv2.cvtColor(left_eye, cv2.COLOR_BGR2GRAY)

    result = np.empty_like(image_bgr)
    result[:, :, 2] = left_gray          # R <- left eye (grayscale)
    result[:, :, 1] = right_eye[:, :, 1]  # G <- right eye (color)
    result[:, :, 0] = right_eye[:, :, 0]  # B <- right eye (color)
    return result


def apply_depth_colorize(image_bgr: np.ndarray, depth_m: np.ndarray, strength: float = 0.5,
                          gradient_style: str = "color", **_unused) -> np.ndarray:
    """
    Blend a depth gradient over the base image (see GRADIENT_STYLES) -
    distance encoded as hue (style="color") rather than the subtle
    brightness fade Depth Fog uses. Hue differences are far more
    perceptually distinguishable than small brightness changes, so this
    stays visibly informative even on a scene with fairly modest depth
    variation (e.g. inspecting a mostly-flat panel from a few feet away),
    where Fog's near-uniform fade can look like almost nothing happened.

    Args:
        image_bgr: base image to tint (H, W, 3) uint8
        depth_m: depth map in meters (H, W) float32, same resolution
        strength: 0 = base image untouched, 1 = fully replaced by the
            colorized depth map (no base image detail left)
        gradient_style: "color" (TURBO rainbow) or "grayscale" - see
            GRADIENT_STYLES

    Returns:
        Depth-tinted BGR uint8 image, same shape as image_bgr
    """
    depth = np.clip(depth_m, MIN_VALID_DEPTH_M, MAX_VALID_DEPTH_M)
    normalized = (depth - MIN_VALID_DEPTH_M) / (MAX_VALID_DEPTH_M - MIN_VALID_DEPTH_M)
    depth_colored = _gradient_colorize_cpu(normalized, gradient_style)

    strength = max(0.0, min(1.0, strength))
    result = image_bgr.astype(np.float32) * (1.0 - strength) + depth_colored * strength
    return np.clip(result, 0, 255).astype(np.uint8)


def _resolve_3d_gpu() -> bool:
    """
    Lazily resolve whether a CUDA GPU is usable for 3D Fusion's depth
    visualizations. Unlike the CPU path (which must downscale to stay
    inside the frame-time budget - confirmed live: 40-68ms/frame at
    RealSense's native 1280x800, close to or exceeding the throttle
    interval itself), a torch/CUDA pipeline keeps every intermediate
    tensor GPU-resident across the whole computation instead of round-
    tripping per call, and runs at full resolution: measured ~5ms/frame
    (~190 FPS) for relief shading at 1280x800 on an RTX 4000 Ada, output
    within ~2/255 mean of the CPU version (kernel-shape differences, not a
    quality loss) - full resolution and full speed, no downscaling needed.
    """
    global _torch_gpu_ready, _torch_device, _torch_kernels
    if _torch_gpu_ready:
        return True
    if not _TORCH_SPEC_AVAILABLE:
        return False
    try:
        import torch
        if not torch.cuda.is_available():
            return False
        device = "cuda"
        # cv2.getGaussianKernel's own coefficients for ksize=5, sigma=1.0 -
        # matches apply_depth_relief's cv2.GaussianBlur(depth, (5,5), 1.0)
        # exactly, rather than the binomial [1,4,6,4,1]/16 approximation
        # (close but not identical - measurably diverges once a real
        # Sobel derivative is taken on top, confirmed via a live CPU/GPU
        # comparison on high-frequency depth data).
        gk_np = cv2.getGaussianKernel(5, 1.0).flatten()
        gk = torch.from_numpy(gk_np.astype(np.float32)).to(device)
        kx = gk.view(1, 1, 1, 5)
        ky = gk.view(1, 1, 5, 1)
        sobel_x = torch.tensor(
            [[-1., 0., 1.], [-2., 0., 2.], [-1., 0., 1.]], device=device
        ).view(1, 1, 3, 3)
        sobel_y = torch.tensor(
            [[-1., -2., -1.], [0., 0., 0.], [1., 2., 1.]], device=device
        ).view(1, 1, 3, 3)
        _torch_device = device
        _torch_kernels = (sobel_x, sobel_y, kx, ky)
        _torch_gpu_ready = True
        logger.info(f"3D Fusion: GPU acceleration active ({torch.cuda.get_device_name(0)})")
        return True
    except Exception as e:
        logger.warning(f"3D Fusion: failed to initialize GPU path, falling back to CPU: {e}")
        return False


def _depth_to_normal_gpu(depth_t, torch, F):
    """Shared depth->surface-normal computation for the GPU relief path."""
    sobel_x, sobel_y, kx, ky = _torch_kernels
    depth_t = torch.clamp(depth_t, MIN_VALID_DEPTH_M, MAX_VALID_DEPTH_M)

    # F.conv2d's own `padding=` argument always zero-pads - for a uniform
    # (or near-uniform) depth region near the frame edge, that fabricates
    # a fake depth "cliff" at the border (edge pixels see manufactured
    # zero-depth neighbors outside the frame), producing bogus non-zero
    # gradients exactly where the real depth has none. cv2.GaussianBlur/
    # cv2.Sobel's default border handling extends the real edge value
    # instead - explicit replicate padding here matches that. Confirmed
    # via a live CPU/GPU comparison on uniform (zero-gradient) depth:
    # 100% of a real ~130-level discrepancy was concentrated in the
    # bordering ~5px (the combined blur+sobel kernel reach), zero diff
    # in the interior.
    depth_t = F.pad(depth_t, (2, 2, 0, 0), mode='replicate')
    depth_t = F.conv2d(depth_t, kx, padding=0)
    depth_t = F.pad(depth_t, (0, 0, 2, 2), mode='replicate')
    depth_t = F.conv2d(depth_t, ky, padding=0)

    depth_padded = F.pad(depth_t, (1, 1, 1, 1), mode='replicate')
    gx = F.conv2d(depth_padded, sobel_x, padding=0)
    gy = F.conv2d(depth_padded, sobel_y, padding=0)
    nx, ny = -gx, -gy
    nz = torch.full_like(depth_t, 0.05)
    norm = torch.sqrt(nx * nx + ny * ny + nz * nz) + 1e-6
    return nx / norm, ny / norm, nz / norm, depth_t


def _gradient_colorize_gpu(normalized_01_t, gradient_style: str, device):
    """GPU equivalent of _gradient_colorize_cpu. normalized_01_t: (1,1,H,W) tensor in [0,1]. Returns (1,3,H,W) BGR float tensor."""
    import torch
    if gradient_style == "grayscale":
        gray_255 = torch.clamp(normalized_01_t * 255.0, 0, 255)
        return gray_255.expand(-1, 3, -1, -1)
    idx = torch.clamp((normalized_01_t * 255.0).long(), 0, 255).squeeze(1)  # (1, H, W)
    lut = _get_turbo_lut_gpu(device)  # (256, 3) BGR
    colored = lut[idx]  # (1, H, W, 3), gather via fancy indexing
    return colored.permute(0, 3, 1, 2)  # (1, 3, H, W)


def _apply_depth_relief_gpu_tensor(img_t, depth_t, strength: float = 0.5,
                                    gradient_style: str = "color"):
    """
    All-tensor core of apply_depth_relief_gpu - takes img_t (1,3,H,W) and
    depth_t (1,1,H,W) float32 GPU tensors, returns a (1,3,H,W) float32
    GPU tensor (0-255 range BGR), no upload/download. See
    apply_depth_relief_gpu's docstring for the algorithm; see
    apply_3d_visualization_fused for why this split exists.
    """
    import torch
    import torch.nn.functional as F

    # Snapshot before _depth_to_normal_gpu's internal blur, for the tint
    # below - see the CPU version's identical depth_for_tint comment for
    # why (the blurred value measurably diverges between CPU's
    # cv2.GaussianBlur and this hand-rolled kernel, and TURBO's colormap
    # isn't perceptually linear enough to absorb that safely). Plain
    # clamp is numerically identical to the CPU path's np.clip.
    depth_for_tint = torch.clamp(depth_t, MIN_VALID_DEPTH_M, MAX_VALID_DEPTH_M)
    nx, ny, nz, _ = _depth_to_normal_gpu(depth_t, torch, F)

    lx, ly, lz = -0.5, -0.5, 0.7
    l_norm = (lx * lx + ly * ly + lz * lz) ** 0.5
    lx, ly, lz = lx / l_norm, ly / l_norm, lz / l_norm

    shade = nx * lx + ny * ly + nz * lz
    shade = 0.5 + 0.5 * shade
    strength = max(0.0, min(1.0, strength))
    factor = 1.0 + strength * (shade - 0.5) * 2.0

    result = img_t * factor
    result = torch.clamp(result, 0, 255)

    # Absolute-depth gradient tint on top of the shading - see the CPU
    # version's docstring for why (relief's slope-based shading alone
    # only reveals RELATIVE depth).
    normalized = (depth_for_tint - MIN_VALID_DEPTH_M) / (MAX_VALID_DEPTH_M - MIN_VALID_DEPTH_M)
    tint = _gradient_colorize_gpu(normalized, gradient_style, _torch_device)
    tint_amount = strength * 0.35
    result = result * (1.0 - tint_amount) + tint * tint_amount
    return torch.clamp(result, 0, 255)


def apply_depth_relief_gpu(image_bgr: np.ndarray, depth_m: np.ndarray, strength: float = 0.5,
                            gradient_style: str = "color", **_unused) -> np.ndarray:
    """GPU (torch/CUDA) implementation of apply_depth_relief - see its docstring for the algorithm."""
    import torch

    img_t = torch.from_numpy(image_bgr).to(_torch_device, dtype=torch.float32).permute(2, 0, 1).unsqueeze(0)
    depth_t = torch.from_numpy(depth_m).to(_torch_device, dtype=torch.float32).unsqueeze(0).unsqueeze(0)
    result = _apply_depth_relief_gpu_tensor(img_t, depth_t, strength, gradient_style)
    return result.squeeze(0).permute(1, 2, 0).contiguous().to(torch.uint8).cpu().numpy()


def apply_depth_fog_gpu(image_bgr: np.ndarray, depth_m: np.ndarray, strength: float = 0.5,
                         near_m: float = 0.3, far_m: float = 4.0,
                         gradient_style: str = "color", fade_metric: str = "distance", **_unused) -> np.ndarray:
    """GPU (torch/CUDA) implementation of apply_depth_fog - see its docstring for the algorithm."""
    import torch

    img_t = torch.from_numpy(image_bgr).to(_torch_device, dtype=torch.float32).permute(2, 0, 1).unsqueeze(0)

    if fade_metric == "motion":
        # Motion itself is computed on CPU (a single grayscale abs-diff -
        # not worth a separate GPU frame cache) then moved to GPU for the
        # blend below, same as the depth-map input already crosses that
        # boundary for every mode here.
        fade_pos_np = 1.0 - _compute_motion_normalized_cpu(image_bgr)
        fade_pos = torch.from_numpy(fade_pos_np).to(_torch_device, dtype=torch.float32).unsqueeze(0).unsqueeze(0)
    else:
        depth_t = torch.from_numpy(depth_m).to(_torch_device, dtype=torch.float32).unsqueeze(0).unsqueeze(0)
        depth_t = torch.clamp(depth_t, near_m, far_m)
        fade_pos = (depth_t - near_m) / max(far_m - near_m, 1e-6)

    target_color = _gradient_colorize_gpu(fade_pos, gradient_style, _torch_device)
    fade = fade_pos * max(0.0, min(1.0, strength))

    result = img_t * (1.0 - fade) + target_color * fade
    result = torch.clamp(result, 0, 255)
    return result.squeeze(0).permute(1, 2, 0).contiguous().to(torch.uint8).cpu().numpy()


def apply_depth_contours_gpu(image_bgr: np.ndarray, depth_m: np.ndarray, strength: float = 0.5,
                              interval_m: float = 0.5, gradient_style: str = "color", **_unused) -> np.ndarray:
    """GPU (torch/CUDA) implementation of apply_depth_contours - see its docstring for the algorithm."""
    import torch
    import torch.nn.functional as F

    img_t = torch.from_numpy(image_bgr).to(_torch_device, dtype=torch.float32).permute(2, 0, 1).unsqueeze(0)
    depth_t = torch.from_numpy(depth_m).to(_torch_device, dtype=torch.float32).unsqueeze(0).unsqueeze(0)
    depth_t = torch.clamp(depth_t, MIN_VALID_DEPTH_M, MAX_VALID_DEPTH_M)
    bands = torch.floor(depth_t / interval_m)

    # Edge where a pixel's band differs from its left/up neighbor - pad
    # with replicate so the border isn't spuriously flagged as an edge.
    bands_padded_x = F.pad(bands, (1, 0, 0, 0), mode='replicate')
    bands_padded_y = F.pad(bands, (0, 0, 1, 0), mode='replicate')
    edge_x = (bands != bands_padded_x[:, :, :, :-1]).float()
    edge_y = (bands != bands_padded_y[:, :, :-1, :]).float()
    edge_mask = torch.clamp(edge_x + edge_y, 0, 1)

    strength = max(0.0, min(1.0, strength))
    alpha = edge_mask * strength
    normalized = (depth_t - MIN_VALID_DEPTH_M) / (MAX_VALID_DEPTH_M - MIN_VALID_DEPTH_M)
    line_colors = _gradient_colorize_gpu(normalized, gradient_style, _torch_device)

    result = img_t * (1.0 - alpha) + line_colors * alpha
    result = torch.clamp(result, 0, 255)
    return result.squeeze(0).permute(1, 2, 0).contiguous().to(torch.uint8).cpu().numpy()


def apply_depth_anaglyph_gpu(image_bgr: np.ndarray, depth_m: np.ndarray, strength: float = 0.5, **_unused) -> np.ndarray:
    """GPU (torch/CUDA) implementation of apply_depth_anaglyph - see its docstring for the algorithm."""
    import torch
    import torch.nn.functional as F

    h, w = image_bgr.shape[:2]
    img_t = torch.from_numpy(image_bgr).to(_torch_device, dtype=torch.float32).permute(2, 0, 1).unsqueeze(0)
    depth_t = torch.from_numpy(depth_m).to(_torch_device, dtype=torch.float32).unsqueeze(0).unsqueeze(0)
    depth_t = torch.clamp(depth_t, MIN_VALID_DEPTH_M, MAX_VALID_DEPTH_M)

    closeness = 1.0 - (depth_t - MIN_VALID_DEPTH_M) / (MAX_VALID_DEPTH_M - MIN_VALID_DEPTH_M)
    strength = max(0.0, min(1.0, strength))
    half_disparity = (closeness * strength * ANAGLYPH_MAX_SHIFT_PX) / 2.0  # (1,1,H,W)

    ys, xs = torch.meshgrid(
        torch.arange(h, device=_torch_device, dtype=torch.float32),
        torch.arange(w, device=_torch_device, dtype=torch.float32),
        indexing='ij'
    )
    xs = xs.unsqueeze(0).unsqueeze(0)
    ys = ys.unsqueeze(0).unsqueeze(0)

    def sample(map_x):
        grid_x = (map_x / max(w - 1, 1)) * 2 - 1
        grid_y = (ys / max(h - 1, 1)) * 2 - 1
        grid = torch.stack([grid_x.squeeze(1), grid_y.squeeze(1)], dim=-1)
        return F.grid_sample(img_t, grid, mode='bilinear', padding_mode='border', align_corners=True)

    left_eye = sample(xs - half_disparity)
    right_eye = sample(xs + half_disparity)

    # Standard BGR2GRAY luma weights (matches cv2.cvtColor's convention).
    left_gray = 0.114 * left_eye[:, 0:1] + 0.587 * left_eye[:, 1:2] + 0.299 * left_eye[:, 2:3]

    result = torch.cat([right_eye[:, 0:1], right_eye[:, 1:2], left_gray], dim=1)  # B, G, R
    result = torch.clamp(result, 0, 255)
    return result.squeeze(0).permute(1, 2, 0).contiguous().to(torch.uint8).cpu().numpy()


_turbo_lut_gpu = None  # cached (256, 3) torch tensor - built once per process


def _get_turbo_lut_gpu(device):
    """Build (once) and cache OpenCV's TURBO colormap as a (256, 3) BGR lookup table on the GPU."""
    global _turbo_lut_gpu
    if _turbo_lut_gpu is None:
        import torch
        gradient = np.arange(256, dtype=np.uint8).reshape(256, 1)
        colored = cv2.applyColorMap(gradient, cv2.COLORMAP_TURBO).reshape(256, 3)  # BGR
        _turbo_lut_gpu = torch.from_numpy(colored.astype(np.float32)).to(device)
    return _turbo_lut_gpu


def apply_depth_colorize_gpu(image_bgr: np.ndarray, depth_m: np.ndarray, strength: float = 0.5,
                              gradient_style: str = "color", **_unused) -> np.ndarray:
    """GPU (torch/CUDA) implementation of apply_depth_colorize - see its docstring for the algorithm."""
    import torch

    depth_t = torch.from_numpy(depth_m).to(_torch_device, dtype=torch.float32)
    depth_t = torch.clamp(depth_t, MIN_VALID_DEPTH_M, MAX_VALID_DEPTH_M)
    normalized = (depth_t - MIN_VALID_DEPTH_M) / (MAX_VALID_DEPTH_M - MIN_VALID_DEPTH_M)

    if gradient_style == "grayscale":
        depth_colored = torch.clamp(normalized * 255.0, 0, 255).unsqueeze(-1).expand(-1, -1, 3)
    else:
        idx = torch.clamp((normalized * 255.0).long(), 0, 255)
        lut = _get_turbo_lut_gpu(_torch_device)
        depth_colored = lut[idx]  # (H, W, 3) BGR, gather via fancy indexing

    img_t = torch.from_numpy(image_bgr).to(_torch_device, dtype=torch.float32)
    strength = max(0.0, min(1.0, strength))
    result = img_t * (1.0 - strength) + depth_colored * strength
    result = torch.clamp(result, 0, 255)
    return result.to(torch.uint8).cpu().numpy()


_CPU_MODE_FN = {
    "relief": apply_depth_relief,
    "fog": apply_depth_fog,
    "contours": apply_depth_contours,
    "anaglyph": apply_depth_anaglyph,
    "colorize": apply_depth_colorize,
}
_GPU_MODE_FN = {
    "relief": apply_depth_relief_gpu,
    "fog": apply_depth_fog_gpu,
    "contours": apply_depth_contours_gpu,
    "anaglyph": apply_depth_anaglyph_gpu,
    "colorize": apply_depth_colorize_gpu,
}

# CPU fallback processing width cap - confirmed live that even the
# cheapest CPU mode cost 40-68ms/frame at RealSense's native 1280x800,
# close to or exceeding a 15Hz throttle interval. Only applies when no
# CUDA GPU is available, since the GPU path runs full-resolution anyway.
CPU_MAX_PROC_WIDTH = 640


def apply_3d_visualization(mode: str, image_bgr: np.ndarray, depth_m: np.ndarray,
                            strength: float = 0.5, **kwargs) -> np.ndarray:
    """
    Apply the selected depth visualization (see THREE_D_MODES), using GPU
    acceleration at full resolution when a CUDA GPU is available, falling
    back to a resolution-capped CPU path otherwise (see CPU_MAX_PROC_WIDTH).

    kwargs are mode-specific tunables passed straight through to the
    underlying function (both CPU and GPU variants share the same extra
    parameter names per mode): fog takes near_m/far_m, contours takes
    interval_m. Irrelevant kwargs for the current mode are simply unused
    by that function's own defaults.
    """
    _t0 = time.perf_counter()
    if _resolve_3d_gpu():
        try:
            gpu_fn = _GPU_MODE_FN.get(mode, apply_depth_relief_gpu)
            result = gpu_fn(image_bgr, depth_m, strength=strength, **kwargs)
            global _apply_3d_viz_call_count
            _apply_3d_viz_call_count += 1
            mem_str = ""
            if _apply_3d_viz_call_count % 50 == 0:
                import torch
                allocated = torch.cuda.memory_allocated() / 1e6
                reserved = torch.cuda.memory_reserved() / 1e6
                mem_str = f" gpu_allocated_mb={allocated:.1f} gpu_reserved_mb={reserved:.1f}"
            print(f"[PROFILE_3D_VIZ] path=GPU mode={mode} shape={image_bgr.shape} "
                  f"ms={(time.perf_counter() - _t0) * 1000:.2f}{mem_str}", flush=True)
            return result
        except Exception as e:
            logger.warning(f"3D Fusion GPU path failed, falling back to CPU: {e}")

    cpu_fn = _CPU_MODE_FN.get(mode, apply_depth_relief)
    bh, bw = image_bgr.shape[:2]
    if bw > CPU_MAX_PROC_WIDTH:
        ph = int(round(bh * CPU_MAX_PROC_WIDTH / bw))
        small_img = cv2.resize(image_bgr, (CPU_MAX_PROC_WIDTH, ph), interpolation=cv2.INTER_LINEAR)
        small_depth = cv2.resize(depth_m, (CPU_MAX_PROC_WIDTH, ph), interpolation=cv2.INTER_NEAREST)
        result = cpu_fn(small_img, small_depth, strength=strength, **kwargs)
        result = cv2.resize(result, (bw, bh), interpolation=cv2.INTER_LINEAR)
        print(f"[PROFILE_3D_VIZ] path=CPU(scaled) mode={mode} shape={image_bgr.shape} "
              f"proc_width={CPU_MAX_PROC_WIDTH} ms={(time.perf_counter() - _t0) * 1000:.2f}", flush=True)
        return result
    result = cpu_fn(image_bgr, depth_m, strength=strength, **kwargs)
    print(f"[PROFILE_3D_VIZ] path=CPU(full) mode={mode} shape={image_bgr.shape} "
          f"ms={(time.perf_counter() - _t0) * 1000:.2f}", flush=True)
    return result


# mode -> tensor-core GPU function, for apply_3d_visualization_fused. Only
# "relief" is refactored into a tensor-in/tensor-out core so far (the mode
# exercised this session) - fog/contours/colorize/anaglyph could get the
# same treatment later the same way, but until they are,
# apply_3d_visualization_fused falls back to the existing two-round-trip
# path for them, same as it does when either GPU isn't ready at all.
_GPU_MODE_FN_TENSOR = {
    "relief": _apply_depth_relief_gpu_tensor,
}


def apply_3d_visualization_fused(mode: str, thermal_colorized: np.ndarray, rgb_frame: np.ndarray,
                                  depth_m: np.ndarray, fusion_processor, strength: float = 0.5,
                                  **kwargs) -> np.ndarray:
    """
    Chains FusionProcessor's feature_weighted GPU blend directly into this
    module's depth-shading GPU pass without downloading the intermediate
    result to numpy and re-uploading it - the two-step alternative
    (fusion_processor.process(...) then apply_3d_visualization(...)) pays
    a full CPU<->GPU round trip for data that never needed to leave the
    GPU. Measured on this hardware: transfer (upload+download) costs
    ~11x the actual compute for these frame sizes, so eliminating one
    round trip is the real win, not a compute optimization.

    Falls back to the existing two-call path (still correct, just not
    fused) whenever either GPU path isn't ready, or mode isn't one of
    the tensor-core-refactored modes in _GPU_MODE_FN_TENSOR - this
    mirrors every other GPU path in this codebase: a pure bonus when
    available, never a requirement (see _GPU_MODE_FN_TENSOR's comment
    and the min-spec reasoning in fusion_processor.py's feature_weighted
    GPU state).

    Args:
        mode: one of THREE_D_MODES
        thermal_colorized: (H, W, 3) uint8 BGR - the palette-applied
            thermal frame (FusionProcessor's own "thermal" input)
        rgb_frame: (H, W, 3) uint8 BGR, aligned to thermal_colorized
        depth_m: (H, W) float32 depth map in meters, same resolution
        fusion_processor: the FusionProcessor instance whose
            fusion_priority/fusion_intensity drive the blend
        strength/kwargs: passed through to the depth-shading stage,
            same as apply_3d_visualization

    Returns:
        (H, W, 3) uint8 BGR - identical in shape/dtype to chaining
        fusion_processor.process() into apply_3d_visualization()
        directly, though not bit-identical: skipping the intermediate
        uint8 quantization step means the shading stage sees the blend's
        true float32 output instead of an already-8-bit-rounded copy of
        it - a strictly more precise input, not a different algorithm.
    """
    tensor_fn = _GPU_MODE_FN_TENSOR.get(mode)
    if (tensor_fn is not None
            and fusion_processor._resolve_feature_weighted_gpu()
            and _resolve_3d_gpu()):
        try:
            import torch
            _t0 = time.perf_counter()
            device = fusion_processor._fw_torch_device

            # process() normally does this resize (RealSense's RGB and
            # thermal are very likely different native resolutions, e.g.
            # 1280x800 vs a Boson's 640x512) before ever reaching
            # _feature_weighted_gpu - calling the tensor core directly
            # bypasses process() entirely, so it has to happen here
            # instead. CPU-side (cv2.warpPerspective/resize), same as it
            # always was in the two-step path - only the two GPU stages
            # are being fused, not this.
            rgb_aligned = fusion_processor.align_rgb_to_thermal(
                rgb_frame, thermal_colorized.shape[:2]
            )

            def to_tensor_chw(img):
                t = torch.from_numpy(img).to(device, dtype=torch.float32)
                return t.permute(2, 0, 1).unsqueeze(0)

            thermal_t = to_tensor_chw(thermal_colorized)
            rgb_t = to_tensor_chw(rgb_aligned)
            depth_t = torch.from_numpy(depth_m).to(device, dtype=torch.float32).unsqueeze(0).unsqueeze(0)

            base_2d_t = fusion_processor._feature_weighted_gpu_tensor(thermal_t, rgb_t)
            result_t = tensor_fn(base_2d_t, depth_t, strength, **kwargs)
            result = result_t.squeeze(0).permute(1, 2, 0).contiguous().to(torch.uint8).cpu().numpy()

            # Not throttled by frame count (this function itself is only
            # called at the caller's own throttled 3D-viz update rate,
            # same as apply_3d_visualization's own print above).
            print(f"[PROFILE_3D_VIZ_FUSED] mode={mode} shape={thermal_colorized.shape} "
                  f"ms={(time.perf_counter() - _t0) * 1000:.2f}", flush=True)
            return result
        except Exception as e:
            logger.warning(f"3D Fusion fused GPU path failed, falling back to two-step: {e}")

    fusion_rgb = fusion_processor.process(thermal_colorized, rgb_frame)
    return apply_3d_visualization(mode, fusion_rgb, depth_m, strength=strength, **kwargs)


class Fusion3DPointCloudView(QWidget):
    """
    Small live point-cloud preview embedded in the 3D Fusion settings
    panel - a verification tool for confirming RealSense depth/RGB/thermal
    are being captured and aligned correctly, not the main 3D Fusion
    feature (see apply_depth_relief for that).
    """

    # Component modes: "fusion" (RGB+thermal blend - needs thermal aligned
    # to RealSense), "rgb_only" (RealSense's own RGB+depth are natively
    # aligned by its SDK, no thermal alignment needed at all - useful to
    # verify the base depth+color pipeline independently of thermal),
    # "thermal_only" (still needs alignment).
    COLOR_MODES = ("fusion", "rgb_only", "thermal_only")

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._scatter = None
        self._gl_view = None
        self.alpha = 0.5  # 0 = all RGB, 1 = all thermal - same convention as 2D Fusion's alpha_blend
        self.color_mode = "fusion"
        self._last_reported_aligned = False
        self._camera_auto_framed = False
        self._build_ui()

    def needs_thermal_alignment(self) -> bool:
        """Whether the current color mode requires thermal aligned to RealSense at all."""
        return self.color_mode != "rgb_only"

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.setMinimumHeight(220)

        if not GL_AVAILABLE:
            placeholder = QLabel(
                "Point-cloud preview unavailable\n\n"
                "PyOpenGL is not installed.\n"
                "Install with: pip install PyOpenGL PyOpenGL_accelerate"
            )
            placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
            placeholder.setWordWrap(True)
            placeholder.setStyleSheet("color: #888888; font-size: 9pt; padding: 12px;")
            layout.addWidget(placeholder)
            return

        self._gl_view = gl.GLViewWidget()
        self._gl_view.setCameraPosition(distance=DEFAULT_CAMERA_DISTANCE, elevation=20, azimuth=45)

        grid = gl.GLGridItem()
        grid.setSize(2, 2)
        grid.setSpacing(0.2, 0.2)
        self._gl_view.addItem(grid)

        self._scatter = gl.GLScatterPlotItem(pos=np.zeros((1, 3), dtype=np.float32))
        # 'translucent' (not 'opaque') so each point renders as a smooth,
        # anti-aliased circular sprite rather than a single hard-edged
        # pixel - with alpha always 1.0 (see update_from_realsense) this
        # doesn't change the final color against the black background,
        # but should make small points read as solid dots instead of
        # faint aliased specks. Per-point color math was verified correct
        # (a controlled test with known bright colors produced the
        # expected RGB output, full alpha) - the reported "points are
        # dark" issue is a rendering visibility problem, not a data bug,
        # so this plus the larger point size below are the fix; not yet
        # confirmed against real hardware.
        self._scatter.setGLOptions('translucent')
        self._gl_view.addItem(self._scatter)

        self._no_source_label = QLabel(
            "No hardware depth sensor connected.\nConnect an Intel RealSense camera."
        )
        self._no_source_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._no_source_label.setWordWrap(True)
        self._no_source_label.setStyleSheet("color: #888888; font-size: 9pt; padding: 12px;")

        self._not_aligned_label = QLabel(
            "RealSense connected, but thermal isn't aligned.\n"
            "Enable Parallax Correction, or switch to RGB Only below."
        )
        self._not_aligned_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._not_aligned_label.setWordWrap(True)
        self._not_aligned_label.setStyleSheet("color: #cc8800; font-size: 9pt; padding: 12px;")

        layout.addWidget(self._gl_view)
        layout.addWidget(self._no_source_label)
        layout.addWidget(self._not_aligned_label)
        self._gl_view.hide()
        self._not_aligned_label.hide()

    def reset_camera(self):
        """Reset the preview to the default framing (also re-triggers auto-fit on next data)."""
        if not GL_AVAILABLE:
            return
        self._gl_view.setCameraPosition(distance=DEFAULT_CAMERA_DISTANCE, elevation=20, azimuth=45)
        self._camera_auto_framed = False

    def set_hardware_available(self, available: bool):
        """Switch to/from the 'no hardware depth' placeholder."""
        if not GL_AVAILABLE:
            return
        if available:
            self._no_source_label.hide()
        else:
            self._gl_view.hide()
            self._not_aligned_label.hide()
            self._no_source_label.show()
            self._camera_auto_framed = False

    def set_thermal_aligned(self, aligned: bool):
        """Record whether thermal is currently aligned to RealSense - see _update_alignment_visibility."""
        self._last_reported_aligned = aligned
        self._update_alignment_visibility()

    def set_color_mode(self, mode: str):
        """Change which components color the preview - see COLOR_MODES."""
        if mode not in self.COLOR_MODES:
            logger.warning(f"Unknown 3D Fusion preview color mode '{mode}', ignoring")
            return
        self.color_mode = mode
        self._update_alignment_visibility()

    def _update_alignment_visibility(self):
        if not GL_AVAILABLE:
            return
        if self._no_source_label.isVisible():
            return
        ok = self._last_reported_aligned or not self.needs_thermal_alignment()
        self._gl_view.setVisible(ok)
        self._not_aligned_label.setVisible(not ok)

    def update_point_cloud(self, vertices: np.ndarray, colors: np.ndarray):
        """
        Update the live preview point cloud.

        Args:
            vertices: (N, 3) float32 XYZ in meters
            colors: (N, 4) float32 RGBA in [0, 1]
        """
        if not GL_AVAILABLE or self._scatter is None:
            return
        if vertices.shape[0] == 0:
            return

        if not self._camera_auto_framed:
            # Frame the camera around the actual data instead of a blind
            # fixed guess - a scene's real depth range varies a lot. This
            # previously only set `distance`, leaving the orbit pivot
            # (`pos`/opts['center']) at pyqtgraph's default of the world
            # origin - RealSense point clouds are camera-space (X right,
            # Y down, Z forward from the sensor, roughly 0.3-5m out), not
            # centered anywhere near (0,0,0), so the camera was orbiting
            # around a point nowhere near the actual cloud: at the default
            # elevation/azimuth this put much of the visible geometry off
            # to one side or entirely out of frame regardless of distance,
            # which is what "wrong angle and wrong zoom" on startup was.
            centroid = np.median(vertices, axis=0)
            median_depth = float(centroid[2])
            if median_depth > 0:
                self._gl_view.setCameraPosition(
                    pos=Vector(float(centroid[0]), float(centroid[1]), float(centroid[2])),
                    distance=median_depth * 1.5,
                )
            self._camera_auto_framed = True

        self._scatter.setData(pos=vertices, color=colors, size=5.0, pxMode=True)

    def update_from_realsense(self, vertices: np.ndarray, uv: np.ndarray,
                               rgb_frame: np.ndarray, thermal_colorized: np.ndarray):
        """
        Build and display a preview point cloud from real RealSense depth,
        colored according to self.color_mode.

        uv is defined as a fraction (0-1) of RealSense's own color frame,
        per its point-cloud API contract - rgb_frame and thermal_colorized
        are sampled at that same fractional position each in their OWN
        resolution (they're very likely different: e.g. a D455's color
        stream vs. a Boson's native 640x512), not a shared pixel-coordinate
        space.

        Args:
            vertices: (N, 3) float32 XYZ in meters, from
                RGBCameraRealSense.get_point_cloud()
            uv: (N, 2) float32 texture coords in [0, 1], from the same call
            rgb_frame: RealSense color frame (H, W, 3) BGR uint8
            thermal_colorized: aligned thermal frame (H, W, 3) BGR uint8
        """
        if not GL_AVAILABLE:
            return
        if vertices.shape[0] == 0:
            self.update_point_cloud(vertices, np.zeros((0, 4), dtype=np.float32))
            return

        valid = (vertices[:, 2] > 0) & (vertices[:, 2] <= MAX_VALID_DEPTH_M)
        vertices = vertices[valid]
        uv = uv[valid]

        n = vertices.shape[0]
        if n > MAX_PREVIEW_POINTS:
            # A fixed index count (not a stride-based [::stride], whose
            # result length is ceil(n/stride) - drifting by one or more
            # points on almost every frame as the actual valid-point count
            # n fluctuates slightly with scene noise) keeps the array size
            # passed to GLScatterPlotItem.setData() constant across
            # frames. Its upload_vbo() only reuses the existing GPU
            # buffer via a cheap write() when the byte size matches
            # exactly - any size drift forces a full allocate() instead,
            # so the previous approach was reallocating the GPU vertex
            # buffer on nearly every update instead of ever reusing it.
            idx = np.linspace(0, n - 1, MAX_PREVIEW_POINTS).astype(np.int64)
            vertices = vertices[idx]
            uv = uv[idx]

        if self.color_mode == "rgb_only":
            rh, rw = rgb_frame.shape[:2]
            rpx = np.clip((uv[:, 0] * rw).astype(np.int32), 0, rw - 1)
            rpy = np.clip((uv[:, 1] * rh).astype(np.int32), 0, rh - 1)
            blended_bgr = rgb_frame[rpy, rpx].astype(np.float32) / 255.0
        elif self.color_mode == "thermal_only":
            th, tw = thermal_colorized.shape[:2]
            tpx = np.clip((uv[:, 0] * tw).astype(np.int32), 0, tw - 1)
            tpy = np.clip((uv[:, 1] * th).astype(np.int32), 0, th - 1)
            blended_bgr = thermal_colorized[tpy, tpx].astype(np.float32) / 255.0
        else:  # "fusion"
            rh, rw = rgb_frame.shape[:2]
            rpx = np.clip((uv[:, 0] * rw).astype(np.int32), 0, rw - 1)
            rpy = np.clip((uv[:, 1] * rh).astype(np.int32), 0, rh - 1)
            rgb_bgr = rgb_frame[rpy, rpx].astype(np.float32)

            th, tw = thermal_colorized.shape[:2]
            tpx = np.clip((uv[:, 0] * tw).astype(np.int32), 0, tw - 1)
            tpy = np.clip((uv[:, 1] * th).astype(np.int32), 0, th - 1)
            thermal_bgr = thermal_colorized[tpy, tpx].astype(np.float32)

            # Same lerp convention as FusionProcessor._alpha_blend: rgb + alpha*(thermal-rgb)
            blended_bgr = (rgb_bgr + self.alpha * (thermal_bgr - rgb_bgr)) / 255.0

        colors = np.ones((vertices.shape[0], 4), dtype=np.float32)
        colors[:, 0] = blended_bgr[:, 2]  # R
        colors[:, 1] = blended_bgr[:, 1]  # G
        colors[:, 2] = blended_bgr[:, 0]  # B

        self.update_point_cloud(vertices.astype(np.float32), colors)


class Fusion3DSettingsPanel(QWidget):
    """
    Right-dock '3D Fusion' tab: settings for the main viewport's
    depth-relief effect, plus a point-cloud preview to verify the
    underlying data.
    """

    strength_changed = pyqtSignal(float)
    mode_changed = pyqtSignal(str)
    data_source_changed = pyqtSignal(str)
    fog_range_changed = pyqtSignal(float, float)   # near_m, far_m
    contour_interval_changed = pyqtSignal(float)   # interval_m
    gradient_style_changed = pyqtSignal(str)       # see GRADIENT_STYLES
    fog_fade_metric_changed = pyqtSignal(str)       # see FOG_FADE_METRICS

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(10)

        self.status_label = QLabel("No hardware depth sensor connected.")
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet("color: #888888; font-size: 10pt;")
        layout.addWidget(self.status_label)

        mode_layout = QHBoxLayout()
        mode_layout.addWidget(QLabel("Mode:"))
        self.mode_combo = QComboBox()
        for mode in THREE_D_MODES:
            self.mode_combo.addItem(THREE_D_MODE_LABELS.get(mode, mode), mode)
        self.mode_combo.setToolTip(
            "Relief Shading: emboss/bump-map effect from real depth\n"
            "Depth Fog: near stays sharp, far fades to neutral gray\n"
            "Depth Contours: topographic-style lines at fixed depth intervals"
        )
        self.mode_combo.currentIndexChanged.connect(self._on_mode_combo_changed)
        mode_layout.addWidget(self.mode_combo)
        layout.addLayout(mode_layout)

        # Controls the MAIN VIEWPORT's base image directly (unlike the
        # "Components" combo further down, which only affects the small
        # point-cloud preview) - "Auto" is the safe default (Fusion only
        # when thermal is actually aligned to RealSense, else RGB Only),
        # but forcing a mode lets you compare them directly.
        source_layout = QHBoxLayout()
        source_layout.addWidget(QLabel("Data Source:"))
        self.data_source_combo = QComboBox()
        self.data_source_combo.addItem("Auto (Fusion when aligned)", "auto")
        self.data_source_combo.addItem("RGB Only", "rgb_only")
        self.data_source_combo.addItem("RGB + Thermal (Fusion)", "fusion")
        self.data_source_combo.setToolTip(
            "What the main viewport's 3D mode shades with real depth.\n"
            "Auto: Fusion when thermal is aligned to RealSense, else RGB Only.\n"
            "Forcing \"RGB + Thermal\" without alignment falls back to RGB "
            "Only anyway - thermal and RGB pixels wouldn't correspond to "
            "the same real-world points otherwise."
        )
        self.data_source_combo.currentIndexChanged.connect(
            lambda i: self.data_source_changed.emit(self.data_source_combo.itemData(i))
        )
        source_layout.addWidget(self.data_source_combo)
        layout.addLayout(source_layout)

        strength_layout = QHBoxLayout()
        strength_layout.addWidget(QLabel("Strength:"))
        self.strength_slider = QSlider(Qt.Orientation.Horizontal)
        self.strength_slider.setRange(0, 100)
        self.strength_slider.setValue(50)
        self.strength_slider.setToolTip(
            "How strongly the selected mode's effect is applied to the 2D "
            "Fusion image in the main viewport's 3D mode (0 = unchanged)"
        )
        self.strength_slider.valueChanged.connect(lambda v: self.strength_changed.emit(v / 100.0))
        strength_layout.addWidget(self.strength_slider)
        layout.addLayout(strength_layout)

        # Applies to every mode except Anaglyph (which has no depth
        # gradient - it's a stereo shift). "Color" (TURBO rainbow) is the
        # most perceptually distinguishable, but thermal already has its
        # OWN color palette encoding temperature - "Grayscale" avoids that
        # clash when fusing with a colorized thermal palette.
        self.gradient_style_row = QWidget()
        gradient_style_layout = QHBoxLayout(self.gradient_style_row)
        gradient_style_layout.setContentsMargins(0, 0, 0, 0)
        gradient_style_layout.addWidget(QLabel("Gradient Style:"))
        self.gradient_style_combo = QComboBox()
        for style in GRADIENT_STYLES:
            self.gradient_style_combo.addItem(GRADIENT_STYLE_LABELS.get(style, style), style)
        self.gradient_style_combo.setToolTip(
            "Color (Turbo): most visually distinguishable, but adds its own "
            "color meaning (hue = distance) on top of whatever the base "
            "image already shows.\n"
            "Grayscale: no hue at all - avoids clashing with a colorized "
            "thermal palette already in the base image."
        )
        self.gradient_style_combo.currentIndexChanged.connect(
            lambda i: self.gradient_style_changed.emit(self.gradient_style_combo.itemData(i))
        )
        gradient_style_layout.addWidget(self.gradient_style_combo)
        layout.addWidget(self.gradient_style_row)

        # Depth Fog tunables (near/far range, meters x10 for 0.1m slider
        # steps) - only shown when Mode is "Depth Fog".
        self.fog_params_widget = QWidget()
        fog_params_layout = QVBoxLayout(self.fog_params_widget)
        fog_params_layout.setContentsMargins(0, 0, 0, 0)
        fog_params_layout.setSpacing(4)

        fade_metric_layout = QHBoxLayout()
        fade_metric_layout.addWidget(QLabel("Fade By:"))
        self.fog_fade_metric_combo = QComboBox()
        for metric in FOG_FADE_METRICS:
            self.fog_fade_metric_combo.addItem(FOG_FADE_METRIC_LABELS.get(metric, metric), metric)
        self.fog_fade_metric_combo.setToolTip(
            "Distance: fades far objects, keeps near ones sharp (needs "
            "real depth).\n"
            "Motion: fades STATIC regions, keeps actively CHANGING ones "
            "sharp - e.g. highlighting a moving belt/fan/vibration against "
            "a static background. Needs no depth data."
        )
        self.fog_fade_metric_combo.currentIndexChanged.connect(self._on_fog_fade_metric_changed)
        fade_metric_layout.addWidget(self.fog_fade_metric_combo)
        fog_params_layout.addLayout(fade_metric_layout)

        near_layout = QHBoxLayout()
        near_layout.addWidget(QLabel("Near (m):"))
        self.fog_near_slider = QSlider(Qt.Orientation.Horizontal)
        self.fog_near_slider.setRange(1, 100)   # 0.1m - 10.0m
        self.fog_near_slider.setValue(3)        # 0.3m default
        self.fog_near_slider.setToolTip("Distance at which objects stay full contrast (closer = sharp)")
        self.fog_near_value = QLabel("0.3m")
        self.fog_near_slider.valueChanged.connect(self._on_fog_range_changed)
        near_layout.addWidget(self.fog_near_slider)
        near_layout.addWidget(self.fog_near_value)
        fog_params_layout.addLayout(near_layout)

        far_layout = QHBoxLayout()
        far_layout.addWidget(QLabel("Far (m):"))
        self.fog_far_slider = QSlider(Qt.Orientation.Horizontal)
        self.fog_far_slider.setRange(1, 100)    # 0.1m - 10.0m
        self.fog_far_slider.setValue(40)        # 4.0m default
        self.fog_far_slider.setToolTip("Distance beyond which objects are fully faded")
        self.fog_far_value = QLabel("4.0m")
        self.fog_far_slider.valueChanged.connect(self._on_fog_range_changed)
        far_layout.addWidget(self.fog_far_slider)
        far_layout.addWidget(self.fog_far_value)
        fog_params_layout.addLayout(far_layout)

        layout.addWidget(self.fog_params_widget)

        # Depth Contours tunable (line spacing) - only shown when Mode is
        # "Depth Contours".
        self.contours_params_widget = QWidget()
        contours_params_layout = QHBoxLayout(self.contours_params_widget)
        contours_params_layout.setContentsMargins(0, 0, 0, 0)
        contours_params_layout.addWidget(QLabel("Line Spacing (m):"))
        self.contour_interval_slider = QSlider(Qt.Orientation.Horizontal)
        self.contour_interval_slider.setRange(1, 50)  # 0.1m - 5.0m
        self.contour_interval_slider.setValue(5)      # 0.5m default
        self.contour_interval_slider.setToolTip("Distance between contour lines")
        self.contour_interval_value = QLabel("0.5m")
        self.contour_interval_slider.valueChanged.connect(self._on_contour_interval_changed)
        contours_params_layout.addWidget(self.contour_interval_slider)
        contours_params_layout.addWidget(self.contour_interval_value)
        layout.addWidget(self.contours_params_widget)

        # default mode is "relief" - neither mode-specific tunable widget applies
        self.fog_params_widget.hide()
        self.contours_params_widget.hide()

        note = QLabel(
            "View 3D Fusion from the main viewport's View Mode button "
            "(cycles Thermal / RGB / Fusion / Side-by-Side / PiP / 3D). "
            "Requires an active Intel RealSense camera with Parallax "
            "Correction enabled (depth method \"Intel RealSense\") - real "
            "measured depth shades the 2D Fusion image, it does not "
            "replace it."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color: #888888; font-size: 9pt; padding-top: 4px;")
        layout.addWidget(note)

        preview_label = QLabel("Point-Cloud Preview (verification only)")
        preview_label.setStyleSheet("font-weight: bold; padding-top: 8px;")
        layout.addWidget(preview_label)

        mode_layout = QHBoxLayout()
        mode_layout.addWidget(QLabel("Components:"))
        self.component_combo = QComboBox()
        self.component_combo.addItem("RGB + Thermal (Fusion)", "fusion")
        self.component_combo.addItem("RGB Only (no thermal needed)", "rgb_only")
        self.component_combo.addItem("Thermal Only", "thermal_only")
        self.component_combo.setToolTip(
            "Isolate which data colors the preview. \"RGB Only\" needs no "
            "thermal alignment at all (RealSense's own RGB+depth are "
            "natively aligned by its SDK) - useful to verify the base "
            "depth+color pipeline independently of thermal alignment."
        )
        mode_layout.addWidget(self.component_combo)
        layout.addLayout(mode_layout)

        self.point_cloud_view = Fusion3DPointCloudView()
        self.component_combo.currentIndexChanged.connect(
            lambda i: self.point_cloud_view.set_color_mode(self.component_combo.itemData(i))
        )
        layout.addWidget(self.point_cloud_view)

        reset_btn = QPushButton("Reset Preview Camera")
        reset_btn.clicked.connect(self.point_cloud_view.reset_camera)
        layout.addWidget(reset_btn)

        layout.addStretch()

    def _on_mode_combo_changed(self, index: int):
        mode = self.mode_combo.itemData(index)
        self.fog_params_widget.setVisible(mode == "fog")
        self.contours_params_widget.setVisible(mode == "contours")
        # Anaglyph is a stereo shift, not a depth gradient - Gradient
        # Style doesn't apply to it at all.
        self.gradient_style_row.setVisible(mode != "anaglyph")
        self.mode_changed.emit(mode)

    def _on_fog_fade_metric_changed(self, index: int):
        metric = self.fog_fade_metric_combo.itemData(index)
        # Near/Far only mean anything for the "distance" metric.
        is_distance = (metric == "distance")
        self.fog_near_slider.setEnabled(is_distance)
        self.fog_far_slider.setEnabled(is_distance)
        self.fog_fade_metric_changed.emit(metric)

    def _on_fog_range_changed(self, _value: int):
        near_m = self.fog_near_slider.value() / 10.0
        far_m = self.fog_far_slider.value() / 10.0
        # Near must stay below far, or apply_depth_fog's np.clip(depth, near, far)
        # would silently treat the whole range as invalid.
        if near_m >= far_m:
            far_m = near_m + 0.1
            self._block_fog_signal = True
            self.fog_far_slider.setValue(int(far_m * 10))
            self._block_fog_signal = False
        self.fog_near_value.setText(f"{near_m:.1f}m")
        self.fog_far_value.setText(f"{far_m:.1f}m")
        if not getattr(self, '_block_fog_signal', False):
            self.fog_range_changed.emit(near_m, far_m)

    def _on_contour_interval_changed(self, value: int):
        interval_m = value / 10.0
        self.contour_interval_value.setText(f"{interval_m:.1f}m")
        self.contour_interval_changed.emit(interval_m)

    def set_status(self, hardware_available: bool, thermal_aligned: bool):
        if not hardware_available:
            self.status_label.setText("No hardware depth sensor connected.")
            self.status_label.setStyleSheet("color: #888888; font-size: 10pt;")
        elif not thermal_aligned:
            self.status_label.setText(
                "RealSense connected, but thermal isn't aligned to it. Enable "
                "Parallax Correction (or set a manual shift) with Correction "
                "Target set to \"Thermal\" - depth method \"Intel RealSense\" "
                "only helps if Correction Target is also \"Thermal\": "
                "\"RGB\" warps the RGB frame away from RealSense's own "
                "native depth alignment."
            )
            self.status_label.setStyleSheet("color: #cc8800; font-size: 10pt;")
        else:
            self.status_label.setText("Live: real depth shading the 2D Fusion image.")
            self.status_label.setStyleSheet("color: #4CAF50; font-size: 10pt;")

        self.point_cloud_view.set_hardware_available(hardware_available)
        self.point_cloud_view.set_thermal_aligned(thermal_aligned)
