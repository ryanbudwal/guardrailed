"""Validated OpenAI-style chat request models."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ChatMessage(BaseModel):
    """A single chat message."""

    model_config = ConfigDict(extra="forbid")

    role: Literal["system", "user", "assistant"]
    content: str = Field(min_length=1, max_length=20_000)


class ChatCompletionRequest(BaseModel):
    """The supported subset of an OpenAI chat completion request."""

    model_config = ConfigDict(extra="forbid")

    model: str = Field(default="mock-model", min_length=1, max_length=100)
    messages: list[ChatMessage] = Field(min_length=1, max_length=50)
    max_tokens: int = Field(default=200, ge=1, le=4096)
    temperature: float = Field(default=0.2, ge=0, le=2)
