@echo off
REM ResolveAI - Quick setup script for Windows
echo Setting up ResolveAI...

REM Check for Python
python --version >nul 2>&1
if errorlevel 1 (
    echo Python is not installed. Please install Python 3.10+ from https://python.org
    exit /b 1
)

REM Create virtual environment
python -m venv .venv
call .venv\Scripts\activate.bat

REM Install dependencies
python -m pip install --upgrade pip
pip install -r requirements.txt

echo.
echo Setup complete!
echo.
echo To start ResolveAI:
echo   .venv\Scripts\activate.bat
echo   python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
echo.
echo Then open http://localhost:8000 in your browser.
pause
