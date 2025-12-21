"""
Core display widgets for the Thermal Inspection GUI.

Contains video display, overlay, and specialized input widgets.
"""

# Import extracted widgets from Phase 2
from .measurement_point import MeasurementPoint
from .info_panel import InfoPanel
from .control_panel import ControlPanel
from .overlay_widget import InspectionOverlayWidget
from .video_widget import VideoWidget

# Import migrated widgets from Phase 5
from .colorbar_widget import ColorbarWidget
from .temperature_histogram_widget import TemperatureHistogramWidget
from .multi_row_tabwidget import MultiRowTabWidget
from .spot_alert_dialog import SpotMeterAlertDialog

__all__ = [
    # Phase 2 widgets
    'MeasurementPoint',
    'InfoPanel',
    'ControlPanel',
    'InspectionOverlayWidget',
    'VideoWidget',
    # Phase 5 widgets
    'ColorbarWidget',
    'TemperatureHistogramWidget',
    'MultiRowTabWidget',
    'SpotMeterAlertDialog',
]
