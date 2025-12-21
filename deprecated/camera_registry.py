"""
Camera Registry System
Tracks detected cameras and their assigned roles (RGB, Thermal, Unknown)

BACKWARD COMPATIBILITY SHIM
New code should import from: thermal_inspection.cameras.camera_registry
"""

from thermal_inspection.cameras.camera_registry import (
    CameraRole,
    CameraDescriptor,
    CameraRegistry,
    get_camera_registry,
)

__all__ = [
    'CameraRole',
    'CameraDescriptor',
    'CameraRegistry',
    'get_camera_registry',
]
