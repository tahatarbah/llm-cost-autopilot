from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from llm_shared import (
    ApiKeyCreate,
    ApiKeyOut,
    BudgetCreate,
    BudgetOut,
    OrgCreate,
    OrgOut,
    ProjectCreate,
    ProjectOut,
    SpendSummary,
    UsageEventOut,
)

from gateway.auth import authenticate_api_key, period_start, sum_spend
from gateway.db import get_session
from gateway.db.models import (
    ApiKey,
    Budget,
    Membership,
    Organization,
    Project,
    UsageEvent,
    User,
    generate_api_key,
)

router = APIRouter(prefix="/admin", tags=["admin"])


def _slugify(value: str) -> str:
    cleaned = "".join(c.lower() if c.isalnum() else "-" for c in value).strip("-")
    while "--" in cleaned:
        cleaned = cleaned.replace("--", "-")
    return cleaned or "item"


async def _require_admin_token(x_admin_token: str | None = Header(default=None)) -> None:
    from llm_shared.settings import settings

    if not x_admin_token or x_admin_token != settings.gateway_secret:
        raise HTTPException(status_code=401, detail="Invalid admin token")


@router.post("/orgs", response_model=OrgOut)
async def create_org(
    body: OrgCreate,
    session: AsyncSession = Depends(get_session),
    _: None = Depends(_require_admin_token),
) -> Organization:
    slug = body.slug or _slugify(body.name)
    existing = await session.execute(select(Organization).where(Organization.slug == slug))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Organization slug already exists")
    org = Organization(name=body.name, slug=slug)
    session.add(org)
    await session.commit()
    await session.refresh(org)
    return org


@router.get("/orgs", response_model=list[OrgOut])
async def list_orgs(
    session: AsyncSession = Depends(get_session),
    _: None = Depends(_require_admin_token),
) -> list[Organization]:
    result = await session.execute(select(Organization).order_by(Organization.created_at.desc()))
    return list(result.scalars().all())


