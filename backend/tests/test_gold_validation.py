from __future__ import annotations

import asyncio
import json
from pathlib import Path
from uuid import UUID

import pytest
from folio_propositions import Disposition

from app.services.gold.store import GoldStore
from app.storage.job_store import JobStore

GOLD_DIR = Path(__file__).resolve().parents[1] / "eval/gold/propositions"
SLUG = "palsgraf-248-ny-339"


def make_store(tmp_path):
    return GoldStore(JobStore(tmp_path / "jobs"), export_dir=tmp_path / "exports")


async def approve(store, session, candidates=None):
    for candidate in session.candidates if candidates is None else candidates:
        await store.record_candidate_outcome(
            session.session_id, candidate.proposition.id, outcome="accepted",
            explicit_unresolved=candidate.explicit_unresolved,
        )


@pytest.mark.asyncio
async def test_validation_approves_final_annotations_and_preserves_originals(tmp_path):
    originals = {path: path.read_bytes() for path in GOLD_DIR.iterdir() if path.is_file()}
    store = make_store(tmp_path)
    store.export_dir.mkdir()
    (store.export_dir / "manifest.json").write_bytes(originals[GOLD_DIR / "manifest.json"])
    session, repeated = await asyncio.gather(
        store.create_validation_session(SLUG), store.create_validation_session(SLUG)
    )
    assert repeated.session_id == session.session_id
    assert session.validation_of == SLUG
    assert session.pre_selector.source == "gold-validation"
    rows = [json.loads(line) for line in (GOLD_DIR / f"{SLUG}.jsonl").read_text().splitlines()]
    annotations = [row for row in rows if row["record_type"] == "annotation"]
    assert len(session.candidates) == len(annotations) == 104
    assert not session.hand_added and not session.cycle_learnings and not session.blind_segment
    for candidate, row in zip(session.candidates, annotations):
        assert candidate.proposition.model_dump(mode="json") == row["proposition"]
        assert candidate.original == candidate.proposition
    await approve(store, session)
    result = await store.export(session.session_id)
    manifest = json.loads(result.manifest.read_text())
    entry = next(item for item in manifest["opinions"] if item["slug"] == f"{SLUG}-validated")
    assert manifest["opinions"][:-1] == json.loads(originals[GOLD_DIR / "manifest.json"])["opinions"]
    assert result.jsonl.name == f"{SLUG}-validated.jsonl"
    assert entry["validation_counts"] == {"approved": 104, "edited": 0, "discarded": 0, "hand_added": 0}
    assert entry["validation_of"] == SLUG
    assert entry["validated_annotator"] == session.validated_annotator
    assert entry["annotator"] == "damien"
    assert entry["text_file"] == f"{SLUG}.txt"
    assert entry["splits"] == next(item for item in store.records() if item["slug"] == SLUG)["splits"]
    bundle = await store.bundle(session.session_id)
    assert bundle["jsonl"] == result.jsonl.read_text()
    assert bundle["ann"] == result.ann.read_text()
    assert bundle["manifest_entry"] == entry
    assert all(path.read_bytes() == data for path, data in originals.items())
    next_session = await store.create_validation_session(SLUG)
    assert next_session.session_id != session.session_id
    for candidate in next_session.candidates:
        await store.record_candidate_outcome(next_session.session_id, candidate.proposition.id, outcome="deleted")
    await store.export(next_session.session_id)
    assert await store.bundle(session.session_id) == bundle
    with pytest.raises(ValueError, match="slug"):
        await store.export(session.session_id, slug=SLUG)


@pytest.mark.asyncio
async def test_validation_recreates_missing_job_and_reuses_existing_job(tmp_path):
    store = make_store(tmp_path)
    session = await store.create_validation_session(SLUG)
    job = await store.job_store.load(UUID(session.job_id))
    assert job.status == "completed"
    assert job.result.canonical_text.full_text == (GOLD_DIR / f"{SLUG}.txt").read_text()
    assert not job.result.propositions
    job.result.metadata["preserve"] = True
    await store.job_store.save(job)
    await store.create_validation_session(SLUG)
    assert (await store.job_store.load(job.id)).result.metadata == {"preserve": True}


