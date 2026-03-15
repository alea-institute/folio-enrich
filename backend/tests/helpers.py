"""Shared test helpers: factories, fake providers, and sample texts.

Import from this module in test files:
    from tests.helpers import make_job, FakeLLMProvider, FailingLLMProvider
"""
from __future__ import annotations

from typing import Any

from app.models.annotation import Annotation, ConceptMatch, Span
from app.models.document import CanonicalText, DocumentFormat, DocumentInput, TextChunk
from app.models.job import Job, JobResult, JobStatus
from app.services.llm.base import LLMProvider


# ── Shared sample texts ──────────────────────────────────────────────


SAMPLE_LEGAL_TEXT = (
    "The defendant filed a Motion to Dismiss pursuant to Federal Rule of "
    "Civil Procedure 12(b)(6). The court considered the plaintiff's claims "
    "of breach of contract and negligence. After reviewing the pleadings, "
    "the court granted the motion in part and denied it in part. "
    "The breach of contract claim survived because the complaint adequately "
    "alleged the existence of a valid contract, breach by the defendant, "
    "and resulting damages. However, the negligence claim was dismissed "
    "for failure to state a claim upon which relief can be granted."
)

SAMPLE_INDIVIDUAL_TEXT = (
    "In Smith v. Jones, 123 U.S. 456 (1987), the Supreme Court of the United States "
    "held that John Smith, the plaintiff, was entitled to $500,000 in damages under "
    "42 U.S.C. § 1983. The case was filed on January 15, 2023 in the S.D.N.Y. "
    "Google LLC argued that the contract signed on 03/15/2022 for a period of "
    "30 days was subject to 5% interest. Judge Roberts ruled that no more than "
    "$1 million could be awarded. Apple® and Microsoft™ were also mentioned. "
    "© 2024 Acme Corp. All rights reserved. The address is "
    "123 Main Street, Suite 100, New York, NY 10001."
)

SAMPLE_PROPERTY_TEXT = (
    "The court reversed the grant of summary judgment and remanded "
    "the case for further proceedings. The motion was denied by the judge. "
    "Counsel argued that the statute applied and the contract was drafted "
    "by the defendant. The ruling was affirmed on appeal."
)


# ── Shared job factory ────────────────────────────────────────────────


def make_job(
    text: str = "The court granted the motion.",
    annotations: list[Annotation] | None = None,
    properties: list | None = None,
    individuals: list | None = None,
    status: JobStatus = JobStatus.COMPLETED,
    with_canonical: bool = True,
    **metadata_kw,
) -> Job:
    """Flexible job factory used across test files."""
    result = JobResult()
    if with_canonical:
        result.canonical_text = CanonicalText(
            full_text=text,
            chunks=[TextChunk(
                text=text, start_offset=0,
                end_offset=len(text), chunk_index=0,
            )],
        )
    if annotations is not None:
        result.annotations = annotations
    if properties is not None:
        result.properties = properties
    if individuals is not None:
        result.individuals = individuals
    for k, v in metadata_kw.items():
        result.metadata[k] = v
    return Job(
        input=DocumentInput(content=text, format=DocumentFormat.PLAIN_TEXT),
        status=status,
        result=result,
    )


# ── Shared fake LLM providers ────────────────────────────────────────


class FakeLLMProvider(LLMProvider):
    """Configurable fake LLM that returns a pre-set structured response."""

    def __init__(self, structured_response: dict | None = None, label: str = "fake"):
        super().__init__(api_key="fake", base_url=None, model="fake-model")
        self._structured_response = structured_response or {}
        self.label = label

    async def complete(self, prompt: str, **kw: Any) -> str:
        return ""

    async def chat(self, messages: list[dict[str, str]], **kw: Any) -> str:
        return ""

    async def structured(self, prompt: str, schema: dict, **kw: Any) -> dict:
        return self._structured_response

    async def test_connection(self) -> bool:
        return True

    async def list_models(self):
        return []

    def __repr__(self) -> str:
        return f"FakeLLMProvider({self.label!r})"


class FailingLLMProvider(LLMProvider):
    """LLM provider that always raises RuntimeError."""

    async def complete(self, prompt: str, **kw: Any) -> str:
        raise RuntimeError("LLM error")

    async def chat(self, messages: list[dict[str, str]], **kw: Any) -> str:
        raise RuntimeError("LLM error")

    async def structured(self, prompt: str, schema: dict, **kw: Any) -> dict:
        raise RuntimeError("LLM error")

    async def test_connection(self) -> bool:
        return False

    async def list_models(self):
        return []
