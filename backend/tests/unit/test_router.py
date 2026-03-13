"""TDD tests for route_query() model router (Phase 4.3).

Covers all four logical branches of PRD §6.2 plus boundary conditions.
No mocking required — router is pure synchronous logic with no I/O.
"""
import pytest

from app.agent.router import route_query
from app.core.config import settings


# ---------------------------------------------------------------------------
# Branch 1: high score + simple → lite model
# ---------------------------------------------------------------------------

def test_high_score_simple_returns_lite():
    model = route_query(max_retrieval_score=0.80, query_class="simple")
    assert model == settings.LLM_LITE_MODEL


# ---------------------------------------------------------------------------
# Branch 2: low score + simple → advanced model (score below threshold)
# ---------------------------------------------------------------------------

def test_low_score_simple_returns_advanced():
    model = route_query(max_retrieval_score=0.50, query_class="simple")
    assert model == settings.LLM_ADVANCED_MODEL


# ---------------------------------------------------------------------------
# Branch 3: high score + complex → advanced model (query_class overrides)
# ---------------------------------------------------------------------------

def test_high_score_complex_returns_advanced():
    model = route_query(max_retrieval_score=0.80, query_class="complex")
    assert model == settings.LLM_ADVANCED_MODEL


# ---------------------------------------------------------------------------
# Branch 4: low score + complex → advanced model (both conditions true)
# ---------------------------------------------------------------------------

def test_low_score_complex_returns_advanced():
    model = route_query(max_retrieval_score=0.50, query_class="complex")
    assert model == settings.LLM_ADVANCED_MODEL


# ---------------------------------------------------------------------------
# Boundary: score == RETRIEVAL_SCORE_THRESHOLD (0.65) with simple
# Condition is strictly-less-than, so 0.65 == threshold → lite
# ---------------------------------------------------------------------------

def test_exact_threshold_simple_returns_lite():
    threshold = settings.RETRIEVAL_SCORE_THRESHOLD  # 0.65
    model = route_query(max_retrieval_score=threshold, query_class="simple")
    assert model == settings.LLM_LITE_MODEL


# ---------------------------------------------------------------------------
# Boundary: score just below threshold → advanced
# ---------------------------------------------------------------------------

def test_just_below_threshold_simple_returns_advanced():
    threshold = settings.RETRIEVAL_SCORE_THRESHOLD  # 0.65
    model = route_query(max_retrieval_score=threshold - 0.0001, query_class="simple")
    assert model == settings.LLM_ADVANCED_MODEL


# ---------------------------------------------------------------------------
# Sanity: return values are the configured model identifiers (not hard-coded)
# ---------------------------------------------------------------------------

def test_return_values_are_settings_strings():
    lite = route_query(max_retrieval_score=0.90, query_class="simple")
    advanced = route_query(max_retrieval_score=0.90, query_class="complex")
    assert lite == settings.LLM_LITE_MODEL
    assert advanced == settings.LLM_ADVANCED_MODEL
    assert lite != advanced
