"""Tests for exact-match keys and approximate usage."""

import fakeredis.aioredis

from app.models.requests import ChatMessage
from app.providers.base import ProviderResult
from app.services.cache import ResponseCache
from app.services.usage import UsageEvent, UsageService, estimate_tokens


async def test_cache_key_is_deterministic_and_round_trips() -> None:
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    cache = ResponseCache(redis, ttl_seconds=30)
    messages = [ChatMessage(role="user", content="[REDACTED_EMAIL]")]
    arguments = {
        "messages": messages,
        "model": "mock-model",
        "temperature": 0.2,
        "max_tokens": 100,
    }
    first = cache.make_key(**arguments)
    second = cache.make_key(**arguments)
    result = ProviderResult(content="safe result", model="mock-model", provider="mock")

    assert first == second
    assert await cache.get(first) is None
    await cache.set(first, result)
    assert await cache.get(first) == result
    await redis.aclose()


async def test_usage_aggregation_and_estimated_cost() -> None:
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    usage = UsageService(redis, estimated_cost_per_1k_tokens=1.0)
    await usage.record("client", UsageEvent(input_tokens=10, output_tokens=6))
    await usage.record(
        "client",
        UsageEvent(blocked=True, cache_hit=True, input_tokens=4),
    )

    totals = await usage.totals("client")

    assert totals.total_requests == 2
    assert totals.blocked_requests == 1
    assert totals.cache_hits == 1
    assert totals.estimated_input_tokens == 14
    assert totals.estimated_output_tokens == 6
    assert totals.estimated_cost == 0.02
    assert estimate_tokens("12345") == 2
    await redis.aclose()
