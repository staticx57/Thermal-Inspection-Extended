#!/usr/bin/env python3
"""
Test if flirpy camera is outputting true T-Linear Y16 or raw 14-bit data.

This validates whether the camera is properly configured for radiometric output.
"""

import logging
from flirpy.camera.boson import Boson

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def test_y16_validity(com_port='COM7'):
    """Test if camera is in proper T-Linear mode."""
    logger.info("=== Y16 T-Linear Validation Test ===\n")
    
    try:
        camera = Boson(port=com_port)
        logger.info(f"✓ Connected to Boson on {com_port}")
        
        # Get FPA temperature as reference
        fpa_temp_c = camera.get_fpa_temperature()
        fpa_temp_k = fpa_temp_c + 273.15
        expected_y16_fpa = int(fpa_temp_k * 100)
        
        logger.info(f"\n📊 Reference Temperatures:")
        logger.info(f"  FPA Temperature: {fpa_temp_c:.1f}°C = {fpa_temp_k:.1f}K")
        logger.info(f"  Expected Y16 value for FPA: ~{expected_y16_fpa}")
        logger.info(f"  Expected Y16 for room temp (20°C): ~29300")
        
        # Capture frames and analyze
        logger.info(f"\n🎥 Analyzing frame data:")
        frames_data = []
        for i in range(5):
            frame = camera.grab()
            if frame is not None:
                min_val = int(frame.min())
                max_val = int(frame.max())
                mean_val = int(frame.mean())
                
                # Convert to temperature assuming Y16
                min_temp_k = min_val / 100.0
                max_temp_k = max_val / 100.0
                mean_temp_k = mean_val / 100.0
                
                min_temp_c = min_temp_k - 273.15
                max_temp_c = max_temp_k - 273.15
                mean_temp_c = mean_temp_k - 273.15
                
                logger.info(f"\n  Frame {i+1}:")
                logger.info(f"    Raw values: [{min_val}, {max_val}], mean={mean_val}")
                logger.info(f"    As Y16 temps: [{min_temp_c:.1f}°C, {max_temp_c:.1f}°C], mean={mean_temp_c:.1f}°C")
                
                frames_data.append({
                    'min': min_val,
                    'max': max_val,
                    'mean': mean_val,
                    'min_temp_c': min_temp_c,
                    'max_temp_c': max_temp_c,
                    'mean_temp_c': mean_temp_c
                })
        
        # Analyze results
        logger.info(f"\n" + "="*60)
        logger.info("ANALYSIS:")
        logger.info("="*60)
        
        avg_mean = sum(f['mean'] for f in frames_data) / len(frames_data)
        avg_temp_c = avg_mean / 100.0 - 273.15
        
        # Check if temperatures are reasonable
        if -50 < avg_temp_c < 100:
            logger.info(f"✓ VALID Y16 T-Linear data")
            logger.info(f"  Average scene temperature: {avg_temp_c:.1f}°C")
            logger.info(f"  Camera is properly configured for radiometric output")
            return True
        else:
            logger.warning(f"✗ INVALID - Raw 14-bit sensor data")
            logger.warning(f"  Interpreted temperature: {avg_temp_c:.1f}°C (unrealistic)")
            logger.warning(f"  Average raw value: {int(avg_mean)}")
            logger.info(f"\n📋 DIAGNOSIS:")
            logger.info(f"  Camera is NOT in T-Linear mode")
            logger.info(f"  SDK command needed: sysctrlSetUsbVideoIR16Mode(2)")
            logger.info(f"  This sets USB output to 'T-Linear radiometric' mode")
            return False
        
        camera.close()
        
    except Exception as e:
        logger.error(f"Test failed: {e}")
        return False

if __name__ == "__main__":
    com_port = input("Enter COM port (default: COM7): ").strip() or 'COM7'
    test_y16_validity(com_port)
