"""
Material emissivity database for environmental compensation.

Emissivity (epsilon) represents how well a material emits thermal radiation:
- 1.0 = perfect blackbody (ideal emitter)
- 0.0 = perfect reflector (no emission)

Lower emissivity materials (like polished metals) appear cooler than actual temperature
and require compensation for accurate radiometric measurement.
"""

from typing import Dict, List
from dataclasses import dataclass


@dataclass
class Material:
    """Material properties for radiometric compensation."""
    name: str
    emissivity: float
    category: str
    description: str


# Material database organized by category
MATERIALS: Dict[str, Material] = {
    # Metals - Oxidized (higher emissivity due to oxide layer)
    'aluminum_oxidized': Material('Aluminum (Oxidized)', 0.20, 'Metal - Oxidized', 'PCB traces, heat sinks'),
    'copper_oxidized': Material('Copper (Oxidized)', 0.78, 'Metal - Oxidized', 'PCB components'),
    'steel_oxidized': Material('Steel (Oxidized)', 0.80, 'Metal - Oxidized', 'Metal casings'),
    'iron_rusted': Material('Iron (Rusted)', 0.85, 'Metal - Oxidized', 'Corroded metal'),

    # Metals - Polished (very low emissivity, highly reflective)
    'aluminum_polished': Material('Aluminum (Polished)', 0.05, 'Metal - Polished', 'Reflective surfaces'),
    'copper_polished': Material('Copper (Polished)', 0.04, 'Metal - Polished', 'New connectors'),
    'steel_polished': Material('Steel (Polished)', 0.16, 'Metal - Polished', 'Clean metal'),

    # Electronics
    'pcb': Material('PCB (FR-4)', 0.90, 'Electronics', 'Circuit boards'),
    'ic_package': Material('IC Package (Black)', 0.95, 'Electronics', 'Integrated circuits'),
    'solder_mask': Material('Solder Mask (Green)', 0.90, 'Electronics', 'PCB coating'),

    # Common Non-Metals (high emissivity)
    'paint_matte': Material('Paint (Matte)', 0.95, 'Common', 'Painted surfaces'),
    'plastic_black': Material('Plastic (Black)', 0.95, 'Common', 'Device housings'),
    'plastic_white': Material('Plastic (White)', 0.90, 'Common', 'Light housings'),
    'rubber': Material('Rubber', 0.94, 'Common', 'Cable insulation'),
    'glass': Material('Glass', 0.92, 'Common', 'Windows'),
    'wood': Material('Wood', 0.90, 'Common', 'Structures'),
    'concrete': Material('Concrete', 0.94, 'Common', 'Buildings'),

    # Special/Biological
    'human_skin': Material('Human Skin', 0.98, 'Biological', 'People'),
    'water': Material('Water', 0.96, 'Liquid', 'Water'),
}

# Default emissivity - good for most non-metallic surfaces
DEFAULT_EMISSIVITY = 0.95


def get_materials_by_category() -> Dict[str, List[Material]]:
    """
    Get materials grouped by category.

    Returns:
        Dictionary mapping category names to lists of materials
    """
    categories = {}
    for material in MATERIALS.values():
        if material.category not in categories:
            categories[material.category] = []
        categories[material.category].append(material)

    for category in categories:
        categories[category].sort(key=lambda m: m.name)

    return categories


def get_material(key: str) -> Material:
    """
    Get material by key.

    Args:
        key: Material key (e.g., 'pcb', 'aluminum_oxidized')

    Returns:
        Material object or None
    """
    return MATERIALS.get(key)


def get_material_keys() -> List[str]:
    """Get list of all material keys."""
    return list(MATERIALS.keys())
