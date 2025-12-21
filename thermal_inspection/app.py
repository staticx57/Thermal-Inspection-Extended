"""
Thermal Inspection Application Coordinator.

This is the slim coordinator that composes all controllers and provides
a clean interface for the main entry point. Extracted from the monolithic
ThermalInspectionFusion class in inspection_main.py.
"""

import sys
import logging
import time
from typing import Optional, Any, List, Dict, Tuple
from dataclasses import dataclass

import cv2
import numpy as np
from PyQt6.QtCore import QTimer

from .core import (
    CameraController, CameraConfig, CameraState,
    FusionController, FusionState, ViewMode,
    ROIController, ROIControllerState,
    RadiometricController, RadiometricState, TemperatureUnit,
)

logger = logging.getLogger(__name__)


@dataclass
class AppConfig:
    """Application configuration."""
    # Camera settings
    thermal_device: Optional[int] = None
    rgb_device: Optional[int] = None
    disable_rgb: bool = False
    width: int = 640
    height: int = 512
    thermal_backend: str = 'opencv'
    enable_boson_sdk: bool = True
    boson_com_port: str = 'COM7'

    # Fusion settings
    fusion_mode: str = 'thermal_overlay'
    fusion_alpha: float = 0.5

    # Processing settings
    device: str = 'cuda'
    palette: str = 'ironbow'
    radiometric: bool = False

    # GUI settings
    gui_type: str = 'qt'
    headless: bool = False

    @classmethod
    def from_args(cls, args) -> 'AppConfig':
        """Create config from argparse namespace."""
        return cls(
            thermal_device=getattr(args, 'thermal_device', None),
            rgb_device=getattr(args, 'rgb_device', None),
            disable_rgb=getattr(args, 'disable_rgb', False),
            width=getattr(args, 'width', 640),
            height=getattr(args, 'height', 512),
            thermal_backend=getattr(args, 'thermal_backend', 'opencv'),
            enable_boson_sdk=getattr(args, 'enable_boson_sdk', True),
            boson_com_port=getattr(args, 'boson_com_port', 'COM7'),
            fusion_mode=getattr(args, 'fusion_mode', 'thermal_overlay'),
            fusion_alpha=getattr(args, 'fusion_alpha', 0.5),
            device=getattr(args, 'device', 'cuda'),
            palette=getattr(args, 'palette', 'ironbow'),
            radiometric=getattr(args, 'radiometric', False),
            gui_type=getattr(args, 'gui', 'qt'),
            headless=getattr(args, 'headless', False),
        )


