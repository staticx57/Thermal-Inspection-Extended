@echo off
setlocal enabledelayedexpansion

:: Thermal Inspection Fusion Tool - Enhanced Launcher
:: Provides interactive menu for common startup configurations

color 0A
title Thermal Inspection Fusion Tool - Launcher

:: Check if arguments were passed directly
if not "%~1"=="" (
    echo Direct arguments detected: %*
    echo.
    goto :run_with_args
)

:main_menu
cls
echo ================================================================================
echo   THERMAL INSPECTION FUSION TOOL - LAUNCHER
echo ================================================================================
echo.
echo   SELECT STARTUP MODE:
echo.
echo   [1] Quick Start (Default Settings)
echo   [2] Thermal Priority Mode (radiometric + flirpy backend)
echo   [3] RGB Priority Mode (visual inspection)
echo   [4] Playback Mode (analyze recorded video)
echo   [5] Headless Mode (no GUI, processing only)
echo   [6] Custom Arguments
echo   [7] View Available Options
echo   [0] Exit
echo.
echo ================================================================================

set /p choice="Enter your choice [0-7]: "

if "%choice%"=="0" goto :exit
if "%choice%"=="1" goto :quick_start
if "%choice%"=="2" goto :thermal_priority
if "%choice%"=="3" goto :rgb_priority
if "%choice%"=="4" goto :playback_mode
if "%choice%"=="5" goto :headless_mode
if "%choice%"=="6" goto :custom_args
if "%choice%"=="7" goto :show_options

echo.
echo Invalid choice. Please try again.
timeout /t 2 >nul
goto :main_menu

:quick_start
echo.
echo Starting with default settings...
set ARGS=
goto :run

:thermal_priority
cls
echo ================================================================================
echo   THERMAL PRIORITY MODE
echo ================================================================================
echo.
echo   This mode optimizes for thermal analysis:
echo   - Flirpy backend (16-bit radiometric)
echo   - Thermal priority fusion
echo   - Boson SDK enabled
echo   - Ironbow palette
echo.
echo   Device Selection:
echo   [1] Auto-detect cameras (recommended)
echo   [2] Manual: Thermal=2, RGB=0
echo   [3] Manual: Thermal=0, RGB=1
echo   [4] Custom device IDs
echo.

set /p dev_choice="Select device option [1-4]: "

set ARGS=--thermal-backend flirpy --enable-boson-sdk --palette ironbow

if "%dev_choice%"=="1" (
    set ARGS=!ARGS! --auto-detect-cameras
) else if "%dev_choice%"=="2" (
    set ARGS=!ARGS! --thermal-device 2 --rgb-device 0
) else if "%dev_choice%"=="3" (
    set ARGS=!ARGS! --thermal-device 0 --rgb-device 1
) else if "%dev_choice%"=="4" (
    echo.
    set /p thermal_id="Enter thermal device ID: "
    set /p rgb_id="Enter RGB device ID: "
    set ARGS=!ARGS! --thermal-device !thermal_id! --rgb-device !rgb_id!
)

echo.
set /p com_port="Enter Boson COM port [default: COM7]: "
if not "!com_port!"=="" set ARGS=!ARGS! --boson-com-port !com_port!

goto :run

:rgb_priority
cls
echo ================================================================================
echo   RGB PRIORITY MODE
echo ================================================================================
echo.
echo   This mode optimizes for visual inspection:
echo   - OpenCV backend (8-bit AGC)
echo   - RGB priority fusion
echo   - Viridis palette
echo.

set ARGS=--thermal-backend opencv --palette viridis

set /p disable_thermal="Disable thermal camera? [y/N]: "
if /i "!disable_thermal!"=="y" set ARGS=!ARGS! --disable-rgb

goto :run

:playback_mode
cls
echo ================================================================================
echo   PLAYBACK MODE
echo ================================================================================
echo.
echo   Analyze recorded thermal video files
echo.

set /p playback_file="Enter video file path (drag and drop file here): "
:: Remove quotes from drag-and-drop
set playback_file=!playback_file:"=!

if "!playback_file!"=="" (
    echo No file specified. Returning to menu...
    timeout /t 2 >nul
    goto :main_menu
)

if not exist "!playback_file!" (
    echo File not found: !playback_file!
    timeout /t 3 >nul
    goto :main_menu
)

set ARGS=--mode playback --playback-file "!playback_file!"

echo.
echo Playback Options:
echo   [1] Thermal backend: OpenCV (8-bit)
echo   [2] Thermal backend: Flirpy (16-bit radiometric)
echo.
set /p backend_choice="Select backend [1-2]: "

if "!backend_choice!"=="2" (
    set ARGS=!ARGS! --thermal-backend flirpy
) else (
    set ARGS=!ARGS! --thermal-backend opencv
)

goto :run

:headless_mode
cls
echo ================================================================================
echo   HEADLESS MODE
echo ================================================================================
echo.
echo   Processing mode without GUI (for automation/testing)
echo.

set ARGS=--headless --gui headless

echo.
set /p output_dir="Enter output directory for results [default: current]: "
if not "!output_dir!"=="" set ARGS=!ARGS! --output-dir "!output_dir!"

goto :run

:custom_args
cls
echo ================================================================================
echo   CUSTOM ARGUMENTS
echo ================================================================================
echo.
echo   Enter custom command-line arguments.
echo   Type "help" to see available options.
echo.

set /p ARGS="Arguments: "

if /i "!ARGS!"=="help" (
    goto :show_options
)

goto :run

:show_options
cls
echo ================================================================================
echo   AVAILABLE COMMAND-LINE OPTIONS
echo ================================================================================
echo.
echo   CAMERA OPTIONS:
echo     --thermal-device ID          Thermal camera device ID
echo     --rgb-device ID              RGB camera device ID
echo     --auto-detect-cameras        Auto-detect camera devices (default)
echo     --disable-rgb                Run without RGB camera
echo.
echo   THERMAL BACKEND:
echo     --thermal-backend TYPE       opencv or flirpy (default: opencv)
echo     --enable-boson-sdk           Enable Boson SDK for control
echo     --boson-com-port PORT        COM port for Boson (default: COM7)
echo.
echo   DISPLAY:
echo     --palette NAME               Thermal palette (ironbow, viridis, etc.)
echo     --fusion-mode MODE           alpha_blend, thermal_overlay,
echo                                  picture_in_picture, etc.
echo     --fusion-alpha VALUE         Fusion transparency (0.0-1.0)
echo.
echo   PROCESSING:
echo     --device TYPE                cuda or cpu (default: cuda)
echo     --auto-roi                   Enable automatic ROI detection
echo.
echo   MODE:
echo     --mode TYPE                  realtime or playback (default: realtime)
echo     --playback-file PATH         Video file for playback mode
echo.
echo   GUI:
echo     --gui TYPE                   qt, opencv, or headless (default: qt)
echo     --headless                   Run without GUI
echo.
echo ================================================================================
echo.
pause
goto :main_menu

:run
echo.
echo ================================================================================
echo   LAUNCHING WITH ARGUMENTS:
echo   !ARGS!
echo ================================================================================
echo.

:run_with_args
python "%~dp0inspection_main.py" %* !ARGS!

echo.
echo ================================================================================
echo   Application exited
echo ================================================================================
echo.

set /p restart="Restart launcher? [Y/n]: "
if /i "!restart!"=="n" goto :exit
if "!restart!"=="" goto :main_menu
if /i "!restart!"=="y" goto :main_menu
goto :exit

:exit
endlocal
exit /b 0
