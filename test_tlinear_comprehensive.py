#!/usr/bin/env python3
"""
Comprehensive Flirpy T-Linear Test & Configuration Script

This script:
1. Tests current camera mode (14-bit raw vs 16-bit T-Linear)
2. Attempts to enable T-Linear mode via SDK commands
3. Validates radiometric output
4. Tests video capture stability

Purpose: Diagnose and fix the root cause of Bug #1 (missing SDK control)
"""

import sys
import os
import time
import logging
import struct

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

# Import flirpy
try:
    from flirpy.camera.boson import Boson
    FLIRPY_AVAILABLE = True
except ImportError:
    logger.error("✗ flirpy not installed")
    sys.exit(1)

# Import SDK for T-Linear configuration
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
        from SDK_USER_PERMISSIONS.ClientFiles_Python import Client_API
        from SDK_USER_PERMISSIONS.ClientFiles_Python.EnumTypes import FLR_BOSON_GAINMODE_E
        SDK_AVAILABLE = True
        logger.info("✓ Boson SDK found")
    except ImportError as e:
        logger.warning(f"⚠ SDK import failed: {e}")


class TLinearTest:
    """Comprehensive test for T-Linear mode configuration."""
    
    def __init__(self, com_port='COM7'):
        self.com_port = com_port
        self.camera = None
        self.sdk_client = None
        
    def connect(self):
        """Connect to camera."""
        logger.info(f"Connecting to Boson on {self.com_port}...")
        self.camera = Boson(port=self.com_port)
        logger.info("✓ Connected via flirpy")
        
    def disconnect(self):
        """Disconnect from camera."""
        if self.camera:
            self.camera.close()
            self.camera = None
        if self.sdk_client:
            self.sdk_client.Close()
            self.sdk_client = None
        
    def test_current_mode(self):
        """Test 1: Check if camera is in T-Linear mode."""
        logger.info("\n" + "="*60)
        logger.info("TEST 1: Current Video Mode Detection")
        logger.info("="*60)
        
        # Get FPA temperature as reference
        fpa_temp_c = self.camera.get_fpa_temperature()
        fpa_temp_k = fpa_temp_c + 273.15
        expected_y16 = int(fpa_temp_k * 100)
        
        logger.info(f"\n📊 Reference:")
        logger.info(f"  FPA: {fpa_temp_c:.1f}°C = {fpa_temp_k:.1f}K")
        logger.info(f"  Expected Y16 for FPA: ~{expected_y16}")
        logger.info(f"  Expected Y16 for room temp (20°C): ~29,300")
        
        # Capture and analyze frames
        logger.info(f"\n🎥 Analyzing video frames:")
        frame = self.camera.grab()
        
        if frame is None:
            logger.error("✗ Failed to capture frame")
            return False
        
        min_val = int(frame.min())
        max_val = int(frame.max())
        mean_val = int(frame.mean())
        
        # Interpret as Y16
        mean_temp_k = mean_val / 100.0
        mean_temp_c = mean_temp_k - 273.15
        
        logger.info(f"  Raw value range: [{min_val}, {max_val}]")
        logger.info(f"  Mean raw value: {mean_val}")
        logger.info(f"  Interpreted as Y16: {mean_temp_c:.1f}°C")
        
        # Determine mode
        if 25000 < mean_val < 35000:  # ~250K to 350K = reasonable temps
            logger.info(f"\n✓ Camera is in T-LINEAR MODE")
            logger.info(f"  Scene temperature: {mean_temp_c:.1f}°C (realistic)")
            return True
        else:
            logger.warning(f"\n✗ Camera is in RAW 14-BIT MODE")
            logger.warning(f"  Raw sensor value: {mean_val}")
            logger.warning(f"  Misinterpreted temp: {mean_temp_c:.1f}°C (unrealistic)")
            logger.info(f"\n  Camera needs SDK configuration!")
            return False
    
    def enable_tlinear_via_sdk(self):
        """Test 2: Enable T-Linear mode using SDK command."""
        logger.info("\n" + "="*60)
        logger.info("TEST 2: Enable T-Linear Mode via SDK")
        logger.info("="*60)
        
        if not SDK_AVAILABLE:
            logger.error("✗ SDK not available - cannot configure camera")
            logger.info("  Install SDK to: 3.0 IDD & SDK/SDK_USER_PERMISSIONS/")
            return False
        
        try:
            # Close flirpy connection temporarily
            logger.info("Closing flirpy connection...")
            self.camera.close()
            time.sleep(1)
            
            # Open SDK connection
            logger.info(f"Opening SDK connection on {self.com_port}...")
            self.sdk_client = Client_API.pyClient(
                manualport=self.com_port,
                manualbaud=921600,
                useDll=True
            )
            logger.info("✓ SDK connected")
            
            # Check current IR16 mode
            logger.info("\n📋 Reading current USB Video IR16 mode...")
            result, current_mode = self.sdk_client.sysctrlGetUsbVideoIR16Mode()
            
            if result.value == 0:
                mode_names = {0: "16-bit raw", 1: "14-bit raw", 2: "T-Linear radiometric"}
                logger.info(f"  Current mode: {mode_names.get(current_mode, f'Unknown ({current_mode})')}")
                
                if current_mode == 2:
                    logger.info("  ✓ Already in T-Linear mode!")
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
            result = self.sdk_client.sysctrlSetUsbVideoIR16Mode(mode_arg)
            
            if result.value == 0:
                logger.info("✓ T-Linear mode SET successfully!")
                logger.info("  Camera will now output true Y16 radiometric data")
                
                # Verify the change
                time.sleep(0.5)
                result, new_mode = self.sdk_client.sysctrlGetUsbVideoIR16Mode()
                if result.value == 0 and new_mode == 2:
                    logger.info(f"  ✓ Verified: Mode is now {new_mode} (T-Linear)")
                return True
            else:
                logger.error(f"✗ Failed to set T-Linear mode (error: {result.value})")
                return False
                
        except Exception as e:
            logger.error(f"✗ SDK configuration failed: {e}")
            return False
        finally:
            # Close SDK and reopen flirpy
            if self.sdk_client:
                logger.info("\nClosing SDK connection...")
                self.sdk_client.Close()
                self.sdk_client = None
            
            time.sleep(1)
            logger.info("Reopening flirpy connection...")
            self.camera = Boson(port=self.com_port)
            logger.info("✓ Flirpy reconnected")
    
    def validate_tlinear_output(self):
        """Test 3: Validate T-Linear radiometric output."""
        logger.info("\n" + "="*60)
        logger.info("TEST 3: Validate T-Linear Output")
        logger.info("="*60)
        
        # Get reference temp
        fpa_temp_c = self.camera.get_fpa_temperature()
        logger.info(f"\n📊 Reference FPA: {fpa_temp_c:.1f}°C")
        
        # Capture multiple frames
        logger.info(f"\n🎥 Capturing 5 frames for validation:")
        temps = []
        
        for i in range(5):
            frame = self.camera.grab()
            if frame is None:
                logger.error(f"  Frame {i+1}: Failed")
                return False
            
            mean_val = int(frame.mean())
            temp_k = mean_val / 100.0
            temp_c = temp_k - 273.15
            temps.append(temp_c)
            
            logger.info(f"  Frame {i+1}: mean={mean_val} → {temp_c:.1f}°C")
            time.sleep(0.05)
        
        # Analyze
        avg_temp = sum(temps) / len(temps)
        logger.info(f"\n📈 Average scene temperature: {avg_temp:.1f}°C")
        
        if 0 < avg_temp < 50:  # Reasonable indoor temp
            logger.info("✓ VALID T-Linear radiometric data!")
            logger.info("  Temperature readings are realistic")
            return True
        else:
            logger.warning(f"✗ Temperature {avg_temp:.1f}°C seems unrealistic")
            logger.warning("  T-Linear mode may not be active")
            return False
    
    def test_video_stability(self):
        """Test 4: Ensure video capture is stable after SDK config."""
        logger.info("\n" + "="*60)
        logger.info("TEST 4: Video Capture Stability")
        logger.info("="*60)
        
        logger.info("\n🎥 Capturing 20 frames to test stability...")
        success_count = 0
        
        for i in range(20):
            frame = self.camera.grab()
            if frame is not None:
                success_count += 1
            else:
                logger.warning(f"  Frame {i+1}: FAILED")
            time.sleep(0.05)
        
        logger.info(f"\n✓ Captured {success_count}/20 frames successfully")
        
        if success_count >= 19:  # Allow 1 dropped frame
            logger.info("✓ Video capture is STABLE")
            return True
        else:
            logger.error("✗ Video capture is UNSTABLE")
            return False
    
    def run_all_tests(self):
        """Run complete test suite."""
        logger.info("="*60)
        logger.info("COMPREHENSIVE T-LINEAR TEST & CONFIGURATION")
        logger.info("="*60)
        
        results = {}
        
        try:
            # Connect
            self.connect()
            
            # Test 1: Check current mode
            is_tlinear = self.test_current_mode()
            results['current_mode'] = is_tlinear
            
            # Test 2: Enable T-Linear if needed
            if not is_tlinear:
                logger.info("\n⚠️  Camera needs T-Linear configuration...")
                tlinear_set = self.enable_tlinear_via_sdk()
                results['tlinear_config'] = tlinear_set
                
                if not tlinear_set:
                    logger.error("\n✗ Cannot configure T-Linear mode")
                    logger.info("   Remaining tests will show raw data")
            else:
                results['tlinear_config'] = True
            
            # Test 3: Validate output
            valid = self.validate_tlinear_output()
            results['validation'] = valid
            
            # Test 4: Stability
            stable = self.test_video_stability()
            results['stability'] = stable
            
        except Exception as e:
            logger.error(f"Test suite error: {e}", exc_info=True)
        finally:
            self.disconnect()
        
        # Summary
        logger.info("\n" + "="*60)
        logger.info("TEST SUMMARY")
        logger.info("="*60)
        
        for test_name, result in results.items():
            status = "✓ PASS" if result else "✗ FAIL"
            logger.info(f"  {status}: {test_name}")
        
        all_passed = all(results.values())
        
        if all_passed:
            logger.info("\n✓ ALL TESTS PASSED!")
            logger.info("\nCamera is properly configured for radiometric imaging:")
            logger.info("  • T-Linear mode ENABLED")
            logger.info("  • Valid Y16 temperature data")
            logger.info("  • Stable video capture")
        else:
            logger.warning("\n⚠ SOME TESTS FAILED")
            if not results.get('tlinear_config', False):
                logger.info("\n📋 ACTION REQUIRED:")
                logger.info("  1. Ensure Boson SDK is installed")
                logger.info("  2. Close all applications using the camera")
                logger.info("  3. Re-run this script")
        
        logger.info("="*60)


def main():
    com_port = input("Enter COM port (default: COM7): ").strip() or 'COM7'
    
    test = TLinearTest(com_port)
    test.run_all_tests()


if __name__ == "__main__":
    main()
