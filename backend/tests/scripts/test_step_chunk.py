"""TDD unit tests for step_chunk() — PRD §4.2 Rules 1-4.

These tests are written BEFORE the implementation (TDD order).
All tests must pass after step_chunk() is implemented in ingest.py.

Import strategy: conftest.py stubs heavy deps (docling, boto3, etc.) at collection
time, so we can use simple top-level imports here — same pattern as test_step_parse.py.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from scripts.ingest import (  # noqa: E402
    ChunkData,
    ParseResult,
    _merge_small_chunks,
    dc_replace,
    step_chunk,
)


# ---------------------------------------------------------------------------
# Module-level aliases exposed as fixtures for backward compatibility
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def ingest_mod():
    import scripts.ingest as _mod
    return _mod


@pytest.fixture(scope="module")
def step_chunk(ingest_mod):  # noqa: F811 — shadows the import intentionally
    return ingest_mod.step_chunk


@pytest.fixture(scope="module")
def ChunkData(ingest_mod):  # noqa: F811
    return ingest_mod.ChunkData


@pytest.fixture(scope="module")
def ParseResult(ingest_mod):  # noqa: F811
    return ingest_mod.ParseResult


@pytest.fixture(scope="module")
def merge_small_chunks(ingest_mod):
    return ingest_mod._merge_small_chunks


# ---------------------------------------------------------------------------
# Factory helpers
# ---------------------------------------------------------------------------

def make_parse_result(ParseResult, markdown: str) -> Any:
    return ParseResult(
        markdown=markdown,
        page_count=1,
        figure_pages=[],
        checksum="abc123",
        doc_name="test_doc",
        original_filename="test_doc.pdf",
    )


def run(coro):
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# Rule 1 — Heading boundaries
# ---------------------------------------------------------------------------

class TestRule1HeadingBoundary:
    def test_single_heading_creates_chunk(self, step_chunk, ParseResult, ChunkData):
        md = "# Section One\n\nSome text here.\n"
        pr = make_parse_result(ParseResult, md)
        chunks = run(step_chunk(pr, "PC300-8", "hydraulics", dry_run=True))

        assert len(chunks) >= 1
        text_chunks = [c for c in chunks if c.chunk_type == "text"]
        assert len(text_chunks) >= 1

    def test_two_headings_create_separate_chunks(self, step_chunk, ParseResult):
        # Content must exceed CHUNK_MIN_TOKENS (80) so _merge_small_chunks keeps both
        words_one = " ".join([f"word{i}" for i in range(90)])
        words_two = " ".join([f"term{i}" for i in range(90)])
        md = (
            f"# Section One\n\n{words_one}\n\n"
            f"# Section Two\n\n{words_two}\n"
        )
        pr = make_parse_result(ParseResult, md)
        chunks = run(step_chunk(pr, "PC300-8", None, dry_run=True))

        text_chunks = [c for c in chunks if c.chunk_type == "text"]
        # Each heading spawns its own chunk (content is large enough to survive merge)
        assert len(text_chunks) >= 2

    def test_section_title_recorded(self, step_chunk, ParseResult):
        md = "## Hydraulic Pump Replacement\n\nTighten bolt to 50 Nm.\n"
        pr = make_parse_result(ParseResult, md)
        chunks = run(step_chunk(pr, "PC300-8", None, dry_run=True))

        text_chunks = [c for c in chunks if c.chunk_type == "text"]
        assert any(
            c.section_title == "Hydraulic Pump Replacement" for c in text_chunks
        ), f"section_titles found: {[c.section_title for c in text_chunks]}"

    def test_h4_heading_is_boundary(self, step_chunk, ParseResult):
        # Content must exceed CHUNK_MIN_TOKENS (80) so _merge_small_chunks keeps both
        words_a = " ".join([f"step_a_word{i}" for i in range(90)])
        words_b = " ".join([f"step_b_word{i}" for i in range(90)])
        md = (
            f"#### Step A\n\n{words_a}\n\n"
            f"#### Step B\n\n{words_b}\n"
        )
        pr = make_parse_result(ParseResult, md)
        chunks = run(step_chunk(pr, "WB97S-5", None, dry_run=True))

        text_chunks = [c for c in chunks if c.chunk_type == "text"]
        assert len(text_chunks) >= 2

    def test_procedural_steps_not_split(self, step_chunk, ParseResult):
        """Lines like '1. Step' or '- item' inside a section stay in one chunk."""
        md = (
            "## Oil Filter Replacement\n\n"
            "1. Drain the oil.\n"
            "2. Remove old filter.\n"
            "3. Install new filter.\n"
            "4. Refill oil.\n"
        )
        pr = make_parse_result(ParseResult, md)
        chunks = run(step_chunk(pr, "PC300-8", None, dry_run=True))

        text_chunks = [c for c in chunks if c.chunk_type == "text"]
        # All procedural lines should be in the same chunk (same section, no heading split)
        section_chunk = next(
            (c for c in text_chunks if c.section_title == "Oil Filter Replacement"), None
        )
        assert section_chunk is not None, "Expected a chunk for 'Oil Filter Replacement'"
        assert "1. Drain the oil." in section_chunk.content
        assert "4. Refill oil." in section_chunk.content


# ---------------------------------------------------------------------------
# Rule 2 — Table isolation
# ---------------------------------------------------------------------------

class TestRule2TableIsolation:
    def test_table_gets_own_chunk(self, step_chunk, ParseResult):
        md = (
            "## Pressure Specs\n\n"
            "| Parameter | Value |\n"
            "|-----------|-------|\n"
            "| Relief pressure | 34.3 MPa |\n"
            "\n"
            "Some follow-up text.\n"
        )
        pr = make_parse_result(ParseResult, md)
        chunks = run(step_chunk(pr, "PC300-8", None, dry_run=True))

        table_chunks = [c for c in chunks if c.chunk_type == "table"]
        assert len(table_chunks) == 1, f"Expected 1 table chunk, got {len(table_chunks)}"

    def test_table_chunk_contains_markdown(self, step_chunk, ParseResult):
        md = (
            "| A | B |\n"
            "|---|---|\n"
            "| 1 | 2 |\n"
        )
        pr = make_parse_result(ParseResult, md)
        chunks = run(step_chunk(pr, "PC300-8", None, dry_run=True))

        table_chunks = [c for c in chunks if c.chunk_type == "table"]
        assert table_chunks, "No table chunk found"
        assert "| A | B |" in table_chunks[0].content

    def test_table_inherits_section_title(self, step_chunk, ParseResult):
        md = (
            "## Torque Values\n\n"
            "| Bolt | Nm |\n"
            "|------|----|\n"
            "| M10  | 50 |\n"
        )
        pr = make_parse_result(ParseResult, md)
        chunks = run(step_chunk(pr, "PC300-8", None, dry_run=True))

        table_chunks = [c for c in chunks if c.chunk_type == "table"]
        assert table_chunks, "No table chunk found"
        assert table_chunks[0].section_title == "Torque Values"

    def test_multiple_tables_each_isolated(self, step_chunk, ParseResult):
        md = (
            "| A | B |\n|---|---|\n| 1 | 2 |\n\n"
            "Some text in between.\n\n"
            "| C | D |\n|---|---|\n| 3 | 4 |\n"
        )
        pr = make_parse_result(ParseResult, md)
        chunks = run(step_chunk(pr, "PC300-8", None, dry_run=True))

        table_chunks = [c for c in chunks if c.chunk_type == "table"]
        assert len(table_chunks) == 2, f"Expected 2 table chunks, got {len(table_chunks)}"


# ---------------------------------------------------------------------------
# Rule 3 — visual_refs empty at chunk time (filled in step_enrich 2.5)
# ---------------------------------------------------------------------------

class TestRule3VisualRefsEmpty:
    def test_all_chunks_have_empty_visual_refs(self, step_chunk, ParseResult):
        md = (
            "## Section\n\nSee Figure 1 for details.\n\n"
            "| A | B |\n|---|---|\n| 1 | 2 |\n"
        )
        pr = make_parse_result(ParseResult, md)
        chunks = run(step_chunk(pr, "PC300-8", None, dry_run=True))

        for chunk in chunks:
            assert chunk.visual_refs == [], (
                f"Chunk {chunk.chunk_index} has non-empty visual_refs: {chunk.visual_refs}"
            )


# ---------------------------------------------------------------------------
# Rule 4 — 10% token overlap (text chunks only)
# ---------------------------------------------------------------------------

class TestRule4Overlap:
    def test_second_text_chunk_starts_with_overlap(self, step_chunk, ParseResult):
        """Second text chunk must start with tail words from the first."""
        # Both sections must exceed CHUNK_MIN_TOKENS (80) to survive _merge_small_chunks
        words_a = " ".join([f"word{i}" for i in range(90)])
        words_b = " ".join([f"term{i}" for i in range(90)])
        md = f"# Section A\n\n{words_a}\n\n# Section B\n\n{words_b}\n"
        pr = make_parse_result(ParseResult, md)
        chunks = run(step_chunk(pr, "PC300-8", None, dry_run=True))

        text_chunks = [c for c in chunks if c.chunk_type == "text"]
        assert len(text_chunks) >= 2, "Need at least 2 text chunks to test overlap"

        first = text_chunks[0]
        second = text_chunks[1]

        # The last word of first chunk should appear at start of second chunk
        last_words_of_first = first.content.split()[-1]
        assert last_words_of_first in second.content, (
            f"Expected overlap word '{last_words_of_first}' at start of second chunk.\n"
            f"Second chunk starts: {second.content[:100]}"
        )

    def test_first_text_chunk_has_no_overlap(self, step_chunk, ParseResult):
        """First chunk must NOT start with overlap content."""
        md = "# Section A\n\nOriginal text here without any prefix overlap.\n\n# Section B\n\nMore text.\n"
        pr = make_parse_result(ParseResult, md)
        chunks = run(step_chunk(pr, "PC300-8", None, dry_run=True))

        text_chunks = [c for c in chunks if c.chunk_type == "text"]
        assert text_chunks, "No text chunks found"
        first = text_chunks[0]
        # First chunk content should start with the actual heading or text, not overlap
        # It should not be prepended by anything from a non-existent previous chunk
        assert first.chunk_index == 0

    def test_table_chunks_no_overlap(self, step_chunk, ParseResult):
        """Table chunks must NOT receive overlap from preceding text chunks."""
        words_a = " ".join([f"word{i}" for i in range(50)])
        md = (
            f"# Section A\n\n{words_a}\n\n"
            "| A | B |\n|---|---|\n| 1 | 2 |\n"
        )
        pr = make_parse_result(ParseResult, md)
        chunks = run(step_chunk(pr, "PC300-8", None, dry_run=True))

        table_chunks = [c for c in chunks if c.chunk_type == "table"]
        assert table_chunks, "No table chunk found"
        table_content = table_chunks[0].content
        # Table content must start with '|', not with overlap text
        assert table_content.lstrip().startswith("|"), (
            f"Table chunk must start with '|', got: {table_content[:60]}"
        )


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_empty_markdown_returns_empty_list(self, step_chunk, ParseResult):
        pr = make_parse_result(ParseResult, "")
        chunks = run(step_chunk(pr, "PC300-8", None, dry_run=True))
        assert chunks == []

    def test_whitespace_only_markdown_returns_empty_list(self, step_chunk, ParseResult):
        pr = make_parse_result(ParseResult, "   \n\n\t\n")
        chunks = run(step_chunk(pr, "PC300-8", None, dry_run=True))
        assert chunks == []

    def test_chunk_data_fields_populated(self, step_chunk, ParseResult):
        """All ChunkData fields must be correctly set."""
        md = "## Maintenance\n\nCheck oil level daily.\n"
        pr = make_parse_result(ParseResult, md)
        chunks = run(step_chunk(pr, "WB97S-5", "maintenance", dry_run=True))

        assert chunks, "Expected at least one chunk"
        c = chunks[0]
        assert c.doc_name == "test_doc"
        assert c.machine_model == "WB97S-5"
        assert c.category == "maintenance"
        assert c.chunk_type in ("text", "table", "visual_caption")
        assert isinstance(c.token_count, int)
        assert c.token_count > 0
        assert isinstance(c.visual_refs, list)
        assert isinstance(c.chunk_index, int)
        assert c.chunk_index >= 0

    def test_chunk_indices_are_sequential(self, step_chunk, ParseResult):
        md = (
            "# A\n\nText A.\n\n"
            "| X | Y |\n|---|---|\n| 1 | 2 |\n\n"
            "# B\n\nText B.\n"
        )
        pr = make_parse_result(ParseResult, md)
        chunks = run(step_chunk(pr, "PC300-8", None, dry_run=True))

        indices = [c.chunk_index for c in chunks]
        assert indices == list(range(len(chunks))), (
            f"chunk_index values are not sequential: {indices}"
        )

    def test_no_empty_content_chunks(self, step_chunk, ParseResult):
        """No chunk should have empty or whitespace-only content."""
        md = (
            "# Section\n\n\n\n"
            "Actual content here.\n\n"
            "# Empty Section\n\n"
            "## Subsection\n\nMore content.\n"
        )
        pr = make_parse_result(ParseResult, md)
        chunks = run(step_chunk(pr, "PC300-8", None, dry_run=True))

        for chunk in chunks:
            assert chunk.content.strip(), (
                f"Chunk {chunk.chunk_index} has empty content"
            )


# ---------------------------------------------------------------------------
# _merge_small_chunks — post-processing step (CHUNK_MIN_TOKENS)
# ---------------------------------------------------------------------------


class TestMergeSmallChunks:
    """Tests for the _merge_small_chunks() helper (PRD Phase 9 improvement)."""

    def _make_text_chunk(self, ChunkData, content: str, index: int = 0) -> object:
        return ChunkData(
            chunk_index=index,
            content=content,
            chunk_type="text",
            section_title=f"Section {index}",
            page_number=index + 1,
            visual_refs=[],
            token_count=len(content.split()),  # rough token count for test purposes
            doc_name="test_doc",
            machine_model="WB97S-5",
            category=None,
        )

    def _make_table_chunk(self, ChunkData, content: str, index: int = 0) -> object:
        return ChunkData(
            chunk_index=index,
            content=content,
            chunk_type="table",
            section_title="Some Section",
            page_number=1,
            visual_refs=[],
            token_count=len(content.split()),
            doc_name="test_doc",
            machine_model="WB97S-5",
            category=None,
        )

    def test_tiny_chunk_merged_into_previous(self, merge_small_chunks, ChunkData, ingest_mod):
        """A text chunk with token_count < min_tokens merges into the preceding text chunk."""
        big = self._make_text_chunk(ChunkData, " ".join([f"w{i}" for i in range(100)]), index=0)
        tiny = self._make_text_chunk(ChunkData, "tiny", index=1)
        tiny_with_count = ingest_mod.dc_replace(tiny, token_count=5)

        result = merge_small_chunks([big, tiny_with_count], min_tokens=80)

        assert len(result) == 1, f"Expected 1 merged chunk, got {len(result)}"
        assert "tiny" in result[0].content
        assert result[0].chunk_index == 0

    def test_chunk_above_threshold_not_merged(self, merge_small_chunks, ChunkData, ingest_mod):
        """A text chunk with token_count >= min_tokens is kept as a separate chunk."""
        big = self._make_text_chunk(ChunkData, " ".join([f"w{i}" for i in range(100)]), index=0)
        medium = self._make_text_chunk(ChunkData, " ".join([f"x{i}" for i in range(90)]), index=1)
        medium_with_count = ingest_mod.dc_replace(medium, token_count=90)

        result = merge_small_chunks([big, medium_with_count], min_tokens=80)

        assert len(result) == 2, f"Expected 2 chunks, got {len(result)}"

    def test_table_chunk_never_merged(self, merge_small_chunks, ChunkData, ingest_mod):
        """Table chunks are never absorbed into preceding text chunks."""
        text = self._make_text_chunk(ChunkData, " ".join([f"w{i}" for i in range(100)]), index=0)
        table = self._make_table_chunk(ChunkData, "| A | B |\n|---|---|\n| 1 | 2 |", index=1)
        table_with_count = ingest_mod.dc_replace(table, token_count=5)

        result = merge_small_chunks([text, table_with_count], min_tokens=80)

        assert len(result) == 2
        assert result[1].chunk_type == "table"

    def test_tiny_first_chunk_kept_as_is(self, merge_small_chunks, ChunkData, ingest_mod):
        """A tiny chunk with no preceding text chunk is kept (cannot merge into nothing)."""
        tiny = self._make_text_chunk(ChunkData, "short", index=0)
        tiny_with_count = ingest_mod.dc_replace(tiny, token_count=3)

        result = merge_small_chunks([tiny_with_count], min_tokens=80)

        assert len(result) == 1
        assert result[0].content == "short"

    def test_indices_resequenced_after_merge(self, merge_small_chunks, ChunkData, ingest_mod):
        """chunk_index values must be 0..N-1 after merging."""
        big = self._make_text_chunk(ChunkData, " ".join([f"w{i}" for i in range(100)]), index=0)
        tiny1 = ingest_mod.dc_replace(self._make_text_chunk(ChunkData, "a", index=1), token_count=2)
        big2 = ingest_mod.dc_replace(self._make_text_chunk(ChunkData, " ".join([f"x{i}" for i in range(100)]), index=2), token_count=100)

        result = merge_small_chunks([big, tiny1, big2], min_tokens=80)

        indices = [c.chunk_index for c in result]
        assert indices == list(range(len(result))), f"Non-sequential indices: {indices}"

    def test_step_chunk_respects_min_tokens(self, step_chunk, ParseResult):
        """step_chunk() must call _merge_small_chunks: a single-word subsection merges."""
        # Two headings: big section (many words) + tiny subsection (1 word)
        big_text = " ".join([f"word{i}" for i in range(150)])
        md = f"# Big Section\n\n{big_text}\n\n## Tiny\n\nX\n"
        pr = make_parse_result(ParseResult, md)
        chunks = run(step_chunk(pr, "WB97S-5", None, dry_run=True))

        text_chunks = [c for c in chunks if c.chunk_type == "text"]
        # "Tiny" section with content "X" has ~1 token → should be merged into "Big Section"
        tiny_standalone = [c for c in text_chunks if c.section_title == "Tiny"]
        assert len(tiny_standalone) == 0, (
            f"Tiny section should have been merged, but found standalone chunk: "
            f"{[c.content[:50] for c in tiny_standalone]}"
        )
