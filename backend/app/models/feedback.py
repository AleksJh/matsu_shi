"""SQLAlchemy ORM model for the `feedback` table.

Schema mirrors migration 0001_initial_schema exactly.
query_id has a UNIQUE constraint — enforces one feedback per query.
Valid rating values: 1 (thumbs up) | -1 (thumbs down)
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import TIMESTAMP, BigInteger, SmallInteger, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


class Feedback(Base):
    __tablename__ = "feedback"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    query_id: Mapped[int | None] = mapped_column(BigInteger, unique=True, nullable=True)
    user_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    rating: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    created_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("NOW()"), nullable=True
    )
