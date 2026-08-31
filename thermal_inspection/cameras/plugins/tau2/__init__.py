"""FLIR Tau 2 camera plugin auto-registration."""
from thermal_inspection.cameras.plugin.camera_plugin_registry import get_registry
from .plugin import Tau2Plugin

get_registry().register(Tau2Plugin())
