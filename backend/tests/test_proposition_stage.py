from __future__ import annotations

import json
from copy import deepcopy
from uuid import UUID

import pytest

from app.config import settings
from app.models.document import DocumentInput
from app.models.job import Job, JobResult, JobStatus
from app.pipeline.stages.ingestion_stage import IngestionStage
from app.pipeline.stages.normalization_stage import NormalizationStage


async def _job(text: str) -> Job:
    job = Job(
        id=UUID("b415b8ef-bff3-5b0b-a06a-e379bf128c36"),
        input=DocumentInput(content=text),
    )
    job = await IngestionStage().execute(job)
    return await NormalizationStage().execute(job)


class FakeLLM:
    model = "proposition-test-model"

    def __init__(self, response: dict | None = None) -> None:
        self.response = response or {"propositions": []}
        self.prompts: list[str] = []

    async def structured(self, prompt: str, schema: dict, **kwargs) -> dict:
        self.prompts.append(prompt)
        return self.response


class RaisingLLM(FakeLLM):
    async def structured(self, prompt: str, schema: dict, **kwargs) -> dict:
        self.prompts.append(prompt)
        raise RuntimeError("provider unavailable")


@pytest.mark.asyncio
async def test_flag_off_returns_job_unchanged(monkeypatch) -> None:
    from app.pipeline.stages.proposition_stage import EarlyPropositionStage

    monkeypatch.setattr(settings, "proposition_extraction_enabled", False)
    job = await _job("Plaintiff contends the statute requires notice.")
    before = job.model_dump(mode="json")
    result = await EarlyPropositionStage().execute(job)
    assert result is job
    assert result.model_dump(mode="json") == before
    assert result.result.propositions == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("text", "proposition_type", "role", "content"),
    [
        (
            "Plaintiff contends the statute requires notice.",
            "Legal Proposition",
            "plaintiff",
            "the statute requires notice",
        ),
        (
            "We hold that the contract is void.",
            "Judicial Legal Conclusion",
            "court",
            "the contract is void",
        ),
    ],
)
async def test_dependency_frames_extract_complement_span(
    monkeypatch, text, proposition_type, role, content
) -> None:
    from app.pipeline.stages.proposition_stage import EarlyPropositionStage

    monkeypatch.setattr(settings, "proposition_extraction_enabled", True)
    result = await EarlyPropositionStage().execute(await _job(text))
    assert len(result.result.propositions) == 1
    proposition = result.result.propositions[0]
    assert proposition.proposition_type == proposition_type
    assert proposition.asserter.role.value == role
    assert proposition.text == content
    assert text[proposition.start_char : proposition.end_char] == content


@pytest.mark.asyncio
async def test_arguendo_marker_builds_declined_assumption(monkeypatch) -> None:
    from app.pipeline.stages.proposition_stage import EarlyPropositionStage

    monkeypatch.setattr(settings, "proposition_extraction_enabled", True)
    result = await EarlyPropositionStage().execute(
        await _job("We assume, without deciding, that the claim was preserved.")
    )
    assert len(result.result.propositions) == 1
    proposition = result.result.propositions[0]
    assert proposition.proposition_type == "arguendo assumption"
    assert proposition.asserter.role.value == "court"
    assert proposition.asserter.assumed is True
    assert proposition.validator.role.value == "court"
    assert proposition.validator.mode.value == "declined"
    assert proposition.disposition.value == "assumed-arguendo"
    assert proposition.text == "the claim was preserved"


@pytest.mark.asyncio
async def test_no_reporting_verb_emits_nothing(monkeypatch) -> None:
    from app.pipeline.stages.proposition_stage import EarlyPropositionStage

    monkeypatch.setattr(settings, "proposition_extraction_enabled", True)
    result = await EarlyPropositionStage().execute(
        await _job("The statute requires written notice.")
    )
    assert result.result.propositions == []


@pytest.mark.asyncio
async def test_keyless_lexicon_only_does_not_require_local_model(monkeypatch) -> None:
    from app.pipeline.stages.proposition_stage import EarlyPropositionStage

    monkeypatch.setattr(settings, "proposition_extraction_enabled", True)
    result = await EarlyPropositionStage(llm=None).execute(
        await _job("Defendant argues the search was unlawful.")
    )
    assert len(result.result.propositions) == 1


