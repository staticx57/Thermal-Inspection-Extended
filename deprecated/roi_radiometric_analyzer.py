"""
ROI Radiometric Analyzer
Manages radiometric temperature analysis for individual ROIs.
Enables per-ROI temperature measurements independent of global measurements.

BACKWARD COMPATIBILITY SHIM
New code should import from: thermal_inspection.processing.roi_radiometric_analyzer
"""

from thermal_inspection.processing.roi_radiometric_analyzer import (
    ROIRadiometricAnalyzer,
)

__all__ = [
    'ROIRadiometricAnalyzer',
]
