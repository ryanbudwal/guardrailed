"""Liveness and Redis readiness endpoints."""

from fastapi import APIRouter
from redis.exceptions import RedisError

from app.dependencies import ServicesDependency
from app.models.errors import GatewayError

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, str]:
    """Confirm the API process can serve requests."""
    return {"status": "ok"}


@router.get("/ready")
async def ready(services: ServicesDependency) -> dict[str, str]:
    """Confirm the required Redis dependency is reachable."""
    try:
        await services.redis.ping()
    except RedisError as exc:
        raise GatewayError(503, "not_ready", "A required service is unavailable.") from exc
    return {"status": "ready"}
