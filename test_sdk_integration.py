"""
Quick test for Boson SDK integration
"""
import sys
import logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s:%(name)s:%(message)s')

# Test COM port scanning
print("=" * 60)
print("TESTING BOSON SDK INTEGRATION")
print("=" * 60)

# Test 1: COM Port Scanning
print("\n1. Testing COM port scanning...")
try:
    import serial.tools.list_ports
    ports = []
    for port in serial.tools.list_ports.comports():
        ports.append(port.device)
        print(f"   Found: {port.device} - {port.description}")
    
    if ports:
        print(f"   ✓ Found {len(ports)} COM ports")
    else:
        print("   ✗ No COM ports found")
except ImportError:
    print("   ✗ pyserial not installed")
except Exception as e:
    print(f"   ✗ Error: {e}")

# Test 2: Check if BosonSDKPanel exists
print("\n2. Testing BosonSDKPanel import...")
try:
    from inspection_gui_qt import BosonSDKPanel
    print("   ✓ BosonSDKPanel imported successfully")
except ImportError as e:
    print(f"   ✗ Import failed: {e}")

# Test 3: Check backend methods
print("\n3. Testing backend methods...")
try:
    from inspection_main import ThermalInspectionFusion
    import inspect
    
    methods = ['connect_boson_sdk', 'scan_boson_com_ports', 'trigger_ffc', 'disconnect_boson_sdk']
    for method in methods:
        if hasattr(ThermalInspectionFusion, method):
            print(f"   ✓ {method} exists")
        else:
            print(f"   ✗ {method} missing")
except Exception as e:
    print(f"   ✗ Error: {e}")

print("\n" + "=" * 60)
print("SDK INTEGRATION TEST COMPLETE")
print("=" * 60)
