"""
Palette Manager for Multi-Palette Thermal Inspection
Manages global and per-ROI color palettes for thermal visualization.
"""

import numpy as np
import cv2
from typing import Dict, List, Optional, Tuple
from enum import Enum
from dataclasses import dataclass
import json
import logging

logger = logging.getLogger(__name__)


def is_camera_native_colorized(frame: np.ndarray) -> bool:
    """
    True when frame is already a genuine, camera-produced false-color BGR
    image (e.g. a Tau2 breakout board with no CCI line - it can't be
    commanded into a raw/grayscale output mode, so this IS the
    display-ready image, the same feed Windows' own Camera app shows).

    Re-running such a frame through apply_composite_palette() would
    collapse it to grayscale (throwing away 2 of 3 real color channels)
    and recolor what's left with an unrelated palette. A camera whose
    channels are actually equal (grayscale replicated into BGR by the
    UVC layer, e.g. a non-radiometric Boson) still needs the normal
    palette path - that's what the channel-equality check excludes.

    Callers that also need to exclude a specific placeholder frame (the
    app's "no camera" filler image) should check that separately by
    identity - this function only classifies the frame's own content.
    """
    return bool(
        frame is not None
        and frame.dtype == np.uint8
        and frame.ndim == 3
        and frame.shape[2] == 3
        and not np.array_equal(frame[:, :, 0], frame[:, :, 1])
    )


class PaletteType(Enum):
    """Available thermal color palettes (115 total)."""

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

    # ===== ADDITIONAL PALETTES (12) =====
    GREEN_HOT = "green_hot"       # Black→green phosphor→white (night-vision style)
    RED_HOT = "red_hot"           # Black→deep red→red→pink→white (low-light friendly)
    COPPER = "copper"             # Black→copper→pale gold (single-hue, matplotlib)
    AFMHOT = "afmhot"             # Black→red→orange→white (matplotlib afmhot)
    GNUPLOT2 = "gnuplot2"         # Black→blue→magenta→red→yellow→white (matplotlib gnuplot2)
    YLORRD = "ylorrd"             # Pale yellow→orange→dark red (ColorBrewer YlOrRd)
    NIPY_SPECTRAL = "nipy_spectral"# Black→purple→blue→green→yellow→red→gray (matplotlib nipy_spectral)
    YLGNBU = "ylgnbu"             # Deep blue→green→pale yellow (ColorBrewer YlGnBu, reversed so hot is light)
    CMRMAP = "cmrmap"             # Perceptual, prints well in grayscale (matplotlib CMRmap)
    SEISMIC = "seismic"           # Dark blue→white→dark red (matplotlib seismic)
    RDYLBU = "rdylbu"             # Blue→pale yellow→red, cold to hot (ColorBrewer RdYlBu)
    BRBG = "brbg"                 # Brown→white→teal diverging (ColorBrewer BrBG)

    # ===== ADDITIONAL PALETTES, BATCH 2 (data in palette_stops.py) =====
    RAIN = "rain"
    CYAN_HOT = "cyan_hot"
    BLUE_HOT = "blue_hot"
    BANDED_HEAT = "banded_heat"
    BANDED_RAINBOW = "banded_rainbow"
    CC_FIRE = "cc_fire"
    CC_BMY = "cc_bmy"
    CC_KBC = "cc_kbc"
    CC_KGY = "cc_kgy"
    CC_ISOLUM = "cc_isolum"
    CC_RAINBOW = "cc_rainbow"
    CC_BGYW = "cc_bgyw"
    BATLOW = "batlow"
    LAJOLLA = "lajolla"
    LIPARI = "lipari"
    OSLO = "oslo"
    TURKU = "turku"
    HAWAII = "hawaii"
    ROMA = "roma"
    VIK = "vik"
    BERLIN = "berlin"
    ROCKET = "rocket"
    MAKO = "mako"
    FLARE = "flare"
    CREST = "crest"
    ICEFIRE = "icefire"
    TWILIGHT_SHIFTED = "twilight_shifted"
    COOL = "cool"
    WISTIA = "wistia"
    BONE = "bone"
    PINK = "pink"
    SUMMER = "summer"
    AUTUMN = "autumn"
    SPRING = "spring"
    GIST_HEAT = "gist_heat"
    GIST_EARTH = "gist_earth"
    GIST_RAINBOW = "gist_rainbow"
    GIST_STERN = "gist_stern"
    GIST_NCAR = "gist_ncar"
    BLUES = "blues"
    GREENS = "greens"
    ORANGES = "oranges"
    REDS = "reds"
    PURPLES = "purples"
    GREYS = "greys"
    YLORBR = "ylorbr"
    ORRD = "orrd"
    PURD = "purd"
    RDPU = "rdpu"
    BUPU = "bupu"
    GNBU = "gnbu"
    BUGN = "bugn"
    PUBU = "pubu"
    RDBU = "rdbu"
    RDGY = "rdgy"
    PIYG = "piyg"
    PRGN = "prgn"
    PUOR = "puor"


# Display grouping shared by every palette picker (global, per-ROI, menus), so a
# new palette only has to be listed once. Every PaletteType should appear exactly once.
PALETTE_CATEGORIES = [
    ("GRAYSCALE", [
        PaletteType.WHITE_HOT, PaletteType.BLACK_HOT, PaletteType.GRAY, PaletteType.SEPIA,
        PaletteType.GREEN_HOT, PaletteType.RED_HOT, PaletteType.COPPER,
    ]),
    ("IRON/FIRE", [
        PaletteType.IRONBOW, PaletteType.LAVA, PaletteType.GRADEDFIRE, PaletteType.HOTTEST,
        PaletteType.AMBER, PaletteType.INFERNO, PaletteType.AFMHOT, PaletteType.GNUPLOT2,
        PaletteType.YLORRD,
    ]),
    ("RAINBOW", [
        PaletteType.RAINBOW, PaletteType.RAINBOW_HC, PaletteType.RAINBOW_REVERSED,
        PaletteType.SPECTRAL, PaletteType.COOL_HOT, PaletteType.NIPY_SPECTRAL,
    ]),
    ("COLD/ARCTIC", [
        PaletteType.ARCTIC, PaletteType.ICE, PaletteType.WINTER, PaletteType.OCEAN,
        PaletteType.YLGNBU,
    ]),
    ("SCIENTIFIC", [
        PaletteType.VIRIDIS, PaletteType.PLASMA, PaletteType.MAGMA, PaletteType.CIVIDIS,
        PaletteType.TURBO, PaletteType.CMRMAP,
    ]),
    ("DIVERGING", [
        PaletteType.BLUE_RED, PaletteType.COOL_WARM, PaletteType.PURPLE_ORANGE,
        PaletteType.GREEN_RED, PaletteType.BLUE_YELLOW, PaletteType.PINK_GREEN,
        PaletteType.SEISMIC, PaletteType.RDYLBU, PaletteType.BRBG,
    ]),
    ("SEQUENTIAL", [
        PaletteType.GLOBOW, PaletteType.MEDICAL, PaletteType.THERMAL, PaletteType.HELIX,
        PaletteType.CUBEHELIX, PaletteType.TWILIGHT, PaletteType.DUSK,
    ]),
    ("SPECIALIZED", [
        PaletteType.FUSION, PaletteType.PRISM, PaletteType.ALARM, PaletteType.LAPLACIAN,
        PaletteType.ISOTHERM, PaletteType.VELOCITY, PaletteType.TERRAIN, PaletteType.DEPTH,
    ]),
]


