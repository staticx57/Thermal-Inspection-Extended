"""
Unit Tests for Custom Exceptions

Tests the exception hierarchy including:
- Exception instantiation
- Exception inheritance
- Exception message formatting
- Exception details/context
"""

import pytest
from exceptions import (
    # Base
    ThermalInspectionError,
    # Camera
    CameraError,
    CameraNotFoundError,
    CameraConnectionError,
    CameraDisconnectedError,
    CameraTimeoutError,
    FrameCaptureError,
    # SDK
    SDKError,
    SDKNotAvailableError,
    SDKConnectionError,
    SDKCommandError,
    SDKTimeoutError,
    # Processing
    ProcessingError,
    FusionError,
    AnalysisError,
    PaletteError,
    # Calibration
    CalibrationError,
    CalibrationNotAvailableError,
    CalibrationInvalidError,
    # Configuration
    ConfigurationError,
    ConfigFileError,
    InvalidConfigError,
    # ROI
    ROIError,
    ROINotFoundError,
    InvalidROIError,
    # Recording
    RecordingError,
    RecordingStartError,
    RecordingWriteError,
    # GUI
    GUIError,
    WidgetError,
)


class TestBaseException:
    """Tests for ThermalInspectionError base class."""

    @pytest.mark.unit
    def test_base_exception_creation(self):
        """Test base exception can be instantiated."""
        exc = ThermalInspectionError("Test error")
        assert str(exc) == "Test error"
        assert exc.message == "Test error"

    @pytest.mark.unit
    def test_base_exception_with_details(self):
        """Test base exception with details."""
        exc = ThermalInspectionError("Test error", details={"key": "value"})
        assert exc.details == {"key": "value"}
        assert "key" in str(exc)

    @pytest.mark.unit
    def test_base_exception_is_exception(self):
        """Test base exception inherits from Exception."""
        exc = ThermalInspectionError("Test")
        assert isinstance(exc, Exception)


class TestCameraExceptions:
    """Tests for camera-related exceptions."""

    @pytest.mark.unit
    def test_camera_error_hierarchy(self):
        """Test CameraError inheritance."""
        exc = CameraError("Camera failed")
        assert isinstance(exc, ThermalInspectionError)
        assert isinstance(exc, Exception)

    @pytest.mark.unit
    def test_camera_not_found_default(self):
        """Test CameraNotFoundError with defaults."""
        exc = CameraNotFoundError()
        assert "not found" in str(exc).lower()

    @pytest.mark.unit
    def test_camera_not_found_with_type(self):
        """Test CameraNotFoundError with camera type."""
        exc = CameraNotFoundError(camera_type="thermal")
        assert "thermal" in str(exc).lower()
        assert exc.camera_type == "thermal"

    @pytest.mark.unit
    def test_camera_not_found_with_device_id(self):
        """Test CameraNotFoundError with device ID."""
        exc = CameraNotFoundError(camera_type="rgb", device_id=2)
        assert exc.device_id == 2
        assert "2" in str(exc)

    @pytest.mark.unit
    def test_camera_connection_error(self):
        """Test CameraConnectionError."""
        exc = CameraConnectionError("Connection refused", camera_type="thermal")
        assert exc.camera_type == "thermal"
        assert "connection" in str(exc).lower()

    @pytest.mark.unit
    def test_camera_disconnected_error(self):
        """Test CameraDisconnectedError."""
        exc = CameraDisconnectedError(camera_type="thermal")
        assert "disconnect" in str(exc).lower()

    @pytest.mark.unit
    def test_camera_timeout_error(self):
        """Test CameraTimeoutError."""
        exc = CameraTimeoutError(operation="frame capture", timeout_seconds=5.0)
        assert exc.operation == "frame capture"
        assert exc.timeout_seconds == 5.0
        assert "5.0" in str(exc)

    @pytest.mark.unit
    def test_frame_capture_error(self):
        """Test FrameCaptureError."""
        exc = FrameCaptureError("Buffer overflow", camera_type="thermal")
        assert exc.camera_type == "thermal"


