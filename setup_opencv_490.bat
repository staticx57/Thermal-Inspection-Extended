@echo off
REM Quick setup for OpenCV 4.9.0 testing
REM Based on GitHub issue #27166 which confirms 4.9.0.80 works for FLIR Boson

echo ======================================================================
echo OpenCV 4.9.0 Test Environment Setup
echo ======================================================================
echo.
echo This will create a virtual environment with OpenCV 4.9.0.80
echo (the version confirmed working for FLIR Boson 16-bit capture)
echo.

REM Check if venv already exists
if exist venv_opencv490 (
    echo WARNING: venv_opencv490 already exists
    set /p "response=Delete and recreate? (y/n): "
    if /i not "%response%"=="y" (
        echo Using existing venv...
        goto activate
    )
    echo Deleting existing venv...
    rmdir /s /q venv_opencv490
)

echo.
echo [Step 1/4] Creating virtual environment...
python -m venv venv_opencv490
if errorlevel 1 (
    echo ERROR: Failed to create virtual environment
    pause
    exit /b 1
)
echo Done!

echo.
echo [Step 2/4] Upgrading pip...
venv_opencv490\Scripts\python.exe -m pip install --upgrade pip
if errorlevel 1 (
    echo WARNING: Failed to upgrade pip, continuing anyway...
)
echo Done!

echo.
echo [Step 3/4] Installing OpenCV 4.9.0.80...
venv_opencv490\Scripts\pip.exe install opencv-python==4.9.0.80
if errorlevel 1 (
    echo ERROR: Failed to install OpenCV 4.9.0.80
    pause
    exit /b 1
)
echo Done!

echo.
echo [Step 4/4] Installing dependencies...
venv_opencv490\Scripts\pip.exe install numpy pyserial
if errorlevel 1 (
    echo WARNING: Failed to install dependencies
)
echo Done!

echo.
echo ======================================================================
echo Verifying Installation
echo ======================================================================
venv_opencv490\Scripts\python.exe -c "import cv2; print('OpenCV version:', cv2.__version__)"
if errorlevel 1 (
    echo ERROR: OpenCV not installed correctly
    pause
    exit /b 1
)

echo.
echo ======================================================================
echo SETUP COMPLETE!
echo ======================================================================
echo.
echo Next steps:
echo.
echo 1. Activate the virtual environment:
echo    venv_opencv490\Scripts\activate
echo.
echo 2. Run the quick test:
echo    python test_opencv_490_quick.py
echo.
echo 3. If successful, you found your solution!
echo.
echo ======================================================================
echo.

:activate
echo To activate now, run:
echo    venv_opencv490\Scripts\activate
echo.
pause