# Batch-2 palettes join the categories above (new categories are appended)
_EXTRA_CATEGORY_MEMBERS = {
    "GRAYSCALE": [PaletteType.CYAN_HOT, PaletteType.BLUE_HOT, PaletteType.BONE, PaletteType.PINK],
    "IRON/FIRE": [PaletteType.CC_FIRE, PaletteType.LAJOLLA, PaletteType.ROCKET, PaletteType.FLARE, PaletteType.WISTIA, PaletteType.AUTUMN, PaletteType.GIST_HEAT, PaletteType.YLORBR, PaletteType.ORRD],
    "RAINBOW": [PaletteType.RAIN, PaletteType.CC_ISOLUM, PaletteType.CC_RAINBOW, PaletteType.HAWAII, PaletteType.GIST_RAINBOW, PaletteType.GIST_STERN, PaletteType.GIST_NCAR],
    "COLD/ARCTIC": [PaletteType.OSLO, PaletteType.MAKO, PaletteType.CREST, PaletteType.COOL, PaletteType.BUPU, PaletteType.GNBU, PaletteType.BUGN, PaletteType.PUBU],
    "SCIENTIFIC": [PaletteType.CC_BMY, PaletteType.CC_KBC, PaletteType.CC_KGY, PaletteType.CC_BGYW, PaletteType.BATLOW, PaletteType.LIPARI, PaletteType.TURKU, PaletteType.TWILIGHT_SHIFTED, PaletteType.SUMMER, PaletteType.SPRING],
    "DIVERGING": [PaletteType.ROMA, PaletteType.VIK, PaletteType.BERLIN, PaletteType.ICEFIRE, PaletteType.RDBU, PaletteType.RDGY, PaletteType.PIYG, PaletteType.PRGN, PaletteType.PUOR],
    "SINGLE-HUE": [PaletteType.GIST_EARTH, PaletteType.BLUES, PaletteType.GREENS, PaletteType.ORANGES, PaletteType.REDS, PaletteType.PURPLES, PaletteType.GREYS, PaletteType.PURD, PaletteType.RDPU],
    "BANDED": [PaletteType.BANDED_HEAT, PaletteType.BANDED_RAINBOW],
}
for _cat, _members in _EXTRA_CATEGORY_MEMBERS.items():
    for _entry in PALETTE_CATEGORIES:
        if _entry[0] == _cat:
            _entry[1].extend(_members)
            break
    else:
        PALETTE_CATEGORIES.append((_cat, list(_members)))


# Friendly names for palette pickers; PaletteType.value stays the internal ID
# (config, presets, CLI). Every PaletteType needs an entry.
PALETTE_DISPLAY_NAMES = {
    PaletteType.WHITE_HOT: "White Hot",
    PaletteType.BLACK_HOT: "Black Hot",
    PaletteType.GRAY: "Grayscale",
    PaletteType.SEPIA: "Sepia",
    PaletteType.GREEN_HOT: "Night Vision Green",
    PaletteType.RED_HOT: "Red Hot",
    PaletteType.COPPER: "Copper",
    PaletteType.IRONBOW: "Ironbow",
    PaletteType.LAVA: "Lava",
    PaletteType.GRADEDFIRE: "Graded Fire",
    PaletteType.HOTTEST: "Hottest",
    PaletteType.AMBER: "Amber",
    PaletteType.INFERNO: "Inferno",
    PaletteType.AFMHOT: "Hot Metal",
    PaletteType.GNUPLOT2: "Midnight Fire",
    PaletteType.YLORRD: "Sunrise",
    PaletteType.RAINBOW: "Rainbow",
    PaletteType.RAINBOW_HC: "Rainbow High Contrast",
    PaletteType.RAINBOW_REVERSED: "Rainbow Reversed",
    PaletteType.SPECTRAL: "Spectral",
    PaletteType.COOL_HOT: "Cool to Hot",
    PaletteType.NIPY_SPECTRAL: "Full Spectrum",
    PaletteType.ARCTIC: "Arctic",
    PaletteType.ICE: "Ice",
    PaletteType.WINTER: "Winter",
    PaletteType.OCEAN: "Ocean",
    PaletteType.YLGNBU: "Lagoon",
    PaletteType.VIRIDIS: "Viridis",
    PaletteType.PLASMA: "Plasma",
    PaletteType.MAGMA: "Magma",
    PaletteType.CIVIDIS: "Cividis (Colorblind-Safe)",
    PaletteType.TURBO: "Turbo",
    PaletteType.CMRMAP: "Perceptual Spectrum",
    PaletteType.BLUE_RED: "Blue – Red",
    PaletteType.COOL_WARM: "Cool – Warm",
    PaletteType.PURPLE_ORANGE: "Purple – Orange",
    PaletteType.GREEN_RED: "Green – Red",
    PaletteType.BLUE_YELLOW: "Blue – Yellow",
    PaletteType.PINK_GREEN: "Pink – Green",
    PaletteType.SEISMIC: "Seismic",
    PaletteType.RDYLBU: "Cold to Hot (Blue-Yellow-Red)",
    PaletteType.BRBG: "Brown – Teal",
    PaletteType.GLOBOW: "Globow",
    PaletteType.MEDICAL: "Medical",
    PaletteType.THERMAL: "Thermal",
    PaletteType.HELIX: "Helix",
    PaletteType.CUBEHELIX: "Cubehelix",
    PaletteType.TWILIGHT: "Twilight",
    PaletteType.DUSK: "Dusk",
    PaletteType.FUSION: "Fusion",
    PaletteType.PRISM: "Prism",
    PaletteType.ALARM: "Alarm",
    PaletteType.LAPLACIAN: "Edge Enhance",
    PaletteType.ISOTHERM: "Isotherm Bands",
    PaletteType.VELOCITY: "Velocity",
    PaletteType.TERRAIN: "Terrain",
    PaletteType.DEPTH: "Depth",
}

