"""
ROI Controller for Thermal Inspection application.

Manages Region of Interest (ROI) operations and delegates to ROIManager.
Extracted from ThermalInspectionFusion class in inspection_main.py.
"""

import logging
from typing import Optional, Callable, List, Dict, Any
from dataclasses import dataclass

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class ROIControllerState:
    """Current state of ROI controller."""
    drawing_mode: bool = False
    auto_detect_enabled: bool = False
    roi_count: int = 0
    last_detected_temp_rois: int = 0
    last_detected_gradient_rois: int = 0


class ROIController:
    """
    Manages ROI operations for thermal inspection.

    This controller handles:
    - ROI drawing mode activation
    - Automatic ROI detection
    - ROI clearing and deletion
    - ROI persistence (save/load)
    - ROI palette management

    Usage:
        controller = ROIController()
        controller.set_roi_manager(roi_manager)
        controller.on_rois_changed = my_callback
        controller.auto_detect(thermal_frame)
    """

    def __init__(self):
        """Initialize ROIController."""
        self.state = ROIControllerState()

        # Manager instances (set externally)
        self.roi_manager = None
        self.palette_manager = None
        self.thermal_analyzer = None

        # Callbacks
        self.on_rois_changed: Optional[Callable[[Dict[str, Any]], None]] = None
        self.on_drawing_mode_changed: Optional[Callable[[bool], None]] = None
        self.on_roi_deleted: Optional[Callable[[str], None]] = None

    def set_roi_manager(self, manager):
        """
        Set the ROIManager instance.

        Args:
            manager: ROIManager instance to delegate to
        """
        self.roi_manager = manager

    def set_palette_manager(self, manager):
        """
        Set the palette manager.

        Args:
            manager: PaletteManager instance
        """
        self.palette_manager = manager

    def set_thermal_analyzer(self, analyzer):
        """
        Set the thermal analyzer.

        Args:
            analyzer: ThermalAnalyzer instance
        """
        self.thermal_analyzer = analyzer

    def _notify_rois_changed(self):
        """Notify listeners that ROIs have changed."""
        if self.on_rois_changed and self.roi_manager:
            roi_data = self._get_roi_data()
            self.on_rois_changed(roi_data)

    def _get_roi_data(self) -> Dict[str, Any]:
        """Get current ROI data for callbacks."""
        if not self.roi_manager:
            return {}

        rois = self.roi_manager.get_all_rois() if hasattr(self.roi_manager, 'get_all_rois') else []
        self.state.roi_count = len(rois)

        return {
            'count': len(rois),
            'rois': rois
        }

    def enable_drawing_mode(self):
        """Enable ROI drawing mode in GUI."""
        self.state.drawing_mode = True
        logger.info("Draw ROI mode activated")

        if self.on_drawing_mode_changed:
            self.on_drawing_mode_changed(True)

    def disable_drawing_mode(self):
        """Disable ROI drawing mode."""
        self.state.drawing_mode = False

        if self.on_drawing_mode_changed:
            self.on_drawing_mode_changed(False)

    def auto_detect(self, thermal_frame: np.ndarray) -> tuple:
        """
        Automatically detect ROIs based on temperature gradients.

        Args:
            thermal_frame: Thermal image frame

        Returns:
            Tuple of (temp_roi_count, gradient_roi_count)
        """
        if not self.roi_manager or thermal_frame is None:
            return (0, 0)

        try:
            # Detect ROIs based on temperature (hot and cold regions)
            temp_rois = self.roi_manager.detect_temperature_rois(
                thermal_frame, detect_hot=True, detect_cold=True
            )

            # Detect ROIs based on thermal gradients
            gradient_rois = self.roi_manager.detect_gradient_rois(thermal_frame)

            self.state.last_detected_temp_rois = len(temp_rois)
            self.state.last_detected_gradient_rois = len(gradient_rois)

            logger.info(f"Auto-detected {len(temp_rois)} temperature ROIs and {len(gradient_rois)} gradient ROIs")

            # NMS Cleanup (remove overlapping ROIs)
            self.roi_manager.cleanup_overlapping_rois()

            self._notify_rois_changed()

            return (len(temp_rois), len(gradient_rois))

        except Exception as e:
            logger.error(f"Error during auto ROI detection: {e}")
            return (0, 0)

    def clear_all(self):
        """Clear all ROIs."""
        if not self.roi_manager:
            return

        self.roi_manager.clear_all_rois()

        self.state.roi_count = 0
        logger.info("All ROIs cleared")

        self._notify_rois_changed()

    def delete_roi(self, roi_id: str):
        """
        Delete a specific ROI.

        Args:
            roi_id: ID of ROI to delete
        """
        if not self.roi_manager:
            return

        self.roi_manager.delete_roi(roi_id)

        # Clear any associated palette config
        if self.palette_manager:
            self.palette_manager.clear_roi_palette(roi_id)

        logger.info(f"ROI {roi_id} deleted")

        if self.on_roi_deleted:
            self.on_roi_deleted(roi_id)

        self._notify_rois_changed()

    def set_roi_palette(self, roi_id: str, palette_name: str):
        """
        Set palette for a specific ROI.

        Args:
            roi_id: ID of ROI
            palette_name: Name of palette to apply
        """
        if self.palette_manager:
            self.palette_manager.set_roi_palette(roi_id, palette_name)
            logger.info(f"ROI {roi_id} palette set to: {palette_name}")

    def save_rois(self, filename: str) -> bool:
        """
        Save ROIs to JSON file.

        Args:
            filename: Path to save file

        Returns:
            True if successful
        """
        if not self.roi_manager:
            return False

        success = self.roi_manager.save_rois(filename)
        logger.info(f"ROIs {'saved to' if success else 'failed to save to'} {filename}")
        return success

    def load_rois(self, filename: str) -> bool:
        """
        Load ROIs from JSON file.

        Args:
            filename: Path to load file

        Returns:
            True if successful
        """
        if not self.roi_manager:
            return False

        success = self.roi_manager.load_rois(filename)
        logger.info(f"ROIs {'loaded from' if success else 'failed to load from'} {filename}")

        if success:
            self._notify_rois_changed()

        return success

    # Properties
    @property
    def is_drawing(self) -> bool:
        """Check if in drawing mode."""
        return self.state.drawing_mode

    @property
    def count(self) -> int:
        """Get current ROI count."""
        return self.state.roi_count

    def get_all_rois(self) -> List:
        """Get all ROIs from manager."""
        if self.roi_manager and hasattr(self.roi_manager, 'get_all_rois'):
            return self.roi_manager.get_all_rois()
        return []

    @property
    def rois(self) -> List:
        """Shortcut for getting all ROIs."""
        return self.get_all_rois()
