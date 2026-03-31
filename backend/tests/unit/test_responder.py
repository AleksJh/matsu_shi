"""TDD tests for ResponderAgent and respond() function (Phase 4.4).

All LLM calls are mocked — no network required.
Tests cover:
  - no_answer bypass (no LLM call when retrieval_result.no_answer=True)
  - model selection (lite vs advanced via route_query)
  - computed field injection (model_used, retrieval_score, query_class, session_id)
  - context building from chunks
"""
from __future__ import annotations

import pytest
from dataclasses import dataclass, field
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from app.agent.responder import (
    NO_ANSWER_TEXT,
    ResponderAgent,
    _build_context,
    respond,
)
from app.core.config import settings
from app.rag.retriever import RetrievalResult
from app.schemas.query import Citation, QueryResponse


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_chunk(
    content: str = "Давление масла: 350 бар.",
    section_title: str = "Гидравлическая система",
    page_number: int = 42,
    visual_refs: list[str] | None = None,
    doc_name: str = "PC300-8 Shop Manual",
) -> MagicMock:
    """Return a mock Chunk ORM object with required attributes."""
    chunk = MagicMock()
    chunk.content = content
    chunk.section_title = section_title
    chunk.page_number = page_number
    chunk.visual_refs = visual_refs or []
    chunk.document = MagicMock()
    chunk.document.display_name = doc_name
    return chunk


def _make_retrieval_result(
    no_answer: bool = False,
    max_score: float = 0.80,
    chunks: list | None = None,
    recommended_model: str | None = None,
) -> RetrievalResult:
    if chunks is None:
        chunks = [(_make_chunk(), max_score)]
    if recommended_model is None:
        recommended_model = settings.LLM_LITE_MODEL
    return RetrievalResult(
        chunks=chunks,
        max_score=max_score,
        no_answer=no_answer,
        recommended_model=recommended_model,
    )


def _make_llm_response(
    answer: str = "Замените фильтр гидравлики.",
    citations: list[Citation] | None = None,
) -> MagicMock:
    """Fake result from ResponderAgent.run()."""
    if citations is None:
        citations = [Citation(doc_name="PC300-8 Shop Manual", section="Гидравлика", page=42)]
    qr = QueryResponse(
        answer=answer,
        citations=citations,
        model_used="PLACEHOLDER",       # overridden by respond()
        retrieval_score=0.0,            # overridden by respond()
        query_class="PLACEHOLDER",      # overridden by respond()
        no_answer=False,
        session_id=None,
    )
    result = MagicMock()
    result.output = qr
    return result


# ---------------------------------------------------------------------------
# 1. no_answer bypass — LLM must NOT be called
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_no_answer_bypasses_llm():
    """When no_answer=True, ResponderAgent.run() must never be invoked."""
    retrieval = _make_retrieval_result(no_answer=True, max_score=0.10, chunks=[])

    with patch.object(ResponderAgent, "run", new=AsyncMock()) as mock_run:
        await respond(
            query_text="Какой код?",
            retrieval_result=retrieval,
            query_class="simple",
            session_id=None,
        )
        mock_run.assert_not_called()


# ---------------------------------------------------------------------------
# 2. no_answer response contains Russian constant text
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_no_answer_text_is_russian_constant():
    retrieval = _make_retrieval_result(no_answer=True, max_score=0.10, chunks=[])

    result = await respond(
        query_text="Неизвестный запрос",
        retrieval_result=retrieval,
        query_class="simple",
        session_id=None,
    )

    assert result.answer == NO_ANSWER_TEXT
    assert result.no_answer is True
    assert result.citations == []


# ---------------------------------------------------------------------------
# 3. Lite model called when score high + simple
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_respond_uses_lite_model_for_high_score_simple():
    retrieval = _make_retrieval_result(max_score=0.80)
    fake_llm = _make_llm_response()

    with patch.object(ResponderAgent, "run", new=AsyncMock(return_value=fake_llm)) as mock_run:
        await respond(
            query_text="Какое давление масла?",
            retrieval_result=retrieval,
            query_class="simple",
            session_id=None,
        )

    _call_kwargs = mock_run.call_args
    model_arg = _call_kwargs.kwargs.get("model") or _call_kwargs.args[1] if len(_call_kwargs.args) > 1 else _call_kwargs.kwargs.get("model")
    assert settings.LLM_LITE_MODEL in model_arg


# ---------------------------------------------------------------------------
# 4. Advanced model called when score low
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_respond_uses_advanced_model_for_low_score():
    retrieval = _make_retrieval_result(max_score=0.50)
    fake_llm = _make_llm_response()

    with patch.object(ResponderAgent, "run", new=AsyncMock(return_value=fake_llm)) as mock_run:
        await respond(
            query_text="Многошаговая диагностика",
            retrieval_result=retrieval,
            query_class="simple",
            session_id=None,
        )

    _call_kwargs = mock_run.call_args
    model_arg = _call_kwargs.kwargs.get("model") or _call_kwargs.args[1] if len(_call_kwargs.args) > 1 else _call_kwargs.kwargs.get("model")
    assert settings.LLM_ADVANCED_MODEL in model_arg


# ---------------------------------------------------------------------------
# 5. model_used = "lite" when lite model selected
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_respond_injects_model_used_lite():
    retrieval = _make_retrieval_result(max_score=0.80)
    fake_llm = _make_llm_response()

    with patch.object(ResponderAgent, "run", new=AsyncMock(return_value=fake_llm)):
        result = await respond(
            query_text="Простой запрос",
            retrieval_result=retrieval,
            query_class="simple",
            session_id=None,
        )

    assert result.model_used == "lite"