PALETTE_DISPLAY_NAMES.update({
    PaletteType.RAIN: "Rain",
    PaletteType.CYAN_HOT: "Cyan Hot",
    PaletteType.BLUE_HOT: "Blue Hot",
    PaletteType.BANDED_HEAT: "Banded Heat",
    PaletteType.BANDED_RAINBOW: "Banded Rainbow (High Contrast)",
    PaletteType.CC_FIRE: "Fire (Perceptual)",
    PaletteType.CC_BMY: "Blue–Magenta–Yellow",
    PaletteType.CC_KBC: "Black–Blue–Cyan",
    PaletteType.CC_KGY: "Black–Green–Yellow",
    PaletteType.CC_ISOLUM: "Isoluminant Rainbow",
    PaletteType.CC_RAINBOW: "Smooth Rainbow",
    PaletteType.CC_BGYW: "Blue–Green–Yellow–White",
    PaletteType.BATLOW: "Batlow",
    PaletteType.LAJOLLA: "La Jolla",
    PaletteType.LIPARI: "Lipari",
    PaletteType.OSLO: "Oslo",
    PaletteType.TURKU: "Turku",
    PaletteType.HAWAII: "Hawaii",
    PaletteType.ROMA: "Roma",
    PaletteType.VIK: "Vik",
    PaletteType.BERLIN: "Berlin",
    PaletteType.ROCKET: "Rocket",
    PaletteType.MAKO: "Mako",
    PaletteType.FLARE: "Flare",
    PaletteType.CREST: "Crest",
    PaletteType.ICEFIRE: "Icefire",
    PaletteType.TWILIGHT_SHIFTED: "Twilight Shifted",
    PaletteType.COOL: "Cyan–Magenta",
    PaletteType.WISTIA: "Golden",
    PaletteType.BONE: "Bone (X-Ray)",
    PaletteType.PINK: "Pink",
    PaletteType.SUMMER: "Summer",
    PaletteType.AUTUMN: "Autumn",
    PaletteType.SPRING: "Spring",
    PaletteType.GIST_HEAT: "Gist Heat",
    PaletteType.GIST_EARTH: "Earth",
    PaletteType.GIST_RAINBOW: "Gist Rainbow",
    PaletteType.GIST_STERN: "Stern",
    PaletteType.GIST_NCAR: "NCAR Spectrum",
    PaletteType.BLUES: "Blues",
    PaletteType.GREENS: "Greens",
    PaletteType.ORANGES: "Oranges",
    PaletteType.REDS: "Reds",
    PaletteType.PURPLES: "Purples",
    PaletteType.GREYS: "Grays",
    PaletteType.YLORBR: "Yellow–Orange–Brown",
    PaletteType.ORRD: "Orange–Red",
    PaletteType.PURD: "Purple–Red",
    PaletteType.RDPU: "Red–Purple",
    PaletteType.BUPU: "Blue–Purple",
    PaletteType.GNBU: "Green–Blue",
    PaletteType.BUGN: "Blue–Green",
    PaletteType.PUBU: "Purple–Blue",
    PaletteType.RDBU: "Deep Blue–Red",
    PaletteType.RDGY: "Gray–Red",
    PaletteType.PIYG: "Pink–Yellow–Green",
    PaletteType.PRGN: "Purple–Green",
    PaletteType.PUOR: "Deep Purple–Orange",
})


