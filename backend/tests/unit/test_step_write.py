"""TDD unit tests for step_write() — Task 2.7 (Phase 2, Step 6: Remote Write).

Tests are written BEFORE the implementation (TDD order).
All tests must pass after step_write() is fully implemented in ingest.py.

Strategy:
  - Load ingest.py via importlib.util with all heavy external deps stubbed
  - Pass a real AsyncMock session; patch ingest_mod.pg_insert and ingest_mod.delete
  - Verify ORM interactions without hitting a real database
"""

from __future__ import annotations

import asyncio
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers — load ingest.py without heavy deps
# ---------------------------------------------------------------------------


def _load_ingest():
    """Import ingest module with all heavy / DB deps stubbed out."""
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
    stubs = {mod: MagicMock() for mod in heavy_mods if mod not in sys.modules}

    app_stubs = {
        "app.core.config": MagicMock(
            settings=MagicMock(
                EMBED_DIM=1024,
                EMBED_MODEL="test",
                CF_R2_ENDPOINT="http://localhost",
                CF_R2_ACCESS_KEY_ID="x",
                CF_R2_SECRET_ACCESS_KEY="x",
                CF_R2_BUCKET="b",
                CF_R2_PUBLIC_BASE_URL="http://r2",
                GEMINI_API_KEY="x",
                LLM_ADVANCED_MODEL="gemini",
                DATABASE_URL="postgresql+asyncpg://u:p@localhost/db",
            )
        ),
        "app.core.database": MagicMock(),
        "app.models.document": MagicMock(),
        "app.models.chunk": MagicMock(),
        "dotenv": MagicMock(),
    }

    all_stubs = {**stubs, **app_stubs}

    with patch.dict(sys.modules, all_stubs):
        # Remove any previously cached ingest module
        for key in list(sys.modules):
            if "ingest" in key and "scripts" in key:
                del sys.modules[key]
        sys.modules.pop("ingest", None)

        spec = importlib.util.spec_from_file_location(
            "ingest",
            pathlib.Path(__file__).resolve().parents[2] / "scripts" / "ingest.py",
        )
        mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
        sys.modules["ingest"] = mod
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        return mod


def run(coro):
    return asyncio.run(coro)


@pytest.fixture(scope="module")
def ingest_mod():
    return _load_ingest()


@pytest.fixture(scope="module")
def ChunkData(ingest_mod):
    return ingest_mod.ChunkData


@pytest.fixture(scope="module")
def ParseResult(ingest_mod):
    return ingest_mod.ParseResult


@pytest.fixture(scope="module")
def step_write(ingest_mod):
    return ingest_mod.step_write


# ---------------------------------------------------------------------------
# Factory helpers
# ---------------------------------------------------------------------------


def _make_chunk(ChunkData, idx: int = 0, *, null_vector: bool = False):
    return ChunkData(
        chunk_index=idx,
        content=f"Content for chunk {idx}.",
        chunk_type="text",
        section_title="Section A",
        page_number=1,
        visual_refs=[],
        token_count=100,
        doc_name="PC300-8_Shop_Manual",
        machine_model="PC300-8",
        category="hydraulics",
        vector=None if null_vector else [0.1] * 10,
    )


def _make_parse_result(ParseResult):
    return ParseResult(
        markdown="# Test Section\n\nContent.",
        page_count=10,
        figure_pages=[],
        checksum="a" * 64,  # 64-char hex string (SHA-256)
        doc_name="PC300-8_Shop_Manual",
        original_filename="PC300-8_Shop_Manual.pdf",
    )


