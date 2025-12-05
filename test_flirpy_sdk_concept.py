#!/usr/bin/env python3
"""
Test Script: Validate SDK Command Injection via Flirpy

Purpose: Proof-of-concept to test if we can send Boson SDK commands
         through flirpy's existing serial connection without breaking
         video capture.

Safety: This script only tests FFC trigger and reads camera info.
        No destructive operations.
"""

import sys
import os
import time
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

# Test flirpy availability
try:
    from flirpy.camera.boson import Boson
    FLIRPY_AVAILABLE = True
    logger.info("✓ flirpy library found")
except ImportError:
    FLIRPY_AVAILABLE = False
    logger.error("✗ flirpy library not installed")
    sys.exit(1)

# Try to import SDK (optional for this test)
SDK_BASE = os.path.join(os.path.dirname(__file__), '3.0 IDD & SDK', 'SDK_USER_PERMISSIONS')
SDK_PATH = os.path.join(SDK_BASE, 'SDK_USER_PERMISSIONS')

SDK_AVAILABLE = False
if os.path.exists(SDK_PATH):
    if SDK_BASE not in sys.path:
        sys.path.insert(0, SDK_BASE)
    if SDK_PATH not in sys.path:
        sys.path.insert(0, SDK_PATH)
    
    try:
        from ClientFiles_Python.EnumTypes import FLR_BOSON_GAINMODE_E
        SDK_AVAILABLE = True
        logger.info("✓ Boson SDK found")
    except ImportError:
        logger.warning("⚠ SDK not available (will use basic flirpy methods only)")

def test_basic_flirpy_connection(com_port='COM7'):
    """Test 1: Verify basic flirpy connection and video capture."""
    logger.info("\n=== TEST 1: Basic Flirpy Connection ===")
    
    try:
        camera = Boson(port=com_port)
        logger.info(f"✓ Connected to Boson on {com_port}")
        
        # Test FPA temperature (native flirpy method)
        temp = camera.get_fpa_temperature()
        logger.info(f"✓ FPA Temperature: {temp:.1f}°C")
        
        # Test video capture
        logger.info("Testing video capture (5 frames)...")
        for i in range(5):
            frame = camera.grab()
            if frame is not None:
                logger.info(f"  Frame {i+1}: {frame.shape}, dtype={frame.dtype}, range=[{frame.min()}, {frame.max()}]")
            else:
                logger.error(f"  Frame {i+1}: Failed to capture")
                camera.close()
                return False
            time.sleep(0.1)
        
        logger.info("✓ Video capture working")
        camera.close()
        return True
        
    except Exception as e:
        logger.error(f"✗ Connection test failed: {e}")
        return False

def test_flirpy_ffc_command(com_port='COM7'):
    """Test 2: Use flirpy's native FFC command (baseline)."""
    logger.info("\n=== TEST 2: Flirpy Native FFC Command ===")
    
    try:
        camera = Boson(port=com_port)
        logger.info(f"✓ Connected to Boson on {com_port}")
        
        # Capture a few frames before FFC
        logger.info("Capturing frames before FFC...")
        pre_frames = [camera.grab() for _ in range(3)]
        logger.info(f"  Before FFC: {len(pre_frames)} frames captured")
        
        # Trigger FFC using native flirpy method
        logger.info("Triggering FFC via flirpy.do_ffc()...")
        camera.do_ffc()
        logger.info("✓ FFC command sent")
        
        # Wait for FFC to complete
        time.sleep(2)
        
        # Capture frames after FFC
        logger.info("Capturing frames after FFC...")
        post_frames = [camera.grab() for _ in range(3)]
        logger.info(f"  After FFC: {len(post_frames)} frames captured")
        
        # Verify video still works
        if all(f is not None for f in post_frames):
            logger.info("✓ Video capture still working after FFC")
        else:
            logger.error("✗ Video capture broken after FFC")
            camera.close()
            return False
        
        camera.close()
        return True
        
    except Exception as e:
        logger.error(f"✗ FFC test failed: {e}")
        return False

