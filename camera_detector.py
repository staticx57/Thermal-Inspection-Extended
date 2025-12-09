"""
Camera Detection Utility
Automatically detect and identify thermal and RGB cameras with proper prioritization

THERMAL CAMERA PRIORITY:
1. FLIR Boson (via Spinnaker SDK or UVC) - 640x512 or 320x256
2. Generic USB UVC thermal cameras - low saturation, grayscale

RGB CAMERA PRIORITY:
1. FLIR Firefly (via Spinnaker SDK) - Global shutter, best quality
2. External USB UVC cameras
3. Built-in laptop webcams
"""
import cv2
import subprocess
import re
import logging
import platform
import time
import numpy as np
from typing import List, Dict, Optional, Tuple
from enum import Enum
from pathlib import Path

# Import camera registry for tracking camera roles
from camera_registry import get_camera_registry, CameraRole

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Try importing Spinnaker/PySpin for FLIR Firefly
try:
    import PySpin
    PYSPIN_AVAILABLE = True
except ImportError:
    PYSPIN_AVAILABLE = False
    logger.debug("PySpin not available - Firefly detection disabled")

# FLIR Systems vendor ID
FLIR_USB_VENDOR_ID = "09CB"


class CameraType(Enum):
    """Camera type classification"""
    THERMAL = "Thermal"
    RGB = "RGB"
    UNKNOWN = "Unknown"


class CameraInfo:
    """Information about a detected camera"""

    def __init__(self, device_id: int, name: str, driver: str, resolution: tuple,
                 interface: str = "opencv", serial: Optional[str] = None,
                 spinnaker_index: Optional[int] = None):
        """
        Args:
            device_id: OpenCV VideoCapture device ID (for UVC cameras)
            name: Camera model/name
            driver: Driver name (v4l2, DSHOW, MSMF, spinnaker)
            resolution: (width, height) tuple
            interface: 'opencv' or 'spinnaker'
            serial: Serial number (for Spinnaker cameras)
            spinnaker_index: Spinnaker camera index (if using PySpin)
        """
        self.device_id = device_id
        self.name = name
        self.driver = driver
        self.resolution = resolution
        self.interface = interface
        self.serial = serial
        self.spinnaker_index = spinnaker_index
        self.is_flir = 'flir' in name.lower() or 'boson' in name.lower()
        self.camera_type = self._detect_camera_type()
        self.priority = self._calculate_priority()

    def _detect_camera_type(self) -> CameraType:
        """
        Detect camera type based on resolution, name, and interface

        Returns:
            CameraType enum
        """
        # FLIR Boson thermal camera resolutions (HIGHEST PRIORITY)
        thermal_resolutions = [
            (640, 512),  # Boson 640
            (320, 256),  # Boson 320
            (512, 640),  # Boson 640 (rotated)
            (256, 320),  # Boson 320 (rotated)
        ]

        # Check resolution with fuzzy matching (DirectShow may report ±10 pixels)
        def is_near_thermal_res(res, tolerance=10):
            for thermal_res in thermal_resolutions:
                if (abs(res[0] - thermal_res[0]) <= tolerance and 
                    abs(res[1] - thermal_res[1]) <= tolerance):
                    return True
            return False
        
        if self.resolution in thermal_resolutions or is_near_thermal_res(self.resolution):
            return CameraType.THERMAL

        # Check name for thermal keywords
        thermal_keywords = ['boson', 'thermal', 'radiometric', 'lwir', 'tau']
        name_lower = self.name.lower()
        if any(keyword in name_lower for keyword in thermal_keywords):
            return CameraType.THERMAL

        # Firefly is RGB (global shutter camera)
        if 'firefly' in name_lower or 'blackfly' in name_lower:
            return CameraType.RGB

        # Generic FLIR cameras via Spinnaker are usually RGB (Firefly/Blackfly)
        # UNLESS they have thermal resolution or keywords
        if self.interface == 'spinnaker':
            return CameraType.RGB

        # RGB camera indicators
        rgb_keywords = ['rgb', 'webcam', 'usb', 'hd', 'color', 'camera']
        if any(keyword in name_lower for keyword in rgb_keywords):
            return CameraType.RGB

        # Common RGB resolutions (HD, FHD, 4K, etc.)
        common_rgb_resolutions = [
            (640, 480),   # VGA
            (1280, 720),  # HD
            (1920, 1080), # Full HD
            (3840, 2160), # 4K
            (2592, 1944), # 5MP
        ]
        if self.resolution in common_rgb_resolutions:
            return CameraType.RGB

        # Unknown type
        return CameraType.UNKNOWN

    def _calculate_priority(self) -> int:
        """
        Calculate camera priority for selection

        IMPORTANT: Thermal and RGB cameras are graded SEPARATELY with COEQUAL importance.
        Priorities are separate within each category.

        THERMAL PRIORITY (0-99):
        0: FLIR Boson (via any interface)
        1: Generic thermal (low saturation, thermal res)

        RGB PRIORITY (0-99):
        0: FLIR Firefly (Spinnaker SDK) - Global shutter, best
        1: External USB UVC camera
        2: Built-in laptop webcam

        Lower number = higher priority WITHIN ITS CATEGORY

        Returns:
            Priority value (int) - only meaningful within camera type
        """
        name_lower = self.name.lower()
        width, height = self.resolution

        # THERMAL CAMERAS (graded separately)
        if self.camera_type == CameraType.THERMAL:
            if 'boson' in name_lower:
                return 0  # Highest thermal priority
            return 1  # Generic thermal

        # RGB CAMERAS (graded separately)
        if self.camera_type == CameraType.RGB:
            # Firefly/Blackfly via Spinnaker = highest RGB priority
            if self.interface == 'spinnaker':
                return 0  # Highest RGB priority

            # High Resolution (4K/1080p) = High Priority
            # This ensures external 4K cams beat internal 720p webcams
            if width >= 1920 or height >= 1080:
                logger.info(f"Assigning Priority 0 to High-Res RGB: {self.name} ({width}x{height})")
                return 1  # Priority 1 (just below Firefly)

            # External USB camera heuristic (Standard Def)
            # Device 0 with VGA (640x480) is likely built-in on laptops
            if self.device_id == 0 and width <= 640:
                return 3  # Built-in laptop webcam (Low priority)

            # Standard external USB
            return 2  # Standard external UVC

        # Unknown type
        return 999

    def is_thermal(self) -> bool:
        """Check if this camera is a thermal camera"""
        return self.camera_type == CameraType.THERMAL

    def is_rgb(self) -> bool:
        """Check if this camera is an RGB camera"""
        return self.camera_type == CameraType.RGB

    def __str__(self):
        type_str = f" [{self.camera_type.value}]"
        return f"[{self.device_id}] {self.name} ({self.resolution[0]}x{self.resolution[1]}){type_str}"


