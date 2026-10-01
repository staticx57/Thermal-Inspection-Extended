@echo off
cd /d "%~dp0.."
REM Thermal Inspection Fusion Tool - Windows Installation Script
REM For Windows 10/11 x86-64 systems
REM
REM This script installs:
REM - Python dependencies (OpenCV, PyQt6, etc.)
REM - UVC webcam support (built-in to Windows)
REM - OPTIONAL: FLIR Firefly Spinnaker SDK (for RGB camera)
REM
REM Usage (run from repo root):
REM   scripts\install_windows.bat                       Install base system (UVC webcams)
REM   scripts\install_windows.bat --with-3d-mapping     Install base + Open3D/PyOpenGL for 3D Mapping
REM   scripts\install_windows.bat --with-firefly        Install base + FLIR Firefly support
REM   scripts\install_windows.bat --with-realsense-l515 Install base + build pyrealsense2 for L515
REM

setlocal enabledelayedexpansion

REM Colors for output (limited in CMD)
set "BLUE=[94m"
set "GREEN=[92m"
set "YELLOW=[93m"
set "RED=[91m"
set "NC=[0m"

echo %BLUE%============================================%NC%
echo %BLUE%Thermal Inspection Fusion Tool Installation%NC%
echo %BLUE%(see CHANGELOG.md for the release notes)%NC%
echo %BLUE%============================================%NC%
echo.

REM Check if Python is installed
call python --version >nul 2>&1
if errorlevel 1 (
    echo %RED%ERROR: Python not found!%NC%
    echo Please install Python 3.10+ from https://www.python.org/
    echo Make sure to check "Add Python to PATH" during installation
    pause
    exit /b 1
)

echo %GREEN%Python version:%NC%
call python --version

REM Python 3.10 or newer is required (3.10 - 3.12 are the tested versions)
call python -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
if errorlevel 1 (
    echo %RED%ERROR: Python 3.10 or newer is required.%NC%
    echo Please install a newer Python from https://www.python.org/
    pause
    exit /b 1
)
call python -c "import sys; sys.exit(1 if sys.version_info >= (3, 13) else 0)" >nul 2>&1
if errorlevel 1 (
    echo %YELLOW%NOTE: Python 3.13+ has not been tested with this project ^(3.10 - 3.12 have^).%NC%
    echo.
)
echo %YELLOW%If you plan to use a FLIR Firefly: the Spinnaker PySpin wheel must match your Python version.%NC%
echo.

REM Check if pip is available
call python -m pip --version >nul 2>&1
if errorlevel 1 (
    echo %RED%ERROR: pip not found!%NC%
    echo Please reinstall Python with pip enabled
    pause
    exit /b 1
)

REM Parse command-line arguments
set INSTALL_FIREFLY=false
set INSTALL_REALSENSE_L515=false
set INSTALL_3D=false
for %%A in (%*) do (
    if "%%A"=="--with-3d-mapping" set INSTALL_3D=true
    if "%%A"=="--with-firefly" set INSTALL_FIREFLY=true
    if "%%A"=="--with-realsense-l515" set INSTALL_REALSENSE_L515=true
)
if "%1"=="--help" (
    echo Usage: %0 [OPTIONS]
    echo.
    echo Options:
    echo   --with-firefly          Install FLIR Firefly Spinnaker SDK ^(optional^)
    echo   --with-realsense-l515   Build pyrealsense2 from source for an Intel
    echo                           RealSense L515 (pip's pyrealsense2 dropped
    echo                           L515 support upstream - see requirements.txt)
    echo   --with-3d-mapping       Install Open3D + PyOpenGL for the 3D Mapping view
    echo                           (needs a RealSense camera: D400 series via pip,
    echo                           or --with-realsense-l515 for an L515)
    echo   --help                  Show this help message
    echo.
    exit /b 0
)

REM Step 1: Upgrade pip
echo %BLUE%[1/7] Upgrading pip...%NC%
call python -m pip install --upgrade pip

