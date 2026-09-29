# Guardrailed Enterprise LLM Proxy Gateway

A security-focused, enterprise-inspired FastAPI MVP that sits between developer
applications and an LLM provider. It removes common sensitive values, applies
simple request policies, limits traffic, caches exact sanitized requests, and
tracks approximate usage. The default provider is deterministic and offline, so
the complete project can be learned and tested without a paid API.

> This is a portfolio and learning project, not a production security boundary.

## The problem

Calling an LLM directly spreads provider credentials, policy decisions, and
usage logic across every application. A gateway creates one visible place to
sanitize input, reject known-bad requests, control load, reuse safe results, and
observe approximate consumption. This MVP demonstrates that architecture while
keeping every component small enough to read.

## Architecture

```mermaid
flowchart LR
    A[Developer App] --> B[FastAPI Gateway]
    B --> C[Authentication]
    C --> D[PII Redaction]
    D --> E[Guardrails]
    E --> F[Redis Rate Limiter]
    F --> G[Exact-Match Cache]
    G -->|MISS| H[LLM Provider]
    G -->|HIT| I[Usage Tracking]
    H --> I
    I --> A
```

The code separates API routes, Pydantic models, guardrail contracts, provider
adapters, and Redis services. `app/main.py` is the composition root where these
small objects are wired together.

## Features

- OpenAI-style `POST /v1/chat/completions` with bearer authentication
- Deterministic offline mock provider and an optional direct OpenAI adapter
- Regex redaction for email, US SSN, Canadian SIN, password assignment, bearer
  tokens, and common API-key formats
- Explainable keyword rules plus optional allowed-topic enforcement
- Redis fixed-window limiting per hashed API-key identifier
- Exact-match cache keyed only from sanitized messages and generation settings
- Approximate per-key usage totals and optional estimated cost
- Liveness/readiness endpoints and generic provider/dependency failures
- Structured request metadata logs that never read request bodies or auth headers
- Python 3.12, typed modules, offline pytest suite, Ruff, mypy, Docker, and CI

## Security decisions

- API keys are SHA-256 hashed, then compared in constant time.
- Redaction precedes policy checks, cache keys, cache values, and provider calls.
- Raw prompts, authorization headers, credentials, and unredacted PII are never
  intentionally logged or stored in Redis.
- Request message counts, field lengths, total prompt size, token limits, and
  provider timeouts are bounded.
- Provider errors are translated to generic client messages.
- Development redaction metadata contains only category counts.
- Redis is required for rate enforcement; rate-limit Redis errors fail closed.

Regex and keyword matching are limited by design. They do not prove that input
is safe, identify all secrets, or defeat novel prompt injection. See
[SECURITY.md](SECURITY.md) before considering any non-local use.

## Zero-setup local demo

If the development dependencies are installed, run the gateway without Docker
or a real Redis server:

```bash
source .venv/bin/activate
python scripts/run_demo.py
```

