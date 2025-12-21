"""
Parallax Compensation Module for Thermal-RGB Fusion

Corrects parallax offset between thermal and RGB cameras using depth estimation.
The thermal and RGB cameras are mounted side-by-side with a baseline distance,
causing parallax that varies with object distance.

This module uses depth estimation to estimate per-pixel depth and compute adaptive 
pixel displacement to align the thermal and RGB views.

Architecture:
- DepthEstimator: Estimates depth from RGB image (supports DepthAnything V2, simplified)
- ParallaxCompensator: Computes alignment displacement based on depth
- Optional: Can be disabled for performance or when cameras are co-located

NEW in v3.3.0:
- DepthAnything V2 ML depth estimation integration (state-of-the-art accuracy)
- Model size selection (small/base/large) for performance/quality tradeoffs
- Auto device detection (CUDA/CPU)
- Lazy model loading
"""

import numpy as np
import cv2
import logging
from typing import Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Optional: Depth estimation model (DepthAnything V2, MiDaS, etc.)
# NOTE: We don't import torch/transformers here to avoid DLL loading errors
# They will be imported lazily when actually needed
DEPTH_ESTIMATION_AVAILABLE = False
TRANSFORMERS_AVAILABLE = False

# Check if torch is importable (without actually importing it at module level)
try:
    import importlib.util
    torch_spec = importlib.util.find_spec("torch")
    if torch_spec is not None:
        # torch package exists, but we won't import it yet (lazy import)
        DEPTH_ESTIMATION_AVAILABLE = True
        logger.info("PyTorch package detected (will load lazily if needed)")
    else:
        logger.info("PyTorch not installed - ML depth estimation disabled")
        logger.info("Parallax correction will use simplified geometric mode")
except Exception as e:
    logger.info(f"Could not detect PyTorch: {e}")
    logger.info("Parallax correction will use simplified geometric mode")



@dataclass
class CameraGeometry:
    """
    Geometric parameters for parallax compensation.

    Attributes:
        baseline_mm: Distance between thermal and RGB camera centers (millimeters)
        thermal_focal_length_mm: Thermal camera focal length (mm)
        rgb_focal_length_mm: RGB camera focal length (mm)
        thermal_sensor_width_mm: Thermal sensor width (mm)
        rgb_sensor_width_mm: RGB sensor width (mm)
        thermal_resolution: (width, height) in pixels
        rgb_resolution: (width, height) in pixels
    """
    baseline_mm: float = 50.0  # Default: 50mm baseline (5cm separation)
    thermal_focal_length_mm: float = 9.0  # Boson 640 typical
    rgb_focal_length_mm: float = 6.0  # Firefly typical
    thermal_sensor_width_mm: float = 10.88  # Boson 640 (17μm × 640px)
    rgb_sensor_width_mm: float = 6.784  # IMX290 (2.9μm × 2336px)
    thermal_resolution: Tuple[int, int] = (640, 512)
    rgb_resolution: Tuple[int, int] = (1920, 1200)


