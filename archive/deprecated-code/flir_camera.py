"""
FLIR Boson Thermal Camera Interface
Optimized for Jetson Orin with GPU acceleration
Enhanced with Boson SDK for serial control (Phase 7)

BACKWARD COMPATIBILITY SHIM
New code should import from: thermal_inspection.cameras.flir_camera
"""

from thermal_inspection.cameras.flir_camera import (
    FLIRBosonCamera,
    SDK_AVAILABLE,
    RADIOMETRIC_AVAILABLE,
)

__all__ = [
    'FLIRBosonCamera',
    'SDK_AVAILABLE',
    'RADIOMETRIC_AVAILABLE',
]
