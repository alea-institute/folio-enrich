from __future__ import annotations

import json
from pathlib import Path

import pytest
from folio_propositions import ActorRef, Disposition, Proposition

from app.models.document import CanonicalText, DocumentInput
from app.models.job import Job, JobResult, JobStatus
from app.services.gold.store import GoldStore, PreSelector
from app.services.proposition.extractor import PropositionExtractor
from app.storage.job_store import JobStore


def proposition(prop_id: str, text: str, start: int) -> Proposition:
    return Proposition(
        id=prop_id,
        start_char=start,
        end_char=start + len(text),
        text=text,
        proposition_type="judicial proposition of law",
        asserter=ActorRef(role="court"),
        validator=None,
        disposition=Disposition.ACCEPTED,
    )


async def make_store(tmp_path: Path, candidates: list[Proposition]):
    jobs = JobStore(tmp_path / "jobs")
    text = "0123456789abcdefghijABCDEFGHIJ klmnopqrstuvwxyz"
    job = Job(
        input=DocumentInput(content=text),
        status=JobStatus.COMPLETED,
        result=JobResult(canonical_text=CanonicalText(full_text=text), propositions=candidates),
    )
    await jobs.save(job)
    store = GoldStore(jobs, tmp_path / "gold")
    session = await store.create_session(
        job.id,
        document_id="validity-opinion",
        pre_selector=PreSelector(source="lexicon+llm", llm_provider="test", llm_model="test"),
    )
    return store, jobs, job, session


@pytest.mark.asyncio
async def test_blind_segment_masks_public_payload_but_retains_candidates(tmp_path: Path) -> None:
    hidden = proposition("hidden", "abcdefghij", 10)
    visible = proposition("visible", "klmnop", 31)
    store, _, _, session = await make_store(tmp_path, [hidden, visible])

    masked = await store.set_blind_segment(session.session_id, 8, 25)

    assert masked.blind_pending == 1
    assert [candidate.proposition.id for candidate in masked.candidates] == ["visible"]
    raw = json.loads(store._path(session.session_id).read_text())
    assert [candidate["proposition"]["id"] for candidate in raw["candidates"]] == ["hidden", "visible"]
    assert "hidden" not in masked.model_dump_json()


@pytest.mark.asyncio
async def test_blind_segment_rejects_already_reviewed_candidate(tmp_path: Path) -> None:
    store, _, _, session = await make_store(tmp_path, [proposition("reviewed", "abcdefghij", 10)])
    await store.record_candidate_outcome(session.session_id, "reviewed", outcome="accepted")

    with pytest.raises(ValueError, match="unassisted"):
        await store.set_blind_segment(session.session_id, 8, 25)


@pytest.mark.asyncio
async def test_reveal_blind_segment_returns_and_persists_diff(tmp_path: Path) -> None:
    first = proposition("tool-1", "abcdefghij", 10)
    second = proposition("tool-2", "ABCDEFGHIJ", 20)
    store, _, _, session = await make_store(tmp_path, [first, second])
    await store.set_blind_segment(session.session_id, 8, 40)
    await store.add_hand_added(session.session_id, proposition("hand-match", "fghijABC", 15))
    await store.add_hand_added(session.session_id, proposition("hand-novel", "klmno", 31))

    revealed = await store.reveal_blind_segment(session.session_id)
    report = revealed.blind_diff_report

    assert revealed.blind_revealed_at is not None
    assert revealed.blind_pending == 0
    assert len(revealed.candidates) == 2
    assert len(report["matched_pairs"]) == 1
    assert len(report["tool_only"]) == 1
    assert len(report["annotator_only"]) == 1
    assert report["anchoring_loss"] == {
        "tool_count": 2,
        "annotator_count": 2,
        "matched_count": 1,
        "tool_only_count": 1,
        "annotator_only_count": 1,
        "match_fraction": 0.5,
        "tool_miss_fraction": 0.5,
        "annotator_novel_fraction": 0.5,
        "anchoring_loss_fraction": 0.5,
    }
    persisted = json.loads(store._path(session.session_id).read_text())
    assert persisted["blind_diff_report"] == report


