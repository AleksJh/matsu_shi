"""TDD unit tests for step_embed() — PRD §4.1 Step 5, §5.1.

Coverage:
  1. embed_text called once per chunk (sequential)
  2. ChunkData.vector populated with list[float]
  3. Dimension mismatch → sys.exit(1)
  4. embed_text returns None on one chunk → non-fatal, vector=None, rest continue
  5. dry_run=True → embed_text never called, vectors stay None
"""

from __future__ import annotations

import asyncio
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers — import target symbols without triggering heavy deps
# ---------------------------------------------------------------------------


def _import_ingest():
    """Import step_embed, ChunkData without loading heavy optional deps."""
    import importlib.util
    import pathlib

    heavy_mods = [
        "docling",
        "docling.document_converter",
        "boto3",
        "pypdfium2",
        "google",
        "google.genai",
        "PIL",
        "PIL.Image",
    ]
    stubs: dict = {}
    for mod in heavy_mods:
        if mod not in sys.modules:
            stubs[mod] = MagicMock()

    with patch.dict(sys.modules, stubs):
        app_stubs = {
            "app.core.config": MagicMock(
                settings=MagicMock(
                    EMBED_DIM=1024,
                    EMBED_MODEL="qwen/qwen3-embedding-4b",
                    OPENROUTER_API_KEY="test-key",
                    CF_R2_ENDPOINT="http://localhost",
                    CF_R2_ACCESS_KEY_ID="x",
                    CF_R2_SECRET_ACCESS_KEY="x",
                    CF_R2_BUCKET="b",
                    CF_R2_PUBLIC_BASE_URL="http://r2",
                    GEMINI_API_KEY="test-key",
                    LLM_ADVANCED_MODEL="gemini-test",
                )
            ),
            "app.core.database": MagicMock(),
            "app.models.document": MagicMock(),
            "dotenv": MagicMock(),
        }
        with patch.dict(sys.modules, app_stubs):
            for key in list(sys.modules):
                if key.endswith("ingest") and "scripts" in key:
                    del sys.modules[key]
                    break

            spec = importlib.util.spec_from_file_location(
                "ingest",
                pathlib.Path(__file__).resolve().parents[2] / "scripts" / "ingest.py",
            )
            mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
            sys.modules["ingest"] = mod
            spec.loader.exec_module(mod)  # type: ignore[union-attr]
            return mod


@pytest.fixture(scope="module")
def ingest_mod():
    return _import_ingest()


@pytest.fixture(scope="module")
def step_embed(ingest_mod):
    return ingest_mod.step_embed


@pytest.fixture(scope="module")
def ChunkData(ingest_mod):
    return ingest_mod.ChunkData


# ---------------------------------------------------------------------------
# Factory helpers
# ---------------------------------------------------------------------------


def make_text_chunk(ChunkData, index=0, content="Описание гидравлического насоса."):
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
        category="hydraulics",
        vector=None,
    )


def run(coro):
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# Test 1 — embed_text called once per chunk
# ---------------------------------------------------------------------------


class TestEmbedCallsAPIPerChunk:
    def test_embed_calls_api_for_each_chunk(self, step_embed, ChunkData, ingest_mod):
        """embed_text must be called exactly once per chunk."""
        chunks = [
            make_text_chunk(ChunkData, index=0, content="Первый фрагмент."),
            make_text_chunk(ChunkData, index=1, content="Второй фрагмент."),
            make_text_chunk(ChunkData, index=2, content="Третий фрагмент."),
        ]
        mock_embed = AsyncMock(return_value=[0.1] * 1024)

        with patch.object(ingest_mod, "embed_text", mock_embed):
            result = run(step_embed(chunks, dry_run=False))

        assert mock_embed.call_count == 3, (
            f"Expected 3 embed_text calls, got {mock_embed.call_count}"
        )
        assert len(result) == 3


# ---------------------------------------------------------------------------
# Test 2 — vector field populated
# ---------------------------------------------------------------------------


