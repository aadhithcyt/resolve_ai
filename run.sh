#!/usr/bin/env bash
# ResolveAI - Quick start script (Linux / macOS / RHEL / Git Bash on Windows)
set -e
cd "$(dirname "$0")"

# Activate the virtual environment if it exists. Do not hard-fail when it is
# missing: on Windows the venv lives in .venv/Scripts, and this script may be
# run from Git Bash without having run setup yet.
if [ -f ".venv/bin/activate" ]; then
    # shellcheck disable=SC1091
    source .venv/bin/activate
elif [ -f ".venv/Scripts/activate" ]; then
    # shellcheck disable=SC1091
    source .venv/Scripts/activate
else
    echo "No virtual environment found at .venv/"
    echo "Run ./setup.sh first (or setup.bat on Windows)."
    echo "Continuing with the system Python..."
fi

exec python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
