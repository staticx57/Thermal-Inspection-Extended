"""
flirpy-based Thermal Backend with Dual-Path SDK Control

BACKWARD COMPATIBILITY SHIM
New code should import from: thermal_inspection.sdk.flirpy_thermal_backend
"""

from thermal_inspection.sdk.flirpy_thermal_backend import (
    FlirpyThermalBackend,
    SDK_AVAILABLE,
)

__all__ = [
    'FlirpyThermalBackend',
    'SDK_AVAILABLE',
]
