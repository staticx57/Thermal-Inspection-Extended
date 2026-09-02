@echo off
cd /d "%~dp0.."
:: Quick Launch - RGB Priority Mode (Visual Inspection)
echo Starting Thermal Inspection Tool in RGB Priority Mode...
echo - Viridis palette
echo - Visual inspection focus
echo.

python -m thermal_inspection --palette viridis --auto-detect-cameras

pause
