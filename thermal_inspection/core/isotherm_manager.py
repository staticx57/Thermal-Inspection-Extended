"""
IsothermManager — Encapsulates 16-bit temperature-aware isotherm overlay state.

Unlike ThresholdManager (8-bit percentage-based), IsothermManager works
with real temperature values from 16-bit radiometric frames.  Supports
single-threshold, band, and multiband modes via IsothermBandManager.
"""

import logging
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

import numpy as np
from PyQt6.QtCore import QObject, pyqtSignal

logger = logging.getLogger(__name__)

# BGR color map for isotherm overlays
ISOTHERM_COLORS: Dict[str, Tuple[int, int, int]] = {
    'red':     (0, 0, 255),
    'green':   (0, 255, 0),
    'blue':    (255, 0, 0),
    'cyan':    (255, 255, 0),
    'magenta': (255, 0, 255),
    'yellow':  (0, 255, 255),
    'white':   (255, 255, 255),
}


@dataclass(frozen=True)
class IsothermState:
    """Immutable snapshot of isotherm configuration for thread-safe reads."""
    enabled: bool = False
    mode: str = "single"            # 'single' | 'band' | 'multiband'
    low_threshold: float = 0.0      # Temperature in Celsius
    high_threshold: float = 100.0   # Temperature in Celsius
    color: str = "red"              # Single-band highlight color name
    multiband_mode: bool = False    # Use IsothermBandManager


class IsothermManager(QObject):
    """
    Manages isotherm overlay state with 16-bit temperature awareness.

    The frame loop calls ``apply_overlay(colorized, temp_frame)`` each
    tick.  The manager reads its own state atomically and applies the
    correct overlay mode.

    Signals:
        state_changed: Emitted when any isotherm parameter changes.
    """

    state_changed = pyqtSignal()

    VALID_MODES = frozenset({"single", "band", "multiband"})
    VALID_COLORS = frozenset(ISOTHERM_COLORS.keys())

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._enabled: bool = False
        self._mode: str = "single"
        self._low_threshold: float = 0.0
        self._high_threshold: float = 100.0
        self._color: str = "red"
        self._band_manager = None       # IsothermBandManager (set by GUI)
        self._multiband_mode: bool = False

    # ------------------------------------------------------------------
    # Atomic snapshot for callers
    # ------------------------------------------------------------------

    def get_state(self) -> IsothermState:
        """Return an immutable snapshot of the current isotherm state."""
        return IsothermState(
            enabled=self._enabled,
            mode=self._mode,
            low_threshold=self._low_threshold,
            high_threshold=self._high_threshold,
            color=self._color,
            multiband_mode=self._multiband_mode,
        )

    # ------------------------------------------------------------------
    # Setters
    # ------------------------------------------------------------------

    def set_enabled(self, enabled: bool) -> None:
        self._enabled = bool(enabled)
        logger.info(f"Isotherm overlay: {'ON' if self._enabled else 'OFF'}")
        self.state_changed.emit()

    def set_mode(self, mode: str) -> None:
        if mode not in self.VALID_MODES:
            logger.warning(f"Invalid isotherm mode '{mode}', ignoring")
            return
        self._mode = mode
        logger.info(f"Isotherm mode: {mode}")
        self.state_changed.emit()

    def set_low_threshold(self, val: float) -> None:
        self._low_threshold = float(val)
        self.state_changed.emit()

    def set_high_threshold(self, val: float) -> None:
        self._high_threshold = float(val)
        self.state_changed.emit()

    def set_color(self, color: str) -> None:
        if color not in self.VALID_COLORS:
            logger.warning(f"Unknown isotherm color '{color}', ignoring")
            return
        self._color = color
        self.state_changed.emit()

    def set_band_manager(self, band_manager) -> None:
        """Set the IsothermBandManager used for multiband rendering."""
        self._band_manager = band_manager
        logger.info("Isotherm band manager updated")
        self.state_changed.emit()

    def set_multiband_mode(self, enabled: bool) -> None:
        self._multiband_mode = bool(enabled)
        logger.info(f"Isotherm multiband mode: {'ON' if self._multiband_mode else 'OFF'}")
        self.state_changed.emit()

    # ------------------------------------------------------------------
    # Overlay application (called from frame loop)
    # ------------------------------------------------------------------

    def apply_overlay(self, frame: np.ndarray, temp_frame: np.ndarray) -> np.ndarray:
        """Apply isotherm coloring to a colorized thermal frame.

        Uses IsothermBandManager when available and multiband mode is active,
        otherwise applies a simple single-threshold colour mask.

        Args:
            frame: Colorized BGR thermal frame (H, W, 3)
            temp_frame: Raw temperature frame — 16-bit Y16 uint16 or float32 Celsius

        Returns:
            Frame with isotherm overlay applied (same shape as input)
        """
        if not self._enabled or temp_frame is None:
            return frame

        try:
            # Multiband path — delegate to the band manager
            if self._multiband_mode and self._band_manager is not None:
                return self._band_manager.apply_bands_to_frame(frame, temp_frame)

            # Single-threshold path — highlight pixels within [low, high]
            out = frame.copy()
            celsius_approx = self._to_celsius(temp_frame)

            mask = (
                (celsius_approx >= self._low_threshold) &
                (celsius_approx <= self._high_threshold)
            )

            bgr = ISOTHERM_COLORS.get(self._color, (0, 0, 255))
            out[mask] = bgr
            return out

        except Exception as e:
            logger.error(f"Error applying isotherm overlay: {e}")
            return frame

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _to_celsius(temp_frame: np.ndarray) -> np.ndarray:
        """Convert a 16-bit Y16 frame to approximate Celsius.

        For true radiometric cameras the Y16 value is Kelvin × 100.
        For non-radiometric (AGC) frames we fall back to a rough
        normalisation over the typical Boson range.

        Args:
            temp_frame: Raw uint16 or float32 temperature frame.

        Returns:
            Float32 array of approximate Celsius values.
        """
        if temp_frame.dtype == np.uint16:
            vals = temp_frame.astype(np.float32)
            # Heuristic: if max > 20000 it's likely Y16 (Kelvin × 100)
            if vals.max() > 20000:
                return (vals / 100.0) - 273.15
            else:
                # AGC mode: rough normalisation
                norm = vals / 65535.0
                return norm * 600.0 - 40.0
        else:
            return temp_frame.astype(np.float32)
