from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.models.annotation import Annotation, ConceptMatch, Span
from app.models.job import Job, JobStatus
from eval import synthetic_runner


class _FakePipeline:
    async def run(self, job: Job) -> Job:
        text = job.input.content
        iri = f"https://example.test/{text.split()[0].lower()}"
        job.result.annotations = [
            Annotation(
                span=Span(start=0, end=len(text), text=text),
                concepts=[ConceptMatch(concept_text=text, folio_iri=iri, state="confirmed")],
                state="confirmed",
            )
        ]
        job.result.metadata[synthetic_runner.SNAPSHOT_METADATA_KEY] = {
            name: [iri] for name in synthetic_runner.STAGE_NAMES
        }
        job.status = JobStatus.COMPLETED
        return job


def _write_items(path: Path) -> None:
    rows = [
        {"item_id": "b", "text": "Court order", "segments": ["Court order"]},
        {"item_id": "a", "text": "Legal motion", "segments": ["Legal motion"]},
    ]
    path.write_text("".join(json.dumps(row) + "\n" for row in rows))


@pytest.mark.asyncio
async def test_contract_shape_and_determinism(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    items = tmp_path / "items.jsonl"
    first = tmp_path / "first.jsonl"
    second = tmp_path / "second.jsonl"
    _write_items(items)
    monkeypatch.setattr(synthetic_runner, "_make_pipeline", lambda _: _FakePipeline())

    await synthetic_runner.run(items, first, lane="deterministic")
    await synthetic_runner.run(items, second, lane="deterministic")

    assert first.read_bytes() == second.read_bytes()
    rows = [json.loads(line) for line in first.read_text().splitlines()]
    assert rows[0]["kind"] == "synthetic-stack-run"
    assert rows[0]["stack"] == "folio-enrich"
    assert rows[0]["lane"] == "deterministic"
    assert isinstance(rows[0]["folio_resolve_version"], str)
    assert isinstance(rows[0]["folio_python_version"], str)
    assert rows[0]["config"]["embedding_disabled"] is True
    assert rows[0]["config"]["contextual_rerank_enabled"] is False
    assert rows[1] == {
        "item_id": "b",
        "iris": ["https://example.test/court"],
        "stages": {name: ["https://example.test/court"] for name in synthetic_runner.STAGE_NAMES},
    }


@pytest.mark.asyncio
async def test_temp_jobs_leave_repo_unchanged(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    items = tmp_path / "items.jsonl"
    output = tmp_path / "out.jsonl"
    _write_items(items)
    monkeypatch.setattr(synthetic_runner, "_make_pipeline", lambda _: _FakePipeline())
    before = {p.relative_to(tmp_path) for p in tmp_path.rglob("*")}
    await synthetic_runner.run(items, output, lane="deterministic")
    after = {p.relative_to(tmp_path) for p in tmp_path.rglob("*")}
    assert after - before == {Path("out.jsonl")}


def test_malformed_items_file_exits_nonzero(tmp_path: Path):
    items = tmp_path / "bad.jsonl"
    items.write_text('{"item_id":"x","text":"missing segments"}\n')
    with pytest.raises(SystemExit) as exc:
        synthetic_runner.main(["--items", str(items), "--out", str(tmp_path / "out.jsonl")])
    assert exc.value.code != 0

