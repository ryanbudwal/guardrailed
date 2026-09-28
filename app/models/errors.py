"""Structured gateway exceptions and public error response models."""

from typing import Any

from pydantic import BaseModel


class ErrorDetail(BaseModel):
    """Machine-readable error detail."""

    code: str
    message: str
    request_id: str | None = None


class ErrorResponse(BaseModel):
    """Consistent public error envelope."""

    error: ErrorDetail


class GatewayError(Exception):
    """An expected error safe to expose through the public API."""

    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        *,
        headers: dict[str, str] | None = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.headers = headers or {}
        self.context = context or {}
