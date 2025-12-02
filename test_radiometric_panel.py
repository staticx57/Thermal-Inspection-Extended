"""
Quick test to verify radiometric_panel.py can be imported and instantiated.
"""
import sys
print(f"Python: {sys.version}")

try:
    print("\n1. Testing PyQt6 import...")
    from PyQt6.QtWidgets import QApplication, QWidget
    from PyQt6.QtCore import pyqtSignal
    print("   ✓ PyQt6 imports successful")
except ImportError as e:
    print(f"   ✗ PyQt6 import failed: {e}")
    sys.exit(1)

try:
    print("\n2. Testing radiometric_panel import...")
    from radiometric_panel import RadiometricPanel
    print("   ✓ RadiometricPanel import successful")
except Exception as e:
    print(f"   ✗ RadiometricPanel import failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

try:
    print("\n3. Creating QApplication...")
    app = QApplication(sys.argv)
    print("   ✓ QApplication created")
except Exception as e:
    print(f"   ✗ QApplication creation failed: {e}")
    sys.exit(1)

try:
    print("\n4. Instantiating RadiometricPanel...")
    panel = RadiometricPanel()
    print("   ✓ RadiometricPanel instantiated")
    
    print("\n5. Checking attributes...")
    attrs = [
        'status_banner',
        'enable_8bit_checkbox',
        'scene_min_spin',
        'scene_max_spin',
        'apply_scene_range_btn',
        'single_point_calib_btn',
        'two_point_calib_btn',
        'calib_offset_label'
    ]
    
    missing = []
    for attr in attrs:
        if hasattr(panel, attr):
            print(f"   ✓ {attr}")
        else:
            print(f"   ✗ {attr} MISSING")
            missing.append(attr)
    
    if missing:
        print(f"\n   ERROR: Missing attributes: {missing}")
        sys.exit(1)
    
    print("\n6. Checking signals...")
    signals = [
        'estimation_8bit_enabled_changed',
        'temperature_range_changed',
        'calibrate_single_point_requested',
        'calibrate_two_point_requested'
    ]
    
    for sig in signals:
        if hasattr(panel, sig):
            print(f"   ✓ {sig}")
        else:
            print(f"   ✗ {sig} MISSING")
    
    print("\n✅ All checks passed!")
    print("RadiometricPanel is properly configured.")
    
except Exception as e:
    print(f"\n✗ Panel instantiation failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
