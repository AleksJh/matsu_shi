"""TDD tests for the mechanic registration FSM flow.

Tests cover the full 5-step registration conversation:
  /start → full_name → country (inline kb) → city → email → phone → pending

Written BEFORE implementation — all tests must fail initially.
"""
from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers — build minimal aiogram Message / CallbackQuery mocks
# ---------------------------------------------------------------------------


def _make_user(user_id: int = 1234, username: str | None = "test_user", first_name: str = "Test") -> MagicMock:
    u = MagicMock()
    u.id = user_id
    u.username = username
    u.first_name = first_name
    return u


def _make_message(text: str = "/start", user_id: int = 1234, username: str | None = None, first_name: str = "Test") -> MagicMock:
    msg = AsyncMock()
    msg.text = text
    msg.from_user = _make_user(user_id=user_id, username=username, first_name=first_name)
    msg.answer = AsyncMock()
    msg.bot = AsyncMock()
    return msg


def _make_callback(data: str, user_id: int = 1234) -> MagicMock:
    cb = AsyncMock()
    cb.data = data
    cb.from_user = _make_user(user_id=user_id)
    cb.message = AsyncMock()
    cb.message.edit_text = AsyncMock()
    cb.answer = AsyncMock()
    cb.bot = AsyncMock()
    return cb


def _make_state(current_state: str | None = None) -> AsyncMock:
    state = AsyncMock()
    state.get_state = AsyncMock(return_value=current_state)
    state.set_state = AsyncMock()
    state.get_data = AsyncMock(return_value={})
    state.update_data = AsyncMock()
    state.clear = AsyncMock()
    return state


# ---------------------------------------------------------------------------
# Test 1: /start from a completely new user → enters full_name state
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_start_new_user_enters_fullname_state() -> None:
    """New user sends /start → bot asks for ФИО, sets state=full_name. No DB write yet."""
    from app.bot.handlers.mechanic import cmd_start
    from app.bot.handlers.mechanic import RegistrationState

    msg = _make_message("/start", user_id=9999)
    state = _make_state(current_state=None)

    with patch("app.bot.handlers.mechanic.AsyncSessionLocal") as mock_session_cm:
        mock_session = AsyncMock()
        mock_session_cm.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_cm.return_value.__aexit__ = AsyncMock(return_value=False)

        svc_mock = AsyncMock()
        svc_mock.get_by_telegram_id = AsyncMock(return_value=None)

        with patch("app.bot.handlers.mechanic.UserService", return_value=svc_mock):
            await cmd_start(msg, state)

    # Must ask for ФИО
    msg.answer.assert_called_once()
    call_text: str = msg.answer.call_args[0][0]
    assert "ФИО" in call_text or "имя" in call_text.lower()

    # Must transition into full_name state
    state.set_state.assert_called_once_with(RegistrationState.full_name)

    # Must NOT create a pending record
    svc_mock.create_pending.assert_not_called()


# ---------------------------------------------------------------------------
# Test 2: /start from a pending user → "ещё на рассмотрении", no state change
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_start_pending_user_no_state_change() -> None:
    """Pending user sends /start → reminder message, state untouched."""
    from app.bot.handlers.mechanic import cmd_start

    msg = _make_message("/start", user_id=1111)
    state = _make_state(current_state=None)

    pending_user = MagicMock()
    pending_user.status = "pending"

    with patch("app.bot.handlers.mechanic.AsyncSessionLocal") as mock_session_cm:
        mock_session = AsyncMock()
        mock_session_cm.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_cm.return_value.__aexit__ = AsyncMock(return_value=False)

        svc_mock = AsyncMock()
        svc_mock.get_by_telegram_id = AsyncMock(return_value=pending_user)

        with patch("app.bot.handlers.mechanic.UserService", return_value=svc_mock):
            await cmd_start(msg, state)

    msg.answer.assert_called_once()
    call_text: str = msg.answer.call_args[0][0]
    assert "рассмотрении" in call_text.lower() or "ожидайте" in call_text.lower()

    state.set_state.assert_not_called()


