"""
GUI components for the Thermal Inspection application.

Submodules:
- widgets: Core display widgets (VideoWidget, OverlayWidget, etc.)
- panels: Control and analysis panels
- camera_control: Camera-specific control panels
- themes: Application themes (Dark, Light, Solarized)
- main_window: Main application window
"""

# Import main window for convenience
from .main_window import InspectionAppWindow

__all__ = [
    'InspectionAppWindow',
]
