import sys
import os

# Add current directory to path
sys.path.append(os.getcwd())

try:
    from main import ThermalRoadMonitorFusion
    print("Successfully imported ThermalRoadMonitorFusion")
    
    print("Checking for _on_camera_connected...")
    if hasattr(ThermalRoadMonitorFusion, '_on_camera_connected'):
        print("FOUND: _on_camera_connected")
    else:
        print("MISSING: _on_camera_connected")
        
    print("Checking for _on_camera_disconnected...")
    if hasattr(ThermalRoadMonitorFusion, '_on_camera_disconnected'):
        print("FOUND: _on_camera_disconnected")
    else:
        print("MISSING: _on_camera_disconnected")
        
    print("\nAll attributes:")
    for attr in dir(ThermalRoadMonitorFusion):
        if 'camera' in attr:
            print(f" - {attr}")
            
except Exception as e:
    print(f"Error importing: {e}")
