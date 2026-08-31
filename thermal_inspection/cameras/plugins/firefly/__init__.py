"""FLIR Firefly RGB camera plugin auto-registration."""
from thermal_inspection.cameras.plugin.camera_plugin_registry import get_registry
from .plugin import FireflyPlugin

get_registry().register(FireflyPlugin())
