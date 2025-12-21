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
from typing import Optional, Tuple, Callable, List
from dataclasses import dataclass
import concurrent.futures

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
            logger.info(f"[OK] {camera_name} initialized successfully ({elapsed:.2f}s)")
            return CameraInitResult(
                success=True,
                camera_object=result_container['camera'],
                error_message=None,
                init_time_seconds=elapsed
            )
        else:
            error = result_container.get('error', 'Unknown error')
            logger.error(f"[FAIL] {camera_name} initialization failed: {error}")
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
            from thermal_inspection.cameras.flir_camera import FLIRBosonCamera

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
            from thermal_inspection.cameras.rgb_camera_firefly import RGBCameraFirefly

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
            from thermal_inspection.cameras.rgb_camera_uvc import RGBCameraUVC

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
    def init_cameras_prioritized(thermal_first: bool = True, enable_sdk: bool = False, com_port: str = 'COM6',
                                known_thermal_id: Optional[int] = None, known_rgb_id: Optional[int] = None) -> Tuple[Optional[object], Optional[object]]:
        """
        Initialize both cameras with priority order using a SINGLE detection scan (or "Fast Path").
        
        Optimization:
        - FAST PATH: If known IDs are provided, attempts to open them directly in PARALLEL (skips detection).
        - FALLBACK: If Fast Path fails, scans all cameras once.
        - PARALLEL INIT: Always initializes Thermal and RGB in parallel threads to save time.
        - Respects priority: Boson > Generic | Firefly > UVC > Built-in

        Args:
            thermal_first: (Deprecated in parallel mode) Valid for sequential fallback only
            enable_sdk: Enable Boson SDK for thermal camera
            com_port: COM port for Boson SDK
            known_thermal_id: Previously known thermal device ID (Fast Path)
            known_rgb_id: Previously known RGB device ID (Fast Path)

        Returns:
            (thermal_camera, rgb_camera) tuple (either can be None if failed)
        """
        from thermal_inspection.cameras.camera_detector import CameraDetector

        logger.info("="*70)
        logger.info("PRIORITIZED CAMERA INITIALIZATION (OPTIMIZED)")
        logger.info("="*70)
        logger.info(f"SDK enabled: {enable_sdk}, COM port: {com_port}")

        thermal_camera = None
        rgb_camera = None
        
        # Helper to initialize thermal
        def init_thermal_task(dev_id, res=(640, 512)):
            return CameraInitializer.init_thermal_camera_safe(
                device_id=dev_id,
                resolution=res,
                enable_sdk=enable_sdk,
                com_port=com_port,
                timeout=8.0
            )

        # Helper to initialize RGB
        def init_rgb_task(dev_info_or_id, res=(0,0)):
            if hasattr(dev_info_or_id, 'interface') and dev_info_or_id.interface == 'spinnaker':
                 return CameraInitializer.init_firefly_camera_safe(
                    camera_index=dev_info_or_id.spinnaker_index,
                    resolution=(0, 0),
                    timeout=15.0
                )
            else:
                # It's an ID or info object
                d_id = dev_info_or_id.device_id if hasattr(dev_info_or_id, 'device_id') else dev_info_or_id
                
                # If we have a resolution hint (from detection or fast path?), use it
                # For fast path, we might default to 4K or 0,0 (auto)
                return CameraInitializer.init_uvc_camera_safe(
                    device_id=d_id,
                    resolution=res,
                    timeout=8.0 # Reduced timeout for parallel
                )

        # ==================================================================================
        # 1. FAST PATH: RAM-cached or Config-cached IDs
        # ==================================================================================
        if known_thermal_id is not None or known_rgb_id is not None:
            logger.info(f"Attempting Fast Path Init (Thermal={known_thermal_id}, RGB={known_rgb_id})")
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
                futures = {}
                
                if known_thermal_id is not None:
                    futures['thermal'] = executor.submit(init_thermal_task, known_thermal_id)
                
                if known_rgb_id is not None:
                     # Check conflict
                    if known_thermal_id is not None and known_thermal_id == known_rgb_id:
                        logger.warning("Fast Path: Skipping RGB, ID matches Thermal")
                    else:
                        # We don't know the resolution, but passing (0,0) will trigger negotiation
                        # OR if we persisted resolution we could use it. For now, 0,0 is okay or we can assume 4K?
                        # Let's use (0,0) and accept the 1.5s hit, OR we can try to guess.
                        # Actually, if we accepted the 1.5s hit, we are still faster than 4s scan.
                        # But wait, we can pass a 'hint' if we had one.
                        # For now, (0,0) is safe.
                        futures['rgb'] = executor.submit(init_rgb_task, known_rgb_id, (0,0))
                
                # Wait for results
                for key, future in futures.items():
                    try:
                        result = future.result()
                        if result.success:
                            if key == 'thermal':
                                thermal_camera = result.camera_object
                                logger.info(f"  [FAST-OK] Thermal (ID {known_thermal_id}) initialized")
                            else:
                                rgb_camera = result.camera_object
                                logger.info(f"  [FAST-OK] RGB (ID {known_rgb_id}) initialized")
                    except Exception as e:
                        logger.error(f"  [FAST-FAIL] {key} init error: {e}")

            # Verification: Did we get what we wanted?
            # CRITICAL FIX: Always try to find RGB camera if it wasn't initialized
            # Fall back to full detection if:
            # 1. Thermal was requested but failed, OR
            # 2. RGB is None (either not requested OR failed)
            # This ensures we always detect RGB cameras even if uncached
            thermal_missing = known_thermal_id is not None and thermal_camera is None
            
            if thermal_missing:
                logger.warning("Fast Path: Thermal not initialized (ID provided but init failed). Reverting to Full Detection.")
                if rgb_camera: 
                    try: rgb_camera.release()
                    except: pass
                    rgb_camera = None
                # Fallback proceeds below to Full Detection
            elif rgb_camera is None:
                # RGB not initialized - could be because:
                # 1. known_rgb_id was None (uncached)
                # 2. known_rgb_id was provided but init failed
                # In either case, run full detection to find RGB
                logger.info("Fast Path: RGB not initialized. Running Full Detection to find RGB camera.")
                # Keep thermal camera, but re-run detection to find RGB
                # Fallback proceeds below to Full Detection
            else:
                # Fast Path Success!
                logger.info("="*70)
                return (thermal_camera, rgb_camera)

        # ==================================================================================
        # 2. FULL DETECTION FALLBACK
        # ==================================================================================
        logger.info("Start Full Camera Detection...")
        all_cameras = CameraDetector.detect_all_cameras()
        time.sleep(0.5) # Settle

        thermal_candidates = [c for c in all_cameras if c.is_thermal()]
        rgb_candidates = [c for c in all_cameras if c.is_rgb()]
        
        best_thermal_info = thermal_candidates[0] if thermal_candidates else None
        best_rgb_info = rgb_candidates[0] if rgb_candidates else None
        
        if best_thermal_info:
            logger.info(f"Selected Thermal: {best_thermal_info.name}")
        if best_rgb_info:
             logger.info(f"Selected RGB: {best_rgb_info.name}")

        # ==================================================================================
        # 3. PARALLEL INITIALIZATION (Fallback)
        # ==================================================================================
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            futures = {}
            
            if best_thermal_info:
                futures['thermal'] = executor.submit(init_thermal_task, best_thermal_info.device_id, best_thermal_info.resolution)
                
            if best_rgb_info:
                 # Check conflict
                if best_thermal_info and best_rgb_info.interface != 'spinnaker' and best_rgb_info.device_id == best_thermal_info.device_id:
                     logger.warning(f"Skipping RGB init: Device {best_rgb_info.device_id} conflict")
                else:
                    futures['rgb'] = executor.submit(init_rgb_task, best_rgb_info, best_rgb_info.resolution)
            
            # Wait for results
            for key, future in futures.items():
                try:
                    result = future.result()
                    if result.success:
                        if key == 'thermal':
                            thermal_camera = result.camera_object
                            logger.info(f"  [OK] Thermal initialized ({result.init_time_seconds:.2f}s)")
                        else:
                            rgb_camera = result.camera_object
                            logger.info(f"  [OK] RGB initialized ({result.init_time_seconds:.2f}s)")
                    else:
                        logger.warning(f"  [FAIL] {key} failed: {result.error_message}")
                except Exception as e:
                    logger.error(f"  [FAIL] {key} exception: {e}")

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
