"""
Spinnaker SDK & PySpin Diagnostic Tool
Checks for common installation issues and provides troubleshooting steps
"""
import sys
import os
import platform
import subprocess

def print_section(title):
    """Print formatted section header"""
    print("\n" + "="*70)
    print(f"  {title}")
    print("="*70)

def check_python_version():
    """Check Python version compatibility"""
    print_section("Python Version Check")
    version = sys.version_info
    print(f"Python version: {version.major}.{version.minor}.{version.micro}")
    print(f"Python executable: {sys.executable}")

    if version.major == 3 and version.minor >= 7:
        print("✓ Python version is compatible with PySpin")
    else:
        print("✗ Warning: PySpin typically requires Python 3.7+")

    return True

def check_pyspin_import():
    """Try to import PySpin and report detailed error"""
    print_section("PySpin Import Test")

    try:
        import PySpin
        print("✓ PySpin imported successfully!")
        print(f"  PySpin version: {PySpin.System.GetInstance().GetLibraryVersion()}")

        # Get library version details
        lib_version = PySpin.System.GetInstance().GetLibraryVersion()
        print(f"  Major: {lib_version.major}")
        print(f"  Minor: {lib_version.minor}")
        print(f"  Type: {lib_version.type}")
        print(f"  Build: {lib_version.build}")

        # Release system
        PySpin.System.GetInstance().ReleaseInstance()

        return True

    except ImportError as e:
        print("✗ Failed to import PySpin")
        print(f"  Error: {e}")
        print("\nPossible causes:")
        print("  1. PySpin is not installed")
        print("  2. Spinnaker SDK is not installed")
        print("  3. PySpin wheel doesn't match Python version")
        print("  4. Environment PATH issues")
        return False
    except Exception as e:
        print(f"✗ Error loading PySpin: {e}")
        return False

def check_spinnaker_installation():
    """Check if Spinnaker SDK is installed on the system"""
    print_section("Spinnaker SDK Installation Check")

    system = platform.system()

    if system == "Windows":
        # Check common Windows installation paths
        possible_paths = [
            "C:\\Program Files\\FLIR Systems\\Spinnaker",
            "C:\\Program Files (x86)\\FLIR Systems\\Spinnaker",
            os.path.expandvars("%PROGRAMFILES%\\FLIR Systems\\Spinnaker"),
        ]

        found = False
        for path in possible_paths:
            if os.path.exists(path):
                print(f"✓ Found Spinnaker SDK at: {path}")
                found = True

                # Check for PySpin wheel files
                pyspin_path = os.path.join(path, "bin64", "vs2015")
                if os.path.exists(pyspin_path):
                    print(f"  Checking for PySpin wheels in: {pyspin_path}")
                    wheels = [f for f in os.listdir(pyspin_path) if f.endswith('.whl')]
                    if wheels:
                        print(f"  Found {len(wheels)} PySpin wheel(s):")
                        for wheel in wheels:
                            print(f"    - {wheel}")
                    else:
                        print("  ⚠ No .whl files found")
                break

        if not found:
            print("✗ Spinnaker SDK not found in standard locations")
            print("\nInstallation instructions:")
            print("  1. Download from: https://www.flir.com/products/spinnaker-sdk/")
            print("  2. Run SpinnakerSDK_FULL_x.x.x.xx_x64.exe")
            print("  3. Choose 'Full Installation' (includes PySpin)")

    elif system == "Linux":
        # Check for Spinnaker libs
        try:
            result = subprocess.run(['ldconfig', '-p'], capture_output=True, text=True)
            if 'libSpinnaker.so' in result.stdout:
                print("✓ Found libSpinnaker.so in library path")
                found = True
            else:
                print("✗ libSpinnaker.so not found in library path")
                found = False
        except:
            print("⚠ Could not check library path")
            found = False

        if not found:
            print("\nInstallation instructions:")
            print("  1. Download from: https://www.flir.com/products/spinnaker-sdk/")
            print("  2. Extract: tar -xzf spinnaker-x.x.x.xx-amd64-pkg.tar.gz")
            print("  3. Run: sudo sh install_spinnaker.sh")

    else:  # macOS
        print("macOS detected - checking for Spinnaker framework...")
        framework_path = "/Library/Frameworks/Spinnaker.framework"
        if os.path.exists(framework_path):
            print(f"✓ Found Spinnaker framework at: {framework_path}")
        else:
            print("✗ Spinnaker framework not found")
            print("\nInstallation instructions:")
            print("  1. Download from: https://www.flir.com/products/spinnaker-sdk/")
            print("  2. Run the .dmg installer")

