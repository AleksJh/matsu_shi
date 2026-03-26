"""TDD unit tests for Phase 8.7 — Ingest Pipeline Checkpointing.

Tests cover:
- _compute_checksum(): stable SHA-256 from bytes
- _save_artifact() / _load_artifact(): roundtrip for each dataclass type
- Pipeline orchestration: --stop-after and --start-from flags
"""
from __future__ import annotations

import asyncio
import dataclasses
import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Import helpers — same pattern as test_step_parse.py (relies on conftest stubs)
# ---------------------------------------------------------------------------

def _import_ingest():
    """Import ingest module symbols. conftest.py already stubs heavy deps."""
    from scripts.ingest import (  # noqa: PLC0415
        ChunkData,
        ParseResult,
        VisualTag,
        _compute_checksum,
        _load_artifact,
        _save_artifact,
    )
    return ChunkData, ParseResult, VisualTag, _compute_checksum, _save_artifact, _load_artifact


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_parse_result():
    _, ParseResult, *_ = _import_ingest()
    return ParseResult(
        markdown="# Title\n\nSome text.",
        page_count=10,
        figure_pages=[{"page_number": 3, "bbox": {"l": 10.0, "t": 20.0, "r": 200.0, "b": 300.0}}],
        checksum="abc123",
        doc_name="test_doc",
        original_filename="test_doc.pdf",
    )


@pytest.fixture
def sample_visual_tags():
    _, _, VisualTag, *_ = _import_ingest()
    return [
        VisualTag(page_number=3, r2_url="https://r2.example.com/p3.webp", description="Гидравлическая схема"),
        VisualTag(page_number=7, r2_url="https://r2.example.com/p7.webp", description="Схема электропроводки"),
    ]


@pytest.fixture
def sample_chunks_no_vector():
    ChunkData, *_ = _import_ingest()
    return [
        ChunkData(
            chunk_index=0,
            content="[Контекст: Раздел о гидравлике.]\n\n# Hydraulics\n\nCheck oil level.",
            chunk_type="text",
            section_title="Hydraulics",
            page_number=1,
            visual_refs=[],
            token_count=42,
            doc_name="test_doc",
            machine_model="PC300-8",
            category="hydraulics",
            vector=None,
        ),
        ChunkData(
            chunk_index=1,
            content="| Param | Value |\n|-------|-------|\n| Press | 34 MPa |",
            chunk_type="table",
            section_title="Hydraulics",
            page_number=2,
            visual_refs=[],
            token_count=18,
            doc_name="test_doc",
            machine_model="PC300-8",
            category="hydraulics",
            vector=None,
        ),
    ]


@pytest.fixture
def sample_chunks_with_vector(sample_chunks_no_vector):
    ChunkData, *_ = _import_ingest()
    import dataclasses
    vector = [0.1 * i for i in range(1024)]
    chunk = sample_chunks_no_vector[0]
    return [dataclasses.replace(chunk, vector=vector)] + sample_chunks_no_vector[1:]


# ---------------------------------------------------------------------------
# _compute_checksum tests
# ---------------------------------------------------------------------------

class TestComputeChecksum:
    def test_same_bytes_same_checksum(self, tmp_path):
        _, _, _, _compute_checksum, *_ = _import_ingest()
        content = b"PDF fake content"
        f = tmp_path / "doc.pdf"
        f.write_bytes(content)
        assert _compute_checksum(f) == _compute_checksum(f)

    def test_different_bytes_different_checksum(self, tmp_path):
        _, _, _, _compute_checksum, *_ = _import_ingest()
        f1 = tmp_path / "a.pdf"
        f2 = tmp_path / "b.pdf"
        f1.write_bytes(b"content A")
        f2.write_bytes(b"content B")
        assert _compute_checksum(f1) != _compute_checksum(f2)

    def test_checksum_is_64_hex_chars(self, tmp_path):
        """SHA-256 produces a 64-character hex string."""
        _, _, _, _compute_checksum, *_ = _import_ingest()
        f = tmp_path / "doc.pdf"
        f.write_bytes(b"any content")
        cs = _compute_checksum(f)
        assert len(cs) == 64
        assert all(c in "0123456789abcdef" for c in cs)


# ---------------------------------------------------------------------------
# _save_artifact / _load_artifact roundtrip tests
# ---------------------------------------------------------------------------

