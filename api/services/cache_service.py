"""
Cache Service — Redis-based semantic cache for LLM responses.

Reduces redundant LLM calls by caching responses keyed by content hash.
"""
import hashlib
import json
import logging
from typing import Optional

import redis.asyncio as aioredis
from api.core.config import settings

logger = logging.getLogger(__name__)

# Cache TTL: 1 hour
DEFAULT_TTL = 3600
CACHE_PREFIX = "nexus:cache:"


class CacheService:
    """Redis-based response cache with hash-keyed lookups."""

    def __init__(self):
        self._redis: Optional[aioredis.Redis] = None

    async def _get_redis(self) -> aioredis.Redis:
        if not self._redis:
            self._redis = aioredis.from_url(
                settings.REDIS_URI, decode_responses=True
            )
        return self._redis

    def _make_key(self, prompt: str, model: str) -> str:
        """Generate a deterministic cache key from prompt + model."""
        content = f"{model}::{prompt}"
        digest = hashlib.sha256(content.encode()).hexdigest()[:16]
        return f"{CACHE_PREFIX}{digest}"

    async def get(self, prompt: str, model: str) -> Optional[str]:
        """Check cache for a previous response."""
        try:
            r = await self._get_redis()
            key = self._make_key(prompt, model)
            cached = await r.get(key)

            if cached:
                logger.info(f"Cache HIT: {key[:30]}...")
                data = json.loads(cached)
                return data.get("response")

            logger.debug(f"Cache MISS: {key[:30]}...")
            return None

        except Exception as e:
            logger.warning(f"Cache get failed: {e}")
            return None

    async def set(
        self, prompt: str, model: str, response: str, ttl: int = DEFAULT_TTL
    ):
        """Store a response in the cache."""
        try:
            r = await self._get_redis()
            key = self._make_key(prompt, model)
            data = json.dumps({
                "response": response,
                "model": model,
                "prompt_hash": hashlib.sha256(prompt.encode()).hexdigest()[:8],
            })
            await r.set(key, data, ex=ttl)
            logger.debug(f"Cache SET: {key[:30]}...")

        except Exception as e:
            logger.warning(f"Cache set failed: {e}")

    async def invalidate(self, prompt: str, model: str):
        """Remove a cached entry."""
        try:
            r = await self._get_redis()
            key = self._make_key(prompt, model)
            await r.delete(key)
        except Exception as e:
            logger.warning(f"Cache invalidate failed: {e}")

    async def get_stats(self) -> dict:
        """Get cache statistics."""
        try:
            r = await self._get_redis()
            info = await r.info("keyspace")
            keys = await r.keys(f"{CACHE_PREFIX}*")
            return {
                "cached_responses": len(keys),
                "redis_info": info,
            }
        except Exception as e:
            return {"error": str(e)}


# Singleton instance
cache_service = CacheService()
