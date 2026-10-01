"""
Geometric alignment calibration (RGB -> thermal homography) as an app-level feature, the counterpart of the parallax
correction: it owns loading/saving/computing the calibration, applying it to the FusionProcessor, switching it on/off,
and remembering it across restarts. (Not to be confused with CalibrationManager, which handles RADIOMETRIC temperature
calibration.)

The homography is exact for the plane it was calibrated on, at the distance it records; parallax correction covers the
other distances, and FusionProcessor.set_parallax_composition keeps the two from double-counting.
"""
import logging
import os
from typing import Any, Dict, Optional

from thermal_inspection.cameras.camera_calibration import CameraCalibrator

logger = logging.getLogger(__name__)

DEFAULT_FILENAME = "alignment_calibration.json"
METHODS = ("features", "edges", "checkerboard")


def default_calibration_path() -> str:
    """The auto-saved calibration lives next to config.json (the project/working directory)."""
    return os.path.abspath(DEFAULT_FILENAME)


class AlignmentCalibrationManager:
    def __init__(self, fusion_processor, config=None):
        self.fusion = fusion_processor
        self._config = config
        self.source_path: Optional[str] = None
        self.last_error: Optional[str] = None

    # ------------------------------------------------------------------ config

    @property
    def config(self):
        if self._config is None:
            from thermal_inspection.utils.config import get_config
            self._config = get_config()
        return self._config

    def _remember(self):
        try:
            self.config.set('alignment_calibration_file', self.source_path, save=False)
            self.config.set('alignment_calibration_enabled', bool(self.fusion.calibration_enabled), save=True)
        except Exception as e:                                       # persistence must never break alignment
            logger.warning(f"Could not persist alignment calibration settings: {e}")

    def restore(self, cli_file: Optional[str] = None) -> bool:
        """Startup: --calibration-file wins over the remembered file. A missing/bad file is reported, not fatal."""
        path = cli_file or self.config.get('alignment_calibration_file')
        if not path:
            return False
        if not os.path.exists(path):
            logger.warning(f"Alignment calibration file not found: {path}")
            self.last_error = f"File not found: {path}"
            return False
        was_enabled = bool(self.config.get('alignment_calibration_enabled', True))   # load() resets and re-saves it
        ok = self.load(path, remember=False)
        if ok:
            if not cli_file:
                self.fusion.set_calibration_enabled(was_enabled)
            self._remember()
        return ok

    # ------------------------------------------------------------------ operations

    def load(self, path: str, remember: bool = True) -> bool:
        if not self.fusion.load_calibration(path):
            self.last_error = f"Could not load a calibration from {path}"
            return False
        self.fusion.set_calibration_enabled(True)
        self.source_path, self.last_error = path, None
        if remember:
            self._remember()
        return True

    def clear(self):
        self.fusion.clear_calibration()
        self.source_path, self.last_error = None, None
        self._remember()

    def set_enabled(self, enabled: bool):
        self.fusion.set_calibration_enabled(enabled)
        self._remember()

    def save(self, path: str) -> bool:
        if not self.fusion.save_calibration(path):
            self.last_error = f"Could not save to {path}"
            return False
        self.source_path, self.last_error = path, None
        self._remember()
        return True

    def capture(self, thermal_frame, rgb_frame, distance_m: float, method: str = "features",
                board=(9, 6)) -> bool:
        """Compute a homography from one pair of live frames (the same scene, same moment), install it, and save it
        beside config.json so it survives a restart. Returns False (and sets last_error) when the fit is not good."""
        self.last_error = None
        if thermal_frame is None or rgb_frame is None:
            self.last_error = "Both a thermal and an RGB frame are needed - is the RGB camera connected?"
            return False
        if not distance_m or distance_m <= 0:
            self.last_error = "Enter the distance to the target (metres)."
            return False
        if method not in METHODS:
            self.last_error = f"Unknown method: {method}"
            return False
        cal = CameraCalibrator()
        if method == "checkerboard":
            ok = cal.calibrate_with_checkerboard(thermal_frame, rgb_frame, tuple(board))
            hint = "the checkerboard was not found in both images (a printed pattern is invisible to a thermal camera)"
        else:
            ok = cal.calibrate_with_features(thermal_frame, rgb_frame, use_edges=(method == "edges"))
            hint = "no consistent matches between the images (try 'edges', a scene with more structure, or hold still)"
        if not ok:
            self.last_error = f"Calibration failed: {hint}."
            return False
        if cal.quality.get("rms_px", 0) > 3.0:
            self.last_error = (f"Fit rejected: RMS error {cal.quality['rms_px']:.1f} px is too high "
                               "(images not registered consistently).")
            return False
        import time
        info = dict(cal.quality, thermal_shape=list(cal.thermal_shape), rgb_shape=list(cal.rgb_shape),
                    timestamp=time.time())
        self.fusion.set_calibration(cal.homography_matrix, distance_m, info)
        target = default_calibration_path()
        if not self.fusion.save_calibration(target):
            logger.warning(f"Calibration applied but could not be saved to {target}")
            self.source_path = None
        else:
            self.source_path = target
        self._remember()
        return True

    # ------------------------------------------------------------------ status

    def status(self) -> Dict[str, Any]:
        f = self.fusion
        info = f.calibration_info or {}
        loaded = f.calibration_matrix is not None
        return {
            "loaded": loaded,
            "enabled": bool(f.calibration_enabled),
            "path": self.source_path,
            "distance_m": f.calibration_distance_m,
            "method": info.get("method"),
            "rms_px": info.get("rms_px"),
            "inliers": info.get("inliers"),
            "points": info.get("points"),
            "thermal_shape": info.get("thermal_shape"),
            "rgb_shape": info.get("rgb_shape"),
            "parallax_composed": getattr(f, "_parallax_composition", None) is not None,
            "error": self.last_error,
        }
