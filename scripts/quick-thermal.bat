@echo off
cd /d "%~dp0.."
:: Quick Launch - Thermal Priority Mode (Radiometric)
echo Starting Thermal Inspection Tool in Thermal Priority Mode...
echo - Boson serial control enabled (FFC, gain, temperature)
echo - Ironbow palette
echo.

call python -m thermal_inspection --enable-boson-sdk --palette ironbow --auto-detect-cameras

pause
