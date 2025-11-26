"""
RGB Camera Interface - FLIR Firefly Global Shutter
Supports FLIR Firefly series cameras via Spinnaker SDK
Requires PySpin (Python wrapper for Spinnaker)

Compatible models:
- Firefly S (USB 2.0)
- Firefly (USB 3.0)
- FireFly MV (Machine Vision)
- All use Sony IMX sensors with GLOBAL SHUTTER (no rolling shutter artifacts)

Advantages over rolling shutter:
- No motion blur for moving objects
- Accurate object detection in high-speed scenarios
- Better for automotive/driving applications

Installation (Cross-Platform):
- Windows: Download and install Spinnaker SDK + PySpin from FLIR website
  https://www.flir.com/products/spinnaker-sdk/
- Linux: Download and install Spinnaker SDK + PySpin from FLIR website
  For Ubuntu: Use .deb packages, then pip install spinnaker_python-*.whl
- macOS: Download and install Spinnaker SDK + PySpin from FLIR website

Note: The SDK is cross-platform and works identically on Windows/Linux/macOS
"""
import numpy as np
import logging
from typing import Tuple, Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Try to import PySpin (optional dependency)
try:
    import PySpin
    PYSPIN_AVAILABLE = True
except ImportError:
    PYSPIN_AVAILABLE = False
    logger.warning("PySpin not available. FLIR Firefly support disabled.")
    logger.warning("Install Spinnaker SDK from: https://www.flir.com/products/spinnaker-sdk/")


