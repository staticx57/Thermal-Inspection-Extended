"""
Thermal Analysis Engine for Inspection Applications
Provides comprehensive temperature analysis, hot/cold spot detection, anomaly detection, and trend tracking.

BACKWARD COMPATIBILITY SHIM
New code should import from: thermal_inspection.processing.thermal_analyzer
"""

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

__all__ = [
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
]
