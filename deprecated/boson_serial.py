"""
FLIR Boson Serial Communication Module
Implements CCI (Camera Command Interface) protocol for Boson 320/640 cameras.

BACKWARD COMPATIBILITY SHIM
New code should import from: thermal_inspection.sdk.boson_serial
"""

from thermal_inspection.sdk.boson_serial import (
    # Enums
    AGCAlgorithm,
    ShutterMode,
    TelemetryLocation,
    GainMode,
    # Dataclasses
    BosonCameraInfo,
    # Main class
    BosonSerialInterface,
)

__all__ = [
    'AGCAlgorithm',
    'ShutterMode',
    'TelemetryLocation',
    'GainMode',
    'BosonCameraInfo',
    'BosonSerialInterface',
]
