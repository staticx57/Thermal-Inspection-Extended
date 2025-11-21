"""
GPU-Accelerated Object Detection for Jetson Orin
Uses YOLOv8 with TensorRT optimization for maximum performance
"""
import cv2
import numpy as np
import time
from typing import List, Tuple, Optional
import logging

try:
    from ultralytics import YOLO
    YOLO_AVAILABLE = True
except ImportError:
    YOLO_AVAILABLE = False
    logging.warning("ultralytics not available, will use fallback detection")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Detection:
    """Object detection result"""

    def __init__(self, bbox: Tuple[int, int, int, int], confidence: float,
                 class_id: int, class_name: str):
        self.bbox = bbox  # (x1, y1, x2, y2)
        self.confidence = confidence
        self.class_id = class_id
        self.class_name = class_name
        self.distance_estimate = None  # Can be added with depth estimation

    def get_center(self) -> Tuple[int, int]:
        """Get bounding box center"""
        x1, y1, x2, y2 = self.bbox
        return ((x1 + x2) // 2, (y1 + y2) // 2)

    def get_area(self) -> int:
        """Get bounding box area"""
        x1, y1, x2, y2 = self.bbox
        return (x2 - x1) * (y2 - y1)


class ObjectDetector:
    """GPU-accelerated object detector optimized for Jetson Orin"""

    # Road-relevant object classes (COCO dataset)
    ROAD_CLASSES = {
        'person': 0, 'bicycle': 1, 'car': 2, 'motorcycle': 3, 'bus': 5,
        'truck': 7, 'traffic light': 9, 'stop sign': 11, 'dog': 16,
        'cat': 15, 'bird': 14, 'deer': None  # deer not in COCO
    }

    def __init__(self, model_path: str = 'yolov8n.pt', confidence_threshold: float = 0.5,
                 use_tensorrt: bool = True, device: str = '0'):
        """
        Initialize object detector

        Args:
            model_path: Path to YOLO model (will auto-convert to TensorRT)
            confidence_threshold: Minimum confidence for detections
            use_tensorrt: Use TensorRT optimization (highly recommended for Jetson)
            device: CUDA device ID
        """
        self.model_path = model_path
        self.confidence_threshold = confidence_threshold
        self.use_tensorrt = use_tensorrt
        self.device = device
        self.model = None
        self.is_initialized = False
        self.fps = 0
        self.last_inference_time = 0

    def initialize(self) -> bool:
        """Initialize the model with GPU acceleration"""
        try:
            if not YOLO_AVAILABLE:
                logger.error("ultralytics package not available. Install with: pip install ultralytics")
                return False

            # Check CUDA availability
            import torch
            cuda_available = False
            try:
                cuda_available = torch.cuda.is_available()
                if cuda_available:
                    # Test if CUDA actually works with real operations
                    test_tensor = torch.zeros(10, 10).cuda()
                    test_result = test_tensor + 1  # Actual CUDA operation
                    test_result = test_result.cpu()  # Transfer back
                    logger.info(f"CUDA available: {torch.cuda.get_device_name(0)}")
                    logger.info(f"CUDA devices: {torch.cuda.device_count()}")
                    logger.info("CUDA test passed successfully")
            except Exception as e:
                logger.error(f"CUDA test failed: {e}")
                logger.error("Cannot use GPU - CUDA operations are broken")
                cuda_available = False
                # Clear CUDA error state
                if torch.cuda.is_available():
                    try:
                        torch.cuda.synchronize()
                    except:
                        pass

            if not cuda_available:
                logger.warning("="*60)
                logger.warning("Running in CPU mode - performance will be limited!")
                logger.warning("For better performance, fix GPU acceleration")
                logger.warning("="*60)
                self.device = 'cpu'
                self.use_tensorrt = False

            logger.info("Loading YOLO model...")
            self.model = YOLO(self.model_path)

            # Export to TensorRT for maximum performance on Jetson (only if CUDA works)
            if self.use_tensorrt and cuda_available:
                logger.info("Converting model to TensorRT (this may take a few minutes on first run)...")
                try:
                    # Export to TensorRT engine - this will be cached
                    engine_path = self.model_path.replace('.pt', '.engine')
                    self.model.export(format='engine', device=self.device, half=True,
                                     workspace=4, simplify=True, dynamic=False)
                    # Load the TensorRT engine
                    self.model = YOLO(engine_path, task='detect')
                    logger.info("TensorRT engine loaded successfully")
                except Exception as e:
                    logger.warning(f"TensorRT export failed: {e}. Using standard PyTorch model.")

            self.is_initialized = True
            logger.info(f"Object detector initialized successfully on device: {self.device}")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize object detector: {e}")
            return False

    def detect(self, frame: np.ndarray, filter_road_objects: bool = True) -> List[Detection]:
        """
        Detect objects in frame using GPU acceleration

        Args:
            frame: Input image (BGR format)
            filter_road_objects: Only return road-relevant objects

        Returns:
            List of Detection objects
        """
        if not self.is_initialized or self.model is None:
            return []

        start_time = time.time()

        try:
            # Run inference (GPU or CPU)
            use_half = self.device != 'cpu'  # FP16 only on GPU
            results = self.model.predict(
                frame,
                conf=self.confidence_threshold,
                device=self.device,
                verbose=False,
                stream=False,
                half=use_half  # FP16 for faster inference on GPU
            )

            detections = []

            # Process results
            for result in results:
                boxes = result.boxes

                for i in range(len(boxes)):
                    # Get box coordinates
                    box = boxes.xyxy[i].cpu().numpy().astype(int)
                    x1, y1, x2, y2 = box

                    # Get confidence and class
                    conf = float(boxes.conf[i])
                    class_id = int(boxes.cls[i])
                    class_name = result.names[class_id]

                    # Filter for road-relevant objects if requested
                    if filter_road_objects and class_name not in self.ROAD_CLASSES:
                        continue

                    detection = Detection(
                        bbox=(x1, y1, x2, y2),
                        confidence=conf,
                        class_id=class_id,
                        class_name=class_name
                    )
                    detections.append(detection)

            # Calculate FPS
            self.last_inference_time = time.time() - start_time
            self.fps = 1.0 / self.last_inference_time if self.last_inference_time > 0 else 0

            return detections

        except Exception as e:
            logger.error(f"Detection error: {e}")
            return []

    def draw_detections(self, frame: np.ndarray, detections: List[Detection],
                       show_fps: bool = True) -> np.ndarray:
        """
        Draw detection boxes and labels on frame

        Args:
            frame: Input image
            detections: List of detections to draw
            show_fps: Show FPS counter

        Returns:
            Annotated frame
        """
        annotated = frame.copy()

        # Color map for different object types
        color_map = {
            'person': (0, 255, 255),      # Yellow
            'car': (0, 255, 0),           # Green
            'truck': (0, 200, 0),         # Dark green
            'bus': (0, 180, 0),           # Darker green
            'bicycle': (255, 0, 255),     # Magenta
            'motorcycle': (200, 0, 255),  # Purple
            'traffic light': (0, 0, 255), # Red
            'stop sign': (0, 0, 255),     # Red
        }

        for det in detections:
            x1, y1, x2, y2 = det.bbox
            color = color_map.get(det.class_name, (255, 255, 255))

            # Draw bounding box
            cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)

            # Draw label with background
            label = f"{det.class_name}: {det.confidence:.2f}"
            (label_w, label_h), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
            cv2.rectangle(annotated, (x1, y1 - label_h - 10), (x1 + label_w, y1), color, -1)
            cv2.putText(annotated, label, (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX,
                       0.5, (0, 0, 0), 1)

        # Draw FPS
        if show_fps:
            fps_text = f"FPS: {self.fps:.1f} | Inference: {self.last_inference_time*1000:.1f}ms"
            cv2.putText(annotated, fps_text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX,
                       0.7, (0, 255, 0), 2)

        return annotated

    def get_performance_metrics(self) -> dict:
        """Get current performance metrics"""
        return {
            'fps': self.fps,
            'inference_time_ms': self.last_inference_time * 1000,
            'using_tensorrt': self.use_tensorrt,
            'device': self.device
        }

    def release(self):
        """Release resources"""
        self.model = None
        self.is_initialized = False
        logger.info("Object detector released")