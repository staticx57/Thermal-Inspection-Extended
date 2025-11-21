"""
Palette Manager for Multi-Palette Thermal Inspection
Manages global and per-ROI color palettes for thermal visualization.
"""

import numpy as np
import cv2
from typing import Dict, List, Optional, Tuple
from enum import Enum
from dataclasses import dataclass, field
import json


class PaletteType(Enum):
    """Available thermal color palettes (45 total)."""

    # ===== GRAYSCALE PALETTES (4) =====
    WHITE_HOT = "white_hot"          # Hot=white, cold=black (FLIR standard)
    BLACK_HOT = "black_hot"          # Hot=black, cold=white (inverted)
    GRAY = "gray"                    # Pure grayscale
    SEPIA = "sepia"                  # Warm sepia tones (reduced eye fatigue)

    # ===== IRON/FIRE PALETTES (6) =====
    IRONBOW = "ironbow"              # Black→purple→red→orange→yellow→white (industry standard)
    LAVA = "lava"                    # Black→red→orange→yellow→white (fire/heat)
    GRADEDFIRE = "gradedfire"        # Sophisticated 10-stop fire gradient
    HOTTEST = "hottest"              # Purple→magenta→red→yellow→white (extreme heat)
    AMBER = "amber"                  # Black→orange→yellow→white (firefighting)
    INFERNO = "inferno"              # Perceptually uniform fire (matplotlib)

    # ===== RAINBOW PALETTES (5) =====
    RAINBOW = "rainbow"              # Standard rainbow (OpenCV JET)
    RAINBOW_HC = "rainbow_hc"        # High contrast rainbow (TURBO)
    RAINBOW_REVERSED = "rainbow_rev" # Reversed rainbow (cold→hot)
    SPECTRAL = "spectral"            # Blue→green→yellow→red spectral
    COOL_HOT = "cool_hot"            # Cool to hot (JET variant)

    # ===== COLD/ARCTIC PALETTES (4) =====
    ARCTIC = "arctic"                # White→cyan→blue→dark blue
    ICE = "ice"                      # Light blue→dark blue gradient
    WINTER = "winter"                # Blue→cyan→green (cold emphasis)
    OCEAN = "ocean"                  # Ocean depths palette

    # ===== PERCEPTUALLY UNIFORM (Scientific) (5) =====
    VIRIDIS = "viridis"              # Yellow→green→blue (matplotlib default)
    PLASMA = "plasma"                # Purple→red→orange→yellow
    MAGMA = "magma"                  # Black→purple→red→yellow
    CIVIDIS = "cividis"              # Blue→yellow (colorblind-friendly)
    TURBO = "turbo"                  # Rainbow-like but perceptually better

    # ===== DIVERGING PALETTES (6) =====
    BLUE_RED = "blue_red"            # Blue→white→red (temperature delta)
    COOL_WARM = "cool_warm"          # Blue→gray→red (balanced)
    PURPLE_ORANGE = "purple_orange"  # Purple→white→orange
    GREEN_RED = "green_red"          # Green→white→red (traffic light)
    BLUE_YELLOW = "blue_yellow"      # Blue→white→yellow
    PINK_GREEN = "pink_green"        # Pink→white→green

    # ===== SEQUENTIAL PALETTES (7) =====
    GLOBOW = "globow"                # Green→yellow→orange→red (increasing danger)
    MEDICAL = "medical"              # Medical imaging (Viridis variant)
    THERMAL = "thermal"              # Thermal-optimized sequential
    HELIX = "helix"                  # Spiral through color space
    CUBEHELIX = "cubehelix"          # Perceptually uniform helix
    TWILIGHT = "twilight"            # Cyclic twilight colors
    DUSK = "dusk"                    # Warm sequential

    # ===== SPECIALIZED/INDUSTRIAL (8) =====
    FUSION = "fusion"                # Blue→purple→pink→red (camera fusion)
    PRISM = "prism"                  # Multi-color prism effect
    ALARM = "alarm"                  # High-contrast alarm colors
    LAPLACIAN = "laplacian"          # Edge-enhanced visualization
    ISOTHERM = "isotherm"            # Discrete isothermal bands
    VELOCITY = "velocity"            # Flow/velocity visualization
    TERRAIN = "terrain"              # Terrain-like elevation
    DEPTH = "depth"                  # Depth perception palette


