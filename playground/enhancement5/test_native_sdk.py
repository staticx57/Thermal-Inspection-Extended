#!/usr/bin/env python3
"""
Test Native SDK directly (without flirpy) to compare GET command behavior.

This will help determine if the GET command issue is:
1. A flirpy serial connection issue
2. A MockFSLP implementation issue
3. An actual camera firmware limitation
"""

import sys
import os

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(CURRENT_DIR))
SDK_BASE = os.path.join(PROJECT_ROOT, '3.0 IDD & SDK', 'SDK_USER_PERMISSIONS')
SDK_PATH = os.path.join(SDK_BASE, 'SDK_USER_PERMISSIONS')

if SDK_BASE not in sys.path:
    sys.path.insert(0, SDK_BASE)
if SDK_PATH not in sys.path:
    sys.path.insert(0, SDK_PATH)

try:
    # Try to import native SDK
    from SDK_USER_PERMISSIONS.ClientFiles_Python import Client_Packager
    from SDK_USER_PERMISSIONS.ClientFiles_Python import FLIRSerial

    print("=" * 60)
    print("Native SDK Direct Test")
    print("=" * 60)

    print("\nTrying to create native FSLP connection to COM7...")

    # Try to create real FSLP connection
    try:
        fslp = FLIRSerial.FLIRSerial()
        fslp.open('COM7', 921600)
        print("✓ Native FSLP connection established")

        # Create packager with real FSLP
        packager = Client_Packager.Packager(fslp)
        print("✓ Packager created with native FSLP")

        # Try GET gamma
        print("\nTesting GET gamma with native SDK...")
        try:
            gamma = packager.CLIENT_pkg_agc_GetGamma()
            print(f"GET gamma result: {gamma}")
        except Exception as e:
            print(f"GET gamma failed: {e}")

        # Try SET then GET
        print("\nTesting SET gamma to 1.5...")
        try:
            packager.CLIENT_pkg_agc_SetGamma(1.5)
            print("✓ SET gamma successful")
        except Exception as e:
            print(f"SET gamma failed: {e}")

        print("Testing GET gamma after SET...")
        try:
            gamma = packager.CLIENT_pkg_agc_GetGamma()
            print(f"GET gamma result: {gamma}")
        except Exception as e:
            print(f"GET gamma failed: {e}")

        # Try GET emissivity
        print("\nTesting GET emissivity...")
        try:
            emissivity = packager.CLIENT_pkg_radiometry_GetEmissivityTarget()
            print(f"GET emissivity result: {emissivity}")
        except Exception as e:
            print(f"GET emissivity failed: {e}")

        fslp.close()
        print("\n✓ Native FSLP connection closed")

    except Exception as e:
        print(f"✗ Native FSLP failed: {e}")
        print("\nThis could mean:")
        print("1. FLIRSerial module not found/compatible")
        print("2. COM7 already in use by another process")
        print("3. SDK version doesn't include FLIRSerial")

except ImportError as e:
    print(f"✗ Could not import native SDK: {e}")
    print("\nNative SDK test not possible.")
    print("The GET command limitation is likely a camera firmware issue,")
    print("not a flirpy/MockFSLP issue, since both would use the same")
    print("underlying serial protocol.")

print("\n" + "=" * 60)
print("NOTE: Official FLIR apps may use USB interface instead of")
print("serial commands for some operations, which would explain")
print("why they can retrieve settings that we cannot via serial.")
print("=" * 60)
