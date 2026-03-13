"""Admin Telegram bot handlers.

Task 1.3 — Inline button callbacks:
  approve:<tg_id>  → set status=active, notify mechanic
  deny:<tg_id>     → set status=denied, notify mechanic
  ban:<tg_id>      → set status=banned, notify mechanic (from /users command)

Task 1.4 — Admin bot commands:
  /users   — paginated user list grouped by status with action buttons
  /stats   — DB summary: user counts, queries today, avg retrieval score (7 days)
  /notify  — broadcast text to all active users
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from loguru import logger
from sqlalchemy import func, select

from app.core.database import AsyncSessionLocal
from app.models.query import Query
from app.services.user_service import UserService

admin_router = Router(name="admin")

# ---------------------------------------------------------------------------
# Helper keyboards
# ---------------------------------------------------------------------------

_STATUS_ACTIONS: dict[str, list[tuple[str, str]]] = {
    "pending":  [("✅ Одобрить", "approve"), ("❌ Отказать", "deny")],
    "active":   [("🚫 Заблокировать", "ban")],
    "denied":   [("✅ Одобрить", "approve")],
    "banned":   [("✅ Одобрить", "approve")],
}


def _user_action_keyboard(telegram_user_id: int, status: str) -> InlineKeyboardMarkup:
    """Return an inline keyboard with status-appropriate action buttons."""
    builder = InlineKeyboardBuilder()
    for label, action in _STATUS_ACTIONS.get(status, []):
        builder.button(text=label, callback_data=f"{action}:{telegram_user_id}")
    builder.adjust(2)
    return builder.as_markup()


# ---------------------------------------------------------------------------
# Task 1.3 — Approve callback
# ---------------------------------------------------------------------------


@admin_router.callback_query(F.data.startswith("approve:"))
async def cb_approve(call: CallbackQuery) -> None:
    """Set user status to active and notify the mechanic."""
    raw = call.data.split(":", 1)[1] if call.data and ":" in call.data else ""
    if not raw.isdigit():
        await call.answer("Ошибка: неверный идентификатор пользователя.")
        return

    tg_id = int(raw)
    async with AsyncSessionLocal() as session:
        svc = UserService(session)
        try:
            user = await svc.update_status(tg_id, "active", approved_by="admin_bot")
        except ValueError:
            await call.answer("Пользователь не найден.")
            logger.warning("cb_approve | user not found | tg_id={}", tg_id)
            return

    logger.info("cb_approve | tg_id={} → active", tg_id)
    await call.answer("✅ Одобрено")

    display = user.first_name or str(tg_id)
    assert call.bot is not None
    await call.bot.send_message(
        tg_id,
        f"✅ Ваш доступ одобрен, {display}! Нажмите /start для входа в систему.",
    )


# ---------------------------------------------------------------------------
# Task 1.3 — Deny callback
# ---------------------------------------------------------------------------


@admin_router.callback_query(F.data.startswith("deny:"))
async def cb_deny(call: CallbackQuery) -> None:
    """Set user status to denied and notify the mechanic."""
    raw = call.data.split(":", 1)[1] if call.data and ":" in call.data else ""
    if not raw.isdigit():
        await call.answer("Ошибка: неверный идентификатор пользователя.")
        return

    tg_id = int(raw)
    async with AsyncSessionLocal() as session:
        svc = UserService(session)
        try:
            user = await svc.update_status(tg_id, "denied")
        except ValueError:
            await call.answer("Пользователь не найден.")
            logger.warning("cb_deny | user not found | tg_id={}", tg_id)
            return

    logger.info("cb_deny | tg_id={} → denied", tg_id)
    await call.answer("❌ Отказано")

    display = user.first_name or str(tg_id)
    assert call.bot is not None
    await call.bot.send_message(
        tg_id,
        f"❌ {display}, в доступе отказано. Обратитесь к администратору.",
    )


# ---------------------------------------------------------------------------
# Task 1.3 — Ban callback
# ---------------------------------------------------------------------------


@admin_router.callback_query(F.data.startswith("ban:"))
async def cb_ban(call: CallbackQuery) -> None:
    """Set user status to banned and notify the mechanic."""
    raw = call.data.split(":", 1)[1] if call.data and ":" in call.data else ""
    if not raw.isdigit():
        await call.answer("Ошибка: неверный идентификатор пользователя.")
        return

    tg_id = int(raw)
    async with AsyncSessionLocal() as session:
        svc = UserService(session)
        try:
            user = await svc.update_status(tg_id, "banned")
        except ValueError:
            await call.answer("Пользователь не найден.")
            logger.warning("cb_ban | user not found | tg_id={}", tg_id)
            return

    logger.info("cb_ban | tg_id={} → banned", tg_id)
    await call.answer("🚫 Заблокировано")

    display = user.first_name or str(tg_id)
    assert call.bot is not None
    await call.bot.send_message(
        tg_id,
        f"🚫 {display}, ваш доступ заблокирован администратором.",
    )


# ---------------------------------------------------------------------------
# Task 1.4 — /users command
# ---------------------------------------------------------------------------

_PAGE_SIZE = 10


@admin_router.message(Command("users"))
async def cmd_users(message: Message) -> None:
    """/users — send user list grouped by status with action buttons."""
    async with AsyncSessionLocal() as session:
        svc = UserService(session)
        all_users = await svc.list_by_status()

    if not all_users:
        await message.answer("Пользователи не найдены.")
        return

    # Group by status for readability
    groups: dict[str, list] = {"pending": [], "active": [], "denied": [], "banned": []}
    for u in all_users:
        groups.setdefault(u.status, []).append(u)

    status_labels = {
        "pending": "⏳ На рассмотрении",
        "active": "✅ Активные",
        "denied": "❌ Отказано",
        "banned": "🚫 Заблокированные",
    }

    for status, users in groups.items():
        if not users:
            continue
        header = status_labels.get(status, status.upper())
        for user in users[:_PAGE_SIZE]:
            uname = f"@{user.username}" if user.username else "—"
            name = user.first_name or "—"
            text = f"{header}\n👤 {name} ({uname})\nID: {user.telegram_user_id}"
            kb = _user_action_keyboard(user.telegram_user_id, status)
            await message.answer(text, reply_markup=kb)

    total = len(all_users)
    if total > _PAGE_SIZE * len([s for s, u in groups.items() if u]):
        await message.answer(f"Показаны первые {_PAGE_SIZE} по каждому статусу. Всего: {total}.")


# ---------------------------------------------------------------------------
# Task 1.4 — /stats command
# ---------------------------------------------------------------------------


@admin_router.message(Command("stats"))
async def cmd_stats(message: Message) -> None:
    """/stats — user counts, queries today, avg retrieval score (last 7 days)."""
    async with AsyncSessionLocal() as session:
        svc = UserService(session)
        user_stats = await svc.get_stats()

        # Queries today (UTC)
        today_start = datetime.now(tz=timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        queries_today_result = await session.scalar(
            select(func.count(Query.id)).where(Query.created_at >= today_start)
        )
        queries_today: int = queries_today_result or 0

        # Avg retrieval score over last 7 days
        week_ago = datetime.now(tz=timezone.utc) - timedelta(days=7)
        avg_score_result = await session.scalar(
            select(func.avg(Query.retrieval_score)).where(
                Query.created_at >= week_ago,
                Query.retrieval_score.is_not(None),
            )
        )
        avg_score: float | None = float(avg_score_result) if avg_score_result is not None else None

    avg_str = f"{avg_score:.3f}" if avg_score is not None else "нет данных"

    text = (
        "📊 <b>Статистика системы</b>\n\n"
        f"👥 Пользователи:\n"
        f"  • Всего: {user_stats['total']}\n"
        f"  • Активных: {user_stats['active']}\n"
        f"  • На рассмотрении: {user_stats['pending']}\n"
        f"  • Отказано: {user_stats['denied']}\n"
        f"  • Заблокировано: {user_stats['banned']}\n\n"
        f"💬 Запросов сегодня: {queries_today}\n"
        f"📈 Средний retrieval score (7 дней): {avg_str}"
    )
    await message.answer(text, parse_mode="HTML")
    logger.info("cmd_stats | user_stats={} queries_today={}", user_stats, queries_today)


# ---------------------------------------------------------------------------
# Task 1.4 — /notify command
# ---------------------------------------------------------------------------


@admin_router.message(Command("notify"))
async def cmd_notify(message: Message) -> None:
    """/notify <text> — broadcast to all active users; confirm count to admin."""
    if not message.text:
        await message.answer("Использование: /notify &lt;текст сообщения&gt;")
        return

    # Strip the command prefix ("/notify " or "/notify")
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip():
        await message.answer("Использование: /notify &lt;текст сообщения&gt;")
        return

    broadcast_text = parts[1].strip()

    async with AsyncSessionLocal() as session:
        svc = UserService(session)
        active_users = await svc.list_by_status(status="active")

    assert message.bot is not None
    sent = 0
    failed = 0
    for user in active_users:
        try:
            await message.bot.send_message(user.telegram_user_id, broadcast_text)
            sent += 1
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "cmd_notify | failed to send to tg_id={} | {}",
                user.telegram_user_id,
                exc,
            )
            failed += 1

    result_text = f"✅ Рассылка завершена.\nОтправлено: {sent}"
    if failed:
        result_text += f"\nОшибок: {failed}"
    await message.answer(result_text)
    logger.info("cmd_notify | sent={} failed={}", sent, failed)
