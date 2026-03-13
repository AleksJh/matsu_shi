"""Sparse retrieval via PostgreSQL Full-Text Search (FTS).

Public API:
    sparse_retrieve(query_text, machine_model, session, top_k=20)
        -> list[tuple[Chunk, float]]

Uses plainto_tsquery + to_tsvector + ts_rank with the "russian" FTS
configuration (Snowball morphological stemmer).  Returns chunks sorted by
ts_rank score DESC.  machine_model pre-filter is mandatory per PRD §4.4
to prevent cross-contamination between models.
"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chunk import Chunk


async def sparse_retrieve(
    query_text: str,
    machine_model: str,
    session: AsyncSession,
    top_k: int = 20,
) -> list[tuple[Chunk, float]]:
    """Return top-k chunks that match *query_text* for the given *machine_model*.

    Args:
        query_text: Natural-language query from the mechanic (arbitrary text).
        machine_model: Machine model identifier used as a mandatory pre-filter.
        session: Async SQLAlchemy session (injected by get_db() in Phase 5).
        top_k: Maximum number of results to return (default 20).

    Returns:
        List of (Chunk, score) tuples sorted by ts_rank score DESC.
        Returns an empty list if no matching chunks exist.
    """
    tsquery = func.plainto_tsquery("russian", query_text)
    tsvector = func.to_tsvector("russian", Chunk.content)
    rank = func.ts_rank(tsvector, tsquery)
    stmt = (
        select(Chunk, rank.label("rank"))
        .where(Chunk.machine_model == machine_model)
        .where(tsvector.op("@@")(tsquery))
        .order_by(rank.desc())
        .limit(top_k)
    )
    rows = (await session.execute(stmt)).all()
    return [(chunk, float(r)) for chunk, r in rows]
