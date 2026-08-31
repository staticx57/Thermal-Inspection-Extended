"""
Camera modules for the Thermal Inspection application.
"""

# Plugin Architecture
from .plugin import (
    CameraPlugin,
    CameraRole as PluginCameraRole,
    CameraPluginMatch,
    CameraCapabilities,
    CameraSDK,
    CameraPluginRegistry,
    get_registry,
    CameraPluginHost,
    ActiveCamera,
    get_host,
    set_host,
)

# Auto-register plugins
from . import plugins

# Tau 2 Camera & Backend
from .tau2_camera import Tau2Camera
from .tau2_backend import Tau2Backend

# Thermal cameras
from .flir_camera import FLIRBosonCamera
from .opencv_thermal_backend import OpenCVThermalBackend
from .pyusb_thermal_backend import PyUSBThermalBackend

# RGB cameras
from .rgb_camera import RGBCamera, detect_rgb_cameras
from .rgb_camera_uvc import RGBCameraUVC, detect_uvc_cameras

# Firefly camera (optional - requires PySpin)
try:
    from .rgb_camera_firefly import RGBCameraFirefly, detect_firefly_cameras, PYSPIN_AVAILABLE
except ImportError:
    RGBCameraFirefly = None
    detect_firefly_cameras = None
    PYSPIN_AVAILABLE = False

# Camera registry
from .camera_registry import (
    CameraRole,
    CameraDescriptor,
    CameraRegistry,
    get_camera_registry,
)

# Camera detection
from .camera_detector import (
    CameraType,
    CameraInfo,
    CameraDetector,
)

# Camera factory
from .camera_factory import (
    create_rgb_camera,
    detect_all_rgb_cameras,
    print_camera_summary,
    autodetect_camera_types,
)

# Camera backends (abstract base classes)
from .camera_backends import (
    CameraBackend,
    ThermalBackend,
    RGBBackend,
    BackendError,
    BackendNotAvailableError,
    BackendInitializationError,
)

# Monitoring, Calibration, Capture
from .camera_monitor import CameraMonitor, get_camera_monitor
from .camera_calibration import CameraCalibrator
from .threaded_camera_capture import ThreadedCameraCapture

__all__ = [
    # Plugin Architecture
    'CameraPlugin',
    'PluginCameraRole',
    'CameraPluginMatch',
    'CameraCapabilities',
    'CameraSDK',
    'CameraPluginRegistry',
    'get_registry',
    'CameraPluginHost',
    'ActiveCamera',
    'get_host',
    'set_host',
    'plugins',
    # Tau 2
    'Tau2Camera',
    'Tau2Backend',
    # Thermal camera
    'FLIRBosonCamera',
    # RGB cameras
    'RGBCamera',
    'detect_rgb_cameras',
    'RGBCameraUVC',
    'detect_uvc_cameras',
    'RGBCameraFirefly',
    'detect_firefly_cameras',
    'PYSPIN_AVAILABLE',
    # Camera registry
    'CameraRole',
    'CameraDescriptor',
    'CameraRegistry',
    'get_camera_registry',
    # Camera detection
    'CameraType',
    'CameraInfo',
    'CameraDetector',
    # Camera factory
    'create_rgb_camera',
    'detect_all_rgb_cameras',
    'print_camera_summary',
    'autodetect_camera_types',
    # Camera backends
    'CameraBackend',
    'ThermalBackend',
    'RGBBackend',
    'BackendError',
    'BackendNotAvailableError',
    'BackendInitializationError',
    # Helpers
    'CameraMonitor',
    'get_camera_monitor',
    'CameraCalibrator',
    'ThreadedCameraCapture',
    'OpenCVThermalBackend',
    'PyUSBThermalBackend',
]
