"""
Thermal-RGB Fusion Processor
Combines thermal and RGB imagery for enhanced object detection
Optimized for Jetson Orin with GPU acceleration
"""
import cv2
import numpy as np
import logging
from typing import Tuple, Optional, Dict
import json
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class FusionProcessor:
    """
    Multi-modal fusion processor for thermal and RGB cameras
    Supports multiple fusion strategies optimized for driving assistance
    """

    def __init__(self, fusion_mode: str = 'alpha_blend', alpha: float = 0.5,
                 calibration_file: Optional[str] = None, fusion_priority: str = 'thermal'):
        """
        Initialize fusion processor

        Args:
            fusion_mode: Fusion strategy
                - 'alpha_blend': Simple weighted average of thermal + RGB
                - 'edge_enhanced': RGB base with thermal edges overlaid
                - 'thermal_overlay': Thermal hotspots overlaid on RGB
                - 'side_by_side': Concatenate thermal and RGB horizontally
                - 'picture_in_picture': Thermal in corner of RGB (or vice versa)
                - 'max_intensity': Take maximum intensity from both sources
                - 'feature_weighted': Adaptive blending based on edge strength
            alpha: Blend ratio for alpha_blend mode (0.0 = all RGB, 1.0 = all thermal)
            calibration_file: Path to camera calibration file (JSON with homography matrix)
            fusion_priority: Which camera gets priority ('thermal' or 'rgb')
                - 'thermal': Thermal is base, RGB overlaid (default)
                - 'rgb': RGB is base, thermal overlaid
        """
        self.fusion_mode = fusion_mode
        self.alpha = alpha
        self.fusion_priority = fusion_priority
        self.calibration_matrix = None
        self.calibration_file = calibration_file

        # Load edge colors and intensity from config
        from config import get_config
        config = get_config()
        # Thermal priority: RGB edges on thermal base (cyan by default)
        self.thermal_priority_edge_color = tuple(config.get('fusion.edge_enhanced.thermal_priority_edge_color', [255, 255, 0]))
        # RGB priority: Thermal edges on RGB base (red by default)
        self.rgb_priority_edge_color = tuple(config.get('fusion.edge_enhanced.rgb_priority_edge_color', [0, 0, 255]))
        # Fusion intensity: controls overlay strength (0.0 = minimal, 1.0 = maximum)
        self.fusion_intensity = float(config.get('fusion.intensity', 0.5))

        # Load calibration if available
        if calibration_file and os.path.exists(calibration_file):
            self.load_calibration(calibration_file)
        else:
            logger.warning("No calibration file provided - using identity transform")

    def load_calibration(self, calibration_file: str) -> bool:
        """
        Load camera calibration from file

        Args:
            calibration_file: Path to JSON file with homography matrix

        Returns:
            True if successful
        """
        try:
            with open(calibration_file, 'r') as f:
                calib_data = json.load(f)

            # Load homography matrix (3x3)
            if 'homography' in calib_data:
                self.calibration_matrix = np.array(calib_data['homography'], dtype=np.float32)
                logger.info(f"Loaded calibration from {calibration_file}")
                return True
            else:
                logger.error("Calibration file missing 'homography' key")
                return False

        except Exception as e:
            logger.error(f"Failed to load calibration: {e}")
            return False

    def save_calibration(self, calibration_file: str) -> bool:
        """
        Save camera calibration to file

        Args:
            calibration_file: Path to output JSON file

        Returns:
            True if successful
        """
        try:
            if self.calibration_matrix is None:
                logger.error("No calibration matrix to save")
                return False

            calib_data = {
                'homography': self.calibration_matrix.tolist()
            }

            with open(calibration_file, 'w') as f:
                json.dump(calib_data, f, indent=2)

            logger.info(f"Saved calibration to {calibration_file}")
            return True

        except Exception as e:
            logger.error(f"Failed to save calibration: {e}")
            return False

    def set_mode(self, fusion_mode: str):
        """
        Set fusion mode dynamically

        Args:
            fusion_mode: New fusion mode to use
        """
        valid_modes = ['alpha_blend', 'edge_enhanced', 'thermal_overlay',
                       'side_by_side', 'picture_in_picture', 'max_intensity', 'feature_weighted']

        if fusion_mode in valid_modes:
            self.fusion_mode = fusion_mode
            logger.info(f"Fusion mode changed to: {fusion_mode}")
        else:
            logger.warning(f"Invalid fusion mode '{fusion_mode}', keeping current mode '{self.fusion_mode}'")

    def set_alpha(self, alpha: float):
        """
        Set alpha blending value dynamically

        Args:
            alpha: Blend ratio (0.0 = all RGB, 1.0 = all thermal)
        """
        if 0.0 <= alpha <= 1.0:
            self.alpha = alpha
            logger.info(f"Fusion alpha changed to: {alpha:.2f}")
        else:
            logger.warning(f"Invalid alpha value {alpha}, must be between 0.0 and 1.0")

    def set_priority(self, priority: str):
        """
        Set fusion priority dynamically

        Args:
            priority: Which camera gets priority ('thermal' or 'rgb')
        """
        if priority in ['thermal', 'rgb']:
            self.fusion_priority = priority
            logger.info(f"Fusion priority changed to: {priority}")
        else:
            logger.warning(f"Invalid priority '{priority}', must be 'thermal' or 'rgb'")

    def set_intensity(self, intensity: float):
        """
        Set fusion intensity dynamically
        Controls overlay strength for edge_enhanced, thermal_overlay, and feature_weighted modes

        Args:
            intensity: Overlay strength (0.0 = minimal, 1.0 = maximum)
        """
        if 0.0 <= intensity <= 1.0:
            self.fusion_intensity = intensity
            logger.info(f"Fusion intensity set to: {intensity:.2f}")
        else:
            logger.warning(f"Invalid intensity value {intensity}, must be between 0.0 and 1.0")

    def align_rgb_to_thermal(self, rgb: np.ndarray, thermal_shape: Tuple[int, int]) -> np.ndarray:
        """
        Align RGB frame to thermal frame coordinate system

        Args:
            rgb: RGB frame (any size)
            thermal_shape: Target thermal resolution (height, width)

        Returns:
            Aligned RGB frame matching thermal dimensions
        """
        target_h, target_w = thermal_shape

        try:
            if self.calibration_matrix is not None:
                # Use calibration matrix for precise alignment
                rgb_aligned = cv2.warpPerspective(
                    rgb, self.calibration_matrix,
                    (target_w, target_h),
                    flags=cv2.INTER_LINEAR
                )
            else:
                # Simple resize as fallback
                rgb_aligned = cv2.resize(rgb, (target_w, target_h), interpolation=cv2.INTER_LINEAR)

            return rgb_aligned

        except Exception as e:
            logger.error(f"Error aligning RGB frame: {e}")
            return cv2.resize(rgb, (target_w, target_h), interpolation=cv2.INTER_LINEAR)

    def fuse_frames(self, thermal: np.ndarray, rgb: np.ndarray) -> np.ndarray:
        """
        Fuse thermal and RGB frames using selected strategy

        Args:
            thermal: Thermal frame (colorized, BGR format)
            rgb: RGB frame (BGR format)

        Returns:
            Fused frame (BGR format)
        """
        # Validate inputs
        if thermal is None or rgb is None:
            logger.error("Invalid input frames for fusion")
            return thermal if thermal is not None else rgb

        # Ensure both frames are BGR
        if len(thermal.shape) == 2:
            thermal = cv2.cvtColor(thermal, cv2.COLOR_GRAY2BGR)
        if len(rgb.shape) == 2:
            rgb = cv2.cvtColor(rgb, cv2.COLOR_GRAY2BGR)

        # Align RGB to thermal dimensions
        thermal_h, thermal_w = thermal.shape[:2]
        rgb_aligned = self.align_rgb_to_thermal(rgb, (thermal_h, thermal_w))

        # Apply fusion strategy
        if self.fusion_mode == 'alpha_blend':
            return self._alpha_blend(thermal, rgb_aligned)
        elif self.fusion_mode == 'edge_enhanced':
            return self._edge_enhanced(thermal, rgb_aligned)
        elif self.fusion_mode == 'thermal_overlay':
            return self._thermal_overlay(thermal, rgb_aligned)
        elif self.fusion_mode == 'side_by_side':
            return self._side_by_side(thermal, rgb_aligned)
        elif self.fusion_mode == 'picture_in_picture':
            return self._picture_in_picture(thermal, rgb_aligned)
        elif self.fusion_mode == 'max_intensity':
            return self._max_intensity(thermal, rgb_aligned)
        elif self.fusion_mode == 'feature_weighted':
            return self._feature_weighted(thermal, rgb_aligned)
        else:
            logger.warning(f"Unknown fusion mode: {self.fusion_mode}, using alpha_blend")
            return self._alpha_blend(thermal, rgb_aligned)

    def _alpha_blend(self, thermal: np.ndarray, rgb: np.ndarray) -> np.ndarray:
        """
        Simple weighted average fusion with priority control

        Args:
            thermal: Thermal frame (BGR)
            rgb: RGB frame (BGR, aligned)

        Returns:
            Blended frame
        """
        try:
            if self.fusion_priority == 'thermal':
                # Thermal-weighted: alpha controls thermal contribution
                return cv2.addWeighted(thermal, self.alpha, rgb, 1.0 - self.alpha, 0)
            else:
                # RGB-weighted: alpha controls RGB contribution
                return cv2.addWeighted(rgb, self.alpha, thermal, 1.0 - self.alpha, 0)
        except Exception as e:
            logger.error(f"Alpha blend error: {e}")
            return thermal

    def _edge_enhanced(self, thermal: np.ndarray, rgb: np.ndarray) -> np.ndarray:
        """
        Edge-enhanced fusion with priority control
        Extracts edges from one source and overlays on the other
        Uses configurable edge colors from config.json

        Args:
            thermal: Thermal frame (BGR)
            rgb: RGB frame (BGR, aligned)

        Returns:
            Edge-enhanced frame
        """
        try:
            if self.fusion_priority == 'rgb':
                # RGB base + thermal edges
                # Extract edges from thermal
                thermal_gray = cv2.cvtColor(thermal, cv2.COLOR_BGR2GRAY)
                edges = cv2.Canny(thermal_gray, 50, 150)

                # Create colored edge overlay (configurable color)
                edge_color = np.zeros_like(thermal)
                edge_color[edges > 0] = self.rgb_priority_edge_color  # Configurable (default: red)

                # Blend: RGB base + thermal edges (use configurable intensity)
                result = rgb.copy()
                result = cv2.addWeighted(result, 1.0, edge_color, self.fusion_intensity, 0)
            else:
                # Thermal base + RGB edges (inverted priority)
                # Extract edges from RGB
                rgb_gray = cv2.cvtColor(rgb, cv2.COLOR_BGR2GRAY)
                edges = cv2.Canny(rgb_gray, 50, 150)

                # Create colored edge overlay (configurable color)
                edge_color = np.zeros_like(rgb)
                edge_color[edges > 0] = self.thermal_priority_edge_color  # Configurable (default: cyan)

                # Blend: Thermal base + RGB edges (use configurable intensity)
                result = thermal.copy()
                result = cv2.addWeighted(result, 1.0, edge_color, self.fusion_intensity, 0)

            return result

        except Exception as e:
            logger.error(f"Edge enhanced error: {e}")
            return self._alpha_blend(thermal, rgb)

    def _thermal_overlay(self, thermal: np.ndarray, rgb: np.ndarray) -> np.ndarray:
        """
        Overlay hotspots on base with priority control
        Priority determines which is base and which is overlay

        Args:
            thermal: Thermal frame (BGR)
            rgb: RGB frame (BGR, aligned)

        Returns:
            Overlaid frame
        """
        try:
            if self.fusion_priority == 'rgb':
                # RGB base + thermal hotspots overlay (use intensity)
                thermal_gray = cv2.cvtColor(thermal, cv2.COLOR_BGR2GRAY)
                threshold = np.percentile(thermal_gray, 70)
                hot_mask = thermal_gray > threshold

                result = rgb.copy()
                result[hot_mask] = cv2.addWeighted(
                    thermal[hot_mask], self.fusion_intensity,
                    rgb[hot_mask], 1.0 - self.fusion_intensity,
                    0
                )
            else:
                # Thermal base + RGB highlights overlay (use intensity)
                rgb_gray = cv2.cvtColor(rgb, cv2.COLOR_BGR2GRAY)
                threshold = np.percentile(rgb_gray, 70)
                bright_mask = rgb_gray > threshold

                result = thermal.copy()
                result[bright_mask] = cv2.addWeighted(
                    rgb[bright_mask], self.fusion_intensity,
                    thermal[bright_mask], 1.0 - self.fusion_intensity,
                    0
                )

            return result

        except Exception as e:
            logger.error(f"Thermal overlay error: {e}")
            return self._alpha_blend(thermal, rgb)

    def _side_by_side(self, thermal: np.ndarray, rgb: np.ndarray) -> np.ndarray:
        """
        Concatenate thermal and RGB horizontally with priority control
        Priority determines left/right order

        Args:
            thermal: Thermal frame (BGR)
            rgb: RGB frame (BGR, aligned)

        Returns:
            Concatenated frame
        """
        try:
            # Ensure same height
            h = thermal.shape[0]
            if rgb.shape[0] != h:
                rgb = cv2.resize(rgb, (rgb.shape[1], h))

            # Concatenate horizontally (priority determines order)
            if self.fusion_priority == 'thermal':
                return np.hstack([thermal, rgb])  # Thermal on left
            else:
                return np.hstack([rgb, thermal])  # RGB on left

        except Exception as e:
            logger.error(f"Side-by-side error: {e}")
            return thermal

    def _picture_in_picture(self, thermal: np.ndarray, rgb: np.ndarray,
                            pip_size: float = 0.25, position: str = 'top-right') -> np.ndarray:
        """
        Picture-in-picture with priority control
        Priority determines which is main and which is inset

        Args:
            thermal: Thermal frame (BGR)
            rgb: RGB frame (BGR, aligned)
            pip_size: Size of inset as fraction of main frame (0.0-1.0)
            position: 'top-right', 'top-left', 'bottom-right', 'bottom-left'

        Returns:
            Picture-in-picture frame
        """
        try:
            # Priority determines main vs inset
            if self.fusion_priority == 'thermal':
                main = thermal.copy()
                inset = rgb
            else:
                main = rgb.copy()
                inset = thermal

            # Calculate inset dimensions
            main_h, main_w = main.shape[:2]
            inset_w = int(main_w * pip_size)
            inset_h = int(main_h * pip_size)
            inset_resized = cv2.resize(inset, (inset_w, inset_h))

            # Determine position
            margin = 10
            if position == 'top-right':
                x, y = main_w - inset_w - margin, margin
            elif position == 'top-left':
                x, y = margin, margin
            elif position == 'bottom-right':
                x, y = main_w - inset_w - margin, main_h - inset_h - margin
            else:  # bottom-left
                x, y = margin, main_h - inset_h - margin

            # Add border to inset
            inset_with_border = cv2.copyMakeBorder(
                inset_resized, 2, 2, 2, 2,
                cv2.BORDER_CONSTANT, value=[255, 255, 255]
            )

            # Overlay inset on main
            ih, iw = inset_with_border.shape[:2]
            main[y:y+ih, x:x+iw] = inset_with_border

            return main

        except Exception as e:
            logger.error(f"Picture-in-picture error: {e}")
            return self._side_by_side(thermal, rgb)

    def _max_intensity(self, thermal: np.ndarray, rgb: np.ndarray) -> np.ndarray:
        """
        Take maximum intensity from thermal and RGB at each pixel
        Preserves brightest features from both sources

        Args:
            thermal: Thermal frame (BGR)
            rgb: RGB frame (BGR, aligned)

        Returns:
            Max intensity frame
        """
        try:
            return np.maximum(thermal, rgb)
        except Exception as e:
            logger.error(f"Max intensity error: {e}")
            return self._alpha_blend(thermal, rgb)

    def _feature_weighted(self, thermal: np.ndarray, rgb: np.ndarray) -> np.ndarray:
        """
        Adaptive fusion based on edge strength with priority bias
        Priority adds bias toward thermal or RGB features

        Args:
            thermal: Thermal frame (BGR)
            rgb: RGB frame (BGR, aligned)

        Returns:
            Adaptively blended frame
        """
        try:
            # Convert to grayscale
            thermal_gray = cv2.cvtColor(thermal, cv2.COLOR_BGR2GRAY)
            rgb_gray = cv2.cvtColor(rgb, cv2.COLOR_BGR2GRAY)

            # Calculate edge strength
            thermal_edges = cv2.Sobel(thermal_gray, cv2.CV_64F, 1, 1, ksize=3)
            rgb_edges = cv2.Sobel(rgb_gray, cv2.CV_64F, 1, 1, ksize=3)

            thermal_strength = np.abs(thermal_edges)
            rgb_strength = np.abs(rgb_edges)

            # Normalize to [0, 1]
            thermal_strength = thermal_strength / (thermal_strength.max() + 1e-6)
            rgb_strength = rgb_strength / (rgb_strength.max() + 1e-6)

            # Apply priority bias (boost preferred source using intensity)
            # intensity controls bias strength: 0.0 = no bias, 1.0 = double strength
            bias_multiplier = 1.0 + self.fusion_intensity
            if self.fusion_priority == 'thermal':
                thermal_strength = thermal_strength * bias_multiplier
            else:
                rgb_strength = rgb_strength * bias_multiplier

            # Compute adaptive weights
            total_strength = thermal_strength + rgb_strength + 1e-6
            thermal_weight = (thermal_strength / total_strength)[:, :, np.newaxis]
            rgb_weight = (rgb_strength / total_strength)[:, :, np.newaxis]

            # Weighted blend
            result = (thermal * thermal_weight + rgb * rgb_weight).astype(np.uint8)

            return result

        except Exception as e:
            logger.error(f"Feature weighted error: {e}")
            return self._alpha_blend(thermal, rgb)

    def set_fusion_mode(self, mode: str):
        """Change fusion mode"""
        valid_modes = ['alpha_blend', 'edge_enhanced', 'thermal_overlay',
                      'side_by_side', 'picture_in_picture', 'max_intensity',
                      'feature_weighted']
        if mode in valid_modes:
            self.fusion_mode = mode
            logger.info(f"Fusion mode changed to: {mode}")
        else:
            logger.warning(f"Invalid fusion mode: {mode}")

    def set_alpha(self, alpha: float):
        """
        Set alpha blend ratio

        Args:
            alpha: Blend ratio (0.0 = all RGB, 1.0 = all thermal)
        """
        self.alpha = np.clip(alpha, 0.0, 1.0)
        logger.info(f"Alpha blend ratio set to: {self.alpha:.2f}")

    def get_available_modes(self) -> list:
        """Get list of available fusion modes"""
        return ['alpha_blend', 'edge_enhanced', 'thermal_overlay',
                'side_by_side', 'picture_in_picture', 'max_intensity',
                'feature_weighted']


