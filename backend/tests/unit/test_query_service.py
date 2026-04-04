"""TDD tests for QueryService.persist_query chunk_ids persistence (Fix 3)
and context-aware classification (Fix 1)."""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

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


# ---------------------------------------------------------------------------
# Fix 1: context-aware classification — process() must short-circuit
# ---------------------------------------------------------------------------

def _make_history_query(query_text: str = "Почему не заводится?", response_text: str = "Проверьте аккумулятор.") -> MagicMock:
    q = MagicMock()
    q.query_text = query_text
    q.response_text = response_text
    return q


def _make_process_retrieval_result() -> RetrievalResult:
    chunk = MagicMock()
    chunk.id = 1
    chunk.content = "Some content"
    return RetrievalResult(
        chunks=[(chunk, 0.80)],
        max_score=0.80,
        no_answer=False,
        recommended_model="gemini-lite",
    )


@pytest.mark.asyncio
async def test_process_with_history_uses_complex_without_calling_classifier():
    """When session history exists, process() must use 'complex' directly
    without calling ClassifierAgent — so advanced model is always used for follow-ups."""
    mock_session = MagicMock()
    mock_redis = MagicMock()

    fake_history = [_make_history_query()]
    fake_retrieval = _make_process_retrieval_result()
    fake_response = QueryResponse(
        answer="Проверьте генератор.",
        citations=[],
        model_used="advanced",
        retrieval_score=0.80,
        query_class="complex",
        no_answer=False,
        session_id=5,
    )

    with patch("app.services.query_service.check_rate_limit", new=AsyncMock()), \
         patch("app.services.query_service.SessionService") as mock_svc_cls, \
         patch("app.services.query_service.reformulate", new=AsyncMock(return_value=["follow-up expanded"])), \
         patch("app.services.query_service.multi_retrieve", new=AsyncMock(return_value=fake_retrieval)), \
         patch("app.services.query_service.classify_query", new=AsyncMock(return_value="simple")) as mock_classify, \
         patch("app.services.query_service.respond", new=AsyncMock(return_value=fake_response)) as mock_respond:

        mock_svc_instance = MagicMock()
        mock_svc_instance.get_history = AsyncMock(return_value=fake_history)
        mock_svc_cls.return_value = mock_svc_instance

        svc = QueryService(mock_session)
        result = await svc.process(
            query_text="А как заменить фильтр?",
            session_id=5,
            machine_model="WB97S",
            user_id=1,
            redis=mock_redis,
        )

    # classify_query must NOT be called — history short-circuits to "complex"
    mock_classify.assert_not_called()

    # respond() must receive query_class="complex"
    _, respond_kwargs = mock_respond.call_args
    assert respond_kwargs.get("query_class") == "complex", (
        f"Expected query_class='complex', got {respond_kwargs.get('query_class')!r}"
    )
