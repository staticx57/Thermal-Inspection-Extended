"""
Fusion Controller for Thermal Inspection application.

Manages thermal-RGB fusion settings and FusionProcessor delegation.
Extracted from ThermalInspectionFusion class in inspection_main.py.
"""

import logging
from typing import Optional, Callable, List
from dataclasses import dataclass
from enum import Enum, auto

from thermal_inspection.processing.fusion_processor import FusionProcessor

logger = logging.getLogger(__name__)

# Global constant for PIP mode
PIP_SIZE_RATIO = 0.2


class ViewMode(Enum):
    """View mode enumeration."""
    THERMAL_ONLY = auto()
    RGB_ONLY = auto()
    FUSION = auto()
    SIDE_BY_SIDE = auto()
    PICTURE_IN_PICTURE = auto()


@dataclass
class FusionState:
    """Current state of fusion settings."""
    mode: str = 'thermal_overlay'
    alpha: float = 0.5
    priority: str = 'thermal'
    strength: float = 0.5
    fuzziness: float = 0.3
    rgb_color_mode: str = 'color'
    view_mode: ViewMode = ViewMode.FUSION
    current_mode_index: int = 0


@dataclass
class EdgeSettings:
    """Edge detection settings."""
    strength: float = 0.5
    fuzziness: float = 0.3
    color: str = 'cyan'


@dataclass
class DetailSettings:
    """Detail injection settings."""
    strength: float = 0.5
    quality: float = 0.5


