"""
Per-point temperature layer for the 3D Mapping world.

The world's colours are only display colours; this layer holds actual temperatures (degrees C) per world point:
  * latest  - most recent reading (NaN = never seen by the thermal camera)
  * peak    - hottest reading ever seen at that point
  * baseline- the `latest` values stored with a loaded world, so a re-visit can be compared against it
Pure numpy; knows nothing about Open3D or the scan state machine.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

import numpy as np

SIDECAR_SUFFIX = ".thermal.npz"

VIEW_MODES = ("colour", "temperature", "peak", "change")
VIEW_MODE_LABELS = {
    "colour": "Texture colour",
    "temperature": "Temperature (live)",
    "peak": "Peak temperature",
    "change": "Change vs loaded world",
}


@dataclass(frozen=True)
class Marker:
    """A labelled place in the world for the viewer to draw. `value` is degrees C for kind 'hot' (peak temperature) and
    a temperature DIFFERENCE in degrees C for 'warm'/'cool' (change vs the loaded world). `index` is the point's index in
    the FULL world arrays, so a click on a marker resolves to an exact reading."""
    label: str
    xyz: Tuple[float, float, float]
    value: float
    kind: str           # 'hot' | 'warm' | 'cool'
    index: int


@dataclass(frozen=True)
class ProbeResult:
    index: int
    xyz: Tuple[float, float, float]
    distance_from_camera: Optional[float]   # metres, None when the camera pose is unknown
    temp: Optional[float]                   # live, degrees C; None = never measured
    peak: Optional[float]
    change: Optional[float]                 # vs the loaded world's baseline; None = no baseline / not measured yet
    has_temp: bool


@dataclass(frozen=True)
class MeasureResult:
    index_a: int
    index_b: int
    distance_m: float
    delta_temp: Optional[float]             # temp(b) - temp(a), degrees C; None when either is unmeasured


def project_visible(points: np.ndarray, pose: np.ndarray, intrinsic_fxfycxcy, frame_shape,
                    depth_m: np.ndarray = None, depth_tolerance: float = 0.03):
    """Which world points does a camera at `pose` (camera-to-world) see in a frame of `frame_shape`?
    Returns (indices, u, v): indices of visible points and their integer pixel coordinates. With depth_m (same size
    as the frame) a point only counts as visible when the observed depth at its pixel agrees with its own distance
    (within depth_tolerance + 2% of range) - otherwise a point hidden behind a nearer surface lands on that
    surface's pixel and takes its value."""
    fx, fy, cx, cy = intrinsic_fxfycxcy
    inv = np.linalg.inv(pose)
    cam = points @ inv[:3, :3].T + inv[:3, 3]
    z = cam[:, 2]
    valid = z > 1e-6
    u = np.zeros_like(z)
    v = np.zeros_like(z)
    u[valid] = cam[valid, 0] * fx / z[valid] + cx
    v[valid] = cam[valid, 1] * fy / z[valid] + cy
    h, w = frame_shape[:2]
    ok = valid & (u >= 0) & (u < w) & (v >= 0) & (v < h)
    idx = np.where(ok)[0]
    ui = u[idx].astype(np.int32)
    vi = v[idx].astype(np.int32)
    if depth_m is not None and depth_m.shape[:2] == (h, w):
        observed = depth_m[vi, ui]
        agrees = (observed > 0) & (np.abs(observed - z[idx]) <= depth_tolerance + 0.02 * z[idx])
        idx, ui, vi = idx[agrees], ui[agrees], vi[agrees]
    return idx, ui, vi


