"""
Material emissivity database for environmental compensation.

BACKWARD COMPATIBILITY SHIM
New code should import from: thermal_inspection.utils.materials
"""

from thermal_inspection.utils.materials import (
    Material,
    MATERIALS,
    DEFAULT_EMISSIVITY,
    get_materials_by_category,
    get_material,
    get_material_keys,
)

__all__ = [
    'Material', 'MATERIALS', 'DEFAULT_EMISSIVITY',
    'get_materials_by_category', 'get_material', 'get_material_keys',
]
