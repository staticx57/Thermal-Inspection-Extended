"""
Thermal Inspection Fusion Tool
Professional thermal-RGB fusion for circuit board and residential inspection.

This package provides:
- Thermal camera integration (FLIR Boson, Tau2, Lepton) via a plugin architecture
- RGB camera support (FLIR Firefly, UVC, GigE cameras)
- Real-time thermal-RGB fusion (9 modes)
- ROI-based analysis
- Radiometric temperature measurement
- Video recording and snapshot capture
"""

__version__ = "3.6.0"

import os
os.environ["OPENCV_VIDEOIO_PRIORITY_OBSENSOR"] = "0"
os.environ["OPENCV_LOG_LEVEL"] = "ERROR"

# Warm up torch's CUDA DLLs before anything below pulls in PyQt6 (`.app`
# imports PyQt6.QtCore at module level). On Windows, importing PyQt6 first
# corrupts the DLL search order for a CUDA-enabled torch build - torch's
# own c10.dll then fails to load at all (WinError 1114) the first time
# something (e.g. ParallaxCompensator's lazy depth-estimation import)
# actually touches torch. Importing torch here, before Qt has a chance to
# load, sidesteps it entirely - confirmed by direct testing, order-
# dependent, no error when torch goes first. Best-effort: torch is an
# optional dependency (only needed for ML depth estimation), so a missing
# install is silently fine here.
try:
    import torch  # noqa: F401
except (ImportError, OSError):
    # OSError covers broken DLL installations (WinError 1114 / c10.dll failure).
    pass

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