class DepthEstimator:
    """
    Estimates depth map from RGB image using deep learning model.

    Supports:
    - DepthAnything V2 (state-of-the-art, recommended)
    - Simplified geometric estimation (fallback, fast)
    - MiDaS (placeholder, not yet implemented)
    """

    def __init__(self, method: str = "simplified", device: str = "auto", model_size: str = "small"):
        """
        Initialize depth estimator.

        Args:
            method: "simplified", "depthanything", or "midas"
            device: "auto", "cpu", "cuda", or "cuda:0" (auto detects best device)
            model_size: "small", "base", "large" (for DepthAnything V2)
        """
        self.method = method
        self.model_size = model_size
        self.model = None
        self.pipeline = None
        self.enabled = False
        self.model_loaded = False
        
        # Auto-detect best device
        if device == "auto":
            if DEPTH_ESTIMATION_AVAILABLE:
                try:
                    import torch
                    if torch.cuda.is_available():
                        self.device = "cuda"
                        logger.info("Auto-detected CUDA GPU for depth estimation")
                    else:
                        self.device = "cpu"
                        logger.info("Using CPU for depth estimation (no GPU detected)")
                except Exception as e:
                    logger.warning(f"Could not load PyTorch for device detection: {e}")
                    self.device = "cpu"
            else:
                self.device = "cpu"
        else:
            self.device = device

        if method == "simplified":
            self.enabled = True
            logger.info("Using simplified depth estimation (geometric heuristics)")
        elif method == "depthanything":
            if DEPTH_ESTIMATION_AVAILABLE and TRANSFORMERS_AVAILABLE:
                logger.info(f"DepthAnything V2 ({model_size}) will be loaded on first use")
                logger.info(f"Device: {self.device}")
                self.enabled = False  # Will be enabled when model loads
            else:
                logger.warning("DepthAnything V2 requested but dependencies not available")
                logger.warning("Falling back to simplified method")
                logger.warning("Install with: pip install torch transformers")
                self.method = "simplified"
                self.enabled = True
        elif method == "midas":
            logger.warning("MiDaS support not yet implemented")
            logger.warning("Falling back to simplified method")
            self.method = "simplified"
            self.enabled = True

    def load_model(self) -> bool:
        """
        Load depth estimation model (DepthAnything V2).
        
        Model is loaded lazily on first inference call.

        Returns:
            True if model loaded successfully
        """
        if self.method == "simplified":
            self.model_loaded = True
            self.enabled = True
            return True

        if not DEPTH_ESTIMATION_AVAILABLE:
            logger.error("Cannot load model - PyTorch not available")
            logger.error("Install with: pip install torch")
            return False
        
        if self.model_loaded:
            logger.info("Depth model already loaded")
            return True

        try:
            if self.method == "depthanything":
                try:
                    from transformers import pipeline
                    global TRANSFORMERS_AVAILABLE
                    TRANSFORMERS_AVAILABLE = True
                except ImportError:
                    logger.error("Cannot load DepthAnything V2 - transformers not available")
                    logger.error("Install with: pip install transformers")
                    return False
                except Exception as e:
                    logger.error(f"Cannot load transformers: {e}")
                    return False
                
                model_map = {
                    "small": "depth-anything/Depth-Anything-V2-Small-hf",
                    "base": "depth-anything/Depth-Anything-V2-Base-hf",
                    "large": "depth-anything/Depth-Anything-V2-Large-hf"
                }
                
                model_id = model_map.get(self.model_size, model_map["small"])
                logger.info(f"Loading DepthAnything V2: {model_id}")
                logger.info(f"Device: {self.device}")
                logger.info("First-time download: ~100-350MB (cached for future use)...")
                
                device_id = 0 if self.device == "cuda" else -1
                
                self.pipeline = pipeline(
                    task="depth-estimation",
                    model=model_id,
                    device=device_id
                )
                
                logger.info(f"✓ DepthAnything V2 ({self.model_size}) loaded successfully")
                self.model_loaded = True
                self.enabled = True
                return True
                
            elif self.method == "midas":
                logger.warning("MiDaS model loading not yet implemented")
                logger.warning("Use method='depthanything' for ML depth estimation")
                return False

            return False
        except Exception as e:
            logger.error(f"Error loading depth model: {e}")
            import traceback
            traceback.print_exc()
            return False

    def estimate_depth(self, rgb_image: np.ndarray) -> Optional[np.ndarray]:
        """
        Estimate depth map from RGB image.

        Args:
            rgb_image: RGB image (H, W, 3) uint8

        Returns:
            Depth map (H, W) float32, values in meters, or None if failed
            Closer objects have smaller values (typical range: 0.5m-5.0m)
        """
        if not self.enabled:
            logger.warning("Depth estimator not enabled")
            return None

        if rgb_image is None or rgb_image.size == 0:
            return None

        try:
            if self.method == "simplified":
                return self._estimate_depth_simplified(rgb_image)
            elif self.method == "depthanything":
                return self._estimate_depth_depthanything(rgb_image)
            elif self.method == "midas":
                return self._estimate_depth_midas(rgb_image)

            return None
        except Exception as e:
            logger.error(f"Error estimating depth: {e}")
            return None

    def _estimate_depth_simplified(self, rgb_image: np.ndarray) -> np.ndarray:
        """
        Simplified depth estimation using geometric heuristics.

        Assumes:
        - Typical inspection distance: 1-3 meters
        - Top of frame = farther (ceiling/background)
        - Bottom of frame = closer (equipment/floor)
        - Center focus distance = ~2 meters

        Args:
            rgb_image: RGB image (H, W, 3)

        Returns:
            Depth map (H, W) in meters
        """
        h, w = rgb_image.shape[:2]

        y_coords = np.linspace(3.0, 1.0, h, dtype=np.float32)
        depth_map = np.tile(y_coords[:, np.newaxis], (1, w))
        depth_map = cv2.GaussianBlur(depth_map, (5, 5), 1.0)

        return depth_map

    def _estimate_depth_midas(self, rgb_image: np.ndarray) -> Optional[np.ndarray]:
        """
        Estimate depth using MiDaS model (not yet implemented).

        Args:
            rgb_image: RGB image (H, W, 3)

        Returns:
            Depth map (H, W) in meters
        """
        logger.warning("MiDaS inference not yet implemented")
        return None

    def _estimate_depth_depthanything(self, rgb_image: np.ndarray) -> Optional[np.ndarray]:
        """
        Estimate depth using DepthAnything V2 model via HuggingFace Transformers.

        Args:
            rgb_image: RGB image (H, W, 3) uint8

        Returns:
            Depth map (H, W) in meters, normalized to 0.5m-5.0m range
        """
        if self.pipeline is None:
            if not self.load_model():
                logger.error("Failed to load DepthAnything V2 model")
                return None
        
        try:
            from PIL import Image
            
            if rgb_image.shape[2] == 3:
                rgb_for_model = cv2.cvtColor(rgb_image, cv2.COLOR_BGR2RGB)
            else:
                rgb_for_model = rgb_image
            
            pil_image = Image.fromarray(rgb_for_model)
            result = self.pipeline(pil_image)
            depth_pil = result["depth"]
            depth_array = np.array(depth_pil).astype(np.float32)
            
            h, w = rgb_image.shape[:2]
            if depth_array.shape != (h, w):
                depth_array = cv2.resize(depth_array, (w, h), interpolation=cv2.INTER_LINEAR)
            
            depth_min = depth_array.min()
            depth_max = depth_array.max()
            
            if depth_max > depth_min:
                depth_normalized = (depth_array - depth_min) / (depth_max - depth_min)
                depth_inverted = 1.0 - depth_normalized
                depth_meters = 0.5 + depth_inverted * 4.5
            else:
                depth_meters = np.full_like(depth_array, 2.0)
            
            return depth_meters
            
        except Exception as e:
            logger.error(f"DepthAnything V2 inference failed: {e}")
            import traceback
            traceback.print_exc()
            return None