@pytest.mark.asyncio
async def test_validation_edits_discards_and_hand_added_counts(tmp_path):
    store = make_store(tmp_path)
    session = await store.create_validation_session(SLUG)
    first, second, *rest = session.candidates
    changed = first.proposition.model_copy(update={"disposition": Disposition.REVISED})
    await store.record_candidate_outcome(session.session_id, first.proposition.id, outcome="edited", proposition=changed)
    await store.record_candidate_outcome(session.session_id, second.proposition.id, outcome="deleted")
    await approve(store, session, rest)
    await store.add_hand_added(session.session_id, first.proposition.model_copy(update={"id": "missed"}))
    result = await store.export(session.session_id)
    bundle = await store.bundle(session.session_id)
    assert bundle["manifest_entry"]["validation_counts"] == {"approved": 102, "edited": 1, "discarded": 1, "hand_added": 1}
    assert bundle["manifest_entry"]["recall_proxy"] == pytest.approx(1 - 1 / 104)
    rows = [json.loads(line) for line in result.jsonl.read_text().splitlines()]
    assert rows[0]["outcome"] == "edited" and rows[0]["edit_kind"] == "field"
    assert rows[1]["record_type"] == "candidate-audit"
    with pytest.raises(ValueError, match="requires edited"):
        await store.record_candidate_outcome(session.session_id, first.proposition.id, outcome="accepted")


@pytest.mark.asyncio
async def test_validation_routes_auth_unknown_and_bundle(tmp_path, monkeypatch, client):
    from app.api.routes import gold
    from app.config import settings

    store = make_store(tmp_path)
    monkeypatch.setattr(gold, "_gold_store", store)
    monkeypatch.setattr(settings, "annotation_token", "review-secret")
    monkeypatch.setattr(settings, "admin_token", "")
    records = await client.get("/gold/records")
    assert records.status_code == 200
    assert [entry["slug"] for entry in records.json()] == [SLUG]
    assert (await client.post("/gold/validation-sessions", json={"slug": SLUG})).status_code == 403
    headers = {"X-Annotation-Token": "review-secret"}
    assert (await client.post("/gold/validation-sessions", json={"slug": "unknown"}, headers=headers)).status_code == 404
    created = await client.post("/gold/validation-sessions", json={"slug": SLUG}, headers=headers)
    assert created.status_code == 201, created.text
    data = created.json()
    repeated = await client.post("/gold/validation-sessions", json={"slug": SLUG}, headers=headers)
    assert repeated.json()["session_id"] == data["session_id"]
    path = f"/gold/sessions/{data['session_id']}/bundle"
    assert (await client.get(path)).status_code == 409
    await approve(store, await store.get(data["session_id"]))
    exported = await client.post(f"/gold/sessions/{data['session_id']}/export", json={}, headers=headers)
    assert exported.status_code == 200, exported.text
    bundle = await client.get(path)
    assert bundle.status_code == 200
    assert bundle.json()["jsonl"] == Path(exported.json()["jsonl"]).read_text()
    assert (await client.get("/gold/sessions/missing/bundle")).status_code == 404


def test_import_bundle_is_idempotent_and_checks_canonical_spans(tmp_path):
    import importlib.util
    from tests.test_proposition_gold_text import _assert_spans

    script = Path(__file__).resolve().parents[2] / "scripts/import_validated_gold.py"
    spec = importlib.util.spec_from_file_location("import_validated_gold", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    gold_dir = tmp_path / "gold"
    gold_dir.mkdir()
    text = "The rule applies."
    (gold_dir / "source.txt").write_text(text)
    original = {"slug": "source", "text_file": "source.txt", "splits": {"development": [0, len(text)]}}
    (gold_dir / "manifest.json").write_text(json.dumps({"manifest_schema_version": 1, "opinions": [original]}))
    proposition = {
        "id": "p1", "schema_version": 3, "proposition_type": "Judicial Legal Conclusion",
        "start_char": 0, "end_char": len(text), "text": text, "disposition": "accepted",
    }
    row = {"record_type": "annotation", "annotation_id": "p1", "proposition": proposition}
    bundle = {
        "session_id": "session", "jsonl": json.dumps(row) + "\n",
        "ann": f"T1\tJUDICIAL_LEGAL_CONCLUSION 0 {len(text)}\t{text}\n",
        "manifest_entry": {"slug": "source-validated", "session_id": "session", "validation_of": "source"},
    }
    module.import_bundle(bundle, gold_dir, session_id="session")
    snapshot = {path.name: path.read_bytes() for path in gold_dir.iterdir()}
    module.import_bundle(bundle, gold_dir, session_id="session")
    assert snapshot == {path.name: path.read_bytes() for path in gold_dir.iterdir()}
    entry = json.loads((gold_dir / "manifest.json").read_text())["opinions"][-1]
    assert entry["text_file"] == original["text_file"]
    assert entry["splits"] == original["splits"]
    rows = [json.loads(line) for line in (gold_dir / "source-validated.jsonl").read_text().splitlines()]
    _assert_spans(text, rows)
    bundle["jsonl"] = bundle["jsonl"].replace("The rule applies.", "Bad rule applies.")
    with pytest.raises(ValueError, match="span"):
        module.import_bundle(bundle, gold_dir, session_id="session")
    assert snapshot == {path.name: path.read_bytes() for path in gold_dir.iterdir()}
