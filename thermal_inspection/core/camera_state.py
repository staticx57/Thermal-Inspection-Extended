"""
Data models for camera state and configuration.
"""
from typing import Optional
from dataclasses import dataclass

@dataclass
class CameraState:
    """Current state of cameras."""
    thermal_connected: bool = False
    rgb_available: bool = False
    is_flir_boson: bool = False
    is_lepton: bool = False
    is_firefly: bool = False
    thermal_device_id: Optional[int] = None
    rgb_device_id: Optional[int] = None
    rgb_camera_source: str = 'uvc'
    is_radiometric: bool = False
    sdk_connected: bool = False
    reconfiguring: bool = False

@dataclass
class CameraConfig:
    """Configuration for camera initialization."""
    thermal_device: Optional[int] = None
    rgb_device: Optional[int] = None
    disable_rgb: bool = False
    width: int = 640
    height: int = 512
    thermal_backend: str = 'opencv'
    enable_boson_sdk: bool = True
    boson_com_port: str = 'COM7'
