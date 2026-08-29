from __future__ import annotations

import argparse
import asyncio
import sys

from sqlalchemy import select

from gateway.db import SessionLocal, init_db
from gateway.db.models import (
    Membership,
    Organization,
    Project,
    RoutingPolicy,
    User,
    generate_api_key,
    ApiKey,
)
from gateway.routing import DEFAULT_ALIASES


async def seed(
    *,
    org_name: str = "Personal",
    project_name: str = "Default",
    admin_email: str = "admin@localhost",
    admin_name: str = "Admin",
) -> str:
    await init_db()
    async with SessionLocal() as session:
        org = (
            await session.execute(select(Organization).where(Organization.slug == "personal"))
        ).scalar_one_or_none()
        if not org:
            org = Organization(name=org_name, slug="personal")
            session.add(org)
            await session.flush()

        user = (
            await session.execute(select(User).where(User.email == admin_email))
        ).scalar_one_or_none()
        if not user:
            user = User(email=admin_email, name=admin_name)
            session.add(user)
            await session.flush()

        membership = (
            await session.execute(
                select(Membership).where(
                    Membership.org_id == org.id, Membership.user_id == user.id
                )
            )
        ).scalar_one_or_none()
        if not membership:
            session.add(Membership(org_id=org.id, user_id=user.id, role="owner"))

        project = (
            await session.execute(
                select(Project).where(Project.org_id == org.id, Project.slug == "default")
            )
        ).scalar_one_or_none()
        if not project:
            project = Project(org_id=org.id, name=project_name, slug="default")
            session.add(project)
            await session.flush()

        # Default routing policies (global)
        for alias, target in DEFAULT_ALIASES.items():
            existing = (
                await session.execute(
                    select(RoutingPolicy).where(
                        RoutingPolicy.org_id.is_(None), RoutingPolicy.alias == alias
                    )
                )
            ).scalar_one_or_none()
            if not existing:
                session.add(RoutingPolicy(org_id=None, alias=alias, target_model=target))

        # Create a fresh API key every seed run and print it
        raw, prefix, key_hash = generate_api_key()
        session.add(
            ApiKey(project_id=project.id, name="seed", prefix=prefix, key_hash=key_hash)
        )
        await session.commit()
        return raw


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Seed LLM Cost Autopilot org/project/admin")
    parser.add_argument("--org-name", default="Personal")
    parser.add_argument("--project-name", default="Default")
    parser.add_argument("--admin-email", default="admin@localhost")
    parser.add_argument("--admin-name", default="Admin")
    args = parser.parse_args(argv)
    raw_key = asyncio.run(
        seed(
            org_name=args.org_name,
            project_name=args.project_name,
            admin_email=args.admin_email,
            admin_name=args.admin_name,
        )
    )
    print("Seed complete.")
    print(f"Virtual API key (save now): {raw_key}")
    print("Use it as: Authorization: Bearer <key>")
    print("Admin token header: X-Admin-Token: <GATEWAY_SECRET>")


if __name__ == "__main__":
    main(sys.argv[1:])
