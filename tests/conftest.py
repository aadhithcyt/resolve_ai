"""Test configuration - use temp database and initialize schema."""
import pytest
import pytest_asyncio
import tempfile
import os
from pathlib import Path

# Set temp DB path before importing app
_tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp_db.close()
os.environ["RESOLVEAI_DB"] = _tmp_db.name

# Disable rate limiting and auth for tests
os.environ["RESOLVEAI_API_KEY"] = ""
os.environ["RATE_LIMIT_RPM"] = "10000"
os.environ["RATE_LIMIT_BURST"] = "10000"


@pytest_asyncio.fixture(autouse=True)
async def init_test_db():
    """Initialize a fresh test database before each test."""
    from app.database import init_db, DB_PATH
    # Delete the temp file so we start fresh
    try:
        os.unlink(DB_PATH)
    except FileNotFoundError:
        pass
    await init_db()
    yield
    # Cleanup
    try:
        os.unlink(DB_PATH)
    except FileNotFoundError:
        pass
