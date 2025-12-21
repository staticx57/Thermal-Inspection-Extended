"""
Custom Exception Classes for Thermal Inspection Application

BACKWARD COMPATIBILITY SHIM
This file re-exports all exceptions from their new location in the package.
New code should import from: thermal_inspection.utils.exceptions

Usage (legacy - still works):
    from exceptions import CameraError, CameraNotFoundError, SDKError

Usage (new - preferred):
    from thermal_inspection.utils.exceptions import CameraError, CameraNotFoundError, SDKError
"""

# Re-export all exceptions from the new location
from thermal_inspection.utils.exceptions import (
    # Base
    ThermalInspectionError,
    # Camera
    CameraError,
    CameraNotFoundError,
    CameraConnectionError,
    CameraDisconnectedError,
    CameraTimeoutError,
    FrameCaptureError,
    # SDK
    SDKError,
    SDKNotAvailableError,
    SDKConnectionError,
    SDKCommandError,
    SDKTimeoutError,
    # Processing
    ProcessingError,
    FusionError,
    AnalysisError,
    PaletteError,
    # Calibration
    CalibrationError,
    CalibrationNotAvailableError,
    CalibrationInvalidError,
    # Configuration
    ConfigurationError,
    ConfigFileError,
    InvalidConfigError,
    # ROI
    ROIError,
    ROINotFoundError,
    InvalidROIError,
    # Recording
    RecordingError,
    RecordingStartError,
    RecordingWriteError,
    # GUI
    GUIError,
    WidgetError,
)

__all__ = [
    'ThermalInspectionError',
    'CameraError', 'CameraNotFoundError', 'CameraConnectionError',
    'CameraDisconnectedError', 'CameraTimeoutError', 'FrameCaptureError',
    'SDKError', 'SDKNotAvailableError', 'SDKConnectionError',
    'SDKCommandError', 'SDKTimeoutError',
    'ProcessingError', 'FusionError', 'AnalysisError', 'PaletteError',
    'CalibrationError', 'CalibrationNotAvailableError', 'CalibrationInvalidError',
    'ConfigurationError', 'ConfigFileError', 'InvalidConfigError',
    'ROIError', 'ROINotFoundError', 'InvalidROIError',
    'RecordingError', 'RecordingStartError', 'RecordingWriteError',
    'GUIError', 'WidgetError',
]
