"""FLIR Boson camera plugin auto-registration."""
from thermal_inspection.cameras.plugin.camera_plugin_registry import get_registry
from .plugin import BosonPlugin

get_registry().register(BosonPlugin())
