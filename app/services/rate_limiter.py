"""Redis-backed fixed-window rate limiting by hashed API-key identifier."""

import time
from collections.abc import Callable
from dataclasses import dataclass

from redis.asyncio import Redis


@dataclass(frozen=True)
class RateLimitResult:
    """Limit state returned for response headers and enforcement."""

    allowed: bool
    limit: int
    remaining: int
    retry_after: int
    reset_after: int

    def headers(self) -> dict[str, str]:
        """Build conventional rate-limit response headers."""
        headers = {
            "X-RateLimit-Limit": str(self.limit),
            "X-RateLimit-Remaining": str(self.remaining),
            "X-RateLimit-Reset": str(self.reset_after),
        }
        if not self.allowed:
            headers["Retry-After"] = str(self.retry_after)
        return headers


class FixedWindowRateLimiter:
    """Count requests in short Redis windows.

    INCR is atomic. Setting expiry is a second operation, an intentional teaching
    trade-off documented in the README; a production version should use Lua.
    """

    def __init__(
        self,
        redis: Redis,
        *,
        limit: int,
        window_seconds: int,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.redis = redis
        self.limit = limit
        self.window_seconds = window_seconds
        self.clock = clock

    async def check(self, identifier: str) -> RateLimitResult:
        """Increment the current bucket and return whether it remains under the limit."""
        now = float(self.clock())
        window = int(now // self.window_seconds)
        reset_after = max(1, int((window + 1) * self.window_seconds - now))
        key = f"rate-limit:{identifier}:{window}"
        count = int(await self.redis.incr(key))
        if count == 1:
            await self.redis.expire(key, self.window_seconds + 1)
        allowed = count <= self.limit
        return RateLimitResult(
            allowed=allowed,
            limit=self.limit,
            remaining=max(0, self.limit - count),
            retry_after=reset_after if not allowed else 0,
            reset_after=reset_after,
        )
