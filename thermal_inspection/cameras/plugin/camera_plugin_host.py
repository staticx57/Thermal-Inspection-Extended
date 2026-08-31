"""
Camera Plugin Host.

Runtime manager for active camera plugins across CameraRole.THERMAL and CameraRole.RGB.
Serves as the unified hardware-abstracted interface for the application coordinator (app.py)
and GUI (main_window.py).
"""
from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from typing import Optional, Dict, Any, List, Tuple, Union, TYPE_CHECKING
import numpy as np

from PyQt6.QtCore import QObject, pyqtSignal, QTimer

from .camera_plugin import (
    CameraPlugin, CameraRole, CameraPluginMatch, CameraCapabilities, CameraSDK
)
from .camera_plugin_registry import CameraPluginRegistry, get_registry

if TYPE_CHECKING:
    from PyQt6.QtWidgets import QWidget

logger = logging.getLogger(__name__)

# Default budget for a single backend.open() call. Camera drivers left in a
# bad state (prior crash, wedged USB hub) can hang indefinitely inside
# cv2.VideoCapture.open()/isOpened() with no way for us to interrupt them, so
# activation is bounded by a watchdog thread rather than called directly.
BACKEND_OPEN_TIMEOUT_S = 10.0


def _open_with_timeout(backend: Any, timeout_seconds: float, plugin_id: str) -> bool:
    """
    Call backend.open() with a bounded wait.

    Python cannot forcibly kill a hung thread, so on timeout the watchdog
    thread is simply abandoned (daemon=True, so it won't block process exit)
    and this returns False — matching the old CameraInitializer's behavior
    that this replaces.
    """
    result: Dict[str, Any] = {}

    def _worker():
        try:
            result['ok'] = backend.open()
        except Exception as exc:
            result['ok'] = False
            result['error'] = exc

    thread = threading.Thread(target=_worker, name=f"OpenBackend-{plugin_id}", daemon=True)
    thread.start()
    thread.join(timeout=timeout_seconds)

    if thread.is_alive():
        logger.error(
            f"backend.open() for plugin '{plugin_id}' did not return within "
            f"{timeout_seconds}s — treating as failed open (driver may be hung)"
        )
        return False

    if 'error' in result:
        logger.error(f"backend.open() for plugin '{plugin_id}' raised: {result['error']}")
        return False

    return bool(result.get('ok', False))


@dataclass
class ActiveCamera:
    """An initialized and active camera managed by the host."""
    plugin: CameraPlugin
    match: CameraPluginMatch
    backend: Any
    sdk: Optional[CameraSDK]
    panel: Optional[Any]
    capabilities: CameraCapabilities


