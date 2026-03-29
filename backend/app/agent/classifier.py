from __future__ import annotations

import asyncio
from typing import Literal

from loguru import logger
from pydantic import BaseModel
from pydantic_ai import Agent

from app.core.config import settings


class ClassifierOutput(BaseModel):
    query_class: Literal["simple", "complex"]


_SYSTEM_PROMPT = """Ты — классификатор запросов технического ассистента Komatsu.

Классифицируй запрос механика как "simple" или "complex":
- simple: поиск одного кода ошибки, прямой вопрос по спецификации,
          вопрос об одной системе, чтение таблицы параметров
- complex: многошаговая диагностика, корреляция нескольких систем,
           анализ нескольких ошибок одновременно, последовательный
           процесс устранения неисправности

Верни ТОЛЬКО JSON с полем query_class."""


ClassifierAgent: Agent[None, ClassifierOutput] = Agent(
    model=f"google-gla:{settings.LLM_LITE_MODEL}",
    output_type=ClassifierOutput,
    system_prompt=_SYSTEM_PROMPT,
)


async def classify_query(query_text: str) -> str:
    """Classify a mechanic's query as 'simple' or 'complex'.

    Retries up to 20 times on Gemini 503 UNAVAILABLE errors (2 s flat wait).
    Raises on all other exceptions or after exhausting retries (PRD §6.2, Roadmap 9.6).

    Returns:
        "simple" or "complex" string.
    """
    for _attempt in range(20):
        try:
            result = await ClassifierAgent.run(query_text)
            return result.output.query_class
        except Exception as _exc:
            if _attempt < 19 and "503" in str(_exc):
                logger.warning(
                    "ClassifierAgent 503, attempt {}/20, waiting 2s ...",
                    _attempt + 1,
                )
                await asyncio.sleep(2)
            else:
                raise
    # Unreachable: last attempt raises above, but satisfies type checkers.
    raise RuntimeError("classify_query: exhausted 20 retries")
