"""TDD unit tests for step_enrich() — PRD §4.1, §4.2 Rule 3.

These tests are written BEFORE the implementation (TDD order).
All tests must pass after step_enrich() is implemented in ingest.py.

Import strategy: conftest.py stubs all heavy deps at collection time.
"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

import pytest

import scripts.ingest as _ingest_module
from scripts.ingest import ChunkData, VisualTag, step_enrich


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def ingest_mod():
    return _ingest_module


@pytest.fixture(scope="module")
def step_enrich(ingest_mod):  # noqa: F811
    return ingest_mod.step_enrich


@pytest.fixture(scope="module")
def ChunkData(ingest_mod):  # noqa: F811
    return ingest_mod.ChunkData


@pytest.fixture(scope="module")
def VisualTag(ingest_mod):  # noqa: F811
    return ingest_mod.VisualTag


# ---------------------------------------------------------------------------
# Factory helpers
# ---------------------------------------------------------------------------

def make_text_chunk(ChunkData, index=0, content="Some text here.", category="hydraulics"):
    return ChunkData(
        chunk_index=index,
        content=content,
        chunk_type="text",
        section_title="Test Section",
        page_number=None,
        visual_refs=[],
        token_count=10,
        doc_name="test_doc",
        machine_model="PC300-8",
        category=category,
    )


def make_table_chunk(ChunkData, index=0):
    return ChunkData(
        chunk_index=index,
        content="| A | B |\n|---|---|\n| 1 | 2 |",
        chunk_type="table",
        section_title="Specs",
        page_number=None,
        visual_refs=[],
        token_count=15,
        doc_name="test_doc",
        machine_model="PC300-8",
        category=None,
    )


def make_visual_tag(VisualTag, page_number=3, r2_url="http://r2/img/page_3.webp",
                    description="Гидравлическая схема насоса."):
    return VisualTag(
        page_number=page_number,
        r2_url=r2_url,
        description=description,
    )


def _mock_gemini_client(summary="Тестовое резюме фрагмента."):
    """Build a mock genai.Client that returns a fixed summary."""
    response = MagicMock()
    response.text = summary
    client = MagicMock()
    client.models.generate_content.return_value = response
    return client


def run(coro):
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# Test 1 — text chunk gets [Контекст: ...] prepended
# ---------------------------------------------------------------------------

class TestEnrichTextChunk:
    def test_enrich_text_chunk_prepends_context(self, step_enrich, ChunkData, ingest_mod):
        chunk = make_text_chunk(ChunkData, content="Описание гидравлического насоса.")
        mock_client = _mock_gemini_client("Фрагмент описывает гидравлический насос.")

        with patch.object(ingest_mod.genai, "Client", return_value=mock_client):
            result = run(step_enrich(
                [chunk], "test_doc", "PC300-8", [], dry_run=False
            ))

        assert len(result) == 1
        assert result[0].content.startswith("[Контекст:"), (
            f"Expected '[Контекст:' prefix, got: {result[0].content[:60]}"
        )
        assert "Описание гидравлического насоса." in result[0].content


# ---------------------------------------------------------------------------
# Test 2 — table chunk gets context header but NOT [Контекст:]
# ---------------------------------------------------------------------------

class TestEnrichTableChunk:
    def test_enrich_table_chunk_prepends_header(self, step_enrich, ChunkData, ingest_mod):
        chunk = make_table_chunk(ChunkData)
        header_text = "Таблица давлений гидравлической системы."
        mock_client = _mock_gemini_client(header_text)

        with patch.object(ingest_mod.genai, "Client", return_value=mock_client):
            result = run(step_enrich(
                [chunk], "test_doc", "PC300-8", [], dry_run=False
            ))

        assert len(result) == 1
        content = result[0].content
        assert "[Контекст:" not in content, (
            f"Table chunk must NOT contain '[Контекст:]', got: {content[:80]}"
        )
        assert header_text in content, f"Expected header text in content: {content[:80]}"
        assert "| A | B |" in content


# ---------------------------------------------------------------------------
# Test 3 — visual_caption chunk gets [Контекст: ...] prepended
# ---------------------------------------------------------------------------

class TestEnrichVisualCaptionChunk:
    def test_enrich_visual_caption_chunk_enriched(self, step_enrich, ChunkData, VisualTag, ingest_mod):
        text_chunk = make_text_chunk(ChunkData)
        vt = make_visual_tag(VisualTag, page_number=5)
        mock_client = _mock_gemini_client("Фрагмент — схема гидравлического контура.")

        with patch.object(ingest_mod.genai, "Client", return_value=mock_client):
            result = run(step_enrich(
                [text_chunk], "test_doc", "PC300-8", [vt], dry_run=False
            ))

        vc_chunks = [c for c in result if c.chunk_type == "visual_caption"]
        assert len(vc_chunks) == 1
        assert vc_chunks[0].content.startswith("[Контекст:"), (
            f"visual_caption should start with '[Контекст:', got: {vc_chunks[0].content[:60]}"
        )


# ---------------------------------------------------------------------------
# Test 4 — text chunk mentioning "Рис. N" gets visual_refs attached
# ---------------------------------------------------------------------------

class TestEnrichAttachesVisualRefs:
    def test_enrich_attaches_visual_refs_to_text_chunk(self, step_enrich, ChunkData, VisualTag):
        chunk = make_text_chunk(
            ChunkData,
            content="Смотри Рис. 3 для деталей.",
        )
        vt = make_visual_tag(VisualTag, page_number=3, r2_url="http://r2/img/page_3.webp")

        result = run(step_enrich(
            [chunk], "test_doc", "PC300-8", [vt], dry_run=True
        ))

        text_results = [c for c in result if c.chunk_type == "text"]
        assert text_results, "No text chunk in result"
        assert "http://r2/img/page_3.webp" in text_results[0].visual_refs, (
            f"Expected r2_url in visual_refs, got: {text_results[0].visual_refs}"
        )

    def test_enrich_does_not_attach_unmatched_ref(self, step_enrich, ChunkData, VisualTag):
        """Text referencing Figure 7 but VisualTag is on page 3 — no match."""
        chunk = make_text_chunk(ChunkData, content="Смотри Figure 7 для деталей.")
        vt = make_visual_tag(VisualTag, page_number=3)

        result = run(step_enrich(
            [chunk], "test_doc", "PC300-8", [vt], dry_run=True
        ))

        text_results = [c for c in result if c.chunk_type == "text"]
        assert text_results[0].visual_refs == []


# ---------------------------------------------------------------------------
# Test 5 — one VisualTag → one new visual_caption ChunkData
# ---------------------------------------------------------------------------

class TestEnrichCreatesVisualCaptionChunks:
    def test_enrich_creates_visual_caption_chunk_per_tag(self, step_enrich, ChunkData, VisualTag):
        text_chunk = make_text_chunk(ChunkData)
        vt1 = make_visual_tag(VisualTag, page_number=1, r2_url="http://r2/p1.webp",
                               description="Схема 1.")
        vt2 = make_visual_tag(VisualTag, page_number=2, r2_url="http://r2/p2.webp",
                               description="Схема 2.")

        result = run(step_enrich(
            [text_chunk], "test_doc", "PC300-8", [vt1, vt2], dry_run=True
        ))

        vc_chunks = [c for c in result if c.chunk_type == "visual_caption"]
        assert len(vc_chunks) == 2, f"Expected 2 visual_caption chunks, got {len(vc_chunks)}"

    def test_visual_caption_chunk_fields_correct(self, step_enrich, ChunkData, VisualTag):
        text_chunk = make_text_chunk(ChunkData, category="hydraulics")
        vt = make_visual_tag(VisualTag, page_number=4, r2_url="http://r2/p4.webp",
                              description="Насос охлаждения.")

        result = run(step_enrich(
            [text_chunk], "test_doc", "PC300-8", [vt], dry_run=True
        ))

        vc = next(c for c in result if c.chunk_type == "visual_caption")
        assert vc.page_number == 4
        assert vc.visual_refs == ["http://r2/p4.webp"]
        assert vc.content == "Насос охлаждения."
        assert vc.doc_name == "test_doc"
        assert vc.machine_model == "PC300-8"
        assert vc.category == "hydraulics"
        assert isinstance(vc.token_count, int) and vc.token_count > 0


# ---------------------------------------------------------------------------
# Test 6 — dry_run skips Gemini (genai.Client never called)
# ---------------------------------------------------------------------------

class TestEnrichDryRun:
    def test_enrich_dry_run_skips_gemini(self, step_enrich, ChunkData, VisualTag, ingest_mod):
        chunks = [make_text_chunk(ChunkData), make_table_chunk(ChunkData, index=1)]
        vt = make_visual_tag(VisualTag)

        with patch.object(ingest_mod.genai, "Client") as mock_client_cls:
            result = run(step_enrich(
                chunks, "test_doc", "PC300-8", [vt], dry_run=True
            ))
            mock_client_cls.assert_not_called()

        # Rule 3 still runs: visual_caption chunk created
        vc_chunks = [c for c in result if c.chunk_type == "visual_caption"]
        assert len(vc_chunks) == 1

    def test_enrich_dry_run_content_unchanged_for_text_and_table(
        self, step_enrich, ChunkData, VisualTag
    ):
        original_text = "Оригинальный текст без изменений."
        text_chunk = make_text_chunk(ChunkData, content=original_text)
        table_chunk = make_table_chunk(ChunkData, index=1)

        result = run(step_enrich(
            [text_chunk, table_chunk], "test_doc", "PC300-8", [], dry_run=True
        ))

        text_results = [c for c in result if c.chunk_type == "text"]
        table_results = [c for c in result if c.chunk_type == "table"]
        assert text_results[0].content == original_text
        assert table_results[0].content == table_chunk.content


# ---------------------------------------------------------------------------
# Test 7 — Gemini error on one chunk: warning logged, rest continue
# ---------------------------------------------------------------------------

class TestEnrichGeminiError:
    def test_enrich_gemini_error_logs_warning_continues(
        self, step_enrich, ChunkData, ingest_mod
    ):
        """If Gemini raises for one chunk, the rest are still enriched."""
        chunk1 = make_text_chunk(ChunkData, index=0, content="Первый фрагмент.")
        chunk2 = make_text_chunk(ChunkData, index=1, content="Второй фрагмент.")

        call_count = 0

        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("Gemini API unavailable")
            response = MagicMock()
            response.text = "Резюме второго фрагмента."
            return response

        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = side_effect

        with patch.object(ingest_mod.genai, "Client", return_value=mock_client):
            result = run(step_enrich(
                [chunk1, chunk2], "test_doc", "PC300-8", [], dry_run=False
            ))

        # Both chunks present
        assert len(result) == 2
        # First chunk: error → content unchanged (no [Контекст:])
        assert not result[0].content.startswith("[Контекст:"), (
            f"chunk1 should be unchanged on error, got: {result[0].content[:60]}"
        )
        # Second chunk: successfully enriched
        assert result[1].content.startswith("[Контекст:"), (
            f"chunk2 should be enriched, got: {result[1].content[:60]}"
        )


# ---------------------------------------------------------------------------
# Test 8 — chunk_index is reindexed 0..N-1 after adding visual_caption chunks
# ---------------------------------------------------------------------------

class TestEnrichReindexing:
    def test_enrich_chunk_indices_sequential_after_reindex(
        self, step_enrich, ChunkData, VisualTag
    ):
        chunks = [
            make_text_chunk(ChunkData, index=0),
            make_table_chunk(ChunkData, index=1),
        ]
        vt = make_visual_tag(VisualTag, page_number=2)

        result = run(step_enrich(
            chunks, "test_doc", "PC300-8", [vt], dry_run=True
        ))

        # 2 original + 1 visual_caption = 3 total
        assert len(result) == 3
        indices = [c.chunk_index for c in result]
        assert indices == list(range(len(result))), (
            f"chunk_index values not sequential: {indices}"
        )
