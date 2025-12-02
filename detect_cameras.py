#!/usr/bin/env python3
"""
Detect all available cameras and identify which is the FLIR Boson.
"""

import cv2
import sys

print("="*70)
print("Camera Detection Script")
print("="*70)
print(f"OpenCV version: {cv2.__version__}")
print()

print("Scanning for cameras (device IDs 0-9)...")
print()

found_cameras = []

for device_id in range(10):
    print(f"Testing device {device_id}...", end=" ")

    # Try opening with DirectShow
    cap = cv2.VideoCapture(device_id, cv2.CAP_DSHOW)

    if cap.isOpened():
        # Get properties
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        backend = cap.getBackendName()

        # Try to read a frame
        ret, frame = cap.read()

        if ret:
            frame_shape = frame.shape
            frame_dtype = frame.dtype

            # Identify camera type
            if width == 640 and height == 512:
                camera_type = "[THERMAL] FLIR BOSON 640 (512 height)"
            elif width == 640 and height == 514:
                camera_type = "[THERMAL] FLIR BOSON 640 (514 height with telemetry)"
            elif width == 640 and height == 480:
                camera_type = "[WEBCAM] Standard VGA"
            elif width == 1280 and height == 720:
                camera_type = "[WEBCAM] HD 720p"
            elif width == 1920 and height == 1080:
                camera_type = "[WEBCAM] Full HD 1080p"
            else:
                camera_type = f"[UNKNOWN] ({width}x{height})"

            print(f"[OK] FOUND")
            print(f"  Type: {camera_type}")
            print(f"  Resolution: {width}x{height}")
            print(f"  FPS: {fps}")
            print(f"  Backend: {backend}")
            print(f"  Frame shape: {frame_shape}")
            print(f"  Frame dtype: {frame_dtype}")

            found_cameras.append({
                'id': device_id,
                'type': camera_type,
                'width': width,
                'height': height,
                'fps': fps,
                'backend': backend,
                'shape': frame_shape,
                'dtype': frame_dtype
            })
            print()
        else:
            print(f"[OK] Opened but couldn't read frame")
            print()

        cap.release()
    else:
        print("[SKIP] Not available")

# Summary
print("="*70)
print("SUMMARY")
print("="*70)
print(f"Found {len(found_cameras)} camera(s)")
print()

if found_cameras:
    # Find FLIR Boson
    boson_cameras = [c for c in found_cameras if 'FLIR BOSON' in c['type']]
    webcams = [c for c in found_cameras if 'FLIR BOSON' not in c['type']]

    if boson_cameras:
        print("[THERMAL] FLIR Boson Camera(s):")
        for cam in boson_cameras:
            print(f"  Device ID {cam['id']}: {cam['width']}x{cam['height']}")
        print()
    else:
        print("[WARNING] No FLIR Boson detected!")
        print("  Expected resolution: 640x512 or 640x514")
        print()

    if webcams:
        print("[OTHER] Other Camera(s):")
        for cam in webcams:
            print(f"  Device ID {cam['id']}: {cam['type']}")
        print()

    print("="*70)
    print("RECOMMENDATION")
    print("="*70)

    if boson_cameras:
        boson_id = boson_cameras[0]['id']
        print(f"Use device_id={boson_id} for FLIR Boson thermal camera")
        print()
        print("Update your test scripts:")
        print(f"  cap = cv2.VideoCapture({boson_id}, cv2.CAP_DSHOW)")
        print()
        print("Update flir_camera.py:")
        print(f"  camera = FLIRBosonCamera(device_id={boson_id}, ...)")
    else:
        print("Could not identify FLIR Boson camera.")
        print()
        print("Possible reasons:")
        print("  1. Camera not connected via USB")
        print("  2. Camera in wrong mode")
        print("  3. Driver issue")
        print()
        print("Check:")
        print("  - Device Manager → Cameras → FLIR Boson")
        print("  - Try different USB port")
        print("  - Check camera_registry.json for registered device_id")
else:
    print("No cameras detected!")
    print()
    print("Troubleshooting:")
    print("  1. Check USB connections")
    print("  2. Check Device Manager")
    print("  3. Try running as Administrator")

print("="*70)
