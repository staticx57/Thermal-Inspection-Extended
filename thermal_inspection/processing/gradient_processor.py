"""
Gradient Processor
==================
Computes temperature-gradient overlays from thermal frames.

Supports four modes:
  magnitude  — Sobel magnitude (overall rate of change)
  horizontal — Sobel X (left/right gradients)
  vertical   — Sobel Y (up/down gradients)
  both       — Arrow-field overlay (magnitude + direction)

The processor is intentionally stateless: call ``compute(frame, settings)``
each frame and composite the returned BGRA overlay onto the display frame.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

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


@dataclass
class GradientSettings:
    """Current settings from GradientOverlayPanel."""
    enabled: bool = False
    mode: str = "magnitude"       # magnitude | horizontal | vertical | both
    threshold: float = 1.0        # °C/px — suppress below this value
    sensitivity: int = 50         # 1-100; scales effective threshold
    colormap: str = "hot"         # hot | cool | jet | viridis | gray
    alpha: float = 0.55           # overlay blend strength


class GradientProcessor:
    """Computes gradient overlays for thermal frames."""

    def __init__(self) -> None:
        self._settings = GradientSettings()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def update_settings(self, **kwargs) -> None:
        """Update any subset of GradientSettings fields."""
        for k, v in kwargs.items():
            if hasattr(self._settings, k):
                setattr(self._settings, k, v)

    @property
    def enabled(self) -> bool:
        return self._settings.enabled

    def compute(self, frame: np.ndarray) -> Optional[np.ndarray]:
        """Return a BGR overlay the same size as *frame*, or None if disabled.

        The caller is responsible for blending this with the display frame
        (e.g. ``cv2.addWeighted``).

        Args:
            frame: Single-channel (8-bit or 16-bit) or 3-channel BGR thermal
                   display frame.  16-bit frames are rescaled to 8-bit for the
                   gradient calculation.

        Returns:
            BGR overlay array (same H×W as *frame*), or None when disabled.
        """
        if not self._settings.enabled:
            return None

        try:
            gray = self._to_gray(frame)
            grad = self._compute_gradient(gray)
            masked = self._apply_threshold(grad)
            colored = self._colorize(masked)
            return colored
        except Exception as exc:
            logger.error(f"GradientProcessor.compute error: {exc}")
            return None

    def blend(self, display_frame: np.ndarray) -> np.ndarray:
        """Convenience: compute and blend in one call.

        Returns *display_frame* unchanged when disabled or on error.
        """
        overlay = self.compute(display_frame)
        if overlay is None:
            return display_frame
        try:
            alpha = self._settings.alpha
            return cv2.addWeighted(display_frame, 1.0, overlay, alpha, 0)
        except Exception as exc:
            logger.error(f"GradientProcessor.blend error: {exc}")
            return display_frame

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _to_gray(frame: np.ndarray) -> np.ndarray:
        """Convert any frame type to uint8 grayscale."""
        if frame.ndim == 3:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        else:
            gray = frame.copy()

        if gray.dtype != np.uint8:
            mn, mx = float(gray.min()), float(gray.max())
            if mx > mn:
                gray = ((gray.astype(np.float32) - mn) / (mx - mn) * 255).astype(np.uint8)
            else:
                gray = np.zeros_like(gray, dtype=np.uint8)
        return gray

    def _compute_gradient(self, gray: np.ndarray) -> np.ndarray:
        """Compute gradient field according to current mode.

        Returns a float32 array (H×W) of gradient magnitudes (always ≥ 0).
        """
        mode = self._settings.mode
        blurred = cv2.GaussianBlur(gray, (3, 3), 0)

        if mode == "horizontal":
            gx = cv2.Sobel(blurred, cv2.CV_32F, 1, 0, ksize=3)
            return np.abs(gx)
        elif mode == "vertical":
            gy = cv2.Sobel(blurred, cv2.CV_32F, 0, 1, ksize=3)
            return np.abs(gy)
        else:  # magnitude or both — compute full gradient
            gx = cv2.Sobel(blurred, cv2.CV_32F, 1, 0, ksize=3)
            gy = cv2.Sobel(blurred, cv2.CV_32F, 0, 1, ksize=3)
            return np.sqrt(gx ** 2 + gy ** 2)

    def _apply_threshold(self, grad: np.ndarray) -> np.ndarray:
        """Zero out pixels below the sensitivity-adjusted threshold.

        Returns a normalized uint8 array (0-255).
        """
        # Sensitivity (1-100) scales threshold inversely:
        #   sensitivity=100 → effective_threshold = threshold * 0
        #   sensitivity=50  → effective_threshold = threshold * 1
        #   sensitivity=1   → effective_threshold = threshold * ~2
        sens = max(1, min(100, self._settings.sensitivity))
        effective = self._settings.threshold * (100 - sens) / 50.0

        mask = grad >= max(0.0, effective)
        filtered = grad * mask.astype(np.float32)

        # Normalize to 0-255
        mx = float(filtered.max())
        if mx > 0:
            normalized = (filtered / mx * 255).astype(np.uint8)
        else:
            normalized = np.zeros_like(filtered, dtype=np.uint8)
        return normalized

    def _colorize(self, gray: np.ndarray) -> np.ndarray:
        """Apply the selected colormap to the normalized gradient array."""
        cmap_id = _COLORMAP_IDS.get(self._settings.colormap, cv2.COLORMAP_HOT)
        if cmap_id == -1:
            # Grayscale: just stack to BGR
            return cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
        return cv2.applyColorMap(gray, cmap_id)