@router.post("/orgs/{org_id}/projects", response_model=ProjectOut)
async def create_project(
    org_id: UUID,
    body: ProjectCreate,
    session: AsyncSession = Depends(get_session),
    _: None = Depends(_require_admin_token),
) -> Project:
    org = await session.get(Organization, org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Org not found")
    slug = body.slug or _slugify(body.name)
    project = Project(org_id=org_id, name=body.name, slug=slug)
    session.add(project)
    await session.commit()
    await session.refresh(project)
    return project


@router.get("/orgs/{org_id}/projects", response_model=list[ProjectOut])
async def list_projects(
    org_id: UUID,
    session: AsyncSession = Depends(get_session),
    _: None = Depends(_require_admin_token),
) -> list[Project]:
    result = await session.execute(
        select(Project).where(Project.org_id == org_id).order_by(Project.created_at.desc())
    )
    return list(result.scalars().all())


@router.post("/api-keys", response_model=ApiKeyOut)
async def create_api_key(
    body: ApiKeyCreate,
    session: AsyncSession = Depends(get_session),
    _: None = Depends(_require_admin_token),
) -> ApiKeyOut:
    project = await session.get(Project, body.project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    raw, prefix, key_hash = generate_api_key()
    api_key = ApiKey(project_id=body.project_id, name=body.name, prefix=prefix, key_hash=key_hash)
    session.add(api_key)
    await session.commit()
    await session.refresh(api_key)
    return ApiKeyOut(
        id=api_key.id,
        project_id=api_key.project_id,
        name=api_key.name,
        prefix=api_key.prefix,
        created_at=api_key.created_at,
        key=raw,
    )


@router.get("/orgs/{org_id}/api-keys", response_model=list[ApiKeyOut])
async def list_api_keys(
    org_id: UUID,
    session: AsyncSession = Depends(get_session),
    _: None = Depends(_require_admin_token),
) -> list[ApiKeyOut]:
    stmt = (
        select(ApiKey)
        .join(Project, ApiKey.project_id == Project.id)
        .where(Project.org_id == org_id, ApiKey.revoked.is_(False))
        .order_by(ApiKey.created_at.desc())
    )
    result = await session.execute(stmt)
    keys = list(result.scalars().all())
    return [
        ApiKeyOut(
            id=k.id,
            project_id=k.project_id,
            name=k.name,
            prefix=k.prefix,
            created_at=k.created_at,
            key=None,
        )
        for k in keys
    ]


@router.delete("/api-keys/{key_id}")
async def revoke_api_key(
    key_id: UUID,
    session: AsyncSession = Depends(get_session),
    _: None = Depends(_require_admin_token),
) -> dict:
    api_key = await session.get(ApiKey, key_id)
    if not api_key:
        raise HTTPException(status_code=404, detail="API key not found")
    api_key.revoked = True
    await session.commit()
    return {"id": str(key_id), "revoked": True}


@router.post("/budgets", response_model=BudgetOut)
async def create_budget(
    body: BudgetCreate,
    org_id: UUID = Query(...),
    session: AsyncSession = Depends(get_session),
    _: None = Depends(_require_admin_token),
) -> BudgetOut:
    org = await session.get(Organization, org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Org not found")
    budget = Budget(
        org_id=org_id,
        project_id=body.project_id,
        scope=body.scope.value,
        period=body.period.value,
        limit_usd=body.limit_usd,
        action=body.action.value,
        alert_threshold=body.alert_threshold,
    )
    session.add(budget)
    await session.commit()
    await session.refresh(budget)
    spent = await sum_spend(
        session,
        org_id=org_id,
        project_id=budget.project_id,
        since=period_start(budget.period),
    )
    return BudgetOut(
        id=budget.id,
        org_id=budget.org_id,
        project_id=budget.project_id,
        scope=body.scope,
        period=body.period,
        limit_usd=budget.limit_usd,
        action=body.action,
        alert_threshold=budget.alert_threshold,
        spent_usd=spent,
    )


@router.get("/orgs/{org_id}/budgets", response_model=list[BudgetOut])
async def list_budgets(
    org_id: UUID,
    session: AsyncSession = Depends(get_session),
    _: None = Depends(_require_admin_token),
) -> list[BudgetOut]:
    result = await session.execute(select(Budget).where(Budget.org_id == org_id))
    budgets = list(result.scalars().all())
    out: list[BudgetOut] = []
    for b in budgets:
        spent = await sum_spend(
            session,
            org_id=org_id,
            project_id=b.project_id,
            since=period_start(b.period),
        )
        out.append(
            BudgetOut(
                id=b.id,
                org_id=b.org_id,
                project_id=b.project_id,
                scope=b.scope,  # type: ignore[arg-type]
                period=b.period,  # type: ignore[arg-type]
                limit_usd=b.limit_usd,
                action=b.action,  # type: ignore[arg-type]
                alert_threshold=b.alert_threshold,
                spent_usd=spent,
            )
        )
    return out


@router.delete("/budgets/{budget_id}")
async def delete_budget(
    budget_id: UUID,
    session: AsyncSession = Depends(get_session),
    _: None = Depends(_require_admin_token),
) -> dict:
    budget = await session.get(Budget, budget_id)
    if not budget:
        raise HTTPException(status_code=404, detail="Budget not found")
    await session.delete(budget)
    await session.commit()
    return {"id": str(budget_id), "deleted": True}


@router.get("/orgs/{org_id}/usage", response_model=list[UsageEventOut])
async def list_usage(
    org_id: UUID,
    project_id: UUID | None = None,
    limit: int = Query(100, le=500),
    session: AsyncSession = Depends(get_session),
    _: None = Depends(_require_admin_token),
) -> list[UsageEvent]:
    filters = [UsageEvent.org_id == org_id]
    if project_id:
        filters.append(UsageEvent.project_id == project_id)
    stmt = (
        select(UsageEvent)
        .where(and_(*filters))
        .order_by(UsageEvent.created_at.desc())
        .limit(limit)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


@router.get("/orgs/{org_id}/spend", response_model=SpendSummary)
async def spend_summary(
    org_id: UUID,
    session: AsyncSession = Depends(get_session),
    _: None = Depends(_require_admin_token),
) -> SpendSummary:
    today = period_start("daily")
    month = period_start("monthly")
    today_usd = await sum_spend(session, org_id=org_id, project_id=None, since=today)
    month_usd = await sum_spend(session, org_id=org_id, project_id=None, since=month)

    count_stmt = select(func.count(UsageEvent.id)).where(
        UsageEvent.org_id == org_id, UsageEvent.created_at >= month
    )
    request_count = int((await session.execute(count_stmt)).scalar_one() or 0)

    hit_stmt = select(func.count(UsageEvent.id)).where(
        UsageEvent.org_id == org_id,
        UsageEvent.created_at >= month,
        UsageEvent.cache_hit.is_(True),
    )
    hits = int((await session.execute(hit_stmt)).scalar_one() or 0)
    cache_hit_rate = (hits / request_count) if request_count else 0.0

    by_model_stmt = (
        select(
            UsageEvent.model,
            func.count(UsageEvent.id),
            func.coalesce(func.sum(UsageEvent.cost_usd), 0.0),
            func.coalesce(func.sum(UsageEvent.input_tokens), 0),
            func.coalesce(func.sum(UsageEvent.output_tokens), 0),
        )
        .where(UsageEvent.org_id == org_id, UsageEvent.created_at >= month)
        .group_by(UsageEvent.model)
        .order_by(func.sum(UsageEvent.cost_usd).desc())
    )
    by_model_rows = (await session.execute(by_model_stmt)).all()
    by_model = [
        {
            "model": r[0],
            "requests": int(r[1]),
            "cost_usd": float(r[2]),
            "input_tokens": int(r[3]),
            "output_tokens": int(r[4]),
        }
        for r in by_model_rows
    ]

    by_project_stmt = (
        select(
            Project.name,
            Project.id,
            func.count(UsageEvent.id),
            func.coalesce(func.sum(UsageEvent.cost_usd), 0.0),
        )
        .join(Project, Project.id == UsageEvent.project_id)
        .where(UsageEvent.org_id == org_id, UsageEvent.created_at >= month)
        .group_by(Project.id, Project.name)
        .order_by(func.sum(UsageEvent.cost_usd).desc())
    )
    by_project_rows = (await session.execute(by_project_stmt)).all()
    by_project = [
        {
            "project": r[0],
            "project_id": str(r[1]),
            "requests": int(r[2]),
            "cost_usd": float(r[3]),
        }
        for r in by_project_rows
    ]

    return SpendSummary(
        today_usd=today_usd,
        month_usd=month_usd,
        request_count=request_count,
        cache_hit_rate=cache_hit_rate,
        by_model=by_model,
        by_project=by_project,
    )


@router.get("/meta/me")
async def resolve_key_context(
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> dict:
    auth = await authenticate_api_key(session, authorization)
    if not auth:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return {
        "org_id": str(auth.org_id),
        "project_id": str(auth.project.id),
        "project_name": auth.project.name,
    }


@router.get("/orgs/{org_id}/members")
async def list_members(
    org_id: UUID,
    session: AsyncSession = Depends(get_session),
    _: None = Depends(_require_admin_token),
) -> list[dict]:
    org = await session.get(Organization, org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Org not found")
    stmt = (
        select(Membership, User)
        .join(User, User.id == Membership.user_id)
        .where(Membership.org_id == org_id)
    )
    rows = (await session.execute(stmt)).all()
    return [
        {
            "membership_id": str(m.id),
            "user_id": str(u.id),
            "email": u.email,
            "name": u.name,
            "role": m.role,
        }
        for m, u in rows
    ]


@router.post("/orgs/{org_id}/members")
async def add_member(
    org_id: UUID,
    email: str = Query(...),
    name: str = Query("Member"),
    role: str = Query("viewer"),
    session: AsyncSession = Depends(get_session),
    _: None = Depends(_require_admin_token),
) -> dict:
    if role not in {"owner", "admin", "viewer"}:
        raise HTTPException(status_code=400, detail="Invalid role")
    org = await session.get(Organization, org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Org not found")
    user = (await session.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if not user:
        user = User(email=email, name=name)
        session.add(user)
        await session.flush()
    existing = (
        await session.execute(
            select(Membership).where(Membership.org_id == org_id, Membership.user_id == user.id)
        )
    ).scalar_one_or_none()
    if existing:
        existing.role = role
    else:
        session.add(Membership(org_id=org_id, user_id=user.id, role=role))
    await session.commit()
    return {"org_id": str(org_id), "email": email, "role": role}
