"""TitleGeneratorAgent — auto-generates a short Russian session title.

Called after the first query in a session is answered and persisted.
Uses the lite LLM model (same as classifier) so it's cheap and fast.

Public API:
    generate_title(query_text, response_text) -> str
        Returns a 3-6 word Russian title describing the diagnostic topic.
"""
from __future__ import annotations

import asyncio

from loguru import logger
from pydantic import BaseModel
from pydantic_ai import Agent

from app.core.config import settings


class TitleOutput(BaseModel):
    title: str


_SYSTEM_PROMPT = """\
Ты — генератор заголовков диагностических сессий механиков Komatsu.

Получив вопрос механика и начало ответа, придумай краткое название сессии (3-6 слов на русском).
Название должно описывать суть технической проблемы или темы.
Не включай в название номер модели техники — он указан отдельно.
Примеры хороших названий:
- "Замена масляного фильтра двигателя"
- "Диагностика гидравлики стрелы"
- "Ошибка E204 электрической схемы"
- "Периодичность ТО трансмиссии"
- "Неисправность системы охлаждения"

Верни ТОЛЬКО JSON с полем title."""

TitleAgent: Agent[None, TitleOutput] = Agent(
    model=f"google-gla:{settings.LLM_LITE_MODEL}",
    output_type=TitleOutput,
    system_prompt=_SYSTEM_PROMPT,
)


async def generate_title(query_text: str, response_text: str) -> str:
    """Generate a short Russian session title from the first Q&A pair.

    Retries up to 3 times on transient errors (503).
    Falls back to a truncated version of the query on failure.
    """
    prompt = f"Вопрос: {query_text}\nОтвет (начало): {response_text[:300]}"
    for attempt in range(3):
        try:
            result = await TitleAgent.run(prompt)
            return result.output.title.strip()
        except Exception as exc:
            if attempt < 2 and "503" in str(exc):
                logger.warning("TitleAgent 503, attempt {}/3, retrying...", attempt + 1)
                await asyncio.sleep(2)
            else:
                logger.warning("TitleAgent failed (attempt {}): {}", attempt + 1, exc)
                break
    # Fallback: first 7 words of the query
    words = query_text.split()
    return " ".join(words[:7]) + ("..." if len(words) > 7 else "")
