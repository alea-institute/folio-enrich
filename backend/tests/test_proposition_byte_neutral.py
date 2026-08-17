"""Characterization proof for proposition extraction's default-off contract.

Regenerate intentionally with::

    FOLIO_REGEN_PROPOSITION_BASELINE=1 pytest tests/test_proposition_byte_neutral.py -q
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import tempfile
import zipfile
from io import BytesIO
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator
from uuid import UUID

import pytest

from app.config import settings
from app.models.document import DocumentInput
from app.models.job import Job, JobStatus
from app.pipeline.orchestrator import PipelineOrchestrator, TaskLLMs
from app.pipeline.stages.ingestion_stage import IngestionStage
from app.pipeline.stages.normalization_stage import NormalizationStage
from app.services.export.registry import get_exporter, list_formats
from app.services.streaming.sse import job_event_stream
from app.storage.job_store import JobStore
from eval.synthetic_runner import PINNED_FLAGS


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "proposition_baseline"
FIXED_JOB_ID = UUID("d3e79092-f12a-5d3b-91e3-e171c7263277")
FIXED_TIME = datetime(2025, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
INPUT_TEXT = "The short memorandum discusses ordinary procedure."
UUID_RE = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-"
    r"[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}\b"
)


@contextmanager
def _deterministic_settings() -> Iterator[None]:
    pinned = {**PINNED_FLAGS, "folio_auto_update": False}
    previous = {name: getattr(settings, name) for name in pinned}
    try:
        for name, value in pinned.items():
            setattr(settings, name, value)
        yield
    finally:
        for name, value in previous.items():
            setattr(settings, name, value)


def _canonicalize_job(job: Job) -> Job:
    """Replace run-generated UUIDs/times while preserving cross references."""
    payload = job.model_dump(mode="json")
    uuid_map: dict[str, str] = {str(job.id): str(FIXED_JOB_ID)}

    def visit(value: Any) -> Any:
        if isinstance(value, dict):
            return {key: visit(item) for key, item in value.items()}
        if isinstance(value, list):
            return [visit(item) for item in value]
        if isinstance(value, str):
            if UUID_RE.fullmatch(value):
                if value not in uuid_map:
                    ordinal = len(uuid_map)
                    uuid_map[value] = f"00000000-0000-5000-8000-{ordinal:012d}"
                return uuid_map[value]
            try:
                parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                return value
            if parsed.tzinfo is not None:
                return FIXED_TIME.isoformat().replace("+00:00", "Z")
        return value

    return Job.model_validate(visit(payload))


def _as_bytes(value: Any) -> bytes:
    if isinstance(value, bytes):
        return value
    if isinstance(value, str):
        return value.encode("utf-8")
    if hasattr(value, "getvalue"):
        return value.getvalue()
    raise TypeError(f"Unsupported exporter output: {type(value)!r}")


def _stable_export_bytes(fmt: str, value: Any) -> bytes:
    content = _as_bytes(value)
    if fmt != "excel":
        return content
    # XLSX is a ZIP container whose member headers otherwise carry wall-clock
    # timestamps. Repacking changes no workbook payload, only container metadata.
    source = BytesIO(content)
    target = BytesIO()
    with zipfile.ZipFile(source) as zin, zipfile.ZipFile(
        target, "w", compression=zipfile.ZIP_DEFLATED
    ) as zout:
        for name in sorted(zin.namelist()):
            info = zipfile.ZipInfo(name, date_time=(2025, 1, 2, 3, 4, 4))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = zin.getinfo(name).external_attr
            payload = zin.read(name)
            if name == "docProps/core.xml":
                payload = re.sub(
                    rb"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z",
                    b"2025-01-02T03:04:05Z",
                    payload,
                )
            zout.writestr(info, payload)
    return target.getvalue()


async def _capture() -> tuple[dict[str, bytes], bytes, bytes]:
    with _deterministic_settings(), tempfile.TemporaryDirectory(
        prefix="folio-proposition-baseline-"
    ) as temp:
        store = JobStore(base_dir=Path(temp) / "jobs")
        stages = [IngestionStage(), NormalizationStage()]
        # The import deliberately remains optional so this same characterization
        # test runs on the pristine pre-U2 tree and after U2 adds the stage.
        try:
            from app.pipeline.stages.proposition_stage import EarlyPropositionStage
        except ModuleNotFoundError:
            pass
        else:
            stages.append(EarlyPropositionStage(llm=None))
        pipeline = PipelineOrchestrator(store, stages=stages)
        job = Job(id=FIXED_JOB_ID, created_at=FIXED_TIME, updated_at=FIXED_TIME,
                  input=DocumentInput(content=INPUT_TEXT))
        job = await pipeline.run(job)
        assert job.status == JobStatus.COMPLETED, job.error
        job = _canonicalize_job(job)
        await store.save(job)

        exports = {
            fmt: _stable_export_bytes(fmt, get_exporter(fmt).export(job))
            for fmt in sorted(list_formats())
        }
        events = [event async for event in job_event_stream(job.id, store, poll_interval=0)]
        sse = json.dumps(events, sort_keys=True, separators=(",", ":")).encode()
        job_json = json.dumps(
            job.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
        ).encode()
        return exports, sse, job_json


def _write_fixtures(exports: dict[str, bytes], sse: bytes, job_json: bytes) -> None:
    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    for path in FIXTURE_DIR.iterdir():
        if path.is_file():
            path.unlink()
    for fmt, content in exports.items():
        (FIXTURE_DIR / f"export.{fmt}").write_bytes(content)
    (FIXTURE_DIR / "sse.json").write_bytes(sse)
    (FIXTURE_DIR / "job.json").write_bytes(job_json)


@pytest.mark.asyncio
@pytest.mark.timeout(180)
async def test_pipeline_is_byte_neutral_when_propositions_are_disabled() -> None:
    exports, sse, job_json = await _capture()
    if os.environ.get("FOLIO_REGEN_PROPOSITION_BASELINE") == "1":
        _write_fixtures(exports, sse, job_json)

    assert FIXTURE_DIR.is_dir(), "regenerate the proposition baseline fixtures"
    for fmt, content in exports.items():
        assert content == (FIXTURE_DIR / f"export.{fmt}").read_bytes(), fmt
    assert sse == (FIXTURE_DIR / "sse.json").read_bytes()

    expected = json.loads((FIXTURE_DIR / "job.json").read_bytes())
    actual = json.loads(job_json)
    if "propositions" not in expected.get("result", {}):
        assert actual["result"].pop("propositions", []) == []
    assert actual == expected


@pytest.mark.asyncio
@pytest.mark.timeout(180)
@pytest.mark.parametrize("enabled", [False, True])
async def test_production_parallel_path_honors_proposition_flag(
    monkeypatch, tmp_path, enabled
) -> None:
    monkeypatch.setattr(settings, "proposition_extraction_enabled", enabled)
    store = JobStore(base_dir=tmp_path / "jobs")
    pipeline = PipelineOrchestrator(store, llm=None, task_llms=TaskLLMs())
    # Construct the same production config and exercise _run_parallel, while
    # removing unrelated enrichment work so this focused wiring test stays fast.
    config = pipeline._config
    assert config is not None
    config.entity_ruler = None
    config.early_individual = None
    config.early_property = None
    config.early_triple = None
    config.document_type = None
    config.post_parallel = []
    job = Job(input=DocumentInput(
        content="Plaintiff contends the statute requires notice."
    ))

    job = await pipeline.run(job)

    assert job.status == JobStatus.COMPLETED, job.error
    assert bool(job.result.propositions) is enabled
    events = [
        event async for event in job_event_stream(job.id, store, poll_interval=0)
    ]
    proposition_events = [
        event for event in events if event["event"] == "proposition_added"
    ]
    assert bool(proposition_events) is enabled


if __name__ == "__main__":
    os.environ["FOLIO_REGEN_PROPOSITION_BASELINE"] = "1"
    asyncio.run(_capture())
