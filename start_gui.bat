@echo off
echo ========================================
echo   Shopee Card Checker Pro - GUI
echo ========================================
echo.
echo Starting application...
echo.

python gui.py

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Error launching GUI. Press any key to exit...
    pause >nul
)
