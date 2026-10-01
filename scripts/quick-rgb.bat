@echo off
cd /d "%~dp0.."
:: Quick Launch - Visual Inspection (viridis palette)
echo Starting Thermal Inspection Tool in RGB Priority Mode...
echo - Viridis palette (visual inspection)
echo.

call python -m thermal_inspection --palette viridis --auto-detect-cameras

pause
