"""LLM Cost Autopilot Python SDK."""

from __future__ import annotations

from typing import Any

import httpx

from cost_engine import estimate_cost, estimate_messages_tokens, list_models


class AutopilotClient:
    """Thin OpenAI-compatible client pointing at the Cost Autopilot gateway."""

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = "http://localhost:8080/v1",
        timeout: float = 120.0,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._client = httpx.Client(timeout=timeout)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> AutopilotClient:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}"}

    def chat_completions(
        self,
        *,
        model: str = "autopilot/balanced",
        messages: list[dict[str, Any]],
        temperature: float | None = None,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"model": model, "messages": messages, **kwargs}
        if temperature is not None:
            payload["temperature"] = temperature
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        resp = self._client.post(
            f"{self.base_url}/chat/completions",
            headers=self._headers(),
            json=payload,
        )
        resp.raise_for_status()
        data = resp.json()
        data["_autopilot"] = {
            "cost_usd": resp.headers.get("x-llm-cost-usd"),
            "estimate_usd": resp.headers.get("x-llm-estimate-usd"),
            "model_used": resp.headers.get("x-llm-model-used"),
            "cache": resp.headers.get("x-llm-cache"),
            "request_id": resp.headers.get("x-llm-request-id"),
            "provider": resp.headers.get("x-llm-provider"),
            "budget_alert": resp.headers.get("x-llm-budget-alert"),
        }
        return data

    def estimate(
        self,
        model: str,
        messages: list[dict[str, Any]],
        expected_output_tokens: int = 256,
        *,
        remote: bool = False,
    ) -> dict[str, Any]:
        if remote:
            resp = self._client.post(
                f"{self.base_url}/estimate",
                headers=self._headers(),
                json={
                    "model": model,
                    "messages": messages,
                    "expected_output_tokens": expected_output_tokens,
                },
            )
            resp.raise_for_status()
            return resp.json()
        input_tokens = estimate_messages_tokens(messages)
        cost = estimate_cost(model, input_tokens, expected_output_tokens)
        return {
            "model": cost.model,
            "provider": cost.provider,
            "input_tokens": cost.input_tokens,
            "output_tokens": cost.output_tokens,
            "estimated_cost_usd": cost.total_cost_usd,
        }

    def list_models_remote(self) -> dict[str, Any]:
        resp = self._client.get(f"{self.base_url}/models", headers=self._headers())
        resp.raise_for_status()
        return resp.json()

    @staticmethod
    def models() -> list[str]:
        return list_models()

    @staticmethod
    def openai_base_url(gateway_url: str = "http://localhost:8080") -> str:
        """Helper for OpenAI SDK: OpenAI(base_url=..., api_key=...)."""
        return f"{gateway_url.rstrip('/')}/v1"


class AsyncAutopilotClient:
    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = "http://localhost:8080/v1",
        timeout: float = 120.0,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(timeout=timeout)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> AsyncAutopilotClient:
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.aclose()

    async def chat_completions(
        self,
        *,
        model: str = "autopilot/balanced",
        messages: list[dict[str, Any]],
        temperature: float | None = None,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"model": model, "messages": messages, **kwargs}
        if temperature is not None:
            payload["temperature"] = temperature
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        resp = await self._client.post(
            f"{self.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json=payload,
        )
        resp.raise_for_status()
        data = resp.json()
        data["_autopilot"] = {
            "cost_usd": resp.headers.get("x-llm-cost-usd"),
            "estimate_usd": resp.headers.get("x-llm-estimate-usd"),
            "model_used": resp.headers.get("x-llm-model-used"),
            "cache": resp.headers.get("x-llm-cache"),
            "request_id": resp.headers.get("x-llm-request-id"),
            "provider": resp.headers.get("x-llm-provider"),
            "budget_alert": resp.headers.get("x-llm-budget-alert"),
        }
        return data
