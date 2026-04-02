"""TDD tests for QueryService.persist_query chunk_ids persistence (Fix 3)."""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.models.query import Query
from app.rag.retriever import RetrievalResult
from app.schemas.query import QueryResponse
from app.services.query_service import QueryService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_chunk(chunk_id: int, content: str = "Some content") -> MagicMock:
    chunk = MagicMock()
    chunk.id = chunk_id
    chunk.content = content
    return chunk


def _make_retrieval_result(chunk_ids: list[int]) -> RetrievalResult:
    chunks = [(_make_chunk(cid), 0.75) for cid in chunk_ids]
    return RetrievalResult(
        chunks=chunks,
        max_score=0.75,
        no_answer=False,
        recommended_model="gemini-lite",
    )


def _make_response(no_answer: bool = False) -> QueryResponse:
    return QueryResponse(
        answer="Проверьте аккумулятор.",
        citations=[],
        model_used="advanced",
        retrieval_score=0.75,
        query_class="complex",
        no_answer=no_answer,
        session_id=1,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_persist_query_saves_chunk_ids_from_last_retrieval_result():
    """After process() sets _last_retrieval_result, persist_query() must
    extract and store the chunk IDs in the Query ORM row."""
    mock_session = MagicMock()
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()

    svc = QueryService(mock_session)
    svc._last_retrieval_result = _make_retrieval_result([101, 202, 303])

    await svc.persist_query(
        user_id=1,
        session_id=5,
        query_text="Почему не заводится?",
        response=_make_response(),
        latency_ms=1200,
    )

    mock_session.add.assert_called_once()
    query_obj: Query = mock_session.add.call_args[0][0]
    assert isinstance(query_obj, Query)
    assert query_obj.retrieved_chunk_ids == [101, 202, 303]


@pytest.mark.asyncio
async def test_persist_query_chunk_ids_none_when_no_retrieval_result():
    """If _last_retrieval_result is None (shouldn't happen in normal flow),
    retrieved_chunk_ids must be None — not crash."""
    mock_session = MagicMock()
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()

    svc = QueryService(mock_session)
    # _last_retrieval_result is None by default

    await svc.persist_query(
        user_id=1,
        session_id=None,
        query_text="Вопрос",
        response=_make_response(),
        latency_ms=500,
    )

    query_obj: Query = mock_session.add.call_args[0][0]
    assert query_obj.retrieved_chunk_ids is None


@pytest.mark.asyncio
async def test_persist_query_chunk_ids_empty_list_when_no_chunks():
    """RetrievalResult with empty chunks list must yield None (not empty list)."""
    mock_session = MagicMock()
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()

    svc = QueryService(mock_session)
    svc._last_retrieval_result = _make_retrieval_result([])

    await svc.persist_query(
        user_id=1,
        session_id=None,
        query_text="Вопрос",
        response=_make_response(),
        latency_ms=500,
    )

    query_obj: Query = mock_session.add.call_args[0][0]
    # empty list → None (consistent with existing or None behavior)
    assert query_obj.retrieved_chunk_ids is None
