"""
ThermalBackend that plays back a FLIR radiometric recording (.seq / .fff) as if it were a live radiometric camera:
Y16 frames (Kelvin x 100), paced at the file's frame rate and looped, with exact per-pixel temperatures. Lets the whole
analysis pipeline (spot meters, ROIs, isotherms, statistics, snapshots) be developed and used without a camera.
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Any, Dict, Optional, Tuple

import numpy as np

from thermal_inspection.cameras.camera_backends import ThermalBackend
from thermal_inspection.sdk.flir_file_reader import FlirFileError, FlirFileSource

logger = logging.getLogger(__name__)


class FlirFileBackend(ThermalBackend):
    def __init__(self, path: str, loop: bool = True, realtime: bool = True):
        self.path = path
        self.loop = loop
        self.realtime = realtime              # pace read() at the recording's frame rate (tests turn this off)
        self._source: Optional[FlirFileSource] = None
        self._index = 0
        self._celsius: Optional[np.ndarray] = None
        self._next_due = 0.0
        self._lock = threading.Lock()
        self.last_error: Optional[str] = None

    # ---- CameraBackend
    def is_available(self) -> bool:
        from thermal_inspection.sdk.flir_file_reader import flirpy_can_read_files
        return flirpy_can_read_files()

    def open(self) -> bool:
        try:
            self._source = FlirFileSource(self.path)
        except FlirFileError as e:
            self.last_error = str(e)
            logger.error(f"FLIR file backend: {e}")
            return False
        self._index = 0
        self._next_due = 0.0
        self.last_error = None
        logger.info(f"Playing {self._source.describe()}")
        return True

    def read(self, flush_buffer: bool = False) -> Tuple[bool, Optional[np.ndarray]]:
        src = self._source
        if src is None:
            return False, None
        with self._lock:
            if self._index >= len(src):
                if not self.loop:
                    return False, None
                self._index = 0
            index = self._index
            self._index += 1
        if self.realtime:
            now = time.monotonic()
            if self._next_due > now:
                time.sleep(self._next_due - now)
            self._next_due = max(now, self._next_due) + 1.0 / src.fps
        try:
            y16, celsius, _ = src.read(index)
        except Exception as e:
            logger.error(f"FLIR file backend: frame {index} unreadable: {e}")
            return False, None
        self._celsius = celsius
        return True, y16

    def release(self):
        self._source = None
        self._celsius = None

    def is_opened(self) -> bool:
        return self._source is not None

    def get_info(self) -> Dict[str, Any]:
        info = {"backend": "FLIR file", "type": "thermal", "bit_depth": 16, "radiometric": True,
                "resolution": self.get_resolution(), "features": ["playback", "loop", "per-frame calibration"]}
        if self._source is not None:
            info.update(self._source.describe())
        return info

    def get_resolution(self) -> Optional[Tuple[int, int]]:
        return (self._source.width, self._source.height) if self._source is not None else None

    # ---- ThermalBackend
    def is_radiometric(self) -> bool:
        return True

    def get_temperature_map(self) -> Optional[np.ndarray]:
        return self._celsius

    def get_spot_temperature(self, x: int, y: int) -> Optional[float]:
        c = self._celsius
        if c is None or not (0 <= y < c.shape[0] and 0 <= x < c.shape[1]):
            return None
        return float(c[y, x])

    def supports_sdk_control(self) -> bool:
        return False

    # ---- playback controls
    @property
    def frame_count(self) -> int:
        return len(self._source) if self._source is not None else 0

    @property
    def position(self) -> int:
        return self._index

    def seek(self, index: int):
        with self._lock:
            self._index = max(0, min(int(index), max(0, self.frame_count - 1)))