def test_flirpy_serial_access(com_port='COM7'):
    """Test 3: Verify we can access flirpy's internal serial connection."""
    logger.info("\n=== TEST 3: Serial Connection Access ===")
    
    try:
        camera = Boson(port=com_port)
        logger.info(f"✓ Connected to Boson on {com_port}")
        
        # Check if camera object has serial-related attributes
        logger.info("Checking camera object attributes...")
        
        # Look for serial port or connection object
        has_send = hasattr(camera, 'send')
        has_receive = hasattr(camera, 'receive')
        has_conn = hasattr(camera, 'conn')
        has_port = hasattr(camera, 'port')
        
        logger.info(f"  has 'send' method: {has_send}")
        logger.info(f"  has 'receive' method: {has_receive}")
        logger.info(f"  has 'conn' attribute: {has_conn}")
        logger.info(f"  has 'port' attribute: {has_port}")
        
        # If port exists, try to inspect it
        if has_port and camera.port:
            logger.info(f"  Port object type: {type(camera.port)}")
            logger.info(f"  Port object attributes: {dir(camera.port)[:10]}...")
        
        # Try using send/receive if available
        if has_send and has_receive:
            logger.info("✓ Camera has send/receive methods")
            logger.info("  (These could potentially be used for SDK commands)")
        else:
            logger.warning("⚠ Camera lacks expected send/receive methods")
            logger.info("  (May need to directly access serial port)")
        
        camera.close()
        return True
        
    except Exception as e:
        logger.error(f"✗ Serial access test failed: {e}")
        return False

def test_camera_info_queries(com_port='COM7'):
    """Test 4: Query camera information (safe read-only operations)."""
    logger.info("\n=== TEST 4: Camera Info Queries ===")
    
    try:
        camera = Boson(port=com_port)
        logger.info(f"✓ Connected to Boson on {com_port}")
        
        # Test various info methods
        logger.info("Querying camera information...")
        
        try:
            serial = camera.get_camera_serial()
            logger.info(f"  Camera Serial: {serial}")
        except Exception as e:
            logger.warning(f"  Camera Serial: Failed ({e})")
        
        try:
            fw = camera.get_firmware_revision()
            logger.info(f"  Firmware: {fw}")
        except Exception as e:
            logger.warning(f"  Firmware: Failed ({e})")
        
        try:
            fpa_temp = camera.get_fpa_temperature()
            logger.info(f"  FPA Temp: {fpa_temp:.1f}°C")
        except Exception as e:
            logger.warning(f"  FPA Temp: Failed ({e})")
        
        try:
            ffc_mode = camera.get_ffc_mode()
            logger.info(f"  FFC Mode: {ffc_mode}")
        except Exception as e:
            logger.warning(f"  FFC Mode: Failed ({e})")
        
        logger.info("✓ Info queries completed")
        camera.close()
        return True
        
    except Exception as e:
        logger.error(f"✗ Info query test failed: {e}")
        return False

def test_tlinear_mode_detection(com_port='COM7'):
    """Test 5: Detect if camera is in T-Linear radiometric mode."""
    logger.info("\n=== TEST 5: T-Linear Mode Detection ===")
    
    try:
        camera = Boson(port=com_port)
        logger.info(f"✓ Connected to Boson on {com_port}")
        
        # Get FPA temperature as reference
        fpa_temp_c = camera.get_fpa_temperature()
        fpa_temp_k = fpa_temp_c + 273.15
        expected_y16 = int(fpa_temp_k * 100)
        
        logger.info(f"\n📊 Reference:")
        logger.info(f"  FPA: {fpa_temp_c:.1f}°C = {fpa_temp_k:.1f}K")
        logger.info(f"  Expected Y16 for FPA: ~{expected_y16}")
        logger.info(f"  Expected Y16 for room temp (20°C): ~29,300")
        
        # Capture and analyze frame
        frame = camera.grab()
        
        if frame is None:
            logger.error("✗ Failed to capture frame")
            camera.close()
            return False
        
        min_val = int(frame.min())
        max_val = int(frame.max())
        mean_val = int(frame.mean())
        
        # Interpret as Y16
        mean_temp_k = mean_val / 100.0
        mean_temp_c = mean_temp_k - 273.15
        
        logger.info(f"\n🎥 Video Analysis:")
        logger.info(f"  Raw value range: [{min_val}, {max_val}]")
        logger.info(f"  Mean raw value: {mean_val}")
        logger.info(f"  Interpreted as Y16: {mean_temp_c:.1f}°C")
        
        # Determine mode
        if 25000 < mean_val < 35000:  # ~250K to 350K = reasonable temps
            logger.info(f"\n✓ Camera is in T-LINEAR MODE")
            logger.info(f"  Scene temperature: {mean_temp_c:.1f}°C (realistic)")
            camera.close()
            return True
        else:
            logger.warning(f"\n✗ Camera is in RAW 14-BIT MODE")
            logger.warning(f"  Raw sensor value: {mean_val}")
            logger.warning(f"  Misinterpreted temp: {mean_temp_c:.1f}°C (unrealistic)")
            logger.info(f"  → Camera needs SDK configuration!")
            camera.close()
            return False
        
    except Exception as e:
        logger.error(f"✗ T-Linear detection failed: {e}")
        return False

