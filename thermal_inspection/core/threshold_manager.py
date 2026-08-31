"""
ThresholdManager — Encapsulates manual threshold overlay state.

Manages the 8-bit threshold detection parameters driven by the
ManualThresholdWidget.  The frame loop reads an atomic ThresholdState
snapshot via ``get_state()`` each tick.
"""

import logging
from dataclasses import dataclass
from typing import Optional

from PyQt6.QtCore import QObject, pyqtSignal

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ThresholdState:
    """Immutable snapshot of threshold configuration for thread-safe reads."""
    enabled: bool = False
    mode: str = "above"                    # ThresholdMode string value
    min_val: float = 50.0                  # min value (% or raw)
    max_val: float = 75.0                  # max value (% or raw)
    use_raw: bool = False                  # False => percentage 0-100
    viz_mode: str = "grayscale_non_anomaly" # ThresholdVisualization string


class ThresholdManager(QObject):
    """
    Manages manual threshold overlay state with validation and change
    notification via Qt signals.

    The GUI connects to the ``state_changed`` signal to react to
    programmatic changes.  The frame loop calls ``get_state()`` each
    tick to read an immutable snapshot without locking.
    """

    # Emitted whenever any threshold parameter changes
    state_changed = pyqtSignal()

    # Valid mode/viz values (mirrors ThresholdMode / ThresholdVisualization enums)
    VALID_MODES = frozenset({"above", "below", "between", "outside"})
    VALID_VIZ = frozenset({
        "highlight_anomaly", "grayscale_non_anomaly",
        "binary_mask", "heatmap_overlay",
    })

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._enabled: bool = False
        self._mode: str = "above"
        self._min_val: float = 50.0
        self._max_val: float = 75.0
        self._use_raw: bool = False
        self._viz_mode: str = "grayscale_non_anomaly"

    # ------------------------------------------------------------------
    # Atomic snapshot for the frame loop
    # ------------------------------------------------------------------

    def get_state(self) -> ThresholdState:
        """Return an immutable snapshot of the current threshold state."""
        return ThresholdState(
            enabled=self._enabled,
            mode=self._mode,
            min_val=self._min_val,
            max_val=self._max_val,
            use_raw=self._use_raw,
            viz_mode=self._viz_mode,
        )

    # ------------------------------------------------------------------
    # Setters (called via EventBus signals)
    # ------------------------------------------------------------------

    def set_enabled(self, enabled: bool) -> None:
        self._enabled = bool(enabled)
        logger.info(f"Manual threshold: {'ON' if self._enabled else 'OFF'}")
        self.state_changed.emit()

    def set_mode(self, mode: str) -> None:
        if mode not in self.VALID_MODES:
            logger.warning(f"Invalid threshold mode '{mode}', ignoring")
            return
        self._mode = mode
        self.state_changed.emit()

    def set_min(self, val: float) -> None:
        self._min_val = float(val)
        self.state_changed.emit()

    def set_max(self, val: float) -> None:
        self._max_val = float(val)
        self.state_changed.emit()

    def set_use_raw(self, enabled: bool) -> None:
        self._use_raw = bool(enabled)
        self.state_changed.emit()

    def set_viz_mode(self, mode: str) -> None:
        if mode not in self.VALID_VIZ:
            logger.warning(f"Invalid viz mode '{mode}', ignoring")
            return
        self._viz_mode = mode
        self.state_changed.emit()
