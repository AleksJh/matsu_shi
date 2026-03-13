"""One-time script to create or update an admin user in the admin_users table.

Usage (run from backend/ directory):
    python scripts/create_admin.py --username admin --password <secret>
"""
from __future__ import annotations

import argparse
import asyncio
import sys

from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

# Must be run from backend/ so .env and app imports resolve correctly
from app.core.config import settings
from app.models import Base  # noqa: F401 — ensures metadata is populated
from app.models.admin_user import AdminUser

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


async def create_or_update_admin(username: str, password: str) -> None:
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        result = await session.execute(
            select(AdminUser).where(AdminUser.username == username)
        )
        existing: AdminUser | None = result.scalar_one_or_none()

        password_hash = _pwd_context.hash(password)

        if existing:
            existing.password_hash = password_hash
            action = "updated"
        else:
            session.add(AdminUser(username=username, password_hash=password_hash))
            action = "created"

        await session.commit()
        print(f"Admin user '{username}' {action} successfully.")

    await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create or update an admin user for the Matsu Shi dashboard."
    )
    parser.add_argument("--username", required=True, help="Admin username")
    parser.add_argument("--password", required=True, help="Plain-text password (will be hashed)")
    args = parser.parse_args()

    if len(args.password) < 8:
        print("Error: password must be at least 8 characters.", file=sys.stderr)
        sys.exit(1)

    asyncio.run(create_or_update_admin(args.username, args.password))


if __name__ == "__main__":
    main()