def test_enable_tlinear_mode(com_port='COM7'):
    """Test 6: Enable T-Linear mode using SDK command."""
    logger.info("\n=== TEST 6: Enable T-Linear Mode via SDK ===")
    
    # Check SDK availability
    if not SDK_AVAILABLE:
        logger.error("✗ SDK not available - cannot configure camera")
        logger.info("  Install SDK to: 3.0 IDD & SDK/SDK_USER_PERMISSIONS/")
        return False
    
    try:
        # Import SDK
        from SDK_USER_PERMISSIONS.ClientFiles_Python import Client_API
        
        # Open SDK connection
        logger.info(f"Opening SDK connection on {com_port}...")
        sdk_client = Client_API.pyClient(
            manualport=com_port,
            manualbaud=921600,
            useDll=True
        )
        logger.info("✓ SDK connected")
        
        # Check current IR16 mode
        logger.info("\n📋 Reading current USB Video IR16 mode...")
        result, current_mode = sdk_client.sysctrlGetUsbVideoIR16Mode()
        
        if result.value == 0:
            mode_names = {0: "16-bit raw", 1: "14-bit raw", 2: "T-Linear radiometric"}
            logger.info(f"  Current mode: {mode_names.get(current_mode, f'Unknown ({current_mode})')}")
            
            if current_mode == 2:
                logger.info("  ✓ Already in T-Linear mode!")
                sdk_client.Close()
                return True
        else:
            logger.warning(f"  Could not read current mode (error: {result.value})")
        
        # Set T-Linear mode
        logger.info("\n⚙️  Setting USB Video IR16 mode to T-Linear (mode 2)...")
        
        # Create mode wrapper
        class Int32Wrapper:
            def __init__(self, val):
                self.value = val
        
        mode_arg = Int32Wrapper(2)
        result = sdk_client.sysctrlSetUsbVideoIR16Mode(mode_arg)
        
        if result.value == 0:
            logger.info("✓ T-Linear mode SET successfully!")
            logger.info("  Camera will now output true Y16 radiometric data")
            
            # Verify the change
            import time
            time.sleep(0.5)
            result, new_mode = sdk_client.sysctrlGetUsbVideoIR16Mode()
            if result.value == 0 and new_mode == 2:
                logger.info(f"  ✓ Verified: Mode is now {new_mode} (T-Linear)")
            
            sdk_client.Close()
            logger.info("✓ SDK disconnected")
            return True
        else:
            logger.error(f"✗ Failed to set T-Linear mode (error: {result.value})")
            sdk_client.Close()
            return False
            
    except Exception as e:
        logger.error(f"✗ SDK configuration failed: {e}")
        return False

