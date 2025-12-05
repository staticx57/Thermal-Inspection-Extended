"""
Diagnostic script to test anomaly detection with 8-bit vs 16-bit data.
This tests hot/cold spot detection to isolate the 16-bit issue.
"""

import numpy as np
import cv2
from thermal_analyzer import ThermalAnalyzer

def create_test_frame_8bit():
    """Create 8-bit test frame with a hot spot."""
    # Base frame: 200x200, gray background
    frame = np.ones((200, 200), dtype=np.uint8) * 100
    
    # Add hot spot: center 40x40 pixels, value 220
    frame[80:120, 80:120] = 220
    
    return frame

def create_test_frame_16bit():
    """Create 16-bit test frame with a hot spot (Y16 format)."""
    # Base frame: 200x200, ~23°C (296.15K = 29615 raw value)
    frame = np.ones((200, 200), dtype=np.uint16) * 29615
    
    # Add hot spot: center 40x40 pixels, ~35°C (308.15K = 30815 raw value)
    frame[80:120, 80:120] = 30815
    
    return frame

def test_detection(frame, name, is_radiometric=False):
    """Test hot spot detection on a frame."""
    print(f"\n{'='*60}")
    print(f"Testing: {name}")
    print(f"{'='*60}")
    print(f"Frame dtype: {frame.dtype}")
    print(f"Frame shape: {frame.shape}")
    print(f"Frame min: {frame.min()}, max: {frame.max()}, mean: {frame.mean():.1f}")
    print(f"Frame median: {np.median(frame):.1f}")
    
    # Create analyzer
    analyzer = ThermalAnalyzer({
        'hot_spot_threshold': 0.95,  # 95th percentile
        'hot_spot_min_area': 100,    # Minimum 100 pixels
        'cold_spot_threshold': 0.05,  # 5th percentile
        'cold_spot_min_area': 100
    })
    analyzer.set_radiometric_mode(is_radiometric)
    
    # Calculate what the threshold should be
    threshold =np.percentile(frame, 95)
    print(f"95th percentile threshold: {threshold:.1f}")
    
    # Detect hot spots
    hot_spots = analyzer.detect_hot_spots(frame)
    
    print(f"\n--- Detection Results ---")
    print(f"Hot spots found: {len(hot_spots)}")
    
    for i, hs in enumerate(hot_spots):
        print(f"\nHot Spot {i+1}:")
        print(f"  Centroid: {hs.centroid}")
        print(f"  BBox: {hs.bbox}")
        print(f"  Max temp: {hs.max_temp:.2f}")
        print(f"  Mean temp: {hs.mean_temp:.2f}")
        print(f"  Area: {hs.area}")
        print(f"  Confidence: {hs.confidence:.3f}")
        print(f"  Raw value: {hs.raw_value:.1f}")
        
        # Calculate what confidence SHOULD be
        max_raw = hs.raw_value
        expected_conf = min(1.0, (max_raw - threshold) / (threshold * 0.5))
        print(f"  Expected confidence: {expected_conf:.3f}")
        print(f"  Numerator: {max_raw - threshold:.1f}")
        print(f"  Denominator: {threshold * 0.5:.1f}")
    
    return hot_spots

def main():
    """Run diagnostic tests."""
    print("="*60)
    print("ANOMALY DETECTION DIAGNOSTIC TEST")
    print("Testing 8-bit vs 16-bit hot spot detection")
    print("="*60)
    
    # Test 8-bit
    frame_8bit = create_test_frame_8bit()
    hot_spots_8bit = test_detection(frame_8bit, "8-bit AGC", is_radiometric=False)
    
    # Test 16-bit
    frame_16bit = create_test_frame_16bit()
    hot_spots_16bit = test_detection(frame_16bit, "16-bit Y16 Radiometric", is_radiometric=True)
    
    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    print(f"8-bit detections: {len(hot_spots_8bit)}")
    print(f"16-bit detections: {len(hot_spots_16bit)}")
    
    if len(hot_spots_8bit) > 0 and len(hot_spots_16bit) == 0:
        print("\n❌ ISSUE CONFIRMED: 16-bit detection is broken!")
        print("   Likely cause: Confidence calculation is scale-dependent")
    elif len(hot_spots_8bit) > 0 and len(hot_spots_16bit) > 0:
        print("\n✓ Both modes detected hot spots")
        print(f"  8-bit confidence: {hot_spots_8bit[0].confidence:.3f}")
        print(f"  16-bit confidence: {hot_spots_16bit[0].confidence:.3f}")
    else:
        print("\n⚠ Neither mode detected hot spots (check test data)")

if __name__ == "__main__":
    main()