# ---------------------------------------------------------------------------
# Test 3: /start from an active user → sends Mini App keyboard button
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_start_active_user_sends_webapp_button() -> None:
    """Active user sends /start → bot replies with ReplyKeyboardMarkup containing WebAppInfo."""
    from app.bot.handlers.mechanic import cmd_start
    from aiogram.types import ReplyKeyboardMarkup

    msg = _make_message("/start", user_id=2222)
    state = _make_state(current_state=None)

    active_user = MagicMock()
    active_user.status = "active"

    with patch("app.bot.handlers.mechanic.AsyncSessionLocal") as mock_session_cm:
        mock_session = AsyncMock()
        mock_session_cm.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_cm.return_value.__aexit__ = AsyncMock(return_value=False)

        svc_mock = AsyncMock()
        svc_mock.get_by_telegram_id = AsyncMock(return_value=active_user)

        with patch("app.bot.handlers.mechanic.UserService", return_value=svc_mock):
            await cmd_start(msg, state)

    msg.answer.assert_called_once()
    # reply_markup must be a ReplyKeyboardMarkup
    call_kwargs = msg.answer.call_args[1]
    assert "reply_markup" in call_kwargs
    assert isinstance(call_kwargs["reply_markup"], ReplyKeyboardMarkup)


# ---------------------------------------------------------------------------
# Test 4: User in full_name state sends valid name → transitions to country
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_handle_fullname_valid_transitions_to_country() -> None:
    """Handler receives valid ФИО (≥2 chars) → saves to FSM data, sets state=country."""
    from app.bot.handlers.mechanic import handle_full_name, RegistrationState

    msg = _make_message("Иванов Иван Иванович")
    state = _make_state(current_state="RegistrationState:full_name")

    await handle_full_name(msg, state)

    state.update_data.assert_called_once()
    call_kwargs = state.update_data.call_args[1]
    assert call_kwargs.get("full_name") == "Иванов Иван Иванович"

    state.set_state.assert_called_once_with(RegistrationState.country)

    # Must send country selection keyboard
    msg.answer.assert_called_once()


# ---------------------------------------------------------------------------
# Test 5: User sends too-short name (<2 chars) → validation error, no state change
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_handle_fullname_too_short_validation_error() -> None:
    """ФИО shorter than 2 chars → error message, state unchanged."""
    from app.bot.handlers.mechanic import handle_full_name

    msg = _make_message("А")
    state = _make_state()

    await handle_full_name(msg, state)

    msg.answer.assert_called_once()
    state.set_state.assert_not_called()
    state.update_data.assert_not_called()


# ---------------------------------------------------------------------------
# Test 6: User selects country from inline keyboard → transitions to city
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_handle_country_selection_transitions_to_city() -> None:
    """Callback data 'country:Россия' → saves country, sets state=city."""
    from app.bot.handlers.mechanic import handle_country_callback, RegistrationState

    cb = _make_callback("country:Россия")
    state = _make_state()

    await handle_country_callback(cb, state)

    state.update_data.assert_called_once()
    call_kwargs = state.update_data.call_args[1]
    assert call_kwargs.get("country") == "Россия"

    state.set_state.assert_called_once_with(RegistrationState.city)
    cb.message.edit_text.assert_called_once()


# ---------------------------------------------------------------------------
# Test 7: User sends city text → transitions to email
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_handle_city_valid_transitions_to_email() -> None:
    """Valid city text → saved to FSM data, state=email."""
    from app.bot.handlers.mechanic import handle_city, RegistrationState

    msg = _make_message("Ереван")
    state = _make_state()

    await handle_city(msg, state)

    state.update_data.assert_called_once()
    call_kwargs = state.update_data.call_args[1]
    assert call_kwargs.get("city") == "Ереван"

    state.set_state.assert_called_once_with(RegistrationState.email)


