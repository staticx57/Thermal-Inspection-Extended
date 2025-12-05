import cv2
import numpy as np
import time
import sys

def diagnose_cameras():
    print("Scanning for cameras...")
    for i in range(5):
        print(f"\nChecking Camera Index {i}...")
        cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
        
        if not cap.isOpened():
            print(f"  Failed to open camera {i}")
            continue
            
        print(f"  [OK] Camera {i} opened")
        
        # Get properties
        width = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
        height = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
        fps = cap.get(cv2.CAP_PROP_FPS)
        backend = cap.getBackendName()
        
        print(f"  Backend: {backend}")
        print(f"  Resolution: {width}x{height}")
        print(f"  FPS: {fps}")
        
        # Read a frame
        ret, frame = cap.read()
        if ret:
            print(f"  Frame shape: {frame.shape}")
            print(f"  Frame dtype: {frame.dtype}")
            
            # Check channels
            if len(frame.shape) == 3:
                b, g, r = cv2.split(frame)
                is_grayscale = np.array_equal(b, g) and np.array_equal(g, r)
                print(f"  Channels identical (Grayscale content): {is_grayscale}")
                
                if is_grayscale:
                    print(f"  Mean value: {np.mean(b):.2f}")
                    print(f"  Min/Max: {np.min(b)}/{np.max(b)}")
                    
                    # Histogram analysis
                    hist = cv2.calcHist([b], [0], None, [256], [0, 256])
                    peaks = np.sum(hist > (hist.max() * 0.3))
                    print(f"  Histogram peaks (>30% max): {peaks}")
            else:
                print("  Single channel frame")
                
        else:
            print("  Failed to read frame")
            
        cap.release()

if __name__ == "__main__":
    diagnose_cameras()
