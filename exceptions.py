"""
Custom Exception Classes for Thermal Inspection Application

This module defines a hierarchy of exceptions for better error handling
and debugging throughout the application.

Usage:
    from exceptions import CameraError, CameraNotFoundError, SDKError

    try:
        camera.connect()
    except CameraNotFoundError:
        logger.error("Camera not connected")
    except CameraTimeoutError:
        logger.warning("Camera timeout, retrying...")
        retry_connection()
    except CameraError as e:
        logger.error(f"Camera error: {e}")
        raise
"""

from typing import Optional, Any


# =============================================================================
# Base Exception
# =============================================================================

class ThermalInspectionError(Exception):
    """
    Base exception for all Thermal Inspection application errors.

    All custom exceptions should inherit from this class to allow
    catching all application-specific errors with a single handler.
    """

    def __init__(self, message: str, details: Optional[Any] = None):
        super().__init__(message)
        self.message = message
        self.details = details

    def __str__(self):
        if self.details:
            return f"{self.message} (details: {self.details})"
        return self.message


# =============================================================================
# Camera Exceptions
# =============================================================================

class CameraError(ThermalInspectionError):
    """Base exception for camera-related errors."""
    pass


class CameraNotFoundError(CameraError):
    """Raised when a camera cannot be found or detected."""

    def __init__(self, camera_type: str = "camera", device_id: Optional[int] = None):
        message = f"{camera_type.title()} not found"
        if device_id is not None:
            message += f" at device ID {device_id}"
        super().__init__(message, details={"camera_type": camera_type, "device_id": device_id})
        self.camera_type = camera_type
        self.device_id = device_id


class CameraConnectionError(CameraError):
    """Raised when a camera fails to connect or initialize."""

    def __init__(self, message: str = "Camera connection failed", camera_type: str = "camera"):
        super().__init__(message, details={"camera_type": camera_type})
        self.camera_type = camera_type


class CameraDisconnectedError(CameraError):
    """Raised when a camera unexpectedly disconnects during operation."""

    def __init__(self, camera_type: str = "camera"):
        super().__init__(f"{camera_type.title()} disconnected unexpectedly")
        self.camera_type = camera_type


class CameraTimeoutError(CameraError):
    """Raised when a camera operation times out."""

    def __init__(self, operation: str = "operation", timeout_seconds: float = 0):
        message = f"Camera {operation} timed out"
        if timeout_seconds > 0:
            message += f" after {timeout_seconds:.1f}s"
        super().__init__(message, details={"operation": operation, "timeout": timeout_seconds})
        self.operation = operation
        self.timeout_seconds = timeout_seconds


class FrameCaptureError(CameraError):
    """Raised when frame capture fails."""

    def __init__(self, message: str = "Failed to capture frame", camera_type: str = "camera"):
        super().__init__(message, details={"camera_type": camera_type})
        self.camera_type = camera_type


# =============================================================================
# SDK Exceptions
# =============================================================================

class SDKError(ThermalInspectionError):
    """Base exception for SDK-related errors (Boson SDK, Spinnaker, etc.)."""
    pass


class SDKNotAvailableError(SDKError):
    """Raised when an SDK is not installed or available."""

    def __init__(self, sdk_name: str = "SDK"):
        super().__init__(f"{sdk_name} is not available or not installed")
        self.sdk_name = sdk_name


class SDKConnectionError(SDKError):
    """Raised when SDK fails to connect to device."""

    def __init__(self, sdk_name: str = "SDK", port: Optional[str] = None):
        message = f"{sdk_name} connection failed"
        if port:
            message += f" on {port}"
        super().__init__(message, details={"sdk_name": sdk_name, "port": port})
        self.sdk_name = sdk_name
        self.port = port


class SDKCommandError(SDKError):
    """Raised when an SDK command fails."""

    def __init__(self, command: str, error_code: Optional[int] = None, sdk_name: str = "SDK"):
        message = f"{sdk_name} command '{command}' failed"
        if error_code is not None:
            message += f" (error code: {error_code})"
        super().__init__(message, details={"command": command, "error_code": error_code})
        self.command = command
        self.error_code = error_code