# ---------------------------------------------------------------------------
# Test 8: Invalid email (no @) → error, no state change
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_handle_email_invalid_no_at_symbol() -> None:
    """Email without '@' → validation error, state unchanged."""
    from app.bot.handlers.mechanic import handle_email

    msg = _make_message("notanemail.com")
    state = _make_state()

    await handle_email(msg, state)

    msg.answer.assert_called_once()
    state.set_state.assert_not_called()
    state.update_data.assert_not_called()


# ---------------------------------------------------------------------------
# Test 9: Valid email → transitions to phone
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_handle_email_valid_transitions_to_phone() -> None:
    """Valid email → saved to FSM data, state=phone."""
    from app.bot.handlers.mechanic import handle_email, RegistrationState

    msg = _make_message("mechanic@example.com")
    state = _make_state()

    await handle_email(msg, state)

    state.update_data.assert_called_once()
    call_kwargs = state.update_data.call_args[1]
    assert call_kwargs.get("email") == "mechanic@example.com"

    state.set_state.assert_called_once_with(RegistrationState.phone)


# ---------------------------------------------------------------------------
# Test 10: Invalid phone (too few digits) → error, no state change
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_handle_phone_too_few_digits() -> None:
    """Phone with <7 digits → validation error, state unchanged."""
    from app.bot.handlers.mechanic import handle_phone

    msg = _make_message("12345")
    state = _make_state()

    await handle_phone(msg, state)

    msg.answer.assert_called_once()
    state.set_state.assert_not_called()


# ---------------------------------------------------------------------------
# Test 11: Valid phone → create_pending called with all 7 fields, admin notified
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_handle_phone_valid_creates_pending_and_notifies_admin() -> None:
    """Complete registration: valid phone → create_pending(7 args) + admin notification."""
    from app.bot.handlers.mechanic import handle_phone

    msg = _make_message("+7 (495) 123-45-67", user_id=5555, first_name="Иван")
    state = _make_state()
    state.get_data = AsyncMock(return_value={
        "full_name": "Иванов Иван Иванович",
        "country": "Россия",
        "city": "Москва",
        "email": "ivan@example.com",
    })

    created_user = MagicMock()
    created_user.first_name = "Иван"
    created_user.full_name = "Иванов Иван Иванович"
    created_user.country = "Россия"
    created_user.city = "Москва"
    created_user.email = "ivan@example.com"
    created_user.phone = "+7 (495) 123-45-67"

    with patch("app.bot.handlers.mechanic.AsyncSessionLocal") as mock_session_cm:
        mock_session = AsyncMock()
        mock_session_cm.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_cm.return_value.__aexit__ = AsyncMock(return_value=False)

        svc_mock = AsyncMock()
        svc_mock.create_pending = AsyncMock(return_value=created_user)

        with patch("app.bot.handlers.mechanic.UserService", return_value=svc_mock):
            with patch("app.bot.handlers.mechanic.settings") as mock_settings:
                mock_settings.ADMIN_TELEGRAM_ID = 9999999
                mock_settings.APP_BASE_URL = "https://matsushi.xyz"
                await handle_phone(msg, state)

    # create_pending must be called with all 7 required kwargs
    svc_mock.create_pending.assert_called_once()
    call_kwargs = svc_mock.create_pending.call_args[1]
    assert call_kwargs["telegram_user_id"] == 5555
    assert call_kwargs["full_name"] == "Иванов Иван Иванович"
    assert call_kwargs["country"] == "Россия"
    assert call_kwargs["city"] == "Москва"
    assert call_kwargs["email"] == "ivan@example.com"
    assert call_kwargs["phone"] == "+7 (495) 123-45-67"

    # FSM state must be cleared after registration
    state.clear.assert_called_once()

    # Admin must be notified
    msg.bot.send_message.assert_called_once()
    admin_call_args = msg.bot.send_message.call_args
    assert admin_call_args[0][0] == 9999999  # sent to ADMIN_TELEGRAM_ID

    # Bot confirms registration to mechanic
    msg.answer.assert_called_once()
