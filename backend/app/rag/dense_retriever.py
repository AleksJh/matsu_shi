"""Dense retrieval via pgvector cosine similarity.

Public API:
    dense_retrieve(vector, machine_model, session, top_k=20)
        -> list[tuple[Chunk, float]]

Uses the <=> cosine distance operator.  Returns chunks sorted by cosine
similarity score DESC (score = 1.0 - cosine_distance, range [0..1]).
Chunks with NULL embeddings are excluded.  machine_model pre-filter is
mandatory per PRD §4.4 to prevent cross-contamination between models.
"""
from __future__ import annotations

from sqlalchemy import Float, cast, select
from sqlalchemy.ext.asyncio import AsyncSession

from pgvector.sqlalchemy import Vector

from app.models.chunk import Chunk


async def dense_retrieve(
    vector: list[float],
    machine_model: str,
    session: AsyncSession,
    top_k: int = 20,
) -> list[tuple[Chunk, float]]:
    """Return top-k chunks closest to *vector* for the given *machine_model*.

    Args:
        vector: Query embedding produced by embed_text().
        machine_model: Machine model identifier used as a mandatory pre-filter.
        session: Async SQLAlchemy session (injected by get_db() in Phase 5).
        top_k: Maximum number of results to return (default 20).

    Returns:
        List of (Chunk, score) tuples sorted by score DESC.
        score = 1.0 - cosine_distance, range [0.0 .. 1.0].
        Returns an empty list if no matching chunks exist.
    """
    distance_col = Chunk.embedding.op("<=>", return_type=Float())(cast(vector, Vector(len(vector))))
    stmt = (
        select(Chunk, distance_col.label("distance"))
        .where(Chunk.machine_model == machine_model)
        .where(Chunk.embedding.is_not(None))
        .order_by(distance_col)
        .limit(top_k)
    )
    rows = (await session.execute(stmt)).all()
    return [(chunk, 1.0 - float(distance)) for chunk, distance in rows]