class TestSDKExceptions:
    """Tests for SDK-related exceptions."""

    @pytest.mark.unit
    def test_sdk_error_hierarchy(self):
        """Test SDKError inheritance."""
        exc = SDKError("SDK failed")
        assert isinstance(exc, ThermalInspectionError)

    @pytest.mark.unit
    def test_sdk_not_available(self):
        """Test SDKNotAvailableError."""
        exc = SDKNotAvailableError(sdk_name="Boson SDK")
        assert exc.sdk_name == "Boson SDK"
        assert "boson" in str(exc).lower()

    @pytest.mark.unit
    def test_sdk_connection_error(self):
        """Test SDKConnectionError."""
        exc = SDKConnectionError(sdk_name="Boson SDK", port="COM7")
        assert exc.sdk_name == "Boson SDK"
        assert exc.port == "COM7"
        assert "COM7" in str(exc)

    @pytest.mark.unit
    def test_sdk_command_error(self):
        """Test SDKCommandError."""
        exc = SDKCommandError(command="set_gain", error_code=0x02, sdk_name="Boson")
        assert exc.command == "set_gain"
        assert exc.error_code == 0x02
        assert "set_gain" in str(exc)

    @pytest.mark.unit
    def test_sdk_timeout_error(self):
        """Test SDKTimeoutError."""
        exc = SDKTimeoutError(operation="FFC", sdk_name="Boson")
        assert exc.operation == "FFC"


class TestProcessingExceptions:
    """Tests for processing-related exceptions."""

    @pytest.mark.unit
    def test_processing_error_hierarchy(self):
        """Test ProcessingError inheritance."""
        exc = ProcessingError("Processing failed")
        assert isinstance(exc, ThermalInspectionError)

    @pytest.mark.unit
    def test_fusion_error(self):
        """Test FusionError."""
        exc = FusionError("Frame size mismatch", fusion_mode="alpha_blend")
        assert exc.fusion_mode == "alpha_blend"

    @pytest.mark.unit
    def test_analysis_error(self):
        """Test AnalysisError."""
        exc = AnalysisError("Invalid data", analysis_type="hot_spot")
        assert exc.analysis_type == "hot_spot"

    @pytest.mark.unit
    def test_palette_error(self):
        """Test PaletteError."""
        exc = PaletteError("Unknown palette", palette_name="invalid")
        assert exc.palette_name == "invalid"


class TestCalibrationExceptions:
    """Tests for calibration-related exceptions."""

    @pytest.mark.unit
    def test_calibration_error_hierarchy(self):
        """Test CalibrationError inheritance."""
        exc = CalibrationError("Calibration failed")
        assert isinstance(exc, ThermalInspectionError)

    @pytest.mark.unit
    def test_calibration_not_available(self):
        """Test CalibrationNotAvailableError."""
        exc = CalibrationNotAvailableError(calibration_type="radiometric")
        assert exc.calibration_type == "radiometric"

    @pytest.mark.unit
    def test_calibration_invalid(self):
        """Test CalibrationInvalidError."""
        exc = CalibrationInvalidError("Corrupted data")
        assert "corrupt" in str(exc).lower() or "invalid" in str(exc).lower()


class TestConfigurationExceptions:
    """Tests for configuration-related exceptions."""

    @pytest.mark.unit
    def test_configuration_error_hierarchy(self):
        """Test ConfigurationError inheritance."""
        exc = ConfigurationError("Config failed")
        assert isinstance(exc, ThermalInspectionError)

    @pytest.mark.unit
    def test_config_file_error(self):
        """Test ConfigFileError."""
        exc = ConfigFileError(filepath="/path/to/config.json", reason="file not found")
        assert exc.filepath == "/path/to/config.json"
        assert exc.reason == "file not found"

    @pytest.mark.unit
    def test_invalid_config_error(self):
        """Test InvalidConfigError."""
        exc = InvalidConfigError(key="threshold", value=-1, reason="must be positive")
        assert exc.key == "threshold"
        assert exc.value == -1