class TestArtifactRoundtrip:
    def test_parse_result_roundtrip(self, tmp_path, sample_parse_result):
        _, _, _, _, _save_artifact, _load_artifact = _import_ingest()
        from scripts.ingest import ParseResult

        _save_artifact(tmp_path, "cs1", "parse", sample_parse_result)
        loaded = _load_artifact(tmp_path, "cs1", "parse", ParseResult)

        assert isinstance(loaded, ParseResult)
        assert loaded.markdown == sample_parse_result.markdown
        assert loaded.page_count == sample_parse_result.page_count
        assert loaded.figure_pages == sample_parse_result.figure_pages
        assert loaded.checksum == sample_parse_result.checksum
        assert loaded.doc_name == sample_parse_result.doc_name
        assert loaded.original_filename == sample_parse_result.original_filename

    def test_visual_tags_roundtrip(self, tmp_path, sample_visual_tags):
        _, _, _, _, _save_artifact, _load_artifact = _import_ingest()
        from scripts.ingest import VisualTag

        _save_artifact(tmp_path, "cs1", "visual", sample_visual_tags)
        loaded = _load_artifact(tmp_path, "cs1", "visual", VisualTag)

        assert isinstance(loaded, list)
        assert len(loaded) == 2
        assert loaded[0].page_number == 3
        assert loaded[0].r2_url == "https://r2.example.com/p3.webp"
        assert loaded[1].description == "Схема электропроводки"

    def test_chunks_no_vector_roundtrip(self, tmp_path, sample_chunks_no_vector):
        _, _, _, _, _save_artifact, _load_artifact = _import_ingest()
        from scripts.ingest import ChunkData

        _save_artifact(tmp_path, "cs1", "chunks", sample_chunks_no_vector)
        loaded = _load_artifact(tmp_path, "cs1", "chunks", ChunkData)

        assert isinstance(loaded, list)
        assert len(loaded) == 2
        assert loaded[0].chunk_type == "text"
        assert loaded[0].vector is None
        assert loaded[1].chunk_type == "table"

    def test_chunks_with_vector_roundtrip(self, tmp_path, sample_chunks_with_vector):
        _, _, _, _, _save_artifact, _load_artifact = _import_ingest()
        from scripts.ingest import ChunkData

        _save_artifact(tmp_path, "cs1", "embedded", sample_chunks_with_vector)
        loaded = _load_artifact(tmp_path, "cs1", "embedded", ChunkData)

        assert loaded[0].vector is not None
        assert len(loaded[0].vector) == 1024
        assert abs(loaded[0].vector[10] - 1.0) < 1e-9  # 0.1 * 10 = 1.0

    def test_artifact_dir_created_if_missing(self, tmp_path, sample_parse_result):
        _, _, _, _, _save_artifact, _ = _import_ingest()
        nested = tmp_path / "deep" / "nested"
        # Does not exist yet — must be created automatically
        _save_artifact(nested, "cs1", "parse", sample_parse_result)
        assert (nested / "cs1" / "parse.json").exists()

    def test_artifact_is_valid_json(self, tmp_path, sample_parse_result):
        _, _, _, _, _save_artifact, _ = _import_ingest()
        _save_artifact(tmp_path, "cs1", "parse", sample_parse_result)
        raw = (tmp_path / "cs1" / "parse.json").read_text(encoding="utf-8")
        data = json.loads(raw)  # must not raise
        assert data["checksum"] == "abc123"

    def test_load_missing_artifact_raises(self, tmp_path):
        _, _, _, _, _, _load_artifact = _import_ingest()
        from scripts.ingest import ParseResult
        with pytest.raises(FileNotFoundError, match="Артефакт не найден"):
            _load_artifact(tmp_path, "nonexistent_checksum", "parse", ParseResult)


# ---------------------------------------------------------------------------
# Pipeline orchestration: --stop-after and --start-from
# ---------------------------------------------------------------------------

FAKE_PDF_BYTES = b"%PDF-1.4 fake pipeline test content"


def _make_pdf_path(tmp_path: Path, name: str = "test.pdf") -> Path:
    p = tmp_path / name
    p.write_bytes(FAKE_PDF_BYTES)
    return p


def _make_parse_result_mock():
    from scripts.ingest import ParseResult
    return ParseResult(
        markdown="# Section\n\nContent.",
        page_count=5,
        figure_pages=[],
        checksum="deadbeef" * 8,
        doc_name="test",
        original_filename="test.pdf",
    )


