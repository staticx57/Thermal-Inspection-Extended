"""
Shared video device enumeration for camera plugin detection.

Opening a video device with ``cv2.VideoCapture`` is expensive — roughly 0.5-1s
per index on Windows (DirectShow/MSMF negotiate formats on open). Each camera
plugin used to run its own independent probe loop over device indices 0..3,
so a single ``autodiscover()`` opened the same handful of physical devices a
dozen or more times and cost ~17s on a machine with one webcam attached.

This module probes each device index exactly once, caches the snapshot for the
lifetime of the process, and hands the same result to every plugin's
``detect()``. Plugins filter the shared snapshot by resolution/name instead of
touching hardware themselves.

The probe also performs a real frame read, not just ``isOpened()``. Phantom
DirectShow filters registered by vendor SDKs (Basler GenICam, Pleora eBUS)
open successfully but never deliver frames, so the frame read is what
distinguishes a real camera from an installed-but-unused capture filter.
"""
from __future__ import annotations

import logging
import platform
import threading
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import cv2

logger = logging.getLogger(__name__)

# Probe this many indices when the OS gives us no device list to size the sweep.
DEFAULT_MAX_DEVICES = 6


@dataclass(frozen=True)
class VideoDevice:
    """A video capture device that was successfully opened and read from."""

    index: int
    name: str
    width: int
    height: int

    @property
    def resolution(self) -> Tuple[int, int]:
        return (self.width, self.height)


_scan_lock = threading.Lock()
_cached_devices: Optional[List[VideoDevice]] = None


def _enumerate_dshow_devices() -> List[str]:
    """Build a DirectShow filter graph and read its input device names."""
    from pygrabber.dshow_graph import FilterGraph

    return FilterGraph().get_input_devices()


def _list_device_names() -> List[str]:
    """
    Get OS-level device names without opening any capture handles.

    DirectShow enumeration requires a single-threaded (STA) COM apartment, but
    the application deliberately starts up in MTA (``sys.coinit_flags = 0`` in
    ``__main__.py``) so OpenCV's DirectShow capture works on the main thread.
    Enumerating from the MTA main thread silently yields zero devices, which
    would disable the persisted fast path and leave us blind-probing a fixed
    index range on every launch.

    COM apartments are per-thread, so the enumeration runs on a short-lived
    worker thread that initialises its own STA apartment.

    Returns an empty list on platforms/systems where enumeration is
    unavailable; callers must not assume index alignment with real devices.
    """
    if platform.system() != "Windows":
        return []

    result: List[str] = []
    error: List[Exception] = []

    def worker():
        com_ready = False
        try:
            import comtypes

            try:
                comtypes.CoInitialize()  # STA
                com_ready = True
            except Exception as exc:
                # Already initialised on this thread, or COM unavailable.
                logger.debug(f"CoInitialize skipped: {exc}")
            result.extend(_enumerate_dshow_devices())
        except Exception as exc:
            error.append(exc)
        finally:
            if com_ready:
                try:
                    import comtypes

                    comtypes.CoUninitialize()
                except Exception:
                    pass

    thread = threading.Thread(target=worker, name="DShowEnumerate", daemon=True)
    thread.start()
    thread.join(timeout=10.0)

    if thread.is_alive():
        logger.warning("DirectShow enumeration timed out")
        return []
    if error:
        logger.debug(f"DirectShow device enumeration unavailable: {error[0]}")
        return []
    return result


def _open_capture(index: int) -> Optional[cv2.VideoCapture]:
    """Try platform-appropriate backends in order, returning the first that opens."""
    if platform.system() == "Windows":
        backends = [cv2.CAP_DSHOW, cv2.CAP_MSMF, None]
    else:
        backends = [cv2.CAP_V4L2, None]

    for backend in backends:
        cap = None
        try:
            cap = cv2.VideoCapture(index) if backend is None else cv2.VideoCapture(index, backend)
            if cap.isOpened():
                return cap
            cap.release()
        except Exception as exc:
            logger.debug(f"Backend {backend} failed to open device {index}: {exc}")
            if cap is not None:
                cap.release()
    return None


def _probe_device(index: int, names: List[str]) -> Optional[VideoDevice]:
    """Open one device index, read a frame to confirm it is real, and record its geometry."""
    cap = _open_capture(index)
    if cap is None:
        return None

    try:
        ok, _frame = cap.read()
        if not ok:
            # Opens but never delivers frames — a registered filter, not a camera.
            logger.debug(f"Device {index} opened but returned no frame; skipping")
            return None

        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        name = names[index] if index < len(names) else f"Video Device {index}"
        logger.info(f"Detected video device {index} ({name}): {width}x{height}")
        return VideoDevice(index=index, name=name, width=width, height=height)
    except Exception as exc:
        logger.debug(f"Error probing device {index}: {exc}")
        return None
    finally:
        cap.release()


