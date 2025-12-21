"""
Region of Interest (ROI) Manager for Thermal Inspection
Handles automatic ROI detection, manual ROI creation, and ROI persistence.

BACKWARD COMPATIBILITY SHIM
New code should import from: thermal_inspection.processing.roi_manager
"""

from thermal_inspection.processing.roi_manager import (
    # Enums
    ROIType,
    ROISource,
    # Dataclasses
    ROI,
    # Main class
    ROIManager,
)

__all__ = [
    'ROIType',
    'ROISource',
    'ROI',
    'ROIManager',
]
