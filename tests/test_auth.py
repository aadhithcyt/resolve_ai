"""Tests for API key authentication and rate limiting."""
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.auth import verify_api_key, _rate_limit_check, _burst_check, _get_client_key
from unittest.mock import MagicMock


@pytest.mark.asyncio
async def test_health_endpoint_no_auth_required():
    """Health endpoint should work without API key."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_api_key_auth_disabled_by_default():
    """When API_KEY is empty, all endpoints should be accessible."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/api/customers/")
        assert resp.status_code == 200


@pytest.mark.asyncio
async def test_verify_api_key_missing_header():
    """Should reject request without X-API-Key when auth is enabled."""
    from app import auth
    original_key = auth.API_KEY
    auth.API_KEY = "test-secret-key"

    try:
        request = MagicMock()
        request.url.path = "/api/customers/"
        request.headers = {}

        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            await verify_api_key(request)
        assert exc_info.value.status_code == 401
    finally:
        auth.API_KEY = original_key


@pytest.mark.asyncio
async def test_verify_api_key_invalid_key():
    """Should reject request with invalid API key."""
    from app import auth
    original_key = auth.API_KEY
    auth.API_KEY = "test-secret-key"

    try:
        request = MagicMock()
        request.url.path = "/api/customers/"
        request.headers = {"X-API-Key": "wrong-key"}

        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            await verify_api_key(request)
        assert exc_info.value.status_code == 403
    finally:
        auth.API_KEY = original_key


@pytest.mark.asyncio
async def test_verify_api_key_valid_key():
    """Should accept request with valid API key."""
    from app import auth
    original_key = auth.API_KEY
    auth.API_KEY = "test-secret-key"

    try:
        request = MagicMock()
        request.url.path = "/api/customers/"
        request.headers = {"X-API-Key": "test-secret-key"}

        # Should not raise
        await verify_api_key(request)
    finally:
        auth.API_KEY = original_key


@pytest.mark.asyncio
async def test_verify_api_key_skips_health():
    """Health endpoint should skip auth even when enabled."""
    from app import auth
    original_key = auth.API_KEY
    auth.API_KEY = "test-secret-key"

    try:
        request = MagicMock()
        request.url.path = "/health"
        request.headers = {}

        # Should not raise
        await verify_api_key(request)
    finally:
        auth.API_KEY = original_key


def test_rate_limit_allows_under_limit():
    """Rate limit should allow requests under the limit."""
    import time
    client_key = "test-client-rl"
    # Clear any existing state
    from app.auth import _rate_store, _burst_store
    _rate_store.pop(client_key, None)
    _burst_store.pop(f"burst:{client_key}", None)
    _burst_store.pop(f"burst_ts:{client_key}", None)

    # Should allow requests under the limit
    for _ in range(5):
        assert _burst_check(client_key) is True
        assert _rate_limit_check(client_key) is True


def test_rate_limit_blocks_over_limit():
    """Rate limit should block requests over the burst limit."""
    from app.auth import _rate_store, _burst_store
    client_key = "test-client-rl-block"
    _rate_store.pop(client_key, None)
    _burst_store.pop(f"burst:{client_key}", None)
    _burst_store.pop(f"burst_ts:{client_key}", None)

    # Use configured burst limit
    from app.config import RATE_LIMIT_BURST
    # Exhaust burst
    for _ in range(RATE_LIMIT_BURST):
        _burst_check(client_key)

    # Next should fail
    assert _burst_check(client_key) is False


# ─── Regression: middleware exceptions must become HTTP responses, not 500 ──
# An HTTPException raised inside BaseHTTPMiddleware.dispatch bypasses FastAPI's
# exception handlers and escapes the ASGI stack, so the client saw a 500.
# These tests go through the real ASGI stack to catch that class of bug.


@pytest.mark.asyncio
async def test_rate_limit_returns_429_not_500():
    """Exceeding the rate limit must yield 429, never 500."""
    from app import auth
    from app import config
    from app.database import init_db

    await init_db()
    auth._rate_store.clear()
    auth._burst_store.clear()

    # conftest disables rate limiting globally; re-enable it for this test only.
    original_rpm = config.RATE_LIMIT_REQUESTS_PER_MINUTE
    original_burst = config.RATE_LIMIT_BURST
    config.RATE_LIMIT_REQUESTS_PER_MINUTE = 3
    config.RATE_LIMIT_BURST = 2
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            codes = set()
            for _ in range(20):
                r = await ac.get("/api/customers/")
                codes.add(r.status_code)
                if r.status_code == 429:
                    break
    finally:
        config.RATE_LIMIT_REQUESTS_PER_MINUTE = original_rpm
        config.RATE_LIMIT_BURST = original_burst
        auth._rate_store.clear()
        auth._burst_store.clear()

    assert 429 in codes, f"expected a 429, saw {codes}"
    assert 500 not in codes, f"rate limiting produced a 500: {codes}"


@pytest.mark.asyncio
async def test_missing_api_key_returns_401_not_500():
    """Missing API key must yield 401, never 500."""
    from app import auth
    from app.database import init_db

    await init_db()
    auth._rate_store.clear()
    auth._burst_store.clear()
    original = auth.API_KEY
    auth.API_KEY = "regression-secret-key"
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            r = await ac.get("/api/customers/")
        assert r.status_code == 401, f"expected 401, got {r.status_code}"
    finally:
        auth.API_KEY = original


@pytest.mark.asyncio
async def test_wrong_api_key_returns_403_not_500():
    """Invalid API key must yield 403, never 500."""
    from app import auth
    from app.database import init_db

    await init_db()
    auth._rate_store.clear()
    auth._burst_store.clear()
    original = auth.API_KEY
    auth.API_KEY = "regression-secret-key"
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            r = await ac.get("/api/customers/", headers={"X-API-Key": "nope"})
        assert r.status_code == 403, f"expected 403, got {r.status_code}"
    finally:
        auth.API_KEY = original


@pytest.mark.asyncio
async def test_health_responds_to_head():
    """HEAD /health must return 200, not 405.

    Load balancers, container orchestrators and uptime monitors commonly probe
    liveness with HEAD. A 405 makes the service look unhealthy to them.
    """
    from app.database import init_db

    await init_db()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.head("/health")
    assert r.status_code == 200, f"HEAD /health returned {r.status_code}, expected 200"


@pytest.mark.asyncio
async def test_health_accessible_without_credentials():
    """GET /health must never require auth, so monitors can reach it."""
    from app import auth
    from app.database import init_db

    await init_db()
    original = auth.API_KEY
    auth.API_KEY = "monitor-should-not-need-this"
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            r = await ac.get("/health")
        assert r.status_code == 200
    finally:
        auth.API_KEY = original
