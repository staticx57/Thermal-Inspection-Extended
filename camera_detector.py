"""
Camera Detection Utility
Automatically detect and identify FLIR Boson cameras
"""
import cv2
import subprocess
import re
import logging
import platform
import numpy as np
from typing import List, Dict, Optional, Tuple
from enum import Enum
from pathlib import Path

# Import camera registry for tracking camera roles
from camera_registry import get_camera_registry, CameraRole

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# FLIR Systems vendor ID
FLIR_USB_VENDOR_ID = "09CB"


class CameraType(Enum):
    """Camera type classification"""
    THERMAL = "Thermal"
    RGB = "RGB"
    UNKNOWN = "Unknown"


class CameraInfo:
    """Information about a detected camera"""

    def __init__(self, device_id: int, name: str, driver: str, resolution: tuple):
        self.device_id = device_id
        self.name = name
        self.driver = driver
        self.resolution = resolution
        self.is_flir = 'flir' in name.lower() or 'boson' in name.lower()
        self.camera_type = self._detect_camera_type()

    def _detect_camera_type(self) -> CameraType:
        """
        Detect camera type based on resolution and name

        Returns:
            CameraType enum
        """
        # FLIR Boson thermal camera resolutions
        thermal_resolutions = [
            (640, 512),  # Boson 640
            (320, 256),  # Boson 320
            (512, 640),  # Boson 640 (rotated)
            (256, 320),  # Boson 320 (rotated)
        ]

        # Check resolution first (most reliable)
        if self.resolution in thermal_resolutions:
            return CameraType.THERMAL

        # Check name for thermal keywords
        thermal_keywords = ['flir', 'boson', 'thermal', 'radiometric', 'lwir']
        name_lower = self.name.lower()
        if any(keyword in name_lower for keyword in thermal_keywords):
            return CameraType.THERMAL

        # RGB camera indicators
        rgb_keywords = ['rgb', 'webcam', 'usb', 'hd', 'firefly', 'color']
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

        Args:
            skip_device_ids: List of device IDs to skip during detection (already in use)
            register_cameras: Whether to register detected cameras with the registry (default: True)

        Returns:
            List of CameraInfo objects
        """
        import platform
        cameras = []
        system = platform.system()

        if skip_device_ids is None:
            skip_device_ids = []

        if system == "Linux":
            # Try v4l2-ctl first (Linux)
            v4l2_cameras = CameraDetector._detect_v4l2(skip_device_ids=skip_device_ids)
            if v4l2_cameras:
                cameras.extend(v4l2_cameras)
            else:
                # Fallback: probe video devices directly
                cameras = CameraDetector._probe_video_devices(skip_device_ids=skip_device_ids)
        elif system == "Windows":
            # Windows: probe cameras using DirectShow/MSMF
            cameras = CameraDetector._probe_windows_cameras(skip_device_ids=skip_device_ids)
        else:
            # macOS or other: probe using default backend
            cameras = CameraDetector._probe_video_devices(skip_device_ids=skip_device_ids)

        # Register cameras with the registry if requested
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
        MAX_CONSECUTIVE_FAILURES = 2

        if skip_device_ids is None:
            skip_device_ids = []

        for device_id in range(max_devices):
            if device_id in skip_device_ids:
                logger.debug(f"Skipping camera index {device_id} (already in use)")
                continue

            cap = None
            try:
                logger.debug(f"Probing Windows camera index {device_id}...")

                # Try DirectShow first (better compatibility with thermal cameras)
                try:
                    cap = cv2.VideoCapture(device_id, cv2.CAP_DSHOW)
                except Exception as e:
                    logger.debug(f"DirectShow failed for camera {device_id}: {e}")
                    cap = None

                if cap is None or not cap.isOpened():
                    # Fall back to MSMF
                    try:
                        if cap is not None:
                            cap.release()
                        cap = cv2.VideoCapture(device_id, cv2.CAP_MSMF)
                    except Exception as e:
                        logger.debug(f"MSMF failed for camera {device_id}: {e}")
                        cap = None

                if cap is not None and cap.isOpened():
                    # ROBUST DETECTION: Read actual frames to identify camera type
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
                        logger.info(f"✓ Thermal camera identified via frame analysis: {name}")
                    
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
                    consecutive_failures += 1

            except Exception as e:
                logger.debug(f"Failed to probe camera {device_id}: {e}")
                consecutive_failures += 1
            finally:
                if cap is not None:
                    try:
                        cap.release()
                    except:
                        pass

            # Early termination after consecutive failures
            if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                logger.debug(f"Stopping probe after {consecutive_failures} failures")
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
            
            # Read a few frames to get stable data
            for _ in range(5):
                ret = cap.grab()  # Discard first few frames
            
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
                logger.debug(f"Device {device_id}: Resolution {resolution} matches thermal (+100 DECISIVE)")
            
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
                logger.info(f"✓ Device {device_id}: Identified as THERMAL (score={thermal_score}): {', '.join(reasons)}")
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
        Find thermal camera automatically

        Returns:
            CameraInfo for thermal camera or None if not found
        """
        import time
        cameras = CameraDetector.detect_all_cameras()

        # Give cameras time to fully release after detection scan
        time.sleep(0.3)

        # First priority: cameras identified as thermal
        for cam in cameras:
            if cam.is_thermal():
                logger.info(f"Found thermal camera: {cam}")
                return cam

        # Second priority: cameras with FLIR/Boson in name
        for cam in cameras:
            if cam.is_flir:
                logger.info(f"Found FLIR camera (assumed thermal): {cam}")
                return cam

        # No thermal camera detected
        logger.warning("No thermal camera detected")
        return None

    @staticmethod
    def find_rgb_camera() -> Optional[CameraInfo]:
        """
        Find RGB camera automatically

        Returns:
            CameraInfo for RGB camera or None if not found
        """
        import time
        cameras = CameraDetector.detect_all_cameras()

        # Give cameras time to fully release after detection scan
        time.sleep(0.3)

        # First priority: cameras identified as RGB
        for cam in cameras:
            if cam.is_rgb():
                logger.info(f"Found RGB camera: {cam}")
                return cam

        # Second priority: any non-thermal camera
        for cam in cameras:
            if not cam.is_thermal() and cam.camera_type != CameraType.UNKNOWN:
                logger.info(f"Found camera (assumed RGB): {cam}")
                return cam

        # No RGB camera detected
        logger.warning("No RGB camera detected")
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