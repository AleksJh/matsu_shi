"""TDD tests for ClassifierAgent (Task 4.2)."""
from __future__ import annotations

import pytest
from pydantic import ValidationError
from unittest.mock import AsyncMock, MagicMock, patch

from app.agent.classifier import ClassifierAgent, ClassifierOutput, classify_query
from app.core.config import settings


# ---------------------------------------------------------------------------
# 1. ClassifierOutput schema tests (no network)
# ---------------------------------------------------------------------------

def test_classifier_output_simple():
    out = ClassifierOutput(query_class="simple")
    assert out.query_class == "simple"


def test_classifier_output_complex():
    out = ClassifierOutput(query_class="complex")
    assert out.query_class == "complex"


def test_classifier_output_invalid():
    with pytest.raises(ValidationError):
        ClassifierOutput(query_class="unknown")


# ---------------------------------------------------------------------------
# 2. classify_query() wrapper tests (mocked Agent.run)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_classify_query_returns_simple():
    mock_result = MagicMock()
    mock_result.output = ClassifierOutput(query_class="simple")

    with patch.object(ClassifierAgent, "run", new=AsyncMock(return_value=mock_result)):
        result = await classify_query("Какой код ошибки E03?")

    assert result == "simple"


@pytest.mark.asyncio
async def test_classify_query_returns_complex():
    mock_result = MagicMock()
    mock_result.output = ClassifierOutput(query_class="complex")

    with patch.object(ClassifierAgent, "run", new=AsyncMock(return_value=mock_result)):
        result = await classify_query(
            "Одновременно горят E03 и E07, гидравлика и трансмиссия не работают — "
            "с чего начать диагностику?"
        )

    assert result == "complex"


# ---------------------------------------------------------------------------
# 3. Agent configuration test (static, no network)
# ---------------------------------------------------------------------------

def test_agent_model_name():
    assert ClassifierAgent.model.model_name == settings.LLM_LITE_MODEL


# ---------------------------------------------------------------------------
# 4. classify_query() with history — context-aware classification
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_classify_followup_with_history_includes_context_in_prompt():
    """When history is provided, the prompt sent to the agent must include
    the session context block so the agent can classify the follow-up correctly."""
    mock_result = MagicMock()
    mock_result.output = ClassifierOutput(query_class="complex")

    captured_prompt: list[str] = []

    async def mock_run(prompt, *args, **kwargs):
        captured_prompt.append(prompt)
        return mock_result

    history = [
        "Вопрос: WB97S не заводится, стартер крутится с трудом.\nОтвет: Проверьте аккумулятор.",
    ]

    with patch.object(ClassifierAgent, "run", side_effect=mock_run):
        result = await classify_query(
            "А может ли проблема быть из-за электромагнитного клапана?",
            history=history,
        )

    assert result == "complex"
    assert captured_prompt, "ClassifierAgent.run was not called"
    assert "Контекст сессии:" in captured_prompt[0]
    assert "WB97S не заводится" in captured_prompt[0]
    assert "электромагнитного клапана" in captured_prompt[0]


@pytest.mark.asyncio
async def test_classify_no_history_sends_query_only():
    """Without history the prompt is just the raw query_text — no context block."""
    mock_result = MagicMock()
    mock_result.output = ClassifierOutput(query_class="simple")

    captured_prompt: list[str] = []

    async def mock_run(prompt, *args, **kwargs):
        captured_prompt.append(prompt)
        return mock_result

    with patch.object(ClassifierAgent, "run", side_effect=mock_run):
        result = await classify_query("Какой код ошибки E03?")

    assert result == "simple"
    assert "Контекст сессии:" not in captured_prompt[0]


@pytest.mark.asyncio
async def test_classify_empty_history_list_sends_query_only():
    """history=[] must behave the same as history=None — no context block."""
    mock_result = MagicMock()
    mock_result.output = ClassifierOutput(query_class="simple")

    captured_prompt: list[str] = []

    async def mock_run(prompt, *args, **kwargs):
        captured_prompt.append(prompt)
        return mock_result

    with patch.object(ClassifierAgent, "run", side_effect=mock_run):
        result = await classify_query("Какой ресурс масляного фильтра?", history=[])

    assert result == "simple"
    assert "Контекст сессии:" not in captured_prompt[0]


@pytest.mark.asyncio
async def test_classify_uses_last_two_history_entries():
    """Only the last 2 history entries must appear in the prompt (keeps it short)."""
    mock_result = MagicMock()
    mock_result.output = ClassifierOutput(query_class="complex")

    captured_prompt: list[str] = []

    async def mock_run(prompt, *args, **kwargs):
        captured_prompt.append(prompt)
        return mock_result

    history = [
        "Вопрос: Первый вопрос.\nОтвет: Первый ответ.",
        "Вопрос: Второй вопрос.\nОтвет: Второй ответ.",
        "Вопрос: Третий вопрос.\nОтвет: Третий ответ.",
    ]

    with patch.object(ClassifierAgent, "run", side_effect=mock_run):
        await classify_query("Новый вопрос.", history=history)

    prompt = captured_prompt[0]
    assert "Третий вопрос" in prompt
    assert "Второй вопрос" in prompt
    assert "Первый вопрос" not in prompt
