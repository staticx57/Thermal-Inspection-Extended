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
echo   [2] Thermal Priority Mode (Boson control + radiometric)
echo   [3] RGB Priority Mode (visual inspection)
echo   [4] Playback Mode (analyze recorded video)
echo   [5] Headless Mode (no GUI, processing only)
echo   [6] Custom Arguments
echo   [7] View Available Options
echo   [8] Diagnostic Run (saves a log to logs\diagnostic.log)
echo   [9] Repair: forget the saved camera scan (cameras missing after a crash)
echo   [0] Exit
echo.
echo ================================================================================

set /p choice="Enter your choice [0-9]: "

if "%choice%"=="0" goto :exit
if "%choice%"=="1" goto :quick_start
if "%choice%"=="2" goto :thermal_priority
if "%choice%"=="3" goto :rgb_priority
if "%choice%"=="4" goto :playback_mode
if "%choice%"=="5" goto :headless_mode
if "%choice%"=="6" goto :custom_args
if "%choice%"=="7" goto :show_options
if "%choice%"=="8" goto :diagnostic_run
if "%choice%"=="9" goto :reset_camera_cache

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
echo   - Boson SDK enabled (radiometric temperature, FFC, gain control)
echo   - Ironbow palette
echo.
echo   Device Selection:
echo   [1] Auto-detect cameras (recommended)
echo   [2] Manual: Thermal=2, RGB=0
echo   [3] Manual: Thermal=0, RGB=1
echo   [4] Custom device IDs
echo.

set /p dev_choice="Select device option [1-4]: "

set ARGS=--enable-boson-sdk --palette ironbow

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
echo   - Viridis palette (easier on the eyes for visual inspection)
echo   - Optionally runs without the thermal camera
echo.

set ARGS=--palette viridis

set /p disable_rgb="Disable RGB camera (thermal only)? [y/N]: "
if /i "!disable_rgb!"=="y" set ARGS=!ARGS! --disable-rgb

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

:diagnostic_run
cls
echo ================================================================================
echo   DIAGNOSTIC RUN
echo ================================================================================
echo.
echo   Starts the app with detailed logging (INFO) written to logs\diagnostic.log.
echo   Reproduce the problem, close the app, then send or open that file: it records
echo   which cameras were found, why one could not be opened, and any errors.
echo.
if not exist logs mkdir logs
set ARGS=--log-level INFO --log-file logs\diagnostic.log
goto :run

:reset_camera_cache
cls
echo ================================================================================
echo   REPAIR: FORGET THE SAVED CAMERA SCAN
echo ================================================================================
echo.
echo   The app remembers which cameras it found so it can start quickly. If a scan ran
echo   while a camera was held by another program (or a frozen copy of this app), the
echo   short list can be remembered and the missing camera never reappears.
echo   This clears that memory; the next start scans the cameras again.
echo.
echo   Close every copy of the app first (a frozen copy can hold a camera: check Task
echo   Manager for python.exe).
echo.
call python -m thermal_inspection --reset-camera-cache
echo.
pause
goto :main_menu

:show_options
cls
echo ================================================================================
echo   AVAILABLE COMMAND-LINE OPTIONS  (python -m thermal_inspection --help for the full text)
echo ================================================================================
echo.
echo   CAMERA OPTIONS:
echo     --thermal-device ID          Thermal camera device ID
echo     --rgb-device ID              RGB camera device ID
echo     --auto-detect-cameras        Auto-detect camera devices (default)
echo     --disable-rgb                Run without RGB camera
echo     --width W / --height H       Thermal frame size (default 640 x 512)
echo.
echo   BOSON:
echo     --enable-boson-sdk           Serial control of the Boson (FFC, gain, temperature)
echo     --boson-com-port PORT        COM port for Boson (default: COM7)
echo     --radiometric                Enable radiometric temperature measurement
echo.
echo   DISPLAY:
echo     --palette ID                 Palette id (ironbow, viridis, ... see README palette table)
echo     --fusion-mode MODE           thermal_overlay, alpha_blend, ... (see --help)
echo     --fusion-alpha VALUE         Alpha for alpha_blend (0.0-1.0)
echo     --calibration-file PATH      Camera alignment calibration
echo.
echo   PROCESSING:
echo     --device TYPE                cuda or cpu (default: cuda)
echo     --auto-roi                   Enable automatic ROI detection
echo     --enable_parallel true/false Parallel detection (default true)
echo     --max_workers N              Worker threads for parallel detection
echo.
echo   MODE:
echo     --mode TYPE                  realtime or playback (default: realtime)
echo     --playback-file PATH         Video file for playback mode
echo.
echo   GUI:
echo     --gui TYPE                   qt, opencv, or headless (default: qt)
echo     --use-opencv-gui / --headless
echo.
echo   DIAGNOSTICS:
echo     --log-level LEVEL            DEBUG, INFO, WARNING (default) or ERROR
echo     --log-file PATH              Also write the log to a file
echo     --reset-camera-cache         Forget the saved camera scan, then exit
echo.
echo   (--thermal-backend is deprecated and ignored: the backend is chosen per camera)
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
:: Use package entry point (preferred) or fallback to legacy script
call python -m thermal_inspection %* !ARGS!

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
