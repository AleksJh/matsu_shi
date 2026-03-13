"""Unit tests for step_visual_ingest() and VisualTag — Task 2.3.

All external dependencies (pypdfium2, boto3, google.genai, PIL) are mocked.
Tests run without a real PDF, R2 bucket, or Gemini API key.

Mocking strategy:
  - conftest.py injects sys.modules stubs at collection time
  - Individual tests use patch() to control return values per-test
  - scripts.ingest is imported lazily inside each test function
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_parse_result(figure_pages=None, doc_name: str = "hydraulics_manual"):
    """Build a ParseResult with controllable figure_pages."""
    from scripts.ingest import ParseResult

    return ParseResult(
        markdown="# Title\n\nText with Рис. 3.",
        page_count=5,
        figure_pages=figure_pages if figure_pages is not None else [],
        checksum="deadbeef" * 8,
        doc_name=doc_name,
        original_filename=f"{doc_name}.pdf",
    )


def _make_pdf_path() -> MagicMock:
    m = MagicMock()
    m.__str__ = lambda self: "/fake/hydraulics_manual.pdf"
    return m


def _mock_settings(public_base_url: str = "https://pub.r2.example.com") -> MagicMock:
    s = MagicMock()
    s.CF_R2_ENDPOINT = "https://r2.example.com"
    s.CF_R2_ACCESS_KEY_ID = "FAKE_KEY_ID"
    s.CF_R2_SECRET_ACCESS_KEY = "FAKE_SECRET"
    s.CF_R2_BUCKET = "matsu-shi"
    s.CF_R2_PUBLIC_BASE_URL = public_base_url
    s.GEMINI_API_KEY = "fake-gemini-key"
    s.LLM_ADVANCED_MODEL = "gemini-3-flash-preview"
    return s


def _make_genai_mock(response_text: str = "Описание схемы") -> MagicMock:
    """Return a mock for the genai module with a configurable generate_content response."""
    mock_response = MagicMock()
    mock_response.text = response_text
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = mock_response
    mock_genai = MagicMock()
    mock_genai.Client.return_value = mock_client
    return mock_genai


# ---------------------------------------------------------------------------
# Test 1: VisualTag dataclass fields
# ---------------------------------------------------------------------------


def test_visual_tag_fields() -> None:
    """VisualTag dataclass exposes page_number, r2_url, description."""
    from scripts.ingest import VisualTag

    tag = VisualTag(
        page_number=3,
        r2_url="https://pub.r2.example.com/PC300-8/manual/page_3.webp",
        description="Гидравлическая схема с насосом и клапанами.",
    )
    assert tag.page_number == 3
    assert tag.r2_url == "https://pub.r2.example.com/PC300-8/manual/page_3.webp"
    assert tag.description == "Гидравлическая схема с насосом и клапанами."


# ---------------------------------------------------------------------------
# Test 2: empty figure_pages → empty list, no IO
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_empty_figure_pages_returns_empty() -> None:
    """No figure pages → returns [] without touching R2, Gemini, or pypdfium2."""
    from scripts.ingest import step_visual_ingest

    parse_result = _make_parse_result(figure_pages=[])
    pdf_path = _make_pdf_path()

    with (
        patch("scripts.ingest.pdfium") as mock_pdfium,
        patch("scripts.ingest.boto3") as mock_boto3,
        patch("scripts.ingest.genai") as mock_genai,
        patch("scripts.ingest.settings", _mock_settings()),
    ):
        result = await step_visual_ingest(pdf_path, parse_result, "PC300-8", dry_run=False)

    assert result == []
    mock_pdfium.PdfDocument.assert_not_called()
    mock_boto3.client.assert_not_called()
    mock_genai.Client.assert_not_called()


# ---------------------------------------------------------------------------
# Test 3: dry_run=True → returns [], skips all IO
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dry_run_returns_empty_and_skips_io() -> None:
    """dry_run=True skips render/upload/Gemini for all figure pages; returns []."""
    from scripts.ingest import step_visual_ingest

    parse_result = _make_parse_result(figure_pages=[{"page_number": 3, "bbox": None}])
    pdf_path = _make_pdf_path()

    with (
        patch("scripts.ingest.pdfium") as mock_pdfium,
        patch("scripts.ingest.boto3") as mock_boto3,
        patch("scripts.ingest.genai") as mock_genai,
        patch("scripts.ingest.settings", _mock_settings()),
    ):
        result = await step_visual_ingest(pdf_path, parse_result, "PC300-8", dry_run=True)

    assert result == []
    mock_pdfium.PdfDocument.assert_not_called()
    mock_boto3.client.assert_not_called()
    mock_genai.Client.assert_not_called()


# ---------------------------------------------------------------------------
# Test 4: happy path — 1 figure page → [VisualTag]
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_happy_path_single_page_returns_visual_tag() -> None:
    """Single figure page: renders, uploads, calls Gemini → returns [VisualTag]."""
    from scripts.ingest import VisualTag, step_visual_ingest

    parse_result = _make_parse_result(figure_pages=[{"page_number": 3, "bbox": None}])
    pdf_path = _make_pdf_path()
    mock_genai = _make_genai_mock("  Описание схемы компонентов  ")

    with (
        patch("scripts.ingest.pdfium"),
        patch("scripts.ingest.boto3"),
        patch("scripts.ingest.genai", mock_genai),
        patch("scripts.ingest.Image"),
        patch("scripts.ingest.settings", _mock_settings()),
    ):
        result = await step_visual_ingest(pdf_path, parse_result, "PC300-8", dry_run=False)

    assert len(result) == 1
    assert isinstance(result[0], VisualTag)
    assert result[0].page_number == 3
    # description is stripped
    assert result[0].description == "Описание схемы компонентов"


# ---------------------------------------------------------------------------
# Test 5: R2 key format
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_r2_key_format() -> None:
    """s3.put_object is called with key '{machine_model}/{doc_name}/page_{n}.webp'."""
    from scripts.ingest import step_visual_ingest

    doc_name = "engine_manual"
    parse_result = _make_parse_result(
        figure_pages=[{"page_number": 7, "bbox": None}], doc_name=doc_name
    )
    pdf_path = _make_pdf_path()

    mock_s3 = MagicMock()
    mock_boto3 = MagicMock()
    mock_boto3.client.return_value = mock_s3

    with (
        patch("scripts.ingest.pdfium"),
        patch("scripts.ingest.boto3", mock_boto3),
        patch("scripts.ingest.genai", _make_genai_mock()),
        patch("scripts.ingest.Image"),
        patch("scripts.ingest.settings", _mock_settings()),
    ):
        await step_visual_ingest(pdf_path, parse_result, "WB97S-5", dry_run=False)

    mock_s3.put_object.assert_called_once()
    call_kwargs = mock_s3.put_object.call_args.kwargs
    assert call_kwargs["Key"] == "WB97S-5/engine_manual/page_7.webp"
    assert call_kwargs["ContentType"] == "image/webp"


# ---------------------------------------------------------------------------
# Test 6: R2 URL in VisualTag
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_r2_url_in_visual_tag() -> None:
    """VisualTag.r2_url == CF_R2_PUBLIC_BASE_URL + '/' + key."""
    from scripts.ingest import step_visual_ingest

    public_base = "https://pub.r2.example.com"
    parse_result = _make_parse_result(
        figure_pages=[{"page_number": 2, "bbox": None}], doc_name="hyd"
    )
    pdf_path = _make_pdf_path()

    with (
        patch("scripts.ingest.pdfium"),
        patch("scripts.ingest.boto3"),
        patch("scripts.ingest.genai", _make_genai_mock()),
        patch("scripts.ingest.Image"),
        patch("scripts.ingest.settings", _mock_settings(public_base_url=public_base)),
    ):
        result = await step_visual_ingest(pdf_path, parse_result, "PC300-8", dry_run=False)

    expected_url = f"{public_base}/PC300-8/hyd/page_2.webp"
    assert result[0].r2_url == expected_url


# ---------------------------------------------------------------------------
# Test 7: Gemini prompt contains Russian text
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_gemini_prompt_contains_russian_text() -> None:
    """generate_content is called with the Russian prompt as the first content item."""
    from scripts.ingest import step_visual_ingest

    parse_result = _make_parse_result(figure_pages=[{"page_number": 1, "bbox": None}])
    pdf_path = _make_pdf_path()
    mock_genai = _make_genai_mock()
    mock_client = mock_genai.Client.return_value

    with (
        patch("scripts.ingest.pdfium"),
        patch("scripts.ingest.boto3"),
        patch("scripts.ingest.genai", mock_genai),
        patch("scripts.ingest.Image"),
        patch("scripts.ingest.settings", _mock_settings()),
    ):
        await step_visual_ingest(pdf_path, parse_result, "PC300-8", dry_run=False)

    mock_client.models.generate_content.assert_called_once()
    call_kwargs = mock_client.models.generate_content.call_args.kwargs
    contents = call_kwargs["contents"]
    prompt_str = next(item for item in contents if isinstance(item, str))
    assert "Опиши техническую схему" in prompt_str
    assert "русском" in prompt_str


# ---------------------------------------------------------------------------
# Test 8: Gemini description is stripped
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_gemini_description_is_stripped() -> None:
    """VisualTag.description == response.text.strip() (no surrounding whitespace)."""
    from scripts.ingest import step_visual_ingest

    parse_result = _make_parse_result(figure_pages=[{"page_number": 1, "bbox": None}])
    pdf_path = _make_pdf_path()
    mock_genai = _make_genai_mock("\n  Насос гидравлический с клапаном.  \n")

    with (
        patch("scripts.ingest.pdfium"),
        patch("scripts.ingest.boto3"),
        patch("scripts.ingest.genai", mock_genai),
        patch("scripts.ingest.Image"),
        patch("scripts.ingest.settings", _mock_settings()),
    ):
        result = await step_visual_ingest(pdf_path, parse_result, "PC300-8", dry_run=False)

    assert result[0].description == "Насос гидравлический с клапаном."


# ---------------------------------------------------------------------------
# Test 9: per-page exception continues the loop
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_per_page_exception_continues() -> None:
    """If put_object fails for page 2, page 5 is still processed; result has 1 VisualTag."""
    from scripts.ingest import VisualTag, step_visual_ingest

    parse_result = _make_parse_result(
        figure_pages=[
            {"page_number": 2, "bbox": None},  # will fail on put_object
            {"page_number": 5, "bbox": None},  # succeeds
        ]
    )
    pdf_path = _make_pdf_path()

    put_object_call_count = 0

    def put_object_side_effect(**kwargs):
        nonlocal put_object_call_count
        put_object_call_count += 1
        if put_object_call_count == 1:
            raise RuntimeError("R2 upload error: connection refused")
        # second call succeeds (returns None, like a real put_object)

    mock_s3 = MagicMock()
    mock_s3.put_object.side_effect = put_object_side_effect
    mock_boto3 = MagicMock()
    mock_boto3.client.return_value = mock_s3

    with (
        patch("scripts.ingest.pdfium"),
        patch("scripts.ingest.boto3", mock_boto3),
        patch("scripts.ingest.genai", _make_genai_mock("Успешное описание")),
        patch("scripts.ingest.Image"),
        patch("scripts.ingest.settings", _mock_settings()),
    ):
        result = await step_visual_ingest(pdf_path, parse_result, "PC300-8", dry_run=False)

    # Only page 5 succeeded; page 2 failed and was skipped
    assert len(result) == 1
    assert isinstance(result[0], VisualTag)
    assert result[0].page_number == 5
    assert result[0].description == "Успешное описание"
