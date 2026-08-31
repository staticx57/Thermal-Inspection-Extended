"""
Isotherm Bands - Multiple Temperature Range Visualization
Phase 2 - Feature 8: Multi-band isotherm support

Allows visualizing multiple temperature bands simultaneously with different colors.
"""

from dataclasses import dataclass
from typing import List, Tuple
import numpy as np
import logging

logger = logging.getLogger(__name__)


@dataclass
class IsothermBand:
    """Single isotherm temperature band configuration."""
    band_id: str
    label: str
    low_temp: float
    high_temp: float
    color: Tuple[int, int, int]  # RGB color (0-255)
    enabled: bool = True
    mode: str = 'between'  # 'between', 'above', 'below'

    def contains_temperature(self, temp: float) -> bool:
        """Check if temperature falls within this band."""
        if not self.enabled:
            return False

        if self.mode == 'between':
            return self.low_temp <= temp <= self.high_temp
        elif self.mode == 'above':
            return temp > self.high_temp
        elif self.mode == 'below':
            return temp < self.low_temp
        return False


class IsothermBandManager:
    """Manages multiple isotherm bands."""

    def __init__(self):
        self.bands: List[IsothermBand] = []
        self._next_id = 1

    def add_band(self, label: str, low_temp: float, high_temp: float,
                 color: Tuple[int, int, int], mode: str = 'between') -> str:
        """Add a new isotherm band.

        Returns:
            band_id: Unique identifier for the band
        """
        band_id = f"band_{self._next_id}"
        self._next_id += 1

        band = IsothermBand(
            band_id=band_id,
            label=label,
            low_temp=low_temp,
            high_temp=high_temp,
            color=color,
            enabled=True,
            mode=mode
        )

        self.bands.append(band)
        logger.info(f"Added isotherm band: {label} ({low_temp}°C - {high_temp}°C)")
        return band_id

    def remove_band(self, band_id: str) -> bool:
        """Remove an isotherm band."""
        for i, band in enumerate(self.bands):
            if band.band_id == band_id:
                removed = self.bands.pop(i)
                logger.info(f"Removed isotherm band: {removed.label}")
                return True
        return False

    def get_band(self, band_id: str) -> IsothermBand:
        """Get band by ID."""
        for band in self.bands:
            if band.band_id == band_id:
                return band
        return None

    def update_band(self, band_id: str, **kwargs):
        """Update band properties."""
        band = self.get_band(band_id)
        if band:
            for key, value in kwargs.items():
                if hasattr(band, key):
                    setattr(band, key, value)
            logger.debug(f"Updated band {band_id}: {kwargs}")

    def clear_bands(self):
        """Remove all bands."""
        self.bands.clear()
        logger.info("Cleared all isotherm bands")

    def apply_bands_to_frame(self, thermal_frame: np.ndarray, temp_map: np.ndarray) -> np.ndarray:
        """Apply all enabled isotherm bands to a thermal frame.

        Args:
            thermal_frame: BGR thermal image (colored by palette)
            temp_map: Temperature map in Celsius (same size as thermal_frame)

        Returns:
            Modified frame with isotherm bands overlaid
        """
        if not self.bands or thermal_frame is None or temp_map is None:
            return thermal_frame

        # Create output frame
        output = thermal_frame.copy()

        # Apply each band in order (later bands can override earlier ones)
        for band in self.bands:
            if not band.enabled:
                continue

            # Create mask for this band
            if band.mode == 'between':
                mask = (temp_map >= band.low_temp) & (temp_map <= band.high_temp)
            elif band.mode == 'above':
                mask = temp_map > band.high_temp
            elif band.mode == 'below':
                mask = temp_map < band.low_temp
            else:
                continue

            # Apply color to masked regions (semi-transparent overlay)
            if np.any(mask):
                # Convert RGB to BGR for OpenCV
                b, g, r = band.color[2], band.color[1], band.color[0]

                # Alpha blend (50% transparency)
                alpha = 0.5
                output[mask] = (
                    alpha * np.array([b, g, r], dtype=np.uint8) +
                    (1 - alpha) * output[mask]
                ).astype(np.uint8)

        return output

    def get_all_bands(self) -> List[IsothermBand]:
        """Get all bands."""
        return self.bands.copy()

    def get_enabled_bands(self) -> List[IsothermBand]:
        """Get only enabled bands."""
        return [band for band in self.bands if band.enabled]


# Preset band configurations
ISOTHERM_PRESETS = {
    "temperature_zones": [
        ("Cold", -40, 10, (0, 128, 255)),      # Blue
        ("Cool", 10, 20, (0, 255, 255)),       # Cyan
        ("Normal", 20, 30, (0, 255, 0)),       # Green
        ("Warm", 30, 40, (255, 255, 0)),       # Yellow
        ("Hot", 40, 60, (255, 128, 0)),        # Orange
        ("Very Hot", 60, 100, (255, 0, 0)),    # Red
    ],
    "comfort_zones": [
        ("Too Cold", -40, 18, (0, 0, 255)),    # Blue
        ("Comfortable", 18, 24, (0, 255, 0)),  # Green
        ("Too Hot", 24, 100, (255, 0, 0)),     # Red
    ],
    "electronics": [
        ("Normal", -40, 50, (0, 255, 0)),      # Green
        ("Warm", 50, 70, (255, 255, 0)),       # Yellow
        ("Overheating", 70, 100, (255, 0, 0)), # Red
    ],
}


def load_preset(manager: IsothermBandManager, preset_name: str):
    """Load a preset configuration into the manager."""
    if preset_name not in ISOTHERM_PRESETS:
        logger.warning(f"Unknown preset: {preset_name}")
        return

    manager.clear_bands()

    for label, low, high, color in ISOTHERM_PRESETS[preset_name]:
        manager.add_band(label, low, high, color, mode='between')

    logger.info(f"Loaded isotherm preset: {preset_name}")