class WorldThermalLayer:
    def __init__(self):
        self.latest = np.zeros(0, np.float32)
        self.peak = np.zeros(0, np.float32)
        self.baseline = None            # float32 array or None
        self.update_count = 0

    # ------------------------------------------------------------------ lifecycle

    def reset(self, point_count: int = 0):
        self.latest = np.full(point_count, np.nan, np.float32)
        self.peak = np.full(point_count, np.nan, np.float32)
        self.baseline = None
        self.update_count = 0

    @property
    def has_data(self) -> bool:
        return self.latest.size > 0 and bool(np.isfinite(self.latest).any())

    @property
    def has_baseline(self) -> bool:
        return self.baseline is not None and bool(np.isfinite(self.baseline).any())

    def coverage(self) -> float:
        """Fraction of world points that have a temperature reading."""
        return float(np.isfinite(self.latest).mean()) if self.latest.size else 0.0

    # ------------------------------------------------------------------ update

    def update(self, points, pose, temp_c, intrinsic_fxfycxcy, depth_m=None) -> int:
        """Record readings from a temperature frame (degrees C, same grid as the depth/colour frame it was
        captured with). Returns how many points were updated. Pixels with non-finite temperature are skipped."""
        if self.latest.size != len(points):
            self.reset(len(points))
        if len(points) == 0:
            return 0
        idx, u, v = project_visible(points, pose, intrinsic_fxfycxcy, temp_c.shape, depth_m)
        if idx.size == 0:
            return 0
        t = temp_c[v, u].astype(np.float32)
        good = np.isfinite(t)
        idx, t = idx[good], t[good]
        if idx.size == 0:
            return 0
        self.latest[idx] = t
        prev = self.peak[idx]
        self.peak[idx] = np.where(np.isfinite(prev), np.maximum(prev, t), t)
        self.update_count += 1
        return int(idx.size)

    # ------------------------------------------------------------------ analysis

    def values(self, mode: str):
        if mode == "peak":
            return self.peak
        if mode == "change":
            if not self.has_baseline or self.baseline.size != self.latest.size:
                return np.full(self.latest.size, np.nan, np.float32)
            return self.latest - self.baseline
        return self.latest

    def stats(self):
        """dict(min, max, mean, coverage) over points with readings, or None when there are none."""
        m = np.isfinite(self.latest)
        if not m.any():
            return None
        t = self.latest[m]
        return {"min": float(t.min()), "max": float(t.max()), "mean": float(t.mean()), "coverage": self.coverage()}

    def hotspots(self, points, count: int = 5, min_separation_m: float = 0.25, mode: str = "peak"):
        """The `count` hottest distinct places: greedy non-maximum suppression so one hot object is one hotspot, not
        thousands of neighbouring points. Returns [(temp_c, xyz ndarray, point_index)] hottest first."""
        vals = self.values(mode)
        return self._extreme(points, vals, count, min_separation_m, hottest=True, signed=False)

    def changes(self, points, count: int = 5, min_separation_m: float = 0.25):
        """Biggest warm-ups and cool-downs vs the baseline: ([hotter...], [cooler...]) as hotspots() entries."""
        delta = self.values("change")
        if not np.isfinite(delta).any():
            return [], []
        warm = self._extreme(points, delta, count, min_separation_m, hottest=True, signed=True)
        cool = self._extreme(points, delta, count, min_separation_m, hottest=False, signed=True)
        return warm, cool

    @staticmethod
    def _extreme(points, vals, count, sep, hottest, signed):
        key = np.where(np.isfinite(vals), vals, -np.inf if hottest else np.inf)
        order = np.argsort(key)
        if hottest:
            order = order[::-1]
        out = []
        for i in order:
            if not np.isfinite(vals[i]) or len(out) >= count:
                break
            if signed and ((hottest and vals[i] <= 0) or (not hottest and vals[i] >= 0)):
                break
            p = points[i]
            if all(np.linalg.norm(p - q) >= sep for _, q, _ in out):
                out.append((float(vals[i]), np.asarray(p, dtype=float), int(i)))
        return out

    def nearest(self, points, xyz, mode: str = "temperature"):
        """(index, distance_m, value) of the world point closest to `xyz`."""
        d = np.linalg.norm(points - np.asarray(xyz, dtype=float), axis=1)
        i = int(np.argmin(d))
        return i, float(d[i]), float(self.values(mode)[i])

    def scale(self, mode: str):
        """(lo, hi) the colour scale uses for `mode`, in degrees C (a difference for 'change', symmetric around 0), or
        None when there is nothing to show. Single source for colorize() and the viewer's legend."""
        vals = self.values(mode)
        finite = np.isfinite(vals)
        if not finite.any():
            return None
        if mode == "change":
            span = float(max(1.0, np.percentile(np.abs(vals[finite]), 98)))
            return -span, span
        lo, hi = float(vals[finite].min()), float(vals[finite].max())
        return (lo, lo + 1.0) if hi - lo < 1e-6 else (lo, hi)

    # ------------------------------------------------------------------ colours

    def colorize(self, mode: str, lo=None, hi=None):
        """(N,3) float RGB 0-1 for a viewport mode, or None when there is nothing to show. Unmeasured points are
        dark grey. 'change' uses a blue-white-red diverging scale centred on 0 K."""
        import cv2
        vals = self.values(mode)
        finite = np.isfinite(vals)
        if not finite.any():
            return None
        out = np.full((vals.size, 3), 0.25, np.float32)
        default_lo, default_hi = self.scale(mode)
        if mode == "change":
            span = float(lo if lo is not None else default_hi)
            x = np.clip(vals[finite] / span, -1.0, 1.0)
            r = np.where(x > 0, 1.0, 1.0 + x)
            b = np.where(x < 0, 1.0, 1.0 - x)
            g = 1.0 - np.abs(x)
            out[finite] = np.stack([r, g, b], axis=1)
            return out
        lo = default_lo if lo is None else lo
        hi = default_hi if hi is None else hi
        x = np.clip((vals[finite] - lo) / (hi - lo), 0, 1)
        lut = cv2.applyColorMap((x * 255).astype(np.uint8).reshape(-1, 1), cv2.COLORMAP_INFERNO).reshape(-1, 3)
        out[finite] = lut[:, ::-1].astype(np.float32) / 255.0      # BGR -> RGB
        return out

    # ------------------------------------------------------------------ persistence

    def save(self, path: str):
        with open(path, "wb") as f:
            np.savez_compressed(f, latest=self.latest, peak=self.peak, update_count=self.update_count)

    def load(self, path: str, point_count: int) -> bool:
        """Load a sidecar written by save(). Ignored (returns False) if it doesn't match this world's point count.
        The stored `latest` becomes the baseline; live readings start fresh so they can be compared against it."""
        try:
            with np.load(path) as z:
                latest = z["latest"].astype(np.float32)
                peak = z["peak"].astype(np.float32)
        except (OSError, KeyError, ValueError):
            return False
        if latest.size != point_count:
            return False
        self.baseline = latest
        self.peak = peak            # peaks carry over; the live layer then keeps raising them
        self.latest = np.full(point_count, np.nan, np.float32)
        self.update_count = 0
        return True

    def export_csv(self, path: str, points: np.ndarray):
        """x, y, z, live temp, peak temp, change vs baseline (blank where unknown)."""
        delta = self.values("change")
        rows = np.column_stack([points, self.latest, self.peak, delta])
        with open(path, "w", encoding="utf-8") as f:
            f.write("x_m,y_m,z_m,temp_c,peak_c,change_c\n")
            for r in rows:
                f.write(",".join("" if not np.isfinite(x) else f"{x:.4f}" for x in r) + "\n")
