#!/bin/bash
# ResolveAI - Quick setup script
set -e

echo "Setting up ResolveAI..."

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Initialize database (happens automatically on first run)
echo ""
echo "Setup complete!"
echo ""
echo "To start ResolveAI:"
echo "  source .venv/bin/activate"
echo "  python -m uvicorn app.main:app --host 0.0.0.0 --port 8000"
echo ""
echo "Then open http://localhost:8000 in your browser."
