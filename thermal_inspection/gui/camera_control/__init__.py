"""
Camera control panels for the Thermal Inspection GUI.

Contains SDK control panels for FLIR Boson, Lepton, and Firefly cameras.
"""

# Import extracted camera control panels from Phase 2
from .boson_sdk_panel import BosonSDKPanel
from .camera_manager_dialog import CameraManagerDialog
from .boson_control_panel import BosonControlPanel

# Import migrated camera control panels from Phase 5
from .lepton_control_panel import LeptonControlPanel
from .firefly_control_panel import FireflyControlPanel

__all__ = [
    # Phase 2 panels
    'BosonSDKPanel',
    'CameraManagerDialog',
    'BosonControlPanel',
    # Phase 5 panels
    'LeptonControlPanel',
    'FireflyControlPanel',
]
