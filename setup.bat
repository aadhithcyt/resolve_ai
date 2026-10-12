@echo off
REM ResolveAI - Quick setup script for Windows
setlocal
echo Setting up ResolveAI...

REM Check for Python
python --version >nul 2>&1
if errorlevel 1 (
    echo Python is not installed. Please install Python 3.10+ from https://python.org
    echo During installation, check "Add Python to PATH".
    exit /b 1
)

REM Verify the Python version is 3.10 or newer
python -c "import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)"
if errorlevel 1 (
    echo Python 3.10 or newer is required. Found:
    python --version
    exit /b 1
)

REM Create virtual environment
if not exist ".venv\Scripts\activate.bat" (
    echo Creating virtual environment...
    python -m venv .venv
    if errorlevel 1 (
        echo Failed to create the virtual environment.
        exit /b 1
    )
)

call .venv\Scripts\activate.bat

REM Install dependencies
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo Dependency installation failed. Check your network connection and
    echo that Python 3.10+ is installed.
    exit /b 1
)

echo.
echo Setup complete!
echo.
echo To start ResolveAI:
echo   run.bat
echo.
echo Then open http://localhost:8000 in your browser.
echo.
echo Remember to set your Groq API key first:
echo   set GROQ_API_KEY=your-key-here
pause
