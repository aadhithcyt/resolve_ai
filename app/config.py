"""Configuration management for ResolveAI."""
import os
import secrets
from datetime import datetime, timezone
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


# ─── Timezone-safe timestamp helpers ────────────────────────────────────────
# SQLite's CURRENT_TIMESTAMP and datetime() produce NAIVE strings
# ("2026-10-12 15:48:29") with no offset, while the application writes
# timezone-AWARE ISO strings ("2026-10-12T15:48:29+00:00"). Both formats end up
# in the same columns. Any arithmetic that mixes the two raises TypeError, and
# because it is easy to wrap that in try/except, such a bug can silently kill a
# whole code path (escalation Rule 3 was dead for exactly this reason).
#
# Always parse stored timestamps with parse_ts() and treat the result as UTC.


def parse_ts(value):
    """Parse a stored timestamp into a timezone-aware UTC datetime.

    Accepts aware ISO strings, naive ISO strings (assumed UTC, which is how
    SQLite writes them), a trailing 'Z', and datetime objects. Returns None for
    None or an unparseable value.
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        text = str(value).strip()
        if not text:
            return None
        try:
            dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def utc_now_iso() -> str:
    """Current UTC time as a timezone-aware ISO-8601 string.

    Use this for every timestamp the application writes, so stored values are
    unambiguous and comparable as strings with SQLite's own output.
    """
    return datetime.now(timezone.utc).isoformat()
