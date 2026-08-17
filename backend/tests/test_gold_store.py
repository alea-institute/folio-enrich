from __future__ import annotations

import asyncio
import json
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from folio_propositions import SCHEMA_VERSION, ActorRef, Disposition, Proposition

from app.models.document import CanonicalText, DocumentInput
from app.models.job import Job, JobResult, JobStatus
from app.storage.job_store import JobStore


def proposition(
    prop_id: str,
    text: str = "the rule applies",
    start: int = 3,
    disposition: Disposition = Disposition.ACCEPTED,
) -> Proposition:
    return Proposition(
        id=prop_id,
        start_char=start,
        end_char=start + len(text),
        text=text,
        proposition_type="Judicial Legal Conclusion",
        asserter=ActorRef(role="court"),
        validator=None,
        disposition=disposition,
    )


async def make_store(tmp_path: Path, propositions: list[Proposition]):
    from app.services.gold.store import GoldStore, PreSelector

    jobs = JobStore(tmp_path / "jobs")
    text = "We hold that the rule applies. " + "word " * 194
    job = Job(
        input=DocumentInput(content=text),
        status=JobStatus.COMPLETED,
        result=JobResult(
            canonical_text=CanonicalText(full_text=text),
            propositions=propositions,
        ),
    )
    await jobs.save(job)
    store = GoldStore(job_store=jobs, export_dir=tmp_path / "gold")
    session = await store.create_session(
        job.id,
        document_id="opinion-1",
        pre_selector=PreSelector(source="lexicon-only", lexicon_version="test-v1"),
    )
    return store, jobs, job, session


@pytest.mark.asyncio
async def test_deleted_trail_metrics_and_hand_added_recall(tmp_path: Path) -> None:
    from app.services.gold.store import precision_from_record, recall_proxy_from_record

    store, _, _, session = await make_store(
        tmp_path, [proposition("p1"), proposition("p2", "the claim fails", 40)]
    )
    await store.record_candidate_outcome(session.session_id, "p1", outcome="accepted")
    await store.record_candidate_outcome(session.session_id, "p2", outcome="deleted")
    await store.add_hand_added(session.session_id, proposition("p3", "notice is required", 70))
    result = await store.export(session.session_id, slug="metrics")
    records = [json.loads(line) for line in result.jsonl.read_text().splitlines()]
    assert next(r for r in records if r.get("annotation_id") == "p2")["audit"] == "deleted-candidate"
    assert next(r for r in records if r.get("annotation_id") == "p3")["provenance"] == "hand-added"
    assert precision_from_record(records) == pytest.approx(0.5)
    assert recall_proxy_from_record(records) == pytest.approx(0.5)


@pytest.mark.asyncio
async def test_export_gate_and_manifest_density(tmp_path: Path) -> None:
    store, _, _, session = await make_store(
        tmp_path, [proposition("p1"), proposition("p2", "the claim fails", 40)]
    )
    await store.record_candidate_outcome(session.session_id, "p1", outcome="accepted")
    with pytest.raises(ValueError, match="1 unreviewed"):
        await store.export(session.session_id, slug="blocked")
    await store.record_candidate_outcome(session.session_id, "p2", outcome="deleted")
    await store.add_learning(
        session.session_id, kind="new-type", tag="novel", annotation_id="p2", note="observe"
    )
    result = await store.export(session.session_id, slug="complete")
    assert result.jsonl.exists() and result.ann.exists() and result.manifest.exists()
    manifest = json.loads(result.manifest.read_text())
    entry = next(item for item in manifest["opinions"] if item["slug"] == "complete")
    assert entry["counts"] == {"accepted": 1, "edited": 0, "deleted": 1, "unreviewed": 0}
    assert entry["density"]["opinion"] == pytest.approx(5.0)


@pytest.mark.asyncio
async def test_unresolved_requires_explicit_annotator_action(tmp_path: Path) -> None:
    store, _, _, session = await make_store(tmp_path, [proposition("p1")])
    unresolved = proposition("p1", disposition=Disposition.UNRESOLVED)
    with pytest.raises(ValueError, match="explicit_unresolved"):
        await store.record_candidate_outcome(
            session.session_id, "p1", outcome="edited", proposition=unresolved
        )
    updated = await store.record_candidate_outcome(
        session.session_id,
        "p1",
        outcome="edited",
        proposition=unresolved,
        explicit_unresolved=True,
    )
    assert updated.candidates[0].explicit_unresolved is True


