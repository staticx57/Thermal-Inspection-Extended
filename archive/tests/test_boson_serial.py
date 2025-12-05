#!/usr/bin/env python3
"""
Test script for FLIR Boson serial communication.
Run this with your Boson 320x256 connected via USB.
"""

import sys
import time
import logging
from boson_serial import (
    BosonSerialInterface,
    AGCAlgorithm,
    ShutterMode,
    GainMode,
    TelemetryLocation
)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def main():
    """Test Boson serial interface with physical camera."""
    print("=" * 80)
    print("FLIR Boson Serial Communication Test")
    print("=" * 80)
    print("\nThis test will:")
    print("1. Detect Boson COM ports")
    print("2. Connect to the camera")
    print("3. Test AGC and shutter commands")
    print("4. Trigger FFC (you'll see the shutter close)")
    print("\nMake sure your Boson camera is connected via USB.")
    print("=" * 80)

    input("\nPress Enter to start...\n")

    # Step 1: Find Boson COM ports
    print("\n[Step 1] Detecting Boson COM ports...")
    ports = BosonSerialInterface.find_boson_com_ports()

    if not ports:
        print("\n[ERROR] No Boson COM ports found!")
        print("\nTroubleshooting:")
        print("1. Check Device Manager (Win+X -> Device Manager)")
        print("2. Look for 'Ports (COM & LPT)'")
        print("3. Boson should appear as 'USB Serial Port (COMX)' or 'FLIR Boson'")
        print("4. If not visible, try:")
        print("   - Reconnect USB cable")
        print("   - Try different USB port")
        print("   - Install FLIR drivers if needed")
        return 1

    print(f"[OK] Found {len(ports)} Boson port(s): {', '.join(ports)}")

    # Step 2: Connect to first port
    print(f"\n[Step 2] Connecting to {ports[0]}...")
    boson = BosonSerialInterface(com_port=ports[0])

    if not boson.open():
        print(f"[ERROR] Failed to connect to {ports[0]}")
        print("\nPossible causes:")
        print("1. Port is in use by another application")
        print("2. Insufficient permissions")
        print("3. Wrong baud rate")
        return 1

    print(f"[OK] Connected to Boson on {boson.com_port}")

    try:
        # Display camera info
        info = boson.get_camera_info()
        print("\n" + "-" * 80)
        print("Camera Information:")
        print("-" * 80)
        print(f"  Model: {info.model}")
        print(f"  Resolution: {info.resolution[0]}x{info.resolution[1]}")
        print(f"  Serial Number: {info.serial_number or 'Not available'}")
        print(f"  Part Number: {info.part_number or 'Not available'}")
        print(f"  Radiometric: {'Yes' if info.radiometric else 'No (this is expected)'}")

        # Test AGC
        print("\n" + "-" * 80)
        print("[Step 3] Testing AGC (Automatic Gain Control)...")
        print("-" * 80)

        current_agc = boson.get_agc_algorithm()
        if current_agc:
            print(f"  Current AGC Algorithm: {current_agc.name}")
        else:
            print("  [WARNING] Could not read current AGC algorithm")

        # Try setting AGC to histogram mode
        print("\n  Attempting to set AGC to HISTOGRAM mode...")
        if boson.set_agc_algorithm(AGCAlgorithm.HISTOGRAM):
            print("  [OK] AGC set to HISTOGRAM")
            time.sleep(0.5)

            # Verify
            new_agc = boson.get_agc_algorithm()
            if new_agc:
                print(f"  Verified: AGC is now {new_agc.name}")
        else:
            print("  [WARNING] AGC command may not be supported on non-radiometric Boson")

        # Test Shutter Mode
        print("\n" + "-" * 80)
        print("[Step 4] Testing Shutter Mode...")
        print("-" * 80)

        current_shutter = boson.get_shutter_mode()
        if current_shutter:
            print(f"  Current Shutter Mode: {current_shutter.name}")
        else:
            print("  [WARNING] Could not read current shutter mode")

        # Test FFC
        print("\n" + "-" * 80)
        print("[Step 5] Testing FFC (Flat Field Correction)...")
        print("-" * 80)
        print("\n  ** WATCH YOUR CAMERA **")
        print("  The shutter should close briefly for calibration.")
        print("  This is normal and expected.")

        input("\n  Press Enter to trigger FFC...\n")

        if boson.trigger_ffc():
            print("  [OK] FFC command sent successfully!")
            print("  (Did you see the shutter close? If yes, serial communication is working!)")
        else:
            print("  [ERROR] FFC trigger failed")
            print("  This might indicate communication issues.")

        # Test Telemetry
        print("\n" + "-" * 80)
        print("[Step 6] Testing Telemetry Configuration...")
        print("-" * 80)

        print("  Enabling telemetry output...")
        if boson.enable_telemetry(True):
            print("  [OK] Telemetry enabled")
            print("  (Telemetry data will now be embedded in video frames)")
        else:
            print("  [WARNING] Telemetry enable may not be supported")

        # Test Gain Mode
        print("\n" + "-" * 80)
        print("[Step 7] Testing Gain Control...")
        print("-" * 80)

        current_gain = boson.get_gain_mode()
        if current_gain:
            print(f"  Current Gain Mode: {current_gain.name}")
        else:
            print("  [WARNING] Could not read current gain mode")

        # Summary
        print("\n" + "=" * 80)
        print("TEST SUMMARY")
        print("=" * 80)
        print(f"  Port: {boson.com_port}")
        print(f"  Connection: {'SUCCESSFUL' if boson.is_connected() else 'FAILED'}")
        print(f"  Camera Model: {info.model}")
        print("\n  Key Tests:")
        print(f"    - AGC Commands: {'Supported' if current_agc else 'Limited/Not Supported'}")
        print(f"    - Shutter Control: {'Supported' if current_shutter else 'Limited/Not Supported'}")
        print(f"    - FFC Trigger: Check if shutter closed visually")
        print(f"    - Gain Control: {'Supported' if current_gain else 'Limited/Not Supported'}")

        print("\n" + "=" * 80)
        print("Next Steps:")
        print("=" * 80)
        print("1. If FFC worked, serial communication is functioning correctly")
        print("2. Some commands may have limited support on non-radiometric Boson")
        print("3. Full command support will be available with radiometric model")
        print("4. You can now integrate this with flir_camera.py for combined video+serial control")

    finally:
        print("\n[Cleanup] Closing serial connection...")
        boson.close()
        print("[OK] Test complete!")

    return 0


if __name__ == "__main__":
    sys.exit(main())
