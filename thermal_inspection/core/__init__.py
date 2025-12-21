"""
Core application logic for the Thermal Inspection application.

Contains controllers extracted from inspection_main.py:
- CameraController: Camera initialization and management
- ProcessingPipeline: Frame processing orchestration
- FusionController: Thermal-RGB fusion control
- ROIController: ROI management
- RadiometricController: Temperature measurement settings
"""

from .camera_controller import CameraController, CameraState, CameraConfig
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

__all__ = [
    'CameraController',
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
]