class FusionController:
    """
    Manages thermal-RGB fusion settings and processor.

    This controller handles:
    - Fusion mode selection and cycling
    - Alpha blending control
    - Priority (thermal vs RGB base)
    - Edge detection settings
    - Detail injection settings
    - View mode management

    Usage:
        controller = FusionController()
        controller.set_fusion_processor(processor)
        controller.on_state_change = my_callback
        controller.set_mode('alpha_blend')
    """

    # Available fusion modes - sourced from FusionProcessor.AVAILABLE_FUSION_MODES
    # rather than a separate copy. This class used to keep its own 9-mode
    # list here, missing thermal_contours/enhanced_edge_highlight/
    # laplacian_pyramid entirely - cycle_mode() could never reach them, and
    # set_mode()'s own drift (see FusionProcessor.set_mode()) meant
    # selecting them from the GUI silently no-opped too.
    AVAILABLE_MODES: List[str] = FusionProcessor.AVAILABLE_FUSION_MODES

    # Color map for edge overlay
    EDGE_COLORS = {
        'white': (255, 255, 255),
        'cyan': (255, 255, 0),
        'green': (0, 255, 0),
        'yellow': (0, 255, 255),
        'red': (0, 0, 255),
        'magenta': (255, 0, 255)
    }

    def __init__(self, initial_mode: str = 'thermal_overlay', initial_alpha: float = 0.5):
        """
        Initialize FusionController.

        Args:
            initial_mode: Initial fusion mode
            initial_alpha: Initial alpha blending value
        """
        self.state = FusionState(
            mode=initial_mode,
            alpha=initial_alpha
        )
        self.edge_settings = EdgeSettings()
        self.detail_settings = DetailSettings()

        # Fusion processor instance
        self.fusion_processor = None

        # Callbacks
        self.on_state_change: Optional[Callable[[FusionState], None]] = None
        self.on_mode_change: Optional[Callable[[str], None]] = None
        self.on_alpha_change: Optional[Callable[[float], None]] = None
        self.on_priority_change: Optional[Callable[[str], None]] = None
        self.on_view_mode_change: Optional[Callable[[ViewMode, str], None]] = None

    def set_fusion_processor(self, processor):
        """
        Set the FusionProcessor instance.

        Args:
            processor: FusionProcessor instance to delegate to
        """
        self.fusion_processor = processor
        # Sync current state to processor
        if processor:
            processor.set_mode(self.state.mode)
            processor.set_alpha(self.state.alpha)
            processor.set_priority(self.state.priority)

    def _notify_state_change(self):
        """Notify listeners of state change."""
        if self.on_state_change:
            self.on_state_change(self.state)

    def set_mode(self, mode: str):
        """
        Set fusion mode.

        Args:
            mode: Fusion mode name (e.g., 'alpha_blend', 'thermal_overlay')
        """
        self.state.mode = mode.lower()
        if self.fusion_processor:
            self.fusion_processor.set_mode(self.state.mode)

        # Update mode index
        try:
            self.state.current_mode_index = self.AVAILABLE_MODES.index(self.state.mode)
        except ValueError:
            self.state.current_mode_index = 0

        logger.info(f"Fusion mode set to: {self.state.mode}")

        if self.on_mode_change:
            self.on_mode_change(self.state.mode)
        self._notify_state_change()

    def set_alpha(self, alpha: float):
        """
        Set fusion alpha blending factor.

        Args:
            alpha: Alpha value (0.0 to 1.0)
        """
        self.state.alpha = max(0.0, min(1.0, alpha))
        if self.fusion_processor:
            self.fusion_processor.set_alpha(self.state.alpha)

        if self.on_alpha_change:
            self.on_alpha_change(self.state.alpha)
        self._notify_state_change()

    def set_priority(self, priority: str):
        """
        Set fusion priority (which image is the base).

        Args:
            priority: 'thermal' or 'rgb'
        """
        self.state.priority = priority.lower()
        if self.fusion_processor:
            self.fusion_processor.set_priority(self.state.priority)

        logger.info(f"Fusion priority set to: {self.state.priority}")

        if self.on_priority_change:
            self.on_priority_change(self.state.priority)
        self._notify_state_change()

    def set_strength(self, strength: float):
        """
        Set fusion strength (intensity).

        Args:
            strength: Strength value (0.0 to 1.0)
        """
        self.state.strength = max(0.0, min(1.0, strength))
        if self.fusion_processor:
            self.fusion_processor.set_intensity(self.state.strength)
        logger.info(f"Fusion strength set to: {self.state.strength:.2f}")
        self._notify_state_change()

    def set_fuzziness(self, fuzziness: float):
        """
        Set fusion fuzziness (edge blur for blending).

        Args:
            fuzziness: Fuzziness value (0.0 to 1.0)
        """
        self.state.fuzziness = max(0.0, min(1.0, fuzziness))
        if self.fusion_processor:
            # Convert 0.0-1.0 to kernel size (0-15)
            kernel_size = int(fuzziness * 15)
            # Ensure odd number for Gaussian blur
            if kernel_size > 0 and kernel_size % 2 == 0:
                kernel_size += 1
            self.fusion_processor.set_edge_blur(kernel_size)
        logger.info(f"Fusion fuzziness set to: {fuzziness:.2f}")
        self._notify_state_change()

    def set_rgb_color_mode(self, mode: str):
        """
        Set RGB fusion color mode (color vs grayscale).

        Args:
            mode: 'color' or 'grayscale'
        """
        self.state.rgb_color_mode = mode.lower()
        logger.info(f"Fusion RGB color mode set to: {self.state.rgb_color_mode}")
        self._notify_state_change()

    def set_view_mode(self, mode: str) -> bool:
        """
        Set view mode.

        Args:
            mode: View mode string (e.g., 'thermal only', 'fusion')

        Returns:
            True if mode was set successfully
        """
        mode_map = {
            "thermal only": ViewMode.THERMAL_ONLY,
            "rgb only": ViewMode.RGB_ONLY,
            "fusion": ViewMode.FUSION,
            "side-by-side": ViewMode.SIDE_BY_SIDE,
            "picture-in-picture": ViewMode.PICTURE_IN_PICTURE
        }
        view_mode = mode_map.get(mode.lower())
        if view_mode:
            self.state.view_mode = view_mode

            # Map ViewMode to overlay-expected string
            overlay_mode_map = {
                ViewMode.THERMAL_ONLY: "thermal",
                ViewMode.RGB_ONLY: "rgb",
                ViewMode.FUSION: "fusion",
                ViewMode.SIDE_BY_SIDE: "side_by_side",
                ViewMode.PICTURE_IN_PICTURE: "picture_in_picture"
            }
            overlay_mode = overlay_mode_map.get(view_mode, "thermal")

            if self.on_view_mode_change:
                self.on_view_mode_change(view_mode, overlay_mode)
            self._notify_state_change()
            return True
        return False

    # Edge detection settings
    def set_edge_strength(self, strength: float):
        """
        Set edge detection strength.

        Args:
            strength: Strength value (0.0 to 1.0). Higher = more edges detected.
        """
        self.edge_settings.strength = max(0.0, min(1.0, strength))
        if self.fusion_processor:
            # Convert to Canny threshold: higher strength = lower threshold
            threshold_low = int(100 - (strength * 90))  # Range: 100→10
            self.fusion_processor.set_edge_strength(threshold_low)
        logger.info(f"Edge strength set to: {strength:.2f}")

    def set_edge_fuzziness(self, fuzziness: float):
        """
        Set edge fuzziness (sharpness/softness).

        Args:
            fuzziness: Fuzziness value (0.0 to 1.0). Lower = sharper edges.
        """
        self.edge_settings.fuzziness = max(0.0, min(1.0, fuzziness))
        if self.fusion_processor:
            kernel_size = int(fuzziness * 15)
            if kernel_size > 0 and kernel_size % 2 == 0:
                kernel_size += 1
            self.fusion_processor.set_edge_blur(kernel_size)

        sharpness = 'sharp' if fuzziness < 0.3 else 'medium' if fuzziness < 0.7 else 'soft'
        logger.info(f"Edge fuzziness set to: {fuzziness:.2f} (sharpness={sharpness})")

    def set_edge_color(self, color: str):
        """
        Set edge overlay color.

        Args:
            color: Color name ('white', 'cyan', 'green', 'yellow', 'red', 'magenta')
        """
        self.edge_settings.color = color.lower()
        if self.fusion_processor:
            bgr_color = self.EDGE_COLORS.get(color.lower(), (255, 255, 0))
            self.fusion_processor.set_edge_color(bgr_color)
        logger.info(f"Edge color set to: {color}")

    # Detail injection settings
    def set_detail_strength(self, strength: float):
        """
        Set Detail Injection/Relief Fusion strength.

        Args:
            strength: Strength value (0.0 to 1.0)
        """
        self.detail_settings.strength = max(0.0, min(1.0, strength))
        if self.fusion_processor:
            self.fusion_processor.detail_strength = self.detail_settings.strength
        logger.info(f"Detail strength set to: {strength:.2f}")

    def set_detail_quality(self, quality: float):
        """
        Set Detail Injection/Relief Fusion quality.

        Args:
            quality: Quality value (0.0 to 1.0)
        """
        self.detail_settings.quality = max(0.0, min(1.0, quality))
        if self.fusion_processor:
            self.fusion_processor.detail_quality = self.detail_settings.quality
        logger.info(f"Detail quality set to: {quality:.2f}")

    # Cycling methods
    def cycle_mode(self) -> str:
        """
        Cycle to next fusion mode.

        Returns:
            New fusion mode name
        """
        self.state.current_mode_index = (self.state.current_mode_index + 1) % len(self.AVAILABLE_MODES)
        self.state.mode = self.AVAILABLE_MODES[self.state.current_mode_index]

        if self.fusion_processor:
            self.fusion_processor.set_mode(self.state.mode)

        logger.info(f"Fusion mode: {self.state.mode}")

        if self.on_mode_change:
            self.on_mode_change(self.state.mode)
        self._notify_state_change()

        return self.state.mode

    def cycle_alpha(self) -> float:
        """
        Cycle fusion alpha by 0.1.

        Returns:
            New alpha value
        """
        self.state.alpha += 0.1
        if self.state.alpha > 1.0:
            self.state.alpha = 0.0

        if self.fusion_processor:
            self.fusion_processor.set_alpha(self.state.alpha)

        logger.info(f"Fusion alpha: {self.state.alpha:.1f}")

        if self.on_alpha_change:
            self.on_alpha_change(self.state.alpha)
        self._notify_state_change()

        return self.state.alpha

    def cycle_priority(self) -> str:
        """
        Toggle fusion priority between thermal and RGB.

        Returns:
            New priority value
        """
        self.state.priority = 'rgb' if self.state.priority == 'thermal' else 'thermal'

        if self.fusion_processor:
            self.fusion_processor.set_priority(self.state.priority)

        logger.info(f"Fusion priority: {self.state.priority}")

        if self.on_priority_change:
            self.on_priority_change(self.state.priority)
        self._notify_state_change()

        return self.state.priority

    # Properties
    @property
    def mode(self) -> str:
        """Get current fusion mode."""
        return self.state.mode

    @property
    def alpha(self) -> float:
        """Get current alpha value."""
        return self.state.alpha

    @property
    def priority(self) -> str:
        """Get current priority."""
        return self.state.priority

    @property
    def available_modes(self) -> List[str]:
        """Get list of available fusion modes."""
        return self.AVAILABLE_MODES.copy()

    def get_overlay_info(self) -> dict:
        """
        Get overlay info for GUI updates.

        Returns:
            Dict with overlay mode and settings
        """
        overlay_mode_map = {
            ViewMode.THERMAL_ONLY: "thermal",
            ViewMode.RGB_ONLY: "rgb",
            ViewMode.FUSION: "fusion",
            ViewMode.SIDE_BY_SIDE: "side_by_side",
            ViewMode.PICTURE_IN_PICTURE: "picture_in_picture"
        }
        return {
            'overlay_mode': overlay_mode_map.get(self.state.view_mode, "thermal"),
            'fusion_priority': self.state.priority,
            'pip_size': PIP_SIZE_RATIO,
            'fusion_mode': self.state.mode
        }
