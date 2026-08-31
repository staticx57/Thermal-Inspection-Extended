"""
Thermal Inspection Fusion Tool
Professional thermal-RGB fusion for circuit board and residential inspection.

This package provides:
- Thermal camera integration (FLIR Boson, Lepton)
- RGB camera support (FLIR Firefly, UVC cameras)
- Real-time thermal-RGB fusion (7 modes)
- ROI-based analysis
- Radiometric temperature measurement
- Video recording and snapshot capture
"""

__version__ = "3.1.0"

import os
os.environ["OPENCV_VIDEOIO_PRIORITY_OBSENSOR"] = "0"
os.environ["OPENCV_LOG_LEVEL"] = "ERROR"

# CLI exports
from .cli import main, parse_arguments

# App exports
from .app import ThermalInspectionApp, AppConfig

__all__ = [
    '__version__',
    'main',
    'parse_arguments',
    'ThermalInspectionApp',
    'AppConfig',
]
