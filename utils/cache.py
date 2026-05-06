"""
utils/cache.py
--------------
Redis-backed caching layer with async support.
Provides query-level caching, session memory storage, and rate limiting.
"""

import hashlib
import json
import time
from typing import Any, Optional

import redis.asyncio as aioredis

from utils.config import settings
from utils.logger import get_logger, metrics

logger = get_logger(__name__, service="cache")

# ─── Redis Client ─────────────────────────────────────────────────────────────

_redis_client: Optional[aioredis.Redis] = None


async def get_redis() -> aioredis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = aioredis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
            retry_on_timeout=True,
            health_check_interval=30,
        )
        logger.info("redis_connected", url=settings.redis_url)
    return _redis_client


async def close_redis() -> None:
    global _redis_client
    if _redis_client:
        await _redis_client.aclose()
        _redis_client = None
        logger.info("redis_disconnected")


# ─── Cache Key Helpers ────────────────────────────────────────────────────────

def _make_query_cache_key(question: str, agent_type: str, top_k: int) -> str:
    """Deterministic cache key for RAG query results."""
    raw = f"query:{question.strip().lower()}:agent:{agent_type}:k:{top_k}"
    digest = hashlib.sha256(raw.encode()).hexdigest()[:16]
    return f"enterprise_ai:query:{digest}"


def _make_session_key(session_id: str) -> str:
    return f"enterprise_ai:session:{session_id}"


def _make_rate_limit_key(identifier: str) -> str:
    minute_bucket = int(time.time() // 60)
    return f"enterprise_ai:ratelimit:{identifier}:{minute_bucket}"


# ─── Core Cache Operations ────────────────────────────────────────────────────

class CacheService:
    """High-level cache operations wrapping Redis."""

    def __init__(self) -> None:
        self.ttl = settings.cache_ttl_seconds

    async def get_query_result(
        self, question: str, agent_type: str, top_k: int
    ) -> Optional[dict]:
        """Retrieve cached query response if available."""
        try:
            redis = await get_redis()
            key = _make_query_cache_key(question, agent_type, top_k)
            cached = await redis.get(key)
            if cached:
                metrics.increment("cache_hit", service="query")
                logger.debug("cache_hit", key=key)
                return json.loads(cached)
            metrics.increment("cache_miss", service="query")
            return None
        except Exception as exc:
            logger.warning("cache_get_failed", error=str(exc))
            return None

    async def set_query_result(
        self,
        question: str,
        agent_type: str,
        top_k: int,
        result: dict,
        ttl: Optional[int] = None,
    ) -> bool:
        """Store query response with TTL."""
        try:
            redis = await get_redis()
            key = _make_query_cache_key(question, agent_type, top_k)
            await redis.setex(
                key,
                ttl or self.ttl,
                json.dumps(result, default=str),
            )
            logger.debug("cache_set", key=key, ttl=ttl or self.ttl)
            return True
        except Exception as exc:
            logger.warning("cache_set_failed", error=str(exc))
            return False

    async def get_session_memory(self, session_id: str) -> list:
        """Retrieve conversation memory for a session."""
        try:
            redis = await get_redis()
            key = _make_session_key(session_id)
            raw = await redis.get(key)
            return json.loads(raw) if raw else []
        except Exception as exc:
            logger.warning("session_get_failed", session_id=session_id, error=str(exc))
            return []

    async def update_session_memory(
        self,
        session_id: str,
        messages: list,
        window_size: int = 10,
    ) -> None:
        """Persist session memory, trimmed to window size."""
        try:
            redis = await get_redis()
            key = _make_session_key(session_id)
            trimmed = messages[-window_size:]
            await redis.setex(key, 86400, json.dumps(trimmed, default=str))  # 24hr TTL
        except Exception as exc:
            logger.warning("session_set_failed", session_id=session_id, error=str(exc))

    async def invalidate_query_cache(self, pattern: str = "*") -> int:
        """Invalidate cache keys matching pattern. Returns count deleted."""
        try:
            redis = await get_redis()
            full_pattern = f"enterprise_ai:query:{pattern}"
            keys = await redis.keys(full_pattern)
            if keys:
                return await redis.delete(*keys)
            return 0
        except Exception as exc:
            logger.warning("cache_invalidate_failed", error=str(exc))
            return 0

    async def check_rate_limit(
        self, identifier: str, limit: int = None
    ) -> tuple[bool, int]:
        """
        Sliding-window rate limiter.
        Returns (is_allowed, remaining_requests).
        """
        limit = limit or settings.rate_limit_per_minute
        try:
            redis = await get_redis()
            key = _make_rate_limit_key(identifier)
            count = await redis.incr(key)
            if count == 1:
                await redis.expire(key, 60)
            remaining = max(0, limit - count)
            return count <= limit, remaining
        except Exception as exc:
            logger.warning("rate_limit_check_failed", error=str(exc))
            return True, limit  # Fail open

    async def store_metrics_snapshot(self, metrics_data: dict) -> None:
        """Persist metrics snapshot for dashboard retrieval."""
        try:
            redis = await get_redis()
            await redis.setex(
                "enterprise_ai:metrics:latest",
                300,  # 5 minute TTL
                json.dumps(metrics_data, default=str),
            )
        except Exception as exc:
            logger.warning("metrics_store_failed", error=str(exc))

    async def health_check(self) -> bool:
        """Verify Redis connectivity."""
        try:
            redis = await get_redis()
            return await redis.ping()
        except Exception:
            return False


# Global cache service instance
cache_service = CacheService()
