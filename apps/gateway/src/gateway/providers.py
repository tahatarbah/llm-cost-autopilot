from __future__ import annotations

import time
import uuid
from typing import Any

import httpx

from cost_engine import provider_for_model
from llm_shared.settings import settings


class ProviderError(Exception):
    def __init__(self, status_code: int, detail: Any):
        self.status_code = status_code
        self.detail = detail
        super().__init__(str(detail))


def _messages_to_dicts(messages: list[Any]) -> list[dict[str, Any]]:
    out = []
    for m in messages:
        if hasattr(m, "model_dump"):
            out.append(m.model_dump())
        elif isinstance(m, dict):
            out.append(m)
        else:
            out.append({"role": getattr(m, "role", "user"), "content": getattr(m, "content", str(m))})
    return out


async def call_openai(model: str, messages: list[dict[str, Any]], **kwargs: Any) -> dict[str, Any]:
    if not settings.openai_api_key:
        raise ProviderError(503, "OPENAI_API_KEY is not configured")
    payload = {"model": model, "messages": messages, **{k: v for k, v in kwargs.items() if v is not None}}
    payload.pop("stream", None)
    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {settings.openai_api_key}"},
            json=payload,
        )
        if resp.status_code >= 400:
            raise ProviderError(resp.status_code, resp.json() if resp.headers.get("content-type", "").startswith("application/json") else resp.text)
        return resp.json()


async def call_anthropic(model: str, messages: list[dict[str, Any]], **kwargs: Any) -> dict[str, Any]:
    if not settings.anthropic_api_key:
        raise ProviderError(503, "ANTHROPIC_API_KEY is not configured")
    system_parts = [m["content"] for m in messages if m.get("role") == "system"]
    chat_messages = []
    for m in messages:
        if m.get("role") == "system":
            continue
        role = "assistant" if m.get("role") == "assistant" else "user"
        chat_messages.append({"role": role, "content": m.get("content", "")})
    payload: dict[str, Any] = {
        "model": model,
        "messages": chat_messages,
        "max_tokens": kwargs.get("max_tokens") or 1024,
    }
    if system_parts:
        payload["system"] = "\n".join(str(p) for p in system_parts)
    if kwargs.get("temperature") is not None:
        payload["temperature"] = kwargs["temperature"]
    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": settings.anthropic_api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json=payload,
        )
        if resp.status_code >= 400:
            raise ProviderError(resp.status_code, resp.json() if resp.headers.get("content-type", "").startswith("application/json") else resp.text)
        data = resp.json()
        text = ""
        for block in data.get("content", []):
            if block.get("type") == "text":
                text += block.get("text", "")
        usage = data.get("usage") or {}
        return {
            "id": data.get("id") or f"chatcmpl-{uuid.uuid4().hex[:24]}",
            "object": "chat.completion",
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": text},
                    "finish_reason": data.get("stop_reason") or "stop",
                }
            ],
            "usage": {
                "prompt_tokens": int(usage.get("input_tokens", 0)),
                "completion_tokens": int(usage.get("output_tokens", 0)),
                "total_tokens": int(usage.get("input_tokens", 0)) + int(usage.get("output_tokens", 0)),
            },
        }


async def call_google(model: str, messages: list[dict[str, Any]], **kwargs: Any) -> dict[str, Any]:
    if not settings.google_api_key:
        raise ProviderError(503, "GOOGLE_API_KEY is not configured")
    contents = []
    system_instruction = None
    for m in messages:
        role = m.get("role")
        content = m.get("content", "")
        if role == "system":
            system_instruction = str(content)
            continue
        gemini_role = "model" if role == "assistant" else "user"
        contents.append({"role": gemini_role, "parts": [{"text": str(content)}]})
    body: dict[str, Any] = {"contents": contents}
    if system_instruction:
        body["systemInstruction"] = {"parts": [{"text": system_instruction}]}
    gen_cfg: dict[str, Any] = {}
    if kwargs.get("temperature") is not None:
        gen_cfg["temperature"] = kwargs["temperature"]
    if kwargs.get("max_tokens") is not None:
        gen_cfg["maxOutputTokens"] = kwargs["max_tokens"]
    if gen_cfg:
        body["generationConfig"] = gen_cfg
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        f"?key={settings.google_api_key}"
    )
    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(url, json=body)
        if resp.status_code >= 400:
            raise ProviderError(resp.status_code, resp.json() if resp.headers.get("content-type", "").startswith("application/json") else resp.text)
        data = resp.json()
        text = ""
        candidates = data.get("candidates") or []
        if candidates:
            parts = candidates[0].get("content", {}).get("parts", [])
            text = "".join(p.get("text", "") for p in parts)
        usage_meta = data.get("usageMetadata") or {}
        return {
            "id": f"chatcmpl-{uuid.uuid4().hex[:24]}",
            "object": "chat.completion",
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": text},
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": int(usage_meta.get("promptTokenCount", 0)),
                "completion_tokens": int(usage_meta.get("candidatesTokenCount", 0)),
                "total_tokens": int(usage_meta.get("totalTokenCount", 0)),
            },
            }


async def dispatch_chat(
    model: str,
    messages: list[Any],
    **kwargs: Any,
) -> tuple[dict[str, Any], str, int]:
    msg_dicts = _messages_to_dicts(messages)
    provider = provider_for_model(model) or "openai"

    if settings.mock_providers:
        started = time.perf_counter()
        prompt_tokens = max(1, sum(len(str(m.get("content", ""))) // 4 for m in msg_dicts))
        completion_tokens = 8
        result = {
            "id": f"chatcmpl-mock-{uuid.uuid4().hex[:12]}",
            "object": "chat.completion",
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": f"[mock:{model}] ok",
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens,
            },
        }
        latency_ms = int((time.perf_counter() - started) * 1000)
        return result, provider, latency_ms

    started = time.perf_counter()
    if provider == "anthropic":
        result = await call_anthropic(model, msg_dicts, **kwargs)
    elif provider == "google":
        result = await call_google(model, msg_dicts, **kwargs)
    else:
        result = await call_openai(model, msg_dicts, **kwargs)
    latency_ms = int((time.perf_counter() - started) * 1000)
    return result, provider, latency_ms
