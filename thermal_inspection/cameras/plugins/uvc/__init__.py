"""
USB / UVC Webcam Plugin — auto-registers on import.
"""
from thermal_inspection.cameras.plugin.camera_plugin_registry import get_registry
from .plugin import UVCPlugin

get_registry().register(UVCPlugin())
