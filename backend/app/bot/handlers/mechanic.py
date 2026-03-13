"""Mechanic-facing Telegram bot handlers.

Registration state machine:
  new user   → create pending record → notify admin with approve/deny keyboard
  pending    → "Ваша заявка уже на рассмотрении."
  active     → "Вы уже одобрены."
  denied     → "В доступе отказано."
  banned     → "В доступе отказано."
"""
from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import (
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


def approve_deny_keyboard(telegram_user_id: int) -> InlineKeyboardMarkup:
    """Build a two-button inline keyboard for the admin approval message."""
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Одобрить", callback_data=f"approve:{telegram_user_id}")
    builder.button(text="❌ Отказать", callback_data=f"deny:{telegram_user_id}")
    builder.adjust(2)
    return builder.as_markup()


@mechanic_router.message(Command("start"))
async def cmd_start(message: Message) -> None:
    if message.from_user is None:
        return

    tg_user = message.from_user
    telegram_user_id: int = tg_user.id
    username: str | None = tg_user.username
    first_name: str | None = tg_user.first_name

    logger.info("cmd_start | user_id={} username={}", telegram_user_id, username)

    if telegram_user_id == settings.ADMIN_TELEGRAM_ID:
        await message.answer(
            "Режим администратора. Доступные команды:\n"
            "/users — список пользователей\n"
            "/stats — статистика\n"
            "/notify &lt;текст&gt; — рассылка"
        )
        return

    async with AsyncSessionLocal() as session:
        svc = UserService(session)
        user = await svc.get_by_telegram_id(telegram_user_id)

        if user is None:
            await svc.create_pending(telegram_user_id, username, first_name)
            await message.answer(
                "Ваша заявка на доступ отправлена. Ожидайте решения администратора."
            )
            display_name = first_name or "—"
            uname_str = f"@{username}" if username else "без username"
            assert message.bot is not None
            await message.bot.send_message(
                settings.ADMIN_TELEGRAM_ID,
                (
                    f"Новый запрос доступа:\n"
                    f"👤 {display_name} ({uname_str})\n"
                    f"ID: {telegram_user_id}"
                ),
                reply_markup=approve_deny_keyboard(telegram_user_id),
            )
            logger.info(
                "new pending user | user_id={} first_name={}", telegram_user_id, first_name
            )
            return

        if user.status == "pending":
            await message.answer("Ваша заявка уже на рассмотрении. Ожидайте ответа.")
        elif user.status == "active":
            kb = ReplyKeyboardMarkup(
                keyboard=[[
                    KeyboardButton(
                        text="🔧 Открыть Matsu Shi",
                        web_app=WebAppInfo(url=settings.APP_BASE_URL),
                    )
                ]],
                resize_keyboard=True,
            )
            await message.answer(
                "Добро пожаловать! Нажмите кнопку ниже для работы.",
                reply_markup=kb,
            )
        else:
            # denied or banned
            await message.answer("В доступе отказано. Обратитесь к администратору.")
