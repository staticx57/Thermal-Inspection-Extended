"""
Intelligent Model Manager for Multi-Modal ADAS
Manages multiple YOLO models and switches intelligently based on camera mode

Supports:
- YOLO COCO models (yolov8n/s/m.pt) - trained on RGB dataset
- FLIR COCO models - custom-trained on FLIR thermal dataset
- Intelligent switching: FLIR model for thermal, YOLO for RGB, both for fusion
"""
import os
import logging
from typing import Optional, Dict, List
from enum import Enum
from dataclasses import dataclass

from object_detector import ObjectDetector, Detection
from config import get_config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ModelType(Enum):
    """Types of detection models"""
    YOLO_COCO = "yolo_coco"      # Standard YOLO trained on COCO (RGB images)
    FLIR_COCO = "flir_coco"      # YOLO trained on FLIR thermal dataset
    CUSTOM = "custom"            # User-provided custom model


@dataclass
class ModelInfo:
    """Information about a model"""
    model_type: ModelType
    model_path: str
    display_name: str
    best_for: str  # "thermal", "rgb", "both"
    performance_tier: str  # "fast" (n), "balanced" (s), "accurate" (m)


class ModelManager:
    """
    Manages multiple object detection models and switches intelligently

    Intelligence Rules:
    1. Thermal-only mode → Use FLIR COCO if available, else YOLO COCO
    2. RGB-only mode → Use YOLO COCO (trained on RGB)
    3. Fusion mode → Use both models OR best available
    4. Separate cameras → Run different models per camera
    """

    def __init__(self, models_dir: str = "./models",
                 default_model: str = "yolov8n.pt",
                 confidence_threshold: float = 0.25,
                 use_tensorrt: bool = True,
                 device: str = '0'):
        """
        Initialize model manager

        Args:
            models_dir: Directory to search for models
            default_model: Fallback model if nothing else found
            confidence_threshold: Detection confidence threshold
            use_tensorrt: Enable TensorRT optimization
            device: CUDA device ID
        """
        self.models_dir = models_dir
        self.default_model = default_model
        self.confidence_threshold = confidence_threshold
        self.use_tensorrt = use_tensorrt
        self.device = device

        # Available models
        self.available_models: Dict[str, ModelInfo] = {}

        # Active detectors (can have multiple for dual-camera fusion)
        self.thermal_detector: Optional[ObjectDetector] = None
        self.rgb_detector: Optional[ObjectDetector] = None

        # Scan for available models
        self._scan_models()

        logger.info(f"ModelManager initialized with {len(self.available_models)} models")

    def _scan_models(self):
        """Scan for available YOLO models"""

        # Check current directory for YOLO models
        yolo_models = []
        for filename in os.listdir('.'):
            if filename.endswith('.pt') and 'yolov8' in filename.lower():
                yolo_models.append(filename)

        # Check models directory if it exists
        if os.path.exists(self.models_dir):
            for filename in os.listdir(self.models_dir):
                if filename.endswith('.pt'):
                    yolo_models.append(os.path.join(self.models_dir, filename))

        # Register standard YOLO models
        for model_path in yolo_models:
            if 'flir' in model_path.lower():
                # FLIR-trained model detected
                tier = self._get_performance_tier(model_path)
                self.available_models[model_path] = ModelInfo(
                    model_type=ModelType.FLIR_COCO,
                    model_path=model_path,
                    display_name=f"FLIR-{tier.upper()}",
                    best_for="thermal",
                    performance_tier=tier
                )
                logger.info(f"Found FLIR model: {model_path}")
            else:
                # Standard YOLO COCO model
                tier = self._get_performance_tier(model_path)
                self.available_models[model_path] = ModelInfo(
                    model_type=ModelType.YOLO_COCO,
                    model_path=model_path,
                    display_name=f"YOLO-{tier.upper()}",
                    best_for="rgb",
                    performance_tier=tier
                )
                logger.info(f"Found YOLO model: {model_path}")

        # Ensure we have at least the default model
        if not self.available_models and os.path.exists(self.default_model):
            tier = self._get_performance_tier(self.default_model)
            self.available_models[self.default_model] = ModelInfo(
                model_type=ModelType.YOLO_COCO,
                model_path=self.default_model,
                display_name=f"YOLO-{tier.upper()}",
                best_for="rgb",
                performance_tier=tier
            )

    def _get_performance_tier(self, model_path: str) -> str:
        """Determine performance tier from model name"""
        model_lower = model_path.lower()
        if 'yolov8n' in model_lower or 'nano' in model_lower:
            return 'fast'
        elif 'yolov8s' in model_lower or 'small' in model_lower:
            return 'balanced'
        elif 'yolov8m' in model_lower or 'medium' in model_lower:
            return 'accurate'
        elif 'yolov8l' in model_lower or 'large' in model_lower:
            return 'very_accurate'
        elif 'yolov8x' in model_lower or 'xlarge' in model_lower:
            return 'maximum'
        else:
            return 'unknown'

    def get_best_model_for_mode(self, camera_mode: str,
                               performance_preference: str = 'balanced') -> Optional[str]:
        """
        Select best model for camera mode

        Args:
            camera_mode: "thermal", "rgb", or "fusion"
            performance_preference: "fast", "balanced", or "accurate"

        Returns:
            Model path or None if no suitable model found
        """
        suitable_models = []

        for model_path, info in self.available_models.items():
            # Check if model is suitable for mode
            if camera_mode == "thermal":
                # Prefer FLIR models for thermal
                if info.best_for == "thermal" or info.best_for == "both":
                    suitable_models.append((model_path, info, 2))  # Priority 2
                elif info.model_type == ModelType.YOLO_COCO:
                    suitable_models.append((model_path, info, 1))  # Priority 1 (fallback)

            elif camera_mode == "rgb":
                # Prefer YOLO COCO for RGB
                if info.best_for == "rgb" or info.best_for == "both":
                    suitable_models.append((model_path, info, 2))
                else:
                    suitable_models.append((model_path, info, 1))

            elif camera_mode == "fusion":
                # For fusion, any model works
                suitable_models.append((model_path, info, 1))

        if not suitable_models:
            return None

        # Sort by priority, then by performance preference match
        def sort_key(item):
            model_path, info, priority = item
            perf_match = 1 if info.performance_tier == performance_preference else 0
            return (priority, perf_match)

        suitable_models.sort(key=sort_key, reverse=True)

        best_model = suitable_models[0][0]
        logger.info(f"Selected model for {camera_mode} mode: {best_model}")
        return best_model

    def initialize_for_mode(self, camera_mode: str,
                          performance_preference: str = 'balanced') -> bool:
        """
        Initialize detector(s) for specified camera mode

        Args:
            camera_mode: "thermal", "rgb", or "fusion"
            performance_preference: "fast", "balanced", or "accurate"

        Returns:
            True if successfully initialized
        """
        # Get user-configured custom models from config
        config = get_config()
        user_rgb_model = config.get('detection.yolo.rgb_model')
        user_thermal_model = config.get('detection.yolo.thermal_model')

        if camera_mode == "thermal":
            # Single detector for thermal - prioritize user config
            model_path = user_thermal_model or self.get_best_model_for_mode("thermal", performance_preference)
            if not model_path:
                logger.error("No suitable model found for thermal mode")
                return False

            if user_thermal_model:
                logger.info(f"Using user-configured thermal model: {user_thermal_model}")

            self.thermal_detector = ObjectDetector(
                model_path=model_path,
                confidence_threshold=self.confidence_threshold,
                use_tensorrt=self.use_tensorrt,
                device=self.device
            )
            return self.thermal_detector.initialize()

        elif camera_mode == "rgb":
            # Single detector for RGB - prioritize user config
            model_path = user_rgb_model or self.get_best_model_for_mode("rgb", performance_preference)
            if not model_path:
                logger.error("No suitable model found for RGB mode")
                return False

            if user_rgb_model:
                logger.info(f"Using user-configured RGB model: {user_rgb_model}")

            self.rgb_detector = ObjectDetector(
                model_path=model_path,
                confidence_threshold=self.confidence_threshold,
                use_tensorrt=self.use_tensorrt,
                device=self.device
            )
            return self.rgb_detector.initialize()

        elif camera_mode == "fusion":
            # Dual-detector mode: prioritize user config, then auto-detect best models
            thermal_model = user_thermal_model or self.get_best_model_for_mode("thermal", performance_preference)
            rgb_model = user_rgb_model or self.get_best_model_for_mode("rgb", performance_preference)

            if user_thermal_model:
                logger.info(f"Using user-configured thermal model: {user_thermal_model}")
            if user_rgb_model:
                logger.info(f"Using user-configured RGB model: {user_rgb_model}")

            # If we have FLIR model, use it for thermal; YOLO for RGB
            if thermal_model and rgb_model and thermal_model != rgb_model:
                logger.info("Fusion mode: Using separate models for thermal and RGB")

                self.thermal_detector = ObjectDetector(
                    model_path=thermal_model,
                    confidence_threshold=self.confidence_threshold,
                    use_tensorrt=self.use_tensorrt,
                    device=self.device
                )

                self.rgb_detector = ObjectDetector(
                    model_path=rgb_model,
                    confidence_threshold=self.confidence_threshold,
                    use_tensorrt=self.use_tensorrt,
                    device=self.device
                )

                success_thermal = self.thermal_detector.initialize()
                success_rgb = self.rgb_detector.initialize()

                return success_thermal and success_rgb

            else:
                # Use single model for both (fallback)
                logger.info("Fusion mode: Using single model for both cameras")
                model_path = thermal_model or rgb_model or self.default_model

                self.thermal_detector = ObjectDetector(
                    model_path=model_path,
                    confidence_threshold=self.confidence_threshold,
                    use_tensorrt=self.use_tensorrt,
                    device=self.device
                )
                # Share same detector
                self.rgb_detector = self.thermal_detector

                return self.thermal_detector.initialize()

        return False

    def detect_thermal(self, frame, filter_road_objects: bool = True) -> List[Detection]:
        """Run detection on thermal frame"""
        if self.thermal_detector and self.thermal_detector.is_initialized:
            return self.thermal_detector.detect(frame, filter_road_objects)
        return []

    def detect_rgb(self, frame, filter_road_objects: bool = True) -> List[Detection]:
        """Run detection on RGB frame"""
        if self.rgb_detector and self.rgb_detector.is_initialized:
            return self.rgb_detector.detect(frame, filter_road_objects)
        return []

    def switch_model(self, model_path: str, target: str = "both") -> bool:
        """
        Switch to different model at runtime

        Args:
            model_path: Path to new model
            target: "thermal", "rgb", or "both"

        Returns:
            True if successful
        """
        if model_path not in self.available_models:
            logger.warning(f"Model not found: {model_path}")
            return False

        try:
            new_detector = ObjectDetector(
                model_path=model_path,
                confidence_threshold=self.confidence_threshold,
                use_tensorrt=self.use_tensorrt,
                device=self.device
            )

            if not new_detector.initialize():
                logger.error(f"Failed to initialize new model: {model_path}")
                return False

            # Update target detector(s)
            if target == "thermal" or target == "both":
                if self.thermal_detector:
                    self.thermal_detector.release()
                self.thermal_detector = new_detector

            if target == "rgb" or target == "both":
                if self.rgb_detector:
                    self.rgb_detector.release()
                self.rgb_detector = new_detector if target == "rgb" else self.thermal_detector

            logger.info(f"Switched {target} detector to: {model_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to switch model: {e}")
            return False

    def add_custom_model(self, model_path: str, model_type: ModelType = ModelType.CUSTOM,
                        best_for: str = "both"):
        """
        Add a custom model (e.g., user's FLIR COCO model when they find it)

        Args:
            model_path: Path to model file
            model_type: Type of model
            best_for: "thermal", "rgb", or "both"
        """
        if not os.path.exists(model_path):
            logger.error(f"Model file not found: {model_path}")
            return False

        tier = self._get_performance_tier(model_path)
        display_name = f"{model_type.value.upper()}-{tier.upper()}"

        self.available_models[model_path] = ModelInfo(
            model_type=model_type,
            model_path=model_path,
            display_name=display_name,
            best_for=best_for,
            performance_tier=tier
        )

        logger.info(f"Added custom model: {model_path} ({display_name})")
        return True

    def list_available_models(self) -> List[str]:
        """Get list of available model paths"""
        return list(self.available_models.keys())

    def get_model_info(self, model_path: str) -> Optional[ModelInfo]:
        """Get information about a model"""
        return self.available_models.get(model_path)

    def get_status(self) -> Dict:
        """Get current status"""
        return {
            'available_models': len(self.available_models),
            'thermal_detector_active': self.thermal_detector is not None and self.thermal_detector.is_initialized,
            'rgb_detector_active': self.rgb_detector is not None and self.rgb_detector.is_initialized,
            'using_dual_models': self.thermal_detector != self.rgb_detector if self.thermal_detector and self.rgb_detector else False,
            'models': {path: {
                'type': info.model_type.value,
                'display_name': info.display_name,
                'best_for': info.best_for,
                'tier': info.performance_tier
            } for path, info in self.available_models.items()}
        }

    def release(self):
        """Release all resources"""
        if self.thermal_detector:
            self.thermal_detector.release()
            self.thermal_detector = None

        if self.rgb_detector and self.rgb_detector != self.thermal_detector:
            self.rgb_detector.release()

        self.rgb_detector = None
        logger.info("ModelManager released")


# Example usage
if __name__ == "__main__":
    # Create model manager
    manager = ModelManager()

    # Show available models
    print("\nAvailable Models:")
    for model_path in manager.list_available_models():
        info = manager.get_model_info(model_path)
        print(f"  {info.display_name}: {model_path}")
        print(f"    Best for: {info.best_for}, Tier: {info.performance_tier}")

    # Initialize for fusion mode
    print("\nInitializing for fusion mode...")
    success = manager.initialize_for_mode("fusion", performance_preference="balanced")
    print(f"Initialization: {'SUCCESS' if success else 'FAILED'}")

    # Show status
    print("\nStatus:")
    status = manager.get_status()
    print(f"  Dual models: {status['using_dual_models']}")
    print(f"  Thermal detector: {'Active' if status['thermal_detector_active'] else 'Inactive'}")
    print(f"  RGB detector: {'Active' if status['rgb_detector_active'] else 'Inactive'}")

    # Cleanup
    manager.release()
