#!/usr/bin/env python3
"""
Test Raw SDK Packet Injection via Flirpy's send/receive

Goal: Validate that we can send raw Boson SDK command packets
      through flirpy's serial connection using send() and receive().

Test Command: GetGainMode (read-only, safe to test)
"""

import sys
import os
import time
import logging

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

# Import flirpy
try:
    from flirpy.camera.boson import Boson
except ImportError:
    logger.error("✗ flirpy not installed")
    sys.exit(1)

# Import SDK for packet generation
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
SDK_BASE = os.path.join(CURRENT_DIR, '3.0 IDD & SDK', 'SDK_USER_PERMISSIONS')
SDK_PATH = os.path.join(SDK_BASE, 'SDK_USER_PERMISSIONS')

SDK_AVAILABLE = False
if os.path.exists(SDK_PATH):
    if SDK_BASE not in sys.path:
        sys.path.insert(0, SDK_BASE)
    if SDK_PATH not in sys.path:
        sys.path.insert(0, SDK_PATH)
    
    try:
        from SDK_USER_PERMISSIONS.ClientFiles_Python import Client_Packager
        from SDK_USER_PERMISSIONS.ClientFiles_Python.EnumTypes import FLR_BOSON_GAINMODE_E
        SDK_AVAILABLE = True
        logger.info("✓ Boson SDK found")
    except ImportError as e:
        logger.warning(f"⚠ SDK import failed: {e}")


class MockFSLP:
    """Mock FSLP layer to capture bytes from SDK Packager."""
    def __init__(self):
        self.last_sent_bytes = None
        self.port_id = 0 # SDK uses port_id or portID depending on version
        self.portID = 0 
        
    def sendToCamera(self, portID, data, numBytes):
        """Capture bytes sent by Packager (matches FSLP signature)."""
        if hasattr(data, 'decode'): 
            self.last_sent_bytes = data
        else: 
             self.last_sent_bytes = bytearray(data)
        return 0 
        
    def sendFrame(self, *args):
        """Capture bytes from sendFrame (robust to varying signatures)."""
        # SDK calls it with different args depending on version
        # We just need to find the data payload (bytes/bytearray/list of ints)
        for arg in args:
            if hasattr(arg, 'decode') or isinstance(arg, (bytes, bytearray)):
                self.last_sent_bytes = arg
                break
            elif isinstance(arg, list) and len(arg) > 0 and isinstance(arg[0], int):
                 self.last_sent_bytes = bytearray(arg)
                 break
        return 0
        
    def readFrame(self, *args):
        """Mock readFrame to satisfy dispatcher."""
        # Dispatcher expects the payload to be returned
        return bytearray(32) # Return dummy bytes to satisfy len() check
        
    def send(self, data):
        """Capture bytes sent by Packager (legacy/fallback)."""
        self.last_sent_bytes = data
        return len(data) 
        
    def read(self, num_bytes):
        """Mock read (not used for generation)."""
        return bytearray(num_bytes)

def test_raw_sdk_packet_injection(com_port='COM7'):
    """Test sending raw SDK command packet via flirpy serial connection."""
    logger.info("="*60)
    logger.info("VALIDATING SEND/RECEIVE WITH REAL COMMANDS")
    logger.info("="*60)
    
    if not SDK_AVAILABLE:
        logger.error("✗ SDK not available - cannot generate packets")
        return False
    
    try:
        # Import Packager
        from SDK_USER_PERMISSIONS.ClientFiles_Python import Client_Packager
        from SDK_USER_PERMISSIONS.ClientFiles_Python.EnumTypes import FLR_BOSON_GAINMODE_E
        
        # 1. Initialize Mock FSLP and Packager
        mock_fslp = MockFSLP()
        packager = Client_Packager.Packager(mock_fslp)
        
        # 2. Generate "Get Gain Mode" packet
        # 0x000B0000 is typically GetGainMode (or similar, need to verify with SDK)
        # Using built-in packager function is safest
        logger.info("Generating 'GetGainMode' packet via SDK Packager...")
        
        # The Packager methods usually return (returnCode, data) AND send bytes to fslp
        # We need to find the specific packager method for Gain Mode
        # Inspecting Client_Packager.py earlier, we saw methods like CLIENT_pkg_boson_SetGainMode
        # Let's hope there's CLIENT_pkg_boson_GetGainMode
        
        if hasattr(packager, 'CLIENT_pkg_boson_GetGainMode'):
            # This triggers fslp.send() internally
            packager.CLIENT_pkg_boson_GetGainMode() 
            packet = mock_fslp.last_sent_bytes
            
            if packet:
                logger.info(f"✓ Packet generated: {packet.hex().upper()}")
                logger.info(f"  Length: {len(packet)} bytes")
            else:
                logger.error("✗ Failed to generate packet")
                return False
        else:
            logger.warning("⚠ CLIENT_pkg_boson_GetGainMode not found, using manual packet for test")
            # Fallback: Construct a known valid packet for "Get Gain Mode"? 
            # Or use a simpler command like GetCameraSN (0x00050002?)
            # Let's try GetCameraSN as fallback
            if hasattr(packager, 'CLIENT_pkg_boson_GetCameraSN'):
                 packager.CLIENT_pkg_boson_GetCameraSN()
                 packet = mock_fslp.last_sent_bytes
                 logger.info(f"✓ Generated 'GetCameraSN' packet: {packet.hex().upper()}")
            else:
                 logger.error("✗ Could not find packager methods")
                 return False

        # 3. Connect via flirpy
        logger.info(f"\n📡 Connecting to Boson on {com_port}...")
        camera = Boson(port=com_port)
        logger.info("✓ Connected via flirpy")
        
        # 4. Inject Packet
        logger.info("\n💉 Injecting packet via camera.send()...")
        
        # Try to use flirpy's send method which might handle framing
        # camera.send(packet)
        # Note: flirpy's send might expect (module, function, data) or just valid packet
        # Let's try sending the raw packet first
        try:
            camera.send(packet)
            logger.info("✓ Packet sent via camera.send()")
            
            # 5. Read Response
            logger.info("📥 Waiting for response...")
            # camera.receive() usually returns the payload
            response = camera.receive()
            if response:
                logger.info(f"✓ Received response: {response}")
                logger.info("✓ TEST PASSED: Successfully sent/received SDK command via flirpy!")
                return True
            else:
                logger.warning("⚠ No response returned by receive()")
                return False
                
        except Exception as e:
            logger.error(f"✗ camera.send() failed: {e}")
            logger.info("  Standard send() might not handle raw payloads.")
            return False
        
    except Exception as e:
        logger.error(f"✗ Test failed: {e}", exc_info=True)
        return False


if __name__ == "__main__":
    com_port = input("Enter COM port (default: COM7): ").strip() or 'COM7'
    test_raw_sdk_packet_injection(com_port)
