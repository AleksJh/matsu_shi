"""ResponderAgent — Phase 4.4.

Produces a structured QueryResponse from retrieval results using Pydantic AI.

Public API:
    respond(query_text, retrieval_result, query_class, session_id) -> QueryResponse

Bypass rule (PRD §5.3):
    When retrieval_result.no_answer is True (max_score < 0.30), the LLM is
    never called.  The fixed Russian "not found" string is returned directly.

Model selection:
    Delegates to route_query() from Phase 4.3.  The chosen model identifier
    is passed to ResponderAgent.run(model=...) to override the default.

Computed fields:
    The LLM output fills `answer` and `citations`.  All other QueryResponse
    fields (model_used, retrieval_score, query_class, no_answer, session_id)
    are injected by respond() after the LLM returns, so they are always
    consistent with the pipeline state regardless of what the LLM emits.
"""
from __future__ import annotations

import asyncio
import time

from loguru import logger
from pydantic_ai import Agent

from app.agent.router import route_query
from app.core.config import settings
from app.core.tracing import get_langfuse
from app.models.chunk import Chunk
from app.rag.retriever import RetrievalResult, retrieve_visual
from app.schemas.query import Citation, QueryResponse  # noqa: F401 (re-exported for tests)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Russian "not found" string — exact wording from PRD §6.3 / US-05; never modify
NO_ANSWER_TEXT = (
    "Информация не найдена. Попробуйте добавить конкретику в запрос."
)

# System prompt — exact text from PRD §6.3; never paraphrase or reword
_SYSTEM_PROMPT = """\
Ты — технический ассистент механиков Komatsu. Отвечай ТОЛЬКО на основе
предоставленного контекста из технических мануалов.

Правила:
1. После каждого технического утверждения вставляй маркер [N], где N — порядковый номер соответствующей записи в списке citations (начиная с 1). Каждый уникальный источник должен быть в citations ровно один раз.
2. Если в контексте нет ответа — строго отвечай:
   "Информация не найдена. Попробуйте добавить конкретику в запрос."
3. Никогда не домысливай. Никогда не используй знания вне контекста.
4. Структура ответа: Причина → Шаги устранения → Проверка → Цитаты.
5. Учитывай только данные модели техники, указанной в сессии."""

# ---------------------------------------------------------------------------
# Agent (default model = lite; overridden per call via respond())
# ---------------------------------------------------------------------------