REM Step 2: Install core dependencies from requirements.txt
echo %BLUE%[2/7] Installing core dependencies...%NC%
if exist requirements.txt (
    echo %GREEN%Found requirements.txt - installing...%NC%
    call python -m pip install -r requirements.txt
) else (
    echo %YELLOW%requirements.txt not found. Installing core packages manually...%NC%
    call python -m pip install opencv-python numpy scipy Pillow PyQt6 "pyqtgraph>=0.14" psutil pyserial flirpy "setuptools<81"
)

REM Step 3: Verify PyQt6
echo %BLUE%[3/7] Verifying PyQt6 installation...%NC%
call python -c "from PyQt6.QtWidgets import QApplication; print('PyQt6 OK')" 2>nul
if errorlevel 1 (
    echo %RED%PyQt6 installation failed%NC%
    echo %YELLOW%Attempting to reinstall...%NC%
    call python -m pip install --upgrade PyQt6
) else (
    echo %GREEN%PyQt6 installed successfully%NC%
)

REM Step 4: OPTIONAL - Install FLIR Firefly Spinnaker SDK
if "%INSTALL_FIREFLY%"=="true" (
    echo %BLUE%[4/7] Installing FLIR Firefly Spinnaker SDK...%NC%
    echo.
    echo %YELLOW%========================================%NC%
    echo %YELLOW%FLIR Spinnaker SDK Installation%NC%
    echo %YELLOW%========================================%NC%
    echo.
    echo %YELLOW%IMPORTANT: Manual Spinnaker SDK installation required%NC%
    echo.
    echo %BLUE%RECOMMENDED: Use a Python 3.10 virtual environment%NC%
    echo   PySpin compatibility is best on Python 3.10 - install it from
    echo   https://www.python.org/ and create a venv before continuing.
    echo.
    echo %BLUE%Quick Guide:%NC%
    echo   1. Download SDK: https://www.flir.com/products/spinnaker-sdk/
    echo   2. Run installer: SpinnakerSDK_FULL_x.x.x_x64.exe
    echo   3. Choose "Full Installation" (includes PySpin)
    echo   4. Install PySpin wheel from SDK folder
    echo.
    echo %YELLOW%Press any key when Spinnaker SDK installation is complete...%NC%
    pause >nul

    REM Verify PySpin installation
    call python -c "import PySpin; print('PySpin version:', PySpin.__version__)" 2>nul
    if errorlevel 1 (
        echo %RED%ERROR: PySpin not detected!%NC%
        echo.
        echo %YELLOW%Troubleshooting:%NC%
        echo   1. Make sure you installed "Full Installation" of Spinnaker SDK
        echo   2. Check if PySpin wheel is in Spinnaker installation folder
        echo   3. Manually install: pip install spinnaker_python-X.X.X-py3-none-win_amd64.whl
        echo   4. Restart command prompt and try again
        echo.
        echo %YELLOW%You can still use UVC webcams without PySpin.%NC%
    ) else (
        echo %GREEN%SUCCESS: PySpin installed!%NC%
        echo %GREEN%FLIR Firefly cameras are now supported.%NC%
    )
) else (
    echo %BLUE%[4/7] Skipping FLIR Firefly support (use --with-firefly to enable)%NC%
)

