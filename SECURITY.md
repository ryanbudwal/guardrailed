# Security Policy

## Reporting a vulnerability

Please do not open a public issue for a suspected vulnerability. Send a private
report through GitHub's **Security → Report a vulnerability** flow. Include the
affected endpoint, reproduction steps, impact, and any suggested remediation.
Please allow a reasonable period for investigation before public disclosure.

## Supported versions

This learning project currently supports only the latest `main` branch.

## MVP security boundaries

Guardrailed is an enterprise-inspired MVP, not a production security product.
Its regex redaction and keyword policies reduce obvious exposure but cannot
detect every sensitive value, encoded secret, novel jailbreak, contextual
policy violation, or prompt-injection technique. The fixed-window limiter uses
atomic `INCR`, but expiry is a separate operation. API keys come from
environment configuration and are hashed in memory for comparison; this is not
a full identity or key-management system.

Before real production use, add a managed secrets store, key rotation and
revocation, TLS termination, tenant isolation, durable audited usage records,
atomic Lua rate limiting, robust provider retry/circuit-breaker behavior,
semantic/content moderation, access-controlled logs and metrics, dependency
scanning, container scanning, and an external security review.

## Safe operation

- Never place a real secret in `.env.example`, tests, issues, screenshots, or logs.
- Use the default mock provider while developing.
- Treat Redis data and application logs as sensitive operational data.
- Rotate any credential that may have entered a prompt before redaction.
