"""
3D Fusion panel - live, rotatable point-cloud view combining real hardware
depth (Intel RealSense), its own RGB texture, and thermal color: a genuine
3D-enhanced view of the world, not just a thermal-colored point cloud.
Each point is colored by an alpha blend of the RealSense color frame and
the aligned thermal frame at that point's texture coordinate, same
blend convention as 2D Fusion's alpha_blend mode (0 = all RGB, 1 = all
thermal).

Deliberately gated on real measured depth only. Parallax correction's
"simplified"/MiDaS/DepthAnything depth methods are estimation heuristics
that exist to correct for the fact that no two cameras can be perfectly
mechanically aligned - they are not accurate enough to present as an actual
3D reconstruction, and doing so would be exactly the kind of "looks
plausible but isn't real" visualization this project avoids elsewhere
(see e.g. radiometric calibration handling). This panel shows a clear
placeholder instead of a point cloud whenever no hardware depth source is
active - it never falls back to an estimated depth map.
"""
from __future__ import annotations

import logging
from typing import Optional

import numpy as np
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSlider
from PyQt6.QtCore import Qt

logger = logging.getLogger(__name__)

try:
    import pyqtgraph.opengl as gl
    GL_AVAILABLE = True
except ImportError:
    GL_AVAILABLE = False
    logger.info("pyqtgraph.opengl not available (PyOpenGL not installed) - 3D Fusion view disabled")
    logger.info("Install with: pip install PyOpenGL PyOpenGL_accelerate")

# Point budget for real-time GLScatterPlotItem updates - a RealSense depth
# frame can have 300k+ valid points at full resolution; redrawing that many
# every frame is not real-time on typical hardware, so the cloud is
# stride-subsampled down to roughly this many points before each update.
MAX_POINTS = 40000


class Fusion3DPanel(QWidget):
    """Live rotatable 3D point-cloud view, RGB+thermal blended, from real hardware depth."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._has_hardware_depth = False
        self._scatter = None
        self._gl_view = None
        self._alpha = 0.5  # 0 = all RGB, 1 = all thermal - same convention as 2D Fusion's alpha_blend
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        if not GL_AVAILABLE:
            placeholder = QLabel(
                "3D Fusion view unavailable\n\n"
                "PyOpenGL is not installed.\n"
                "Install with: pip install PyOpenGL PyOpenGL_accelerate"
            )
            placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
            placeholder.setStyleSheet("color: #888888; font-size: 11pt; padding: 24px;")
            layout.addWidget(placeholder)
            return

        self._gl_view = gl.GLViewWidget()
        self._gl_view.setCameraPosition(distance=2.0, elevation=20, azimuth=45)

        grid = gl.GLGridItem()
        grid.setSize(2, 2)
        grid.setSpacing(0.2, 0.2)
        self._gl_view.addItem(grid)

        self._scatter = gl.GLScatterPlotItem(pos=np.zeros((1, 3), dtype=np.float32))
        self._scatter.setGLOptions('opaque')
        self._gl_view.addItem(self._scatter)

        alpha_layout = QHBoxLayout()
        alpha_layout.addWidget(QLabel("RGB"))
        self._alpha_slider = QSlider(Qt.Orientation.Horizontal)
        self._alpha_slider.setRange(0, 100)
        self._alpha_slider.setValue(int(self._alpha * 100))
        self._alpha_slider.setToolTip(
            "Blend between RGB texture and thermal color for each point "
            "(same as 2D Fusion's Alpha)"
        )
        self._alpha_slider.valueChanged.connect(self._on_alpha_changed)
        alpha_layout.addWidget(self._alpha_slider)
        alpha_layout.addWidget(QLabel("Thermal"))

        self._no_source_label = QLabel(
            "No hardware depth sensor connected.\n\n"
            "Connect an Intel RealSense camera to see a live 3D view here.\n"
            "This view intentionally does not use estimated depth "
            "(simplified/MiDaS/DepthAnything) - those exist to correct "
            "camera misalignment, not to reconstruct real 3D geometry."
        )
        self._no_source_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._no_source_label.setStyleSheet("color: #888888; font-size: 11pt; padding: 24px;")

        layout.addWidget(self._gl_view)
        layout.addLayout(alpha_layout)
        layout.addWidget(self._no_source_label)
        self._gl_view.hide()

    def _on_alpha_changed(self, value: int):
        self._alpha = value / 100.0

    def set_hardware_available(self, available: bool):
        """Switch between the live GL view and the 'no hardware depth' placeholder."""
        if not GL_AVAILABLE:
            return
        self._has_hardware_depth = available
        self._gl_view.setVisible(available)
        self._no_source_label.setVisible(not available)

    def update_point_cloud(self, vertices: np.ndarray, colors: np.ndarray):
        """
        Update the live point cloud.

        Args:
            vertices: (N, 3) float32 XYZ in meters
            colors: (N, 4) float32 RGBA in [0, 1]
        """
        if not GL_AVAILABLE or self._scatter is None:
            return
        if vertices.shape[0] == 0:
            return
        self._scatter.setData(pos=vertices, color=colors, size=2.0, pxMode=True)

    def update_from_realsense(self, vertices: np.ndarray, uv: np.ndarray,
                               rgb_frame: np.ndarray, thermal_colorized: np.ndarray):
        """
        Build and display a point cloud from real RealSense depth, colored
        by an alpha blend of the RealSense color frame and the aligned
        thermal frame at each point's texture coordinate - a genuine
        RGB+thermal 3D view, not a thermal-only point cloud. uv indexes
        both frames identically: RealSense's own color frame (what its
        point cloud's texture coordinates are defined against) and the
        thermal frame after parallax correction has warped it to match
        that same RGB perspective/grid.

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

        # Drop points with no valid depth (RealSense reports these as the
        # origin) before subsampling, so the point budget isn't spent on
        # points that wouldn't be drawn anyway.
        valid = vertices[:, 2] > 0
        vertices = vertices[valid]
        uv = uv[valid]

        n = vertices.shape[0]
        if n > MAX_POINTS:
            stride = n // MAX_POINTS
            vertices = vertices[::stride]
            uv = uv[::stride]

        h, w = thermal_colorized.shape[:2]
        px = np.clip((uv[:, 0] * w).astype(np.int32), 0, w - 1)
        py = np.clip((uv[:, 1] * h).astype(np.int32), 0, h - 1)

        rgb_bgr = rgb_frame[py, px].astype(np.float32)
        thermal_bgr = thermal_colorized[py, px].astype(np.float32)
        # Same lerp convention as FusionProcessor._alpha_blend: rgb + alpha*(thermal-rgb)
        blended_bgr = (rgb_bgr + self._alpha * (thermal_bgr - rgb_bgr)) / 255.0

        colors = np.ones((vertices.shape[0], 4), dtype=np.float32)
        colors[:, 0] = blended_bgr[:, 2]  # R
        colors[:, 1] = blended_bgr[:, 1]  # G
        colors[:, 2] = blended_bgr[:, 0]  # B

        self.update_point_cloud(vertices.astype(np.float32), colors)
