"""Unit-test fixtures and module-level mocks.

Heavy/optional dependencies are mocked at the sys.modules level so that
`scripts.ingest` can be imported without them being installed.
This must happen at collection time (conftest, not inside test functions).
"""
from __future__ import annotations

import sys
from unittest.mock import MagicMock

# --- docling ---
_docling_mock = MagicMock()
sys.modules.setdefault("docling", _docling_mock)
sys.modules.setdefault("docling.document_converter", _docling_mock)

# --- pypdfium2 (PDF renderer, ships with docling but may be absent in CI) ---
sys.modules.setdefault("pypdfium2", MagicMock())

# --- boto3 (S3/R2 client) ---
sys.modules.setdefault("boto3", MagicMock())

# --- google.genai (Gemini SDK v1.x) ---
# Pre-import the real package so pydantic-ai can load its Google provider.
# After this, setdefault() is a no-op for these keys; ingest tests still
# use patch() per-test to stub individual google.genai calls.
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
