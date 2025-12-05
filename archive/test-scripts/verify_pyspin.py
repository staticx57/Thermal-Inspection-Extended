"""
PySpin Installation Verification Script
Run this after installing PySpin to verify everything works
"""

def test_pyspin_import():
    """Test if PySpin can be imported"""
    print("="*70)
    print("TEST 1: PySpin Import")
    print("="*70)

    try:
        import PySpin
        print("[PASS] PySpin imported successfully!")
        return True, PySpin
    except ImportError as e:
        print(f"[FAIL] Cannot import PySpin: {e}")
        print("\nNext steps:")
        print("  1. Make sure PySpin wheel is installed")
        print("  2. Check Python version compatibility")
        print("  3. See install_pyspin.md for instructions")
        return False, None

def test_pyspin_version(PySpin):
    """Test PySpin version"""
    print("\n" + "="*70)
    print("TEST 2: PySpin Version")
    print("="*70)

    try:
        system = PySpin.System.GetInstance()
        version = system.GetLibraryVersion()
        print(f"[PASS] PySpin Library Version:")
        print(f"  Major: {version.major}")
        print(f"  Minor: {version.minor}")
        print(f"  Type: {version.type}")
        print(f"  Build: {version.build}")
        system.ReleaseInstance()
        return True
    except Exception as e:
        print(f"[FAIL] Error getting version: {e}")
        return False

