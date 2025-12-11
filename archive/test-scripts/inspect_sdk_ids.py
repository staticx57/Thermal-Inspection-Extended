
import sys
import os
import inspect

# Add SDK path
CURRENT_DIR = os.path.abspath('.')
SDK_BASE = os.path.join(CURRENT_DIR, '3.0 IDD & SDK', 'SDK_USER_PERMISSIONS')
SDK_PATH = os.path.join(SDK_BASE, 'SDK_USER_PERMISSIONS')

print(f"Adding SDK path: {SDK_PATH}")
if SDK_BASE not in sys.path:
    sys.path.insert(0, SDK_BASE)
if SDK_PATH not in sys.path:
    sys.path.insert(0, SDK_PATH)

try:
    try:
        from SDK_USER_PERMISSIONS.ClientFiles_Python import Client_Packager
    except ImportError:
        from ClientFiles_Python import Client_Packager
    print("Successfully imported Client_Packager")
    
    # helper to print function info
    def print_func_info(func_name):
        if hasattr(Client_Packager.Packager, func_name):
            func = getattr(Client_Packager.Packager, func_name)
            print(f"\n--- {func_name} ---")
            try:
                # Print the source code to find command ID
                src = inspect.getsource(func)
                for line in src.splitlines():
                    if "CLIENT_dispatch" in line:
                        print(f"  {line.strip()}")
            except Exception as e:
                print(f"  Could not get source: {e}")
        else:
            print(f"\n--- {func_name} NOT FOUND ---")

    # Functions to inspect
    funcs_to_check = [
        "CLIENT_pkg_boson_SetGainMode",
        "CLIENT_pkg_boson_SetFFCMode",
        "CLIENT_pkg_boson_RunFFC",
        "CLIENT_pkg_colorLut_SetId",
        "CLIENT_pkg_colorLut_SetControl"
    ]

    for func_name in funcs_to_check:
        print_func_info(func_name)
        if hasattr(Client_Packager.Packager, func_name):
            func = getattr(Client_Packager.Packager, func_name)
            try:
                src = inspect.getsource(func)
                print("  Source snippet:")
                for line in src.splitlines()[0:15]: # Print first 15 lines to see packing
                     print(f"    {line.strip()}")
            except:
                pass

except ImportError as e:
    print(f"ImportError: {e}")
except Exception as e:
    print(f"Error: {e}")
