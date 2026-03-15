"""Tests for the early DocumentTypeStage (parallel document type identification)."""

from __future__ import annotations

from typing import Any

import pytest

from app.models.document import DocumentFormat, DocumentInput
from app.models.job import Job, JobResult, JobStatus
from app.pipeline.stages.document_type_stage import DocumentTypeStage

from tests.helpers import FakeLLMProvider, FailingLLMProvider, make_job


SAMPLE_TEXT = (
    "IN THE UNITED STATES DISTRICT COURT\n"
    "FOR THE SOUTHERN DISTRICT OF NEW YORK\n\n"
    "ACME CORP.,\n    Plaintiff,\nv.\n"
    "WIDGET INC.,\n    Defendant.\n\n"
    "DEFENDANT'S MOTION TO DISMISS UNDER RULE 12(b)(6)\n"
    "FOR FAILURE TO STATE A CLAIM\n\n"
    "Defendant Widget Inc., by and through its attorneys, hereby moves this Court..."
)


def _make_job(text: str = SAMPLE_TEXT) -> Job:
    return make_job(text=text, status=JobStatus.MATCHING)


class FakeDocTypeLLM(FakeLLMProvider):
    """Returns a canned document type classification."""

    def __init__(self, response: dict | None = None):
        super().__init__(structured_response=response or {
            "self_identified_type": "Defendant's Motion to Dismiss Under Rule 12(b)(6) for Failure to State a Claim",
            "confidence": 0.95,
            "reasoning": "Extracted from document header",
        })

    async def structured(self, prompt: str, schema: dict, **kw: Any) -> dict:
        return self._structured_response


FailingLLM = FailingLLMProvider


class TestDocumentTypeStage:
    @pytest.mark.asyncio
    async def test_sets_metadata(self):
        stage = DocumentTypeStage(FakeDocTypeLLM())
        job = _make_job()
        result = await stage.execute(job)

        assert result.result.metadata["self_identified_type"] == (
            "Defendant's Motion to Dismiss Under Rule 12(b)(6) for Failure to State a Claim"
        )
        assert result.result.metadata["document_type"] == result.result.metadata["self_identified_type"]
        assert result.result.metadata["document_type_confidence"] == 0.95

    @pytest.mark.asyncio
    async def test_activity_log(self):
        stage = DocumentTypeStage(FakeDocTypeLLM())
        job = _make_job()
        result = await stage.execute(job)

        log = result.result.metadata.get("activity_log", [])
        assert len(log) == 1
        assert log[0]["stage"] == "document_type_classification"
        assert "Defendant's Motion to Dismiss" in log[0]["msg"]
        assert "95%" in log[0]["msg"]

    @pytest.mark.asyncio
    async def test_stage_name(self):
        stage = DocumentTypeStage(FakeDocTypeLLM())
        assert stage.name == "document_type_classification"

    @pytest.mark.asyncio
    async def test_no_canonical_text(self):
        stage = DocumentTypeStage(FakeDocTypeLLM())
        job = Job(
            input=DocumentInput(content="text", format=DocumentFormat.PLAIN_TEXT),
            status=JobStatus.MATCHING,
            result=JobResult(),
        )
        result = await stage.execute(job)
        assert "self_identified_type" not in result.result.metadata

    @pytest.mark.asyncio
    async def test_empty_text(self):
        stage = DocumentTypeStage(FakeDocTypeLLM())
        job = _make_job("")
        result = await stage.execute(job)
        assert "self_identified_type" not in result.result.metadata

    @pytest.mark.asyncio
    async def test_llm_failure_graceful(self):
        stage = DocumentTypeStage(FailingLLM())
        job = _make_job()
        result = await stage.execute(job)
        # Should not crash, just skip
        assert "self_identified_type" not in result.result.metadata

    @pytest.mark.asyncio
    async def test_empty_self_type_not_stored(self):
        llm = FakeDocTypeLLM({"self_identified_type": "", "confidence": 0.0, "reasoning": ""})
        stage = DocumentTypeStage(llm)
        job = _make_job()
        result = await stage.execute(job)
        assert "self_identified_type" not in result.result.metadata

    @pytest.mark.asyncio
    async def test_prompt_uses_first_500_chars(self):
        """Verify the prompt limits input to 500 characters."""
        captured_prompt = {}

        class CaptureLLM(FakeDocTypeLLM):
            async def structured(self, prompt: str, schema: dict, **kw: Any) -> dict:
                captured_prompt["text"] = prompt
                return await super().structured(prompt, schema, **kw)

        long_text = "A" * 1000
        stage = DocumentTypeStage(CaptureLLM())
        job = _make_job(long_text)
        await stage.execute(job)

        # The prompt should contain exactly 500 A's, not 1000
        prompt_text = captured_prompt["text"]
        assert "A" * 500 in prompt_text
        assert "A" * 501 not in prompt_text
