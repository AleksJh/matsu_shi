"""Unit tests for step_parse() and _prompt_machine_model() — Task 2.2.

All external dependencies (filesystem, DB, Docling, pypdf) are mocked.
Tests run without a real PDF, database connection, or docling installation.

Import strategy:
  - scripts.ingest is imported lazily (inside each test) so the conftest.py
    has already injected docling stubs into sys.modules before first use.
  - pdf_path is always a MagicMock (not a real pathlib.Path), so no filesystem
    access occurs and no Path.read_bytes patching is needed.
  - pypdf.PdfReader / PdfWriter are patched via patch.object on the global
    sys.modules["pypdf"] MagicMock (set by conftest) to control page counts
    without requiring a real PDF file.
"""
from __future__ import annotations

import hashlib
import sys
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

FAKE_PDF_BYTES = b"%PDF-1.4 fake content for testing"
FAKE_CHECKSUM = hashlib.sha256(FAKE_PDF_BYTES).hexdigest()


def _make_pdf_path(name: str = "test.pdf") -> MagicMock:
    """Return a MagicMock that acts like a pathlib.Path to a PDF file."""
    mock = MagicMock()
    mock.name = name
    mock.stem = name.removesuffix(".pdf")
    mock.__str__ = lambda self: f"/fake/{name}"
    mock.read_bytes.return_value = FAKE_PDF_BYTES
    return mock


def _make_docling_result(
    markdown: str = "# Title\n\nSome text.",
    num_pages: int = 3,
    pictures: list[Any] | None = None,
) -> MagicMock:
    """Return a mock ConversionResult matching Docling v2 API."""
    mock_doc = MagicMock()
    mock_doc.export_to_markdown.return_value = markdown
    mock_doc.pictures = pictures if pictures is not None else []
    mock_doc.pages = [MagicMock() for _ in range(num_pages)]

    mock_result = MagicMock()
    mock_result.document = mock_doc
    return mock_result


def _make_pypdf_reader_mock(num_pages: int) -> MagicMock:
    """Return a mock PdfReader whose .pages list has *num_pages* items."""
    mock_reader = MagicMock()
    mock_reader.pages = [MagicMock() for _ in range(num_pages)]
    return mock_reader


def _make_picture(page_no: int, bbox: MagicMock | None = None) -> MagicMock:
    """Return a mock PictureItem with prov[0].page_no and optional bbox."""
    prov = MagicMock()
    prov.page_no = page_no
    prov.bbox = bbox

    pic = MagicMock()
    pic.prov = [prov]
    return pic


# ---------------------------------------------------------------------------
# Tests: step_parse()
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dry_run_skips_db_check() -> None:
    """dry_run=True must not open a DB session."""
    from scripts.ingest import step_parse

    fake_result = _make_docling_result()
    pdf_path = _make_pdf_path("test.pdf")

    with (
        patch("scripts.ingest.DocumentConverter") as mock_converter_cls,
        patch("scripts.ingest.AsyncSessionLocal") as mock_session_factory,
    ):
        mock_converter_cls.return_value.convert.return_value = fake_result

        result = await step_parse(pdf_path, "PC300-8", rebuild_index=False, dry_run=True)

    mock_session_factory.assert_not_called()
    assert result is not None
    assert result.checksum == FAKE_CHECKSUM


@pytest.mark.asyncio
async def test_skips_if_checksum_exists() -> None:
    """Returns None when checksum already exists in DB (no dry_run, no rebuild)."""
    from scripts.ingest import step_parse

    existing_doc = MagicMock()  # truthy — document found in DB

    mock_session = AsyncMock()
    mock_session.scalar = AsyncMock(return_value=existing_doc)
    mock_cm = AsyncMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_session)
    mock_cm.__aexit__ = AsyncMock(return_value=False)

    pdf_path = _make_pdf_path("test.pdf")

    with patch("scripts.ingest.AsyncSessionLocal", return_value=mock_cm):
        result = await step_parse(pdf_path, "PC300-8", rebuild_index=False, dry_run=False)

    assert result is None


@pytest.mark.asyncio
async def test_proceeds_if_rebuild_index() -> None:
    """rebuild_index=True skips DB check entirely and proceeds with parsing."""
    from scripts.ingest import step_parse

    fake_result = _make_docling_result()
    pdf_path = _make_pdf_path("manual.pdf")

    with (
        patch("scripts.ingest.DocumentConverter") as mock_converter_cls,
        patch("scripts.ingest.AsyncSessionLocal") as mock_session_factory,
    ):
        mock_converter_cls.return_value.convert.return_value = fake_result

        result = await step_parse(pdf_path, "PC300-8", rebuild_index=True, dry_run=False)

    mock_session_factory.assert_not_called()
    assert result is not None


