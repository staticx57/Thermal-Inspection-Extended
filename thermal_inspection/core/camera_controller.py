"""
Camera Controller for Thermal Inspection application.

Handles camera initialization, connection, and lifecycle management.
Extracted from ThermalInspectionFusion class in inspection_main.py.
"""

import logging
import threading
import time
from typing import Optional, Tuple, Callable, Dict, Any
from dataclasses import dataclass, field

import cv2
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class CameraState:
    """Current state of cameras."""
    thermal_connected: bool = False
    rgb_available: bool = False
    is_flir_boson: bool = False
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


class CameraController:
    """
    Manages camera initialization, connection, and lifecycle.

    This controller handles:
    - Camera auto-detection and connection
    - Thermal/RGB camera management
    - SDK connection for Boson cameras
    - Camera swapping and reassignment
    - Radiometric mode detection

    Usage:
        controller = CameraController(config)
        controller.on_state_change = my_callback
        thermal_ok, rgb_ok = controller.initialize_cameras()
    """

    def __init__(self, config: Optional[CameraConfig] = None):
        """
        Initialize CameraController.

        Args:
            config: Camera configuration. If None, uses defaults.
        """
        self.config = config or CameraConfig()
        self.state = CameraState()

        # Camera instances
        self.thermal_camera = None
        self.rgb_camera = None

        # Callbacks
        self.on_state_change: Optional[Callable[[CameraState], None]] = None
        self.on_sdk_connected: Optional[Callable[[Dict[str, Any]], None]] = None
        self.on_radiometric_detected: Optional[Callable[[bool], None]] = None

        # Import required modules (deferred to avoid circular imports)
        self._imports_loaded = False

    def _load_imports(self):
        """Load required imports on first use."""
        if self._imports_loaded:
            return

        # Camera modules
        global FLIRBosonCamera, FlirpyThermalBackend
        global create_rgb_camera, CameraDetector, CameraInitializer
        global create_thermal_backend, get_config
        global CameraError, CameraNotFoundError, CameraConnectionError
        global CameraTimeoutError, SDKError, SDKConnectionError, SDKTimeoutError

        from thermal_inspection.cameras.flir_camera import FLIRBosonCamera
        from thermal_inspection.sdk.flirpy_thermal_backend import FlirpyThermalBackend
        from thermal_inspection.cameras.camera_factory import create_rgb_camera
        from thermal_inspection.cameras.camera_detector import CameraDetector
        from thermal_inspection.cameras.camera_initializer import CameraInitializer
        from thermal_inspection.cameras.thermal_backend_factory import create_thermal_backend
        from thermal_inspection.utils.config import get_config
        from thermal_inspection.utils.exceptions import (
            CameraError, CameraNotFoundError, CameraConnectionError,
            CameraTimeoutError, SDKError, SDKConnectionError, SDKTimeoutError
        )

        self._imports_loaded = True

    def _notify_state_change(self):
        """Notify listeners of state change."""
        if self.on_state_change:
            self.on_state_change(self.state)

    def initialize_cameras(self) -> Tuple[bool, bool]:
        """
        Initialize cameras using robust detection with timeout protection.

        Returns:
            (thermal_success, rgb_success) tuple
        """
        self._load_imports()

        logger.info("=" * 70)
        logger.info("INITIALIZING CAMERAS (ROBUST MODE)")
        logger.info("=" * 70)

        # Get cached/config device IDs
        cfg = get_config()
        cached_thermal_id = cfg.get('thermal_device_id')
        cached_rgb_id = cfg.get('rgb_device_id')

        # Override with explicit config if present
        if self.config.thermal_device is not None:
            cached_thermal_id = self.config.thermal_device
        if self.config.rgb_device is not None:
            cached_rgb_id = self.config.rgb_device

        # Use robust initializer with thermal-first priority
        thermal_cam, rgb_cam = CameraInitializer.init_cameras_prioritized(
            thermal_first=True,
            enable_sdk=self.config.enable_boson_sdk,
            com_port=self.config.boson_com_port,
            known_thermal_id=cached_thermal_id,
            known_rgb_id=cached_rgb_id
        )

        # Handle thermal camera
        thermal_success = self._handle_thermal_camera(thermal_cam, cfg)

        # Handle RGB camera
        rgb_success = self._handle_rgb_camera(rgb_cam, cfg)

        self._notify_state_change()
        logger.info("=" * 70)
        return (thermal_success, rgb_success)

    def capture_frames(self) -> Tuple[Optional[np.ndarray], Optional[np.ndarray]]:
        """
        Capture frames from both cameras.
        
        Returns:
            (thermal_frame, rgb_frame) tuple
        """
        thermal_frame = None
        rgb_frame = None

        # Capture thermal
        if self.thermal_camera:
            try:
                # Some backends have read_thermal, others just read
                if hasattr(self.thermal_camera, 'read_thermal'):
                    success, thermal_frame = self.thermal_camera.read_thermal()
                else:
                    success, thermal_frame = self.thermal_camera.read()
                
                if not success:
                    thermal_frame = None
            except Exception as e:
                logger.error(f"Error capturing thermal frame: {e}")
                thermal_frame = None

        # Capture RGB
        if self.rgb_camera and not self.config.disable_rgb:
            try:
                success, rgb_frame = self.rgb_camera.read()
                if not success:
                    rgb_frame = None
            except Exception as e:
                logger.error(f"Error capturing RGB frame: {e}")
                rgb_frame = None

        return thermal_frame, rgb_frame

    def _handle_thermal_camera(self, thermal_cam, cfg) -> bool:
        """Handle thermal camera initialization result."""
        if not thermal_cam:
            logger.warning("Thermal camera initialization failed - using placeholder")
            return False

        self.thermal_camera = thermal_cam
        self.state.thermal_connected = True
        self.state.is_flir_boson = True

        # Persist device ID
        if hasattr(thermal_cam, 'device_id'):
            self.state.thermal_device_id = thermal_cam.device_id
            cfg.set('thermal_device_id', thermal_cam.device_id, save=True)
        elif hasattr(thermal_cam, 'device'):
            self.state.thermal_device_id = thermal_cam.device
            cfg.set('thermal_device_id', thermal_cam.device, save=True)
        else:
            self.state.thermal_device_id = self.config.thermal_device or 2

        logger.info(f"Persisted thermal device ID: {self.state.thermal_device_id}")

        # Check SDK status
        if hasattr(thermal_cam, 'is_sdk_connected') and thermal_cam.is_sdk_connected:
            self.state.sdk_connected = True
            self._handle_sdk_connected(thermal_cam)
        elif self.config.enable_boson_sdk:
            # Try auto-scan for SDK
            self._auto_scan_sdk(thermal_cam)

        # Auto-enable radiometric if available
        self._try_enable_radiometric(thermal_cam)

        return True

    def _handle_sdk_connected(self, thermal_cam):
        """Handle SDK connection success."""
        logger.info("=" * 60)
        logger.info("[OK] Boson SDK connected - serial control enabled")
        info = thermal_cam.get_camera_info()
        if info:
            logger.info(f"  Camera SN: {info.serial_number}")
        logger.info("=" * 60)

        # Notify callback
        if self.on_sdk_connected and info:
            self.on_sdk_connected({
                'serial_number': info.serial_number,
                'camera_part_number': getattr(info, 'camera_part_number', None),
                'software_version': getattr(info, 'software_version', None),
                'gain_mode': getattr(info, 'gain_mode', None)
            })

    def _auto_scan_sdk(self, thermal_cam):
        """Auto-scan for Boson SDK on available COM ports."""
        logger.warning(f"SDK failed to connect on default port {self.config.boson_com_port}, attempting auto-scan...")

        try:
            available_ports = self.scan_com_ports()
            for port in available_ports:
                if port == self.config.boson_com_port:
                    continue  # Skip already failed port

                logger.info(f"Trying SDK connection on {port}...")
                if hasattr(thermal_cam, 'connect_sdk') and thermal_cam.connect_sdk(port):
                    logger.info(f"[OK] Found Boson SDK on {port}!")
                    self.config.boson_com_port = port
                    self.state.sdk_connected = True

                    info = thermal_cam.get_camera_info()
                    if info:
                        logger.info(f"  Camera SN: {info.serial_number}")
                    break
                else:
                    logger.debug(f"Failed on {port}")
        except Exception as e:
            logger.debug(f"SDK auto-scan failed: {e}")

    def _try_enable_radiometric(self, thermal_cam):
        """Try to auto-enable radiometric mode."""
        if hasattr(thermal_cam, 'enable_radiometric_mode'):
            try:
                if thermal_cam.enable_radiometric_mode():
                    logger.info("Auto-enabled radiometric mode")
            except Exception as e:
                logger.debug(f"Radiometric mode not available: {e}")

    def _handle_rgb_camera(self, rgb_cam, cfg) -> bool:
        """Handle RGB camera initialization result."""
        if self.config.disable_rgb:
            return False

        if not rgb_cam:
            logger.warning("RGB camera initialization failed - thermal-only mode")
            return False

        self.rgb_camera = rgb_cam
        self.state.rgb_available = True

        # Persist RGB info
        if hasattr(rgb_cam, 'device_id'):
            self.state.rgb_device_id = rgb_cam.device_id
            if getattr(rgb_cam, 'camera_type', '') != 'firefly':
                cfg.set('rgb_device_id', rgb_cam.device_id, save=True)
        elif hasattr(rgb_cam, 'device'):
            self.state.rgb_device_id = rgb_cam.device
            cfg.set('rgb_device_id', rgb_cam.device, save=True)

        self.state.rgb_camera_source = getattr(rgb_cam, 'camera_source', 'uvc')
        logger.info(f"Persisted RGB device ID: {self.state.rgb_device_id}, Source: {self.state.rgb_camera_source}")

        return True

    def detect_radiometric_mode(self) -> bool:
        """
        Detect if camera is providing radiometric data (T-Linear).

        Returns:
            True if radiometric mode detected, False otherwise
        """
        if not self.thermal_camera:
            return False

        logger.info("Detecting camera mode...")

        # Grab frames to settle
        for _ in range(5):
            if hasattr(self.thermal_camera, 'read_thermal'):
                self.thermal_camera.read_thermal()
            else:
                self.thermal_camera.read()

        # Read frame for analysis
        if hasattr(self.thermal_camera, 'read_thermal'):
            success, frame = self.thermal_camera.read_thermal()
        else:
            success, frame = self.thermal_camera.read()

        if not success or frame is None:
            logger.warning("Could not grab frame for mode detection")
            return False

        # Check median value - T-Linear values are typically > 10000
        median_val = np.median(frame)
        logger.info(f"Median pixel value: {median_val:.1f}")

        is_radiometric = median_val > 10000
        self.state.is_radiometric = is_radiometric

        if is_radiometric:
            logger.info(f"[DETECTED] Radiometric Mode (T-Linear) - median {median_val:.0f} > 10000")
        else:
            logger.info(f"[DETECTED] Non-Radiometric Mode (Raw/AGC) - median {median_val:.0f} <= 10000")

        if self.on_radiometric_detected:
            self.on_radiometric_detected(is_radiometric)

        return is_radiometric

    def swap_cameras(self) -> bool:
        """
        Swap RGB and Thermal camera sources.

        Returns:
            True if swap initiated successfully
        """
        logger.info("Swapping camera sources...")

        current_thermal = self.state.thermal_device_id or 0
        current_rgb = self.state.rgb_device_id

        if current_rgb is None:
            current_rgb = 1 if current_thermal == 0 else 0

        # Swap
        new_thermal = current_rgb
        new_rgb = current_thermal

        # Run in separate thread to avoid blocking
        threading.Thread(
            target=self.reassign_cameras,
            args=(new_thermal, new_rgb),
            daemon=True
        ).start()

        return True

    def reassign_cameras(self, thermal_id: int, rgb_id: int) -> bool:
        """
        Reassign camera device IDs.

        Args:
            thermal_id: New thermal camera device ID
            rgb_id: New RGB camera device ID

        Returns:
            True if successful
        """
        if self.state.reconfiguring:
            logger.warning("Already reconfiguring cameras...")
            return False

        self.state.reconfiguring = True
        logger.info(f"Reassigning cameras: Thermal={thermal_id}, RGB={rgb_id}")

        try:
            # Update config
            self.config.thermal_device = thermal_id
            self.config.rgb_device = rgb_id

            # Release current cameras
            self.release_cameras()

            # Force OpenCV to release resources
            cv2.waitKey(1)
            cv2.destroyAllWindows()
            cv2.waitKey(1)

            # Wait for OS to release resources
            logger.info("Waiting for OS to release camera resources...")
            time.sleep(2.0)

            # Reinitialize
            thermal_ok, rgb_ok = self.initialize_cameras()

            if thermal_ok or rgb_ok:
                logger.info("[OK] Camera reassignment complete")
            else:
                logger.error("[ERROR] No cameras connected after reassignment")

            return thermal_ok or rgb_ok

        except Exception as e:
            logger.error(f"Error reassigning cameras: {e}")
            import traceback
            traceback.print_exc()
            return False

        finally:
            self.state.reconfiguring = False
            self._notify_state_change()

    def release_cameras(self):
        """Release all camera resources."""
        if self.thermal_camera:
            logger.info("Releasing thermal camera...")
            if hasattr(self.thermal_camera, 'release'):
                self.thermal_camera.release()
            elif hasattr(self.thermal_camera, 'close'):
                self.thermal_camera.close()
            self.thermal_camera = None
            self.state.thermal_connected = False
            self.state.is_flir_boson = False

        if self.rgb_camera:
            logger.info("Releasing RGB camera...")
            if hasattr(self.rgb_camera, 'release'):
                self.rgb_camera.release()
            elif hasattr(self.rgb_camera, 'close'):
                self.rgb_camera.close()
            self.rgb_camera = None
            self.state.rgb_available = False

    def scan_com_ports(self) -> list:
        """
        Scan for available COM ports.

        Returns:
            List of available COM port names
        """
        try:
            import serial.tools.list_ports

            ports = []
            for port in serial.tools.list_ports.comports():
                ports.append(port.device)
                logger.debug(f"Found COM port: {port.device} - {port.description}")

            logger.info(f"Scanned {len(ports)} COM ports")
            return ports

        except ImportError:
            logger.error("pyserial not installed - cannot scan COM ports")
            return []
        except Exception as e:
            logger.error(f"Error scanning COM ports: {e}")
            return []

    def get_thermal_resolution(self) -> Optional[Tuple[int, int]]:
        """Get current thermal camera resolution."""
        if self.thermal_camera and hasattr(self.thermal_camera, 'get_actual_resolution'):
            return self.thermal_camera.get_actual_resolution()
        return None

    def get_rgb_resolution(self) -> Optional[Tuple[int, int]]:
        """Get current RGB camera resolution."""
        if self.rgb_camera and hasattr(self.rgb_camera, 'get_actual_resolution'):
            return self.rgb_camera.get_actual_resolution()
        return None

    @property
    def has_thermal(self) -> bool:
        """Check if thermal camera is connected."""
        return self.state.thermal_connected and self.thermal_camera is not None

    @property
    def has_rgb(self) -> bool:
        """Check if RGB camera is available."""
        return self.state.rgb_available and self.rgb_camera is not None

    @property
    def has_sdk(self) -> bool:
        """Check if Boson SDK is connected."""
        return self.state.sdk_connected
