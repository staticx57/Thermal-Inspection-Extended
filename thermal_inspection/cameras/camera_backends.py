"""
Abstract base classes for camera backends.

This module defines the interfaces for all camera backends, enabling
modular, runtime-switchable camera support.
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Tuple
import numpy as np
import logging

logger = logging.getLogger(__name__)


class CameraBackend(ABC):
    """
    Abstract base class for all camera backends.

    All camera backends (OpenCV, PyUSB, PySpin, etc.) must implement
    this interface to ensure consistent API across the application.
    """

    @abstractmethod
    def is_available(self) -> bool:
        """
        Check if this backend can be initialized on the current system.

        Returns:
            bool: True if backend is available, False otherwise
        """
        pass

    @abstractmethod
    def open(self) -> bool:
        """
        Open/initialize the camera.

        Returns:
            bool: True if camera opened successfully, False otherwise
        """
        pass

    @abstractmethod
    def read(self) -> Tuple[bool, Optional[np.ndarray]]:
        """
        Read a frame from the camera.

        Returns:
            tuple: (success: bool, frame: np.ndarray or None)
        """
        pass

    @abstractmethod
    def release(self):
        """Release camera resources and cleanup."""
        pass

    @abstractmethod
    def is_opened(self) -> bool:
        """
        Check if camera is currently opened.

        Returns:
            bool: True if camera is opened, False otherwise
        """
        pass

    @abstractmethod
    def get_info(self) -> Dict:
        """
        Get information about this camera backend.

        Returns:
            dict: Backend information including:
                - backend: str (backend name)
                - type: str ('thermal' or 'rgb')
                - bit_depth: int (8 or 16)
                - radiometric: bool
                - resolution: tuple (width, height)
                - features: list[str]
        """
        pass

    @abstractmethod
    def get_resolution(self) -> Optional[Tuple[int, int]]:
        """
        Get current resolution.

        Returns:
            tuple: (width, height) or None if not available
        """
        pass


class ThermalBackend(CameraBackend):
    """
    Abstract base class for thermal camera backends.

    Extends CameraBackend with thermal-specific functionality.
    """

    @abstractmethod
    def is_radiometric(self) -> bool:
        """
        Check if this backend provides true radiometric data.

        Returns:
            bool: True if backend provides absolute temperature values,
                  False if it provides AGC-processed visual data
        """
        pass

    @abstractmethod
    def get_temperature_map(self) -> Optional[np.ndarray]:
        """
        Get temperature map in Celsius (if radiometric).

        Returns:
            np.ndarray: Temperature map in Celsius, or None if not radiometric
        """
        pass

    @abstractmethod
    def supports_sdk_control(self) -> bool:
        """
        Check if this backend supports SDK control (FFC, AGC, etc.).

        Returns:
            bool: True if SDK control is available
        """
        pass

    def get_fpa_temperature(self) -> Optional[float]:
        """
        Get Focal Plane Array temperature in Celsius (if available).

        Returns:
            float: FPA temperature in Celsius, or None if not available
        """
        return None


class RGBBackend(CameraBackend):
    """
    Abstract base class for RGB camera backends.

    Extends CameraBackend with RGB-specific functionality.
    """

    @abstractmethod
    def supports_color(self) -> bool:
        """
        Check if this backend provides color images.

        Returns:
            bool: True if color, False if grayscale
        """
        pass

    @abstractmethod
    def get_exposure(self) -> Optional[float]:
        """
        Get current exposure time in milliseconds.

        Returns:
            float: Exposure time in ms, or None if not available
        """
        pass

    @abstractmethod
    def set_exposure(self, exposure_ms: float) -> bool:
        """
        Set exposure time in milliseconds.

        Args:
            exposure_ms: Exposure time in milliseconds

        Returns:
            bool: True if successful, False otherwise
        """
        pass


class BackendError(Exception):
    """Exception raised for backend-specific errors."""
    pass


class BackendNotAvailableError(BackendError):
    """Exception raised when a backend is not available on the system."""
    pass


class BackendInitializationError(BackendError):
    """Exception raised when a backend fails to initialize."""
    pass
