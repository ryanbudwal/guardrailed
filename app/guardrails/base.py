"""Interfaces and shared result types for replaceable guardrail engines."""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class GuardrailDecision:
    """The result of checking sanitized text against tenant policy."""

    allowed: bool
    category: str = "allowed"
    reason: str = ""


class GuardrailEngine(Protocol):
    """Contract that a future semantic guardrail implementation can satisfy."""

    def evaluate(self, text: str) -> GuardrailDecision:
        """Evaluate sanitized text and return a policy decision."""
        ...