class SDKTimeoutError(SDKError):
    """Raised when an SDK operation times out."""

    def __init__(self, operation: str = "operation", sdk_name: str = "SDK"):
        super().__init__(f"{sdk_name} {operation} timed out")
        self.operation = operation


# =============================================================================
# Processing Exceptions
# =============================================================================

class ProcessingError(ThermalInspectionError):
    """Base exception for frame/image processing errors."""
    pass


class FusionError(ProcessingError):
    """Raised when thermal-RGB fusion fails."""

    def __init__(self, message: str = "Fusion processing failed", fusion_mode: Optional[str] = None):
        super().__init__(message, details={"fusion_mode": fusion_mode})
        self.fusion_mode = fusion_mode


class AnalysisError(ProcessingError):
    """Raised when thermal analysis fails."""

    def __init__(self, message: str = "Thermal analysis failed", analysis_type: Optional[str] = None):
        super().__init__(message, details={"analysis_type": analysis_type})
        self.analysis_type = analysis_type


class PaletteError(ProcessingError):
    """Raised when palette application fails."""

    def __init__(self, message: str = "Palette application failed", palette_name: Optional[str] = None):
        super().__init__(message, details={"palette_name": palette_name})
        self.palette_name = palette_name


# =============================================================================
# Calibration Exceptions
# =============================================================================

class CalibrationError(ThermalInspectionError):
    """Base exception for calibration-related errors."""
    pass


class CalibrationNotAvailableError(CalibrationError):
    """Raised when calibration data is not available."""

    def __init__(self, calibration_type: str = "calibration"):
        super().__init__(f"{calibration_type.title()} not available or not configured")
        self.calibration_type = calibration_type


class CalibrationInvalidError(CalibrationError):
    """Raised when calibration data is invalid or corrupted."""

    def __init__(self, message: str = "Invalid calibration data"):
        super().__init__(message)


# =============================================================================
# Configuration Exceptions
# =============================================================================

class ConfigurationError(ThermalInspectionError):
    """Base exception for configuration-related errors."""
    pass


class ConfigFileError(ConfigurationError):
    """Raised when config file cannot be read or parsed."""

    def __init__(self, filepath: str, reason: str = "unknown error"):
        super().__init__(f"Configuration file error: {filepath} ({reason})")
        self.filepath = filepath
        self.reason = reason


class InvalidConfigError(ConfigurationError):
    """Raised when configuration values are invalid."""

    def __init__(self, key: str, value: Any, reason: str = "invalid value"):
        super().__init__(f"Invalid configuration: {key}={value} ({reason})")
        self.key = key
        self.value = value
        self.reason = reason


# =============================================================================
# ROI Exceptions
# =============================================================================

class ROIError(ThermalInspectionError):
    """Base exception for ROI-related errors."""
    pass


class ROINotFoundError(ROIError):
    """Raised when an ROI cannot be found."""

    def __init__(self, roi_id: str):
        super().__init__(f"ROI not found: {roi_id}")
        self.roi_id = roi_id


class InvalidROIError(ROIError):
    """Raised when ROI coordinates or dimensions are invalid."""

    def __init__(self, message: str = "Invalid ROI parameters"):
        super().__init__(message)


# =============================================================================
# Recording Exceptions
# =============================================================================

class RecordingError(ThermalInspectionError):
    """Base exception for recording-related errors."""
    pass


class RecordingStartError(RecordingError):
    """Raised when recording fails to start."""

    def __init__(self, message: str = "Failed to start recording", filepath: Optional[str] = None):
        super().__init__(message, details={"filepath": filepath})
        self.filepath = filepath


class RecordingWriteError(RecordingError):
    """Raised when writing to recording fails."""

    def __init__(self, message: str = "Failed to write frame"):
        super().__init__(message)


# =============================================================================
# GUI Exceptions
# =============================================================================

class GUIError(ThermalInspectionError):
    """Base exception for GUI-related errors."""
    pass


class WidgetError(GUIError):
    """Raised when a widget operation fails."""

    def __init__(self, widget_name: str, operation: str = "operation"):
        super().__init__(f"Widget '{widget_name}' {operation} failed")
        self.widget_name = widget_name
        self.operation = operation
