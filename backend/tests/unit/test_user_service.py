"""Unit tests for UserService — written BEFORE implementation (TDD)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Minimal User stub — avoids importing SQLAlchemy models before the ORM is
# wired up.  Tests only check the SERVICE behaviour, not the ORM model.
# ---------------------------------------------------------------------------


class _UserStub:
    """Minimal stand-in for the real User ORM model."""

    def __init__(self, **kwargs: Any) -> None:
        for k, v in kwargs.items():
            setattr(self, k, v)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_session() -> AsyncMock:
    """Return a fully-mocked AsyncSession."""
    session = AsyncMock()
    # scalars().first() chain used by get_by_telegram_id / update_status
    session.scalars = MagicMock(return_value=AsyncMock())
    return session


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_service(session: AsyncMock):
    """Import and instantiate UserService with the given session."""
    from app.services.user_service import UserService

    return UserService(session)


def _scalars_returning(session: AsyncMock, value: Any) -> None:
    """Configure session.scalars().first() to return *value*."""
    scalars_result = AsyncMock()
    scalars_result.first = MagicMock(return_value=value)
    session.scalars = AsyncMock(return_value=scalars_result)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_pending_new_user(mock_session: AsyncMock) -> None:
    """create_pending must add a User with status='pending' to the session."""
    svc = _make_service(mock_session)

    user = await svc.create_pending(
        telegram_user_id=123,
        username="alex",
        first_name="Alex",
    )

    mock_session.add.assert_called_once()
    mock_session.commit.assert_awaited_once()
    mock_session.refresh.assert_awaited_once()
    assert user.status == "pending"
    assert user.telegram_user_id == 123


@pytest.mark.asyncio
async def test_get_by_telegram_id_found(mock_session: AsyncMock) -> None:
    """get_by_telegram_id returns the User when the DB row exists."""
    existing = _UserStub(telegram_user_id=42, status="active")
    _scalars_returning(mock_session, existing)

    svc = _make_service(mock_session)
    result = await svc.get_by_telegram_id(42)

    assert result is existing


@pytest.mark.asyncio
async def test_get_by_telegram_id_not_found(mock_session: AsyncMock) -> None:
    """get_by_telegram_id returns None when no matching row exists."""
    _scalars_returning(mock_session, None)

    svc = _make_service(mock_session)
    result = await svc.get_by_telegram_id(999)

    assert result is None


@pytest.mark.asyncio
async def test_update_status_to_active_sets_approved_at(mock_session: AsyncMock) -> None:
    """update_status('active') must set approved_at to a non-None value."""
    user_stub = _UserStub(
        telegram_user_id=7,
        status="pending",
        approved_at=None,
        approved_by=None,
    )
    _scalars_returning(mock_session, user_stub)

    svc = _make_service(mock_session)
    result = await svc.update_status(
        telegram_user_id=7,
        status="active",
        approved_by="admin_bot",
    )

    assert result.status == "active"
    assert result.approved_by == "admin_bot"
    assert result.approved_at is not None
    mock_session.commit.assert_awaited_once()
    mock_session.refresh.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_status_to_denied_no_approved_at(mock_session: AsyncMock) -> None:
    """update_status('denied') must NOT set approved_at."""
    user_stub = _UserStub(
        telegram_user_id=8,
        status="pending",
        approved_at=None,
        approved_by=None,
    )
    _scalars_returning(mock_session, user_stub)

    svc = _make_service(mock_session)
    result = await svc.update_status(telegram_user_id=8, status="denied")

    assert result.status == "denied"
    assert result.approved_at is None
    mock_session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_status_user_not_found(mock_session: AsyncMock) -> None:
    """update_status raises ValueError when the user does not exist."""
    _scalars_returning(mock_session, None)

    svc = _make_service(mock_session)
    with pytest.raises(ValueError, match="not found"):
        await svc.update_status(telegram_user_id=9999, status="active")
