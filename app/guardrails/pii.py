"""Regex-based PII and credential redaction for the MVP."""

import re
from collections import Counter
from dataclasses import dataclass
from re import Pattern


@dataclass(frozen=True)
class RedactionResult:
    """Sanitized text plus counts that cannot reconstruct the original values."""

    text: str
    categories: dict[str, int]

    @property
    def total(self) -> int:
        return sum(self.categories.values())


@dataclass(frozen=True)
class RedactionPattern:
    """One compiled sensitive-data pattern and its replacement."""

    category: str
    pattern: Pattern[str]
    replacement: str


class RedactionService:
    """Redact a deliberately small, auditable set of sensitive-data formats."""

    def __init__(self) -> None:
        flags = re.IGNORECASE
        self.patterns = (
            RedactionPattern(
                "bearer_token",
                re.compile(r"\bBearer\s+[A-Za-z0-9._~+/\-=]{12,}", flags),
                "Bearer [REDACTED_BEARER_TOKEN]",
            ),
            RedactionPattern(
                "password",
                re.compile(r"\b(password|passwd|pwd)(\s*[:=]\s*)([^\s,;]+)", flags),
                r"\1\2[REDACTED_PASSWORD]",
            ),
            RedactionPattern(
                "email",
                re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", flags),
                "[REDACTED_EMAIL]",
            ),
            RedactionPattern(
                "ssn",
                re.compile(r"(?<!\d)\d{3}-\d{2}-\d{4}(?!\d)"),
                "[REDACTED_SSN]",
            ),
            RedactionPattern(
                "sin",
                re.compile(r"(?<!\d)\d{3}[ -]\d{3}[ -]\d{3}(?!\d)"),
                "[REDACTED_SIN]",
            ),
            RedactionPattern(
                "api_key",
                re.compile(
                    r"\b(?:sk|pk|ghp|github_pat|xox[baprs])[-_][A-Za-z0-9_-]{12,}\b",
                    flags,
                ),
                "[REDACTED_API_KEY]",
            ),
            RedactionPattern(
                "api_key",
                re.compile(
                    r"\b(api[_ -]?key|access[_ -]?token)(\s*[:=]\s*)"
                    r"([A-Za-z0-9._-]{12,})",
                    flags,
                ),
                r"\1\2[REDACTED_API_KEY]",
            ),
            RedactionPattern(
                "phone",
                re.compile(r"\d{3}-\d{3}-\d{4}"),
                "[REDACTED_PHONE]",
            ),
        )

    def redact(self, text: str) -> RedactionResult:
        """Apply patterns in a stable order and count replacements by category."""
        sanitized = text
        counts: Counter[str] = Counter()
        for item in self.patterns:
            sanitized, replacements = item.pattern.subn(item.replacement, sanitized)
            if replacements:
                counts[item.category] += replacements
        return RedactionResult(text=sanitized, categories=dict(counts))