def palette_display_name(palette_type: PaletteType) -> str:
    """Friendly name for a palette (falls back to a tidied version of its ID)."""
    return PALETTE_DISPLAY_NAMES.get(palette_type, palette_type.value.replace("_", " ").title())


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

        # WHITE_HOT - standard grayscale (cold=black, hot=white)
        self.palette_cache[PaletteType.WHITE_HOT] = self._create_gradient_palette(
            [(0, 0, 0), (255, 255, 255)]
        )

        # BLACK_HOT - inverted grayscale (cold=white, hot=black)
        self.palette_cache[PaletteType.BLACK_HOT] = self._create_gradient_palette(
            [(255, 255, 255), (0, 0, 0)]
        )

        # IRONBOW - iron color scheme (black -> purple -> red -> orange -> yellow -> white)
        self.palette_cache[PaletteType.IRONBOW] = self._create_gradient_palette([
            (0, 0, 0),      # Black (BGR)
            (64, 0, 64),    # Dark purple (BGR)
            (128, 0, 128),  # Purple (BGR)
            (0, 0, 255),    # Red (BGR)
            (0, 128, 255),  # Orange (BGR)
            (0, 255, 255),  # Yellow (BGR)
            (255, 255, 255) # White (BGR)
        ])

        # RAINBOW_HC - high contrast rainbow
        self.palette_cache[PaletteType.RAINBOW_HC] = self._create_gradient_palette([
            (255, 0, 0),    # Blue (BGR)
            (255, 255, 0),  # Cyan (BGR)
            (0, 255, 0),    # Green (BGR)
            (0, 255, 255),  # Yellow (BGR)
            (0, 128, 255),  # Orange (BGR)
            (0, 0, 255)     # Red (BGR)
        ])

        # FUSION - blue to red through purple
        self.palette_cache[PaletteType.FUSION] = self._create_gradient_palette([
            (255, 0, 0),    # Blue (BGR)
            (255, 0, 128),  # Purple (BGR)
            (128, 0, 255),  # Pink (BGR)
            (0, 0, 255)     # Red (BGR)
        ])

        # LAVA - black -> red -> orange -> yellow -> white
        self.palette_cache[PaletteType.LAVA] = self._create_gradient_palette([
            (0, 0, 0),      # Black (BGR)
            (0, 0, 128),    # Dark red (BGR)
            (0, 0, 255),    # Red (BGR)
            (0, 128, 255),  # Orange (BGR)
            (0, 255, 255),  # Yellow (BGR)
            (255, 255, 255) # White (BGR)
        ])

        # ARCTIC - dark blue -> blue -> cyan -> white (cold to hot)
        self.palette_cache[PaletteType.ARCTIC] = self._create_gradient_palette([
            (128, 0, 0),     # Dark blue (BGR)
            (255, 0, 0),     # Blue (BGR)
            (255, 128, 0),   # Light blue (BGR)
            (255, 255, 0),   # Cyan (BGR)
            (255, 255, 128), # Light cyan (BGR)
            (255, 255, 255)  # White (BGR)
        ])

        # GLOBOW - green -> yellow -> orange -> red
        self.palette_cache[PaletteType.GLOBOW] = self._create_gradient_palette([
            (0, 255, 0),    # Green (BGR)
            (0, 255, 128),  # Yellow-green (BGR)
            (0, 255, 255),  # Yellow (BGR)
            (0, 128, 255),  # Orange (BGR)
            (0, 0, 255)     # Red (BGR)
        ])

        # GRADEDFIRE - sophisticated fire palette
        self.palette_cache[PaletteType.GRADEDFIRE] = self._create_gradient_palette([
            (0, 0, 0),      # Black (BGR)
            (0, 0, 64),     # Very dark red (BGR)
            (0, 0, 128),    # Dark red (BGR)
            (0, 0, 255),    # Red (BGR)
            (0, 64, 255),   # Red-orange (BGR)
            (0, 128, 255),  # Orange (BGR)
            (0, 192, 255),  # Yellow-orange (BGR)
            (0, 255, 255),  # Yellow (BGR)
            (128, 255, 255),# Light yellow (BGR)
            (255, 255, 255) # White (BGR)
        ])

        # HOTTEST - extreme hot palette (cold=black, hot=white through purple/red/yellow)
        self.palette_cache[PaletteType.HOTTEST] = self._create_gradient_palette([
            (0, 0, 0),      # Black (BGR)
            (64, 0, 64),    # Dark purple (BGR)
            (128, 0, 128),  # Purple (BGR)
            (0, 0, 255),    # Red (BGR)
            (0, 128, 255),  # Orange (BGR)
            (0, 255, 255),  # Yellow (BGR)
            (255, 255, 255) # White (BGR)
        ])

        # BLUE_RED - blue -> white -> red (diverging)
        self.palette_cache[PaletteType.BLUE_RED] = self._create_gradient_palette([
            (255, 0, 0),    # Blue (BGR)
            (255, 128, 128),# Light blue (BGR)
            (255, 255, 255),# White (BGR)
            (128, 128, 255),# Light red (BGR)
            (0, 0, 255)     # Red (BGR)
        ])

        # ===== NEW GRAYSCALE PALETTES =====
        # GRAY - pure grayscale
        self.palette_cache[PaletteType.GRAY] = self._create_gradient_palette([
            (0, 0, 0),      # Black (BGR)
            (255, 255, 255) # White (BGR)
        ])

        # SEPIA - warm sepia tones (cold=dark brown, hot=light beige)
        self.palette_cache[PaletteType.SEPIA] = self._create_gradient_palette([
            (10, 15, 20),    # Very dark brown (BGR: low blue, low green, low red)
            (40, 50, 60),    # Dark brown (BGR)
            (20, 66, 112),   # Sepia brown (BGR: low blue, moderate green, high red)
            (50, 102, 156),  # Light sepia (BGR)
            (116, 160, 204), # Beige (BGR)
            (195, 220, 240)  # Light beige (BGR)
        ])

        # ===== NEW FIRE/HEAT PALETTES =====
        # AMBER - firefighting visualization (cold=black, hot=bright amber)
        self.palette_cache[PaletteType.AMBER] = self._create_gradient_palette([
            (0, 0, 0),        # Black (BGR)
            (0, 32, 64),      # Very dark amber (BGR) - low B, low-med G, med R
            (0, 64, 128),     # Dark amber (BGR)
            (0, 128, 192),    # Amber (BGR) - orange tone
            (0, 192, 255),    # Light amber (BGR)
            (128, 224, 255),  # Very light amber (BGR)
            (255, 255, 255)   # White (BGR)
        ])

        # INFERNO - perceptually uniform fire (matplotlib)
        self.palette_cache[PaletteType.INFERNO] = self._create_gradient_palette([
            (4, 0, 0),       # Almost black (BGR)
            (84, 11, 40),    # Dark purple (BGR)
            (110, 21, 101),  # Purple (BGR)
            (99, 42, 159),   # Magenta (BGR)
            (66, 72, 212),   # Red-orange (BGR)
            (21, 125, 245),  # Orange (BGR)
            (37, 206, 252),  # Yellow (BGR)
            (164, 255, 252)  # Light yellow (BGR)
        ])

        # ===== NEW RAINBOW PALETTES =====
        # RAINBOW_REVERSED - hot to cold (red to blue) - REVERSED order
        self.palette_cache[PaletteType.RAINBOW_REVERSED] = self._create_gradient_palette([
            (0, 0, 255),     # Red (hot) (BGR)
            (0, 128, 255),   # Orange (BGR)
            (0, 255, 255),   # Yellow (BGR)
            (0, 255, 0),     # Green (BGR)
            (255, 255, 0),   # Cyan (BGR)
            (255, 0, 0)      # Blue (cold) (BGR)
        ])

        # SPECTRAL - spectral colors
        self.palette_cache[PaletteType.SPECTRAL] = self._create_gradient_palette([
            (66, 1, 158),    # Dark red (BGR)
            (79, 62, 213),   # Red (BGR)
            (67, 109, 244),  # Orange (BGR)
            (97, 174, 253),  # Light orange (BGR)
            (139, 224, 254), # Yellow (BGR)
            (152, 245, 230), # Yellow-green (BGR)
            (164, 221, 171), # Light green (BGR)
            (165, 194, 102), # Green (BGR)
            (189, 136, 50),  # Blue (BGR)
            (162, 79, 94)    # Dark blue (BGR)
        ])

        # ===== NEW COLD/ARCTIC PALETTES =====
        # ICE - dark to light blue (cold=dark blue, hot=white)
        self.palette_cache[PaletteType.ICE] = self._create_gradient_palette([
            (64, 0, 0),      # Very dark blue (BGR)
            (128, 64, 0),    # Dark blue (BGR)
            (192, 128, 64),  # Blue (BGR)
            (255, 200, 128), # Medium blue (BGR)
            (255, 240, 192), # Light blue (BGR)
            (255, 255, 224), # Very light blue (BGR)
            (255, 255, 255)  # White (BGR)
        ])

        # WINTER - blue to cyan to green (cold=dark, hot=light)
        self.palette_cache[PaletteType.WINTER] = self._create_gradient_palette([
            (128, 0, 0),     # Dark blue (BGR)
            (255, 0, 0),     # Blue (BGR)
            (255, 64, 0),    # Blue-cyan (BGR)
            (255, 128, 0),   # Cyan (BGR)
            (255, 192, 0),   # Light cyan (BGR)
            (192, 255, 0),   # Cyan-green (BGR)
            (128, 255, 64)   # Green (BGR)
        ])

        # OCEAN - ocean depths
        self.palette_cache[PaletteType.OCEAN] = self._create_gradient_palette([
            (0, 0, 0),       # Black (deep ocean) (BGR)
            (64, 0, 0),      # Very dark blue (BGR)
            (96, 32, 0),     # Dark blue (BGR)
            (128, 64, 0),    # Blue (BGR)
            (160, 96, 0),    # Medium blue (BGR)
            (192, 128, 32),  # Light blue (BGR)
            (224, 192, 64)   # Cyan-blue (BGR)
        ])

        # ===== PERCEPTUALLY UNIFORM (Scientific) =====
        # VIRIDIS - yellow-green-blue (matplotlib default)
        self.palette_cache[PaletteType.VIRIDIS] = self._create_gradient_palette([
            (84, 1, 68),     # Dark purple (BGR)
            (122, 44, 71),   # Purple (BGR)
            (139, 82, 59),   # Blue-purple (BGR)
            (142, 113, 44),  # Blue (BGR)
            (140, 145, 33),  # Cyan-green (BGR)
            (129, 173, 39),  # Green (BGR)
            (99, 200, 92),   # Light green (BGR)
            (50, 220, 170),  # Yellow-green (BGR)
            (37, 231, 253)   # Yellow (BGR)
        ])

        # PLASMA - purple-red-orange-yellow
        self.palette_cache[PaletteType.PLASMA] = self._create_gradient_palette([
            (135, 8, 13),    # Dark blue-purple (BGR)
            (161, 3, 75),    # Purple (BGR)
            (168, 3, 125),   # Magenta (BGR)
            (150, 34, 168),  # Pink-magenta (BGR)
            (121, 70, 203),  # Pink (BGR)
            (93, 107, 229),  # Orange-pink (BGR)
            (65, 148, 248),  # Orange (BGR)
            (40, 195, 253),  # Yellow-orange (BGR)
            (164, 255, 252)  # Light yellow (BGR)
        ])

        # MAGMA - black-purple-red-yellow
        self.palette_cache[PaletteType.MAGMA] = self._create_gradient_palette([
            (4, 0, 0),       # Almost black (BGR)
            (68, 16, 28),    # Dark purple (BGR)
            (123, 18, 79),   # Purple (BGR)
            (129, 37, 129),  # Magenta (BGR)
            (122, 54, 181),  # Pink-magenta (BGR)
            (100, 80, 229),  # Pink-red (BGR)
            (97, 136, 251),  # Orange (BGR)
            (135, 194, 254), # Yellow-orange (BGR)
            (191, 253, 252)  # Light yellow (BGR)
        ])

        # CIVIDIS - colorblind-friendly blue-yellow
        self.palette_cache[PaletteType.CIVIDIS] = self._create_gradient_palette([
            (76, 32, 0),     # Dark blue (BGR)
            (105, 50, 0),    # Blue (BGR)
            (121, 69, 32),   # Medium blue (BGR)
            (126, 88, 70),   # Blue-gray (BGR)
            (122, 107, 108), # Gray-blue (BGR)
            (111, 126, 145), # Beige (BGR)
            (96, 147, 184),  # Yellow-beige (BGR)
            (81, 173, 222),  # Yellow (BGR)
            (87, 208, 253)   # Light yellow (BGR)
        ])

        # TURBO - improved rainbow
        self.palette_cache[PaletteType.TURBO] = self._create_gradient_palette([
            (59, 18, 48),    # Dark purple (BGR)
            (120, 40, 71),   # Purple (BGR)
            (174, 72, 87),   # Blue-purple (BGR)
            (207, 117, 87),  # Blue (BGR)
            (225, 163, 70),  # Light blue (BGR)
            (225, 207, 53),  # Cyan (BGR)
            (197, 245, 66),  # Green-cyan (BGR)
            (149, 255, 122), # Green (BGR)
            (94, 248, 184),  # Yellow-green (BGR)
            (49, 219, 243),  # Yellow (BGR)
            (41, 169, 253),  # Orange (BGR)
            (46, 107, 244),  # Red-orange (BGR)
            (39, 48, 215)    # Red (BGR)
        ])

        # ===== DIVERGING PALETTES =====
        # COOL_WARM - blue-gray-red
        self.palette_cache[PaletteType.COOL_WARM] = self._create_gradient_palette([
            (192, 76, 59),   # Blue (BGR)
            (220, 150, 120), # Light blue (BGR)
            (180, 180, 180), # Gray (BGR)
            (120, 150, 220), # Light red (BGR)
            (59, 76, 192)    # Red (BGR)
        ])

        # PURPLE_ORANGE - purple-white-orange
        self.palette_cache[PaletteType.PURPLE_ORANGE] = self._create_gradient_palette([
            (128, 0, 128),   # Purple (BGR)
            (200, 100, 180), # Light purple (BGR)
            (255, 255, 255), # White (BGR)
            (100, 200, 255), # Light orange (BGR)
            (0, 128, 255)    # Orange (BGR)
        ])

        # GREEN_RED - traffic light style
        self.palette_cache[PaletteType.GREEN_RED] = self._create_gradient_palette([
            (0, 255, 0),     # Green (BGR)
            (128, 255, 128), # Light green (BGR)
            (255, 255, 255), # White (BGR)
            (128, 128, 255), # Light red (BGR)
            (0, 0, 255)      # Red (BGR)
        ])

        # BLUE_YELLOW - blue-white-yellow
        self.palette_cache[PaletteType.BLUE_YELLOW] = self._create_gradient_palette([
            (255, 0, 0),     # Blue (BGR)
            (255, 128, 128), # Light blue (BGR)
            (255, 255, 255), # White (BGR)
            (128, 255, 255), # Light yellow (BGR)
            (0, 255, 255)    # Yellow (BGR)
        ])

        # PINK_GREEN - pink-white-green
        self.palette_cache[PaletteType.PINK_GREEN] = self._create_gradient_palette([
            (213, 24, 203),  # Pink (BGR)
            (240, 140, 230), # Light pink (BGR)
            (255, 255, 255), # White (BGR)
            (140, 240, 140), # Light green (BGR)
            (24, 213, 24)    # Green (BGR)
        ])

        # ===== SEQUENTIAL PALETTES =====
        # THERMAL - thermal-optimized sequential
        self.palette_cache[PaletteType.THERMAL] = self._create_gradient_palette([
            (0, 0, 0),       # Black (BGR)
            (128, 0, 0),     # Dark blue (BGR)
            (128, 128, 0),   # Cyan (BGR)
            (128, 255, 0),   # Green-cyan (BGR)
            (0, 255, 128),   # Yellow-green (BGR)
            (0, 255, 255),   # Yellow (BGR)
            (0, 128, 255),   # Orange (BGR)
            (0, 0, 255),     # Red (BGR)
            (255, 255, 255)  # White (BGR)
        ])

        # HELIX - spiral through color space
        self.palette_cache[PaletteType.HELIX] = self._create_gradient_palette([
            (0, 0, 0),       # Black (BGR)
            (128, 0, 64),    # Purple (BGR)
            (192, 64, 0),    # Blue (BGR)
            (128, 192, 0),   # Cyan-green (BGR)
            (0, 192, 192),   # Yellow (BGR)
            (0, 128, 255),   # Orange (BGR)
            (255, 255, 255)  # White (BGR)
        ])

        # CUBEHELIX - perceptually uniform helix
        self.palette_cache[PaletteType.CUBEHELIX] = self._create_gradient_palette([
            (0, 0, 0),       # Black (BGR)
            (53, 10, 26),    # Dark purple (BGR)
            (89, 40, 39),    # Blue-purple (BGR)
            (102, 79, 38),   # Blue (BGR)
            (96, 117, 47),   # Cyan (BGR)
            (91, 148, 89),   # Green (BGR)
            (109, 169, 154), # Yellow-green (BGR)
            (150, 187, 214), # Beige (BGR)
            (220, 210, 255)  # Light pink (BGR)
        ])

        # TWILIGHT - cyclic twilight
        self.palette_cache[PaletteType.TWILIGHT] = self._create_gradient_palette([
            (226, 217, 226), # Light pink (BGR)
            (206, 151, 172), # Purple (BGR)
            (187, 103, 109), # Dark purple (BGR)
            (166, 90, 72),   # Blue (BGR)
            (161, 134, 88),  # Cyan-blue (BGR)
            (163, 175, 147), # Green-blue (BGR)
            (175, 202, 206), # Beige (BGR)
            (195, 216, 240), # Light beige (BGR)
            (226, 217, 226)  # Light pink (cyclic) (BGR)
        ])

        # DUSK - warm sequential
        self.palette_cache[PaletteType.DUSK] = self._create_gradient_palette([
            (16, 0, 0),      # Almost black (BGR)
            (64, 16, 32),    # Dark purple (BGR)
            (96, 32, 96),    # Purple (BGR)
            (96, 64, 160),   # Magenta (BGR)
            (64, 128, 224),  # Orange (BGR)
            (96, 192, 255),  # Light orange (BGR)
            (192, 240, 255)  # Very light (BGR)
        ])

        # ===== SPECIALIZED/INDUSTRIAL =====
        # PRISM - multi-color prism
        self.palette_cache[PaletteType.PRISM] = self._create_gradient_palette([
            (0, 0, 255),     # Red (BGR)
            (0, 128, 255),   # Orange (BGR)
            (0, 255, 255),   # Yellow (BGR)
            (0, 255, 0),     # Green (BGR)
            (255, 255, 0),   # Cyan (BGR)
            (255, 0, 0),     # Blue (BGR)
            (255, 0, 128),   # Purple (BGR)
            (255, 0, 255)    # Magenta (BGR)
        ])

        # ALARM - high contrast alarm
        self.palette_cache[PaletteType.ALARM] = self._create_gradient_palette([
            (255, 0, 0),     # Blue (safe) (BGR)
            (0, 255, 0),     # Green (normal) (BGR)
            (0, 255, 255),   # Yellow (caution) (BGR)
            (0, 128, 255),   # Orange (warning) (BGR)
            (0, 0, 255),     # Red (alarm) (BGR)
            (255, 0, 255)    # Magenta (critical) (BGR)
        ])

        # LAPLACIAN - edge-enhanced
        self.palette_cache[PaletteType.LAPLACIAN] = self._create_gradient_palette([
            (128, 0, 0),     # Dark blue (negative) (BGR)
            (255, 128, 0),   # Blue (BGR)
            (255, 255, 255), # White (zero) (BGR)
            (0, 128, 255),   # Orange (BGR)
            (0, 0, 128)      # Dark red (positive) (BGR)
        ])

        # ISOTHERM - discrete bands
        self.palette_cache[PaletteType.ISOTHERM] = self._create_gradient_palette([
            (128, 0, 0),     # Dark blue (BGR)
            (255, 128, 0),   # Blue (BGR)
            (255, 255, 0),   # Cyan (BGR)
            (0, 255, 0),     # Green (BGR)
            (0, 255, 255),   # Yellow (BGR)
            (0, 128, 255),   # Orange (BGR)
            (0, 0, 255)      # Red (BGR)
        ])

        # VELOCITY - flow visualization
        self.palette_cache[PaletteType.VELOCITY] = self._create_gradient_palette([
            (255, 0, 0),     # Blue (slow) (BGR)
            (255, 128, 0),   # Light blue (BGR)
            (128, 255, 0),   # Cyan-green (BGR)
            (0, 255, 128),   # Yellow-green (BGR)
            (0, 255, 255),   # Yellow (BGR)
            (0, 128, 255),   # Orange (BGR)
            (0, 0, 255)      # Red (fast) (BGR)
        ])

        # TERRAIN - elevation-like
        self.palette_cache[PaletteType.TERRAIN] = self._create_gradient_palette([
            (128, 0, 0),     # Dark blue (water) (BGR)
            (192, 128, 0),   # Blue (shallow) (BGR)
            (128, 192, 192), # Beige (beach) (BGR)
            (0, 128, 0),     # Green (lowland) (BGR)
            (64, 192, 128),  # Yellow-green (hills) (BGR)
            (64, 128, 192),  # Brown (mountains) (BGR)
            (255, 255, 255)  # White (peaks) (BGR)
        ])

        # DEPTH - depth perception
        self.palette_cache[PaletteType.DEPTH] = self._create_gradient_palette([
            (0, 0, 64),      # Dark red (far) (BGR)
            (0, 32, 128),    # Brown-red (BGR)
            (32, 96, 192),   # Brown (BGR)
            (64, 160, 224),  # Light brown (BGR)
            (128, 224, 240), # Beige (BGR)
            (192, 255, 255), # Light beige (BGR)
            (255, 255, 255)  # White (near) (BGR)
        ])

        # ===== ADDITIONAL PALETTES =====
        # GREEN_HOT - Black→green phosphor→white (night-vision style)
        self.palette_cache[PaletteType.GREEN_HOT] = self._create_gradient_palette([
            (0, 0, 0),
            (0, 40, 0),
            (0, 120, 20),
            (40, 220, 60),
            (170, 255, 170),
            (255, 255, 255)  # BGR stops
        ])

        # RED_HOT - Black→deep red→red→pink→white (low-light friendly)
        self.palette_cache[PaletteType.RED_HOT] = self._create_gradient_palette([
            (0, 0, 0),
            (0, 0, 110),
            (0, 0, 255),
            (120, 120, 255),
            (255, 255, 255)  # BGR stops
        ])

        # COPPER - Black→copper→pale gold (single-hue, matplotlib)
        self.palette_cache[PaletteType.COPPER] = self._create_gradient_palette([
            (0, 0, 0),
            (16, 25, 40),
            (32, 50, 79),
            (48, 75, 119),
            (64, 100, 158),
            (80, 125, 198),
            (96, 150, 237),
            (111, 175, 255),
            (127, 199, 255)  # BGR stops
        ])

        # AFMHOT - Black→red→orange→white (matplotlib afmhot)
        self.palette_cache[PaletteType.AFMHOT] = self._create_gradient_palette([
            (0, 0, 0),
            (0, 0, 64),
            (0, 0, 128),
            (0, 64, 192),
            (1, 128, 255),
            (65, 192, 255),
            (129, 255, 255),
            (193, 255, 255),
            (255, 255, 255)  # BGR stops
        ])

        # GNUPLOT2 - Black→blue→magenta→red→yellow→white (matplotlib gnuplot2)
        self.palette_cache[PaletteType.GNUPLOT2] = self._create_gradient_palette([
            (0, 0, 0),
            (100, 0, 0),
            (204, 0, 0),
            (255, 0, 38),
            (255, 0, 120),
            (213, 42, 201),
            (163, 92, 255),
            (111, 144, 255),
            (61, 194, 255),
            (9, 246, 255),
            (255, 255, 255)  # BGR stops
        ])

        # YLORRD - Pale yellow→orange→dark red (ColorBrewer YlOrRd)
        self.palette_cache[PaletteType.YLORRD] = self._create_gradient_palette([
            (204, 255, 255),
            (160, 237, 255),
            (118, 217, 254),
            (76, 178, 254),
            (60, 140, 253),
            (42, 77, 252),
            (28, 25, 226),
            (38, 0, 187),
            (38, 0, 128)  # BGR stops
        ])

        # NIPY_SPECTRAL - Black→purple→blue→green→yellow→red→gray (matplotlib nipy_spectral)
        self.palette_cache[PaletteType.NIPY_SPECTRAL] = self._create_gradient_palette([
            (0, 0, 0),
            (140, 0, 123),
            (162, 0, 67),
            (209, 0, 0),
            (221, 120, 0),
            (207, 158, 0),
            (152, 170, 0),
            (29, 157, 0),
            (0, 188, 0),
            (0, 231, 0),
            (0, 255, 103),
            (0, 241, 228),
            (0, 201, 255),
            (0, 105, 255),
            (0, 0, 236),
            (0, 0, 207),
            (204, 204, 204)  # BGR stops
        ])

        # YLGNBU - Deep blue→green→pale yellow (ColorBrewer YlGnBu, reversed so hot is light)
        self.palette_cache[PaletteType.YLGNBU] = self._create_gradient_palette([
            (88, 29, 8),
            (146, 51, 36),
            (168, 93, 34),
            (192, 144, 29),
            (196, 181, 64),
            (187, 205, 126),
            (180, 233, 198),
            (177, 248, 237),
            (217, 255, 255)  # BGR stops
        ])

        # CMRMAP - Perceptual, prints well in grayscale (matplotlib CMRmap)
        self.palette_cache[PaletteType.CMRMAP] = self._create_gradient_palette([
            (0, 0, 0),
            (100, 30, 30),
            (166, 38, 61),
            (167, 43, 106),
            (110, 54, 173),
            (38, 65, 255),
            (8, 115, 235),
            (16, 167, 230),
            (66, 207, 230),
            (155, 235, 235),
            (255, 255, 255)  # BGR stops
        ])

        # SEISMIC - Dark blue→white→dark red (matplotlib seismic)
        self.palette_cache[PaletteType.SEISMIC] = self._create_gradient_palette([
            (76, 0, 0),
            (166, 0, 0),
            (255, 1, 1),
            (255, 129, 129),
            (253, 253, 255),
            (125, 125, 255),
            (0, 0, 254),
            (0, 0, 190),
            (0, 0, 128)  # BGR stops
        ])

        # RDYLBU - Blue→pale yellow→red, cold to hot (ColorBrewer RdYlBu)
        self.palette_cache[PaletteType.RDYLBU] = self._create_gradient_palette([
            (149, 54, 49),
            (179, 116, 69),
            (209, 173, 116),
            (233, 216, 170),
            (248, 243, 224),
            (192, 255, 254),
            (144, 224, 254),
            (96, 173, 253),
            (67, 109, 244),
            (39, 47, 214),
            (38, 0, 165)  # BGR stops
        ])

        # BRBG - Brown→white→teal diverging (ColorBrewer BrBG)
        self.palette_cache[PaletteType.BRBG] = self._create_gradient_palette([
            (5, 48, 84),
            (10, 80, 139),
            (45, 129, 191),
            (123, 193, 222),
            (195, 232, 246),
            (245, 245, 244),
            (229, 234, 199),
            (192, 204, 127),
            (143, 151, 53),
            (93, 101, 1),
            (48, 60, 0)  # BGR stops
        ])

        # ===== ADDITIONAL PALETTES, BATCH 2 =====
        from .palette_stops import EXTRA_PALETTE_STOPS
        for _pid, (_kind, _stops) in EXTRA_PALETTE_STOPS.items():
            if _kind == "steps":
                self.palette_cache[PaletteType(_pid)] = self._create_stepped_palette(_stops)
            else:
                self.palette_cache[PaletteType(_pid)] = self._create_gradient_palette(_stops)

    def _create_stepped_palette(self, colors: List[Tuple[int, int, int]]) -> np.ndarray:
        """256-entry palette of flat bands, one per colour (for banded/high-contrast palettes)."""
        band = np.minimum(np.arange(256) * len(colors) // 256, len(colors) - 1)
        return np.array(colors, dtype=np.uint8)[band]

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
            # Auto-contrast stretch using the 1st/99th percentile, not the
            # true min/max. A raw sensor frame with no onboard AGC (e.g. a
            # Tau2 breakout board with no CCI control line, so this app
            # can't put the camera in a calibrated mode) commonly carries a
            # handful of noisy/outlier pixels; stretching to the TRUE min/
            # max lets a single such pixel claim one end of the 0-255 range,
            # compressing every real-scene value into a narrow band at the
            # other end - the auto-contrast step visibly runs, but the
            # actual scene still looks washed out. Percentiles clip that
            # outlier's influence while still adapting per frame the way
            # auto-contrast is meant to.
            # Subsampled, not run on every pixel: np.percentile requires a
            # partial sort, and measured at ~5-6ms/frame on a full 640x512
            # image - by far the dominant cost of colorizing a frame (the
            # actual color mapping below is sub-millisecond). Percentiles
            # are robust to subsampling at this scale (same technique
            # already used in ThermalTemperatureEstimator._estimate_scene_
            # range()) - a stride of 4 in each axis is 16x fewer samples
            # (~20K instead of ~327K) for a statistically indistinguishable
            # 1st/99th percentile.
            sampled = image[::4, ::4]
            min_val = np.percentile(sampled, 1)
            max_val = np.percentile(sampled, 99)

            # Coarse/quantized raw sensor data (no onboard AGC) can have the
            # 1st/99th percentile collapse to the same integer even when the
            # frame has some real variation - fall back to true min/max so
            # there's still a stretch as long as ANY variance exists. Always
            # produce a valid uint8 array: leaving `image` as the original
            # (uint16, values in the thousands for a raw 14-bit source) fed
            # a wrong-range, wrong-dtype array into cv2.applyColorMap/LUT
            # below, which expect uint8 - this produced a blank/garbage
            # frame with no error, not just "less contrast".
            if max_val <= min_val:
                min_val = np.min(image)
                max_val = np.max(image)

            if max_val > min_val:
                # cv2.convertScaleAbs (one SIMD-backed call: scale, offset,
                # saturate-cast to uint8) instead of the numpy clip/
                # subtract/divide/multiply/cast chain - that chain allocates
                # a fresh full-frame temporary at every one of those steps,
                # the same allocation-count issue found and fixed in
                # fusion_processor.py's blends earlier this session, and
                # was still costing ~4-5ms/frame even after subsampling the
                # percentile computation above. Clip in place first (no new
                # allocation) so every value is already within [min_val,
                # max_val] before the scale - convertScaleAbs takes an
                # absolute value after scaling, which would silently
                # flip a below-min_val pixel to a wrong bright value
                # instead of clamping to 0 if it weren't pre-clipped.
                np.clip(image, min_val, max_val, out=image, casting='unsafe')
                scale = 255.0 / (max_val - min_val)
                offset = -min_val * scale
                image = cv2.convertScaleAbs(image, alpha=scale, beta=offset)
            else:
                image = np.full(image.shape, 128, dtype=np.uint8)
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
            # Use custom palette - LUT is (256, 3)
            lut = self.palette_cache[palette_type]

            # Split into separate channel LUTs for cv2.LUT()
            lut_b = lut[:, 0]  # Blue channel
            lut_g = lut[:, 1]  # Green channel
            lut_r = lut[:, 2]  # Red channel

            # Apply to each channel
            b = cv2.LUT(thermal_adjusted, lut_b)
            g = cv2.LUT(thermal_adjusted, lut_g)
            r = cv2.LUT(thermal_adjusted, lut_r)

            # Merge channels
            colorized = cv2.merge([b, g, r])
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

        # Apply ROI-specific palettes (from roi_palettes dict - legacy)
        if self.roi_palettes:
            logger.debug(f"Applying {len(self.roi_palettes)} ROI palettes from config")

        # Cleanup stale ROI palettes (self-healing)
        stale_rois = []
        for roi_id in self.roi_palettes:
            roi = roi_manager.get_roi(roi_id)
            if roi is None:
                stale_rois.append(roi_id)

        for roi_id in stale_rois:
            del self.roi_palettes[roi_id]
            logger.debug(f"Cleaned up stale palette for missing ROI {roi_id}")

        for roi_id, palette_config in self.roi_palettes.items():
            roi = roi_manager.get_roi(roi_id)
            if roi is None or not roi.active:
                # Should be caught by cleanup above, but check active status
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
            logger.debug(f"Applied palette {palette_config.palette_type.value} to ROI {roi_id} (mask sum: {np.sum(mask)})")

        # Apply custom palettes from ROI.custom_palette field (NEW!)
        for roi in roi_manager.get_all_rois(active_only=True):
            if roi.custom_palette:
                # Get ROI mask
                mask = roi.get_mask(thermal_frame.shape)
                if mask is None or np.sum(mask) == 0:
                    continue

                # Create palette config from custom_palette name
                try:
                    palette_type = PaletteType(roi.custom_palette)
                    palette_config = PaletteConfig(palette_type=palette_type)
                    roi_colorized = self.apply_palette(thermal_frame, palette_config)

                    # Blend ROI palette onto output
                    mask_3ch = cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR)
                    output = np.where(mask_3ch > 0, roi_colorized, output)
                except (ValueError, KeyError):
                    # Invalid palette name - skip
                    pass

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

    def get_current_palette_lut(self) -> Optional[np.ndarray]:
        """
        Get the current global palette LUT (lookup table).

        Returns:
            numpy array of shape (256, 3) with BGR values, or None if not found
        """
        return self.get_palette_lut(self.global_palette.palette_type)

    def get_palette_lut(self, palette_type: PaletteType) -> np.ndarray:
        """
        Get the (256, 3) BGR lookup table for any palette (not just the active one),
        e.g. to draw previews in a palette picker.
        """
        if palette_type in self.palette_cache:
            return self.palette_cache[palette_type].copy()
        elif palette_type in self.OPENCV_COLORMAPS:
            # Generate LUT from OpenCV colormap
            # Create a gradient image (0-255)
            gradient = np.arange(256, dtype=np.uint8).reshape(1, 256)
            # Apply colormap
            colored = cv2.applyColorMap(gradient, self.OPENCV_COLORMAPS[palette_type])
            # Extract LUT (256, 1, 3) -> (256, 3)
            lut = colored.reshape(256, 3)
            return lut
        else:
            # Fallback to grayscale
            gray_lut = np.arange(256, dtype=np.uint8).reshape(256, 1)
            lut = np.concatenate([gray_lut, gray_lut, gray_lut], axis=1)
            return lut

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
        with open(filepath) as f:
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
