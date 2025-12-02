#!/usr/bin/env python3
"""
Setup script to create a test environment with OpenCV 4.6.0 for Y16 testing.

This creates a virtual environment with OpenCV 4.6.0 (the version confirmed
working by FLIR forum users) to test if the OpenCV version is the issue,
independent of Windows version.

Usage:
    python setup_opencv_4.6.0_test.py
"""

import subprocess
import sys
import os
from pathlib import Path

def run_command(cmd, description):
    """Run a command and print status."""
    print(f"\n{'='*70}")
    print(f"{description}")
    print(f"{'='*70}")
    print(f"Command: {' '.join(cmd)}")
    print()

    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print(result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr)
        print(f"✓ SUCCESS: {description}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"✗ FAILED: {description}")
        print(f"Error: {e}")
        if e.stdout:
            print("STDOUT:", e.stdout)
        if e.stderr:
            print("STDERR:", e.stderr)
        return False
    except FileNotFoundError:
        print(f"✗ FAILED: Command not found")
        print(f"Make sure Python is in your PATH")
        return False


def main():
    print("="*70)
    print("OpenCV 4.6.0 Test Environment Setup")
    print("="*70)
    print()
    print("This will create a virtual environment with OpenCV 4.6.0")
    print("to test if OpenCV version is the issue for Y16 capture.")
    print()
    print(f"Current Python: {sys.version}")
    print(f"Current OpenCV: (to be replaced with 4.6.0)")
    print()

    # Ask for confirmation
    response = input("Continue? (y/n): ").lower().strip()
    if response != 'y':
        print("Aborted.")
        return

    # Setup paths
    project_dir = Path(__file__).parent
    venv_dir = project_dir / "venv_opencv460"

    print(f"\nVirtual environment will be created at: {venv_dir}")

    # Check if venv already exists
    if venv_dir.exists():
        print(f"\n⚠ WARNING: Virtual environment already exists at {venv_dir}")
        response = input("Delete and recreate? (y/n): ").lower().strip()
        if response == 'y':
            print("Deleting existing venv...")
            import shutil
            shutil.rmtree(venv_dir)
        else:
            print("Using existing venv...")

    # Step 1: Create virtual environment
    if not venv_dir.exists():
        if not run_command(
            [sys.executable, "-m", "venv", str(venv_dir)],
            "Creating virtual environment"
        ):
            print("\n✗ Failed to create virtual environment")
            return

    # Determine activation script
    if sys.platform == "win32":
        python_exe = venv_dir / "Scripts" / "python.exe"
        pip_exe = venv_dir / "Scripts" / "pip.exe"
        activate_script = venv_dir / "Scripts" / "activate.bat"
    else:
        python_exe = venv_dir / "bin" / "python"
        pip_exe = venv_dir / "bin" / "pip"
        activate_script = venv_dir / "bin" / "activate"

    # Step 2: Upgrade pip
    if not run_command(
        [str(python_exe), "-m", "pip", "install", "--upgrade", "pip"],
        "Upgrading pip"
    ):
        print("\n⚠ Warning: Failed to upgrade pip (continuing anyway)")

    # Step 3: Install OpenCV 4.6.0
    print("\n" + "="*70)
    print("Installing OpenCV 4.6.0.66")
    print("="*70)
    print("This is the version confirmed working by FLIR forum users")
    print()

    if not run_command(
        [str(pip_exe), "install", "opencv-python==4.6.0.66"],
        "Installing OpenCV 4.6.0.66"
    ):
        print("\n✗ Failed to install OpenCV 4.6.0")
        return

    # Step 4: Install other dependencies
    dependencies = [
        "pyserial",
        "numpy",
    ]

    for dep in dependencies:
        if not run_command(
            [str(pip_exe), "install", dep],
            f"Installing {dep}"
        ):
            print(f"\n⚠ Warning: Failed to install {dep} (continuing anyway)")

    # Step 5: Verify installation
    print("\n" + "="*70)
    print("Verifying Installation")
    print("="*70)

    verify_script = """
import sys
import cv2
import numpy as np

print(f"Python version: {sys.version}")
print(f"OpenCV version: {cv2.__version__}")
print(f"NumPy version: {np.__version__}")

# Verify it's the correct version
if cv2.__version__.startswith("4.6.0"):
    print("\\n✓ SUCCESS: OpenCV 4.6.0 is installed correctly!")
else:
    print(f"\\n✗ WARNING: Expected 4.6.0, got {cv2.__version__}")
"""

    result = subprocess.run(
        [str(python_exe), "-c", verify_script],
        capture_output=True,
        text=True
    )
    print(result.stdout)
    if result.stderr:
        print("STDERR:", result.stderr)

    # Step 6: Copy test script to venv directory
    print("\n" + "="*70)
    print("Copying Test Scripts")
    print("="*70)

    test_scripts = [
        "test_convert_rgb_order.py",
        "test_flir_official_method.py",
    ]

    for script in test_scripts:
        src = project_dir / script
        dst = venv_dir / script
        if src.exists():
            import shutil
            shutil.copy2(src, dst)
            print(f"✓ Copied {script} to venv directory")
        else:
            print(f"⚠ Warning: {script} not found")

    # Final instructions
    print("\n" + "="*70)
    print("SETUP COMPLETE!")
    print("="*70)
    print()
    print("Next steps:")
    print()
    print("1. Activate the virtual environment:")
    if sys.platform == "win32":
        print(f"   {venv_dir}\\Scripts\\activate")
    else:
        print(f"   source {venv_dir}/bin/activate")
    print()
    print("2. Verify OpenCV version:")
    print("   python -c \"import cv2; print(cv2.__version__)\"")
    print("   Should show: 4.6.0")
    print()
    print("3. Run the Y16 test:")
    print("   python test_convert_rgb_order.py")
    print()
    print("4. If successful, check results!")
    print()
    print("To deactivate later:")
    print("   deactivate")
    print()
    print("="*70)
    print()
    print("IMPORTANT: This tests if OpenCV version is the issue.")
    print("If 4.6.0 works, you can:")
    print("  - Use this venv for thermal camera work")
    print("  - Downgrade main environment to 4.6.0")
    print("  - Wait for OpenCV to fix the regression")
    print()


if __name__ == "__main__":
    main()
