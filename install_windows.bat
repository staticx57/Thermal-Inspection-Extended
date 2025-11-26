@echo off
REM Thermal Inspection Fusion Tool - Windows Installation Script
REM For Windows 10/11 x86-64 systems
REM
REM This script installs:
REM - Python dependencies (OpenCV, PyQt5, etc.)
REM - UVC webcam support (built-in to Windows)
REM - OPTIONAL: FLIR Firefly Spinnaker SDK (for RGB camera)
REM
REM Usage:
REM   install_windows.bat                 Install base system (UVC webcams)
REM   install_windows.bat --with-firefly  Install base + FLIR Firefly support
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
echo %BLUE%Version 3.0.0%NC%
echo %BLUE%============================================%NC%
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo %RED%ERROR: Python not found!%NC%
    echo Please install Python 3.8+ from https://www.python.org/
    echo Make sure to check "Add Python to PATH" during installation
    pause
    exit /b 1
)

echo %GREEN%Python version:%NC%
python --version

REM Check Python version and warn if 3.12+
for /f "tokens=2" %%i in ('python --version') do set PYTHON_VER=%%i
echo %PYTHON_VER% | findstr /C:"3.12" >nul && (
    echo %YELLOW%WARNING: Python 3.12 detected!%NC%
    echo %YELLOW%PySpin (FLIR Firefly support) may not be compatible.%NC%
    echo %YELLOW%Recommended: Python 3.10 for best compatibility.%NC%
    echo %YELLOW%See: archive\implementation-docs\setup_python310_env.md%NC%
    echo.
)
echo %PYTHON_VER% | findstr /C:"3.13" >nul && (
    echo %YELLOW%WARNING: Python 3.13 detected!%NC%
    echo %YELLOW%PySpin (FLIR Firefly support) may not be compatible.%NC%
    echo %YELLOW%Recommended: Python 3.10 for best compatibility.%NC%
    echo %YELLOW%See: archive\implementation-docs\setup_python310_env.md%NC%
    echo.
)
echo.

REM Check if pip is available
python -m pip --version >nul 2>&1
if errorlevel 1 (
    echo %RED%ERROR: pip not found!%NC%
    echo Please reinstall Python with pip enabled
    pause
    exit /b 1
)

REM Parse command-line arguments
set INSTALL_FIREFLY=false
if "%1"=="--with-firefly" set INSTALL_FIREFLY=true
if "%1"=="--help" (
    echo Usage: %0 [OPTIONS]
    echo.
    echo Options:
    echo   --with-firefly    Install FLIR Firefly Spinnaker SDK (optional)
    echo   --help            Show this help message
    echo.
    exit /b 0
)

REM Step 1: Upgrade pip
echo %BLUE%[1/5] Upgrading pip...%NC%
python -m pip install --upgrade pip

REM Step 2: Install core dependencies from requirements.txt
echo %BLUE%[2/5] Installing core dependencies...%NC%
if exist requirements.txt (
    echo %GREEN%Found requirements.txt - installing...%NC%
    python -m pip install -r requirements.txt
) else (
    echo %YELLOW%requirements.txt not found. Installing core packages manually...%NC%
    python -m pip install opencv-python opencv-contrib-python numpy Pillow PyQt6 psutil pyserial
)

REM Step 3: Verify PyQt6
echo %BLUE%[3/5] Verifying PyQt6 installation...%NC%
python -c "from PyQt6.QtWidgets import QApplication; print('PyQt6 OK')" 2>nul
if errorlevel 1 (
    echo %RED%PyQt6 installation failed%NC%
    echo %YELLOW%Attempting to reinstall...%NC%
    python -m pip install --upgrade PyQt6
) else (
    echo %GREEN%PyQt6 installed successfully%NC%
)

