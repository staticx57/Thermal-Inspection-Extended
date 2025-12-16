@echo off
:: Quick Launch - RGB Priority Mode (Visual Inspection)
echo Starting Thermal Inspection Tool in RGB Priority Mode...
echo - OpenCV backend (8-bit AGC)
echo - Viridis palette
echo - Visual inspection focus
echo.

python "%~dp0inspection_main.py" --thermal-backend opencv --palette viridis --auto-detect-cameras

pause