REM Step 5: OPTIONAL - Build pyrealsense2 from source for L515 support
if "%INSTALL_REALSENSE_L515%"=="true" (
    echo %BLUE%[5/7] Building pyrealsense2 from source for Intel RealSense L515...%NC%
    echo.
    echo %YELLOW%========================================%NC%
    echo %YELLOW%Intel RealSense L515 Support%NC%
    echo %YELLOW%========================================%NC%
    echo.
    echo %YELLOW%pip's pyrealsense2 dropped L515 support upstream in v2.55+ - the%NC%
    echo %YELLOW%only working path is building it from source. This needs git, CMake,%NC%
    echo %YELLOW%and a Visual Studio install with the C++ ATL component. Can take%NC%
    echo %YELLOW%10-30+ minutes. See requirements.txt for details.%NC%
    echo.
    echo %YELLOW%D400-series cameras (D415/D435/D455/etc.) do NOT need this - use the%NC%
    echo %YELLOW%plain pyrealsense2 pip pin in requirements.txt instead.%NC%
    echo.

    powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install_realsense_l515.ps1"
    if errorlevel 1 (
        echo.
        echo %RED%ERROR: pyrealsense2 build failed - see errors above.%NC%
        echo %YELLOW%You can retry directly with more control:%NC%
        echo   powershell -File scripts\install_realsense_l515.ps1 -Clean
        echo.
        echo %YELLOW%You can still use the app without RealSense support.%NC%
    ) else (
        echo %GREEN%SUCCESS: pyrealsense2 built and installed for L515!%NC%
    )
) else (
    echo %BLUE%[5/7] Skipping RealSense L515 build (use --with-realsense-l515 to enable)%NC%
)

REM Step 6: OPTIONAL - 3D Mapping packages
if "%INSTALL_3D%"=="true" (
    echo %BLUE%[6/7] Installing 3D Mapping packages ^(Open3D, PyOpenGL^)...%NC%
    call python -m pip install "open3d>=0.18.0" "PyOpenGL>=3.1.0" "PyOpenGL_accelerate>=3.1.0"
    if errorlevel 1 (
        echo %YELLOW%Some 3D Mapping packages failed to install - the 3D Mapping view will show a placeholder.%NC%
        echo %YELLOW%^(PyOpenGL_accelerate needs a C compiler and is optional: pip install "open3d>=0.18.0" PyOpenGL^)%NC%
    )
) else (
    echo %BLUE%[6/7] Skipping 3D Mapping packages ^(use --with-3d-mapping to enable^)%NC%
)

REM Step 7: Verify installation
echo %BLUE%[7/7] Verifying installation...%NC%
echo.

echo %BLUE%Testing Python modules...%NC%
call python -c "import numpy; print('  ✓ NumPy')" 2>nul || echo   ✗ NumPy - FAILED
call python -c "import cv2; print('  ✓ OpenCV')" 2>nul || echo   ✗ OpenCV - FAILED
call python -c "import PyQt6.QtWidgets; print('  ✓ PyQt6')" 2>nul || echo   ✗ PyQt6 - FAILED
call python -c "import serial; print('  ✓ PySerial')" 2>nul || echo   ✗ PySerial - FAILED
call python -c "import pyqtgraph; print('  ✓ pyqtgraph', pyqtgraph.__version__)" 2>nul || echo   ✗ pyqtgraph - FAILED
call python -c "import scipy; print('  ✓ SciPy')" 2>nul || echo   ✗ SciPy - FAILED
call python -c "import flirpy; print('  ✓ flirpy (Boson)')" 2>nul || echo   ✗ flirpy - FAILED
if "%INSTALL_3D%"=="true" (
    call python -c "import open3d; print('  ✓ Open3D', open3d.__version__)" 2>nul || echo   ✗ Open3D - FAILED
    call python -c "import OpenGL; print('  ✓ PyOpenGL')" 2>nul || echo   ✗ PyOpenGL - FAILED
)
call python -c "import psutil; print('  ✓ psutil')" 2>nul || echo   ✗ psutil - FAILED
if "%INSTALL_REALSENSE_L515%"=="true" (
    call python -c "import pyrealsense2; print('  ✓ pyrealsense2 (L515 build)')" 2>nul || echo   ✗ pyrealsense2 - FAILED
)

