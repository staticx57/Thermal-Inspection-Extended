#!/usr/bin/env python3
"""
Quick test to verify Firefly camera can be accessed and controlled.
This script properly cleans up Spinnaker resources.
"""
import PySpin
import sys

def test_firefly_basic():
    """Test basic Firefly camera access and control."""
    system = None
    cam_list = None
    cam = None
    
    try:
        print("=" * 60)
        print("Firefly Camera Quick Test")
        print("=" * 60)
        
        # Get system instance
        system = PySpin.System.GetInstance()
        
        # Get camera list
        cam_list = system.GetCameras()
        num_cameras = cam_list.GetSize()
        
        print(f"\nCameras detected: {num_cameras}")
        
        if num_cameras == 0:
            print("ERROR: No cameras found!")
            return False
        
        # Get first camera
        cam = cam_list.GetByIndex(0)
        
        # Get device info
        nodemap_tldevice = cam.GetTLDeviceNodeMap()
        node_device_info = PySpin.CCategoryPtr(nodemap_tldevice.GetNode('DeviceInformation'))
        
        if PySpin.IsAvailable(node_device_info) and PySpin.IsReadable(node_device_info):
            features = node_device_info.GetFeatures()
            print("\nCamera Information:")
            for feature in features:
                node_feature = PySpin.CValuePtr(feature)
                if PySpin.IsReadable(node_feature):
                    print(f"  {node_feature.GetName()}: {node_feature.ToString()}")
        
        # Initialize camera
        print("\nInitializing camera...")
        cam.Init()
        print("✅ Camera initialized successfully!")
        
        # Get camera nodemap
        nodemap = cam.GetNodeMap()
        
        # Test exposure mode
        print("\nTesting Exposure Control...")
        node_exposure_auto = PySpin.CEnumerationPtr(nodemap.GetNode('ExposureAuto'))
        if PySpin.IsAvailable(node_exposure_auto) and PySpin.IsWritable(node_exposure_auto):
            print("  ✅ Exposure control available")
            # Try setting to manual
            entry_off = node_exposure_auto.GetEntryByName('Off')
            if PySpin.IsAvailable(entry_off):
                node_exposure_auto.SetIntValue(entry_off.GetValue())
                print("  ✅ Set to manual mode")
        
        # Test gain control
        print("\nTesting Gain Control...")
        node_gain = PySpin.CFloatPtr(nodemap.GetNode('Gain'))
        if PySpin.IsAvailable(node_gain) and PySpin.IsWritable(node_gain):
            current_gain = node_gain.GetValue()
            print(f"  ✅ Gain control available (current: {current_gain:.2f} dB)")
        
        # Test white balance
        print("\nTesting White Balance...")
        node_wb_auto = PySpin.CEnumerationPtr(nodemap.GetNode('BalanceWhiteAuto'))
        if PySpin.IsAvailable(node_wb_auto):
            print("  ✅ White balance control available")
        
        # Test trigger
        print("\nTesting Trigger Mode...")
        node_trigger_mode = PySpin.CEnumerationPtr(nodemap.GetNode('TriggerMode'))
        if PySpin.IsAvailable(node_trigger_mode):
            print("  ✅ Trigger control available")
        
        print("\n" + "=" * 60)
        print("✅ ALL BASIC TESTS PASSED!")
        print("=" * 60)
        print("\nThe Firefly camera is ready for use in the main application.")
        print("You can now run: python inspection_main.py")
        print("=" * 60)
        
        return True
        
    except PySpin.SpinnakerException as ex:
        print(f"\n❌ Spinnaker Error: {ex}")
        return False
    except Exception as e:
        print(f"\n❌ Unexpected Error: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # Proper cleanup
        print("\nCleaning up...")
        if cam is not None:
            try:
                if cam.IsInitialized():
                    cam.DeInit()
                    print("  Camera deinitialized")
            except:
                pass
            try:
                del cam
                print("  Camera object deleted")
            except:
                pass
        
        if cam_list is not None:
            try:
                cam_list.Clear()
                print("  Camera list cleared")
            except:
                pass
            try:
                del cam_list
            except:
                pass
        
        if system is not None:
            try:
                system.ReleaseInstance()
                print("  System released")
            except:
                pass
        
        print("✅ Cleanup complete\n")

if __name__ == "__main__":
    success = test_firefly_basic()
    sys.exit(0 if success else 1)
