"""Tests for JWT authentication for support agents."""
import pytest
import pytest_asyncio
import jwt
from datetime import datetime, timedelta, timezone
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.jwt_auth import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
    JWT_SECRET_KEY,
    JWT_ALGORITHM,
    JWT_ACCESS_TOKEN_EXPIRE_HOURS,
)
from app.database import get_db
from app.auth import verify_api_key
from unittest.mock import MagicMock
from fastapi import HTTPException


# ─── Fixtures ────────────────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def admin_agent():
    """Create an admin agent in the database."""
    async with get_db() as db:
        password_hash = hash_password("adminpass123")
        cursor = await db.execute(
            """INSERT INTO agents (email, password_hash, name, role)
               VALUES (?, ?, ?, ?)""",
            ("admin@test.com", password_hash, "Admin User", "admin"),
        )
        await db.commit()
        return {"id": cursor.lastrowid, "email": "admin@test.com", "role": "admin"}


@pytest_asyncio.fixture
async def regular_agent():
    """Create a regular agent in the database."""
    async with get_db() as db:
        password_hash = hash_password("agentpass123")
        cursor = await db.execute(
            """INSERT INTO agents (email, password_hash, name, role)
               VALUES (?, ?, ?, ?)""",
            ("agent@test.com", password_hash, "Regular Agent", "agent"),
        )
        await db.commit()
        return {"id": cursor.lastrowid, "email": "agent@test.com", "role": "agent" }


# ─── Password hashing tests ─────────────────────────────────────────────────


def test_hash_password_returns_hash():
    """hash_password should return a bcrypt hash string."""
    hash1 = hash_password("mypassword")
    assert isinstance(hash1, str)
    assert len(hash1) > 20


def test_hash_password_produces_different_hashes():
    """Same password should produce different hashes (due to salt)."""
    hash1 = hash_password("mypassword")
    hash2 = hash_password("mypassword")
    assert hash1 != hash2


def test_verify_password_correct():
    """verify_password should return True for correct password."""
    hash_val = hash_password("mypassword")
    assert verify_password("mypassword", hash_val) is True


def test_verify_password_incorrect():
    """verify_password should return False for incorrect password."""
    hash_val = hash_password("mypassword")
    assert verify_password("wrongpassword", hash_val) is False


# ─── JWT token creation/verification tests ──────────────────────────────────


def test_create_access_token_returns_jwt():
    """create_access_token should return a valid JWT string."""
    token = create_access_token(1, "test@example.com", "agent")
    assert isinstance(token, str)
    parts = token.split(".")
    assert len(parts) == 3


def test_decode_access_token_valid():
    """decode_access_token should return payload for valid token."""
    token = create_access_token(1, "test@example.com", "agent")
    payload = decode_access_token(token)
    assert payload["sub"] == "1"
    assert payload["email"] == "test@example.com"
    assert payload["role"] == "agent"


def test_decode_access_token_expired():
    """decode_access_token should raise HTTPException for expired token."""
    now = datetime.now(timezone.utc) - timedelta(hours=25)
    payload = {
        "sub": "1",
        "email": "test@example.com",
        "role": "agent",
        "iat": now,
        "exp": now + timedelta(hours=1),
    }
    token = jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    with pytest.raises(HTTPException) as exc_info:
        decode_access_token(token)
    assert exc_info.value.status_code == 401


def test_decode_access_token_invalid():
    """decode_access_token should raise HTTPException for invalid token."""
    with pytest.raises(HTTPException) as exc_info:
        decode_access_token("invalid.token.here")
    assert exc_info.value.status_code == 401


def test_jwt_expiry_is_24_hours():
    """Token should expire in 24 hours."""
    token = create_access_token(1, "test@example.com", "agent")
    payload = decode_access_token(token)
    iat = datetime.fromtimestamp(payload["iat"], tz=timezone.utc)
    exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
    delta = exp - iat
    assert delta.total_seconds() == pytest.approx(JWT_ACCESS_TOKEN_EXPIRE_HOURS * 3600, abs=5)


