"""Authentication endpoints — Phase 5.3.

POST /api/v1/auth/telegram       Validate Telegram initData → JWT (mechanic)
POST /api/v1/auth/admin/login    Username + bcrypt password → JWT (admin)
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import (
    _verify_password,
    create_access_token,
    validate_telegram_init_data,
)
from app.models.admin_user import AdminUser
from app.services.user_service import UserService

router = APIRouter(tags=["auth"])


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------


class TelegramAuthRequest(BaseModel):
    init_data: str


class AdminLoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/auth/telegram", response_model=TokenResponse)
async def auth_telegram(
    body: TelegramAuthRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Validate Telegram Mini App initData and return a mechanic JWT.

    Flow:
      1. HMAC-validate initData via aiogram's safe_parse_webapp_init_data
      2. Look up or inform frontend of user status
      3. If user is active → issue JWT with role=mechanic
      4. If user is pending/denied/banned → 403
    """
    webapp_data = validate_telegram_init_data(body.init_data)
    telegram_user = webapp_data.user
    if telegram_user is None:
        raise HTTPException(status_code=400, detail="initData не содержит данных пользователя")

    user = await UserService(db).get_by_telegram_id(telegram_user.id)
    if user is None:
        raise HTTPException(
            status_code=403,
            detail="Аккаунт не зарегистрирован. Используйте /start в боте.",
        )
    if user.status != "active":
        raise HTTPException(
            status_code=403,
            detail="Доступ не разрешён. Ожидайте подтверждения администратора.",
        )

    token = create_access_token(user_id=user.telegram_user_id, role="mechanic")
    return TokenResponse(access_token=token)


@router.post("/auth/admin/login", response_model=TokenResponse)
async def auth_admin_login(
    body: AdminLoginRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Validate admin credentials and return an admin JWT.

    Flow:
      1. Lookup AdminUser by username
      2. bcrypt-verify password
      3. Issue JWT with role=admin
    """
    result = await db.scalars(
        select(AdminUser).where(AdminUser.username == body.username)
    )
    admin = result.first()

    if admin is None or not _verify_password(body.password, admin.password_hash):
        raise HTTPException(status_code=401, detail="Неверный логин или пароль")

    token = create_access_token(user_id=admin.id, role="admin")
    return TokenResponse(access_token=token)
