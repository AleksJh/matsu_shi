"""Fixtures and module-level mocks for web-application unit tests.

Only the minimal set of stubs required by app.* modules is set up here.
Ingest-pipeline dependencies (docling, pypdfium2, boto3, PIL) live in
tests/scripts/conftest.py and must not bleed into this test suite.
"""
from __future__ import annotations

import os

# --- GOOGLE_API_KEY ---
# Pydantic AI's Google provider reads GOOGLE_API_KEY from os.environ at Agent()
# construction time, which happens at module import.  Our .env uses GEMINI_API_KEY;
# bridge the two so pydantic-ai can initialise without a real network call.
if "GOOGLE_API_KEY" not in os.environ:
    os.environ["GOOGLE_API_KEY"] = os.environ.get("GEMINI_API_KEY", "test-placeholder")

# --- google.genai (Gemini SDK v1.x) ---
# Pre-import the real package so pydantic-ai can load its Google provider.
try:
    import google.genai as _real_google_genai  # noqa: F401
except Exception:
    import sys
    from unittest.mock import MagicMock
    _google_mock = MagicMock()
    sys.modules.setdefault("google", _google_mock)
    sys.modules.setdefault("google.genai", MagicMock())