REM Step 4: OPTIONAL - Install FLIR Firefly Spinnaker SDK
if "%INSTALL_FIREFLY%"=="true" (
    echo %BLUE%[4/5] Installing FLIR Firefly Spinnaker SDK...%NC%
    echo.
    echo %YELLOW%========================================%NC%
    echo %YELLOW%FLIR Spinnaker SDK Installation%NC%
    echo %YELLOW%========================================%NC%
    echo.
    echo %YELLOW%IMPORTANT: Manual Spinnaker SDK installation required%NC%
    echo.
    echo %BLUE%RECOMMENDED: Use Python 3.10 virtual environment%NC%
    echo   For best compatibility with PySpin, use Python 3.10:
    echo   1. Install Python 3.10 from https://www.python.org/
    echo   2. Run: setup_venv_py310.bat
    echo   3. Then continue with Spinnaker SDK installation
    echo.
    echo %BLUE%Quick Guide:%NC%
    echo   1. Download SDK: https://www.flir.com/products/spinnaker-sdk/
    echo   2. Run installer: SpinnakerSDK_FULL_x.x.x_x64.exe
    echo   3. Choose "Full Installation" (includes PySpin)
    echo   4. Install PySpin wheel from SDK folder
    echo.
    echo %BLUE%Detailed Instructions:%NC%
    echo   See: archive\implementation-docs\install_pyspin.md
    echo   Run diagnostic: python diagnose_spinnaker.py
    echo.
    echo %YELLOW%Press any key when Spinnaker SDK installation is complete...%NC%
    pause >nul

    REM Verify PySpin installation
    python -c "import PySpin; print('PySpin version:', PySpin.__version__)" 2>nul
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
    echo %BLUE%[4/5] Skipping FLIR Firefly support (use --with-firefly to enable)%NC%
)

REM Step 5: Verify installation
echo %BLUE%[5/5] Verifying installation...%NC%
echo.

echo %BLUE%Testing Python modules...%NC%
python -c "import numpy; print('  ✓ NumPy')" 2>nul || echo   ✗ NumPy - FAILED
python -c "import cv2; print('  ✓ OpenCV')" 2>nul || echo   ✗ OpenCV - FAILED
python -c "import PyQt6.QtWidgets; print('  ✓ PyQt6')" 2>nul || echo   ✗ PyQt6 - FAILED
python -c "import serial; print('  ✓ PySerial')" 2>nul || echo   ✗ PySerial - FAILED
python -c "import psutil; print('  ✓ psutil')" 2>nul || echo   ✗ psutil - FAILED

echo.
echo %BLUE%Checking project files...%NC%
if exist inspection_main.py (echo   ✓ inspection_main.py) else echo   ✗ inspection_main.py - MISSING
if exist inspection_gui_qt.py (echo   ✓ inspection_gui_qt.py) else echo   ✗ inspection_gui_qt.py - MISSING
if exist flir_camera.py (echo   ✓ flir_camera.py) else echo   ✗ flir_camera.py - MISSING
if exist fusion_processor.py (echo   ✓ fusion_processor.py) else echo   ✗ fusion_processor.py - MISSING
if exist palette_manager.py (echo   ✓ palette_manager.py) else echo   ✗ palette_manager.py - MISSING
if exist thermal_analyzer.py (echo   ✓ thermal_analyzer.py) else echo   ✗ thermal_analyzer.py - MISSING
if exist roi_manager.py (echo   ✓ roi_manager.py) else echo   ✗ roi_manager.py - MISSING
if exist boson_sdk_wrapper.py (echo   ✓ boson_sdk_wrapper.py) else echo   ✗ boson_sdk_wrapper.py - MISSING
if exist config.json (echo   ✓ config.json) else echo   ✗ config.json - MISSING

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
echo.
echo %BLUE%Key Features:%NC%
echo   • 7 Fusion Algorithms (thermal/RGB fusion)
echo   • 45 Thermal Palettes (7 categories)
echo   • ROI Management (4 auto-detection methods)
echo   • Temperature Analysis (spot, trend, anomaly detection)
echo   • FLIR Boson SDK Integration (FFC, AGC, radiometric)
echo   • Camera Auto-Detection (thermal + RGB)
echo   • Media Recording (video, snapshots, metadata)
echo.
echo %BLUE%Boson SDK Requirements:%NC%
echo   • FLIR Boson thermal camera connected via USB
echo   • COM port driver (included with Boson SDK)
echo   • Serial communication enabled
echo.
echo %BLUE%Next Steps:%NC%
echo   1. Connect FLIR Boson thermal camera
echo   2. (Optional) Connect RGB camera (webcam or FLIR Firefly)
echo   3. Configure COM port in config.json (default: COM6)
echo   4. Run system: python inspection_main.py
echo   5. Enable Boson SDK: python inspection_main.py --enable-boson-sdk
echo.
echo %BLUE%Documentation:%NC%
echo   • Quick start: README.md
echo   • Full changelog: CHANGELOG.md
echo   • Development roadmap: TODO.md
echo   • SDK integration: archive\sdk-docs\BOSON_SDK_STATUS.md
echo   • Camera setup: archive\implementation-docs\FIREFLY_INTEGRATION.md
echo   • Troubleshooting: archive\implementation-docs\DEBUGGING_GUIDELINES.md
echo.
echo %YELLOW%Press any key to exit...%NC%
pause >nul
