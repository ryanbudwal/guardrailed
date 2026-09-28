"""Optional direct OpenAI adapter with bounded network timeouts."""

import httpx

from app.models.requests import ChatMessage
from app.providers.base import ProviderError, ProviderResult


class OpenAIProvider:
    """Call the OpenAI-compatible chat completions API when explicitly configured."""

    def __init__(self, api_key: str, base_url: str, timeout_seconds: float) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    @property
    def name(self) -> str:
        return "openai"

    async def complete(
        self,
        *,
        messages: list[ChatMessage],
        model: str,
        max_tokens: int,
        temperature: float,
    ) -> ProviderResult:
        payload = {
            "model": model,
            "messages": [message.model_dump() for message in messages],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
                content = data["choices"][0]["message"]["content"]
        except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as exc:
            raise ProviderError("OpenAI request failed") from exc
        return ProviderResult(content=str(content), model=model, provider=self.name)
