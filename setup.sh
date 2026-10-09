#!/usr/bin/env bash
# ResolveAI - Cross-platform setup script (Linux/macOS/RHEL)
set -e

echo "Setting up ResolveAI..."

# Detect OS
OS="$(uname -s)"
case "$OS" in
    Linux*)     PLATFORM="linux" ;;
    Darwin*)    PLATFORM="macos" ;;
    CYGWIN*|MINGW*|MSYS*) PLATFORM="windows" ;;
    *)          PLATFORM="unknown" ;;
esac

echo "Detected platform: $PLATFORM"

# Check for Python
if ! command -v python3 &> /dev/null; then
    echo "Python 3 not found. Please install Python 3.10+ first."
    if [ "$PLATFORM" = "linux" ]; then
        echo "  RHEL/CentOS: sudo dnf install python3 python3-pip"
        echo "  Ubuntu/Debian: sudo apt install python3 python3-pip"
    elif [ "$PLATFORM" = "macos" ]; then
        echo "  macOS: brew install python3"
    fi
    exit 1
fi

PYTHON=python3

# Create virtual environment
$PYTHON -m venv .venv

# Activate virtual environment
if [ "$PLATFORM" = "windows" ]; then
    source .venv/Scripts/activate
else
    source .venv/bin/activate
fi

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

echo ""
echo "Setup complete!"
echo ""
echo "To start ResolveAI:"
if [ "$PLATFORM" = "windows" ]; then
    echo "  .venv\\Scripts\\activate.bat"
else
    echo "  source .venv/bin/activate"
fi
echo "  python -m uvicorn app.main:app --host 0.0.0.0 --port 8000"
echo ""
echo "Then open http://localhost:8000 in your browser."
