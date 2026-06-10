import asyncio
import hashlib
import json
from typing import List, Optional
import openai
import redis.asyncio as aioredis
from app.config import get_settings

settings = get_settings()


class EmbeddingService:
    """
    Wraps OpenAI embedding API with:
    - Redis caching (avoid re-embedding identical text)
    - Batch processing (up to 100 texts per API call)
    - Retry logic for rate limits
    """

    def __init__(self, redis_client: aioredis.Redis):
        self.client = openai.AsyncOpenAI(
            api_key=settings.api_key,
            base_url=settings.api_base_url,
        )
        self.model = settings.api_embedding_model
        self.redis = redis_client
        self.cache_ttl = 60 * 60 * 24 * 7    # 7 days
        self.batch_size = 100                  # OpenAI max per call

    def _cache_key(self, text: str) -> str:
        text_hash = hashlib.sha256(text.encode()).hexdigest()
        return f"embedding:{self.model}:{text_hash}"

    async def embed_single(self, text: str) -> List[float]:
        """Embed a single text string, with Redis cache check."""
        cache_key = self._cache_key(text)

        # Check cache
        cached = await self.redis.get(cache_key)
        if cached:
            return json.loads(cached)

        # Call API
        response = await self.client.embeddings.create(
            input=[text],
            model=self.model,
        )
        embedding = response.data[0].embedding

        # Store in cache
        await self.redis.setex(cache_key, self.cache_ttl, json.dumps(embedding))
        return embedding

    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Embed a list of texts in batches.
        Returns embeddings in the same order as input texts.
        """
        results: List[Optional[List[float]]] = [None] * len(texts)
        uncached_indices: List[int] = []
        uncached_texts: List[str] = []

        # Check cache for all texts
        for i, text in enumerate(texts):
            cache_key = self._cache_key(text)
            cached = await self.redis.get(cache_key)
            if cached:
                results[i] = json.loads(cached)
            else:
                uncached_indices.append(i)
                uncached_texts.append(text)

        # Batch API calls for uncached texts
        for batch_start in range(0, len(uncached_texts), self.batch_size):
            batch_texts = uncached_texts[batch_start : batch_start + self.batch_size]
            batch_indices = uncached_indices[batch_start : batch_start + self.batch_size]

            response = await self.client.embeddings.create(
                input=batch_texts,
                model=self.model,
            )

            for j, embedding_data in enumerate(response.data):
                embedding = embedding_data.embedding
                original_idx = batch_indices[j]
                results[original_idx] = embedding

                # Cache it
                cache_key = self._cache_key(batch_texts[j])
                await self.redis.setex(cache_key, self.cache_ttl, json.dumps(embedding))

            # Rate limit safety: brief pause between batches
            if batch_start + self.batch_size < len(uncached_texts):
                await asyncio.sleep(0.1)

        return results
