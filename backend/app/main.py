import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import redis.asyncio as aioredis
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api import auth as auth_api
from app.api import admin as admin_api
from app.api import chat as chat_api
from app.api import feedback as feedback_api
from app.bot.dispatcher import bot, dp
from app.core.config import settings
from app.core.database import engine
from app.core.logging import setup_logging

setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # Redis client — shared across all requests via app.state.redis
    app.state.redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)

    if settings.ENVIRONMENT == "development":
        polling_task = asyncio.create_task(dp.start_polling(bot, handle_signals=False))
    else:
        webhook_url = f"{settings.APP_BASE_URL}/webhook/telegram"
        await bot.set_webhook(url=webhook_url, secret_token=settings.WEBHOOK_SECRET)
    yield
    if settings.ENVIRONMENT == "development":
        polling_task.cancel()
    else:
        await bot.delete_webhook()
    await bot.session.close()
    await engine.dispose()
    await app.state.redis.aclose()


app = FastAPI(title="Matsu Shi API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        settings.APP_BASE_URL,
        "http://localhost:5173",
        "http://localhost:5174",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API routers — all mounted under /api/v1
app.include_router(auth_api.router, prefix="/api/v1")
app.include_router(chat_api.router, prefix="/api/v1")
app.include_router(feedback_api.router, prefix="/api/v1")
app.include_router(admin_api.router, prefix="/api/v1")


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.post("/webhook/telegram")
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
) -> dict:
    if settings.WEBHOOK_SECRET and x_telegram_bot_api_secret_token != settings.WEBHOOK_SECRET:
        raise HTTPException(status_code=403, detail="Forbidden")
    from aiogram.types import Update

    data = await request.json()
    update = Update.model_validate(data)
    await dp.feed_webhook_update(bot=bot, update=update)
    return {"ok": True}
