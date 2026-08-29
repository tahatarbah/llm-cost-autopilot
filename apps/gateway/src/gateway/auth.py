from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import Select, and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from gateway.db.models import ApiKey, Budget, Project, UsageEvent, hash_api_key


@dataclass
class AuthContext:
    api_key: ApiKey
    project: Project
    org_id: UUID


async def authenticate_api_key(session: AsyncSession, authorization: str | None) -> AuthContext | None:
    if not authorization:
        return None
    raw = authorization.strip()
    if raw.lower().startswith("bearer "):
        raw = raw[7:].strip()
    if not raw:
        return None
    key_hash = hash_api_key(raw)
    stmt: Select = (
        select(ApiKey)
        .where(ApiKey.key_hash == key_hash, ApiKey.revoked.is_(False))
        .options(selectinload(ApiKey.project))
    )
    result = await session.execute(stmt)
    api_key = result.scalar_one_or_none()
    if not api_key or not api_key.project:
        return None
    return AuthContext(api_key=api_key, project=api_key.project, org_id=api_key.project.org_id)


def period_start(period: str) -> datetime:
    now = datetime.now(timezone.utc)
    if period == "daily":
        return now.replace(hour=0, minute=0, second=0, microsecond=0)
    # monthly
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


async def sum_spend(
    session: AsyncSession,
    *,
    org_id: UUID,
    project_id: UUID | None,
    since: datetime,
) -> float:
    filters = [UsageEvent.org_id == org_id, UsageEvent.created_at >= since]
    if project_id is not None:
        filters.append(UsageEvent.project_id == project_id)
    stmt = select(func.coalesce(func.sum(UsageEvent.cost_usd), 0.0)).where(and_(*filters))
    result = await session.execute(stmt)
    return float(result.scalar_one() or 0.0)


@dataclass
class BudgetDecision:
    allowed: bool
    reason: str | None = None
    spent_usd: float = 0.0
    limit_usd: float | None = None
    action: str | None = None
    alert: bool = False


async def check_budgets(session: AsyncSession, auth: AuthContext) -> BudgetDecision:
    stmt = select(Budget).where(Budget.org_id == auth.org_id)
    result = await session.execute(stmt)
    budgets = list(result.scalars().all())
    if not budgets:
        return BudgetDecision(allowed=True)

    for budget in budgets:
        if budget.scope == "project" and budget.project_id not in (None, auth.project.id):
            continue
        if budget.scope == "org":
            project_id = None
        else:
            project_id = budget.project_id or auth.project.id
        spent = await sum_spend(
            session,
            org_id=auth.org_id,
            project_id=project_id,
            since=period_start(budget.period),
        )
        if spent >= budget.limit_usd:
            if budget.action == "block":
                return BudgetDecision(
                    allowed=False,
                    reason=f"Budget exceeded: spent ${spent:.4f} of ${budget.limit_usd:.4f} ({budget.period})",
                    spent_usd=spent,
                    limit_usd=budget.limit_usd,
                    action=budget.action,
                )
            return BudgetDecision(
                allowed=True,
                spent_usd=spent,
                limit_usd=budget.limit_usd,
                action=budget.action,
                alert=True,
                reason=f"Budget alert: spent ${spent:.4f} of ${budget.limit_usd:.4f}",
            )
        if spent >= budget.limit_usd * budget.alert_threshold:
            return BudgetDecision(
                allowed=True,
                spent_usd=spent,
                limit_usd=budget.limit_usd,
                action=budget.action,
                alert=True,
                reason=f"Approaching budget: spent ${spent:.4f} of ${budget.limit_usd:.4f}",
            )
    return BudgetDecision(allowed=True)
