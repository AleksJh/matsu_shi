"""TDD unit tests for embed_text() in app/rag/embedder.py — Task 3.1.

Strategy:
  - Load embedder module via importlib.util with app.core.config stubbed.
  - Patch httpx.AsyncClient on the loaded module to avoid real HTTP calls.
  - Cover: success, HTTP 4xx, HTTP 5xx, timeout, malformed JSON.
"""

from __future__ import annotations

import asyncio
import importlib.util
import json
import pathlib
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest


# ---------------------------------------------------------------------------
# Helpers — load embedder.py without triggering real settings
# ---------------------------------------------------------------------------

def _load_embedder():
    """Load app.rag.embedder with app.core.config stubbed."""
    config_stub = MagicMock()
    config_stub.settings = MagicMock(
        OPENROUTER_API_KEY="test-key",
        EMBED_MODEL="test-model",
    )

    stubs = {}
    if "app.core.config" not in sys.modules:
        stubs["app.core.config"] = config_stub

    with patch.dict(sys.modules, stubs):
        spec = importlib.util.spec_from_file_location(
            "app.rag.embedder",
            pathlib.Path(__file__).resolve().parents[2]
            / "app" / "rag" / "embedder.py",
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

    return mod


_embedder = _load_embedder()


# ---------------------------------------------------------------------------
# Helper — build a mock httpx response
# ---------------------------------------------------------------------------

def _mock_response(status_code: int, payload: dict | None = None) -> MagicMock:
    """Return a MagicMock that mimics an httpx.Response."""
    resp = MagicMock()
    resp.status_code = status_code
    if payload is not None:
        resp.json = MagicMock(return_value=payload)
    if status_code >= 400:
        resp.raise_for_status = MagicMock(
            side_effect=httpx.HTTPStatusError(
                f"HTTP {status_code}",
                request=MagicMock(),
                response=resp,
            )
        )
    else:
        resp.raise_for_status = MagicMock()
    return resp


def _patch_client(post_return=None, post_side_effect=None):
    """Return a context manager that patches httpx.AsyncClient on the module."""
    mock_instance = AsyncMock()
    if post_side_effect is not None:
        mock_instance.post = AsyncMock(side_effect=post_side_effect)
    else:
        mock_instance.post = AsyncMock(return_value=post_return)

    mock_cls = MagicMock()
    mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_instance)
    mock_cls.return_value.__aexit__ = AsyncMock(return_value=None)

    return patch.object(_embedder, "httpx", MagicMock(
        AsyncClient=mock_cls,
        HTTPStatusError=httpx.HTTPStatusError,
        TimeoutException=httpx.TimeoutException,
    ))


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_embed_text_success():
    """Happy path: valid API response returns a list[float]."""
    vector = [0.1, 0.2, 0.3]
    resp = _mock_response(200, {"data": [{"embedding": vector}]})

    with _patch_client(post_return=resp):
        result = asyncio.run(_embedder.embed_text("hello world"))

    assert result == vector
    assert isinstance(result, list)
    assert all(isinstance(v, float) for v in result)


def test_embed_text_http_4xx_returns_none():
    """HTTP 4xx from OpenRouter must return None without raising."""
    resp = _mock_response(401)

    with _patch_client(post_return=resp):
        result = asyncio.run(_embedder.embed_text("some query"))

    assert result is None


def test_embed_text_http_5xx_returns_none():
    """HTTP 5xx from OpenRouter must return None without raising."""
    resp = _mock_response(503)

    with _patch_client(post_return=resp):
        result = asyncio.run(_embedder.embed_text("some query"))

    assert result is None


def test_embed_text_timeout_returns_none():
    """Network timeout must return None without raising."""
    with _patch_client(post_side_effect=httpx.TimeoutException("timed out")):
        result = asyncio.run(_embedder.embed_text("some query"))

    assert result is None


def test_embed_text_invalid_json_returns_none():
    """Malformed JSON response (missing 'data' key) must return None."""
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    # Response body lacks expected structure
    resp.json = MagicMock(side_effect=json.JSONDecodeError("bad", "", 0))

    with _patch_client(post_return=resp):
        result = asyncio.run(_embedder.embed_text("some query"))

    assert result is None
