import sys
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    from PyQt5.QtWidgets import QApplication
    app = QApplication(sys.argv)
    logger.info("QApplication created")
except ImportError:
    logger.error("PyQt5 not found")
    sys.exit(1)

try:
    import inspection_gui_qt
    logger.info("inspection_gui_qt imported")
    
    from inspection_gui_qt import InspectionAppWindow
    logger.info("InspectionAppWindow imported")
    
    # Mock app instance
    class MockApp:
        def __init__(self):
            self.args = type('Args', (), {'palette': 'ironbow'})()
            self.palette_manager = type('PM', (), {'get_available_palettes': lambda: ['ironbow', 'rainbow']})()
            self.inspection_mode = 'realtime'
            self.recording_enabled = False
            self.motion_enabled = True
            self.edge_enabled = True
            self.fusion_mode = 'thermal_overlay'
            self.fusion_alpha = 0.5
            self.fusion_priority = 'thermal'
            self.roi_manager = type('RM', (), {'get_all_rois': lambda active_only: []})()
    
    mock_app = MockApp()
    window = InspectionAppWindow(mock_app)
    logger.info("InspectionAppWindow instantiated")
    
    window.show()
    logger.info("Window shown (test)")
    
except Exception as e:
    logger.error(f"GUI Error: {e}", exc_info=True)
    sys.exit(1)

logger.info("GUI Test Passed")
