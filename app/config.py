"""Configuration management for ResolveAI."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = os.getenv("RESOLVEAI_DB", str(BASE_DIR / "resolveai.db"))
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("RESOLVEAI_MODEL", "openai/gpt-oss-120b")
HOST = os.getenv("RESOLVEAI_HOST", "127.0.0.1")
PORT = int(os.getenv("RESOLVEAI_PORT", "8000"))
DEBUG = os.getenv("RESOLVEAI_DEBUG", "false").lower() == "true"
