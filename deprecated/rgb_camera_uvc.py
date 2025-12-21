"""
RGB Camera Interface - Generic UVC Webcam
Supports any USB Video Class (UVC) compliant webcam

BACKWARD COMPATIBILITY SHIM
New code should import from: thermal_inspection.cameras.rgb_camera_uvc
"""

from thermal_inspection.cameras.rgb_camera_uvc import (
    RGBCameraUVC,
    detect_uvc_cameras,
)

__all__ = [
    'RGBCameraUVC',
    'detect_uvc_cameras',
]
