"""
Abstract base classes for camera backends.

BACKWARD COMPATIBILITY SHIM
New code should import from: thermal_inspection.cameras.camera_backends
"""

from thermal_inspection.cameras.camera_backends import (
    CameraBackend,
    ThermalBackend,
    RGBBackend,
    BackendError,
    BackendNotAvailableError,
    BackendInitializationError,
)

__all__ = [
    'CameraBackend',
    'ThermalBackend',
    'RGBBackend',
    'BackendError',
    'BackendNotAvailableError',
    'BackendInitializationError',
]