@dataclass
class PaletteConfig:
    """Configuration for a palette application."""
    palette_type: PaletteType
    auto_contrast: bool = True
    contrast_min: float = 0.0
    contrast_max: float = 1.0
    gamma: float = 1.0
    invert: bool = False


class PaletteManager:
    """
    Manages thermal color palettes with global and per-ROI override support.

    Architecture:
    - Global default palette (applies to entire image)
    - Per-ROI palette overrides (independent palettes for specific ROIs)
    - Composite rendering (combine global + ROI-specific palettes)
    """

    # OpenCV colormap mappings for standard palettes
    OPENCV_COLORMAPS = {
        PaletteType.RAINBOW: cv2.COLORMAP_RAINBOW,
        PaletteType.COOL_HOT: cv2.COLORMAP_JET,
        PaletteType.WHITE_HOT: cv2.COLORMAP_BONE,
        PaletteType.MEDICAL: cv2.COLORMAP_HOT,
    }

    def __init__(self, config: Optional[Dict] = None):
        """
        Initialize palette manager.

        Args:
            config: Configuration dictionary
        """
        self.config = config or {}

        # Global default palette
        self.global_palette = PaletteConfig(
            palette_type=PaletteType(self.config.get("default_palette", "white_hot")),
            auto_contrast=self.config.get("auto_contrast", True),
            gamma=self.config.get("gamma", 1.0)
        )

        # Per-ROI palette overrides: roi_id -> PaletteConfig
        self.roi_palettes: Dict[str, PaletteConfig] = {}

        # Cache for custom palette LUTs
        self.palette_cache: Dict[PaletteType, np.ndarray] = {}

        # Initialize custom palettes
        self._init_custom_palettes()

    def _init_custom_palettes(self):
        """Initialize custom palette lookup tables."""

        # BLACK_HOT - inverted grayscale
        self.palette_cache[PaletteType.BLACK_HOT] = self._create_gradient_palette(
            [(0, 0, 0), (255, 255, 255)]
        )

        # IRONBOW - iron color scheme (black -> purple -> red -> orange -> yellow -> white)
        self.palette_cache[PaletteType.IRONBOW] = self._create_gradient_palette([
            (0, 0, 0),      # Black
            (0, 0, 128),    # Dark blue
            (128, 0, 128),  # Purple
            (255, 0, 0),    # Red
            (255, 128, 0),  # Orange
            (255, 255, 0),  # Yellow
            (255, 255, 255) # White
        ])

        # RAINBOW_HC - high contrast rainbow
        self.palette_cache[PaletteType.RAINBOW_HC] = self._create_gradient_palette([
            (0, 0, 255),    # Blue
            (0, 255, 255),  # Cyan
            (0, 255, 0),    # Green
            (255, 255, 0),  # Yellow
            (255, 128, 0),  # Orange
            (255, 0, 0)     # Red
        ])

        # FUSION - blue to red through purple
        self.palette_cache[PaletteType.FUSION] = self._create_gradient_palette([
            (0, 0, 255),    # Blue
            (128, 0, 255),  # Purple
            (255, 0, 128),  # Pink
            (255, 0, 0)     # Red
        ])

        # LAVA - black -> red -> orange -> yellow -> white
        self.palette_cache[PaletteType.LAVA] = self._create_gradient_palette([
            (0, 0, 0),      # Black
            (128, 0, 0),    # Dark red
            (255, 0, 0),    # Red
            (255, 128, 0),  # Orange
            (255, 255, 0),  # Yellow
            (255, 255, 255) # White
        ])

        # ARCTIC - white -> cyan -> blue -> dark blue
        self.palette_cache[PaletteType.ARCTIC] = self._create_gradient_palette([
            (255, 255, 255), # White
            (128, 255, 255), # Light cyan
            (0, 255, 255),   # Cyan
            (0, 128, 255),   # Light blue
            (0, 0, 255),     # Blue
            (0, 0, 128)      # Dark blue
        ])

        # GLOBOW - green -> yellow -> orange -> red
        self.palette_cache[PaletteType.GLOBOW] = self._create_gradient_palette([
            (0, 255, 0),    # Green
            (128, 255, 0),  # Yellow-green
            (255, 255, 0),  # Yellow
            (255, 128, 0),  # Orange
            (255, 0, 0)     # Red
        ])

        # GRADEDFIRE - sophisticated fire palette
        self.palette_cache[PaletteType.GRADEDFIRE] = self._create_gradient_palette([
            (0, 0, 0),      # Black
            (64, 0, 0),     # Very dark red
            (128, 0, 0),    # Dark red
            (255, 0, 0),    # Red
            (255, 64, 0),   # Red-orange
            (255, 128, 0),  # Orange
            (255, 192, 0),  # Yellow-orange
            (255, 255, 0),  # Yellow
            (255, 255, 128),# Light yellow
            (255, 255, 255) # White
        ])

        # HOTTEST - extreme hot palette (purple -> red -> yellow -> white)
        self.palette_cache[PaletteType.HOTTEST] = self._create_gradient_palette([
            (128, 0, 128),  # Purple
            (255, 0, 128),  # Magenta
            (255, 0, 0),    # Red
            (255, 128, 0),  # Orange
            (255, 255, 0),  # Yellow
            (255, 255, 255) # White
        ])

        # BLUE_RED - blue -> white -> red (diverging)
        self.palette_cache[PaletteType.BLUE_RED] = self._create_gradient_palette([
            (0, 0, 255),    # Blue
            (128, 128, 255),# Light blue
            (255, 255, 255),# White
            (255, 128, 128),# Light red
            (255, 0, 0)     # Red
        ])

        # ===== NEW GRAYSCALE PALETTES =====
        # GRAY - pure grayscale
        self.palette_cache[PaletteType.GRAY] = self._create_gradient_palette([
            (0, 0, 0),      # Black
            (255, 255, 255) # White
        ])

        # SEPIA - warm sepia tones
        self.palette_cache[PaletteType.SEPIA] = self._create_gradient_palette([
            (20, 15, 10),    # Very dark brown
            (60, 50, 40),    # Dark brown
            (112, 66, 20),   # Sepia brown
            (156, 102, 50),  # Light sepia
            (204, 160, 116), # Beige
            (240, 220, 195)  # Light beige
        ])

        # ===== NEW FIRE/HEAT PALETTES =====
        # AMBER - firefighting visualization
        self.palette_cache[PaletteType.AMBER] = self._create_gradient_palette([
            (0, 0, 0),       # Black
            (0, 32, 64),     # Very dark amber
            (0, 64, 128),    # Dark amber
            (0, 128, 192),   # Amber
            (0, 192, 255),   # Light amber
            (128, 224, 255), # Very light amber
            (255, 255, 255)  # White
        ])

        # INFERNO - perceptually uniform fire (matplotlib)
        self.palette_cache[PaletteType.INFERNO] = self._create_gradient_palette([
            (0, 0, 4),       # Almost black
            (40, 11, 84),    # Dark purple
            (101, 21, 110),  # Purple
            (159, 42, 99),   # Magenta
            (212, 72, 66),   # Red-orange
            (245, 125, 21),  # Orange
            (252, 206, 37),  # Yellow
            (252, 255, 164)  # Light yellow
        ])

        # ===== NEW RAINBOW PALETTES =====
        # RAINBOW_REVERSED - cold to hot
        self.palette_cache[PaletteType.RAINBOW_REVERSED] = self._create_gradient_palette([
            (255, 0, 0),     # Red
            (255, 128, 0),   # Orange
            (255, 255, 0),   # Yellow
            (0, 255, 0),     # Green
            (0, 255, 255),   # Cyan
            (0, 0, 255)      # Blue
        ])

        # SPECTRAL - spectral colors
        self.palette_cache[PaletteType.SPECTRAL] = self._create_gradient_palette([
            (158, 1, 66),    # Dark red
            (213, 62, 79),   # Red
            (244, 109, 67),  # Orange
            (253, 174, 97),  # Light orange
            (254, 224, 139), # Yellow
            (230, 245, 152), # Yellow-green
            (171, 221, 164), # Light green
            (102, 194, 165), # Green
            (50, 136, 189),  # Blue
            (94, 79, 162)    # Dark blue
        ])

        # ===== NEW COLD/ARCTIC PALETTES =====
        # ICE - light to dark blue
        self.palette_cache[PaletteType.ICE] = self._create_gradient_palette([
            (255, 255, 255), # White
            (224, 255, 255), # Very light blue
            (192, 240, 255), # Light blue
            (128, 200, 255), # Medium blue
            (64, 128, 192),  # Blue
            (0, 64, 128),    # Dark blue
            (0, 0, 64)       # Very dark blue
        ])

        # WINTER - blue-cyan-green cold
        self.palette_cache[PaletteType.WINTER] = self._create_gradient_palette([
            (0, 0, 255),     # Blue
            (0, 64, 255),    # Blue-cyan
            (0, 128, 255),   # Cyan-blue
            (0, 192, 255),   # Light cyan
            (0, 255, 192),   # Cyan-green
            (0, 255, 128)    # Green-cyan
        ])

        # OCEAN - ocean depths
        self.palette_cache[PaletteType.OCEAN] = self._create_gradient_palette([
            (0, 0, 0),       # Black (deep ocean)
            (0, 0, 64),      # Very dark blue
            (0, 32, 96),     # Dark blue
            (0, 64, 128),    # Blue
            (0, 96, 160),    # Medium blue
            (32, 128, 192),  # Light blue
            (64, 192, 224)   # Cyan-blue
        ])

        # ===== PERCEPTUALLY UNIFORM (Scientific) =====
        # VIRIDIS - yellow-green-blue (matplotlib default)
        self.palette_cache[PaletteType.VIRIDIS] = self._create_gradient_palette([
            (68, 1, 84),     # Dark purple
            (71, 44, 122),   # Purple
            (59, 82, 139),   # Blue-purple
            (44, 113, 142),  # Blue
            (33, 145, 140),  # Cyan-green
            (39, 173, 129),  # Green
            (92, 200, 99),   # Light green
            (170, 220, 50),  # Yellow-green
            (253, 231, 37)   # Yellow
        ])

        # PLASMA - purple-red-orange-yellow
        self.palette_cache[PaletteType.PLASMA] = self._create_gradient_palette([
            (13, 8, 135),    # Dark blue-purple
            (75, 3, 161),    # Purple
            (125, 3, 168),   # Magenta
            (168, 34, 150),  # Pink-magenta
            (203, 70, 121),  # Pink
            (229, 107, 93),  # Orange-pink
            (248, 148, 65),  # Orange
            (253, 195, 40),  # Yellow-orange
            (252, 255, 164)  # Light yellow
        ])

        # MAGMA - black-purple-red-yellow
        self.palette_cache[PaletteType.MAGMA] = self._create_gradient_palette([
            (0, 0, 4),       # Almost black
            (28, 16, 68),    # Dark purple
            (79, 18, 123),   # Purple
            (129, 37, 129),  # Magenta
            (181, 54, 122),  # Pink-magenta
            (229, 80, 100),  # Pink-red
            (251, 136, 97),  # Orange
            (254, 194, 135), # Yellow-orange
            (252, 253, 191)  # Light yellow
        ])

        # CIVIDIS - colorblind-friendly blue-yellow
        self.palette_cache[PaletteType.CIVIDIS] = self._create_gradient_palette([
            (0, 32, 76),     # Dark blue
            (0, 50, 105),    # Blue
            (32, 69, 121),   # Medium blue
            (70, 88, 126),   # Blue-gray
            (108, 107, 122), # Gray-blue
            (145, 126, 111), # Beige
            (184, 147, 96),  # Yellow-beige
            (222, 173, 81),  # Yellow
            (253, 208, 87)   # Light yellow
        ])

        # TURBO - improved rainbow
        self.palette_cache[PaletteType.TURBO] = self._create_gradient_palette([
            (48, 18, 59),    # Dark purple
            (71, 40, 120),   # Purple
            (87, 72, 174),   # Blue-purple
            (87, 117, 207),  # Blue
            (70, 163, 225),  # Light blue
            (53, 207, 225),  # Cyan
            (66, 245, 197),  # Green-cyan
            (122, 255, 149), # Green
            (184, 248, 94),  # Yellow-green
            (243, 219, 49),  # Yellow
            (253, 169, 41),  # Orange
            (244, 107, 46),  # Red-orange
            (215, 48, 39)    # Red
        ])

        # ===== DIVERGING PALETTES =====
        # COOL_WARM - blue-gray-red
        self.palette_cache[PaletteType.COOL_WARM] = self._create_gradient_palette([
            (59, 76, 192),   # Blue
            (120, 150, 220), # Light blue
            (180, 180, 180), # Gray
            (220, 150, 120), # Light red
            (192, 76, 59)    # Red
        ])

        # PURPLE_ORANGE - purple-white-orange
        self.palette_cache[PaletteType.PURPLE_ORANGE] = self._create_gradient_palette([
            (128, 0, 128),   # Purple
            (180, 100, 200), # Light purple
            (255, 255, 255), # White
            (255, 200, 100), # Light orange
            (255, 128, 0)    # Orange
        ])

        # GREEN_RED - traffic light style
        self.palette_cache[PaletteType.GREEN_RED] = self._create_gradient_palette([
            (0, 255, 0),     # Green
            (128, 255, 128), # Light green
            (255, 255, 255), # White
            (255, 128, 128), # Light red
            (255, 0, 0)      # Red
        ])

        # BLUE_YELLOW - blue-white-yellow
        self.palette_cache[PaletteType.BLUE_YELLOW] = self._create_gradient_palette([
            (255, 0, 0),     # Blue (BGR!)
            (255, 128, 128), # Light blue
            (255, 255, 255), # White
            (128, 255, 255), # Light yellow
            (0, 255, 255)    # Yellow
        ])

        # PINK_GREEN - pink-white-green
        self.palette_cache[PaletteType.PINK_GREEN] = self._create_gradient_palette([
            (203, 24, 213),  # Pink
            (230, 140, 240), # Light pink
            (255, 255, 255), # White
            (140, 240, 140), # Light green
            (24, 213, 24)    # Green
        ])

        # ===== SEQUENTIAL PALETTES =====
        # THERMAL - thermal-optimized sequential
        self.palette_cache[PaletteType.THERMAL] = self._create_gradient_palette([
            (0, 0, 0),       # Black
            (0, 0, 128),     # Dark blue
            (0, 128, 128),   # Cyan
            (0, 255, 128),   # Green-cyan
            (128, 255, 0),   # Yellow-green
            (255, 255, 0),   # Yellow
            (255, 128, 0),   # Orange
            (255, 0, 0),     # Red
            (255, 255, 255)  # White
        ])

        # HELIX - spiral through color space
        self.palette_cache[PaletteType.HELIX] = self._create_gradient_palette([
            (0, 0, 0),       # Black
            (64, 0, 128),    # Purple
            (0, 64, 192),    # Blue
            (0, 192, 128),   # Cyan-green
            (192, 192, 0),   # Yellow
            (255, 128, 0),   # Orange
            (255, 255, 255)  # White
        ])

        # CUBEHELIX - perceptually uniform helix
        self.palette_cache[PaletteType.CUBEHELIX] = self._create_gradient_palette([
            (0, 0, 0),       # Black
            (26, 10, 53),    # Dark purple
            (39, 40, 89),    # Blue-purple
            (38, 79, 102),   # Blue
            (47, 117, 96),   # Cyan
            (89, 148, 91),   # Green
            (154, 169, 109), # Yellow-green
            (214, 187, 150), # Beige
            (255, 210, 220)  # Light pink
        ])

        # TWILIGHT - cyclic twilight
        self.palette_cache[PaletteType.TWILIGHT] = self._create_gradient_palette([
            (226, 217, 226), # Light pink
            (172, 151, 206), # Purple
            (109, 103, 187), # Dark purple
            (72, 90, 166),   # Blue
            (88, 134, 161),  # Cyan-blue
            (147, 175, 163), # Green-blue
            (206, 202, 175), # Beige
            (240, 216, 195), # Light beige
            (226, 217, 226)  # Light pink (cyclic)
        ])

        # DUSK - warm sequential
        self.palette_cache[PaletteType.DUSK] = self._create_gradient_palette([
            (0, 0, 16),      # Almost black
            (32, 16, 64),    # Dark purple
            (96, 32, 96),    # Purple
            (160, 64, 96),   # Magenta
            (224, 128, 64),  # Orange
            (255, 192, 96),  # Light orange
            (255, 240, 192)  # Very light
        ])

        # ===== SPECIALIZED/INDUSTRIAL =====
        # PRISM - multi-color prism
        self.palette_cache[PaletteType.PRISM] = self._create_gradient_palette([
            (255, 0, 0),     # Red
            (255, 128, 0),   # Orange
            (255, 255, 0),   # Yellow
            (0, 255, 0),     # Green
            (0, 255, 255),   # Cyan
            (0, 0, 255),     # Blue
            (128, 0, 255),   # Purple
            (255, 0, 255)    # Magenta
        ])

        # ALARM - high contrast alarm
        self.palette_cache[PaletteType.ALARM] = self._create_gradient_palette([
            (0, 0, 255),     # Blue (safe)
            (0, 255, 0),     # Green (normal)
            (255, 255, 0),   # Yellow (caution)
            (255, 128, 0),   # Orange (warning)
            (255, 0, 0),     # Red (alarm)
            (255, 0, 255)    # Magenta (critical)
        ])

        # LAPLACIAN - edge-enhanced
        self.palette_cache[PaletteType.LAPLACIAN] = self._create_gradient_palette([
            (0, 0, 128),     # Dark blue (negative)
            (0, 128, 255),   # Blue
            (255, 255, 255), # White (zero)
            (255, 128, 0),   # Orange
            (128, 0, 0)      # Dark red (positive)
        ])

        # ISOTHERM - discrete bands
        self.palette_cache[PaletteType.ISOTHERM] = self._create_gradient_palette([
            (0, 0, 128),     # Dark blue
            (0, 128, 255),   # Blue
            (0, 255, 255),   # Cyan
            (0, 255, 0),     # Green
            (255, 255, 0),   # Yellow
            (255, 128, 0),   # Orange
            (255, 0, 0)      # Red
        ])

        # VELOCITY - flow visualization
        self.palette_cache[PaletteType.VELOCITY] = self._create_gradient_palette([
            (0, 0, 255),     # Blue (slow)
            (0, 128, 255),   # Light blue
            (0, 255, 128),   # Cyan-green
            (128, 255, 0),   # Yellow-green
            (255, 255, 0),   # Yellow
            (255, 128, 0),   # Orange
            (255, 0, 0)      # Red (fast)
        ])

        # TERRAIN - elevation-like
        self.palette_cache[PaletteType.TERRAIN] = self._create_gradient_palette([
            (0, 0, 128),     # Dark blue (water)
            (0, 128, 192),   # Blue (shallow)
            (192, 192, 128), # Beige (beach)
            (0, 128, 0),     # Green (lowland)
            (128, 192, 64),  # Yellow-green (hills)
            (192, 128, 64),  # Brown (mountains)
            (255, 255, 255)  # White (peaks)
        ])

        # DEPTH - depth perception
        self.palette_cache[PaletteType.DEPTH] = self._create_gradient_palette([
            (64, 0, 0),      # Dark red (far)
            (128, 32, 0),    # Brown-red
            (192, 96, 32),   # Brown
            (224, 160, 64),  # Light brown
            (240, 224, 128), # Beige
            (255, 255, 192), # Light beige
            (255, 255, 255)  # White (near)
        ])

    def _create_gradient_palette(self, colors: List[Tuple[int, int, int]]) -> np.ndarray:
        """
        Create a 256-entry color palette from gradient control points.

        Args:
            colors: List of BGR tuples defining gradient stops

        Returns:
            256x3 numpy array (BGR color palette)
        """
        if len(colors) < 2:
            # Default to grayscale
            return np.array([[i, i, i] for i in range(256)], dtype=np.uint8)

        palette = np.zeros((256, 3), dtype=np.uint8)

        # Distribute colors evenly across 256 values
        num_segments = len(colors) - 1
        segment_size = 256 // num_segments

        for i in range(num_segments):
            start_idx = i * segment_size
            end_idx = (i + 1) * segment_size if i < num_segments - 1 else 256

            start_color = np.array(colors[i], dtype=np.float32)
            end_color = np.array(colors[i + 1], dtype=np.float32)

            for j in range(start_idx, end_idx):
                alpha = (j - start_idx) / (end_idx - start_idx)
                palette[j] = (start_color * (1 - alpha) + end_color * alpha).astype(np.uint8)

        return palette

    def _apply_contrast(self, image: np.ndarray, config: PaletteConfig) -> np.ndarray:
        """
        Apply contrast adjustment to image.

        Args:
            image: Grayscale image
            config: Palette configuration

        Returns:
            Contrast-adjusted image
        """
        if config.auto_contrast:
            # Auto-contrast stretch to full range
            min_val = np.min(image)
            max_val = np.max(image)

            if max_val > min_val:
                image = ((image - min_val) / (max_val - min_val) * 255).astype(np.uint8)
        else:
            # Manual contrast adjustment
            min_val = config.contrast_min * 255
            max_val = config.contrast_max * 255

            image = np.clip(image, min_val, max_val)
            if max_val > min_val:
                image = ((image - min_val) / (max_val - min_val) * 255).astype(np.uint8)

        return image

    def _apply_gamma(self, image: np.ndarray, gamma: float) -> np.ndarray:
        """
        Apply gamma correction.

        Args:
            image: Grayscale image
            gamma: Gamma value (1.0 = no change)

        Returns:
            Gamma-corrected image
        """
        if gamma == 1.0:
            return image

        # Build gamma lookup table
        inv_gamma = 1.0 / gamma
        lut = np.array([((i / 255.0) ** inv_gamma) * 255 for i in range(256)], dtype=np.uint8)

        return cv2.LUT(image, lut)

    def apply_palette(self, thermal_frame: np.ndarray,
                     palette_config: Optional[PaletteConfig] = None) -> np.ndarray:
        """
        Apply a color palette to thermal frame.

        Args:
            thermal_frame: Grayscale thermal image
            palette_config: Palette configuration (uses global if None)

        Returns:
            Colorized thermal image (BGR)
        """
        if thermal_frame is None or thermal_frame.size == 0:
            return thermal_frame

        config = palette_config if palette_config is not None else self.global_palette

        # Ensure grayscale
        if len(thermal_frame.shape) == 3:
            thermal_gray = cv2.cvtColor(thermal_frame, cv2.COLOR_BGR2GRAY)
        else:
            thermal_gray = thermal_frame.copy()

        # Apply contrast adjustment
        thermal_adjusted = self._apply_contrast(thermal_gray, config)

        # Apply gamma correction
        thermal_adjusted = self._apply_gamma(thermal_adjusted, config.gamma)

        # Invert if needed
        if config.invert:
            thermal_adjusted = 255 - thermal_adjusted

        # Apply color palette
        palette_type = config.palette_type

        if palette_type in self.OPENCV_COLORMAPS:
            # Use OpenCV built-in colormap
            colorized = cv2.applyColorMap(thermal_adjusted, self.OPENCV_COLORMAPS[palette_type])
        elif palette_type in self.palette_cache:
            # Use custom palette
            lut = self.palette_cache[palette_type]
            colorized = cv2.LUT(thermal_adjusted, lut)
        else:
            # Fallback to white_hot (grayscale)
            colorized = cv2.cvtColor(thermal_adjusted, cv2.COLOR_GRAY2BGR)

        return colorized

    def apply_composite_palette(self, thermal_frame: np.ndarray,
                               roi_manager) -> np.ndarray:
        """
        Apply composite palette (global + ROI overrides).

        Args:
            thermal_frame: Grayscale thermal image
            roi_manager: ROIManager instance with active ROIs

        Returns:
            Colorized thermal image with ROI-specific palettes
        """
        if thermal_frame is None or thermal_frame.size == 0:
            return thermal_frame

        # Start with global palette
        output = self.apply_palette(thermal_frame, self.global_palette)

        # Apply ROI-specific palettes
        for roi_id, palette_config in self.roi_palettes.items():
            roi = roi_manager.get_roi(roi_id)
            if roi is None or not roi.active:
                continue

            # Get ROI mask
            mask = roi.get_mask(thermal_frame.shape)
            if mask is None or np.sum(mask) == 0:
                continue

            # Apply palette to ROI region
            roi_colorized = self.apply_palette(thermal_frame, palette_config)

            # Blend ROI palette onto output
            mask_3ch = cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR)
            output = np.where(mask_3ch > 0, roi_colorized, output)

        return output

    def set_global_palette(self, palette_type: PaletteType, **kwargs):
        """
        Set global default palette.

        Args:
            palette_type: Palette type to use
            **kwargs: Additional palette configuration (auto_contrast, gamma, etc.)
        """
        self.global_palette.palette_type = palette_type

        for key, value in kwargs.items():
            if hasattr(self.global_palette, key):
                setattr(self.global_palette, key, value)

    def set_roi_palette(self, roi_id: str, palette_type: PaletteType, **kwargs):
        """
        Set palette override for a specific ROI.

        Args:
            roi_id: ROI identifier
            palette_type: Palette type to use
            **kwargs: Additional palette configuration
        """
        if roi_id not in self.roi_palettes:
            self.roi_palettes[roi_id] = PaletteConfig(palette_type=palette_type)
        else:
            self.roi_palettes[roi_id].palette_type = palette_type

        for key, value in kwargs.items():
            if hasattr(self.roi_palettes[roi_id], key):
                setattr(self.roi_palettes[roi_id], key, value)

    def clear_roi_palette(self, roi_id: str):
        """Remove palette override for an ROI."""
        if roi_id in self.roi_palettes:
            del self.roi_palettes[roi_id]

    def clear_all_roi_palettes(self):
        """Clear all ROI palette overrides."""
        self.roi_palettes.clear()

    def get_global_palette(self) -> PaletteConfig:
        """Get global palette configuration."""
        return self.global_palette

    def get_roi_palette(self, roi_id: str) -> Optional[PaletteConfig]:
        """Get palette configuration for a specific ROI."""
        return self.roi_palettes.get(roi_id)

    def has_roi_palette(self, roi_id: str) -> bool:
        """Check if an ROI has a palette override."""
        return roi_id in self.roi_palettes

    def get_available_palettes(self) -> List[str]:
        """Get list of available palette names."""
        return [p.value for p in PaletteType]

    def save_palette_config(self, filepath: str):
        """
        Save palette configuration to JSON.

        Args:
            filepath: Path to save file
        """
        config = {
            "global_palette": {
                "palette_type": self.global_palette.palette_type.value,
                "auto_contrast": self.global_palette.auto_contrast,
                "contrast_min": self.global_palette.contrast_min,
                "contrast_max": self.global_palette.contrast_max,
                "gamma": self.global_palette.gamma,
                "invert": self.global_palette.invert
            },
            "roi_palettes": {}
        }

        for roi_id, palette_config in self.roi_palettes.items():
            config["roi_palettes"][roi_id] = {
                "palette_type": palette_config.palette_type.value,
                "auto_contrast": palette_config.auto_contrast,
                "contrast_min": palette_config.contrast_min,
                "contrast_max": palette_config.contrast_max,
                "gamma": palette_config.gamma,
                "invert": palette_config.invert
            }

        with open(filepath, 'w') as f:
            json.dump(config, f, indent=2)

    def load_palette_config(self, filepath: str):
        """
        Load palette configuration from JSON.

        Args:
            filepath: Path to load file
        """
        with open(filepath, 'r') as f:
            config = json.load(f)

        # Load global palette
        global_config = config.get("global_palette", {})
        self.global_palette = PaletteConfig(
            palette_type=PaletteType(global_config.get("palette_type", "white_hot")),
            auto_contrast=global_config.get("auto_contrast", True),
            contrast_min=global_config.get("contrast_min", 0.0),
            contrast_max=global_config.get("contrast_max", 1.0),
            gamma=global_config.get("gamma", 1.0),
            invert=global_config.get("invert", False)
        )

        # Load ROI palettes
        self.roi_palettes.clear()
        for roi_id, roi_config in config.get("roi_palettes", {}).items():
            self.roi_palettes[roi_id] = PaletteConfig(
                palette_type=PaletteType(roi_config.get("palette_type", "white_hot")),
                auto_contrast=roi_config.get("auto_contrast", True),
                contrast_min=roi_config.get("contrast_min", 0.0),
                contrast_max=roi_config.get("contrast_max", 1.0),
                gamma=roi_config.get("gamma", 1.0),
                invert=roi_config.get("invert", False)
            )

    def create_palette_preview(self, palette_type: PaletteType,
                              width: int = 256, height: int = 50) -> np.ndarray:
        """
        Create a preview image of a palette.

        Args:
            palette_type: Palette to preview
            width: Preview width
            height: Preview height

        Returns:
            Preview image (BGR)
        """
        # Create gradient from 0 to 255
        gradient = np.tile(np.linspace(0, 255, width, dtype=np.uint8), (height, 1))

        # Apply palette
        config = PaletteConfig(palette_type=palette_type, auto_contrast=False)
        preview = self.apply_palette(gradient, config)

        return preview
