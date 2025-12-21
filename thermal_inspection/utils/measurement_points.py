"""
Temperature Measurement Points Manager

Allows users to place and manage temperature measurement points on the thermal view.
Points can be added/removed dynamically with no fixed limit.
"""

import numpy as np
from typing import List, Tuple, Optional, Dict
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class MeasurementPoint:
    """
    Temperature measurement point.

    Attributes:
        point_id: Unique identifier
        x: X coordinate in frame
        y: Y coordinate in frame
        temperature: Current temperature in user-selected units (None if not available)
        label: User-defined label (e.g., "Motor", "Bearing")
        color: RGB color tuple for visualization
        unit: Temperature unit symbol (e.g., "°C", "°F", "K")
    """
    point_id: str
    x: int
    y: int
    temperature: Optional[float] = None
    label: str = ""
    color: Tuple[int, int, int] = (255, 255, 0)  # Yellow default
    unit: str = "°C"  # Default unit


class MeasurementPointManager:
    """
    Manages temperature measurement points on thermal frames.

    Features:
    - Add/remove points dynamically
    - No fixed limit on number of points
    - Update temperatures from radiometric data
    - Export point data
    """

    def __init__(self):
        """Initialize measurement point manager."""
        self.points: Dict[str, MeasurementPoint] = {}
        self._next_id = 1

    def add_point(self, x: int, y: int, label: str = "") -> MeasurementPoint:
        """
        Add a new measurement point.

        Args:
            x: X coordinate
            y: Y coordinate
            label: Optional label for the point

        Returns:
            Created MeasurementPoint
        """
        point_id = f"M{self._next_id}"
        self._next_id += 1

        # Auto-generate label if not provided
        if not label:
            label = f"Point {self._next_id - 1}"

        point = MeasurementPoint(
            point_id=point_id,
            x=x,
            y=y,
            label=label,
            color=self._get_color_for_point(len(self.points))
        )

        self.points[point_id] = point
        logger.info(f"Added measurement point '{label}' at ({x}, {y})")
        return point

    def remove_point(self, point_id: str) -> bool:
        """
        Remove a measurement point.

        Args:
            point_id: ID of point to remove

        Returns:
            True if removed, False if not found
        """
        if point_id in self.points:
            point = self.points.pop(point_id)
            logger.info(f"Removed measurement point '{point.label}'")
            return True
        return False

    def clear_all_points(self):
        """Remove all measurement points."""
        count = len(self.points)
        self.points.clear()
        self._next_id = 1
        logger.info(f"Cleared {count} measurement points")

    def update_temperatures(self, temp_frame: np.ndarray, unit: str = "°C") -> int:
        """
        Update temperatures for all points from temperature frame.

        Args:
            temp_frame: Temperature frame (H, W) in user-selected units
            unit: Temperature unit symbol (e.g., "°C", "°F", "K")

        Returns:
            Number of points updated
        """
        if temp_frame is None:
            return 0

        h, w = temp_frame.shape
        updated = 0

        for point in self.points.values():
            # Check bounds
            if 0 <= point.x < w and 0 <= point.y < h:
                point.temperature = float(temp_frame[point.y, point.x])
                point.unit = unit  # Update unit for display
                updated += 1
            else:
                point.temperature = None

        return updated

    def get_point_at_position(self, x: int, y: int, tolerance: int = 10) -> Optional[MeasurementPoint]:
        """
        Find measurement point near given position.

        Args:
            x: X coordinate
            y: Y coordinate
            tolerance: Maximum distance in pixels

        Returns:
            MeasurementPoint if found, None otherwise
        """
        for point in self.points.values():
            dist = np.sqrt((point.x - x)**2 + (point.y - y)**2)
            if dist <= tolerance:
                return point
        return None

    def get_all_points(self) -> List[MeasurementPoint]:
        """
        Get all measurement points.

        Returns:
            List of MeasurementPoint objects
        """
        return list(self.points.values())

    def get_point_by_id(self, point_id: str) -> Optional[MeasurementPoint]:
        """Get measurement point by ID."""
        return self.points.get(point_id)

    def update_point_label(self, point_id: str, label: str) -> bool:
        """
        Update label for a measurement point.

        Args:
            point_id: Point ID
            label: New label

        Returns:
            True if updated, False if not found
        """
        point = self.points.get(point_id)
        if point:
            point.label = label
            logger.info(f"Updated point {point_id} label to '{label}'")
            return True
        return False

    def move_point(self, point_id: str, x: int, y: int) -> bool:
        """
        Move a measurement point to new position.

        Args:
            point_id: Point ID
            x: New X coordinate
            y: New Y coordinate

        Returns:
            True if moved, False if not found
        """
        point = self.points.get(point_id)
        if point:
            point.x = x
            point.y = y
            logger.info(f"Moved point '{point.label}' to ({x}, {y})")
            return True
        return False

    def export_data(self) -> List[Dict]:
        """
        Export measurement point data.

        Returns:
            List of dictionaries with point data
        """
        data = []
        for point in self.points.values():
            data.append({
                'id': point.point_id,
                'label': point.label,
                'x': point.x,
                'y': point.y,
                'temperature_c': point.temperature,
                'color_rgb': point.color
            })
        return data

    def import_data(self, data: List[Dict]) -> int:
        """
        Import measurement points from data.

        Args:
            data: List of dictionaries with point data

        Returns:
            Number of points imported
        """
        imported = 0
        for item in data:
            try:
                point = MeasurementPoint(
                    point_id=item.get('id', f"M{self._next_id}"),
                    x=item['x'],
                    y=item['y'],
                    label=item.get('label', f"Point {self._next_id}"),
                    color=tuple(item.get('color_rgb', (255, 255, 0)))
                )
                self.points[point.point_id] = point
                self._next_id = max(self._next_id, int(point.point_id[1:]) + 1)
                imported += 1
            except Exception as e:
                logger.error(f"Error importing point: {e}")

        logger.info(f"Imported {imported} measurement points")
        return imported

    def get_count(self) -> int:
        """Get number of measurement points."""
        return len(self.points)

    def _get_color_for_point(self, index: int) -> Tuple[int, int, int]:
        """
        Get color for point based on index.

        Args:
            index: Point index

        Returns:
            RGB color tuple
        """
        # Cycle through distinct colors
        colors = [
            (255, 255, 0),   # Yellow
            (0, 255, 255),   # Cyan
            (255, 0, 255),   # Magenta
            (0, 255, 0),     # Green
            (255, 128, 0),   # Orange
            (128, 0, 255),   # Purple
            (255, 255, 255), # White
            (255, 0, 0),     # Red
        ]
        return colors[index % len(colors)]


