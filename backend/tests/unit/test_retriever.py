"""TDD unit tests for retrieve() — PRD §5.2, §5.3, §6.2.

Tests mock all I/O: dense_retrieve, sparse_retrieve, embed_text, httpx.AsyncClient.
No real DB or network calls are made.

Run inside Docker:
    docker compose exec backend pytest tests/unit/test_retriever.py -v
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.chunk import Chunk
from app.rag.retriever import RetrievalResult, retrieve


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_chunk(id_: int, content: str = "some content") -> MagicMock:
    """Return a minimal Chunk-like mock."""
    chunk = MagicMock(spec=Chunk)
    chunk.id = id_
    chunk.content = content
    return chunk


def _jina_response(indices: list[int], scores: list[float]) -> MagicMock:
    """Build a mock httpx response that looks like Jina reranker output."""
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json.return_value = {
        "results": [
            {"index": idx, "relevance_score": score}
            for idx, score in zip(indices, scores)
        ]
    }
    return resp


def _mock_httpx_client(resp: MagicMock) -> MagicMock:
    """Return a mock httpx.AsyncClient context manager that returns *resp* on post()."""
    client = AsyncMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=None)
    client.post = AsyncMock(return_value=resp)
    return client


async def _embed_stub(text: str) -> list[float]:
    return [0.0] * 4


# ---------------------------------------------------------------------------
# Test 1: dedup — same chunk.id in both channels appears once in candidates
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dedup_same_id_appears_once():
    """Chunk present in both dense and sparse results is included only once."""
    shared_chunk = _make_chunk(id_=1, content="shared")
    dense_only = _make_chunk(id_=2, content="dense only")
    sparse_only = _make_chunk(id_=3, content="sparse only")

    dense_results = [(shared_chunk, 0.8), (dense_only, 0.75)]
    sparse_results = [(shared_chunk, 0.6), (sparse_only, 0.55)]

    # Jina returns all 3 candidates
    jina_resp = _jina_response([0, 1, 2], [0.9, 0.8, 0.7])
    mock_client = _mock_httpx_client(jina_resp)

    with (
        patch("app.rag.retriever.dense_retrieve", AsyncMock(return_value=dense_results)),
        patch("app.rag.retriever.sparse_retrieve", AsyncMock(return_value=sparse_results)),
        patch("app.rag.retriever.httpx.AsyncClient", return_value=mock_client),
    ):
        result = await retrieve("query", "PC300-8", AsyncMock(), embedder_fn=_embed_stub)

    # Jina was called with exactly 3 unique candidates
    call_body = mock_client.post.call_args.kwargs["json"]
    assert len(call_body["documents"]) == 3, (
        "Expected 3 unique candidates after dedup, "
        f"got {len(call_body['documents'])}"
    )


# ---------------------------------------------------------------------------
# Test 2: jina_called — correct request body sent when candidates exist
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_jina_called_with_correct_body():
    """When candidates exist Jina is called with Authorization header and correct fields."""
    chunk = _make_chunk(id_=1, content="hydraulic pump specs")
    dense_results = [(chunk, 0.75)]
    sparse_results = []

    jina_resp = _jina_response([0], [0.95])
    mock_client = _mock_httpx_client(jina_resp)

    with (
        patch("app.rag.retriever.dense_retrieve", AsyncMock(return_value=dense_results)),
        patch("app.rag.retriever.sparse_retrieve", AsyncMock(return_value=sparse_results)),
        patch("app.rag.retriever.httpx.AsyncClient", return_value=mock_client),
    ):
        result = await retrieve(
            "hydraulic pump pressure", "D375A", AsyncMock(), embedder_fn=_embed_stub
        )

    assert mock_client.post.called, "httpx.AsyncClient.post must be called when candidates exist"
    call_kwargs = mock_client.post.call_args.kwargs
    headers = call_kwargs["headers"]
    body = call_kwargs["json"]

    assert "Authorization" in headers
    assert headers["Authorization"].startswith("Bearer ")
    assert body["query"] == "hydraulic pump pressure"
    assert body["documents"] == ["hydraulic pump specs"]
    assert "model" in body
    assert "top_n" in body


# ---------------------------------------------------------------------------
# Test 3: no_answer — max_score < 0.30 returns no_answer=True, Jina skipped
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_no_answer_when_max_score_below_threshold():
    """max_score < RETRIEVAL_NO_ANSWER_THRESHOLD → no_answer=True, Jina not called."""
    chunk = _make_chunk(id_=1)
    dense_results = [(chunk, 0.15)]  # below 0.30
    sparse_results = [(chunk, 0.10)]

    mock_client = _mock_httpx_client(MagicMock())

    with (
        patch("app.rag.retriever.dense_retrieve", AsyncMock(return_value=dense_results)),
        patch("app.rag.retriever.sparse_retrieve", AsyncMock(return_value=sparse_results)),
        patch("app.rag.retriever.httpx.AsyncClient", return_value=mock_client),
    ):
        result = await retrieve("unknown query", "PC300-8", AsyncMock(), embedder_fn=_embed_stub)

    assert result.no_answer is True
    assert result.chunks == []
    assert not mock_client.post.called, "Jina must NOT be called when no_answer=True"


# ---------------------------------------------------------------------------
# Test 4: routing_advanced — max_score=0.50 → LLM_ADVANCED_MODEL
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_routing_advanced_when_score_below_065():
    """max_score=0.50 (< 0.65 threshold) → recommended_model = LLM_ADVANCED_MODEL."""
    chunk = _make_chunk(id_=1, content="engine spec")
    dense_results = [(chunk, 0.50)]
    sparse_results = []

    jina_resp = _jina_response([0], [0.88])
    mock_client = _mock_httpx_client(jina_resp)

    with (
        patch("app.rag.retriever.dense_retrieve", AsyncMock(return_value=dense_results)),
        patch("app.rag.retriever.sparse_retrieve", AsyncMock(return_value=sparse_results)),
        patch("app.rag.retriever.httpx.AsyncClient", return_value=mock_client),
    ):
        result = await retrieve("engine query", "PC300-8", AsyncMock(), embedder_fn=_embed_stub)

    from app.core.config import settings
    assert result.recommended_model == settings.LLM_ADVANCED_MODEL
    assert result.no_answer is False


# ---------------------------------------------------------------------------
# Test 5: routing_lite — max_score=0.70 → LLM_LITE_MODEL
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_routing_lite_when_score_above_065():
    """max_score=0.70 (≥ 0.65 threshold) → recommended_model = LLM_LITE_MODEL."""
    chunk = _make_chunk(id_=1, content="brake system")
    dense_results = [(chunk, 0.70)]
    sparse_results = []

    jina_resp = _jina_response([0], [0.92])
    mock_client = _mock_httpx_client(jina_resp)

    with (
        patch("app.rag.retriever.dense_retrieve", AsyncMock(return_value=dense_results)),
        patch("app.rag.retriever.sparse_retrieve", AsyncMock(return_value=sparse_results)),
        patch("app.rag.retriever.httpx.AsyncClient", return_value=mock_client),
    ):
        result = await retrieve("brake query", "D375A", AsyncMock(), embedder_fn=_embed_stub)

    from app.core.config import settings
    assert result.recommended_model == settings.LLM_LITE_MODEL
    assert result.no_answer is False


# ---------------------------------------------------------------------------
# Test 6: empty_inputs — both channels empty → no_answer=True, Jina not called
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_empty_inputs_returns_no_answer():
    """Both dense and sparse return [] → max_score=0.0, no_answer=True, Jina not called."""
    mock_client = _mock_httpx_client(MagicMock())

    with (
        patch("app.rag.retriever.dense_retrieve", AsyncMock(return_value=[])),
        patch("app.rag.retriever.sparse_retrieve", AsyncMock(return_value=[])),
        patch("app.rag.retriever.httpx.AsyncClient", return_value=mock_client),
    ):
        result = await retrieve("anything", "PC300-8", AsyncMock(), embedder_fn=_embed_stub)

    assert result.no_answer is True
    assert result.chunks == []
    assert result.max_score == 0.0
    assert not mock_client.post.called, "Jina must NOT be called when no candidates"
