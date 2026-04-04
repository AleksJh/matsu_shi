"""Query processing pipeline — Phase 5.8 + Phase A/B.

Orchestrates the full RAG → LLM pipeline for a single mechanic query:
  1. Redis rate limiting
  2. Load session history (before retrieval, for reformulator)
  3. Query reformulation (expand follow-up into specific retrieval queries)
  4. Multi-query hybrid retrieval (embed → dense+sparse → rerank, parallel)
  5. Early exit if no_answer
  6. Query classification (simple|complex)
  7. Prior context assembly (reuses history from step 2, no second DB call)
  8. LLM response generation with Langfuse tracing
  9. Async Query row persistence (after SSE stream ends)

Public API:
    QueryService(session).process(query_text, session_id, machine_model, user_id, redis)
        -> QueryResponse
"""
from __future__ import annotations

import time

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.classifier import classify_query
from app.agent.reformulator import reformulate
from app.agent.responder import respond
from app.core.security import check_rate_limit
from app.models.query import Query
from app.rag.multi_retriever import multi_retrieve
from app.rag.retriever import RetrievalResult
from app.schemas.query import QueryResponse
from app.services.session_service import SessionService


class QueryService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._last_retrieval_result: RetrievalResult | None = None

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
            2. get_history() — load session history BEFORE retrieval
            3. reformulate() — expand follow-up into specific retrieval queries
            4. multi_retrieve() — embed + dense/sparse + rerank (parallel for N queries)
            5. no_answer early return — skips ALL LLM calls when score < 0.30
            6. classify_query() — "simple" | "complex" (always original query_text)
            7. prior_context — reuse history from step 2 (no second DB call)
            8. respond() — LLM generation with routing + Langfuse tracing
        """
        # 1. Rate limit
        await check_rate_limit(user_id, redis)

        # 2. Load history BEFORE retrieval so reformulator can use it
        history: list[str] = []
        if session_id is not None:
            raw_history = await SessionService(self._session).get_history(session_id)
            if raw_history:
                history = [
                    f"Вопрос: {q.query_text}\nОтвет: {q.response_text or ''}"
                    for q in raw_history
                ]

        # 3. Reformulate: expand follow-up into specific retrieval queries
        retrieval_queries = await reformulate(history, query_text)

        # 4. Multi-query retrieval (handles single-query case internally)
        retrieval_result = await multi_retrieve(
            queries=retrieval_queries,
            machine_model=machine_model,
            session=self._session,
        )
        self._last_retrieval_result = retrieval_result

        # 5. no_answer — skip all LLM calls
        if retrieval_result.no_answer:
            if retrieval_result.embed_failed:
                return QueryResponse(
                    answer="Сервис поиска временно недоступен. Попробуйте повторить запрос через несколько минут.",
                    citations=[],
                    model_used="none",
                    retrieval_score=0.0,
                    query_class="simple",
                    no_answer=True,
                    session_id=session_id,
                )
            return await respond(
                query_text=query_text,
                retrieval_result=retrieval_result,
                query_class="simple",
                session_id=session_id,
            )

        # 6. Classification — follow-ups in active sessions always use advanced
        #    model; only classify fresh queries (no history) via LLM.
        if history:
            query_class = "complex"
        else:
            query_class = await classify_query(query_text)

        # 7. prior_context from history loaded in step 2 (no second DB call)
        prior_context: list[str] | None = history if history else None

        # 8. Generate response — use reformulated query so LLM sees full diagnostic context
        llm_query = retrieval_queries[0]
        return await respond(
            query_text=llm_query,
            retrieval_result=retrieval_result,
            query_class=query_class,
            session_id=session_id,
            prior_context=prior_context,
            trace_id=retrieval_result.trace_id,
            machine_model=machine_model,
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
            chunk_ids: list[int] = (
                [c.id for c, _ in self._last_retrieval_result.chunks if c.id is not None]
                if self._last_retrieval_result
                else []
            )
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
