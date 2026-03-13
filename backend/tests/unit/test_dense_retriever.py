"""TDD unit tests for dense_retrieve() — PRD §5.2, §4.4.

Tests are written alongside the implementation (TDD order).
All tests must pass after dense_retriever.py is implemented.

Run inside Docker:
    docker compose exec backend pytest tests/unit/test_dense_retriever.py -v
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

# ---------------------------------------------------------------------------
# Import the real module — no heavy deps in dense_retriever.py import chain:
#   dense_retriever -> app.models.chunk -> app.models (Base) -> sqlalchemy
#   dense_retriever -> pgvector.sqlalchemy (available in venv)
# No DB connection is created at import time.
# ---------------------------------------------------------------------------
from app.rag.dense_retriever import dense_retrieve
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
    """dense_retrieve returns list[(Chunk, score)] sorted score DESC."""
    chunks = [_make_chunk(i) for i in range(3)]
    # DB returns rows ordered by distance ASC (0.1 < 0.3 < 0.5)
    rows = [
        (chunks[0], 0.1),
        (chunks[1], 0.3),
        (chunks[2], 0.5),
    ]
    session = _mock_session(rows)

    result = await dense_retrieve([0.0] * 1024, "PC300-8", session, top_k=20)

    assert len(result) == 3
    # Each element is (Chunk, float)
    for chunk_obj, score in result:
        assert isinstance(score, float)
    # Scores must be descending: 0.9 > 0.7 > 0.5
    scores = [score for _, score in result]
    assert scores == sorted(scores, reverse=True)
    assert pytest.approx(scores[0]) == 0.9
    assert pytest.approx(scores[1]) == 0.7
    assert pytest.approx(scores[2]) == 0.5


# ---------------------------------------------------------------------------
# Test 2: machine_model pre-filter is included in the SQL query
# ---------------------------------------------------------------------------


async def test_machine_model_filter_applied():
    """The WHERE clause must reference machine_model column (PRD §4.4)."""
    session = _mock_session([])

    await dense_retrieve([0.0] * 4, "PC300-8", session, top_k=5)

    assert session.execute.called, "session.execute must be called"
    stmt = session.execute.call_args.args[0]
    # Compile to SQL string (placeholder style, no dialect needed)
    sql_str = str(stmt.compile(compile_kwargs={"literal_binds": False}))
    assert "machine_model" in sql_str, (
        f"machine_model filter not found in compiled SQL:\n{sql_str}"
    )


# ---------------------------------------------------------------------------
# Test 3: Empty result — returns [] without exception
# ---------------------------------------------------------------------------


async def test_empty_result_returns_empty_list():
    """When the DB has no matching chunks, dense_retrieve returns []."""
    session = _mock_session([])

    result = await dense_retrieve([0.1] * 1024, "D375A", session, top_k=20)

    assert result == []


# ---------------------------------------------------------------------------
# Test 4: top_k parameter is respected (LIMIT applied)
# ---------------------------------------------------------------------------


async def test_top_k_limit_applied():
    """dense_retrieve returns at most top_k results."""
    chunks = [_make_chunk(i) for i in range(5)]
    rows = [(c, 0.1 * (i + 1)) for i, c in enumerate(chunks)]
    session = _mock_session(rows)

    result = await dense_retrieve([0.0] * 1024, "PC300-8", session, top_k=5)

    assert len(result) == 5
    # Also verify the LIMIT clause is in the SQL
    stmt = session.execute.call_args.args[0]
    sql_str = str(stmt.compile(compile_kwargs={"literal_binds": False}))
    assert "LIMIT" in sql_str.upper(), "LIMIT clause must be present in query"


# ---------------------------------------------------------------------------
# Test 5: score conversion — score = 1.0 - distance, type float, range [0..1]
# ---------------------------------------------------------------------------


async def test_score_conversion_and_range():
    """Score equals 1.0 - cosine_distance and is always a float in [0, 1]."""
    chunk = _make_chunk()
    test_cases = [
        (0.0, 1.0),   # identical vectors
        (1.0, 0.0),   # orthogonal vectors
        (0.5, 0.5),   # midpoint
        (0.25, 0.75),
    ]
    for distance, expected_score in test_cases:
        session = _mock_session([(chunk, distance)])
        result = await dense_retrieve([0.0] * 4, "PC300-8", session, top_k=1)
        assert len(result) == 1
        _, score = result[0]
        assert isinstance(score, float), f"score must be float, got {type(score)}"
        assert pytest.approx(score) == expected_score
        assert 0.0 <= score <= 1.0, f"score {score} out of [0, 1] range"
