"""
SDK wrappers for camera control.

Contains:
- BosonSDK: FLIR Boson SDK wrapper for full camera control
- BosonSerialInterface: Low-level CCI protocol for Boson cameras
- LeptonSDK: FLIR Lepton SDK wrapper (IDD protocol)
- FlirpySDKBridge: Bridge for sending SDK commands via flirpy
- FlirpyThermalBackend: flirpy-based thermal capture with SDK control
"""

# Boson SDK
from thermal_inspection.sdk.boson_sdk_wrapper import (
    BosonSDK,
    BosonInfo,
    GainMode as BosonGainMode,
    FFCMode as BosonFFCMode,
    ColorLUT as BosonColorLUT,
)

# Boson Serial (low-level CCI protocol)
from thermal_inspection.sdk.boson_serial import (
    BosonSerialInterface,
    BosonCameraInfo,
    AGCAlgorithm,
    ShutterMode,
    TelemetryLocation,
    GainMode as SerialGainMode,
)

# Lepton SDK
from thermal_inspection.sdk.lepton_sdk_wrapper import (
    LeptonSDK,
    LeptonModule,
    CommandType,
    LeptonRegister,
    LeptonTransport,
    MockLeptonTransport,
)

# Flirpy integrations
from thermal_inspection.sdk.flirpy_sdk_bridge import (
    FlirpySDKBridge,
)

# FlirpyThermalBackend - lazy import to avoid circular dependency with cameras package
# Import directly from thermal_inspection.sdk.flirpy_thermal_backend when needed
try:
    from thermal_inspection.sdk.flirpy_thermal_backend import (
        FlirpyThermalBackend,
        SDK_AVAILABLE,
    )
except ImportError:
    # Fallback if circular import occurs during package initialization
    FlirpyThermalBackend = None
    SDK_AVAILABLE = False


__all__ = [
    # Boson SDK
    'BosonSDK',
    'BosonInfo',
    'BosonGainMode',
    'BosonFFCMode',
    'BosonColorLUT',
    # Boson Serial
    'BosonSerialInterface',
    'BosonCameraInfo',
    'AGCAlgorithm',
    'ShutterMode',
    'TelemetryLocation',
    'SerialGainMode',
    # Lepton SDK
    'LeptonSDK',
    'LeptonModule',
    'CommandType',
    'LeptonRegister',
    'LeptonTransport',
    'MockLeptonTransport',
    # Flirpy
    'FlirpySDKBridge',
    'FlirpyThermalBackend',
    'SDK_AVAILABLE',
    # Phase 5 modules
]
