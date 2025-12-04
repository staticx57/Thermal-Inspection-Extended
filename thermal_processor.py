"""
Thermal Image Processor for Inspection Applications
Hardware-accelerated thermal processing with motion and edge detection.
Replaces vpi_detector.py - YOLO removed, inspection features added.
"""

import cv2
import numpy as np
import time
from typing import List, Tuple, Optional, Dict
from dataclasses import dataclass
import logging
from concurrent.futures import ThreadPoolExecutor

try:
    import vpi
    VPI_AVAILABLE = True
except ImportError:
    VPI_AVAILABLE = False
    logging.warning("VPI not available - using OpenCV fallback")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class MotionDetection:
    """Motion detection result."""
    bbox: Tuple[int, int, int, int]  # x1, y1, x2, y2
    centroid: Tuple[int, int]
    area: int
    confidence: float
    persistence: int  # Number of frames detected


@dataclass
class EdgeCluster:
    """Edge detection cluster result."""
    bbox: Tuple[int, int, int, int]  # x1, y1, x2, y2
    centroid: Tuple[int, int]
    area: int
    confidence: float
    edge_density: float


class ThermalProcessor:
    """
    Hardware-accelerated thermal image processor for inspection.

    Capabilities:
    - Motion detection (temporal differencing)
    - Edge detection (hardware-accelerated with VPI)
    - Thermal palette application (14 palettes)
    - Integration with ROI manager and thermal analyzer
    """

    def __init__(self, config: Optional[Dict] = None):
        """
        Initialize thermal processor.

        Args:
            config: Configuration dictionary
        """
        self.config = config or {}

        # Processing settings
        self.device = self.config.get("device", "cuda")
        self.is_initialized = False
        self.fps = 0
        self.last_processing_time = 0

        # VPI backend (if available)
        if VPI_AVAILABLE:
            self.vpi_backend = vpi.Backend.CUDA if self.device == 'cuda' else vpi.Backend.CPU
        else:
            self.vpi_backend = None
            logger.info("VPI not available - using OpenCV fallback")

        # Motion detection settings
        self.motion_enabled = self.config.get("motion_detection_enabled", True)
        self.motion_threshold = self.config.get("motion_threshold", 20)
        self.min_motion_area = self.config.get("min_motion_area", 400)
        self.max_motion_area_ratio = self.config.get("max_motion_area_ratio", 0.6)
        self.motion_persistence_frames = self.config.get("motion_persistence_frames", 2)

        # Motion tracking state
        self.prev_frame = None
        self.motion_history: Dict = {}  # region_key -> {'count': int, 'bbox': tuple}
        self.prev_normalized_distance = None  # For temporal smoothing of anomaly visualization

        # Edge detection settings
        self.edge_enabled = self.config.get("edge_detection_enabled", True)
        self.edge_threshold_low = self.config.get("edge_threshold_low", 50)
        self.edge_threshold_high = self.config.get("edge_threshold_high", 150)

        # Anomaly priority settings
        self.anomaly_priority_enabled = self.config.get("anomaly_priority_enabled", False)
        self.anomaly_fade_strength = self.config.get("anomaly_fade_strength", 1.0)  # Gradient steepness (0.5-2.0)
        self.anomaly_max_distance = self.config.get("anomaly_max_distance", 100)  # Max pixel distance for gradient
        self.min_edge_cluster_area = self.config.get("min_edge_cluster_area", 500)

        # Parallel processing (Phase 1 optimization)
        self.enable_parallel_processing = self.config.get("enable_parallel", True)
        if self.enable_parallel_processing:
            self.detection_executor = ThreadPoolExecutor(
                max_workers=2,
                thread_name_prefix="thermal_proc"
            )
        else:
            self.detection_executor = None

        # Legacy palette support (for backward compatibility)
        # New code should use palette_manager instead
        self.thermal_palette = self.config.get("thermal_palette", "white_hot")
        self.color_palettes = self._create_color_palettes()

    def _create_color_palettes(self) -> Dict:
        """
        Create thermal color palette lookup tables (14 palettes).
        Note: This is legacy support. New code should use palette_manager.
        """
        palettes = {}

        def create_lut(colormap_id):
            gradient = np.arange(256, dtype=np.uint8).reshape(256, 1)
            return cv2.applyColorMap(gradient, colormap_id)

        # White Hot & Black Hot
        white_hot_lut = np.zeros((256, 1, 3), dtype=np.uint8)
        black_hot_lut = np.zeros((256, 1, 3), dtype=np.uint8)
        for i in range(256):
            white_hot_lut[i, 0, :] = i
            black_hot_lut[i, 0, :] = 255 - i
        palettes['white_hot'] = white_hot_lut
        palettes['black_hot'] = black_hot_lut

        # Standard palettes
        palettes['ironbow'] = create_lut(cv2.COLORMAP_HOT)
        palettes['rainbow'] = create_lut(cv2.COLORMAP_JET)
        palettes['rainbow_hc'] = create_lut(cv2.COLORMAP_TURBO)
        palettes['arctic'] = create_lut(cv2.COLORMAP_WINTER)
        palettes['lava'] = create_lut(cv2.COLORMAP_INFERNO)
        palettes['medical'] = create_lut(cv2.COLORMAP_VIRIDIS)
        palettes['plasma'] = create_lut(cv2.COLORMAP_PLASMA)
        palettes['sepia'] = create_lut(cv2.COLORMAP_AUTUMN)
        palettes['ocean'] = create_lut(cv2.COLORMAP_OCEAN)
        palettes['feather'] = create_lut(cv2.COLORMAP_COOL)

        # Custom amber palette
        amber_lut = np.zeros((256, 1, 3), dtype=np.uint8)
        for i in range(256):
            amber_lut[i, 0, 0] = 0
            amber_lut[i, 0, 1] = min(255, int(i * 0.8))
            amber_lut[i, 0, 2] = min(255, int(i * 1.0))
            if i > 200:
                boost = (i - 200) * 5
                amber_lut[i, 0, 0] = min(255, boost)
                amber_lut[i, 0, 1] = min(255, int(i * 0.8) + boost)
        palettes['amber'] = amber_lut

        # Gray
        gray_lut = np.zeros((256, 1, 3), dtype=np.uint8)
        for i in range(256):
            gray_lut[i, 0, :] = i
        palettes['gray'] = gray_lut

        return palettes

    def reset_motion_detection(self):
        """Reset motion detection state (call when frame size changes)."""
        self.prev_frame = None
        self.motion_history.clear()
        self.prev_normalized_distance = None

    def initialize(self) -> bool:
        """Initialize processor with VPI or OpenCV fallback."""
        try:
            if not VPI_AVAILABLE:
                logger.info("VPI not available - using OpenCV fallback")
                self.is_initialized = True
                return True

            # Try VPI backends
            if self.device == 'cuda':
                backends_to_try = [
                    (vpi.Backend.CUDA, "CUDA"),
                    (vpi.Backend.PVA, "PVA"),
                    (vpi.Backend.VIC, "VIC")
                ]
            else:
                backends_to_try = [(vpi.Backend.CPU, "CPU")]

            test_img = np.zeros((100, 100, 3), dtype=np.uint8)

            for backend, name in backends_to_try:
                try:
                    logger.info(f"Trying VPI backend: {name}")
                    with backend:
                        test_vpi = vpi.asimage(test_img, vpi.Format.BGR8)
                        test_gray = test_vpi.convert(vpi.Format.U8)

                    logger.info(f"VPI {name} backend initialized!")
                    self.vpi_backend = backend
                    self.is_initialized = True
                    return True
                except Exception as e:
                    logger.warning(f"VPI {name} backend failed: {e}")
                    continue

            # All VPI backends failed
            logger.info("VPI initialization failed - using OpenCV fallback")
            self.is_initialized = True
            return True

        except Exception as e:
            logger.error(f"Initialization error: {e}")
            return False

    def apply_thermal_palette(self, frame: np.ndarray, palette_name: Optional[str] = None) -> np.ndarray:
        """
        Apply thermal color palette to grayscale frame.

        Args:
            frame: Grayscale or BGR thermal frame
            palette_name: Palette to use (uses self.thermal_palette if None)

        Returns:
            Colorized thermal frame
        """
        try:
            palette = palette_name or self.thermal_palette

            # Convert to grayscale if needed
            if len(frame.shape) == 3:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            else:
                gray = frame

            # Convert 16-bit to 8-bit if needed
            if gray.dtype == np.uint16:
                gray = cv2.convertScaleAbs(gray, alpha=(255.0/65535.0))

            # Ensure uint8
            if gray.dtype != np.uint8:
                gray = gray.astype(np.uint8)

            # Apply palette
            if palette in self.color_palettes:
                lut = self.color_palettes[palette]
                # LUT is (256, 1, 3) - extract B, G, R channels
                # cv2.LUT requires separate 1D LUTs for each channel
                lut_b = lut[:, 0, 0]  # Blue channel
                lut_g = lut[:, 0, 1]  # Green channel
                lut_r = lut[:, 0, 2]  # Red channel
                
                # Apply LUT to each channel separately
                b = cv2.LUT(gray, lut_b)
                g = cv2.LUT(gray, lut_g)
                r = cv2.LUT(gray, lut_r)
                
                # Merge channels back to BGR
                return cv2.merge([b, g, r])
            else:
                logger.warning(f"Palette {palette} not found, using fallback")
                return cv2.applyColorMap(gray, cv2.COLORMAP_HOT)

        except Exception as e:
            logger.error(f"Error applying palette: {e}")
            if len(frame.shape) == 2:
                return cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
            return frame

    def detect_motion(self, frame: np.ndarray) -> List[MotionDetection]:
        """
        Detect motion using temporal differencing.

        Args:
            frame: Input image (grayscale OR BGR format)

        Returns:
            List of MotionDetection objects
        """
        if not self.motion_enabled:
            return []

        detections = []

        try:
            frame_h, frame_w = frame.shape[:2]
            frame_area = frame_h * frame_w

            # Convert to grayscale if needed (thermal camera gives grayscale)
            if len(frame.shape) == 3:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            else:
                gray = frame  # Already grayscale
            
            # Ensure uint8 dtype for OpenCV operations
            if gray.dtype != np.uint8:
                gray = gray.astype(np.uint8)
            
            gray = cv2.GaussianBlur(gray, (21, 21), 0)

            # Initialize previous frame
            if self.prev_frame is None:
                self.prev_frame = gray.copy()
                return []
            
            # Check for frame size change
            if self.prev_frame.shape != gray.shape:
                logger.info(f"Frame size changed from {self.prev_frame.shape} to {gray.shape} - resetting motion detection")
                self.prev_frame = gray.copy()
                self.motion_history.clear()
                return []
            
            # Ensure matching dtypes for absdiff
            if self.prev_frame.dtype != gray.dtype:
                self.prev_frame = self.prev_frame.astype(gray.dtype)

            # Compute difference
            frame_diff = cv2.absdiff(self.prev_frame, gray)
            _, thresh = cv2.threshold(frame_diff, self.motion_threshold, 255, cv2.THRESH_BINARY)
            thresh = cv2.dilate(thresh, None, iterations=2)

            # Find contours
            contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            # Check for widespread camera motion
            total_motion_area = sum(cv2.contourArea(c) for c in contours)
            motion_ratio = total_motion_area / frame_area

            if motion_ratio > self.max_motion_area_ratio:
                logger.debug(f"Camera motion detected ({motion_ratio*100:.1f}%), skipping frame")
                self.prev_frame = gray
                return []

            # Process motion contours
            current_motion_regions = []

            for contour in contours:
                area = cv2.contourArea(contour)

                if area < self.min_motion_area:
                    continue

                x, y, w, h = cv2.boundingRect(contour)

                # Track by grid region
                center_x = x + w // 2
                center_y = y + h // 2
                region_key = (center_x // 50, center_y // 50)

                current_motion_regions.append(region_key)

                # Update motion history
                if region_key not in self.motion_history:
                    self.motion_history[region_key] = {'count': 1, 'bbox': (x, y, w, h)}
                else:
                    self.motion_history[region_key]['count'] += 1
                    self.motion_history[region_key]['bbox'] = (x, y, w, h)

                # Only report persistent motion
                if self.motion_history[region_key]['count'] >= self.motion_persistence_frames:
                    persistence = self.motion_history[region_key]['count']
                    persistence_bonus = min(0.3, persistence * 0.05)
                    size_confidence = min(0.5, area / (frame_area * 0.1))
                    confidence = min(0.95, 0.4 + size_confidence + persistence_bonus)

                    detection = MotionDetection(
                        bbox=(x, y, x + w, y + h),
                        centroid=(center_x, center_y),
                        area=int(area),
                        confidence=confidence,
                        persistence=persistence
                    )
                    detections.append(detection)

            # Clean up old motion history
            old_regions = set(self.motion_history.keys()) - set(current_motion_regions)
            for region in old_regions:
                del self.motion_history[region]

            self.prev_frame = gray

            return detections

        except Exception as e:
            logger.error(f"Motion detection error: {e}")
            return []

    def detect_edges(self, frame: np.ndarray) -> Tuple[np.ndarray, List[EdgeCluster]]:
        """
        Detect edges and edge clusters.

        Args:
            frame: Input image (BGR format)

        Returns:
            Tuple of (edge image, list of EdgeCluster objects)
        """
        if not self.edge_enabled:
            return None, []

        clusters = []

        try:
            # Use VPI for hardware acceleration if available
            if VPI_AVAILABLE and self.vpi_backend is not None:
                with self.vpi_backend:
                    vpi_img = vpi.asimage(frame, vpi.Format.BGR8)
                    gray = vpi_img.convert(vpi.Format.U8)
                    blurred = gray.gaussian_filter(7, sigma=1.5, border=vpi.Border.CLAMP)
                    edges = blurred.canny(thresh_weak=self.edge_threshold_low,
                                         thresh_strong=self.edge_threshold_high)
                    edges_np = edges.cpu()
            else:
                # OpenCV fallback
                if len(frame.shape) == 3:
                    gray_np = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                else:
                    gray_np = frame.copy() if frame.ndim == 2 else frame
                
                # Ensure uint8 dtype (thermal cameras may output uint16)
                if gray_np.dtype != np.uint8:
                    gray_np = cv2.convertScaleAbs(gray_np, alpha=(255.0/65535.0) if gray_np.dtype == np.uint16 else 1.0)
                
                # Ensure contiguous array
                if not gray_np.flags['C_CONTIGUOUS']:
                    gray_np = np.ascontiguousarray(gray_np)

                blurred_np = cv2.GaussianBlur(gray_np, (7, 7), 1.5)
                edges_np = cv2.Canny(blurred_np, self.edge_threshold_low, self.edge_threshold_high)

            # Find edge clusters
            contours, _ = cv2.findContours(edges_np, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            frame_h, frame_w = frame.shape[:2]
            min_area = self.min_edge_cluster_area
            max_area = (frame_w * frame_h) * 0.3

            # Debug logging (only log occasionally to avoid spam)
            if not hasattr(self, '_edge_debug_counter'):
                self._edge_debug_counter = 0
            if len(contours) > 0:
                self._edge_debug_counter += 1
                if self._edge_debug_counter % 100 == 0:
                    logger.info(f"Edge detection: {len(contours)} contours found, min_area={min_area}, max_area={max_area}")

            for contour in contours:
                area = cv2.contourArea(contour)

                if area < min_area or area > max_area:
                    continue

                x, y, w, h = cv2.boundingRect(contour)

                # Calculate edge density in bounding box
                roi = edges_np[y:y+h, x:x+w]
                edge_density = np.sum(roi > 0) / (w * h) if (w * h) > 0 else 0

                # Calculate confidence
                perimeter = cv2.arcLength(contour, True)
                if perimeter == 0:
                    continue

                circularity = 4 * np.pi * area / (perimeter * perimeter)
                confidence = min(1.0, edge_density * 0.7 + (1.0 - circularity) * 0.3)

                center_x = x + w // 2
                center_y = y + h // 2

                cluster = EdgeCluster(
                    bbox=(x, y, x + w, y + h),
                    centroid=(center_x, center_y),
                    area=int(area),
                    confidence=confidence,
                    edge_density=edge_density
                )
                clusters.append(cluster)

            return edges_np, clusters

        except Exception as e:
            logger.error(f"Edge detection error: {e}")
            return None, []

    def process_frame(self, frame: np.ndarray) -> Dict:
        """
        Process frame with all enabled detection methods.

        Args:
            frame: Input image (BGR format)

        Returns:
            Dictionary with processing results
        """
        if not self.is_initialized:
            return {
                'motion_detections': [],
                'edge_image': None,
                'edge_clusters': [],
                'processing_time_ms': 0,
                'fps': 0
            }

        start_time = time.time()

        # OPTIMIZATION: Parallel motion + edge detection (Phase 1)
        if self.enable_parallel_processing and self.detection_executor and (self.motion_enabled or self.edge_enabled):
            # Submit tasks in parallel
            future_motion = None
            future_edges = None

            if self.motion_enabled:
                future_motion = self.detection_executor.submit(self.detect_motion, frame)

            if self.edge_enabled:
                future_edges = self.detection_executor.submit(self.detect_edges, frame)

            # Collect results
            motion_detections = future_motion.result() if future_motion else []
            if future_edges:
                edge_image, edge_clusters = future_edges.result()
            else:
                edge_image, edge_clusters = None, []

        else:
            # FALLBACK: Sequential execution
            motion_detections = self.detect_motion(frame) if self.motion_enabled else []
            edge_image, edge_clusters = self.detect_edges(frame) if self.edge_enabled else (None, [])

        # Calculate performance metrics
        processing_time = time.time() - start_time
        self.last_processing_time = processing_time
        self.fps = 1.0 / processing_time if processing_time > 0 else 0

        return {
            'motion_detections': motion_detections,
            'edge_image': edge_image,
            'edge_clusters': edge_clusters,
            'processing_time_ms': processing_time * 1000,
            'fps': self.fps
        }

    def set_palette(self, palette_name: str):
        """Change thermal color palette."""
        if palette_name in self.color_palettes:
            self.thermal_palette = palette_name
            logger.info(f"Switched to {palette_name} palette")
        else:
            logger.warning(f"Unknown palette: {palette_name}")

    def get_available_palettes(self) -> List[str]:
        """Get list of available color palettes."""
        return list(self.color_palettes.keys())

    def set_device(self, device: str):
        """Change processing device (cuda/cpu)."""
        if device not in ['cuda', 'cpu']:
            logger.warning(f"Invalid device: {device}")
            return

        if device == self.device:
            return

        self.device = device

        if VPI_AVAILABLE:
            self.vpi_backend = vpi.Backend.CUDA if device == 'cuda' else vpi.Backend.CPU

        logger.info(f"Device switched to {device}")

    def set_motion_enabled(self, enabled: bool):
        """Enable or disable motion detection."""
        self.motion_enabled = enabled
        logger.info(f"Motion detection: {'enabled' if enabled else 'disabled'}")

    def set_edge_enabled(self, enabled: bool):
        """Enable or disable edge detection."""
        self.edge_enabled = enabled
        logger.info(f"Edge detection: {'enabled' if enabled else 'disabled'}")

    def apply_anomaly_priority_colorization(
        self,
        thermal_frame: np.ndarray,
        anomalies: List,
        colored_frame: np.ndarray
    ) -> np.ndarray:
        """
        Apply anomaly priority: color anomalies, fade non-anomalies to grayscale.

        Creates a smooth gradient transition from colored (anomalies) to grayscale
        (non-anomalies) based on distance transform.

        Args:
            thermal_frame: Original grayscale thermal frame (H, W) or (H, W, 1)
            anomalies: List of anomaly dicts/objects with 'bbox' attribute (x1, y1, x2, y2)
            colored_frame: Thermal frame with palette applied (H, W, 3)

        Returns:
            Blended frame (H, W, 3) with gradient fade from color to grayscale
        """
        try:
            # Handle empty anomalies list
            if not anomalies:
                # No anomalies - return fully grayscale
                if len(thermal_frame.shape) == 3:
                    gray = cv2.cvtColor(thermal_frame, cv2.COLOR_BGR2GRAY)
                else:
                    gray = thermal_frame
                return cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)

            h, w = thermal_frame.shape[:2]

            # Create binary mask of anomaly regions
            anomaly_mask = np.zeros((h, w), dtype=np.uint8)

            for anomaly in anomalies:
                # Handle different anomaly types (dict or object)
                if hasattr(anomaly, 'bbox'):
                    bbox = anomaly.bbox
                elif isinstance(anomaly, dict) and 'bbox' in anomaly:
                    bbox = anomaly['bbox']
                else:
                    continue

                # Ensure bbox is within frame bounds
                x1, y1, x2, y2 = bbox
                x1 = max(0, min(w-1, x1))
                y1 = max(0, min(h-1, y1))
                x2 = max(0, min(w, x2))
                y2 = max(0, min(h, y2))

                if x2 > x1 and y2 > y1:
                    anomaly_mask[y1:y2, x1:x2] = 255

            # Compute distance transform (distance from nearest anomaly pixel)
            # distance_map = 0 at anomaly pixels, increasing as we move away
            # OPTIMIZATION: Use cv2.distanceTransform (GPU-accelerated) instead of scipy
            # cv2 is ~10x faster than scipy for distance transforms
            distance_map = cv2.distanceTransform((anomaly_mask == 0).astype(np.uint8), cv2.DIST_L2, 5)

            # Normalize distance to 0-1 range based on max_distance parameter
            # 0 = at anomaly (full color), 1 = far from anomaly (full grayscale)
            normalized_distance = np.clip(
                distance_map / self.anomaly_max_distance,
                0,
                1
            ) ** self.anomaly_fade_strength

            # Temporal smoothing to prevent flickering
            if self.prev_normalized_distance is not None and self.prev_normalized_distance.shape == normalized_distance.shape:
                # Alpha for new frame (0.3 means 30% new, 70% history - smooths jitter)
                alpha = 0.3
                normalized_distance = cv2.addWeighted(
                    normalized_distance.astype(np.float32), alpha,
                    self.prev_normalized_distance.astype(np.float32), 1.0 - alpha,
                    0
                )

            self.prev_normalized_distance = normalized_distance

            # Create grayscale version of thermal frame
            if len(thermal_frame.shape) == 3:
                gray = cv2.cvtColor(thermal_frame, cv2.COLOR_BGR2GRAY)
            else:
                gray = thermal_frame

            # Convert grayscale to BGR format
            grayscale_frame = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)

            # Blend: 0=full color (anomaly), 1=full grayscale (far from anomaly)
            # blend_weight shape: (H, W, 1) to broadcast across color channels
            blend_weight = normalized_distance[:, :, np.newaxis]

            # Perform weighted blend
            blended = (
                colored_frame * (1 - blend_weight) +
                grayscale_frame * blend_weight
            ).astype(np.uint8)

            return blended

        except Exception as e:
            logger.error(f"Anomaly priority colorization error: {e}")
            # Return original colored frame on error
            return colored_frame

    def set_anomaly_priority_enabled(self, enabled: bool):
        """Enable or disable anomaly priority mode."""
        self.anomaly_priority_enabled = enabled
        logger.info(f"Anomaly priority: {'enabled' if enabled else 'disabled'}")

    def get_performance_metrics(self) -> Dict:
        """Get current performance metrics."""
        return {
            'fps': self.fps,
            'processing_time_ms': self.last_processing_time * 1000,
            'vpi_available': VPI_AVAILABLE,
            'device': self.device
        }

    # ========================================================================
    # Temperature Overlay (Radiometric Visualization)
    # ========================================================================

    def apply_temperature_overlay(self, thermal_frame: np.ndarray,
                                  temp_frame: np.ndarray,
                                  colormap: str = "jet",
                                  opacity: float = 0.5) -> np.ndarray:
        """
        Apply temperature colormap overlay to thermal frame.

        Args:
            thermal_frame: Original thermal frame (H, W, 3) BGR
            temp_frame: Temperature data (H, W) float32 in Celsius
            colormap: OpenCV colormap name ("jet", "hot", "cool", "viridis", "plasma")
            opacity: Overlay opacity 0.0-1.0

        Returns:
            Thermal frame with temperature overlay applied
        """
        if thermal_frame is None or temp_frame is None:
            return thermal_frame

        if thermal_frame.shape[:2] != temp_frame.shape:
            # Resize temperature frame to match thermal
            temp_frame = cv2.resize(temp_frame, (thermal_frame.shape[1], thermal_frame.shape[0]),
                                   interpolation=cv2.INTER_LINEAR)

        try:
            # Normalize temperature to 0-255 range
            temp_min = temp_frame.min()
            temp_max = temp_frame.max()

            if temp_max - temp_min > 0.1:  # Avoid division by zero
                temp_normalized = ((temp_frame - temp_min) / (temp_max - temp_min) * 255).astype(np.uint8)
            else:
                temp_normalized = np.zeros_like(temp_frame, dtype=np.uint8)

            # Apply colormap
            colormap_map = {
                "jet": cv2.COLORMAP_JET,
                "hot": cv2.COLORMAP_HOT,
                "cool": cv2.COLORMAP_COOL,
                "viridis": cv2.COLORMAP_VIRIDIS,
                "plasma": cv2.COLORMAP_PLASMA
            }
            cv_colormap = colormap_map.get(colormap, cv2.COLORMAP_JET)
            temp_colored = cv2.applyColorMap(temp_normalized, cv_colormap)

            # Blend with original thermal frame
            result = cv2.addWeighted(thermal_frame, 1.0 - opacity, temp_colored, opacity, 0)

            return result

        except Exception as e:
            logger.error(f"Error applying temperature overlay: {e}")
            return thermal_frame

    # ========================================================================
    # Isotherm Temperature Highlighting
    # ========================================================================

    def apply_isotherm_highlighting(self, colored_frame: np.ndarray,
                                    temp_frame: np.ndarray,
                                    mode: str = "above",
                                    low_threshold: float = 30.0,
                                    high_threshold: float = 50.0,
                                    highlight_color: str = "Red") -> np.ndarray:
        """
        Apply isotherm temperature highlighting to thermal frame.
        
        Args:
            colored_frame: Already colorized thermal frame (H, W, 3) BGR
            temp_frame: Temperature data (H, W) float32 in Celsius
            mode: "above", "below", "between", "outside"
            low_threshold: Low temperature threshold (°C)
            high_threshold: High temperature threshold (°C)
            highlight_color: Color name for highlighting
            
        Returns:
            Frame with isotherm regions highlighted
        """
        if colored_frame is None or temp_frame is None:
            return colored_frame
        
        try:
            # Resize temp_frame if needed
            if colored_frame.shape[:2] != temp_frame.shape:
                temp_frame = cv2.resize(temp_frame, 
                                      (colored_frame.shape[1], colored_frame.shape[0]),
                                      interpolation=cv2.INTER_LINEAR)
            
            # Create mask based on mode
            if mode == "above":
                mask = temp_frame > low_threshold
            elif mode == "below":
                mask = temp_frame < high_threshold
            elif mode == "between":
                mask = (temp_frame >= low_threshold) & (temp_frame <= high_threshold)
            elif mode == "outside":
                mask = (temp_frame < low_threshold) | (temp_frame > high_threshold)
            else:
                logger.warning(f"Unknown isotherm mode: {mode}")
                return colored_frame
            
            # Define highlight color
            color_map = {
                "Red": (0, 0, 255),
                "Yellow": (0, 255, 255),
                "Green": (0, 255, 0),
                "Blue": (255, 0, 0),
                "Magenta": (255, 0, 255),
                "Cyan": (255, 255, 0),
                "White": (255, 255, 255)
            }
            bgr_color = color_map.get(highlight_color, (0, 0, 255))
            
            # Create highlighted overlay
            result = colored_frame.copy()
            
            # Apply semi-transparent highlighting
            overlay = colored_frame.copy()
            overlay[mask] = bgr_color
            
            # Blend 50% overlay with original
            result = cv2.addWeighted(colored_frame, 0.5, overlay, 0.5, 0)
            
            return result
            
        except Exception as e:
            logger.error(f"Error applying isotherm highlighting: {e}")
            return colored_frame

    def release(self):
        """Release resources."""
        # Shutdown thread pool executor (Phase 1 optimization)
        if hasattr(self, 'detection_executor') and self.detection_executor:
            logger.info("Shutting down thermal processor executor...")
            self.detection_executor.shutdown(wait=True, cancel_futures=True)
            logger.info("Thermal processor executor shutdown complete")

        self.is_initialized = False
        self.prev_frame = None
        self.motion_history.clear()
        logger.info("Thermal processor released")
