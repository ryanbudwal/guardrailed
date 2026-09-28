"""Shared offline application fixtures."""

from collections.abc import AsyncIterator

import fakeredis.aioredis
import pytest
from httpx import ASGITransport, AsyncClient

from app.config import Settings
from app.main import build_services, create_app


@pytest.fixture
def settings() -> Settings:
    """Use an isolated API key and generous default limit."""
    return Settings(
        api_keys=["test-key"],
        redis_url="redis://unused",
        rate_limit_requests=10,
        rate_limit_window_seconds=60,
        cache_ttl_seconds=60,
    )


@pytest.fixture
async def redis_client() -> AsyncIterator[fakeredis.aioredis.FakeRedis]:
    """Provide an in-memory Redis implementation with no network access."""
    client = fakeredis.aioredis.FakeRedis(decode_responses=True)
    yield client
    await client.aclose()


@pytest.fixture
async def client(
    settings: Settings,
    redis_client: fakeredis.aioredis.FakeRedis,
) -> AsyncIterator[AsyncClient]:
    """Create a FastAPI client with explicitly injected fake services."""
    application = create_app(settings)
    application.state.services = build_services(settings, redis_client)
    async with AsyncClient(
        transport=ASGITransport(app=application),
        base_url="http://test",
    ) as test_client:
        yield test_client


@pytest.fixture
def auth_headers() -> dict[str, str]:
    """Return valid local authentication."""
    return {"Authorization": "Bearer test-key"}


@pytest.fixture
def chat_payload() -> dict[str, object]:
    """Return a small deterministic completion request."""
    return {
        "model": "mock-model",
        "messages": [{"role": "user", "content": "Help me write a greeting."}],
        "max_tokens": 100,
        "temperature": 0.2,
    }
