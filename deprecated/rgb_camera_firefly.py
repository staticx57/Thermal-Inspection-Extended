"""
RGB Camera Interface - FLIR Firefly Global Shutter
Supports FLIR Firefly series cameras via Spinnaker SDK

BACKWARD COMPATIBILITY SHIM
New code should import from: thermal_inspection.cameras.rgb_camera_firefly
"""

from thermal_inspection.cameras.rgb_camera_firefly import (
    RGBCameraFirefly,
    detect_firefly_cameras,
    PYSPIN_AVAILABLE,
)

__all__ = [
    'RGBCameraFirefly',
    'detect_firefly_cameras',
    'PYSPIN_AVAILABLE',
]
