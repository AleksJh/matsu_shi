"""TDD tests for Citation and QueryResponse Pydantic schemas (Phase 4.1)."""

import pytest
from pydantic import ValidationError

from app.schemas.query import Citation, QueryResponse


class TestCitation:
    def test_citation_required_fields_ok(self):
        c = Citation(doc_name="PC300-8 Shop Manual", section="Hydraulic Pump", page=247)
        assert c.doc_name == "PC300-8 Shop Manual"
        assert c.section == "Hydraulic Pump"
        assert c.page == 247

    def test_citation_missing_required_field_raises(self):
        with pytest.raises(ValidationError):
            Citation(doc_name="Manual", section="Pump")  # page missing

    def test_citation_visual_url_optional_defaults_none(self):
        c = Citation(doc_name="Manual", section="Section 1", page=1)
        assert c.visual_url is None

    def test_citation_visual_url_accepted(self):
        url = "https://r2.example.com/images/page247.webp"
        c = Citation(doc_name="Manual", section="Section 1", page=1, visual_url=url)
        assert c.visual_url == url


class TestQueryResponse:
    def _full(self, **overrides):
        defaults = dict(
            answer="Насос неисправен.",
            citations=[Citation(doc_name="Manual", section="Pump", page=10)],
            model_used="lite",
            retrieval_score=0.85,
            query_class="simple",
            no_answer=False,
            session_id=None,
        )
        defaults.update(overrides)
        return QueryResponse(**defaults)

    def test_queryresponse_all_fields(self):
        qr = self._full(session_id=42)
        assert qr.answer == "Насос неисправен."
        assert len(qr.citations) == 1
        assert qr.model_used == "lite"
        assert qr.retrieval_score == 0.85
        assert qr.query_class == "simple"
        assert qr.no_answer is False
        assert qr.session_id == 42

    def test_queryresponse_defaults(self):
        qr = self._full()
        assert qr.session_id is None
        assert qr.no_answer is False

    def test_queryresponse_missing_required_field_raises(self):
        with pytest.raises(ValidationError):
            QueryResponse(
                citations=[],
                model_used="lite",
                retrieval_score=0.5,
                query_class="simple",
                no_answer=False,
            )  # answer missing

    def test_json_round_trip(self):
        original = self._full(session_id=7, no_answer=True, retrieval_score=0.25)
        json_str = original.model_dump_json()
        restored = QueryResponse.model_validate_json(json_str)
        assert restored.answer == original.answer
        assert restored.citations[0].page == original.citations[0].page
        assert restored.model_used == original.model_used
        assert restored.retrieval_score == original.retrieval_score
        assert restored.query_class == original.query_class
        assert restored.no_answer == original.no_answer
        assert restored.session_id == original.session_id

    def test_advanced_model_complex_query(self):
        qr = self._full(model_used="advanced", query_class="complex", session_id=99)
        assert qr.model_used == "advanced"
        assert qr.query_class == "complex"
        assert qr.session_id == 99

    def test_empty_citations_list(self):
        qr = self._full(citations=[], no_answer=True, retrieval_score=0.1)
        assert qr.citations == []
        assert qr.no_answer is True
