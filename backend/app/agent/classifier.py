from __future__ import annotations

from typing import Literal

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

    Returns:
        "simple" or "complex" string (PRD §6.2).
    """
    result = await ClassifierAgent.run(query_text)
    return result.output.query_class
