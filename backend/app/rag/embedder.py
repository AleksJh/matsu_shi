"""RAG Embedding Module.

Public API:
    embed_text(text: str) -> list[float] | None

Calls OpenRouter /embeddings endpoint.  Returns the float vector on success,
or None on any error (HTTP 4xx/5xx, timeout, malformed JSON).  Dimension
validation is the caller's responsibility.
"""

from __future__ import annotations

import asyncio

import httpx
from loguru import logger

from app.core.config import settings

_BASE_URL = "https://openrouter.ai/api/v1"


async def embed_text(text: str) -> list[float] | None:
    """Embed *text* via OpenRouter and return the float vector.

    Retries up to 20 times on HTTP 503 (2 s flat wait, Roadmap 9.6).
    All other HTTP errors, timeouts, and parse errors return None immediately
    so that callers can continue processing remaining items without crashing.
    """
    for _attempt in range(20):
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
                body = response.json()
                if "data" not in body:
                    # OpenRouter sometimes returns {"error": {...}} with HTTP 200
                    if _attempt < 19:
                        logger.warning(
                            "embed_text: no 'data' in response (attempt {}/20), body: {}, retrying in 2s ...",
                            _attempt + 1,
                            str(body)[:300],
                        )
                        await asyncio.sleep(2)
                        continue
                    logger.warning(
                        "embed_text: no 'data' after 20 attempts, last body: {}",
                        str(body)[:300],
                    )
                    return None
                data: list[float] = body["data"][0]["embedding"]
                return data
        except httpx.HTTPStatusError as exc:
            if _attempt < 19 and exc.response.status_code in (503, 429):
                logger.warning(
                    "embed_text: OpenRouter HTTP {}, attempt {}/20, waiting 2s ...",
                    exc.response.status_code,
                    _attempt + 1,
                )
                await asyncio.sleep(2)
                continue
            logger.warning(
                "embed_text: HTTP {} от OpenRouter: {}",
                exc.response.status_code,
                exc,
            )
            return None
        except httpx.TimeoutException as exc:
            logger.warning("embed_text: timeout при обращении к OpenRouter: {}", exc)
            return None
        except (KeyError, IndexError, ValueError) as exc:
            logger.warning(
                "embed_text: неожиданный формат ответа OpenRouter: {}, body snippet logged above",
                exc,
            )
            return None
        except Exception as exc:  # noqa: BLE001
            logger.warning("embed_text: ошибка: {}", exc)
            return None
    # Reached only when all 20 attempts returned 503.
    logger.warning("embed_text: исчерпаны 20 попыток на 503, возвращаю None")
    return None
