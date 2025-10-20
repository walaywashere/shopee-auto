@echo off
title Shopee Card Checker Pro - Setup and Launch
color 0A

echo ========================================
echo   Shopee Card Checker Pro - GUI
echo ========================================
echo.

:: Check if Python is installed and working
echo [1/3] Checking Python installation...

:: Try python command first
python --version >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    set PYTHON_CMD=python
    goto :python_found
)

:: Try py command (Windows Python Launcher)
py --version >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    set PYTHON_CMD=py
    goto :python_found
)

:: Python not found
echo.
echo [ERROR] Python is not installed or not in PATH!
echo.
echo Please install Python from: https://www.python.org/downloads/
echo Make sure to check "Add Python to PATH" during installation.
echo.
pause
exit /b 1

:python_found
for /f "tokens=*" %%i in ('%PYTHON_CMD% --version 2^>^&1') do set PYTHON_VERSION=%%i
echo %PYTHON_VERSION% found!
echo.

echo [2/3] Checking dependencies...

:: Check if requirements are installed by trying to import a key package
%PYTHON_CMD% -c "import customtkinter" >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo Installing required packages...
    echo This may take 1-2 minutes on first run...
    echo.
    
    %PYTHON_CMD% -m pip install --upgrade pip --quiet >nul 2>&1
    %PYTHON_CMD% -m pip install -r requirements.txt --quiet
    
    if %ERRORLEVEL% EQU 0 (
        echo.
        echo All dependencies installed successfully!
    ) else (
        echo.
        echo [ERROR] Failed to install dependencies.
        echo.
        echo Please try running manually: pip install -r requirements.txt
        echo.
        pause
        exit /b 1
    )
) else (
    echo All dependencies are already installed!
)

echo.
echo [3/3] Launching GUI...
echo.
echo ========================================
echo.

:: Launch the GUI
%PYTHON_CMD% gui.py

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] GUI failed to launch.
    echo.
    pause
)
