"""Configuration management for ResolveAI."""
import os
import secrets
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = os.getenv("RESOLVEAI_DB", str(BASE_DIR / "resolveai.db"))
UPLOADS_DIR = os.getenv("RESOLVEAI_UPLOADS", str(BASE_DIR / "uploads"))
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("RESOLVEAI_MODEL", "openai/gpt-oss-120b")
HOST = os.getenv("RESOLVEAI_HOST", "127.0.0.1")
PORT = int(os.getenv("RESOLVEAI_PORT", "8000"))
DEBUG = os.getenv("RESOLVEAI_DEBUG", "false").lower() == "true"

# API authentication
API_KEY = os.getenv("RESOLVEAI_API_KEY", "")
RATE_LIMIT_REQUESTS_PER_MINUTE = int(os.getenv("RATE_LIMIT_RPM", "60"))
RATE_LIMIT_BURST = int(os.getenv("RATE_LIMIT_BURST", "10"))

# SLA targets (in hours) by priority
SLA_TARGETS_HOURS = {
    "low": 72,
    "medium": 48,
    "high": 24,
    "urgent": 4,
}

# Email notifications (optional)
EMAIL_HOST = os.getenv("EMAIL_HOST", "")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_USER = os.getenv("EMAIL_USER", "")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD", "")
EMAIL_FROM = os.getenv("EMAIL_FROM", "noreply@resolveai.local")
EMAIL_TO = os.getenv("EMAIL_TO", "")
