"""TDD tests for Phase A: reformulate() function."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.agent.reformulator import ReformulationResult, ReformulatorAgent, reformulate


# 1. Без истории — возвращает оригинальный запрос без вызова Agent
@pytest.mark.asyncio
async def test_no_history_returns_original_query():
    with patch.object(ReformulatorAgent, "run", new=AsyncMock()) as mock_run:
        result = await reformulate([], "вопрос без истории")
    assert result == ["вопрос без истории"]
    mock_run.assert_not_called()


# 2. С историей — Agent.run вызывается ровно один раз
@pytest.mark.asyncio
async def test_with_history_calls_agent():
    mock_result = MagicMock()
    mock_result.output = ReformulationResult(queries=["конкретный технический запрос"])
    with patch.object(ReformulatorAgent, "run", new=AsyncMock(return_value=mock_result)) as mock_run:
        result = await reformulate(["Вопрос: X\nОтвет: Y"], "следующий вопрос")
    mock_run.assert_called_once()
    assert result == ["конкретный технический запрос"]


# 3. Возвращает список строк
@pytest.mark.asyncio
async def test_reformulation_returns_list_of_strings():
    mock_result = MagicMock()
    mock_result.output = ReformulationResult(queries=["q1", "q2"])
    with patch.object(ReformulatorAgent, "run", new=AsyncMock(return_value=mock_result)):
        result = await reformulate(["history"], "вопрос")
    assert result == ["q1", "q2"]


# 4. ReformulationResult — схема max_length=5
def test_reformulation_schema_max_5():
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        ReformulationResult(queries=["a"] * 6)


# 5. ReformulationResult — схема min_length=1
def test_reformulation_schema_min_1():
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        ReformulationResult(queries=[])


# 6. Fallback на 503 — возвращает [query_text]
@pytest.mark.asyncio
async def test_reformulation_fallback_on_error():
    with patch.object(
        ReformulatorAgent, "run",
        new=AsyncMock(side_effect=RuntimeError("503 UNAVAILABLE"))
    ):
        result = await reformulate(["history"], "мой вопрос")
    assert result == ["мой вопрос"]


# 7. Только последние 3 записи истории передаются в Agent
@pytest.mark.asyncio
async def test_reformulation_uses_last_3_history_entries():
    history = [f"Вопрос: q{i}\nОтвет: a{i}" for i in range(5)]
    captured_prompt: list[str] = []

    async def mock_run(prompt, **kwargs):
        captured_prompt.append(prompt)
        r = MagicMock()
        r.output = ReformulationResult(queries=["result"])
        return r

    with patch.object(ReformulatorAgent, "run", side_effect=mock_run):
        await reformulate(history, "новый вопрос")

    assert "q4" in captured_prompt[0]  # последняя запись присутствует
    assert "q0" not in captured_prompt[0]  # первая запись отсутствует (history[-3:])
    assert "q1" not in captured_prompt[0]
