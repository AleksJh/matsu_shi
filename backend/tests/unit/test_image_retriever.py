"""
TDD tests for Phase C: retrieve_visual() function.
Tests must FAIL before implementation.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.rag.retriever import retrieve_visual
from app.agent.responder import respond
from app.rag.retriever import RetrievalResult


def _make_visual_chunk(chunk_id: int = 99, visual_refs: list | None = None):
    from app.models.chunk import Chunk
    c = Chunk()
    c.id = chunk_id
    c.content = "Figure 12: Hydraulic pump assembly"
    c.chunk_type = "visual_caption"
    c.section_title = "Hydraulic"
    c.page_number = None
    c.machine_model = "WB97S"
    c.visual_refs = visual_refs or ["https://r2.example.com/img1.jpg"]
    return c


def _make_text_chunk(chunk_id: int = 1):
    from app.models.chunk import Chunk
    c = Chunk()
    c.id = chunk_id
    c.content = "Замените гидравлический фильтр."
    c.chunk_type = "text"
    c.section_title = "Hydraulic"
    c.page_number = None
    c.machine_model = "WB97S"
    c.visual_refs = []
    return c


def _make_retrieval_result(max_score: float = 0.80):
    chunk = _make_text_chunk()
    return RetrievalResult(
        chunks=[(chunk, max_score)],
        max_score=max_score,
        no_answer=False,
        recommended_model="gemini-2.5-flash-lite",
    )


@pytest.mark.asyncio
async def test_retrieve_visual_returns_none_below_threshold():
    """chunk with score 0.70, min_score=0.75 → None"""
    visual_chunk = _make_visual_chunk()
    mock_row = (visual_chunk, 0.70)

    with patch("app.rag.retriever.embed_text", new=AsyncMock(return_value=[0.1] * 1024)), \
         patch("app.rag.retriever.AsyncSessionLocal") as mock_session_cls:
        mock_session = AsyncMock()
        mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=None)
        mock_result = MagicMock()
        mock_result.first.return_value = mock_row
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await retrieve_visual(
            query_text="гидравлический насос",
            machine_model="WB97S",
            min_score=0.75,
        )

    assert result is None


@pytest.mark.asyncio
async def test_retrieve_visual_returns_chunk_above_threshold():
    """chunk with score 0.80, min_score=0.75 → returns (chunk, 0.80)"""
    visual_chunk = _make_visual_chunk()
    mock_row = (visual_chunk, 0.80)

    with patch("app.rag.retriever.embed_text", new=AsyncMock(return_value=[0.1] * 1024)), \
         patch("app.rag.retriever.AsyncSessionLocal") as mock_session_cls:
        mock_session = AsyncMock()
        mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=None)
        mock_result = MagicMock()
        mock_result.first.return_value = mock_row
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await retrieve_visual(
            query_text="гидравлический насос",
            machine_model="WB97S",
            min_score=0.75,
        )

    assert result is not None
    chunk, score = result
    assert chunk.id == 99
    assert score == 0.80


@pytest.mark.asyncio
async def test_retrieve_visual_returns_none_when_db_empty():
    """No rows in DB → returns None"""
    with patch("app.rag.retriever.embed_text", new=AsyncMock(return_value=[0.1] * 1024)), \
         patch("app.rag.retriever.AsyncSessionLocal") as mock_session_cls:
        mock_session = AsyncMock()
        mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=None)
        mock_result = MagicMock()
        mock_result.first.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await retrieve_visual(
            query_text="гидравлический насос",
            machine_model="WB97S",
            min_score=0.75,
        )

    assert result is None


@pytest.mark.asyncio
async def test_respond_attaches_visual_url_to_first_citation():
    """When retrieve_visual returns a visual chunk, citations[0].visual_url is set."""
    from unittest.mock import patch
    from app.schemas.query import QueryResponse, Citation
    from app.agent.responder import respond

    retrieval = _make_retrieval_result(max_score=0.80)
    visual_chunk = _make_visual_chunk(visual_refs=["https://r2.example.com/img.jpg"])

    fake_llm = QueryResponse(
        answer="Замените фильтр [1].",
        citations=[Citation(doc_name="WB97S Manual", section="Hydraulic", page=47, visual_url=None)],
        model_used="lite",
        no_answer=False,
        retrieval_score=0.80,
        query_class="simple",
        session_id=None,
    )

    with patch("app.agent.responder.ResponderAgent") as mock_agent_cls, \
         patch("app.agent.responder.retrieve_visual", new=AsyncMock(return_value=(visual_chunk, 0.80))):
        mock_agent = MagicMock()
        mock_agent_cls.run = AsyncMock(return_value=MagicMock(output=fake_llm))

        result = await respond(
            query_text="Проблема с гидравлическим насосом",
            retrieval_result=retrieval,
            query_class="simple",
            session_id=1,
            prior_context=None,
            machine_model="WB97S",
        )

    assert result.citations[0].visual_url == "https://r2.example.com/img.jpg"


@pytest.mark.asyncio
async def test_respond_no_visual_when_retrieve_returns_none():
    """When retrieve_visual returns None, citations have no visual_url."""
    from app.schemas.query import QueryResponse, Citation
    from app.agent.responder import respond

    retrieval = _make_retrieval_result(max_score=0.80)

    fake_llm = QueryResponse(
        answer="Замените фильтр [1].",
        citations=[Citation(doc_name="WB97S Manual", section="Hydraulic", page=47, visual_url=None)],
        model_used="lite",
        no_answer=False,
        retrieval_score=0.80,
        query_class="simple",
        session_id=None,
    )

    with patch("app.agent.responder.ResponderAgent") as mock_agent_cls, \
         patch("app.agent.responder.retrieve_visual", new=AsyncMock(return_value=None)):
        mock_agent_cls.run = AsyncMock(return_value=MagicMock(output=fake_llm))

        result = await respond(
            query_text="Проблема с гидравлическим насосом",
            retrieval_result=retrieval,
            query_class="simple",
            session_id=1,
            prior_context=None,
            machine_model="WB97S",
        )

    assert result.citations[0].visual_url is None