@pytest.mark.asyncio
async def test_completeness_requires_outcomes_coverage_and_blind_reveal(tmp_path: Path) -> None:
    store, _, _, session = await make_store(tmp_path, [proposition("tool", "abcdefghij", 10)])
    await store.set_blind_segment(session.session_id, 8, 25)
    initial = await store.completeness(session.session_id)
    assert initial == {
        "complete": False,
        "reasons": [
            "1 candidate(s) remain unreviewed",
            "full-text coverage pass has not been recorded",
            "blind segment has not been revealed",
        ],
    }

    await store.record_coverage_pass(session.session_id)
    await store.reveal_blind_segment(session.session_id)
    await store.record_candidate_outcome(session.session_id, "tool", outcome="deleted")

    assert await store.completeness(session.session_id) == {"complete": True, "reasons": []}
    exported = await store.export(session.session_id, "blind-complete")
    records = [json.loads(line) for line in exported.jsonl.read_text().splitlines()]
    blind_record = next(record for record in records if record["record_type"] == "blind-segment")
    assert blind_record["diff_report"]["anchoring_loss"]["tool_only_count"] == 1
    manifest = json.loads(exported.manifest.read_text())
    entry = next(item for item in manifest["opinions"] if item["slug"] == "blind-complete")
    assert entry["blind_segment"] is True
    assert entry["baseline"] is False
    assert entry["completeness"] == {"complete": True, "reasons": []}


@pytest.mark.asyncio
async def test_coverage_pass_is_never_implicit_on_create_or_export(tmp_path: Path) -> None:
    store, _, _, session = await make_store(tmp_path, [proposition("tool", "abcdefghij", 10)])
    assert session.coverage_pass_completed_at is None
    await store.record_candidate_outcome(session.session_id, "tool", outcome="accepted")
    await store.export(session.session_id, "explicit-coverage")
    assert (await store.get(session.session_id)).coverage_pass_completed_at is None


@pytest.mark.asyncio
async def test_baseline_session_forces_lexicon_only_and_reseeds_deterministically(tmp_path: Path) -> None:
    jobs = JobStore(tmp_path / "jobs")
    text = "We hold that the rule applies."
    job = Job(
        input=DocumentInput(content=text),
        status=JobStatus.COMPLETED,
        result=JobResult(canonical_text=CanonicalText(full_text=text)),
    )
    deterministic = PropositionExtractor().extract(job)
    job.result.propositions = [*deterministic, proposition("llm-extra", "rule", 17)]
    await jobs.save(job)
    store = GoldStore(jobs, tmp_path / "gold")

    session = await store.create_session(
        job.id,
        pre_selector=PreSelector(source="lexicon+llm", llm_provider="test", llm_model="test"),
        baseline=True,
    )

    assert session.baseline is True
    assert session.pre_selector.source == "lexicon-only"
    assert session.pre_selector.llm_provider is None
    assert session.pre_selector.llm_model is None
    assert [item.proposition for item in session.candidates] == deterministic


@pytest.mark.asyncio
async def test_keyless_baseline_candidates_equal_job_propositions(tmp_path: Path) -> None:
    jobs = JobStore(tmp_path / "jobs")
    text = "We hold that the rule applies."
    job = Job(
        input=DocumentInput(content=text),
        status=JobStatus.COMPLETED,
        result=JobResult(canonical_text=CanonicalText(full_text=text)),
    )
    job.result.propositions = PropositionExtractor().extract(job)
    await jobs.save(job)
    store = GoldStore(jobs, tmp_path / "gold")

    session = await store.create_session(
        job.id, pre_selector=PreSelector(source="lexicon-only"), baseline=True
    )

    assert [item.proposition for item in session.candidates] == job.result.propositions


@pytest.mark.asyncio
async def test_validity_routes_expose_actions_and_masking(tmp_path: Path, monkeypatch, client) -> None:
    from app.api.routes import gold

    jobs = JobStore(tmp_path / "jobs")
    text = "We hold that the rule applies."
    job = Job(
        input=DocumentInput(content=text),
        status=JobStatus.COMPLETED,
        result=JobResult(
            canonical_text=CanonicalText(full_text=text),
            propositions=[proposition("tool", "rule", 17)],
        ),
    )
    await jobs.save(job)
    monkeypatch.setattr(gold, "_job_store", jobs)
    monkeypatch.setattr(gold, "_gold_store", GoldStore(jobs, tmp_path / "gold"))
    created = await client.post(
        "/gold/sessions",
        json={
            "job_id": str(job.id),
            "baseline": False,
            "pre_selector": {"source": "lexicon-only"},
        },
    )
    assert created.status_code == 201, created.text
    session_id = created.json()["session_id"]

    blinded = await client.post(
        f"/gold/sessions/{session_id}/blind-segment",
        json={"start_char": 15, "end_char": 24},
    )
    assert blinded.status_code == 200, blinded.text
    assert blinded.json()["blind_pending"] == 1
    assert blinded.json()["candidates"] == []
    completeness = await client.get(f"/gold/sessions/{session_id}/completeness")
    assert completeness.status_code == 200
    assert completeness.json()["complete"] is False
    assert (await client.post(f"/gold/sessions/{session_id}/coverage-pass")).status_code == 200
    revealed = await client.post(f"/gold/sessions/{session_id}/blind-segment/reveal")
    assert revealed.status_code == 200, revealed.text
    assert len(revealed.json()["candidates"]) == 1
