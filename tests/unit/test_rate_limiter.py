"""Boundary and reset tests for the Redis fixed-window limiter."""

import fakeredis.aioredis

from app.services.rate_limiter import FixedWindowRateLimiter


async def test_below_at_and_above_limit() -> None:
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    limiter = FixedWindowRateLimiter(redis, limit=2, window_seconds=60, clock=lambda: 10)

    below = await limiter.check("client")
    at_limit = await limiter.check("client")
    above = await limiter.check("client")

    assert below.allowed and below.remaining == 1
    assert at_limit.allowed and at_limit.remaining == 0
    assert not above.allowed and above.remaining == 0
    assert above.headers()["Retry-After"] == "50"
    await redis.aclose()


async def test_window_reset() -> None:
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    now = [59.0]
    limiter = FixedWindowRateLimiter(
        redis,
        limit=1,
        window_seconds=60,
        clock=lambda: now[0],
    )

    assert (await limiter.check("client")).allowed
    assert not (await limiter.check("client")).allowed
    now[0] = 60.0
    reset = await limiter.check("client")

    assert reset.allowed
    assert reset.remaining == 0
    await redis.aclose()
