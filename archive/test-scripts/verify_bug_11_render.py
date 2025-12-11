
import sys
import logging
import numpy as np
import cv2
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from unittest.mock import MagicMock

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("Bug11Verifier")

# Import classes
from inspection_gui_qt import InspectionAppWindow
from roi_manager import ROI, ROIType, ROISource, ROIManager
from palette_manager import PaletteManager, PaletteType, PaletteConfig

def verify_bug_11_rendering():
    print("\n=== STARTING RENDERING VERIFICATION ===")
    
    # 1. Setup Managers
    palette_mgr = PaletteManager({'default_palette': 'white_hot'})
    roi_mgr = ROIManager({'auto_roi_min_area': 100})
    
    # 2. Setup Test Image (Gradient)
    h, w = 100, 100
    frame = np.zeros((h, w), dtype=np.uint8)
    for i in range(h):
        frame[i, :] = i * 2  # Vertical gradient
        
    print(f"Created test frame: {w}x{h}")
    
    # 3. Create ROI (Top-Left Quarter)
    # Define points for rectangle: (x1, y1), (x2, y2)
    # ROI class usually takes points list. For RECTANGLE: [(x1,y1), (x2,y2)] is common in this codebase?
    # Let's verify ROI implementation or just assume standard
    roi1 = ROI(roi_id="roi_test", roi_type=ROIType.RECTANGLE, roi_source=ROISource.MANUAL, 
               points=[(10, 10), (40, 40)], label="Test ROI")
    roi1.active = True
    roi_mgr.add_roi(roi1)
    
    # 4. Set ROI Palette
    print("Setting ROI palette to RAINBOW (via manager)...")
    palette_mgr.set_roi_palette("roi_test", PaletteType.RAINBOW)
    
    # 5. Apply Composite Palette
    print("Applying composite palette...")
    output = palette_mgr.apply_composite_palette(frame, roi_mgr)
    
    # 6. Verify Results
    # Get a pixel inside ROI (25, 25)
    pixel_roi = output[25, 25]
    # Get a pixel outside ROI (80, 80)
    pixel_global = output[80, 80]
    
    print(f"Pixel inside ROI (25,25): {pixel_roi}")
    print(f"Pixel outside ROI (80,80): {pixel_global}")
    
    # White hot (global default): Gray values (B=G=R)
    # Rainbow: Colorful values (B!=G!=R usually)
    
    is_global_grayscale = (pixel_global[0] == pixel_global[1] == pixel_global[2])
    is_roi_colorful = (pixel_roi[0] != pixel_roi[1] or pixel_roi[1] != pixel_roi[2])
    
    if is_global_grayscale:
        print("PASS: Global region is Grayscale (White Hot).")
    else:
        print("FAIL: Global region is NOT Grayscale.")
        
    if is_roi_colorful:
        print("PASS: ROI region is Colorful (Rainbow).")
    else:
        print("FAIL: ROI region is NOT Colorful. Palette override failed.")
        return False
        
    print("\n Rendering Verification Complete.")
    return True

if __name__ == "__main__":
    success = verify_bug_11_rendering()
    sys.exit(0 if success else 1)
