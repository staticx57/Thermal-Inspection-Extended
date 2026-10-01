"""
Reader for FLIR radiometric recordings (.seq sequences and single .fff frames), built on flirpy's io module (the
SEQ/FFF support that is new and much more robust in flirpy 0.6: frame extents come from each FFF header's record
directory instead of searching for the magic bytes, which also occur inside image data).

A FLIR file stores raw sensor counts plus the Planck calibration constants and the environmental settings in force
(emissivity, distance, atmosphere, reflected temperature, window). flirpy's raw2temp turns that into Celsius per frame.
This module hands the rest of the app what a live radiometric Boson provides: a uint16 Y16 frame (Kelvin x 100) plus
the Celsius map, so every temperature consumer works unchanged on a recording.

Not supported: .csq (FLIR's compressed sequence, JPEG-LS frames) - flirpy cannot decode it; export to .seq in FLIR Tools.
"""
import logging
import os
from typing import Any, Dict, Tuple

import numpy as np

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = (".seq", ".fff")
DEFAULT_FPS = 9.0
MAX_Y16 = 65535


class FlirFileError(Exception):
    """The file cannot be used (missing, unsupported format, no frames)."""


MIN_FLIRPY = (0, 6)


def flirpy_version():
    """Installed flirpy version as a tuple, or None when flirpy is missing."""
    import re
    from importlib import metadata
    try:
        return tuple(int(x) for x in re.findall(r"\d+", metadata.version("flirpy"))[:3])
    except metadata.PackageNotFoundError:
        return None


def flirpy_can_read_files() -> bool:
    """flirpy 0.3 finds FFF frames by searching for magic bytes and fails on many real files; 0.6 walks each FFF
    header's record directory. Playback relies on the latter."""
    v = flirpy_version()
    return v is not None and v[:2] >= MIN_FLIRPY


def celsius_to_y16(celsius: np.ndarray) -> np.ndarray:
    """Celsius -> the Boson's T-Linear Y16 convention (Kelvin x 100), clipped to the uint16 range (0 .. 382 C)."""
    y = np.rint((np.asarray(celsius, dtype=np.float64) + 273.15) * 100.0)
    return np.clip(np.nan_to_num(y, nan=0.0, posinf=MAX_Y16, neginf=0.0), 0, MAX_Y16).astype(np.uint16)


class FlirFileSource:
    """Random access to the frames of a .seq / .fff file."""

    def __init__(self, path: str):
        ext = os.path.splitext(path)[1].lower()
        if ext == ".csq":
            raise FlirFileError(".csq (compressed FLIR sequence) cannot be decoded; export it to .seq in FLIR Tools")
        if ext not in SUPPORTED_EXTENSIONS:
            raise FlirFileError(f"Unsupported file type '{ext}' (expected {', '.join(SUPPORTED_EXTENSIONS)})")
        if not os.path.isfile(path):
            raise FlirFileError(f"File not found: {path}")
        if not flirpy_can_read_files():
            raise FlirFileError(f"Reading FLIR files needs flirpy >= 0.6 (installed: {flirpy_version()}): "
                                "pip install -U flirpy   (it brings opencv-python-headless; see requirements.txt)")
        from flirpy.io.fff import Fff
        from flirpy.io.seq import Seq
        self.path = path
        try:
            if ext == ".seq":
                self._seq = Seq(path)
                self._single = None
            else:
                self._seq = None
                self._single = Fff(path)
        except Exception as e:
            raise FlirFileError(f"Could not parse {os.path.basename(path)}: {e}")
        if len(self) == 0:
            raise FlirFileError(f"{os.path.basename(path)} contains no frames")
        first = self._frame(0)
        self.height, self.width = first.get_image().shape[:2]
        self.meta: Dict[str, Any] = dict(first.meta)
        self.meta.update(self._identity_strings(first))

    @staticmethod
    def _identity_strings(frame) -> Dict[str, str]:
        """Serial number and firmware, read from the camera-info record at their ExifTool offsets (0x104 / 0x114).
        flirpy 0.6 reads these two at decimal 104 / 114, which lands inside other fields and returns overlapping
        garbage, so they are taken directly here."""
        out: Dict[str, str] = {}
        try:
            for rec in frame.records:
                if rec.record_type != 0x20:
                    continue
                blob = frame.data[rec.record_offset:rec.record_offset + rec.record_length]
                for key, off in (("CameraSerialNumber", 0x104), ("CameraSoftware", 0x114)):
                    chunk = blob[off:off + 16]
                    text = chunk.split(b"\x00")[0].decode("ascii", errors="ignore").strip()
                    if text and text.isprintable():
                        out[key] = text
        except Exception as e:                                       # identity is cosmetic: never block playback
            logger.debug(f"Could not read camera identity strings: {e}")
        return out

    def __len__(self) -> int:
        return len(self._seq) if self._seq is not None else 1

    def _frame(self, index: int):
        return self._seq[index] if self._seq is not None else self._single

    @property
    def fps(self) -> float:
        rate = self.meta.get("FrameRate")
        return float(rate) if isinstance(rate, (int, float)) and 0 < rate <= 1000 else DEFAULT_FPS

    def read(self, index: int) -> Tuple[np.ndarray, np.ndarray, Dict[str, Any]]:
        """(y16 uint16, celsius float32, meta) for frame `index`. Temperatures use that frame's own calibration."""
        if not 0 <= index < len(self):
            raise IndexError(index)
        frame = self._frame(index)
        celsius = np.asarray(frame.get_radiometric_image(dtype="float"), dtype=np.float32)
        return celsius_to_y16(celsius), celsius, frame.meta

    def describe(self) -> Dict[str, Any]:
        def text(key):
            v = self.meta.get(key)
            return v.decode(errors="ignore").strip("\x00 ") if isinstance(v, (bytes, bytearray)) else v
        return {
            "file": os.path.basename(self.path), "frames": len(self), "fps": self.fps,
            "resolution": (self.width, self.height),
            "model": text("CameraModel"), "serial": text("CameraSerialNumber"), "lens": text("LensModel"),
            "emissivity": self.meta.get("Emissivity"), "object_distance_m": self.meta.get("Object Distance"),
            "reflected_c": self.meta.get("Reflected Apparent Temperature"),
            "atmospheric_c": self.meta.get("Atmospheric Temperature"),
            "humidity": self.meta.get("Relative Humidity"),
        }