class CameraPluginHost(QObject):
    """
    Host manager executing camera lifecycle and command dispatch.

    Decouples app.py and main_window.py from specific camera hardware models.
    """

    # Signals
    camera_connected = pyqtSignal(str, dict)          # (role_str, capabilities_dict)
    camera_disconnected = pyqtSignal(str)             # (role_str)
    camera_command_result = pyqtSignal(str, str, dict)# (role_str, command_str, result_dict)
    sdk_connected = pyqtSignal(str, dict)             # (role_str, info_dict)
    sdk_disconnected = pyqtSignal(str)                # (role_str)
    panel_ready = pyqtSignal(str, object)             # (role_str, panel_widget)
    scan_result = pyqtSignal(list)                    # list of match dicts

    def __init__(self, registry: Optional[CameraPluginRegistry] = None, parent=None):
        super().__init__(parent)
        self.registry = registry or get_registry()
        self._active_cameras: Dict[str, ActiveCamera] = {}   # 'thermal' -> ActiveCamera, 'rgb' -> ActiveCamera
        self._lock = threading.RLock()
        logger.info("CameraPluginHost initialized")

    def _get_role_key(self, role: Union[CameraRole, str]) -> str:
        if isinstance(role, CameraRole):
            return role.value
        return str(role).lower()

    def get_active_camera(self, role: Union[CameraRole, str]) -> Optional[ActiveCamera]:
        """Retrieve active camera container for the given role."""
        key = self._get_role_key(role)
        with self._lock:
            return self._active_cameras.get(key)

    def is_connected(self, role: Union[CameraRole, str]) -> bool:
        """Check if a camera is active and opened for the given role."""
        cam = self.get_active_camera(role)
        if not cam or not cam.backend:
            return False
        try:
            if hasattr(cam.backend, 'is_opened') and callable(cam.backend.is_opened):
                return bool(cam.backend.is_opened())
            if hasattr(cam.backend, 'is_open'):
                return bool(cam.backend.is_open)
            if hasattr(cam.backend, 'cap') and cam.backend.cap is not None:
                return bool(cam.backend.cap.isOpened())
            return True
        except Exception:
            return False

    def activate_camera(self, role_or_match: Union[CameraPluginMatch, str, CameraRole], match: Optional[CameraPluginMatch] = None) -> bool:
        """
        Activate and open a camera plugin for a detected match.

        Args:
            role_or_match: The CameraPluginMatch, or the role string/enum if match is passed as 2nd arg.
            match: Optional CameraPluginMatch if 1st arg is role.

        Returns:
            bool: True if camera backend successfully opened.
        """
        target_match = match if isinstance(role_or_match, (str, CameraRole)) else role_or_match
        if not target_match or not isinstance(target_match, CameraPluginMatch):
            logger.error(f"Cannot activate camera: invalid match object '{target_match}'")
            return False

        plugin = self.registry.get_plugin(target_match.plugin_id)
        if not plugin:
            logger.error(f"Cannot activate camera: unknown plugin ID '{target_match.plugin_id}'")
            return False

        role_key = self._get_role_key(role_or_match if isinstance(role_or_match, (str, CameraRole)) else plugin.camera_role)

        # Deactivate any currently active camera for this role
        self.deactivate_camera(role_key)

        logger.info(f"Activating camera plugin '{plugin.plugin_id}' for role '{role_key}' (dev={target_match.device_index})...")

        try:
            # 1. Instantiate backend
            backend = plugin.create_backend(target_match)
            if not backend:
                logger.error(f"Plugin '{plugin.plugin_id}' returned None backend")
                return False

            # 2. Open backend (bounded — see _open_with_timeout)
            if not _open_with_timeout(backend, BACKEND_OPEN_TIMEOUT_S, plugin.plugin_id):
                logger.error(f"Failed to open backend for plugin '{plugin.plugin_id}'")
                try:
                    backend.release()
                except Exception:
                    pass
                return False

            # 3. Instantiate SDK & Control Panel
            sdk = plugin.create_sdk(target_match)
            panel = plugin.create_control_panel()
            capabilities = plugin.get_capabilities(target_match)

            active = ActiveCamera(
                plugin=plugin,
                match=target_match,
                backend=backend,
                sdk=sdk,
                panel=panel,
                capabilities=capabilities
            )

            with self._lock:
                self._active_cameras[role_key] = active

            # 4. Attempt automatic SDK connection if COM port provided
            if sdk:
                if target_match.com_port:
                    try:
                        ok = sdk.connect()
                        if ok:
                            plugin.on_sdk_connected(sdk, panel)
                            info_res = sdk.execute("get_camera_info")
                            self.sdk_connected.emit(role_key, info_res if info_res.get("success") else {})
                    except Exception as e:
                        logger.warning(f"Initial SDK connect on {target_match.com_port} failed: {e}")

            # 5. Emit events
            #
            # plugin_id is injected here rather than added to
            # CameraCapabilities.to_dict() itself: callers that match a
            # connected camera to its control panel (see
            # main_window._on_bus_camera_connected) need it, and to_dict()
            # has no other reason to carry plugin identity.
            capabilities_dict = capabilities.to_dict()
            capabilities_dict['plugin_id'] = plugin.plugin_id
            self.camera_connected.emit(role_key, capabilities_dict)
            if panel is not None:
                self.panel_ready.emit(role_key, panel)

            logger.info(f"[OK] Camera plugin '{plugin.plugin_id}' activated for role '{role_key}'")
            return True

        except Exception as e:
            logger.error(f"Exception activating camera plugin '{plugin.plugin_id}': {e}", exc_info=True)
            return False

    def deactivate_camera(self, role: Union[CameraRole, str]):
        """Release and deactivate active camera for a given role."""
        role_key = self._get_role_key(role)
        with self._lock:
            active = self._active_cameras.pop(role_key, None)

        if active:
            logger.info(f"Deactivating camera plugin '{active.plugin.plugin_id}' for role '{role_key}'...")
            try:
                if active.sdk:
                    active.sdk.disconnect()
                    active.plugin.on_sdk_disconnected(active.panel)
            except Exception as e:
                logger.debug(f"Error disconnecting SDK: {e}")

            try:
                if active.backend:
                    active.backend.release()
            except Exception as e:
                logger.debug(f"Error releasing backend: {e}")

            self.camera_disconnected.emit(role_key)

    def execute_command(self, role: Union[CameraRole, str], command: str,
                        params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Execute a hardware command via the active camera's SDK.

        Args:
            role: 'thermal' or 'rgb'
            command: Command name (e.g. 'ffc', 'set_gain_mode')
            params: Parameters dictionary

        Returns:
            Dict containing execution results with {'success': bool}
        """
        role_key = self._get_role_key(role)
        active = self.get_active_camera(role_key)
        params = params or {}

        if not active:
            result = {"success": False, "error": f"No active camera for role '{role_key}'"}
            self.camera_command_result.emit(role_key, command, result)
            return result

        if not active.sdk:
            result = {"success": False, "error": f"Camera '{active.plugin.plugin_id}' does not support SDK control"}
            self.camera_command_result.emit(role_key, command, result)
            return result

        try:
            result = active.sdk.execute(command, params)
            if not isinstance(result, dict):
                result = {"success": bool(result)}

            # Handle side-effects
            if command == "connect" and result.get("success"):
                active.plugin.on_sdk_connected(active.sdk, active.panel)
                self.sdk_connected.emit(role_key, result.get("info", {}))
            elif command == "disconnect" and result.get("success"):
                active.plugin.on_sdk_disconnected(active.panel)
                self.sdk_disconnected.emit(role_key)

            self.camera_command_result.emit(role_key, command, result)
            return result

        except Exception as e:
            logger.error(f"Error executing command '{command}' on role '{role_key}': {e}")
            result = {"success": False, "error": str(e)}
            self.camera_command_result.emit(role_key, command, result)
            return result

    def execute_command_async(self, role: str, command: str, params: Optional[Dict[str, Any]] = None):
        """Execute a hardware command asynchronously on the Qt event loop."""
        QTimer.singleShot(0, lambda: self.execute_command(role, command, params))

    def read_thermal(self) -> Tuple[bool, Optional[np.ndarray]]:
        """Grab a frame from the active thermal camera."""
        active = self.get_active_camera("thermal")
        if not active or not active.backend:
            return False, None
        try:
            return active.backend.read()
        except Exception as e:
            logger.error(f"Error reading thermal frame: {e}")
            return False, None

    def read_rgb(self) -> Tuple[bool, Optional[np.ndarray]]:
        """Grab a frame from the active RGB camera."""
        active = self.get_active_camera("rgb")
        if not active or not active.backend:
            return False, None
        try:
            return active.backend.read()
        except Exception as e:
            logger.error(f"Error reading RGB frame: {e}")
            return False, None

    def get_temperature_map(self) -> Optional[np.ndarray]:
        """Fetch calibrated Celsius float32 temperature map if supported."""
        active = self.get_active_camera("thermal")
        if not active or not active.backend:
            return None
        try:
            if hasattr(active.backend, 'get_temperature_map'):
                return active.backend.get_temperature_map()
        except Exception as e:
            logger.debug(f"Error getting temperature map: {e}")
        return None

    def get_capabilities(self, role: Union[CameraRole, str]) -> Optional[CameraCapabilities]:
        """Get capabilities for the active camera of the specified role."""
        active = self.get_active_camera(role)
        return active.capabilities if active else None

    def get_active_panel(self, role: Union[CameraRole, str]) -> Optional[QWidget]:
        """Get control panel widget for the active camera."""
        active = self.get_active_camera(role)
        return active.panel if active else None

    def get_all_active(self) -> Dict[str, ActiveCamera]:
        """Return shallow copy of all active cameras."""
        with self._lock:
            return dict(self._active_cameras)

    def autodiscover(self, roles: Optional[List[CameraRole]] = None) -> List[ActiveCamera]:
        """
        Discover and activate best matching cameras for requested roles.

        Returns:
            List of activated ActiveCamera objects.
        """
        matches = self.registry.discover(roles=roles)
        activated: List[ActiveCamera] = []

        # Find best match for THERMAL. The role is passed explicitly rather
        # than left for activate_camera() to re-derive from plugin.camera_role:
        # for a dual-role plugin (e.g. GigE, whose camera_role is fixed to
        # RGB but individual matches can be is_thermal via _match_is_role's
        # per-match override) that re-derivation lands the camera in the
        # wrong slot even though it was correctly filtered into
        # thermal_matches a moment earlier.
        if not roles or CameraRole.THERMAL in roles:
            thermal_matches = [m for m in matches if self._match_is_role(m, CameraRole.THERMAL)]
            if thermal_matches:
                best_thermal = thermal_matches[0]
                if self.activate_camera(CameraRole.THERMAL, best_thermal):
                    activated.append(self.get_active_camera("thermal"))

        # Find best match for RGB
        if not roles or CameraRole.RGB in roles:
            rgb_matches = [m for m in matches if self._match_is_role(m, CameraRole.RGB)]
            if rgb_matches:
                best_rgb = rgb_matches[0]
                if self.activate_camera(CameraRole.RGB, best_rgb):
                    activated.append(self.get_active_camera("rgb"))

        return activated

    def _match_is_role(self, match: CameraPluginMatch, role: CameraRole) -> bool:
        # Per-match override: a plugin whose devices can be either role (e.g.
        # GigE Vision, whose single plugin discovers both thermal and RGB
        # cameras over the network) marks which one a specific match actually
        # is via extra['is_thermal']. Without this override, a match from
        # such a plugin is always routed by the plugin's fixed camera_role —
        # a real thermal GigE camera would never be selectable for the
        # THERMAL role, since GigEPlugin.camera_role is fixed to RGB.
        is_thermal = match.extra.get('is_thermal') if match.extra else None
        if is_thermal is not None:
            return (role == CameraRole.THERMAL) == bool(is_thermal)

        plugin = self.registry.get_plugin(match.plugin_id)
        return plugin is not None and plugin.camera_role == role

    def release_all(self):
        """Deactivate and clean up all active camera backends and SDKs."""
        with self._lock:
            roles = list(self._active_cameras.keys())
        for r in roles:
            self.deactivate_camera(r)


# Global singleton instance
_host: Optional[CameraPluginHost] = None


def get_host() -> CameraPluginHost:
    """Access or create global CameraPluginHost singleton."""
    global _host
    if _host is None:
        _host = CameraPluginHost()
    return _host


def set_host(host: CameraPluginHost):
    """Override global CameraPluginHost singleton."""
    global _host
    _host = host
