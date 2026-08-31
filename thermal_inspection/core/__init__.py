"""
Core application logic for the Thermal Inspection application.

Contains controllers extracted from inspection_main.py:
- CameraController: Camera initialization and management
- FusionController: Thermal-RGB fusion control
- ROIController: ROI management
- RadiometricController: Temperature measurement settings
- MediaManager: Video recording and snapshot capture
- CalibrationManager: Radiometric calibration lifecycle
- SDKProxy: Hardware SDK delegation (Boson, Lepton, Firefly)
- ThresholdManager: Manual threshold overlay state (8-bit)
- IsothermManager: Temperature-aware isotherm overlay state (16-bit)
- AppEventBus: Central typed signal broker for GUI ↔ backend
"""

from .camera_state import CameraState, CameraConfig
from .fusion_controller import (
    FusionController,
    FusionState,
    ViewMode,
    EdgeSettings,
    DetailSettings,
)
from .roi_controller import ROIController, ROIControllerState
from .radiometric_controller import (
    RadiometricController,
    RadiometricState,
    TemperatureUnit,
    RadiometricMethod,
    EnvironmentalParams,
    CalibrationPoint,
)
from .media_manager import MediaManager
from .calibration_manager import CalibrationManager
from .threshold_manager import ThresholdManager, ThresholdState
from .isotherm_manager import IsothermManager, IsothermState
from .event_bus import AppEventBus

__all__ = [
    'CameraState',
    'CameraConfig',
    'FusionController',
    'FusionState',
    'ViewMode',
    'EdgeSettings',
    'DetailSettings',
    'ROIController',
    'ROIControllerState',
    'RadiometricController',
    'RadiometricState',
    'TemperatureUnit',
    'RadiometricMethod',
    'EnvironmentalParams',
    'CalibrationPoint',
    'MediaManager',
    'CalibrationManager',
    'ThresholdManager',
    'ThresholdState',
    'IsothermManager',
    'IsothermState',
    'AppEventBus',
]
