"""Mechanic-facing Telegram bot handlers.

Registration state machine (new users):
  /start (new)    → ask ФИО          [RegistrationState.full_name]
                  → ask country      [RegistrationState.country]
                  → ask city         [RegistrationState.city]
                  → ask email        [RegistrationState.email]
                  → ask phone        [RegistrationState.phone]
                  → create pending   → notify admin

Existing user flows:
  /start (pending)  → "Ваша заявка уже на рассмотрении."
  /start (active)   → Mini App keyboard button
  /start (denied/banned) → rejection message
"""
from __future__ import annotations

import re

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
    WebAppInfo,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder
from loguru import logger

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.services.user_service import UserService

mechanic_router = Router(name="mechanic")

# ---------------------------------------------------------------------------
# Country list
# ---------------------------------------------------------------------------

COUNTRIES: list[str] = [
    "Россия", "Армения", "Азербайджан", "Грузия", "Казахстан",
    "Узбекистан", "Кыргызстан", "Таджикистан", "Туркменистан",
    "Беларусь", "Украина", "Молдова", "Монголия",
    "Германия", "Франция", "Великобритания", "Италия", "Испания",
    "Польша", "Нидерланды", "Австрия", "Швейцария", "Бельгия",
    "США", "Канада", "Бразилия", "Австралия",
    "Китай", "Япония", "Южная Корея", "Индия", "Турция",
    "ОАЭ", "Саудовская Аравия", "Иран", "Израиль",
    "Другая",
]


# ---------------------------------------------------------------------------
# FSM States
# ---------------------------------------------------------------------------


class RegistrationState(StatesGroup):
    full_name = State()
    country = State()
    city = State()
    email = State()
    phone = State()


# ---------------------------------------------------------------------------
# Helper keyboards
# ---------------------------------------------------------------------------


def _webapp_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[
            KeyboardButton(
                text="🔧 Открыть Matsu Shi",
                web_app=WebAppInfo(url=settings.APP_BASE_URL),
            )
        ]],
        resize_keyboard=True,
    )


def _country_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for country in COUNTRIES:
        builder.button(text=country, callback_data=f"country:{country}")
    builder.adjust(3)
    return builder.as_markup()


def _approve_deny_keyboard(telegram_user_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Одобрить", callback_data=f"approve:{telegram_user_id}")
    builder.button(text="❌ Отказать", callback_data=f"deny:{telegram_user_id}")
    builder.adjust(2)
    return builder.as_markup()


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


def _count_digits(text: str) -> int:
    return sum(1 for c in text if c.isdigit())


def _is_valid_email(text: str) -> bool:
    return "@" in text and "." in text.split("@")[-1]


# ---------------------------------------------------------------------------
# /start command
# ---------------------------------------------------------------------------


@mechanic_router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext) -> None:
    if message.from_user is None:
        return

    tg_user = message.from_user
    telegram_user_id: int = tg_user.id
    username: str | None = tg_user.username
    first_name: str | None = tg_user.first_name

    logger.info("cmd_start | user_id={} username={}", telegram_user_id, username)

    if telegram_user_id == settings.ADMIN_TELEGRAM_ID:
        builder = InlineKeyboardBuilder()
        builder.button(text="🖥 Открыть Admin Dashboard", url=f"{settings.APP_BASE_URL}/admin/")
        await message.answer(
            "Режим администратора. Доступные команды:\n"
            "/users — список пользователей\n"
            "/stats — статистика\n"
            "/notify &lt;текст&gt; — рассылка",
            reply_markup=builder.as_markup(),
        )
        return

    async with AsyncSessionLocal() as session:
        svc = UserService(session)
        user = await svc.get_by_telegram_id(telegram_user_id)

    if user is None:
        # New user — start registration flow
        await state.set_state(RegistrationState.full_name)
        await message.answer(
            "Добро пожаловать! Для получения доступа заполните небольшую анкету.\n\n"
            "Введите ваше ФИО (Фамилия Имя Отчество):"
        )
        logger.info("new user started registration | user_id={}", telegram_user_id)
        return

    if user.status == "pending":
        await message.answer("Ваша заявка уже на рассмотрении. Ожидайте ответа.")
    elif user.status == "active":
        await message.answer(
            "Добро пожаловать! Нажмите кнопку ниже для работы.",
            reply_markup=_webapp_keyboard(),
        )
    else:
        # denied or banned
        await message.answer("В доступе отказано. Обратитесь к администратору.")


# ---------------------------------------------------------------------------
# Step 1: Full name
# ---------------------------------------------------------------------------