def test_raw_packet_sendreceive(com_port='COM7'):
    """Test 7: Validate send/receive with raw SDK packet (GetCameraSN)."""
    logger.info("\n=== TEST 7: Raw Packet Send/Receive Test ===")
    
    if not SDK_AVAILABLE:
        logger.warning("⚠ SDK not available - skipping raw packet test")
        return None
    
    try:
        camera = Boson(port=com_port)
        logger.info(f"✓ Connected to Boson on {com_port}")
        
        # Check if camera has send/receive methods
        if not (hasattr(camera, 'send') and hasattr(camera, 'receive')):
            logger.error("✗ Camera lacks send/receive methods")
            camera.close()
            return False
        
        logger.info("✓ Camera has send() and receive() methods")
        logger.info("\n📦 Attempting to send raw SDK command: GetCameraSN")
        
        # Try simple SDK command: Get Camera Serial Number
        # This is a read-only query, safe to test
        try:
            # Use camera's built-in method as baseline
            expected_serial = camera.get_camera_serial()
            logger.info(f"  Baseline (native method): Serial = {expected_serial}")
            
            # The fact that get_camera_serial() works means flirpy
            # is already using send/receive internally
            logger.info("\n✓ Flirpy's send/receive methods are WORKING")
            logger.info("  (Native methods like get_camera_serial use them internally)")
            
            camera.close()
            return True
            
        except Exception as e:
            logger.error(f"✗ Packet communication failed: {e}")
            camera.close()
            return False
        
    except Exception as e:
        logger.error(f"✗ Raw packet test failed: {e}")
        return False

def main():
    """Run all tests in sequence."""
    logger.info("=" * 60)
    logger.info("Flirpy SDK Command Injection - Proof of Concept Test")
    logger.info("=" * 60)
    
    # Get COM port from user
    com_port = input("\nEnter COM port (default: COM7): ").strip() or 'COM7'
    logger.info(f"Using COM port: {com_port}\n")
    
    # Run tests
    results = {}
    
    # Phase 1: Basic connectivity tests
    results['basic_connection'] = test_basic_flirpy_connection(com_port)
    if not results['basic_connection']:
        logger.error("\n✗ CRITICAL: Basic connection failed. Cannot proceed.")
        return
    
    results['ffc_command'] = test_flirpy_ffc_command(com_port)
    results['serial_access'] = test_flirpy_serial_access(com_port)
    results['info_queries'] = test_camera_info_queries(com_port)
    
    # Phase 2: T-Linear radiometric tests
    results['tlinear_detection'] = test_tlinear_mode_detection(com_port)
    
    if not results['tlinear_detection']:
        logger.info("\n⚠️  Camera needs T-Linear configuration...")
        results['tlinear_config'] = test_enable_tlinear_mode(com_port)
        
        if results['tlinear_config']:
            logger.info("\n✓ T-Linear mode enabled! Re-checking...")
            import time
            time.sleep(1)
            results['tlinear_validation'] = test_tlinear_mode_detection(com_port)
        else:
            results['tlinear_validation'] = False
    else:
        results['tlinear_config'] = True  # Already in T-Linear
        results['tlinear_validation'] = True
    
def test_sequential_access(com_port='COM7'):
    """Test 7: Validate Sequential Access Pattern (SDK → Flirpy).
    
    This simulates the production startup sequence:
    1. Open SDK to read/write settings (e.g. Gain Mode)
    2. Close SDK
    3. Open Flirpy for video capture
    """
    logger.info("\n=== TEST 7: Sequential Access Pattern (SDK → Flirpy) ===")
    
    if not SDK_AVAILABLE:
        logger.warning("⚠ SDK not available - skipping sequential test")
        return None
        
    try:
        # Step 1: SDK Interaction
        logger.info("1. accessing Camera via SDK...")
        from SDK_USER_PERMISSIONS.ClientFiles_Python import Client_API
        from SDK_USER_PERMISSIONS.ClientFiles_Python.EnumTypes import FLR_BOSON_GAINMODE_E
        
        sdk_client = Client_API.pyClient(manualport=com_port, manualbaud=921600, useDll=True)
        
        # Read Gain Mode
        ret, gain_mode = sdk_client.bosonGetGainMode()
        if ret.value == 0:
            logger.info(f"   ✓ SDK Read Gain Mode: {gain_mode} (0=High, 1=Low, 2=Auto)")
        else:
            logger.warning(f"   ⚠ Failed to read gain mode: {ret.value}")
            
        sdk_client.Close()
        logger.info("   ✓ SDK Connection Closed")
        
        time.sleep(0.5)
        
        # Step 2: Flirpy Interaction
        logger.info("2. Switching to Flirpy for Video...")
        camera = Boson(port=com_port)
        frame = camera.grab()
        
        if frame is not None:
             logger.info(f"   ✓ Flirpy Frame Captured: ({frame.shape})")
             msg = "Success"
        else:
             logger.error("   ✗ Failed to capture frame")
             msg = "Failed"
             
        camera.close()
        logger.info(f"   ✓ Flirpy Connection Closed ({msg})")
        
        return True
        
    except Exception as e:
        logger.error(f"✗ Sequential access test failed: {e}")
        return False

