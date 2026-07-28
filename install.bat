@echo off
title NovelForge Installer
echo ============================================
echo        NovelForge - Dependency Installer
echo ============================================
echo.

REM ---------- Backend: create venv & install deps ----------
echo [1/2] Setting up backend (Python venv)...
echo.
cd /d "%~dp0backend"

if exist venv (
    echo venv already exists. Skipping creation.
) else (
    echo Creating virtual environment...
    python -m venv venv
    if errorlevel 1 (
        echo.
        echo ERROR: Failed to create venv. Make sure Python is installed and on PATH.
        pause
        exit /b 1
    )
)

echo Installing backend dependencies...
venv\Scripts\python.exe -m pip install --upgrade pip
venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo ERROR: Failed to install backend dependencies.
    pause
    exit /b 1
)
echo Backend setup complete.
echo.

REM ---------- Frontend: npm install ----------
echo [2/2] Setting up frontend (npm install)...
echo.
cd /d "%~dp0frontend"

if not exist package.json (
    echo ERROR: package.json not found in frontend folder.
    pause
    exit /b 1
)

echo Installing frontend dependencies (this may take a while)...
call npm install
if errorlevel 1 (
    echo.
    echo ERROR: Failed to install frontend dependencies.
    pause
    exit /b 1
)
echo Frontend setup complete.
echo.

REM ---------- Done ----------
cd /d "%~dp0"
echo ============================================
echo  Installation finished successfully!
echo  Next: run run-backend.bat, then run-frontend.bat
echo ============================================
pause
