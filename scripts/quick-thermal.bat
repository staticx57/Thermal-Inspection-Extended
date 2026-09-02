@echo off
cd /d "%~dp0.."
:: Quick Launch - Thermal Priority Mode (Radiometric)
echo Starting Thermal Inspection Tool in Thermal Priority Mode...
echo - Boson SDK enabled (radiometric temperature, FFC, gain control)
echo - Ironbow palette
echo.

python -m thermal_inspection --enable-boson-sdk --palette ironbow --auto-detect-cameras

pause