# ---------------------------------------------------------------------------
# 6. model_used = "advanced" when advanced model selected
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_respond_injects_model_used_advanced():
    retrieval = _make_retrieval_result(max_score=0.50)
    fake_llm = _make_llm_response()

    with patch.object(ResponderAgent, "run", new=AsyncMock(return_value=fake_llm)):
        result = await respond(
            query_text="Сложный запрос",
            retrieval_result=retrieval,
            query_class="complex",
            session_id=None,
        )

    assert result.model_used == "advanced"


# ---------------------------------------------------------------------------
# 7. retrieval_score injected from retrieval_result.max_score
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_respond_injects_retrieval_score():
    retrieval = _make_retrieval_result(max_score=0.73)
    fake_llm = _make_llm_response()

    with patch.object(ResponderAgent, "run", new=AsyncMock(return_value=fake_llm)):
        result = await respond(
            query_text="Вопрос",
            retrieval_result=retrieval,
            query_class="simple",
            session_id=None,
        )

    assert result.retrieval_score == pytest.approx(0.73)


# ---------------------------------------------------------------------------
# 8. session_id propagated correctly
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_respond_injects_session_id():
    retrieval = _make_retrieval_result(max_score=0.80)
    fake_llm = _make_llm_response()

    with patch.object(ResponderAgent, "run", new=AsyncMock(return_value=fake_llm)):
        result = await respond(
            query_text="Вопрос",
            retrieval_result=retrieval,
            query_class="simple",
            session_id=99,
        )

    assert result.session_id == 99


# ---------------------------------------------------------------------------
# 9. query_class propagated correctly
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_respond_injects_query_class():
    retrieval = _make_retrieval_result(max_score=0.50)
    fake_llm = _make_llm_response()

    with patch.object(ResponderAgent, "run", new=AsyncMock(return_value=fake_llm)):
        result = await respond(
            query_text="Вопрос",
            retrieval_result=retrieval,
            query_class="complex",
            session_id=None,
        )

    assert result.query_class == "complex"


# ---------------------------------------------------------------------------
# 10. _build_context includes chunk content and section title
# ---------------------------------------------------------------------------

def test_build_context_includes_content_and_section():
    chunk = _make_chunk(
        content="Давление масла: 350 бар.",
        section_title="Гидравлика",
        page_number=42,
    )
    context = _build_context([(chunk, 0.9)])
    assert "Давление масла: 350 бар." in context
    assert "Гидравлика" in context
    assert "42" in context


# ---------------------------------------------------------------------------
# 11. _build_context includes visual refs when present
# ---------------------------------------------------------------------------

def test_build_context_includes_visual_refs():
    chunk = _make_chunk(
        content="Схема гидропривода.",
        visual_refs=["https://r2.example.com/page_42.webp"],
    )
    context = _build_context([(chunk, 0.8)])
    assert "https://r2.example.com/page_42.webp" in context


# ---------------------------------------------------------------------------
# 12. respond() retries on 504 DEADLINE_EXCEEDED
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_respond_retries_on_504():
    """respond() must retry when Google returns 504 DEADLINE_EXCEEDED."""
    retrieval = _make_retrieval_result(max_score=0.80)
    fake_llm = _make_llm_response()

    err_504 = Exception("status_code: 504, model_name: gemini-2.5-flash, body: DEADLINE_EXCEEDED")
    run_mock = AsyncMock(side_effect=[err_504, fake_llm])

    with patch.object(ResponderAgent, "run", new=run_mock):
        result = await respond(
            query_text="Вопрос",
            retrieval_result=retrieval,
            query_class="simple",
            session_id=None,
        )

    assert run_mock.call_count == 2
    assert result.answer == fake_llm.output.answer


# ---------------------------------------------------------------------------
# 13. respond() injects visual_url from chunk.visual_refs when page matches
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_visual_url_injected_from_chunk_visual_refs():
    """visual_url must be set on citations whose page matches a chunk with visual_refs."""
    visual_url = "https://r2.example.com/page42.webp"
    chunk = _make_chunk(page_number=42, visual_refs=[visual_url])
    retrieval = _make_retrieval_result(max_score=0.80, chunks=[(chunk, 0.80)])
    citation = Citation(doc_name="PC300-8 Shop Manual", section="Гидравлика", page=42)
    fake_llm = _make_llm_response(citations=[citation])

    with patch.object(ResponderAgent, "run", new=AsyncMock(return_value=fake_llm)):
        result = await respond(
            query_text="Вопрос",
            retrieval_result=retrieval,
            query_class="simple",
            session_id=None,
        )

    assert result.citations[0].visual_url == visual_url


# ---------------------------------------------------------------------------
# 14. respond() does NOT inject visual_url when no chunk page matches citation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_visual_url_not_injected_when_no_page_match():
    """visual_url must remain None when no retrieved chunk matches the citation page."""
    chunk = _make_chunk(page_number=42, visual_refs=["https://r2.example.com/page42.webp"])
    retrieval = _make_retrieval_result(max_score=0.80, chunks=[(chunk, 0.80)])
    citation = Citation(doc_name="PC300-8 Shop Manual", section="Гидравлика", page=99)
    fake_llm = _make_llm_response(citations=[citation])

    with patch.object(ResponderAgent, "run", new=AsyncMock(return_value=fake_llm)):
        result = await respond(
            query_text="Вопрос",
            retrieval_result=retrieval,
            query_class="simple",
            session_id=None,
        )

    assert result.citations[0].visual_url is None
