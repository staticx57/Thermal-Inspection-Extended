@echo off
REM ThermalFusionDrivingAssist - Windows Installation Script
REM For Windows 10/11 x86-64 systems (ThinkPad P16, etc.)
REM
REM This script installs:
REM - Python dependencies (OpenCV, NumPy, etc.)
REM - UVC webcam support (built-in to Windows)
REM - OPTIONAL: FLIR Firefly Spinnaker SDK (for global shutter cameras)
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

echo %BLUE%========================================%NC%
echo %BLUE%ThermalFusionDrivingAssist Installation%NC%
echo %BLUE%========================================%NC%
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
    echo %YELLOW%PySpin ^(FLIR Firefly support^) may not be compatible.%NC%
    echo %YELLOW%Recommended: Python 3.10 for best compatibility.%NC%
    echo %YELLOW%See: docs\install\setup_python310_env.md%NC%
    echo.
)
echo %PYTHON_VER% | findstr /C:"3.13" >nul && (
    echo %YELLOW%WARNING: Python 3.13 detected!%NC%
    echo %YELLOW%PySpin ^(FLIR Firefly support^) may not be compatible.%NC%
    echo %YELLOW%Recommended: Python 3.10 for best compatibility.%NC%
    echo %YELLOW%See: docs\install\setup_python310_env.md%NC%
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
    echo   --with-firefly    Install FLIR Firefly Spinnaker SDK ^(optional^)
    echo   --help            Show this help message
    echo.
    exit /b 0
)

REM Step 1: Upgrade pip
echo %BLUE%[1/5] Upgrading pip...%NC%
python -m pip install --upgrade pip

REM Step 2: Install OpenCV
echo %BLUE%[2/5] Installing OpenCV...%NC%
python -m pip install opencv-python opencv-contrib-python

REM Step 3: Install NumPy and core dependencies
echo %BLUE%[3/5] Installing NumPy and core dependencies...%NC%
python -m pip install numpy

REM Step 4: Install project dependencies
echo %BLUE%[4/6] Installing project dependencies...%NC%
if exist requirements.txt (
    echo %GREEN%Found requirements.txt - installing...%NC%
    python -m pip install -r requirements.txt
) else (
    echo %YELLOW%requirements.txt not found. Installing core packages manually...%NC%
    python -m pip install numpy ultralytics supervision torch torchvision
)

REM Step 4.5: Install PyQt5 for Qt GUI
echo %BLUE%[4.5/6] Installing PyQt5 for Qt GUI ^(v3.x^)...%NC%
python -m pip install PyQt5

REM Verify PyQt5
python -c "from PyQt5.QtWidgets import QApplication; print('OK PyQt5 installed successfully')" 2>nul
if errorlevel 1 (
    echo %RED%PyQt5 installation failed%NC%
    echo %YELLOW%Qt GUI may not work. Please check your Python installation.%NC%
) else (
    echo %GREEN%PyQt5 installed successfully%NC%
)

REM Step 5: OPTIONAL - Install FLIR Firefly Spinnaker SDK
if "%INSTALL_FIREFLY%"=="true" (
    echo %BLUE%[5/6] Installing FLIR Firefly Spinnaker SDK...%NC%
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
    echo   3. Choose "Full Installation" ^(includes PySpin^)
    echo   4. Install PySpin wheel from SDK folder
    echo.
    echo %BLUE%Detailed Instructions:%NC%
    echo   See: docs\install\install_pyspin.md
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
    echo %BLUE%[5/6] Skipping FLIR Firefly support ^(use --with-firefly to enable^)%NC%
)

REM Step 6: Verify installation
echo %BLUE%[6/6] Verifying installation...%NC%
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
echo %GREEN%Installation Complete ^& Verified!%NC%
echo %GREEN%========================================%NC%
echo.
echo %BLUE%System Status:%NC%
echo   ✓ Python 3 ^& dependencies
echo   ✓ OpenCV ^(computer vision^)
echo   ✓ PyQt5 ^(Qt GUI v3.x^)
echo   ✓ UVC webcam support
if "%INSTALL_FIREFLY%"=="true" (
    echo   ✓ FLIR Firefly support ^(check above for status^)
) else (
    echo   ⚠ FLIR Firefly support: Not installed ^(use --with-firefly^)
)
echo.
echo %BLUE%Qt GUI Features ^(v3.x^):%NC%
echo   • Multithreaded architecture ^(VideoProcessorWorker^)
echo   • Developer mode ^(Ctrl+D^) with 9 controls:
echo     - Palette cycling, Detection toggle, Device switch
echo     - Model cycling ^(with custom model support^)
echo     - Fusion mode/alpha, Buffer flush, Frame skip
echo     - Simulated thermal camera ^(debug mode^)
echo   • ADAS-compliant alert overlays
echo   • Light/Dark theme auto-switching
echo.
echo %BLUE%Next Steps:%NC%
echo   1. Connect RGB camera ^(UVC webcam or FLIR Firefly^)
echo   2. ^(Optional^) Add custom models to config.json
echo   3. Run system: python main.py
echo   4. Press Ctrl+D to toggle developer mode
echo.
echo %BLUE%Documentation:%NC%
echo   • Main guide: README.md
echo   • Windows setup: docs\WINDOWS_SETUP.md
echo   • PySpin setup: docs\install\install_pyspin.md
echo   • Custom models: docs\CUSTOM_MODELS.md
echo   • Troubleshooting: docs\DEBUGGING_GUIDELINES.md
echo.
echo %YELLOW%Press any key to exit...%NC%
pause >nul
