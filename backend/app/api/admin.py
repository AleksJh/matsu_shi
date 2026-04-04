"""Admin endpoints — Phase 5.6.

All endpoints require a valid admin JWT (get_current_admin dependency).

GET    /api/v1/admin/users              List users (filter by status, pagination)
PUT    /api/v1/admin/users/{id}/status  Update user status: active|denied|banned
GET    /api/v1/admin/documents          List indexed documents
GET    /api/v1/admin/queries            Paginated query log
GET    /api/v1/admin/queries/{id}       Full query detail + feedback
GET    /api/v1/admin/stats              Aggregated system metrics
POST   /api/v1/admin/broadcast          Broadcast message to all active users
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.dispatcher import bot
from app.core.database import get_db
from app.core.security import get_current_admin
from app.models.admin_user import AdminUser
from app.models.document import Document
from app.models.feedback import Feedback
from app.models.query import Query as QueryModel
from app.models.user import User
from app.services.user_service import UserService

router = APIRouter(prefix="/admin", tags=["admin"])


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class UserAdminView(BaseModel):
    id: int
    telegram_user_id: int
    username: str | None
    first_name: str | None
    status: str
    created_at: datetime | None
    approved_at: datetime | None

    model_config = {"from_attributes": True}


class UpdateUserStatusRequest(BaseModel):
    status: str  # active | denied | banned


class DocumentAdminView(BaseModel):
    id: int
    display_name: str
    machine_model: str
    category: str | None
    page_count: int | None
    chunk_count: int | None
    status: str | None
    indexed_at: datetime | None

    model_config = {"from_attributes": True}


class QueryAdminView(BaseModel):
    id: int
    user_id: int | None
    session_id: int | None
    query_text: str
    response_text: str | None
    model_used: str | None
    retrieval_score: float | None
    query_class: str | None
    no_answer: bool | None
    latency_ms: int | None
    created_at: datetime | None

    model_config = {"from_attributes": True}


class QueryDetailView(QueryAdminView):
    feedback_rating: int | None = None


class StatsResponse(BaseModel):
    queries_today: int
    avg_retrieval_score_7d: float | None
    model_usage: dict[str, int]
    feedback_up: int
    feedback_down: int
    users: dict[str, int]


class BulkDeleteRequest(BaseModel):
    ids: list[int]


class SendMessageRequest(BaseModel):
    message: str


class BroadcastRequest(BaseModel):
    message: str


class BroadcastResponse(BaseModel):
    sent: int
    failed: int


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------


@router.get("/users", response_model=list[UserAdminView])
async def list_users(
    status: str | None = Query(default=None, description="Filter: pending|active|denied|banned"),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    _admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> list[UserAdminView]:
    """List all users with optional status filter and pagination."""
    query = (
        select(User)
        .order_by(User.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    if status is not None:
        query = query.where(User.status == status)
    result = await db.scalars(query)
    users = list(result.all())
    return [UserAdminView.model_validate(u) for u in users]


@router.put("/users/{user_id}/status")
async def update_user_status(
    user_id: int,
    body: UpdateUserStatusRequest,
    _admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Update a user's status to active, denied, or banned."""
    valid = {"active", "denied", "banned"}
    if body.status not in valid:
        raise HTTPException(status_code=422, detail=f"Допустимые статусы: {', '.join(valid)}")

    # Lookup by PK (users.id)
    result = await db.scalars(select(User).where(User.id == user_id))
    user = result.first()
    if user is None:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    await UserService(db).update_status(
        telegram_user_id=user.telegram_user_id,
        status=body.status,
    )
    return {"ok": True}


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: int,
    _admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Permanently delete a user and all related data (cascade)."""
    result = await db.scalars(select(User).where(User.id == user_id))
    user = result.first()
    if user is None:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    await db.delete(user)
    await db.commit()
    return {"ok": True}


@router.post("/users/bulk-delete")
async def bulk_delete_users(
    body: BulkDeleteRequest,
    _admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Permanently delete multiple users by their id list."""
    if not body.ids:
        raise HTTPException(status_code=422, detail="Список id не может быть пустым")

    result = await db.scalars(select(User).where(User.id.in_(body.ids)))
    users = list(result.all())
    for user in users:
        await db.delete(user)
    await db.commit()
    return {"deleted": len(users)}


