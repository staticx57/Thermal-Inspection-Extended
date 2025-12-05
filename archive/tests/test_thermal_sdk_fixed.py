#!/usr/bin/env python3
"""Test script for thermal camera with correct COM port."""
import sys
import time
sys.path.insert(0, r'C:\Users\stati\Desktop\Projects\Thermal-Inspection')

from flir_camera import FLIRBosonCamera

print("="*60)
print("Testing Thermal Camera with Correct COM Port (COM7)")
print("="*60)

# Test with correct COM port
print("\n[Test] Connection with SDK enabled (COM7)...")
cam = FLIRBosonCamera(device_id=1, resolution=(640, 512), enable_sdk=True, com_port='COM7')
opened = cam.open()
print(f"  Camera opened: {opened}")
print(f"  SDK connected: {cam.sdk_connected}")

if opened:
    if cam.sdk_connected:
        print("\n  SDK Connection Successful!")

        # Get camera info
        info = cam.get_camera_info()
        if info:
            print(f"    Serial Number: {info.serial_number}")
            print(f"    FPA Temperature: {info.fpa_temperature_k - 273.15:.1f}°C" if info.fpa_temperature_k else "    FPA Temperature: N/A")

    # Wait for camera to stabilize after T-Linear mode change
    print("\n  Waiting for camera to stabilize...")
    time.sleep(1.0)

    # Read frame and check mode
    print("\n  Reading thermal frame...")
    ret, frame = cam.read_thermal()
    print(f"    Frame read: {ret}")

    if frame is not None:
        print(f"    Frame dtype: {frame.dtype}")
        print(f"    Frame shape: {frame.shape}")
        print(f"    Radiometric capable: {cam.is_radiometric_capable()}")

        # Check pixel value range to verify data type
        import numpy as np
        print(f"    Frame min value: {frame.min()}")
        print(f"    Frame max value: {frame.max()}")
        print(f"    Frame mean value: {frame.mean():.2f}")

        if frame.dtype == np.uint16:
            print("\n  SUCCESS: Camera is in 16-bit radiometric mode!")
        else:
            print("\n  WARNING: Camera is still in 8-bit mode (expected 16-bit)")

    cam.release()
    print("\n  Camera released")

print("\n" + "="*60)
print("Test Complete")
print("="*60)
