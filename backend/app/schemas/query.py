"""Pydantic output schemas for the RAG query pipeline (Phase 4.1).

These models are the contract between:
- ResponderAgent (Phase 4.4) — produces QueryResponse
- POST /api/v1/chat/query (Phase 5.4) — serialises QueryResponse for SSE
- GET /api/v1/chat/sessions/{id}/history (Phase 5.4) — returns list[QueryResponse]
"""

from __future__ import annotations

from pydantic import BaseModel


class Citation(BaseModel):
    doc_name: str
    section: str
    page: int
    visual_url: str | None = None  # Cloudflare R2 WebP URL, if applicable


class QueryResponse(BaseModel):
    answer: str  # Structured markdown text
    citations: list[Citation]
    model_used: str  # "lite" | "advanced"
    retrieval_score: float
    query_class: str  # "simple" | "complex"
    no_answer: bool  # True when score < 0.30
    session_id: int | None = None  # Set for complex (Step-by-Step) queries
