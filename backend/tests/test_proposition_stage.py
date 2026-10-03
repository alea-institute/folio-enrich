from __future__ import annotations

import json
from copy import deepcopy
from uuid import UUID

import pytest
from folio_propositions import WORKING_TAXONOMY

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
        self.schemas: list[dict] = []

    async def structured(self, prompt: str, schema: dict, **kwargs) -> dict:
        self.prompts.append(prompt)
        self.schemas.append(schema)
        return self.response


class RaisingLLM(FakeLLM):
    async def structured(self, prompt: str, schema: dict, **kwargs) -> dict:
        self.prompts.append(prompt)
        raise RuntimeError("provider unavailable")


def test_every_lexicon_frame_uses_the_working_taxonomy() -> None:
    from app.services.proposition.lexicon import REPORTING_VERBS

    assert {
        frame.proposition_type for frame in REPORTING_VERBS.values()
    } <= set(WORKING_TAXONOMY)


@pytest.mark.asyncio
async def test_flag_off_returns_job_unchanged(monkeypatch) -> None:
    from app.pipeline.stages.proposition_stage import EarlyPropositionStage

    monkeypatch.setattr(settings, "proposition_extraction_enabled", False)
    job = await _job("Plaintiff contends the statute requires notice.")
    job.result.metadata["proposition_lexicon_version"] = "older-version"
    job.result.metadata["unrelated"] = "preserved"
    before = job.model_dump(mode="json")
    result = await EarlyPropositionStage().execute(job)
    assert result is job
    assert result.model_dump(mode="json") == before
    assert result.result.propositions == []


