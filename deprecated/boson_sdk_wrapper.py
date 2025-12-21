"""
FLIR Boson SDK Wrapper
Uses the official FLIR Boson SDK from boson3dmapping project.
Provides simplified interface for inspection tool.

BACKWARD COMPATIBILITY SHIM
New code should import from: thermal_inspection.sdk.boson_sdk_wrapper
"""

from thermal_inspection.sdk.boson_sdk_wrapper import (
    # Enums
    GainMode,
    FFCMode, 
    ColorLUT,
    # Dataclasses
    BosonInfo,
    # Main class
    BosonSDK,
)

__all__ = [
    'GainMode',
    'FFCMode',
    'ColorLUT',
    'BosonInfo',
    'BosonSDK',
]
