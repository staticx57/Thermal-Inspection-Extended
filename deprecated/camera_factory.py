"""
RGB Camera Factory - Auto-detection and instantiation

BACKWARD COMPATIBILITY SHIM
New code should import from: thermal_inspection.cameras.camera_factory
"""

from thermal_inspection.cameras.camera_factory import (
    create_rgb_camera,
    detect_all_rgb_cameras,
    print_camera_summary,
    autodetect_camera_types,
)

# Re-export PYSPIN_AVAILABLE from the Firefly module
try:
    from thermal_inspection.cameras.rgb_camera_firefly import PYSPIN_AVAILABLE
except ImportError:
    PYSPIN_AVAILABLE = False

__all__ = [
    'create_rgb_camera',
    'detect_all_rgb_cameras',
    'print_camera_summary',
    'autodetect_camera_types',
    'PYSPIN_AVAILABLE',
]
