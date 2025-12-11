
import sys
import logging
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from unittest.mock import MagicMock

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("Bug11Verifier")

# Import the GUI classes
from inspection_gui_qt import InspectionAppWindow
from roi_manager import ROI, ROIType, ROISource

def verify_bug_11():
    app = QApplication(sys.argv)
    
    # Mock the main app controller
    mock_app = MagicMock()
    
    # Create main window
    window = InspectionAppWindow(mock_app)
    window.show()
    
    # 1. Setup Test ROIs
    print("\n--- Setting up Test ROIs ---")
    roi1 = ROI(roi_id="roi_1", roi_type=ROIType.RECTANGLE, roi_source=ROISource.MANUAL, points=[(10,10), (50,50)], label="ROI 1")
    roi2 = ROI(roi_id="roi_2", roi_type=ROIType.CIRCLE, roi_source=ROISource.MANUAL, points=[(100,100), (150,150)], label="ROI 2")
    rois = [roi1, roi2]
    
    # Update panel with ROIs
    window.analysis_panel.update_rois(rois)
    print(f"Added {len(rois)} ROIs to analysis panel.")
    
    # Verify list population
    count = window.analysis_panel.roi_list.count()
    if count != 2:
        print(f"FAILURE: ROI list has {count} items, expected 2.")
        return False
        
    print("ROI list populated correctly.")
    
    # 2. Test Signal Connection: Overlay -> Window -> Panel
    print("\n--- Testing Signal Chain: Overlay -> Analysis Panel ---")
    
    # Simulate user clicking ROI 2 in overlay
    print("Emitting roi_selected('roi_2') from video_widget.overlay...")
    window.video_widget.overlay.roi_selected.emit("roi_2")
    
    # Process events to allow signal propagation
    app.processEvents()
    
    # Check if list selected index 1 (ROI 2)
    current_row = window.analysis_panel.roi_list.currentRow()
    current_item = window.analysis_panel.roi_list.currentItem()
    current_id = current_item.data(Qt.ItemDataRole.UserRole) if current_item else None
    
    print(f"Current Row: {current_row}")
    print(f"Current ROI ID: {current_id}")
    
    if current_id == "roi_2":
        print("SUCCESS: Analysis panel selected correct ROI via signal chain.")
    else:
        print(f"FAILURE: Expected 'roi_2', got '{current_id}'. Signal chain broken.")
        return False

    # 3. Test Silent Failure Logging (Non-existent ROI)
    print("\n--- Testing Non-Existent ROI Selection ---")
    print("Emitting roi_selected('roi_999')... (Check logs for warning)")
    window.video_widget.overlay.roi_selected.emit("roi_999")
    app.processEvents()
    
    # Should stay on previous selection or do nothing
    current_id_new = window.analysis_panel.roi_list.currentItem().data(Qt.ItemDataRole.UserRole)
    print(f"Current ROI ID (should still be roi_2): {current_id_new}")
    
    print("\nVerification Complete.")
    return True

if __name__ == "__main__":
    success = verify_bug_11()
    sys.exit(0 if success else 1)
