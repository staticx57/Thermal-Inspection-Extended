"""
Thermal-RGB Fusion Processor
Combines thermal and RGB imagery for enhanced object detection

BACKWARD COMPATIBILITY SHIM
New code should import from: thermal_inspection.processing.fusion_processor
"""

from thermal_inspection.processing.fusion_processor import FusionProcessor

__all__ = ['FusionProcessor']
