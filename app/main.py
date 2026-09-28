"""FastAPI application factory and process entry point."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from redis.asyncio import Redis

from app.api import chat, health, usage
from app.config import Settings, get_settings
from app.dependencies import AppServices
from app.guardrails.pii import RedactionService
from app.guardrails.rules import RuleBasedGuardrailEngine
from app.models.errors import GatewayError
from app.providers.base import LLMProvider
from app.providers.mock import MockProvider
from app.providers.openai import OpenAIProvider
from app.services.cache import ResponseCache
from app.services.logging import SafeRequestLoggingMiddleware, configure_logging
from app.services.rate_limiter import FixedWindowRateLimiter
from app.services.usage import UsageService


def build_provider(settings: Settings) -> LLMProvider:
    """Select the offline default or explicitly configured external adapter."""
    if settings.provider == "openai":
        if settings.openai_api_key is None or not settings.openai_api_key.get_secret_value():
            raise RuntimeError("GATEWAY_OPENAI_API_KEY is required for the OpenAI provider")
        return OpenAIProvider(
            api_key=settings.openai_api_key.get_secret_value(),
            base_url=settings.openai_base_url,
            timeout_seconds=settings.provider_timeout_seconds,
        )
    return MockProvider()


def build_services(settings: Settings, redis: Redis) -> AppServices:
    """Construct application services in one visible dependency-injection boundary."""
    return AppServices(
        settings=settings,
        redis=redis,
        redactor=RedactionService(),
        guardrails=RuleBasedGuardrailEngine(settings.allowed_topics),
        rate_limiter=FixedWindowRateLimiter(
            redis,
            limit=settings.rate_limit_requests,
            window_seconds=settings.rate_limit_window_seconds,
        ),
        cache=ResponseCache(redis, settings.cache_ttl_seconds),
        usage=UsageService(redis, settings.estimated_cost_per_1k_tokens),
        provider=build_provider(settings),
    )


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create an app that can be configured independently by tests."""
    resolved_settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        redis = Redis.from_url(resolved_settings.redis_url, decode_responses=True)
        app.state.services = build_services(resolved_settings, redis)
        yield
        await redis.aclose()

    configure_logging()
    application = FastAPI(
        title="Guardrailed Enterprise LLM Proxy Gateway",
        version="0.1.0",
        description="Security-focused, enterprise-inspired local MVP.",
        lifespan=lifespan,
    )
    application.add_middleware(SafeRequestLoggingMiddleware)
    application.include_router(health.router)
    application.include_router(chat.router)
    application.include_router(usage.router)

    @application.exception_handler(GatewayError)
    async def gateway_error_handler(request: Request, exc: GatewayError) -> JSONResponse:
        request_id = getattr(request.state, "request_id", None)
        return JSONResponse(
            status_code=exc.status_code,
            headers=exc.headers,
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "request_id": request_id,
                }
            },
        )

    return application


app = create_app()