def _make_session():
    session = AsyncMock()
    # session.execute(...) returns an awaitable whose result has .scalar_one()
    session.execute.return_value.scalar_one.return_value = 7  # simulated doc_id
    return session


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestStepWrite:
    def test_write_adds_document_with_correct_fields(
        self, ingest_mod, ChunkData, ParseResult, step_write
    ):
        """pg_insert is invoked with the exact field values from ParseResult and CLI args."""
        chunks = [_make_chunk(ChunkData, 0), _make_chunk(ChunkData, 1)]
        parse_result = _make_parse_result(ParseResult)
        session = _make_session()

        mock_pg_insert = MagicMock()
        mock_delete = MagicMock()

        with patch.object(ingest_mod, "pg_insert", mock_pg_insert), patch.object(
            ingest_mod, "delete", mock_delete
        ):
            run(
                step_write(
                    chunks, parse_result, "PC300-8", "hydraulics", False, session
                )
            )

        # pg_insert was called (with Document class as arg)
        mock_pg_insert.assert_called_once()

        # .values() received the correct kwargs
        values_call = mock_pg_insert.return_value.values
        values_call.assert_called_once()
        kwargs = values_call.call_args.kwargs

        assert kwargs["original_filename"] == "PC300-8_Shop_Manual.pdf"
        assert kwargs["display_name"] == "PC300-8_Shop_Manual"
        assert kwargs["machine_model"] == "PC300-8"
        assert kwargs["category"] == "hydraulics"
        assert kwargs["page_count"] == 10
        assert kwargs["chunk_count"] == 2
        assert kwargs["status"] == "indexed"
        assert kwargs["checksum"] == "a" * 64

    def test_write_inserts_all_chunks(
        self, ingest_mod, ChunkData, ParseResult, step_write
    ):
        """session.add_all is called with a list of exactly N Chunk objects."""
        chunks = [_make_chunk(ChunkData, i) for i in range(5)]
        parse_result = _make_parse_result(ParseResult)
        session = _make_session()

        mock_pg_insert = MagicMock()
        mock_delete = MagicMock()

        with patch.object(ingest_mod, "pg_insert", mock_pg_insert), patch.object(
            ingest_mod, "delete", mock_delete
        ):
            run(step_write(chunks, parse_result, "PC300-8", None, False, session))

        session.add_all.assert_called_once()
        added = session.add_all.call_args.args[0]
        assert len(added) == 5

        # session.commit was awaited to persist the batch
        session.commit.assert_awaited_once()

    def test_write_rebuild_index_deletes_existing_chunks(
        self, ingest_mod, ChunkData, ParseResult, step_write
    ):
        """When rebuild_index=True, DELETE chunks by document_id is executed before insert."""
        chunks = [_make_chunk(ChunkData, 0)]
        parse_result = _make_parse_result(ParseResult)
        session = _make_session()

        mock_pg_insert = MagicMock()
        mock_delete = MagicMock()

        with patch.object(ingest_mod, "pg_insert", mock_pg_insert), patch.object(
            ingest_mod, "delete", mock_delete
        ):
            run(step_write(chunks, parse_result, "PC300-8", None, True, session))

        # delete() was called (for the rebuild)
        mock_delete.assert_called_once()

        # session.execute was awaited twice: once for upsert, once for DELETE
        assert session.execute.await_count == 2

    def test_write_no_delete_without_rebuild_index(
        self, ingest_mod, ChunkData, ParseResult, step_write
    ):
        """When rebuild_index=False, DELETE is NOT executed and session.execute fires once."""
        chunks = [_make_chunk(ChunkData, 0)]
        parse_result = _make_parse_result(ParseResult)
        session = _make_session()

        mock_pg_insert = MagicMock()
        mock_delete = MagicMock()

        with patch.object(ingest_mod, "pg_insert", mock_pg_insert), patch.object(
            ingest_mod, "delete", mock_delete
        ):
            run(step_write(chunks, parse_result, "PC300-8", None, False, session))

        mock_delete.assert_not_called()
        session.execute.assert_awaited_once()

    def test_write_chunk_with_none_vector_inserts_without_error(
        self, ingest_mod, ChunkData, ParseResult, step_write
    ):
        """A chunk whose vector=None is written with embedding=None — no exception raised."""
        chunk_no_vec = _make_chunk(ChunkData, 0, null_vector=True)
        assert chunk_no_vec.vector is None

        parse_result = _make_parse_result(ParseResult)
        session = _make_session()

        mock_pg_insert = MagicMock()
        mock_delete = MagicMock()

        with patch.object(ingest_mod, "pg_insert", mock_pg_insert), patch.object(
            ingest_mod, "delete", mock_delete
        ):
            # Must complete without raising
            run(
                step_write(
                    [chunk_no_vec], parse_result, "PC300-8", None, False, session
                )
            )

        session.add_all.assert_called_once()
        added = session.add_all.call_args.args[0]
        assert len(added) == 1
        session.commit.assert_awaited_once()
