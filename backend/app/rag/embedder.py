"""RAG Embedding Module.

Public API:
    embed_text(text: str) -> list[float] | None

Calls OpenRouter /embeddings endpoint.  Returns the float vector on success,
or None on any error (HTTP 4xx/5xx, timeout, malformed JSON).  Dimension
validation is the caller's responsibility.
"""

from __future__ import annotations

import httpx
from loguru import logger

from app.core.config import settings

_BASE_URL = "https://openrouter.ai/api/v1"


async def embed_text(text: str) -> list[float] | None:
    """Embed *text* via OpenRouter and return the float vector.

    Returns None (and logs a WARNING) on any error so that callers can
    continue processing the remaining items without crashing.
    """
    try:
        async with httpx.AsyncClient(base_url=_BASE_URL) as client:
            response = await client.post(
                "/embeddings",
                headers={
                    "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
                    "HTTP-Referer": "matsu-shi",
                },
                json={"model": settings.EMBED_MODEL, "input": text, "dimensions": settings.EMBED_DIM},
            )
            response.raise_for_status()
            data: list[float] = response.json()["data"][0]["embedding"]
            return data
    except httpx.HTTPStatusError as exc:
        logger.warning(
            f"embed_text: HTTP {exc.response.status_code} от OpenRouter: {exc}"
        )
        return None
    except httpx.TimeoutException as exc:
        logger.warning(f"embed_text: timeout при обращении к OpenRouter: {exc}")
        return None
    except (KeyError, IndexError, ValueError) as exc:
        logger.warning(f"embed_text: неожиданный формат ответа OpenRouter: {exc}")
        return None
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"embed_text: ошибка: {exc}")
        return None
