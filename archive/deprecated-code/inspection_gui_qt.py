#!/usr/bin/env python3
"""
Qt-based GUI for Thermal Inspection Fusion Tool
Professional interface for circuit board and residential house inspection
Optimized for Jetson Orin and x86-64 platforms

BACKWARD COMPATIBILITY SHIM
===========================
This file now re-exports all GUI components from the modular thermal_inspection.gui package.
All classes have been extracted to:
- thermal_inspection/gui/themes/         - Theme definitions
- thermal_inspection/gui/widgets/        - Core display widgets
- thermal_inspection/gui/panels/         - Control and analysis panels
- thermal_inspection/gui/camera_control/ - Camera-specific panels
- thermal_inspection/gui/main_window.py  - Main application window

For new code, import directly from:
    from thermal_inspection.gui import InspectionAppWindow
    from thermal_inspection.gui.widgets import VideoWidget, MeasurementPoint
    from thermal_inspection.gui.panels import ThermalAnalysisPanel
    from thermal_inspection.gui.themes import DARK_THEME, THEMES
"""

import sys
import logging

# Check PyQt availability
try:
    from PyQt6.QtWidgets import QApplication
    PYQT_AVAILABLE = True
except ImportError:
    PYQT_AVAILABLE = False
    print("WARNING: PyQt6 not available. Install with: pip3 install PyQt6")

logger = logging.getLogger(__name__)

# =============================================================================
# BACKWARD COMPATIBILITY RE-EXPORTS
# =============================================================================

# Themes
from thermal_inspection.gui.themes import (
    DARK_THEME,
    LIGHT_THEME,
    SOLARIZED_THEME,
    COLORFUL_THEME,
    THEMES,
)

# Widgets
from thermal_inspection.gui.widgets import (
    MeasurementPoint,
    VideoWidget,
    ControlPanel,
    InfoPanel,
    InspectionOverlayWidget,
)

# Panels
from thermal_inspection.gui.panels import (
    ThermalAnalysisPanel,
    ManualThresholdWidget,
    AnomalyWidget,
    CombinedAnomalyWidget,
    SettingsPanel,
)

# Camera Control
from thermal_inspection.gui.camera_control import (
    BosonControlPanel,
    BosonSDKPanel,
    CameraManagerDialog,
)

# Main Window
from thermal_inspection.gui.main_window import InspectionAppWindow

# =============================================================================
# MODULE-LEVEL EXPORTS
# =============================================================================

__all__ = [
    # Themes
    'DARK_THEME',
    'LIGHT_THEME',
    'SOLARIZED_THEME',
    'COLORFUL_THEME',
    'THEMES',
    # Widgets
    'MeasurementPoint',
    'VideoWidget',
    'ControlPanel',
    'InfoPanel',
    'InspectionOverlayWidget',
    # Panels
    'ThermalAnalysisPanel',
    'ManualThresholdWidget',
    'AnomalyWidget',
    'CombinedAnomalyWidget',
    'SettingsPanel',
    # Camera Control
    'BosonControlPanel',
    'BosonSDKPanel',
    'CameraManagerDialog',
    # Main Window
    'InspectionAppWindow',
    # Flags
    'PYQT_AVAILABLE',
]


# =============================================================================
# Standalone Test
# =============================================================================

def main():
    """Standalone test of inspection GUI."""
    if not PYQT_AVAILABLE:
        print("ERROR: PyQt6 is required. Install with: pip3 install PyQt6")
        sys.exit(1)

    import numpy as np

    app = QApplication(sys.argv)
    window = InspectionAppWindow()
    window.show()

    # Test with dummy data
    dummy_frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
    window.update_frame(dummy_frame)
    window.update_metrics(fps=30.0, roi_count=3, thermal_connected=True, rgb_connected=True)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
