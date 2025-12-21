"""
Thermal Image Processor for Inspection Applications
Hardware-accelerated thermal processing with motion and edge detection.

BACKWARD COMPATIBILITY SHIM
New code should import from: thermal_inspection.processing.thermal_processor
"""

from thermal_inspection.processing.thermal_processor import (
    ThermalProcessor,
    MotionDetection,
    EdgeCluster,
    VPI_AVAILABLE,
)

__all__ = [
    'ThermalProcessor',
    'MotionDetection',
    'EdgeCluster',
    'VPI_AVAILABLE',
]
