"""
FLIR file playback plugin - auto-registers on import.
"""
from thermal_inspection.cameras.plugin.camera_plugin_registry import get_registry
from .plugin import FlirFilePlugin

get_registry().register(FlirFilePlugin())
