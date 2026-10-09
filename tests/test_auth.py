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
