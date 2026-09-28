"""Approximate token estimation and Redis usage aggregation."""

import math
from collections.abc import Awaitable
from dataclasses import dataclass
from typing import cast

from redis.asyncio import Redis

from app.models.responses import UsageResponse


def estimate_tokens(text: str) -> int:
    """Estimate tokens as ceil(character count / 4), never claiming exact billing."""
    return math.ceil(len(text) / 4) if text else 0


@dataclass(frozen=True)
class UsageEvent:
    """Fields aggregated for one authenticated chat request."""

    request_count: int = 1
    blocked: bool = False
    cache_hit: bool = False
    input_tokens: int = 0
    output_tokens: int = 0


class UsageService:
    """Store per-key counters in Redis without prompts or raw credentials."""

    def __init__(self, redis: Redis, estimated_cost_per_1k_tokens: float = 0) -> None:
        self.redis = redis
        self.estimated_cost_per_1k_tokens = estimated_cost_per_1k_tokens

    async def record(self, identifier: str, event: UsageEvent) -> None:
        """Atomically increment all counters in one Redis transaction."""
        key = f"usage:{identifier}"
        async with self.redis.pipeline(transaction=True) as pipeline:
            pipeline.hincrby(key, "total_requests", event.request_count)
            pipeline.hincrby(key, "blocked_requests", int(event.blocked))
            pipeline.hincrby(key, "cache_hits", int(event.cache_hit))
            pipeline.hincrby(key, "estimated_input_tokens", event.input_tokens)
            pipeline.hincrby(key, "estimated_output_tokens", event.output_tokens)
            await pipeline.execute()

    async def totals(self, identifier: str) -> UsageResponse:
        """Return zero-filled counters and an explicitly estimated optional cost."""
        operation = cast(
            Awaitable[dict[str | bytes, str | bytes]],
            self.redis.hgetall(f"usage:{identifier}"),
        )
        raw = await operation

        def value(name: str) -> int:
            candidate = raw.get(name) or raw.get(name.encode())
            return int(candidate or 0)

        input_tokens = value("estimated_input_tokens")
        output_tokens = value("estimated_output_tokens")
        estimated_cost = (input_tokens + output_tokens) / 1000 * self.estimated_cost_per_1k_tokens
        return UsageResponse(
            total_requests=value("total_requests"),
            blocked_requests=value("blocked_requests"),
            cache_hits=value("cache_hits"),
            estimated_input_tokens=input_tokens,
            estimated_output_tokens=output_tokens,
            estimated_cost=round(estimated_cost, 6),
        )
