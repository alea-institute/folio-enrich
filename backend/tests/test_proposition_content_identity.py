"""Cross-document proposition identity (content IRIs shared with folio-insights)."""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import quote

import pytest
from fastapi.testclient import TestClient
from folio_propositions import (
    ActorRef,
    Proposition,
    content_iri,
    document_source_uri,
)

from app.config import settings
from app.models.document import CanonicalText, DocumentInput
from app.models.job import Job, JobResult, JobStatus
from app.pipeline.stages.proposition_stage import EarlyPropositionStage
from app.services.proposition.identity import proposition_id
from app.services.proposition.source import (
    SOURCE_URI_METADATA_KEY,
    job_source_uri,
    stamped_propositions,
    validate_source_uri,
)
from app.storage.job_store import JobStore

TEXT = "Plaintiff contends the statute requires notice."
SOURCE = "https://example.org/opinions/notice"


def _job(text: str = TEXT, source_uri: str | None = None) -> Job:
    return Job(
        input=DocumentInput(content=text, source_uri=source_uri),
        result=JobResult(canonical_text=CanonicalText(full_text=text)),
    )


async def _extract(monkeypatch, job: Job) -> Job:
    monkeypatch.setattr(settings, "proposition_extraction_enabled", True)
    return await EarlyPropositionStage(llm=None).execute(job)


@pytest.mark.asyncio
async def test_same_text_two_jobs_share_content_iris_not_ids(monkeypatch):
    first = await _extract(monkeypatch, _job())
    second = await _extract(monkeypatch, _job())

    assert first.result.propositions, "fixture text must yield propositions"
    assert len(first.result.propositions) == len(second.result.propositions)
    first_ids = [p.id for p in first.result.propositions]
    second_ids = [p.id for p in second.result.propositions]
    assert set(first_ids).isdisjoint(second_ids)
    assert [p.content_iri for p in first.result.propositions] == [
        p.content_iri for p in second.result.propositions
    ]
    uri = document_source_uri(TEXT)
    assert first.result.metadata[SOURCE_URI_METADATA_KEY] == uri
    for proposition in first.result.propositions:
        assert proposition.content_iri == content_iri(uri, proposition.text)
        # The legacy job-scoped uuid5 stays the proposition id.
        assert proposition.id == proposition_id(
            first.id, proposition.start_char, proposition.end_char,
            proposition.proposition_type,
        )


@pytest.mark.asyncio
async def test_caller_source_uri_changes_content_iris(monkeypatch):
    default = await _extract(monkeypatch, _job())
    supplied = await _extract(monkeypatch, _job(source_uri=SOURCE))

    assert supplied.result.metadata[SOURCE_URI_METADATA_KEY] == SOURCE
    default_iris = {p.content_iri for p in default.result.propositions}
    supplied_iris = {p.content_iri for p in supplied.result.propositions}
    assert supplied_iris and default_iris.isdisjoint(supplied_iris)
    for proposition in supplied.result.propositions:
        assert proposition.content_iri == content_iri(SOURCE, proposition.text)


def test_job_source_uri_precedence():
    job = _job()
    assert job_source_uri(job) == document_source_uri(TEXT)
    job.result.metadata[SOURCE_URI_METADATA_KEY] = "urn:example:recorded"
    assert job_source_uri(job) == "urn:example:recorded"
    job.input.source_uri = SOURCE
    assert job_source_uri(job) == SOURCE
    empty = Job(input=DocumentInput(content=""))
    assert job_source_uri(empty) == f"urn:uuid:{empty.id}"


@pytest.mark.parametrize("value", ["", "   ", "no-scheme", "x:" + "a" * 2047, "http://[::1", "http://[::1/x"])
def test_validate_source_uri_rejects(value):
    with pytest.raises(ValueError):
        validate_source_uri(value)


def test_enrich_request_validates_source_uri():
    from pydantic import ValidationError

    from app.api.routes.enrich import EnrichRequest

    assert EnrichRequest(content="x", source_uri=SOURCE).source_uri == SOURCE
    assert EnrichRequest(content="x").source_uri is None
    with pytest.raises(ValidationError):
        EnrichRequest(content="x", source_uri="not a uri")


def test_document_input_omits_unset_source_uri():
    assert "source_uri" not in DocumentInput(content="x").model_dump()
    assert DocumentInput(content="x", source_uri=SOURCE).model_dump()["source_uri"] == SOURCE
    restored = DocumentInput.model_validate_json(
        DocumentInput(content="x", source_uri=SOURCE).model_dump_json()
    )
    assert restored.source_uri == SOURCE


