#!/usr/bin/env python3
"""
SettingsManager - Central configuration management system

BACKWARD COMPATIBILITY SHIM
New code should import from: thermal_inspection.utils.settings_manager
"""

from thermal_inspection.utils.settings_manager import (
    SettingsManager,
    get_settings,
    reset_settings_instance,
)

__all__ = ['SettingsManager', 'get_settings', 'reset_settings_instance']
