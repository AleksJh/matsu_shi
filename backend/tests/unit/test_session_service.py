"""Unit tests for SessionService — written BEFORE implementation (TDD)."""
from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest


# ---------------------------------------------------------------------------
# Minimal stubs — avoids importing SQLAlchemy models before ORM is wired up.
# ---------------------------------------------------------------------------


class _SessionStub:
    """Minimal stand-in for the real DiagnosticSession ORM model."""

    def __init__(self, **kwargs: Any) -> None:
        for k, v in kwargs.items():
            setattr(self, k, v)


class _QueryStub:
    """Minimal stand-in for the real Query ORM model."""

    def __init__(self, **kwargs: Any) -> None:
        for k, v in kwargs.items():
            setattr(self, k, v)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_db() -> AsyncMock:
    """Return a fully-mocked AsyncSession (db connection)."""
    db = AsyncMock()
    db.scalars = MagicMock(return_value=AsyncMock())
    return db


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_service(db: AsyncMock):
    """Import and instantiate SessionService with the given db session."""
    from app.services.session_service import SessionService

    return SessionService(db)


def _scalars_first(db: AsyncMock, value: Any) -> None:
    """Configure db.scalars().first() to return *value*."""
    result = AsyncMock()
    result.first = MagicMock(return_value=value)
    db.scalars = AsyncMock(return_value=result)


def _scalars_all(db: AsyncMock, values: list[Any]) -> None:
    """Configure db.scalars().all() to return *values*."""
    result = AsyncMock()
    result.all = MagicMock(return_value=values)
    db.scalars = AsyncMock(return_value=result)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_session(mock_db: AsyncMock) -> None:
    """create_session must add a DiagnosticSession with status='active'."""
    svc = _make_service(mock_db)

    session_obj = await svc.create_session(user_id=1, machine_model="PC200-8")

    mock_db.add.assert_called_once()
    mock_db.commit.assert_awaited_once()
    mock_db.refresh.assert_awaited_once()
    assert session_obj.user_id == 1
    assert session_obj.machine_model == "PC200-8"
    assert session_obj.status == "active"


@pytest.mark.asyncio
async def test_get_session_found(mock_db: AsyncMock) -> None:
    """get_session returns DiagnosticSession when the row exists."""
    existing = _SessionStub(id=42, status="active", machine_model="WA470-6")
    _scalars_first(mock_db, existing)

    svc = _make_service(mock_db)
    result = await svc.get_session(42)

    assert result is existing


@pytest.mark.asyncio
async def test_get_session_not_found(mock_db: AsyncMock) -> None:
    """get_session returns None when the session does not exist."""
    _scalars_first(mock_db, None)

    svc = _make_service(mock_db)
    result = await svc.get_session(9999)

    assert result is None


@pytest.mark.asyncio
async def test_update_status(mock_db: AsyncMock) -> None:
    """update_status must execute an UPDATE and commit."""
    svc = _make_service(mock_db)

    await svc.update_status(session_id=10, status="paused")

    mock_db.execute.assert_awaited_once()
    mock_db.commit.assert_awaited_once()
    # Verify the UPDATE statement targets the correct session_id and status
    call_args = mock_db.execute.call_args[0][0]
    compiled = str(call_args.compile(compile_kwargs={"literal_binds": True}))
    assert "paused" in compiled
    assert "10" in compiled


@pytest.mark.asyncio
async def test_get_history_ordered(mock_db: AsyncMock) -> None:
    """get_history returns list[Query] ordered by created_at ASC."""
    from datetime import datetime, timezone

    q1 = _QueryStub(id=1, session_id=5, query_text="first", created_at=datetime(2024, 1, 1, tzinfo=timezone.utc))
    q2 = _QueryStub(id=2, session_id=5, query_text="second", created_at=datetime(2024, 1, 2, tzinfo=timezone.utc))
    _scalars_all(mock_db, [q1, q2])

    svc = _make_service(mock_db)
    history = await svc.get_history(session_id=5)

    assert history == [q1, q2]
    assert history[0].query_text == "first"
    assert history[1].query_text == "second"