class RGBCameraFirefly:
    """
    FLIR Firefly camera interface (Global Shutter)
    Requires Spinnaker SDK + PySpin
    """

    def __init__(self, camera_index: int = 0, resolution: Tuple[int, int] = (640, 480),
                 fps: int = 30, pixel_format: str = "BGR8"):
        """
        Initialize FLIR Firefly camera

        Args:
            camera_index: Camera index (0 for first Firefly detected)
            resolution: Desired resolution (width, height)
            fps: Target frame rate
            pixel_format: Pixel format ("BGR8" for OpenCV compatibility, "Mono8" for grayscale)
        """
        if not PYSPIN_AVAILABLE:
            raise ImportError("PySpin not available. Install Spinnaker SDK from FLIR.")

        self.camera_index = camera_index
        self.width, self.height = resolution
        self.fps = fps
        self.pixel_format = pixel_format
        self.system = None
        self.cam = None
        self.is_open = False
        self.camera_type = "FLIR Firefly"

    def open(self) -> bool:
        """
        Open camera connection

        Returns:
            True if successful
        """
        if not PYSPIN_AVAILABLE:
            logger.error("PySpin not available. Cannot open Firefly camera.")
            return False

        try:
            # Retrieve singleton reference to system object
            self.system = PySpin.System.GetInstance()

            # Retrieve list of cameras from the system
            cam_list = self.system.GetCameras()

            num_cameras = cam_list.GetSize()
            logger.info(f'Number of FLIR cameras detected: {num_cameras}')

            if num_cameras == 0:
                logger.error('No FLIR Firefly cameras detected!')
                cam_list.Clear()
                self.system.ReleaseInstance()
                return False

            # Check if requested index is valid
            if self.camera_index >= num_cameras:
                logger.error(f'Camera index {self.camera_index} out of range (0-{num_cameras-1})')
                cam_list.Clear()
                self.system.ReleaseInstance()
                return False

            # Retrieve camera by index
            self.cam = cam_list[self.camera_index]

            # Initialize camera
            self.cam.Init()

            # Get device info (log only essential info to avoid access exceptions)
            nodemap_tldevice = self.cam.GetTLDeviceNodeMap()

            try:
                # Get essential camera info
                node_model = PySpin.CStringPtr(nodemap_tldevice.GetNode('DeviceModelName'))
                if PySpin.IsReadable(node_model):
                    logger.info(f'Model: {node_model.GetValue()}')

                node_serial = PySpin.CStringPtr(nodemap_tldevice.GetNode('DeviceSerialNumber'))
                if PySpin.IsReadable(node_serial):
                    logger.info(f'Serial: {node_serial.GetValue()}')

                node_vendor = PySpin.CStringPtr(nodemap_tldevice.GetNode('DeviceVendorName'))
                if PySpin.IsReadable(node_vendor):
                    logger.info(f'Vendor: {node_vendor.GetValue()}')
            except:
                logger.debug("Could not read all device info properties")

            # Configure camera settings
            self._configure_camera()

            # Start acquisition
            self.cam.BeginAcquisition()

            logger.info(f"{self.camera_type} opened successfully")
            logger.info(f"Resolution: {self.width}x{self.height} @ {self.fps} FPS")
            logger.info(f"Pixel format: {self.pixel_format}")
            logger.info(f"Global shutter: Motion blur eliminated")

            # Release camera list (but keep camera reference)
            cam_list.Clear()

            # Warm up camera (discard first few frames)
            for _ in range(5):
                try:
                    image_result = self.cam.GetNextImage(1000)  # 1000ms timeout
                    image_result.Release()
                except:
                    pass

            self.is_open = True
            return True

        except PySpin.SpinnakerException as ex:
            logger.error(f'Spinnaker error: {ex}')
            return False
        except Exception as e:
            logger.error(f'Failed to open Firefly camera: {e}')
            return False

    def get_max_resolution(self) -> Tuple[int, int]:
        """
        Get maximum supported resolution of the camera

        Returns:
            (max_width, max_height) tuple
        """
        if self.cam is None:
            return (0, 0)

        try:
            nodemap = self.cam.GetNodeMap()

            # Get max width
            node_width = PySpin.CIntegerPtr(nodemap.GetNode('Width'))
            if PySpin.IsAvailable(node_width) and PySpin.IsReadable(node_width):
                max_width = node_width.GetMax()
            else:
                max_width = self.width

            # Get max height
            node_height = PySpin.CIntegerPtr(nodemap.GetNode('Height'))
            if PySpin.IsAvailable(node_height) and PySpin.IsReadable(node_height):
                max_height = node_height.GetMax()
            else:
                max_height = self.height

            return (max_width, max_height)

        except Exception as e:
            logger.warning(f"Could not get max resolution: {e}")
            return (self.width, self.height)

    def _configure_camera(self):
        """
        Configure camera settings (resolution, FPS, pixel format)

        IMPORTANT: If resolution is not specified (0x0), uses maximum available resolution
        to preserve detail before any downstream resizing.
        """
        if self.cam is None:
            return

        try:
            nodemap = self.cam.GetNodeMap()

            # Auto-detect max resolution if not specified
            if self.width == 0 or self.height == 0:
                logger.info("Resolution not specified - detecting maximum available resolution...")
                max_width, max_height = self.get_max_resolution()
                self.width = max_width
                self.height = max_height
                logger.info(f"Using maximum resolution: {self.width}x{self.height}")

            # Set pixel format
            node_pixel_format = PySpin.CEnumerationPtr(nodemap.GetNode('PixelFormat'))
            if PySpin.IsAvailable(node_pixel_format) and PySpin.IsWritable(node_pixel_format):
                # Map OpenCV-friendly formats to Spinnaker formats
                format_map = {
                    'BGR8': 'BGR8',
                    'RGB8': 'RGB8',
                    'Mono8': 'Mono8',
                    'BayerRG8': 'BayerRG8'
                }
                spinnaker_format = format_map.get(self.pixel_format, 'BGR8')

                node_pixel_format_entry = node_pixel_format.GetEntryByName(spinnaker_format)
                if PySpin.IsAvailable(node_pixel_format_entry) and PySpin.IsReadable(node_pixel_format_entry):
                    pixel_format_value = node_pixel_format_entry.GetValue()
                    node_pixel_format.SetIntValue(pixel_format_value)
                    logger.info(f'Pixel format set to: {spinnaker_format}')
                else:
                    logger.warning(f'Pixel format {spinnaker_format} not available, using default')

            # Set width
            node_width = PySpin.CIntegerPtr(nodemap.GetNode('Width'))
            if PySpin.IsAvailable(node_width) and PySpin.IsWritable(node_width):
                max_width = node_width.GetMax()
                target_width = min(self.width, max_width)
                node_width.SetValue(target_width)
                self.width = target_width
                logger.info(f'Width set to: {self.width}')

            # Set height
            node_height = PySpin.CIntegerPtr(nodemap.GetNode('Height'))
            if PySpin.IsAvailable(node_height) and PySpin.IsWritable(node_height):
                max_height = node_height.GetMax()
                target_height = min(self.height, max_height)
                node_height.SetValue(target_height)
                self.height = target_height
                logger.info(f'Height set to: {self.height}')

            # Set frame rate (enable acquisition frame rate control first)
            node_acquisition_framerate_enable = PySpin.CBooleanPtr(nodemap.GetNode('AcquisitionFrameRateEnable'))
            if PySpin.IsAvailable(node_acquisition_framerate_enable) and PySpin.IsWritable(node_acquisition_framerate_enable):
                node_acquisition_framerate_enable.SetValue(True)

            node_acquisition_framerate = PySpin.CFloatPtr(nodemap.GetNode('AcquisitionFrameRate'))
            if PySpin.IsAvailable(node_acquisition_framerate) and PySpin.IsWritable(node_acquisition_framerate):
                max_fps = node_acquisition_framerate.GetMax()
                target_fps = min(self.fps, max_fps)
                node_acquisition_framerate.SetValue(target_fps)
                self.fps = target_fps
                logger.info(f'Frame rate set to: {self.fps} FPS')

            # Set acquisition mode to continuous
            node_acquisition_mode = PySpin.CEnumerationPtr(nodemap.GetNode('AcquisitionMode'))
            if PySpin.IsAvailable(node_acquisition_mode) and PySpin.IsWritable(node_acquisition_mode):
                node_acquisition_mode_continuous = node_acquisition_mode.GetEntryByName('Continuous')
                if PySpin.IsAvailable(node_acquisition_mode_continuous) and PySpin.IsReadable(node_acquisition_mode_continuous):
                    acquisition_mode_continuous = node_acquisition_mode_continuous.GetValue()
                    node_acquisition_mode.SetIntValue(acquisition_mode_continuous)
                    logger.info('Acquisition mode set to continuous')

            # Enable auto exposure
            node_exposure_auto = PySpin.CEnumerationPtr(nodemap.GetNode('ExposureAuto'))
            if PySpin.IsAvailable(node_exposure_auto) and PySpin.IsWritable(node_exposure_auto):
                node_exposure_auto_continuous = node_exposure_auto.GetEntryByName('Continuous')
                if PySpin.IsAvailable(node_exposure_auto_continuous) and PySpin.IsReadable(node_exposure_auto_continuous):
                    exposure_auto_continuous = node_exposure_auto_continuous.GetValue()
                    node_exposure_auto.SetIntValue(exposure_auto_continuous)
                    logger.info('Auto exposure enabled')

            # Enable auto gain
            node_gain_auto = PySpin.CEnumerationPtr(nodemap.GetNode('GainAuto'))
            if PySpin.IsAvailable(node_gain_auto) and PySpin.IsWritable(node_gain_auto):
                node_gain_auto_continuous = node_gain_auto.GetEntryByName('Continuous')
                if PySpin.IsAvailable(node_gain_auto_continuous) and PySpin.IsReadable(node_gain_auto_continuous):
                    gain_auto_continuous = node_gain_auto_continuous.GetValue()
                    node_gain_auto.SetIntValue(gain_auto_continuous)
                    logger.info('Auto gain enabled')

            # Enable auto white balance (if available)
            node_balance_white_auto = PySpin.CEnumerationPtr(nodemap.GetNode('BalanceWhiteAuto'))
            if PySpin.IsAvailable(node_balance_white_auto) and PySpin.IsWritable(node_balance_white_auto):
                node_balance_white_auto_continuous = node_balance_white_auto.GetEntryByName('Continuous')
                if PySpin.IsAvailable(node_balance_white_auto_continuous) and PySpin.IsReadable(node_balance_white_auto_continuous):
                    balance_white_auto_continuous = node_balance_white_auto_continuous.GetValue()
                    node_balance_white_auto.SetIntValue(balance_white_auto_continuous)
                    logger.info('Auto white balance enabled')

        except PySpin.SpinnakerException as ex:
            logger.error(f'Error configuring camera: {ex}')

    def read(self, flush_buffer: bool = False) -> Tuple[bool, Optional[np.ndarray]]:
        """
        Read frame from camera

        Args:
            flush_buffer: If True, grab latest frame (not used for Firefly, always returns latest)

        Returns:
            (success, frame) tuple
        """
        if not self.is_open or self.cam is None:
            return False, None

        try:
            # Retrieve next received image (1000ms timeout)
            image_result = self.cam.GetNextImage(1000)

            # Ensure image completion
            if image_result.IsIncomplete():
                logger.warning(f'Image incomplete with status {image_result.GetImageStatus()}')
                image_result.Release()
                return False, None

            # Convert to numpy array
            if self.pixel_format == "BGR8":
                # Already in BGR8 format (OpenCV compatible)
                image_data = image_result.GetNDArray()
            elif self.pixel_format == "RGB8":
                # Convert RGB to BGR for OpenCV
                image_data = image_result.GetNDArray()
                image_data = image_data[:, :, ::-1]  # RGB to BGR
            elif self.pixel_format == "Mono8":
                # Grayscale
                image_data = image_result.GetNDArray()
            else:
                # For other formats, convert to BGR8
                image_converted = image_result.Convert(PySpin.PixelFormat_BGR8, PySpin.HQ_LINEAR)
                image_data = image_converted.GetNDArray()

            # Release image
            image_result.Release()

            return True, image_data

        except PySpin.SpinnakerException as ex:
            logger.error(f'Spinnaker error reading image: {ex}')
            return False, None
        except Exception as e:
            logger.error(f'Error reading Firefly camera: {e}')
            return False, None

    def get_actual_resolution(self) -> Tuple[int, int]:
        """
        Get actual camera resolution

        Returns:
            (width, height) tuple
        """
        if not self.is_open or self.cam is None:
            return (0, 0)

        return (self.width, self.height)

    def set_property(self, prop_name: str, value) -> bool:
        """
        Set camera property (Spinnaker-specific)

        Args:
            prop_name: Property name (e.g., "ExposureTime", "Gain")
            value: Property value

        Returns:
            True if successful
        """
        if not self.is_open or self.cam is None:
            return False

        try:
            nodemap = self.cam.GetNodeMap()
            node = nodemap.GetNode(prop_name)

            if node is None or not PySpin.IsAvailable(node) or not PySpin.IsWritable(node):
                logger.warning(f"Property {prop_name} not available or not writable")
                return False

            # Try different node types
            if PySpin.CFloatPtr(node).IsValid():
                PySpin.CFloatPtr(node).SetValue(float(value))
            elif PySpin.CIntegerPtr(node).IsValid():
                PySpin.CIntegerPtr(node).SetValue(int(value))
            elif PySpin.CBooleanPtr(node).IsValid():
                PySpin.CBooleanPtr(node).SetValue(bool(value))
            else:
                logger.warning(f"Unsupported property type for {prop_name}")
                return False

            logger.info(f"Set {prop_name} = {value}")
            return True

        except PySpin.SpinnakerException as ex:
            logger.error(f'Error setting property {prop_name}: {ex}')
            return False

    def get_property(self, prop_name: str):
        """
        Get camera property (Spinnaker-specific)

        Args:
            prop_name: Property name (e.g., "ExposureTime", "Gain")

        Returns:
            Property value or None
        """
        if not self.is_open or self.cam is None:
            return None

        try:
            nodemap = self.cam.GetNodeMap()
            node = nodemap.GetNode(prop_name)

            if node is None or not PySpin.IsAvailable(node) or not PySpin.IsReadable(node):
                logger.warning(f"Property {prop_name} not available or not readable")
                return None

            # Try different node types
            if PySpin.CFloatPtr(node).IsValid():
                return PySpin.CFloatPtr(node).GetValue()
            elif PySpin.CIntegerPtr(node).IsValid():
                return PySpin.CIntegerPtr(node).GetValue()
            elif PySpin.CBooleanPtr(node).IsValid():
                return PySpin.CBooleanPtr(node).GetValue()
            else:
                logger.warning(f"Unsupported property type for {prop_name}")
                return None

        except PySpin.SpinnakerException as ex:
            logger.error(f'Error getting property {prop_name}: {ex}')
            return None

    # ========================================================================
    # Advanced Camera Controls - Exposure
    # ========================================================================

    def set_exposure_mode(self, mode: str) -> bool:
        """
        Set exposure control mode
        
        Args:
            mode: 'Off' (manual), 'Once' (single auto), or 'Continuous' (continuous auto)
        
        Returns:
            True if successful
        """
        if not self.is_open or self.cam is None:
            return False
        
        try:
            nodemap = self.cam.GetNodeMap()
            node_exposure_auto = PySpin.CEnumerationPtr(nodemap.GetNode('ExposureAuto'))
            
            if PySpin.IsAvailable(node_exposure_auto) and PySpin.IsWritable(node_exposure_auto):
                mode_entry = node_exposure_auto.GetEntryByName(mode)
                if PySpin.IsAvailable(mode_entry) and PySpin.IsReadable(mode_entry):
                    node_exposure_auto.SetIntValue(mode_entry.GetValue())
                    logger.info(f'Exposure mode set to: {mode}')
                    return True
            return False
        except PySpin.SpinnakerException as ex:
            logger.error(f'Error setting exposure mode: {ex}')
            return False

    def set_exposure_time(self, time_us: float) -> bool:
        """
        Set manual exposure time in microseconds
        
        Args:
            time_us: Exposure time (e.g., 5000 = 5ms)
        
        Returns:
            True if successful
        """
        if not self.is_open or self.cam is None:
            return False
        
        try:
            # First set mode to manual
            self.set_exposure_mode('Off')
            
            nodemap = self.cam.GetNodeMap()
            node_exposure_time = PySpin.CFloatPtr(nodemap.GetNode('ExposureTime'))
            
            if PySpin.IsAvailable(node_exposure_time) and PySpin.IsWritable(node_exposure_time):
                # Clamp to valid range
                min_exp = node_exposure_time.GetMin()
                max_exp = node_exposure_time.GetMax()
                clamped_time = max(min_exp, min(time_us, max_exp))
                
                node_exposure_time.SetValue(clamped_time)
                logger.info(f'Exposure time set to: {clamped_time} µs')
                return True
            return False
        except PySpin.SpinnakerException as ex:
            logger.error(f'Error setting exposure time: {ex}')
            return False

    def get_exposure_time(self) -> float:
        """Get current exposure time in microseconds"""
        return self.get_property('ExposureTime') or 0.0

    def get_exposure_range(self) -> Tuple[float, float]:
        """
        Get valid exposure time range
        
        Returns:
            (min_us, max_us) tuple
        """
        if not self.is_open or self.cam is None:
            return (0.0, 0.0)
        
        try:
            nodemap = self.cam.GetNodeMap()
            node_exposure_time = PySpin.CFloatPtr(nodemap.GetNode('ExposureTime'))
            
            if PySpin.IsAvailable(node_exposure_time) and PySpin.IsReadable(node_exposure_time):
                return (node_exposure_time.GetMin(), node_exposure_time.GetMax())
        except:
            pass
        return (0.0, 0.0)

    # ========================================================================
    # Advanced Camera Controls - Gain
    # ========================================================================

    def set_gain_mode(self, mode: str) -> bool:
        """
        Set gain control mode
        
        Args:
            mode: 'Off' (manual), 'Once' (single auto), or 'Continuous' (continuous auto)
        
        Returns:
            True if successful
        """
        if not self.is_open or self.cam is None:
            return False
        
        try:
            nodemap = self.cam.GetNodeMap()
            node_gain_auto = PySpin.CEnumerationPtr(nodemap.GetNode('GainAuto'))
            
            if PySpin.IsAvailable(node_gain_auto) and PySpin.IsWritable(node_gain_auto):
                mode_entry = node_gain_auto.GetEntryByName(mode)
                if PySpin.IsAvailable(mode_entry) and PySpin.IsReadable(mode_entry):
                    node_gain_auto.SetIntValue(mode_entry.GetValue())
                    logger.info(f'Gain mode set to: {mode}')
                    return True
            return False
        except PySpin.SpinnakerException as ex:
            logger.error(f'Error setting gain mode: {ex}')
            return False

    def set_gain(self, gain_db: float) -> bool:
        """
        Set manual gain in decibels
        
        Args:
            gain_db: Gain value (0.0 - 18.0 dB typical)
        
        Returns:
            True if successful
        """
        if not self.is_open or self.cam is None:
            return False
        
        try:
            # First set mode to manual
            self.set_gain_mode('Off')
            
            nodemap = self.cam.GetNodeMap()
            node_gain = PySpin.CFloatPtr(nodemap.GetNode('Gain'))
            
            if PySpin.IsAvailable(node_gain) and PySpin.IsWritable(node_gain):
                min_gain = node_gain.GetMin()
                max_gain = node_gain.GetMax()
                clamped_gain = max(min_gain, min(gain_db, max_gain))
                
                node_gain.SetValue(clamped_gain)
                logger.info(f'Gain set to: {clamped_gain} dB')
                return True
            return False
        except PySpin.SpinnakerException as ex:
            logger.error(f'Error setting gain: {ex}')
            return False

    def get_gain(self) -> float:
        """Get current gain in dB"""
        return self.get_property('Gain') or 0.0

    def get_gain_range(self) -> Tuple[float, float]:
        """
        Get valid gain range
        
        Returns:
            (min_db, max_db) tuple
        """
        if not self.is_open or self.cam is None:
            return (0.0, 0.0)
        
        try:
            nodemap = self.cam.GetNodeMap()
            node_gain = PySpin.CFloatPtr(nodemap.GetNode('Gain'))
            
            if PySpin.IsAvailable(node_gain) and PySpin.IsReadable(node_gain):
                return (node_gain.GetMin(), node_gain.GetMax())
        except:
            pass
        return (0.0, 0.0)

    # ========================================================================
    # Advanced Camera Controls - White Balance
    # ========================================================================

    def set_white_balance_mode(self, mode: str) -> bool:
        """
        Set white balance mode
        
        Args:
            mode: 'Off' (manual), 'Once' (single calibration), or 'Continuous' (auto)
        
        Returns:
            True if successful
        """
        if not self.is_open or self.cam is None:
            return False
        
        try:
            nodemap = self.cam.GetNodeMap()
            node_wb_auto = PySpin.CEnumerationPtr(nodemap.GetNode('BalanceWhiteAuto'))
            
            if PySpin.IsAvailable(node_wb_auto) and PySpin.IsWritable(node_wb_auto):
                mode_entry = node_wb_auto.GetEntryByName(mode)
                if PySpin.IsAvailable(mode_entry) and PySpin.IsReadable(mode_entry):
                    node_wb_auto.SetIntValue(mode_entry.GetValue())
                    logger.info(f'White balance mode set to: {mode}')
                    return True
            return False
        except PySpin.SpinnakerException as ex:
            logger.error(f'Error setting white balance mode: {ex}')
            return False

    def calibrate_white_balance(self) -> bool:
        """
        Perform one-shot white balance calibration
        Point camera at white surface before calling
        
        Returns:
            True if successful
        """
        logger.info("Performing white balance calibration...")
        return self.set_white_balance_mode('Once')

    def set_white_balance_ratio(self, color: str, ratio: float) -> bool:
        """
        Set manual white balance ratio for specific color
        
        Args:
            color: 'Red' or 'Blue'
            ratio: Balance ratio (typically 0.5 - 3.0)
        
        Returns:
            True if successful
        """
        if not self.is_open or self.cam is None:
            return False
        
        try:
            # First set mode to manual
            self.set_white_balance_mode('Off')
            
            nodemap = self.cam.GetNodeMap()
            
            # Select color channel
            node_selector = PySpin.CEnumerationPtr(nodemap.GetNode('BalanceRatioSelector'))
            if PySpin.IsAvailable(node_selector) and PySpin.IsWritable(node_selector):
                color_entry = node_selector.GetEntryByName(color)
                if PySpin.IsAvailable(color_entry):
                    node_selector.SetIntValue(color_entry.GetValue())
                    
                    # Set ratio
                    node_ratio = PySpin.CFloatPtr(nodemap.GetNode('BalanceRatio'))
                    if PySpin.IsAvailable(node_ratio) and PySpin.IsWritable(node_ratio):
                        min_ratio = node_ratio.GetMin()
                        max_ratio = node_ratio.GetMax()
                        clamped_ratio = max(min_ratio, min(ratio, max_ratio))
                        
                        node_ratio.SetValue(clamped_ratio)
                        logger.info(f'{color} balance ratio set to: {clamped_ratio}')
                        return True
            return False
        except PySpin.SpinnakerException as ex:
            logger.error(f'Error setting white balance ratio: {ex}')
            return False

    # ========================================================================
    # Advanced Camera Controls - Trigger
    # ========================================================================

    def set_trigger_mode(self, enabled: bool, source: str = 'Software') -> bool:
        """
        Configure trigger mode
        
        Args:
            enabled: True to enable triggering, False for free-run
            source: 'Software', 'Line0', 'Line1', 'Line2', etc.
        
        Returns:
            True if successful
        """
        if not self.is_open or self.cam is None:
            return False
        
        try:
            nodemap = self.cam.GetNodeMap()
            
            # Stop acquisition for trigger mode change
            was_streaming = self.cam.IsStreaming()
            if was_streaming:
                self.cam.EndAcquisition()
            
            # Set trigger mode
            node_trigger_mode = PySpin.CEnumerationPtr(nodemap.GetNode('TriggerMode'))
            if PySpin.IsAvailable(node_trigger_mode) and PySpin.IsWritable(node_trigger_mode):
                mode_value = 'On' if enabled else 'Off'
                mode_entry = node_trigger_mode.GetEntryByName(mode_value)
                if PySpin.IsAvailable(mode_entry):
                    node_trigger_mode.SetIntValue(mode_entry.GetValue())
            
            if enabled:
                # Set trigger source
                node_trigger_source = PySpin.CEnumerationPtr(nodemap.GetNode('TriggerSource'))
                if PySpin.IsAvailable(node_trigger_source) and PySpin.IsWritable(node_trigger_source):
                    source_entry = node_trigger_source.GetEntryByName(source)
                    if PySpin.IsAvailable(source_entry):
                        node_trigger_source.SetIntValue(source_entry.GetValue())
            
            # Restart acquisition if it was running
            if was_streaming:
                self.cam.BeginAcquisition()
            
            logger.info(f'Trigger mode: {enabled}, source: {source}')
            return True
        except PySpin.SpinnakerException as ex:
            logger.error(f'Error setting trigger mode: {ex}')
            return False

    def execute_software_trigger(self) -> bool:
        """
        Fire software trigger to capture next frame
        Only works if trigger mode is enabled with source='Software'
        
        Returns:
            True if successful
        """
        if not self.is_open or self.cam is None:
            return False
        
        try:
            nodemap = self.cam.GetNodeMap()
            node_trigger_software = PySpin.CCommandPtr(nodemap.GetNode('TriggerSoftware'))
            
            if PySpin.IsAvailable(node_trigger_software) and PySpin.IsWritable(node_trigger_software):
                node_trigger_software.Execute()
                return True
            return False
        except PySpin.SpinnakerException as ex:
            logger.error(f'Error executing software trigger: {ex}')
            return False

    # ========================================================================
    # Advanced Camera Controls - Image Settings
    # ========================================================================

    def set_gamma(self, gamma: float) -> bool:
        """
        Set gamma correction
        
        Args:
            gamma: Gamma value (typically 0.5 - 4.0, default 1.0)
                   < 1.0 = darker, > 1.0 = brighter
        
        Returns:
            True if successful
        """
        if not self.is_open or self.cam is None:
            return False
        
        try:
            # First ensure gamma is enabled
            enable_result = self.set_property('GammaEnable', True)
            
            if enable_result:
                return self.set_property('Gamma', gamma)
            return False
        except Exception as e:
            logger.error(f'Error setting gamma: {e}')
            return False

    def set_sharpness(self, enabled: bool, value: float = 1.0) -> bool:
        """
        Set sharpness/edge enhancement
        
        Args:
            enabled: Enable sharpness control
            value: Sharpness value (camera-dependent, typically 0.0 - 4.0)
        
        Returns:
            True if successful
        """
        if not self.is_open or self.cam is None:
            return False
        
        try:
            enable_result = self.set_property('SharpnessEnable', enabled)
            
            if enabled and enable_result:
                return self.set_property('Sharpness', value)
            return enable_result
        except Exception as e:
            logger.error(f'Error setting sharpness: {e}')
            return False

    def get_camera_info(self) -> dict:
        """
        Get camera information for GUI display

        Returns:
            Dict with keys: model, serial, width, height, fps, pixel_format
        """
        info = {
            'model': self.camera_type,
            'serial': 'Unknown',
            'width': self.width,
            'height': self.height,
            'fps': self.fps,
            'pixel_format': self.pixel_format
        }

        if self.cam is not None and self.is_open:
            try:
                nodemap_tldevice = self.cam.GetTLDeviceNodeMap()

                # Get model name
                node_model = PySpin.CStringPtr(nodemap_tldevice.GetNode('DeviceModelName'))
                if PySpin.IsReadable(node_model):
                    info['model'] = node_model.GetValue()

                # Get serial number
                node_serial = PySpin.CStringPtr(nodemap_tldevice.GetNode('DeviceSerialNumber'))
                if PySpin.IsReadable(node_serial):
                    info['serial'] = node_serial.GetValue()
            except Exception as e:
                logger.debug(f"Could not read camera info: {e}")

        return info

    def release(self):
        """Release camera resources"""
        if self.cam is not None:
            try:
                # End acquisition
                if self.cam.IsStreaming():
                    self.cam.EndAcquisition()

                # Deinitialize camera
                self.cam.DeInit()

                # Release camera reference
                del self.cam
                self.cam = None

                logger.info("Firefly camera released")
            except PySpin.SpinnakerException as ex:
                logger.error(f'Error releasing camera: {ex}')

        if self.system is not None:
            try:
                # Release system instance
                self.system.ReleaseInstance()
                self.system = None
            except:
                pass

        self.is_open = False

    def __del__(self):
        """Cleanup on deletion"""
        self.release()


