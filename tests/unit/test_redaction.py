"""Tests for sensitive-data regex behavior."""

from app.guardrails.pii import RedactionService


def test_redacts_supported_sensitive_values() -> None:
    redactor = RedactionService()
    text = (
        "Email person@example.com, SSN 123-45-6789, SIN 123 456 789, "
        "phone=123-456-7890 , password=hunter2, Authorization: Bearer abcdefghijklmnop "
        "api_key=abcdefghijklmnop"
    )

    result = redactor.redact(text)

    assert "person@example.com" not in result.text
    assert "hunter2" not in result.text
    assert "[REDACTED_EMAIL]" in result.text
    assert "password=[REDACTED_PASSWORD]" in result.text
    assert "123-456-7890" not in result.text
    assert "phone=[REDACTED_PHONE]" in result.text
    assert result.categories == {
        "bearer_token": 1,
        "password": 1,
        "email": 1,
        "ssn": 1,
        "sin": 1,
        "api_key": 1,
        "phone": 1,
    }


def test_avoids_common_false_positives() -> None:
    text = "Version 123-45-678 is not an SSN. Contact user@localhost in development."

    result = RedactionService().redact(text)

    assert result.text == text
    assert result.total == 0
