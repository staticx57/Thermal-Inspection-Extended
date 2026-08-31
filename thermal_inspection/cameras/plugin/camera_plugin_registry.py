"""
Camera Plugin Registry.

Provides thread-safe registration and discovery across all known camera plugins.
"""
from __future__ import annotations

import logging
import threading
from typing import Dict, List, Optional
from .camera_plugin import CameraPlugin, CameraPluginMatch, CameraRole

logger = logging.getLogger(__name__)


class CameraPluginRegistry:
    """Registry maintaining all available camera plugins."""

    def __init__(self):
        self._plugins: Dict[str, CameraPlugin] = {}
        self._lock = threading.Lock()

    def register(self, plugin: CameraPlugin) -> None:
        """Register a camera plugin."""
        with self._lock:
            if plugin.plugin_id in self._plugins:
                logger.debug(f"Overwriting existing camera plugin: {plugin.plugin_id}")
            else:
                logger.info(f"Registered camera plugin: {plugin.plugin_id} ({plugin.display_name})")
            self._plugins[plugin.plugin_id] = plugin

    def unregister(self, plugin_id: str) -> None:
        """Unregister a camera plugin by its ID."""
        with self._lock:
            if plugin_id in self._plugins:
                del self._plugins[plugin_id]
                logger.info(f"Unregistered camera plugin: {plugin_id}")

    def get_plugin(self, plugin_id: str) -> Optional[CameraPlugin]:
        """Retrieve a registered plugin by ID."""
        with self._lock:
            return self._plugins.get(plugin_id)

    def get_all_plugins(self) -> List[CameraPlugin]:
        """Retrieve a list of all registered plugins."""
        with self._lock:
            return list(self._plugins.values())

    def get_plugins_for_role(self, role: CameraRole) -> List[CameraPlugin]:
        """Retrieve all plugins matching the specified CameraRole."""
        with self._lock:
            return [p for p in self._plugins.values() if p.camera_role == role]

    def list_registered(self) -> List[str]:
        """Return list of all registered plugin IDs."""
        with self._lock:
            return list(self._plugins.keys())

    def discover(self, roles: Optional[List[CameraRole]] = None,
                 skip_device_ids: Optional[List[int]] = None) -> List[CameraPluginMatch]:
        """
        Run hardware discovery across all registered plugins.

        Args:
            roles: Optional filter for specific CameraRole(s).
            skip_device_ids: Device IDs to ignore during probing.

        Returns:
            List of detected CameraPluginMatch objects sorted by score descending.
        """
        all_matches: List[CameraPluginMatch] = []
        with self._lock:
            plugins = list(self._plugins.values())

        for plugin in plugins:
            if roles and plugin.camera_role not in roles:
                continue
            try:
                matches = plugin.detect()
                if skip_device_ids:
                    matches = [m for m in matches if m.device_index not in skip_device_ids]
                all_matches.extend(matches)
            except Exception as e:
                logger.warning(f"Plugin '{plugin.plugin_id}' detection raised an exception: {e}")

        # Sort matches by detection confidence score descending
        return sorted(all_matches, key=lambda m: m.score, reverse=True)


# Global singleton instance
_registry = CameraPluginRegistry()


def get_registry() -> CameraPluginRegistry:
    """Access global CameraPluginRegistry singleton."""
    return _registry
