"""Deterministic, offline provider used by default and in tests."""

from app.models.requests import ChatMessage
from app.providers.base import ProviderResult


class MockProvider:
    """Return stable text without network calls or paid credentials."""

    @property
    def name(self) -> str:
        return "mock"

    async def complete(
        self,
        *,
        messages: list[ChatMessage],
        model: str,
        max_tokens: int,
        temperature: float,
    ) -> ProviderResult:
        del max_tokens, temperature
        prompt = "\n".join(message.content for message in messages)
        return ProviderResult(
            content=f"Mock response to: {prompt}",
            model=model,
            provider=self.name,
        )
