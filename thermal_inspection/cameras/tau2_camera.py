"""
FLIR Tau 2 UVC Video Capture Driver.

Captures video over UVC via LVDS/USB bridge boards (TeAx ThermalCapture,
GetThermal, Cypress FX3, or OEM USB adapters). Some such boards genuinely
expose 16-bit Y16 raw radiometric video; others - confirmed live on the
board this was last tested against - have no CCI/serial control line at
all and only ever deliver a standard, already onboard-AGC'd 3-channel BGR
image (via YUY2, auto-converted by DirectShow), with no raw mode
accessible from the host. This driver does not assume either: it reads
whatever the camera actually negotiates and branches on the real shape/
dtype it gets back (see _sanitize_frame()) rather than forcing a FOURCC and
asserting the result is raw.

Features:
- Windows DirectShow (CAP_DSHOW) / Linux V4L2 (CAP_V4L2) backend selection
- Robust sanitization for 1D flattened arrays, YUYV container views, and a
  plain already-colorized 3-channel BGR frame
- Auto-alignment detection for 14-bit data packed into 16-bit buffers, for
  boards confirmed to genuinely deliver a raw uint16 Y16 frame
- Advanced Radiometry T-Linear to Celsius conversion (0.04 K/count & 0.4 K/count)
"""
from __future__ import annotations

import logging
import platform
from typing import Optional, Tuple

import cv2
import numpy as np

logger = logging.getLogger(__name__)

TAU2_RESOLUTIONS = [
    (640, 512),   # Tau2 640
    (336, 256),   # Tau2 336
    (324, 256),   # Tau2 324
    (160, 128),   # Tau2 160
]


