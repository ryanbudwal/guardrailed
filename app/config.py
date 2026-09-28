"""Environment-driven application configuration."""

from functools import lru_cache
from typing import Annotated

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    """Validated settings loaded from environment variables or a local .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="GATEWAY_",
        case_sensitive=False,
        extra="ignore",
    )

    environment: str = "development"
    api_keys: Annotated[list[SecretStr], NoDecode] = Field(
        default_factory=lambda: [SecretStr("local-development-key")],
        min_length=1,
    )
    redis_url: str = "redis://redis:6379/0"
    provider: str = "mock"
    openai_api_key: SecretStr | None = None
    openai_base_url: str = "https://api.openai.com/v1"
    provider_timeout_seconds: float = Field(default=20.0, gt=0, le=120)
    rate_limit_requests: int = Field(default=20, ge=1)
    rate_limit_window_seconds: int = Field(default=60, ge=1)
    cache_ttl_seconds: int = Field(default=300, ge=1)
    max_prompt_chars: int = Field(default=20_000, ge=100, le=1_000_000)
    allowed_topics: Annotated[list[str], NoDecode] = Field(default_factory=list)
    estimated_cost_per_1k_tokens: float = Field(default=0.0, ge=0)

    @field_validator("api_keys", "allowed_topics", mode="before")
    @classmethod
    def split_csv(cls, value: object) -> object:
        """Accept convenient comma-separated environment values."""
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @field_validator("provider")
    @classmethod
    def supported_provider(cls, value: str) -> str:
        normalized = value.lower()
        if normalized not in {"mock", "openai"}:
            raise ValueError("provider must be 'mock' or 'openai'")
        return normalized

    @property
    def development_mode(self) -> bool:
        """Whether non-sensitive developer diagnostics may be returned."""
        return self.environment.lower() == "development"


@lru_cache
def get_settings() -> Settings:
    """Return one settings object for the process."""
    return Settings()