@pytest.mark.asyncio
async def test_selector_configs_and_edit_kinds(tmp_path: Path) -> None:
    from app.services.gold.store import PreSelector

    store, jobs, job, session = await make_store(tmp_path, [proposition("p1")])
    assisted = await store.create_session(
        job.id,
        document_id="opinion-2",
        pre_selector=PreSelector(
            source="lexicon+llm", lexicon_config={"strict": True}, llm_provider="openai", llm_model="x"
        ),
    )
    assert session.pre_selector.source != assisted.pre_selector.source
    field = proposition("p1")
    field.disposition = Disposition.REVISED
    updated = await store.record_candidate_outcome(
        session.session_id, "p1", outcome="edited", proposition=field
    )
    assert updated.candidates[0].edit_kind == "field"
    boundary = proposition("p1", text="he rule applies", start=4)
    updated = await store.record_candidate_outcome(
        session.session_id, "p1", outcome="edited", proposition=boundary
    )
    assert updated.candidates[0].edit_kind == "boundary"


@pytest.mark.asyncio
async def test_concurrent_candidate_updates_preserve_both_outcomes(tmp_path: Path) -> None:
    store, _, _, session = await make_store(
        tmp_path, [proposition("p1"), proposition("p2", "the claim fails", 40)]
    )

    await asyncio.gather(
        store.record_candidate_outcome(session.session_id, "p1", outcome="accepted"),
        store.record_candidate_outcome(session.session_id, "p2", outcome="deleted"),
    )

    persisted = await store.get(session.session_id)
    assert {candidate.proposition.id: candidate.outcome for candidate in persisted.candidates} == {
        "p1": "accepted",
        "p2": "deleted",
    }


@pytest.mark.asyncio
async def test_default_export_slug_is_unique_per_session_and_reexport_is_idempotent(
    tmp_path: Path,
) -> None:
    from app.services.gold.store import PreSelector

    store, _, job, first = await make_store(tmp_path, [proposition("p1")])
    second = await store.create_session(
        job.id,
        document_id=first.document_id,
        pre_selector=PreSelector(source="lexicon-only"),
    )
    await store.record_candidate_outcome(first.session_id, "p1", outcome="accepted")
    await store.record_candidate_outcome(second.session_id, "p1", outcome="deleted")

    first_export = await store.export(first.session_id)
    second_export = await store.export(second.session_id)
    repeated = await store.export(first.session_id)

    assert first_export.jsonl != second_export.jsonl
    assert repeated.jsonl == first_export.jsonl
    opinions = json.loads(repeated.manifest.read_text())["opinions"]
    assert {item["session_id"] for item in opinions} == {first.session_id, second.session_id}
    assert len(opinions) == 2


def test_wrapper_and_payload_migrations_are_separate() -> None:
    from app.services.gold.store import migrate_session, migrate_proposition_payload

    payload = proposition("p1").model_dump(mode="json")
    wrapped = {
        "wrapper_schema_version": 1,
        "candidates": [{"proposition": deepcopy(payload), "original": deepcopy(payload)}],
        "hand_added": [],
    }
    migrated = migrate_session(wrapped, 2)
    assert migrated["wrapper_schema_version"] == 2
    assert migrated["provenance_model"] == "origin+outcome"
    assert migrated["candidates"][0]["proposition"] == payload
    assert migrate_proposition_payload(payload, target_version=payload["schema_version"]) == payload


def test_library_migration_hook_receives_payload(monkeypatch) -> None:
    import app.services.gold.store as gold_store

    payload = proposition("p1").model_dump(mode="json")
    calls = []

    def fake_migrate(record, target_version):
        calls.append((deepcopy(record), target_version))
        return {**record, "schema_version": target_version}

    monkeypatch.setattr(gold_store, "migrate_record", fake_migrate)
    assert gold_store.migrate_proposition_payload(payload, 2)["schema_version"] == 2
    assert calls == [(payload, 2)]


