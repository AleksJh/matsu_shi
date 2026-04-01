"""
TDD tests for Phase D: inline citation [N] markers.
These tests must FAIL before the implementation changes.
"""
import re
import pytest
from unittest.mock import AsyncMock, patch

from app.agent.responder import _normalize_citation_markers, respond, _SYSTEM_PROMPT
from app.rag.retriever import RetrievalResult
from app.models.chunk import Chunk
from app.schemas.query import QueryResponse, Citation


def _make_citation(doc_name: str = "WB97S Manual", section: str = "Hydraulic", page: int = 47) -> Citation:
    return Citation(doc_name=doc_name, section=section, page=page, visual_url=None)


def _make_retrieval_result(max_score: float = 0.80) -> RetrievalResult:
    chunk = Chunk()
    chunk.id = 1
    chunk.content = "Гидравлический фильтр требует замены каждые 500 часов."
    chunk.chunk_type = "text"
    chunk.section_title = "Hydraulic System"
    chunk.page_number = 47
    chunk.machine_model = "WB97S"
    chunk.visual_refs = []
    return RetrievalResult(
        chunks=[(chunk, max_score)],
        max_score=max_score,
        no_answer=False,
        recommended_model="gemini-2.5-flash-lite",
    )


def _make_llm_response(answer: str = "Замените фильтр [1].", citations: list | None = None) -> QueryResponse:
    if citations is None:
        citations = [_make_citation()]
    return QueryResponse(
        answer=answer,
        citations=citations,
        model_used="lite",
        no_answer=False,
        retrieval_score=0.80,
        query_class="simple",
        session_id=None,
    )


# --- Test _normalize_citation_markers ---

def test_normalize_keeps_valid_markers():
    answer = "текст [1] и [2]."
    citations = [_make_citation(), _make_citation("Doc2")]
    result = _normalize_citation_markers(answer, citations)
    assert "[1]" in result
    assert "[2]" in result


def test_normalize_strips_out_of_range():
    answer = "текст [3]"
    citations = [_make_citation(), _make_citation("Doc2")]
    result = _normalize_citation_markers(answer, citations)
    assert "[3]" not in result


def test_normalize_no_markers_passthrough():
    answer = "Информация не найдена. Попробуйте добавить конкретику."
    citations = []
    result = _normalize_citation_markers(answer, citations)
    assert result == answer


def test_normalize_valid_marker_not_stripped():
    answer = "см. инструкцию [1]"
    citations = [_make_citation()]
    result = _normalize_citation_markers(answer, citations)
    assert "[1]" in result


# --- Test system prompt ---

def test_system_prompt_uses_N_markers():
    assert "[N]" in _SYSTEM_PROMPT


def test_system_prompt_does_not_use_old_format():
    assert "[Документ:" not in _SYSTEM_PROMPT
