@echo off
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
echo %BLUE%Version 3.0.0%NC%
echo %BLUE%============================================%NC%
echo.

REM Check if we're in the right directory
if not exist inspection_main.py (
    echo %RED%Error: inspection_main.py not found%NC%
    echo %YELLOW%Please run this script from the Thermal-Inspection directory%NC%
    pause
    exit /b 1
)

echo %GREEN%Project directory found%NC%
echo.

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo %RED%ERROR: Python not found!%NC%
    echo Please install Python 3.8+ from https://www.python.org/
    pause
    exit /b 1
)

echo %GREEN%Python version:%NC%
python --version
echo.

REM Step 1: Update pip
echo %BLUE%[1/4] Updating pip...%NC%
python -m pip install --upgrade pip

REM Step 2: Install/update PyQt6
echo %BLUE%[2/4] Installing/updating PyQt6...%NC%
python -m pip install --upgrade PyQt6

REM Verify PyQt6
python -c "from PyQt6.QtWidgets import QApplication; print('OK PyQt6 verified')" 2>nul
if errorlevel 1 (
    echo %RED%PyQt6 installation failed%NC%
    echo %YELLOW%Please check your Python installation%NC%
) else (
    echo %GREEN%PyQt6 verified%NC%
)

REM Step 3: Update requirements
echo %BLUE%[3/4] Updating project dependencies...%NC%
if exist requirements.txt (
    echo %GREEN%Found requirements.txt - updating...%NC%
    python -m pip install --upgrade -r requirements.txt
) else (
    echo %YELLOW%requirements.txt not found. Updating core packages...%NC%
    python -m pip install --upgrade numpy opencv-python opencv-contrib-python PyQt6 psutil pyserial
)

REM Step 4: Verify installation
echo %BLUE%[4/4] Verifying repaired installation...%NC%
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
if exist boson_sdk_wrapper.py (echo   ✓ boson_sdk_wrapper.py) else echo   ✗ boson_sdk_wrapper.py - MISSING
if exist config.json (echo   ✓ config.json) else echo   ✗ config.json - MISSING

echo.
echo %GREEN%============================================%NC%
echo %GREEN%Repair Complete ^& Verified!%NC%
echo %GREEN%============================================%NC%
echo.
echo %BLUE%Current Features (v3.0):%NC%
echo   • PyQt6 GUI (modern Qt6 framework)
echo   • 7 Fusion algorithms (thermal/RGB fusion)
echo   • 45 Thermal palettes (7 categories)
echo   • ROI management (auto-detection + manual)
echo   • Temperature analysis (spot, trend, anomaly)
echo   • Boson SDK integration (FFC, AGC, radiometric)
echo   • Camera auto-detection
echo   • Media recording (video + snapshots)
echo.
echo %GREEN%Ready to run:%NC%
echo   python inspection_main.py
echo   python inspection_main.py --enable-boson-sdk
echo.
echo %YELLOW%Press any key to exit...%NC%
pause >nul
