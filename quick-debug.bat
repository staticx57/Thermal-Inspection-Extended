@echo off
:: Quick Launch - Debug Mode
echo Starting Thermal Inspection Tool in Debug Mode...
echo - Detailed console logging
echo - Developer mode enabled
echo - Auto-detect cameras
echo.

python "%~dp0inspection_main.py" --auto-detect-cameras

echo.
echo ================================================================================
echo Debug session ended. Check thermal_inspection_debug.log for details.
echo ================================================================================

pause
