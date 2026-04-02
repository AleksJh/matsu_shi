"""TDD tests for Phase B: multi_retrieve() function."""
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.rag.multi_retriever import multi_retrieve
from app.rag.retriever import RetrievalResult
from app.models.chunk import Chunk


def _make_chunk(chunk_id: int, score: float) -> tuple:
    c = MagicMock(spec=Chunk)
    c.id = chunk_id
    c.content = f"chunk {chunk_id}"
    c.chunk_type = "text"
    c.visual_refs = []
    return c, score


def _make_result(
    no_answer: bool = False,
    max_score: float = 0.80,
    chunk_pairs: list | None = None,
) -> RetrievalResult:
    if chunk_pairs is None:
        chunk_pairs = [_make_chunk(1, max_score)]
    return RetrievalResult(
        chunks=chunk_pairs,
        max_score=max_score,
        no_answer=no_answer,
        recommended_model="gemini-2.5-flash-lite",
        trace_id="trace-123",
    )


# 1. Один запрос → прямой вызов retrieve() без gather
@pytest.mark.asyncio
async def test_single_query_calls_retrieve_directly():
    expected = _make_result()
    with patch("app.rag.multi_retriever.retrieve", new=AsyncMock(return_value=expected)) as mock_retrieve:
        result = await multi_retrieve(["q1"], "WB97S", MagicMock())
    mock_retrieve.assert_called_once()
    assert result is expected


# 2. Дедупликация — оставляем максимальный score по chunk_id
@pytest.mark.asyncio
async def test_dedup_keeps_highest_score():
    chunk_a, _ = _make_chunk(42, 0.0)
    result1 = _make_result(chunk_pairs=[(chunk_a, 0.70)], max_score=0.70)
    result2 = _make_result(chunk_pairs=[(chunk_a, 0.85)], max_score=0.85)

    with patch("app.rag.multi_retriever.retrieve", new=AsyncMock(side_effect=[result1, result2])):
        merged = await multi_retrieve(["q1", "q2"], "WB97S", MagicMock())

    assert len(merged.chunks) == 1
    assert merged.chunks[0][1] == pytest.approx(0.85)


# 3. no_answer=True только если ВСЕ результаты no_answer
@pytest.mark.asyncio
async def test_no_answer_when_all_no_answer():
    r1 = _make_result(no_answer=True, max_score=0.1, chunk_pairs=[])
    r2 = _make_result(no_answer=True, max_score=0.1, chunk_pairs=[])

    with patch("app.rag.multi_retriever.retrieve", new=AsyncMock(side_effect=[r1, r2])):
        merged = await multi_retrieve(["q1", "q2"], "WB97S", MagicMock())

    assert merged.no_answer is True


# 4. no_answer=False если хотя бы один результат имеет ответ
@pytest.mark.asyncio
async def test_not_no_answer_when_any_has_answer():
    r1 = _make_result(no_answer=True, max_score=0.1, chunk_pairs=[])
    r2 = _make_result(no_answer=False, max_score=0.80)

    with patch("app.rag.multi_retriever.retrieve", new=AsyncMock(side_effect=[r1, r2])):
        merged = await multi_retrieve(["q1", "q2"], "WB97S", MagicMock())

    assert merged.no_answer is False


# 5. max_score — глобальный максимум
@pytest.mark.asyncio
async def test_max_score_is_global_max():
    r1 = _make_result(max_score=0.70, chunk_pairs=[_make_chunk(1, 0.70)])
    r2 = _make_result(max_score=0.90, chunk_pairs=[_make_chunk(2, 0.90)])

    with patch("app.rag.multi_retriever.retrieve", new=AsyncMock(side_effect=[r1, r2])):
        merged = await multi_retrieve(["q1", "q2"], "WB97S", MagicMock())

    assert merged.max_score == pytest.approx(0.90)


# 6. Merged список обрезается до 10 чанков
@pytest.mark.asyncio
async def test_caps_merged_at_10_chunks():
    # 3 queries × 7 unique chunks each = 21 chunks total → cap at 10
    def make_result_with_many(offset: int) -> RetrievalResult:
        pairs = [_make_chunk(offset + i, 0.80 - i * 0.01) for i in range(7)]
        return _make_result(chunk_pairs=pairs, max_score=0.80)

    side_effects = [make_result_with_many(i * 7) for i in range(3)]

    with patch("app.rag.multi_retriever.retrieve", new=AsyncMock(side_effect=side_effects)):
        merged = await multi_retrieve(["q1", "q2", "q3"], "WB97S", MagicMock())

    assert len(merged.chunks) == 10


# 7. Параллельное выполнение — все N retrieve() вызваны
@pytest.mark.asyncio
async def test_parallel_execution_all_called():
    results = [_make_result(chunk_pairs=[_make_chunk(i, 0.80)]) for i in range(3)]
    mock_retrieve = AsyncMock(side_effect=results)

    with patch("app.rag.multi_retriever.retrieve", new=mock_retrieve):
        await multi_retrieve(["q1", "q2", "q3"], "WB97S", MagicMock())

    assert mock_retrieve.call_count == 3
