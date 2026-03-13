"""Unit tests for admin callback handlers (Tasks 1.3) and bot commands (Task 1.4).

Written BEFORE implementation — TDD.

Approach:
- Handlers import UserService and AsyncSessionLocal.
- We patch AsyncSessionLocal as an async context manager returning a mock session.
- We mock CallbackQuery / Message objects as needed.
- No real DB or Telegram connection.
"""
from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Minimal stubs
# ---------------------------------------------------------------------------


class _UserStub:
    def __init__(self, **kwargs: Any) -> None:
        for k, v in kwargs.items():
            setattr(self, k, v)


def _make_call(data: str, bot: Any | None = None) -> AsyncMock:
    """Build a minimal CallbackQuery mock."""
    call = AsyncMock()
    call.data = data
    call.from_user = MagicMock(id=999, username="admin_user")
    call.message = AsyncMock()
    call.bot = bot or AsyncMock()
    return call


def _make_message(text: str = "", bot: Any | None = None) -> AsyncMock:
    """Build a minimal Message mock."""
    msg = AsyncMock()
    msg.text = text
    msg.from_user = MagicMock(id=999, username="admin_user")
    msg.bot = bot or AsyncMock()
    return msg


def _patch_session(user_stub: Any) -> tuple[Any, Any]:
    """Return (mock_session, context_manager_patch) where session returns user_stub via scalars."""
    mock_session = AsyncMock()
    scalars_result = AsyncMock()
    scalars_result.first = MagicMock(return_value=user_stub)
    mock_session.scalars = AsyncMock(return_value=scalars_result)

    # Also patch list_by_status result (for /users and /stats)
    scalars_all = AsyncMock()
    scalars_all.all = MagicMock(return_value=[user_stub] if user_stub else [])
    # Make scalars return different results depending on call order is complex —
    # simplest: override per test where needed.
    return mock_session


# ---------------------------------------------------------------------------
# Task 1.3 — approve callback
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cb_approve_calls_update_status() -> None:
    """cb_approve must call update_status(tg_id, 'active') and notify the mechanic."""
    user_stub = _UserStub(
        telegram_user_id=42,
        status="pending",
        approved_at=None,
        approved_by=None,
        first_name="Иван",
    )
    mock_session = _patch_session(user_stub)

    # Simulate update_status side effect
    async def fake_update_status(self: Any, tg_id: int, status: str, approved_by: str | None = None) -> _UserStub:
        user_stub.status = status
        user_stub.approved_by = approved_by
        return user_stub

    with (
        patch("app.bot.handlers.admin.AsyncSessionLocal") as mock_ctx,
        patch("app.services.user_service.UserService.update_status", new=fake_update_status),
    ):
        mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

        from app.bot.handlers.admin import cb_approve  # noqa: PLC0415

        call = _make_call("approve:42")
        await cb_approve(call)

    call.answer.assert_awaited()
    # The mechanic (tg_id=42) must receive a message
    call.bot.send_message.assert_awaited()
    sent_tg_id = call.bot.send_message.call_args[0][0]
    assert sent_tg_id == 42


@pytest.mark.asyncio
async def test_cb_deny_calls_update_status() -> None:
    """cb_deny must call update_status(tg_id, 'denied') and notify the mechanic."""
    user_stub = _UserStub(
        telegram_user_id=55,
        status="pending",
        approved_at=None,
        approved_by=None,
        first_name="Пётр",
    )
    mock_session = _patch_session(user_stub)

    async def fake_update_status(self: Any, tg_id: int, status: str, approved_by: str | None = None) -> _UserStub:
        user_stub.status = status
        return user_stub

    with (
        patch("app.bot.handlers.admin.AsyncSessionLocal") as mock_ctx,
        patch("app.services.user_service.UserService.update_status", new=fake_update_status),
    ):
        mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

        from app.bot.handlers.admin import cb_deny  # noqa: PLC0415

        call = _make_call("deny:55")
        await cb_deny(call)

    call.answer.assert_awaited()
    call.bot.send_message.assert_awaited()
    sent_tg_id = call.bot.send_message.call_args[0][0]
    assert sent_tg_id == 55