class ThermalInspectionApp:
    """
    Main application coordinator for Thermal Inspection.

    This class composes all controllers and provides a unified interface
    for the application lifecycle.

    Usage:
        app = ThermalInspectionApp(config)
        if app.initialize():
            app.run()
        app.cleanup()
    """

    def __init__(self, config: Optional[AppConfig] = None, qt_app=None):
        """
        Initialize the application.

        Args:
            config: Application configuration
            qt_app: Optional QApplication instance for Qt GUI
        """
        self.config = config or AppConfig()
        self.qt_app = qt_app

        # Initialize controllers
        self._init_controllers()

        # GUI reference (set during initialization)
        self.gui = None

        # Processing components (set during initialization)
        self.fusion_processor = None
        self.thermal_processor = None
        self.thermal_analyzer = None
        self.roi_manager = None
        self.palette_manager = None

        # State flags
        self.initialized = False
        self.running = False
        self.frame_frozen = False
        self.recording_enabled = False
        self.enabled_anomaly_types = {}
        self.view_mode = ViewMode.THERMAL_ONLY # Initial default
        self.args = config # Legacy compatibility for GUI

        # New: Processing loop state
        self.timer = QTimer()
        self.timer.timeout.connect(self._process_frame_loop)
        self.frame_count = 0
        self.last_fps_time = time.time()
        self.frame_times = []
        self.smoothed_fps = 0.0

        # Placeholders
        self.thermal_placeholder = None
        self.rgb_placeholder = None

    def _init_controllers(self):
        """Initialize all controllers."""
        # Camera controller
        camera_config = CameraConfig(
            thermal_device=self.config.thermal_device,
            rgb_device=self.config.rgb_device,
            disable_rgb=self.config.disable_rgb,
            width=self.config.width,
            height=self.config.height,
            thermal_backend=self.config.thermal_backend,
            enable_boson_sdk=self.config.enable_boson_sdk,
            boson_com_port=self.config.boson_com_port,
        )
        self.camera_controller = CameraController(camera_config)

        # Fusion controller
        self.fusion_controller = FusionController(
            initial_mode=self.config.fusion_mode,
            initial_alpha=self.config.fusion_alpha,
        )

        # ROI controller
        self.roi_controller = ROIController()

        # Radiometric controller
        self.radiometric_controller = RadiometricController()

        # Wire up controller callbacks
        self._wire_callbacks()

    def _wire_callbacks(self):
        """Wire up callbacks between controllers."""
        # Camera state changes
        self.camera_controller.on_state_change = self._on_camera_state_change
        self.camera_controller.on_radiometric_detected = self._on_radiometric_detected

        # Fusion state changes
        self.fusion_controller.on_state_change = self._on_fusion_state_change
        self.fusion_controller.on_mode_change = self._on_fusion_mode_change

        # ROI changes
        self.roi_controller.on_rois_changed = self._on_rois_changed

        # Radiometric changes
        self.radiometric_controller.on_state_change = self._on_radiometric_state_change

    def _on_camera_state_change(self, state: CameraState):
        """Handle camera state changes."""
        logger.debug(f"Camera state changed: thermal={state.thermal_connected}, rgb={state.rgb_available}")
        if self.gui and hasattr(self.gui, 'update_camera_status'):
            self.gui.update_camera_status(state)

    def _on_radiometric_detected(self, is_radiometric: bool):
        """Handle radiometric mode detection."""
        logger.info(f"Radiometric mode detected: {is_radiometric}")
        self.radiometric_controller.state.capable = is_radiometric
        self.radiometric_controller.state.enabled = is_radiometric

    def _on_fusion_state_change(self, state: FusionState):
        """Handle fusion state changes."""
        logger.debug(f"Fusion state changed: mode={state.mode}, alpha={state.alpha}")

    def _on_fusion_mode_change(self, mode: str):
        """Handle fusion mode change."""
        if self.gui and hasattr(self.gui, 'control_panel'):
            self.gui.control_panel.update_fusion_mode_button(mode)

    def _on_rois_changed(self, roi_data: dict):
        """Handle ROI changes."""
        if self.gui and hasattr(self.gui, 'roi_temp_panel'):
            self.gui.roi_temp_panel.update_roi_data(roi_data)

    def _on_radiometric_state_change(self, state: RadiometricState):
        """Handle radiometric state changes."""
        if self.gui and hasattr(self.gui, 'radiometric_panel'):
            self.gui.radiometric_panel.set_radiometric_status(
                state.capable, state.enabled, state.mode
            )

    def initialize(self) -> bool:
        """
        Initialize all application components.

        Returns:
            True if initialization successful
        """
        logger.info("=" * 80)
        logger.info("Thermal Inspection Fusion Tool")
        logger.info("=" * 80)

        try:
            # Initialize cameras (allow fallback mode with no cameras)
            thermal_ok, rgb_ok = self.camera_controller.initialize_cameras()

            if not thermal_ok and not rgb_ok:
                logger.warning("No cameras available - running in fallback mode")

            # Initialize processing components
            self._init_processing()

            # Connect controllers to components
            self._connect_controllers()

            # Initialize GUI if not headless
            if not self.config.headless:
                self._init_gui()

            # Pre-allocate placeholders
            self._init_placeholders()

            self.initialized = True
            logger.info("Initialization complete")
            return True

        except Exception as e:
            logger.error(f"Initialization failed: {e}", exc_info=True)
            return False

    def _init_processing(self):
        """Initialize processing components."""
        # Import processing modules from new package structure
        try:
            from .processing import FusionProcessor, ThermalProcessor, ThermalAnalyzer
            from .processing import ROIManager, PaletteManager

            # Create processors
            self.fusion_processor = FusionProcessor()
            self.fusion_controller.set_fusion_processor(self.fusion_processor)

            self.thermal_processor = ThermalProcessor({'device': self.config.device})
            self.thermal_analyzer = ThermalAnalyzer()
            self.roi_manager = ROIManager()
            self.palette_manager = PaletteManager({'default_palette': self.config.palette})

            logger.info("Processing components initialized")

        except ImportError as e:
            logger.warning(f"Some processing components not available: {e}")

    def _connect_controllers(self):
        """Connect controllers to processing components."""
        # ROI controller
        if self.roi_manager:
            self.roi_controller.set_roi_manager(self.roi_manager)
        if self.palette_manager:
            self.roi_controller.set_palette_manager(self.palette_manager)
        if self.thermal_analyzer:
            self.roi_controller.set_thermal_analyzer(self.thermal_analyzer)

        # Radiometric controller
        if self.camera_controller.thermal_camera:
            self.radiometric_controller.set_thermal_camera(
                self.camera_controller.thermal_camera
            )
        if self.thermal_analyzer:
            self.radiometric_controller.set_thermal_analyzer(self.thermal_analyzer)

    def _init_gui(self):
        """Initialize GUI components."""
        if self.config.gui_type == 'qt' and self.qt_app:
            try:
                from .gui import InspectionAppWindow
                self.gui = InspectionAppWindow(self)
                self.gui.show()
                logger.info("Qt GUI initialized")
            except ImportError as e:
                logger.warning(f"Qt GUI not available: {e}")

    def run(self):
        """Run the main application loop."""
        if not self.initialized:
            logger.error("Application not initialized")
            return

        self.running = True
        logger.info("Starting main loop")

        # Start processing timer (30 FPS)
        self.timer.start(33)

        try:
            if self.qt_app:
                # Qt event loop
                sys.exit(self.qt_app.exec())
            else:
                # Headless or OpenCV loop
                self._run_headless_loop()

        except KeyboardInterrupt:
            logger.info("Interrupted by user")
        finally:
            self.cleanup()

    def _run_headless_loop(self):
        """Run headless processing loop."""
        import time

        while self.running:
            # Process frames
            # This would be expanded with actual processing logic
            time.sleep(0.1)

    def cleanup(self):
        """Clean up resources."""
        logger.info("Cleaning up...")
        self.running = False
        self.timer.stop()

        # Release cameras
        self.camera_controller.release_cameras()

        logger.info("Cleanup complete")

    @property
    def thermal_camera(self):
        """Get thermal camera instance."""
        return self.camera_controller.thermal_camera

    @property
    def rgb_camera(self):
        """Get RGB camera instance."""
        return self.camera_controller.rgb_camera

    # Public API methods that delegate to controllers

    def set_fusion_mode(self, mode: str):
        """Set fusion mode."""
        self.fusion_controller.set_mode(mode)

    def set_fusion_alpha(self, alpha: float):
        """Set fusion alpha."""
        self.fusion_controller.set_alpha(alpha)

    def cycle_fusion_mode(self):
        """Cycle to next fusion mode."""
        return self.fusion_controller.cycle_mode()

    def swap_cameras(self):
        """Swap camera assignments."""
        return self.camera_controller.swap_cameras()

    def auto_roi_detect(self):
        """Auto-detect ROIs (alias for auto_detect_rois)."""
        # In a real app, we'd need the latest frame. 
        # For now, this is a placeholder or delegates to controller if it tracks frames.
        pass

    def clear_rois(self):
        """Clear all ROIs."""
        self.roi_controller.clear_all()

    def set_temperature_unit(self, unit: str):
        """Set temperature display unit."""
        self.radiometric_controller.set_temperature_unit(unit)

    def enable_radiometric(self, enable: bool):
        """Enable/disable radiometric mode."""
        return self.radiometric_controller.enable_radiometric(enable)

    def swap_cameras(self):
        """Swap thermal and RGB cameras."""
        return self.camera_controller.swap_cameras()

    def reassign_cameras(self, thermal_id: int, rgb_id: int):
        """Reassign camera device IDs."""
        return self.camera_controller.reassign_cameras(thermal_id, rgb_id)

    def switch_thermal_backend(self, backend_id: str):
        """Switch thermal camera backend (opencv/flirpy)."""
        logger.info(f"Switching thermal backend to {backend_id}")
        self.config.thermal_backend = backend_id
        return self.camera_controller.reassign_cameras(
            self.camera_controller.state.thermal_device_id,
            self.camera_controller.state.rgb_device_id
        )

    def trigger_ffc(self):
        """Trigger Flat Field Correction (FFC)."""
        if hasattr(self.camera_controller.thermal_camera, 'trigger_ffc'):
            return self.camera_controller.thermal_camera.trigger_ffc()
        return False

    def _init_placeholders(self):
        """Pre-allocate placeholder frames for fallback mode."""
        w, h = self.config.width, self.config.height
        
        # Thermal placeholder (ironbow-ish gradient with text)
        self.thermal_placeholder = np.zeros((h, w, 3), dtype=np.uint8)
        cv2.putText(self.thermal_placeholder, "NO THERMAL SIGNAL", (w//4, h//2), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
        
        # RGB placeholder (dark gray with text)
        self.rgb_placeholder = np.full((h, w, 3), 40, dtype=np.uint8)
        cv2.putText(self.rgb_placeholder, "NO RGB SIGNAL", (w//3, h//2), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (200, 200, 200), 2)

    def _process_frame_loop(self):
        """Main processing loop triggered by timer."""
        if not self.running:
            return

        loop_start = time.time()
        self.frame_count += 1

        try:
            # 1. Capture frames
            thermal_frame, rgb_frame = self.camera_controller.capture_frames()
            
            # Handle fallback
            if thermal_frame is None:
                thermal_frame = self.thermal_placeholder
            
            if rgb_frame is None and not self.config.disable_rgb:
                rgb_frame = self.rgb_placeholder

            # 2. Process thermal & Colorization
            thermal_16bit = None
            if hasattr(self.camera_controller.thermal_camera, 'get_raw_frame'):
                thermal_16bit = self.camera_controller.thermal_camera.get_raw_frame()

            # Base colorized frame
            if thermal_frame is self.thermal_placeholder:
                colorized_thermal = thermal_frame
            elif self.palette_manager:
                colorized_thermal = self.palette_manager.apply_composite_palette(thermal_frame, self.roi_controller.roi_manager)
            else:
                colorized_thermal = cv2.cvtColor(thermal_frame, cv2.COLOR_GRAY2BGR) if len(thermal_frame.shape) == 2 else thermal_frame

            # Detections (Motion/Edges)
            proc_results = {}
            if self.thermal_processor and thermal_frame is not self.thermal_placeholder:
                proc_results = self.thermal_processor.process_frame(thermal_frame)
            
            # Anomaly Priority (Fade to gray)
            if self.thermal_processor and self.thermal_processor.anomaly_priority_enabled:
                 # Need anomalies from analyzer for this
                 pass # We'll do this after analysis

            # 3. Analyze (Radiometric stats)
            analysis_results = {
                'stats': None, 'hot_spots': [], 'cold_spots': [], 
                'anomalies': [], 'motion_detections': [], 
                'edge_clusters': [], 'trend': None
            }
            
            if self.thermal_analyzer and thermal_frame is not self.thermal_placeholder:
                # Use 16bit for analysis if available
                source_for_analysis = thermal_16bit if thermal_16bit is not None else thermal_frame
                analysis_results = self.thermal_analyzer.analyze(source_for_analysis)
            
            # Enrich analysis with proc_results (motion, edges)
            analysis_results['motion_detections'] = proc_results.get('motion_detections', [])
            analysis_results['edge_clusters'] = proc_results.get('edge_clusters', [])

            # Apply anomaly priority if enabled
            if self.thermal_processor and self.thermal_processor.anomaly_priority_enabled:
                colorized_thermal = self.thermal_processor.apply_anomaly_priority_colorization(
                    thermal_frame, analysis_results['anomalies'], colorized_thermal
                )

            # 4. Select display frame based on view mode
            display_frame = colorized_thermal  # Default
            
            if self.view_mode == ViewMode.THERMAL_ONLY:
                display_frame = colorized_thermal
            elif self.view_mode == ViewMode.RGB_ONLY:
                if rgb_frame is not None:
                    display_frame = rgb_frame
                else:
                    display_frame = self.rgb_placeholder if self.rgb_placeholder is not None else colorized_thermal
            elif self.view_mode == ViewMode.FUSION:
                if self.fusion_processor and rgb_frame is not None:
                    display_frame = self.fusion_processor.process(colorized_thermal, rgb_frame)
                else:
                    display_frame = colorized_thermal
            elif self.view_mode == ViewMode.SIDE_BY_SIDE:
                if rgb_frame is not None:
                    # Create side-by-side view
                    import cv2
                    h1, w1 = colorized_thermal.shape[:2]
                    h2, w2 = rgb_frame.shape[:2]
                    # Resize RGB to match thermal height
                    if h1 != h2:
                        rgb_resized = cv2.resize(rgb_frame, (int(w2 * h1 / h2), h1))
                    else:
                        rgb_resized = rgb_frame
                    display_frame = cv2.hconcat([colorized_thermal, rgb_resized])
                else:
                    display_frame = colorized_thermal
            elif self.view_mode == ViewMode.PICTURE_IN_PICTURE:
                if rgb_frame is not None:
                    import cv2
                    h, w = colorized_thermal.shape[:2]
                    pip_h, pip_w = int(h * 0.25), int(w * 0.25)
                    pip_rgb = cv2.resize(rgb_frame, (pip_w, pip_h))
                    display_frame = colorized_thermal.copy()
                    # Place PIP in top-right corner with margin
                    margin = 10
                    display_frame[margin:margin+pip_h, w-pip_w-margin:w-margin] = pip_rgb
                else:
                    display_frame = colorized_thermal

            # 5. Push to GUI
            if self.gui:
                self.gui.update_frame(display_frame)
                
                # Update metrics
                state = self.camera_controller.state
                self.gui.update_metrics(
                    fps=self.smoothed_fps,
                    roi_count=len(self.roi_controller.rois) if self.roi_controller else 0,
                    thermal_connected=state.thermal_connected,
                    rgb_connected=state.rgb_available
                )
                
                # Get palette LUT for histogram coloring
                palette_lut = None
                if self.palette_manager:
                    palette_lut = self.palette_manager.get_current_palette_lut()
                
                # Update analysis
                self.gui.update_thermal_analysis(
                    stats=analysis_results.get('stats'),
                    hot_spots=analysis_results.get('hot_spots', []),
                    cold_spots=analysis_results.get('cold_spots', []),
                    anomalies=analysis_results.get('anomalies', []),
                    motion_detections=analysis_results.get('motion_detections', []),
                    edge_clusters=analysis_results.get('edge_clusters', []),
                    trend=analysis_results.get('trend'),
                    temp_array=analysis_results.get('temp_array'),
                    palette_lut=palette_lut,
                    is_radiometric=analysis_results.get('is_radiometric', False)
                )
                
                # Update ROIs
                if self.roi_controller:
                    self.gui.update_rois(self.roi_controller.rois)

        except Exception as e:
            logger.error(f"Error in processing loop: {e}", exc_info=True)

        # Performance tracking
        loop_time = time.time() - loop_start
        self.frame_times.append(loop_time)
        if len(self.frame_times) > 30:
            self.frame_times.pop(0)
            avg_time = sum(self.frame_times) / len(self.frame_times)
            self.smoothed_fps = 1.0 / avg_time if avg_time > 0 else 0

        if self.frame_count % 30 == 0:
            logger.debug(f"Loop running: {self.smoothed_fps:.1f} FPS")

    def toggle_freeze(self, enabled: bool):
        """Toggle frame freeze."""
        self.frame_frozen = enabled
        logger.info(f"Frame freeze: {'ON' if enabled else 'OFF'}")

    def toggle_recording(self, enabled: bool):
        """Toggle recording."""
        self.recording_enabled = enabled
        logger.info(f"Recording: {'ON' if enabled else 'OFF'}")

    def cycle_palette(self):
        """Cycle to next palette."""
        if self.palette_manager:
            palettes = self.palette_manager.get_available_palettes()
            current = self.palette_manager.global_palette.palette_type.value
            try:
                idx = palettes.index(current)
                next_palette = palettes[(idx + 1) % len(palettes)]
                self.palette_manager.set_global_palette(next_palette)
                logger.info(f"Switched to palette: {next_palette}")
            except (ValueError, IndexError):
                if palettes:
                    self.palette_manager.set_global_palette(palettes[0])

    def set_palette(self, palette_name: str):
        """Set palette by name."""
        if self.palette_manager:
            try:
                from .processing import PaletteType
                self.palette_manager.set_global_palette(PaletteType(palette_name))
                logger.info(f"Switched to palette: {palette_name}")
            except Exception as e:
                logger.error(f"Failed to set palette {palette_name}: {e}")

    def cycle_view_mode(self):
        """Cycle view mode."""
        modes = [ViewMode.THERMAL_ONLY, ViewMode.RGB_ONLY, ViewMode.FUSION, 
                 ViewMode.SIDE_BY_SIDE, ViewMode.PICTURE_IN_PICTURE]
        try:
            idx = modes.index(self.view_mode)
            self.view_mode = modes[(idx + 1) % len(modes)]
            
            # Convert ViewMode enum to string format expected by set_view_mode
            mode_name_map = {
                ViewMode.THERMAL_ONLY: "thermal only",
                ViewMode.RGB_ONLY: "rgb only",
                ViewMode.FUSION: "fusion",
                ViewMode.SIDE_BY_SIDE: "side-by-side",
                ViewMode.PICTURE_IN_PICTURE: "picture-in-picture"
            }
            mode_str = mode_name_map.get(self.view_mode, "thermal only")
            self.fusion_controller.set_view_mode(mode_str)
            logger.info(f"Switched view mode to: {self.view_mode}")
        except ValueError:
            self.view_mode = modes[0]


    def capture_snapshot(self):
        """Capture snapshot."""
        logger.info("Snapshot capture requested")
        # Implement snapshot logic via a SnapshotManager if available
        pass

    def toggle_anomaly_priority(self, enabled: bool):
        """Toggle anomaly priority mode."""
        if self.thermal_processor and hasattr(self.thermal_processor, 'set_anomaly_priority_enabled'):
            self.thermal_processor.set_anomaly_priority_enabled(enabled)

    def set_enabled_anomaly_types(self, types_dict: dict):
        """Set enabled anomaly types."""
        self.enabled_anomaly_types = types_dict.copy()

    def delete_roi(self, roi_id: str):
        """Delete specific ROI."""
        self.roi_controller.delete_roi(roi_id)

    # Advanced Fusion/Edge settings placeholders 
    # (MainWindow calls these, so we need them to avoid AttributeErrors)
    def set_fusion_priority(self, priority: str):
        """Set fusion priority (thermal or rgb)."""
        if self.fusion_processor:
            self.fusion_processor.set_priority(priority)
            logger.info(f"Fusion priority set to: {priority}")
    def set_fusion_strength(self, strength: float):
        """Set fusion strength/intensity."""
        if self.fusion_processor:
            self.fusion_processor.set_intensity(strength)

    def set_fusion_fuzziness(self, fuzziness: float):
        """Set fusion edge blur/fuzziness."""
        if self.fusion_processor:
            # Convert float 0.0-1.0 to kernel size (0-15)
            kernel_size = int(fuzziness * 15)
            self.fusion_processor.set_edge_blur(kernel_size)

    def set_fusion_color_mode(self, mode: str):
        """Set fusion color mode (placeholder for now)."""
        # Feature pending in FusionProcessor
        pass

    def set_edge_strength(self, strength: float):
        """Set Canny edge detection thresholds based on strength."""
        if self.fusion_processor:
            # strength 0.0-1.0 -> low threshold 200-10
            # Higher strength = detect more edges = lower threshold
            low_thresh = int(200 - (strength * 190))
            self.fusion_processor.set_edge_strength(low_thresh)

    def set_edge_fuzziness(self, fuzziness: float):
        """Set edge blur/fuzziness."""
        if self.fusion_processor:
            kernel_size = int(fuzziness * 15)
            self.fusion_processor.set_edge_blur(kernel_size)

    def set_edge_color(self, color_name: str):
        """Set edge color."""
        # Simple color map
        colors = {
            'red': (0, 0, 255),
            'green': (0, 255, 0),
            'blue': (255, 0, 0),
            'cyan': (255, 255, 0),
            'magenta': (255, 0, 255),
            'yellow': (0, 255, 255),
            'white': (255, 255, 255),
            'black': (0, 0, 0)
        }
        if self.fusion_processor and color_name in colors:
            self.fusion_processor.set_edge_color(colors[color_name])

    def set_detail_strength(self, strength: float):
        """Set detail injection strength."""
        if self.fusion_processor:
             # direct property set - FusionProcessor doesn't have a setter for this yet?
             # Checking FusionProcessor, it has parameters but maybe not a setter method for just strength
             # It acts via FusionProcessor.detail_strength attribute
             self.fusion_processor.detail_strength = strength

    def set_detail_quality(self, quality: str):
        """Set detail quality (low/med/high)."""
        if self.fusion_processor:
            q_map = {'low': 0.0, 'medium': 0.5, 'high': 1.0}
            val = q_map.get(quality, 0.5)
            self.fusion_processor.detail_quality = val

    def set_emissivity(self, val: float):
        """Set emissivity value."""
        if self.thermal_analyzer:
            self.thermal_analyzer.set_emissivity(val)

    def set_atmospheric_temperature(self, val: float):
        """Set atmospheric temperature."""
        if self.thermal_analyzer:
            self.thermal_analyzer.set_atmospheric_temperature(val)

    def set_atmospheric_transmission(self, val: float):
        """Set atmospheric transmission."""
        if self.thermal_analyzer:
            self.thermal_analyzer.set_atmospheric_transmission(val)

    def set_manual_threshold_enabled(self, enabled: bool):
        """Enable/disable manual thresholding."""
        if self.thermal_analyzer:
            # Delegating to thermal analyzer or processor if it supports it
            # The ThermalAnalyzer is likely the right place for threshold logic
            pass # Pending implementation in ThermalAnalyzer

    def set_manual_threshold_mode(self, mode: str):
        pass

    def set_manual_min_threshold(self, val: float):
        pass

    def set_manual_max_threshold(self, val: float):
        pass

    def set_manual_use_raw_values(self, enabled: bool):
        pass

    def set_manual_viz_mode(self, mode: str):
        pass

    # === PALETTE METHODS ===
    def set_palette(self, palette_name: str):
        """Set global palette.
        
        Args:
            palette_name: Name of the palette to use (e.g., 'ironbow', 'rainbow', etc.)
        """
        if self.palette_manager:
            from thermal_inspection.processing.palette_manager import PaletteType
            # Convert string to PaletteType enum
            try:
                # Normalize name (lowercase, replace spaces with underscores)
                clean_name = palette_name.lower().replace(' ', '_').replace('-', '_')
                palette_type = PaletteType(clean_name)
                self.palette_manager.set_global_palette(palette_type)
                logger.info(f"Global palette set to: {palette_name}")
            except ValueError:
                logger.warning(f"Unknown palette: {palette_name}")

    def set_roi_palette(self, roi_id: str, palette_name: str):
        """Set palette for a specific ROI.
        
        Args:
            roi_id: ID of the ROI
            palette_name: Name of the palette to use
        """
        if self.palette_manager:
            from thermal_inspection.processing.palette_manager import PaletteType
            try:
                clean_name = palette_name.lower().replace(' ', '_').replace('-', '_')
                palette_type = PaletteType(clean_name)
                self.palette_manager.set_roi_palette(roi_id, palette_type)
                # Also update ROI object if ROI controller exists
                if self.roi_controller:
                    roi = self.roi_controller.get_roi(roi_id)
                    if roi:
                        roi.custom_palette = palette_name
                logger.info(f"ROI {roi_id} palette set to: {palette_name}")
            except ValueError:
                logger.warning(f"Unknown palette for ROI: {palette_name}")
