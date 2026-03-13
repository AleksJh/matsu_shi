"""TDD unit tests for core/security.py — Phase 5.

Tests:
  1. validate_telegram_init_data — valid initData → WebAppInitData returned
  2. validate_telegram_init_data — invalid initData → HTTPException(403)
  3. create_access_token — payload contains sub, role, exp
  4. decode_access_token — valid token round-trip
  5. decode_access_token — expired token → HTTPException(401)
  6. check_rate_limit — 15 requests pass without exception
  7. check_rate_limit — 16th request → HTTPException(429) with Russian message
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from jose import jwt

from app.core.config import settings


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_redis_mock(count: int) -> AsyncMock:
    """Return an async Redis mock whose incr() returns `count`."""
    redis = AsyncMock()
    redis.incr = AsyncMock(return_value=count)
    redis.expire = AsyncMock()
    return redis


# ---------------------------------------------------------------------------
# Telegram initData validation
# ---------------------------------------------------------------------------


class TestValidateTelegramInitData:
    def test_valid_initdata_returns_webapp_data(self):
        """valid initData → WebAppInitData object returned (no exception)."""
        from aiogram.utils.web_app import WebAppInitData, WebAppUser

        fake_user = WebAppUser(
            id=123456789,
            is_bot=False,
            first_name="Иван",
            username="ivan_mech",
        )
        fake_data = MagicMock(spec=WebAppInitData)
        fake_data.user = fake_user

        with patch(
            "app.core.security.safe_parse_webapp_init_data",
            return_value=fake_data,
        ):
            from app.core.security import validate_telegram_init_data

            result = validate_telegram_init_data("query_id=1&user=...")
            assert result is fake_data
            assert result.user.id == 123456789

    def test_invalid_initdata_raises_403(self):
        """Tampered / invalid initData → HTTPException with status_code=403."""
        with patch(
            "app.core.security.safe_parse_webapp_init_data",
            side_effect=ValueError("hash mismatch"),
        ):
            from app.core.security import validate_telegram_init_data

            with pytest.raises(HTTPException) as exc_info:
                validate_telegram_init_data("tampered_data")

            assert exc_info.value.status_code == 403


# ---------------------------------------------------------------------------
# JWT
# ---------------------------------------------------------------------------


class TestJWT:
    def test_create_access_token_payload(self):
        """Token payload contains sub (str), role, and exp fields."""
        from app.core.security import create_access_token

        token = create_access_token(user_id=42, role="mechanic")
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )

        assert payload["sub"] == "42"
        assert payload["role"] == "mechanic"
        assert "exp" in payload

    def test_decode_access_token_valid_round_trip(self):
        """create → decode returns original sub and role."""
        from app.core.security import create_access_token, decode_access_token

        token = create_access_token(user_id=99, role="admin")
        payload = decode_access_token(token)

        assert payload["sub"] == "99"
        assert payload["role"] == "admin"

    def test_decode_access_token_expired_raises_401(self):
        """Expired JWT → HTTPException with status_code=401."""
        from app.core.security import decode_access_token

        expired_payload = {
            "sub": "1",
            "role": "mechanic",
            "exp": datetime.now(UTC) - timedelta(minutes=1),
        }
        expired_token = jwt.encode(
            expired_payload,
            settings.SECRET_KEY,
            algorithm=settings.JWT_ALGORITHM,
        )

        with pytest.raises(HTTPException) as exc_info:
            decode_access_token(expired_token)

        assert exc_info.value.status_code == 401


# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------


class TestRateLimit:
    @pytest.mark.asyncio
    async def test_rate_limit_allows_15_requests(self):
        """Exactly 15 calls within RATE_LIMIT should not raise."""
        from app.core.security import check_rate_limit

        redis = _make_redis_mock(count=15)
        # Should complete without raising
        await check_rate_limit(user_id=1, redis=redis)

    @pytest.mark.asyncio
    async def test_rate_limit_blocks_16th_request(self):
        """16th call within the window → HTTP 429 with Russian detail."""
        from app.core.security import check_rate_limit

        redis = _make_redis_mock(count=16)

        with pytest.raises(HTTPException) as exc_info:
            await check_rate_limit(user_id=1, redis=redis)

        assert exc_info.value.status_code == 429
        assert "Слишком много запросов" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_rate_limit_sets_expiry_on_first_call(self):
        """First call (count==1) sets TTL via redis.expire()."""
        from app.core.security import check_rate_limit

        redis = _make_redis_mock(count=1)
        await check_rate_limit(user_id=5, redis=redis)

        redis.expire.assert_awaited_once_with("rate:5", 60)
