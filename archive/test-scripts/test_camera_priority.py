#!/usr/bin/env python3
"""Quick camera detection test to verify priority fix"""
from camera_detector import CameraDetector

print("="*70)
print("TESTING CAMERA PRIORITY DETECTION")
print("="*70)

cameras = CameraDetector.detect_all_cameras()

print("\n=== PRIORITY RESULTS ===")
thermal = [c for c in cameras if c.is_thermal()]
rgb = [c for c in cameras if c.is_rgb()]

if thermal:
    print(f"\nThermal Priority Camera:")
    print(f"  {thermal[0]}")
    print(f"  Priority Score: {thermal[0].priority}")
    
if rgb:
    print(f"\nRGB Priority Camera:")
    print(f"  {rgb[0]}")
    print(f"  Priority Score: {rgb[0].priority}")
    
    if len(rgb) > 1:
        print(f"\nOther RGB Cameras:")
        for i, cam in enumerate(rgb[1:], 2):
            print(f"  {i}. {cam}")
            print(f"     Priority Score: {cam.priority}")

print("\n" + "="*70)
