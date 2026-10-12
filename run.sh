#!/bin/bash
# ResolveAI - Quick start script
cd "$(dirname "$0")"
source .venv/bin/activate
exec python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