class ParallaxCompensator:
    """
    Computes and applies parallax correction to align thermal and RGB cameras.

    Uses depth map to calculate per-pixel displacement based on camera geometry.
    """

    def __init__(self, camera_geometry: Optional[CameraGeometry] = None,
                 depth_method: str = "simplified"):
        """
        Initialize parallax compensator.

        Args:
            camera_geometry: Camera geometric parameters
            depth_method: Depth estimation method ("simplified", "depthanything", "midas")
        """
        self.geometry = camera_geometry or CameraGeometry()
        self.depth_estimator = DepthEstimator(method=depth_method)
        self.enabled = False  # CRITICAL: Disabled by default

        # Cache
        self.last_depth_map = None
        self.last_displacement_map = None

        logger.info(f"ParallaxCompensator initialized (DISABLED by default)")
        logger.info(f"  Baseline: {self.geometry.baseline_mm}mm")
        logger.info(f"  Depth method: {depth_method}")

    def enable(self, enabled: bool = True):
        """Enable or disable parallax compensation."""
        self.enabled = enabled
        logger.info(f"Parallax compensation: {'ENABLED' if enabled else 'DISABLED'}")

    def is_enabled(self) -> bool:
        """Check if parallax compensation is enabled."""
        return self.enabled

    def set_baseline(self, baseline_mm: float):
        """Set camera baseline distance in millimeters."""
        self.geometry.baseline_mm = baseline_mm
        logger.info(f"Parallax baseline set to {baseline_mm}mm")
        self.last_displacement_map = None

    def compute_disparity(self, depth_map: np.ndarray) -> np.ndarray:
        """
        Compute pixel disparity from depth map using camera geometry.

        Formula: disparity = (baseline × focal_length) / depth

        Args:
            depth_map: Depth map in meters (H, W)

        Returns:
            Disparity map in pixels (H, W)
        """
        thermal_focal_px = (self.geometry.thermal_focal_length_mm /
                           self.geometry.thermal_sensor_width_mm *
                           self.geometry.thermal_resolution[0])

        disparity_px = (self.geometry.baseline_mm * thermal_focal_px) / (depth_map * 1000.0)

        return disparity_px.astype(np.float32)

    def apply_correction(self, thermal_frame: np.ndarray,
                        rgb_frame: np.ndarray) -> np.ndarray:
        """
        Apply parallax correction to thermal frame to align with RGB frame.

        Args:
            thermal_frame: Thermal image (H_t, W_t, C) or (H_t, W_t)
            rgb_frame: RGB image (H_r, W_r, 3)

        Returns:
            Corrected thermal frame aligned with RGB perspective
        """
        if not self.enabled:
            return thermal_frame

        if thermal_frame is None or rgb_frame is None:
            return thermal_frame

        try:
            depth_map = self.depth_estimator.estimate_depth(rgb_frame)
            if depth_map is None:
                logger.warning("Depth estimation failed - returning uncorrected thermal frame")
                return thermal_frame

            self.last_depth_map = depth_map

            thermal_h, thermal_w = thermal_frame.shape[:2]
            depth_resized = cv2.resize(depth_map, (thermal_w, thermal_h),
                                      interpolation=cv2.INTER_LINEAR)

            disparity_map = self.compute_disparity(depth_resized)

            flow_map = np.zeros((thermal_h, thermal_w, 2), dtype=np.float32)
            flow_map[:, :, 0] = disparity_map
            flow_map[:, :, 1] = 0

            self.last_displacement_map = flow_map

            corrected_thermal = self._remap_thermal(thermal_frame, flow_map)

            return corrected_thermal

        except Exception as e:
            logger.error(f"Error applying parallax correction: {e}")
            return thermal_frame

    def _remap_thermal(self, thermal_frame: np.ndarray,
                      flow_map: np.ndarray) -> np.ndarray:
        """Remap thermal frame using displacement map."""
        h, w = thermal_frame.shape[:2]

        x_coords, y_coords = np.meshgrid(np.arange(w), np.arange(h))

        map_x = (x_coords - flow_map[:, :, 0]).astype(np.float32)
        map_y = (y_coords - flow_map[:, :, 1]).astype(np.float32)

        corrected = cv2.remap(thermal_frame, map_x, map_y,
                             interpolation=cv2.INTER_LINEAR,
                             borderMode=cv2.BORDER_REPLICATE)

        return corrected

    def get_depth_map(self) -> Optional[np.ndarray]:
        """Get last computed depth map for visualization."""
        return self.last_depth_map

    def get_displacement_map(self) -> Optional[np.ndarray]:
        """Get last computed displacement map for debugging."""
        return self.last_displacement_map

    def get_info(self) -> dict:
        """Get parallax compensator information."""
        return {
            'enabled': self.enabled,
            'depth_method': self.depth_estimator.method,
            'baseline_mm': self.geometry.baseline_mm,
            'thermal_resolution': self.geometry.thermal_resolution,
            'rgb_resolution': self.geometry.rgb_resolution,
            'depth_available': self.last_depth_map is not None
        }


