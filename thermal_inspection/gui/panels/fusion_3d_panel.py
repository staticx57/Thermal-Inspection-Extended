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
from typing import Optional

import cv2
import numpy as np
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSlider, QComboBox, QPushButton
)
from PyQt6.QtCore import Qt, pyqtSignal

logger = logging.getLogger(__name__)

try:
    import pyqtgraph.opengl as gl
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
THREE_D_MODES = ["relief", "fog", "contours"]
THREE_D_MODE_LABELS = {
    "relief": "Relief Shading",
    "fog": "Depth Fog",
    "contours": "Depth Contours",
}


def apply_depth_relief(image_bgr: np.ndarray, depth_m: np.ndarray, strength: float = 0.5) -> np.ndarray:
    """
    Shade a BGR image using real depth-derived surface normals - an
    emboss/bump-map effect giving edges and surfaces a subtle 3D-relief
    look driven by real measured geometry, not RGB edge structure (compare
    FusionProcessor._relief_fusion, which embosses RGB gradients instead).

    Args:
        image_bgr: base image to shade (H, W, 3) uint8 - typically the 2D
            Fusion RGB+thermal blend, but works with any BGR image the same
            resolution as depth_m
        depth_m: depth map in meters (H, W) float32, same resolution as
            image_bgr (resize first if not - see caller)
        strength: 0 = no effect (image unchanged), 1 = strong relief

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
    return result.astype(np.uint8)


def apply_depth_fog(image_bgr: np.ndarray, depth_m: np.ndarray, strength: float = 0.5,
                     near_m: float = 0.3, far_m: float = 4.0) -> np.ndarray:
    """
    Fade the image toward neutral gray as real measured depth increases -
    near objects stay full contrast, far ones fade out, drawing the eye to
    close-range detail using real distance rather than RGB/thermal
    contrast alone.

    Args:
        image_bgr: base image to fade (H, W, 3) uint8
        depth_m: depth map in meters (H, W) float32, same resolution
        strength: 0 = no effect, 1 = far objects fade to fully neutral gray
        near_m/far_m: depth range the fade spans (meters) - closer than
            near_m stays full contrast, farther than far_m is fully faded

    Returns:
        Faded BGR uint8 image, same shape as image_bgr
    """
    depth = np.clip(depth_m, near_m, far_m)
    depth -= near_m
    depth /= max(far_m - near_m, 1e-6)
    depth *= max(0.0, min(1.0, strength))  # fade amount per pixel, 0-1

    fade_3ch = depth[:, :, np.newaxis]
    result = image_bgr.astype(np.float32)
    result *= (1.0 - fade_3ch)
    result += 128.0 * fade_3ch  # blend toward neutral mid-gray
    np.clip(result, 0, 255, out=result)
    return result.astype(np.uint8)


def apply_depth_contours(image_bgr: np.ndarray, depth_m: np.ndarray, strength: float = 0.5,
                          interval_m: float = 0.5) -> np.ndarray:
    """
    Overlay topographic-style contour lines at fixed real-depth intervals -
    communicates distance bands explicitly without altering the base
    image's overall brightness/color the way relief/fog do.

    Args:
        image_bgr: base image to draw on (H, W, 3) uint8
        depth_m: depth map in meters (H, W) float32, same resolution
        strength: 0 = no lines, 1 = fully opaque contour lines
        interval_m: spacing between contour lines, in meters

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
    contour_color = np.array([255, 255, 0], dtype=np.float32)  # cyan (BGR)
    blended = result[edges].astype(np.float32)
    blended *= (1.0 - strength)
    blended += contour_color * strength
    result[edges] = np.clip(blended, 0, 255).astype(np.uint8)
    return result


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
        self._scatter.setGLOptions('opaque')
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
            # fixed guess - a scene's real depth range varies a lot.
            median_depth = float(np.median(vertices[:, 2]))
            if median_depth > 0:
                self._gl_view.setCameraPosition(distance=median_depth * 2.0)
            self._camera_auto_framed = True

        self._scatter.setData(pos=vertices, color=colors, size=2.0, pxMode=True)

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
            stride = n // MAX_PREVIEW_POINTS
            vertices = vertices[::stride]
            uv = uv[::stride]

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
        self.mode_combo.currentIndexChanged.connect(
            lambda i: self.mode_changed.emit(self.mode_combo.itemData(i))
        )
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

    def set_status(self, hardware_available: bool, thermal_aligned: bool):
        if not hardware_available:
            self.status_label.setText("No hardware depth sensor connected.")
            self.status_label.setStyleSheet("color: #888888; font-size: 10pt;")
        elif not thermal_aligned:
            self.status_label.setText(
                "RealSense connected, but thermal isn't aligned to it. "
                "Enable Parallax Correction (depth method \"Intel RealSense\")."
            )
            self.status_label.setStyleSheet("color: #cc8800; font-size: 10pt;")
        else:
            self.status_label.setText("Live: real depth shading the 2D Fusion image.")
            self.status_label.setStyleSheet("color: #4CAF50; font-size: 10pt;")

        self.point_cloud_view.set_hardware_available(hardware_available)
        self.point_cloud_view.set_thermal_aligned(thermal_aligned)
