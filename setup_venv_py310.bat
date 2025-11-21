@echo off
REM Setup Python 3.10 Virtual Environment for PySpin
REM Run this after installing Python 3.10

echo ========================================================================
echo  Python 3.10 Virtual Environment Setup
echo  For FLIR Firefly Camera (PySpin Support)
echo ========================================================================
echo.

REM Check if Python 3.10 is available
echo [1/6] Checking for Python 3.10...
py -3.10 --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python 3.10 is not installed!
    echo.
    echo Please install Python 3.10 first:
    echo   1. Download from: https://www.python.org/downloads/release/python-31011/
    echo   2. Install with "Add to PATH" checked
    echo   3. Run this script again
    echo.
    pause
    exit /b 1
)

py -3.10 --version
echo [OK] Python 3.10 found!
echo.

REM Navigate to project directory
cd /d "%~dp0"
echo Current directory: %CD%
echo.

REM Remove old venv if exists
if exist venv_py310 (
    echo [2/6] Removing old virtual environment...
    rmdir /s /q venv_py310
    echo [OK] Old environment removed
    echo.
)

REM Create virtual environment
echo [3/6] Creating Python 3.10 virtual environment...
py -3.10 -m venv venv_py310
if errorlevel 1 (
    echo [ERROR] Failed to create virtual environment!
    pause
    exit /b 1
)
echo [OK] Virtual environment created: venv_py310
echo.

REM Activate virtual environment
echo [4/6] Activating virtual environment...
call venv_py310\Scripts\activate.bat
echo [OK] Virtual environment activated
echo.

REM Upgrade pip
echo [5/6] Upgrading pip...
python -m pip install --upgrade pip
if errorlevel 1 (
    echo [WARNING] Could not upgrade pip, continuing...
)
echo.

REM Install requirements
echo [6/6] Installing project requirements...
if exist requirements.txt (
    pip install -r requirements.txt
    if errorlevel 1 (
        echo [WARNING] Some packages failed to install
        echo You may need to install them manually
    ) else (
        echo [OK] Requirements installed successfully!
    )
) else (
    echo [WARNING] requirements.txt not found
    echo Installing basic packages...
    pip install numpy opencv-python PyQt5 ultralytics
)
echo.

echo ========================================================================
echo  SETUP COMPLETE!
echo ========================================================================
echo.
echo Virtual environment created: venv_py310
echo Python version in venv:
python --version
echo.
echo NEXT STEPS:
echo   1. Download PySpin wheel from FLIR website
echo   2. Install with: pip install path\to\spinnaker_python-X-cp310-cp310-win_amd64.whl
echo   3. Verify with: python verify_pyspin.py
echo   4. Run application: python main.py
echo.
echo TO USE THIS ENVIRONMENT IN THE FUTURE:
echo   Run: venv_py310\Scripts\activate
echo.
echo ========================================================================
echo.

REM Keep window open
echo Press any key to exit...
pause >nul
