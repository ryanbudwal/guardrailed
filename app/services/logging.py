"""Structured request logging that excludes prompts and credentials."""

import json
import logging
import time
import uuid
from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware


class SafeRequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log request metadata only; request bodies and authorization are never read."""

    def __init__(self, app: object) -> None:
        super().__init__(app)  # type: ignore[arg-type]
        self.logger = logging.getLogger("gateway.request")

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        started = time.perf_counter()
        response = await call_next(request)
        latency_ms = round((time.perf_counter() - started) * 1000, 2)
        response.headers["X-Request-ID"] = request_id
        record = {
            "event": "request_complete",
            "request_id": request_id,
            "path": request.url.path,
            "status_code": response.status_code,
            "latency_ms": latency_ms,
            "cache_status": getattr(request.state, "cache_status", "N/A"),
            "guardrail_decision": getattr(request.state, "guardrail_decision", "N/A"),
        }
        self.logger.info(json.dumps(record, separators=(",", ":")))
        return response


def configure_logging() -> None:
    """Configure a compact process-wide log format."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
