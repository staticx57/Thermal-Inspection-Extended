"""
Gradient Processor
==================
Computes temperature-gradient overlays from thermal data.

Supports four modes:
  magnitude  - Sobel magnitude (overall rate of change)
  horizontal - Sobel X (left/right gradients)
  vertical   - Sobel Y (up/down gradients)
  both       - magnitude tint plus an arrow field showing the direction of increasing temperature

Gradients are measured in real units on the thermal DATA, not on the colourised picture: for a radiometric
(16-bit Y16) source they are in degrees C per pixel; for an 8-bit AGC source they are in raw counts per pixel
(there is no temperature to report). Only pixels at or above the threshold are tinted, so a colormap that is
not black at zero (Cool, Jet, Viridis) doesn't colour the whole frame.

Call ``blend(display_frame, source)`` each frame; ``source`` is the thermal data (Y16 or 8-bit) the gradient
is measured on - when omitted the display frame itself is used.

Performance
-----------
This runs on every displayed frame, so the hot path is built to touch as few pixels as possible:
  * only the pixels that pass the threshold (a few percent of a typical scene) are coloured and blended - the
    frame is never converted to float32 wholesale;
  * colours come from a cached 256-entry lookup table indexed at the same 8-bit values the colormap used;
  * the overlay is computed once per distinct source frame - the processing loop runs faster than the camera,
    so identical frames are common, and the cached result is reused exactly. Recomputes are also held to ~15% of a
    core (see AUTO_BUDGET): a large sensor's overlay can lag by up to ~33-50 ms, while small frames are never
    throttled. ``min_interval_s`` forces a limit explicitly;
  * arrows are drawn with a handful of batched ``polylines`` calls, not one call per arrow.
The output is bit-identical to the straightforward dense implementation for magnitude/horizontal/vertical.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import List, Optional, Tuple

import cv2
import numpy as np

logger = logging.getLogger(__name__)

_COLORMAP_IDS: dict[str, int] = {
    "hot": cv2.COLORMAP_HOT,
    "cool": cv2.COLORMAP_COOL,
    "jet": cv2.COLORMAP_JET,
    "viridis": cv2.COLORMAP_VIRIDIS,
    "gray": -1,  # special-cased below
}

# Y16 stores Kelvin x 100: one count is 0.01 K, so a count *difference* times this is a degree difference
Y16_DEGREES_PER_COUNT = 0.01

# Expensive recomputes are limited to ~15% of a core: after a recompute that took `cost` seconds (> AUTO_MIN_COST_S),
# the next one waits at least cost / AUTO_BUDGET (capped at AUTO_MAX_INTERVAL_S) - frames in between reuse the last
# overlay. A 320x256 recompute (a fraction of a millisecond) is never throttled, even at 60 Hz, so its behaviour never
# depends on timing; a 640x512 one (~5 ms) is held to ~30 Hz.
AUTO_BUDGET = 0.15
AUTO_MAX_INTERVAL_S = 0.05
AUTO_MIN_COST_S = 0.002        # only recomputes costlier than this are throttled at all (small frames never are)

# A composited layer, stored sparsely: pixels[idx] = pixels[idx] * keep + add, where pixels is the frame viewed as
# (H*W, 3). idx: int64 flat pixel indices; keep: float32 (n, 1); add: float32 (n, 3). Indices (not a boolean mask)
# so that compositing costs time proportional to the tinted pixels instead of scanning the whole frame twice.
_Layer = Tuple[np.ndarray, np.ndarray, np.ndarray]


@dataclass
class GradientSettings:
    """Current settings from GradientOverlayPanel."""
    enabled: bool = False
    mode: str = "magnitude"       # magnitude | horizontal | vertical | both
    # deg C/px (8-bit source: counts/px) - suppress below this value. Measured on a Boson 320: sensor noise puts
    # the median at ~0.04 C/px, p90 ~0.12, p99 ~0.46 and strong edges ~1 C/px, so 0.2 shows clear edges
    # without the noise floor (the old default of 1.0 passed essentially nothing on a real scene).
    threshold: float = 0.2
    sensitivity: int = 50         # 1-100; scales effective threshold
    colormap: str = "hot"         # hot | cool | jet | viridis | gray
    alpha: float = 0.55           # overlay blend strength
    # Recompute the overlay at most this often (seconds); frames in between reuse the last one. 0 = every distinct
    # frame. Useful for very large frames where the gradient maths is the bottleneck (staleness <= this interval).
    min_interval_s: float = 0.0


class GradientProcessor:
    """Computes gradient overlays for thermal frames."""

    def __init__(self) -> None:
        self._settings = GradientSettings()
        self._norm_hi: Optional[float] = None   # smoothed brightness scale, so the overlay doesn't flicker
        self._luts: dict = {}                   # colormap name -> (256, 3) uint8 lookup table
        self._version = 0                       # bumped whenever settings change (invalidates the cache)
        self._cache: Optional[dict] = None      # last computed layers + what they were computed from
        self._last_cost_s = 0.0                 # cost estimate that drives the automatic throttle (see _layers_for)
        self._prev_cost_s: Optional[float] = None   # the previous recompute's measured cost
        self._stats_sample: Optional[np.ndarray] = None   # every 4th gradient pixel of the last frame, for scene_stats()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def update_settings(self, **kwargs) -> None:
        """Update any subset of GradientSettings fields."""
        for k, v in kwargs.items():
            if hasattr(self._settings, k):
                setattr(self._settings, k, v)
        self._version += 1
        self._cache = None
        if not self._settings.enabled:
            self._norm_hi = None

    @property
    def enabled(self) -> bool:
        return self._settings.enabled

    def effective_threshold(self) -> float:
        """Threshold after sensitivity: 100% -> 0 (show everything), 50% -> as set, 1% -> ~2x."""
        sens = max(1, min(100, self._settings.sensitivity))
        return max(0.0, self._settings.threshold * (100 - sens) / 50.0)

    def scene_stats(self) -> Optional[dict]:
        """
        How strong the last frame's gradients were, to help pick a threshold: {"p50", "p90", "p99"} in the
        processor's units (deg C/px, or counts/px on an 8-bit source), or None before the first frame.

        Computed on demand from a 1-in-16 pixel sample kept from the last recompute, so asking costs nothing
        per frame. (A scene's own noise floor is the median; clear edges sit around the 99th percentile.)
        """
        sample = self._stats_sample
        if sample is None or sample.size == 0:
            return None
        p50, p90, p99 = np.percentile(sample, [50, 90, 99])
        return {"p50": float(p50), "p90": float(p90), "p99": float(p99)}

    def compute(self, frame: np.ndarray, source: Optional[np.ndarray] = None) -> Optional[np.ndarray]:
        """Return a dense BGR overlay the same size as *frame*, or None if disabled or on error.

        Pixels below the threshold are the colormap's zero colour. This is the convenient, dense form (used by
        tests and tools); the per-frame path is ``blend``, which never builds it.
        """
        if not self._settings.enabled or frame is None or frame.size == 0:
            return None
        try:
            src = frame if source is None else source
            values, per_count = self._to_float(src)
            gx, gy = self._derivatives(values, per_count, frame.shape[:2], src.shape[:2])
            mag = self._magnitude(gx, gy)
            eff = self.effective_threshold()
            mask = (mag >= eff) & (mag > 0)
            hi = self._scale(mag[mask], eff)
            norm = np.clip(mag / hi, 0.0, 1.0).astype(np.float32)
            return self._colorize((norm * 255).astype(np.uint8))
        except Exception as exc:
            logger.error(f"GradientProcessor.compute error: {exc}")
            return None

    def blend(self, display_frame: np.ndarray, source: Optional[np.ndarray] = None) -> np.ndarray:
        """Composite the gradient overlay onto *display_frame* (only where the gradient passes the threshold).

        Returns *display_frame* unchanged when disabled or on error.
        """
        if not self._settings.enabled or display_frame is None or display_frame.size == 0:
            return display_frame
        try:
            src = display_frame if source is None else source
            layers = self._layers_for(display_frame.shape[:2], src)
            if not layers:
                return display_frame
            out = display_frame.copy()
            flat = out.reshape(-1, out.shape[-1]) if out.ndim == 3 else out.reshape(-1, 1)
            for idx, keep, add in layers:
                px = flat[idx].astype(np.float32)
                flat[idx] = np.clip(px * keep + add, 0, 255).astype(np.uint8)
            return out
        except Exception as exc:
            logger.error(f"GradientProcessor.blend error: {exc}")
            return display_frame

    # ------------------------------------------------------------------
    # Layers (computed once per distinct source frame, then reused)
    # ------------------------------------------------------------------

    def _layers_for(self, display_hw, src: np.ndarray) -> List[_Layer]:
        now = time.perf_counter()
        key = (self._version, tuple(display_hw), src.shape, src.dtype.str)
        c = self._cache
        if c is not None and c["key"] == key:
            interval = self._settings.min_interval_s
            if interval <= 0 and self._last_cost_s > AUTO_MIN_COST_S:
                interval = min(AUTO_MAX_INTERVAL_S, self._last_cost_s / AUTO_BUDGET)   # cost-proportional
            if interval > 0 and now - c["time"] < interval:
                return c["layers"]                       # throttled: a recent overlay is good enough
            if np.array_equal(c["source"], src):         # same frame again (the loop outruns the camera)
                return c["layers"]
        layers = self._build_layers(display_hw, src)
        cost = time.perf_counter() - now
        # Throttle on the cheaper of the last two recomputes: one slow outlier (cold caches, a busy machine, the very
        # first call) must not make a cheap frame size look expensive; a large sensor is slow every time.
        self._last_cost_s = 0.0 if self._prev_cost_s is None else min(cost, self._prev_cost_s)
        self._prev_cost_s = cost
        # keep a private copy: capture code reuses its frame buffers, so identity alone can't prove "same frame"
        self._cache = {"key": key, "time": now, "source": src.copy(), "layers": layers}
        return layers

    def _build_layers(self, display_hw, src: np.ndarray) -> List[_Layer]:
        values, per_count = self._to_float(src)
        gx, gy = self._derivatives(values, per_count, display_hw, src.shape[:2])
        mag = self._magnitude(gx, gy)
        self._stats_sample = mag[::4, ::4]

        eff = self.effective_threshold()
        mask = (mag >= eff) & (mag > 0)
        passed = mag[mask]
        if passed.size == 0:
            return []
        hi = self._scale(passed, eff)

        # exactly the dense formulas, evaluated only on the pixels that passed
        norm = np.clip(passed / hi, 0.0, 1.0).astype(np.float32)
        colors = self._lut()[(norm * 255).astype(np.uint8)].astype(np.float32)
        alpha = np.float32(self._settings.alpha) * (0.4 + 0.6 * norm)
        if self._settings.mode == "both":
            alpha = alpha * np.float32(0.5)      # fainter tint underneath the arrows
        a = alpha[:, None]
        layers: List[_Layer] = [(np.flatnonzero(mask), (1.0 - a).astype(np.float32), colors * a)]

        if self._settings.mode == "both":
            arrows = self._arrow_layer(gx, gy, mag, hi, eff)
            if arrows is not None:
                layers.append(arrows)
        return layers

    # ------------------------------------------------------------------
    # Maths
    # ------------------------------------------------------------------

    @staticmethod
    def _to_float(frame: np.ndarray) -> Tuple[np.ndarray, float]:
        """Thermal data as float32 plus degrees-per-count (0.01 for Y16; 1.0 = raw counts for 8-bit)."""
        per_count = Y16_DEGREES_PER_COUNT if frame.dtype == np.uint16 else 1.0
        if frame.ndim == 3:
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if frame.dtype == np.uint8 else frame[..., 0]
        return frame.astype(np.float32), per_count

    @staticmethod
    def _derivatives(values: np.ndarray, per_count: float, out_hw, src_hw) -> Tuple[np.ndarray, np.ndarray]:
        """Per-display-pixel derivatives (units per pixel), resized to the display frame if sizes differ."""
        blurred = cv2.GaussianBlur(values, (3, 3), 0)
        # Sobel's 3x3 kernel has a gain of 8, so /8 gives the derivative per source pixel
        gx = cv2.Sobel(blurred, cv2.CV_32F, 1, 0, ksize=3)
        gy = cv2.Sobel(blurred, cv2.CV_32F, 0, 1, ksize=3)
        gx *= per_count / 8.0           # in place: the same float32 multiply, without a second full-frame array
        gy *= per_count / 8.0
        if tuple(src_hw) != tuple(out_hw):
            h, w = out_hw
            gx = cv2.resize(gx, (w, h), interpolation=cv2.INTER_LINEAR) * (src_hw[1] / w)
            gy = cv2.resize(gy, (w, h), interpolation=cv2.INTER_LINEAR) * (src_hw[0] / h)
        return gx, gy

    def _magnitude(self, gx: np.ndarray, gy: np.ndarray) -> np.ndarray:
        mode = self._settings.mode
        if mode == "horizontal":
            return np.abs(gx)
        if mode == "vertical":
            return np.abs(gy)
        # sqrt(gx^2 + gy^2) in place: the same IEEE operations as the plain numpy expression (so bit-identical -
        # cv2.magnitude is faster still but rounds differently in the last bit, which can flip a pixel that sits
        # exactly at the threshold), without its temporaries
        m = gx * gx
        m += gy * gy
        return np.sqrt(m, out=m)

    def _scale(self, passed: np.ndarray, eff: float) -> float:
        """Brightness scale: the 99th percentile of the passed gradients, smoothed over frames (no flicker)."""
        if passed.size:
            hi = float(np.percentile(passed, 99))
            self._norm_hi = hi if self._norm_hi is None else 0.8 * self._norm_hi + 0.2 * hi
        return max(self._norm_hi or 0.0, eff * 1.5, 1e-6)

    def _lut(self) -> np.ndarray:
        """(256, 3) BGR colour for each 8-bit gradient brightness, for the selected colormap (cached)."""
        name = self._settings.colormap
        lut = self._luts.get(name)
        if lut is None:
            lut = self._colorize(np.arange(256, dtype=np.uint8).reshape(256, 1)).reshape(256, 3)
            self._luts[name] = lut
        return lut

    def _colorize(self, gray: np.ndarray) -> np.ndarray:
        """Apply the selected colormap to a 0-255 brightness image."""
        cmap_id = _COLORMAP_IDS.get(self._settings.colormap, cv2.COLORMAP_HOT)
        if cmap_id == -1:
            return cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
        return cv2.applyColorMap(gray, cmap_id)

    # ------------------------------------------------------------------
    # Arrows ('both' mode)
    # ------------------------------------------------------------------

    def _arrow_layer(self, gx, gy, mag, hi, eff) -> Optional[_Layer]:
        """Arrows pointing toward increasing temperature, on a grid of cells, drawn with batched polylines."""
        h, w = mag.shape
        step = max(14, min(h, w) // 20)
        rows, cols = max(1, h // step), max(1, w // step)
        cgx = cv2.resize(gx, (cols, rows), interpolation=cv2.INTER_AREA)
        cgy = cv2.resize(gy, (cols, rows), interpolation=cv2.INTER_AREA)
        cmag = cv2.magnitude(cgx, cgy)
        cnorm = np.clip(cmag / hi, 0.0, 1.0)

        sel = (cmag >= eff) & (cmag > 0)
        if not sel.any():
            return None
        rr, cc = np.nonzero(sel)
        m = cmag[rr, cc]
        n = cnorm[rr, cc]
        cx = (cc + 0.5) * w / cols
        cy = (rr + 0.5) * h / rows
        length = step * 0.45 * (0.4 + 0.6 * n)
        ux, uy = cgx[rr, cc] / m, cgy[rr, cc] / m                  # unit direction of increasing temperature
        x0, y0 = cx - ux * length, cy - uy * length
        x1, y1 = cx + ux * length, cy + uy * length
        tip = 0.45 * 2 * length                                      # head length: 45% of the shaft, as arrowedLine
        ang = np.pi / 4                                              # head half-angle (what cv2.arrowedLine uses)
        head = []
        for sgn in (1.0, -1.0):
            ca, sa = np.cos(sgn * ang), np.sin(sgn * ang)
            hx = x1 - tip * (ux * ca - uy * sa)
            hy = y1 - tip * (ux * sa + uy * ca)
            head.append(np.stack([hx, hy], axis=1))
        p0 = np.stack([x0, y0], axis=1)
        p1 = np.stack([x1, y1], axis=1)

        # colour per arrow from the LUT, quantised to 16 levels so a whole field needs only ~16 draw calls
        level = np.round(np.minimum(1.0, n * 1.25) * 15).astype(np.int32)
        bins = self._lut()[(level * 255 // 15).astype(np.uint8)]                 # (k, 3)
        canvas = np.zeros((h, w, 3), np.uint8)                                   # colour, antialiased, on black
        cover = np.zeros((h, w), np.uint8)                                       # antialiased coverage
        shafts = np.stack([p0, p1], axis=1).round().astype(np.int32)             # (k, 2, 2)
        wings = [np.stack([hd, p1], axis=1).round().astype(np.int32) for hd in head]
        lines = [s.reshape(-1, 1, 2) for s in shafts] + [wg.reshape(-1, 1, 2) for wing in wings for wg in wing]
        owner = np.concatenate([np.arange(len(shafts))] * 3)                     # which arrow each line belongs to

        # one polylines call per colour level, plus one for coverage
        for lv in np.unique(level):
            chosen = [lines[i] for i in np.nonzero(level[owner] == lv)[0]]
            colour = tuple(int(v) for v in self._lut()[int(lv) * 255 // 15])
            cv2.polylines(canvas, chosen, False, colour, 1, cv2.LINE_AA)
        cv2.polylines(cover, lines, False, 255, 1, cv2.LINE_AA)

        idx = np.flatnonzero(cover)
        if idx.size == 0:
            return None
        k = np.float32(min(1.0, self._settings.alpha + 0.4))
        covn = cover.reshape(-1)[idx].astype(np.float32) / 255.0
        # canvas is colour * coverage (drawn on black), i.e. premultiplied: out = out*(1 - cov*k) + canvas*k
        return idx, (1.0 - covn * k)[:, None].astype(np.float32), canvas.reshape(-1, 3)[idx].astype(np.float32) * k
