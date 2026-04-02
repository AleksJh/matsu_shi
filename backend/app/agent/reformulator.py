"""ReformulatorAgent — expands follow-up queries using session history.

Public API:
    reformulate(history, query_text) -> list[str]

Returns 1–3 specific RAG search queries derived from the session history
and the current question. Falls back to [query_text] on any error.
"""
from __future__ import annotations

import asyncio

from loguru import logger
from pydantic import BaseModel, Field
from pydantic_ai import Agent
from typing import Annotated

from app.core.config import settings


class ReformulationResult(BaseModel):
    queries: Annotated[list[str], Field(min_length=1, max_length=5)]


_SYSTEM_PROMPT = """Ты — технический ассистент по диагностике строительной техники.
Тебе дана история диагностической сессии и новый вопрос пользователя.
Твоя задача: сформулировать от 1 до 3 конкретных технических запросов для поиска
в векторной базе знаний по мануалам технике.

Правила:
- Каждый запрос должен быть самодостаточным (не требовать контекста для понимания)
- Используй конкретные технические термины из истории и текущего вопроса
- Если вопрос однозначен — 1 запрос. Если вопрос требует нескольких аспектов — до 3.
- Запросы на русском языке.
- ТОЛЬКО queries в ответе, без пояснений."""


ReformulatorAgent: Agent[None, ReformulationResult] = Agent(
    model=f"google-gla:{settings.LLM_LITE_MODEL}",
    output_type=ReformulationResult,
    system_prompt=_SYSTEM_PROMPT,
)


async def reformulate(
    history: list[str],
    query_text: str,
) -> list[str]:
    """Return 1–N specific RAG queries expanded from history + current question.

    Args:
        history: List of prior Q&A strings, each formatted as
                 "Вопрос: {text}\nОтвет: {text}". May be empty.
        query_text: The raw user question (unchanged).

    Returns:
        List of 1–3 specific search queries. Falls back to [query_text] on error.

    Notes:
        - If history is empty, returns [query_text] immediately (no LLM call).
        - Only the last 3 history entries are sent to keep the prompt concise.
        - Retries on 503/504/DEADLINE_EXCEEDED (same pattern as classifier.py).
    """
    if not history:
        return [query_text]

    prior_block = "\n\n".join(history[-3:])
    prompt = f"История:\n{prior_block}\n\nНовый вопрос: {query_text}"

    for _attempt in range(20):
        try:
            result = await ReformulatorAgent.run(prompt)
            return result.output.queries
        except Exception as _exc:
            if _attempt < 19 and (
                "503" in str(_exc)
                or "504" in str(_exc)
                or "DEADLINE_EXCEEDED" in str(_exc)
            ):
                logger.warning(
                    "ReformulatorAgent transient error (attempt {}/20), waiting 2s: {}",
                    _attempt + 1,
                    _exc,
                )
                await asyncio.sleep(2)
            else:
                logger.warning(
                    "reformulate failed on attempt {}, falling back to original query: {}",
                    _attempt + 1,
                    _exc,
                )
                return [query_text]

    return [query_text]
