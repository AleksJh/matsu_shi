"""SQLAlchemy ORM model for the `documents` table.

Schema mirrors migration 0001_initial_schema exactly.
Valid status values: indexed | error | processing
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import TIMESTAMP, BigInteger, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    original_filename: Mapped[str] = mapped_column(String(500), nullable=False)
    display_name: Mapped[str] = mapped_column(String(500), nullable=False)
    machine_model: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str | None] = mapped_column(String(255), nullable=True)
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    chunk_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str | None] = mapped_column(
        String(20), server_default="indexed", nullable=True
    )
    indexed_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("NOW()"), nullable=True
    )
    checksum: Mapped[str | None] = mapped_column(String(64), nullable=True, unique=True)
