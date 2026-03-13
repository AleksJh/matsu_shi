"""Database access layer for the `feedback` table.

All operations use SQLAlchemy async ORM — no raw SQL.
"""
from __future__ import annotations

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.feedback import Feedback


class FeedbackService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add_feedback(
        self,
        query_id: int,
        user_id: int,
        rating: int,
    ) -> Feedback:
        """Insert a feedback row and return it.

        Args:
            query_id: FK → queries.id (UNIQUE constraint enforces one per query).
            user_id:  FK → users.id.
            rating:   1 (thumbs up) or -1 (thumbs down).

        Raises:
            IntegrityError: re-raised when feedback for this query_id already exists.
                            The API layer catches it and returns HTTP 409.
        """
        feedback = Feedback(query_id=query_id, user_id=user_id, rating=rating)
        self._session.add(feedback)
        try:
            await self._session.commit()
        except IntegrityError:
            await self._session.rollback()
            raise
        await self._session.refresh(feedback)
        return feedback
