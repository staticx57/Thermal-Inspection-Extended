"""
Camera Plugin System — Public API.

All external code imports from here:
    from thermal_inspection.cameras.plugin import (
        CameraPlugin, CameraRole, CameraPluginMatch, CameraCapabilities, CameraSDK,
        CameraPluginRegistry, get_registry,
        CameraPluginHost, ActiveCamera, get_host, set_host
    )
"""
from .camera_plugin import (
    CameraPlugin, CameraRole, CameraPluginMatch, CameraCapabilities, CameraSDK
)
from .camera_plugin_registry import CameraPluginRegistry, get_registry
from .camera_plugin_host import CameraPluginHost, ActiveCamera, get_host, set_host

__all__ = [
    'CameraPlugin', 'CameraRole', 'CameraPluginMatch', 'CameraCapabilities', 'CameraSDK',
    'CameraPluginRegistry', 'get_registry',
    'CameraPluginHost', 'ActiveCamera', 'get_host', 'set_host',
]
