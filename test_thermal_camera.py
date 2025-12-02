#!/usr/bin/env python3
"""Test script for thermal camera connection and radiometric mode."""
import sys
import time
sys.path.insert(0, r'C:\Users\stati\Desktop\Projects\Thermal-Inspection')

from flir_camera import FLIRBosonCamera

print("="*60)
print("Testing Thermal Camera Connection")
print("="*60)

# Test 1: Basic connection without SDK
print("\n[Test 1] Basic connection (no SDK)...")
cam = FLIRBosonCamera(device_id=1, resolution=(640, 512), enable_sdk=False)
opened = cam.open()
print(f"  Camera opened: {opened}")
print(f"  Is opened: {cam.is_opened}")

if opened:
    ret, frame = cam.read_thermal()
    print(f"  Frame read: {ret}")
    if frame is not None:
        print(f"  Frame dtype: {frame.dtype}")
        print(f"  Frame shape: {frame.shape}")
        print(f"  Radiometric capable: {cam.is_radiometric_capable()}")
    cam.release()
    print("  Camera released\n")

# Test 2: Connection with SDK enabled
print("[Test 2] Connection with SDK enabled (COM6)...")
cam2 = FLIRBosonCamera(device_id=1, resolution=(640, 512), enable_sdk=True, com_port='COM6')
opened2 = cam2.open()
print(f"  Camera opened: {opened2}")
print(f"  SDK connected: {cam2.sdk_connected}")

if opened2:
    time.sleep(0.5)  # Allow camera to stabilize
    ret, frame = cam2.read_thermal()
    print(f"  Frame read: {ret}")
    if frame is not None:
        print(f"  Frame dtype: {frame.dtype}")
        print(f"  Frame shape: {frame.shape}")
        print(f"  Radiometric capable: {cam2.is_radiometric_capable()}")
    cam2.release()
    print("  Camera released")

print("\n" + "="*60)
print("Test Complete")
print("="*60)
