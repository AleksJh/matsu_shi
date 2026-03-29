"""TDD tests for Gemini/OpenRouter 503 retry logic (Roadmap 9.6).

Covers:
  - classifier.classify_query(): retries on 503, raises on other errors,
    succeeds after N-1 failures.
  - responder.respond(): retries on 503, raises on other errors,
    succeeds after N-1 failures.
  - embedder.embed_text(): retries on 503, returns None after exhausting
    retries, returns None immediately on non-503 HTTP errors.

All asyncio.sleep calls are patched to avoid real waits.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from unittest.mock import AsyncMock, MagicMock, call, patch

import httpx
import pytest

from app.agent.classifier import ClassifierAgent, ClassifierOutput, classify_query
from app.agent.responder import NO_ANSWER_TEXT, ResponderAgent, respond
from app.rag.retriever import RetrievalResult
from app.schemas.query import Citation, QueryResponse


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_retrieval_result(
    max_score: float = 0.75,
    no_answer: bool = False,
) -> RetrievalResult:
    chunk = MagicMock()
    chunk.content = "Давление масла: 350 бар."
    chunk.section_title = "Гидравлическая система"
    chunk.page_number = 42
    chunk.visual_refs = []
    chunk.document = MagicMock()
    chunk.document.display_name = "PC300-8 Shop Manual"
    return RetrievalResult(
        chunks=[(chunk, max_score)],
        max_score=max_score,
        no_answer=no_answer,
        recommended_model="gemini-2.5-flash-lite",
    )


def _make_query_response() -> QueryResponse:
    return QueryResponse(
        answer="Замените фильтр гидравлики.",
        citations=[Citation(doc_name="PC300-8 Shop Manual", section="Гидравлика", page=42)],
        model_used="lite",
        retrieval_score=0.75,
        query_class="simple",
        no_answer=False,
        session_id=None,
    )


def _503_exception() -> Exception:
    """Return an exception whose str() contains '503', matching the retry guard."""
    return RuntimeError("Gemini API error: 503 UNAVAILABLE — Service temporarily unavailable")


def _non_503_exception() -> Exception:
    return RuntimeError("Gemini API error: 400 BAD_REQUEST — Invalid argument")


# ---------------------------------------------------------------------------
# ClassifierAgent retry tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@patch("app.agent.classifier.asyncio.sleep", new_callable=AsyncMock)
async def test_classifier_retries_on_503_then_succeeds(mock_sleep):
    """classify_query() retries on 503 and returns result on the 3rd attempt."""
    good_result = MagicMock()
    good_result.output = ClassifierOutput(query_class="simple")

    run_mock = AsyncMock(
        side_effect=[_503_exception(), _503_exception(), good_result]
    )
    with patch.object(ClassifierAgent, "run", run_mock):
        result = await classify_query("Какой код ошибки E03?")

    assert result == "simple"
    assert run_mock.call_count == 3
    assert mock_sleep.call_count == 2
    mock_sleep.assert_called_with(2)


@pytest.mark.asyncio
@patch("app.agent.classifier.asyncio.sleep", new_callable=AsyncMock)
async def test_classifier_raises_on_non_503(mock_sleep):
    """classify_query() raises immediately on a non-503 error (no retry)."""
    with patch.object(ClassifierAgent, "run", AsyncMock(side_effect=_non_503_exception())):
        with pytest.raises(RuntimeError, match="400"):
            await classify_query("some query")

    mock_sleep.assert_not_called()


@pytest.mark.asyncio
@patch("app.agent.classifier.asyncio.sleep", new_callable=AsyncMock)
async def test_classifier_raises_after_20_503s(mock_sleep):
    """classify_query() raises after exhausting all 20 attempts."""
    with patch.object(
        ClassifierAgent, "run", AsyncMock(side_effect=_503_exception())
    ):
        with pytest.raises(Exception, match="503"):
            await classify_query("some query")

    # 19 sleeps (attempts 0–18 retry; attempt 19 raises)
    assert mock_sleep.call_count == 19


# ---------------------------------------------------------------------------
# ResponderAgent retry tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@patch("app.agent.responder.asyncio.sleep", new_callable=AsyncMock)
async def test_responder_retries_on_503_then_succeeds(mock_sleep):
    """respond() retries on 503 and returns QueryResponse on the 2nd attempt."""
    good_result = MagicMock()
    good_result.output = _make_query_response()

    run_mock = AsyncMock(side_effect=[_503_exception(), good_result])
    retrieval = _make_retrieval_result()

    with patch.object(ResponderAgent, "run", run_mock):
        # Patch Langfuse to avoid real tracing setup
        with patch("app.agent.responder.get_langfuse", MagicMock()):
            response = await respond(
                query_text="Почему давит масло?",
                retrieval_result=retrieval,
                query_class="simple",
                session_id=None,
            )

    assert response.answer == "Замените фильтр гидравлики."
    assert run_mock.call_count == 2
    assert mock_sleep.call_count == 1
    mock_sleep.assert_called_with(2)


@pytest.mark.asyncio
@patch("app.agent.responder.asyncio.sleep", new_callable=AsyncMock)
async def test_responder_raises_on_non_503(mock_sleep):
    """respond() raises immediately on a non-503 error (no retry)."""
    retrieval = _make_retrieval_result()

    with patch.object(ResponderAgent, "run", AsyncMock(side_effect=_non_503_exception())):
        with pytest.raises(RuntimeError, match="400"):
            await respond(
                query_text="some query",
                retrieval_result=retrieval,
                query_class="simple",
                session_id=None,
            )

    mock_sleep.assert_not_called()


@pytest.mark.asyncio
async def test_responder_no_answer_bypass_skips_retry():
    """respond() with no_answer=True bypasses the LLM entirely — no retry needed."""
    retrieval = _make_retrieval_result(max_score=0.1, no_answer=True)

    with patch.object(ResponderAgent, "run", AsyncMock()) as run_mock:
        response = await respond(
            query_text="something irrelevant",
            retrieval_result=retrieval,
            query_class="simple",
            session_id=None,
        )

    run_mock.assert_not_called()
    assert response.no_answer is True
    assert response.answer == NO_ANSWER_TEXT


# ---------------------------------------------------------------------------
# embedder retry tests
# ---------------------------------------------------------------------------

def _mock_response_503() -> MagicMock:
    resp = MagicMock()
    resp.status_code = 503
    resp.raise_for_status = MagicMock(
        side_effect=httpx.HTTPStatusError(
            "HTTP 503",
            request=MagicMock(),
            response=resp,
        )
    )
    return resp


def _mock_response_200(vector: list[float]) -> MagicMock:
    resp = MagicMock()
    resp.status_code = 200
    resp.raise_for_status = MagicMock()
    resp.json = MagicMock(return_value={"data": [{"embedding": vector}]})
    return resp


def _patch_embedder_client(side_effects: list):
    """Patch httpx.AsyncClient.post to return side_effects in order."""
    from app.rag import embedder as emb_mod

    mock_post = AsyncMock(side_effect=side_effects)
    mock_instance = AsyncMock()
    mock_instance.post = mock_post
    mock_cls = MagicMock()
    mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_instance)
    mock_cls.return_value.__aexit__ = AsyncMock(return_value=None)

    return patch.object(
        emb_mod,
        "httpx",
        MagicMock(
            AsyncClient=mock_cls,
            HTTPStatusError=httpx.HTTPStatusError,
            TimeoutException=httpx.TimeoutException,
        ),
    ), mock_post


@patch("app.rag.embedder.asyncio.sleep", new_callable=AsyncMock)
def test_embed_text_retries_503_then_succeeds(mock_sleep):
    """embed_text() retries on 503 and returns vector on the 3rd attempt."""
    from app.rag import embedder as emb_mod

    vector = [0.1, 0.2, 0.3]
    responses = [_mock_response_503(), _mock_response_503(), _mock_response_200(vector)]
    ctx, mock_post = _patch_embedder_client(responses)

    with ctx:
        result = asyncio.run(emb_mod.embed_text("query text"))

    assert result == vector
    assert mock_post.call_count == 3
    assert mock_sleep.call_count == 2
    mock_sleep.assert_called_with(2)


@patch("app.rag.embedder.asyncio.sleep", new_callable=AsyncMock)
def test_embed_text_returns_none_after_20_503s(mock_sleep):
    """embed_text() returns None after exhausting all 20 retries on 503."""
    from app.rag import embedder as emb_mod

    responses = [_mock_response_503()] * 20
    ctx, mock_post = _patch_embedder_client(responses)

    with ctx:
        result = asyncio.run(emb_mod.embed_text("query text"))

    assert result is None
    assert mock_post.call_count == 20
    assert mock_sleep.call_count == 19  # sleeps between attempts 0–18


@patch("app.rag.embedder.asyncio.sleep", new_callable=AsyncMock)
def test_embed_text_non_503_returns_none_immediately(mock_sleep):
    """embed_text() returns None immediately on non-503 HTTP errors (no retry)."""
    from app.rag import embedder as emb_mod

    resp = MagicMock()
    resp.status_code = 401
    resp.raise_for_status = MagicMock(
        side_effect=httpx.HTTPStatusError("HTTP 401", request=MagicMock(), response=resp)
    )
    ctx, mock_post = _patch_embedder_client([resp])

    with ctx:
        result = asyncio.run(emb_mod.embed_text("query text"))

    assert result is None
    assert mock_post.call_count == 1
    mock_sleep.assert_not_called()
