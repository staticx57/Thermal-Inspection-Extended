"""
Test if OpenCV can capture Y16 (16-bit) format from Boson via UVC driver.

This would allow us to get radiometric data WITHOUT needing WinUSB driver!
"""

import cv2
import numpy as np
import sys

print("=" * 60)
print("Testing OpenCV Y16 Capture from FLIR Boson")
print("=" * 60)

# Try device ID 1 (adjust if needed)
DEVICE_ID = 1

print(f"\n1. Opening camera on device {DEVICE_ID}...")
cap = cv2.VideoCapture(DEVICE_ID, cv2.CAP_DSHOW)

if not cap.isOpened():
    print(f"[X] Failed to open camera on device {DEVICE_ID}")
    print("Trying device 0 instead...")
    DEVICE_ID = 0
    cap = cv2.VideoCapture(DEVICE_ID, cv2.CAP_DSHOW)
    if not cap.isOpened():
        print(f"[X] Failed to open camera on device {DEVICE_ID} too")
        sys.exit(1)

print("[OK] Camera opened successfully")

# Get backend name
backend_name = cap.getBackendName()
print(f"\n2. Backend: {backend_name}")

# Get current format info
width = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
height = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
fps = cap.get(cv2.CAP_PROP_FPS)
fourcc = cap.get(cv2.CAP_PROP_FOURCC)

print(f"\n3. Current format:")
print(f"   Resolution: {int(width)}x{int(height)}")
print(f"   FPS: {fps}")
print(f"   FourCC: {int(fourcc)} (0x{int(fourcc):08X})")

# Read a frame with default settings
print(f"\n4. Reading frame with default settings...")
ret, frame_default = cap.read()

if ret:
    print(f"[OK] Frame captured")
    print(f"   Shape: {frame_default.shape}")
    print(f"   Dtype: {frame_default.dtype}")
    print(f"   Range: {frame_default.min()} - {frame_default.max()}")
else:
    print(f"[X] Failed to read frame")

# Now try to request Y16 format
print(f"\n5. Attempting to set Y16 format...")

# Y16 fourcc codes to try
y16_formats = [
    ('Y16 ', cv2.VideoWriter_fourcc('Y','1','6',' ')),
    ('Y16', cv2.VideoWriter_fourcc('Y','1','6','\0')),
    ('GREY', cv2.VideoWriter_fourcc('G','R','E','Y')),
    ('Y800', cv2.VideoWriter_fourcc('Y','8','0','0')),
]

for name, fourcc_code in y16_formats:
    print(f"\n   Trying {name} (0x{fourcc_code:08X})...")

    # Create new capture with format
    cap2 = cv2.VideoCapture(DEVICE_ID, cv2.CAP_DSHOW)

    # Set format
    cap2.set(cv2.CAP_PROP_FOURCC, fourcc_code)
    cap2.set(cv2.CAP_PROP_CONVERT_RGB, 0)  # Don't convert to RGB

    # Check if it was set
    actual_fourcc = cap2.get(cv2.CAP_PROP_FOURCC)
    print(f"   Requested: 0x{fourcc_code:08X}, Got: 0x{int(actual_fourcc):08X}")

    # Try to read a frame
    ret, frame = cap2.read()

    if ret:
        print(f"   [OK] Frame captured")
        print(f"      Shape: {frame.shape}")
        print(f"      Dtype: {frame.dtype}")
        print(f"      Range: {frame.min()} - {frame.max()}")

        # Check if it's 16-bit
        if frame.dtype == np.uint16:
            print(f"\n*** SUCCESS! Got 16-bit data! ***")

            # Try to convert to temperature
            print(f"\n   Converting to temperature...")

            # Y16 format: pixel_value = Kelvin * 100
            temp_k = frame.astype(np.float32) / 100.0
            temp_c = temp_k - 273.15

            print(f"   Temperature range: {temp_c.min():.1f}C - {temp_c.max():.1f}C")

            # Check center pixel
            center_y, center_x = frame.shape[0] // 2, frame.shape[1] // 2
            center_temp = temp_c[center_y, center_x]
            print(f"   Center pixel: {center_temp:.1f}C")

            # This is the winner!
            print(f"\n*** WINNER: Format '{name}' gives us Y16! ***")
            print(f"   We can get 16-bit radiometric WITHOUT WinUSB driver!")

            cap2.release()
            break
    else:
        print(f"   [X] Failed to read frame")

    cap2.release()

else:
    print(f"\n[X] None of the Y16 formats worked")
    print(f"   Boson may only expose 8-bit AGC via UVC")

# Alternative: Try listing all available formats
print(f"\n6. Trying alternative method with CAP_PROP_MODE...")

cap3 = cv2.VideoCapture(DEVICE_ID, cv2.CAP_DSHOW)

# Some cameras expose different modes
for mode in range(10):
    cap3.set(cv2.CAP_PROP_MODE, mode)
    ret, frame = cap3.read()

    if ret:
        print(f"   Mode {mode}: {frame.shape}, {frame.dtype}, range {frame.min()}-{frame.max()}")

        if frame.dtype == np.uint16:
            print(f"   [OK] Mode {mode} gives uint16!")

cap3.release()

# Check if OpenCV was built with DirectShow support
print(f"\n7. OpenCV build info:")
print(f"   Version: {cv2.__version__}")
print(f"   Build info (first 500 chars):")
build_info = cv2.getBuildInformation()
print(build_info[:500])

cap.release()

print(f"\n" + "=" * 60)
print("Test complete!")
print("=" * 60)