@pytest.mark.asyncio
async def test_returns_parse_result_fields() -> None:
    """ParseResult has all expected fields when parsing succeeds (dry_run mode)."""
    from scripts.ingest import step_parse

    fake_result = _make_docling_result(markdown="# Section\n\nContent.", num_pages=5)
    pdf_path = _make_pdf_path("hydraulics_manual.pdf")
    mock_reader = _make_pypdf_reader_mock(num_pages=5)
    pypdf_mod = sys.modules["pypdf"]

    with (
        patch("scripts.ingest.DocumentConverter") as mock_converter_cls,
        patch.object(pypdf_mod, "PdfReader", return_value=mock_reader),
        patch.object(pypdf_mod, "PdfWriter"),
    ):
        mock_converter_cls.return_value.convert.return_value = fake_result

        result = await step_parse(
            pdf_path, "WB97S-5", rebuild_index=False, dry_run=True
        )

    assert result is not None
    assert result.doc_name == "hydraulics_manual"
    assert result.original_filename == "hydraulics_manual.pdf"
    assert result.checksum == FAKE_CHECKSUM
    assert result.page_count == 5
    assert result.markdown == "# Section\n\nContent."
    assert result.figure_pages == []


@pytest.mark.asyncio
async def test_figure_pages_skips_no_prov() -> None:
    """Pictures with empty prov list are silently skipped in figure_pages."""
    from scripts.ingest import step_parse

    pic_no_prov = MagicMock()
    pic_no_prov.prov = []  # empty — no provenance

    fake_result = _make_docling_result(pictures=[pic_no_prov])
    pdf_path = _make_pdf_path()

    with patch("scripts.ingest.DocumentConverter") as mock_converter_cls:
        mock_converter_cls.return_value.convert.return_value = fake_result

        result = await step_parse(pdf_path, "PC300-8", rebuild_index=False, dry_run=True)

    assert result is not None
    assert result.figure_pages == []


@pytest.mark.asyncio
async def test_figure_pages_no_bbox_gives_none() -> None:
    """Picture with prov but bbox=None produces bbox=None in the figure_pages entry."""
    from scripts.ingest import step_parse

    pic = _make_picture(page_no=2, bbox=None)
    fake_result = _make_docling_result(pictures=[pic])
    pdf_path = _make_pdf_path()
    mock_reader = _make_pypdf_reader_mock(num_pages=3)
    pypdf_mod = sys.modules["pypdf"]

    with (
        patch("scripts.ingest.DocumentConverter") as mock_converter_cls,
        patch.object(pypdf_mod, "PdfReader", return_value=mock_reader),
        patch.object(pypdf_mod, "PdfWriter"),
    ):
        mock_converter_cls.return_value.convert.return_value = fake_result

        result = await step_parse(pdf_path, "PC300-8", rebuild_index=False, dry_run=True)

    assert result is not None
    assert len(result.figure_pages) == 1
    assert result.figure_pages[0] == {"page_number": 2, "bbox": None}


@pytest.mark.asyncio
async def test_figure_pages_with_bbox() -> None:
    """Picture with a valid bbox produces the correct l/t/r/b dict."""
    from scripts.ingest import step_parse

    bbox = MagicMock()
    bbox.l = 10.0
    bbox.t = 20.0
    bbox.r = 200.0
    bbox.b = 300.0

    pic = _make_picture(page_no=4, bbox=bbox)
    fake_result = _make_docling_result(pictures=[pic])
    pdf_path = _make_pdf_path()
    mock_reader = _make_pypdf_reader_mock(num_pages=4)
    pypdf_mod = sys.modules["pypdf"]

    with (
        patch("scripts.ingest.DocumentConverter") as mock_converter_cls,
        patch.object(pypdf_mod, "PdfReader", return_value=mock_reader),
        patch.object(pypdf_mod, "PdfWriter"),
    ):
        mock_converter_cls.return_value.convert.return_value = fake_result

        result = await step_parse(pdf_path, "PC300-8", rebuild_index=False, dry_run=True)

    assert result is not None
    assert result.figure_pages[0] == {
        "page_number": 4,
        "bbox": {"l": 10.0, "t": 20.0, "r": 200.0, "b": 300.0},
    }


# ---------------------------------------------------------------------------
# Tests: _prompt_machine_model()
# ---------------------------------------------------------------------------


def test_prompt_empty_then_valid(monkeypatch: pytest.MonkeyPatch) -> None:
    """Loops on empty/whitespace input; returns first non-empty value."""
    from scripts.ingest import _prompt_machine_model

    inputs = iter(["", "  ", "PC300-8"])
    monkeypatch.setattr("builtins.input", lambda _: next(inputs))

    result = _prompt_machine_model("test.pdf")
    assert result == "PC300-8"


def test_prompt_strips_whitespace(monkeypatch: pytest.MonkeyPatch) -> None:
    """Leading/trailing whitespace is stripped from the returned value."""
    from scripts.ingest import _prompt_machine_model

    monkeypatch.setattr("builtins.input", lambda _: "  WB97S-5  ")

    result = _prompt_machine_model("manual.pdf")
    assert result == "WB97S-5"