if __name__ == "__main__":
    """Test fusion processor with synthetic data"""
    print("="*60)
    print("Fusion Processor Test")
    print("="*60)

    # Create synthetic thermal and RGB frames
    thermal = np.random.randint(0, 255, (512, 640, 3), dtype=np.uint8)
    thermal = cv2.applyColorMap(cv2.cvtColor(thermal, cv2.COLOR_BGR2GRAY), cv2.COLORMAP_HOT)

    rgb = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)

    # Draw some test patterns
    cv2.circle(thermal, (320, 256), 50, (0, 0, 255), -1)  # Hot spot
    cv2.rectangle(rgb, (200, 200), (400, 400), (0, 255, 0), 3)  # Green box

    # Test all fusion modes
    processor = FusionProcessor()

    modes = processor.get_available_modes()
    print(f"\nTesting {len(modes)} fusion modes...")

    for mode in modes:
        print(f"\nMode: {mode}")
        processor.set_fusion_mode(mode)
        fused = processor.fuse_frames(thermal, rgb)

        if fused is not None:
            cv2.imshow(f"Fusion Mode: {mode}", fused)
            print(f"  Output shape: {fused.shape}")
            key = cv2.waitKey(0)
            if key == ord('q'):
                break

    cv2.destroyAllWindows()
    print("\nTest complete!")