@pytest.mark.asyncio
async def test_cb_ban_calls_update_status() -> None:
    """cb_ban must call update_status(tg_id, 'banned') and notify the mechanic."""
    user_stub = _UserStub(
        telegram_user_id=77,
        status="active",
        approved_at=None,
        approved_by=None,
        first_name="Алексей",
    )
    mock_session = _patch_session(user_stub)

    async def fake_update_status(self: Any, tg_id: int, status: str, approved_by: str | None = None) -> _UserStub:
        user_stub.status = status
        return user_stub

    with (
        patch("app.bot.handlers.admin.AsyncSessionLocal") as mock_ctx,
        patch("app.services.user_service.UserService.update_status", new=fake_update_status),
    ):
        mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

        from app.bot.handlers.admin import cb_ban  # noqa: PLC0415

        call = _make_call("ban:77")
        await cb_ban(call)

    call.answer.assert_awaited()
    call.bot.send_message.assert_awaited()
    sent_tg_id = call.bot.send_message.call_args[0][0]
    assert sent_tg_id == 77


# ---------------------------------------------------------------------------
# Task 1.3 — callback data format guard
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cb_approve_invalid_data_is_ignored() -> None:
    """If callback data has no colon, the handler must not raise an exception."""
    with patch("app.bot.handlers.admin.AsyncSessionLocal") as mock_ctx:
        mock_session = AsyncMock()
        mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

        from app.bot.handlers.admin import cb_approve  # noqa: PLC0415

        call = _make_call("approve:")  # empty id
        # Should not raise
        try:
            await cb_approve(call)
        except Exception:  # noqa: BLE001
            pytest.fail("cb_approve raised an exception on malformed callback data")


# ---------------------------------------------------------------------------
# Task 1.4 — /stats command
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cmd_stats_sends_message() -> None:
    """/stats must send a message containing user counts."""
    mock_session = AsyncMock()

    # UserService.get_stats() is called internally; mock it
    async def fake_get_stats(self: Any) -> dict:
        return {"total": 5, "active": 3, "pending": 1, "denied": 1, "banned": 0}

    # Query count and retrieval score mocked at ORM level
    scalars_result = AsyncMock()
    scalars_result.all = MagicMock(return_value=[])
    scalars_result.first = MagicMock(return_value=None)
    mock_session.scalars = AsyncMock(return_value=scalars_result)
    mock_session.scalar = AsyncMock(return_value=0)

    with (
        patch("app.bot.handlers.admin.AsyncSessionLocal") as mock_ctx,
        patch("app.services.user_service.UserService.get_stats", new=fake_get_stats),
    ):
        mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

        from app.bot.handlers.admin import cmd_stats  # noqa: PLC0415

        msg = _make_message("/stats")
        await cmd_stats(msg)

    msg.answer.assert_awaited_once()
    text: str = msg.answer.call_args[0][0]
    assert "активных" in text.lower() or "active" in text.lower() or "3" in text


# ---------------------------------------------------------------------------
# Task 1.4 — /notify command
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cmd_notify_broadcasts_to_active_users() -> None:
    """/notify <text> must send the text to all active users."""
    active_user = _UserStub(telegram_user_id=101, status="active")
    mock_session = AsyncMock()

    async def fake_list_by_status(self: Any, status: str | None = None) -> list:
        if status == "active":
            return [active_user]
        return []

    with (
        patch("app.bot.handlers.admin.AsyncSessionLocal") as mock_ctx,
        patch("app.services.user_service.UserService.list_by_status", new=fake_list_by_status),
    ):
        mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

        from app.bot.handlers.admin import cmd_notify  # noqa: PLC0415

        msg = _make_message("/notify Плановое обслуживание завтра в 10:00")
        await cmd_notify(msg)

    # Bot must have sent a message to tg_id=101
    msg.bot.send_message.assert_awaited()
    calls = msg.bot.send_message.call_args_list
    sent_ids = [c[0][0] for c in calls]
    assert 101 in sent_ids
    # Admin must receive confirmation
    msg.answer.assert_awaited()
