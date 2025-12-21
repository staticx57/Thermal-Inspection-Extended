"""
Flirpy SDK Bridge - Inject Boson SDK commands via flirpy's serial connection

BACKWARD COMPATIBILITY SHIM
New code should import from: thermal_inspection.sdk.flirpy_sdk_bridge
"""

from thermal_inspection.sdk.flirpy_sdk_bridge import (
    # Enums
    GainMode,
    FFCMode,
    ColorLUT,
    # Main class
    FlirpySDKBridge,
)

__all__ = [
    'GainMode',
    'FFCMode',
    'ColorLUT',
    'FlirpySDKBridge',
]
