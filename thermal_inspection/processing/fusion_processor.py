"""
Thermal-RGB Fusion Processor
Combines thermal and RGB imagery for enhanced object detection
Optimized for Jetson Orin with GPU acceleration
"""
import cv2
import numpy as np
import logging
from typing import Tuple, Optional
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
                - 'detail_inject': Detail Injection - overlays grayscale high-frequency detail from RGB
                - 'relief_fusion': Relief Fusion - embossing filter (3D bas-relief effect)
                - 'edge_enhanced': RGB base with thermal edges overlaid (prominent colored edges)
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
        from thermal_inspection.utils.config import get_config
        config = get_config()
        # Thermal priority: RGB edges on thermal base (cyan by default)
        self.thermal_priority_edge_color = tuple(config.get('fusion.edge_enhanced.thermal_priority_edge_color', [255, 255, 0]))
        # RGB priority: Thermal edges on RGB base (red by default)
        self.rgb_priority_edge_color = tuple(config.get('fusion.edge_enhanced.rgb_priority_edge_color', [0, 0, 255]))
        # Fusion intensity: controls overlay strength (0.0 = minimal, 1.0 = maximum)
        self.fusion_intensity = float(config.get('fusion.intensity', 0.5))

        # Hardware acceleration status
        self.has_cuda = hasattr(cv2, 'cuda') and hasattr(cv2.cuda, 'getCudaEnabledDeviceCount') and cv2.cuda.getCudaEnabledDeviceCount() > 0
        if self.has_cuda:
            logger.info("FusionProcessor: CUDA GPU acceleration detected and enabled")
        else:
            logger.info("FusionProcessor: Running in CPU vectorized mode (OpenCV SIMD / IPP)")


        # Edge detection parameters (NEW)
        self.edge_threshold_low = 50   # Canny low threshold (more edges = lower value)
        self.edge_threshold_high = 150  # Canny high threshold (more edges = lower value)
        self.edge_blur_kernel = 0      # Gaussian blur kernel size for edge sharpness (0 = sharp edges, >0 = softer edges)

        # Detail Injection / Relief Fusion parameters
        self.detail_strength = 0.7     # Detail overlay strength (0.0 = subtle, 1.0 = strong)
        self.detail_quality = 0.5      # Detail quality/level (0.0 = less detail, 1.0 = maximum detail)

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
            with open(calibration_file) as f:
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
        valid_modes = ['alpha_blend', 'detail_inject', 'relief_fusion', 'edge_enhanced', 'thermal_overlay',
                       'side_by_side', 'picture_in_picture', 'max_intensity', 'feature_weighted', 'anomaly_priority']

        if fusion_mode in valid_modes:
            self.fusion_mode = fusion_mode
            logger.info(f"Fusion mode changed to: {fusion_mode}")
        else:
            logger.warning(f"Invalid fusion mode '{fusion_mode}', keeping current mode '{self.fusion_mode}'")

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

    def set_edge_color(self, color: Tuple[int, int, int], priority: str = None):
        """
        Set edge color for edge-enhanced fusion mode

        Args:
            color: BGR color tuple (0-255 for each channel)
            priority: Which priority mode this color applies to ('thermal' or 'rgb')
                     If None, applies to current priority
        """
        if priority is None:
            priority = self.fusion_priority

        if priority == 'thermal':
            self.thermal_priority_edge_color = tuple(color)
            logger.info(f"Thermal priority edge color set to: {color}")
        elif priority == 'rgb':
            self.rgb_priority_edge_color = tuple(color)
            logger.info(f"RGB priority edge color set to: {color}")
        else:
            logger.warning(f"Invalid priority '{priority}', must be 'thermal' or 'rgb'")

    def set_edge_strength(self, threshold_low: int, threshold_high: int = None):
        """
        Set edge detection strength (Canny thresholds)
        Lower values = more edges detected, Higher values = fewer edges

        Args:
            threshold_low: Lower threshold for Canny edge detection (10-100 typical)
            threshold_high: Upper threshold (if None, automatically set to 3x low threshold)
        """
        threshold_low = max(1, min(200, threshold_low))  # Clamp to reasonable range
        if threshold_high is None:
            threshold_high = threshold_low * 3
        else:
            threshold_high = max(threshold_low, min(300, threshold_high))

        self.edge_threshold_low = threshold_low
        self.edge_threshold_high = threshold_high
        logger.info(f"Edge thresholds set to: low={threshold_low}, high={threshold_high}")

    def set_edge_blur(self, kernel_size: int):
        """
        Set edge fuzziness (Gaussian blur applied to edge mask after detection)
        Controls edge sharpness without affecting which edges are detected.

        Lower values = sharp, crisp edges (more detail visible)
        Higher values = soft, blurred edges (smoother appearance)

        Args:
            kernel_size: Gaussian blur kernel size (0 = no blur/sharp, 1-15 typical for soft)
                        Will be converted to odd number for cv2.GaussianBlur
        """
        if kernel_size < 0:
            kernel_size = 0
        elif kernel_size > 0 and kernel_size % 2 == 0:
            kernel_size += 1  # Ensure odd number

        self.edge_blur_kernel = min(15, kernel_size)
        logger.info(f"Edge blur kernel size set to: {self.edge_blur_kernel}")

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

    def process(self, thermal: np.ndarray, rgb: np.ndarray) -> np.ndarray:
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
        elif self.fusion_mode == 'detail_inject':
            return self._detail_inject(thermal, rgb_aligned)
        elif self.fusion_mode == 'relief_fusion':
            return self._relief_fusion(thermal, rgb_aligned)
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
        elif self.fusion_mode == 'thermal_contours':
            return self._thermal_contours(thermal, rgb_aligned)
        elif self.fusion_mode == 'enhanced_edge_highlight':
            return self._enhanced_edge_highlight(thermal, rgb_aligned)
        elif self.fusion_mode == 'laplacian_pyramid':
            return self._laplacian_pyramid(thermal, rgb_aligned)
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

    def _detail_inject(self, thermal: np.ndarray, rgb: np.ndarray) -> np.ndarray:
        """
        Detail Injection fusion - FLIR MSX-style (Multi-Spectral Dynamic Imaging)
        Overlays grayscale high-frequency spatial detail from RGB onto thermal
        Adds visible structure (edges, text, outlines) as grayscale information

        Key insight: MSX extracts sharp GRAYSCALE detail (not binary edges, not embossing)
        from the visible camera and overlays it on thermal to add spatial context
        while preserving thermal radiometric data.

        Args:
            thermal: Thermal frame (BGR, colorized)
            rgb: RGB frame (BGR, aligned)

        Returns:
            Detail-injected thermal frame (thermal + grayscale RGB detail)
        """
        try:
            # Convert RGB to grayscale to extract spatial detail
            rgb_gray = cv2.cvtColor(rgb, cv2.COLOR_BGR2GRAY)

            # Extract high-frequency detail (edges, texture, structure) from RGB
            # Use high-pass filter to isolate sharp features
            # Quality controls blur kernel size (higher quality = larger kernel = more detail isolation)
            kernel_size = int(3 + self.detail_quality * 8)  # Range: 3 to 11
            if kernel_size % 2 == 0:  # Ensure odd kernel size
                kernel_size += 1
            blurred = cv2.GaussianBlur(rgb_gray, (kernel_size, kernel_size), 0)

            # Subtract to get high-frequency detail (edges/structure)
            detail = cv2.subtract(rgb_gray, blurred)

            # Enhance the detail contrast based on quality setting
            # Higher quality = more aggressive contrast enhancement
            contrast_alpha = 2.0 + self.detail_quality * 4.0  # Range: 2.0 to 6.0
            detail = cv2.convertScaleAbs(detail, alpha=contrast_alpha, beta=0)

            # Normalize to full range for better visibility
            if detail.max() > 0:
                detail = cv2.normalize(detail, None, 0, 255, cv2.NORM_MINMAX)

            # Convert detail to BGR for overlay
            detail_bgr = cv2.cvtColor(detail, cv2.COLOR_GRAY2BGR)

            # Overlay grayscale detail onto thermal with strength-controlled blending
            # Higher strength = more visible RGB structure
            blend_strength = self.fusion_intensity * self.detail_strength
            result = cv2.addWeighted(
                thermal, 1.0 - blend_strength * 0.3,  # Slightly reduce thermal
                detail_bgr, blend_strength * 0.7,      # Strength-controlled detail overlay
                0
            )

            return result

        except Exception as e:
            logger.error(f"Detail Injection fusion error: {e}")
            return thermal

    def _relief_fusion(self, thermal: np.ndarray, rgb: np.ndarray) -> np.ndarray:
        """
        Relief Fusion - Embossing filter for 3D bas-relief effect
        Creates 3D bas-relief appearance with highlights/shadows from RGB structure

        Uses convolution with emboss kernel to create raised/recessed appearance
        based on edges and gradients in the visible light image.

        Args:
            thermal: Thermal frame (BGR, colorized)
            rgb: RGB frame (BGR, aligned)

        Returns:
            Relief-fused thermal frame (thermal + embossed RGB structure)
        """
        try:
            # Convert RGB to grayscale for embossing
            rgb_gray = cv2.cvtColor(rgb, cv2.COLOR_BGR2GRAY)

            # Apply emboss filter using convolution kernel
            # Creates highlights (bright) on top/left edges, shadows (dark) on bottom/right
            # Quality controls emboss kernel strength
            kernel_strength = 1.0 + self.detail_quality * 2.0  # Range: 1.0 to 3.0
            emboss_kernel = np.array([
                [-2, -1,  0],
                [-1,  1,  1],
                [ 0,  1,  2]
            ], dtype=np.float32) * kernel_strength

            # Apply emboss convolution
            embossed = cv2.filter2D(rgb_gray, -1, emboss_kernel)

            # Normalize and add gray offset to center around 128
            # This creates the highlight/shadow effect for 3D appearance
            embossed = embossed.astype(np.float32)
            embossed = embossed + 128.0  # Center at mid-gray
            embossed = np.clip(embossed, 0, 255).astype(np.uint8)

            # Convert embossed grayscale to BGR for blending
            embossed_bgr = cv2.cvtColor(embossed, cv2.COLOR_GRAY2BGR)

            # Blend embossed details onto thermal
            # Use fusion_intensity and detail_strength to control how strong the embossing appears
            blend_strength = self.fusion_intensity * self.detail_strength
            result = cv2.addWeighted(
                thermal, 1.0 - blend_strength * 0.5,  # Thermal base
                embossed_bgr, blend_strength * 0.5,     # Strength-controlled embossed structure
                0
            )

            return result

        except Exception as e:
            logger.error(f"Relief Fusion error: {e}")
            return thermal

    def _edge_enhanced(self, thermal: np.ndarray, rgb: np.ndarray) -> np.ndarray:
        """
        Edge-enhanced fusion with priority control
        Extracts edges from one source and overlays on the other
        Uses configurable edge colors, strength, and fuzziness

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

                # Extract edges with configurable thresholds (no pre-blur)
                edges = cv2.Canny(thermal_gray,
                                 self.edge_threshold_low,
                                 self.edge_threshold_high)

                # Apply Gaussian blur to edges if configured (for softer edge appearance)
                # This creates smooth gradients around edges instead of sharp lines
                if self.edge_blur_kernel > 0:
                    edges = cv2.GaussianBlur(edges,
                                            (self.edge_blur_kernel, self.edge_blur_kernel),
                                            0)

                # Normalize edges to 0.0-1.0 for alpha blending
                edges_normalized = edges.astype(np.float32) / 255.0

                # Create colored edge overlay using edge values as alpha
                result = rgb.copy().astype(np.float32)
                edge_color_rgb = np.array(self.rgb_priority_edge_color, dtype=np.float32)

                # Blend edges with intensity: result = rgb * (1 - alpha) + edge_color * alpha
                for c in range(3):
                    alpha_channel = edges_normalized * self.fusion_intensity
                    result[:, :, c] = result[:, :, c] * (1 - alpha_channel) + edge_color_rgb[c] * alpha_channel

                result = np.clip(result, 0, 255).astype(np.uint8)
            else:
                # Thermal base + RGB edges (inverted priority)
                # Extract edges from RGB
                rgb_gray = cv2.cvtColor(rgb, cv2.COLOR_BGR2GRAY)

                # Extract edges with configurable thresholds (no pre-blur)
                edges = cv2.Canny(rgb_gray,
                                 self.edge_threshold_low,
                                 self.edge_threshold_high)

                # Apply Gaussian blur to edges if configured (for softer edge appearance)
                # This creates smooth gradients around edges instead of sharp lines
                if self.edge_blur_kernel > 0:
                    edges = cv2.GaussianBlur(edges,
                                            (self.edge_blur_kernel, self.edge_blur_kernel),
                                            0)

                # Normalize edges to 0.0-1.0 for alpha blending
                edges_normalized = edges.astype(np.float32) / 255.0

                # Create colored edge overlay using edge values as alpha
                result = thermal.copy().astype(np.float32)
                edge_color_rgb = np.array(self.thermal_priority_edge_color, dtype=np.float32)

                # Blend edges with intensity: result = thermal * (1 - alpha) + edge_color * alpha
                for c in range(3):
                    alpha_channel = edges_normalized * self.fusion_intensity
                    result[:, :, c] = result[:, :, c] * (1 - alpha_channel) + edge_color_rgb[c] * alpha_channel

                result = np.clip(result, 0, 255).astype(np.uint8)

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

            # Calculate allocated inset dimensions
            main_h, main_w = main.shape[:2]
            allocated_w = int(main_w * pip_size)
            allocated_h = int(main_h * pip_size)

            # CRITICAL FIX: Maintain aspect ratio when resizing inset
            # This matches the pip_thermal_rect calculation in inspection_gui_qt.py
            inset_h, inset_w = inset.shape[:2]
            inset_aspect = inset_w / inset_h
            allocated_aspect = allocated_w / allocated_h

            logger.info(f"[FUSION PIP] Inset: {inset_w}x{inset_h} (aspect {inset_aspect:.3f}), Allocated: {allocated_w}x{allocated_h} (aspect {allocated_aspect:.3f})")

            if inset_aspect > allocated_aspect:
                # Inset is wider, fit to width
                actual_w = allocated_w
                actual_h = int(allocated_w / inset_aspect)
                offset_x = 0
                offset_y = (allocated_h - actual_h) // 2
            else:
                # Inset is taller, fit to height
                actual_h = allocated_h
                actual_w = int(allocated_h * inset_aspect)
                offset_x = (allocated_w - actual_w) // 2
                offset_y = 0

            logger.info(f"[FUSION PIP] Actual size: {actual_w}x{actual_h}, Offset: ({offset_x}, {offset_y})")

            # Resize inset maintaining aspect ratio
            inset_resized = cv2.resize(inset, (actual_w, actual_h))

            # Determine position for allocated space
            margin = 10
            if position == 'top-right':
                x, y = main_w - allocated_w - margin, margin
            elif position == 'top-left':
                x, y = margin, margin
            elif position == 'bottom-right':
                x, y = main_w - allocated_w - margin, main_h - allocated_h - margin
            else:  # bottom-left
                x, y = margin, main_h - allocated_h - margin

            # Add border to inset
            inset_with_border = cv2.copyMakeBorder(
                inset_resized, 2, 2, 2, 2,
                cv2.BORDER_CONSTANT, value=[255, 255, 255]
            )

            # Overlay inset on main at aspect-ratio-corrected position
            ih, iw = inset_with_border.shape[:2]
            main[y+offset_y:y+offset_y+ih, x+offset_x:x+offset_x+iw] = inset_with_border

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

    def _thermal_contours(self, thermal: np.ndarray, rgb: np.ndarray) -> np.ndarray:
        """
        Thermal Contours on RGB - Phase 3 Feature 12
        Overlays thermal contour lines on RGB image to show temperature boundaries.

        Args:
            thermal: Thermal frame (BGR, colorized)
            rgb: RGB frame (BGR, aligned)

        Returns:
            RGB frame with thermal contour overlay
        """
        try:
            # Start with RGB as base
            result = rgb.copy()

            # Convert thermal to grayscale for contour detection
            thermal_gray = cv2.cvtColor(thermal, cv2.COLOR_BGR2GRAY)

            # Find contours at multiple temperature levels
            # Create several threshold levels to show temperature gradients
            num_levels = 8
            contour_colors = [
                (0, 0, 255),      # Red (hottest)
                (0, 128, 255),    # Orange
                (0, 255, 255),    # Yellow
                (0, 255, 128),    # Yellow-green
                (0, 255, 0),      # Green
                (128, 255, 0),    # Cyan-green
                (255, 255, 0),    # Cyan
                (255, 0, 0)       # Blue (coolest)
            ]

            # Find min and max values
            t_min = thermal_gray.min()
            t_max = thermal_gray.max()

            if t_max - t_min < 10:
                # Not enough temperature variation
                return result

            # Draw contours for each level
            for i in range(num_levels):
                threshold_val = t_min + (t_max - t_min) * (i + 1) / (num_levels + 1)
                _, thresh = cv2.threshold(thermal_gray, threshold_val, 255, cv2.THRESH_BINARY)

                # Find contours
                contours, _ = cv2.findContours(thresh, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)

                # Draw contours
                color = contour_colors[i % len(contour_colors)]
                cv2.drawContours(result, contours, -1, color, 2)

            # Optionally add semi-transparent thermal overlay
            if self.fusion_intensity > 0.3:
                # Add subtle thermal color overlay
                alpha = (self.fusion_intensity - 0.3) * 0.5  # Max 0.35 alpha
                result = cv2.addWeighted(result, 1.0 - alpha, thermal, alpha, 0)

            return result

        except Exception as e:
            logger.error(f"Thermal contours error: {e}")
            return rgb

    def _enhanced_edge_highlight(self, thermal: np.ndarray, rgb: np.ndarray) -> np.ndarray:
        """
        Enhanced Edge Highlight Fusion - Phase 3 Feature 13
        Advanced edge detection with multi-scale analysis and adaptive thresholding.
        Provides more prominent and accurate edge visualization than basic edge_enhanced mode.

        Args:
            thermal: Thermal frame (BGR, colorized)
            rgb: RGB frame (BGR, aligned)

        Returns:
            Fused frame with enhanced edge highlighting
        """
        try:
            # Determine base and overlay based on priority
            if self.fusion_priority == 'thermal':
                base = thermal
                overlay_source = rgb
                edge_color = self.thermal_priority_edge_color
            else:
                base = rgb
                overlay_source = thermal
                edge_color = self.rgb_priority_edge_color

            result = base.copy()

            # Convert overlay source to grayscale
            if len(overlay_source.shape) == 3:
                overlay_gray = cv2.cvtColor(overlay_source, cv2.COLOR_BGR2GRAY)
            else:
                overlay_gray = overlay_source

            # Apply Gaussian blur for noise reduction (adaptive based on edge_blur_kernel)
            if self.edge_blur_kernel > 0:
                kernel_size = self.edge_blur_kernel if self.edge_blur_kernel % 2 == 1 else self.edge_blur_kernel + 1
                overlay_gray = cv2.GaussianBlur(overlay_gray, (kernel_size, kernel_size), 0)

            # Multi-scale edge detection for enhanced results
            # Scale 1: Fine details
            edges_fine = cv2.Canny(overlay_gray, self.edge_threshold_low, self.edge_threshold_high)

            # Scale 2: Medium features (dilate to capture broader structures)
            kernel_medium = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
            gray_medium = cv2.morphologyEx(overlay_gray, cv2.MORPH_GRADIENT, kernel_medium)
            edges_medium = cv2.Canny(gray_medium, self.edge_threshold_low * 0.7, self.edge_threshold_high * 0.7)

            # Scale 3: Large features
            kernel_large = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
            gray_large = cv2.morphologyEx(overlay_gray, cv2.MORPH_GRADIENT, kernel_large)
            edges_large = cv2.Canny(gray_large, self.edge_threshold_low * 0.5, self.edge_threshold_high * 0.5)

            # Combine multi-scale edges (weighted combination)
            edges = cv2.addWeighted(edges_fine, 0.5, edges_medium, 0.3, 0)
            edges = cv2.add(edges, cv2.addWeighted(edges_large, 0.2, np.zeros_like(edges_large), 0, 0))

            # Apply morphological operations to enhance edge connectivity
            kernel_connect = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2, 2))
            edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel_connect)

            # Dilate edges slightly for better visibility (controlled by fusion_intensity)
            if self.fusion_intensity > 0.3:
                dilation_size = int(1 + self.fusion_intensity * 2)
                kernel_dilate = cv2.getStructuringElement(cv2.MORPH_RECT, (dilation_size, dilation_size))
                edges = cv2.dilate(edges, kernel_dilate, iterations=1)

            # Create colored edge overlay
            edge_mask = edges > 0
            if edge_mask.any():
                # Apply edge color with intensity-based alpha
                edge_alpha = 0.6 + (self.fusion_intensity * 0.4)  # Range: 0.6 to 1.0

                # Create edge layer
                edge_layer = np.zeros_like(result)
                edge_layer[edge_mask] = edge_color

                # Blend edges onto result
                result = cv2.addWeighted(result, 1.0, edge_layer, edge_alpha, 0)

            return result

        except Exception as e:
            logger.error(f"Enhanced edge highlight error: {e}")
            return self._edge_enhanced(thermal, rgb)

    def _laplacian_pyramid(
        self, thermal: np.ndarray, rgb: np.ndarray, levels: int = 4
    ) -> np.ndarray:
        """
        Multi-scale Laplacian Pyramid blending.

        Blends thermal and RGB at each frequency scale independently, guided
        by the local edge energy of the thermal frame.  This eliminates the
        halo/ghosting artefacts produced by per-pixel gradient weighting
        (feature_weighted mode) while preserving sharp RGB texture detail.

        Uses only standard OpenCV (pyrDown / pyrUp) — no contrib required.

        Args:
            thermal: Colourised thermal frame (BGR)
            rgb:     Aligned RGB frame (BGR)
            levels:  Number of pyramid levels (4 is a good default for 640×512)

        Returns:
            Blended BGR frame
        """
        thermal_f = thermal.astype(np.float32)
        rgb_f = rgb.astype(np.float32)

        # Build Gaussian pyramids
        gp_thermal = [thermal_f]
        gp_rgb = [rgb_f]
        for _ in range(levels):
            gp_thermal.append(cv2.pyrDown(gp_thermal[-1]))
            gp_rgb.append(cv2.pyrDown(gp_rgb[-1]))

        # Build Laplacian pyramids
        lp_thermal = []
        lp_rgb = []
        for i in range(levels):
            h, w = gp_thermal[i].shape[:2]
            up_t = cv2.pyrUp(gp_thermal[i + 1], dstsize=(w, h))
            up_r = cv2.pyrUp(gp_rgb[i + 1], dstsize=(w, h))
            lp_thermal.append(gp_thermal[i] - up_t)
            lp_rgb.append(gp_rgb[i] - up_r)
        lp_thermal.append(gp_thermal[levels])
        lp_rgb.append(gp_rgb[levels])

        # Build per-level weight maps from thermal edge energy
        # (higher local gradient → more thermal; smooth areas → more RGB)
        gray_thermal = cv2.cvtColor(thermal, cv2.COLOR_BGR2GRAY).astype(np.float32)
        gp_weight = [gray_thermal]
        for _ in range(levels):
            gp_weight.append(cv2.pyrDown(gp_weight[-1]))

        blended_pyramid = []
        for i in range(levels + 1):
            # Normalise edge energy to [0, 1] as blend weight for thermal
            w_map = gp_weight[i]
            sobel_x = cv2.Sobel(w_map, cv2.CV_32F, 1, 0, ksize=3)
            sobel_y = cv2.Sobel(w_map, cv2.CV_32F, 0, 1, ksize=3)
            edge = cv2.magnitude(sobel_x, sobel_y)

            # Avoid division by zero; scale to [0, 1]
            max_e = edge.max()
            alpha_map = (edge / max_e) if max_e > 0 else np.zeros_like(edge)
            alpha_map = cv2.GaussianBlur(alpha_map, (5, 5), 0)   # smooth weight map
            alpha_map = np.clip(alpha_map, 0.0, 1.0)
            # Apply overall fusion intensity
            alpha_map = alpha_map * self.fusion_intensity
            # Expand to 3-channel
            alpha_3 = np.stack([alpha_map] * 3, axis=-1)


            blended = lp_thermal[i] * alpha_3 + lp_rgb[i] * (1.0 - alpha_3)
            blended_pyramid.append(blended)

        # Reconstruct from blended pyramid
        result = blended_pyramid[levels]
        for i in range(levels - 1, -1, -1):
            h, w = blended_pyramid[i].shape[:2]
            result = cv2.pyrUp(result, dstsize=(w, h)) + blended_pyramid[i]

        return np.clip(result, 0, 255).astype(np.uint8)

    def set_fusion_mode(self, mode: str):
        """Change fusion mode"""
        valid_modes = [
            'alpha_blend', 'edge_enhanced', 'thermal_overlay',
            'side_by_side', 'picture_in_picture', 'max_intensity',
            'feature_weighted', 'thermal_contours', 'enhanced_edge_highlight',
            'laplacian_pyramid',
        ]
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
        return [
            'alpha_blend', 'edge_enhanced', 'thermal_overlay',
            'side_by_side', 'picture_in_picture', 'max_intensity',
            'feature_weighted', 'thermal_contours', 'enhanced_edge_highlight',
            'laplacian_pyramid',
        ]


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
