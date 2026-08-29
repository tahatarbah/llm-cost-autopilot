from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cost_engine import (
    estimate_cost,
    estimate_messages_tokens,
    get_model_price,
    list_models,
    load_price_table,
)
from llm_shared import ChatMessage

from gateway.auth import authenticate_api_key
from gateway.db import get_session
from gateway.db.models import RoutingPolicy
from gateway.routing import DEFAULT_ALIASES, resolve_model

router = APIRouter(prefix="/v1", tags=["openai-extra"])


class EstimateRequest(BaseModel):
    model: str = "autopilot/balanced"
    messages: list[ChatMessage]
    expected_output_tokens: int = Field(default=256, ge=1, le=128000)


class EstimateResponse(BaseModel):
    requested_model: str
    resolved_model: str
    provider: str
    input_tokens: int
    output_tokens: int
    estimated_cost_usd: float
    input_cost_usd: float
    output_cost_usd: float


@router.get("/models")
async def list_available_models(
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """OpenAI-style model list plus Autopilot aliases."""
    auth = await authenticate_api_key(session, authorization)
    if not auth:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")

    result = await session.execute(
        select(RoutingPolicy).where(
            (RoutingPolicy.org_id == auth.org_id) | (RoutingPolicy.org_id.is_(None))
        )
    )
    overrides = {p.alias: p.target_model for p in result.scalars().all()}
    aliases = {**DEFAULT_ALIASES, **overrides}

    data = []
    for alias, target in sorted(aliases.items()):
        price = get_model_price(target)
        data.append(
            {
                "id": alias,
                "object": "model",
                "owned_by": "autopilot",
                "resolves_to": target,
                "provider": price.provider if price else "unknown",
                "pricing": {
                    "input_per_1m": price.input_per_1m if price else None,
                    "output_per_1m": price.output_per_1m if price else None,
                },
            }
        )
    for name in list_models():
        price = load_price_table()[name]
        data.append(
            {
                "id": name,
                "object": "model",
                "owned_by": price.provider,
                "resolves_to": name,
                "provider": price.provider,
                "pricing": {
                    "input_per_1m": price.input_per_1m,
                    "output_per_1m": price.output_per_1m,
                },
            }
        )
    return {"object": "list", "data": data}


@router.post("/estimate", response_model=EstimateResponse)
async def estimate_request_cost(
    body: EstimateRequest,
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> EstimateResponse:
    auth = await authenticate_api_key(session, authorization)
    if not auth:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")

    result = await session.execute(
        select(RoutingPolicy).where(
            (RoutingPolicy.org_id == auth.org_id) | (RoutingPolicy.org_id.is_(None))
        )
    )
    overrides = {p.alias: p.target_model for p in result.scalars().all()}
    resolved = resolve_model(body.model, overrides)
    messages = [m.model_dump() for m in body.messages]
    input_tokens = estimate_messages_tokens(messages)
    cost = estimate_cost(resolved, input_tokens, body.expected_output_tokens)
    return EstimateResponse(
        requested_model=body.model,
        resolved_model=resolved,
        provider=cost.provider,
        input_tokens=cost.input_tokens,
        output_tokens=cost.output_tokens,
        estimated_cost_usd=cost.total_cost_usd,
        input_cost_usd=cost.input_cost_usd,
        output_cost_usd=cost.output_cost_usd,
    )
