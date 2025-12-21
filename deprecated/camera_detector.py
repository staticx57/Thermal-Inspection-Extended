"""
Camera Detection Utility
Automatically detect and identify thermal and RGB cameras

BACKWARD COMPATIBILITY SHIM
New code should import from: thermal_inspection.cameras.camera_detector
"""

from thermal_inspection.cameras.camera_detector import (
    CameraType,
    CameraInfo,
    CameraDetector,
    PYSPIN_AVAILABLE,
    FLIR_USB_VENDOR_ID,
)

__all__ = [
    'CameraType',
    'CameraInfo',
    'CameraDetector',
    'PYSPIN_AVAILABLE',
    'FLIR_USB_VENDOR_ID',
]
