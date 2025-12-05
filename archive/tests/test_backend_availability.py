"""
Quick test to check if flirpy backend is available and can initialize.
"""
import logging

logging.basicConfig(level=logging.INFO)

print("=" * 60)
print("Testing Backend Availability")
print("=" * 60)

# Test 1: Check flirpy installation
print("\n1. Checking flirpy installation...")
try:
    from flirpy.camera.boson import Boson
    print("[OK] flirpy is installed")
except ImportError as e:
    print(f"[X] flirpy not installed: {e}")
    exit(1)

# Test 2: Check backend import
print("\n2. Checking backend import...")
try:
    from flirpy_thermal_backend import FlirpyThermalBackend
    print("[OK] FlirpyThermalBackend imported")
except ImportError as e:
    print(f"[X] Backend import failed: {e}")
    exit(1)

# Test 3: Check backend availability
print("\n3. Checking backend availability...")
backend = FlirpyThermalBackend()
if backend.is_available():
    print("[OK] flirpy backend is available")
else:
    print("[X] flirpy backend is NOT available")
    print("    This means flirpy cannot detect the Boson camera")
    exit(1)

# Test 4: Try to open backend
print("\n4. Trying to open backend...")
if backend.open():
    print("[OK] Backend opened successfully")
    print(f"    Backend info: {backend.get_info()}")

    # Test 5: Try to read a frame
    print("\n5. Trying to read frame...")
    ret, frame = backend.read()
    if ret and frame is not None:
        print(f"[OK] Frame read: shape={frame.shape}, dtype={frame.dtype}")
        print(f"    Range: {frame.min()} - {frame.max()}")
    else:
        print("[X] Failed to read frame")

    # Cleanup
    print("\n6. Closing backend...")
    backend.release()
    print("[OK] Backend closed")
else:
    print("[X] Failed to open backend")
    exit(1)

print("\n" + "=" * 60)
print("SUCCESS - flirpy backend is fully functional")
print("=" * 60)
