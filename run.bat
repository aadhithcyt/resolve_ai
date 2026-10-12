@echo off
REM ResolveAI - Quick start script for Windows
cd /d "%~dp0"

if not exist ".venv\Scripts\activate.bat" (
    echo No virtual environment found at .venv\
    echo Run setup.bat first.
    echo.
    pause
    exit /b 1
)

call .venv\Scripts\activate.bat
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