def run(coro):
    return asyncio.run(coro)


class TestStopAfterParse:
    def test_stop_after_parse_saves_artifact_and_exits(self, tmp_path):
        """--stop-after parse: parse.json created, no further steps run."""
        from scripts.ingest import main, build_parser

        pdf = _make_pdf_path(tmp_path)
        artifact_dir = tmp_path / "cache"
        parse_result = _make_parse_result_mock()

        with (
            patch("scripts.ingest.step_parse", new=AsyncMock(return_value=parse_result)) as mock_parse,
            patch("scripts.ingest.step_visual_ingest", new=AsyncMock(return_value=[])) as mock_visual,
            patch("scripts.ingest.step_chunk", new=AsyncMock(return_value=[])) as mock_chunk,
            patch("scripts.ingest.step_enrich", new=AsyncMock(return_value=[])) as mock_enrich,
            patch("scripts.ingest.step_embed", new=AsyncMock(return_value=[])) as mock_embed,
            patch("scripts.ingest.step_write", new=AsyncMock()) as mock_write,
            patch("scripts.ingest.AsyncSessionLocal"),
        ):
            parser = build_parser()
            args = parser.parse_args([
                "--path", str(pdf),
                "--machine-model", "PC300-8",
                "--stop-after", "parse",
                "--artifact-dir", str(artifact_dir),
            ])
            run(main(args))

        mock_parse.assert_called_once()
        mock_visual.assert_not_called()
        mock_chunk.assert_not_called()
        mock_enrich.assert_not_called()
        mock_embed.assert_not_called()
        mock_write.assert_not_called()

        # Artifact file must exist
        import hashlib
        cs = hashlib.sha256(FAKE_PDF_BYTES).hexdigest()
        assert (artifact_dir / cs / "parse.json").exists()


class TestStartFromChunk:
    def test_start_from_chunk_skips_step_parse_and_visual(self, tmp_path):
        """--start-from chunk: step_parse and step_visual_ingest NOT called."""
        from scripts.ingest import main, build_parser, ParseResult, VisualTag, ChunkData, _save_artifact

        pdf = _make_pdf_path(tmp_path)
        artifact_dir = tmp_path / "cache"

        import hashlib
        cs = hashlib.sha256(FAKE_PDF_BYTES).hexdigest()

        # Pre-populate artifacts
        pr = _make_parse_result_mock()
        pr_with_cs = dataclasses.replace(pr, checksum=cs)
        _save_artifact(artifact_dir, cs, "parse", pr_with_cs)
        _save_artifact(artifact_dir, cs, "visual", [])

        fake_chunks = [
            ChunkData(chunk_index=0, content="text", chunk_type="text",
                      section_title=None, page_number=None, visual_refs=[],
                      token_count=1, doc_name="test", machine_model="PC300-8",
                      category=None, vector=None)
        ]

        with (
            patch("scripts.ingest.step_parse", new=AsyncMock(return_value=None)) as mock_parse,
            patch("scripts.ingest.step_visual_ingest", new=AsyncMock(return_value=[])) as mock_visual,
            patch("scripts.ingest.step_chunk", new=AsyncMock(return_value=fake_chunks)) as mock_chunk,
            patch("scripts.ingest.step_enrich", new=AsyncMock(return_value=fake_chunks)) as mock_enrich,
            patch("scripts.ingest.step_embed", new=AsyncMock(return_value=fake_chunks)) as mock_embed,
            patch("scripts.ingest.step_write", new=AsyncMock()) as mock_write,
            patch("scripts.ingest.AsyncSessionLocal"),
        ):
            parser = build_parser()
            args = parser.parse_args([
                "--path", str(pdf),
                "--machine-model", "PC300-8",
                "--start-from", "chunk",
                "--artifact-dir", str(artifact_dir),
            ])
            run(main(args))

        mock_parse.assert_not_called()
        mock_visual.assert_not_called()
        mock_chunk.assert_called_once()
        mock_enrich.assert_called_once()
        mock_embed.assert_called_once()
        mock_write.assert_called_once()