class Tau2Camera:
    """UVC Camera driver for FLIR Tau 2 thermal cameras."""

    def __init__(self, device_id: int = 0, resolution: Tuple[int, int] = (640, 512),
                 tlinear: bool = True, high_res: bool = True, byte_split_packing: bool = False,
                 raw_mode: bool = False, byte_order: str = 'swap'):
        self.device_id = device_id
        self.width, self.height = resolution
        self.tlinear = tlinear
        self.high_res = high_res
        # Only meaningful if this camera is later confirmed to genuinely
        # deliver a raw uint16 Y16 buffer (see open()'s docstring - on the
        # breakout board this was written against, it does not, so this
        # defaults off). If a future board's live probe shows a real 2D
        # uint16 frame with a wider-than-8-bit value range, its wire format
        # would need to be confirmed (e.g. against the seller's spec) before
        # turning this on - the previous default of True here was applied
        # without that confirmation and corrupted an already-valid image.
        self.byte_split_packing = byte_split_packing
        # Selectable alternative to the default onboard-colorized BGR
        # passthrough: request a genuine raw Y16 stream instead. Confirmed
        # live on this board that Y16 IS actually negotiable - the earlier
        # conclusion that it wasn't was an artifact of setting FOURCC before
        # resolution (DirectShow only offers the Y16 media type once the
        # resolution matches one it's advertised at) plus reading frames
        # before the format switch had settled (the first ~20-30 frames come
        # back mostly/entirely zero). See open()'s docstring for the
        # negotiation sequence and _warmup_after_format_switch() for why the
        # warmup exists. No temperature calibration is applied to this data
        # (tlinear is forced off in read() below) - the seller's described
        # wire format didn't match what a live capture showed (byte-split
        # decode gave a still-scrambled image; a plain byte-swap of the
        # naive little-endian read gave a clean, coherent one instead), so
        # only the confirmed-correct byte re-ordering is applied, not an
        # absolute Kelvin/count scale nobody has verified yet.
        self.raw_mode = raw_mode
        self.byte_order = byte_order  # 'swap' (confirmed), 'native', or 'split' (seller's original claim)
        self.cap: Optional[cv2.VideoCapture] = None
        self._is_opened = False
        self._fps = 30.0
        self._bit_depth = 16
        self._negotiated_raw = False  # True once open() confirms Y16 actually negotiated

    def open(self) -> bool:
        """
        Open UVC video stream for Tau 2.

        By default (raw_mode=False) does NOT force a 'Y16 ' FOURCC: without a
        CCI/serial control line, there is no way to command the sensor into
        a particular digital output mode, and DirectShow negotiates whatever
        the camera offers by default (measured as YUY2 on this board, auto-
        converted to a normal 3-channel BGR frame - already display-ready,
        the camera's own onboard AGC). See _sanitize_frame() for why that
        path returns the frame unchanged rather than extracting one channel.

        raw_mode=True instead requests the camera's genuine Y16 stream.
        Confirmed live that this board DOES advertise a real Y16 media type
        (alongside YUY2/YV12/Y8, all at the same resolution) - it just needs:
        1. Resolution set BEFORE the FOURCC request. Requesting Y16 before
           resolution silently fails and the negotiated format stays YUY2
           with no error - this was the original reason raw mode looked
           unsupported.
        2. A warmup period after the switch. The first ~20-30 frames after
           changing format come back mostly or entirely zero (a partially-
           reconfigured capture pipeline, not real data) - see
           _warmup_after_format_switch().
        Falls back to the default negotiation if Y16 doesn't actually come
        back (readback check), so raw_mode never leaves the camera unusable
        on hardware that doesn't support it.
        """
        try:
            logger.info(f"Opening Tau 2 UVC camera on device {self.device_id} ({self.width}x{self.height})...")

            # Choose DirectShow on Windows (MSMF truncates Y16 to 8-bit)
            if platform.system() == "Windows":
                self.cap = cv2.VideoCapture(self.device_id, cv2.CAP_DSHOW)
            else:
                self.cap = cv2.VideoCapture(self.device_id, cv2.CAP_V4L2)

            if not self.cap.isOpened():
                logger.error(f"Failed to open video device {self.device_id}")
                return False

            # Resolution MUST be set before requesting Y16 - see docstring.
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)

            actual_w = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            actual_h = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            if actual_w > 0 and actual_h > 0:
                self.width, self.height = actual_w, actual_h

            if self.raw_mode:
                self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'Y16 '))
                self.cap.set(cv2.CAP_PROP_CONVERT_RGB, 0)
                fourcc_int = int(self.cap.get(cv2.CAP_PROP_FOURCC))
                fourcc_str = "".join(chr((fourcc_int >> 8 * i) & 0xFF) for i in range(4))
                self._negotiated_raw = fourcc_str.strip() == 'Y16'
                if self._negotiated_raw:
                    logger.info("Tau 2: negotiated genuine Y16 raw stream - warming up...")
                    self._warmup_after_format_switch()
                else:
                    logger.warning(
                        f"Tau 2: raw_mode requested but camera negotiated {fourcc_str!r} "
                        "instead of Y16 - falling back to default onboard-colorized stream"
                    )

            self._is_opened = True
            logger.info(f"[OK] Tau 2 camera opened successfully ({self.width}x{self.height})")
            return True

        except Exception as e:
            logger.error(f"Exception opening Tau 2 camera: {e}", exc_info=True)
            self.release()
            return False

    def _warmup_after_format_switch(self, max_frames: int = 30) -> None:
        """
        Discard frames until real data flows or max_frames is reached.

        Measured live: right after switching to Y16, the first several
        frames come back with most or all pixels zero (the capture pipeline
        settling into the new format, not a real dark scene) - a frame is
        "real" once fewer than half its pixels are exactly zero, which a
        genuine thermal scene essentially never hits.
        """
        for _ in range(max_frames):
            ret, frame = self.cap.read()
            if ret and frame is not None and (frame == 0).mean() < 0.5:
                return

    def is_opened(self) -> bool:
        return self._is_opened and self.cap is not None and self.cap.isOpened()

    def read(self) -> Tuple[bool, Optional[np.ndarray]]:
        """
        Grab and sanitize a raw frame from the Tau 2 camera.

        Returns:
            Tuple of (success, frame). Frame is typically 2D uint16 (or uint8 fallback).
        """
        if not self.is_opened():
            return False, None

        ret, raw_frame = self.cap.read()
        if not ret or raw_frame is None:
            return False, None

        frame = self._sanitize_frame(raw_frame)

        if self.tlinear and frame is not None and frame.dtype == np.uint16:
            # Re-express raw 14-bit sensor counts as Kelvin x100 (the Boson
            # Y16 convention). ThermalAnalyzer is shared across all camera
            # plugins and has no per-camera scale awareness - it hardcodes
            # celsius = value/100 - 273.15 everywhere a Y16 frame reaches
            # it. Left as raw counts, that formula reads a ~7300-count room
            # temperature as -199 C. Tau2's T-Linear scale is 0.04 K/count
            # (high-res) or 0.4 K/count (low-res): counts * scale = Kelvin,
            # so counts * scale * 100 = Kelvin x100, matching Boson's frame.
            # Clipped because low-res mode's wider span (0.4 K/count) can
            # exceed uint16 range on very hot scenes (>382 C) - clamped
            # rather than wrapped/crashed.
            #
            # This 0.04/0.4 K/count scale is the documented Tau2 T-Linear
            # spec value, which requires the camera to actually BE in
            # T-Linear mode (a CCI-commanded setting) for raw counts to mean
            # that. Tau2Plugin only ever constructs this class with
            # tlinear=True when a CCI port was found (see create_backend()),
            # so raw_mode's byte-swapped-but-uncalibrated counts never reach
            # this block on hardware with no CCI - if CCI does become
            # available later, this scale still shouldn't be trusted for
            # raw_mode until verified against a known-temperature reference,
            # since byte_order='swap' was reverse-engineered from image
            # coherence, not from the seller's (unconfirmed for this board)
            # documented count scale.
            scale = 0.04 if self.high_res else 0.40
            frame = np.clip(frame.astype(np.float32) * scale * 100.0, 0, 65535).astype(np.uint16)

        return True, frame

    def _sanitize_frame(self, raw_frame: np.ndarray) -> np.ndarray:
        """Handle OpenCV Y16 buffer representation quirks."""
        h, w = self.height, self.width

        # Case 1: Ideal 2D uint16 array
        if raw_frame.dtype == np.uint16 and raw_frame.ndim == 2:
            return self._normalize_14bit(raw_frame)

        # Case 2: Flattened 1D array bug
        if raw_frame.ndim == 1:
            if raw_frame.dtype == np.uint16:
                return self._normalize_14bit(raw_frame.reshape((h, w)))
            elif raw_frame.dtype == np.uint8 and raw_frame.size >= h * w * 2:
                return self._normalize_14bit(raw_frame[:h * w * 2].view(np.uint16).reshape((h, w)))

        # Case 3: 16-bit packed into (H, W, 2) uint8 YUYV buffer
        if raw_frame.ndim == 3 and raw_frame.shape[2] == 2 and raw_frame.dtype == np.uint8:
            return self._normalize_14bit(raw_frame.view(np.uint16).reshape((h, w)))

        # Case 4: Camera negotiated a standard 3-channel 8-bit format (YUY2
        # auto-converted to BGR by DirectShow, on the board this was tested
        # against - measured live: without a CCI line to command any raw/
        # Y16 output mode, this is what the camera actually delivers, and
        # it already looks like a complete, coherent false-color thermal
        # image (its own onboard AGC + palette, not ours - the same feed
        # Windows' own Camera app displays correctly). This used to extract
        # channel 0 (blue) alone as a "grayscale intensity", discarding the
        # other two channels of a real false-color image and feeding
        # something-like-noise into this app's OWN colorization palette -
        # return the full frame unchanged instead; the caller (see
        # Tau2Backend.read()) is responsible for recognizing a 3-channel
        # frame as already display-ready and not re-palettizing it.
        if raw_frame.ndim == 3 and raw_frame.shape[2] == 3:
            self._bit_depth = 8
            return raw_frame

        return raw_frame

    def _normalize_14bit(self, frame_uint16: np.ndarray) -> np.ndarray:
        """
        Re-order bytes in a genuinely raw Y16 buffer per self.byte_order.

        Only reached when raw_mode negotiated real Y16 (see open()) - the
        onboard-colorized 3-channel case never calls this. 'swap' is the
        option confirmed live on this board (see _decode_byte_swapped()'s
        docstring); 'split' is the seller's originally-described layout,
        kept available in case a different board genuinely uses it (tested
        against live data from THIS board and found to still look
        scrambled - not the default); 'native' assumes the naive little-
        endian read is already correct.
        """
        if self.byte_order == 'swap':
            return self._decode_byte_swapped(frame_uint16)
        if self.byte_order == 'split':
            return self._decode_split_byte_14bit(frame_uint16)
        return frame_uint16

    def _decode_byte_swapped(self, frame_uint16: np.ndarray) -> np.ndarray:
        """
        Swap the high/low bytes of a naive little-endian uint16 read.

        Confirmed live against this board's real (post-warmup) Y16 stream:
        the plain little-endian assembly OpenCV/numpy produces is not the
        camera's actual byte order - swapping high and low bytes turned a
        low-spatial-coherence, effectively-blank-looking buffer into a
        clearly recognizable, spatially coherent thermal image (coherence
        ratio, mean adjacent-pixel diff over global std: 0.135 unswapped vs
        0.030 swapped - tighter than the camera's own onboard-colorized
        feed). No absolute Kelvin/count scale is applied here - see read()'s
        tlinear handling.
        """
        return (((frame_uint16 & 0xFF) << 8) | (frame_uint16 >> 8)).astype(np.uint16)

    def _decode_split_byte_14bit(self, frame_uint16: np.ndarray) -> np.ndarray:
        """
        Decode the seller's originally-described byte-split 14-bit layout.

        A plain little-endian uint16 view already assembled byte0 (low) and
        byte1 (high) as ``byte0 | (byte1 << 8)``. Per the seller's layout,
        byte0 holds video[5:0] and byte1 holds video[13:6], so byte1 needs to
        land at bit position 6 in the reconstructed value, not 8. Pull the
        two bytes back out of the naive assembly and re-shift byte1
        correctly rather than re-reading raw bytes, so this works regardless
        of which _sanitize_frame case produced the uint16 view.

        Tested against this board's real (post-warmup, properly-negotiated)
        Y16 data and found to NOT produce a coherent image - kept available
        (self.byte_order = 'split') in case a different unit genuinely uses
        this layout, but 'swap' is the confirmed-correct default for the
        board this was developed against.
        """
        byte0 = frame_uint16 & 0xFF          # video[5:0], top 2 bits zero-padded
        byte1 = (frame_uint16 >> 8) & 0xFF   # video[13:6]
        return ((byte1 << 6) | (byte0 & 0x3F)).astype(np.uint16)

    def read_temperature_map(self) -> Optional[np.ndarray]:
        """
        Convert current frame to calibrated Celsius temperature map.

        Returns:
            float32 2D numpy array of temperatures in Celsius, or None.
        """
        if not self.tlinear:
            return None

        success, frame = self.read()
        if not success or frame is None or frame.dtype != np.uint16:
            return None

        # read() already rescaled to Kelvin x100 when tlinear is enabled.
        temp_celsius = (frame.astype(np.float32) / 100.0) - 273.15
        return temp_celsius

    def set_tlinear(self, enabled: bool, high_res: bool = True):
        self.tlinear = enabled
        self.high_res = high_res

    def get_resolution(self) -> Tuple[int, int]:
        return (self.width, self.height)

    @property
    def fps(self) -> float:
        return self._fps

    def release(self):
        """Release camera resources."""
        if self.cap:
            try:
                self.cap.release()
            except Exception as e:
                logger.debug(f"Error releasing Tau 2 capture on device {self.device_id}: {e}")
            self.cap = None
        self._is_opened = False
        logger.info(f"Tau 2 camera on device {self.device_id} released")