@pytest.mark.asyncio
async def test_llm_assist_is_routed_through_proposition_task(monkeypatch) -> None:
    import app.pipeline.orchestrator as orchestrator
    from app.pipeline.stages.proposition_stage import EarlyPropositionStage

    fake = FakeLLM()
    calls: list[tuple[str, str]] = []

    def fake_make_llm(provider: str, model: str = ""):
        calls.append((provider, model))
        return fake

    monkeypatch.setattr(settings, "proposition_extraction_enabled", True)
    monkeypatch.setattr(settings, "llm_proposition_provider", "anthropic")
    monkeypatch.setattr(settings, "llm_proposition_model", "claude-proposition")
    monkeypatch.setattr(orchestrator, "_make_llm", fake_make_llm)

    task_llms = orchestrator.TaskLLMs.from_settings(fallback=None)
    assert task_llms.proposition is fake
    assert calls == [("anthropic", "claude-proposition")]
    await EarlyPropositionStage(llm=task_llms.proposition).execute(
        await _job("The statute requires notice.")
    )
    assert len(fake.prompts) == 1


@pytest.mark.asyncio
async def test_llm_assist_builds_and_merges_same_span_different_type(
    monkeypatch,
) -> None:
    from app.pipeline.stages.proposition_stage import EarlyPropositionStage

    text = "Plaintiff contends the statute requires notice."
    content = "the statute requires notice"
    start = text.index(content)
    fake = FakeLLM(response={"propositions": [{
        "start_char": start,
        "end_char": start + len(content),
        "proposition_type": "Factual Statement",
        "asserter_role": "plaintiff",
        "validator_mode": None,
        "disposition": "unresolved",
    }]})
    monkeypatch.setattr(settings, "proposition_extraction_enabled", True)

    result = await EarlyPropositionStage(llm=fake).execute(await _job(text))

    assert len(result.result.propositions) == 2
    assert {item.proposition_type for item in result.result.propositions} == {
        "Factual Statement",
        "Legal Proposition",
    }
    assert len({item.id for item in result.result.propositions}) == 2


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "item",
    [
        {
            "start_char": 0,
            "end_char": 10_000,
            "proposition_type": "Legal Proposition",
        },
        {"start_char": 0, "end_char": 4},
        {
            "start_char": {"not": "an integer"},
            "end_char": 4,
            "proposition_type": "Legal Proposition",
        },
    ],
)
async def test_llm_assist_skips_invalid_items(monkeypatch, item) -> None:
    from app.pipeline.stages.proposition_stage import EarlyPropositionStage

    monkeypatch.setattr(settings, "proposition_extraction_enabled", True)
    result = await EarlyPropositionStage(
        llm=FakeLLM(response={"propositions": [item]})
    ).execute(await _job("The statute requires notice."))

    assert result.result.propositions == []


@pytest.mark.asyncio
async def test_llm_assist_provider_failure_preserves_lexicon_candidates(
    monkeypatch,
) -> None:
    from app.pipeline.stages.proposition_stage import EarlyPropositionStage

    monkeypatch.setattr(settings, "proposition_extraction_enabled", True)
    result = await EarlyPropositionStage(llm=RaisingLLM()).execute(
        await _job("Plaintiff contends the statute requires notice.")
    )

    assert len(result.result.propositions) == 1
    assert result.result.propositions[0].proposition_type == "Legal Proposition"


@pytest.mark.asyncio
async def test_sse_emits_each_proposition_id_once() -> None:
    from folio_propositions import ActorRef, Disposition, Proposition

    from app.services.streaming.sse import job_event_stream

    proposition = Proposition(
        id="prop-1",
        start_char=0,
        end_char=6,
        text="notice",
        proposition_type="Legal Proposition",
        asserter=ActorRef(role="plaintiff"),
        validator=None,
        disposition=Disposition.UNRESOLVED,
    )
    job = Job(
        id=UUID("b415b8ef-bff3-5b0b-a06a-e379bf128c36"),
        status=JobStatus.COMPLETED,
        result=JobResult(propositions=[proposition, deepcopy(proposition)]),
    )

    class Store:
        async def load(self, job_id):
            return job

    events = [event async for event in job_event_stream(job.id, Store(), poll_interval=0)]
    additions = [event for event in events if event["event"] == "proposition_added"]
    assert len(additions) == 1
    assert json.loads(additions[0]["data"])["id"] == "prop-1"
