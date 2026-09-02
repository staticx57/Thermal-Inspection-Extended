@echo off
cd /d "%~dp0.."
:: Quick Launch - Thermal Priority Mode (Radiometric)
echo Starting Thermal Inspection Tool in Thermal Priority Mode...
echo - Flirpy backend (16-bit radiometric)
echo - Boson SDK enabled
echo - Ironbow palette
echo.

python -m thermal_inspection --thermal-backend flirpy --enable-boson-sdk --palette ironbow --auto-detect-cameras

pause
