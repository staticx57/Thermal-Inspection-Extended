"""
Robust Camera Initialization with Timeout and Priority Handling

Handles issues like:
- Cameras that hang during initialization
- Cameras already in use
- Failed camera initialization without blocking the app
"""

import threading
import time
import logging
from typing import Optional, Tuple, Callable
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class CameraInitResult:
    """Result of camera initialization attempt"""
    success: bool
    camera_object: Optional[object] = None
    error_message: Optional[str] = None
    init_time_seconds: float = 0.0


class CameraInitializer:
    """
    Thread-safe camera initializer with timeout support
    """

    @staticmethod
    def init_with_timeout(init_func: Callable, timeout_seconds: float = 10.0,
                         camera_name: str = "Camera") -> CameraInitResult:
        """
        Initialize a camera with timeout protection

        Args:
            init_func: Function that initializes and returns camera object (should return (success, camera))
            timeout_seconds: Maximum time to wait for initialization
            camera_name: Name for logging

        Returns:
            CameraInitResult with success status and camera object
        """
        result_container = {}
        start_time = time.time()

        def init_thread():
            """Thread function to run camera initialization"""
            try:
                success, camera = init_func()
                result_container['success'] = success
                result_container['camera'] = camera
                result_container['error'] = None
            except Exception as e:
                logger.error(f"Exception in {camera_name} initialization: {e}")
                result_container['success'] = False
                result_container['camera'] = None
                result_container['error'] = str(e)

        # Start initialization in separate thread
        logger.info(f"Initializing {camera_name} (timeout: {timeout_seconds}s)...")
        thread = threading.Thread(target=init_thread, daemon=True)
        thread.start()

        # Wait for thread with timeout
        thread.join(timeout=timeout_seconds)
        elapsed = time.time() - start_time

        # Check if thread completed
        if thread.is_alive():
            # Timeout occurred
            logger.error(f"{camera_name} initialization TIMEOUT after {timeout_seconds}s")
            logger.warning(f"  Thread still running - camera may be hung or in use")
            return CameraInitResult(
                success=False,
                camera_object=None,
                error_message=f"Initialization timeout after {timeout_seconds}s",
                init_time_seconds=elapsed
            )

        # Thread completed - check result
        if result_container.get('success', False):
            logger.info(f"✓ {camera_name} initialized successfully ({elapsed:.2f}s)")
            return CameraInitResult(
                success=True,
                camera_object=result_container['camera'],
                error_message=None,
                init_time_seconds=elapsed
            )
        else:
            error = result_container.get('error', 'Unknown error')
            logger.error(f"✗ {camera_name} initialization failed: {error}")
            return CameraInitResult(
                success=False,
                camera_object=None,
                error_message=error,
                init_time_seconds=elapsed
            )

    @staticmethod
    def init_thermal_camera_safe(device_id: int = 0, resolution: Tuple[int, int] = (640, 512),
                                enable_sdk: bool = False, com_port: str = 'COM6',
                                timeout: float = 10.0) -> CameraInitResult:
        """
        Safely initialize thermal camera with timeout

        Args:
            device_id: Camera device ID
            resolution: Camera resolution
            enable_sdk: Enable Boson SDK
            com_port: COM port for SDK
            timeout: Initialization timeout in seconds

        Returns:
            CameraInitResult
        """
        def init_func():
            from flir_camera import FLIRBosonCamera

            thermal_cam = FLIRBosonCamera(
                device_id=device_id,
                resolution=resolution,
                enable_sdk=enable_sdk,
                com_port=com_port
            )

            success = thermal_cam.open()
            return (success, thermal_cam if success else None)

        return CameraInitializer.init_with_timeout(
            init_func,
            timeout_seconds=timeout,
            camera_name=f"Thermal Camera (device {device_id})"
        )

    @staticmethod
    def init_firefly_camera_safe(camera_index: int = 0,
                                resolution: Tuple[int, int] = (0, 0),
                                fps: int = 30,
                                timeout: float = 15.0) -> CameraInitResult:
        """
        Safely initialize Firefly camera with timeout

        Firefly cameras can sometimes hang during initialization,
        especially if they were not properly released.

        Args:
            camera_index: Spinnaker camera index
            resolution: Desired resolution (0,0 for max)
            fps: Frame rate
            timeout: Initialization timeout in seconds (default 15s)

        Returns:
            CameraInitResult
        """
        def init_func():
            from rgb_camera_firefly import RGBCameraFirefly

            firefly_cam = RGBCameraFirefly(
                camera_index=camera_index,
                resolution=resolution,
                fps=fps,
                pixel_format="BGR8"
            )

            success = firefly_cam.open()
            return (success, firefly_cam if success else None)

        return CameraInitializer.init_with_timeout(
            init_func,
            timeout_seconds=timeout,
            camera_name=f"Firefly Camera (index {camera_index})"
        )

    @staticmethod
    def init_uvc_camera_safe(device_id: int = 1,
                            resolution: Tuple[int, int] = (0, 0),
                            fps: int = 30,
                            timeout: float = 10.0) -> CameraInitResult:
        """
        Safely initialize UVC camera with timeout

        Args:
            device_id: Camera device ID
            resolution: Desired resolution (0,0 for max)
            fps: Frame rate
            timeout: Initialization timeout in seconds

        Returns:
            CameraInitResult
        """
        def init_func():
            from rgb_camera_uvc import RGBCameraUVC

            uvc_cam = RGBCameraUVC(
                device_id=device_id,
                resolution=resolution,
                fps=fps
            )

            success = uvc_cam.open()
            return (success, uvc_cam if success else None)

        return CameraInitializer.init_with_timeout(
            init_func,
            timeout_seconds=timeout,
            camera_name=f"UVC Camera (device {device_id})"
        )

    @staticmethod
    def init_cameras_prioritized(thermal_first: bool = True, enable_sdk: bool = False, com_port: str = 'COM6') -> Tuple[Optional[object], Optional[object]]:
        """
        Initialize both cameras with priority order

        Args:
            thermal_first: If True, initialize thermal first (recommended for inspection apps)
                          If False, initialize RGB first
            enable_sdk: Enable Boson SDK for thermal camera
            com_port: COM port for Boson SDK

        Returns:
            (thermal_camera, rgb_camera) tuple (either can be None if failed)
        """
        from camera_detector import CameraDetector

        logger.info("="*70)
        logger.info("PRIORITIZED CAMERA INITIALIZATION")
        logger.info("="*70)
        logger.info(f"SDK enabled: {enable_sdk}, COM port: {com_port}")

        # Detect cameras first
        thermal_info = CameraDetector.find_thermal_camera()
        rgb_info = CameraDetector.find_rgb_camera()

        thermal_camera = None
        rgb_camera = None

        if thermal_first:
            # Initialize thermal first (priority)
            if thermal_info:
                result = CameraInitializer.init_thermal_camera_safe(
                    device_id=thermal_info.device_id,
                    resolution=thermal_info.resolution,
                    enable_sdk=enable_sdk,
                    com_port=com_port,
                    timeout=10.0
                )
                if result.success:
                    thermal_camera = result.camera_object
                    logger.info(f"  ✓ Thermal initialized ({result.init_time_seconds:.2f}s)")
                else:
                    logger.warning(f"  ✗ Thermal failed: {result.error_message}")

            # Small delay between cameras
            time.sleep(0.5)

            # Initialize RGB second
            if rgb_info:
                # Check for conflict with thermal camera
                conflict = False
                if thermal_camera and hasattr(thermal_camera, 'device_id'):
                    # Check if RGB camera uses the same device ID
                    if rgb_info.interface != 'spinnaker' and rgb_info.device_id == thermal_camera.device_id:
                        logger.warning(f"Skipping RGB init: Device {rgb_info.device_id} already used by thermal camera")
                        conflict = True
                
                if not conflict:
                    if rgb_info.interface == 'spinnaker':
                        result = CameraInitializer.init_firefly_camera_safe(
                            camera_index=rgb_info.spinnaker_index,
                            resolution=(0, 0),  # Max resolution
                            timeout=15.0
                        )
                    else:
                        result = CameraInitializer.init_uvc_camera_safe(
                            device_id=rgb_info.device_id,
                            resolution=(0, 0),  # Max resolution
                            timeout=10.0
                        )

                    if result.success:
                        rgb_camera = result.camera_object
                        logger.info(f"  ✓ RGB initialized ({result.init_time_seconds:.2f}s)")
                    else:
                        logger.warning(f"  ✗ RGB failed: {result.error_message}")

        else:
            # Initialize RGB first
            if rgb_info:
                if rgb_info.interface == 'spinnaker':
                    result = CameraInitializer.init_firefly_camera_safe(
                        camera_index=rgb_info.spinnaker_index,
                        resolution=(0, 0),
                        timeout=15.0
                    )
                else:
                    result = CameraInitializer.init_uvc_camera_safe(
                        device_id=rgb_info.device_id,
                        resolution=(0, 0),
                        timeout=10.0
                    )

                if result.success:
                    rgb_camera = result.camera_object
                    logger.info(f"  ✓ RGB initialized ({result.init_time_seconds:.2f}s)")

            time.sleep(0.5)

            # Initialize thermal second
            if thermal_info:
                result = CameraInitializer.init_thermal_camera_safe(
                    device_id=thermal_info.device_id,
                    resolution=thermal_info.resolution,
                    enable_sdk=enable_sdk,
                    com_port=com_port,
                    timeout=10.0
                )
                if result.success:
                    thermal_camera = result.camera_object
                    logger.info(f"  ✓ Thermal initialized ({result.init_time_seconds:.2f}s)")

        logger.info("="*70)
        return (thermal_camera, rgb_camera)


if __name__ == "__main__":
    """Test camera initializer"""
    logging.basicConfig(level=logging.INFO)

    print("\n" + "="*70)
    print("CAMERA INITIALIZER TEST")
    print("="*70)

    # Test: Initialize cameras with thermal first
    thermal, rgb = CameraInitializer.init_cameras_prioritized(thermal_first=True)

    print("\nResults:")
    print(f"  Thermal: {'[OK]' if thermal else '[FAILED]'}")
    print(f"  RGB: {'[OK]' if rgb else '[FAILED]'}")

    # Clean up
    if thermal:
        thermal.release()
    if rgb:
        rgb.release()

    print("\nDone!")
