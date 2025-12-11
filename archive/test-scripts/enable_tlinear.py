import sys
import os
import time
import logging
import ctypes

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Add current directory to path to find modules
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

# Add SDK path
sdk_path = os.path.join(current_dir, '3.0 IDD & SDK', 'SDK_USER_PERMISSIONS')
if sdk_path not in sys.path:
    sys.path.insert(0, sdk_path)

try:
    from boson_sdk_wrapper import BosonSDK
    from boson_serial import BosonSerialInterface
    # Try to import the Enum
    from SDK_USER_PERMISSIONS.ClientFiles_Python.EnumTypes import FLR_ENABLE_E
except ImportError as e:
    logger.error(f"Failed to import SDK wrappers or Enums: {e}")
    # Fallback: create a mock object if import fails
    class FLR_ENABLE_E:
        class FLR_ENABLE:
            value = 1
        class FLR_DISABLE:
            value = 0

def enable_tlinear():
    # 1. Scan for ports
    ports = BosonSerialInterface.find_boson_com_ports()
    if not ports:
        logger.error("No Boson COM ports found")
        return

    port = ports[0]
    logger.info(f"Connecting to Boson on {port}...")

    sdk = BosonSDK(com_port=port)
    if not sdk.open():
        logger.error("Failed to open SDK")
        return

    try:
        # 2. Enable T-Linear
        logger.info("Attempting to enable T-Linear...")
        
        cam = sdk.camera
        
        if hasattr(cam, 'CLIENT_pkg_TLinear_SetControl'):
            # Pass the Enum object, not an int
            # FLR_ENABLE_E.FLR_ENABLE is likely the value 1, but we need an object with .value
            # If FLR_ENABLE_E is an IntEnum, it might not have .value if passed directly?
            # The error said "int object has no attribute value", so it expects something with .value.
            
            # Let's check what FLR_ENABLE_E.FLR_ENABLE is
            # If it's just an int, we need to wrap it.
            
            # Create a simple wrapper class
            class CTypesInt:
                def __init__(self, val):
                    self.value = val
            
            arg = CTypesInt(1)
            
            logger.info(f"Calling SetControl with object having value={arg.value}...")
            res = cam.CLIENT_pkg_TLinear_SetControl(arg)
            
            # Handle result
            val = res.value if hasattr(res, 'value') else res
            
            if val == 0:
                logger.info("✓ T-Linear ENABLED successfully")
            else:
                logger.error(f"Failed to enable T-Linear. Result code: {val}")
        else:
            logger.error("CLIENT_pkg_TLinear_SetControl not found on camera object")

        # 3. Verify with GetControl
        if hasattr(cam, 'CLIENT_pkg_TLinear_GetControl'):
            try:
                ret = cam.CLIENT_pkg_TLinear_GetControl()
                # Usually returns (result, output_enum)
                if isinstance(ret, tuple):
                    res = ret[0]
                    enabled = ret[1]
                    
                    res_val = res.value if hasattr(res, 'value') else res
                    en_val = enabled.value if hasattr(enabled, 'value') else enabled
                    
                    logger.info(f"GetControl Result: {res_val}")
                    logger.info(f"T-Linear State: {en_val} (1=Enabled)")
                else:
                    logger.info(f"GetControl returned: {ret}")
            except Exception as e:
                logger.error(f"Error calling GetControl: {e}")

    except Exception as e:
        logger.error(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        sdk.close()

if __name__ == "__main__":
    enable_tlinear()
