"""Response models exposed by the gateway API."""

from typing import Literal

from pydantic import BaseModel, Field


class RedactionSummary(BaseModel):
    """Safe redaction metadata; original matched values are never included."""

    total: int
    categories: dict[str, int]


class ResponseMessage(BaseModel):
    """Assistant content in a completion choice."""

    role: Literal["assistant"] = "assistant"
    content: str


class ChatChoice(BaseModel):
    """One deterministic completion choice."""

    index: int = 0
    message: ResponseMessage
    finish_reason: str = "stop"


class TokenUsage(BaseModel):
    """Approximate usage using the documented character-count heuristic."""

    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class ChatCompletionResponse(BaseModel):
    """OpenAI-style chat response with optional development metadata."""

    id: str
    object: Literal["chat.completion"] = "chat.completion"
    created: int
    model: str
    choices: list[ChatChoice]
    usage: TokenUsage
    redactions: RedactionSummary | None = None


class UsageResponse(BaseModel):
    """Aggregated approximate usage for the authenticated API key."""

    total_requests: int = 0
    blocked_requests: int = 0
    cache_hits: int = 0
    estimated_input_tokens: int = 0
    estimated_output_tokens: int = 0
    estimated_cost: float = Field(default=0, description="Optional configured estimate")
    cost_is_estimate: bool = True