class TestStartFromEnrich:
    def test_start_from_enrich_skips_parse_visual_chunk(self, tmp_path):
        """--start-from enrich: only step_enrich, step_embed, step_write called."""
        from scripts.ingest import main, build_parser, ChunkData, _save_artifact

        pdf = _make_pdf_path(tmp_path)
        artifact_dir = tmp_path / "cache"

        import hashlib
        cs = hashlib.sha256(FAKE_PDF_BYTES).hexdigest()

        pr = _make_parse_result_mock()
        pr_with_cs = dataclasses.replace(pr, checksum=cs)
        _save_artifact(artifact_dir, cs, "parse", pr_with_cs)
        _save_artifact(artifact_dir, cs, "visual", [])

        fake_chunks = [
            ChunkData(chunk_index=0, content="text", chunk_type="text",
                      section_title=None, page_number=None, visual_refs=[],
                      token_count=1, doc_name="test", machine_model="PC300-8",
                      category=None, vector=None)
        ]
        _save_artifact(artifact_dir, cs, "chunks", fake_chunks)

        with (
            patch("scripts.ingest.step_parse", new=AsyncMock()) as mock_parse,
            patch("scripts.ingest.step_visual_ingest", new=AsyncMock()) as mock_visual,
            patch("scripts.ingest.step_chunk", new=AsyncMock()) as mock_chunk,
            patch("scripts.ingest.step_enrich", new=AsyncMock(return_value=fake_chunks)) as mock_enrich,
            patch("scripts.ingest.step_embed", new=AsyncMock(return_value=fake_chunks)) as mock_embed,
            patch("scripts.ingest.step_write", new=AsyncMock()) as mock_write,
            patch("scripts.ingest.AsyncSessionLocal"),
        ):
            parser = build_parser()
            args = parser.parse_args([
                "--path", str(pdf),
                "--machine-model", "PC300-8",
                "--start-from", "enrich",
                "--artifact-dir", str(artifact_dir),
            ])
            run(main(args))

        mock_parse.assert_not_called()
        mock_visual.assert_not_called()
        mock_chunk.assert_not_called()
        mock_enrich.assert_called_once()
        mock_embed.assert_called_once()
        mock_write.assert_called_once()


class TestSaveArtifactsFlag:
    def test_save_artifacts_flag_saves_all_stages(self, tmp_path):
        """--save-artifacts during full run: all 5 artifact files created."""
        from scripts.ingest import main, build_parser, ChunkData, ParseResult

        pdf = _make_pdf_path(tmp_path)
        artifact_dir = tmp_path / "cache"

        import hashlib
        cs = hashlib.sha256(FAKE_PDF_BYTES).hexdigest()

        pr = _make_parse_result_mock()
        pr_with_cs = dataclasses.replace(pr, checksum=cs)

        fake_chunks = [
            ChunkData(chunk_index=0, content="text", chunk_type="text",
                      section_title=None, page_number=None, visual_refs=[],
                      token_count=1, doc_name="test", machine_model="PC300-8",
                      category=None, vector=None)
        ]
        fake_chunks_embedded = [dataclasses.replace(fake_chunks[0], vector=[0.1] * 1024)]

        with (
            patch("scripts.ingest.step_parse", new=AsyncMock(return_value=pr_with_cs)),
            patch("scripts.ingest.step_visual_ingest", new=AsyncMock(return_value=[])),
            patch("scripts.ingest.step_chunk", new=AsyncMock(return_value=fake_chunks)),
            patch("scripts.ingest.step_enrich", new=AsyncMock(return_value=fake_chunks)),
            patch("scripts.ingest.step_embed", new=AsyncMock(return_value=fake_chunks_embedded)),
            patch("scripts.ingest.step_write", new=AsyncMock()),
            patch("scripts.ingest.AsyncSessionLocal"),
        ):
            parser = build_parser()
            args = parser.parse_args([
                "--path", str(pdf),
                "--machine-model", "PC300-8",
                "--save-artifacts",
                "--artifact-dir", str(artifact_dir),
            ])
            run(main(args))

        cache_dir = artifact_dir / cs
        assert (cache_dir / "parse.json").exists(), "parse.json missing"
        assert (cache_dir / "visual.json").exists(), "visual.json missing"
        assert (cache_dir / "chunks.json").exists(), "chunks.json missing"
        assert (cache_dir / "enriched.json").exists(), "enriched.json missing"
        assert (cache_dir / "embedded.json").exists(), "embedded.json missing"
