"""Authentication and injectable application service dependencies."""

import hashlib
import hmac
from dataclasses import dataclass
from typing import Annotated, cast

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from redis.asyncio import Redis

from app.config import Settings
from app.guardrails.base import GuardrailEngine
from app.guardrails.pii import RedactionService
from app.models.errors import GatewayError
from app.providers.base import LLMProvider
from app.services.cache import ResponseCache
from app.services.rate_limiter import FixedWindowRateLimiter
from app.services.usage import UsageService

bearer_scheme = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class AuthenticatedClient:
    """Non-secret stable identifier derived from a valid API key."""

    identifier: str


@dataclass
class AppServices:
    """Objects shared across requests and replaceable in tests."""

    settings: Settings
    redis: Redis
    redactor: RedactionService
    guardrails: GuardrailEngine
    rate_limiter: FixedWindowRateLimiter
    cache: ResponseCache
    usage: UsageService
    provider: LLMProvider


def get_services(request: Request) -> AppServices:
    """Fetch services initialized by the application lifespan."""
    return cast(AppServices, request.app.state.services)


async def authenticate(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    services: Annotated[AppServices, Depends(get_services)],
) -> AuthenticatedClient:
    """Hash candidates and use constant-time comparisons against configured keys."""
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise GatewayError(401, "invalid_api_key", "A valid bearer API key is required.")

    candidate_digest = hashlib.sha256(credentials.credentials.encode()).digest()
    matched = False
    for configured in services.settings.api_keys:
        configured_digest = hashlib.sha256(configured.get_secret_value().encode()).digest()
        matched = hmac.compare_digest(candidate_digest, configured_digest) or matched
    if not matched:
        raise GatewayError(401, "invalid_api_key", "A valid bearer API key is required.")
    return AuthenticatedClient(identifier=candidate_digest.hex()[:16])


ServicesDependency = Annotated[AppServices, Depends(get_services)]
ClientDependency = Annotated[AuthenticatedClient, Depends(authenticate)]
