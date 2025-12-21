"""
Palette Manager for Multi-Palette Thermal Inspection
Manages global and per-ROI color palettes for thermal visualization.

BACKWARD COMPATIBILITY SHIM
New code should import from: thermal_inspection.processing.palette_manager
"""

from thermal_inspection.processing.palette_manager import (
    PaletteType,
    PaletteConfig,
    PaletteManager,
)

__all__ = [
    'PaletteType',
    'PaletteConfig',
    'PaletteManager',
]