def _load_fast_path(names: List[str]) -> Optional[List[VideoDevice]]:
    """
    Return the persisted scan if it still matches the current hardware.

    The OS device-name list is the fingerprint: enumerating it costs nothing
    (no capture handles are opened), so if it is byte-for-byte what we saw when
    the cache was written, the same devices are attached in the same order and
    the stored resolutions are still valid. Any difference at all — a camera
    added, removed, or reordered — invalidates the whole cache and forces a
    full probe.
    """
    if not names:
        # Without a device list there is no fingerprint to validate against.
        return None

    try:
        from thermal_inspection.utils.config import get_config

        cached = get_config().get('video_device_cache') or {}
    except Exception as exc:
        logger.debug(f"Could not read persisted device scan: {exc}")
        return None

    if cached.get('device_names') != names:
        return None

    try:
        devices = [
            VideoDevice(index=d['index'], name=d['name'], width=d['width'], height=d['height'])
            for d in cached.get('devices', [])
        ]
    except (KeyError, TypeError) as exc:
        logger.debug(f"Persisted device scan is malformed, ignoring: {exc}")
        return None

    logger.info(f"Fast path: reusing persisted scan of {len(devices)} device(s)")
    return devices


def _save_fast_path(names: List[str], devices: List[VideoDevice]) -> None:
    """Persist a completed scan alongside the device-name fingerprint that produced it."""
    if not names:
        return
    try:
        from thermal_inspection.utils.config import get_config

        # Config.set() persists to disk by default.
        get_config().set('video_device_cache', {
            'device_names': names,
            'devices': [
                {'index': d.index, 'name': d.name, 'width': d.width, 'height': d.height}
                for d in devices
            ],
        })
    except Exception as exc:
        logger.debug(f"Could not persist device scan: {exc}")


def scan_video_devices(force: bool = False) -> List[VideoDevice]:
    """
    Enumerate all usable video capture devices, probing hardware at most once.

    Results are cached in-process, and persisted across runs when the OS device
    list is available (see ``_load_fast_path``), so a warm start opens no
    capture handles at all.

    Args:
        force: Re-probe hardware, bypassing both the in-process and persisted
            caches. Use after a hot-plug event; normal detection paths should
            leave this False.

    Returns:
        Devices that opened and delivered at least one frame.
    """
    global _cached_devices

    with _scan_lock:
        if _cached_devices is not None and not force:
            return list(_cached_devices)

        names = _list_device_names()

        if not force:
            fast_path = _load_fast_path(names)
            if fast_path is not None:
                _cached_devices = fast_path
                return list(fast_path)

        # Trust the OS device count when we have one; otherwise sweep a fixed range.
        max_devices = len(names) if names else DEFAULT_MAX_DEVICES

        devices: List[VideoDevice] = []
        for index in range(max_devices):
            device = _probe_device(index, names)
            if device is not None:
                devices.append(device)

        _cached_devices = devices
        _save_fast_path(names, devices)
        logger.info(f"Video device scan complete: {len(devices)} usable device(s) of {max_devices} probed")
        return list(devices)


def invalidate_cache() -> None:
    """
    Drop the cached scan so the next ``scan_video_devices()`` re-probes hardware.

    Clears both the in-process cache and the persisted fast path. The
    persisted entry is keyed only by the OS device-name list (see
    ``_load_fast_path``), so a caller invalidating for a reason other than
    "the device list changed" — e.g. a camera failed its frame-read check —
    would otherwise have the stale result handed straight back from disk,
    with no hardware actually re-probed.
    """
    global _cached_devices
    with _scan_lock:
        _cached_devices = None
        try:
            from thermal_inspection.utils.config import get_config
            get_config().set('video_device_cache', None)
        except Exception as exc:
            logger.debug(f"Could not clear persisted device scan: {exc}")
    logger.debug("Video device scan cache invalidated")


def find_devices_by_resolution(resolutions: List[Tuple[int, int]],
                               tolerance: int = 0) -> List[VideoDevice]:
    """
    Return cached devices whose resolution matches one of ``resolutions``.

    Args:
        resolutions: Acceptable (width, height) pairs.
        tolerance: Per-axis pixel slack. 0 requires an exact match.
    """
    matches = []
    for device in scan_video_devices():
        for width, height in resolutions:
            if abs(device.width - width) <= tolerance and abs(device.height - height) <= tolerance:
                matches.append(device)
                break
    return matches


def get_device_map() -> Dict[int, VideoDevice]:
    """Return the cached scan keyed by device index."""
    return {device.index: device for device in scan_video_devices()}