# ─── Login endpoint tests ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_login_success(admin_agent):
    """Login with valid credentials should return a token."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post("/api/auth/login", json={
            "email": "admin@test.com",
            "password": "adminpass123",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["expires_in"] == JWT_ACCESS_TOKEN_EXPIRE_HOURS * 3600


@pytest.mark.asyncio
async def test_login_invalid_email():
    """Login with non-existent email should return 401."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post("/api/auth/login", json={
            "email": "nonexistent@test.com",
            "password": "somepass",
        })
        assert resp.status_code == 401


@pytest.mark.asyncio
async def test_login_wrong_password(admin_agent):
    """Login with wrong password should return 401."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post("/api/auth/login", json={
            "email": "admin@test.com",
            "password": "wrongpassword",
        })
        assert resp.status_code == 401


@pytest.mark.asyncio
async def test_login_missing_fields():
    """Login with missing fields should return 422."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post("/api/auth/login", json={
            "email": "admin@test.com",
        })
        assert resp.status_code == 422


# ─── Register endpoint tests ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_register_success(admin_agent):
    """Admin should be able to register a new agent."""
    # First login as admin
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        login_resp = await ac.post("/api/auth/login", json={
            "email": "admin@test.com",
            "password": "adminpass123",
        })
        token = login_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        resp = await ac.post("/api/auth/register", headers=headers, json={
            "email": "newagent@test.com",
            "password": "newpass123",
            "name": "New Agent",
            "role": "agent",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["email"] == "newagent@test.com"
        assert data["name"] == "New Agent"
        assert data["role"] == "agent"
        assert "id" in data


@pytest.mark.asyncio
async def test_register_requires_admin(regular_agent):
    """Non-admin agent should not be able to register new agents."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        login_resp = await ac.post("/api/auth/login", json={
            "email": "agent@test.com",
            "password": "agentpass123",
        })
        token = login_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        resp = await ac.post("/api/auth/register", headers=headers, json={
            "email": "another@test.com",
            "password": "pass123",
            "name": "Another Agent",
            "role": "agent",
        })
        assert resp.status_code == 403


@pytest.mark.asyncio
async def test_register_duplicate_email(admin_agent):
    """Registering with an existing email should return 409."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        login_resp = await ac.post("/api/auth/login", json={
            "email": "admin@test.com",
            "password": "adminpass123",
        })
        token = login_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        resp = await ac.post("/api/auth/register", headers=headers, json={
            "email": "admin@test.com",
            "password": "newpass123",
            "name": "Duplicate",
            "role": "agent",
        })
        assert resp.status_code == 409


