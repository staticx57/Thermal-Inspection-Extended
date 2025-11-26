"""
Quick camera enumeration script to identify device IDs
"""
import cv2

print("Enumerating cameras...")
print("=" * 60)

for i in range(10):
    cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
    if cap.isOpened():
        ret, frame = cap.read()
        if ret and frame is not None:
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fps = cap.get(cv2.CAP_PROP_FPS)
            print(f"Device {i}: {width}x{height} @ {fps:.1f} FPS")
        else:
            print(f"Device {i}: Opened but failed to read")
        cap.release()
    else:
        print(f"Device {i}: Not available")
        
print("=" * 60)
