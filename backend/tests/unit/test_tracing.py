"""TDD unit tests for Phase 4.6 — Langfuse tracing.

Tests mock the Langfuse client; no real network calls are made.

Run inside Docker:
    docker compose exec backend pytest tests/unit/test_tracing.py -v
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.tracing import create_trace, get_langfuse


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_langfuse(trace_id: str = "abc123def456abc123def456abc123de") -> tuple[MagicMock, MagicMock]:
    """Return (mock_client, mock_span) with pre-configured .trace_id and .id."""
    mock_lf = MagicMock()
    mock_span = MagicMock()
    mock_span.trace_id = trace_id
    mock_span.id = "deadbeef12345678"
    mock_lf.start_span.return_value = mock_span
    mock_lf.start_observation.return_value = MagicMock()
    return mock_lf, mock_span


def _make_chunk(id_: int, content: str = "content") -> MagicMock:
    from app.models.chunk import Chunk
    chunk = MagicMock(spec=Chunk)
    chunk.id = id_
    chunk.content = content
    return chunk


# ---------------------------------------------------------------------------
# Test 1: create_trace returns span with .trace_id on success
# ---------------------------------------------------------------------------


def test_create_trace_returns_span_on_success():
    """create_trace() should return a LangfuseSpan with .trace_id when Langfuse is up."""
    mock_lf, mock_span = _make_mock_langfuse("trace001")
    with patch("app.core.tracing.get_client", return_value=mock_lf):
        result = create_trace("rag-pipeline", input={"q": "test"})

    assert result is mock_span
    assert result.trace_id == "trace001"
    mock_lf.start_span.assert_called_once_with(name="rag-pipeline", input={"q": "test"})


# ---------------------------------------------------------------------------
# Test 2: create_trace returns None when Langfuse raises
# ---------------------------------------------------------------------------


def test_create_trace_returns_none_on_exception():
    """create_trace() must return None (not raise) when Langfuse client throws."""
    mock_lf = MagicMock()
    mock_lf.start_span.side_effect = RuntimeError("connection refused")
    with patch("app.core.tracing.get_client", return_value=mock_lf):
        result = create_trace("rag-pipeline")

    assert result is None


# ---------------------------------------------------------------------------
# Test 3: create_trace logs a warning on exception
# ---------------------------------------------------------------------------


def test_create_trace_logs_warning_on_exception():
    """create_trace() must emit a logger.warning when Langfuse is unavailable."""
    mock_lf = MagicMock()
    mock_lf.start_span.side_effect = ConnectionError("timeout")
    with (
        patch("app.core.tracing.get_client", return_value=mock_lf),
        patch("app.core.tracing.logger") as mock_logger,
    ):
        create_trace("test-trace")

    mock_logger.warning.assert_called_once()


# ---------------------------------------------------------------------------
# Test 4: retrieve() propagates trace_id through RetrievalResult
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_retrieve_records_trace_id_in_result():
    """retrieve() must return RetrievalResult.trace_id == root_span.trace_id."""
    from app.rag.retriever import retrieve

    trace_id = "cafebabe" * 4  # 32-char hex

    mock_lf, mock_span = _make_mock_langfuse(trace_id)
    mock_span.start_span.return_value = MagicMock()  # child retrieval span

    chunk = _make_chunk(id_=1, content="hydraulic")
    jina_resp = MagicMock()
    jina_resp.raise_for_status = MagicMock()
    jina_resp.json.return_value = {"results": [{"index": 0, "relevance_score": 0.9}]}
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.post = AsyncMock(return_value=jina_resp)

    async def _embed_stub(text: str) -> list[float]:
        return [0.0] * 4

    with (
        patch("app.core.tracing.get_client", return_value=mock_lf),
        patch("app.rag.retriever.create_trace", return_value=mock_span),
        patch("app.rag.retriever.dense_retrieve", AsyncMock(return_value=[(chunk, 0.8)])),
        patch("app.rag.retriever.sparse_retrieve", AsyncMock(return_value=[])),
        patch("app.rag.retriever.httpx.AsyncClient", return_value=mock_client),
    ):
        result = await retrieve("hydraulic pump", "PC300-8", AsyncMock(), embedder_fn=_embed_stub)

    assert result.trace_id == trace_id, (
        f"Expected trace_id={trace_id!r}, got {result.trace_id!r}"
    )


# ---------------------------------------------------------------------------
# Test 5: retrieve() with no_answer=True still records trace_id
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_retrieve_no_answer_still_records_trace_id():
    """no_answer early return must include trace_id in RetrievalResult."""
    from app.rag.retriever import retrieve

    trace_id = "deadbeef" * 4  # 32-char hex

    mock_lf, mock_span = _make_mock_langfuse(trace_id)
    mock_span.start_span.return_value = MagicMock()

    chunk = _make_chunk(id_=1)

    async def _embed_stub(text: str) -> list[float]:
        return [0.0] * 4

    with (
        patch("app.core.tracing.get_client", return_value=mock_lf),
        patch("app.rag.retriever.create_trace", return_value=mock_span),
        patch("app.rag.retriever.dense_retrieve", AsyncMock(return_value=[(chunk, 0.10)])),
        patch("app.rag.retriever.sparse_retrieve", AsyncMock(return_value=[])),
    ):
        result = await retrieve("unknown", "PC300-8", AsyncMock(), embedder_fn=_embed_stub)

    assert result.no_answer is True
    assert result.trace_id == trace_id, (
        f"no_answer path must set trace_id={trace_id!r}, got {result.trace_id!r}"
    )