def check_pip_packages():
    """Check for PySpin in pip packages"""
    print_section("Pip Package Check")

    try:
        result = subprocess.run([sys.executable, '-m', 'pip', 'list'],
                              capture_output=True, text=True)

        # Look for PySpin-related packages
        pyspin_packages = [line for line in result.stdout.split('\n')
                          if 'pyspin' in line.lower() or 'spinnaker' in line.lower()]

        if pyspin_packages:
            print("✓ Found PySpin-related packages:")
            for pkg in pyspin_packages:
                print(f"  {pkg}")
        else:
            print("✗ No PySpin packages found in pip")
            print("\nTo install PySpin:")

            system = platform.system()
            if system == "Windows":
                print("  1. Navigate to Spinnaker SDK installation folder:")
                print("     C:\\Program Files\\FLIR Systems\\Spinnaker\\bin64\\vs2015\\")
                print("  2. Find the .whl file matching your Python version")
                print(f"     (You're using Python {sys.version_info.major}.{sys.version_info.minor})")
                print("  3. Install with: pip install spinnaker_python-X.X.X-cpXX-cpXX-win_amd64.whl")
            elif system == "Linux":
                print("  After installing Spinnaker SDK:")
                print("  1. Find the .whl file in the SDK folder")
                print("  2. Install with: pip install spinnaker_python-*.whl")
            else:
                print("  After installing Spinnaker SDK:")
                print("  pip install spinnaker-python")

    except Exception as e:
        print(f"⚠ Could not check pip packages: {e}")

def check_environment():
    """Check environment variables"""
    print_section("Environment Variables Check")

    system = platform.system()

    if system == "Windows":
        # Check PATH for Spinnaker
        path = os.environ.get('PATH', '')
        if 'spinnaker' in path.lower():
            print("✓ Spinnaker found in PATH")
        else:
            print("⚠ Spinnaker not found in PATH (may be okay)")

        # Check GENICAM_GENTL64_PATH
        gentl = os.environ.get('GENICAM_GENTL64_PATH')
        if gentl:
            print(f"✓ GENICAM_GENTL64_PATH set: {gentl}")
        else:
            print("⚠ GENICAM_GENTL64_PATH not set (should be set by Spinnaker installer)")

    elif system == "Linux":
        # Check LD_LIBRARY_PATH
        ld_path = os.environ.get('LD_LIBRARY_PATH', '')
        if 'spinnaker' in ld_path.lower():
            print("✓ Spinnaker found in LD_LIBRARY_PATH")
        else:
            print("⚠ Spinnaker not found in LD_LIBRARY_PATH")
            print("  You may need to add: export LD_LIBRARY_PATH=/opt/spinnaker/lib:$LD_LIBRARY_PATH")

