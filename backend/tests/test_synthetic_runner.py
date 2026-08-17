from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.models.annotation import Annotation, ConceptMatch, Span
from app.models.job import Job, JobStatus
from tests.helpers import FakeLLMProvider
from eval import synthetic_runner


class _FakePipeline:
    def __init__(self, stage_names=synthetic_runner.STAGE_NAMES):
        self.stage_names = stage_names

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
            name: [iri] for name in self.stage_names
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


@pytest.mark.asyncio
async def test_llm_on_lane_includes_llm_stages(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    items = tmp_path / "items.jsonl"
    output = tmp_path / "out.jsonl"
    deterministic_output = tmp_path / "deterministic.jsonl"
    _write_items(items)
    llm = FakeLLMProvider()
    llm.api_key = "secret-sentinel-that-must-not-appear"
    real_pipeline = synthetic_runner._make_llm_pipeline(tmp_path / "jobs", llm)
    config = real_pipeline._config
    assert config is not None
    configured_stages = [
        *config.pre_parallel,
        config.entity_ruler,
        config.llm_concept,
        config.early_individual,
        config.early_property,
        config.early_proposition,
        config.early_triple,
        config.document_type,
        *config.post_parallel,
    ]
    llm_stage_names = tuple(stage.name for stage in configured_stages if stage is not None)
    assert "llm_concept_identification" in llm_stage_names
    assert "metadata" in llm_stage_names
    monkeypatch.setattr(
        synthetic_runner,
        "_make_llm_pipeline",
        lambda _jobs_dir, provider: _FakePipeline(llm_stage_names),
    )
    monkeypatch.setattr(synthetic_runner, "_make_pipeline", lambda _: _FakePipeline())

    await synthetic_runner.run(items, output, lane="llm-on", llm=llm)
    await synthetic_runner.run(items, deterministic_output, lane="deterministic")

    rows = [json.loads(line) for line in output.read_text().splitlines()]
    deterministic_rows = [
        json.loads(line) for line in deterministic_output.read_text().splitlines()
    ]
    assert rows[0]["lane"] == "llm-on"
    assert rows[0]["config"]["llm_provider"] == "FakeLLMProvider"
    assert rows[0]["config"]["llm_model"] == "fake-model"
    assert rows[0]["config"]["contextual_rerank_enabled"] is False
    assert "secret-sentinel-that-must-not-appear" not in output.read_text()
    assert set(rows[1]["stages"]) != set(deterministic_rows[1]["stages"])
    assert "llm_concept_identification" in rows[1]["stages"]


def test_llm_on_without_provider_env_exits_nonzero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    items = tmp_path / "items.jsonl"
    _write_items(items)
    monkeypatch.delenv("FOLIO_ENRICH_LLM_PROVIDER", raising=False)
    for key in synthetic_runner.PROVIDER_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)

    with pytest.raises(SystemExit) as exc:
        synthetic_runner.main([
            "--items", str(items), "--out", str(tmp_path / "out.jsonl"), "--llm-on"
        ])

    assert exc.value.code != 0
    assert "owner-run lane: provider env not configured" in capsys.readouterr().err