class TestEmbedSetsVectorField:
    def test_embed_sets_vector_as_list_of_floats(self, step_embed, ChunkData, ingest_mod):
        """Each ChunkData.vector must be a non-empty list[float] after embedding."""
        chunk = make_text_chunk(ChunkData)
        mock_embed = AsyncMock(return_value=[0.1] * 1024)

        with patch.object(ingest_mod, "embed_text", mock_embed):
            result = run(step_embed([chunk], dry_run=False))

        assert len(result) == 1
        vec = result[0].vector
        assert isinstance(vec, list), f"Expected list, got {type(vec)}"
        assert len(vec) == 1024, f"Expected 1024 floats, got {len(vec)}"
        assert all(isinstance(v, float) for v in vec), "All elements must be float"

    def test_embed_passes_chunk_content_to_api(self, step_embed, ChunkData, ingest_mod):
        """The chunk content string must be passed to embed_text."""
        content = "Технический раздел: замена масляного фильтра."
        chunk = make_text_chunk(ChunkData, content=content)
        mock_embed = AsyncMock(return_value=[0.1] * 1024)

        with patch.object(ingest_mod, "embed_text", mock_embed):
            run(step_embed([chunk], dry_run=False))

        mock_embed.assert_called_once_with(content)


# ---------------------------------------------------------------------------
# Test 3 — dimension mismatch → sys.exit
# ---------------------------------------------------------------------------


class TestEmbedDimensionValidation:
    def test_embed_exits_on_dimension_mismatch(self, step_embed, ChunkData, ingest_mod):
        """If returned vector dim != EMBED_DIM, step_embed must call sys.exit(1)."""
        chunk = make_text_chunk(ChunkData)
        # Return dim=512 but EMBED_DIM=1024
        mock_embed = AsyncMock(return_value=[0.1] * 512)

        with patch.object(ingest_mod, "embed_text", mock_embed):
            with pytest.raises(SystemExit) as exc_info:
                run(step_embed([chunk], dry_run=False))

        assert exc_info.value.code == 1, (
            f"Expected sys.exit(1), got code={exc_info.value.code}"
        )

    def test_embed_does_not_exit_on_correct_dimension(self, step_embed, ChunkData, ingest_mod):
        """No SystemExit when vector dim matches EMBED_DIM (1024)."""
        chunk = make_text_chunk(ChunkData)
        mock_embed = AsyncMock(return_value=[0.1] * 1024)

        with patch.object(ingest_mod, "embed_text", mock_embed):
            result = run(step_embed([chunk], dry_run=False))

        assert len(result) == 1
        assert result[0].vector is not None


# ---------------------------------------------------------------------------
# Test 4 — embed_text returns None on one chunk: non-fatal, vector=None, rest continue
# ---------------------------------------------------------------------------


class TestEmbedNonFatalAPIError:
    def test_embed_api_error_sets_vector_none_and_continues(
        self, step_embed, ChunkData, ingest_mod
    ):
        """embed_text returning None on chunk 0 → vector stays None; chunk 1 still gets a vector."""
        chunk0 = make_text_chunk(ChunkData, index=0, content="Первый фрагмент.")
        chunk1 = make_text_chunk(ChunkData, index=1, content="Второй фрагмент.")

        # First call returns None (error), second returns valid vector
        mock_embed = AsyncMock(side_effect=[None, [0.1] * 1024])

        with patch.object(ingest_mod, "embed_text", mock_embed):
            result = run(step_embed([chunk0, chunk1], dry_run=False))

        assert len(result) == 2
        assert result[0].vector is None, (
            f"chunk0 should have vector=None after error, got: {result[0].vector}"
        )
        assert result[1].vector is not None, "chunk1 should have a vector after success"
        assert len(result[1].vector) == 1024


# ---------------------------------------------------------------------------
# Test 5 — dry_run=True → embed_text never called, vectors stay None
# ---------------------------------------------------------------------------


class TestEmbedDryRun:
    def test_embed_dry_run_skips_api(self, step_embed, ChunkData, ingest_mod):
        """dry_run=True must not call embed_text at all."""
        chunks = [
            make_text_chunk(ChunkData, index=0),
            make_text_chunk(ChunkData, index=1),
        ]
        mock_embed = AsyncMock()

        with patch.object(ingest_mod, "embed_text", mock_embed):
            result = run(step_embed(chunks, dry_run=True))
            mock_embed.assert_not_called()

        assert len(result) == 2
        for chunk in result:
            assert chunk.vector is None, (
                f"dry_run chunks must have vector=None, got: {chunk.vector}"
            )

    def test_embed_dry_run_preserves_chunk_content(self, step_embed, ChunkData, ingest_mod):
        """dry_run must not mutate chunk content."""
        original_content = "Неизменённый текст."
        chunk = make_text_chunk(ChunkData, content=original_content)
        mock_embed = AsyncMock()

        with patch.object(ingest_mod, "embed_text", mock_embed):
            result = run(step_embed([chunk], dry_run=True))

        assert result[0].content == original_content
