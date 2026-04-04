"""Database access layer for the `users` table.

All operations use SQLAlchemy async ORM — no raw SQL.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


class UserService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_telegram_id(self, telegram_user_id: int) -> User | None:
        """Return the User row for *telegram_user_id*, or None if absent."""
        result = await self._session.scalars(
            select(User).where(User.telegram_user_id == telegram_user_id)
        )
        return result.first()

    async def create_pending(
        self,
        telegram_user_id: int,
        username: str | None,
        first_name: str | None,
        full_name: str | None = None,
        country: str | None = None,
        city: str | None = None,
        email: str | None = None,
        phone: str | None = None,
    ) -> User:
        """Insert a new User with status='pending' and return the persisted row."""
        user = User(
            telegram_user_id=telegram_user_id,
            username=username,
            first_name=first_name,
            status="pending",
            full_name=full_name,
            country=country,
            city=city,
            email=email,
            phone=phone,
        )
        self._session.add(user)
        await self._session.commit()
        await self._session.refresh(user)
        return user

    async def update_status(
        self,
        telegram_user_id: int,
        status: str,
        approved_by: str | None = None,
    ) -> User:
        """Update user status and return the refreshed row.

        Sets approved_at only when transitioning to 'active'.
        approved_by is recorded for all status changes when provided.
        """
        result = await self._session.scalars(
            select(User).where(User.telegram_user_id == telegram_user_id)
        )
        user = result.first()
        if user is None:
            raise ValueError(f"User with telegram_user_id={telegram_user_id} not found")

        user.status = status
        if approved_by is not None:
            user.approved_by = approved_by
        if status == "active":
            user.approved_at = datetime.now(tz=timezone.utc)

        await self._session.commit()
        await self._session.refresh(user)
        return user

    async def list_by_status(self, status: str | None = None) -> list[User]:
        """Return all users, optionally filtered by status, ordered by created_at DESC."""
        query = select(User).order_by(User.created_at.desc())
        if status is not None:
            query = query.where(User.status == status)
        result = await self._session.scalars(query)
        return list(result.all())

    async def get_stats(self) -> dict[str, int]:
        """Return a count breakdown by status plus total.

        Returns: {"total": N, "active": N, "pending": N, "denied": N, "banned": N}
        """
        all_users = await self.list_by_status()
        stats: dict[str, int] = {
            "total": len(all_users),
            "active": 0,
            "pending": 0,
            "denied": 0,
            "banned": 0,
        }
        for user in all_users:
            if user.status in stats:
                stats[user.status] += 1
        return stats
