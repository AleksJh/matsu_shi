"""Hybrid retrieval orchestrator — Phase 3 top-level pipeline.

Public API:
    retrieve(query_text, machine_model, session, embedder_fn, top_k_final)
        -> RetrievalResult

Pipeline (PRD §5.2):
    1. Embed query
    2. Parallel dense (pgvector cosine) + sparse (PostgreSQL FTS) retrieval
    3. Score threshold check — skip Jina and return no_answer if max_score < 0.30
    4. Merge + dedup by chunk.id (dense-first priority) → up to 40 candidates
    5. Jina reranker (jina-reranker-v3) → top-5 final chunks
    6. Model routing (PRD §5.3, §6.2): lite vs advanced based on max cosine score

max_score is always taken from the dense channel BEFORE dedup.
"""
from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from dataclasses import dataclass, field

import httpx
from loguru import logger

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.tracing import create_trace, get_langfuse
from app.models.chunk import Chunk
from app.rag.dense_retriever import dense_retrieve
from app.rag.embedder import embed_text
from app.rag.sparse_retriever import sparse_retrieve


@dataclass
class RetrievalResult:
    chunks: list[tuple[Chunk, float]]  # top-k, sorted by rerank score DESC
    max_score: float                    # max cosine score from dense channel (pre-dedup)
    no_answer: bool
    recommended_model: str             # settings.LLM_LITE_MODEL or LLM_ADVANCED_MODEL
    trace_id: str | None = field(default=None)  # Langfuse trace_id for Phase 5 correlation


async def _rerank(
    query_text: str,
    candidates: list[tuple[Chunk, float]],
    top_k: int,
) -> list[tuple[Chunk, float]]:
    """Call Jina reranker and return top_k (Chunk, score) sorted DESC."""
    if not candidates:
        return []
    documents = [chunk.content for chunk, _ in candidates]
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://api.jina.ai/v1/rerank",
            headers={"Authorization": f"Bearer {settings.JINA_API_KEY}"},
            json={
                "model": settings.RERANKER_MODEL,
                "query": query_text,
                "documents": documents,
                "top_n": top_k,
            },
            timeout=30.0,
        )
        resp.raise_for_status()
    results = resp.json()["results"]
    # results[i]["index"] → index into candidates list
    reranked = [
        (candidates[r["index"]][0], float(r["relevance_score"]))
        for r in results
    ]
    return sorted(reranked, key=lambda x: x[1], reverse=True)


async def retrieve(
    query_text: str,
    machine_model: str,
    session: AsyncSession,
    embedder_fn: Callable = embed_text,
    top_k_final: int = 5,
) -> RetrievalResult:
    """Run hybrid retrieval pipeline and return a RetrievalResult.

    Args:
        query_text: Natural-language query from the mechanic.
        machine_model: Machine model identifier (mandatory pre-filter, PRD §4.4).
        session: Async SQLAlchemy session (injected by get_db() in Phase 5).
        embedder_fn: Async callable that takes text and returns list[float].
                     Defaults to embed_text; override in tests.
        top_k_final: Number of final chunks after reranking (default 5).

    Returns:
        RetrievalResult with chunks, max_score, no_answer flag, recommended_model.
    """
    # --- Langfuse: start root span (trace entry point) ---
    _t0 = time.monotonic()
    _root_span = create_trace(
        "rag-pipeline",
        input={"query_text": query_text, "machine_model": machine_model},
    )
    _trace_id: str | None = _root_span.trace_id if _root_span else None

    # 1. Embed query
    vector = await embedder_fn(query_text)
    if vector is None:
        logger.warning("embed_text returned None — returning no_answer for query: {!r}", query_text)
        return RetrievalResult(
            chunks=[],
            max_score=0.0,
            no_answer=True,
            recommended_model=settings.LLM_LITE_MODEL,
            trace_id=_trace_id,
        )

    # 2. Parallel dense + sparse retrieval
    dense_results, sparse_results = await asyncio.gather(
        dense_retrieve(vector, machine_model, session, top_k=20),
        sparse_retrieve(query_text, machine_model, session, top_k=20),
    )

    # 3. max cosine score from dense channel (before dedup)
    max_score = max((score for _, score in dense_results), default=0.0)

    # 4. no_answer early exit — skip Jina to save API cost (PRD §5.3)
    if max_score < settings.RETRIEVAL_NO_ANSWER_THRESHOLD:
        # Write trace before early return so no_answer is still observable
        try:
            if _root_span:
                _ret_span = _root_span.start_span(
                    name="retrieval",
                    input={"query_text": query_text, "machine_model": machine_model},
                    output={"max_score": max_score, "no_answer": True, "chunk_count": 0},
                    metadata={"latency_ms": round((time.monotonic() - _t0) * 1000)},
                )
                _ret_span.end()
                _root_span.end()
                get_langfuse().flush()
        except Exception as exc:
            logger.warning("Langfuse retrieval span (no_answer) failed: {}", exc)
        return RetrievalResult(
            chunks=[],
            max_score=max_score,
            no_answer=True,
            recommended_model=settings.LLM_LITE_MODEL,
            trace_id=_trace_id,
        )

    # 5. Merge + dedup by chunk.id (dense results first = priority per spec)
    seen_ids: set[int] = set()
    candidates: list[tuple[Chunk, float]] = []
    for chunk, score in dense_results + sparse_results:
        if chunk.id not in seen_ids:
            seen_ids.add(chunk.id)
            candidates.append((chunk, score))

    # 6. Jina reranker → top_k_final chunks
    top_chunks = await _rerank(query_text, candidates, top_k=top_k_final)

    # 7. Model routing (PRD §6.2)
    recommended = (
        settings.LLM_ADVANCED_MODEL
        if max_score < settings.RETRIEVAL_SCORE_THRESHOLD
        else settings.LLM_LITE_MODEL
    )

    # --- Langfuse: write retrieval span ---
    try:
        if _root_span:
            _ret_span = _root_span.start_span(
                name="retrieval",
                input={"query_text": query_text, "machine_model": machine_model},
                output={"max_score": max_score, "no_answer": False, "chunk_count": len(top_chunks)},
                metadata={"latency_ms": round((time.monotonic() - _t0) * 1000)},
            )
            _ret_span.end()
            _root_span.end()
            get_langfuse().flush()
    except Exception as exc:
        logger.warning("Langfuse retrieval span failed: {}", exc)

    return RetrievalResult(
        chunks=top_chunks,
        max_score=max_score,
        no_answer=False,
        recommended_model=recommended,
        trace_id=_trace_id,
    )