@pytest.mark.asyncio
async def test_session_save_upgrades_v2_payloads_and_session_stamp(tmp_path: Path) -> None:
    store, _, _, session = await make_store(tmp_path, [proposition("p1")])
    path = store._path(session.session_id)
    raw = json.loads(path.read_text())
    raw["schema_version"] = 2
    for key in ("proposition", "original"):
        raw["candidates"][0][key]["schema_version"] = 2
        raw["candidates"][0][key]["proposition_type"] = (
            "judicial proposition of law"
        )
    path.write_text(json.dumps(raw))

    updated = await store.record_candidate_outcome(
        session.session_id, "p1", outcome="accepted"
    )

    assert updated.schema_version == SCHEMA_VERSION == 3
    assert updated.candidates[0].proposition.proposition_type == (
        "Judicial Legal Conclusion"
    )
    persisted = json.loads(path.read_text())
    assert persisted["schema_version"] == 3
    assert persisted["candidates"][0]["original"]["schema_version"] == 3


def test_proposition_brat_attributes_and_empty_output() -> None:
    from app.services.export.brat_exporter import BratExporter

    assert BratExporter.export_propositions([]) == ""
    output = BratExporter.export_propositions([proposition("p1")])
    assert "T1\tJUDICIAL_LEGAL_CONCLUSION 3 19\tthe rule applies" in output
    assert "Asserter T1 court" in output
    assert "Disposition T1 accepted" in output


@pytest.mark.asyncio
async def test_cleanup_protected_until_export(tmp_path: Path) -> None:
    store, jobs, job, session = await make_store(tmp_path, [proposition("p1")])
    job.updated_at = datetime.now(timezone.utc) - timedelta(days=40)
    await jobs.save(job)
    assert await jobs.cleanup_expired(retention_days=30) == 0
    await store.record_candidate_outcome(session.session_id, "p1", outcome="accepted")
    await store.export(session.session_id, slug="retention")
    assert await jobs.cleanup_expired(retention_days=30) == 1


@pytest.mark.asyncio
async def test_route_happy_path(tmp_path: Path, monkeypatch, client) -> None:
    from app.api.routes import gold
    from app.services.gold.store import GoldStore

    jobs = JobStore(tmp_path / "jobs")
    store = GoldStore(jobs, tmp_path / "gold")
    monkeypatch.setattr(gold, "_job_store", jobs)
    monkeypatch.setattr(gold, "_gold_store", store)
    job = Job(
        input=DocumentInput(content="We hold that the rule applies."),
        status=JobStatus.COMPLETED,
        result=JobResult(
            canonical_text=CanonicalText(full_text="We hold that the rule applies."),
            propositions=[proposition("p1")],
        ),
    )
    await jobs.save(job)
    created = await client.post(
            "/gold/sessions",
            json={
                "job_id": str(job.id),
                "document_id": "route-opinion",
                "pre_selector": {"source": "lexicon-only", "lexicon_version": "v1"},
            },
    )
    assert created.status_code == 201, created.text
    session_id = created.json()["session_id"]
    patched = await client.patch(
        f"/gold/sessions/{session_id}/candidates/p1", json={"outcome": "accepted"}
    )
    assert patched.status_code == 200, patched.text
    exported = await client.post(f"/gold/sessions/{session_id}/export", json={"slug": "route"})
    assert exported.status_code == 200, exported.text
    assert Path(exported.json()["jsonl"]).exists()


@pytest.mark.asyncio
async def test_gold_mutations_require_configured_admin_token(
    tmp_path: Path, monkeypatch, client
) -> None:
    from app.api.routes import gold
    from app.config import settings
    from app.services.gold.store import GoldStore

    jobs = JobStore(tmp_path / "jobs")
    monkeypatch.setattr(gold, "_job_store", jobs)
    monkeypatch.setattr(gold, "_gold_store", GoldStore(jobs, tmp_path / "gold"))
    job = Job(
        input=DocumentInput(content="We hold that the rule applies."),
        status=JobStatus.COMPLETED,
        result=JobResult(canonical_text=CanonicalText(full_text="We hold that the rule applies.")),
    )
    await jobs.save(job)
    payload = {
        "job_id": str(job.id),
        "pre_selector": {"source": "lexicon-only"},
    }

    monkeypatch.setattr(settings, "admin_token", "s3cret")
    assert (await client.post("/gold/sessions", json=payload)).status_code == 403
    assert (
        await client.post("/gold/sessions", json=payload, headers={"X-Admin-Token": "s3cret"})
    ).status_code == 201

    monkeypatch.setattr(settings, "admin_token", "")
    assert (await client.post("/gold/sessions", json=payload)).status_code == 201
