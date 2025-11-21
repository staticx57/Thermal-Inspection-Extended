"""
Region of Interest (ROI) Manager for Thermal Inspection
Handles automatic ROI detection, manual ROI creation, and ROI persistence.
"""

import numpy as np
import cv2
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Tuple, Optional, Any
from enum import Enum
import json
import time
from pathlib import Path


class ROIType(Enum):
    """Type of ROI."""
    RECTANGLE = "rectangle"
    POLYGON = "polygon"
    ELLIPSE = "ellipse"
    CIRCLE = "circle"


class ROISource(Enum):
    """How the ROI was created."""
    MANUAL = "manual"
    AUTO_TEMPERATURE = "auto_temperature"
    AUTO_GRADIENT = "auto_gradient"
    AUTO_MOTION = "auto_motion"
    AUTO_EDGE = "auto_edge"


@dataclass
class ROI:
    """Region of Interest data structure."""
    roi_id: str
    roi_type: ROIType
    roi_source: ROISource
    points: List[Tuple[int, int]]  # List of (x,y) points
    label: str = ""
    color: Tuple[int, int, int] = (0, 255, 0)  # BGR
    active: bool = True
    locked: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    last_updated: float = field(default_factory=time.time)

    def get_bbox(self) -> Tuple[int, int, int, int]:
        """Get bounding box (x, y, w, h) for this ROI."""
        if not self.points:
            return (0, 0, 0, 0)

        points_array = np.array(self.points)
        x_min = int(np.min(points_array[:, 0]))
        y_min = int(np.min(points_array[:, 1]))
        x_max = int(np.max(points_array[:, 0]))
        y_max = int(np.max(points_array[:, 1]))

        return (x_min, y_min, x_max - x_min, y_max - y_min)

    def get_mask(self, shape: Tuple[int, int]) -> np.ndarray:
        """
        Get binary mask for this ROI.

        Args:
            shape: Image shape (height, width)

        Returns:
            Binary mask (uint8) where ROI area is 255
        """
        mask = np.zeros(shape, dtype=np.uint8)

        if not self.points:
            return mask

        points_array = np.array(self.points, dtype=np.int32)

        if self.roi_type == ROIType.RECTANGLE:
            if len(self.points) >= 2:
                x, y, w, h = self.get_bbox()
                cv2.rectangle(mask, (x, y), (x+w, y+h), 255, -1)

        elif self.roi_type == ROIType.POLYGON:
            if len(self.points) >= 3:
                cv2.fillPoly(mask, [points_array], 255)

        elif self.roi_type == ROIType.ELLIPSE:
            if len(self.points) >= 2:
                x, y, w, h = self.get_bbox()
                center = (x + w//2, y + h//2)
                axes = (w//2, h//2)
                cv2.ellipse(mask, center, axes, 0, 0, 360, 255, -1)

        elif self.roi_type == ROIType.CIRCLE:
            if len(self.points) >= 2:
                # First point is center, second defines radius
                center = self.points[0]
                dx = self.points[1][0] - self.points[0][0]
                dy = self.points[1][1] - self.points[0][1]
                radius = int(np.sqrt(dx**2 + dy**2))
                cv2.circle(mask, center, radius, 255, -1)

        return mask

    def get_centroid(self) -> Tuple[int, int]:
        """Get centroid of ROI."""
        if not self.points:
            return (0, 0)

        points_array = np.array(self.points)
        centroid_x = int(np.mean(points_array[:, 0]))
        centroid_y = int(np.mean(points_array[:, 1]))

        return (centroid_x, centroid_y)

    def contains_point(self, point: Tuple[int, int]) -> bool:
        """Check if a point is inside this ROI."""
        if not self.points:
            return False

        points_array = np.array(self.points, dtype=np.int32)

        if self.roi_type == ROIType.RECTANGLE:
            x, y, w, h = self.get_bbox()
            return x <= point[0] <= x+w and y <= point[1] <= y+h

        elif self.roi_type == ROIType.POLYGON:
            # Use cv2.pointPolygonTest
            result = cv2.pointPolygonTest(points_array, point, False)
            return result >= 0

        elif self.roi_type == ROIType.ELLIPSE:
            x, y, w, h = self.get_bbox()
            center = (x + w//2, y + h//2)
            # Check if point is inside ellipse
            dx = (point[0] - center[0]) / (w/2)
            dy = (point[1] - center[1]) / (h/2)
            return (dx**2 + dy**2) <= 1

        elif self.roi_type == ROIType.CIRCLE:
            center = self.points[0]
            dx = self.points[1][0] - self.points[0][0]
            dy = self.points[1][1] - self.points[0][1]
            radius = np.sqrt(dx**2 + dy**2)
            dist = np.sqrt((point[0] - center[0])**2 + (point[1] - center[1])**2)
            return dist <= radius

        return False

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "roi_id": self.roi_id,
            "roi_type": self.roi_type.value,
            "roi_source": self.roi_source.value,
            "points": self.points,
            "label": self.label,
            "color": self.color,
            "active": self.active,
            "locked": self.locked,
            "metadata": self.metadata,
            "created_at": self.created_at,
            "last_updated": self.last_updated
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'ROI':
        """Create ROI from dictionary."""
        return cls(
            roi_id=data["roi_id"],
            roi_type=ROIType(data["roi_type"]),
            roi_source=ROISource(data["roi_source"]),
            points=data["points"],
            label=data.get("label", ""),
            color=tuple(data.get("color", [0, 255, 0])),
            active=data.get("active", True),
            locked=data.get("locked", False),
            metadata=data.get("metadata", {}),
            created_at=data.get("created_at", time.time()),
            last_updated=data.get("last_updated", time.time())
        )


class ROIManager:
    """
    Manages regions of interest for thermal inspection.

    Capabilities:
    - Automatic ROI detection (temperature, gradient, motion, edges)
    - Manual ROI creation (rectangle, polygon, ellipse, circle)
    - ROI persistence (save/load JSON)
    - ROI tracking and updates
    """

    def __init__(self, config: Optional[Dict] = None):
        """
        Initialize ROI manager.

        Args:
            config: Configuration dictionary
        """
        self.config = config or {}

        # ROI storage
        self.rois: Dict[str, ROI] = {}  # roi_id -> ROI
        self.roi_counter = 0

        # Auto-detection settings
        self.auto_temp_threshold_hot = self.config.get("auto_temp_threshold_hot", 0.85)
        self.auto_temp_threshold_cold = self.config.get("auto_temp_threshold_cold", 0.15)
        self.auto_gradient_threshold = self.config.get("auto_gradient_threshold", 20.0)
        self.auto_edge_threshold = self.config.get("auto_edge_threshold", 100)
        self.auto_roi_min_area = self.config.get("auto_roi_min_area", 500)
        self.auto_roi_max_count = self.config.get("auto_roi_max_count", 20)

        # Visual settings
        self.default_colors = {
            ROISource.MANUAL: (0, 255, 0),  # Green
            ROISource.AUTO_TEMPERATURE: (0, 0, 255),  # Red
            ROISource.AUTO_GRADIENT: (255, 165, 0),  # Orange
            ROISource.AUTO_MOTION: (255, 0, 255),  # Magenta
            ROISource.AUTO_EDGE: (0, 255, 255)  # Cyan
        }

    def add_roi(self, roi: ROI) -> str:
        """
        Add a new ROI.

        Args:
            roi: ROI object to add

        Returns:
            ROI ID
        """
        self.rois[roi.roi_id] = roi
        return roi.roi_id

    def create_manual_roi(self, roi_type: ROIType, points: List[Tuple[int, int]],
                         label: str = "", color: Optional[Tuple[int, int, int]] = None) -> ROI:
        """
        Create a manual ROI.

        Args:
            roi_type: Type of ROI
            points: List of points defining the ROI
            label: Optional label
            color: Optional color (BGR)

        Returns:
            Created ROI object
        """
        roi_id = f"manual_{self.roi_counter}"
        self.roi_counter += 1

        if color is None:
            color = self.default_colors[ROISource.MANUAL]

        roi = ROI(
            roi_id=roi_id,
            roi_type=roi_type,
            roi_source=ROISource.MANUAL,
            points=points,
            label=label,
            color=color
        )

        self.add_roi(roi)
        return roi

    def create_rectangle_roi(self, x: int, y: int, w: int, h: int,
                            label: str = "", source: ROISource = ROISource.MANUAL) -> ROI:
        """
        Create a rectangle ROI.

        Args:
            x, y: Top-left corner
            w, h: Width and height
            label: Optional label
            source: ROI source

        Returns:
            Created ROI object
        """
        roi_id = f"{source.value}_{self.roi_counter}"
        self.roi_counter += 1

        points = [(x, y), (x+w, y+h)]

        roi = ROI(
            roi_id=roi_id,
            roi_type=ROIType.RECTANGLE,
            roi_source=source,
            points=points,
            label=label,
            color=self.default_colors.get(source, (0, 255, 0))
        )

        self.add_roi(roi)
        return roi

    def detect_temperature_rois(self, thermal_frame: np.ndarray,
                                detect_hot: bool = True,
                                detect_cold: bool = True) -> List[ROI]:
        """
        Automatically detect ROIs based on temperature thresholds.

        Args:
            thermal_frame: Thermal image (grayscale)
            detect_hot: Detect hot regions
            detect_cold: Detect cold regions

        Returns:
            List of created ROI objects
        """
        detected_rois = []

        if thermal_frame is None or thermal_frame.size == 0:
            return detected_rois

        # Detect hot regions
        if detect_hot:
            hot_threshold = np.percentile(thermal_frame, self.auto_temp_threshold_hot * 100)
            hot_mask = (thermal_frame >= hot_threshold).astype(np.uint8) * 255

            contours, _ = cv2.findContours(hot_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            for contour in contours:
                area = cv2.contourArea(contour)
                if area < self.auto_roi_min_area:
                    continue

                x, y, w, h = cv2.boundingRect(contour)

                roi = self.create_rectangle_roi(
                    x, y, w, h,
                    label="Hot Region",
                    source=ROISource.AUTO_TEMPERATURE
                )
                detected_rois.append(roi)

                if len(detected_rois) >= self.auto_roi_max_count:
                    break

        # Detect cold regions
        if detect_cold and len(detected_rois) < self.auto_roi_max_count:
            cold_threshold = np.percentile(thermal_frame, self.auto_temp_threshold_cold * 100)
            cold_mask = (thermal_frame <= cold_threshold).astype(np.uint8) * 255

            contours, _ = cv2.findContours(cold_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            for contour in contours:
                area = cv2.contourArea(contour)
                if area < self.auto_roi_min_area:
                    continue

                x, y, w, h = cv2.boundingRect(contour)

                roi = self.create_rectangle_roi(
                    x, y, w, h,
                    label="Cold Region",
                    source=ROISource.AUTO_TEMPERATURE
                )
                detected_rois.append(roi)

                if len(detected_rois) >= self.auto_roi_max_count:
                    break

        return detected_rois

    def detect_gradient_rois(self, thermal_frame: np.ndarray) -> List[ROI]:
        """
        Automatically detect ROIs based on temperature gradients.

        Args:
            thermal_frame: Thermal image (grayscale)

        Returns:
            List of created ROI objects
        """
        detected_rois = []

        if thermal_frame is None or thermal_frame.size == 0:
            return detected_rois

        # Compute gradient
        thermal_float = thermal_frame.astype(np.float32)
        grad_x = cv2.Sobel(thermal_float, cv2.CV_32F, 1, 0, ksize=3)
        grad_y = cv2.Sobel(thermal_float, cv2.CV_32F, 0, 1, ksize=3)
        gradient = np.sqrt(grad_x**2 + grad_y**2)

        # Normalize and threshold
        gradient_norm = cv2.normalize(gradient, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
        _, gradient_mask = cv2.threshold(gradient_norm, self.auto_gradient_threshold, 255, cv2.THRESH_BINARY)

        # Find contours
        contours, _ = cv2.findContours(gradient_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        for contour in contours:
            area = cv2.contourArea(contour)
            if area < self.auto_roi_min_area:
                continue

            x, y, w, h = cv2.boundingRect(contour)

            roi = self.create_rectangle_roi(
                x, y, w, h,
                label="Gradient Region",
                source=ROISource.AUTO_GRADIENT
            )
            detected_rois.append(roi)

            if len(detected_rois) >= self.auto_roi_max_count:
                break

        return detected_rois

    def detect_motion_rois(self, motion_detections: List[Dict]) -> List[ROI]:
        """
        Create ROIs from motion detections.

        Args:
            motion_detections: List of motion detection dicts with 'bbox' key

        Returns:
            List of created ROI objects
        """
        detected_rois = []

        for detection in motion_detections:
            if len(detected_rois) >= self.auto_roi_max_count:
                break

            bbox = detection.get("bbox")
            if bbox is None:
                continue

            x, y, w, h = bbox

            # Filter small motion detections
            if w * h < self.auto_roi_min_area:
                continue

            roi = self.create_rectangle_roi(
                x, y, w, h,
                label="Motion Detected",
                source=ROISource.AUTO_MOTION
            )
            detected_rois.append(roi)

        return detected_rois

    def detect_edge_rois(self, frame: np.ndarray) -> List[ROI]:
        """
        Automatically detect ROIs based on edge clustering.

        Args:
            frame: Input image (grayscale or color)

        Returns:
            List of created ROI objects
        """
        detected_rois = []

        if frame is None or frame.size == 0:
            return detected_rois

        # Convert to grayscale if needed
        if len(frame.shape) == 3:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        else:
            gray = frame

        # Detect edges
        edges = cv2.Canny(gray, self.auto_edge_threshold, self.auto_edge_threshold * 2)

        # Dilate to connect nearby edges
        kernel = np.ones((5, 5), np.uint8)
        edges_dilated = cv2.dilate(edges, kernel, iterations=2)

        # Find contours
        contours, _ = cv2.findContours(edges_dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        for contour in contours:
            area = cv2.contourArea(contour)
            if area < self.auto_roi_min_area:
                continue

            x, y, w, h = cv2.boundingRect(contour)

            roi = self.create_rectangle_roi(
                x, y, w, h,
                label="Edge Cluster",
                source=ROISource.AUTO_EDGE
            )
            detected_rois.append(roi)

            if len(detected_rois) >= self.auto_roi_max_count:
                break

        return detected_rois

    def get_roi(self, roi_id: str) -> Optional[ROI]:
        """Get ROI by ID."""
        return self.rois.get(roi_id)

    def get_all_rois(self, active_only: bool = True) -> List[ROI]:
        """
        Get all ROIs.

        Args:
            active_only: Only return active ROIs

        Returns:
            List of ROI objects
        """
        if active_only:
            return [roi for roi in self.rois.values() if roi.active]
        return list(self.rois.values())

    def get_rois_by_source(self, source: ROISource) -> List[ROI]:
        """Get all ROIs from a specific source."""
        return [roi for roi in self.rois.values() if roi.roi_source == source]

    def update_roi(self, roi_id: str, **kwargs):
        """
        Update ROI properties.

        Args:
            roi_id: ROI to update
            **kwargs: Properties to update
        """
        if roi_id not in self.rois:
            return

        roi = self.rois[roi_id]

        if roi.locked:
            return  # Cannot update locked ROIs

        for key, value in kwargs.items():
            if hasattr(roi, key):
                setattr(roi, key, value)

        roi.last_updated = time.time()

    def delete_roi(self, roi_id: str):
        """Delete an ROI."""
        if roi_id in self.rois:
            del self.rois[roi_id]

    def delete_rois_by_source(self, source: ROISource):
        """Delete all ROIs from a specific source."""
        to_delete = [roi_id for roi_id, roi in self.rois.items() if roi.roi_source == source]
        for roi_id in to_delete:
            del self.rois[roi_id]

    def clear_all_rois(self):
        """Clear all ROIs."""
        self.rois.clear()

    def save_rois(self, filepath: str):
        """
        Save all ROIs to JSON file.

        Args:
            filepath: Path to save file
        """
        data = {
            "rois": [roi.to_dict() for roi in self.rois.values()],
            "saved_at": time.time()
        }

        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)

    def load_rois(self, filepath: str, clear_existing: bool = True):
        """
        Load ROIs from JSON file.

        Args:
            filepath: Path to load file
            clear_existing: Clear existing ROIs before loading
        """
        if not Path(filepath).exists():
            return

        with open(filepath, 'r') as f:
            data = json.load(f)

        if clear_existing:
            self.clear_all_rois()

        for roi_dict in data.get("rois", []):
            roi = ROI.from_dict(roi_dict)
            self.add_roi(roi)

    def draw_rois(self, frame: np.ndarray, active_only: bool = True,
                 show_labels: bool = True, thickness: int = 2) -> np.ndarray:
        """
        Draw all ROIs on frame.

        Args:
            frame: Image to draw on
            active_only: Only draw active ROIs
            show_labels: Draw labels
            thickness: Line thickness

        Returns:
            Frame with ROIs drawn
        """
        output = frame.copy()

        rois = self.get_all_rois(active_only=active_only)

        for roi in rois:
            if not roi.points:
                continue

            points_array = np.array(roi.points, dtype=np.int32)

            if roi.roi_type == ROIType.RECTANGLE:
                x, y, w, h = roi.get_bbox()
                cv2.rectangle(output, (x, y), (x+w, y+h), roi.color, thickness)

            elif roi.roi_type == ROIType.POLYGON:
                cv2.polylines(output, [points_array], True, roi.color, thickness)

            elif roi.roi_type == ROIType.ELLIPSE:
                x, y, w, h = roi.get_bbox()
                center = (x + w//2, y + h//2)
                axes = (w//2, h//2)
                cv2.ellipse(output, center, axes, 0, 0, 360, roi.color, thickness)

            elif roi.roi_type == ROIType.CIRCLE:
                center = roi.points[0]
                dx = roi.points[1][0] - roi.points[0][0]
                dy = roi.points[1][1] - roi.points[0][1]
                radius = int(np.sqrt(dx**2 + dy**2))
                cv2.circle(output, center, radius, roi.color, thickness)

            # Draw label
            if show_labels and roi.label:
                centroid = roi.get_centroid()
                cv2.putText(output, roi.label, centroid, cv2.FONT_HERSHEY_SIMPLEX,
                           0.5, roi.color, 1, cv2.LINE_AA)

        return output