def detect_firefly_cameras():
    """
    Detect all connected FLIR Firefly cameras
    
    Returns:
        List of camera info dicts with keys: index, model, serial
    """
    if not PYSPIN_AVAILABLE:
        return []
    
    cameras_found = []
    system = None
    cam_list = None
    
    try:
        system = PySpin.System.GetInstance()
        cam_list = system.GetCameras()
        num_cameras = cam_list.GetSize()
        
        logger.info(f'Number of FLIR cameras detected: {num_cameras}')
        
        for i in range(num_cameras):
            try:
                cam = cam_list.GetByIndex(i)
                
                # Get camera info without initializing
                nodemap_tldevice = cam.GetTLDeviceNodeMap()
                
                # Get model name
                node_device_model = PySpin.CStringPtr(nodemap_tldevice.GetNode('DeviceModelName'))
                if PySpin.IsAvailable(node_device_model) and PySpin.IsReadable(node_device_model):
                    model_name = node_device_model.GetValue()
                else:
                    model_name = "Unknown"
                
                # Get serial number
                node_device_serial = PySpin.CStringPtr(nodemap_tldevice.GetNode('DeviceSerialNumber'))
                if PySpin.IsAvailable(node_device_serial) and PySpin.IsReadable(node_device_serial):
                    serial_number = node_device_serial.GetValue()
                else:
                    serial_number = "Unknown"
                
                logger.info(f'Found FLIR camera {i}: {model_name} (S/N: {serial_number})')
                
                cameras_found.append({
                    'index': i,
                    'model': model_name,
                    'serial': serial_number
                })
                
                # Important: Delete camera reference immediately
                del cam
                
            except PySpin.SpinnakerException as ex:
                logger.error(f'Spinnaker error during detection: {ex}')
                continue
        
    except Exception as e:
        logger.error(f'Error detecting cameras: {e}')
    finally:
        # Clean up - DON'T call Clear() as it can cause reference issues
        # Just delete the list object and let Python GC handle it
        if cam_list is not None:
            del cam_list
        
        # Don't release system instance here - let it persist
        # This prevents "can't clear camera" errors
        # system will be cleaned up when process exits
    
    return cameras_found


