from roi_manager import ROIManager, ROIType, ROISource

def verify_scaling():
    print("=== Verifying Drift-Free ROI Scaling ===")
    
    # 1. Initialize with UVC resolution
    initial_res = (640, 512)
    manager = ROIManager({'resolution': initial_res})
    print(f"Initialized with resolution: {initial_res}")
    
    # 2. Create ROI at specific coordinates
    # Using prime numbers to test rounding
    orig_points = [(100, 100), (200, 200)] 
    roi = manager.create_manual_roi(ROIType.RECTANGLE, orig_points, label="Test ROI")
    print(f"Created ROI: {roi.points}")
    print(f"Normalized: {roi.normalized_points}")
    
    assert roi.points == orig_points, "Initial points match failed"
    
    # 3. Switch to Low Res (Flirpy/Thermal)
    low_res = (320, 256)
    print(f"\n--- Switching to {low_res} ---")
    manager.scale_rois(low_res)
    print(f"Scaled ROI: {roi.points}")
    
    expected_low = [(50, 50), (100, 100)]
    assert roi.points == expected_low, f"Downscale failed. Expected {expected_low}, got {roi.points}"
    
    # 4. Switch back to High Res (UVC)
    print(f"\n--- Switching back to {initial_res} ---")
    manager.scale_rois(initial_res)
    print(f"Restored ROI: {roi.points}")
    
    assert roi.points == orig_points, f"Round-trip failed! Drift detected. Expected {orig_points}, got {roi.points}"
    print("[PASS] Exact Round-Trip Preserved")
    
    # 5. Odd resolution test (Stress Test)
    odd_res = (321, 257)
    print(f"\n--- Switching to Odd Res {odd_res} ---")
    manager.scale_rois(odd_res)
    print(f"Odd Res ROI: {roi.points}")
    
    # 6. Back to High Res again
    print(f"\n--- Switching back to {initial_res} ---")
    manager.scale_rois(initial_res)
    print(f"Restored ROI (2nd time): {roi.points}")
    
    assert roi.points == orig_points, f"Odd-resolution Round-trip failed! Expected {orig_points}, got {roi.points}"
    print("[PASS] Odd-Resolution Round-Trip Preserved")

if __name__ == "__main__":
    try:
        verify_scaling()
        print("\n✅ VERIFICATION SUCCESSFUL")
    except AssertionError as e:
        print(f"\n❌ VERIFICATION FAILED: {e}")
        exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        exit(1)
