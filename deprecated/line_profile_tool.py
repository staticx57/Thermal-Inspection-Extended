"""
Line Profile Tool - Temperature Profile Analysis
Phase 3 - Feature 10: Draw lines and analyze temperature profiles

Allows users to draw lines across thermal images and view temperature distribution along the line.
"""

import numpy as np
from dataclasses import dataclass
from typing import List, Tuple, Optional
import logging

logger = logging.getLogger(__name__)


@dataclass
class LineProfileData:
    """Data for a single line profile."""
    line_id: str
    start_point: Tuple[int, int]  # (x, y) in thermal coordinates
    end_point: Tuple[int, int]    # (x, y) in thermal coordinates
    distances: np.ndarray          # Distance along line (pixels)
    temperatures: np.ndarray       # Temperature values (Celsius)
    num_points: int                # Number of sample points
    label: str = "Line"
    color: Tuple[int, int, int] = (255, 255, 0)  # Yellow default

    @property
    def length(self) -> float:
        """Calculate line length in pixels."""
        dx = self.end_point[0] - self.start_point[0]
        dy = self.end_point[1] - self.start_point[1]
        return np.sqrt(dx**2 + dy**2)

    @property
    def min_temp(self) -> float:
        """Minimum temperature along line."""
        return np.min(self.temperatures) if len(self.temperatures) > 0 else 0.0

    @property
    def max_temp(self) -> float:
        """Maximum temperature along line."""
        return np.max(self.temperatures) if len(self.temperatures) > 0 else 0.0

    @property
    def avg_temp(self) -> float:
        """Average temperature along line."""
        return np.mean(self.temperatures) if len(self.temperatures) > 0 else 0.0

    @property
    def std_temp(self) -> float:
        """Temperature standard deviation along line."""
        return np.std(self.temperatures) if len(self.temperatures) > 1 else 0.0


