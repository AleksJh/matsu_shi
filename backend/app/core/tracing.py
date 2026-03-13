"""Langfuse tracing helpers — Phase 4.6.

Provides a Langfuse v3 client singleton and a create_trace() helper that
creates a root span (the entry point for a new trace).

Usage in retrieve():
    root_span = create_trace("rag-pipeline", input={...})
    trace_id  = root_span.trace_id if root_span else None
    child     = root_span.start_span(name="retrieval", ...) if root_span else None
    child.end(); root_span.end()

Usage in respond():
    from langfuse.types import TraceContext
    tc  = TraceContext({"trace_id": trace_id})
    gen = get_langfuse().start_observation(
        as_type="generation", name="llm-response", trace_context=tc, ...
    )
    gen.end(); get_langfuse().flush()

Error isolation: all Langfuse calls are wrapped in try/except so that a
Langfuse outage never interrupts the main pipeline.
"""
from __future__ import annotations

from loguru import logger

from langfuse import get_client
from langfuse._client.span import LangfuseSpan


def get_langfuse():
    """Return the Langfuse v3 singleton client.

    Reads LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY and LANGFUSE_HOST from
    environment automatically (standard Langfuse v3 behavior).
    """
    return get_client()


def create_trace(name: str, **kwargs) -> LangfuseSpan | None:
    """Create a new Langfuse root span (= trace entry point).

    In Langfuse v3 (OTEL-based) there is no explicit Trace object; the first
    span automatically starts a new trace.  This helper wraps span creation in
    a try/except so that Langfuse errors never propagate to the caller.

    Args:
        name:    Span / trace name shown in the Langfuse dashboard.
        **kwargs: Forwarded to start_span() — e.g. input={...}.

    Returns:
        LangfuseSpan if creation succeeded, None otherwise.
        Callers must call .end() on the returned span when done.
    """
    try:
        return get_langfuse().start_span(name=name, **kwargs)
    except Exception as exc:
        logger.warning("Langfuse unavailable, tracing skipped: {}", exc)
        return None
