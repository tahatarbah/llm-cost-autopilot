"""LLM cost estimation and reconciliation."""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable


@dataclass(frozen=True)
class ModelPrice:
    model: str
    provider: str
    input_per_1m: float
    output_per_1m: float


@dataclass(frozen=True)
class CostBreakdown:
    model: str
    provider: str
    input_tokens: int
    output_tokens: int
    input_cost_usd: float
    output_cost_usd: float
    total_cost_usd: float


def _default_prices_path() -> Path:
    return Path(__file__).with_name("prices.json")


@lru_cache(maxsize=4)
def load_price_table(path: str | None = None) -> dict[str, ModelPrice]:
    price_path = Path(path) if path else _default_prices_path()
    raw = json.loads(price_path.read_text(encoding="utf-8"))
    models: dict[str, ModelPrice] = {}
    for name, entry in raw.get("models", {}).items():
        models[name] = ModelPrice(
            model=name,
            provider=entry["provider"],
            input_per_1m=float(entry["input"]),
            output_per_1m=float(entry["output"]),
        )
    return models


def get_model_price(model: str, path: str | None = None) -> ModelPrice | None:
    table = load_price_table(path)
    if model in table:
        return table[model]
    # Allow provider/model style ids
    if "/" in model:
        short = model.split("/", 1)[1]
        return table.get(short)
    return None


def estimate_cost(
    model: str,
    input_tokens: int,
    output_tokens: int = 0,
    *,
    path: str | None = None,
) -> CostBreakdown:
    price = get_model_price(model, path)
    if price is None:
        return CostBreakdown(
            model=model,
            provider="unknown",
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            input_cost_usd=0.0,
            output_cost_usd=0.0,
            total_cost_usd=0.0,
        )
    input_cost = (input_tokens / 1_000_000) * price.input_per_1m
    output_cost = (output_tokens / 1_000_000) * price.output_per_1m
    return CostBreakdown(
        model=price.model,
        provider=price.provider,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        input_cost_usd=round(input_cost, 8),
        output_cost_usd=round(output_cost, 8),
        total_cost_usd=round(input_cost + output_cost, 8),
    )


def reconcile_usage(
    model: str,
    usage: dict[str, Any] | None,
    *,
    path: str | None = None,
) -> CostBreakdown:
    usage = usage or {}
    input_tokens = int(
        usage.get("prompt_tokens")
        or usage.get("input_tokens")
        or usage.get("promptTokenCount")
        or 0
    )
    output_tokens = int(
        usage.get("completion_tokens")
        or usage.get("output_tokens")
        or usage.get("candidatesTokenCount")
        or 0
    )
    return estimate_cost(model, input_tokens, output_tokens, path=path)


def approx_token_count(text: str) -> int:
    """Rough heuristic (~4 chars/token) for pre-call estimates."""
    if not text:
        return 0
    return max(1, len(text) // 4)


def estimate_messages_tokens(messages: Iterable[dict[str, Any]]) -> int:
    total = 0
    for msg in messages:
        content = msg.get("content", "")
        if isinstance(content, list):
            parts = []
            for part in content:
                if isinstance(part, dict) and part.get("type") == "text":
                    parts.append(str(part.get("text", "")))
                else:
                    parts.append(str(part))
            content = " ".join(parts)
        total += approx_token_count(str(content))
        total += 4  # role / formatting overhead
    return total


@dataclass
class UsageAggregate:
    key: str
    request_count: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    cache_hits: int = 0


def aggregate_events(
    events: Iterable[dict[str, Any]],
    *,
    group_by: str = "model",
) -> list[UsageAggregate]:
    buckets: dict[str, UsageAggregate] = {}
    for event in events:
        key = str(event.get(group_by, "unknown"))
        bucket = buckets.setdefault(key, UsageAggregate(key=key))
        bucket.request_count += 1
        bucket.input_tokens += int(event.get("input_tokens", 0) or 0)
        bucket.output_tokens += int(event.get("output_tokens", 0) or 0)
        bucket.cost_usd = round(bucket.cost_usd + float(event.get("cost_usd", 0) or 0), 8)
        if event.get("cache_hit"):
            bucket.cache_hits += 1
    return sorted(buckets.values(), key=lambda b: b.cost_usd, reverse=True)


def list_models(path: str | None = None) -> list[str]:
    return sorted(load_price_table(path).keys())


def provider_for_model(model: str, path: str | None = None) -> str | None:
    price = get_model_price(model, path)
    return price.provider if price else None
