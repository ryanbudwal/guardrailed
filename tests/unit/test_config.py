"""Tests for secure and convenient environment configuration."""

import pytest
from pydantic import ValidationError

from app.config import Settings
from app.main import build_provider


def test_comma_separated_environment_values(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GATEWAY_API_KEYS", "alpha,beta")
    monkeypatch.setenv("GATEWAY_ALLOWED_TOPICS", "python,security")

    settings = Settings()

    assert [key.get_secret_value() for key in settings.api_keys] == ["alpha", "beta"]
    assert settings.allowed_topics == ["python", "security"]


def test_api_key_list_cannot_be_empty() -> None:
    with pytest.raises(ValidationError):
        Settings(api_keys=[])


def test_openai_provider_requires_nonempty_key() -> None:
    settings = Settings(provider="openai", openai_api_key="")
    with pytest.raises(RuntimeError, match="GATEWAY_OPENAI_API_KEY"):
        build_provider(settings)
