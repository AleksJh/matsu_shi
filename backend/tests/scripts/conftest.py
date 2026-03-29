"""Fixtures and module-level mocks for ingest-pipeline tests.

Heavy optional dependencies (docling, pypdfium2, boto3, PIL) are stubbed at
the sys.modules level so that `scripts.ingest` can be imported in CI without
those packages being installed.  This must happen at collection time
(conftest, not inside test functions).

All ingest test files use the simple pattern:
    from scripts.ingest import step_parse, ChunkData, ...
"""
from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock

# --- GOOGLE_API_KEY ---
# Pydantic AI's Google provider reads GOOGLE_API_KEY from os.environ at Agent()
# construction time.  Our .env uses GEMINI_API_KEY; bridge the two.
if "GOOGLE_API_KEY" not in os.environ:
    os.environ["GOOGLE_API_KEY"] = os.environ.get("GEMINI_API_KEY", "test-placeholder")

# --- docling (+ all submodules imported by scripts/ingest.py) ---
_docling_mock = MagicMock()
sys.modules.setdefault("docling", _docling_mock)
sys.modules.setdefault("docling.datamodel", _docling_mock)
sys.modules.setdefault("docling.datamodel.base_models", _docling_mock)
sys.modules.setdefault("docling.datamodel.pipeline_options", _docling_mock)
sys.modules.setdefault("docling.document_converter", _docling_mock)

# --- pypdfium2 (PDF renderer bundled with docling, often absent in CI) ---
sys.modules.setdefault("pypdfium2", MagicMock())

# --- pypdf (installed, but tests use fake PDF paths — override to avoid FileNotFoundError) ---
# scripts/ingest.py calls PdfReader(str(pdf_path)); all step_parse tests pass mock paths,
# so we stub the whole module here rather than patching per-test.
sys.modules["pypdf"] = MagicMock()

# --- boto3 (S3/R2 client) ---
sys.modules.setdefault("boto3", MagicMock())

# --- google.genai (Gemini SDK v1.x) ---
# Try to import the real package first (needed for pydantic-ai Google provider).
# Fall back to a mock if not installed.
try:
    import google.genai as _real_google_genai  # noqa: F401
except Exception:
    _google_mock = MagicMock()
    sys.modules.setdefault("google", _google_mock)
    sys.modules.setdefault("google.genai", MagicMock())

# --- PIL / Pillow ---
_pil_mock = MagicMock()
sys.modules.setdefault("PIL", _pil_mock)
sys.modules.setdefault("PIL.Image", MagicMock())