def _write_v3_job(store: JobStore, text: str = TEXT) -> Job:
    """Persist a job shaped like a pre-0.4.0 (schema v3) job file."""
    job = Job(
        status=JobStatus.COMPLETED,
        input=DocumentInput(content=text),
        result=JobResult(canonical_text=CanonicalText(full_text=text)),
    )
    path = store._job_path(job.id)
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = json.loads(job.model_dump_json())
    span = "the statute requires notice"
    start = text.index(span)
    raw["result"]["propositions"] = [
        {
            "id": proposition_id(job.id, start, start + len(span), kind),
            "schema_version": 3,
            "start_char": start,
            "end_char": start + len(span),
            "text": span,
            "proposition_type": kind,
            "asserter": {"role": "plaintiff"},
            "validator": None,
            "disposition": "unresolved",
        }
        for kind in ("Factual Statement", "Legal Proposition")
    ]
    path.write_text(json.dumps(raw))
    return job


@pytest.mark.asyncio
async def test_old_v3_job_loads_and_stamps_lazily(tmp_path: Path):
    store = JobStore(base_dir=tmp_path / "jobs")
    job = _write_v3_job(store)
    before = store._job_path(job.id).read_bytes()

    loaded = await store.load(job.id)
    assert loaded is not None
    assert all(p.schema_version == 4 for p in loaded.result.propositions)
    assert all(p.content_iri is None for p in loaded.result.propositions)

    stamped = stamped_propositions(loaded)
    expected = content_iri(document_source_uri(TEXT), "the statute requires notice")
    assert [p.content_iri for p in stamped] == [expected, expected]
    # Read-side stamping never rewrites the stored job.
    assert store._job_path(job.id).read_bytes() == before
    assert all(p.content_iri is None for p in loaded.result.propositions)


@pytest.fixture
def api(tmp_path: Path, monkeypatch):
    import app.api.routes.enrich as enrich_mod
    from app.main import app

    store = JobStore(base_dir=tmp_path / "jobs")
    monkeypatch.setattr(enrich_mod, "_job_store", store)
    return TestClient(app), store


def test_lookup_by_uuid5_and_by_content_iri(api):
    client, store = api
    job = _write_v3_job(store)
    raw = json.loads(store._job_path(job.id).read_text())
    first_id = raw["result"]["propositions"][0]["id"]
    iri = content_iri(document_source_uri(TEXT), "the statute requires notice")

    by_id = client.get(f"/enrich/{job.id}/propositions/{first_id}")
    assert by_id.status_code == 200
    body = by_id.json()
    assert [p["id"] for p in body["propositions"]] == [first_id]
    assert body["propositions"][0]["content_iri"] == iri
    assert body["source_uri"] == document_source_uri(TEXT)

    for ref in (quote(iri, safe=""), iri):
        by_iri = client.get(f"/enrich/{job.id}/propositions/{ref}")
        assert by_iri.status_code == 200, ref
        matches = by_iri.json()["propositions"]
        assert len(matches) == 2
        assert {p["proposition_type"] for p in matches} == {
            "Factual Statement", "Legal Proposition",
        }
        assert all(p["content_iri"] == iri for p in matches)


def test_lookup_404s(api):
    client, store = api
    job = _write_v3_job(store)
    missing = client.get(f"/enrich/{job.id}/propositions/urn%3Afolio%3Ashard%2F{'0' * 32}")
    assert missing.status_code == 404
    assert missing.json()["detail"] == "Proposition not found"
    other = Job()
    assert client.get(f"/enrich/{other.id}/propositions/x").status_code == 404


def test_job_model_migrates_bare_v3_propositions():
    proposition = Proposition(
        id="p", proposition_type="Judicial Legal Conclusion",
        asserter=ActorRef(role="court"), validator=None, disposition="accepted",
    ).model_dump(mode="json")
    proposition["schema_version"] = 3
    proposition.pop("content_iri")
    proposition.pop("axiom_history")
    result = JobResult.model_validate({"propositions": [proposition]})
    assert result.propositions[0].schema_version == 4
    assert result.propositions[0].axiom_history == []


def test_enrich_route_rejects_malformed_source_uri_with_422(api):
    client, _ = api
    response = client.post("/enrich", json={"content": "x", "source_uri": "http://[::1"})
    assert response.status_code == 422


def test_lookup_with_slashed_source_uri(api):
    client, store = api
    source = "https://courts.example.gov/opinions/2024/ny/palsgraf-v-lirr"
    job = _write_v3_job(store)
    raw = json.loads(store._job_path(job.id).read_text())
    raw["input"]["source_uri"] = source
    store._job_path(job.id).write_text(json.dumps(raw))
    iri = content_iri(source, "the statute requires notice")
    assert iri != content_iri(document_source_uri(TEXT), "the statute requires notice")

    for ref in (quote(iri, safe=""), iri):
        response = client.get(f"/enrich/{job.id}/propositions/{ref}")
        assert response.status_code == 200, ref
        body = response.json()
        assert body["source_uri"] == source
        assert len(body["propositions"]) == 2
        assert all(p["content_iri"] == iri for p in body["propositions"])
