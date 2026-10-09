"""API key and JWT authentication middleware and helpers."""
import time
import hashlib
import hmac
from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware

from .config import API_KEY


# ─── API Key Auth ───────────────────────────────────────────────────────────

async def verify_api_key(request: Request) -> None:
    """Verify the X-API-Key header or JWT Bearer token.

    Accepts either:
    - X-API-Key header (if API_KEY is configured)
    - Authorization: Bearer <jwt_token>

    Skips auth entirely if no API_KEY is configured AND no Bearer token is present.
    """
    # Skip auth for health endpoint
    if request.url.path == "/health":
        return

    api_key_header = request.headers.get("X-API-Key", "")
    auth_header = request.headers.get("Authorization", "")

    # Try Bearer token first
    if auth_header.startswith("Bearer "):
        from .jwt_auth import decode_access_token
        token = auth_header[7:]
        try:
            payload = decode_access_token(token)
            request.state.agent = {
                "id": int(payload["sub"]),
                "email": payload["email"],
                "role": payload["role"],
            }
            return
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
                headers={"WWW-Authenticate": "Bearer"},
            )

    # Fall back to API key
    if not API_KEY:
        # No API key configured and no bearer token -> auth disabled
        if not api_key_header:
            return

    if not api_key_header:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-API-Key header or Bearer token",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    if not hmac.compare_digest(api_key_header, API_KEY):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API key",
        )


# ─── Simple in-memory rate limiter (per client IP) ─────────────────────────

# {client_key: [(timestamp, count), ...]}
_rate_store: dict[str, list[float]] = {}
_burst_store: dict[str, int] = {}


def _get_client_key(request: Request) -> str:
    """Get a key for rate limiting: prefer X-API-Key or Bearer token, fall back to IP."""
    api_key = request.headers.get("X-API-Key", "")
    if api_key:
        return hashlib.sha256(api_key.encode()).hexdigest()[:16]
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        return hashlib.sha256(token.encode()).hexdigest()[:16]
    return request.client.host if request.client else "unknown"


def _get_rpm() -> int:
    """Read rate limit RPM from config at call time (respects env overrides)."""
    from .config import RATE_LIMIT_REQUESTS_PER_MINUTE
    return RATE_LIMIT_REQUESTS_PER_MINUTE


def _get_burst() -> int:
    """Read rate limit burst from config at call time."""
    from .config import RATE_LIMIT_BURST
    return RATE_LIMIT_BURST


def _rate_limit_check(client_key: str) -> bool:
    """Check if the client has exceeded the rate limit. Returns True if allowed."""
    now = time.time()
    window = 60.0  # 1 minute window
    rpm = _get_rpm()

    # Clean old entries
    if client_key in _rate_store:
        _rate_store[client_key] = [
            ts for ts in _rate_store[client_key] if now - ts < window
        ]
    else:
        _rate_store[client_key] = []

    # Sliding window count
    count = len(_rate_store[client_key])
    if count >= rpm:
        return False

    _rate_store[client_key].append(now)
    return True


def _burst_check(client_key: str) -> bool:
    """Burst allowance check."""
    from .config import RATE_LIMIT_BURST
    now = time.time()
    key = f"burst:{client_key}"
    burst_max = _get_burst()

    if key not in _burst_store:
        _burst_store[key] = burst_max

    last_ts = _burst_store.get(f"burst_ts:{client_key}", 0.0)
    if now - last_ts >= 1:
        # Refill 1 token per second
        elapsed = now - last_ts
        _burst_store[key] = min(
            burst_max,
            _burst_store[key] + int(elapsed),
        )
        _burst_store[f"burst_ts:{client_key}"] = now

    if _burst_store[key] <= 0:
        return False

    _burst_store[key] -= 1
    return True


# ─── Middleware ─────────────────────────────────────────────────────────────

class AuthMiddleware(BaseHTTPMiddleware):
    """Middleware that enforces API key auth and rate limiting."""

    async def dispatch(self, request: Request, call_next):
        # Verify API key
        await verify_api_key(request)

        # Rate limiting (skip for health)
        if request.url.path != "/health":
            client_key = _get_client_key(request)
            if not _burst_check(client_key) or not _rate_limit_check(client_key):
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Rate limit exceeded",
                    headers={"Retry-After": "60"},
                )

        response = await call_next(request)
        return response