@router.post("/users/{user_id}/message")
async def send_message_to_user(
    user_id: int,
    body: SendMessageRequest,
    _admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Send a Telegram message to a specific user via the bot."""
    result = await db.scalars(select(User).where(User.id == user_id))
    user = result.first()
    if user is None:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    try:
        await bot.send_message(user.telegram_user_id, body.message)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Не удалось отправить сообщение: {exc}") from exc

    return {"ok": True}


# ---------------------------------------------------------------------------
# Documents
# ---------------------------------------------------------------------------


@router.get("/documents", response_model=list[DocumentAdminView])
async def list_documents(
    _admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> list[DocumentAdminView]:
    """Return all indexed documents, newest first."""
    result = await db.scalars(
        select(Document).order_by(Document.indexed_at.desc())
    )
    docs = list(result.all())
    return [DocumentAdminView.model_validate(d) for d in docs]


# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------


@router.get("/queries", response_model=list[QueryAdminView])
async def list_queries(
    user_id: int | None = Query(default=None),
    model_used: str | None = Query(default=None),
    since: datetime | None = Query(default=None, description="ISO datetime lower bound"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    _admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> list[QueryAdminView]:
    """Paginated query log with optional filters."""
    query = (
        select(QueryModel)
        .order_by(QueryModel.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    if user_id is not None:
        query = query.where(QueryModel.user_id == user_id)
    if model_used is not None:
        query = query.where(QueryModel.model_used == model_used)
    if since is not None:
        query = query.where(QueryModel.created_at >= since)

    result = await db.scalars(query)
    rows = list(result.all())
    return [QueryAdminView.model_validate(r) for r in rows]


@router.get("/queries/{query_id}", response_model=QueryDetailView)
async def get_query(
    query_id: int,
    _admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> QueryDetailView:
    """Full query detail including feedback rating."""
    result = await db.scalars(
        select(QueryModel).where(QueryModel.id == query_id)
    )
    row = result.first()
    if row is None:
        raise HTTPException(status_code=404, detail="Запрос не найден")

    # Fetch feedback rating if exists
    fb_result = await db.scalars(
        select(Feedback).where(Feedback.query_id == query_id)
    )
    fb = fb_result.first()

    detail = QueryDetailView.model_validate(row)
    detail.feedback_rating = fb.rating if fb else None
    return detail


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------


@router.get("/stats", response_model=StatsResponse)
async def get_stats(
    _admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> StatsResponse:
    """Aggregated system metrics for the admin dashboard."""
    now = datetime.now(tz=timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_ago = now - timedelta(days=7)

    # Queries today
    queries_today: int = await db.scalar(
        select(func.count(QueryModel.id)).where(
            QueryModel.created_at >= today_start
        )
    ) or 0

    # Avg retrieval score (last 7 days)
    avg_score: float | None = await db.scalar(
        select(func.avg(QueryModel.retrieval_score)).where(
            QueryModel.created_at >= week_ago
        )
    )

    # Model usage breakdown
    model_rows = await db.execute(
        select(QueryModel.model_used, func.count(QueryModel.id))
        .group_by(QueryModel.model_used)
    )
    model_usage: dict[str, int] = {
        (row[0] or "unknown"): row[1] for row in model_rows.all()
    }

    # Feedback counts
    fb_up: int = await db.scalar(
        select(func.count(Feedback.id)).where(Feedback.rating == 1)
    ) or 0
    fb_down: int = await db.scalar(
        select(func.count(Feedback.id)).where(Feedback.rating == -1)
    ) or 0

    # User counts by status
    user_stats = await UserService(db).get_stats()

    return StatsResponse(
        queries_today=queries_today,
        avg_retrieval_score_7d=round(float(avg_score), 4) if avg_score is not None else None,
        model_usage=model_usage,
        feedback_up=fb_up,
        feedback_down=fb_down,
        users=user_stats,
    )


# ---------------------------------------------------------------------------
# Broadcast
# ---------------------------------------------------------------------------


@router.post("/broadcast", response_model=BroadcastResponse)
async def broadcast(
    body: BroadcastRequest,
    _admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> BroadcastResponse:
    """Send a message to all active mechanics via the Telegram bot."""
    active_users = await UserService(db).list_by_status("active")
    sent = 0
    failed = 0
    for user in active_users:
        try:
            await bot.send_message(user.telegram_user_id, body.message)
            sent += 1
        except Exception:
            failed += 1
    return BroadcastResponse(sent=sent, failed=failed)
