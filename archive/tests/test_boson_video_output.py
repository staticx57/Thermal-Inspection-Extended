#!/usr/bin/env python3
"""Test Boson SDK video output mode control."""
import sys
sys.path.insert(0, r'C:\Users\stati\Desktop\Projects\Thermal-Inspection')
from boson_sdk_wrapper import BosonSDK

print("="*60)
print("Testing Boson Video Output Mode Control")
print("="*60)

sdk = BosonSDK(com_port='COM7')

if sdk.open():
    print("\n[OK] SDK connected")
    cam = sdk.camera

    # Look for video output format functions
    print("\nSearching for video output / format functions:")
    video_funcs = [attr for attr in dir(cam) if any(keyword in attr.lower() for keyword in ['video', 'output', 'format', 'mode', 'bpr'])]

    if video_funcs:
        print(f"  Found {len(video_funcs)} related functions:")
        for func in sorted(video_funcs)[:30]:  # Show first 30
            print(f"    - {func}")
    else:
        print("  No video output functions found")

    # Check for BPR (Bytes Per Row) or video mode settings
    print("\nLooking for BPR/Data format functions:")
    bpr_funcs = [attr for attr in dir(cam) if 'bpr' in attr.lower() or 'dataformat' in attr.lower() or 'outputmode' in attr.lower()]
    for func in bpr_funcs:
        print(f"  - {func}")

    # Try to get current video output settings
    print("\nTrying to read current video settings:")
    try:
        if hasattr(cam, 'bosonGetVideoOutputFormat'):
            result = cam.bosonGetVideoOutputFormat()
            print(f"  VideoOutputFormat: {result}")
    except Exception as e:
        print(f"  Error: {e}")

    # Check AGC mode (might affect output)
    print("\nChecking AGC settings:")
    try:
        if hasattr(cam, 'bosonGetAGCMode'):
            result = cam.bosonGetAGCMode()
            print(f"  AGCMode: {result}")
    except Exception as e:
        print(f"  Error: {e}")

    sdk.close()
    print("\n[OK] SDK closed")

print("\n" + "="*60)
