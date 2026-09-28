"""Authenticated usage-summary endpoint."""

from fastapi import APIRouter
from redis.exceptions import RedisError

from app.dependencies import ClientDependency, ServicesDependency
from app.models.errors import GatewayError
from app.models.responses import UsageResponse

router = APIRouter(prefix="/v1", tags=["usage"])


@router.get("/usage", response_model=UsageResponse)
async def usage(
    client: ClientDependency,
    services: ServicesDependency,
) -> UsageResponse:
    """Return approximate counters scoped to the authenticated API key."""
    try:
        return await services.usage.totals(client.identifier)
    except RedisError as exc:
        raise GatewayError(
            503, "service_unavailable", "A required service is unavailable."
        ) from exc
