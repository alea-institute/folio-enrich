"""Tests for the DocumentTypeChecker quality cross-check service."""

from __future__ import annotations

from typing import Any

import pytest

from app.models.annotation import Annotation, ConceptMatch, Span
from app.models.job import Job
from app.services.quality.document_type_checker import DocumentTypeChecker

from tests.helpers import FakeLLMProvider, FailingLLMProvider, make_job


SAMPLE_TEXT = "IN THE UNITED STATES DISTRICT COURT..."


def _make_job(
    self_type: str = "Motion to Dismiss",
    annotations: list[Annotation] | None = None,
    resolved_concepts: list[dict] | None = None,
) -> Job:
    kw = {}
    if self_type:
        kw["self_identified_type"] = self_type
    if resolved_concepts:
        kw["resolved_concepts"] = resolved_concepts
    return make_job(
        text=SAMPLE_TEXT,
        annotations=annotations or [],
        **kw,
    )


class FakeQualityLLM(FakeLLMProvider):
    def __init__(self, signals: list[dict] | None = None):
        self._signals = signals if signals is not None else [
            {
                "signal": "Missing procedural branch",
                "severity": "warning",
                "details": "A Motion to Dismiss typically has procedural concepts",
            }
        ]
        super().__init__()

    async def structured(self, prompt: str, schema: dict, **kw: Any) -> dict:
        return {"signals": self._signals}


FailingLLM = FailingLLMProvider


class TestDocumentTypeChecker:
    @pytest.mark.asyncio
    async def test_returns_signals(self):
        checker = DocumentTypeChecker(FakeQualityLLM())
        job = _make_job()
        signals = await checker.check(job)
        assert len(signals) == 1
        assert signals[0]["signal"] == "Missing procedural branch"
        assert signals[0]["severity"] == "warning"

    @pytest.mark.asyncio
    async def test_no_self_type_returns_empty(self):
        checker = DocumentTypeChecker(FakeQualityLLM())
        job = _make_job(self_type="")
        signals = await checker.check(job)
        assert signals == []

    @pytest.mark.asyncio
    async def test_llm_failure_returns_empty(self):
        checker = DocumentTypeChecker(FailingLLM())
        job = _make_job()
        signals = await checker.check(job)
        assert signals == []

    @pytest.mark.asyncio
    async def test_empty_signals(self):
        checker = DocumentTypeChecker(FakeQualityLLM(signals=[]))
        job = _make_job()
        signals = await checker.check(job)
        assert signals == []

    @pytest.mark.asyncio
    async def test_severity_normalization(self):
        checker = DocumentTypeChecker(FakeQualityLLM(signals=[
            {"signal": "test", "severity": "critical", "details": "bad severity"},
        ]))
        job = _make_job()
        signals = await checker.check(job)
        assert signals[0]["severity"] == "info"  # Normalized from invalid value

    @pytest.mark.asyncio
    async def test_includes_resolved_concepts(self):
        """Checker uses resolved concepts from metadata for cross-check."""
        captured_prompt = {}

        class CaptureLLM(FakeQualityLLM):
            async def structured(self, prompt: str, schema: dict, **kw: Any) -> dict:
                captured_prompt["text"] = prompt
                return await super().structured(prompt, schema, **kw)

        checker = DocumentTypeChecker(CaptureLLM())
        job = _make_job(
            resolved_concepts=[
                {"folio_label": "Summary Judgment", "branches": ["CivilProcedure"]},
                {"folio_label": "Summary Judgment", "branches": ["CivilProcedure"]},
                {"folio_label": "Contract", "branches": ["SubstantiveLaw"]},
            ],
        )
        signals = await checker.check(job)

        prompt = captured_prompt["text"]
        assert "CivilProcedure" in prompt
        assert "Summary Judgment" in prompt
