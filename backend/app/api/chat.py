"""Chat endpoints — Phase 5.4.

POST   /api/v1/chat/sessions              Create new diagnostic session
GET    /api/v1/chat/sessions              List user's sessions (sidebar)
PUT    /api/v1/chat/sessions/{id}/status  Update session status (paused|completed)
POST   /api/v1/chat/query                 SSE stream: submit query, receive response
GET    /api/v1/chat/sessions/{id}/history Full message history for a session
"""
from __future__ import annotations

import asyncio
import time
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from loguru import logger
from pydantic import BaseModel
from sqlalchemy import distinct, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.title_generator import generate_title
from app.core.database import AsyncSessionLocal, get_db
from app.core.security import get_current_user, get_redis
from app.models.document import Document
from app.models.session import DiagnosticSession
from app.models.user import User
from app.schemas.query import QueryResponse
from app.services.query_service import QueryService
from app.services.session_service import SessionService

router = APIRouter(tags=["chat"])


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------


class CreateSessionRequest(BaseModel):
    machine_model: str
    title: str | None = None


class SessionResponse(BaseModel):
    id: int
    machine_model: str | None
    title: str | None
    status: str
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class UpdateStatusRequest(BaseModel):
    status: str  # "active" | "paused" | "completed"


class RenameTitleRequest(BaseModel):
    title: str


class QueryRequest(BaseModel):
    session_id: int
    query_text: str


class QueryHistoryItem(BaseModel):
    id: int
    query_text: str
    response_text: str | None
    model_used: str | None
    retrieval_score: float | None
    query_class: str | None
    no_answer: bool | None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/chat/models", response_model=list[str])
async def list_models(
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> list[str]:
    """Return distinct machine_model values from indexed documents."""
    result = await session.execute(
        select(distinct(Document.machine_model)).where(Document.status == "indexed")
    )
    return list(result.scalars().all())


@router.post("/chat/sessions", response_model=SessionResponse, status_code=201)
async def create_session(
    body: CreateSessionRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SessionResponse:
    """Create a new diagnostic session for the current user."""
    svc = SessionService(db)
    session = await svc.create_session(
        user_id=user.id,
        machine_model=body.machine_model,
    )
    if body.title:
        # Update title inline (not a separate service method — one-off operation)
        from sqlalchemy import update as sa_update
        await db.execute(
            sa_update(DiagnosticSession)
            .where(DiagnosticSession.id == session.id)
            .values(title=body.title)
        )
        await db.commit()
        await db.refresh(session)

    return SessionResponse.model_validate(session)


@router.get("/chat/sessions", response_model=list[SessionResponse])
async def list_sessions(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[SessionResponse]:
    """Return all diagnostic sessions for the current user, newest first."""
    result = await db.scalars(
        select(DiagnosticSession)
        .where(DiagnosticSession.user_id == user.id)
        .order_by(DiagnosticSession.updated_at.desc())
    )
    sessions = list(result.all())
    return [SessionResponse.model_validate(s) for s in sessions]


@router.put("/chat/sessions/{session_id}/status")
async def update_session_status(
    session_id: int,
    body: UpdateStatusRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Update session status. Only the owning user can update their session."""
    svc = SessionService(db)
    session = await svc.get_session(session_id)
    if session is None or session.user_id != user.id:
        raise HTTPException(status_code=404, detail="Сессия не найдена")

    valid_statuses = {"active", "paused", "completed"}
    if body.status not in valid_statuses:
        raise HTTPException(status_code=422, detail="Недопустимый статус сессии")

    await svc.update_status(session_id, body.status)
    return {"ok": True}


@router.delete("/chat/sessions/{session_id}", status_code=204)
async def delete_session(
    session_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Hard-delete a session and all its queries. Only owner can delete."""
    svc = SessionService(db)
    session = await svc.get_session(session_id)
    if session is None or session.user_id != user.id:
        raise HTTPException(status_code=404, detail="Сессия не найдена")
    await svc.delete_session(session_id)


@router.patch("/chat/sessions/{session_id}/title")
async def rename_session(
    session_id: int,
    body: RenameTitleRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Rename a session title (max 100 chars). Only owner can rename."""
    if not body.title.strip():
        raise HTTPException(status_code=422, detail="Название не может быть пустым")
    svc = SessionService(db)
    session = await svc.get_session(session_id)
    if session is None or session.user_id != user.id:
        raise HTTPException(status_code=404, detail="Сессия не найдена")
    await svc.rename_session(session_id, body.title.strip())
    return {"ok": True}


async def _auto_title(session_id: int, query_text: str, answer: str) -> None:
    """Background task: generate and save a title for the first query in a session."""
    try:
        title = await generate_title(query_text, answer)
        async with AsyncSessionLocal() as db:
            await SessionService(db).rename_session(session_id, title)
    except Exception as exc:
        logger.warning("Auto-title failed for session {}: {}", session_id, exc)


@router.post("/chat/query")
async def query_endpoint(
    body: QueryRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
) -> StreamingResponse:
    """Submit a query and receive a structured response via SSE.

    Flow:
      1. Validate that session belongs to the user and fetch machine_model
      2. Run QueryService.process() — rate limit + RAG + LLM
      3. Stream QueryResponse as a single SSE event
      4. Persist Query row after stream ends (same session, non-blocking)

    Returns:
        text/event-stream with one data: {...QueryResponse JSON...}\\n\\n event.
    """
    t0 = time.monotonic()

    # Resolve machine_model from session
    session_obj = await SessionService(db).get_session(body.session_id)
    if session_obj is None or session_obj.user_id != user.id:
        raise HTTPException(status_code=404, detail="Сессия не найдена")

    machine_model: str = session_obj.machine_model or ""

    svc = QueryService(db)
    response: QueryResponse = await svc.process(
        query_text=body.query_text,
        session_id=body.session_id,
        machine_model=machine_model,
        user_id=user.id,
        redis=redis,
    )
    latency_ms = round((time.monotonic() - t0) * 1000)

    needs_title = session_obj.title is None and response.model_used != "none"

    async def event_generator():
        yield f"data: {response.model_dump_json()}\n\n"
        # Persist after stream is delivered — session is still open here
        await svc.persist_query(
            user_id=user.id,
            session_id=body.session_id,
            query_text=body.query_text,
            response=response,
            latency_ms=latency_ms,
        )
        # Auto-generate title for the first query in this session
        if needs_title:
            asyncio.create_task(
                _auto_title(body.session_id, body.query_text, response.answer)
            )

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"},
    )


@router.get("/chat/sessions/{session_id}/history", response_model=list[QueryHistoryItem])
async def session_history(
    session_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[QueryHistoryItem]:
    """Return all query rows for a session, ordered by created_at ASC."""
    session_obj = await SessionService(db).get_session(session_id)
    if session_obj is None or session_obj.user_id != user.id:
        raise HTTPException(status_code=404, detail="Сессия не найдена")

    history = await SessionService(db).get_history(session_id)
    return [QueryHistoryItem.model_validate(q) for q in history]
