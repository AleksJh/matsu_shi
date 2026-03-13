"""ORM model for the `queries` table.

Matches migration 0001_initial_schema exactly.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import ARRAY, TIMESTAMP, BigInteger, Boolean, Float, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


class Query(Base):
    __tablename__ = "queries"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    session_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    user_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    query_text: Mapped[str] = mapped_column(Text, nullable=False)
    response_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    model_used: Mapped[str | None] = mapped_column(String(20), nullable=True)
    retrieval_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    query_class: Mapped[str | None] = mapped_column(String(20), nullable=True)
    retrieved_chunk_ids: Mapped[list[int] | None] = mapped_column(ARRAY(BigInteger), nullable=True)
    no_answer: Mapped[bool | None] = mapped_column(
        Boolean, nullable=True, server_default=text("false")
    )
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("NOW()"), nullable=True
    )
