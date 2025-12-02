#!/usr/bin/env python3
"""Test T-Linear SDK function calls."""
import sys
sys.path.insert(0, r'C:\Users\stati\Desktop\Projects\Thermal-Inspection')

from boson_sdk_wrapper import BosonSDK

print("="*60)
print("Testing T-Linear SDK Functions")
print("="*60)

sdk = BosonSDK(com_port='COM7')

if sdk.open():
    print("\n[OK] SDK connected")

    # Check available functions
    cam = sdk.camera
    print("\nChecking for T-Linear functions:")

    tlinear_funcs = [attr for attr in dir(cam) if 'tlinear' in attr.lower() or 'TLinear' in attr]
    if tlinear_funcs:
        print(f"  Found {len(tlinear_funcs)} T-Linear functions:")
        for func in tlinear_funcs:
            print(f"    - {func}")
    else:
        print("  No T-Linear functions found")

    # Try to get current T-Linear state
    print("\nTrying to read T-Linear state:")
    try:
        if hasattr(cam, 'CLIENT_pkg_TLinear_GetControl'):
            result = cam.CLIENT_pkg_TLinear_GetControl()
            print(f"  GetControl result: {result}")
            if hasattr(result, 'value'):
                print(f"  Value: {result.value}")
    except Exception as e:
        print(f"  Error: {e}")

    # Try to enable T-Linear
    print("\nTrying to enable T-Linear mode:")
    try:
        if hasattr(cam, 'CLIENT_pkg_TLinear_SetControl'):
            class CTypesInt:
                def __init__(self, val):
                    self.value = val

            arg = CTypesInt(1)  # 1 = Enable
            result = cam.CLIENT_pkg_TLinear_SetControl(arg)
            val = result.value if hasattr(result, 'value') else result
            print(f"  SetControl result: {val}")

            if val == 0:
                print("  [OK] T-Linear enabled successfully")

                # Try to read state again
                result2 = cam.CLIENT_pkg_TLinear_GetControl()
                print(f"  Verify GetControl: {result2}")
            else:
                print(f"  [ERROR] T-Linear enable failed with code: {val}")
        else:
            print("  CLIENT_pkg_TLinear_SetControl not found")
    except Exception as e:
        print(f"  Error: {e}")
        import traceback
        traceback.print_exc()

    sdk.close()
    print("\n[OK] SDK closed")

print("\n" + "="*60)