echo.
echo %BLUE%Checking project files...%NC%
if exist thermal_inspection\app.py (echo   ✓ thermal_inspection\app.py) else echo   ✗ thermal_inspection\app.py - MISSING
if exist thermal_inspection\gui\main_window.py (echo   ✓ thermal_inspection\gui\main_window.py) else echo   ✗ thermal_inspection\gui\main_window.py - MISSING
if exist thermal_inspection\cameras\flir_camera.py (echo   ✓ thermal_inspection\cameras\flir_camera.py) else echo   ✗ thermal_inspection\cameras\flir_camera.py - MISSING
if exist thermal_inspection\processing\fusion_processor.py (echo   ✓ thermal_inspection\processing\fusion_processor.py) else echo   ✗ thermal_inspection\processing\fusion_processor.py - MISSING
if exist thermal_inspection\processing\palette_manager.py (echo   ✓ thermal_inspection\processing\palette_manager.py) else echo   ✗ thermal_inspection\processing\palette_manager.py - MISSING
if exist thermal_inspection\processing\thermal_analyzer.py (echo   ✓ thermal_inspection\processing\thermal_analyzer.py) else echo   ✗ thermal_inspection\processing\thermal_analyzer.py - MISSING
if exist thermal_inspection\processing\roi_manager.py (echo   ✓ thermal_inspection\processing\roi_manager.py) else echo   ✗ thermal_inspection\processing\roi_manager.py - MISSING
if exist thermal_inspection\sdk\boson_sdk_wrapper.py (echo   ✓ thermal_inspection\sdk\boson_sdk_wrapper.py) else echo   ✗ thermal_inspection\sdk\boson_sdk_wrapper.py - MISSING
if exist config.json (echo   ✓ config.json) else echo   - config.json will be created on first run

echo.
echo %GREEN%============================================%NC%
echo %GREEN%Installation Complete!%NC%
echo %GREEN%============================================%NC%
echo.
echo %BLUE%System Status:%NC%
echo   ✓ Python 3 ^& dependencies
echo   ✓ OpenCV (computer vision)
echo   ✓ PyQt6 (GUI framework)
echo   ✓ PySerial (Boson SDK communication)
echo   ✓ UVC camera support (built-in)
if "%INSTALL_FIREFLY%"=="true" (
    echo   ✓ FLIR Firefly support (check above for status)
) else (
    echo   ⚠ FLIR Firefly support: Not installed (use --with-firefly)
)
if "%INSTALL_REALSENSE_L515%"=="true" (
    echo   ✓ Intel RealSense L515 support (check above for status)
) else (
    echo   ⚠ Intel RealSense L515 support: Not installed (use --with-realsense-l515)
    echo     ^(D400-series RealSense cameras just need the plain pip pin in requirements.txt^)
)
echo.
echo %BLUE%Key Features:%NC%
echo   • Thermal/RGB fusion modes, 100+ thermal palettes
echo   • ROI Manager (live stats, alerts, history) and spot meters
echo   • Temperature analysis (isotherms, gradients, anomalies, radiometric units)
echo   • FLIR Boson / Tau 2 / Lepton thermal cameras, UVC / Firefly / GigE / RealSense RGB
echo   • 3D Fusion and 3D Mapping with RealSense depth (optional)
echo   • Media recording (video, snapshots, metadata)
echo.
echo %BLUE%Boson SDK Requirements:%NC%
echo   • FLIR Boson thermal camera connected via USB
echo   • COM port driver (included with Boson SDK)
echo   • Serial communication enabled
echo.
echo %BLUE%Next Steps:%NC%
echo   1. Connect FLIR Boson thermal camera
echo   2. (Optional) Connect RGB camera (webcam or FLIR Firefly)
echo   3. Configure COM port with --boson-com-port (default: COM7)
echo   4. Run system: python -m thermal_inspection
echo   5. Enable Boson SDK: python -m thermal_inspection --enable-boson-sdk
echo   6. Troubleshooting: python -m thermal_inspection --log-level DEBUG --log-file debug.log
echo   Or use a quick-launch script in scripts\ (see LAUNCHER_GUIDE.md)
echo.
echo %BLUE%Documentation:%NC%
echo   • Quick start: README.md
echo   • Launcher guide: LAUNCHER_GUIDE.md
echo   • Full changelog: CHANGELOG.md
echo.
echo %YELLOW%Press any key to exit...%NC%
pause >nul
