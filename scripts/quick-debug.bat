@echo off
cd /d "%~dp0.."
:: Quick Launch - Debug Mode
echo Starting Thermal Inspection Tool in Debug Mode...
echo - Verbose logging (DEBUG) to the console AND thermal_inspection_debug.log
echo - Auto-detect cameras
echo - Tip: press Ctrl+D inside the app to toggle Developer mode
echo.

call python -m thermal_inspection --auto-detect-cameras --log-level DEBUG --log-file thermal_inspection_debug.log

echo.
echo ================================================================================
echo Debug session ended. Check thermal_inspection_debug.log for details.
echo ================================================================================

pause
