"""Run the gateway locally with in-memory Redis and the offline mock provider.

This beginner-friendly launcher is for learning and demonstration only. All
cache, rate-limit, and usage data disappears when the process stops.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import fakeredis.aioredis
import uvicorn
from fastapi import FastAPI

from app.config import Settings
from app.main import build_services, create_app

settings = Settings(
    environment="development",
    api_keys=["local-development-key"],
    provider="mock",
)
app = create_app(settings)


@asynccontextmanager
async def demo_lifespan(application: FastAPI) -> AsyncIterator[None]:
    """Inject an in-memory Redis replacement for a zero-setup demonstration."""
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    application.state.services = build_services(settings, redis)
    yield
    await redis.aclose()


app.router.lifespan_context = demo_lifespan


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
