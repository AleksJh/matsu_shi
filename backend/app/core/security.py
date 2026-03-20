"""Security layer for Phase 5.

Provides:
  - validate_telegram_init_data(init_data) -> WebAppInitData
      Uses aiogram's built-in HMAC helper (no manual implementation needed).
  - create_access_token(user_id, role) -> str
  - decode_access_token(token) -> dict
  - pwd_ctx — bcrypt CryptContext for admin password hashing
  - get_current_user — FastAPI dependency → User (role=mechanic, status=active)
  - get_current_admin — FastAPI dependency → AdminUser (role=admin)
  - get_redis — FastAPI dependency → redis client from app.state
  - check_rate_limit(user_id, redis) — raises HTTP 429 after 15 req/min
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

from aiogram.utils.web_app import WebAppInitData, safe_parse_webapp_init_data
from fastapi import Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from loguru import logger
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.models.admin_user import AdminUser
from app.models.user import User
from app.services.user_service import UserService

# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------

pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__truncate_error=False)

# ---------------------------------------------------------------------------
# OAuth2 scheme — reads Bearer token from Authorization header
# ---------------------------------------------------------------------------

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/admin/login")

# ---------------------------------------------------------------------------
# Rate limiting constants
# ---------------------------------------------------------------------------

RATE_LIMIT = 15
RATE_WINDOW = 60  # seconds

# ---------------------------------------------------------------------------
# Telegram initData HMAC validation
# ---------------------------------------------------------------------------


def validate_telegram_init_data(init_data: str) -> WebAppInitData:
    """Validate Telegram Mini App initData HMAC signature.

    Uses aiogram's `safe_parse_webapp_init_data` which implements the exact
    HMAC-SHA256 algorithm specified by Telegram:
      secret_key = HMAC-SHA256("WebAppData", BOT_TOKEN)
      hash = HMAC-SHA256(data_check_string, secret_key)

    Raises:
        HTTPException(403): if signature is invalid or initData is malformed.

    Returns:
        WebAppInitData with .user.id, .user.username, .user.first_name, etc.
    """
    try:
        return safe_parse_webapp_init_data(
            token=settings.BOT_TOKEN,
            init_data=init_data,
        )
    except ValueError as exc:
        logger.warning("Invalid Telegram initData: {}", exc)
        raise HTTPException(status_code=403, detail="Недействительная подпись Telegram")


# ---------------------------------------------------------------------------
# JWT
# ---------------------------------------------------------------------------


def create_access_token(user_id: int, role: str) -> str:
    """Create a signed JWT token.

    Payload: {"sub": str(user_id), "role": "mechanic"|"admin", "exp": ...}
    """
    payload = {
        "sub": str(user_id),
        "role": role,
        "exp": datetime.now(UTC) + timedelta(minutes=settings.JWT_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> dict:
    """Decode and verify a JWT token.

    Raises:
        HTTPException(401): if token is expired, tampered, or otherwise invalid.
    """
    try:
        return jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
    except JWTError as exc:
        logger.warning("JWT decode failed: {}", exc)
        raise HTTPException(status_code=401, detail="Недействительный токен")


# ---------------------------------------------------------------------------
# Redis dependency
# ---------------------------------------------------------------------------


async def get_redis(request: Request):
    """FastAPI dependency that returns the shared Redis client from app.state."""
    return request.app.state.redis


# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------


async def check_rate_limit(user_id: int, redis) -> None:
    """Enforce 15 req/min per user_id using Redis INCR + EXPIRE.

    Raises:
        HTTPException(429): if the user exceeds RATE_LIMIT within RATE_WINDOW.
    """
    key = f"rate:{user_id}"
    count = await redis.incr(key)
    if count == 1:
        await redis.expire(key, RATE_WINDOW)
    if count > RATE_LIMIT:
        raise HTTPException(
            status_code=429,
            detail="Слишком много запросов. Повторите через минуту.",
        )


# ---------------------------------------------------------------------------
# FastAPI dependencies
# ---------------------------------------------------------------------------


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Decode JWT, verify role=mechanic, load User, check status=active."""
    payload = decode_access_token(token)

    if payload.get("role") != "mechanic":
        raise HTTPException(status_code=403, detail="Недостаточно прав")

    try:
        telegram_user_id = int(payload["sub"])
    except (KeyError, ValueError):
        raise HTTPException(status_code=401, detail="Недействительный токен")

    user = await UserService(db).get_by_telegram_id(telegram_user_id)
    if user is None or user.status != "active":
        raise HTTPException(status_code=403, detail="Доступ запрещён")

    return user


async def get_current_admin(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> AdminUser:
    """Decode JWT, verify role=admin, load AdminUser row."""
    payload = decode_access_token(token)

    if payload.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Недостаточно прав")

    try:
        admin_id = int(payload["sub"])
    except (KeyError, ValueError):
        raise HTTPException(status_code=401, detail="Недействительный токен")

    result = await db.scalars(
        select(AdminUser).where(AdminUser.id == admin_id)
    )
    admin = result.first()
    if admin is None:
        raise HTTPException(status_code=403, detail="Доступ запрещён")

    return admin