Then open [http://localhost:8000/docs](http://localhost:8000/docs). This mode
uses the offline mock provider and in-memory fake Redis. Its cache, rate-limit,
and usage data disappear when the process stops.

## Quick start with Docker

Requirements: Docker with Compose v2.

```bash
cp .env.example .env
docker compose up --build
```

Open [http://localhost:8000/docs](http://localhost:8000/docs). The default local
key is intentionally non-secret: `local-development-key`. Stop with
`docker compose down`; add `--volumes` only when you also want to erase local
Redis data.

Check the service:

```bash
curl http://localhost:8000/health
curl http://localhost:8000/ready
```

## Example request

```bash
curl --request POST http://localhost:8000/v1/chat/completions \
  --header "Authorization: Bearer local-development-key" \
  --header "Content-Type: application/json" \
  --data '{
    "model": "mock-model",
    "messages": [
      {
        "role": "user",
        "content": "My email is person@example.com and password=hunter2. Write a greeting."
      }
    ],
    "max_tokens": 200,
    "temperature": 0.2
  }'
```

The mock provider sees and echoes only:

```text
My email is [REDACTED_EMAIL] and password=[REDACTED_PASSWORD]. Write a greeting.
```

Development responses include safe metadata such as:

```json
{
  "redactions": {
    "total": 2,
    "categories": {"email": 1, "password": 1}
  }
}
```

Repeat the same request to change `X-LLM-Cache: MISS` to
`X-LLM-Cache: HIT`.

```bash
curl --header "Authorization: Bearer local-development-key" \
  http://localhost:8000/v1/usage
```

## Local development and testing

Python 3.12 and a local Redis are needed to run the app outside Compose. Tests
use `fakeredis`, so Redis itself is not required for `pytest`.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
ruff check .
ruff format --check .
mypy app
pytest
```

Coverage is configured with an 80% minimum and CI never contacts a real LLM.
To run the API against a host Redis, set
`GATEWAY_REDIS_URL=redis://localhost:6379/0` and run:

```bash
uvicorn app.main:app --reload
```

## API endpoints

| Method | Endpoint | Authentication | Purpose |
|---|---|---:|---|
| `POST` | `/v1/chat/completions` | Bearer key | Sanitize, guard, limit, cache, and complete |
| `GET` | `/v1/usage` | Bearer key | Per-key approximate usage totals |
| `GET` | `/health` | No | API process liveness |
| `GET` | `/ready` | No | Redis connectivity readiness |
| `GET` | `/docs` | No | Interactive OpenAPI documentation |

## Environment variables

All settings use the `GATEWAY_` prefix.

| Variable | Default | Meaning |
|---|---|---|
| `GATEWAY_ENVIRONMENT` | `development` | Includes safe redaction counts only in development |
| `GATEWAY_API_KEYS` | `local-development-key` | Comma-separated accepted keys |
| `GATEWAY_REDIS_URL` | `redis://redis:6379/0` | Redis connection |
| `GATEWAY_PROVIDER` | `mock` | `mock` or explicit `openai` |
| `GATEWAY_OPENAI_API_KEY` | unset | Required only for the OpenAI adapter |
| `GATEWAY_OPENAI_BASE_URL` | OpenAI `/v1` URL | OpenAI-compatible base URL |
| `GATEWAY_PROVIDER_TIMEOUT_SECONDS` | `20` | External request timeout |
| `GATEWAY_RATE_LIMIT_REQUESTS` | `20` | Requests allowed per window |
| `GATEWAY_RATE_LIMIT_WINDOW_SECONDS` | `60` | Fixed-window size |
| `GATEWAY_CACHE_TTL_SECONDS` | `300` | Exact-match cache lifetime |
| `GATEWAY_MAX_PROMPT_CHARS` | `20000` | Combined message-size ceiling |
| `GATEWAY_ALLOWED_TOPICS` | empty | Optional comma-separated literal topic terms |
| `GATEWAY_ESTIMATED_COST_PER_1K_TOKENS` | `0` | Optional mock estimate, never live pricing |

Do not commit `.env`. Selecting the OpenAI provider is optional and should be
done only with a separately managed credential. CI always selects `mock`.

## Design trade-offs

- **Fixed window:** `INCR` is atomic and readable, but first-use `EXPIRE` is a
  second operation and boundary bursts are possible. Production should use an
  atomic Lua token bucket or sliding window.
- **Regex redaction:** fast, local, and auditable, but incomplete and
  context-blind. Tests include false positives; more formats need more tests.
- **Keyword guardrails:** explainable but easy to paraphrase around. The
  `GuardrailEngine` interface leaves room for semantic policy later.
- **Exact cache:** deterministic and privacy-conscious after redaction, but
  cannot reuse similar prompts and may conflate different raw values that redact
  to the same placeholder. That privacy/behavior choice must be tenant policy.
- **Token estimate:** `ceil(characters / 4)` is useful for learning and rough
  totals, not billing. Provider tokenizers and returned usage should replace it.
- **Redis usage:** convenient but not a durable audit ledger. Cache/usage writes
  degrade gracefully; rate limiting fails closed.
- **Environment API keys:** adequate for local MVP learning, not lifecycle,
  identity, fine-grained authorization, or managed-secret requirements.


## Skills demonstrated

FastAPI API design, Pydantic validation, async Python, interface-based design,
security-conscious data handling, Redis counters and TTL caching, dependency
injection, deterministic testing, failure modeling, Docker hardening, CI quality
gates, and technical documentation.


<img width="1648" height="1226" alt="image" src="https://github.com/user-attachments/assets/01eb6f66-6024-498a-9940-b0f2e46655b9" />
<img width="1620" height="1180" alt="image" src="https://github.com/user-attachments/assets/ab540fe4-1be0-4dda-a0d9-1d3dae085dd0" />
<img width="1088" height="730" alt="image" src="https://github.com/user-attachments/assets/247a90f7-dd28-4357-8b46-854a182ee500" />


