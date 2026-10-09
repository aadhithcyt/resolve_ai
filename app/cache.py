"""In-memory cache for Groq API responses to reduce quota usage."""
import time
import hashlib
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Simple in-memory cache: {cache_key: {"response": data, "expires": timestamp}}
_cache: dict[str, dict] = {}
DEFAULT_TTL = 300  # 5 minutes


def _make_key(messages: list, tools: list = None, temperature: float = 0.7) -> str:
    """Create a cache key from request parameters."""
    key_data = str(messages) + str(tools) + str(temperature)
    return hashlib.sha256(key_data.encode()).hexdigest()[:12]


def get_cached_response(messages: list, tools: list = None, temperature: float = 0.7) -> Optional[dict]:
    """Get cached response if available and not expired."""
    key = _make_key(messages, tools, temperature)
    if key in _cache:
        entry = _cache[key]
        if time.time() < entry["expires"]:
            logger.debug(f"Cache hit for key {key}")
            return entry["response"]
        else:
            # Expired, remove
            del _cache[key]
    return None


def cache_response(messages: list, response: dict, tools: list = None, temperature: float = 0.7, ttl: int = DEFAULT_TTL) -> None:
    """Cache a response with TTL."""
    key = _make_key(messages, tools, temperature)
    _cache[key] = {
        "response": response,
        "expires": time.time() + ttl,
    }
    logger.debug(f"Cached response for key {key}, TTL={ttl}s")


def clear_cache() -> None:
    """Clear all cached responses."""
    _cache.clear()
    logger.info("Cache cleared")


def get_cache_stats() -> dict:
    """Get cache statistics."""
    now = time.time()
    total = len(_cache)
    expired = sum(1 for e in _cache.values() if e["expires"] <= now)
    valid = total - expired
    return {
        "total_entries": total,
        "valid_entries": valid,
        "expired_entries": expired,
    }