def test_camera_detection():
    """Try to detect FLIR cameras"""
    print_section("Camera Detection Test")

    try:
        import PySpin

        # Get system instance
        system = PySpin.System.GetInstance()

        # Get camera list
        cam_list = system.GetCameras()
        num_cameras = cam_list.GetSize()

        print(f"Number of FLIR cameras detected: {num_cameras}")

        if num_cameras == 0:
            print("\n✗ No FLIR cameras detected!")
            print("\nTroubleshooting:")
            print("  1. Check USB connection (use USB 3.0 port)")
            print("  2. Check Device Manager (Windows) or lsusb (Linux)")
            print("  3. Try unplugging and replugging the camera")
            print("  4. On Linux, check udev rules:")
            print("     sudo sh -c 'echo \"SUBSYSTEM==\\\"usb\\\", ATTRS{idVendor}==\\\"1e10\\\", MODE=\\\"0666\\\"\" > /etc/udev/rules.d/40-flir-spinnaker.rules'")
            print("     sudo udevadm control --reload-rules")
        else:
            print("\n✓ Camera(s) detected!")
            for i in range(num_cameras):
                cam = cam_list[i]

                # Get device info
                nodemap_tldevice = cam.GetTLDeviceNodeMap()

                # Get model
                node_model = PySpin.CStringPtr(nodemap_tldevice.GetNode('DeviceModelName'))
                if PySpin.IsAvailable(node_model) and PySpin.IsReadable(node_model):
                    model = node_model.GetValue()
                else:
                    model = "Unknown"

                # Get serial
                node_serial = PySpin.CStringPtr(nodemap_tldevice.GetNode('DeviceSerialNumber'))
                if PySpin.IsAvailable(node_serial) and PySpin.IsReadable(node_serial):
                    serial = node_serial.GetValue()
                else:
                    serial = "Unknown"

                print(f"\nCamera {i}:")
                print(f"  Model: {model}")
                print(f"  Serial: {serial}")

        # Cleanup
        cam_list.Clear()
        system.ReleaseInstance()

        return num_cameras > 0

    except ImportError:
        print("✗ Cannot test - PySpin not available")
        return False
    except Exception as e:
        print(f"✗ Error during camera detection: {e}")
        return False

def check_system_info():
    """Display system information"""
    print_section("System Information")
    print(f"OS: {platform.system()} {platform.release()}")
    print(f"Machine: {platform.machine()}")
    print(f"Processor: {platform.processor()}")
    print(f"Python: {sys.version}")

def main():
    """Run all diagnostic checks"""
    print("\n" + "="*70)
    print("  SPINNAKER SDK & PYSPIN DIAGNOSTIC TOOL")
    print("  For FLIR Firefly Camera Support")
    print("="*70)

    # Run checks
    check_system_info()
    check_python_version()
    pyspin_available = check_pyspin_import()
    check_spinnaker_installation()
    check_pip_packages()
    check_environment()

    if pyspin_available:
        cameras_found = test_camera_detection()
    else:
        cameras_found = False

    # Summary
    print_section("SUMMARY")

    if pyspin_available and cameras_found:
        print("✓ SUCCESS: PySpin is working and cameras are detected!")
        print("\nYour FLIR Firefly camera should work with the application.")
        print("Run main.py to start the Thermal Fusion Driving Assist application.")
    elif pyspin_available and not cameras_found:
        print("⚠ PARTIAL: PySpin is installed but no cameras detected")
        print("\nPossible issues:")
        print("  1. Camera not connected")
        print("  2. USB driver issues")
        print("  3. Camera permissions (Linux)")
        print("\nTry:")
        print("  - Check USB connection")
        print("  - Use USB 3.0 port")
        print("  - Run with administrator/sudo privileges")
    else:
        print("✗ FAILED: PySpin is not available")
        print("\nNext steps:")
        print("  1. Install Spinnaker SDK from:")
        print("     https://www.flir.com/products/spinnaker-sdk/")
        print("  2. Install PySpin (usually included with SDK)")
        print("  3. Re-run this diagnostic")

    print("\n" + "="*70)
    print("\nFor more help, see:")
    print("  - CROSS_PLATFORM.md in this repository")
    print("  - FLIR Spinnaker SDK documentation")
    print("="*70 + "\n")

if __name__ == "__main__":
    main()
