"""Feedback endpoint — Phase 5.5.

POST /api/v1/feedback/{query_id}   Submit thumbs up (+1) or thumbs down (-1)
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.services.feedback_service import FeedbackService

router = APIRouter(tags=["feedback"])


class FeedbackRequest(BaseModel):
    rating: int = Field(..., description="1 (thumbs up) or -1 (thumbs down)")


class FeedbackResponse(BaseModel):
    id: int
    query_id: int | None
    user_id: int | None
    rating: int

    model_config = {"from_attributes": True}


@router.post("/feedback/{query_id}", response_model=FeedbackResponse, status_code=201)
async def submit_feedback(
    query_id: int,
    body: FeedbackRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FeedbackResponse:
    """Submit thumbs up / thumbs down for a query response.

    The feedback table has a UNIQUE constraint on query_id (one per query).
    A second submission returns HTTP 409.
    """
    if body.rating not in {1, -1}:
        raise HTTPException(status_code=422, detail="Допустимые значения: 1 (👍) или -1 (👎)")

    svc = FeedbackService(db)
    try:
        feedback = await svc.add_feedback(
            query_id=query_id,
            user_id=user.id,
            rating=body.rating,
        )
    except IntegrityError:
        raise HTTPException(
            status_code=409,
            detail="Отзыв для этого запроса уже оставлен",
        )

    return FeedbackResponse.model_validate(feedback)
