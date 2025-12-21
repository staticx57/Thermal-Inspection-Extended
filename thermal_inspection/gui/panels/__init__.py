"""
Analysis and control panels for the Thermal Inspection GUI.

Contains specialized panels for thermal analysis, camera control, and data visualization.
"""

# Import extracted panels from Phase 2
from .anomaly_widgets import ManualThresholdWidget, AnomalyWidget, CombinedAnomalyWidget
from .settings_panel import SettingsPanel
from .thermal_analysis import ThermalAnalysisPanel

# Import migrated panels from Phase 5
from .spot_meter_panel import SpotMeterPanel, SpotMeterData, SpotMeterAlert, SpotMeterPresets
from .radiometric_panel import RadiometricPanel
from .fusion_panel import FusionPanel
from .isotherm_panel import IsothermPanel
from .roi_temperature_panel import ROITemperaturePanel
from .calibration_panel import CalibrationPanel
from .line_profile_panel import LineProfilePanel
from .parallax_panel import ParallaxPanel
from .gradient_overlay_panel import GradientOverlayPanel
from .grid_overlay_panel import GridOverlayPanel
from .environmental_compensation_panel import EnvironmentalCompensationPanel

__all__ = [
    # Phase 2 panels
    'ThermalAnalysisPanel',
    'ManualThresholdWidget',
    'AnomalyWidget',
    'CombinedAnomalyWidget',
    'SettingsPanel',
    # Phase 5 panels
    'SpotMeterPanel',
    'SpotMeterData',
    'SpotMeterAlert',
    'SpotMeterPresets',
    'RadiometricPanel',
    'FusionPanel',
    'IsothermPanel',
    'ROITemperaturePanel',
    'CalibrationPanel',
    'LineProfilePanel',
    'ParallaxPanel',
    'GradientOverlayPanel',
    'GridOverlayPanel',
    'EnvironmentalCompensationPanel',
]
