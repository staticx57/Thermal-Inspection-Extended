"""
Simple camera diagnostic tool to find all accessible video devices
"""
import cv2
import time

def test_camera(device_id, backend=None):
    """Test if a camera exists on the given device ID"""
    try:
        if backend:
            cap = cv2.VideoCapture(device_id, backend)
        else:
            cap = cv2.VideoCapture(device_id)

        if cap.isOpened():
            # Try to read a frame
            ret, frame = cap.read()
            if ret and frame is not None:
                height, width = frame.shape[:2]
                dtype = frame.dtype
                channels = frame.shape[2] if len(frame.shape) == 3 else 1

                # Try to get backend name
                backend_name = "unknown"
                try:
                    backend_name = cap.getBackendName()
                except:
                    pass

                cap.release()
                return True, f"{width}x{height}", dtype, channels, backend_name
            else:
                cap.release()
                return False, "Cannot read frames", None, None, None
        else:
            return False, "Cannot open", None, None, None
    except Exception as e:
        return False, str(e), None, None, None

print("="*70)
print("CAMERA DIAGNOSTIC TOOL")
print("="*70)
print()

# Test device IDs 0-10 with different backends
backends = [
    ("DirectShow", cv2.CAP_DSHOW),
    ("MSMF", cv2.CAP_MSMF),
    ("Default", None),
]

for backend_name, backend_code in backends:
    print(f"\n{backend_name} Backend:")
    print("-" * 70)

    found_any = False
    for device_id in range(10):
        success, info, dtype, channels, actual_backend = test_camera(device_id, backend_code)

        if success:
            print(f"  Device {device_id}: SUCCESS - {info}, dtype={dtype}, channels={channels}, backend={actual_backend}")
            found_any = True
        else:
            print(f"  Device {device_id}: FAILED - {info}")

        # Small delay between attempts
        time.sleep(0.1)

    if not found_any:
        print(f"  No cameras found with {backend_name} backend")

print()
print("="*70)
print("DIAGNOSTIC COMPLETE")
print("="*70)
