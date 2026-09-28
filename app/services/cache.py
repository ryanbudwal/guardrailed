"""Exact-match Redis caching using only sanitized request data."""

import hashlib
import json
from dataclasses import asdict

from redis.asyncio import Redis

from app.models.requests import ChatMessage
from app.providers.base import ProviderResult


class ResponseCache:
    """Read and write provider-neutral completion results with a bounded TTL."""

    def __init__(self, redis: Redis, ttl_seconds: int) -> None:
        self.redis = redis
        self.ttl_seconds = ttl_seconds

    @staticmethod
    def make_key(
        *,
        messages: list[ChatMessage],
        model: str,
        temperature: float,
        max_tokens: int,
    ) -> str:
        """Hash canonical JSON containing sanitized messages and generation settings."""
        payload = {
            "messages": [message.model_dump() for message in messages],
            "model": model,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        digest = hashlib.sha256(canonical.encode()).hexdigest()
        return f"llm-cache:{digest}"

    async def get(self, key: str) -> ProviderResult | None:
        """Return a cached provider result when present."""
        raw = await self.redis.get(key)
        if raw is None:
            return None
        data = json.loads(raw)
        return ProviderResult(**data)

    async def set(self, key: str, result: ProviderResult) -> None:
        """Cache only the sanitized provider result."""
        await self.redis.set(key, json.dumps(asdict(result)), ex=self.ttl_seconds)
