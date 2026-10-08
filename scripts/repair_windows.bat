@echo off
cd /d "%~dp0.."
REM Thermal Inspection Fusion Tool - Windows Repair/Update Script
REM Brings existing installation up to date with latest requirements
REM
REM Usage: repair_windows.bat
REM

setlocal enabledelayedexpansion

REM Colors
set "BLUE=[94m"
set "GREEN=[92m"
set "YELLOW=[93m"
set "RED=[91m"
set "NC=[0m"

echo %BLUE%============================================%NC%
echo %BLUE%Thermal Inspection Fusion Tool Repair%NC%
echo %BLUE%(see CHANGELOG.md for the release notes)%NC%
echo %BLUE%============================================%NC%
echo.

REM Check if we're in the right directory
if not exist thermal_inspection\app.py (
    echo %RED%Error: thermal_inspection\app.py not found%NC%
    echo %YELLOW%Please run this script from the Thermal-Inspection repo root%NC%
    pause
    exit /b 1
)

echo %GREEN%Project directory found%NC%
echo.

REM Check Python
call python --version >nul 2>&1
if errorlevel 1 (
    echo %RED%ERROR: Python not found!%NC%
    echo Please install Python 3.10+ from https://www.python.org/
    pause
    exit /b 1
)

echo %GREEN%Python version:%NC%
call python --version
echo.

REM Step 1: Update pip
echo %BLUE%[1/5] Updating pip...%NC%
call python -m pip install --upgrade pip

REM Step 2: Install/update PyQt6
echo %BLUE%[2/5] Installing/updating PyQt6...%NC%
call python -m pip install --upgrade PyQt6

REM Verify PyQt6
call python -c "from PyQt6.QtWidgets import QApplication; print('OK PyQt6 verified')" 2>nul
if errorlevel 1 (
    echo %RED%PyQt6 installation failed%NC%
    echo %YELLOW%Please check your Python installation%NC%
) else (
    echo %GREEN%PyQt6 verified%NC%
)

REM Step 3: Update requirements
echo %BLUE%[3/5] Updating project dependencies...%NC%
if exist requirements.txt (
    echo %GREEN%Found requirements.txt - updating...%NC%
    call python -m pip install --upgrade -r requirements.txt
) else (
    echo %YELLOW%requirements.txt not found. Updating core packages...%NC%
    call python -m pip install --upgrade numpy scipy opencv-python Pillow PyQt6 "pyqtgraph>=0.14" psutil pyserial flirpy "setuptools<81"
)

REM Step 4: Forget the saved camera scan. A scan that ran while a camera was held by another (or a frozen) copy of
REM the app can save a short device list that the app then trusts on every start, so a camera never reappears.
echo %BLUE%[4/5] Forgetting the saved camera scan (rebuilt on the next start)...%NC%
echo %YELLOW%      If a frozen copy of the app is holding a camera, end python.exe in Task Manager first.%NC%
call python -m thermal_inspection --reset-camera-cache
echo.

REM Step 5: Verify installation
echo %BLUE%[5/5] Verifying repaired installation...%NC%
echo.

echo %BLUE%Testing Python modules...%NC%
call python -c "import numpy; print('  ✓ NumPy')" 2>nul || echo   ✗ NumPy - FAILED
call python -c "import cv2; print('  ✓ OpenCV')" 2>nul || echo   ✗ OpenCV - FAILED
call python -c "import PyQt6.QtWidgets; print('  ✓ PyQt6')" 2>nul || echo   ✗ PyQt6 - FAILED
call python -c "import serial; print('  ✓ PySerial')" 2>nul || echo   ✗ PySerial - FAILED
call python -c "import pyqtgraph; print('  ✓ pyqtgraph', pyqtgraph.__version__)" 2>nul || echo   ✗ pyqtgraph - FAILED
call python -c "import scipy; print('  ✓ SciPy')" 2>nul || echo   ✗ SciPy - FAILED
call python -c "import flirpy; print('  ✓ flirpy (Boson)')" 2>nul || echo   ✗ flirpy - FAILED
call python -c "import psutil; print('  ✓ psutil')" 2>nul || echo   ✗ psutil - FAILED
call python -c "import pygrabber, comtypes; print('  ✓ pygrabber + comtypes (Windows camera list)')" 2>nul || echo   ✗ pygrabber / comtypes - FAILED ^(camera names will be missing^)
call python -c "import libusb_package; print('  ✓ libusb-package (optional: Tau 2 USB probe tool)')" 2>nul || echo   - libusb-package not installed ^(optional^)

echo.
echo %BLUE%Checking project files...%NC%
if exist thermal_inspection\app.py (echo   ✓ thermal_inspection\app.py) else echo   ✗ thermal_inspection\app.py - MISSING
if exist thermal_inspection\gui\main_window.py (echo   ✓ thermal_inspection\gui\main_window.py) else echo   ✗ thermal_inspection\gui\main_window.py - MISSING
if exist thermal_inspection\cameras\flir_camera.py (echo   ✓ thermal_inspection\cameras\flir_camera.py) else echo   ✗ thermal_inspection\cameras\flir_camera.py - MISSING
if exist thermal_inspection\processing\fusion_processor.py (echo   ✓ thermal_inspection\processing\fusion_processor.py) else echo   ✗ thermal_inspection\processing\fusion_processor.py - MISSING
if exist thermal_inspection\processing\palette_manager.py (echo   ✓ thermal_inspection\processing\palette_manager.py) else echo   ✗ thermal_inspection\processing\palette_manager.py - MISSING
if exist thermal_inspection\sdk\boson_sdk_wrapper.py (echo   ✓ thermal_inspection\sdk\boson_sdk_wrapper.py) else echo   ✗ thermal_inspection\sdk\boson_sdk_wrapper.py - MISSING
if exist config.json (echo   ✓ config.json) else echo   - config.json will be created on first run

echo.
echo %GREEN%============================================%NC%
echo %GREEN%Repair Complete ^& Verified!%NC%
echo %GREEN%============================================%NC%
echo.
echo %BLUE%What you have:%NC%
echo   • PyQt6 GUI with a camera plugin architecture
echo   • Thermal/RGB fusion modes, 100+ thermal palettes
echo   • ROI Manager and spot meters, temperature analysis
echo   • Optional 3D Fusion / 3D Mapping ^(RealSense; see requirements.txt^)
echo   • Media recording ^(video + snapshots^)
echo.
echo %GREEN%Ready to run:%NC%
echo   python -m thermal_inspection
echo   python -m thermal_inspection --enable-boson-sdk
echo   Cameras missing after a crash: python -m thermal_inspection --reset-camera-cache
echo   Troubleshooting: python -m thermal_inspection --log-level DEBUG --log-file debug.log
echo   Or use the quick-launch scripts in scripts\ (see LAUNCHER_GUIDE.md)
echo.
echo %YELLOW%Press any key to exit...%NC%
pause >nul