if __name__ == "__main__":
    """Test FLIR Firefly camera capture"""
    print("="*60)
    print("FLIR Firefly Camera Test")
    print("="*60)

    if not PYSPIN_AVAILABLE:
        print("ERROR: PySpin not installed!")
        print("Install Spinnaker SDK from: https://www.flir.com/products/spinnaker-sdk/")
        exit(1)

    # Detect cameras
    print("\nDetecting FLIR Firefly cameras...")
    cameras = detect_firefly_cameras()

    if not cameras:
        print("No FLIR Firefly cameras found!")
        print("Make sure:")
        print("  1. Camera is connected via USB")
        print("  2. Spinnaker SDK is installed")
        print("  3. PySpin is installed (pip install spinnaker-python)")
        exit(1)

    print(f"\nFound {len(cameras)} camera(s):")
    for cam in cameras:
        print(f"  {cam['model']} (S/N: {cam['serial']})")

    # Test first camera
    print(f"\nTesting camera 0...")

    firefly_cam = RGBCameraFirefly(
        camera_index=0,
        resolution=(640, 480),
        fps=30,
        pixel_format="BGR8"
    )

    if not firefly_cam.open():
        print("Failed to open camera!")
        exit(1)

    print("Camera opened successfully. Press 'q' to quit.")

    frame_count = 0
    import time
    start_time = time.time()

    try:
        import cv2

        while True:
            ret, frame = firefly_cam.read()

            if not ret:
                print("Failed to read frame")
                break

            frame_count += 1

            # Calculate FPS
            if frame_count % 30 == 0:
                elapsed = time.time() - start_time
                fps = frame_count / elapsed
                print(f"FPS: {fps:.1f} (Global Shutter - No motion blur!)")

            # Display frame
            cv2.imshow("FLIR Firefly Test", frame)

            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                break

    except KeyboardInterrupt:
        print("\nInterrupted by user")
    except ImportError:
        print("\nOpenCV not available for display. Camera is working!")
        import time
        for i in range(100):
            ret, frame = firefly_cam.read()
            if ret:
                print(f"Frame {i+1}: {frame.shape}")
            time.sleep(0.033)
    finally:
        firefly_cam.release()
        try:
            cv2.destroyAllWindows()
        except:
            pass

    print("\nTest complete!")
