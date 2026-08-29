from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


class MemberRole(str, Enum):
    OWNER = "owner"
    ADMIN = "admin"
    VIEWER = "viewer"


class BudgetPeriod(str, Enum):
    DAILY = "daily"
    MONTHLY = "monthly"


class BudgetAction(str, Enum):
    ALERT = "alert"
    BLOCK = "block"


class BudgetScope(str, Enum):
    PROJECT = "project"
    ORG = "org"


class ChatMessage(BaseModel):
    role: str
    content: Any


class ChatCompletionRequest(BaseModel):
    model: str
    messages: list[ChatMessage]
    temperature: float | None = None
    max_tokens: int | None = None
    stream: bool = False
    user: str | None = None
    extra: dict[str, Any] = Field(default_factory=dict)

    model_config = {"extra": "allow"}


class UsageInfo(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class BudgetCreate(BaseModel):
    scope: BudgetScope = BudgetScope.PROJECT
    project_id: UUID | None = None
    period: BudgetPeriod = BudgetPeriod.MONTHLY
    limit_usd: float
    action: BudgetAction = BudgetAction.BLOCK
    alert_threshold: float = 0.8


class BudgetOut(BaseModel):
    id: UUID
    org_id: UUID
    project_id: UUID | None
    scope: BudgetScope
    period: BudgetPeriod
    limit_usd: float
    action: BudgetAction
    alert_threshold: float
    spent_usd: float = 0.0


class ApiKeyCreate(BaseModel):
    project_id: UUID
    name: str = "default"


class ApiKeyOut(BaseModel):
    id: UUID
    project_id: UUID
    name: str
    prefix: str
    created_at: datetime
    key: str | None = None  # only on create


class ProjectCreate(BaseModel):
    name: str
    slug: str | None = None


class ProjectOut(BaseModel):
    id: UUID
    org_id: UUID
    name: str
    slug: str


class OrgCreate(BaseModel):
    name: str
    slug: str | None = None


class OrgOut(BaseModel):
    id: UUID
    name: str
    slug: str


class UsageEventOut(BaseModel):
    id: UUID
    project_id: UUID
    model: str
    provider: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    cache_hit: bool
    latency_ms: int
    created_at: datetime
    status: str = "ok"


class SpendSummary(BaseModel):
    today_usd: float
    month_usd: float
    request_count: int
    cache_hit_rate: float
    by_model: list[dict[str, Any]]
    by_project: list[dict[str, Any]]


class HealthOut(BaseModel):
    status: Literal["ok"] = "ok"
    service: str = "llm-cost-autopilot"
