"""
Camera Registry System
Tracks detected cameras and their assigned roles (RGB, Thermal, Unknown)
Supports manual role assignment and hot-plugging
"""
import logging
import threading
import json
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)


class CameraRole(Enum):
    """Camera role assignment"""
    THERMAL = "thermal"
    RGB = "rgb"
    UNASSIGNED = "unassigned"


@dataclass
class CameraDescriptor:
    """
    Camera descriptor for identifying cameras across reconnections
    Uses multiple characteristics to identify cameras even if device ID changes
    """
    device_id: int
    name: str
    resolution: Tuple[int, int]
    driver: str
    role: CameraRole = CameraRole.UNASSIGNED
    is_connected: bool = True
    manual_override: bool = False  # True if user manually assigned role
    
    def get_signature(self) -> str:
        """
        Get unique signature for camera identification
        Uses resolution and name pattern (device ID can change)
        """
        # Create signature from stable characteristics
        return f"{self.resolution[0]}x{self.resolution[1]}_{self.name[:20]}"
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization"""
        d = asdict(self)
        d['role'] = self.role.value
        return d
    
    @staticmethod
    def from_dict(data: dict) -> 'CameraDescriptor':
        """Create from dictionary"""
        data['role'] = CameraRole(data['role'])
        data['resolution'] = tuple(data['resolution'])
        return CameraDescriptor(**data)


class CameraRegistry:
    """
    Central registry for tracking cameras and their role assignments
    Thread-safe and persists to configuration
    """
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize camera registry
        
        Args:
            config_path: Path to save camera assignments (default: camera_registry.json)
        """
        self.config_path = config_path or "camera_registry.json"
        self.cameras: Dict[int, CameraDescriptor] = {}  # device_id -> descriptor
        self.lock = threading.Lock()
        self._load_from_config()
    
    def _load_from_config(self):
        """Load camera assignments from configuration file"""
        try:
            config_file = Path(self.config_path)
            if config_file.exists():
                with open(config_file, 'r') as f:
                    data = json.load(f)
                    
                # Load camera descriptors
                for cam_data in data.get('cameras', []):
                    cam = CameraDescriptor.from_dict(cam_data)
                    self.cameras[cam.device_id] = cam
                    logger.info(f"Loaded camera assignment: {cam.name} -> {cam.role.value}")
        except Exception as e:
            logger.warning(f"Failed to load camera registry: {e}")
    
    def _save_to_config(self):
        """Save camera assignments to configuration file"""
        try:
            data = {
                'cameras': [cam.to_dict() for cam in self.cameras.values()],
                'version': '1.0'
            }
            
            with open(self.config_path, 'w') as f:
                json.dump(data, f, indent=2)
                
            logger.debug("Camera registry saved to config")
        except Exception as e:
            logger.error(f"Failed to save camera registry: {e}")
    
    def register_camera(self, device_id: int, name: str, resolution: Tuple[int, int], 
                       driver: str, detected_role: CameraRole = CameraRole.UNASSIGNED) -> CameraDescriptor:
        """
        Register a newly detected camera
        
        Args:
            device_id: Camera device ID
            name: Camera name/description
            resolution: Camera resolution (width, height)
            driver: Camera driver (v4l2, DirectShow, etc.)
            detected_role: Auto-detected role (can be overridden by manual assignment)
        
        Returns:
            CameraDescriptor for the registered camera
        """
        with self.lock:
            # Check if we already know this camera by signature
            signature = f"{resolution[0]}x{resolution[1]}_{name[:20]}"
            
            # Look for existing camera with same signature (may have different device_id)
            existing_camera = None
            for cam in self.cameras.values():
                if cam.get_signature() == signature:
                    existing_camera = cam
                    break
            
            if existing_camera:
                # Camera was previously registered - update device ID and connection status
                logger.info(f"Known camera reconnected: {name} (was device {existing_camera.device_id}, now device {device_id})")
                
                # Remove old device_id entry
                if existing_camera.device_id in self.cameras:
                    del self.cameras[existing_camera.device_id]
                
                # Update device ID and connection status
                existing_camera.device_id = device_id
                existing_camera.is_connected = True
                
                # If it has manual override, keep that role; otherwise update to detected role
                if not existing_camera.manual_override and detected_role != CameraRole.UNASSIGNED:
                    existing_camera.role = detected_role
                
                self.cameras[device_id] = existing_camera
                self._save_to_config()
                return existing_camera
            else:
                # New camera - create descriptor
                camera = CameraDescriptor(
                    device_id=device_id,
                    name=name,
                    resolution=resolution,
                    driver=driver,
                    role=detected_role,
                    is_connected=True,
                    manual_override=False
                )
                
                self.cameras[device_id] = camera
                logger.info(f"New camera registered: {name} at device {device_id} as {detected_role.value}")
                self._save_to_config()
                return camera
    
    def set_camera_role(self, device_id: int, role: CameraRole, manual: bool = True):
        """
        Set camera role (manual assignment)
        
        Args:
            device_id: Camera device ID
            role: New role to assign
            manual: Whether this is a manual override (default: True)
        """
        with self.lock:
            if device_id in self.cameras:
                self.cameras[device_id].role = role
                self.cameras[device_id].manual_override = manual
                logger.info(f"Camera {device_id} role set to {role.value} (manual={manual})")
                self._save_to_config()
            else:
                logger.warning(f"Cannot set role for unknown camera {device_id}")
    
    def mark_disconnected(self, device_id: int):
        """Mark camera as disconnected"""
        with self.lock:
            if device_id in self.cameras:
                self.cameras[device_id].is_connected = False
                logger.info(f"Camera {device_id} marked as disconnected")
                # Don't remove from registry - we want to remember it for reconnection
    
    def get_camera(self, device_id: int) -> Optional[CameraDescriptor]:
        """Get camera descriptor by device ID"""
        with self.lock:
            return self.cameras.get(device_id)
    
    def get_all_cameras(self) -> List[CameraDescriptor]:
        """Get all registered cameras"""
        with self.lock:
            return list(self.cameras.values())
    
    def get_cameras_by_role(self, role: CameraRole, connected_only: bool = True) -> List[CameraDescriptor]:
        """
        Get all cameras with specified role
        
        Args:
            role: Camera role to filter by
            connected_only: Only return connected cameras (default: True)
        
        Returns:
            List of matching camera descriptors
        """
        with self.lock:
            cameras = [cam for cam in self.cameras.values() if cam.role == role]
            if connected_only:
                cameras = [cam for cam in cameras if cam.is_connected]
            return cameras
    
    def get_thermal_camera(self) -> Optional[CameraDescriptor]:
        """Get the thermal camera (if any)"""
        cameras = self.get_cameras_by_role(CameraRole.THERMAL, connected_only=True)
        return cameras[0] if cameras else None
    
    def get_rgb_camera(self) -> Optional[CameraDescriptor]:
        """Get the RGB camera (if any)"""
        cameras = self.get_cameras_by_role(CameraRole.RGB, connected_only=True)
        return cameras[0] if cameras else None
    
    def clear_manual_assignments(self):
        """Clear all manual role assignments (revert to auto-detection)"""
        with self.lock:
            for cam in self.cameras.values():
                if cam.manual_override:
                    cam.manual_override = False
                    cam.role = CameraRole.UNASSIGNED
                    logger.info(f"Cleared manual assignment for camera {cam.device_id}")
            self._save_to_config()
    
    
    def get_connected_cameras(self) -> List[CameraDescriptor]:
        """Get all connected cameras"""
        with self.lock:
            return [cam for cam in self.cameras.values() if cam.is_connected]
    
    def get_disconnected_cameras(self) -> List[CameraDescriptor]:
        """Get all known but currently disconnected cameras"""
        with self.lock:
            return [cam for cam in self.cameras.values() if not cam.is_connected]
    
    def find_camera_by_signature(self, signature: str) -> Optional[CameraDescriptor]:
        """
        Find camera by signature (resolution + name pattern)
        
        Args:
            signature: Camera signature to search for
        
        Returns:
            CameraDescriptor if found, None otherwise
        """
        with self.lock:
            for cam in self.cameras.values():
                if cam.get_signature() == signature:
                    return cam
            return None
    
    def reset(self):
        """Reset registry (clear all cameras)"""
        with self.lock:
            self.cameras.clear()
            self._save_to_config()
            logger.info("Camera registry reset")


# Global camera registry instance
_registry_instance: Optional[CameraRegistry] = None
_registry_lock = threading.Lock()


def get_camera_registry() -> CameraRegistry:
    """Get global camera registry instance (singleton)"""
    global _registry_instance
    
    if _registry_instance is None:
        with _registry_lock:
            if _registry_instance is None:
                _registry_instance = CameraRegistry()
    
    return _registry_instance
