"""Query processing pipeline — Phase 5.8.

Orchestrates the full RAG → LLM pipeline for a single mechanic query:
  1. Redis rate limiting
  2. Hybrid retrieval (embed → dense+sparse → rerank)
  3. Early exit if no_answer
  4. Query classification (simple|complex)
  5. Prior context assembly for complex queries
  6. LLM response generation with Langfuse tracing
  7. Async Query row persistence (after SSE stream ends)

Public API:
    QueryService(session).process(query_text, session_id, machine_model, user_id, redis)
        -> QueryResponse
"""
from __future__ import annotations

import time

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.classifier import classify_query
from app.agent.responder import respond
from app.core.security import check_rate_limit
from app.models.query import Query
from app.rag.retriever import retrieve
from app.schemas.query import QueryResponse
from app.services.session_service import SessionService


class QueryService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def process(
        self,
        query_text: str,
        session_id: int | None,
        machine_model: str,
        user_id: int,
        redis,
    ) -> QueryResponse:
        """Run the full RAG → LLM pipeline and return a QueryResponse.

        Steps:
            1. check_rate_limit — 15 req/min per user_id (HTTP 429 on exceed)
            2. retrieve() — embed + dense/sparse + rerank (pipeline entry point)
            3. no_answer early return — skips ALL LLM calls when score < 0.30
            4. classify_query() — "simple" | "complex"
            5. get_history() — prior Q&A context for complex sessions
            6. respond() — LLM generation with routing + Langfuse tracing
        """
        # 1. Rate limit
        await check_rate_limit(user_id, redis)

        # 2. Retrieval (embed_text is called inside retrieve)
        retrieval_result = await retrieve(
            query_text=query_text,
            machine_model=machine_model,
            session=self._session,
        )

        # 3. no_answer — skip all LLM calls
        if retrieval_result.no_answer:
            return await respond(
                query_text=query_text,
                retrieval_result=retrieval_result,
                query_class="simple",
                session_id=session_id,
            )

        # 4. Classification
        query_class = await classify_query(query_text)

        # 5. Prior context — load for any query within a session so follow-up
        # questions ("simple" class) still receive conversation history
        prior_context: list[str] | None = None
        if session_id is not None:
            history = await SessionService(self._session).get_history(session_id)
            if history:
                prior_context = [
                    f"Вопрос: {q.query_text}\nОтвет: {q.response_text or ''}"
                    for q in history
                ]

        # 6. Generate response
        return await respond(
            query_text=query_text,
            retrieval_result=retrieval_result,
            query_class=query_class,
            session_id=session_id,
            prior_context=prior_context,
            trace_id=retrieval_result.trace_id,
        )

    async def persist_query(
        self,
        user_id: int,
        session_id: int | None,
        query_text: str,
        response: QueryResponse,
        latency_ms: int,
    ) -> None:
        """Persist the Query row after the SSE stream ends.

        Called via asyncio.ensure_future / after stream generator exhausts,
        so it never blocks the SSE response delivery.
        Uses the same SQLAlchemy session as the request — caller must ensure
        the session is still open (it is, for the full FastAPI request lifespan).
        """
        try:
            chunk_ids: list[int] = []  # populated by retriever when chunks are returned
            query = Query(
                session_id=session_id,
                user_id=user_id,
                query_text=query_text,
                response_text=response.answer,
                model_used=response.model_used,
                retrieval_score=response.retrieval_score,
                query_class=response.query_class,
                retrieved_chunk_ids=chunk_ids or None,
                no_answer=response.no_answer,
                latency_ms=latency_ms,
            )
            self._session.add(query)
            await self._session.commit()
        except Exception as exc:
            logger.warning("Failed to persist Query row: {}", exc)