@mechanic_router.message(RegistrationState.full_name)
async def handle_full_name(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if len(text) < 2:
        await message.answer("Пожалуйста, введите корректное ФИО (не менее 2 символов):")
        return

    await state.update_data(full_name=text)
    await state.set_state(RegistrationState.country)
    await message.answer(
        "Выберите вашу страну:",
        reply_markup=_country_keyboard(),
    )


# ---------------------------------------------------------------------------
# Step 2: Country (inline callback)
# ---------------------------------------------------------------------------


@mechanic_router.callback_query(F.data.startswith("country:"), RegistrationState.country)
async def handle_country_callback(call: CallbackQuery, state: FSMContext) -> None:
    raw = call.data.split(":", 1)[1] if call.data and ":" in call.data else ""
    if not raw:
        await call.answer("Ошибка выбора. Попробуйте снова.")
        return

    await state.update_data(country=raw)
    await state.set_state(RegistrationState.city)
    await call.answer()
    await call.message.edit_text(f"Страна: {raw} ✅\n\nВведите ваш город:")


# ---------------------------------------------------------------------------
# Step 3: City
# ---------------------------------------------------------------------------


@mechanic_router.message(RegistrationState.city)
async def handle_city(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if len(text) < 1:
        await message.answer("Пожалуйста, введите название города:")
        return

    await state.update_data(city=text)
    await state.set_state(RegistrationState.email)
    await message.answer("Введите ваш e-mail:")


# ---------------------------------------------------------------------------
# Step 4: Email
# ---------------------------------------------------------------------------


@mechanic_router.message(RegistrationState.email)
async def handle_email(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if not _is_valid_email(text):
        await message.answer(
            "Некорректный e-mail. Пожалуйста, введите адрес в формате name@example.com:"
        )
        return

    await state.update_data(email=text)
    await state.set_state(RegistrationState.phone)
    await message.answer("Введите ваш номер телефона:")


# ---------------------------------------------------------------------------
# Step 5: Phone — final step, creates pending record and notifies admin
# ---------------------------------------------------------------------------


@mechanic_router.message(RegistrationState.phone)
async def handle_phone(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if _count_digits(text) < 7:
        await message.answer(
            "Некорректный номер телефона. Введите номер с указанием кода страны "
            "(например: +7 495 123-45-67):"
        )
        return

    data = await state.get_data()
    tg_user = message.from_user
    assert tg_user is not None

    async with AsyncSessionLocal() as session:
        svc = UserService(session)
        user = await svc.create_pending(
            telegram_user_id=tg_user.id,
            username=tg_user.username,
            first_name=tg_user.first_name,
            full_name=data.get("full_name"),
            country=data.get("country"),
            city=data.get("city"),
            email=data.get("email"),
            phone=text,
        )

    await state.clear()

    await message.answer(
        "✅ Анкета заполнена! Ваша заявка отправлена на рассмотрение администратора.\n"
        "Вы получите уведомление о решении."
    )

    # Notify admin with full registration details
    full_name = user.full_name or tg_user.first_name or "—"
    uname_str = f"@{tg_user.username}" if tg_user.username else "без username"
    assert message.bot is not None
    await message.bot.send_message(
        settings.ADMIN_TELEGRAM_ID,
        (
            f"📋 Новый запрос доступа:\n\n"
            f"👤 {full_name} ({uname_str})\n"
            f"🌍 Страна: {user.country or '—'}\n"
            f"🏙 Город: {user.city or '—'}\n"
            f"📧 E-mail: {user.email or '—'}\n"
            f"📞 Телефон: {user.phone or '—'}\n"
            f"🆔 Telegram ID: {tg_user.id}"
        ),
        reply_markup=_approve_deny_keyboard(tg_user.id),
    )

    logger.info(
        "new pending user | user_id={} full_name={} country={}",
        tg_user.id,
        user.full_name,
        user.country,
    )


# ---------------------------------------------------------------------------
# Fallback for plain text messages outside registration flow
# ---------------------------------------------------------------------------


@mechanic_router.message(F.text)
async def handle_text_message(message: Message) -> None:
    """Handle plain text messages sent directly to the bot.

    Active users are reminded to use the WebApp. Other statuses get
    the same responses as /start so the UX is consistent.
    """
    if message.from_user is None:
        return

    telegram_user_id: int = message.from_user.id

    async with AsyncSessionLocal() as session:
        svc = UserService(session)
        user = await svc.get_by_telegram_id(telegram_user_id)

    if user is None:
        await message.answer("Отправьте /start для регистрации.")
        return

    if user.status == "active":
        await message.answer(
            "Для отправки вопросов используйте встроенное приложение 👇",
            reply_markup=_webapp_keyboard(),
        )
    elif user.status == "pending":
        await message.answer("Ваша заявка ещё на рассмотрении. Ожидайте ответа.")
    else:
        await message.answer("В доступе отказано. Обратитесь к администратору.")
