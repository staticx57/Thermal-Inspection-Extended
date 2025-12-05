"""
Diagnose Dual-Path Camera Access

Tests the feasibility of simultaneous flirpy (UVC) and BosonSDK (COM) access.
"""
import sys
import time
import cv2
import numpy as np

print("=" * 60)
print("Dual-Path Diagnostic Tool")
print("=" * 60)

# 1. Test flirpy (Video) Isolation
print("\nTEST 1: flirpy (Video) Isolation")
try:
    from flirpy.camera.boson import Boson
    print("   Creating Boson()...")
    cam = Boson()
    print("   Grabbing frame...")
    frame = cam.grab()
    if frame is not None:
        print(f"   [OK] Frame captured: {frame.shape}, dtype={frame.dtype}")
    else:
        print("   [FAIL] Frame is None")
    cam.close()
    print("   [OK] Closed flirpy")
except Exception as e:
    print(f"   [FAIL] flirpy error: {e}")

# 2. Test SDK (COM) Isolation
print("\nTEST 2: SDK (COM) Isolation")
try:
    from boson_sdk_wrapper import BosonSDK
    print("   Connecting to SDK on COM7...")
    sdk = BosonSDK(com_port='COM7')
    if sdk.open():
        print("   [OK] SDK Connected")
        sn = sdk.get_camera_info().serial_number if sdk.get_camera_info() else "Unknown"
        print(f"   Serial: {sn}")
        sdk.close()
        print("   [OK] Closed SDK")
    else:
        print("   [FAIL] Could not open SDK")
except Exception as e:
    print(f"   [FAIL] SDK error: {e}")

# 3. Test Sequence: Flirpy -> SDK
print("\nTEST 3: Sequence Flirpy (Video) -> SDK (COM)")
try:
    print("   1. Opening flirpy...")
    cam = Boson()
    frame = cam.grab()
    if frame is not None:
        print("   [OK] flirpy captured frame")
        
        print("   2. Opening SDK (while flirpy is open)...")
        sdk = BosonSDK(com_port='COM7')
        if sdk.open():
            print("   [OK] SDK Connected!")
            
            # Try to grab another frame while SDK is connected
            print("   3. Grabbing frame with SDK connected...")
            frame2 = cam.grab()
            if frame2 is not None:
                print("   [OK] Frame captured (Dual-Path Working!)")
            else:
                print("   [FAIL] Could not capture frame while SDK connected")
                
            sdk.close()
        else:
            print("   [FAIL] SDK connection failed while flirpy open")
            
    else:
        print("   [FAIL] flirpy failed to capture initial frame")
        
    cam.close()
    
except Exception as e:
    print(f"   [FAIL] Error: {e}")

# 4. Test Sequence: SDK -> Flirpy
print("\nTEST 4: Sequence SDK (COM) -> Flirpy (Video)")
try:
    print("   1. Opening SDK...")
    sdk = BosonSDK(com_port='COM7')
    if sdk.open():
        print("   [OK] SDK Connected")
        
        print("   2. Opening flirpy (while SDK is open)...")
        try:
            cam = Boson()
            frame = cam.grab()
            if frame is not None:
                print("   [OK] Frame captured (Dual-Path Working!)")
                cam.close()
            else:
                print("   [FAIL] Frame is None")
        except Exception as e:
            print(f"   [FAIL] flirpy error: {e}")
            
        sdk.close()
    else:
        print("   [FAIL] SDK connection failed")
        
except Exception as e:
    print(f"   [FAIL] Error: {e}")

print("\n" + "=" * 60)
print("Diagnostic Complete")
print("=" * 60)