@pytest.mark.asyncio
async def test_flag_on_records_extraction_lexicon_version(monkeypatch) -> None:
    from app.pipeline.stages.proposition_stage import EarlyPropositionStage
    from app.services.proposition.lexicon import LEXICON_VERSION

    monkeypatch.setattr(settings, "proposition_extraction_enabled", True)
    job = await _job("We hold that the contract is void.")
    job.result.metadata["unrelated"] = "preserved"
    result = await EarlyPropositionStage().execute(job)
    assert result.result.metadata["proposition_lexicon_version"] == LEXICON_VERSION
    assert result.result.metadata["unrelated"] == "preserved"


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
        (
            "The Restatement states that duty exists.",
            "cited-authority proposition",
            "secondary_source",
            "duty exists",
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
    item_schema = fake.schemas[0]["properties"]["propositions"]["items"]
    assert item_schema["properties"]["proposition_type"]["enum"] == list(
        WORKING_TAXONOMY
    )
    assert "Allowed proposition types:" in fake.prompts[0]


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


def _extract(text):
    from app.models.document import CanonicalText
    from app.services.proposition.extractor import PropositionExtractor

    return PropositionExtractor().extract(Job(
        id=UUID('b415b8ef-bff3-5b0b-a06a-e379bf128c36'),
        result=JobResult(canonical_text=CanonicalText(full_text=text)),
    ))


@pytest.mark.parametrize('text, content', [
    ('The plaintiff has no claim that the guard was negligent.', 'The plaintiff has no claim that the guard was negligent'),
    ('No reasonable person would suggest that the guard was negligent.', 'No reasonable person would suggest that the guard was negligent'),
    ('We do not hold that the contract is void.', 'We do not hold that the contract is void'),
    ('The plaintiff never contends that notice was given.', 'The plaintiff never contends that notice was given'),
    ('The plaintiff denies that notice was given.', 'The plaintiff denies that notice was given'),
    ('The plaintiff contends that notice was not given.', 'notice was not given'),
    ('The plaintiff contends that notice was given.', 'notice was given'),
])
def test_reporting_negation_keeps_governing_clause(text, content):
    propositions = _extract(text)
    assert len(propositions) == 1
    assert propositions[0].text == content
    assert text[propositions[0].start_char:propositions[0].end_char] == content


def test_negation_in_outer_clause_drops_reporting_candidate():
    assert _extract('It is not true that the plaintiff contends that notice was given.') == []


@pytest.mark.parametrize('text, pattern', [
    ('Negligence is not actionable unless it violates a right.', 'copular-definition'),
    ('The risk reasonably to be perceived defines the duty to be obeyed.', 'copular-definition'),
    ('A defendant is liable for foreseeable harm.', 'modal-deontic'),
    ('A carrier is bound to exercise care.', 'modal-deontic'),
    ('A carrier owes a duty to passengers.', 'modal-deontic'),
    ('The claimant must establish a breach of duty.', 'modal-deontic'),
    ('A claimant may not recover twice.', 'modal-deontic'),
    ('A claimant cannot recover twice.', 'modal-deontic'),
    ('There must be a duty to the claimant.', 'existential-obligation'),
    ('One who seeks redress must establish a wrong.', 'generic-rule'),
    ('If a person breaches a duty, that person is liable for the harm.', 'generic-rule'),
])
def test_assertion_frames(text, pattern):
    propositions = _extract(text)
    assert len(propositions) == 1
    p = propositions[0]
    assert p.text == text.rstrip('.')
    assert p.pattern_name == pattern
    assert p.proposition_type == 'Judicial Legal Conclusion'
    assert p.asserter.role.value == 'court'
    assert p.validator.mode.value == 'ruled'
    assert p.disposition.value == 'accepted'
    assert 'pattern_name' not in p.model_dump()


@pytest.mark.parametrize('text', [
    'It is so.',
    'The train stopped at the station.',
    'The carrier paid the claimant.',
    'There was a parcel on the platform.',
    'One passenger boarded the train.',
    'If John arrived, Mary waved.',
    'Is negligence actionable?',
    'The writer copied "The Law of Torts."',
])
def test_assertion_frame_negative_fixtures(text):
    assert _extract(text) == []


def test_assertion_parse_is_single_and_patterns_do_not_change_json(monkeypatch):
    import app.services.proposition.extractor as module
    nlp = module.get_spacy_nlp()
    calls = []

    def parse(text):
        calls.append(text)
        return nlp(text)

    monkeypatch.setattr(module, 'get_spacy_nlp', lambda: parse)
    text = 'A claimant cannot recover twice. Negligence is a breach of duty.'
    first = _extract(text)
    second = _extract(text)
    assert calls == [text, text]
    assert len(first) == 2
    assert [p.model_dump_json() for p in first] == [p.model_dump_json() for p in second]
    assert all('pattern_name' not in p.model_dump_json() for p in first)


@pytest.mark.parametrize('text, content, role, pattern', [
    ('"Negligence is the absence of care, according to the circumstances" (Willes, J., in Vaughan v. Taff Vale Ry. Co., 5 H. & N. 679, 688).',
     'Negligence is the absence of care, according to the circumstances', 'secondary_source', 'quoted-authority'),
    ('"A claimant must establish a duty" (Smith v. Jones, 12 N.Y. 34).',
     'A claimant must establish a duty', 'secondary_source', 'quoted-authority'),
    ('The Restatement explains: “A carrier owes a duty of care.”',
     'A carrier owes a duty of care', 'secondary_source', 'quoted-authority'),
    ('The judge said, "A claimant cannot recover twice."',
     'A claimant cannot recover twice', 'secondary_source', 'quoted-authority'),
    ('"A claimant must establish a duty."',
     'A claimant must establish a duty', 'court', 'quoted-court'),
    ('"Negligence is not actionable without harm" (Treatise on Torts, p. 25).',
     'Negligence is not actionable without harm', 'secondary_source', 'quoted-authority'),
    ('"The claimant is not entitled to recover."',
     'The claimant is not entitled to recover', 'court', 'quoted-court'),
])
def test_quoted_assertions(text, content, role, pattern):
    propositions = _extract(text)
    assert len(propositions) == 1
    p = propositions[0]
    assert p.text == content
    assert p.asserter.role.value == role
    assert p.pattern_name == pattern
    expected_type = 'cited-authority proposition' if role == 'secondary_source' else 'Judicial Legal Conclusion'
    assert p.proposition_type == expected_type
    assert text[p.start_char:p.end_char] == content
    assert 'pattern_name' not in p.model_dump_json()


@pytest.mark.parametrize('text', [
    '"negligence" (Smith v. Jones, 12 N.Y. 34).',
    '"The Law of Torts" (Treatise, p. 20).',
    '"To exercise care" (Smith v. Jones, 12 N.Y. 34).',
    'The court did not say "A claimant is liable."',
])
def test_quoted_nonassertions_and_outer_negation_are_not_emitted(text):
    assert _extract(text) == []


def test_dissenting_court_assertion_keeps_judge_identity():
    text = 'RIVERA, J. (dissenting):\n\nNegligence is a breach of duty.'
    propositions = _extract(text)
    assert len(propositions) == 1
    assert propositions[0].asserter.role.value == 'court'
    assert propositions[0].asserter.name == 'RIVERA (dissenting)'
    assert propositions[0].proposition_type == 'Judicial Legal Conclusion'


def test_every_new_frame_uses_existing_taxonomy_and_serializes_without_diagnostics():
    from folio_propositions import ActorRef, AdjudicatorRef
    from app.services.proposition.lexicon import ASSERTION_FRAMES, QUOTED_AUTHORITY_FRAME, QUOTED_COURT_FRAME

    for frame in [*ASSERTION_FRAMES.values(), QUOTED_AUTHORITY_FRAME, QUOTED_COURT_FRAME]:
        assert frame.proposition_type in WORKING_TAXONOMY
        ActorRef(role=frame.asserter_role)
        if frame.validator_mode:
            AdjudicatorRef(role='court', mode=frame.validator_mode)
    p = _extract('Negligence is a breach of duty.')[0]
    job = Job(result=JobResult(propositions=[p]))
    assert 'pattern_name' not in job.model_dump_json()
    assert 'frame' not in p.model_dump()


def test_inch_mark_does_not_swallow_modal_or_quoted_argue_complement():
    text = ('The board was 6" wide. A carrier must exercise care. '
            'The plaintiff argues that "the rule is clear." We hold that a duty exists.')
    propositions = _extract(text)
    assert any(p.text == 'A carrier must exercise care' and p.pattern_name == 'modal-deontic'
               for p in propositions)
    assert any('the rule is clear' in p.text and p.proposition_type == 'Legal Proposition'
               and p.asserter.role.value == 'plaintiff' for p in propositions)
    inch = text.index('"')
    assert not any(getattr(p, 'pattern_name', None) == 'quoted-court'
                   and p.start_char <= inch + 1 < p.end_char for p in propositions)


@pytest.mark.parametrize('text', [
    'An unclosed "fragment.\n\nA carrier must exercise care. "',
    'An unclosed "fragment. It ended. Another passed. A carrier must exercise care. "',
])
def test_straight_quotes_cannot_cross_paragraph_or_sentence_cap(text):
    propositions = _extract(text)
    assert any(getattr(p, 'pattern_name', None) == 'modal-deontic' for p in propositions)
    assert not any(getattr(p, 'pattern_name', None) == 'quoted-court' for p in propositions)


def test_straight_quote_can_span_three_sentences():
    text = '"A carrier must exercise care. The duty is clear. A claimant may recover."'
    propositions = _extract(text)
    assert len(propositions) == 1
    assert propositions[0].pattern_name == 'quoted-court'


def test_rejected_unclosed_quote_does_not_consume_next_valid_quote():
    text = ('An unclosed "fragment. It ended. Another passed. A carrier must exercise care. '
            'The text says "A claimant may recover."')
    propositions = _extract(text)
    assert any(getattr(p, 'pattern_name', None) == 'modal-deontic' for p in propositions)
    assert any(p.text == 'A claimant may recover' and p.pattern_name == 'quoted-authority'
               for p in propositions)
