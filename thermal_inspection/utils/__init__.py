"""
Utility modules for the Thermal Inspection application.

Contains:
- logging_setup: Logging configuration
- platform_detection: Platform detection utilities
- config: Configuration management
- exceptions: Custom exception classes
- performance_monitor: Performance tracking
- settings_manager: Settings persistence
"""

from .logging_setup import setup_logging
from .platform_detection import (
    detect_platform,
    is_jetson,
    is_cuda_available,
    get_optimal_device,
)
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
from .performance_monitor import PerformanceMonitor
from .materials import (
    Material, MATERIALS, DEFAULT_EMISSIVITY,
    get_materials_by_category, get_material, get_material_keys,
)

# Migrated modules from Phase 5
from .measurement_points import MeasurementPointManager
from .preset_manager import PresetManager
from .thermal_estimator import ThermalTemperatureEstimator
from .radiometric_calibration import RadiometricCalibrator
from .placeholder_frames import create_thermal_placeholder, create_rgb_placeholder
from .spot_meter_exporter import SpotMeterExporter
from .media_recorder import VideoRecorder, VideoPlayer, SnapshotManager

__all__ = [
    # Logging
    'setup_logging',
    # Platform
    'detect_platform',
    'is_jetson',
    'is_cuda_available',
    'get_optimal_device',
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
    # Performance Monitor
    'PerformanceMonitor',
    # Materials
    'Material', 'MATERIALS', 'DEFAULT_EMISSIVITY',
    'get_materials_by_category', 'get_material', 'get_material_keys',
    # Phase 5 modules
    'MeasurementPointManager',
    'PresetManager',
    'ThermalTemperatureEstimator',
    'RadiometricCalibrator',
    'create_thermal_placeholder',
    'create_rgb_placeholder',
    'SpotMeterExporter',
    'VideoRecorder',
    'VideoPlayer',
    'SnapshotManager',
]
