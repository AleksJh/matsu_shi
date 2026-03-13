"""SQLAlchemy ORM model for the `chunks` table.

Schema mirrors migration 0001_initial_schema exactly.
Valid chunk_type values: text | table | visual_caption
"""
from __future__ import annotations

import os

from sqlalchemy import ARRAY, BigInteger, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from pgvector.sqlalchemy import Vector

from app.models import Base

EMBED_DIM = int(os.environ.get("EMBED_DIM", 1024))


class Chunk(Base):
    __tablename__ = "chunks"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    document_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("documents.id", ondelete="CASCADE"), nullable=True
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    chunk_type: Mapped[str | None] = mapped_column(
        String(20), server_default="text", nullable=True
    )
    section_title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    machine_model: Mapped[str | None] = mapped_column(String(255), nullable=True)
    visual_refs: Mapped[list[str] | None] = mapped_column(ARRAY(Text()), nullable=True)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBED_DIM), nullable=True)
    token_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
