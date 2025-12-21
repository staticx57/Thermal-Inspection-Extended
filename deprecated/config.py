"""
Configuration Management for Thermal Inspection Application

BACKWARD COMPATIBILITY SHIM
This file re-exports Config from its new location in the package.
New code should import from: thermal_inspection.utils.config

Usage (legacy - still works):
    from config import Config, get_config

Usage (new - preferred):
    from thermal_inspection.utils.config import Config, get_config
"""

# Re-export from new location
from thermal_inspection.utils.config import Config, get_config

__all__ = ['Config', 'get_config']