def create_parallax_compensator(baseline_mm: float = 50.0,
                                depth_method: str = "simplified",
                                enabled: bool = False) -> ParallaxCompensator:
    """
    Create and configure parallax compensator.

    Args:
        baseline_mm: Camera baseline distance (mm)
        depth_method: "simplified", "depthanything", or "midas"
        enabled: Enable parallax correction (default: False)

    Returns:
        Configured ParallaxCompensator instance
    """
    geometry = CameraGeometry(baseline_mm=baseline_mm)
    compensator = ParallaxCompensator(camera_geometry=geometry,
                                     depth_method=depth_method)
    compensator.enable(enabled)

    return compensator


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("\n" + "="*70)
    print("PARALLAX COMPENSATOR TEST")
    print("="*70)

    compensator = create_parallax_compensator(baseline_mm=50.0, enabled=False)

    print(f"\nCompensator info:")
    info = compensator.get_info()
    for key, value in info.items():
        print(f"  {key}: {value}")

    print(f"\nTesting with dummy frames...")
    thermal_dummy = np.random.randint(0, 255, (512, 640, 3), dtype=np.uint8)
    rgb_dummy = np.random.randint(0, 255, (1200, 1920, 3), dtype=np.uint8)

    result_disabled = compensator.apply_correction(thermal_dummy, rgb_dummy)
    assert np.array_equal(result_disabled, thermal_dummy), "Disabled mode should return original"
    print("✓ Disabled mode: Returns original thermal frame")

    compensator.enable(True)
    result_enabled = compensator.apply_correction(thermal_dummy, rgb_dummy)
    print(f"✓ Enabled mode: Processed frame shape {result_enabled.shape}")

    if compensator.get_depth_map() is not None:
        print(f"✓ Depth map generated: {compensator.get_depth_map().shape}")

    print("\n" + "="*70)
    print("Test complete!")
    print("="*70 + "\n")
