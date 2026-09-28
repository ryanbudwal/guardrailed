"""Small, explicit keyword policies for the MVP guardrail layer."""

from app.guardrails.base import GuardrailDecision


class RuleBasedGuardrailEngine:
    """Apply explainable phrase checks to already-sanitized request text."""

    _blocked_phrases: dict[str, tuple[str, ...]] = {
        "secret_exfiltration": (
            "reveal the password",
            "show me the api key",
            "print the api key",
            "expose credentials",
        ),
        "instruction_bypass": (
            "ignore previous instructions",
            "ignore all instructions",
            "bypass system instructions",
            "jailbreak the system",
        ),
        "toxic_language": (
            "kill yourself",
            "racial slur",
            "you are worthless",
        ),
    }

    def __init__(self, allowed_topics: list[str] | None = None) -> None:
        self.allowed_topics = tuple(topic.lower() for topic in (allowed_topics or []))

    def evaluate(self, text: str) -> GuardrailDecision:
        """Return the first deterministic policy violation or allow the request."""
        lowered = text.lower()
        for category, phrases in self._blocked_phrases.items():
            if any(phrase in lowered for phrase in phrases):
                return GuardrailDecision(
                    allowed=False,
                    category=category,
                    reason="Request violates the configured content policy.",
                )
        if self.allowed_topics and not any(topic in lowered for topic in self.allowed_topics):
            return GuardrailDecision(
                allowed=False,
                category="topic_not_allowed",
                reason="Request is outside the configured allowed topics.",
            )
        return GuardrailDecision(allowed=True)
