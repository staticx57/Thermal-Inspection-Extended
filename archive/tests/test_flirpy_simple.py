"""
Simplest possible test of flirpy Boson connection.
"""
from flirpy.camera.boson import Boson
import time

print("="*60)
print("Testing flirpy Boson - Simple Test")
print("="*60)

print("\n1. Opening Boson camera...")
try:
    camera = Boson()
    print("[OK] Camera opened")
except Exception as e:
    print(f"[X] Failed to open camera: {e}")
    exit(1)

print("\n2. Trying to grab 5 frames...")
for i in range(5):
    try:
        frame = camera.grab()
        if frame is not None:
            print(f"[OK] Frame {i+1}: shape={frame.shape}, dtype={frame.dtype}, range={frame.min()}-{frame.max()}")
        else:
            print(f"[X] Frame {i+1}: None returned")
    except Exception as e:
        print(f"[X] Frame {i+1}: Error: {e}")
    time.sleep(0.2)

print("\n3. Closing camera...")
camera.close()
print("[OK] Camera closed")

print("\n" + "="*60)
print("Test complete")
print("="*60)