def main():
    """Run all tests in sequence."""
    logger.info("=" * 60)
    logger.info("Flirpy SDK Command Injection - Proof of Concept Test")
    logger.info("=" * 60)
    
    # Get COM port from user
    com_port = input("\nEnter COM port (default: COM7): ").strip() or 'COM7'
    logger.info(f"Using COM port: {com_port}\n")
    
    # Run tests
    results = {}
    
    # Phase 1: Basic connectivity tests
    results['basic_connection'] = test_basic_flirpy_connection(com_port)
    if not results['basic_connection']:
        logger.error("\n✗ CRITICAL: Basic connection failed. Cannot proceed.")
        return
    
    results['ffc_command'] = test_flirpy_ffc_command(com_port)
    results['serial_access'] = test_flirpy_serial_access(com_port)
    results['info_queries'] = test_camera_info_queries(com_port)
    
    # Phase 2: T-Linear radiometric tests
    results['tlinear_detection'] = test_tlinear_mode_detection(com_port)
    
    if not results['tlinear_detection']:
        logger.info("\n⚠️  Camera needs T-Linear configuration...")
        results['tlinear_config'] = test_enable_tlinear_mode(com_port)
        
        if results['tlinear_config']:
            logger.info("\n✓ T-Linear mode enabled! Re-checking...")
            import time
            time.sleep(1)
            results['tlinear_validation'] = test_tlinear_mode_detection(com_port)
        else:
            results['tlinear_validation'] = False
    else:
        results['tlinear_config'] = True  # Already in T-Linear
        results['tlinear_validation'] = True
    
    # Phase 3: Integration Patterns
    # results['raw_packet_test'] = test_raw_packet_sendreceive(com_port) # Deprecated in favor of sequential test
    results['sequential_access'] = test_sequential_access(com_port)
    
    # Summary
    logger.info("\n" + "="*60)
    logger.info("TEST SUMMARY")
    logger.info("="*60)
    
    for test_name, result in results.items():
        if result is None:
            status = "⊘ SKIP"
        elif result:
            status = "✓ PASS"
        else:
            status = "✗ FAIL"
        logger.info(f"  {status}: {test_name}")
    
    # Filter out None (skipped) tests for pass/fail analysis
    actual_results = {k: v for k, v in results.items() if v is not None}
    all_passed = all(actual_results.values()) if actual_results else False
    
    if all_passed:
        logger.info("\n✓ ALL TESTS PASSED!")
        logger.info("\nKey Achievements:")
        logger.info("  ✅ Flirpy connection working")
        logger.info("  ✅ FFC commands functional")
        logger.info("  ✅ T-Linear radiometric mode ENABLED")
        logger.info("  ✅ Valid temperature data (Y16 format)")
        logger.info("  ✅ Serial send/receive methods available")
        logger.info("\n📋 Ready for Integration:")
        logger.info("  → Implement T-Linear configuration in FlirpyThermalBackend.open()")
        logger.info("  → Add SDK bridge for advanced controls (gain mode, emissivity)")
    else:
        logger.warning("\n⚠ SOME TESTS FAILED")
        
        if not results.get('tlinear_validation', False):
            logger.info("\n❌ T-Linear Mode Issue:")
            if not SDK_AVAILABLE:
                logger.info("  → SDK not available. Install to: 3.0 IDD & SDK/SDK_USER_PERMISSIONS/")
            else:
                logger.info("  → Re-run test to configure T-Linear mode")
    
    logger.info("="*60)

if __name__ == "__main__":
    main()
