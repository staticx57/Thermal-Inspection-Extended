import cv2
import numpy as np
import time

def test_16bit(device_id=1):
    print(f"Testing 16-bit capture on Camera {device_id}...")
    
    backends = [
        ("DSHOW", cv2.CAP_DSHOW),
        ("MSMF", cv2.CAP_MSMF),
        ("ANY", cv2.CAP_ANY)
    ]
    
    for name, backend in backends:
        print(f"\n=== Testing Backend: {name} ===")
        
        # Try 1: Default
        print("  --- Attempt 1: Default ---")
        cap = cv2.VideoCapture(device_id, backend)
        if cap.isOpened():
            ret, frame = cap.read()
            if ret:
                print(f"    Shape: {frame.shape}, Dtype: {frame.dtype}")
            else:
                print("    Failed to read frame")
            cap.release()
        else:
            print("    Failed to open camera")
            
        # Try 2: Convert RGB = 0
        print("  --- Attempt 2: Convert RGB = 0 ---")
        cap = cv2.VideoCapture(device_id, backend)
        if cap.isOpened():
            cap.set(cv2.CAP_PROP_CONVERT_RGB, 0)
            ret, frame = cap.read()
            if ret:
                print(f"    Shape: {frame.shape}, Dtype: {frame.dtype}")
            else:
                print("    Failed to read frame")
            cap.release()
            
        # Try 3: FOURCC Y16
        print("  --- Attempt 3: FOURCC Y16 ---")
        cap = cv2.VideoCapture(device_id, backend)
        if cap.isOpened():
            cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'Y16 '))
            cap.set(cv2.CAP_PROP_CONVERT_RGB, 0)
            ret, frame = cap.read()
            if ret:
                print(f"    Shape: {frame.shape}, Dtype: {frame.dtype}")
            else:
                print("    Failed to read frame")
            cap.release()

if __name__ == "__main__":
    test_16bit(1)