class TestROIExceptions:
    """Tests for ROI-related exceptions."""

    @pytest.mark.unit
    def test_roi_error_hierarchy(self):
        """Test ROIError inheritance."""
        exc = ROIError("ROI failed")
        assert isinstance(exc, ThermalInspectionError)

    @pytest.mark.unit
    def test_roi_not_found(self):
        """Test ROINotFoundError."""
        exc = ROINotFoundError(roi_id="roi_123")
        assert exc.roi_id == "roi_123"
        assert "roi_123" in str(exc)

    @pytest.mark.unit
    def test_invalid_roi(self):
        """Test InvalidROIError."""
        exc = InvalidROIError("Negative dimensions")
        assert "invalid" in str(exc).lower() or "negative" in str(exc).lower()


class TestRecordingExceptions:
    """Tests for recording-related exceptions."""

    @pytest.mark.unit
    def test_recording_error_hierarchy(self):
        """Test RecordingError inheritance."""
        exc = RecordingError("Recording failed")
        assert isinstance(exc, ThermalInspectionError)

    @pytest.mark.unit
    def test_recording_start_error(self):
        """Test RecordingStartError."""
        exc = RecordingStartError("Codec not found", filepath="/videos/test.mp4")
        assert exc.filepath == "/videos/test.mp4"

    @pytest.mark.unit
    def test_recording_write_error(self):
        """Test RecordingWriteError."""
        exc = RecordingWriteError("Disk full")
        assert "write" in str(exc).lower() or "disk" in str(exc).lower()


class TestGUIExceptions:
    """Tests for GUI-related exceptions."""

    @pytest.mark.unit
    def test_gui_error_hierarchy(self):
        """Test GUIError inheritance."""
        exc = GUIError("GUI failed")
        assert isinstance(exc, ThermalInspectionError)

    @pytest.mark.unit
    def test_widget_error(self):
        """Test WidgetError."""
        exc = WidgetError(widget_name="VideoWidget", operation="resize")
        assert exc.widget_name == "VideoWidget"
        assert exc.operation == "resize"


class TestExceptionRaising:
    """Tests for raising and catching exceptions."""

    @pytest.mark.unit
    def test_raise_and_catch_base(self):
        """Test raising and catching base exception."""
        with pytest.raises(ThermalInspectionError):
            raise ThermalInspectionError("Test")

    @pytest.mark.unit
    def test_catch_derived_as_base(self):
        """Test catching derived exception as base type."""
        with pytest.raises(ThermalInspectionError):
            raise CameraNotFoundError()

    @pytest.mark.unit
    def test_catch_specific_exception(self):
        """Test catching specific exception type."""
        with pytest.raises(CameraNotFoundError):
            raise CameraNotFoundError(camera_type="thermal")

    @pytest.mark.unit
    def test_exception_chaining(self):
        """Test exception chaining with 'from'."""
        try:
            try:
                raise ValueError("Original error")
            except ValueError as e:
                raise CameraError("Camera failed") from e
        except CameraError as exc:
            assert exc.__cause__ is not None
            assert isinstance(exc.__cause__, ValueError)

    @pytest.mark.unit
    def test_multiple_exception_catch(self):
        """Test catching multiple exception types."""
        exceptions_to_test = [
            CameraNotFoundError(),
            CameraTimeoutError(),
            CameraDisconnectedError()
        ]

        for exc in exceptions_to_test:
            with pytest.raises(CameraError):
                raise exc


class TestExceptionDetails:
    """Tests for exception details and context."""

    @pytest.mark.unit
    def test_exception_details_dict(self):
        """Test that details are stored as dict."""
        exc = CameraNotFoundError(camera_type="thermal", device_id=1)
        assert isinstance(exc.details, dict)
        assert "camera_type" in exc.details
        assert "device_id" in exc.details

    @pytest.mark.unit
    def test_exception_str_includes_details(self):
        """Test that str representation includes key details."""
        exc = SDKCommandError(command="test_cmd", error_code=5)
        msg = str(exc)
        assert "test_cmd" in msg
        assert "5" in msg

    @pytest.mark.unit
    def test_exception_repr(self):
        """Test exception repr for debugging."""
        exc = CameraTimeoutError(operation="connect", timeout_seconds=10)
        # Should be representable
        repr_str = repr(exc)
        assert "CameraTimeoutError" in repr_str or "connect" in repr_str
