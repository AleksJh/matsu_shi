"""TDD unit tests for sparse_retrieve() — PRD §5.2, §4.4.

Tests are written alongside the implementation (TDD order).
All tests must pass after sparse_retriever.py is implemented.

Run inside Docker:
    docker compose exec backend pytest tests/unit/test_sparse_retriever.py -v
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

# ---------------------------------------------------------------------------
# Import the real module — no heavy deps in sparse_retriever.py import chain:
#   sparse_retriever -> app.models.chunk -> app.models (Base) -> sqlalchemy
# No DB connection is created at import time.
# ---------------------------------------------------------------------------
from app.rag.sparse_retriever import sparse_retrieve
from app.models.chunk import Chunk


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_chunk(id_: int = 1, machine_model: str = "PC300-8") -> MagicMock:
    """Return a minimal Chunk-like mock (not a real ORM row)."""
    chunk = MagicMock(spec=Chunk)
    chunk.id = id_
    chunk.machine_model = machine_model
    return chunk


def _mock_session(rows: list) -> AsyncMock:
    """Return an AsyncSession mock whose execute().all() returns *rows*."""
    result = MagicMock()
    result.all.return_value = rows
    session = AsyncMock()
    session.execute.return_value = result
    return session


# ---------------------------------------------------------------------------
# Test 1: Happy path — returns (Chunk, float) tuples sorted by score DESC
# ---------------------------------------------------------------------------


async def test_happy_path_returns_sorted_desc():
    """sparse_retrieve returns list[(Chunk, score)] sorted score DESC."""
    chunks = [_make_chunk(i) for i in range(3)]
    # DB returns rows ordered by ts_rank DESC (0.9 > 0.6 > 0.3)
    rows = [
        (chunks[0], 0.9),
        (chunks[1], 0.6),
        (chunks[2], 0.3),
    ]
    session = _mock_session(rows)

    result = await sparse_retrieve("замена масляного фильтра", "PC300-8", session, top_k=20)

    assert len(result) == 3
    for chunk_obj, score in result:
        assert isinstance(score, float)
    scores = [score for _, score in result]
    assert scores == sorted(scores, reverse=True)
    assert pytest.approx(scores[0]) == 0.9
    assert pytest.approx(scores[1]) == 0.6
    assert pytest.approx(scores[2]) == 0.3


# ---------------------------------------------------------------------------
# Test 2: machine_model pre-filter is included in the SQL query (PRD §4.4)
# ---------------------------------------------------------------------------


async def test_machine_model_filter_applied():
    """The WHERE clause must reference machine_model column (PRD §4.4)."""
    session = _mock_session([])

    await sparse_retrieve("фильтр", "D375A", session, top_k=5)

    assert session.execute.called, "session.execute must be called"
    stmt = session.execute.call_args.args[0]
    sql_str = str(stmt.compile(compile_kwargs={"literal_binds": False}))
    assert "machine_model" in sql_str, (
        f"machine_model filter not found in compiled SQL:\n{sql_str}"
    )


# ---------------------------------------------------------------------------
# Test 3: Empty result — returns [] without exception
# ---------------------------------------------------------------------------


async def test_empty_result_returns_empty_list():
    """When the DB has no matching chunks, sparse_retrieve returns []."""
    session = _mock_session([])

    result = await sparse_retrieve("неизвестный запрос", "WA500-8", session, top_k=20)

    assert result == []


# ---------------------------------------------------------------------------
# Test 4: top_k parameter is respected (LIMIT applied)
# ---------------------------------------------------------------------------


async def test_top_k_limit_applied():
    """sparse_retrieve respects top_k and includes LIMIT in the query."""
    chunks = [_make_chunk(i) for i in range(5)]
    rows = [(c, 0.9 - 0.1 * i) for i, c in enumerate(chunks)]
    session = _mock_session(rows)

    result = await sparse_retrieve("гидравлика", "PC300-8", session, top_k=5)

    assert len(result) == 5
    stmt = session.execute.call_args.args[0]
    sql_str = str(stmt.compile(compile_kwargs={"literal_binds": False}))
    assert "LIMIT" in sql_str.upper(), "LIMIT clause must be present in query"


# ---------------------------------------------------------------------------
# Test 5: score type — always float via float(r) conversion
# ---------------------------------------------------------------------------


async def test_score_type_is_float():
    """Score is always a Python float regardless of DB return type."""
    chunk = _make_chunk()
    # Simulate DB returning various numeric types (int, Decimal-like)
    for raw_score in [1, 0, 0.75, "0.5"]:
        session = _mock_session([(chunk, raw_score)])
        result = await sparse_retrieve("запрос", "PC300-8", session, top_k=1)
        assert len(result) == 1
        _, score = result[0]
        assert isinstance(score, float), f"score must be float, got {type(score)} for raw={raw_score!r}"
