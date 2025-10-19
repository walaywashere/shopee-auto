@echo off
title Shopee Card Checker Pro - Setup and Launch
color 0A

echo ========================================
echo   Shopee Card Checker Pro - GUI
echo ========================================
echo.

:: Check if Python is installed
echo [1/3] Checking Python installation...
python --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Python is not installed!
    echo.
    echo This script will now install Python automatically.
    echo NOTE: This requires Administrator privileges.
    echo.
    pause
    
    echo.
    echo Downloading Python installer...
    :: Download Python installer using PowerShell
    powershell -Command "& {Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.11.6/python-3.11.6-amd64.exe' -OutFile '%TEMP%\python_installer.exe'}"
    
    if exist "%TEMP%\python_installer.exe" (
        echo Installing Python... (UAC prompt will appear)
        echo Please click "Yes" when prompted.
        echo.
        :: Run installer with admin rights
        powershell -Command "Start-Process '%TEMP%\python_installer.exe' -ArgumentList '/quiet InstallAllUsers=1 PrependPath=1 Include_test=0' -Verb RunAs -Wait"
        
        :: Clean up installer
        del "%TEMP%\python_installer.exe"
        
        echo.
        echo Python installed successfully!
        echo Please close this window and run the script again.
        echo.
        pause
        exit /b 0
    ) else (
        echo.
        echo Failed to download Python installer.
        echo Please install Python manually from: https://www.python.org/downloads/
        echo.
        pause
        exit /b 1
    )
) else (
    python --version
    echo Python is installed!
)

echo.
echo [2/3] Checking dependencies...

:: Check if requirements are installed by trying to import a key package
python -c "import customtkinter" >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo Dependencies not found. Installing requirements...
    echo This may take a few minutes...
    echo.
    
    python -m pip install --upgrade pip --quiet
    python -m pip install -r requirements.txt --quiet
    
    if %ERRORLEVEL% EQU 0 (
        echo.
        echo Dependencies installed successfully!
    ) else (
        echo.
        echo Failed to install dependencies.
        echo Please run: pip install -r requirements.txt
        echo.
        pause
        exit /b 1
    )
) else (
    echo All dependencies are installed!
)

echo.
echo [3/3] Launching GUI...
echo.
echo ========================================
echo.

:: Launch the GUI
python gui.py

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Error launching GUI.
    echo.
    pause
)
