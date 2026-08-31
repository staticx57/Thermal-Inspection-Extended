"""
Camera Plugin System - Base Interfaces and Data Contracts.

Defines the abstract contracts for CameraPlugin, CameraSDK,
CameraPluginMatch, CameraCapabilities, and CameraRole.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Dict, Any, List, Union, Tuple, TYPE_CHECKING
import logging

if TYPE_CHECKING:
    from PyQt6.QtWidgets import QWidget
    from thermal_inspection.cameras.camera_backends import ThermalBackend, RGBBackend, CameraBackend

logger = logging.getLogger(__name__)


class CameraRole(Enum):
    """Operational role of a camera."""
    THERMAL = "thermal"
    RGB = "rgb"


@dataclass
class CameraCapabilities:
    """Introspection data describing what an individual camera hardware can do."""
    bit_depth: int = 8                       # 8 or 14/16
    radiometric: bool = False                # absolute calibrated temperature values
    resolutions: List[Tuple[int, int]] = field(default_factory=list)
    max_fps: float = 30.0

    # Hardware capabilities
    has_ffc: bool = False
    has_gain_mode: bool = False
    has_agc_control: bool = False
    has_palette_control: bool = False
    has_tlinear: bool = False
    has_serial_control: bool = False
    has_shutter_control: bool = False
    has_exposure_control: bool = False

    # Identity
    serial_number: str = ""
    firmware_version: str = ""
    model: str = ""
    sensor_type: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert capabilities to a serializable dictionary."""
        return {
            'bit_depth': self.bit_depth,
            'radiometric': self.radiometric,
            'resolutions': self.resolutions,
            'max_fps': self.max_fps,
            'has_ffc': self.has_ffc,
            'has_gain_mode': self.has_gain_mode,
            'has_agc_control': self.has_agc_control,
            'has_palette_control': self.has_palette_control,
            'has_tlinear': self.has_tlinear,
            'has_serial_control': self.has_serial_control,
            'has_shutter_control': self.has_shutter_control,
            'has_exposure_control': self.has_exposure_control,
            'serial_number': self.serial_number,
            'firmware_version': self.firmware_version,
            'model': self.model,
            'sensor_type': self.sensor_type,
        }


@dataclass
class CameraPluginMatch:
    """A detected camera hardware instance."""
    plugin_id: str
    device_index: int                        # OS VideoCapture device ID (-1 if non-UVC)
    com_port: Optional[str] = None           # Virtual COM port for SDK control
    baud_rate: int = 115200
    name: str = ""
    resolution: Tuple[int, int] = (0, 0)
    score: int = 0                           # Higher score indicates higher detection confidence
    extra: Dict[str, Any] = field(default_factory=dict)


class CameraSDK(ABC):
    """
    Abstract SDK controller for hardware communication (Serial/USB/IP).

    Plugins implement this to bridge generic string commands into camera-specific SDK calls.
    """

    @abstractmethod
    def connect(self) -> bool:
        """Establish connection with camera control interface."""
        pass

    @abstractmethod
    def disconnect(self):
        """Disconnect from camera control interface."""
        pass

    @abstractmethod
    def is_connected(self) -> bool:
        """Check if SDK interface is currently connected."""
        pass

    @abstractmethod
    def execute(self, command: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Execute a named camera command.

        Args:
            command: Command name (e.g. 'ffc', 'set_gain_mode', 'get_fpa_temp', 'connect')
            params: Optional dictionary of arguments for the command.

        Returns:
            Dictionary with at least {'success': bool}, plus any return data.
        """
        pass

    def get_supported_commands(self) -> List[str]:
        """Return list of standard commands supported by this SDK."""
        return []


class CameraPlugin(ABC):
    """
    Self-contained Camera Plugin contract.

    Encapsulates detection, frame backend instantiation, SDK control, and GUI widgets.
    """

    @property
    @abstractmethod
    def plugin_id(self) -> str:
        """Unique identifier string (e.g., 'flir_boson', 'flir_tau2')."""
        pass

    @property
    @abstractmethod
    def display_name(self) -> str:
        """Human-readable display name (e.g., 'FLIR Boson')."""
        pass

    @property
    @abstractmethod
    def camera_role(self) -> CameraRole:
        """Operational role of this camera (THERMAL or RGB)."""
        pass

    @abstractmethod
    def detect(self) -> List[CameraPluginMatch]:
        """
        Detect connected instances of this camera type without opening continuous streams.

        Returns:
            List of detected CameraPluginMatch instances.
        """
        pass

    @abstractmethod
    def create_backend(self, match: CameraPluginMatch) -> Union[ThermalBackend, RGBBackend, CameraBackend]:
        """Create video capture backend instance for this match."""
        pass

    def create_sdk(self, match: CameraPluginMatch) -> Optional[CameraSDK]:
        """Create camera SDK controller instance for this match."""
        return None

    @abstractmethod
    def create_control_panel(self) -> Optional[QWidget]:
        """Create GUI control panel widget for this camera model."""
        pass

    def get_capabilities(self, match: CameraPluginMatch) -> CameraCapabilities:
        """Return static or match-derived capabilities."""
        return CameraCapabilities()

    def on_sdk_connected(self, sdk: CameraSDK, panel: Optional[QWidget]) -> None:
        """Callback invoked when SDK successfully connects to refresh panel state."""
        pass

    def on_sdk_disconnected(self, panel: Optional[QWidget]) -> None:
        """Callback invoked when SDK disconnects."""
        pass
