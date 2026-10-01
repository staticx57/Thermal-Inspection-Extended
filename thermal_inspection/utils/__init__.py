"""
Utility modules for the Thermal Inspection application.

Contains configuration, custom exceptions, settings persistence, materials, thermal estimation and calibration,
media recording and exporters. (Logging is configured by thermal_inspection.cli.configure_logging.)
"""

from .exceptions import (
    ThermalInspectionError,
    CameraError, CameraNotFoundError, CameraConnectionError,
    CameraDisconnectedError, CameraTimeoutError, FrameCaptureError,
    SDKError, SDKNotAvailableError, SDKConnectionError,
    SDKCommandError, SDKTimeoutError,
    ProcessingError, FusionError, AnalysisError, PaletteError,
    CalibrationError, CalibrationNotAvailableError, CalibrationInvalidError,
    ConfigurationError, ConfigFileError, InvalidConfigError,
    ROIError, ROINotFoundError, InvalidROIError,
    RecordingError, RecordingStartError, RecordingWriteError,
    GUIError, WidgetError,
)
from .config import Config, get_config
from .view_mode import ViewMode
from .settings_manager import SettingsManager, get_settings, reset_settings_instance
from .materials import (
    Material, MATERIALS, DEFAULT_EMISSIVITY,
    get_materials_by_category, get_material, get_material_keys,
)

# Migrated modules from Phase 5
from .preset_manager import PresetManager
from .thermal_estimator import ThermalTemperatureEstimator
from .radiometric_calibration import RadiometricCalibrator
from .spot_meter_exporter import SpotMeterExporter
from .media_recorder import VideoRecorder, VideoPlayer, SnapshotManager

__all__ = [
    # Exceptions
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
    # Config
    'Config', 'get_config',
    # View Mode
    'ViewMode',
    # Settings Manager
    'SettingsManager', 'get_settings', 'reset_settings_instance',
    # Materials
    'Material', 'MATERIALS', 'DEFAULT_EMISSIVITY',
    'get_materials_by_category', 'get_material', 'get_material_keys',
    # Phase 5 modules
    'PresetManager',
    'ThermalTemperatureEstimator',
    'RadiometricCalibrator',
    'SpotMeterExporter',
    'VideoRecorder',
    'VideoPlayer',
    'SnapshotManager',
]
