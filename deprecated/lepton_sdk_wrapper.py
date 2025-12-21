"""
FLIR Lepton SDK Wrapper
Implements the FLIR Lepton Software Interface Description Document (IDD) protocol.
Provides a high-level interface for controlling Lepton cameras via CCI/TWI (I2C).

BACKWARD COMPATIBILITY SHIM
New code should import from: thermal_inspection.sdk.lepton_sdk_wrapper
"""

from thermal_inspection.sdk.lepton_sdk_wrapper import (
    # Enums
    LeptonModule,
    CommandType,
    LeptonRegister,
    # Classes
    LeptonTransport,
    MockLeptonTransport,
    LeptonSDK,
)

__all__ = [
    'LeptonModule',
    'CommandType',
    'LeptonRegister',
    'LeptonTransport',
    'MockLeptonTransport',
    'LeptonSDK',
]
