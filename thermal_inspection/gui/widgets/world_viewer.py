"""
3D world viewer for 3D Mapping mode: shows the mapped world full-size in the main view and is where you interact with
it - click a point to read its temperature, measure between two points, jump to hotspots, see the camera.

Coordinates: the world uses the first camera's frame (x right, y DOWN, z forward). The GL scene is drawn with z up, so
everything handed to GL goes through to_gl(); everything emitted to callers is in world coordinates.

All picking maths are plain functions (no GL context needed) so they can be unit-tested headless.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

import numpy as np
from PyQt6.QtCore import QPointF, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QImage, QPixmap
from PyQt6.QtWidgets import (
    QCheckBox, QFrame, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QVBoxLayout, QWidget
)

from thermal_inspection.processing import world_units

try:
    import pyqtgraph.opengl as gl
    from pyqtgraph import Vector
    GL_AVAILABLE = True
except Exception:       # pragma: no cover - depends on the install
    GL_AVAILABLE = False

PICK_RADIUS_PX = 12.0       # how close a click must be to a point to pick it
SNAP_RADIUS_PX = 22.0       # ... and to a hotspot marker, which wins over a plain point when snapping is on
CLICK_MOVE_TOLERANCE_PX = 4.0

MARKER_COLORS = {"hot": (1.0, 0.45, 0.1, 1.0), "warm": (1.0, 0.2, 0.2, 1.0), "cool": (0.3, 0.6, 1.0, 1.0)}
QUALITY_COLORS = {"good": (0.2, 0.9, 0.3, 1.0), "degraded": (1.0, 0.8, 0.1, 1.0),
                  "lost": (1.0, 0.2, 0.2, 1.0), "n/a": (0.6, 0.6, 0.6, 1.0)}


# ------------------------------------------------------------------ pure helpers

def overlay_gl_options():
    """GL state for things drawn ON TOP of the cloud (markers, labels, selection): blended, no depth test - they sit at
    the same depth as the surface points they mark and would otherwise be hidden by them."""
    from OpenGL import GL
    return {GL.GL_DEPTH_TEST: False, GL.GL_BLEND: True, GL.GL_ALPHA_TEST: False, GL.GL_CULL_FACE: False,
            "glBlendFunc": (GL.GL_SRC_ALPHA, GL.GL_ONE_MINUS_SRC_ALPHA)}


def to_gl(points) -> np.ndarray:
    """World (x right, y down, z forward) -> GL scene (x right, y forward, z up). Accepts (3,) or (N,3)."""
    p = np.asarray(points, dtype=np.float32)
    if p.ndim == 1:
        return np.array([p[0], p[2], -p[1]], dtype=np.float32)
    return np.stack([p[:, 0], p[:, 2], -p[:, 1]], axis=1)


def from_gl(points) -> np.ndarray:
    p = np.asarray(points, dtype=np.float64)
    if p.ndim == 1:
        return np.array([p[0], -p[2], p[1]])
    return np.stack([p[:, 0], -p[:, 2], p[:, 1]], axis=1)


def matrix_to_numpy(qmatrix) -> np.ndarray:
    """QMatrix4x4 -> 4x4 numpy (Qt stores column-major)."""
    return np.array(qmatrix.data(), dtype=np.float64).reshape(4, 4).T


def project_to_screen(points: np.ndarray, mvp: np.ndarray, width: float, height: float):
    """Project (N,3) scene points with a model-view-projection matrix. Returns (xy (N,2) pixels with y down, depth (N,),
    visible (N,) bool). Points behind the camera or outside the clip volume are not visible."""
    pts = np.asarray(points, dtype=np.float64)
    h = np.concatenate([pts, np.ones((len(pts), 1))], axis=1)
    clip = h @ mvp.T
    w = clip[:, 3]
    ok = w > 1e-9
    safe_w = np.where(ok, w, 1.0)
    ndc = clip[:, :3] / safe_w[:, None]
    visible = ok & (np.abs(ndc[:, 0]) <= 1.0) & (np.abs(ndc[:, 1]) <= 1.0) & (ndc[:, 2] >= -1.0) & (ndc[:, 2] <= 1.0)
    x = (ndc[:, 0] * 0.5 + 0.5) * width
    y = (1.0 - (ndc[:, 1] * 0.5 + 0.5)) * height
    return np.stack([x, y], axis=1), w, visible


def pick_nearest(points: np.ndarray, mvp: np.ndarray, size: Tuple[float, float], cursor: Tuple[float, float],
                 radius: float = PICK_RADIUS_PX) -> Optional[int]:
    """Index (into `points`) of the point whose screen position is nearest the cursor within `radius` px, or None.
    Among points about equally close to the cursor, the one nearer the camera wins (cheap occlusion: you pick the
    surface you see, not the one behind it)."""
    if len(points) == 0:
        return None
    xy, depth, visible = project_to_screen(points, mvp, size[0], size[1])
    d = np.hypot(xy[:, 0] - cursor[0], xy[:, 1] - cursor[1])
    d = np.where(visible, d, np.inf)
    best = float(d.min())
    if not np.isfinite(best) or best > radius:
        return None
    near = np.where(d <= best + 2.0)[0]
    return int(near[np.argmin(depth[near])])


@dataclass(frozen=True)
class PickResult:
    index: int                      # full-world point index
    xyz: Tuple[float, float, float]  # world coordinates
    source: str                     # 'marker' | 'cloud'


def resolve_pick(points_gl: np.ndarray, indices: np.ndarray, markers: Sequence, mvp: np.ndarray,
                 size: Tuple[float, float], cursor: Tuple[float, float], snap: bool = True,
                 radius: float = PICK_RADIUS_PX, snap_radius: float = SNAP_RADIUS_PX) -> Optional[PickResult]:
    """What did a click at `cursor` hit? With snapping on, a hotspot marker within snap_radius px wins over any plain
    point; otherwise the nearest drawn point within radius. `markers` are processing.world_thermal.Marker."""
    if snap and len(markers):
        mpts = to_gl(np.array([m.xyz for m in markers], dtype=np.float64))
        k = pick_nearest(mpts, mvp, size, cursor, snap_radius)
        if k is not None:
            m = markers[k]
            return PickResult(int(m.index), tuple(m.xyz), "marker")
    if len(points_gl) == 0:
        return None
    k = pick_nearest(points_gl, mvp, size, cursor, radius)
    if k is None:
        return None
    return PickResult(int(indices[k]), tuple(from_gl(points_gl[k])), "cloud")


def frustum_lines(pose: np.ndarray, size: float = 0.2) -> np.ndarray:
    """Line-segment endpoints (pairs) of a small camera frustum for `pose` (camera-to-world), in GL coordinates."""
    hw, hh = size * 0.6, size * 0.45
    corners_cam = np.array([[-hw, -hh, size], [hw, -hh, size], [hw, hh, size], [-hw, hh, size]])
    R, t = np.asarray(pose)[:3, :3], np.asarray(pose)[:3, 3]
    corners = corners_cam @ R.T + t
    segs = []
    for c in corners:
        segs += [t, c]
    for a, b in ((0, 1), (1, 2), (2, 3), (3, 0)):
        segs += [corners[a], corners[b]]
    return to_gl(np.array(segs))


def gradient_image(mode: str, height: int = 160, width: int = 14) -> QImage:
    """Colour-scale strip for the legend, matching WorldThermalLayer.colorize (top = high)."""
    import cv2
    ramp = np.linspace(1.0, 0.0, height)
    if mode == "change":
        x = ramp * 2 - 1
        r = np.where(x > 0, 1.0, 1.0 + x)
        b = np.where(x < 0, 1.0, 1.0 - x)
        g = 1.0 - np.abs(x)
        rgb = (np.stack([r, g, b], axis=1) * 255).astype(np.uint8)
    else:
        bgr = cv2.applyColorMap((ramp * 255).astype(np.uint8).reshape(-1, 1), cv2.COLORMAP_INFERNO).reshape(-1, 3)
        rgb = bgr[:, ::-1].copy()
    strip = np.ascontiguousarray(np.repeat(rgb[:, None, :], width, axis=1))
    img = QImage(strip.data, width, height, width * 3, QImage.Format.Format_RGB888)
    return img.copy()           # detach from the numpy buffer


# ------------------------------------------------------------------ widget

class WorldViewer(QWidget):
    probe_requested = pyqtSignal(int)               # full-world index of the clicked point
    measure_completed = pyqtSignal(int, int)        # full-world indices A, B
    measure_mode_changed = pyqtSignal(bool)
    snap_changed = pyqtSignal(bool)
    reset_view_requested = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._points_gl = np.zeros((0, 3), np.float32)
        self._indices = np.zeros(0, np.int64)
        self._markers: list = []
        self._measure_a: Optional[PickResult] = None
        self._measure_b: Optional[PickResult] = None
        self._selected: Optional[PickResult] = None
        self._camera_framed = False
        self._camera_pos_gl = None          # latest camera position (GL coords), included when framing the view
        self._framed_with_camera = False
        self._press = None
        self._view = None
        self._build_ui()

    # ---- construction ----------------------------------------------------------------------------------------

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(2)

        bar = QHBoxLayout()
        self._measure_check = QPushButton("Measure")
        self._measure_check.setCheckable(True)
        self._measure_check.setToolTip("Click two points to measure the distance between them (Esc cancels)")
        self._measure_check.toggled.connect(self._on_measure_toggled)
        self._snap_check = QCheckBox("Snap to hotspots")
        self._snap_check.setChecked(True)
        self._snap_check.setToolTip("Clicks near a hotspot marker pick that marker's point exactly")
        self._snap_check.toggled.connect(self.snap_changed.emit)
        self._reset_button = QPushButton("Reset view")
        self._reset_button.clicked.connect(self.reset_view)
        bar.addWidget(self._measure_check)
        bar.addWidget(self._snap_check)
        bar.addStretch(1)
        bar.addWidget(self._reset_button)
        root.addLayout(bar)

        if not GL_AVAILABLE:
            msg = QLabel("3D view unavailable\n\nPyOpenGL is not installed.\nInstall with: pip install PyOpenGL PyOpenGL_accelerate")
            msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
            root.addWidget(msg, 1)
            self._build_overlays(self)
            return

        self._view = _PickingView()
        self._view.setCameraPosition(distance=4.0, elevation=20, azimuth=-90)
        self._view.clicked.connect(self._on_click)
        self._cloud = gl.GLScatterPlotItem(pos=np.zeros((1, 3), np.float32))
        self._cloud.setGLOptions("translucent")
        self._view.addItem(self._cloud)
        self._marker_halo = gl.GLScatterPlotItem(pos=np.zeros((0, 3), np.float32), size=24, pxMode=True,
                                                 color=(1, 1, 1, 0.9))
        self._marker_halo.setGLOptions(overlay_gl_options())
        self._marker_halo.setDepthValue(10)
        self._view.addItem(self._marker_halo)
        self._marker_item = gl.GLScatterPlotItem(pos=np.zeros((0, 3), np.float32), size=16, pxMode=True)
        self._marker_item.setGLOptions(overlay_gl_options())
        self._marker_item.setDepthValue(11)
        self._view.addItem(self._marker_item)
        self._select_item = gl.GLScatterPlotItem(pos=np.zeros((0, 3), np.float32), size=18, pxMode=True,
                                                 color=(1, 1, 1, 1))
        self._select_item.setGLOptions(overlay_gl_options())
        self._select_item.setDepthValue(12)
        self._view.addItem(self._select_item)
        self._measure_line = gl.GLLinePlotItem(pos=np.zeros((0, 3), np.float32), width=3, color=(1, 1, 0.2, 1))
        self._measure_line.setGLOptions(overlay_gl_options())
        self._measure_line.setDepthValue(12)
        self._view.addItem(self._measure_line)
        self._camera_item = gl.GLLinePlotItem(pos=np.zeros((0, 3), np.float32), width=2, mode="lines",
                                              color=QUALITY_COLORS["n/a"])
        self._view.addItem(self._camera_item)
        self._marker_labels: list = []
        self._label_timer = QTimer(self)
        self._label_timer.setInterval(33)
        self._label_timer.timeout.connect(self._update_marker_labels)
        root.addWidget(self._view, 1)
        self._build_overlays(self._view)

    def _build_overlays(self, host: QWidget):
        self._card = QLabel(host)
        self._card.setWordWrap(True)
        self._card.setStyleSheet("background: rgba(20,20,20,200); color: #eee; padding: 8px; border-radius: 6px;")
        self._card.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._card.hide()
        self._legend = QFrame(host)
        self._legend.setStyleSheet("background: rgba(20,20,20,170); border-radius: 6px;")
        self._legend.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        lay = QVBoxLayout(self._legend)
        lay.setContentsMargins(6, 6, 6, 6)
        self._legend_hi = QLabel("")
        self._legend_bar = QLabel("")
        self._legend_lo = QLabel("")
        for lab in (self._legend_hi, self._legend_lo):
            lab.setStyleSheet("color: #eee; background: transparent;")
        self._legend_bar.setStyleSheet("background: transparent;")
        lay.addWidget(self._legend_hi)
        lay.addWidget(self._legend_bar, 0, Qt.AlignmentFlag.AlignHCenter)
        lay.addWidget(self._legend_lo)
        self._legend.hide()
        self._inset = QLabel(host)
        self._inset.setStyleSheet("border: 2px solid rgba(255,255,255,160); background: black;")
        self._inset.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._inset.hide()
        self._hint = QLabel("", host)
        self._hint.setStyleSheet("background: rgba(20,20,20,170); color: #ddd; padding: 4px 8px; border-radius: 4px;")
        self._hint.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._hint.hide()
        self._host = host
        self._card_source = None             # ('probe'|'measure', result) so a unit change can re-render it
        self._unit = "C"
        host.installEventFilter(self)

    def eventFilter(self, obj, event):
        from PyQt6.QtCore import QEvent
        if obj is self._host and event.type() == QEvent.Type.Resize:
            self._layout_overlays()
        return super().eventFilter(obj, event)

    def _layout_overlays(self):
        w, h = self._host.width(), self._host.height()
        self._card.setFixedWidth(min(340, max(160, w // 2)))
        self._card.adjustSize()
        self._card.move(10, 10)
        self._legend.adjustSize()
        self._legend.move(w - self._legend.width() - 10, 10)
        iw = min(240, max(120, w // 4))
        ih = int(iw * 0.75)
        self._inset.setFixedSize(iw, ih)
        self._inset.move(w - iw - 10, h - ih - 10)
        self._hint.adjustSize()
        self._hint.move(10, h - self._hint.height() - 10)

    # ---- data in -----------------------------------------------------------------------------------------------

    def set_world(self, points: np.ndarray, colors: np.ndarray, indices: Optional[np.ndarray] = None):
        """points (N,3) world coords, colors (N,3|4) float 0-1, indices (N,) full-world index of each point."""
        n = len(points)
        self._indices = np.arange(n, dtype=np.int64) if indices is None else np.asarray(indices, dtype=np.int64)
        self._points_gl = to_gl(points) if n else np.zeros((0, 3), np.float32)
        if self._view is None or n == 0:
            return
        c = np.asarray(colors, dtype=np.float32)
        if c.shape[1] == 3:
            c = np.concatenate([c, np.ones((n, 1), np.float32)], axis=1)
        if not self._camera_framed:
            self._frame(self._points_gl)
        self._cloud.setData(pos=self._points_gl, color=c, size=3.0, pxMode=True)

    def _frame(self, pts_gl: np.ndarray):
        if self._view is None or len(pts_gl) == 0:
            return
        lo, hi = np.percentile(pts_gl, 2, axis=0), np.percentile(pts_gl, 98, axis=0)
        if self._camera_pos_gl is not None:             # keep the camera marker in frame too
            lo, hi = np.minimum(lo, self._camera_pos_gl), np.maximum(hi, self._camera_pos_gl)
            self._framed_with_camera = True
        centre = (lo + hi) / 2
        radius = float(np.linalg.norm(hi - lo)) / 2
        self._view.setCameraPosition(pos=Vector(*[float(v) for v in centre]), distance=max(1.0, radius * 2.4),
                                     elevation=20, azimuth=-90)
        self._camera_framed = True

    def reset_view(self):
        self._camera_framed = False
        self._frame(self._points_gl)
        self.reset_view_requested.emit()

    def fly_to(self, xyz):
        """Re-centre the orbit on a world point (keeps the current zoom and angles)."""
        if self._view is None:
            return
        c = to_gl(np.asarray(xyz, dtype=np.float64))
        self._view.opts["center"] = Vector(float(c[0]), float(c[1]), float(c[2]))
        self._view.update()

    def set_camera_pose(self, pose: Optional[np.ndarray], quality_state: str = "n/a"):
        if self._view is None:
            return
        if pose is None:
            self._camera_item.setData(pos=np.zeros((0, 3), np.float32))
            return
        self._camera_pos_gl = to_gl(np.asarray(pose)[:3, 3])
        self._camera_item.setData(pos=frustum_lines(pose), color=QUALITY_COLORS.get(quality_state, QUALITY_COLORS["n/a"]))
        if not self._framed_with_camera and len(self._points_gl):
            self._frame(self._points_gl)                # first pose: re-frame once so the camera is visible

    def set_markers(self, markers: list):
        """Hotspot/change markers (processing.world_thermal.Marker): drawn as coloured dots with labels."""
        self._markers = list(markers)
        if self._view is None:
            return
        for lab in self._marker_labels:
            lab.deleteLater()
        self._marker_labels = []
        if not self._markers:
            self._label_timer.stop()
            self._marker_item.setData(pos=np.zeros((0, 3), np.float32))
            self._marker_halo.setData(pos=np.zeros((0, 3), np.float32))
            return
        pos = to_gl(np.array([m.xyz for m in self._markers], dtype=np.float64))
        self._marker_halo.setData(pos=pos, color=(1, 1, 1, 0.9), size=24, pxMode=True)
        col = np.array([MARKER_COLORS.get(m.kind, (1, 1, 1, 1)) for m in self._markers], dtype=np.float32)
        self._marker_item.setData(pos=pos, color=col, size=14, pxMode=True)
        for m in self._markers:
            lab = QLabel(m.label, self._view)
            r, g, b = (int(c * 255) for c in MARKER_COLORS.get(m.kind, (1, 1, 1, 1))[:3])
            lab.setStyleSheet(f"background: rgba(20,20,20,200); color: rgb({r},{g},{b}); font-weight: bold; "
                              "padding: 1px 5px; border-radius: 4px;")
            lab.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            lab.adjustSize()
            lab.show()
            self._marker_labels.append(lab)
        self._label_timer.start()
        self._update_marker_labels()

    def _update_marker_labels(self):
        """Place each marker's label beside its projected position (hidden when the marker is off-screen/behind)."""
        if self._view is None or not self._marker_labels:
            return
        mvp, size = self._current_mvp()
        pts = to_gl(np.array([m.xyz for m in self._markers], dtype=np.float64))
        xy, _, visible = project_to_screen(pts, mvp, *size)
        for lab, (x, y), ok in zip(self._marker_labels, xy, visible):
            lab.setVisible(bool(ok))
            if ok:
                lab.move(int(x) + 12, int(y) - lab.height() - 4)

    def set_unit(self, unit: str):
        """The app's temperature unit changed: re-render the open info card in it."""
        if unit == self._unit:
            return
        self._unit = unit
        if self._card_source is not None:
            kind, result = self._card_source
            (self.show_probe if kind == "probe" else self.show_measure)(result, unit)

    def set_legend(self, mode: str, lo: Optional[float], hi: Optional[float], unit: str = "C"):
        """Colour scale for temperature/peak/change modes; lo/hi in degrees C (a difference for 'change'). None hides it."""
        if lo is None or hi is None or mode == "colour":
            self._legend.hide()
            return
        if mode == "change":
            top, bottom = world_units.format_delta(hi, unit), world_units.format_delta(lo, unit)
        else:
            top, bottom = world_units.format_temp(hi, unit), world_units.format_temp(lo, unit)
        self._legend_hi.setText(top)
        self._legend_lo.setText(bottom)
        self._legend_bar.setPixmap(QPixmap.fromImage(gradient_image(mode)))
        self._legend.show()
        self._layout_overlays()

    def set_inset(self, frame_bgr: Optional[np.ndarray]):
        """Small live RGB picture in the corner (None hides it)."""
        if frame_bgr is None:
            self._inset.hide()
            return
        import cv2
        rgb = np.ascontiguousarray(cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB))
        h, w = rgb.shape[:2]
        img = QImage(rgb.data, w, h, w * 3, QImage.Format.Format_RGB888).copy()
        self._inset.setPixmap(QPixmap.fromImage(img).scaled(
            self._inset.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        self._inset.show()

    # ---- results in --------------------------------------------------------------------------------------------

    def show_probe(self, result, unit: str = "C"):
        """Info card for a ProbeResult (None clears it)."""
        self._card_source = ("probe", result) if result is not None else None
        self._unit = unit
        if result is None:
            self._card.hide()
            return
        x, y, z = result.xyz
        lines = [f"<b>Point</b> ({x:+.2f}, {y:+.2f}, {z:+.2f}) m"]
        if result.distance_from_camera is not None:
            lines.append(f"{world_units.format_distance(result.distance_from_camera)} from the camera")
        if result.has_temp:
            if result.temp is not None:
                lines.append(f"Temperature: <b>{world_units.format_temp(result.temp, unit)}</b>")
            if result.peak is not None:
                lines.append(f"Peak: {world_units.format_temp(result.peak, unit)}")
            if result.change is not None:
                lines.append(f"Change vs loaded world: {world_units.format_delta(result.change, unit)}")
        else:
            lines.append("No temperature recorded here")
        self._card.setText("<br>".join(lines))
        self._card.show()
        self._layout_overlays()

    def show_measure(self, result, unit: str = "C"):
        """Info card for a MeasureResult."""
        self._card_source = ("measure", result) if result is not None else None
        self._unit = unit
        if result is None:
            self._card.hide()
            return
        lines = [f"<b>Distance</b> {world_units.format_distance(result.distance_m)}"]
        if result.delta_temp is not None:
            lines.append(f"Temperature difference (B - A): {world_units.format_delta(result.delta_temp, unit)}")
        self._card.setText("<br>".join(lines))
        self._card.show()
        self._layout_overlays()

    # ---- interaction -------------------------------------------------------------------------------------------

    @property
    def measure_mode(self) -> bool:
        return self._measure_check.isChecked()

    @property
    def snap_enabled(self) -> bool:
        return self._snap_check.isChecked()

    def set_snap_enabled(self, on: bool):
        self._snap_check.setChecked(bool(on))

    def set_measure_mode(self, on: bool):
        self._measure_check.setChecked(bool(on))

    def _on_measure_toggled(self, on: bool):
        self._clear_measure()
        self._hint.setText("Measure: click the first point (Esc cancels)" if on else "")
        self._hint.setVisible(on)
        self._layout_overlays()
        self.measure_mode_changed.emit(on)

    def _clear_measure(self):
        self._measure_a = self._measure_b = None
        if self._view is not None:
            self._measure_line.setData(pos=np.zeros((0, 3), np.float32))
            self._set_selection([])

    def _set_selection(self, picks: List[PickResult]):
        if self._view is None:
            return
        if not picks:
            self._select_item.setData(pos=np.zeros((0, 3), np.float32))
            return
        self._select_item.setData(pos=to_gl(np.array([p.xyz for p in picks], dtype=np.float64)),
                                  color=(1, 1, 1, 1), size=18, pxMode=True)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self._clear_measure()
            if self.measure_mode:
                self._hint.setText("Measure: click the first point (Esc cancels)")
            self._card.hide()
            event.accept()
            return
        super().keyPressEvent(event)

    def _current_mvp(self) -> Tuple[np.ndarray, Tuple[float, float]]:
        w, h = max(1, self._view.width()), max(1, self._view.height())
        proj = matrix_to_numpy(self._view.projectionMatrix((0, 0, w, h), (0, 0, w, h)))
        return proj @ matrix_to_numpy(self._view.viewMatrix()), (float(w), float(h))

    def pick_at(self, x: float, y: float) -> Optional[PickResult]:
        """What is under widget coordinates (x, y)? Honours the snap toggle."""
        if self._view is None:
            return None
        mvp, size = self._current_mvp()
        return resolve_pick(self._points_gl, self._indices, self._markers, mvp, size, (x, y), snap=self.snap_enabled)

    def _on_click(self, pos: QPointF, modifiers):
        pick = self.pick_at(pos.x(), pos.y())
        measuring = self.measure_mode or bool(modifiers & Qt.KeyboardModifier.ShiftModifier)
        if pick is None:
            if not measuring:
                self._selected = None
                self._set_selection([])
                self._card.hide()
            return
        if not measuring:
            self._selected = pick
            self._set_selection([pick])
            self.probe_requested.emit(pick.index)
            return
        if self._measure_a is None or self._measure_b is not None:       # first point (or start over)
            self._clear_measure()
            self._measure_a = pick
            self._set_selection([pick])
            self._hint.setText("Measure: click the second point (Esc cancels)")
            self._hint.setVisible(True)
            self._layout_overlays()
            self.probe_requested.emit(pick.index)
            return
        self._measure_b = pick
        self._set_selection([self._measure_a, pick])
        self._measure_line.setData(pos=to_gl(np.array([self._measure_a.xyz, pick.xyz], dtype=np.float64)))
        self._hint.setText("Measure: click again to start a new measurement")
        self._layout_overlays()
        self.measure_completed.emit(self._measure_a.index, pick.index)


if GL_AVAILABLE:
    class _PickingView(gl.GLViewWidget):
        """GLViewWidget that reports a click (press+release without dragging) so orbiting never triggers a pick."""
        clicked = pyqtSignal(QPointF, object)

        def mousePressEvent(self, ev):
            self._press = (ev.position(), time.monotonic())
            super().mousePressEvent(ev)

        def mouseReleaseEvent(self, ev):
            super().mouseReleaseEvent(ev)
            if self._press is not None and ev.button() == Qt.MouseButton.LeftButton:
                start, t0 = self._press
                moved = (ev.position() - start).manhattanLength()
                if moved <= CLICK_MOVE_TOLERANCE_PX and (time.monotonic() - t0) < 0.6:
                    self.clicked.emit(ev.position(), ev.modifiers())
            self._press = None
