"""
Thermal processing and analysis modules.

Contains:
- ThermalProcessor: Motion and edge detection with VPI acceleration
- ThermalAnalyzer: Statistics, hot/cold spot detection, anomaly detection
- FusionProcessor: Thermal-RGB fusion algorithms
- PaletteManager: Color palette management
- ROIManager: ROI creation and management
"""

# Processing modules
from thermal_inspection.processing.thermal_processor import (
    ThermalProcessor,
    MotionDetection,
    EdgeCluster,
    VPI_AVAILABLE,
)

from thermal_inspection.processing.fusion_processor import FusionProcessor

from thermal_inspection.processing.palette_manager import (
    PaletteManager,
    PaletteType,
    PaletteConfig,
)

# Analysis modules
from thermal_inspection.processing.thermal_analyzer import (
    # Enums
    TemperatureUnit,
    AnomalyType,
    ThresholdMode,
    ThresholdVisualization,
    # Dataclasses
    ThermalStatistics,
    HotSpot,
    ColdSpot,
    ThermalAnomaly,
    TemperatureTrend,
    ThresholdDetectionResult,
    # Main class
    ThermalAnalyzer,
)

# ROI modules
from thermal_inspection.processing.roi_manager import (
    ROIType,
    ROISource,
    ROI,
    ROIManager,
)

# Migrated modules from Phase 5
from thermal_inspection.processing.radiometric_converter import TLinearConverter
from thermal_inspection.processing.isotherm_bands import IsothermBandManager
from thermal_inspection.processing.line_profile_tool import LineProfileAnalyzer, LineProfileData
from thermal_inspection.processing.parallax_compensator import ParallaxCompensator, CameraGeometry


__all__ = [
    # Thermal Processor
    'ThermalProcessor',
    'MotionDetection',
    'EdgeCluster',
    'VPI_AVAILABLE',
    # Fusion
    'FusionProcessor',
    # Palettes
    'PaletteManager',
    'PaletteType',
    'PaletteConfig',
    # Thermal Analyzer
    'TemperatureUnit',
    'AnomalyType',
    'ThresholdMode',
    'ThresholdVisualization',
    'ThermalStatistics',
    'HotSpot',
    'ColdSpot',
    'ThermalAnomaly',
    'TemperatureTrend',
    'ThresholdDetectionResult',
    'ThermalAnalyzer',
    # ROI
    'ROIType',
    'ROISource',
    'ROI',
    'ROIManager',
    # Phase 5 modules
    'TLinearConverter',
    'IsothermBandManager',
    'LineProfileAnalyzer',
    'LineProfileData',
    'ParallaxCompensator',
    'CameraGeometry',
]