@pytest.mark.asyncio
async def test_register_requires_auth():
    """Register without auth should return 401."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post("/api/auth/register", json={
            "email": "new@test.com",
            "password": "pass123",
            "name": "New Agent",
            "role": "agent",
        })
        assert resp.status_code == 401


# ─── Middleware / Bearer token tests ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_bearer_token_accepted(admin_agent):
    """Valid Bearer token should be accepted by middleware."""
    token = create_access_token(admin_agent["id"], admin_agent["email"], admin_agent["role"])
    request = MagicMock()
    request.url.path = "/api/customers/"
    request.headers = {"Authorization": f"Bearer {token}"}
    request.state = MagicMock()

    # Should not raise
    await verify_api_key(request)


@pytest.mark.asyncio
async def test_bearer_token_invalid_rejected():
    """Invalid Bearer token should be rejected."""
    request = MagicMock()
    request.url.path = "/api/customers/"
    request.headers = {"Authorization": "Bearer invalid.token.here"}
    request.state = MagicMock()

    with pytest.raises(HTTPException) as exc_info:
        await verify_api_key(request)
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_bearer_token_expired_rejected():
    """Expired Bearer token should be rejected."""
    now = datetime.now(timezone.utc) - timedelta(hours=25)
    payload = {
        "sub": "1",
        "email": "test@example.com",
        "role": "agent",
        "iat": now,
        "exp": now + timedelta(hours=1),
    }
    token = jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)

    request = MagicMock()
    request.url.path = "/api/customers/"
    request.headers = {"Authorization": f"Bearer {token}"}
    request.state = MagicMock()

    with pytest.raises(HTTPException) as exc_info:
        await verify_api_key(request)
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_api_key_still_works():
    """X-API-Key should still work when configured."""
    from app import auth
    original_key = auth.API_KEY
    auth.API_KEY = "test-secret-key"

    try:
        request = MagicMock()
        request.url.path = "/api/customers/"
        request.headers = {"X-API-Key": "test-secret-key"}
        request.state = MagicMock()

        # Should not raise
        await verify_api_key(request)
    finally:
        auth.API_KEY = original_key


@pytest.mark.asyncio
async def test_api_key_invalid_rejected():
    """Invalid X-API-Key should be rejected."""
    from app import auth
    original_key = auth.API_KEY
    auth.API_KEY = "test-secret-key"

    try:
        request = MagicMock()
        request.url.path = "/api/customers/"
        request.headers = {"X-API-Key": "wrong-key"}
        request.state = MagicMock()

        with pytest.raises(HTTPException) as exc_info:
            await verify_api_key(request)
        assert exc_info.value.status_code == 403
    finally:
        auth.API_KEY = original_key


# ─── Agent table tests ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_agents_table_exists():
    """Agents table should exist in the database."""
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='agents'"
        )
        row = await cursor.fetchone()
        assert row is not None


@pytest.mark.asyncio
async def test_agents_table_has_correct_columns():
    """Agents table should have the required columns."""
    async with get_db() as db:
        cursor = await db.execute("PRAGMA table_info(agents)")
        rows = await cursor.fetchall()
        columns = {row[1] for row in rows}
        assert "id" in columns
        assert "email" in columns
        assert "password_hash" in columns
        assert "name" in columns
        assert "role" in columns
        assert "created_at" in columns


@pytest.mark.asyncio
async def test_agent_role_check_constraint():
    """Agents table should enforce role check constraint."""
    async with get_db() as db:
        with pytest.raises(Exception):
            await db.execute(
                """INSERT INTO agents (email, password_hash, name, role)
                   VALUES (?, ?, ?, ?)""",
                ("bad@test.com", "hash", "Bad Role", "superadmin"),
            )
            await db.commit()


# ─── Integration: Bearer token on protected endpoints ────────────────────────


@pytest.mark.asyncio
async def test_bearer_token_on_protected_endpoint(admin_agent):
    """Valid Bearer token should grant access to protected endpoints."""
    token = create_access_token(admin_agent["id"], admin_agent["email"], admin_agent["role"])
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get(
            "/api/customers/",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200


@pytest.mark.asyncio
async def test_no_auth_on_protected_endpoint():
    """No auth headers at all should still work when API_KEY is empty (auth disabled)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/api/customers/")
        assert resp.status_code == 200


@pytest.mark.asyncio
async def test_bearer_token_sets_request_state(admin_agent):
    """Middleware should set request.state.agent when Bearer token is valid."""
    token = create_access_token(admin_agent["id"], admin_agent["email"], admin_agent["role"])
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == "admin@test.com"
        assert data["role"] == "admin"


# ─── Role-based access tests ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_admin_can_register_agent(admin_agent):
    """Admin role should allow registering new agents."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        login_resp = await ac.post("/api/auth/login", json={
            "email": "admin@test.com",
            "password": "adminpass123",
        })
        token = login_resp.json()["access_token"]

        resp = await ac.post(
            "/api/auth/register",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "email": "created@test.com",
                "password": "created123",
                "name": "Created Agent",
                "role": "agent",
            },
        )
        assert resp.status_code == 201


@pytest.mark.asyncio
async def test_agent_cannot_register_agent(regular_agent):
    """Agent role should NOT allow registering new agents."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        login_resp = await ac.post("/api/auth/login", json={
            "email": "agent@test.com",
            "password": "agentpass123",
        })
        token = login_resp.json()["access_token"]

        resp = await ac.post(
            "/api/auth/register",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "email": "shouldfail@test.com",
                "password": "pass123",
                "name": "Should Fail",
                "role": "agent",
            },
        )
        assert resp.status_code == 403


@pytest.mark.asyncio
async def test_get_me_endpoint(admin_agent):
    """GET /api/auth/me should return current agent info."""
    token = create_access_token(admin_agent["id"], admin_agent["email"], admin_agent["role"])
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == admin_agent["id"]
        assert data["email"] == "admin@test.com"
        assert data["name"] == "Admin User"
        assert data["role"] == "admin"