class CameraDetector:
    """Detect and identify connected cameras"""

    @staticmethod
    def detect_all_cameras(skip_device_ids: Optional[List[int]] = None, register_cameras: bool = True) -> List[CameraInfo]:
        """
        Detect all available cameras (cross-platform: Linux/Windows/macOS)

        Detection order:
        1. Spinnaker cameras (FLIR Firefly RGB, possibly Boson thermal)
        2. UVC cameras (thermal Boson, generic USB, built-in webcams)

        Args:
            skip_device_ids: List of device IDs to skip during detection (already in use)
            register_cameras: Whether to register detected cameras with the registry (default: True)

        Returns:
            List of CameraInfo objects sorted by priority
        """
        import platform
        cameras = []
        system = platform.system()

        if skip_device_ids is None:
            skip_device_ids = []

        logger.info("="*70)
        logger.info("COMPREHENSIVE CAMERA DETECTION")
        logger.info("="*70)

        # STEP 1: Detect Spinnaker cameras (FLIR Firefly RGB only)
        # Note: Boson thermal uses its own SDK or UVC, NOT Spinnaker
        spinnaker_cameras = CameraDetector._detect_spinnaker_cameras()
        cameras.extend(spinnaker_cameras)

        # STEP 2: Detect UVC cameras (Boson thermal, generic USB, built-in)
        if system == "Linux":
            # Try v4l2-ctl first (Linux)
            v4l2_cameras = CameraDetector._detect_v4l2(skip_device_ids=skip_device_ids)
            if v4l2_cameras:
                cameras.extend(v4l2_cameras)
            else:
                # Fallback: probe video devices directly
                uvc_cameras = CameraDetector._probe_video_devices(skip_device_ids=skip_device_ids)
                cameras.extend(uvc_cameras)
        elif system == "Windows":
            # Windows: probe cameras using DirectShow/MSMF
            uvc_cameras = CameraDetector._probe_windows_cameras(skip_device_ids=skip_device_ids)
            cameras.extend(uvc_cameras)
        else:
            # macOS or other: probe using default backend
            uvc_cameras = CameraDetector._probe_video_devices(skip_device_ids=skip_device_ids)
            cameras.extend(uvc_cameras)

        # STEP 3: Sort cameras by priority (lower = better)
        cameras.sort(key=lambda cam: cam.priority)

        # STEP 4: Print detection summary
        CameraDetector._print_detection_summary(cameras)

        # STEP 5: Register cameras with the registry if requested
        if register_cameras:
            registry = get_camera_registry()
            for cam in cameras:
                # Convert CameraType to CameraRole
                if cam.is_thermal():
                    detected_role = CameraRole.THERMAL
                elif cam.is_rgb():
                    detected_role = CameraRole.RGB
                else:
                    detected_role = CameraRole.UNASSIGNED

                # Register camera with registry
                registry.register_camera(
                    device_id=cam.device_id,
                    name=cam.name,
                    resolution=cam.resolution,
                    driver=cam.driver,
                    detected_role=detected_role
                )

        return cameras

    @staticmethod
    def _detect_spinnaker_cameras() -> List[CameraInfo]:
        """
        Detect FLIR cameras via Spinnaker SDK (Firefly RGB)

        Note: Boson thermal cameras do NOT use Spinnaker

        Returns:
            List of CameraInfo for Spinnaker cameras
        """
        if not PYSPIN_AVAILABLE:
            logger.info("[STEP 1] Spinnaker: Not available (PySpin not installed)")
            return []

        logger.info("[STEP 1] Scanning for Spinnaker cameras (Firefly RGB)...")

        cameras = []
        system = None
        cam_list = None

        try:
            system = PySpin.System.GetInstance()
            cam_list = system.GetCameras()
            num_cameras = cam_list.GetSize()

            logger.info(f"  Found {num_cameras} Spinnaker camera(s)")

            for i in range(num_cameras):
                try:
                    cam = cam_list.GetByIndex(i)
                    nodemap_tldevice = cam.GetTLDeviceNodeMap()

                    # Get model name
                    node_model = PySpin.CStringPtr(nodemap_tldevice.GetNode('DeviceModelName'))
                    model = node_model.GetValue() if PySpin.IsReadable(node_model) else "Unknown"

                    # Get serial number
                    node_serial = PySpin.CStringPtr(nodemap_tldevice.GetNode('DeviceSerialNumber'))
                    serial = node_serial.GetValue() if PySpin.IsReadable(node_serial) else "Unknown"

                    # Determine if this is a Firefly/Blackfly (RGB) or something else
                    model_lower = model.lower()
                    is_firefly = 'firefly' in model_lower or 'blackfly' in model_lower

                    # Log detection
                    if is_firefly:
                        logger.info(f"  [OK] Firefly RGB Camera: {model} (S/N: {serial})")
                    else:
                        logger.info(f"  [?] Spinnaker camera: {model} (not Firefly/Blackfly)")

                    # Create CameraInfo
                    # Note: Spinnaker cameras don't use OpenCV VideoCapture device IDs
                    # We store the Spinnaker index separately
                    cameras.append(CameraInfo(
                        device_id=-1,  # Not applicable for Spinnaker cameras
                        name=model,
                        driver='spinnaker',
                        resolution=(640, 480),  # Will be set when opened
                        interface='spinnaker',
                        serial=serial,
                        spinnaker_index=i
                    ))

                    # Clean up camera reference
                    del cam

                except Exception as e:
                    logger.warning(f"  Error reading Spinnaker camera {i}: {e}")

        except Exception as e:
            logger.error(f"  Spinnaker detection error: {e}")
        finally:
            if cam_list is not None:
                del cam_list
            # Don't release system instance - let it persist

        if cameras:
            logger.info(f"  Spinnaker detection complete: {len(cameras)} camera(s)")
        else:
            logger.info("  No Spinnaker cameras detected")

        return cameras

    @staticmethod
    def _print_detection_summary(cameras: List[CameraInfo]):
        """
        Print comprehensive camera detection summary

        Args:
            cameras: List of detected cameras (sorted by priority)
        """
        logger.info("\n" + "="*70)
        logger.info("DETECTION SUMMARY")
        logger.info("="*70)

        thermal_cams = [c for c in cameras if c.is_thermal()]
        rgb_cams = [c for c in cameras if c.is_rgb()]
        unknown_cams = [c for c in cameras if c.camera_type == CameraType.UNKNOWN]

        logger.info(f"\nTotal cameras: {len(cameras)}")
        logger.info(f"  Thermal: {len(thermal_cams)}")
        logger.info(f"  RGB: {len(rgb_cams)}")
        if unknown_cams:
            logger.info(f"  Unknown: {len(unknown_cams)}")

        if thermal_cams:
            logger.info("\nTHERMAL CAMERAS (by priority):")
            for i, cam in enumerate(thermal_cams, 1):
                interface_str = f"[{cam.interface.upper()}]"
                logger.info(f"  {i}. {cam.name} {interface_str}")
                if cam.interface == 'spinnaker':
                    logger.info(f"     Spinnaker Index: {cam.spinnaker_index}, S/N: {cam.serial}")
                else:
                    logger.info(f"     Device ID: {cam.device_id}, Resolution: {cam.resolution}")

        if rgb_cams:
            logger.info("\nRGB CAMERAS (by priority - graded separately from thermal):")
            for i, cam in enumerate(rgb_cams, 1):
                priority_label = {
                    0: "BEST - Firefly (Spinnaker)",
                    1: "GOOD - External USB",
                    2: "OK - Built-in webcam"
                }.get(cam.priority, f"Unknown (priority={cam.priority})")

                interface_str = f"[{cam.interface.upper()}]"
                logger.info(f"  {i}. [{priority_label}] {cam.name} {interface_str}")
                if cam.interface == 'spinnaker':
                    logger.info(f"     Spinnaker Index: {cam.spinnaker_index}, S/N: {cam.serial}")
                else:
                    logger.info(f"     Device ID: {cam.device_id}, Resolution: {cam.resolution}")

        logger.info("="*70 + "\n")

    @staticmethod
    def _detect_v4l2(skip_device_ids: Optional[List[int]] = None) -> List[CameraInfo]:
        """Detect cameras using v4l2-ctl"""
        cameras = []

        if skip_device_ids is None:
            skip_device_ids = []

        try:
            # Get list of video devices
            result = subprocess.run(
                ['v4l2-ctl', '--list-devices'],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode == 0:
                cameras = CameraDetector._parse_v4l2_output(result.stdout, skip_device_ids=skip_device_ids)

        except (subprocess.TimeoutExpired, FileNotFoundError):
            logger.warning("v4l2-ctl not available or timed out")

        return cameras

    @staticmethod
    def _parse_v4l2_output(output: str, skip_device_ids: Optional[List[int]] = None) -> List[CameraInfo]:
        """Parse v4l2-ctl output"""
        cameras = []
        lines = output.strip().split('\n')

        if skip_device_ids is None:
            skip_device_ids = []

        current_name = ""
        for line in lines:
            line = line.strip()

            # Device name line (doesn't start with /)
            if line and not line.startswith('/dev/'):
                # Remove trailing colon and model info
                current_name = line.rstrip(':').strip()

            # Device path line
            elif line.startswith('/dev/video'):
                device_path = line.strip()
                # Extract device number
                match = re.search(r'/dev/video(\d+)', device_path)
                if match:
                    device_id = int(match.group(1))

                    # Skip devices that are already in use
                    if device_id in skip_device_ids:
                        logger.debug(f"Skipping camera index {device_id} (already in use)")
                        continue

                    # Get resolution for this device
                    resolution = CameraDetector._get_device_resolution(device_id)

                    cameras.append(CameraInfo(
                        device_id=device_id,
                        name=current_name if current_name else f"Camera {device_id}",
                        driver="v4l2",
                        resolution=resolution
                    ))

        return cameras

    @staticmethod
    def _get_device_resolution(device_id: int) -> tuple:
        """Get native resolution of a video device"""
        try:
            # Try to query formats
            result = subprocess.run(
                ['v4l2-ctl', '-d', f'/dev/video{device_id}', '--list-formats-ext'],
                capture_output=True,
                text=True,
                timeout=3
            )

            if result.returncode == 0:
                # Look for Size: line
                matches = re.findall(r'Size:\s+Discrete\s+(\d+)x(\d+)', result.stdout)
                if matches:
                    # Return the first (usually native) resolution
                    width, height = matches[0]
                    return (int(width), int(height))

            # Fallback: try opening with OpenCV
            return CameraDetector._probe_opencv_resolution(device_id)

        except:
            return CameraDetector._probe_opencv_resolution(device_id)

    @staticmethod
    def _probe_opencv_resolution(device_id: int) -> tuple:
        """Probe resolution using OpenCV"""
        try:
            cap = cv2.VideoCapture(device_id, cv2.CAP_V4L2)
            if cap.isOpened():
                width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                cap.release()
                return (width, height)
        except:
            pass

        return (0, 0)

    @staticmethod
    def _probe_video_devices(max_devices: int = 10, skip_device_ids: Optional[List[int]] = None) -> List[CameraInfo]:
        """Probe /dev/video* devices directly (Linux)"""
        cameras = []

        if skip_device_ids is None:
            skip_device_ids = []

        for device_id in range(max_devices):
            # Skip devices that are already in use
            if device_id in skip_device_ids:
                logger.debug(f"Skipping camera index {device_id} (already in use)")
                continue

            try:
                cap = cv2.VideoCapture(device_id, cv2.CAP_V4L2)

                if cap.isOpened():
                    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                    cap.release()

                    cameras.append(CameraInfo(
                        device_id=device_id,
                        name=f"Camera {device_id}",
                        driver="opencv",
                        resolution=(width, height)
                    ))

            except:
                pass

        return cameras
    
    @staticmethod
    def _get_usb_device_info(device_id: int) -> Optional[Dict[str, str]]:
        """
        Get USB device information (vendor ID, product ID, description)
        
        Args:
            device_id: Camera device ID
        
        Returns:
            Dictionary with 'vendor_id', 'product_id', 'description' or None
        """
        try:
            system = platform.system()
            
            if system == "Linux":
                # Read from /sys/class/video4linux/videoX/device
                device_path = Path(f"/sys/class/video4linux/video{device_id}/device")
                if device_path.exists():
                    # Read vendor and product IDs
                    vendor_file = device_path / "../idVendor"
                    product_file = device_path / "../idProduct"
                    manufacturer_file = device_path / "../manufacturer"
                    
                    info = {}
                    if vendor_file.exists():
                        info['vendor_id'] = vendor_file.read_text().strip()
                    if product_file.exists():
                        info['product_id'] = product_file.read_text().strip()
                    if manufacturer_file.exists():
                        info['description'] = manufacturer_file.read_text().strip()
                    
                    if info:
                        logger.debug(f"USB device info for {device_id}: {info}")
                        return info
            
            elif system == "Windows":
                # On Windows, we could use win32api or pyusb, but those require additional dependencies
                # For now, skip USB info on Windows (frame analysis is sufficient)
                pass
                
        except Exception as e:
            logger.debug(f"Could not read USB device info for {device_id}: {e}")
        
        return None

    @staticmethod
    def _probe_windows_cameras(max_devices: int = 5, skip_device_ids: Optional[List[int]] = None) -> List[CameraInfo]:
        """
        Probe cameras on Windows using DirectShow/MSMF with ROBUST frame-based detection
        
        CRITICAL: Reads actual frames to identify thermal cameras, not just resolution queries.
        FLIR Boson cameras may report incorrect resolutions until frames are read.

        Args:
            max_devices: Maximum number of device indices to probe (default: 5)
            skip_device_ids: List of device IDs to skip (already in use)

        Returns:
            List of detected CameraInfo objects
        """
        cameras = []
        consecutive_failures = 0
        MAX_CONSECUTIVE_FAILURES = 3  # INCREASED: Allow more gaps (e.g. if device 1 fails but 2 works)

        if skip_device_ids is None:
            skip_device_ids = []
            
        logger.info(f"Probing Windows cameras (max={max_devices})...")

        for device_id in range(max_devices):
            if device_id in skip_device_ids:
                logger.debug(f"Skipping camera index {device_id} (already in use)")
                continue

            cap = None
            try:
                logger.info(f"Probing Windows camera index {device_id}...")  # Changed to INFO for visibility

                # Add small delay to let drivers settle
                time.sleep(0.05)

                # Try DirectShow first (better compatibility with thermal cameras)
                try:
                    cap = cv2.VideoCapture(device_id, cv2.CAP_DSHOW)
                    logger.info(f"  DirectShow attempt: isOpened={cap.isOpened() if cap else False}")
                except Exception as e:
                    logger.info(f"  DirectShow failed for camera {device_id}: {e}")
                    cap = None

                if cap is None or not cap.isOpened():
                    # Fall back to MSMF
                    try:
                        if cap is not None:
                            cap.release()
                        cap = cv2.VideoCapture(device_id, cv2.CAP_MSMF)
                        logger.info(f"  MSMF attempt: isOpened={cap.isOpened() if cap else False}")
                    except Exception as e:
                        logger.info(f"  MSMF failed for camera {device_id}: {e}")
                        cap = None

                if cap is not None and cap.isOpened():
                    logger.info(f"  Camera {device_id} opened successfully, analyzing frames...")
                    
                    # PROBE FOR HIGH RESOLUTION (4K/1080p)
                    # Many 4K webcams default to 640x480 unless requested
                    detected_resolution = (640, 480) # Default fallback
                    
                    # Try setting 4K first
                    try:
                        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 3840)
                        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 2160)
                        time.sleep(0.1)
                        if cap.get(cv2.CAP_PROP_FRAME_WIDTH) >= 3840:
                             logger.info(f"  - Camera {device_id} accepted 4K request")
                    except:
                        pass
                        
                    # ROBUST DETECTION: Read actual frames to identify camera type and real max res
                    is_thermal, resolution = CameraDetector._identify_camera_by_frames(cap, device_id)
                    
                    # Get camera name
                    name = f"Camera {device_id}"
                    try:
                        backend_name = cap.getBackendName()
                        name = f"Camera {device_id} ({backend_name})"
                    except:
                        pass

                    # Update name if thermal
                    if is_thermal:
                        name = f"FLIR Boson {resolution[0]}x{resolution[1]} (Camera {device_id})"
                        logger.info(f"[OK] Thermal camera identified via frame analysis: {name}")
                    elif resolution[0] >= 1920:
                         name = f"High-Res Camera {device_id} ({resolution[0]}x{resolution[1]})"
                         logger.info(f"[OK] High-Res RGB camera identified: {name}")
                    
                    cap.release()
                    cap = None

                    cameras.append(CameraInfo(
                        device_id=device_id,
                        name=name,
                        driver="DSHOW/MSMF",
                        resolution=resolution
                    ))

                    logger.info(f"Detected: {name} at index {device_id}")
                    consecutive_failures = 0

                else:
                    logger.info(f"  Camera {device_id} could not be opened")
                    consecutive_failures += 1

            except Exception as e:
                logger.info(f"  Exception probing camera {device_id}: {e}")  # Changed to INFO
                consecutive_failures += 1
            finally:
                if cap is not None:
                    try:
                        cap.release()
                    except:
                        pass

            # Early termination after consecutive failures
            if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                logger.info(f"  Stopping probe after {consecutive_failures} consecutive failures")  # Changed to INFO
                break

        logger.info(f"Windows camera probe complete: {len(cameras)} camera(s) found")
        return cameras
    
    @staticmethod
    def _identify_camera_by_frames(cap, device_id: int) -> Tuple[bool, Tuple[int, int]]:
        """
        Identify if camera is thermal by reading and analyzing actual frames
        
        This is the ROBUST approach that works when resolution queries fail.
        Uses multiple heuristics: resolution, frame content, histogram, USB device info.
        
        Args:
            cap: Opened cv2.VideoCapture object
            device_id: Camera device ID (for logging)
        
        Returns:
            Tuple of (is_thermal: bool, resolution: tuple)
        """
        try:
            # Check USB device info first (most reliable on Linux)
            usb_info = CameraDetector._get_usb_device_info(device_id)
            if usb_info and usb_info.get('vendor_id', '').upper() == FLIR_USB_VENDOR_ID:
                logger.info(f"Device {device_id}: FLIR vendor ID detected (USB) - definitely thermal")
                # Still need to get resolution from frame
                ret, frame = cap.read()
                if ret and frame is not None:
                    height, width = frame.shape[:2]
                    return True, (width, height)
            
            # Read a couple frames to get stable data
            for _ in range(2):
                ret = cap.grab()  # Discard first frames
            
            ret, frame = cap.read()
            
            if not ret or frame is None:
                # Can't read frames - use query as fallback
                width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                return False, (width, height)
            
            # Analyze frame characteristics
            height, width = frame.shape[:2]
            resolution = (width, height)
            
            logger.debug(f"Device {device_id} frame: {width}x{height}, shape={frame.shape}, dtype={frame.dtype}")
            
            # THERMAL DETECTION HEURISTICS (scored system for robustness):
            thermal_score = 0
            reasons = []
            
            # 1. Check if resolution matches known thermal resolutions (DECISIVE - if yes, it's thermal)
            thermal_resolutions = [(640, 512), (320, 256), (512, 640), (256, 320)]
            if resolution in thermal_resolutions:
                thermal_score += 100  # INCREASED: Resolution match is decisive
                reasons.append(f"thermal resolution {resolution}")
                logger.info(f"Device {device_id}: Resolution {resolution} matches thermal (+100 DECISIVE)")
                
                # If resolution is a perfect match for Boson, return immediately as thermal
                # This bypasses channel checks which might fail on some drivers
                return True, resolution
            
            # 2. Check if frame is grayscale (thermal cameras are single-channel)
            if len(frame.shape) == 2:
                thermal_score += 60  # INCREASED: True grayscale is very strong indicator
                reasons.append("single-channel grayscale")
                logger.debug(f"Device {device_id}: Grayscale frame (+60)")
            
            # 3. Check if all channels are identical (grayscale in RGB format)
            if len(frame.shape) == 3 and frame.shape[2] == 3:
                # Check if R == G == B (grayscale data in color format)
                if np.array_equal(frame[:,:,0], frame[:,:,1]) and np.array_equal(frame[:,:,1], frame[:,:,2]):
                    # CRITICAL: This alone is NOT enough - uniform RGB scenes can match this
                    # Only add small score, require other indicators
                    thermal_score += 5  # REDUCED from 20: Not reliable alone
                    reasons.append("RGB channels identical")
                    logger.debug(f"Device {device_id}: All color channels identical (+5)")
                    
                    # 3a. Check pixel value range - thermal usually has limited range
                    min_val, max_val = frame.min(), frame.max()
                    pixel_range = max_val - min_val
                    
                    # Thermal cameras typically have lower dynamic range in 8-bit conversion
                    # BUT: Dark RGB scenes also have narrow range!
                    # Only score if range is VERY specific to thermal
                    if pixel_range < 100:  # Very narrow range
                        thermal_score += 10  # REDUCED from 15
                        reasons.append(f"narrow pixel range ({pixel_range})")
                        logger.debug(f"Device {device_id}: Narrow range {pixel_range} (+10)")
                    
                    # 3b. Check uniformity - thermal scenes often more uniform
                    # BUT: Walls and empty scenes are also uniform!
                    std_dev = np.std(frame[:,:,0])
                    if std_dev < 20:  # STRICTER threshold (was 30)
                        thermal_score += 10  # REDUCED from 15
                        reasons.append(f"high uniformity (std={std_dev:.1f})")
                        logger.debug(f"Device {device_id}: High uniformity std={std_dev:.1f} (+10)")
                    
                    # 3c. Histogram analysis - thermal has characteristic distribution
                    hist = cv2.calcHist([frame[:,:,0]], [0], None, [256], [0, 256])
                    hist_peak_count = np.sum(hist > (hist.max() * 0.3))  # Count bins with significant values
                    
                    # Thermal cameras tend to have fewer active histogram bins (narrow distribution)
                    if hist_peak_count < 80:  # STRICTER threshold (was 100)
                        thermal_score += 10  # KEPT same
                        reasons.append(f"narrow histogram ({hist_peak_count} bins)")
                        logger.debug(f"Device {device_id}: Narrow histogram {hist_peak_count} bins (+10)")
            
            # 4. Aspect ratio check (common for thermal cameras)
            aspect_ratio = width / height if height > 0 else 0
            # FLIR Boson 640: 640/512 = 1.25 (unusual for webcams)
            # FLIR Boson 320: 320/256 = 1.25
            if 1.2 < aspect_ratio < 1.3:  # 1.25 aspect ratio
                thermal_score += 20  # INCREASED from 15: This is very specific
                reasons.append(f"thermal aspect ratio ({aspect_ratio:.2f})")
                logger.debug(f"Device {device_id}: Aspect ratio {aspect_ratio:.2f} (+20)")
            elif 1.95 < aspect_ratio < 2.05:  # 2.0 aspect ratio (some thermal cameras)
                thermal_score += 15  # INCREASED from 10
                reasons.append(f"unusual aspect ratio ({aspect_ratio:.2f})")
                logger.debug(f"Device {device_id}: Aspect ratio {aspect_ratio:.2f} (+15)")
            
            # Decision threshold: INCREASED to 60 (was 50)
            # This ensures we need EITHER:
            #  - Thermal resolution (100 points alone)
            #  - True grayscale (60 points alone)
            #  - Multiple strong indicators (aspect ratio + histogram + range + uniformity)
            is_thermal = thermal_score >= 60
            
            if is_thermal:
                logger.info(f"[OK] Device {device_id}: Identified as THERMAL (score={thermal_score}): {', '.join(reasons)}")
            else:
                logger.debug(f"Device {device_id}: Identified as RGB (score={thermal_score})")
            
            return is_thermal, resolution
            
        except Exception as e:
            logger.warning(f"Frame analysis failed for device {device_id}: {e}")
            # Fallback to resolution query
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            return False, (width, height)

    @staticmethod
    def find_thermal_camera() -> Optional[CameraInfo]:
        """
        Find best thermal camera automatically (by priority)

        Priority:
        0: FLIR Boson (via any interface)
        1: Generic thermal camera

        Returns:
            CameraInfo for best thermal camera or None if not found
        """
        import time
        cameras = CameraDetector.detect_all_cameras()

        # Give cameras time to fully release after detection scan
        time.sleep(0.3)

        # Get all thermal cameras (already sorted by priority)
        thermal_cameras = [cam for cam in cameras if cam.is_thermal()]

        if thermal_cameras:
            best_thermal = thermal_cameras[0]  # Already sorted, first is best
            logger.info(f"[OK] Selected thermal camera: {best_thermal.name} (priority={best_thermal.priority})")
            return best_thermal

        # Fallback: cameras with FLIR/Boson in name (might be misidentified)
        for cam in cameras:
            if cam.is_flir and not cam.is_rgb():
                logger.warning(f"Found FLIR camera (assumed thermal): {cam}")
                return cam

        # No thermal camera detected
        logger.warning("[FAIL] No thermal camera detected")
        return None

    @staticmethod
    def find_rgb_camera(exclude_thermal_devices: bool = True) -> Optional[CameraInfo]:
        """
        Find best RGB camera automatically (by priority)

        Priority:
        10: FLIR Firefly (Spinnaker SDK) - Global shutter, best
        20: External USB UVC camera
        30: Built-in laptop webcam

        Args:
            exclude_thermal_devices: If True, exclude devices already assigned as thermal

        Returns:
            CameraInfo for best RGB camera or None if not found
        """
        import time
        cameras = CameraDetector.detect_all_cameras()

        # Give cameras time to fully release after detection scan
        time.sleep(0.3)

        # Get all RGB cameras (already sorted by priority)
        rgb_cameras = [cam for cam in cameras if cam.is_rgb()]

        if rgb_cameras:
            best_rgb = rgb_cameras[0]  # Already sorted, first is best
            priority_label = {
                0: "Firefly (Spinnaker) - BEST",
                1: "External USB - GOOD",
                2: "Built-in webcam - OK"
            }.get(best_rgb.priority, f"priority={best_rgb.priority}")

            logger.info(f"[OK] Selected RGB camera: {best_rgb.name} [{priority_label}]")
            return best_rgb

        # Fallback: any non-thermal camera
        for cam in cameras:
            if not cam.is_thermal() and cam.camera_type != CameraType.UNKNOWN:
                logger.warning(f"Found camera (assumed RGB): {cam}")
                return cam

        # No RGB camera detected
        logger.warning("✗ No RGB camera detected")
        return None

    @staticmethod
    def find_flir_boson() -> Optional[CameraInfo]:
        """
        Find FLIR Boson camera automatically (backward compatibility)

        Returns:
            CameraInfo for FLIR Boson or None if not found
        """
        # Use new thermal camera detection
        return CameraDetector.find_thermal_camera()

    @staticmethod
    def print_camera_list(cameras: List[CameraInfo]):
        """Print formatted list of cameras"""
        print("\n" + "="*60)
        print("DETECTED CAMERAS:")
        print("="*60)

        if not cameras:
            print("  No cameras detected")
        else:
            for cam in cameras:
                marker = " [FLIR]" if cam.is_flir else ""
                print(f"  {cam}{marker}")

        print("="*60 + "\n")