"""The secured OpenAI-style chat completion request pipeline."""

import json
import logging
import time
import uuid
from collections import Counter
from datetime import UTC, datetime

from fastapi import APIRouter, Request, Response
from redis.exceptions import RedisError

from app.dependencies import ClientDependency, ServicesDependency
from app.models.errors import GatewayError
from app.models.requests import ChatCompletionRequest, ChatMessage
from app.models.responses import (
    ChatChoice,
    ChatCompletionResponse,
    RedactionSummary,
    ResponseMessage,
    TokenUsage,
)
from app.providers.base import ProviderError
from app.services.usage import UsageEvent, estimate_tokens

router = APIRouter(prefix="/v1", tags=["chat"])
logger = logging.getLogger("gateway.chat")


@router.post("/chat/completions", response_model=ChatCompletionResponse)
async def chat_completion(
    payload: ChatCompletionRequest,
    request: Request,
    response: Response,
    client: ClientDependency,
    services: ServicesDependency,
) -> ChatCompletionResponse:
    """Redact, guard, limit, cache, forward, and account for a chat request."""
    raw_characters = sum(len(message.content) for message in payload.messages)
    if raw_characters > services.settings.max_prompt_chars:
        raise GatewayError(413, "prompt_too_large", "The combined prompt is too large.")

    sanitized_messages: list[ChatMessage] = []
    category_counts: Counter[str] = Counter()
    for message in payload.messages:
        redaction = services.redactor.redact(message.content)
        category_counts.update(redaction.categories)
        sanitized_messages.append(ChatMessage(role=message.role, content=redaction.text))
    sanitized_text = "\n".join(message.content for message in sanitized_messages)
    input_tokens = estimate_tokens(sanitized_text)
    try:
        await services.usage.record(
            client.identifier,
            UsageEvent(input_tokens=input_tokens),
        )
    except RedisError:
        logger.exception("Failed to record request usage")

    decision = services.guardrails.evaluate(sanitized_text)
    request.state.guardrail_decision = decision.category
    if not decision.allowed:
        try:
            await services.usage.record(
                client.identifier,
                UsageEvent(request_count=0, blocked=True),
            )
        except RedisError:
            logger.exception("Failed to record blocked request usage")
        raise GatewayError(403, "request_blocked", decision.reason)

    try:
        limit = await services.rate_limiter.check(client.identifier)
    except RedisError as exc:
        raise GatewayError(
            503, "service_unavailable", "A required service is unavailable."
        ) from exc
    for name, value in limit.headers().items():
        response.headers[name] = value
    if not limit.allowed:
        raise GatewayError(
            429,
            "rate_limit_exceeded",
            "Rate limit exceeded. Try again later.",
            headers=limit.headers(),
        )

    cache_key = services.cache.make_key(
        messages=sanitized_messages,
        model=payload.model,
        temperature=payload.temperature,
        max_tokens=payload.max_tokens,
    )
    try:
        provider_result = await services.cache.get(cache_key)
    except (RedisError, ValueError, TypeError):
        logger.exception("Cache read failed")
        provider_result = None

    cache_hit = provider_result is not None
    request.state.cache_status = "HIT" if cache_hit else "MISS"
    response.headers["X-LLM-Cache"] = request.state.cache_status
    started = time.perf_counter()
    if provider_result is None:
        try:
            provider_result = await services.provider.complete(
                messages=sanitized_messages,
                model=payload.model,
                max_tokens=payload.max_tokens,
                temperature=payload.temperature,
            )
        except ProviderError as exc:
            raise GatewayError(
                502, "provider_error", "The model provider could not complete the request."
            ) from exc
        try:
            await services.cache.set(cache_key, provider_result)
        except RedisError:
            logger.exception("Cache write failed")

    output_tokens = estimate_tokens(provider_result.content)
    latency_ms = round((time.perf_counter() - started) * 1000, 2)
    try:
        await services.usage.record(
            client.identifier,
            UsageEvent(
                request_count=0,
                cache_hit=cache_hit,
                output_tokens=output_tokens,
            ),
        )
    except RedisError:
        logger.exception("Usage write failed")

    # This event intentionally contains identifiers and metrics, never prompt content.
    logger.info(
        json.dumps(
            {
                "event": "completion",
                "request_id": request.state.request_id,
                "api_key_id": client.identifier,
                "provider": provider_result.provider,
                "model": provider_result.model,
                "estimated_input_tokens": input_tokens,
                "estimated_output_tokens": output_tokens,
                "cache_hit": cache_hit,
                "latency_ms": latency_ms,
                "guardrail_outcome": "allowed",
                "timestamp": datetime.now(UTC).isoformat(),
            },
            separators=(",", ":"),
        )
    )
    redactions = None
    if services.settings.development_mode:
        redactions = RedactionSummary(
            total=sum(category_counts.values()),
            categories=dict(category_counts),
        )
    return ChatCompletionResponse(
        id=f"chatcmpl-{uuid.uuid4().hex}",
        created=int(time.time()),
        model=provider_result.model,
        choices=[ChatChoice(message=ResponseMessage(content=provider_result.content))],
        usage=TokenUsage(
            prompt_tokens=input_tokens,
            completion_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
        ),
        redactions=redactions,
    )
