"""Database access layer for the `diagnostic_sessions` table.

All operations use SQLAlchemy async ORM — no raw SQL.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.query import Query
from app.models.session import DiagnosticSession


class SessionService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_session(
        self,
        user_id: int | None,
        machine_model: str | None,
    ) -> DiagnosticSession:
        """Create a new diagnostic session with status='active' and return it."""
        session_obj = DiagnosticSession(
            user_id=user_id,
            machine_model=machine_model,
            status="active",
        )
        self._session.add(session_obj)
        await self._session.commit()
        await self._session.refresh(session_obj)
        return session_obj

    async def get_session(self, session_id: int) -> DiagnosticSession | None:
        """Return the DiagnosticSession row for *session_id*, or None if absent."""
        result = await self._session.scalars(
            select(DiagnosticSession).where(DiagnosticSession.id == session_id)
        )
        return result.first()

    async def update_status(self, session_id: int, status: str) -> None:
        """Update session status to one of: active | paused | completed.

        Also refreshes updated_at to the current timestamp.
        """
        await self._session.execute(
            update(DiagnosticSession)
            .where(DiagnosticSession.id == session_id)
            .values(status=status, updated_at=datetime.now(tz=timezone.utc))
        )
        await self._session.commit()

    async def delete_session(self, session_id: int) -> None:
        """Hard-delete a session and all its query rows (cascade via ORM)."""
        await self._session.execute(
            delete(Query).where(Query.session_id == session_id)
        )
        await self._session.execute(
            delete(DiagnosticSession).where(DiagnosticSession.id == session_id)
        )
        await self._session.commit()

    async def rename_session(self, session_id: int, title: str) -> None:
        """Update the human-readable title of a session (max 100 chars)."""
        await self._session.execute(
            update(DiagnosticSession)
            .where(DiagnosticSession.id == session_id)
            .values(title=title[:100])
        )
        await self._session.commit()

    async def get_history(self, session_id: int) -> list[Query]:
        """Return all Query rows for *session_id*, ordered by created_at ASC."""
        result = await self._session.scalars(
            select(Query)
            .where(Query.session_id == session_id)
            .order_by(Query.created_at.asc())
        )
        return list(result.all())
