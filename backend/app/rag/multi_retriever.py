"""Multi-query retrieval with parallel execution and chunk deduplication.

Public API:
    multi_retrieve(queries, machine_model, session) -> RetrievalResult

Runs N retrieve() calls in parallel via asyncio.gather, deduplicates chunks
by chunk.id keeping the highest Jina reranker score, and returns a merged
RetrievalResult. Falls back to single retrieve() when len(queries) == 1.
"""
from __future__ import annotations

import asyncio

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.router import route_query
from app.core.config import settings
from app.models.chunk import Chunk
from app.rag.retriever import RetrievalResult, retrieve


async def multi_retrieve(
    queries: list[str],
    machine_model: str,
    session: AsyncSession,
) -> RetrievalResult:
    """Run N retrieve() calls in parallel and merge results.

    Args:
        queries: 1–N search queries from the reformulator.
        machine_model: Machine model identifier for pre-filtering chunks.
        session: Async SQLAlchemy session (retrieve() creates its own
                 AsyncSessionLocal per call, so sharing is safe).

    Returns:
        Merged RetrievalResult:
        - no_answer=True only if ALL individual results are no_answer
        - chunks: deduped by chunk.id keeping highest score, top-10
        - max_score: global max across all results
        - recommended_model: derived from global max_score

    Notes:
        retrieve() already creates its own AsyncSessionLocal() for dense and
        sparse sub-queries, so N parallel calls do NOT share session state.
    """
    if len(queries) == 1:
        return await retrieve(queries[0], machine_model, session)

    all_results: list[RetrievalResult] = await asyncio.gather(
        *[retrieve(q, machine_model, session) for q in queries]
    )

    # no_answer only if ALL queries returned no_answer
    if all(r.no_answer for r in all_results):
        return all_results[0]

    # Merge: dedup by chunk.id, keep highest Jina score per chunk
    seen: dict[int, tuple[Chunk, float]] = {}
    max_score = 0.0
    for result in all_results:
        max_score = max(max_score, result.max_score)
        for chunk, score in result.chunks:
            if chunk.id not in seen or score > seen[chunk.id][1]:
                seen[chunk.id] = (chunk, score)

    # Sort by score DESC, cap at 10
    merged_chunks = sorted(seen.values(), key=lambda x: x[1], reverse=True)[:10]

    # Model routing based on global max_score
    recommended = route_query(max_score, "complex")

    return RetrievalResult(
        chunks=merged_chunks,
        max_score=max_score,
        no_answer=False,
        recommended_model=recommended,
        trace_id=all_results[0].trace_id,
    )
