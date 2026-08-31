"""
Camera Monitoring Service
Monitors camera connections and disconnections in background thread
Supports hot-plugging and automatic reconnection
"""
import time
import threading
import logging
from typing import Callable, Optional, Set
from dataclasses import dataclass
from enum import Enum

from thermal_inspection.cameras.camera_detector import CameraDetector, CameraInfo
from thermal_inspection.cameras.camera_registry import get_camera_registry, CameraRole

logger = logging.getLogger(__name__)


class CameraEventType(Enum):
    """Types of camera events"""
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    ROLE_CHANGED = "role_changed"


@dataclass
class CameraEvent:
    """Camera state change event"""
    event_type: CameraEventType
    device_id: int
    camera_info: Optional[CameraInfo] = None
    role: Optional[CameraRole] = None


class CameraMonitor:
    """
    Background service that monitors camera connections/disconnections

    Features:
    - Periodic scanning for new cameras
    - Detection of camera disconnections
    - Integration with camera registry
    - Callback notifications for state changes
    """

    def __init__(self, scan_interval: float = 3.0, callback: Optional[Callable[[CameraEvent], None]] = None):
        """
        Initialize camera monitor

        Args:
            scan_interval: Seconds between camera scans (default: 3.0)
            callback: Function to call when camera state changes
        """
        self.scan_interval = scan_interval
        self.callback = callback
        self.registry = get_camera_registry()

        # State tracking
        self.running = False
        self.thread: Optional[threading.Thread] = None
        self.known_device_ids: Set[int] = set()
        self.active_device_ids: Set[int] = set()  # Currently in use by application

        # Cheap hot-plug fingerprint: the OS device-name list. A full
        # detect_all_cameras() sweep costs ~10s because it renegotiates
        # resolutions and reads frames, so we only pay for it when this
        # fingerprint actually changes. None means "not yet sampled".
        self._last_device_fingerprint: Optional[list] = None
        # Tracked separately from _last_device_fingerprint: that attribute is
        # None both "before the first scan" and "fingerprint unavailable this
        # tick", so it alone can't tell first-scan apart from a fingerprint
        # outage. Conflating them left auto cache-invalidation permanently
        # disabled whenever enumeration was ever unavailable.
        self._has_scanned_once = False

        logger.info(f"Camera monitor initialized (scan interval: {scan_interval}s)")

    @staticmethod
    def _device_fingerprint() -> Optional[list]:
        """
        Snapshot the OS video-device list without opening any capture handles.

        Returns None when enumeration is unavailable, which callers must treat
        as "cannot tell — do the full scan".
        """
        try:
            from thermal_inspection.cameras.device_scanner import _list_device_names
            names = _list_device_names()
            return names if names else None
        except Exception as exc:
            logger.debug(f"Device fingerprint unavailable: {exc}")
            return None

    def start(self):
        """Start monitoring in background thread"""
        if self.running:
            logger.warning("Camera monitor already running")
            return

        self.running = True
        self.thread = threading.Thread(target=self._scan_loop, daemon=True, name="CameraMonitor")
        self.thread.start()
        logger.info("Camera monitor started")

    def stop(self):
        """Stop monitoring thread"""
        if not self.running:
            return

        self.running = False
        if self.thread:
            self.thread.join(timeout=5.0)
            self.thread = None
        logger.info("Camera monitor stopped")

    def mark_device_active(self, device_id: int):
        """
        Mark a device as actively in use by the application
        This prevents the monitor from trying to probe it

        Args:
            device_id: Camera device ID in use
        """
        self.active_device_ids.add(device_id)
        logger.debug(f"Device {device_id} marked as active")

    def mark_device_inactive(self, device_id: int):
        """
        Mark a device as no longer in use

        Args:
            device_id: Camera device ID no longer in use
        """
        self.active_device_ids.discard(device_id)
        logger.debug(f"Device {device_id} marked as inactive")

    def force_scan(self):
        """Force an immediate full camera scan (non-blocking)"""
        logger.info("Forcing immediate camera scan")
        threading.Thread(
            target=self._perform_scan,
            kwargs={"force": True},
            daemon=True,
            name="ForcedCameraScan",
        ).start()

    def _scan_loop(self):
        """Main monitoring loop (runs in background thread)"""
        logger.info("Camera monitoring loop started")

        while self.running:
            try:
                self._perform_scan()
            except Exception as e:
                logger.error(f"Error in camera scan: {e}", exc_info=True)

            # Sleep with frequent checks to allow quick shutdown
            for _ in range(int(self.scan_interval * 10)):
                if not self.running:
                    break
                time.sleep(0.1)

        logger.info("Camera monitoring loop stopped")

    def _perform_scan(self, force: bool = False):
        """
        Perform a single scan for camera changes.

        A full detection sweep is expensive (it renegotiates resolutions and
        reads frames), so it is skipped entirely while the cheap OS device
        fingerprint is unchanged — nothing can have been plugged in or removed
        without that list changing.

        Args:
            force: Run the full sweep regardless of the fingerprint.
        """
        fingerprint = self._device_fingerprint()
        is_first_scan = not self._has_scanned_once
        fingerprint_unavailable = fingerprint is None
        # When enumeration is unavailable we cannot cheaply tell whether
        # hardware changed, so treat every such tick as "changed" — this
        # matches the full scan below, which already runs unconditionally in
        # that state (see the early-return guard just below).
        hardware_changed = not is_first_scan and (
            fingerprint_unavailable or fingerprint != self._last_device_fingerprint
        )

        if not force and not is_first_scan and not fingerprint_unavailable and not hardware_changed:
            logger.debug("Device list unchanged — skipping full camera scan")
            return

        if hardware_changed:
            logger.info(
                "Device list changed — running full camera scan"
                if not fingerprint_unavailable else
                "Device enumeration unavailable — running full camera scan"
            )

        self._has_scanned_once = True
        self._last_device_fingerprint = fingerprint

        # Only drop the shared scan when hardware actually moved (or we can't
        # tell, which we treat the same way). On the first tick the cache was
        # just built by startup discovery, and throwing it away would make
        # every plugin re-probe for nothing.
        if hardware_changed or force:
            from thermal_inspection.cameras.device_scanner import invalidate_cache
            invalidate_cache()

        # Detect all available cameras (skip devices that are actively in use)
        skip_ids = list(self.active_device_ids)
        cameras = CameraDetector.detect_all_cameras(
            skip_device_ids=skip_ids,
            register_cameras=True  # Automatically register with registry
        )

        # Get current device IDs
        current_device_ids = {cam.device_id for cam in cameras}

        # Detect new connections (cameras that weren't there before)
        new_device_ids = current_device_ids - self.known_device_ids
        for device_id in new_device_ids:
            camera = next((c for c in cameras if c.device_id == device_id), None)
            if camera:
                logger.info(f"🔌 New camera connected: Device {device_id} - {camera.name}")

                # Fire connection event
                if self.callback:
                    event = CameraEvent(
                        event_type=CameraEventType.CONNECTED,
                        device_id=device_id,
                        camera_info=camera
                    )
                    try:
                        self.callback(event)
                    except Exception as e:
                        logger.error(f"Error in camera event callback: {e}", exc_info=True)

        # Detect disconnections (cameras that disappeared)
        # Only check devices that aren't actively in use
        inactive_known = self.known_device_ids - self.active_device_ids
        disconnected_ids = inactive_known - current_device_ids

        for device_id in disconnected_ids:
            logger.info(f"🔌 Camera disconnected: Device {device_id}")

            # Mark as disconnected in registry
            self.registry.mark_disconnected(device_id)

            # Fire disconnection event
            if self.callback:
                event = CameraEvent(
                    event_type=CameraEventType.DISCONNECTED,
                    device_id=device_id
                )
                try:
                    self.callback(event)
                except Exception as e:
                    logger.error(f"Error in camera event callback: {e}", exc_info=True)

        # Update known device IDs (excluding active ones to avoid false disconnects)
        self.known_device_ids = current_device_ids | self.active_device_ids

    def get_status(self) -> dict:
        """
        Get current monitor status

        Returns:
            Dictionary with status information
        """
        return {
            'running': self.running,
            'scan_interval': self.scan_interval,
            'known_devices': len(self.known_device_ids),
            'active_devices': len(self.active_device_ids),
            'inactive_devices': len(self.known_device_ids - self.active_device_ids)
        }


# Global camera monitor instance
_monitor_instance: Optional[CameraMonitor] = None
_monitor_lock = threading.Lock()


def get_camera_monitor(scan_interval: float = 3.0,
                       callback: Optional[Callable[[CameraEvent], None]] = None) -> CameraMonitor:
    """
    Get global camera monitor instance (singleton)

    Args:
        scan_interval: Seconds between scans (only used on first call)
        callback: Event callback (only used on first call)

    Returns:
        CameraMonitor instance
    """
    global _monitor_instance

    if _monitor_instance is None:
        with _monitor_lock:
            if _monitor_instance is None:
                _monitor_instance = CameraMonitor(scan_interval=scan_interval, callback=callback)

    return _monitor_instance
