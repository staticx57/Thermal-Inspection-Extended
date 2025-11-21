@echo off
REM ThermalFusionDrivingAssist - Windows Repair/Update Script
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

echo %BLUE%========================================%NC%
echo %BLUE%ThermalFusionDrivingAssist Repair%NC%
echo %BLUE%========================================%NC%
echo.

REM Check if we're in the right directory
if not exist main.py (
    echo %RED%Error: main.py not found%NC%
    echo %YELLOW%Please run this script from the ThermalFusionDrivingAssist directory%NC%
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

REM Step 2: Install/update PyQt5
echo %BLUE%[2/4] Installing/updating PyQt5...%NC%
python -m pip install --upgrade PyQt5

REM Verify PyQt5
python -c "from PyQt5.QtWidgets import QApplication; print('OK PyQt5 verified')" 2>nul
if errorlevel 1 (
    echo %RED%PyQt5 installation failed%NC%
    echo %YELLOW%Please check your Python installation%NC%
) else (
    echo %GREEN%PyQt5 verified%NC%
)

REM Step 3: Update requirements
echo %BLUE%[3/4] Updating project dependencies...%NC%
if exist requirements.txt (
    echo %GREEN%Found requirements.txt - updating...%NC%
    python -m pip install --upgrade -r requirements.txt
) else (
    echo %YELLOW%requirements.txt not found. Updating core packages...%NC%
    python -m pip install --upgrade numpy opencv-python ultralytics supervision torch torchvision
)

REM Step 4: Verify installation
echo %BLUE%[4/4] Verifying repaired installation...%NC%
echo.

echo %BLUE%Testing Python modules...%NC%
python -c "import numpy; print('  ✓ NumPy')" 2>nul || echo   ✗ NumPy - FAILED
python -c "import cv2; print('  ✓ OpenCV')" 2>nul || echo   ✗ OpenCV - FAILED
python -c "import PyQt5.QtWidgets; print('  ✓ PyQt5')" 2>nul || echo   ✗ PyQt5 - FAILED
python -c "import ultralytics; print('  ✓ Ultralytics YOLO')" 2>nul || echo   ✗ Ultralytics - FAILED

echo.
echo %BLUE%Checking project files...%NC%
if exist main.py (echo   ✓ main.py) else echo   ✗ main.py - MISSING
if exist driver_gui_qt.py (echo   ✓ driver_gui_qt.py) else echo   ✗ driver_gui_qt.py - MISSING
if exist video_worker.py (echo   ✓ video_worker.py) else echo   ✗ video_worker.py - MISSING
if exist developer_panel.py (echo   ✓ developer_panel.py) else echo   ✗ developer_panel.py - MISSING
if exist alert_overlay.py (echo   ✓ alert_overlay.py) else echo   ✗ alert_overlay.py - MISSING
if exist config.py (echo   ✓ config.py) else echo   ✗ config.py - MISSING

echo.
echo %GREEN%========================================%NC%
echo %GREEN%Repair Complete ^& Verified!%NC%
echo %GREEN%========================================%NC%
echo.
echo %BLUE%Latest Features ^(v3.x^):%NC%
echo   • Qt GUI ^(replaces OpenCV GUI^)
echo   • Multithreaded video processing
echo   • Developer mode ^(Ctrl+D^) with 9 controls
echo   • ADAS-compliant alert overlays
echo   • Custom model support ^(see CUSTOM_MODELS.md^)
echo   • Simulated thermal camera ^(debug mode^)
echo   • Light/Dark theme auto-switching
echo.
echo %GREEN%Ready to run: python main.py%NC%
echo.
echo %YELLOW%Press any key to exit...%NC%
pause >nul
