@echo off
title Shopee Card Checker Pro - Setup and Launch
color 0A

echo ========================================
echo   Shopee Card Checker Pro - GUI
echo ========================================
echo.

:: Check if Python is installed
echo [1/3] Checking Python installation...
where python >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo Python not found in PATH. Trying 'py' command...
    where py >nul 2>&1
    if %ERRORLEVEL% NEQ 0 (
        echo.
        echo [ERROR] Python is not installed!
        echo.
        echo Would you like to install Python automatically?
        echo This requires Administrator privileges and will download ~30MB.
        echo.
        set /p install_python="Install Python now? (y/n): "
        
        if /i "%install_python%" NEQ "y" (
            echo.
            echo Installation cancelled.
            echo Please install Python manually from: https://www.python.org/downloads/
            echo.
            pause
            exit /b 1
        )
        
        echo.
        echo Downloading Python installer...
        powershell -Command "& {[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.11.6/python-3.11.6-amd64.exe' -OutFile '%TEMP%\python_installer.exe'}"
        
        if exist "%TEMP%\python_installer.exe" (
            echo Installing Python... (UAC prompt will appear)
            echo Please click "Yes" when prompted.
            echo.
            powershell -Command "Start-Process '%TEMP%\python_installer.exe' -ArgumentList '/quiet InstallAllUsers=1 PrependPath=1 Include_test=0' -Verb RunAs -Wait"
            
            del "%TEMP%\python_installer.exe" >nul 2>&1
            
            echo.
            echo Python installed successfully!
            echo.
            echo IMPORTANT: Please close this window and run start_gui.bat again.
            echo (The PATH needs to be refreshed)
            echo.
            pause
            exit /b 0
        ) else (
            echo.
            echo [ERROR] Failed to download Python installer.
            echo Please install Python manually from: https://www.python.org/downloads/
            echo.
            pause
            exit /b 1
        )
    ) else (
        set PYTHON_CMD=py
    )
) else (
    set PYTHON_CMD=python
)

:: Verify Python works and get version
%PYTHON_CMD% --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Python command failed. Please reinstall Python.
    pause
    exit /b 1
)

for /f "tokens=*" %%i in ('%PYTHON_CMD% --version 2^>^&1') do set PYTHON_VERSION=%%i
echo %PYTHON_VERSION% installed
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
