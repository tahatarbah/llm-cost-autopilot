from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cost_engine import estimate_cost, estimate_messages_tokens, reconcile_usage
from llm_shared import ChatCompletionRequest

from gateway.auth import authenticate_api_key, check_budgets
from gateway.cache import cache_get, cache_key, cache_set
from gateway.db import get_session
from gateway.db.models import RoutingPolicy, UsageEvent
from gateway.providers import ProviderError, dispatch_chat
from gateway.routing import resolve_model

router = APIRouter(prefix="/v1", tags=["openai"])


@router.post("/chat/completions")
async def chat_completions(
    body: ChatCompletionRequest,
    response: Response,
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    auth = await authenticate_api_key(session, authorization)
    if not auth:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")

    if body.stream:
        raise HTTPException(status_code=400, detail="Streaming is not supported in v1")

    budget = await check_budgets(session, auth)
    if not budget.allowed:
        raise HTTPException(
            status_code=402,
            detail={
                "error": "budget_exceeded",
                "message": budget.reason,
                "spent_usd": budget.spent_usd,
                "limit_usd": budget.limit_usd,
            },
        )

    # Org-specific routing overrides
    result = await session.execute(
        select(RoutingPolicy).where(
            (RoutingPolicy.org_id == auth.org_id) | (RoutingPolicy.org_id.is_(None))
        )
    )
    overrides = {p.alias: p.target_model for p in result.scalars().all()}
    resolved_model = resolve_model(body.model, overrides)

    messages = [m.model_dump() for m in body.messages]
    key = cache_key(
        resolved_model,
        messages,
        temperature=body.temperature,
        max_tokens=body.max_tokens,
    )

    cached = await cache_get(key)
    request_id = f"req_{uuid.uuid4().hex[:16]}"

    if cached:
        usage_event = UsageEvent(
            org_id=auth.org_id,
            project_id=auth.project.id,
            model=resolved_model,
            provider=cached.get("provider", "cache"),
            input_tokens=0,
            output_tokens=0,
            cost_usd=0.0,
            cache_hit=True,
            latency_ms=0,
            status="ok",
            request_id=request_id,
        )
        session.add(usage_event)
        await session.commit()
        response.headers["x-llm-cost-usd"] = "0"
        response.headers["x-llm-model-used"] = resolved_model
        response.headers["x-llm-cache"] = "hit"
        response.headers["x-llm-request-id"] = request_id
        if budget.alert:
            response.headers["x-llm-budget-alert"] = budget.reason or "true"
        return cached["body"]

    input_est = estimate_messages_tokens(messages)
    out_est = body.max_tokens or 256
    pre_cost = estimate_cost(resolved_model, input_est, out_est)
    response.headers["x-llm-estimate-usd"] = str(pre_cost.total_cost_usd)

    try:
        completion, provider, latency_ms = await dispatch_chat(
            resolved_model,
            messages,
            temperature=body.temperature,
            max_tokens=body.max_tokens,
        )
    except ProviderError as exc:
        session.add(
            UsageEvent(
                org_id=auth.org_id,
                project_id=auth.project.id,
                model=resolved_model,
                provider=provider_for_safe(resolved_model),
                input_tokens=0,
                output_tokens=0,
                cost_usd=0.0,
                cache_hit=False,
                latency_ms=0,
                status="error",
                request_id=request_id,
            )
        )
        await session.commit()
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

    cost = reconcile_usage(resolved_model, completion.get("usage"))
    session.add(
        UsageEvent(
            org_id=auth.org_id,
            project_id=auth.project.id,
            model=resolved_model,
            provider=provider,
            input_tokens=cost.input_tokens,
            output_tokens=cost.output_tokens,
            cost_usd=cost.total_cost_usd,
            cache_hit=False,
            latency_ms=latency_ms,
            status="ok",
            request_id=request_id,
        )
    )
    await session.commit()

    await cache_set(key, {"body": completion, "provider": provider})

    response.headers["x-llm-cost-usd"] = str(cost.total_cost_usd)
    response.headers["x-llm-model-used"] = resolved_model
    response.headers["x-llm-cache"] = "miss"
    response.headers["x-llm-request-id"] = request_id
    response.headers["x-llm-provider"] = provider
    if budget.alert:
        response.headers["x-llm-budget-alert"] = budget.reason or "true"

    # Ensure model field reflects resolved model
    completion["model"] = resolved_model
    return completion


def provider_for_safe(model: str) -> str:
    from cost_engine import provider_for_model

    return provider_for_model(model) or "unknown"