class LineProfileAnalyzer:
    """Analyzes temperature profiles along user-drawn lines."""

    def __init__(self, num_samples: int = 100):
        """Initialize line profile analyzer.

        Args:
            num_samples: Number of points to sample along the line
        """
        self.num_samples = num_samples
        self.profiles: List[LineProfileData] = []
        self._next_id = 1

    def add_line(self, start: Tuple[int, int], end: Tuple[int, int],
                 temp_map: np.ndarray, label: str = None) -> str:
        """Add a new line profile.

        Args:
            start: Starting point (x, y) in thermal coordinates
            end: Ending point (x, y) in thermal coordinates
            temp_map: Temperature map in Celsius
            label: Optional label for the line

        Returns:
            line_id: Unique identifier for the line
        """
        line_id = f"line_{self._next_id}"
        self._next_id += 1

        if label is None:
            label = f"Line {len(self.profiles) + 1}"

        # Sample temperatures along the line
        distances, temperatures = self._sample_line(start, end, temp_map)

        # Assign color (cycle through colors)
        colors = [(255, 255, 0), (0, 255, 255), (255, 0, 255), (0, 255, 0), (255, 128, 0)]
        color = colors[len(self.profiles) % len(colors)]

        profile = LineProfileData(
            line_id=line_id,
            start_point=start,
            end_point=end,
            distances=distances,
            temperatures=temperatures,
            num_points=self.num_samples,
            label=label,
            color=color
        )

        self.profiles.append(profile)
        logger.info(f"Added line profile: {label} from {start} to {end}, length={profile.length:.1f}px")
        return line_id

    def _sample_line(self, start: Tuple[int, int], end: Tuple[int, int],
                     temp_map: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """Sample temperatures along a line.

        Args:
            start: Starting point (x, y)
            end: Ending point (x, y)
            temp_map: Temperature map in Celsius

        Returns:
            (distances, temperatures): Arrays of distance and temperature values
        """
        x0, y0 = start
        x1, y1 = end

        # Generate sample points along the line
        num = self.num_samples
        x_coords = np.linspace(x0, x1, num)
        y_coords = np.linspace(y0, y1, num)

        # Calculate distances from start
        distances = np.sqrt((x_coords - x0)**2 + (y_coords - y0)**2)

        # Sample temperatures (with bounds checking)
        h, w = temp_map.shape
        temperatures = []

        for x, y in zip(x_coords, y_coords):
            ix = int(np.clip(x, 0, w - 1))
            iy = int(np.clip(y, 0, h - 1))
            temperatures.append(temp_map[iy, ix])

        return distances, np.array(temperatures)

    def update_line(self, line_id: str, temp_map: np.ndarray):
        """Update temperature data for an existing line.

        Args:
            line_id: Line identifier
            temp_map: Updated temperature map in Celsius
        """
        profile = self.get_profile(line_id)
        if profile:
            distances, temperatures = self._sample_line(
                profile.start_point,
                profile.end_point,
                temp_map
            )
            profile.distances = distances
            profile.temperatures = temperatures

    def remove_line(self, line_id: str) -> bool:
        """Remove a line profile.

        Args:
            line_id: Line identifier

        Returns:
            True if removed, False if not found
        """
        for i, profile in enumerate(self.profiles):
            if profile.line_id == line_id:
                removed = self.profiles.pop(i)
                logger.info(f"Removed line profile: {removed.label}")
                return True
        return False

    def get_profile(self, line_id: str) -> Optional[LineProfileData]:
        """Get line profile data by ID.

        Args:
            line_id: Line identifier

        Returns:
            LineProfileData or None if not found
        """
        for profile in self.profiles:
            if profile.line_id == line_id:
                return profile
        return None

    def clear_all(self):
        """Remove all line profiles."""
        self.profiles.clear()
        logger.info("Cleared all line profiles")

    def get_all_profiles(self) -> List[LineProfileData]:
        """Get all line profiles."""
        return self.profiles.copy()

    def export_profile_csv(self, line_id: str, filepath: str):
        """Export line profile data to CSV.

        Args:
            line_id: Line identifier
            filepath: Output CSV file path
        """
        profile = self.get_profile(line_id)
        if not profile:
            logger.warning(f"Cannot export: line {line_id} not found")
            return

        import csv
        with open(filepath, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['Distance (px)', 'Temperature (°C)'])
            for dist, temp in zip(profile.distances, profile.temperatures):
                writer.writerow([f"{dist:.2f}", f"{temp:.2f}"])

        logger.info(f"Exported line profile to {filepath}")

    def set_num_samples(self, num_samples: int):
        """Change the number of sample points.

        Args:
            num_samples: New number of sample points
        """
        if num_samples < 10:
            num_samples = 10
        elif num_samples > 1000:
            num_samples = 1000

        self.num_samples = num_samples
        logger.info(f"Line profile sample count set to {num_samples}")


def find_temperature_peaks(temperatures: np.ndarray, prominence: float = 1.0) -> List[int]:
    """Find temperature peaks along a profile.

    Args:
        temperatures: Array of temperature values
        prominence: Minimum prominence for peak detection

    Returns:
        List of peak indices
    """
    try:
        from scipy.signal import find_peaks
        peaks, _ = find_peaks(temperatures, prominence=prominence)
        return peaks.tolist()
    except ImportError:
        # Fallback: simple peak detection
        peaks = []
        for i in range(1, len(temperatures) - 1):
            if temperatures[i] > temperatures[i-1] and temperatures[i] > temperatures[i+1]:
                if temperatures[i] - min(temperatures[i-1], temperatures[i+1]) >= prominence:
                    peaks.append(i)
        return peaks


def find_temperature_valleys(temperatures: np.ndarray, prominence: float = 1.0) -> List[int]:
    """Find temperature valleys (local minima) along a profile.

    Args:
        temperatures: Array of temperature values
        prominence: Minimum prominence for valley detection

    Returns:
        List of valley indices
    """
    # Invert temperatures and find peaks
    inverted = -temperatures
    peaks = find_temperature_peaks(inverted, prominence)
    return peaks