ResponderAgent: Agent[None, QueryResponse] = Agent(
    model=f"google-gla:{settings.LLM_LITE_MODEL}",
    output_type=QueryResponse,
    system_prompt=_SYSTEM_PROMPT,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _normalize_citation_markers(answer: str, citations: list) -> str:
    """Strip [N] markers where N exceeds the length of the citations list."""
    import re
    n = len(citations)
    return re.sub(r'\[(\d+)\]', lambda m: m.group(0) if int(m.group(1)) <= n else '', answer)


def _build_context(chunks: list[tuple[Chunk, float]]) -> str:
    """Format retrieval chunks into a structured context string for the LLM.

    Each chunk is rendered as a numbered block containing the section title,
    page number, content, and (if present) Cloudflare R2 image URLs.
    """
    parts: list[str] = []
    for i, (chunk, _score) in enumerate(chunks, start=1):
        visual_line = ""
        if chunk.visual_refs:
            visual_line = f"\nВизуальные ресурсы: {', '.join(chunk.visual_refs)}"
        section = chunk.section_title or ""
        page = chunk.page_number or "?"
        parts.append(
            f"[Фрагмент {i}] {section} | Стр. {page}\n"
            f"{chunk.content}"
            f"{visual_line}"
        )
    return "\n\n---\n\n".join(parts)


def _no_answer_response(
    retrieval_result: RetrievalResult,
    query_class: str,
    session_id: int | None,
) -> QueryResponse:
    """Return the fixed no-answer QueryResponse without calling the LLM."""
    return QueryResponse(
        answer=NO_ANSWER_TEXT,
        citations=[],
        model_used="lite",
        retrieval_score=retrieval_result.max_score,
        query_class=query_class,
        no_answer=True,
        session_id=session_id,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def respond(
    query_text: str,
    retrieval_result: RetrievalResult,
    query_class: str,
    session_id: int | None,
    prior_context: list[str] | None = None,
    trace_id: str | None = None,
    machine_model: str = "",
) -> QueryResponse:
    """Generate a structured QueryResponse from retrieval results.

    Args:
        query_text:       Original mechanic query string.
        retrieval_result: Output from Phase 3 retrieve() — chunks + scores.
        query_class:      "simple" or "complex" from ClassifierAgent (Phase 4.2).
        session_id:       Active diagnostic_session PK, or None for simple queries.
        prior_context:    List of prior Q&A strings for session resume (complex only).
                          Each item: "Вопрос: {text}\nОтвет: {text}".
        trace_id:         Langfuse trace_id from RetrievalResult.trace_id (Phase 4.6).
                          When provided, a generation span is appended to the same trace.

    Returns:
        Fully populated QueryResponse with answer, citations, and all metadata.
    """
    _t0 = time.monotonic()

    # Bypass: no LLM call when no relevant chunks found (PRD §5.3)
    if retrieval_result.no_answer:
        return _no_answer_response(retrieval_result, query_class, session_id)

    # Build structured context string for the LLM
    context = _build_context(retrieval_result.chunks)

    # For queries with prior history (any class), prepend the diagnostic thread
    if prior_context:
        prior_block = "\n\n".join(prior_context)
        user_prompt = (
            f"История диагностики:\n{prior_block}\n\n"
            f"Контекст:\n{context}\n\n"
            f"Вопрос: {query_text}"
        )
    else:
        user_prompt = f"Контекст:\n{context}\n\nВопрос: {query_text}"

    # Select model via router (PRD §6.2); override the default at call time
    model_name = route_query(retrieval_result.max_score, query_class)
    model_label = "lite" if model_name == settings.LLM_LITE_MODEL else "advanced"

    for _attempt in range(20):
        try:
            result = await ResponderAgent.run(
                user_prompt,
                model=f"google-gla:{model_name}",
            )
            break
        except Exception as _exc:
            if _attempt < 19 and (
                "503" in str(_exc)
                or "504" in str(_exc)
                or "DEADLINE_EXCEEDED" in str(_exc)
            ):
                logger.warning(
                    "ResponderAgent transient error (attempt {}/20), waiting 2s: {}",
                    _attempt + 1,
                    _exc,
                )
                await asyncio.sleep(2)
            else:
                raise

    # Normalize [N] markers: strip any that reference a non-existent citation
    normalized_answer = _normalize_citation_markers(
        result.output.answer, result.output.citations
    )

    # Image search — one vector search filtered to visual_caption chunks
    visual_result = await retrieve_visual(
        query_text=query_text,
        machine_model=machine_model,
        min_score=settings.VISUAL_MIN_SCORE,
    )

    visual_url: str | None = None
    if visual_result:
        visual_chunk, visual_score = visual_result
        visual_url = visual_chunk.visual_refs[0] if visual_chunk.visual_refs else None
        logger.info(
            "visual_url found: score={:.3f} chunk_id={} (session={})",
            visual_score,
            visual_chunk.id,
            session_id,
        )
    else:
        logger.info("visual_url: no visual chunk above threshold (session={})", session_id)

    # Attach visual_url to the first citation only
    updated_citations = [
        c.model_copy(update={"visual_url": visual_url}) if i == 0 and visual_url else c
        for i, c in enumerate(result.output.citations)
    ]

    # Inject computed fields that must reflect pipeline state, not LLM output
    response = result.output.model_copy(
        update={
            "answer": normalized_answer,
            "citations": updated_citations,
            "model_used": model_label,
            "retrieval_score": retrieval_result.max_score,
            "query_class": query_class,
            "no_answer": False,
            "session_id": session_id,
        }
    )

    # --- Langfuse: write generation span to the existing trace ---
    try:
        if trace_id:
            from langfuse.types import TraceContext
            _lf = get_langfuse()
            _tc = TraceContext({"trace_id": trace_id})
            _gen = _lf.start_observation(
                as_type="generation",
                name="llm-response",
                trace_context=_tc,
                model=model_name,
                input={"query_class": query_class, "context_length": len(context)},
                output={"model_used": model_label, "no_answer": False},
                metadata={
                    "latency_ms": round((time.monotonic() - _t0) * 1000),
                    "retrieval_score": retrieval_result.max_score,
                },
            )
            _gen.end()
            _lf.flush()
    except Exception as exc:
        logger.warning("Langfuse generation span failed: {}", exc)

    return response
