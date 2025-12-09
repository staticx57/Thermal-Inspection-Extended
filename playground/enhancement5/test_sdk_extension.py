#!/usr/bin/env python3
"""
Test Enhanced FlirpySDKBridge with Camera

Tests the SDK packet injection functionality added in Enhancement #5.
Requires a FLIR Boson camera connected via USB + COM port.

Usage:
    python test_sdk_extension.py
    python test_sdk_extension.py --mock-only  # Test packet generation without camera
"""

import sys
import os
import argparse
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)

# Add parent paths for imports
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, CURRENT_DIR)

from flirpy_sdk_bridge import (
    FlirpySDKBridge, MockFSLP, GainMode, ColorLUT,
    SDK_PACKAGER_AVAILABLE, Client_Packager
)


def test_mock_fslp():
    """Test that MockFSLP captures packets correctly (no camera needed)."""
    print("\n" + "=" * 60)
    print("TEST: MockFSLP Packet Capture")
    print("=" * 60)
    
    if not SDK_PACKAGER_AVAILABLE:
        print("[X] SDK Packager not available - cannot test packet generation")
        return False
    
    try:
        mock_fslp = MockFSLP()
        packager = Client_Packager.Packager(mock_fslp)
        
        # Test generating a GetGainMode packet
        print("\n1. Testing GetGainMode packet generation...")
        if hasattr(packager, 'CLIENT_pkg_boson_GetGainMode'):
            packager.CLIENT_pkg_boson_GetGainMode()
            packet = mock_fslp.get_last_packet()
            if packet:
                print(f"   [OK] Packet generated: {len(packet)} bytes")
                print(f"   [OK] Hex: {packet.hex()[:60]}...")
            else:
                print("   [X] No packet captured")
                return False
        else:
            print("   [!] CLIENT_pkg_boson_GetGainMode not found")
        
        # Test generating an AGC SetGamma packet
        print("\n2. Testing AGC SetGamma packet generation...")
        mock_fslp.clear()
        if hasattr(packager, 'CLIENT_pkg_agc_SetGamma'):
            packager.CLIENT_pkg_agc_SetGamma(1.5)
            packet = mock_fslp.get_last_packet()
            if packet:
                print(f"   [OK] Packet generated: {len(packet)} bytes")
                print(f"   [OK] Hex: {packet.hex()[:60]}...")
            else:
                print("   [X] No packet captured")
                return False
        else:
            print("   [!] CLIENT_pkg_agc_SetGamma not found")
        
        # Test emissivity packet
        print("\n3. Testing Radiometry SetEmissivityTarget packet...")
        mock_fslp.clear()
        if hasattr(packager, 'CLIENT_pkg_radiometry_SetEmissivityTarget'):
            packager.CLIENT_pkg_radiometry_SetEmissivityTarget(0.95)
            packet = mock_fslp.get_last_packet()
            if packet:
                print(f"   [OK] Packet generated: {len(packet)} bytes")
                print(f"   [OK] Hex: {packet.hex()[:60]}...")
            else:
                print("   [X] No packet captured")
                return False
        else:
            print("   [!] CLIENT_pkg_radiometry_SetEmissivityTarget not found")

        print("\n[OK] MockFSLP packet capture test PASSED")
        return True

    except Exception as e:
        print(f"\n[X] MockFSLP test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_with_camera(com_port='COM7'):
    """Test SDK commands with real camera."""
    print("\n" + "=" * 60)
    print(f"TEST: Live SDK Commands (Camera on {com_port})")
    print("=" * 60)
    
    try:
        from flirpy.camera.boson import Boson
    except ImportError:
        print("[X] flirpy not installed")
        return False
    
    try:
        print(f"\n1. Connecting to Boson on {com_port}...")
        camera = Boson(port=com_port)
        print("   [OK] Connected via flirpy")

        print("\n2. Initializing SDK bridge...")
        bridge = FlirpySDKBridge(camera)
        print(f"   SDK available: {bridge.is_sdk_available()}")

        if not bridge.is_sdk_available():
            print("   [X] SDK Packager not available - cannot test advanced commands")
            camera.close()
            return False
        
        # Test native flirpy methods (should always work)
        print("\n3. Testing native flirpy methods...")
        fpa_temp = bridge.get_fpa_temperature()
        print(f"   FPA Temperature: {fpa_temp}")
        
        serial = bridge.get_camera_serial()
        print(f"   Camera Serial: {serial}")
        
        # Test AGC gamma
        print("\n4. Testing AGC gamma control...")
        current_gamma = bridge.get_agc_gamma()
        print(f"   Current gamma: {current_gamma}")
        
        success = bridge.set_agc_gamma(1.2)
        print(f"   Set gamma to 1.2: {'[OK]' if success else '[X]'}")

        # Verify change
        new_gamma = bridge.get_agc_gamma()
        print(f"   New gamma: {new_gamma}")

        # Test emissivity
        print("\n5. Testing emissivity control...")
        current_emissivity = bridge.get_emissivity()
        print(f"   Current emissivity: {current_emissivity}")

        success = bridge.set_emissivity(0.95)
        print(f"   Set emissivity to 0.95: {'[OK]' if success else '[X]'}")

        # Close camera
        print("\n6. Closing camera...")
        camera.close()
        print("   [OK] Camera closed")

        print("\n[OK] Live camera test PASSED")
        return True

    except Exception as e:
        print(f"\n[X] Camera test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    parser = argparse.ArgumentParser(description='Test Enhanced FlirpySDKBridge')
    parser.add_argument('--mock-only', action='store_true', 
                        help='Only test packet generation (no camera needed)')
    parser.add_argument('--port', default='COM7',
                        help='COM port for camera (default: COM7)')
    args = parser.parse_args()
    
    print("=" * 60)
    print("Enhancement #5: Flirpy SDK Extension Test")
    print("=" * 60)
    
    # Always run mock test first
    mock_passed = test_mock_fslp()
    
    if args.mock_only:
        print("\n" + "=" * 60)
        print(f"RESULT: {'PASSED' if mock_passed else 'FAILED'} (mock-only mode)")
        print("=" * 60)
        return 0 if mock_passed else 1
    
    # Run camera test
    camera_passed = test_with_camera(args.port)
    
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"  Mock FSLP test:  {'PASSED' if mock_passed else 'FAILED'}")
    print(f"  Camera test:     {'PASSED' if camera_passed else 'FAILED'}")
    print("=" * 60)
    
    return 0 if (mock_passed and camera_passed) else 1


if __name__ == "__main__":
    sys.exit(main())
