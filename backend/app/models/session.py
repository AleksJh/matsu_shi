"""ORM model for the `diagnostic_sessions` table.

Matches migration 0001_initial_schema exactly.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import TIMESTAMP, BigInteger, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


class DiagnosticSession(Base):
    __tablename__ = "diagnostic_sessions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    machine_model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'active'")
    )
    created_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("NOW()"), nullable=True
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("NOW()"), nullable=True
    )
