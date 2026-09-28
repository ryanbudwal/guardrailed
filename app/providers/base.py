"""Provider interface shared by mock and external LLM adapters."""

from dataclasses import dataclass
from typing import Protocol

from app.models.requests import ChatMessage


@dataclass(frozen=True)
class ProviderResult:
    """Provider-neutral generated text and approximate output usage."""

    content: str
    model: str
    provider: str


class LLMProvider(Protocol):
    """Minimal async contract for adding another completion provider."""

    @property
    def name(self) -> str:
        """Return the stable provider identifier."""
        ...

    async def complete(
        self,
        *,
        messages: list[ChatMessage],
        model: str,
        max_tokens: int,
        temperature: float,
    ) -> ProviderResult:
        """Generate a response from sanitized messages."""
        ...


class ProviderError(Exception):
    """Internal provider failure whose details must not reach clients."""
