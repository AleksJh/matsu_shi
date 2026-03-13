"""Model routing logic for the LLM Control Plane (Phase 4.3).

Single source of truth for model selection. Combines the retrieval score
(from Phase 3 dense channel) and the query classification (from Phase 4.2
ClassifierAgent) to select the appropriate LLM model per PRD §6.2.

Public API:
    route_query(max_retrieval_score, query_class) -> str
        Returns a model identifier string suitable for passing to ResponderAgent.
"""
from __future__ import annotations

from app.core.config import settings


def route_query(max_retrieval_score: float, query_class: str) -> str:
    """Select LLM model based on retrieval score and query classification.

    Logic (PRD §6.2):
        score < RETRIEVAL_SCORE_THRESHOLD (0.65) OR query_class == "complex"
            → settings.LLM_ADVANCED_MODEL  (gemini-3-flash-preview)
        otherwise
            → settings.LLM_LITE_MODEL      (gemini-2.5-flash-lite)

    This function is never called when no_answer=True (score < 0.30); that
    bypass is handled upstream by QueryService before routing is invoked.

    Args:
        max_retrieval_score: Max cosine similarity score from the dense
            retrieval channel (RetrievalResult.max_score from Phase 3).
        query_class: Classification result — "simple" or "complex" —
            produced by ClassifierAgent (Phase 4.2).

    Returns:
        Model identifier string: settings.LLM_LITE_MODEL or
        settings.LLM_ADVANCED_MODEL. Pass directly to ResponderAgent.
    """
    if max_retrieval_score < settings.RETRIEVAL_SCORE_THRESHOLD or query_class == "complex":
        return settings.LLM_ADVANCED_MODEL
    return settings.LLM_LITE_MODEL
