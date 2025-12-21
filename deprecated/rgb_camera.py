"""
RGB Camera Interface - Cross-platform (Windows/Linux/macOS)
Supports USB webcams and CSI cameras (Jetson only)
Designed to match FLIR camera interface for easy integration

BACKWARD COMPATIBILITY SHIM
New code should import from: thermal_inspection.cameras.rgb_camera
"""

from thermal_inspection.cameras.rgb_camera import (
    RGBCamera,
    detect_rgb_cameras,
)

__all__ = [
    'RGBCamera',
    'detect_rgb_cameras',
]
