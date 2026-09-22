"""
Measurement point data class for spot temperature measurements.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class MeasurementPoint:
    """Spot measurement point."""
    x: int
    y: int
    label: str
    color: tuple = (255, 255, 0)  # RGB
    temperature: Optional[float] = None
    unit: str = "°C"
    distance_m: Optional[float] = None  # Real depth-camera distance to this point, meters; None if no RealSense
