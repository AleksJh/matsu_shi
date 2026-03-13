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
