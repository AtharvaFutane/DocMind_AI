import json
from typing import Any, Optional
import redis.asyncio as aioredis


class ResponseCache:
    """
    Redis-backed cache for:
    1. RAG response cache (1 hour TTL) — avoid re-running expensive LLM calls for identical questions
    2. Embedding cache (7 days TTL) — handled in EmbeddingService
    3. Rate limiting keys

    Cache key patterns:
    - rag:{question_text}          → full RAG response
    - embedding:{model}:{hash}     → vector (handled in embedder.py)
    - ratelimit:{ip}:{minute}      → request count for rate limiting
    """

    def __init__(self, redis_client: aioredis.Redis):
        self.redis = redis_client

    async def get(self, key: str) -> Optional[Any]:
        """Get a value from cache, returns None on miss."""
        value = await self.redis.get(key)
        if value:
            return json.loads(value)
        return None

    async def set(self, key: str, value: Any, ttl: int = 3600):
        """Set a value in cache with TTL (default 1 hour)."""
        await self.redis.setex(key, ttl, json.dumps(value))

    async def delete(self, key: str):
        """Delete a key from cache."""
        await self.redis.delete(key)

    async def invalidate_prefix(self, prefix: str):
        """Invalidate all keys matching a prefix (e.g., on re-crawl)."""
        async for key in self.redis.scan_iter(f"{prefix}*"):
            await self.redis.delete(key)

    async def check_rate_limit(self, identifier: str, limit: int = 20, window: int = 60) -> bool:
        """
        Simple sliding window rate limiter.
        Returns True if request is allowed, False if rate limited.
        """
        key = f"ratelimit:{identifier}"
        pipe = self.redis.pipeline()
        pipe.incr(key)
        pipe.expire(key, window)
        results = await pipe.execute()
        count = results[0]
        return count <= limit
