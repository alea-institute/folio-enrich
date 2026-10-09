"""Shared-schema ``propositions`` / ``propositions-ndjson`` exports."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from app.config import settings
from app.models.document import CanonicalText, DocumentInput
from app.models.job import Job, JobResult, JobStatus
from app.pipeline.stages.proposition_stage import EarlyPropositionStage
from app.services.export.propositions_exporter import app_version
from app.services.export.registry import get_exporter, list_formats
from app.storage.job_store import JobStore
from fastapi.testclient import TestClient
from folio_propositions import (
    SCHEMA_VERSION,
    PropositionDocumentRecord,
    content_iri,
    document_source_uri,
)

from tests.test_proposition_content_identity import TEXT, _write_v3_job

SOURCE = "https://example.org/opinions/notice"
GOLD_MANIFEST = Path(__file__).resolve().parents[1] / "eval/gold/propositions/manifest.json"


async def _extracted_job(monkeypatch, source_uri: str | None = None) -> Job:
    monkeypatch.setattr(settings, "proposition_extraction_enabled", True)
    job = Job(
        status=JobStatus.COMPLETED,
        input=DocumentInput(content=TEXT, filename="notice.txt", source_uri=source_uri),
        result=JobResult(canonical_text=CanonicalText(full_text=TEXT)),
    )
    return await EarlyPropositionStage(llm=None).execute(job)


def test_formats_registered_with_content_types():
    assert {"propositions", "propositions-ndjson"} <= set(list_formats())
    assert get_exporter("propositions").content_type == "application/json"
    assert get_exporter("propositions-ndjson").content_type == "application/x-ndjson"


@pytest.mark.asyncio
async def test_export_validates_against_library_record(monkeypatch):
    job = await _extracted_job(monkeypatch, source_uri=SOURCE)
    payload = json.loads(get_exporter("propositions").export(job))

    # model_validate runs the record's content_iri cross-check against source_uri.
    record = PropositionDocumentRecord.model_validate(payload)
    assert record.schema_version == SCHEMA_VERSION == 4
    assert record.document_id == str(job.id)
    assert record.source_uri == SOURCE
    assert record.generator.tool == "folio-enrich"
    assert record.generator.version == app_version()
    assert record.document_metadata == {
        "job_id": str(job.id),
        "proposition_lexicon_version": job.result.metadata["proposition_lexicon_version"],
        "filename": "notice.txt",
    }
    assert [p.id for p in record.propositions] == [p.id for p in job.result.propositions]
    assert record.propositions
    for proposition in record.propositions:
        assert proposition.content_iri == content_iri(SOURCE, proposition.text)


@pytest.mark.asyncio
async def test_record_cross_check_rejects_tampered_iri(monkeypatch):
    job = await _extracted_job(monkeypatch)
    payload = json.loads(get_exporter("propositions").export(job))
    payload["propositions"][0]["content_iri"] = "urn:folio:shard/" + "0" * 32
    with pytest.raises(ValueError, match="content_iri"):
        PropositionDocumentRecord.model_validate(payload)


@pytest.mark.asyncio
async def test_ndjson_line_structure(monkeypatch):
    job = await _extracted_job(monkeypatch)
    content = get_exporter("propositions-ndjson").export(job)
    assert content.endswith("\n")
    lines = [json.loads(line) for line in content.splitlines()]
    header, rows = lines[0], lines[1:]
    assert header["record_type"] == "header"
    assert "propositions" not in header
    assert header["source_uri"] == document_source_uri(TEXT)
    assert len(rows) == len(job.result.propositions) > 0
    assert all(row["record_type"] == "proposition" for row in rows)
    # Flat lines: the proposition fields sit beside record_type, not nested.
    assert all("proposition" not in row and "proposition_type" in row for row in rows)

    # Reassembling the stream yields the same record as the JSON exporter.
    header.pop("record_type")
    rebuilt = PropositionDocumentRecord.model_validate(
        {**header, "propositions": [{k: v for k, v in row.items() if k != "record_type"} for row in rows]}
    )
    single = PropositionDocumentRecord.model_validate_json(
        get_exporter("propositions").export(job)
    )
    assert rebuilt == single


@pytest.mark.asyncio
async def test_old_v3_job_exports_with_stamped_iris(tmp_path: Path):
    store = JobStore(base_dir=tmp_path / "jobs")
    job = _write_v3_job(store)
    loaded = await store.load(job.id)

    record = PropositionDocumentRecord.model_validate_json(
        get_exporter("propositions").export(loaded)
    )
    expected = content_iri(document_source_uri(TEXT), "the statute requires notice")
    assert [p.content_iri for p in record.propositions] == [expected, expected]
    assert all(p.schema_version == 4 for p in record.propositions)
    assert "proposition_lexicon_version" not in record.document_metadata


def test_gold_job_uses_gold_document_id():
    entry = json.loads(GOLD_MANIFEST.read_text())["opinions"][0]
    job = Job(id=entry["job_id"], input=DocumentInput(content=TEXT),
              result=JobResult(canonical_text=CanonicalText(full_text=TEXT)))
    record = json.loads(get_exporter("propositions").export(job))
    assert record["document_id"] == entry["document_id"]
    job.result.metadata["gold_document_id"] = "explicit-doc"
    assert json.loads(get_exporter("propositions").export(job))["document_id"] == "explicit-doc"


def test_export_route_serves_propositions(tmp_path: Path, monkeypatch):
    import app.api.routes.export as export_mod
    from app.main import app

    store = JobStore(base_dir=tmp_path / "jobs")
    monkeypatch.setattr(export_mod, "_job_store", store)
    job = _write_v3_job(store)
    client = TestClient(app)

    response = client.get(f"/enrich/{job.id}/export", params={"format": "propositions"})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    PropositionDocumentRecord.model_validate(response.json())

    stream = client.get(f"/enrich/{job.id}/export", params={"format": "propositions-ndjson"})
    assert stream.status_code == 200
    assert stream.headers["content-type"].startswith("application/x-ndjson")
    assert json.loads(stream.text.splitlines()[0])["record_type"] == "header"


@pytest.mark.asyncio
async def test_ndjson_lines_follow_insights_parse_rule(monkeypatch):
    """Reproduce folio-insights' parse_ndjson_text rule without importing it.

    For every line: pop ``record_type``; a header kind keeps the rest as the
    record header; a ``proposition`` kind must validate as a
    ``folio_propositions.Proposition`` on its own (flat, not nested).
    """
    from folio_propositions import Proposition

    job = await _extracted_job(monkeypatch)
    content = get_exporter("propositions-ndjson").export(job)
    header = None
    propositions = []
    for line in content.splitlines():
        if not line.strip():
            continue
        obj = json.loads(line)
        kind = obj.pop("record_type", None)
        if kind in {"proposition_document", "document", "record", "header"}:
            assert header is None
            header = obj
        else:
            assert kind == "proposition"
            propositions.append(Proposition.model_validate(obj))
    assert header is not None
    assert len(propositions) == len(job.result.propositions) > 0
    assert all(p.content_iri for p in propositions)
    record = PropositionDocumentRecord.model_validate(
        {**header, "propositions": [p.model_dump(mode="json") for p in propositions]}
    )
    assert record.source_uri == header["source_uri"]