# ============================================================================
# Test
# ============================================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("\n" + "="*70)
    print("MEASUREMENT POINTS MANAGER TEST")
    print("="*70)

    manager = MeasurementPointManager()

    # Add some points
    p1 = manager.add_point(100, 100, "Motor")
    p2 = manager.add_point(200, 150, "Bearing")
    p3 = manager.add_point(300, 200)  # Auto-labeled

    print(f"\nAdded {manager.get_count()} points")

    # Create dummy temperature frame
    temp_frame = np.random.uniform(20.0, 80.0, (512, 640)).astype(np.float32)

    # Update temperatures
    updated = manager.update_temperatures(temp_frame)
    print(f"Updated {updated} temperatures")

    # Display points
    for point in manager.get_all_points():
        print(f"  {point.label}: ({point.x}, {point.y}) = {point.temperature:.1f}°C")

    # Test finding point
    found = manager.get_point_at_position(105, 105, tolerance=10)
    if found:
        print(f"\nFound point near (105,105): {found.label}")

    # Test export
    data = manager.export_data()
    print(f"\nExported {len(data)} points")

    # Test removal
    manager.remove_point(p2.point_id)
    print(f"After removal: {manager.get_count()} points")

    print("\n" + "="*70)
    print("Test complete!")
    print("="*70 + "\n")