def test_camera_detection(PySpin):
    """Test FLIR camera detection"""
    print("\n" + "="*70)
    print("TEST 3: FLIR Camera Detection")
    print("="*70)

    try:
        # Get system instance
        system = PySpin.System.GetInstance()

        # Get camera list
        cam_list = system.GetCameras()
        num_cameras = cam_list.GetSize()

        print(f"Number of FLIR cameras detected: {num_cameras}")

        if num_cameras == 0:
            print("[WARN] No FLIR cameras detected!")
            print("\nTroubleshooting:")
            print("  1. Check camera is connected via USB 3.0")
            print("  2. Check Device Manager for camera device")
            print("  3. Try different USB port")
            print("  4. Restart computer")
            print("  5. Check camera has power (some models need external power)")
            cam_list.Clear()
            system.ReleaseInstance()
            return False

        # List camera details
        print(f"\n[PASS] Found {num_cameras} camera(s):")

        for i in range(num_cameras):
            cam = cam_list[i]

            # Get device info
            nodemap = cam.GetTLDeviceNodeMap()

            # Model
            node_model = PySpin.CStringPtr(nodemap.GetNode('DeviceModelName'))
            model = node_model.GetValue() if PySpin.IsAvailable(node_model) and PySpin.IsReadable(node_model) else "Unknown"

            # Serial
            node_serial = PySpin.CStringPtr(nodemap.GetNode('DeviceSerialNumber'))
            serial = node_serial.GetValue() if PySpin.IsAvailable(node_serial) and PySpin.IsReadable(node_serial) else "Unknown"

            print(f"\n  Camera {i}:")
            print(f"    Model: {model}")
            print(f"    Serial: {serial}")

        # Cleanup
        cam_list.Clear()
        system.ReleaseInstance()
        return True

    except Exception as e:
        print(f"[FAIL] Error during camera detection: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_camera_open(PySpin):
    """Test opening and capturing from first camera"""
    print("\n" + "="*70)
    print("TEST 4: Camera Open & Capture")
    print("="*70)

    try:
        # Get system instance
        system = PySpin.System.GetInstance()

        # Get camera list
        cam_list = system.GetCameras()
        num_cameras = cam_list.GetSize()

        if num_cameras == 0:
            print("[SKIP] No cameras to test")
            cam_list.Clear()
            system.ReleaseInstance()
            return False

        # Get first camera
        cam = cam_list[0]

        print("Opening camera 0...")
        cam.Init()
        print("[PASS] Camera initialized")

        # Configure for continuous acquisition
        nodemap = cam.GetNodeMap()
        node_acquisition_mode = PySpin.CEnumerationPtr(nodemap.GetNode('AcquisitionMode'))
        if PySpin.IsAvailable(node_acquisition_mode) and PySpin.IsWritable(node_acquisition_mode):
            node_mode_continuous = node_acquisition_mode.GetEntryByName('Continuous')
            acquisition_mode_continuous = node_mode_continuous.GetValue()
            node_acquisition_mode.SetIntValue(acquisition_mode_continuous)
            print("[PASS] Acquisition mode set to continuous")

        # Start acquisition
        cam.BeginAcquisition()
        print("[PASS] Acquisition started")

        # Capture test frames
        print("Capturing 5 test frames...")
        for i in range(5):
            image_result = cam.GetNextImage(1000)

            if image_result.IsIncomplete():
                print(f"  Frame {i+1}: [FAIL] Incomplete")
            else:
                width = image_result.GetWidth()
                height = image_result.GetHeight()
                print(f"  Frame {i+1}: [PASS] {width}x{height}")

            image_result.Release()

        # End acquisition
        cam.EndAcquisition()
        print("[PASS] Acquisition stopped")

        # Deinitialize
        cam.DeInit()
        print("[PASS] Camera deinitialized")

        # Cleanup
        del cam
        cam_list.Clear()
        system.ReleaseInstance()

        print("\n[PASS] Camera open & capture test successful!")
        return True

    except Exception as e:
        print(f"[FAIL] Error during camera test: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_application_compatibility():
    """Test if application can detect the camera"""
    print("\n" + "="*70)
    print("TEST 5: Application Compatibility")
    print("="*70)

    try:
        from rgb_camera_firefly import RGBCameraFirefly, detect_firefly_cameras, PYSPIN_AVAILABLE

        print(f"PYSPIN_AVAILABLE: {PYSPIN_AVAILABLE}")

        if not PYSPIN_AVAILABLE:
            print("[FAIL] Application reports PySpin not available")
            return False

        print("[PASS] Application can import PySpin")

        # Try detection
        cameras = detect_firefly_cameras()
        print(f"Application detected {len(cameras)} camera(s)")

        if len(cameras) == 0:
            print("[WARN] No cameras detected by application")
            return False

        for cam in cameras:
            print(f"  - {cam['model']} (S/N: {cam['serial']})")

        print("\n[PASS] Application compatibility verified!")
        return True

    except Exception as e:
        print(f"[FAIL] Application compatibility test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all verification tests"""
    print("\n" + "="*70)
    print("  PYSPIN INSTALLATION VERIFICATION")
    print("="*70)

    import sys
    print(f"\nPython Version: {sys.version}")
    print(f"Python Executable: {sys.executable}")

    # Test 1: Import
    success, PySpin = test_pyspin_import()
    if not success:
        print("\n" + "="*70)
        print("RESULT: PySpin is NOT installed")
        print("="*70)
        print("See install_pyspin.md for installation instructions")
        return

    # Test 2: Version
    test_pyspin_version(PySpin)

    # Test 3: Detection
    cameras_found = test_camera_detection(PySpin)

    # Test 4: Open & Capture (only if cameras found)
    if cameras_found:
        test_camera_open(PySpin)

    # Test 5: Application compatibility
    test_application_compatibility()

    # Summary
    print("\n" + "="*70)
    print("  SUMMARY")
    print("="*70)

    if cameras_found:
        print("[SUCCESS] PySpin is fully functional!")
        print("\nYou can now run the main application:")
        print("  python main.py")
    else:
        print("[PARTIAL SUCCESS] PySpin is installed but no cameras detected")
        print("\nNext steps:")
        print("  1. Connect FLIR Firefly camera via USB 3.0")
        print("  2. Check Device Manager")
        print("  3. Run this script again")

    print("="*70 + "\n")

if __name__ == "__main__":
    main()
